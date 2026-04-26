"""
MT Parser Service
Parses XML files containing SWIFT MT message blocks
Supports MT103, MT202, MT940 and other MT formats
"""

import xml.etree.ElementTree as ET
import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


# ── MT Block Definitions ──────────────────────────────────────────────────────
# Maps XML tag names → SWIFT MT block info
MT_BLOCK_DEFINITIONS = {
    # MT103 blocks
    "TransactionReference":     {"tag": ":20",  "format": "16x",      "type": "string", "name": "Transaction Reference"},
    "BankOperationCode":        {"tag": ":23B",  "format": "4!a",      "type": "string", "name": "Bank Operation Code"},
    "ValueDate":                {"tag": ":32A",  "format": "6n3a15d",  "type": "map",    "name": "Value Date/Currency/Amount",
                                 "sub_fields": {
                                     "Date":     {"format": "6n",  "iso_format": "YYYYMMDD"},
                                     "Currency": {"format": "3a",  "iso_format": "3!a"},
                                     "Amount":   {"format": "15d", "iso_format": "15d"}
                                 }},
    "Amount":                   {"tag": ":32A",  "format": "6n3a15d",  "type": "map",    "name": "Value Date/Currency/Amount",
                                 "sub_fields": {
                                     "Date":     {"format": "6n"},
                                     "Currency": {"format": "3a"},
                                     "Value":    {"format": "15d"}
                                 }},
    "OrderingCustomer":         {"tag": ":50K",  "format": "35x",      "type": "map",    "name": "Ordering Customer",
                                 "sub_fields": {
                                     "Name":     {"format": "35x"},
                                     "Account":  {"format": "34x"}
                                 }},
    "OrderingInstitution":      {"tag": ":52A",  "format": "35x",      "type": "map",    "name": "Ordering Institution",
                                 "sub_fields": {
                                     "BIC":      {"format": "11!a"},
                                     "Name":     {"format": "35x"}
                                 }},
    "IntermediaryInstitution":  {"tag": ":56A",  "format": "35x",      "type": "map",    "name": "Intermediary Institution",
                                 "sub_fields": {
                                     "BIC":      {"format": "11!a"},
                                     "Name":     {"format": "35x"}
                                 }},
    "AccountWithInstitution":   {"tag": ":57A",  "format": "35x",      "type": "map",    "name": "Account With Institution",
                                 "sub_fields": {
                                     "BIC":      {"format": "11!a"},
                                     "Name":     {"format": "35x"}
                                 }},
    "Beneficiary":              {"tag": ":59",   "format": "35x",      "type": "map",    "name": "Beneficiary",
                                 "sub_fields": {
                                     "Name":     {"format": "35x"},
                                     "Account":  {"format": "34x"}
                                 }},
    "BeneficiaryCustomer":      {"tag": ":59",   "format": "35x",      "type": "map",    "name": "Beneficiary Customer",
                                 "sub_fields": {
                                     "Name":     {"format": "35x"},
                                     "Account":  {"format": "34x"}
                                 }},
    "RemittanceInformation":    {"tag": ":70",   "format": "35x",      "type": "string", "name": "Remittance Information"},
    "AdditionalInfo":           {"tag": ":70",   "format": "35x",      "type": "string", "name": "Remittance Information"},
    "Charges":                  {"tag": ":71A",  "format": "3!a",      "type": "string", "name": "Details of Charges"},
    "ChargeBearer":             {"tag": ":71A",  "format": "3!a",      "type": "string", "name": "Details of Charges"},
    "SenderToReceiverInfo":     {"tag": ":72",   "format": "35x",      "type": "string", "name": "Sender to Receiver Information"},

    # MT202 specific
    "TransactionID":            {"tag": ":20",   "format": "16x",      "type": "string", "name": "Transaction Reference"},
    "RelatedReference":         {"tag": ":21",   "format": "16x",      "type": "string", "name": "Related Reference"},

    # Banks
    "Banks":                    {"tag": ":52A",  "format": "11!a",     "type": "map",    "name": "Banks",
                                 "sub_fields": {
                                     "SenderBank":   {"format": "11!a"},
                                     "ReceiverBank": {"format": "11!a"}
                                 }},
}

# MT type detection based on blocks present
MT_TYPE_SIGNATURES = {
    "MT103": [":20", ":32A", ":50K", ":59", ":71A"],
    "MT202": [":20", ":21", ":32A", ":52A", ":58A"],
    "MT940": [":20", ":25", ":28C", ":60F", ":62F"],
    "MT900": [":20", ":21", ":25", ":32A"],
    "MT910": [":20", ":21", ":25", ":32A"],
}

# ISO 20022 target by MT type
MT_TO_ISO_TARGET = {
    "MT103": "pacs.008.001.08",
    "MT202": "pacs.009.001.08",
    "MT940": "camt.053.001.08",
    "MT900": "camt.054.001.08",
    "MT910": "camt.054.001.08",
}


class MTParser:
    """
    Parser for XML files containing SWIFT MT message blocks.
    Detects MT type and extracts blocks with their sub-fields.
    """

    def is_mt_xml(self, file_path: str) -> bool:
        """
        Check if an XML file contains SWIFT MT blocks.
        Returns True if at least 2 known MT tags are detected.
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            known_tags = set(MT_BLOCK_DEFINITIONS.keys())
            found = 0
            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag in known_tags:
                    found += 1
                if found >= 2:
                    return True
            return False
        except Exception:
            return False

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse an XML MT file and extract all blocks.

        Returns:
            {
                "mt_type": "MT103",
                "iso_target": "pacs.008.001.08",
                "mt_blocks": {
                    ":20": {"tag": ":20", "name": "...", "type": "string", "format": "16x", "value": "REF123"},
                    ":32A": {"tag": ":32A", "name": "...", "type": "map", "sub_fields": {
                        "Currency": {"format": "3a", "value": "EUR"},
                        "Amount": {"format": "15d", "value": "1000"}
                    }},
                    ...
                },
                "columns": [":20", ":32A.Currency", ":32A.Amount", ...],
                "sample_data": [{...}]
            }
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Extract blocks
            mt_blocks = self._extract_blocks(root)

            # Detect MT type
            mt_type = self._detect_mt_type(mt_blocks)

            # Get ISO target
            iso_target = MT_TO_ISO_TARGET.get(mt_type, "pacs.008.001.08")

            # Build flat columns list for AI suggestion
            columns = self._build_columns(mt_blocks)

            # Build sample data
            sample_data = self._build_sample_data(mt_blocks)

            logger.info(f"✅ MT Parser: detected {mt_type}, {len(mt_blocks)} blocks, {len(columns)} fields")

            return {
                "mt_type": mt_type,
                "iso_target": iso_target,
                "mt_blocks": mt_blocks,
                "columns": columns,
                "sample_data": [sample_data]
            }

        except Exception as e:
            logger.error(f"MT Parser failed: {e}")
            raise ValueError(f"MT XML parsing error: {str(e)}")

    def _extract_blocks(self, root: ET.Element) -> Dict[str, Any]:
        """Extract all MT blocks from XML root."""
        mt_blocks = {}

        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag

            if tag not in MT_BLOCK_DEFINITIONS:
                continue

            block_def = MT_BLOCK_DEFINITIONS[tag]
            swift_tag = block_def["tag"]

            # Skip if already processed this SWIFT tag
            if swift_tag in mt_blocks:
                continue

            if block_def["type"] == "string":
                # Simple string block
                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "xml_tag": tag,
                    "name": block_def["name"],
                    "type": "string",
                    "format": block_def["format"],
                    "value": elem.text.strip() if elem.text else None
                }

            elif block_def["type"] == "map":
                # Map block with sub-fields
                sub_fields = {}
                sub_field_defs = block_def.get("sub_fields", {})

                for sub_name, sub_def in sub_field_defs.items():
                    # Search for sub-field element
                    sub_elem = elem.find(sub_name)
                    if sub_elem is None:
                        # Try case-insensitive
                        for child in elem:
                            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                            if child_tag.lower() == sub_name.lower():
                                sub_elem = child
                                break

                    sub_fields[sub_name] = {
                        "format": sub_def.get("format", "35x"),
                        "value": sub_elem.text.strip() if sub_elem is not None and sub_elem.text else None
                    }

                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "xml_tag": tag,
                    "name": block_def["name"],
                    "type": "map",
                    "format": block_def["format"],
                    "sub_fields": sub_fields
                }

        return mt_blocks

    def _detect_mt_type(self, mt_blocks: Dict[str, Any]) -> str:
        """Detect MT type based on blocks present."""
        present_tags = set(mt_blocks.keys())

        best_match = "MT103"
        best_score = 0

        for mt_type, signature in MT_TYPE_SIGNATURES.items():
            score = len(set(signature) & present_tags)
            if score > best_score:
                best_score = score
                best_match = mt_type

        return best_match

    def _build_columns(self, mt_blocks: Dict[str, Any]) -> List[str]:
        """Build flat list of columns from MT blocks for AI suggestion."""
        columns = []

        for swift_tag, block in mt_blocks.items():
            if block["type"] == "string":
                # Simple column: ":20"
                columns.append(swift_tag)
            elif block["type"] == "map":
                # Sub-field columns: ":32A.Currency", ":32A.Amount"
                for sub_name in block.get("sub_fields", {}).keys():
                    columns.append(f"{swift_tag}.{sub_name}")

        return columns

    def _build_sample_data(self, mt_blocks: Dict[str, Any]) -> Dict[str, Any]:
        """Build a flat sample data row from MT blocks."""
        row = {}

        for swift_tag, block in mt_blocks.items():
            if block["type"] == "string":
                row[swift_tag] = block.get("value")
            elif block["type"] == "map":
                for sub_name, sub_field in block.get("sub_fields", {}).items():
                    row[f"{swift_tag}.{sub_name}"] = sub_field.get("value")

        return row


# Singleton instance
mt_parser = MTParser()