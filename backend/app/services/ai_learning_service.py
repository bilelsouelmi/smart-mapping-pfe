from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.models.ai_learning import AILearning
from app.services.element_matcher import ElementMatcher
import logging
from collections import Counter
import datetime
import httpx  # pour DuckDuckGo web search

logger = logging.getLogger(__name__)


class AILearningService:
    """
    Service pour les suggestions IA avec apprentissage automatique
    """

    # ISO 20022 root elements, mirrors transform_mapping.py's ISO_ROOT_ELEMENTS.
    # Kept as a local copy (not imported) to avoid a circular import between
    # ai_learning_service and the routes module.
    _ISO_ROOT_ELEMENTS = {
        "pacs.008.001.08": "FIToFICstmrCdtTrf",
        "pacs.009.001.08": "FICdtTrf",
        "camt.053.001.08": "BkToCstmrStmt",
        "camt.054.001.08": "BkToCstmrDbtCdtNtfctn",
    }

    def _to_full_xpath(self, target_path: str, iso_target: Optional[str]) -> str:
        """
        Converts a StandardElement-style dot-notation target (e.g.
        "GrpHdr.MsgId") into a full XPath consistent with what the RAG
        knowledge base already returns (e.g.
        "/Document/FIToFICstmrCdtTrf/GrpHdr/MsgId"). If target_path is
        already a full path (starts with '/' or "Document"), or if we
        don't know the iso_target's root element, it is returned unchanged.
        """
        if not target_path:
            return target_path
        if target_path.startswith('/') or target_path.startswith('Document'):
            return target_path
        root = self._ISO_ROOT_ELEMENTS.get(iso_target) if iso_target else None
        if not root:
            return target_path
        return f"/Document/{root}/{target_path.replace('.', '/')}"

    async def suggest_field_mapping(
        self,
        field_id: str,
        field_name: str,
        sample_data: Optional[List] = None,
        message_description_id: Optional[int] = None,
        db: Session = None,
        mt_type: Optional[str] = None,
        iso_target: Optional[str] = None,
    ) -> Dict:
        """
        Args:
            mt_type: Le type SWIFT MT (ex: "MT103") ou ISO (ex: "pacs.008.001.08")
                     du fichier source en cours d'analyse. Utilisé pour filtrer
                     le RAG Qdrant et éviter de mélanger les suggestions entre
                     différents types de messages (ex: ne pas suggérer une
                     formule MT202 pour un champ d'un fichier MT103).
            iso_target: Le schéma ISO 20022 cible (ex: "pacs.008.001.08"). Utilisé
                     pour convertir le target_path en notation courte issue de
                     StandardElement (ex: "GrpHdr.MsgId") en XPath complet.
        """
        print(f"\n🔍 === SUGGEST FIELD MAPPING FOR: {field_id} (mt_type={mt_type}) ===")
        logger.info(f"🔍 Generating suggestion for field: {field_id} (mt_type={mt_type})")

        suggestion = None

        # Étape 1 : Historique
        if db:
            historical_match = self._find_historical_match(field_id, None, db)
            if historical_match and historical_match['confidence'] > 0.50:
                suggestion = {
                    "element_id": historical_match.get('element_id', field_id),
                    "element_name": historical_match['description'],
                    "description": historical_match['description'],
                    "source": historical_match['source'],
                    "target": historical_match['target'],
                    "transformation": historical_match['transformation'],
                    "criticality": historical_match['criticality'],
                    "confidence": historical_match['confidence'],
                    "suggestion_source": "learning",
                    "mapping_formula": historical_match.get('mapping_formula'),
                }

        # Étape 2 : ElementMatcher
        if suggestion is None:
            matcher_field_name = field_name or field_id
            if field_id.startswith(':'):
                mt_names = {
                    ':20': 'Transaction Reference',
                    ':32A': 'Value Date Currency Amount',
                    ':50K': 'Ordering Customer',
                    ':59': 'Beneficiary',
                    ':71A': 'Charge Bearer',
                    ':70': 'Remittance Information',
                    ':52A': 'Ordering Institution',
                    ':56A': 'Intermediary Institution',
                    ':57A': 'Account With Institution',
                }
                if '.' in field_id:
                    tag, sub = field_id.split('.', 1)
                    matcher_field_name = sub
                else:
                    matcher_field_name = mt_names.get(field_id, field_id.replace(':', ''))

            matcher = ElementMatcher(db)
            matches = matcher._find_matches(matcher_field_name, sample_data)
            if matches:
                best_match = matches[0]
                raw_target = best_match.get('target_path', '')
                suggestion = {
                    "element_id": best_match['element_id'],
                    "element_name": best_match['element_name'],
                    "description": best_match['element_name'],
                    "source": best_match.get('source_path', field_id),
                    "target": self._to_full_xpath(raw_target, iso_target),
                    "transformation": "DIRECT_COPY",
                    "criticality": "MEDIUM",
                    "confidence": best_match['confidence'] / 100.0,
                    "suggestion_source": "element_matcher"
                }

        # Étape 3 : Default
        if suggestion is None:
            suggestion = {
                "element_id": field_id,
                "element_name": field_name or field_id,
                "description": field_name or field_id,
                "source": field_id,
                "target": "",
                "transformation": "DIRECT_COPY",
                "criticality": "LOW",
                "confidence": 0.3,
                "suggestion_source": "default"
            }

        # Étape 4 : RAG Enrichment
        try:
            qdrant_field_name = field_name or field_id
            if field_id.startswith(':'):
                if '.' in field_id:
                    tag, sub = field_id.split('.', 1)
                    qdrant_field_name = f"SWIFT MT {tag} {sub} field"
                else:
                    qdrant_field_name = f"SWIFT MT {field_id} field"

            rag_enrichment = self._enrich_from_qdrant(field_id, qdrant_field_name, mt_type=mt_type, iso_target=iso_target)
            if rag_enrichment:
                suggestion.update(rag_enrichment)
                # An exact RAG match (this field's own dataset-authored
                # formula) is always more trustworthy than Step 2's fuzzy
                # ElementMatcher guess against the generic standard_elements
                # table — it should win outright, not just fill a gap.
                # Previously this only applied when suggestion.target was
                # still empty, so any field ElementMatcher also produced a
                # (wrong) guess for kept displaying — and, worse, saving on
                # Accept — that wrong target while showing the CORRECT
                # formula pseudocode right below it, an inconsistent pair.
                if rag_enrichment.get('rag_target_path'):
                    suggestion['target'] = rag_enrichment['rag_target_path']
                    suggestion['target_path'] = rag_enrichment['rag_target_path']
                if rag_enrichment.get('rag_element_id'):
                    suggestion['element_id'] = rag_enrichment['rag_element_id']
                    suggestion['element_name'] = rag_enrichment['rag_element_id']
                # suggestion.update() above copies rag_similarity_score in
                # under ITS OWN key, but the confidence badge the frontend
                # actually renders (SuggestionCard.jsx) reads
                # suggestion['confidence'] — which is a different key, left
                # over from Step 2's fuzzy ElementMatcher guess (often as
                # low as 0.3). Without this, a field with an exact
                # dataset-authored formula (shown right below as "100%
                # match") displayed a contradictory 30% badge above it.
                if rag_enrichment.get('rag_similarity_score') is not None:
                    suggestion['confidence'] = rag_enrichment['rag_similarity_score']
                print(f"  ✨ Enriched with RAG (mapping: {rag_enrichment.get('rag_mapping_id')})")
        except Exception as e:
            logger.warning(f"RAG enrichment failed for {field_id}: {e}")

        # Étape 4.5 : LLM Fallback — only reached when nothing above found a
        # trustworthy answer (no history, no exact RAG/dataset match): this
        # is what turns a genuinely NEW field (one this platform has never
        # seen before) into a real suggestion instead of a placeholder.
        # Previously suggest_xml_mapping() existed but was never called
        # from anywhere, so an unmapped field just kept ElementMatcher's
        # weak fuzzy guess (or the flat 0.3 default) with target "N/A".
        if suggestion.get('suggestion_source') in ('element_matcher', 'default') \
                and (suggestion.get('confidence') or 0) < 0.6 and mt_type and iso_target:
            try:
                llm_result = self._suggest_via_llm(field_id, field_name, mt_type, iso_target, db)
                if llm_result:
                    suggestion.update(llm_result)
                    print(f"  🤖 LLM-generated suggestion for {field_id} → {llm_result.get('target')}")
            except Exception as e:
                logger.warning(f"LLM fallback failed for {field_id}: {e}")

        # Étape 5 : Web Search
        rag_score = suggestion.get('rag_similarity_score', 0.0) or 0.0
        should_search_web = (
            suggestion.get('suggestion_source') == 'default' or
            not suggestion.get('rag_mapping_id') or
            rag_score < 0.65
        )
        if should_search_web:
            try:
                web_field_name = field_name or field_id
                if field_id.startswith(':'):
                    if '.' in field_id:
                        tag, sub = field_id.split('.', 1)
                        web_field_name = f"SWIFT {tag} {sub}"
                    else:
                        web_field_name = f"SWIFT {field_id} field"

                web_results = await self._search_web(field_id, web_field_name)
                if web_results:
                    suggestion['web_enrichment'] = web_results
                    suggestion['web_search_performed'] = True
                else:
                    suggestion['web_search_performed'] = True
                    suggestion['web_enrichment'] = []
            except Exception as e:
                logger.warning(f"Web search failed for {field_id}: {e}")

        return suggestion

    def _suggest_via_llm(
        self,
        field_id: str,
        field_name: Optional[str],
        mt_type: str,
        iso_target: str,
        db: Optional[Session],
    ) -> Optional[Dict]:
        """
        Genuinely generates a mapping for a field with no exact RAG match —
        as opposed to every other path in this file, which only ever
        RETRIEVES a pre-authored answer. Grounds the LLM with whatever
        formulas have already been accepted for this same mt_type (the
        closest available context short of a real semantic search over
        Qdrant), so it isn't reasoning from field name alone.
        """
        from app.services.llm_service import LLMService
        from app.models.mapping_formula import MappingFormula
        from app.models.message_description import MessageDescription

        llm_service = LLMService()
        formulas_context = None
        if db:
            md_ids = [
                md.id for md in db.query(MessageDescription.id)
                .filter(MessageDescription.mt_type == mt_type).all()
            ]
            if md_ids:
                rows = db.query(MappingFormula).filter(
                    MappingFormula.message_description_id.in_(md_ids),
                    MappingFormula.target_path.isnot(None),
                    MappingFormula.target_path != ''
                ).limit(10).all()
                if rows:
                    formulas_context = [
                        {
                            "source_path": r.source_path,
                            "target_path": r.target_path,
                            "transformation_type": r.transformation_type,
                            "transformation_rule": r.transformation_rule,
                        }
                        for r in rows
                    ]

        # Semantic grounding: find the closest EXISTING formulas (by vector
        # similarity on the field's own name, not an exact tag match — this
        # only runs when the exact lookup already found nothing) so the LLM
        # reasons from real worked examples instead of the field name alone.
        # This is what a hallucination like :26T: -> GrpHdr/MsgId had none
        # of — no similar field to anchor its answer against.
        from app.services.exact_rag_lookup import semantic_similar_formulas
        rag_context = semantic_similar_formulas(field_name or field_id, mt_type, iso_target, n_results=3)

        field_tag = field_id if field_id.startswith(':') else None
        result = llm_service.suggest_xml_mapping(
            mt_type=mt_type,
            iso_target=iso_target,
            source_fields=[{
                "name": field_name or field_id,
                "tag": field_tag,
                "description": field_name or field_id,
            }],
            formulas=formulas_context,
            rag_context=rag_context or None,
        )
        elements = result.get("elements") or []
        if not elements:
            return None

        item = elements[0]
        target_xpath = (item.get("target_xpath") or "").strip()
        if not target_xpath:
            return None

        # The prompt asks for a bare relative path ("GrpHdr/MsgId"), but an
        # LLM won't always follow that literally — it may prepend a
        # leading slash, "Document/", or even the schema name itself
        # (observed: "pacs.008.001.08/GrpHdr/MsgId"). Strip whatever
        # prefix it added rather than assuming one fixed shape, or a
        # naive f"/Document/{root}/{target_xpath}" produces a malformed
        # doubled-up path.
        target_xpath = target_xpath.lstrip('/')
        if target_xpath.startswith('Document/'):
            target_xpath = target_xpath[len('Document/'):]
        if iso_target and target_xpath.startswith(iso_target + '/'):
            target_xpath = target_xpath[len(iso_target) + 1:]

        root = self._ISO_ROOT_ELEMENTS.get(iso_target)
        if root and (target_xpath == root or target_xpath.startswith(root + '/')):
            full_target = f"/Document/{target_xpath}"
        elif root:
            full_target = f"/Document/{root}/{target_xpath}"
        else:
            full_target = f"/Document/{target_xpath}"

        confidence = item.get("confidence", 0.5)
        if confidence > 1:
            confidence = confidence / 100.0

        return {
            "target": full_target,
            "target_path": full_target,
            "mapping_formula": item.get("expression"),
            "confidence": confidence,
            "suggestion_source": "ai",
            "criticality": "MEDIUM" if item.get("is_mandatory") else "LOW",
        }

    async def _search_web(self, field_id: str, field_name: str) -> Optional[List[Dict]]:
        try:
            from ddgs import DDGS
            query = f"{field_name or field_id} SWIFT ISO 20022 banking field definition"
            results = []
            with DDGS() as ddgs:
                search_results = list(ddgs.text(query, max_results=3))
                for r in search_results:
                    results.append({
                        "title": r.get('title', '')[:150],
                        "url": r.get('href', ''),
                        "snippet": r.get('body', '')[:500],
                        "source": r.get('href', '').split('/')[2] if r.get('href') else 'Web'
                    })
            return results if results else None
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return None

    def _enrich_from_qdrant(
        self,
        field_id: str,
        field_name: str,
        mt_type: Optional[str] = None,
        iso_target: Optional[str] = None,
    ) -> Optional[Dict]:
        """
        Recherche dans Qdrant les champs enrichis pour un field donné.

        Délègue au module partagé exact_rag_lookup (lookup_mt_to_iso), qui
        est la SEULE implémentation de cette recherche exacte filtrée par
        mt_type dans tout le projet. Avant cette consolidation, cette
        logique était dupliquée ici ET dans mappings.py (find_target_for_tag
        / find_xpath_for_mt_tag), chacune ayant accumulé sa propre version
        du même bug (recherche sémantique non filtrée, contamination
        croisée entre types de messages). Désormais, corriger
        exact_rag_lookup.py corrige TOUS les appelants en même temps.
        """
        try:
            from app.services.exact_rag_lookup import lookup_mt_to_iso_all, lookup_iso_to_mt_all
            # field_id shape tells us the direction: a dotted, colon-free
            # string ("CdtTrfTxInf.Dbtr.Nm") is an XML path from an
            # XML->MT upload; a SWIFT tag ("...", starts with ':') is the
            # MT->ISO direction this always assumed before. Without this,
            # every XML-sourced field silently searched Qdrant as if it
            # were an MT tag and never found anything.
            is_xml_path = bool(field_id) and not field_id.startswith(':') and '.' in field_id
            if is_xml_path:
                results = lookup_iso_to_mt_all(field_id, mt_type, iso_target)
            else:
                results = lookup_mt_to_iso_all(field_id, mt_type, iso_target)
            if not results:
                return None
            result = results[0]

            print(f"  🎯 Exact lookup: {field_id} → {result.get('target_path')}"
                  + (f" (+{len(results) - 1} more target(s))" if len(results) > 1 else ""))

            enrichment = {
                "rag_mapping_id": result.get('mapping_id'),
                "rag_mapping_name": result.get('mapping_name'),
                "rag_similarity_score": 1.0 if result.get('mapping_name') else 0.7,
                "performance_impact": result.get('performance_impact'),
                "has_audit_requirement": result.get('has_audit_requirement', False),
                "has_compliance_requirement": result.get('has_compliance_requirement', False),
                "has_migration_note": result.get('has_migration_note', False),
                "mapping_formula": result.get('formula_pseudocode'),
                "global_variable_refs": result.get('global_variable_refs', []),
                "rag_target_path": result.get('target_path'),
                "rag_element_id": result.get('element_id'),
                "rag_src_mapping_id": result.get('mapping_id'),
                "audit_requirement": result.get('audit_requirement'),
                "compliance_requirement": result.get('compliance_requirement'),
                "data_privacy": result.get('data_privacy'),
                "migration_note": result.get('migration_note'),
                "caching_strategy": result.get('caching_strategy'),
                # A single source field can drive several ISO 20022 targets
                # from one shared multi-statement formula (e.g. :50K: ->
                # Dbtr.Nm AND DbtrAcct.Id.IBAN, via a <TargetFields>
                # wrapper). lookup_mt_to_iso_all returns every one of them;
                # the first becomes the primary suggestion above, the rest
                # are carried here so the accept flow can create a
                # MappingFormula for each instead of silently dropping them.
                "additional_targets": [
                    {
                        "target_path": r.get('target_path'),
                        "element_id": r.get('element_id'),
                    }
                    for r in results[1:] if r.get('target_path')
                ],
            }
            enrichment = {k: v for k, v in enrichment.items() if v is not None and v != [] and v != {}}
            return enrichment if len(enrichment) > 1 else None

        except Exception as e:
            logger.warning(f"_enrich_from_qdrant failed: {e}")
            return None

    def _extract_section(self, text: str, label: str) -> Optional[str]:
        if not text or label not in text:
            return None
        try:
            start = text.index(label) + len(label)
            remaining = text[start:].strip()
            end = remaining.find('\n\n')
            if end != -1:
                return remaining[:end].strip()
            for next_label in [
                "Audit Requirement:", "Compliance Requirement:",
                "Data Privacy (GDPR):", "Migration Note:",
                "Caching Strategy:", "Global Variables Used:",
                "Performance Impact:", "Business Rationale:",
                "Impact if Mapping Fails:"
            ]:
                if next_label != label and next_label in remaining:
                    end = remaining.index(next_label)
                    return remaining[:end].strip()
            return remaining[:500].strip()
        except Exception:
            return None

    def _find_historical_match(self, field_id, field_tag, db):
        if not db:
            return None
        patterns = self._generate_patterns(field_id)
        query = db.query(AILearning).filter(
            AILearning.user_action.in_(['accept', 'edit']),
            AILearning.field_pattern.in_(patterns)
        )
        if field_tag:
            query = query.filter(AILearning.field_tag == field_tag)
        results = query.order_by(AILearning.created_at.desc()).limit(10).all()
        if not results:
            return None
        confidence = self._calculate_confidence(results)
        aggregated = self._aggregate_results(results)
        return {"confidence": confidence, **aggregated}

    def record_user_decision(self, field_id, field_tag, suggestion, user_action,
                              final_values, message_description_id, mapping_formula_id,
                              user_id, db):
        if user_action not in ['accept', 'edit', 'reject']:
            raise ValueError(f"Invalid action: {user_action}")
        field_pattern = self._generate_patterns(field_id)[0]
        confidence_raw = suggestion.get('confidence', 0.5)
        confidence_score = confidence_raw / 100.0 if confidence_raw > 1 else confidence_raw
        suggested_description = suggestion.get('description') or suggestion.get('element_name')
        learning_entry = AILearning(
            field_pattern=field_pattern,
            field_tag=field_tag,
            original_field_name=field_id,
            suggested_element_id=suggestion.get('element_id'),
            suggested_description=suggested_description,
            suggested_source=suggestion.get('source'),
            suggested_target=suggestion.get('target'),
            suggested_transformation=suggestion.get('transformation'),
            suggested_criticality=suggestion.get('criticality'),
            suggestion_source=suggestion.get('suggestion_source', 'unknown'),
            suggested_mapping_formula=suggestion.get('mapping_formula'),
            user_action=user_action,
            confidence_score=confidence_score,
            message_description_id=message_description_id,
            mapping_formula_id=mapping_formula_id,
            created_by=user_id
        )
        if user_action == 'edit' and final_values:
            learning_entry.final_element_id = final_values.get('element_id')
            learning_entry.final_description = final_values.get('element_name') or final_values.get('description')
            learning_entry.final_source = final_values.get('source')
            learning_entry.final_target = final_values.get('target')
            learning_entry.final_transformation = final_values.get('transformation')
            learning_entry.final_criticality = final_values.get('criticality')
            learning_entry.final_mapping_formula = final_values.get('mapping_formula')
        elif user_action == 'accept':
            learning_entry.final_element_id = suggestion.get('element_id')
            learning_entry.final_description = suggested_description
            learning_entry.final_source = suggestion.get('source')
            learning_entry.final_target = suggestion.get('target')
            learning_entry.final_transformation = suggestion.get('transformation')
            learning_entry.final_criticality = suggestion.get('criticality')
            learning_entry.final_mapping_formula = suggestion.get('mapping_formula')
        db.add(learning_entry)
        db.commit()
        db.refresh(learning_entry)
        logger.info(f"✅ Recorded {user_action} for {field_id} by user {user_id}")
        return learning_entry

    def _generate_patterns(self, field_id):
        patterns = [field_id]
        if field_id.startswith(':'):
            if '.' in field_id:
                tag, sub = field_id.split('.', 1)
                patterns.append(f"{tag}.*")
                patterns.append(f"*.{sub}")
            else:
                patterns.append(field_id)
        elif '_' in field_id and field_id.startswith('FIELD_'):
            parts = field_id.split('_')
            if len(parts) == 2 and parts[1].isdigit():
                number = parts[1]
                patterns.append(f"FIELD_*{number[-1]}")
                patterns.append(f"FIELD_{number[0]}*")
        elif '.' in field_id:
            parts = field_id.split('.')
            if len(parts) == 2:
                patterns.append(f"*.{parts[1]}")
                patterns.append(f"{parts[0]}.*")
        return patterns

    def _calculate_confidence(self, results):
        if not results:
            return 0.0
        count_factor = min(len(results) / 10.0, 1.0)
        now = datetime.datetime.now()
        recency_scores = []
        for r in results:
            created_at = r.created_at
            if created_at.tzinfo is not None:
                created_at = created_at.replace(tzinfo=None)
            days_old = (now - created_at).days
            recency = 1.0 / (1.0 + days_old / 30.0)
            recency_scores.append(recency)
        recency_factor = sum(recency_scores) / len(recency_scores)
        final_targets = [r.final_target or r.suggested_target for r in results if (r.final_target or r.suggested_target)]
        if final_targets:
            most_common = max(set(final_targets), key=final_targets.count)
            coherence_factor = final_targets.count(most_common) / len(final_targets)
        else:
            coherence_factor = 0.5
        return round(count_factor * 0.3 + recency_factor * 0.3 + coherence_factor * 0.4, 2)

    def _aggregate_results(self, results):
        element_ids = [r.final_element_id or r.suggested_element_id for r in results if (r.final_element_id or r.suggested_element_id)]
        descriptions = [r.final_description or r.suggested_description for r in results if (r.final_description or r.suggested_description)]
        sources = [r.final_source or r.suggested_source for r in results if (r.final_source or r.suggested_source)]
        targets = [r.final_target or r.suggested_target for r in results if (r.final_target or r.suggested_target)]
        transformations = [r.final_transformation or r.suggested_transformation for r in results if (r.final_transformation or r.suggested_transformation)]
        criticalities = [r.final_criticality or r.suggested_criticality for r in results if (r.final_criticality or r.suggested_criticality)]
        mapping_formulas = [r.final_mapping_formula or r.suggested_mapping_formula for r in results if (r.final_mapping_formula or r.suggested_mapping_formula)]
        return {
            "element_id": Counter(element_ids).most_common(1)[0][0] if element_ids else None,
            "description": Counter(descriptions).most_common(1)[0][0] if descriptions else None,
            "source": Counter(sources).most_common(1)[0][0] if sources else None,
            "target": Counter(targets).most_common(1)[0][0] if targets else None,
            "transformation": Counter(transformations).most_common(1)[0][0] if transformations else "DIRECT_COPY",
            "criticality": Counter(criticalities).most_common(1)[0][0] if criticalities else "MEDIUM",
            "mapping_formula": mapping_formulas[0] if mapping_formulas else None
        }


# Singleton
ai_learning_service = AILearningService()