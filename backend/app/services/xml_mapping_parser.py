"""
XML Mapping Parser Service
Parses XML mapping files and extracts structured data
"""

import os
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any
from pathlib import Path
import logging
import traceback

logger = logging.getLogger(__name__)


class XMLMappingParser:
    """
    Service to parse XML mapping files from the mappings directory
    """

    def __init__(self, mappings_dir: str = "dataset/mappings"):
        self.mappings_dir = Path(mappings_dir)
        self.mappings_cache: Dict[str, Dict[str, Any]] = {}
        print(f"XMLMappingParser initialized with dir: {self.mappings_dir}")

    def load_all_mappings(self) -> Dict[str, Dict[str, Any]]:
        """
        Load all XML mapping files from the mappings directory
        Returns dict with mapping_id as key
        """
        print(f"\n{'='*60}")
        print(f"=== DEBUG XML PARSER - load_all_mappings() CALLED ===")
        print(f"{'='*60}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Mappings directory path: {self.mappings_dir}")
        print(f"Mappings directory absolute: {self.mappings_dir.absolute()}")
        print(f"Mappings directory exists: {self.mappings_dir.exists()}")
        print(f"Cache status: {len(self.mappings_cache)} items cached")
        
        if self.mappings_cache:
            print(f"⚠️ WARNING: Returning cached mappings ({len(self.mappings_cache)} items)")
            print(f"Cached IDs: {list(self.mappings_cache.keys())}")
            return self.mappings_cache
            
        xml_files = list(self.mappings_dir.glob("*.xml"))
        
        print(f"\n📄 XML files found: {len(xml_files)}")
        for i, f in enumerate(xml_files, 1):
            print(f"  {i}. {f.name} ({f.stat().st_size} bytes)")
        print(f"{'='*60}\n")
        
        logger.info(f"Found {len(xml_files)} XML mapping files")
        
        # Parse each file
        for xml_file in xml_files:
            print(f"\n🔍 Attempting to parse: {xml_file.name}")
            print(f"   Full path: {xml_file.absolute()}")
            try:
                mapping_data = self.parse_xml_file(xml_file)
                print(f"   ✅ Parsed successfully!")
                print(f"   Keys in mapping_data: {list(mapping_data.keys())}")
                
                mapping_id = mapping_data.get("mapping_id")
                print(f"   mapping_id extracted: '{mapping_id}' (type: {type(mapping_id)})")
                
                if mapping_id:
                    self.mappings_cache[mapping_id] = mapping_data
                    logger.info(f"Loaded mapping: {mapping_id}")
                    print(f"   ✅ ADDED to cache with ID: '{mapping_id}'")
                else:
                    print(f"   ⚠️ WARNING: No mapping_id found!")
                    print(f"   general_information: {mapping_data.get('general_information')}")
                    fallback_id = xml_file.stem
                    print(f"   Using filename as fallback ID: '{fallback_id}'")
                    self.mappings_cache[fallback_id] = mapping_data
                    mapping_data["mapping_id"] = fallback_id
                    print(f"   ✅ ADDED to cache with fallback ID: '{fallback_id}'")
                    
            except Exception as e:
                logger.error(f"Error parsing {xml_file.name}: {str(e)}")
                print(f"   ❌ EXCEPTION during parsing:")
                print(f"   {type(e).__name__}: {str(e)}")
                traceback.print_exc()
                continue

        print(f"\n{'='*60}")
        print(f"=== FINAL RESULTS ===")
        print(f"mappings_cache size: {len(self.mappings_cache)}")
        print(f"Mapping IDs in cache: {list(self.mappings_cache.keys())}")
        print(f"{'='*60}\n")
                
        return self.mappings_cache

    def parse_xml_file(self, xml_path: Path) -> Dict[str, Any]:
        """
        Parse a single XML mapping file and extract all relevant data
        """
        print(f"      → parse_xml_file() called for {xml_path.name}")
        tree = ET.parse(xml_path)
        root = tree.getroot()
        print(f"      → XML parsed, root tag: {root.tag}")

        # Extract namespace
        ns_match = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
        ns = {'ns': ns_match} if ns_match else {}
        print(f"      → Namespace detected: '{ns_match}'")

        # Extract General Information
        print(f"      → Extracting general information...")
        general_info = self._parse_general_information(root, ns)
        print(f"      → general_info keys: {list(general_info.keys())}")
        print(f"      → mapping_id from general_info: '{general_info.get('mapping_id')}'")

        # Extract Source Message
        source_message = self._parse_source_message(root, ns)

        # Extract Target Message
        target_message = self._parse_target_message(root, ns)

        # Extract Field Mappings
        field_mappings = self._parse_field_mappings(root, ns)

        # Extract Validation Rules
        validation_rules = self._parse_validation_rules(root, ns)

        # Build complete mapping object
        mapping_data = {
            "file_name": xml_path.name,
            "mapping_id": general_info.get("mapping_id"),
            "mapping_name": general_info.get("mapping_name"),
            "version": general_info.get("version"),
            "status": general_info.get("status"),
            "general_information": general_info,
            "source_message": source_message,
            "target_message": target_message,
            "field_mappings": field_mappings,
            "validation_rules": validation_rules,
            "statistics": self._calculate_statistics(source_message, target_message, field_mappings)
        }

        print(f"      → Built mapping_data, mapping_id: '{mapping_data.get('mapping_id')}'")
        return mapping_data

    def _parse_general_information(self, root: ET.Element, ns: dict) -> Dict[str, Any]:
        """Extract general information section"""
        general_info = {}

        # Try to find GeneralInformation with and without namespace
        gen_info_elem = None
        if ns and ns.get('ns'):
            gen_info_elem = root.find('.//ns:GeneralInformation', ns)
        if gen_info_elem is None:
            gen_info_elem = root.find('.//GeneralInformation')
        
        if gen_info_elem is None:
            print(f"         ⚠️ GeneralInformation element not found!")
            return general_info

        print(f"         ✅ GeneralInformation element found")

        # Basic fields
        fields = [
            'MappingId', 'MappingName', 'Version', 'CreatedDate',
            'CreatedBy', 'LastModifiedDate', 'Status'
        ]

        for field in fields:
            elem = None
            if ns and ns.get('ns'):
                elem = gen_info_elem.find(f'.//ns:{field}', ns)
            if elem is None:
                elem = gen_info_elem.find(f'.//{field}')
            
            print(f"         → Searching for {field}: {'FOUND ✓' if elem is not None else 'NOT FOUND ✗'}")
            
            if elem is not None and elem.text:
                key = field[0].lower() + field[1:]
                key = ''.join(['_' + c.lower() if c.isupper() else c for c in key]).lstrip('_')
                general_info[key] = elem.text.strip()
                print(f"            Extracted: '{elem.text.strip()}'")

        # Business Context
        business_ctx = None
        if ns and ns.get('ns'):
            business_ctx = gen_info_elem.find('.//ns:BusinessContext', ns)
        if business_ctx is None:
            business_ctx = gen_info_elem.find('.//BusinessContext')
            
        if business_ctx is not None:
            desc_elem = None
            if ns and ns.get('ns'):
                desc_elem = business_ctx.find('ns:Description', ns)
            if desc_elem is None:
                desc_elem = business_ctx.find('Description')
                
            if desc_elem is not None and desc_elem.text:
                general_info['description'] = desc_elem.text.strip()

            # Use cases
            use_cases = []
            uc_list = business_ctx.findall('.//ns:UseCase', ns) if ns and ns.get('ns') else []
            if not uc_list:
                uc_list = business_ctx.findall('.//UseCase')
            for uc in uc_list:
                if uc.text:
                    use_cases.append(uc.text.strip())
            general_info['use_cases'] = use_cases

        # Technical Specifications
        tech_specs = None
        if ns and ns.get('ns'):
            tech_specs = gen_info_elem.find('.//ns:TechnicalSpecifications', ns)
        if tech_specs is None:
            tech_specs = gen_info_elem.find('.//TechnicalSpecifications')
            
        if tech_specs is not None:
            general_info['source_format'] = self._get_text(tech_specs, 'SourceFormat', ns)
            general_info['target_format'] = self._get_text(tech_specs, 'TargetFormat', ns)
            general_info['processing_mode'] = self._get_text(tech_specs, 'ProcessingMode', ns)

        # ── NOUVEAU : GlobalVariables ──────────────────────────────────────────
        global_vars_elem = None
        if ns and ns.get('ns'):
            global_vars_elem = gen_info_elem.find('.//ns:GlobalVariables', ns)
        if global_vars_elem is None:
            global_vars_elem = gen_info_elem.find('.//GlobalVariables')

        if global_vars_elem is not None:
            global_vars = {}
            var_list = global_vars_elem.findall('ns:Variable', ns) if ns and ns.get('ns') else []
            if not var_list:
                var_list = global_vars_elem.findall('Variable')
            for var in var_list:
                name = var.get('name')
                value = var.get('value')
                var_type = var.get('type', 'STRING')
                description = var.get('description', '')
                currency = var.get('currency', '')
                if name:
                    global_vars[name] = {
                        'value': value,
                        'type': var_type,
                        'description': description,
                        'currency': currency
                    }
            general_info['global_variables'] = global_vars
            print(f"         → GlobalVariables extracted: {len(global_vars)} variables")
        # ── FIN NOUVEAU ────────────────────────────────────────────────────────

        return general_info

    def _parse_source_message(self, root: ET.Element, ns: dict) -> Dict[str, Any]:
        """Extract source message structure"""
        source_elem = None
        if ns and ns.get('ns'):
            source_elem = root.find('.//ns:SourceMessage', ns)
        if source_elem is None:
            source_elem = root.find('.//SourceMessage')
            
        if source_elem is None:
            return {}

        source_data = {
            'message_type': self._get_text(source_elem, 'MessageType', ns),
            'message_name': self._get_text(source_elem, 'MessageName', ns),
            'standard': self._get_text(source_elem, 'Standard', ns),
            'fields': []
        }

        fields_elem = None
        if ns and ns.get('ns'):
            fields_elem = source_elem.find('.//ns:Fields', ns)
        if fields_elem is None:
            fields_elem = source_elem.find('.//Fields')
            
        if fields_elem is not None:
            field_list = fields_elem.findall('ns:Field', ns) if ns and ns.get('ns') else []
            if not field_list:
                field_list = fields_elem.findall('Field')
            for field in field_list:
                field_data = self._parse_field(field, ns)
                if field_data:
                    source_data['fields'].append(field_data)

        return source_data

    def _parse_target_message(self, root: ET.Element, ns: dict) -> Dict[str, Any]:
        """Extract target message structure"""
        target_elem = None
        if ns and ns.get('ns'):
            target_elem = root.find('.//ns:TargetMessage', ns)
        if target_elem is None:
            target_elem = root.find('.//TargetMessage')
        if target_elem is None:
            if ns and ns.get('ns'):
                target_elem = root.find('.//ns:TargetSystem', ns)
            if target_elem is None:
                target_elem = root.find('.//TargetSystem')
        if target_elem is None:
            return {}

        target_data = {
            'message_type': self._get_text(target_elem, 'MessageType', ns) or self._get_text(target_elem, 'SystemName', ns),
            'message_name': self._get_text(target_elem, 'MessageName', ns) or self._get_text(target_elem, 'SystemType', ns),
            'standard': self._get_text(target_elem, 'Standard', ns) or self._get_text(target_elem, 'DataFormat', ns),
            'fields': []
        }

        fields_elem = None
        if ns and ns.get('ns'):
            fields_elem = target_elem.find('.//ns:Fields', ns)
        if fields_elem is None:
            fields_elem = target_elem.find('.//Fields')
            
        entities_elem = None
        if ns and ns.get('ns'):
            entities_elem = target_elem.find('.//ns:Entities', ns)
        if entities_elem is None:
            entities_elem = target_elem.find('.//Entities')

        if fields_elem is not None:
            field_list = fields_elem.findall('ns:Field', ns) if ns and ns.get('ns') else []
            if not field_list:
                field_list = fields_elem.findall('Field')
            for field in field_list:
                field_data = self._parse_field(field, ns)
                if field_data:
                    target_data['fields'].append(field_data)
        elif entities_elem is not None:
            entity_list = entities_elem.findall('ns:Entity', ns) if ns and ns.get('ns') else []
            if not entity_list:
                entity_list = entities_elem.findall('Entity')
            for entity in entity_list:
                entity_data = self._parse_entity(entity, ns)
                if entity_data:
                    target_data['fields'].append(entity_data)

        return target_data

    def _parse_field(self, field_elem: ET.Element, ns: dict) -> Dict[str, Any]:
        """Parse a single field element"""
        field_id = field_elem.get('id', '')

        field_data = {
            'id': field_id,
            'field_tag': self._get_text(field_elem, 'FieldTag', ns),
            'field_name': self._get_text(field_elem, 'FieldName', ns),
            'xpath': self._get_text(field_elem, 'XPath', ns),
            'data_type': self._get_text(field_elem, 'DataType', ns),
            'max_length': self._get_text(field_elem, 'MaxLength', ns),
            'mandatory': self._get_text(field_elem, 'Mandatory', ns),
            'description': self._get_text(field_elem, 'Description', ns),
            'example_value': self._get_text(field_elem, 'ExampleValue', ns),
            # ── NOUVEAU : ElementId + TargetPath ──────────────────────────────
            'element_id': self._get_text(field_elem, 'ElementId', ns),
            'target_path': self._get_text(field_elem, 'TargetPath', ns),
            'target_xpath': self._get_text(field_elem, 'TargetXPath', ns),
            # ── FIN NOUVEAU ───────────────────────────────────────────────────
        }

        # Parse Components if present
        components_elem = field_elem.find('Components')
        if components_elem is None and ns:
            components_elem = field_elem.find('ns:Components', ns)
        if components_elem is not None:
            components = []
            comp_list = components_elem.findall('Component')
            if not comp_list and ns:
                comp_list = components_elem.findall('ns:Component', ns)
            for comp in comp_list:
                comp_data = {
                    'name': comp.get('name'),
                    'type': comp.get('type'),
                    'format': comp.get('format'),
                    'target_path': comp.get('targetPath'),
                    'description': comp.get('description'),
                }
                comp_data = {k: v for k, v in comp_data.items() if v is not None}
                components.append(comp_data)
            if components:
                field_data['components'] = components

        field_data = {k: v for k, v in field_data.items() if v is not None}
        return field_data

    def _parse_entity(self, entity_elem: ET.Element, ns: dict) -> Dict[str, Any]:
        """Parse an entity element (for core banking target)"""
        entity_data = {
            'id': entity_elem.get('id', ''),
            'entity_name': self._get_text(entity_elem, 'EntityName', ns),
            'entity_type': self._get_text(entity_elem, 'EntityType', ns),
            'api_endpoint': self._get_text(entity_elem, 'APIEndpoint', ns),
            'description': self._get_text(entity_elem, 'Description', ns),
            'is_entity': True
        }

        entity_data = {k: v for k, v in entity_data.items() if v is not None}
        return entity_data

    def _parse_field_mappings(self, root: ET.Element, ns: dict) -> List[Dict[str, Any]]:
        """Extract field mappings"""
        mappings = []

        mappings_elem = None
        if ns and ns.get('ns'):
            mappings_elem = root.find('.//ns:FieldMappings', ns)
        if mappings_elem is None:
            mappings_elem = root.find('.//FieldMappings')
            
        if mappings_elem is None:
            return mappings

        mapping_list = mappings_elem.findall('ns:Mapping', ns) if ns and ns.get('ns') else []
        if not mapping_list:
            mapping_list = mappings_elem.findall('Mapping')
            
        for mapping in mapping_list:
            mapping_id = mapping.get('id', '')

            mapping_data = {
                'id': mapping_id,
                'source_field': self._get_attribute(mapping, 'SourceField', 'ref', ns),
                'target_field': self._get_attribute(mapping, 'TargetField', 'ref', ns),
                'formula_type': None,
                'formula_expression': None,
                'conditions': [],
                'criticality': None,
                'impact_if_fails': None,
                'business_rationale': None,
                # ── NOUVEAU : champs enrichis ──────────────────────────────────
                'performance_impact': None,
                'audit_requirement': None,
                'compliance_requirement': None,
                'data_privacy': None,
                'migration_note': None,
                'caching_strategy': None,
                'global_variable_refs': [],
                # ── FIN NOUVEAU ────────────────────────────────────────────────
            }

            # MappingFormula
            formula_elem = None
            if ns and ns.get('ns'):
                formula_elem = mapping.find('.//ns:MappingFormula', ns)
            if formula_elem is None:
                formula_elem = mapping.find('.//MappingFormula')
                
            if formula_elem is not None:
                type_elem = None
                if ns and ns.get('ns'):
                    type_elem = formula_elem.find('ns:Type', ns)
                if type_elem is None:
                    type_elem = formula_elem.find('Type')
                if type_elem is not None and type_elem.text:
                    mapping_data['formula_type'] = type_elem.text.strip()

                expr_elem = None
                if ns and ns.get('ns'):
                    expr_elem = formula_elem.find('ns:Expression', ns)
                if expr_elem is None:
                    expr_elem = formula_elem.find('Expression')
                if expr_elem is not None and expr_elem.text:
                    mapping_data['formula_expression'] = expr_elem.text.strip()

                # ── NOUVEAU : extraire PseudoCode ─────────────────────────────
                pseudo_elem = None
                if ns and ns.get("ns"):
                    pseudo_elem = formula_elem.find("ns:PseudoCode", ns)
                if pseudo_elem is None:
                    pseudo_elem = formula_elem.find("PseudoCode")
                if pseudo_elem is not None and pseudo_elem.text:
                    mapping_data["formula_pseudocode"] = pseudo_elem.text.strip()
                # ── FIN NOUVEAU ───────────────────────────────────────────────

            # Conditions
            conditions_elem = None
            if ns and ns.get('ns'):
                conditions_elem = mapping.find('.//ns:Conditions', ns)
            if conditions_elem is None:
                conditions_elem = mapping.find('.//Conditions')
                
            if conditions_elem is not None:
                cond_list = conditions_elem.findall('ns:Condition', ns) if ns and ns.get('ns') else []
                if not cond_list:
                    cond_list = conditions_elem.findall('Condition')
                for condition in cond_list:
                    cond_data = {
                        'priority': condition.get('priority', ''),
                        'type': self._get_text(condition, 'Type', ns),
                        'expression': self._get_text(condition, 'Expression', ns),
                        'action': self._get_text(condition, 'Action', ns)
                    }
                    mapping_data['conditions'].append(cond_data)

            # General section
            general_elem = None
            if ns and ns.get('ns'):
                general_elem = mapping.find('.//ns:General', ns)
            if general_elem is None:
                general_elem = mapping.find('.//General')
                
            if general_elem is not None:
                mapping_data['criticality'] = self._get_text(general_elem, 'Criticality', ns)
                mapping_data['impact_if_fails'] = self._get_text(general_elem, 'ImpactIfFails', ns)
                mapping_data['business_rationale'] = self._get_text(general_elem, 'BusinessRationale', ns)
                # ── NOUVEAU : 5 nouveaux champs General ───────────────────────
                mapping_data['performance_impact'] = self._get_text(general_elem, 'PerformanceImpact', ns)
                mapping_data['audit_requirement'] = self._get_text(general_elem, 'AuditRequirement', ns)
                mapping_data['compliance_requirement'] = self._get_text(general_elem, 'ComplianceRequirement', ns)
                mapping_data['data_privacy'] = self._get_text(general_elem, 'DataPrivacy', ns)
                mapping_data['migration_note'] = self._get_text(general_elem, 'MigrationNote', ns)
                mapping_data['caching_strategy'] = self._get_text(general_elem, 'CachingStrategy', ns)
                # ── FIN NOUVEAU ────────────────────────────────────────────────

            # ── NOUVEAU : GlobalVariables par mapping ──────────────────────────
            gv_elem = None
            if ns and ns.get('ns'):
                gv_elem = mapping.find('.//ns:GlobalVariables', ns)
            if gv_elem is None:
                gv_elem = mapping.find('.//GlobalVariables')

            if gv_elem is not None:
                var_refs = []
                var_list = gv_elem.findall('ns:Variable', ns) if ns and ns.get('ns') else []
                if not var_list:
                    var_list = gv_elem.findall('Variable')
                for var in var_list:
                    ref = var.get('ref') or var.get('name')
                    if ref:
                        var_refs.append(ref)
                mapping_data['global_variable_refs'] = var_refs
            # ── FIN NOUVEAU ────────────────────────────────────────────────────

            mappings.append(mapping_data)

        return mappings

    def _parse_validation_rules(self, root: ET.Element, ns: dict) -> Dict[str, Any]:
        """Extract validation rules"""
        validation_data = {
            'pre_conversion': [],
            'post_conversion': []
        }

        val_rules_elem = None
        if ns and ns.get('ns'):
            val_rules_elem = root.find('.//ns:ValidationRules', ns)
        if val_rules_elem is None:
            val_rules_elem = root.find('.//ValidationRules')
            
        if val_rules_elem is None:
            return validation_data

        pre_elem = None
        if ns and ns.get('ns'):
            pre_elem = val_rules_elem.find('.//ns:PreConversionRules', ns)
        if pre_elem is None:
            pre_elem = val_rules_elem.find('.//PreConversionRules')
            
        if pre_elem is not None:
            rule_list = pre_elem.findall('ns:Rule', ns) if ns and ns.get('ns') else []
            if not rule_list:
                rule_list = pre_elem.findall('Rule')
            for rule in rule_list:
                rule_data = {
                    'id': rule.get('id', ''),
                    'type': rule.get('type', ''),
                    'description': self._get_text(rule, 'Description', ns)
                }
                validation_data['pre_conversion'].append(rule_data)

        post_elem = None
        if ns and ns.get('ns'):
            post_elem = val_rules_elem.find('.//ns:PostConversionRules', ns)
        if post_elem is None:
            post_elem = val_rules_elem.find('.//PostConversionRules')
            
        if post_elem is not None:
            rule_list = post_elem.findall('ns:Rule', ns) if ns and ns.get('ns') else []
            if not rule_list:
                rule_list = post_elem.findall('Rule')
            for rule in rule_list:
                rule_data = {
                    'id': rule.get('id', ''),
                    'type': rule.get('type', ''),
                    'description': self._get_text(rule, 'Description', ns)
                }
                validation_data['post_conversion'].append(rule_data)

        return validation_data

    def _calculate_statistics(self, source: Dict, target: Dict, mappings: List) -> Dict[str, int]:
        """Calculate statistics about the mapping"""
        return {
            'source_fields_count': len(source.get('fields', [])),
            'target_fields_count': len(target.get('fields', [])),
            'mappings_count': len(mappings),
            'critical_mappings': len([m for m in mappings if m.get('criticality') == 'CRITICAL']),
            'high_mappings': len([m for m in mappings if m.get('criticality') == 'HIGH']),
            'medium_mappings': len([m for m in mappings if m.get('criticality') == 'MEDIUM']),
            'low_mappings': len([m for m in mappings if m.get('criticality') == 'LOW'])
        }

    def _get_text(self, parent: ET.Element, tag: str, ns: dict) -> Optional[str]:
        """Helper to get text from element with namespace handling"""
        elem = None
        if ns and ns.get('ns'):
            elem = parent.find(f'ns:{tag}', ns)
        if elem is None:
            elem = parent.find(tag)
        if elem is not None and elem.text:
            return elem.text.strip()
        return None

    def _get_attribute(self, parent: ET.Element, tag: str, attr: str, ns: dict) -> Optional[str]:
        """Helper to get attribute from element"""
        elem = None
        if ns and ns.get('ns'):
            elem = parent.find(f'ns:{tag}', ns)
        if elem is None:
            elem = parent.find(tag)
        if elem is not None:
            return elem.get(attr)
        return None

    def get_mapping_by_id(self, mapping_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific mapping by ID"""
        if not self.mappings_cache:
            self.load_all_mappings()
        return self.mappings_cache.get(mapping_id)

    def get_all_mapping_summaries(self) -> List[Dict[str, Any]]:
        """Get summary of all mappings for listing"""
        if not self.mappings_cache:
            self.load_all_mappings()

        summaries = []
        for mapping_id, mapping_data in self.mappings_cache.items():
            summary = {
                'mapping_id': mapping_id,
                'mapping_name': mapping_data.get('mapping_name'),
                'version': mapping_data.get('version'),
                'status': mapping_data.get('status'),
                'source_format': mapping_data.get('general_information', {}).get('source_format'),
                'target_format': mapping_data.get('general_information', {}).get('target_format'),
                'statistics': mapping_data.get('statistics', {})
            }
            summaries.append(summary)

        return summaries


# Singleton instance
xml_parser = XMLMappingParser()