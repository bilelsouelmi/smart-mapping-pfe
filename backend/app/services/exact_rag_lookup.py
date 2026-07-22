"""
exact_rag_lookup.py

Single source of truth for "look up a field's mapping in the RAG (Qdrant)
knowledge base" — for BOTH directions (MT -> ISO 20022 and ISO 20022 -> MT).

WHY THIS FILE EXISTS:
Before this consolidation, the same kind of lookup was implemented
independently in two places:
  - ai_learning_service.py's _enrich_from_qdrant() (MT -> ISO direction)
  - mappings.py's find_target_for_tag() / find_xpath_for_mt_tag()
Each implementation accumulated its own version of the same root bug
(weak/unfiltered semantic search instead of an exact match, leading to
cross-contamination between unrelated MT types — e.g. an MT103 field
silently getting MT900's or MT202's formula). Fixing one copy never fixed
the other, which is exactly the whack-a-mole pattern that kept recurring
during testing.

From now on, EVERY caller (AI Suggestions, Generate Elements MT->ISO,
Generate Elements ISO->MT) should call the functions in this file instead
of writing its own Qdrant search. Fix it once here, it's correct
everywhere, including for any future MT/ISO pair that gets added.

DESIGN PRINCIPLE: prefer returning "no match" (caller marks field as
pending for manual review) over a confidently wrong match borrowed from a
different message type. There is intentionally NO fallback search without
the mt_type filter anywhere in this file.
"""
from typing import Dict, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


def _get_qdrant():
    """Lazy import to avoid circular imports at module load time."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.services.qdrant_manager import qdrant_manager as qm
    return Filter, FieldCondition, MatchValue, qm


_MULTI_PATH_RE = re.compile(r'\s(AND|OR|or)\s|\s\+\s')


def _looks_like_single_path(path: Optional[str]) -> bool:
    """Some reference files (e.g. MT900_to_camt054.xml) put a human-readable
    description of MULTIPLE targets directly in a SourceField's own
    <TargetPath> tag — e.g. "GrpHdr/MsgId AND Ntfctn/Id" or "Ntry/Amt +
    Ntry/Amt/@Ccy + Ntry/ValDt/Dt + ..." — instead of one real XPath. That
    string was never meant to be machine-parsed; it's documentation of the
    fact that this source field feeds several target fields (which the
    file's FieldMappings/TargetFields already model properly, each with
    its own clean single XPath). Treating it as a literal path produces
    garbage nested elements when set_xpath_value/build_xml_from_dict try to
    build XML out of it. This filters it out so callers fall through to
    the FIELD_MAPPING -> TARGET_FIELD resolution instead, which always
    resolves to one genuine XPath."""
    if not path:
        return False
    return not _MULTI_PATH_RE.search(path)


def _resolve_target_field_tag(qm, Filter, FieldCondition, MatchValue, target_field_id: str,
                               mt_type_lower: Optional[str], iso_target_lower: Optional[str],
                               mapping_id: Optional[str] = None) -> Optional[str]:
    # TARGET_XX ids (like FIELD_XX ids — see lookup_mt_to_iso_all's Step 2
    # mapping_id filter) are only unique WITHIN one dataset file. Two files
    # that legitimately share source_message_type/target_message_type (a
    # forward file and its XML->MT reverse counterpart, e.g.
    # MT202_to_pacs009.xml and pacs009_to_MT202_reverse.xml both declare
    # mt202/pacs.009.001.08) can reuse the same "TARGET_09" id for
    # unrelated fields. Without pinning to the same mapping_id Step 1/2
    # already resolved, this non-deterministically returns whichever
    # file's chunk Qdrant's scroll happens to return first.
    must = [
        FieldCondition(key='chunk_type', match=MatchValue(value='TARGET_FIELD')),
        FieldCondition(key='field_id', match=MatchValue(value=target_field_id))
    ]
    if mt_type_lower:
        must.append(FieldCondition(key='source_message_type', match=MatchValue(value=mt_type_lower)))
    if iso_target_lower:
        must.append(FieldCondition(key='target_message_type', match=MatchValue(value=iso_target_lower)))
    if mapping_id:
        must.append(FieldCondition(key='mapping_id', match=MatchValue(value=mapping_id)))
    try:
        result = qm.client.scroll(
            collection_name=qm.collection_name,
            scroll_filter=Filter(must=must),
            limit=1,
            with_payload=True
        )
        if result[0]:
            return result[0][0].payload.get('field_tag')
    except Exception as e:
        logger.warning(f"TARGET_FIELD resolution failed for {target_field_id}: {e}")
    return None


def lookup_mt_to_iso_all(tag: str, mt_type: Optional[str], iso_target: Optional[str] = None) -> List[Dict]:
    """
    MT -> ISO 20022 direction, returning EVERY target this source field maps
    to — not just one.

    Most reference fields map to a single ISO 20022 element, but some feed
    several from one FieldMapping (e.g. MT202's :32A: -> both Amt/InstdAmt
    AND IntrBkSttlmDt, via a <TargetFields> wrapper with multiple
    <TargetField ref=.../> children). lookup_mt_to_iso() only ever
    surfaced the first one, silently dropping the rest — this is the
    version Generate Elements should use so it can create one
    MappingElement per real target instead of losing all but the first.

    iso_target (e.g. "pacs.009.001.08"), when provided, additionally filters
    on the reference file's target_message_type. This matters because some
    MT types are the *source* of more than one reference file — e.g. both
    MT202_to_pacs009.xml and MT202_to_MT500.xml declare "MT202" as their
    source_message_type and reuse the same internal field_id scheme
    (FIELD_01, FIELD_02, ...). Without this extra filter, a field_tag +
    mt_type match alone can non-deterministically resolve to whichever
    file's chunk Qdrant's scroll happens to return first — e.g. :32A: on an
    MT202->pacs.009 mapping silently getting MT500's target field instead
    of Amt/InstdAmt. Always pass iso_target when the caller knows it.

    Exact lookup chain:
      1. SOURCE_FIELD chunk (field_tag == tag, source_message_type == mt_type)
         -> internal XML field_id (e.g. "FIELD_10"), and target_path if the
            reference file already has it directly on this field.
      2. FIELD_MAPPING chunk (source == that field_id, source_message_type
         == mt_type) -> the authoritative pseudocode/expression formula and
         full compliance/audit/migration metadata for this exact field, plus
         every target it declares (target_all).
      3. For each target not already resolved by step 1, resolve it via the
         TARGET_FIELD chunk referenced by that target's internal id.

    Returns a list of dicts (empty if no exact match), each shaped like:
      {
        "target_path": str,
        "mapping_id": str,
        "mapping_name": str,
        "element_id": str,
        "formula_pseudocode": str,
        "global_variable_refs": [str, ...],
        "audit_requirement": str,
        "compliance_requirement": str,
        "data_privacy": str,
        "migration_note": str,
        "caching_strategy": str,
        "performance_impact": str,
        "has_audit_requirement": bool,
        "has_compliance_requirement": bool,
        "has_migration_note": bool,
      }
    """
    if not tag:
        return []

    try:
        Filter, FieldCondition, MatchValue, qm = _get_qdrant()
    except Exception as e:
        logger.warning(f"Qdrant unavailable for lookup_mt_to_iso({tag}): {e}")
        return []

    mt_type_lower = mt_type.lower().strip() if mt_type else None
    iso_target_lower = iso_target.lower().strip() if iso_target else None
    clean_tag = str(tag).strip()
    tag_variants = [clean_tag, f":{clean_tag.strip(':')}:", f":{clean_tag.strip(':')}"]

    # ── Step 1: SOURCE_FIELD exact lookup ──────────────────────────────────
    src_target_path = None
    src_element_id = None
    src_mapping_id = None
    src_field_id = None
    try:
        for tv in tag_variants:
            must = [
                FieldCondition(key='chunk_type', match=MatchValue(value='SOURCE_FIELD')),
                FieldCondition(key='field_tag', match=MatchValue(value=tv))
            ]
            if mt_type_lower:
                must.append(FieldCondition(key='source_message_type', match=MatchValue(value=mt_type_lower)))
            if iso_target_lower:
                must.append(FieldCondition(key='target_message_type', match=MatchValue(value=iso_target_lower)))
            result = qm.client.scroll(
                collection_name=qm.collection_name,
                scroll_filter=Filter(must=must),
                limit=3,
                with_payload=True
            )
            for point in result[0]:
                if not src_field_id and point.payload.get('field_id'):
                    src_field_id = point.payload.get('field_id')
                    src_mapping_id = src_mapping_id or point.payload.get('mapping_id')
                if point.payload.get('target_path') and _looks_like_single_path(point.payload['target_path']):
                    src_target_path = point.payload['target_path']
                    src_element_id = point.payload.get('element_id')
                    src_mapping_id = point.payload.get('mapping_id')
                    break
            if src_target_path:
                break
    except Exception as e:
        logger.warning(f"SOURCE_FIELD lookup failed for {tag}/{mt_type}: {e}")

    # ── Step 2: exact FIELD_MAPPING lookup via internal field_id ───────────
    field_mapping_meta = None
    if src_field_id:
        try:
            must = [
                FieldCondition(key='chunk_type', match=MatchValue(value='FIELD_MAPPING')),
                FieldCondition(key='source', match=MatchValue(value=src_field_id))
            ]
            if mt_type_lower:
                must.append(FieldCondition(key='source_message_type', match=MatchValue(value=mt_type_lower)))
            if iso_target_lower:
                must.append(FieldCondition(key='target_message_type', match=MatchValue(value=iso_target_lower)))
            if src_mapping_id:
                # field_id ("FIELD_03", ...) is only unique WITHIN one
                # dataset file, not globally — two files can (and now do:
                # MT103_to_pacs008.xml and pacs008_to_MT103_reverse.xml
                # both declare source_message_type=mt103/target_message_
                # type=pacs.008.001.08, so mt_type/iso_target alone can't
                # tell them apart) reuse the same field_id for unrelated
                # fields. Pin the search to the SAME file Step 1's
                # SOURCE_FIELD match came from.
                must.append(FieldCondition(key='mapping_id', match=MatchValue(value=src_mapping_id)))
            result = qm.client.scroll(
                collection_name=qm.collection_name,
                scroll_filter=Filter(must=must),
                limit=1,
                with_payload=True
            )
            if result[0]:
                field_mapping_meta = result[0][0].payload
        except Exception as e:
            logger.warning(f"FIELD_MAPPING lookup failed for {tag}/{mt_type}: {e}")

    if not field_mapping_meta:
        # No exact FIELD_MAPPING chunk — at most return the bare target_path
        # from Step 1 if we have one, with no formula/compliance content.
        if src_target_path:
            return [{
                "target_path": src_target_path,
                "element_id": src_element_id,
                "mapping_id": src_mapping_id,
            }]
        return []

    mapping_formula_obj = field_mapping_meta.get('mapping_formula', {})
    formula_details = mapping_formula_obj.get('details', {}) if isinstance(mapping_formula_obj, dict) else {}
    global_vars = formula_details.get('global_variables', {})

    shared_fields = {
        "element_id": src_element_id,
        "mapping_id": field_mapping_meta.get('mapping_id'),
        "mapping_name": field_mapping_meta.get('mapping_name'),
        "formula_pseudocode": mapping_formula_obj.get('pseudocode') if isinstance(mapping_formula_obj, dict) else None,
        "global_variable_refs": list(global_vars.keys()) if global_vars else [],
        "audit_requirement": field_mapping_meta.get('audit_requirement'),
        "compliance_requirement": field_mapping_meta.get('compliance_requirement'),
        "data_privacy": field_mapping_meta.get('data_privacy'),
        "migration_note": field_mapping_meta.get('migration_note'),
        "caching_strategy": field_mapping_meta.get('caching_strategy'),
        "performance_impact": field_mapping_meta.get('performance_impact'),
        "has_audit_requirement": field_mapping_meta.get('has_audit_requirement', False),
        "has_compliance_requirement": field_mapping_meta.get('has_compliance_requirement', False),
        "has_migration_note": field_mapping_meta.get('has_migration_note', False),
    }

    # ── Step 3: resolve every declared target ───────────────────────────────
    target_ids = field_mapping_meta.get('target_all') or (
        [field_mapping_meta.get('target')] if field_mapping_meta.get('target') else []
    )
    if not target_ids and src_target_path:
        return [{"target_path": src_target_path, **shared_fields}]

    results = []
    for i, target_field_id in enumerate(target_ids):
        resolved_target_path = src_target_path if i == 0 else None
        if not resolved_target_path and target_field_id:
            resolved_target_path = _resolve_target_field_tag(
                qm, Filter, FieldCondition, MatchValue, target_field_id, mt_type_lower, iso_target_lower,
                mapping_id=field_mapping_meta.get('mapping_id')
            )
        if resolved_target_path:
            results.append({"target_path": resolved_target_path, **shared_fields})
    return results


def lookup_mt_to_iso(tag: str, mt_type: Optional[str], iso_target: Optional[str] = None) -> Dict:
    """
    MT -> ISO 20022 direction, single-target convenience wrapper around
    lookup_mt_to_iso_all() — returns only the FIRST resolved target. Used by
    callers that display/store one primary target per field (e.g. AI
    Suggestions' suggestion card). See lookup_mt_to_iso_all()'s docstring
    for the full lookup chain and why iso_target matters.
    """
    if not tag:
        return {}
    results = lookup_mt_to_iso_all(tag, mt_type, iso_target)
    return results[0] if results else {}


def lookup_iso_to_mt(tag: str, mt_type: Optional[str], iso_target: Optional[str] = None) -> Dict:
    """
    ISO 20022 -> MT direction.

    Given a SWIFT field tag (e.g. ":20:" — representing the MT-side field
    that this XML/ISO content corresponds to) and the MT type on the MT
    side (e.g. "MT950"), returns the camt/pacs XPath and formula for that
    field.

    IMPORTANT: this delegates directly to lookup_mt_to_iso(). Both
    directions are answering the exact same underlying question — "given
    this SWIFT tag and this MT type, what ISO 20022 XPath does the
    reference mapping file say it corresponds to?" — via the same
    SOURCE_FIELD -> field_id -> FIELD_MAPPING -> TARGET_FIELD chain that
    every MT->ISO reference file already has natively (SourceField/
    TargetField refs are the core of every <Mapping> element).

    This function used to rely on an optional <SourceMT> back-reference
    tag that only 2 of the 9 reference XML files actually had (MT900,
    MT910) — meaning ISO->MT silently failed for the other 7 message
    types and fell through to LLM hallucination. Reusing lookup_mt_to_iso
    here makes ISO->MT direction work for any reference file, with no
    dependency on that optional tag at all.
    """
    if not tag:
        return {}

    result = lookup_mt_to_iso(tag, mt_type, iso_target)
    if not result:
        return {}

    return {
        "target_path": result.get("target_path"),
        "formula_pseudocode": result.get("formula_pseudocode"),
    }


def lookup_iso_to_mt_all(tag: str, mt_type: Optional[str], iso_target: Optional[str] = None) -> List[Dict]:
    """Multi-target counterpart to lookup_iso_to_mt(), mirroring
    lookup_mt_to_iso_all() — see that function's docstring for why a single
    source field can resolve to more than one target."""
    if not tag:
        return []
    return [
        {"target_path": r.get("target_path"), "formula_pseudocode": r.get("formula_pseudocode")}
        for r in lookup_mt_to_iso_all(tag, mt_type, iso_target)
    ]


def semantic_similar_formulas(
    query_text: str,
    mt_type: Optional[str],
    iso_target: Optional[str] = None,
    n_results: int = 3,
) -> List[str]:
    """
    Everything else in this file is an EXACT lookup (a field either has a
    dataset-authored formula or it doesn't). This is the one genuinely
    semantic search here — used to ground the LLM fallback
    (ai_learning_service._suggest_via_llm) for a field that has NO exact
    match, by finding the closest existing formulas as worked examples
    instead of asking the LLM to invent an answer from the field's bare
    name alone.

    Still filtered to the same (mt_type, iso_target) pair as every exact
    lookup above — a "similar" field from an unrelated message type is
    exactly the cross-contamination this whole module exists to prevent
    (see file docstring), just via vector distance instead of a stale
    literal-string cache.

    Returns the raw chunk `content` text (human-readable, already includes
    the pseudocode formula) for the top matches — cheap to drop straight
    into an LLM prompt, no further parsing needed.
    """
    if not query_text:
        return []
    _, _, _, qm = _get_qdrant()
    filter_metadata = {"chunk_type": "FIELD_MAPPING"}
    if mt_type:
        filter_metadata["source_message_type"] = mt_type.lower()
    if iso_target:
        filter_metadata["target_message_type"] = iso_target.lower()
    try:
        result = qm.search(query_text, n_results=n_results, filter_metadata=filter_metadata)
        if not result or not result.get("documents"):
            return []
        return [doc for doc in result["documents"][0] if doc]
    except Exception as e:
        logger.warning(f"semantic_similar_formulas failed for '{query_text}': {e}")
        return []