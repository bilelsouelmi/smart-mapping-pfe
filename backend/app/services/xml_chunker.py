"""
XML Chunking Service
Converts XML mappings into semantic chunks for RAG
"""

import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class XMLChunk:
    """Represents a semantic chunk of XML mapping data"""

    def __init__(self, content: str, metadata: Dict[str, Any], chunk_type: str, chunk_id: str):
        self.content = content
        self.metadata = metadata
        self.chunk_type = chunk_type
        self.chunk_id = chunk_id


class XMLChunker:
    """Intelligent chunking of XML mapping files for RAG"""

    def __init__(self):
        self.chunk_types = [
            "GENERAL_INFO", "SOURCE_FIELD", "TARGET_FIELD", "FIELD_MAPPING",
            "VALIDATION_RULE", "USE_CASE", "BUSINESS_CONTEXT", "GLOBAL_VARIABLES",
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
        chunks.extend(self._chunk_global_variables(mapping_data, mapping_id, mapping_name))

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

            related_mapping = next(
                (m for m in mapping_data.get('field_mappings', []) if m.get('source_field') == field_id),
                None
            )
            src_formula_obj = None
            if related_mapping:
                global_info = mapping_data.get('general_information', {}).get('global_variables', {})
                gv_refs = related_mapping.get('global_variable_refs', [])
                src_global_vars = {ref: global_info.get(ref, {}).get('value', '') for ref in gv_refs}
                src_conditions = {
                    f"condition_{c.get('priority', str(i))}": c.get('expression', '')
                    for i, c in enumerate(related_mapping.get('conditions', []), 1)
                }
                src_formula_obj = {
                    "pseudocode": related_mapping.get('formula_pseudocode') or related_mapping.get('formula_expression'),
                    "expression": related_mapping.get('formula_expression'),
                    "details": {"global_variables": src_global_vars, "conditions": src_conditions}
                }

            chunks.append(XMLChunk(
                content=content,
                metadata={
                    "chunk_type": "SOURCE_FIELD", "mapping_id": mapping_id, "mapping_name": mapping_name,
                    "field_id": field_id, "field_name": field_name, "field_tag": field_tag,
                    "message_type": source_type, "side": "SOURCE",
                    "source_message_type": source_msg_type.lower() if source_msg_type else None,
                    "target_message_type": target_msg_type.lower() if target_msg_type else None,
                    "element_id": field.get('element_id'),
                    "target_path": field.get('target_path'),
                    "target_xpath": field.get('target_xpath'),
                    "mapping_formula": src_formula_obj,
                    "formula_type": related_mapping.get('formula_type') if related_mapping else None,
                    "criticality": related_mapping.get('criticality') if related_mapping else None,
                    "audit_requirement": related_mapping.get('audit_requirement') if related_mapping else None,
                    "compliance_requirement": related_mapping.get('compliance_requirement') if related_mapping else None,
                    "data_privacy": related_mapping.get('data_privacy') if related_mapping else None,
                    "migration_note": related_mapping.get('migration_note') if related_mapping else None,
                    "caching_strategy": related_mapping.get('caching_strategy') if related_mapping else None,
                    "performance_impact": related_mapping.get('performance_impact') if related_mapping else None,
                    "has_audit_requirement": bool(related_mapping.get('audit_requirement')) if related_mapping else False,
                    "has_compliance_requirement": bool(related_mapping.get('compliance_requirement')) if related_mapping else False,
                    "has_migration_note": bool(related_mapping.get('migration_note')) if related_mapping else False,
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
            tgt_formula_obj = None
            if related_mapping:
                global_info = mapping_data.get('general_information', {}).get('global_variables', {})
                gv_refs = related_mapping.get('global_variable_refs', [])
                tgt_global_vars = {ref: global_info.get(ref, {}).get('value', '') for ref in gv_refs}
                tgt_conditions = {
                    f"condition_{c.get('priority', str(i))}": c.get('expression', '')
                    for i, c in enumerate(related_mapping.get('conditions', []), 1)
                }
                tgt_formula_obj = {
                    "pseudocode": related_mapping.get('formula_pseudocode') or related_mapping.get('formula_expression'),
                    "expression": related_mapping.get('formula_expression'),
                    "details": {"global_variables": tgt_global_vars, "conditions": tgt_conditions}
                }

            chunks.append(XMLChunk(
                content=content,
                metadata={
                    "chunk_type": "TARGET_FIELD", "mapping_id": mapping_id, "mapping_name": mapping_name,
                    "field_id": field_id, "field_name": field_name, "field_tag": field_tag,
                    "message_type": target_type, "side": "TARGET",
                    "is_entity": field.get('is_entity', False),
                    "source_message_type": source_msg_type.lower() if source_msg_type else None,
                    "target_message_type": target_msg_type.lower() if target_msg_type else None,
                    # NOUVEAU : utilisé par generate-elements en sens ISO -> MT
                    "source_mt": source_mt,
                    "mapping_formula": tgt_formula_obj,
                    "formula_type": related_mapping.get('formula_type') if related_mapping else None,
                    "criticality": related_mapping.get('criticality') if related_mapping else None,
                    "audit_requirement": related_mapping.get('audit_requirement') if related_mapping else None,
                    "compliance_requirement": related_mapping.get('compliance_requirement') if related_mapping else None,
                    "data_privacy": related_mapping.get('data_privacy') if related_mapping else None,
                    "migration_note": related_mapping.get('migration_note') if related_mapping else None,
                    "caching_strategy": related_mapping.get('caching_strategy') if related_mapping else None,
                    "performance_impact": related_mapping.get('performance_impact') if related_mapping else None,
                    "has_audit_requirement": bool(related_mapping.get('audit_requirement')) if related_mapping else False,
                    "has_compliance_requirement": bool(related_mapping.get('compliance_requirement')) if related_mapping else False,
                    "has_migration_note": bool(related_mapping.get('migration_note')) if related_mapping else False,
                },
                chunk_type="TARGET_FIELD", chunk_id=f"{mapping_id}_TGT_{field_id}"
            ))
        return chunks

    def _chunk_field_mappings(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        field_mappings = mapping_data.get('field_mappings', [])
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        for mapping in field_mappings:
            if not mapping:
                continue
            map_id = mapping.get('id', 'UNKNOWN')
            source_field = mapping.get('source_field', 'UNKNOWN')
            target_field = mapping.get('target_field', 'UNKNOWN')
            # target_field_refs carries EVERY target this mapping declares
            # (via a <TargetFields> wrapper) — target_field above is only
            # the first, kept for display/back-compat. Resolved to actual
            # target_path strings in xml_chunker's caller via TARGET_FIELD
            # chunks; here we just pass the raw internal refs through so
            # exact_rag_lookup can look each one up.
            target_field_refs = mapping.get('target_field_refs') or ([target_field] if target_field and target_field != 'UNKNOWN' else [])

            content_parts = [
                f"Field Mapping: {source_field} -> {target_field}",
                f"Mapping ID: {map_id}", f"Conversion: {mapping_name}", ""
            ]
            if mapping.get('criticality'):
                content_parts.append(f"Criticality: {mapping['criticality']}")
            if mapping.get('formula_type'):
                content_parts.extend(["", f"Transformation Type: {mapping['formula_type']}"])
            if mapping.get('formula_expression'):
                content_parts.extend(["", "Transformation Logic:", mapping['formula_expression']])
            conditions = mapping.get('conditions', [])
            if conditions:
                content_parts.extend(["", f"Validation Conditions ({len(conditions)}):"])
                for i, condition in enumerate(conditions, 1):
                    cond_type = condition.get('type', 'UNKNOWN')
                    cond_expr = condition.get('expression', '')
                    cond_action = condition.get('action', '')
                    content_parts.append(f"{i}. {cond_type}: {cond_expr} -> {cond_action}")
            if mapping.get('business_rationale'):
                content_parts.extend(["", "Business Rationale:", mapping['business_rationale']])
            if mapping.get('impact_if_fails'):
                content_parts.extend(["", "Impact if Mapping Fails:", mapping['impact_if_fails']])
            if mapping.get('performance_impact'):
                content_parts.extend(["", f"Performance Impact: {mapping['performance_impact']}"])
            if mapping.get('audit_requirement'):
                content_parts.extend(["", "Audit Requirement:", mapping['audit_requirement']])
            if mapping.get('compliance_requirement'):
                content_parts.extend(["", "Compliance Requirement:", mapping['compliance_requirement']])
            if mapping.get('data_privacy'):
                content_parts.extend(["", "Data Privacy (GDPR):", mapping['data_privacy']])
            if mapping.get('migration_note'):
                content_parts.extend(["", "Migration Note:", mapping['migration_note']])
            if mapping.get('caching_strategy'):
                content_parts.extend(["", "Caching Strategy:", mapping['caching_strategy']])
            if mapping.get('global_variable_refs'):
                content_parts.extend(["", f"Global Variables Used: {', '.join(mapping['global_variable_refs'])}"])

            content = "\n".join(content_parts)
            keywords = [source_field, target_field, mapping.get('formula_type', ''), mapping.get('criticality', '')]

            global_info = mapping_data.get('general_information', {}).get('global_variables', {})
            gv_refs = mapping.get('global_variable_refs', [])
            global_vars_dict = {
                ref: global_info.get(ref, {}).get('value', '') if ref in global_info else ''
                for ref in gv_refs
            } if gv_refs else {}
            conditions_dict = {
                f"condition_{c.get('priority', str(i))}": c.get('expression', '')
                for i, c in enumerate(mapping.get('conditions', []), 1)
            } if mapping.get('conditions') else {}
            mapping_formula_obj = {
                "pseudocode": mapping.get("formula_pseudocode") or mapping.get("formula_expression"),
                "expression": mapping.get("formula_expression"),
                "details": {"global_variables": global_vars_dict, "conditions": conditions_dict}
            }

            chunks.append(XMLChunk(
                content=content,
                metadata={
                    "chunk_type": "FIELD_MAPPING", "mapping_id": mapping_id, "mapping_name": mapping_name,
                    "map_id": map_id, "source": source_field, "target": target_field,
                    "target_all": target_field_refs, "element_id": map_id,
                    "mapping_formula": mapping_formula_obj,
                    "source_message_type": source_msg_type.lower() if source_msg_type else None,
                    "target_message_type": target_msg_type.lower() if target_msg_type else None,
                    "criticality": mapping.get('criticality'), "formula_type": mapping.get('formula_type'),
                    "keywords": ", ".join([k for k in keywords if k]),
                    "has_audit_requirement": bool(mapping.get('audit_requirement')),
                    "has_compliance_requirement": bool(mapping.get('compliance_requirement')),
                    "has_migration_note": bool(mapping.get('migration_note')),
                    "performance_impact": mapping.get('performance_impact'),
                    "audit_requirement": mapping.get('audit_requirement'),
                    "compliance_requirement": mapping.get('compliance_requirement'),
                    "data_privacy": mapping.get('data_privacy'),
                    "migration_note": mapping.get('migration_note'),
                    "caching_strategy": mapping.get('caching_strategy'),
                },
                chunk_type="FIELD_MAPPING", chunk_id=f"{mapping_id}_MAP_{map_id}"
            ))
        return chunks

    def _chunk_global_variables(self, mapping_data, mapping_id, mapping_name):
        chunks = []
        general_info = mapping_data.get('general_information', {})
        global_vars = general_info.get('global_variables', {})
        if not global_vars:
            return chunks
        source_msg_type = mapping_data.get('source_message', {}).get('message_type', '')
        target_msg_type = mapping_data.get('target_message', {}).get('message_type', '')

        content_parts = [
            f"Global Variables and Configuration for {mapping_name}",
            f"Conversion: {general_info.get('source_format', 'N/A')} -> {general_info.get('target_format', 'N/A')}",
            "", "These variables control the behavior of all mappings in this conversion:", ""
        ]
        for name, var_info in global_vars.items():
            value = var_info.get('value', 'N/A')
            var_type = var_info.get('type', 'STRING')
            description = var_info.get('description', '')
            currency = var_info.get('currency', '')
            currency_str = f" [{currency}]" if currency else ""
            content_parts.append(f"- {name} = {value}{currency_str} ({var_type}): {description}")

        content = "\n".join(content_parts)
        chunks.append(XMLChunk(
            content=content,
            metadata={
                "mapping_id": mapping_id, "mapping_name": mapping_name,
                "chunk_type": "GLOBAL_VARIABLES", "variables_count": len(global_vars),
                "source": source_msg_type.lower() if source_msg_type else None,
                "target": target_msg_type.lower() if target_msg_type else None
            },
            chunk_type="GLOBAL_VARIABLES", chunk_id=f"{mapping_id}_GLOBALVARS"
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