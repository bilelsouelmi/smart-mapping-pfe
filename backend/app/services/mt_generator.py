"""
MT Generator Service
Generates SWIFT MT text files from extracted ISO 20022 fields.
"""

from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# MT type → block2 message type number
MT_TYPE_TO_NUM = {
    "MT103": "103",
    "MT202": "202",
    "MT900": "900",
    "MT910": "910",
    "MT940": "940",
    "MT950": "950",
}

# ChrgBr reverse mapping (ISO → SWIFT)
CHRGBR_REVERSE = {
    "SHAR": "SHA",
    "DEBT": "OUR",
    "CRED": "BEN",
    "SHA": "SHA",
    "OUR": "OUR",
    "BEN": "BEN",
}


class MTGenerator:

    def _build_32a(self, fields: Dict[str, str]) -> str:
        """Build :32A: field from date + currency + amount."""
        val = fields.get(":32A:", "")
        
        # Already in SWIFT format YYMMDDCCCAMOUNT
        import re
        if re.match(r"^\d{6}[A-Z]{3}", val):
            return val
        
        # It's a date - need to find amount separately
        date_str = ""
        amount_str = ""
        currency = "EUR"
        
        if len(val) == 10 and val[4] == '-':
            parts = val.split('-')
            date_str = f"{parts[0][2:]}{parts[1]}{parts[2]}"
        
        # Try to find amount from Amt field
        for key, v in fields.items():
            if 'Amt' in key or key == ":32A_amount:":
                amount_str = v.replace('.', ',')
                break
        
        if date_str and amount_str:
            return f"{date_str}{currency}{amount_str}"
        elif date_str:
            return f"{date_str}{currency}0,"
        return val

    def generate(self, extracted_fields: Dict[str, str], mt_type: str,
                 iso_source: str = "", envelope: dict = None) -> str:
        """
        Generate SWIFT MT text from extracted ISO 20022 fields.
        extracted_fields: {":20:": "value", ":32A:": "value", ...}
        envelope: optional dict with original block1/block5 data
        """
        mt_num = MT_TYPE_TO_NUM.get(mt_type, "103")
        envelope = envelope or {}

        # Build block1 — restore original or use default
        b1_data = envelope.get('block1', '')
        if b1_data and len(b1_data) >= 10:
            block1 = f"{{1:{b1_data}}}"
        else:
            block1 = f"{{1:F01SMRT{mt_type.replace('MT','')}XXXX0000000000}}"

        # Build block2 — restore destination or use default
        b2_dest = envelope.get('block2_dest', 'BNPAFRPPXXXX')
        b2_priority = envelope.get('block2_priority', 'N')
        if not b2_dest:
            b2_dest = 'BNPAFRPPXXXX'
        block2 = f"{{2:I{mt_num}{b2_dest}{b2_priority}}}"

        # Build block3 — restore original ref or use :20: value
        b3_108 = envelope.get('block3_108', '')
        ref = extracted_fields.get(":20:", "")
        if b3_108:
            block3 = f"{{3:{{108:{b3_108}}}}}"
        elif ref:
            block3 = f"{{3:{{108:{ref}}}}}"
        else:
            block3 = "{3:{108:GENERATED}}"

        # Build block4 fields
        block4_fields = self._build_block4(extracted_fields, mt_type)

        # Build block5 — restore original CHK or use placeholder
        b5_chk = envelope.get('block5_chk', '000000000000')
        if not b5_chk:
            b5_chk = '000000000000'
        block5 = f"{{5:{{CHK:{b5_chk}}}}}"

        # Assemble
        block4_content = "\n".join(block4_fields)
        mt_text = f"{block1}{block2}{block3}{{4:\n{block4_content}\n-}}{block5}"

        return mt_text

    def _build_block4(self, fields: Dict[str, str], mt_type: str) -> list:
        """Build block4 field lines in correct MT order."""
        lines = []

        # MT field order per message type
        mt_orders = {
            "MT103": [":20:", ":23B:", ":23E:", ":32A:", ":33B:", ":36:",
                      ":50K:", ":52A:", ":53A:", ":54A:", ":56A:", ":57A:",
                      ":59:", ":70:", ":71A:", ":72:", ":77B:"],
            "MT900": [":20:", ":21:", ":25:", ":32A:", ":52A:", ":72:"],
            "MT910": [":20:", ":21:", ":25:", ":32A:", ":50K:", ":52A:",
                      ":56A:", ":72:"],
            "MT940": [":20:", ":25:", ":28C:", ":60F:", ":61:", ":86:", ":62F:",
                      ":64:", ":65:"],
            "MT950": [":20:", ":25:", ":28C:", ":60F:", ":61:", ":62F:", ":64:"],
            "MT202": [":20:", ":21:", ":32A:", ":52A:", ":53A:", ":54A:", ":56A:",
                      ":57A:", ":58A:", ":72:"],
        }

        order = mt_orders.get(mt_type, list(fields.keys()))

        # For MT103 :23B: is always CRED (bank operation code not in ISO 20022)
        if mt_type == 'MT103' and ':23B:' not in fields:
            fields[':23B:'] = 'CRED'

        for tag in order:
            if tag == ":32A:":
                value = self._build_32a(fields)
            else:
                value = fields.get(tag, '')
            if not value:
                continue

            # Post-process values
            if tag != ":32A:":
                value = self._process_value(tag, value, mt_type)
            if value:
                lines.append(f"{tag}{value}")

        return lines

    def _process_value(self, tag: str, value: str, mt_type: str) -> str:
        """Post-process field values for MT format."""
        if not value:
            return ''

        # ChrgBr: ISO → SWIFT format
        if tag == ":71A:":
            return CHRGBR_REVERSE.get(value, value)

        # :32A: handling - value could be date OR amount
        if tag == ":32A:":
            # If it's a date (2026-05-06)
            if len(value) == 10 and value[4] == '-':
                parts = value.split('-')
                if len(parts) == 3:
                    date_str = f"{parts[0][2:]}{parts[1]}{parts[2]}"
                    # Look for amount in fields dict (passed via context)
                    return f"{date_str}EUR0,"  # will be fixed by combine step
            # If it's an amount (5000.00)
            if value.replace('.','').replace(',','').isdigit():
                return value.replace('.', ',')
            # Already in SWIFT format (260506EUR25000,)
            return value

        return value

    def generate_from_md(self, md_elements: list, mt_type: str) -> str:
        """
        Generate MT from MessageDescriptionElements.
        md_elements: list of MessageDescriptionElement objects
        """
        # Build field map from element example values
        field_map = {}
        for el in md_elements:
            if el.field_tag and el.field_tag not in ('block1', 'block2',
                                                       'block3', 'block4', 'block5'):
                value = el.example_value or ''
                if value:
                    tag = el.field_tag if el.field_tag.startswith(':') else f':{el.field_tag}:'
                    field_map[tag] = value

        return self.generate(field_map, mt_type)


# Singleton
mt_generator = MTGenerator()