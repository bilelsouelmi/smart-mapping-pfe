"""
MT Parser Service
Parses XML files containing SWIFT MT message blocks
Supports MT103, MT202, MT940, MT950 and other MT formats
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
    # ── Common / MT103 ────────────────────────────────────────────────────────
    "TransactionReference":     {"tag": ":20",  "format": "16x",      "type": "string", "name": "Transaction Reference"},
    "BankOperationCode":        {"tag": ":23B",  "format": "4!a",      "type": "string", "name": "Bank Operation Code"},
    "ValueDate":                {"tag": ":32A",  "format": "6n3a15d",  "type": "map",    "name": "Value Date/Currency/Amount",
                                 "sub_fields": {
                                     "Date":     {"format": "6n",  "iso_format": "YYYYMMDD"},
                                     "Currency": {"format": "3a",  "iso_format": "3!a"},
                                     "Amount":   {"format": "15d", "iso_format": "15d"}
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
    "Beneficiary":              {"tag": ":59",   "format": "35x",      "type": "map",    "name": "Beneficiary Customer",
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
    "AdditionalInfo":           {"tag": ":86",   "format": "35x",      "type": "string", "name": "Information to Account Owner"},
    "Charges":                  {"tag": ":71A",  "format": "3!a",      "type": "string", "name": "Details of Charges"},
    "ChargeBearer":             {"tag": ":71A",  "format": "3!a",      "type": "string", "name": "Details of Charges"},
    "SenderToReceiverInfo":     {"tag": ":72",   "format": "35x",      "type": "string", "name": "Sender to Receiver Information"},

    # ── MT202 specific ────────────────────────────────────────────────────────
    "TransactionID":            {"tag": ":20",   "format": "16x",      "type": "string", "name": "Transaction Reference"},
    "RelatedReference":         {"tag": ":21",   "format": "16x",      "type": "string", "name": "Related Reference"},
    "Banks":                    {"tag": ":52A",  "format": "11!a",     "type": "map",    "name": "Banks",
                                 "sub_fields": {
                                     "SenderBank":   {"format": "11!a"},
                                     "ReceiverBank": {"format": "11!a"}
                                 }},

    # ── MT940 / MT950 specific ────────────────────────────────────────────────
    "AccountIdentification":    {"tag": ":25",   "format": "35x",      "type": "string", "name": "Account Identification"},
    "StatementNumber":          {"tag": ":28C",  "format": "5n/2n",    "type": "map",    "name": "Statement Number",
                                 "sub_fields": {
                                     "Number":   {"format": "5n"},
                                     "Sequence": {"format": "2n"}
                                 }},
    "OpeningBalance":           {"tag": ":60F",  "format": "1a6n3a15d","type": "map",    "name": "Opening Balance",
                                 "sub_fields": {
                                     "DebitCredit": {"format": "1a"},
                                     "Date":        {"format": "6n"},
                                     "Currency":    {"format": "3a"},
                                     "Amount":      {"format": "15d"}
                                 }},
    "IntermediateOpeningBalance": {"tag": ":60M","format": "1a6n3a15d","type": "map",    "name": "Intermediate Opening Balance",
                                 "sub_fields": {
                                     "DebitCredit": {"format": "1a"},
                                     "Date":        {"format": "6n"},
                                     "Currency":    {"format": "3a"},
                                     "Amount":      {"format": "15d"}
                                 }},
    "StatementLine":            {"tag": ":61",   "format": "6n6n2a15d","type": "map",    "name": "Statement Line",
                                 "sub_fields": {
                                     "ValueDate":   {"format": "6n"},
                                     "DebitCredit": {"format": "2a"},
                                     "Amount":      {"format": "15d"},
                                     "Reference":   {"format": "16x"}
                                 }},
    "ClosingBalance":           {"tag": ":62F",  "format": "1a6n3a15d","type": "map",    "name": "Closing Balance",
                                 "sub_fields": {
                                     "DebitCredit": {"format": "1a"},
                                     "Date":        {"format": "6n"},
                                     "Currency":    {"format": "3a"},
                                     "Amount":      {"format": "15d"}
                                 }},
    "IntermediateClosingBalance": {"tag": ":62M","format": "1a6n3a15d","type": "map",    "name": "Intermediate Closing Balance",
                                 "sub_fields": {
                                     "DebitCredit": {"format": "1a"},
                                     "Date":        {"format": "6n"},
                                     "Currency":    {"format": "3a"},
                                     "Amount":      {"format": "15d"}
                                 }},
    "ClosingAvailableBalance":  {"tag": ":64",   "format": "1a6n3a15d","type": "map",    "name": "Closing Available Balance",
                                 "sub_fields": {
                                     "DebitCredit": {"format": "1a"},
                                     "Date":        {"format": "6n"},
                                     "Currency":    {"format": "3a"},
                                     "Amount":      {"format": "15d"}
                                 }},
    "InformationToAccountOwner": {"tag": ":86",  "format": "35x",      "type": "string", "name": "Information to Account Owner"},
}

# MT type detection — tags that uniquely identify each MT type
MT_TYPE_SIGNATURES = {
    "MT103": [":20", ":32A", ":50K", ":59", ":71A"],
    "MT202": [":20", ":21", ":32A", ":52A", ":58A"],
    "MT940": [":20", ":25", ":28C", ":60F", ":62F"],
    "MT950": [":20", ":25", ":28C", ":60F", ":62F"],
    "MT900": [":20", ":21", ":25", ":32A"],
    "MT910": [":20", ":21", ":25", ":32A", ":50K"],
}

# Unique tags per MT type — used to disambiguate MT940 vs MT950
MT_UNIQUE_TAGS = {
    "MT950": [":25"],   # MT950 always has AccountIdentification
    "MT940": [":61"],   # MT940 always has StatementLine transactions
}

# ISO 20022 target by MT type
MT_TO_ISO_TARGET = {
    "MT103": "pacs.008.001.08",
    "MT202": "pacs.009.001.08",
    "MT940": "camt.053.001.08",
    "MT950": "camt.053.001.08",
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
        """Parse an XML MT file and extract all blocks."""
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Extract blocks
            mt_blocks = self._extract_blocks(root)

            # Detect MT type — pass root for block2/MessageType lookup
            mt_type = self._detect_mt_type(mt_blocks, root)

            # Get ISO target
            iso_target = MT_TO_ISO_TARGET.get(mt_type, "pacs.008.001.08")

            # Build flat columns list
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

            # Handle duplicate tags (e.g. multiple StatementLine → :61, :61_1, :61_2)
            if swift_tag in mt_blocks:
                count = sum(1 for k in mt_blocks if k == swift_tag or k.startswith(f"{swift_tag}_"))
                swift_tag = f"{swift_tag}_{count}"

            if block_def["type"] == "string":
                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "xml_tag": tag,
                    "name": block_def["name"],
                    "type": "string",
                    "format": block_def["format"],
                    "value": elem.text.strip() if elem.text else None
                }

            elif block_def["type"] == "map":
                sub_fields = {}
                sub_field_defs = block_def.get("sub_fields", {})

                for sub_name, sub_def in sub_field_defs.items():
                    sub_elem = elem.find(sub_name)
                    if sub_elem is None:
                        for child in elem:
                            child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                            if child_tag.lower() == sub_name.lower():
                                sub_elem = child
                                break

                    sub_fields[sub_name] = {
                        "format": sub_def.get("format", "35x"),
                        "value": sub_elem.text.strip() if sub_elem is not None and sub_elem.text else None
                    }

                # If element has flat text value but all sub_fields are null
                # (e.g. <OrderingInstitution>BNPAFRPPXXX</OrderingInstitution>)
                # store the text in the first sub_field (BIC) as fallback
                flat_text = elem.text.strip() if elem.text and elem.text.strip() else None
                all_null = all(v.get("value") is None for v in sub_fields.values())
                if flat_text and all_null and sub_fields:
                    first_key = list(sub_fields.keys())[0]
                    sub_fields[first_key]["value"] = flat_text

                mt_blocks[swift_tag] = {
                    "tag": swift_tag,
                    "xml_tag": tag,
                    "name": block_def["name"],
                    "type": "map",
                    "format": block_def["format"],
                    "sub_fields": sub_fields,
                    "sub_fields_order": list(sub_fields.keys())
                }

        return mt_blocks

    def _detect_mt_type(self, mt_blocks: Dict[str, Any], root: ET.Element = None) -> str:
        """Detect MT type based on blocks present, with block2/MessageType as primary source."""

        # Primary: read MessageType from block2 in XML root — most reliable
        if root is not None:
            try:
                # Try direct child block2/MessageType
                for elem in root.iter():
                    tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                    if tag == 'MessageType' and elem.text and elem.text.strip().isdigit():
                        return f"MT{elem.text.strip()}"
            except Exception:
                pass

        present_tags = set()
        for k in mt_blocks.keys():
            # Normalize duplicate tags: ":61_1" → ":61"
            base = re.sub(r'_\d+$', '', k)
            present_tags.add(base)

        # Score each MT type
        best_match = "MT103"
        best_score = 0

        for mt_type, signature in MT_TYPE_SIGNATURES.items():
            score = len(set(signature) & present_tags)
            if score > best_score:
                best_score = score
                best_match = mt_type

        # Disambiguate MT940 vs MT950 — both have same signature
        if best_match in ("MT940", "MT950"):
            # MT950 has :25 (AccountIdentification), MT940 has :61 (StatementLine)
            if ":25" in present_tags and ":61" not in present_tags:
                return "MT950"
            elif ":61" in present_tags:
                return "MT940"
            # If both present, prefer MT940
            return "MT940"

        # Disambiguate MT900/MT910 vs MT202 — MT202 has :52A and :58A (not :25)
        # MT900/MT910 have :25 (account identification) but NOT :52A/:58A at top level
        if best_match == "MT202":
            if ":25" in present_tags and ":52A" not in present_tags and ":58A" not in present_tags:
                # Has account + related ref + amount but no institution fields → MT900 or MT910
                if ":50K" in present_tags or ":50A" in present_tags:
                    return "MT910"
                return "MT900"

        # If best is MT900, check for :50K/:50A to upgrade to MT910
        if best_match == "MT900":
            if ":50K" in present_tags or ":50A" in present_tags:
                return "MT910"

        return best_match

    def _build_columns(self, mt_blocks: Dict[str, Any]) -> List[str]:
        """Build flat list of columns from MT blocks."""
        columns = []
        for swift_tag, block in mt_blocks.items():
            if block["type"] == "string":
                columns.append(swift_tag)
            elif block["type"] == "map":
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