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
    "MT950": "camt.053.001.08",
    "MT900": "camt.054.001.08",
    "MT910": "camt.054.001.08",
}

# MT type signatures — minimum tags to identify each MT type
MT_TYPE_SIGNATURES = {
    "MT103": ["20", "32A", "50K", "59", "71A"],
    "MT202": ["20", "21", "32A", "52A", "58A"],
    "MT940": ["20", "25", "28C", "60F", "62F", "61"],
    "MT950": ["20", "25", "28C", "60F", "62F"],
    "MT900": ["20", "21", "25", "32A"],
    "MT910": ["20", "21", "25", "32A", "50K"],
}

# Mapping files for each MT type
MT_MAPPING_FILES = {
    "MT103": "MT103_to_pacs008.xml",
    "MT202": "MT202_to_pacs009.xml",
    "MT940": "MT940_to_camt053.xml",
    "MT950": "MT950_to_camt053.xml",
    "MT900": "MT900_to_camt054.xml",
    "MT910": "MT910_to_camt054.xml",
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
                # NB: "elem_a or elem_b" is wrong for ElementTree elements —
                # Element.__bool__() reflects child COUNT, not text content,
                # so a real leaf element like <FieldName>Foo</FieldName> (no
                # child elements) is falsy and always fell through to the
                # `or` branch. Since every mapping file in this project has
                # no XML namespace, that branch is always None too — so
                # DataType/FieldName/Format/Mandatory/MaxLength were silently
                # discarded for every field, of every MT type, on every .txt
                # upload (block_type was never 'map', so :32A:/:60F:/:33B:
                # etc. never decomposed into Date/Currency/Amount sub_fields).
                name_elem = field.find('FieldName')
                if name_elem is None and ns:
                    name_elem = field.find('ns:FieldName', ns)
                field_name = name_elem.text.strip() if name_elem is not None and name_elem.text else raw_tag

                # Get DataType
                type_elem = field.find('DataType')
                if type_elem is None and ns:
                    type_elem = field.find('ns:DataType', ns)
                data_type = type_elem.text.strip().upper() if type_elem is not None and type_elem.text else 'STRING'

                # Get Format
                format_elem = field.find('Format')
                if format_elem is None and ns:
                    format_elem = field.find('ns:Format', ns)
                format_val = format_elem.text.strip() if format_elem is not None and format_elem.text else '35x'

                # Get Mandatory
                mandatory_elem = field.find('Mandatory')
                if mandatory_elem is None and ns:
                    mandatory_elem = field.find('ns:Mandatory', ns)
                mandatory = mandatory_elem.text.strip().lower() == 'true' if mandatory_elem is not None and mandatory_elem.text else False

                # Get MaxLength
                maxlen_elem = field.find('MaxLength')
                if maxlen_elem is None and ns:
                    maxlen_elem = field.find('ns:MaxLength', ns)
                max_length = maxlen_elem.text.strip() if maxlen_elem is not None and maxlen_elem.text else None

                # Determine block type
                block_type = 'map' if data_type == 'COMPOSITE' else 'string'

                # Get sub-field components if COMPOSITE
                sub_fields = {}
                if block_type == 'map':
                    components_elem = field.find('Components')
                    if components_elem is None and ns:
                        components_elem = field.find('ns:Components', ns)
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
            # An XML file is never SWIFT MT text, no matter what its content
            # matches below — check this first. Without it, any ISO 20022
            # XML this project generates gets misdetected as SWIFT: every
            # such file has a <CreDtTm> ISO timestamp like "16:19:37", and
            # its "19:" substring matches the tag regex below (":19:" looks
            # exactly like a 2-digit SWIFT field tag).
            if content.lstrip().startswith('<'):
                return False
            # Real SWIFT tags always start a line (e.g. ":20:REF123..."),
            # so anchor to line-start — this is also what rules out
            # embedded HH:MM:SS timestamps from matching in non-XML text.
            has_tags = bool(re.search(r'(?m)^:\d{2}[A-Z]?:', content))
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

            # Parse SWIFT envelope blocks {1:} {2:} {4:}
            swift_blocks = self._parse_swift_blocks(content)

            # Extract body from block4 or raw content
            body = swift_blocks.get("block4") or self._extract_body(content)

            # Parse raw tags from body
            raw_tags = self._parse_tags(body)
            logger.info(f"Raw tags found: {list(raw_tags.keys())}")

            # Detect MT type from raw tags
            mt_type = self._detect_mt_type(raw_tags, swift_blocks.get("block2", ""))
            logger.info(f"Detected MT type: {mt_type}")

            # Load tag definitions from XML
            tag_defs = self._load_tag_definitions(mt_type)

            # Build mt_blocks using XML definitions
            mt_blocks = self._build_blocks(raw_tags, tag_defs, mt_type)

            # ── NOUVEAU : Add block1, block2, block3, block4, block5 to mt_blocks ─
            if "block1" in swift_blocks:
                b1_sub = self._parse_block1(swift_blocks["block1"])
                mt_blocks["block1"] = {
                    "tag": "block1",
                    "name": "block1",
                    "type": "map",
                    "format": "25!x",
                    "mandatory": True,
                    "value": swift_blocks["block1"],
                    "sub_fields": b1_sub,
                    "sub_fields_order": list(b1_sub.keys())
                }

            if "block2" in swift_blocks:
                b2_val = swift_blocks["block2"]
                if b2_val.startswith("I"):
                    b2_sub = self._parse_block2_input(b2_val)
                else:
                    b2_sub = self._parse_block2_output(b2_val)
                mt_blocks["block2"] = {
                    "tag": "block2",
                    "name": "block2",
                    "type": "map",
                    "format": "35x",
                    "mandatory": True,
                    "value": b2_val,
                    "sub_fields": b2_sub,
                    "sub_fields_order": list(b2_sub.keys())
                }

            # Add block3 (user header) if present
            if "block3" in swift_blocks:
                b3_val = swift_blocks["block3"]
                # Parse block3 tags like {108:...}{113:...}
                b3_tags = re.findall(r'\{(\w+):([^}]*)\}', b3_val)
                b3_sub = {}
                for tag_name, tag_val in b3_tags:
                    b3_sub[tag_name] = {"format": "35x", "value": tag_val, "description": f"Block 3 field {tag_name}"}
                mt_blocks["block3"] = {
                    "tag": "block3",
                    "name": "block3",
                    "type": "map",
                    "format": "35x",
                    "mandatory": False,
                    "value": b3_val,
                    "sub_fields": b3_sub if b3_sub else {"Value": {"format": "35x", "value": b3_val}}
                }

            # Add block5 (trailer) if present
            if "block5" in swift_blocks:
                b5_val = swift_blocks["block5"]
                b5_tags = re.findall(r'\{(\w+):([^}]*)\}', b5_val)
                b5_sub = {}
                for tag_name, tag_val in b5_tags:
                    b5_sub[tag_name] = {"format": "35x", "value": tag_val, "description": f"Block 5 field {tag_name}"}
                mt_blocks["block5"] = {
                    "tag": "block5",
                    "name": "block5",
                    "type": "map",
                    "format": "35x",
                    "mandatory": False,
                    "value": b5_val,
                    "sub_fields": b5_sub if b5_sub else {"Value": {"format": "35x", "value": b5_val}}
                }

            # Rename body blocks to block4
            body_blocks = {}
            for tag, block in mt_blocks.items():
                if not tag.startswith("block"):
                    body_blocks[tag] = block
            if body_blocks:
                mt_blocks["block4"] = {
                    "tag": "block4",
                    "name": "block4",
                    "type": "map",
                    "format": "35x",
                    "mandatory": True,
                    "value": "",
                    "sub_fields": body_blocks,
                    "sub_fields_order": list(body_blocks.keys())
                }
                # Remove body blocks from top level
                for tag in list(body_blocks.keys()):
                    del mt_blocks[tag]
            # ── FIN NOUVEAU ───────────────────────────────────────────────

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
        """Extract all :TAG:VALUE pairs from body. Handles duplicate tags with index suffix."""
        tags = {}
        tag_counts = {}
        pattern = r':(\d{2}[A-Z]?):(.*?)(?=:\d{2}[A-Z]?:|$)'
        matches = re.findall(pattern, body, re.DOTALL)
        for tag, value in matches:
            if tag not in tag_counts:
                tag_counts[tag] = 0
                tags[tag] = value.strip()
            else:
                tag_counts[tag] += 1
                tags[f"{tag}_{tag_counts[tag]}"] = value.strip()
        return tags

    # ── Step 6: Detect MT type ────────────────────────────────────────────────

    def _detect_mt_type(self, raw_tags: Dict[str, str], block2: str = "") -> str:
        """Detect MT type — first try block2 MessageType, then tag signatures."""
        # Primary: extract MessageType from block2 (most reliable)
        if block2:
            # block2 format: I103BNPAFRPPXXXXN or O103...
            m = re.match(r'^[IO](\d{3})', block2.strip())
            if m:
                mt_num = m.group(1)
                return f"MT{mt_num}"

        # Fallback: tag signature matching
        present = set(raw_tags.keys())
        best = "MT103"
        best_score = 0
        for mt_type, signature in MT_TYPE_SIGNATURES.items():
            score = len(set(signature) & present)
            if score > best_score:
                best_score = score
                best = mt_type

        # Disambiguate MT940 vs MT950: MT940 requires :61: transaction lines
        if best == "MT940" and "61" not in present:
            best = "MT950"

        return best

    # ── Step 7: Build blocks ──────────────────────────────────────────────────

    def _build_blocks(self, raw_tags: Dict[str, str], tag_defs: Dict, mt_type: str) -> Dict[str, Any]:
        """
        Build mt_blocks from raw tags using XML tag definitions.
        Always stores sub_fields_order to preserve insertion order against PostgreSQL JSONB sorting.
        """
        mt_blocks = {}

        for tag, value in raw_tags.items():
            # Clean tag: remove index suffix for definition lookup: 61_1 → 61
            import re as _re
            clean_tag = _re.sub(r'_\d+$', '', tag)
            swift_tag = f":{tag}"

            # Get definition from XML using clean tag
            tag_def = tag_defs.get(clean_tag)

            if tag_def is None:
                tag_def = {
                    "name": clean_tag,
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
                xml_sub_fields = tag_def.get("sub_fields") or {}
                parsed_sub_fields = self._parse_sub_fields(clean_tag, value, xml_sub_fields)

                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "name": tag_def["name"],
                    "type": "map",
                    "format": tag_def.get("format", "35x"),
                    "mandatory": tag_def.get("mandatory", False),
                    "sub_fields": parsed_sub_fields,
                    "sub_fields_order": list(parsed_sub_fields.keys())
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


    # ── NOUVEAU : Parse SWIFT envelope blocks {1:} {2:} {4:} ─────────────────

    def _parse_swift_blocks(self, content: str) -> Dict[str, str]:
        """Extract all SWIFT blocks {N:...} including nested braces."""
        blocks = {}

        # Block 4 ends with -} — extract first (special case)
        b4 = re.search(r'\{4:(.*?)-\}', content, re.DOTALL)
        if b4:
            blocks["block4"] = b4.group(1).strip()
            # Remove block4 to avoid confusion
            content_no_b4 = content[:b4.start()] + content[b4.end():]
        else:
            content_no_b4 = content

        # Parse other blocks using balanced brace matching
        i = 0
        while i < len(content_no_b4):
            if (content_no_b4[i] == '{' and
                i + 2 < len(content_no_b4) and
                content_no_b4[i+1].isdigit() and
                content_no_b4[i+2] == ':'):
                block_num = content_no_b4[i+1]
                depth = 1
                j = i + 3
                while j < len(content_no_b4) and depth > 0:
                    if content_no_b4[j] == '{':
                        depth += 1
                    elif content_no_b4[j] == '}':
                        depth -= 1
                    j += 1
                block_content = content_no_b4[i+3:j-1].strip()
                if block_content:
                    blocks[f"block{block_num}"] = block_content
                i = j
            else:
                i += 1

        return blocks

    def _parse_block1(self, value: str) -> Dict[str, Any]:
        """Parse block 1: F01BIATTNTT0000000000 (flexible length)"""
        sub = {}
        v = value.strip()
        # Format: AppId(1) + ServiceId(2) + LT(8-12) + Session(4) + Seq(2-6)
        # Try strict first, then flexible
        m = re.match(r'^([A-Z])(\d{2})([A-Z0-9]{8,12})(\d{2,4})(\d{2,6})$', v)
        if m:
            sub["ApplicationIdentifier"] = {"format": "1!a", "value": m.group(1), "description": "F=FIN Application"}
            sub["ServiceIdentifier"]     = {"format": "2!n", "value": m.group(2), "description": "Service Identifier"}
            sub["LogicalTerminalAddress"]= {"format": "12!c","value": m.group(3), "description": "BIC Logical Terminal"}
            sub["SessionNumber"]         = {"format": "4!n", "value": m.group(4), "description": "Session Number"}
            sub["SequenceNumber"]        = {"format": "6!n", "value": m.group(5), "description": "Sequence Number"}
        else:
            # Manual split: 1 + 2 + rest split as LT(12) + Session(4) + Seq(rest)
            try:
                from collections import OrderedDict
                sub = OrderedDict()
                app_id = v[0]
                svc_id = v[1:3]
                remaining = v[3:]
                if len(remaining) >= 6:
                    lt_addr = remaining[:12] if len(remaining) >= 12 else remaining[:8]
                    rest = remaining[len(lt_addr):]
                    session = rest[:4] if len(rest) >= 4 else rest
                    seq = rest[4:] if len(rest) > 4 else "000000"
                    sub["ApplicationIdentifier"] = {"format": "1!a", "value": app_id, "description": "F=FIN Application"}
                    sub["ServiceIdentifier"]     = {"format": "2!n", "value": svc_id, "description": "Service Identifier"}
                    sub["LogicalTerminalAddress"]= {"format": "12!c","value": lt_addr, "description": "BIC Logical Terminal"}
                    sub["SessionNumber"]         = {"format": "4!n", "value": session, "description": "Session Number"}
                    sub["SequenceNumber"]        = {"format": "6!n", "value": seq or "000000", "description": "Sequence Number"}
                else:
                    sub["Value"] = {"format": "25!x", "value": v}
            except Exception:
                sub["Value"] = {"format": "25!x", "value": v}
        return sub

    def _parse_block2_input(self, value: str) -> Dict[str, Any]:
        """Parse block 2 input: I202BNPAFRPPXXXXN"""
        sub = {}
        m = re.match(r'^I(\d{3})([A-Z0-9]{12})([A-Z]?)$', value.strip())
        if m:
            sub["InputOutputIdentifier"] = {"format": "1!a", "value": "I",       "description": "I=Input message"}
            sub["MessageType"]           = {"format": "3!n", "value": m.group(1), "description": "SWIFT Message Type"}
            sub["DestinationAddress"]    = {"format": "12!c","value": m.group(2), "description": "Destination BIC"}
            if m.group(3):
                sub["Priority"] = {"format": "1!a", "value": m.group(3), "description": "N=Normal U=Urgent"}
        else:
            sub["Value"] = {"format": "35x", "value": value}
        return sub

    def _parse_block2_output(self, value: str) -> Dict[str, Any]:
        """Parse block 2 output: O202HHMM YYMMDD BIC SESSION SEQ YYMMDD HHMM P"""
        sub = {}
        m = re.match(r'^O(\d{3})(\d{4})(\d{6})([A-Z0-9]{12})(\d{4})(\d{6})(\d{6})(\d{4})([A-Z]?)$', value.strip())
        if m:
            sub["InputOutputIdentifier"] = {"format": "1!a", "value": "O",        "description": "O=Output message"}
            sub["MessageType"]           = {"format": "3!n", "value": m.group(1), "description": "SWIFT Message Type"}
            sub["InputTime"]             = {"format": "4!n", "value": m.group(2), "description": "Input Time HHMM"}
            sub["InputDate"]             = {"format": "6!n", "value": m.group(3), "description": "Input Date YYMMDD"}
            sub["LogicalTerminalAddress"]= {"format": "12!c","value": m.group(4), "description": "Input LT Address"}
            sub["SessionNumber"]         = {"format": "4!n", "value": m.group(5), "description": "Session Number"}
            sub["SequenceNumber"]        = {"format": "6!n", "value": m.group(6), "description": "Sequence Number"}
            sub["OutputDate"]            = {"format": "6!n", "value": m.group(7), "description": "Output Date YYMMDD"}
            sub["OutputTime"]            = {"format": "4!n", "value": m.group(8), "description": "Output Time HHMM"}
        else:
            sub["Value"] = {"format": "35x", "value": value}
        return sub

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