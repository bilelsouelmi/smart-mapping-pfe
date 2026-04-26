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
    
    async def suggest_field_mapping(
        self,
        field_id: str,
        field_name: str,
        sample_data: Optional[List] = None,
        message_description_id: Optional[int] = None,
        db: Session = None
    ) -> Dict:
        """
        Génère une suggestion intelligente pour un champ

        Workflow:
        1. Cherche dans l'historique d'apprentissage (ai_learning)
        2. Si trouvé avec haute confiance (>50%) → Retourne suggestion apprise
        3. Sinon → Fallback sur ElementMatcher
        4. Enrichit avec Qdrant RAG
        5. Si Qdrant score < 0.65 → Web Search DuckDuckGo
        6. Fallback par défaut si rien trouvé
        """
        
        print(f"\n🔍 === SUGGEST FIELD MAPPING FOR: {field_id} ===")
        logger.info(f"🔍 Generating suggestion for field: {field_id}")
        
        suggestion = None

        # ── Étape 1 : Cherche dans l'historique d'apprentissage ───────────────
        if db:
            print(f"  Searching in historical data...")
            historical_match = self._find_historical_match(field_id, None, db)
            
            if historical_match:
                confidence = historical_match['confidence']
                print(f"  ✅ Found historical match with confidence: {confidence:.2f}")
                
                if confidence > 0.50:
                    print(f"  🧠 Using LEARNED suggestion (confidence > 0.50)")
                    logger.info(f"🧠 Using learned pattern for {field_id} (confidence: {confidence})")
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
                else:
                    print(f"  ⚠️ Confidence too low ({confidence:.2f}), falling back to ElementMatcher")
            else:
                print(f"  ❌ No historical match found")

        # ── Étape 2 : Fallback sur ElementMatcher ────────────────────────────
        if suggestion is None:
            print(f"  📚 Using ElementMatcher")
            logger.info(f"📚 Using ElementMatcher for {field_id}")

            # ── NOUVEAU : pour les tags MT, utiliser le nom du bloc comme field_name
            matcher_field_id = field_id
            matcher_field_name = field_name or field_id
            if field_id.startswith(':'):
                # Extraire le nom lisible du tag MT
                # ex: ":32A.Currency" → "Currency", ":20" → "Transaction Reference"
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
                    matcher_field_name = sub  # e.g. "Currency", "Name", "Account"
                else:
                    matcher_field_name = mt_names.get(field_id, field_id.replace(':', ''))
            # ── FIN NOUVEAU ───────────────────────────────────────────────────

            matcher = ElementMatcher(db)
            matches = matcher._find_matches(matcher_field_name, sample_data)
            
            if matches and len(matches) > 0:
                best_match = matches[0]
                print(f"  ✅ ElementMatcher found: {best_match['element_name']} (confidence: {best_match['confidence']}%)")
                suggestion = {
                    "element_id": best_match['element_id'],
                    "element_name": best_match['element_name'],
                    "description": best_match['element_name'],
                    "source": best_match.get('source_path', field_id),
                    "target": best_match.get('target_path', ''),
                    "transformation": "DIRECT_COPY",
                    "criticality": "MEDIUM",
                    "confidence": best_match['confidence'] / 100.0,
                    "suggestion_source": "element_matcher"
                }

        # ── Étape 3 : Fallback par défaut ────────────────────────────────────
        if suggestion is None:
            print(f"  ⚠️ No match found, using default")
            logger.info(f"⚠️ No match found for {field_id}, using default")
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

        # ── Étape 4 : Enrichissement Qdrant RAG ──────────────────────────────
        try:
            # ── NOUVEAU : query enrichie pour tags MT ─────────────────────────
            qdrant_field_name = field_name or field_id
            if field_id.startswith(':'):
                if '.' in field_id:
                    tag, sub = field_id.split('.', 1)
                    qdrant_field_name = f"SWIFT MT {tag} {sub} field"
                else:
                    qdrant_field_name = f"SWIFT MT {field_id} field"
            # ── FIN NOUVEAU ───────────────────────────────────────────────────

            rag_enrichment = self._enrich_from_qdrant(field_id, qdrant_field_name)
            if rag_enrichment:
                if suggestion.get('mapping_formula'):
                    rag_enrichment.pop('mapping_formula', None)
                suggestion.update(rag_enrichment)
                print(f"  ✨ Enriched with Qdrant RAG data (mapping: {rag_enrichment.get('rag_mapping_id')})")
                logger.info(f"✨ RAG enrichment applied for {field_id}")
        except Exception as e:
            logger.warning(f"RAG enrichment failed for {field_id}: {e}")
            print(f"  ⚠️ RAG enrichment failed: {e}")

        # ── Étape 5 : Web Search DuckDuckGo si Qdrant insuffisant ────────────
        rag_score = suggestion.get('rag_similarity_score', 0.0) or 0.0
        should_search_web = (
            suggestion.get('suggestion_source') == 'default' or
            not suggestion.get('rag_mapping_id') or
            rag_score < 0.65
        )
        if should_search_web:
            try:
                # ── NOUVEAU : query web enrichie pour tags MT ─────────────────
                web_field_name = field_name or field_id
                if field_id.startswith(':'):
                    if '.' in field_id:
                        tag, sub = field_id.split('.', 1)
                        web_field_name = f"SWIFT {tag} {sub}"
                    else:
                        web_field_name = f"SWIFT {field_id} field"
                # ── FIN NOUVEAU ───────────────────────────────────────────────

                web_results = await self._search_web(field_id, web_field_name)
                if web_results:
                    suggestion['web_enrichment'] = web_results
                    suggestion['web_search_performed'] = True
                    print(f"  🌐 Web enrichment added for {field_id} ({len(web_results)} results)")
                    logger.info(f"🌐 Web enrichment applied for {field_id}")
                else:
                    suggestion['web_search_performed'] = True
                    suggestion['web_enrichment'] = []
                    print(f"  🌐 Web search performed but no results for {field_id}")
            except Exception as e:
                logger.warning(f"Web search failed for {field_id}: {e}")
                print(f"  ⚠️ Web search failed: {e}")

        return suggestion

    async def _search_web(self, field_id: str, field_name: str) -> Optional[List[Dict]]:
        """Recherche DuckDuckGo pour enrichir les infos sur un field SWIFT/ISO 20022."""
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

    def _enrich_from_qdrant(self, field_id: str, field_name: str) -> Optional[Dict]:
        """Recherche dans Qdrant les champs enrichis pour un field donné."""
        try:
            from app.services.rag_service import rag_service
            if not rag_service._is_available():
                return None

            query = f"field mapping {field_name or field_id} transformation rules compliance audit"
            results = rag_service.query(
                query=query,
                n_results=3,
                filter_metadata={"chunk_type": "FIELD_MAPPING"}
            )

            if not results:
                return None

            metadatas = results.get('metadatas', [[]])[0]
            documents = results.get('documents', [[]])[0]
            distances = results.get('distances', [[]])[0]

            if not metadatas:
                return None

            best_meta = metadatas[0]
            best_doc = documents[0] if documents else ""
            best_score = distances[0] if distances else 0.0

            if best_score < 0.3:
                return None

            mapping_formula_obj = best_meta.get('mapping_formula', {})
            formula_details = mapping_formula_obj.get('details', {}) if isinstance(mapping_formula_obj, dict) else {}
            global_vars_dict = formula_details.get('global_variables', {})

            enrichment = {
                "rag_mapping_id": best_meta.get('mapping_id'),
                "rag_mapping_name": best_meta.get('mapping_name'),
                "rag_similarity_score": round(best_score, 3),
                "performance_impact": best_meta.get('performance_impact'),
                "has_audit_requirement": best_meta.get('has_audit_requirement', False),
                "has_compliance_requirement": best_meta.get('has_compliance_requirement', False),
                "has_migration_note": best_meta.get('has_migration_note', False),
                "mapping_formula": mapping_formula_obj.get('pseudocode') if isinstance(mapping_formula_obj, dict) else None,
                "global_variable_refs": list(global_vars_dict.keys()) if global_vars_dict else [],
            }

            enrichment["audit_requirement"] = best_meta.get('audit_requirement') or self._extract_section(best_doc, "Audit Requirement:")
            enrichment["compliance_requirement"] = best_meta.get('compliance_requirement') or self._extract_section(best_doc, "Compliance Requirement:")
            enrichment["data_privacy"] = best_meta.get('data_privacy') or self._extract_section(best_doc, "Data Privacy (GDPR):")
            enrichment["migration_note"] = best_meta.get('migration_note') or self._extract_section(best_doc, "Migration Note:")
            enrichment["caching_strategy"] = best_meta.get('caching_strategy') or self._extract_section(best_doc, "Caching Strategy:")

            enrichment = {k: v for k, v in enrichment.items() if v is not None and v != [] and v != {}}
            return enrichment if len(enrichment) > 2 else None

        except Exception as e:
            logger.warning(f"_enrich_from_qdrant failed: {e}")
            return None

    def _extract_section(self, text: str, label: str) -> Optional[str]:
        """Extrait le contenu d'une section depuis le texte d'un chunk."""
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

    def _find_historical_match(
        self,
        field_id: str,
        field_tag: Optional[str],
        db: Session
    ) -> Optional[Dict]:
        """Cherche dans l'historique des décisions acceptées/éditées"""
        if not db:
            return None
        
        patterns = self._generate_patterns(field_id)
        print(f"    🔎 Generated patterns: {patterns}")
        
        query = db.query(AILearning).filter(
            AILearning.user_action.in_(['accept', 'edit']),
            AILearning.field_pattern.in_(patterns)
        )
        
        if field_tag:
            query = query.filter(AILearning.field_tag == field_tag)
        
        results = query.order_by(AILearning.created_at.desc()).limit(10).all()
        print(f"    📊 Found {len(results)} historical entries")
        
        if not results:
            return None
        
        confidence = self._calculate_confidence(results)
        aggregated = self._aggregate_results(results)
        
        print(f"    🎯 Aggregated description: {aggregated.get('description')}")
        print(f"    📈 Calculated confidence: {confidence:.2f}")
        
        return {
            "confidence": confidence,
            **aggregated
        }
    
    def record_user_decision(
        self,
        field_id: str,
        field_tag: Optional[str],
        suggestion: Dict,
        user_action: str,
        final_values: Optional[Dict],
        message_description_id: Optional[int],
        mapping_formula_id: Optional[int],
        user_id: int,
        db: Session
    ):
        """Enregistre la décision de l'utilisateur pour apprentissage futur"""
        print(f"\n📝 === RECORDING DECISION: {user_action} for {field_id} ===")
        
        if user_action not in ['accept', 'edit', 'reject']:
            raise ValueError(f"Invalid action: {user_action}")
        
        field_pattern = self._generate_patterns(field_id)[0]
        print(f"  Field pattern: {field_pattern}")
        
        confidence_raw = suggestion.get('confidence', 0.5)
        if confidence_raw > 1:
            confidence_score = confidence_raw / 100.0
        else:
            confidence_score = confidence_raw
        
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
            print(f"  Final (edited): {learning_entry.final_description}")
        elif user_action == 'accept':
            learning_entry.final_element_id = suggestion.get('element_id')
            learning_entry.final_description = suggested_description
            learning_entry.final_source = suggestion.get('source')
            learning_entry.final_target = suggestion.get('target')
            learning_entry.final_transformation = suggestion.get('transformation')
            learning_entry.final_criticality = suggestion.get('criticality')
            learning_entry.final_mapping_formula = suggestion.get('mapping_formula')
            print(f"  Final (accepted): {learning_entry.final_description}")
        
        db.add(learning_entry)
        db.commit()
        db.refresh(learning_entry)
        
        print(f"  ✅ Recorded decision ID: {learning_entry.id}")
        logger.info(f"✅ Recorded {user_action} for {field_id} by user {user_id}")
        
        return learning_entry
    
    def _generate_patterns(self, field_id: str) -> List[str]:
        """
        Génère des patterns pour matching.
        Supporte maintenant les tags MT SWIFT (:20, :32A.Currency, etc.)
        """
        patterns = [field_id]

        # ── NOUVEAU : patterns pour tags MT SWIFT ─────────────────────────────
        if field_id.startswith(':'):
            if '.' in field_id:
                # :32A.Currency → aussi matcher :32A.* et *.Currency
                tag, sub = field_id.split('.', 1)
                patterns.append(f"{tag}.*")
                patterns.append(f"*.{sub}")
            else:
                # :20 → pattern exact seulement
                patterns.append(field_id)
        # ── FIN NOUVEAU ───────────────────────────────────────────────────────

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
    
    def _calculate_confidence(self, results: List[AILearning]) -> float:
        """Calcule le score de confiance"""
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
        
        final_targets = [
            r.final_target or r.suggested_target 
            for r in results 
            if (r.final_target or r.suggested_target)
        ]
        
        if final_targets:
            most_common = max(set(final_targets), key=final_targets.count)
            coherence_factor = final_targets.count(most_common) / len(final_targets)
        else:
            coherence_factor = 0.5
        
        confidence = (
            count_factor * 0.3 + 
            recency_factor * 0.3 + 
            coherence_factor * 0.4
        )
        
        return round(confidence, 2)
    
    def _aggregate_results(self, results: List[AILearning]) -> Dict:
        """Agrège les résultats pour trouver la suggestion la plus commune"""
        element_ids = [r.final_element_id or r.suggested_element_id for r in results if (r.final_element_id or r.suggested_element_id)]
        descriptions = [r.final_description or r.suggested_description for r in results if (r.final_description or r.suggested_description)]
        sources = [r.final_source or r.suggested_source for r in results if (r.final_source or r.suggested_source)]
        targets = [r.final_target or r.suggested_target for r in results if (r.final_target or r.suggested_target)]
        transformations = [r.final_transformation or r.suggested_transformation for r in results if (r.final_transformation or r.suggested_transformation)]
        criticalities = [r.final_criticality or r.suggested_criticality for r in results if (r.final_criticality or r.suggested_criticality)]
        
        mapping_formulas = [
            r.final_mapping_formula or r.suggested_mapping_formula
            for r in results
            if (r.final_mapping_formula or r.suggested_mapping_formula)
        ]
        best_mapping_formula = mapping_formulas[0] if mapping_formulas else None

        return {
            "element_id": Counter(element_ids).most_common(1)[0][0] if element_ids else None,
            "description": Counter(descriptions).most_common(1)[0][0] if descriptions else None,
            "source": Counter(sources).most_common(1)[0][0] if sources else None,
            "target": Counter(targets).most_common(1)[0][0] if targets else None,
            "transformation": Counter(transformations).most_common(1)[0][0] if transformations else "DIRECT_COPY",
            "criticality": Counter(criticalities).most_common(1)[0][0] if criticalities else "MEDIUM",
            "mapping_formula": best_mapping_formula
        }


# Singleton
ai_learning_service = AILearningService()