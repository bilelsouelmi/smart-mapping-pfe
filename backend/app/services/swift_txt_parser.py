"""
SWIFT MT Text Parser
Parses SWIFT MT messages in standard text format (.txt)
Format: {1:...}{2:...}{4:\n:tag:value\n-}
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# MT Block definitions for text format
MT_TAG_DEFINITIONS = {
    "20":  {"name": "Transaction Reference",        "type": "string", "format": "16x"},
    "21":  {"name": "Related Reference",            "type": "string", "format": "16x"},
    "23B": {"name": "Bank Operation Code",          "type": "string", "format": "4!a"},
    "32A": {"name": "Value Date/Currency/Amount",   "type": "map",    "format": "6n3a15d"},
    "50K": {"name": "Ordering Customer",            "type": "map",    "format": "35x"},
    "50A": {"name": "Ordering Customer BIC",        "type": "map",    "format": "35x"},
    "52A": {"name": "Ordering Institution",         "type": "map",    "format": "11!a"},
    "56A": {"name": "Intermediary Institution",     "type": "map",    "format": "11!a"},
    "57A": {"name": "Account With Institution",     "type": "map",    "format": "11!a"},
    "58A": {"name": "Beneficiary Institution",      "type": "map",    "format": "11!a"},
    "59":  {"name": "Beneficiary",                  "type": "map",    "format": "35x"},
    "59A": {"name": "Beneficiary BIC",              "type": "map",    "format": "11!a"},
    "70":  {"name": "Remittance Information",       "type": "string", "format": "35x"},
    "71A": {"name": "Details of Charges",           "type": "string", "format": "3!a"},
    "72":  {"name": "Sender to Receiver Info",      "type": "string", "format": "35x"},
}

# MT type detection by tags present
MT_TYPE_SIGNATURES = {
    "MT103": ["20", "32A", "50K", "59", "71A"],
    "MT202": ["20", "21", "32A", "52A", "58A"],
    "MT940": ["20", "25", "28C", "60F", "62F"],
}

MT_TO_ISO_TARGET = {
    "MT103": "pacs.008.001.08",
    "MT202": "pacs.009.001.08",
    "MT940": "camt.053.001.08",
}


class SWIFTTextParser:
    """
    Parser for SWIFT MT messages in standard text format.
    Supports both raw SWIFT format and simplified text format.
    """

    def is_swift_txt(self, file_path: str) -> bool:
        """Check if file contains SWIFT MT text format."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            # Check for SWIFT tags pattern :XX: or {1: header
            has_tags = bool(re.search(r':\d{2}[A-Z]?:', content))
            has_header = '{1:' in content or '{4:' in content
            return has_tags or has_header
        except Exception:
            return False

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a SWIFT MT text file.
        Returns mt_type, iso_target, mt_blocks, columns, sample_data.
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            # Extract block 4 (message body) if present
            body = self._extract_body(content)

            # Parse tags from body
            raw_tags = self._parse_tags(body)

            # Build mt_blocks
            mt_blocks = self._build_blocks(raw_tags)

            # Detect MT type
            mt_type = self._detect_mt_type(mt_blocks)

            # ISO target
            iso_target = MT_TO_ISO_TARGET.get(mt_type, "pacs.008.001.08")

            # Build columns and sample data
            columns = self._build_columns(mt_blocks)
            sample_data = [self._build_sample_row(mt_blocks)]

            logger.info(f"✅ SWIFT TXT Parser: {mt_type} → {iso_target}, {len(mt_blocks)} blocks")

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

    def _extract_body(self, content: str) -> str:
        """Extract message body — block 4 or full content."""
        # Try to extract {4:\n...\n-}
        match = re.search(r'\{4:(.*?)-\}', content, re.DOTALL)
        if match:
            return match.group(1)
        # Fallback: use full content
        return content

    def _parse_tags(self, body: str) -> Dict[str, str]:
        """Extract all :TAG:VALUE pairs from body."""
        tags = {}
        # Pattern: :tag: followed by value until next :tag: or end
        pattern = r':(\d{2}[A-Z]?):(.*?)(?=:\d{2}[A-Z]?:|$)'
        matches = re.findall(pattern, body, re.DOTALL)
        for tag, value in matches:
            tags[tag] = value.strip()
        return tags

    def _build_blocks(self, raw_tags: Dict[str, str]) -> Dict[str, Any]:
        """Build mt_blocks structure from raw tags."""
        mt_blocks = {}

        for tag, value in raw_tags.items():
            tag_def = MT_TAG_DEFINITIONS.get(tag)
            if not tag_def:
                continue

            swift_tag = f":{tag}"

            if tag_def["type"] == "string":
                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "name": tag_def["name"],
                    "type": "string",
                    "format": tag_def["format"],
                    "value": value
                }

            elif tag_def["type"] == "map":
                sub_fields = self._parse_sub_fields(tag, value)
                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "name": tag_def["name"],
                    "type": "map",
                    "format": tag_def["format"],
                    "sub_fields": sub_fields
                }

        return mt_blocks

    def _parse_sub_fields(self, tag: str, value: str) -> Dict[str, Any]:
        """Parse sub-fields based on tag type."""
        sub_fields = {}

        if tag == "32A":
            # Format: YYMMDDCCCAMOUNT
            match = re.match(r'(\d{6})([A-Z]{3})([\d,]+)', value)
            if match:
                sub_fields["Date"] = {"format": "6n", "value": match.group(1)}
                sub_fields["Currency"] = {"format": "3a", "value": match.group(2)}
                sub_fields["Amount"] = {"format": "15d", "value": match.group(3).replace(',', '.')}
            else:
                sub_fields["Value"] = {"format": "6n3a15d", "value": value}

        elif tag in ["50K", "50A", "59", "59A"]:
            lines = value.strip().split('\n')
            # First line may be account
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
                if len(lines) > 1:
                    sub_fields["Name"] = {"format": "35x", "value": lines[1].strip()}

        else:
            sub_fields["Value"] = {"format": "35x", "value": value}

        return sub_fields

    def _detect_mt_type(self, mt_blocks: Dict[str, Any]) -> str:
        """Detect MT type from blocks present."""
        present = set(tag.lstrip(':') for tag in mt_blocks.keys())
        best = "MT103"
        best_score = 0
        for mt_type, signature in MT_TYPE_SIGNATURES.items():
            score = len(set(signature) & present)
            if score > best_score:
                best_score = score
                best = mt_type
        return best

    def _build_columns(self, mt_blocks: Dict[str, Any]) -> List[str]:
        """Build flat column list."""
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