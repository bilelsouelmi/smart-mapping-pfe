"""
SWIFT MT Text Parser — Dynamic Version
Reads MT field definitions dynamically from dataset/mappings/*.xml files.
No hardcoded tags — fully driven by XML mapping files.
Supports MT103, MT202, MT940 and any future MT type with a mapping file.
"""

import re
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ISO 20022 target by MT type
MT_TO_ISO_TARGET = {
    "MT103": "pacs.008.001.08",
    "MT202": "pacs.009.001.08",
    "MT940": "camt.053.001.08",
    "MT900": "camt.054.001.08",
    "MT910": "camt.054.001.08",
}

# MT type signatures — minimum tags to identify each MT type
MT_TYPE_SIGNATURES = {
    "MT103": ["20", "32A", "50K", "59", "71A"],
    "MT202": ["20", "21", "32A", "52A", "58A"],
    "MT940": ["20", "25", "28C", "60F", "62F"],
}

# Mapping files for each MT type
MT_MAPPING_FILES = {
    "MT103": "MT103_to_pacs008.xml",
    "MT202": "MT202_to_pacs009.xml",
    "MT940": "MT940_to_camt053.xml",
}

# Mappings directory
MAPPINGS_DIR = Path("/app/dataset/mappings")


class SWIFTTextParser:
    """
    Parser for SWIFT MT text format files.
    Field definitions are loaded dynamically from XML mapping files.
    Supports MT103, MT202, MT940.
    """

    def __init__(self):
        self._tag_definitions_cache: Dict[str, Dict] = {}

    # ── Step 1: Load tag definitions from XML ────────────────────────────────

    def _load_tag_definitions(self, mt_type: str) -> Dict[str, Any]:
        """
        Load field tag definitions from the corresponding XML mapping file.
        Returns dict: { "20": {name, format, type, mandatory}, "32A": {...}, ... }
        """
        if mt_type in self._tag_definitions_cache:
            return self._tag_definitions_cache[mt_type]

        mapping_file = MT_MAPPING_FILES.get(mt_type)
        if not mapping_file:
            logger.warning(f"No mapping file configured for {mt_type}")
            return {}

        xml_path = MAPPINGS_DIR / mapping_file
        if not xml_path.exists():
            logger.warning(f"Mapping file not found: {xml_path}")
            return {}

        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # Handle namespace
            ns_match = root.tag.split('}')[0].strip('{') if '}' in root.tag else ''
            ns = {'ns': ns_match} if ns_match else {}

            tag_defs = {}

            # Find SourceMessage/Fields
            fields_elem = None
            if ns:
                fields_elem = root.find('.//ns:SourceMessage/ns:Fields', ns)
            if fields_elem is None:
                fields_elem = root.find('.//SourceMessage/Fields')
            if fields_elem is None:
                fields_elem = root.find('.//Fields')

            if fields_elem is None:
                logger.warning(f"No Fields element found in {mapping_file}")
                return {}

            field_list = fields_elem.findall('Field')
            if not field_list and ns:
                field_list = fields_elem.findall('ns:Field', ns)

            for field in field_list:
                # Get FieldTag
                tag_elem = field.find('FieldTag')
                if tag_elem is None and ns:
                    tag_elem = field.find('ns:FieldTag', ns)
                if tag_elem is None or not tag_elem.text:
                    continue

                # Clean tag: ":20:" → "20", ":32A:" → "32A"
                raw_tag = tag_elem.text.strip().strip(':')

                # Get FieldName
                name_elem = field.find('FieldName') or (field.find('ns:FieldName', ns) if ns else None)
                field_name = name_elem.text.strip() if name_elem is not None and name_elem.text else raw_tag

                # Get DataType
                type_elem = field.find('DataType') or (field.find('ns:DataType', ns) if ns else None)
                data_type = type_elem.text.strip().upper() if type_elem is not None and type_elem.text else 'STRING'

                # Get Format
                format_elem = field.find('Format') or (field.find('ns:Format', ns) if ns else None)
                format_val = format_elem.text.strip() if format_elem is not None and format_elem.text else '35x'

                # Get Mandatory
                mandatory_elem = field.find('Mandatory') or (field.find('ns:Mandatory', ns) if ns else None)
                mandatory = mandatory_elem.text.strip().lower() == 'true' if mandatory_elem is not None and mandatory_elem.text else False

                # Get MaxLength
                maxlen_elem = field.find('MaxLength') or (field.find('ns:MaxLength', ns) if ns else None)
                max_length = maxlen_elem.text.strip() if maxlen_elem is not None and maxlen_elem.text else None

                # Determine block type
                block_type = 'map' if data_type == 'COMPOSITE' else 'string'

                # Get sub-field components if COMPOSITE
                sub_fields = {}
                if block_type == 'map':
                    components_elem = field.find('Components') or (field.find('ns:Components', ns) if ns else None)
                    if components_elem is not None:
                        comp_list = components_elem.findall('Component')
                        if not comp_list and ns:
                            comp_list = components_elem.findall('ns:Component', ns)
                        for comp in comp_list:
                            comp_name = comp.get('name', '')
                            comp_format = comp.get('format', '35x')
                            if comp_name:
                                sub_fields[comp_name] = {"format": comp_format}

                tag_defs[raw_tag] = {
                    "name": field_name,
                    "type": block_type,
                    "format": format_val,
                    "mandatory": mandatory,
                    "max_length": max_length,
                    "sub_fields": sub_fields if sub_fields else None
                }

            logger.info(f"✅ Loaded {len(tag_defs)} tag definitions for {mt_type} from {mapping_file}")
            self._tag_definitions_cache[mt_type] = tag_defs
            return tag_defs

        except Exception as e:
            logger.error(f"Failed to load tag definitions from {mapping_file}: {e}")
            return {}

    # ── Step 2: Check if file is SWIFT TXT ───────────────────────────────────

    def is_swift_txt(self, file_path: str) -> bool:
        """Check if file contains SWIFT MT text format."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read(500)
            has_tags = bool(re.search(r':\d{2}[A-Z]?:', content))
            has_header = '{1:' in content or '{4:' in content
            return has_tags or has_header
        except Exception:
            return False

    # ── Step 3: Main parse ────────────────────────────────────────────────────

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a SWIFT MT text file.
        Returns mt_type, iso_target, mt_blocks, columns, sample_data.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Extract body
            body = self._extract_body(content)

            # Parse raw tags from body
            raw_tags = self._parse_tags(body)
            logger.info(f"Raw tags found: {list(raw_tags.keys())}")

            # Detect MT type from raw tags
            mt_type = self._detect_mt_type(raw_tags)
            logger.info(f"Detected MT type: {mt_type}")

            # Load tag definitions from XML
            tag_defs = self._load_tag_definitions(mt_type)

            # Build mt_blocks using XML definitions
            mt_blocks = self._build_blocks(raw_tags, tag_defs, mt_type)

            # ISO target
            iso_target = MT_TO_ISO_TARGET.get(mt_type, "pacs.008.001.08")

            # Build columns and sample data
            columns = self._build_columns(mt_blocks)
            sample_data = [self._build_sample_row(mt_blocks)]

            logger.info(f"✅ SWIFT TXT Parser: {mt_type} → {iso_target}, {len(mt_blocks)} blocks, {len(columns)} columns")

            return {
                "mt_type": mt_type,
                "iso_target": iso_target,
                "mt_blocks": mt_blocks,
                "columns": columns,
                "sample_data": sample_data
            }

        except Exception as e:
            logger.error(f"SWIFT TXT Parser failed: {e}")
            raise ValueError(f"SWIFT text parsing error: {str(e)}")

    # ── Step 4: Extract body ──────────────────────────────────────────────────

    def _extract_body(self, content: str) -> str:
        """Extract message body — block 4 or full content."""
        match = re.search(r'\{4:(.*?)-\}', content, re.DOTALL)
        if match:
            return match.group(1)
        return content

    # ── Step 5: Parse raw tags ────────────────────────────────────────────────

    def _parse_tags(self, body: str) -> Dict[str, str]:
        """Extract all :TAG:VALUE pairs from body."""
        tags = {}
        pattern = r':(\d{2}[A-Z]?):(.*?)(?=:\d{2}[A-Z]?:|$)'
        matches = re.findall(pattern, body, re.DOTALL)
        for tag, value in matches:
            tags[tag] = value.strip()
        return tags

    # ── Step 6: Detect MT type ────────────────────────────────────────────────

    def _detect_mt_type(self, raw_tags: Dict[str, str]) -> str:
        """Detect MT type based on tags present."""
        present = set(raw_tags.keys())
        best = "MT103"
        best_score = 0
        for mt_type, signature in MT_TYPE_SIGNATURES.items():
            score = len(set(signature) & present)
            if score > best_score:
                best_score = score
                best = mt_type
        return best

    # ── Step 7: Build blocks ──────────────────────────────────────────────────

    def _build_blocks(self, raw_tags: Dict[str, str], tag_defs: Dict, mt_type: str) -> Dict[str, Any]:
        """
        Build mt_blocks from raw tags using XML tag definitions.
        If no definition found for a tag, use a generic definition.
        """
        mt_blocks = {}

        for tag, value in raw_tags.items():
            swift_tag = f":{tag}"

            # Get definition from XML
            tag_def = tag_defs.get(tag)

            if tag_def is None:
                # Generic fallback for unknown tags
                tag_def = {
                    "name": tag,
                    "type": "string",
                    "format": "35x",
                    "mandatory": False,
                    "sub_fields": None
                }

            block_type = tag_def.get("type", "string")

            if block_type == "string":
                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "name": tag_def["name"],
                    "type": "string",
                    "format": tag_def.get("format", "35x"),
                    "mandatory": tag_def.get("mandatory", False),
                    "value": value
                }

            elif block_type == "map":
                # Parse sub-fields from value
                xml_sub_fields = tag_def.get("sub_fields") or {}
                parsed_sub_fields = self._parse_sub_fields(tag, value, xml_sub_fields)

                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "name": tag_def["name"],
                    "type": "map",
                    "format": tag_def.get("format", "35x"),
                    "mandatory": tag_def.get("mandatory", False),
                    "sub_fields": parsed_sub_fields
                }

        return mt_blocks

    # ── Step 8: Parse sub-fields ──────────────────────────────────────────────

    def _parse_sub_fields(self, tag: str, value: str, xml_sub_fields: Dict) -> Dict[str, Any]:
        """
        Parse composite field value into sub-fields.
        Uses XML component definitions when available.
        """
        sub_fields = {}

        if tag == "32A":
            # YYMMDDCCCAMOUNT
            match = re.match(r'(\d{6})([A-Z]{3})([\d,]+)', value.strip())
            if match:
                sub_fields["Date"] = {"format": "6n", "value": match.group(1)}
                sub_fields["Currency"] = {"format": "3a", "value": match.group(2)}
                sub_fields["Amount"] = {"format": "15d", "value": match.group(3).replace(',', '.')}
            else:
                sub_fields["Value"] = {"format": "6n3a15d", "value": value}

        elif tag in ["60F", "60M", "62F", "62M", "64"]:
            # D/C + YYMMDD + CCY + AMOUNT
            match = re.match(r'([CD])(\d{6})([A-Z]{3})([\d,]+)', value.strip())
            if match:
                sub_fields["DebitCredit"] = {"format": "1a", "value": match.group(1)}
                sub_fields["Date"] = {"format": "6n", "value": match.group(2)}
                sub_fields["Currency"] = {"format": "3a", "value": match.group(3)}
                sub_fields["Amount"] = {"format": "15d", "value": match.group(4).replace(',', '.')}
            else:
                sub_fields["Value"] = {"format": "1a6n3a15d", "value": value}

        elif tag == "28C":
            # NNNNN/NN
            parts = value.strip().split('/')
            sub_fields["StatementNumber"] = {"format": "5n", "value": parts[0]}
            sub_fields["SequenceNumber"] = {"format": "2n", "value": parts[1] if len(parts) > 1 else "001"}

        elif tag == "61":
            # YYMMDD[MMDD]2a15d[NTRN]ref
            match = re.match(r'(\d{6})(\d{4})?([A-Z]{1,2})([\d,]+)([A-Z]{4})([\w]+)?', value.strip())
            if match:
                sub_fields["ValueDate"] = {"format": "6n", "value": match.group(1)}
                sub_fields["DebitCredit"] = {"format": "2a", "value": match.group(3)}
                sub_fields["Amount"] = {"format": "15d", "value": match.group(4).replace(',', '.')}
                if match.group(6):
                    sub_fields["Reference"] = {"format": "16x", "value": match.group(6)}
            else:
                sub_fields["Value"] = {"format": "6n6n2a15d", "value": value}

        elif tag in ["50K", "50A", "59", "59A"]:
            lines = value.strip().split('\n')
            if lines and lines[0].startswith('/'):
                sub_fields["Account"] = {"format": "34x", "value": lines[0].lstrip('/')}
                sub_fields["Name"] = {"format": "35x", "value": ' '.join(lines[1:]).strip()}
            else:
                sub_fields["Name"] = {"format": "35x", "value": lines[0].strip()}
                if len(lines) > 1:
                    sub_fields["Address"] = {"format": "35x", "value": ' '.join(lines[1:]).strip()}

        elif tag in ["52A", "56A", "57A", "58A"]:
            lines = value.strip().split('\n')
            if lines and lines[0].startswith('/'):
                sub_fields["Account"] = {"format": "34x", "value": lines[0].lstrip('/')}
                sub_fields["BIC"] = {"format": "11!a", "value": lines[1].strip() if len(lines) > 1 else ""}
            else:
                sub_fields["BIC"] = {"format": "11!a", "value": lines[0].strip()}

        else:
            # Use XML sub-field definitions if available
            if xml_sub_fields:
                for sub_name, sub_def in xml_sub_fields.items():
                    sub_fields[sub_name] = {"format": sub_def.get("format", "35x"), "value": value}
            else:
                sub_fields["Value"] = {"format": "35x", "value": value}

        return sub_fields

    # ── Step 9: Build columns and sample ─────────────────────────────────────

    def _build_columns(self, mt_blocks: Dict[str, Any]) -> List[str]:
        """Build flat column list from mt_blocks."""
        columns = []
        for tag, block in mt_blocks.items():
            if block["type"] == "string":
                columns.append(tag)
            elif block["type"] == "map":
                for sub_name in block.get("sub_fields", {}).keys():
                    columns.append(f"{tag}.{sub_name}")
        return columns

    def _build_sample_row(self, mt_blocks: Dict[str, Any]) -> Dict[str, Any]:
        """Build flat sample data row."""
        row = {}
        for tag, block in mt_blocks.items():
            if block["type"] == "string":
                row[tag] = block.get("value")
            elif block["type"] == "map":
                for sub_name, sub_field in block.get("sub_fields", {}).items():
                    row[f"{tag}.{sub_name}"] = sub_field.get("value")
        return row


# Singleton
swift_txt_parser = SWIFTTextParser()