"""
XML Chunking Service
Converts XML mappings into semantic chunks for RAG

Phase 2 of the Qdrant/RAG redesign: chunks are now lean, structured
retrieval units instead of documentation carriers. business_rationale,
migration_note, audit_requirement, compliance_requirement, data_privacy,
caching_strategy, and performance_impact no longer appear in ANY chunk's
payload or embedded content — that's PostgreSQL's job now
(mapping_documentation, populated by mapping_documentation_import.py).
Qdrant chunks carry only what's useful for finding and reusing a
transformation pattern: identifiers, a resolvable doc_id back to
Postgres, extracted functions/reference-data/global-variable usage (see
formula_knowledge_extractor.py), and a short (1-2 sentence) semantic
summary kept specifically to preserve embedding/retrieval quality for
fuzzy natural-language queries — everything else is exact-match
metadata, not prose.

GLOBAL_VARIABLES chunks are retired entirely: they fully duplicated
what's already live (and more current) in the business_variables
Postgres table, and is now also surfaced dynamically at LLM-prompt time
by context_builder.py's CAG layer — retrieving a static snapshot of it
from Qdrant added nothing.
"""

import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class XMLChunk:
    """Represents a semantic chunk of XML mapping data"""

    def __init__(self, content: str, metadata: Dict[str, Any], chunk_type: str, chunk_id: str):
        self.content = content
        self.metadata = metadata
        self.chunk_type = chunk_type
        self.chunk_id = chunk_id


def _short_summary(text: str, max_sentences: int = 2) -> str:
    """First 1-2 sentences of a longer text (e.g. business_rationale),
    used ONLY as a short embedding-quality aid — never the full text.
    The full text lives in mapping_documentation, resolvable via doc_id."""
    if not text:
        return None
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    summary = ' '.join(s for s in sentences[:max_sentences] if s).strip()
    return summary or None


class XMLChunker:
    """Intelligent chunking of XML mapping files for RAG"""

    def __init__(self):
        self.chunk_types = [
            "GENERAL_INFO", "SOURCE_FIELD", "TARGET_FIELD", "FIELD_MAPPING",
            "VALIDATION_RULE", "USE_CASE",
        ]

    def chunk_mapping(self, mapping_data: Dict[str, Any]) -> List[XMLChunk]:
        chunks = []
        mapping_id = mapping_data.get('mapping_id', 'UNKNOWN')
        mapping_name = mapping_data.get('mapping_name', 'Unknown Mapping')

        chunks.extend(self._chunk_general_info(mapping_data, mapping_id, mapping_name))
        chunks.extend(self._chunk_source_fields(mapping_data, mapping_id, mapping_name))
        chunks.extend(self._chunk_target_fields(mapping_data, mapping_id, mapping_name))
        chunks.extend(self._chunk_field_mappings(mapping_data, mapping_id, mapping_name))
        chunks.extend(self._chunk_validation_rules(mapping_data, mapping_id, mapping_name))
        chunks.extend(self._chunk_use_cases(mapping_data, mapping_id, mapping_name))

        logger.info(f"Created {len(chunks)} chunks for mapping: {mapping_id}")
        return chunks

    def _chunk_general_info(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        general_info = mapping_data.get('general_information', {})
        if not general_info:
            return chunks
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')
        content_parts = [
            f"Mapping: {mapping_name}", f"ID: {mapping_id}",
            f"Version: {general_info.get('version', 'N/A')}",
            f"Status: {general_info.get('status', 'N/A')}", "",
            "Conversion:",
            f"Source Format: {general_info.get('source_format', 'N/A')}",
            f"Target Format: {general_info.get('target_format', 'N/A')}",
            f"Processing Mode: {general_info.get('processing_mode', 'N/A')}",
        ]
        if general_info.get('description'):
            content_parts.extend(["", "Description:", general_info['description']])
        content = "\n".join(content_parts)
        chunks.append(XMLChunk(
            content=content,
            metadata={
                "mapping_id": mapping_id, "mapping_name": mapping_name,
                "source_format": general_info.get('source_format'),
                "target_format": general_info.get('target_format'),
                "version": general_info.get('version'), "chunk_type": "GENERAL_INFO",
                "source": source_msg_type.lower() if source_msg_type else None,
                "target": target_msg_type.lower() if target_msg_type else None
            },
            chunk_type="GENERAL_INFO", chunk_id=f"{mapping_id}_GENERAL"
        ))
        return chunks

    def _chunk_source_fields(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        source_message = mapping_data.get('source_message', {})
        fields = source_message.get('fields', [])
        source_type = source_message.get('message_type', 'UNKNOWN')
        source_standard = source_message.get('standard', 'UNKNOWN')
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        for field in fields:
            if not field:
                continue
            field_id = field.get('id', 'UNKNOWN')
            field_name = field.get('field_name', 'Unnamed Field')
            field_tag = field.get('field_tag') or field.get('xpath') or field_id

            content_parts = [
                f"Source Field: {field_name}", f"Field Tag: {field_tag}",
                f"Field ID: {field_id}", f"Message Type: {source_type}",
                f"Standard: {source_standard}", ""
            ]
            if field.get('data_type'):
                content_parts.append(f"Data Type: {field['data_type']}")
            if field.get('max_length'):
                content_parts.append(f"Max Length: {field['max_length']}")
            if field.get('mandatory'):
                content_parts.append(f"Mandatory: {field['mandatory']}")
            if field.get('description'):
                content_parts.extend(["", "Description:", field['description']])
            if field.get('example_value'):
                content_parts.extend(["", f"Example: {field['example_value']}"])
            content = "\n".join(content_parts)

            # Only cross-referenced for its id now — the transformation
            # itself (expression, criticality, etc.) lives on the
            # FIELD_MAPPING chunk / mapping_documentation, not duplicated
            # here. See this file's module docstring.
            related_mapping = next(
                (m for m in mapping_data.get('field_mappings', []) if m.get('source_field') == field_id),
                None
            )

            chunks.append(XMLChunk(
                content=content,
                metadata={
                    "chunk_type": "SOURCE_FIELD", "mapping_id": mapping_id, "mapping_name": mapping_name,
                    "field_id": field_id, "field_name": field_name, "field_tag": field_tag,
                    "message_type": source_type, "side": "SOURCE",
                    "data_type": field.get('data_type'), "mandatory": field.get('mandatory'),
                    "source_message_type": source_msg_type.lower() if source_msg_type else None,
                    "target_message_type": target_msg_type.lower() if target_msg_type else None,
                    # Structural resolution data (NOT documentation) —
                    # exact_rag_lookup.py's Step 1 depends on these: some
                    # reference files put a direct <TargetPath> on the
                    # SourceField itself, which is the fast path to a
                    # target xpath without needing the FIELD_MAPPING ->
                    # TARGET_FIELD chain at all.
                    "element_id": field.get('element_id'),
                    "target_path": field.get('target_path'),
                    "target_xpath": field.get('target_xpath'),
                    "related_element_id": related_mapping.get('id') if related_mapping else None,
                },
                chunk_type="SOURCE_FIELD", chunk_id=f"{mapping_id}_SRC_{field_id}"
            ))
        return chunks

    def _chunk_target_fields(self, mapping_data, mapping_id, mapping_name):
        """Create chunks for each target field"""
        chunks = []
        target_message = mapping_data.get('target_message', {})
        fields = target_message.get('fields', [])
        target_type = target_message.get('message_type', 'UNKNOWN')
        target_standard = target_message.get('standard', 'UNKNOWN')
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        for field in fields:
            if not field:
                continue
            field_id = field.get('id', 'UNKNOWN')
            field_name = field.get('field_name') or field.get('entity_name', 'Unnamed Field')
            field_tag = field.get('field_tag') or field.get('xpath') or field.get('entity_name') or field_id

            # NOUVEAU : capture SourceMT pour le sens ISO -> MT
            source_mt = field.get('source_mt') or ''

            content_parts = [
                f"Target Field: {field_name}", f"Field Tag: {field_tag}",
                f"Field ID: {field_id}", f"Message Type: {target_type}",
                f"Standard: {target_standard}", ""
            ]
            if field.get('is_entity'):
                content_parts.append("Type: Entity (Complex Structure)")
                if field.get('entity_type'):
                    content_parts.append(f"Entity Type: {field['entity_type']}")
                if field.get('api_endpoint'):
                    content_parts.append(f"API Endpoint: {field['api_endpoint']}")
            else:
                if field.get('data_type'):
                    content_parts.append(f"Data Type: {field['data_type']}")
                if field.get('max_length'):
                    content_parts.append(f"Max Length: {field['max_length']}")
            if field.get('mandatory'):
                content_parts.append(f"Mandatory: {field['mandatory']}")
            if field.get('description'):
                content_parts.extend(["", "Description:", field['description']])
            if source_mt:
                content_parts.extend(["", f"Source MT Field: {source_mt}"])

            content = "\n".join(content_parts)

            related_mapping = next(
                (m for m in mapping_data.get('field_mappings', []) if m.get('target_field') == field_id),
                None
            )

            chunks.append(XMLChunk(
                content=content,
                metadata={
                    "chunk_type": "TARGET_FIELD", "mapping_id": mapping_id, "mapping_name": mapping_name,
                    "field_id": field_id, "field_name": field_name, "field_tag": field_tag,
                    "message_type": target_type, "side": "TARGET",
                    "is_entity": field.get('is_entity', False),
                    "data_type": field.get('data_type'), "mandatory": field.get('mandatory'),
                    "source_message_type": source_msg_type.lower() if source_msg_type else None,
                    "target_message_type": target_msg_type.lower() if target_msg_type else None,
                    # NOUVEAU : utilisé par generate-elements en sens ISO -> MT
                    "source_mt": source_mt,
                    "related_element_id": related_mapping.get('id') if related_mapping else None,
                },
                chunk_type="TARGET_FIELD", chunk_id=f"{mapping_id}_TGT_{field_id}"
            ))
        return chunks

    def _chunk_field_mappings(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        field_mappings = mapping_data.get('field_mappings', [])
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        # Resolves a target field's internal id (e.g. "TARGET_04") to its
        # real ISO 20022 XPath, so single-target mappings can carry
        # target_xpath directly (the common case) without every retrieval
        # consumer needing a second lookup.
        target_xpath_by_id = {
            f.get('id'): (f.get('xpath') or f.get('field_tag'))
            for f in mapping_data.get('target_message', {}).get('fields', [])
            if f
        }

        # doc_id resolution: one bulk query per mapping file (not per
        # field), matching the same "open a short-lived session for a
        # cross-cutting read-only lookup" pattern already used by
        # context_builder.py and transform_mapping.py's
        # _get_global_variables() — xml_chunker has no db session of its
        # own to borrow, and threading one through chunk_mapping()'s
        # public signature would ripple into rag_initializer.py for no
        # benefit over this.
        doc_ids_by_element = {}
        try:
            from app.database import SessionLocal
            from app.models.mapping_documentation import MappingDocumentation
            db = SessionLocal()
            try:
                rows = db.query(MappingDocumentation.element_id, MappingDocumentation.id).filter(
                    MappingDocumentation.mapping_id == mapping_id
                ).all()
                doc_ids_by_element = {element_id: doc_id for element_id, doc_id in rows}
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not resolve doc_id for {mapping_id}: {e}")

        from app.services.formula_knowledge_extractor import extract_all

        for mapping in field_mappings:
            if not mapping:
                continue
            map_id = mapping.get('id', 'UNKNOWN')
            source_field = mapping.get('source_field', 'UNKNOWN')
            target_field = mapping.get('target_field', 'UNKNOWN')
            # target_field_refs carries EVERY target this mapping declares
            # (via a <TargetFields> wrapper) — target_field above is only
            # the first, kept for display/back-compat.
            target_field_refs = mapping.get('target_field_refs') or ([target_field] if target_field and target_field != 'UNKNOWN' else [])
            target_xpath = target_xpath_by_id.get(target_field) if len(target_field_refs) == 1 else None

            expression = mapping.get('formula_expression') or ''
            functions, reference_data, global_variables = extract_all(expression)

            summary = _short_summary(mapping.get('business_rationale'))
            if not summary:
                summary = f"{source_field} -> {target_field} ({mapping.get('formula_type') or 'DIRECT'})"

            keywords = sorted(set(filter(None, [
                source_field, target_field, mapping.get('formula_type'), mapping.get('criticality'),
                *functions, *reference_data,
            ])))

            content = "\n".join(filter(None, [
                f"{source_field} -> {target_field} ({source_msg_type or '?'} -> {target_msg_type or '?'}, {mapping.get('formula_type') or 'DIRECT'})",
                f"Functions: {', '.join(functions)}" if functions else None,
                f"Reference Data: {', '.join(reference_data)}" if reference_data else None,
                summary,
            ]))

            chunks.append(XMLChunk(
                content=content,
                metadata={
                    "chunk_type": "FIELD_MAPPING",
                    "mapping_id": mapping_id, "mapping_name": mapping_name,
                    "element_id": map_id,
                    "doc_id": doc_ids_by_element.get(map_id),
                    "source_message_type": source_msg_type.lower() if source_msg_type else None,
                    "target_message_type": target_msg_type.lower() if target_msg_type else None,
                    "source_field": source_field, "target_field": target_field,
                    "target_all": target_field_refs, "target_xpath": target_xpath,
                    "formula_type": mapping.get('formula_type'),
                    "functions": functions,
                    "reference_data": reference_data,
                    "global_variables": global_variables,
                    "criticality": mapping.get('criticality'),
                    "keywords": keywords,
                    "summary": summary,
                },
                chunk_type="FIELD_MAPPING", chunk_id=f"{mapping_id}_{map_id}"
            ))
        return chunks

    def _chunk_validation_rules(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        validation_rules = mapping_data.get('validation_rules', {})
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        for phase, rules_key in [('Pre-Conversion', 'pre_conversion'), ('Post-Conversion', 'post_conversion')]:
            for rule in validation_rules.get(rules_key, []):
                if not rule:
                    continue
                rule_id = rule.get('id', 'UNKNOWN')
                rule_type = rule.get('type', 'UNKNOWN')
                description = rule.get('description', '')
                phase_code = 'PRE' if phase == 'Pre-Conversion' else 'POST'
                phase_note = "BEFORE" if phase == 'Pre-Conversion' else "AFTER"

                content = f"""Validation Rule: {rule_id}
Type: {rule_type}
Phase: {phase}
Mapping: {mapping_name}

Description:
{description}

This rule is applied {phase_note} the conversion process to ensure data quality."""

                chunks.append(XMLChunk(
                    content=content,
                    metadata={
                        "mapping_id": mapping_id, "mapping_name": mapping_name,
                        "rule_id": rule_id, "rule_type": rule_type,
                        "phase": f"{phase_code}_CONVERSION", "chunk_type": "VALIDATION_RULE",
                        "source": source_msg_type.lower() if source_msg_type else None,
                        "target": target_msg_type.lower() if target_msg_type else None
                    },
                    chunk_type="VALIDATION_RULE", chunk_id=f"{mapping_id}_VAL_{phase_code}_{rule_id}"
                ))
        return chunks

    def _chunk_use_cases(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        general_info = mapping_data.get('general_information', {})
        use_cases = general_info.get('use_cases', [])
        if not use_cases:
            return chunks
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        content_parts = [
            f"Use Cases for {mapping_name}",
            f"Conversion: {general_info.get('source_format')} -> {general_info.get('target_format')}",
            "", "This conversion is used in the following scenarios:", ""
        ]
        for i, use_case in enumerate(use_cases, 1):
            content_parts.append(f"{i}. {use_case}")

        content = "\n".join(content_parts)
        chunks.append(XMLChunk(
            content=content,
            metadata={
                "mapping_id": mapping_id, "mapping_name": mapping_name,
                "use_cases_count": len(use_cases), "chunk_type": "USE_CASE",
                "source": source_msg_type.lower() if source_msg_type else None,
                "target": target_msg_type.lower() if target_msg_type else None
            },
            chunk_type="USE_CASE", chunk_id=f"{mapping_id}_USECASES"
        ))
        return chunks

    def chunk_all_mappings(self, all_mappings: Dict[str, Dict[str, Any]]) -> List[XMLChunk]:
        all_chunks = []
        for mapping_id, mapping_data in all_mappings.items():
            try:
                chunks = self.chunk_mapping(mapping_data)
                all_chunks.extend(chunks)
                logger.info(f"Successfully chunked {mapping_id}: {len(chunks)} chunks")
            except Exception as e:
                logger.error(f"Error chunking {mapping_id}: {str(e)}")
        logger.info(f"Total chunks created: {len(all_chunks)}")
        return all_chunks


xml_chunker = XMLChunker()
