from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import logging

from app.core.deps import get_current_user
from app.models.user import User
from app.database import get_db
from app.models.mapping import Mapping, MappingElement, MappingStatus
from app.models.message_description import MessageDescription
from app.models.message_description_element import MessageDescriptionElement
from app.models.mapping_formula import MappingFormula
from app.services.audit_service import log_action
from app.schemas.mapping import (
    MappingCreate,
    MappingUpdate,
    MappingResponse,
    MappingListResponse,
    MappingElementCreate,
    MappingElementUpdate,
    MappingElementResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# MAPPING CRUD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/", response_model=List[MappingListResponse])
def get_mappings(
    message_description_id: int = None,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Mapping)
    if message_description_id:
        query = query.filter(Mapping.message_description_id == message_description_id)
    mappings = query.offset(skip).limit(limit).all()
    result = []
    for m in mappings:
        result.append(MappingListResponse(
            id=m.id,
            message_description_id=m.message_description_id,
            name=m.name,
            source=m.source,
            target=m.target,
            status=m.status,
            created_at=m.created_at,
            element_count=len(m.mapping_elements)
        ))
    return result


@router.get("/{mapping_id}", response_model=MappingResponse)
def get_mapping(
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found")
    return mapping


@router.post("/", response_model=MappingResponse, status_code=status.HTTP_201_CREATED)
def create_mapping(
    mapping: MappingCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == mapping.message_description_id
    ).first()
    if not message_desc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {mapping.message_description_id} not found")

    mapping_data = mapping.model_dump()
    # Maker-checker, same reasoning as MessageDescription approval: a
    # mapping drives real Transforms, so it shouldn't be usable until
    # someone has actually reviewed its formulas. An admin's own creation
    # can go straight to active (self-approval, same carve-out MD approval
    # uses) — anyone else's always starts in draft regardless of what
    # status they send, and needs a separate admin approval afterward.
    if not current_user.is_admin:
        mapping_data['status'] = MappingStatus.DRAFT

    db_mapping = Mapping(**mapping_data)
    db.add(db_mapping)
    db.commit()
    db.refresh(db_mapping)
    logger.info(f"Mapping created: id={db_mapping.id} source={db_mapping.source} target={db_mapping.target}")
    return db_mapping


@router.put("/{mapping_id}", response_model=MappingResponse)
def update_mapping(
    mapping_id: int,
    mapping: MappingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not db_mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found")

    update_data = mapping.model_dump(exclude_unset=True)

    # Same maker-checker gate as creation: activating a mapping (draft/
    # inactive -> active) needs an admin, since that's the point where it
    # becomes usable for real Transforms (see the status check in
    # transform_with_mapping). Any other field a non-admin can already
    # touch freely.
    becoming_active = update_data.get('status') == MappingStatus.ACTIVE and db_mapping.status != MappingStatus.ACTIVE
    if becoming_active and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only an administrator can activate a Mapping."
        )

    for field, value in update_data.items():
        setattr(db_mapping, field, value)

    db.commit()
    db.refresh(db_mapping)

    if becoming_active:
        log_action(
            db, current_user, action="approve", entity_type="Mapping",
            entity_id=db_mapping.id,
            details=f"Activated mapping \"{db_mapping.name}\" ({db_mapping.source} → {db_mapping.target})"
        )
        db.commit()

    return db_mapping


@router.delete("/{mapping_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping(
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not db_mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found")
    db.delete(db_mapping)
    db.commit()
    return None


# ══════════════════════════════════════════════════════════════════════════════
# MAPPING ELEMENT CRUD
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/{mapping_id}/elements", response_model=List[MappingElementResponse])
def get_mapping_elements(
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found")
    return mapping.mapping_elements


@router.post("/{mapping_id}/elements", response_model=MappingElementResponse, status_code=status.HTTP_201_CREATED)
def create_mapping_element(
    mapping_id: int,
    element: MappingElementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found")

    if element.msg_desc_element_id:
        el = db.query(MessageDescriptionElement).filter(
            MessageDescriptionElement.id == element.msg_desc_element_id
        ).first()
        if not el:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MessageDescriptionElement {element.msg_desc_element_id} not found")

    if element.mapping_formula_id:
        formula = db.query(MappingFormula).filter(
            MappingFormula.id == element.mapping_formula_id
        ).first()
        if not formula:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                detail=f"MappingFormula {element.mapping_formula_id} not found")

    element_data = element.model_dump()
    element_data['mapping_id'] = mapping_id
    db_element = MappingElement(**element_data)
    db.add(db_element)
    db.commit()
    db.refresh(db_element)
    return db_element


@router.put("/{mapping_id}/elements/{element_id}", response_model=MappingElementResponse)
def update_mapping_element(
    mapping_id: int,
    element_id: int,
    element: MappingElementUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_element = db.query(MappingElement).filter(
        MappingElement.id == element_id,
        MappingElement.mapping_id == mapping_id
    ).first()
    if not db_element:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingElement {element_id} not found")

    update_data = element.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_element, field, value)

    db.commit()
    db.refresh(db_element)
    return db_element


@router.delete("/{mapping_id}/elements/{element_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mapping_element(
    mapping_id: int,
    element_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_element = db.query(MappingElement).filter(
        MappingElement.id == element_id,
        MappingElement.mapping_id == mapping_id
    ).first()
    if not db_element:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MappingElement {element_id} not found")
    db.delete(db_element)
    db.commit()
    return None


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY: Get available sources and targets from MessageDescriptions
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/sources-targets/available")
def get_available_sources_targets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retourne les types MT et ISO 20022 disponibles, combinés dans une seule
    liste utilisée pour les deux dropdowns (Source et Target), afin de
    permettre la création de mappings dans les deux sens :
      - MT -> ISO 20022 (ex: MT900 -> camt.054.001.08)
      - ISO 20022 -> MT (ex: camt.054.001.08 -> MT900)
    """
    mds = db.query(
        MessageDescription.mt_type,
        MessageDescription.iso_target
    ).filter(
        MessageDescription.mt_type != None,
        MessageDescription.iso_target != None
    ).distinct().all()

    mt_types = sorted(set(md.mt_type for md in mds if md.mt_type))
    iso_types = sorted(set(md.iso_target for md in mds if md.iso_target))

    combined = mt_types + iso_types

    return {
        "sources": combined,
        "targets": combined,
        "mt_types": mt_types,
        "iso_types": iso_types,
    }


# ══════════════════════════════════════════════════════════════════════════════
# AUTO-GENERATE MAPPING ELEMENTS
#
# PRIORITY ORDER (the actual fix for this turn):
#   1. Accepted MappingFormula (Step 1 of the workflow) — the user reviewed
#      and accepted these in the Mapping Formula / AI Suggestions screen, so
#      they are the MOST TRUSTED source and always win when present.
#   2. RAG exact lookup via Qdrant (SOURCE_FIELD/TARGET_FIELD chunk_type,
#      filtered by exact field_tag/source_mt) — used to FILL GAPS for fields
#      that have no accepted formula yet.
#   3. LLM single-field fallback — only as a last resort, only for fields
#      that still have nothing after steps 1 and 2.
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/{mapping_id}/generate-elements")
def generate_mapping_elements(
    mapping_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto-génère les MappingElements. Les formules acceptées par l'utilisateur
    (MappingFormula, issues de l'écran Mapping Formula / AI Suggestions) sont
    la source prioritaire — c'est le but explicite du workflow en 2 étapes
    (Step 1: suggestions IA + revue utilisateur, Step 2: génération des
    éléments de mapping à partir de ces formules validées). Le RAG Qdrant et
    le LLM ne servent qu'à compléter les champs pour lesquels aucune formule
    n'a encore été acceptée.
    """
    # NOTE: direct qdrant_manager import removed — RAG lookups now go
    # through app.services.exact_rag_lookup (lookup_mt_to_iso/lookup_iso_to_mt),
    # the single shared implementation used by every caller in the project.
    # NOTE: LLM fallback removed (see PRIORITY 3 comment below) — no longer
    # need an LLMService instance here.

    mapping = db.query(Mapping).filter(Mapping.id == mapping_id).first()
    if not mapping:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mapping {mapping_id} not found")

    message_desc = db.query(MessageDescription).filter(
        MessageDescription.id == mapping.message_description_id
    ).first()
    if not message_desc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"MessageDescription {mapping.message_description_id} not found")

    def get_block4_elements(md_id):
        block4 = db.query(MessageDescriptionElement).filter(
            MessageDescriptionElement.message_description_id == md_id,
            MessageDescriptionElement.field_tag == 'block4'
        ).first()
        if block4:
            return db.query(MessageDescriptionElement).filter(
                MessageDescriptionElement.message_description_id == md_id,
                MessageDescriptionElement.parent_id == block4.id
            ).all()
        return []

    # ── Determine which mt_type this mapping actually needs, from the
    # mapping's OWN source/target fields — not from message_desc.mt_type,
    # which could itself be wrong if message_description_id was previously
    # mislinked to an unrelated file (e.g. a "camt.053 to MT950" mapping
    # accidentally pointing at an MT900 upload). This is the real fix: a
    # mapping with elements at the wrong mt_type was being silently trusted
    # just because elements existed, never reaching the fallback search at
    # all (since that only triggered when elements were MISSING, not when
    # they were simply the wrong type).
    expected_mt_type = (
        mapping.target if not mapping.source.upper().startswith('MT') else mapping.source
    )
    is_iso_to_mt = not mapping.source.upper().startswith('MT')

    # Target the NEWEST MessageDescription of the correct mt_type that
    # actually HAS elements (i.e. Generate MD was run on it). Generate MD
    # is still a hard prerequisite — Generate Elements always fails if NO
    # upload of this mt_type has ever had it run — but it no longer has to
    # be the literal latest upload. This endpoint has no way to know which
    # specific file the user means (it's called with no file context, just
    # the mapping id), so "always use the absolute newest row" meant any
    # incidental re-upload of the same file (e.g. testing Transform, or
    # clicking upload twice) silently became "the" file and blocked every
    # future Generate Elements click until Generate MD was re-run on that
    # throwaway duplicate — even though a perfectly good MD already existed.
    #
    # A candidate's mt_type matching isn't enough on its own: an XML->MT
    # mapping (is_iso_to_mt=True, e.g. pacs.008 -> MT103) and its MT->XML
    # counterpart share the exact same mt_type/iso_target pair, so an
    # unrelated MT103 *text* upload (e.g. one used to test round-trip
    # validation) can legitimately share mt_type='MT103' with a pacs.008
    # XML upload while being structurally incompatible — its elements are
    # MT-tag field_tags (":20:", ...), not the XML dotted paths this
    # mapping's formulas are written against. Filtering candidates by
    # file_type keeps each direction looking only at its own kind of
    # upload.
    newest_md = None
    newest_with_elements = None
    if expected_mt_type:
        candidates = db.query(MessageDescription).filter(
            MessageDescription.mt_type == expected_mt_type
        ).order_by(MessageDescription.id.desc()).all()
        if is_iso_to_mt:
            candidates = [md for md in candidates if md.file_type == 'XML_ISO20022']
        else:
            candidates = [md for md in candidates if md.file_type != 'XML_ISO20022']
        if candidates:
            newest_md = candidates[0]
        for md in candidates:
            if get_block4_elements(md.id):
                newest_with_elements = md
                break

    if not newest_md:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No {expected_mt_type} file has been uploaded yet. Upload a file first.")

    if not newest_with_elements:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{newest_md.file_name}' hasn't had its Message Description generated yet. "
                   f"Go to Message Descriptions and click 'Generate MD' before generating mapping elements.")

    if newest_with_elements.id != newest_md.id:
        logger.info(
            f"Newest {expected_mt_type} upload (MD {newest_md.id}, '{newest_md.file_name}') "
            f"has no elements yet; using MD {newest_with_elements.id} "
            f"('{newest_with_elements.file_name}') instead."
        )
    newest_md = newest_with_elements
    elements = get_block4_elements(newest_md.id)

    if mapping.message_description_id != newest_md.id:
        logger.info(
            f"Mapping {mapping_id} relinked from message_description_id "
            f"{mapping.message_description_id} to {newest_md.id} (most recent {expected_mt_type} upload)"
        )
        mapping.message_description_id = newest_md.id
        db.commit()
        message_desc = newest_md

    # ── Get accepted MappingFormulas (Step 1 of the workflow) for this MT type ─
    # Ordered most-recent-first so that if duplicate/stale formulas exist for
    # the same field (e.g. accepted again after a fix, or re-accepted after
    # correcting an earlier mistake), the NEWEST one always wins rather than
    # depending on unordered DB row order.
    formulas = db.query(MappingFormula).filter(
        MappingFormula.message_description_id.in_(
            [md.id for md in db.query(MessageDescription).filter(
                MessageDescription.mt_type == expected_mt_type
            ).all()]
        )
    ).order_by(MappingFormula.id.desc()).all()

    # For an XML->MT mapping, a valid target_path is always a bare F-tag
    # ("F20", "F50K", ...) — see _transform_xml_to_mt_with_mapping, which
    # only ever consumes targets shaped that way. Formulas accepted before
    # the RAG-target-priority fix (ai_learning_service.suggest_field_mapping
    # used to let ElementMatcher's fuzzy guess block the exact RAG target)
    # were saved with a leftover ISO dotted-path target like
    # "/Document/FIToFICstmrCdtTrf/GrpHdr/MsgId" instead — structurally
    # invalid for this direction. Left in, they don't break Transform (it
    # already skips any target_field not starting with "F"), but they
    # dedup as DIFFERENT target_paths from the correct F-tag formula for
    # the same source field, so both survive into formula_map and both
    # become MappingElements — cluttering the table with rows that will
    # never resolve. Filtering them out here means Generate Elements
    # self-heals stale mappings instead of needing a one-off DB cleanup.
    import re as _re
    valid_f_tag = _re.compile(r'^F[A-Z0-9]+$')

    # formula_map[key] is a LIST, not a single formula — a source field can
    # have multiple accepted formulas targeting different ISO elements (e.g.
    # :50K: -> Dbtr.Nm and, separately, :50K: -> DbtrAcct.Id.IBAN). Dedup by
    # target_path within each key so re-accepting/editing the same target
    # doesn't create duplicates — newest wins there, per the ordering above.
    formula_map = {}
    for f in formulas:
        if is_iso_to_mt and f.target_path and not valid_f_tag.match(f.target_path):
            continue
        for key in (f.source_path, f.source_path.strip(':')):
            bucket = formula_map.setdefault(key, [])
            if not any(existing.target_path == f.target_path for existing in bucket):
                bucket.append(f)

    name_to_tag = {
        'transaction reference number': ':20:', 'transaction reference': ':20:',
        'related reference': ':21:',
        'bank operation code': ':23B:',
        'account identification': ':25:',
        'statement number': ':28C:', 'statement number / sequence number': ':28C:',
        'value date, currency code, amount': ':32A:',
        'value date/currency/amount': ':32A:',
        'ordering customer (bic option)': ':50A:',
        'ordering customer (name and address option)': ':50K:',
        'ordering customer': ':50K:',
        'ordering institution': ':52A:',
        'intermediary institution': ':56A:',
        'beneficiary customer': ':59:',
        'beneficiary': ':59:',
        'opening balance': ':60F:', 'intermediate opening balance': ':60M:',
        'statement line': ':61:',
        'closing balance': ':62F:', 'intermediate closing balance': ':62M:',
        'remittance information': ':70:',
        'details of charges': ':71A:',
        'charge bearer': ':71A:',
        'sender to receiver information': ':72:',
        'information to account owner': ':86:',
        'date/time indication': ':13D:',
    }

    def resolve_tag(el):
        """
        Resolve the SWIFT tag (:20:, :25:, ...) for this element, regardless
        of direction. Skips synthetic internal keys like ':32A_date:' or
        ':32A_amount:' that the ISO parser uses internally — these are not
        real SWIFT tags and duplicate their base tag (':32A:'). These often
        appear in `name` rather than `field_tag` since field_tag is empty.
        """
        synthetic_pattern = r'_(date|amount|iban|name):?$'
        if el.field_tag and _re.search(synthetic_pattern, el.field_tag):
            return None
        if el.name and _re.search(synthetic_pattern, el.name):
            return None
        if el.field_tag and el.field_tag.startswith(':'):
            return el.field_tag
        if el.field_tag and '.' in el.field_tag:
            # XML->MT direction: field_tag is a dotted XML path (e.g.
            # "CdtTrfTxInf.Dbtr.Nm"), not a SWIFT tag — returned as-is so
            # formula_map/RAG lookups below can match against it directly.
            return el.field_tag
        name_stripped = (el.name or '').strip()
        if name_stripped.startswith(':') and name_stripped.endswith(':'):
            return name_stripped
        key = name_stripped.lower()
        if key in name_to_tag:
            return name_to_tag[key]
        desc = el.description or ''
        m = _re.search(r':(\d{2}[A-Z]?):', desc)
        if m:
            return f":{m.group(1)}:"
        return None

    db.query(MappingElement).filter(
        MappingElement.mapping_id == mapping_id
    ).delete()

    created = 0
    skipped = 0
    rag_hits = 0
    formula_hits = 0

    for el in elements:
        name = el.name or ""
        tag = resolve_tag(el)

        # A repeated SWIFT tag (":61_1", ":61_2", ...) — swift_txt_parser
        # index-suffixes every occurrence beyond the first (see
        # _parse_tags) and resolve_tag() returns el.field_tag verbatim
        # (single leading colon, NO trailing colon — confirmed against
        # real stored rows: ":61", ":61_1", not ":61:"/":61_1:") — has no
        # dataset/RAG entry of its OWN; the dataset only ever authors the
        # pattern once, against the bare tag (":61"). Falling back to the
        # base tag's formula here is what lets EVERY occurrence of a
        # repeating field (MT940/950's :61:/:86: statement lines) get a
        # real 'mapped' status instead of only the first. The shared
        # expression still only ever says "MT.F61" — resolving that to
        # THIS occurrence's own value at transform time (not always the
        # first) is a separate fix in transform_mapping.py's repeat-group
        # handling.
        base_tag = tag
        repeat_match = _re.match(r'^:(\d{2}[A-Z]?)_(\d+)$', tag or '')
        if repeat_match:
            base_tag = f':{repeat_match.group(1)}'

        formulas_for_tag = None

        # ── PRIORITY 1: Accepted MappingFormula(s) (Step 1, user-reviewed) ────
        # Works for both directions — MappingFormula.source_path/target_path
        # are just strings, and generate_mapping_elements's own
        # expected_mt_type derivation (mapping.source vs mapping.target)
        # already makes the formula_map query direction-agnostic. This used
        # to be MT -> ISO only, back when nothing produced XML -> MT
        # formulas at all; now that XML.<path> pseudocode is a real thing
        # (see _XMLPathRef), gating it out would just silently ignore
        # reviewed XML -> MT formulas the same way the old bug did.
        formulas_for_tag = (
            formula_map.get(tag) or formula_map.get(name) or formula_map.get((tag or '').strip(':')) or
            (formula_map.get(base_tag) or formula_map.get(base_tag.strip(':')) if base_tag != tag else None)
        )

        # results: list of {"target_field": str, "expression": str, "formula_id": Optional[int]}
        # — usually one, but a single source field can feed SEVERAL ISO
        # 20022 elements from the same FieldMapping (e.g. MT202's :32A: ->
        # both Amt/InstdAmt and IntrBkSttlmDt, via a <TargetFields>
        # wrapper). Each becomes its own MappingElement below, sharing the
        # same source tag/expression — evaluate_expression()'s per-target
        # matching picks the right computed value out of that shared
        # multi-statement pseudocode for each one's own target_field.
        results = []
        if formulas_for_tag:
            for f in formulas_for_tag:
                if f.target_path:
                    results.append({"target_field": f.target_path, "expression": f.transformation_rule or "", "formula_id": f.id})
                    formula_hits += 1

        # ── PRIORITY 2: RAG exact lookup — fills the gap if no accepted formula ─
        # Delegates to the SHARED exact_rag_lookup module (one implementation
        # used by every caller in the project: AI Suggestions, and both
        # directions of Generate Elements) instead of a locally duplicated
        # search. This is the consolidation fix: previously each direction
        # had its own independent lookup with its own version of the same
        # cross-contamination bug; now there is exactly one place to get it
        # right, for any current or future MT/ISO pair.
        if not results and tag:
            from app.services.exact_rag_lookup import lookup_mt_to_iso_all, lookup_iso_to_mt_all
            # exact_rag_lookup is keyed by the bare tag too — a repeated
            # occurrence (":61_1:") needs base_tag (":61:") here for the
            # same reason as Priority 1 above.
            rag_lookup_tag = base_tag
            if is_iso_to_mt:
                rag_results = lookup_iso_to_mt_all(rag_lookup_tag, mapping.target, mapping.source)
            else:
                rag_results = lookup_mt_to_iso_all(rag_lookup_tag, mapping.source, mapping.target)
            for r in rag_results:
                if r.get('target_path'):
                    results.append({"target_field": r['target_path'], "expression": r.get('formula_pseudocode', '') or "", "formula_id": None})
            if results:
                rag_hits += 1

        # NOTE: intentionally NO LLM fallback (Priority 3 removed). The LLM
        # was fabricating plausible-looking but wrong XPaths for fields that
        # genuinely have no accepted formula and no exact RAG match (e.g.
        # complex composite fields like MT950's :61: Statement Line, or
        # tags that aren't real fields of this message type at all) —
        # exactly the "confidently wrong" failure mode this whole session's
        # fixes were about avoiding. A field with no real data now honestly
        # stays "pending" for manual review instead of getting a fabricated
        # answer that looks authoritative but isn't.
        if not results:
            results.append({"target_field": "", "expression": "", "formula_id": None})

        for r in results:
            db_element = MappingElement(
                mapping_id=mapping_id,
                msg_desc_element_id=el.id,
                mapping_formula_id=r.get("formula_id"),
                source_field=tag or name,
                source_xpath=f"block4/{tag}" if tag else None,
                target_field=r["target_field"],
                target_xpath=None,
                expression=r["expression"] or None,
                is_mandatory=el.mandatory or False,
                default_value=el.example_value,
                status='mapped' if r["target_field"] else 'pending'
            )
            db.add(db_element)
            if r["target_field"]:
                created += 1
            else:
                skipped += 1

    db.commit()
    logger.info(
        f"Generated {created} mapped + {skipped} pending elements for mapping "
        f"{mapping_id} — {formula_hits} from accepted formulas, {rag_hits} from RAG"
    )

    return {
        "message": f"Generated {created + skipped} mapping elements "
                   f"({formula_hits} from accepted formulas, {rag_hits} from RAG)",
        "mapped": created,
        "pending": skipped,
        "total": created + skipped,
        "formula_hits": formula_hits,
        "rag_exact_hits": rag_hits
    }