from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import re
import uuid
import logging
from pathlib import Path
from app.core.deps import get_current_user
from app.models.user import User
from app.database import get_db
from app.config import settings
from app.models.validation_rule import ValidationRule
from app.models.message_description import MessageDescription
from app.models.message_description_element import MessageDescriptionElement

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(settings.UPLOAD_DIR)


# ── Import rules from MessageDescription ─────────────────────────────────────
@router.post("/validation-rules/import-from-md/{md_id}")
async def import_rules_from_md(
    md_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Import validation rules from a MessageDescription's elements."""
    md = db.query(MessageDescription).filter(
        MessageDescription.id == md_id,
        MessageDescription.user_id == current_user.id
    ).first()
    if not md:
        raise HTTPException(status_code=404, detail="MessageDescription not found")
    if not md.mt_type:
        raise HTTPException(status_code=400, detail="MessageDescription has no MT type")

    # Delete existing rules for this MT type
    db.query(ValidationRule).filter(ValidationRule.mt_type == md.mt_type).delete()

    # Get all elements recursively
    elements = db.query(MessageDescriptionElement).filter(
        MessageDescriptionElement.message_description_id == md_id
    ).all()

    # Build parent map for quick lookup
    elem_map = {e.id: e for e in elements}

    # Reverse map: display name → field_tag
    NAME_TO_TAG = {
        "Transaction Reference": ":20",
        "Related Reference": ":21",
        "Bank Operation Code": ":23B",
        "Instruction Code": ":23E",
        "Account Identification": ":25",
        "Statement Number": ":28C",
        "Value Date/Currency/Amount": ":32A",
        "Currency/Instructed Amount": ":33B",
        "Ordering Customer": ":50K",
        "Ordering Institution": ":52A",
        "Sender's Correspondent": ":53A",
        "Receiver's Correspondent": ":54A",
        "Intermediary Institution": ":56A",
        "Account With Institution": ":57A",
        "Beneficiary Institution": ":58A",
        "Beneficiary Customer": ":59",
        "Opening Balance": ":60F",
        "Intermediate Opening Balance": ":60M",
        "Statement Line": ":61",
        "Closing Balance": ":62F",
        "Intermediate Closing Balance": ":62M",
        "Remittance Information": ":70",
        "Details of Charges": ":71A",
        "Sender to Receiver Information": ":72",
        "Information to Account Owner": ":86",
    }

    def get_field_tag(elem):
        """Get field_tag for an element."""
        if elem.field_tag:
            return elem.field_tag
        # Try reverse lookup by name
        if elem.name in NAME_TO_TAG:
            return NAME_TO_TAG[elem.name]
        return None

    # Multiline fields — their max_length should be multiplied
    MULTILINE_FIELDS = {
        'Ordering Customer', 'Beneficiary Customer', 'Beneficiary Institution',
        'Remittance Information', 'Sender to Receiver Information',
        'Information to Account Owner', 'Statement Line',
        'Ordering Institution', 'Intermediary Institution',
        'Account With Institution'
    }

    # Fields with compound formats that may exceed simple max_length
    # e.g. :28C = 5!n/3!n = "00001/001" = 9 chars
    COMPOUND_FIELDS = {
        'Statement Number': 12,       # 5!n/3!n
        'Opening Balance': 25,        # C/D + 6n + 3a + 15d
        'Closing Balance': 25,
        'Intermediate Opening Balance': 25,
        'Intermediate Closing Balance': 25,
    }

    # Track added tags to handle duplicates like :61_1 → add :61 rule too
    added_tags = set()

    created = 0
    for elem in elements:
        block_name = _get_block_name(elem, elements)
        field_tag = get_field_tag(elem)

        # Fix max_length for multiline fields
        max_length = elem.max_length
        if elem.name in MULTILINE_FIELDS:
            max_length = max(max_length or 35, 140)
        elif elem.name in COMPOUND_FIELDS:
            max_length = max(max_length or 0, COMPOUND_FIELDS[elem.name])

        # Use example_value length as minimum max_length
        if elem.example_value and max_length:
            max_length = max(max_length, len(str(elem.example_value)) + 10)
        elif elem.example_value and not max_length:
            max_length = max(35, len(str(elem.example_value)) + 10)

        rule = ValidationRule(
            mt_type=md.mt_type,
            block_name=block_name,
            field_tag=field_tag,
            field_name=elem.name,
            mandatory=elem.mandatory if elem.mandatory is not None else False,
            min_length=elem.min_length,
            max_length=max_length,
            fin_format=elem.fin_format,
            pattern=elem.pattern,
            element_type=elem.element_type,
            description=elem.description
        )
        db.add(rule)
        created += 1

        # For duplicate tags like :61_1, :86_1 → also add rule for base tag :61, :86
        if field_tag and re.search(r'_\d+$', field_tag):
            base_tag = re.sub(r'_\d+$', '', field_tag)
            if base_tag not in added_tags:
                added_tags.add(base_tag)
                base_rule = ValidationRule(
                    mt_type=md.mt_type,
                    block_name=block_name,
                    field_tag=base_tag,
                    field_name=elem.name,
                    mandatory=False,  # duplicates are optional
                    min_length=elem.min_length,
                    max_length=max_length,
                    fin_format=elem.fin_format,
                    pattern=elem.pattern,
                    element_type=elem.element_type,
                    description=elem.description
                )
                db.add(base_rule)
                created += 1

    db.commit()
    return {"message": f"Imported {created} validation rules for {md.mt_type}", "count": created}


def _get_block_name(elem, all_elements):
    """Get the block name (block1, block2, block4) for an element."""
    if elem.parent_id is None:
        return elem.name
    parent = next((e for e in all_elements if e.id == elem.parent_id), None)
    if parent and parent.parent_id is None:
        return parent.name
    if parent:
        return _get_block_name(parent, all_elements)
    return None


# ── List rules ────────────────────────────────────────────────────────────────
@router.get("/validation-rules")
async def list_rules(
    mt_type: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all validation rules, optionally filtered by MT type."""
    query = db.query(ValidationRule)
    if mt_type:
        query = query.filter(ValidationRule.mt_type == mt_type)
    rules = query.order_by(ValidationRule.mt_type, ValidationRule.block_name, ValidationRule.id).all()
    return [_rule_to_dict(r) for r in rules]


# ── Validate file ─────────────────────────────────────────────────────────────
@router.post("/validate")
async def validate_swift_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Validate a client SWIFT file against stored rules."""
    from app.services.swift_txt_parser import swift_txt_parser

    # Save file
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = UPLOAD_DIR / unique_filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        # Parse the file
        result = swift_txt_parser.parse(str(file_path))
        mt_type = result.get("mt_type")
        mt_blocks = result.get("mt_blocks", {})

        if not mt_type:
            raise HTTPException(status_code=400, detail="Could not detect MT type from file")

        # Load validation rules for this MT type
        rules = db.query(ValidationRule).filter(
            ValidationRule.mt_type == mt_type
        ).all()

        if not rules:
            raise HTTPException(
                status_code=404,
                detail=f"No validation rules found for {mt_type}. Please import rules first."
            )

        # Build flat field map from parsed blocks
        field_map = _build_field_map(mt_blocks)

        # Run validation
        errors = []
        warnings = []
        passed = []

        for rule in rules:
            # Try multiple keys to find value: field_tag, field_name, block.field_name
            field_key = rule.field_tag or rule.field_name
            value = (
                field_map.get(rule.field_tag) if rule.field_tag else None
            ) or field_map.get(rule.field_name) or (
                field_map.get(f"{rule.block_name}.{rule.field_name}") if rule.block_name else None
            )

            result_item = {
                "field": field_key,
                "field_name": rule.field_name,
                "block": rule.block_name,
                "value": value,
                "rule": {
                    "mandatory": rule.mandatory,
                    "min_length": rule.min_length,
                    "max_length": rule.max_length,
                    "fin_format": rule.fin_format,
                    "pattern": rule.pattern,
                    "element_type": rule.element_type
                }
            }

            field_errors = _validate_field(rule, value)

            if field_errors:
                result_item["errors"] = field_errors
                errors.append(result_item)
            else:
                passed.append(result_item)

        # Check for unexpected fields
        # Build set of all known identifiers (tags + names + block.name patterns)
        known_fields = set()
        for r in rules:
            if r.field_tag:
                known_fields.add(r.field_tag)
            if r.field_name:
                known_fields.add(r.field_name)
            if r.block_name and r.field_name:
                known_fields.add(f"{r.block_name}.{r.field_name}")

        # Only warn about truly unknown fields (not matched by any rule)
        warned = set()
        for field_key, value in field_map.items():
            # Skip block-level entries and already-known fields
            if field_key in known_fields:
                continue
            if field_key.startswith("block"):
                continue
            # Skip sub-patterns like "block1.X" if X is known
            parts = field_key.split(".")
            if len(parts) == 2 and parts[1] in known_fields:
                continue
            # Deduplicate warnings
            base_key = parts[-1] if "." in field_key else field_key
            if base_key not in warned:
                warned.add(base_key)
                warnings.append({
                    "field": field_key,
                    "value": value,
                    "message": f"Unknown field '{field_key}' not in standard {mt_type}"
                })

        return {
            "mt_type": mt_type,
            "file_name": file.filename,
            "is_valid": len(errors) == 0,
            "summary": {
                "total_rules": len(rules),
                "passed": len(passed),
                "failed": len(errors),
                "warnings": len(warnings)
            },
            "errors": errors,
            "warnings": warnings,
            "passed": passed
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


def _build_field_map(mt_blocks: dict) -> dict:
    """Flatten mt_blocks into a multi-key value map.
    Stores values by: field_tag, field_name, and block.fieldname pattern.
    """
    field_map = {}

    def recurse(blocks, block_name=None):
        for tag, block in blocks.items():
            if not isinstance(block, dict):
                continue

            value = block.get("value")
            field_tag = block.get("tag", tag)
            name = block.get("name", tag)

            # Store by field_tag (e.g. ":20", "block1")
            if value and field_tag:
                field_map[field_tag] = value

            # Store by name (e.g. "TransactionReference")
            if value and name and name != field_tag:
                field_map[name] = value

            # Store by block.name (e.g. "block1.ApplicationIdentifier")
            if value and block_name and name:
                field_map[f"{block_name}.{name}"] = value

            sub_fields = block.get("sub_fields", {})
            if sub_fields:
                # Determine current block name for children
                current_block = name if block.get("type") == "map" else block_name
                for sub_name, sub_field in sub_fields.items():
                    if isinstance(sub_field, dict):
                        sub_val = sub_field.get("value")
                        sub_tag = sub_field.get("tag", sub_name)

                        # Store by sub_name
                        if sub_val:
                            field_map[sub_name] = sub_val
                        # Store by tag
                        if sub_val and sub_tag and sub_tag != sub_name:
                            field_map[sub_tag] = sub_val
                        # Store by block.subname
                        if sub_val and current_block:
                            field_map[f"{current_block}.{sub_name}"] = sub_val

                        # Recurse deeper
                        if sub_field.get("sub_fields"):
                            recurse({sub_name: sub_field}, current_block)

    recurse(mt_blocks)
    return field_map


def _validate_field(rule: ValidationRule, value) -> List[str]:
    """Validate a single field value against its rule. Returns list of error messages."""
    errors = []

    # Skip validation for COMPOSITE parent blocks — only validate leaf fields
    if rule.element_type == 'COMPOSITE':
        return []

    # Skip validation for block-level entries (block1, block2, block4...)
    if rule.field_name in ('block1', 'block2', 'block2Input', 'block2Output', 'block3', 'block4', 'block5'):
        return []

    # 1. PRESENCE check
    if rule.mandatory and (value is None or value == ""):
        errors.append(f"Field is mandatory but missing")
        return errors  # No point checking further if missing

    if value is None or value == "":
        return []  # Optional field not present — OK

    str_val = str(value).strip()

    # 2. LENGTH check — use min_length/max_length if available
    # Only use fin_format length if min/max not explicitly set
    effective_min = rule.min_length
    effective_max = rule.max_length

    # If fin_format defines length but min/max conflict, prefer min/max
    if rule.fin_format and (effective_min is None and effective_max is None):
        # Extract length from fin_format as fallback
        import re as _re
        m = _re.match(r'^(\d+)(!?)([a-zA-Z])$', rule.fin_format.strip())
        if m:
            length = int(m.group(1))
            exact = m.group(2) == '!'
            if exact:
                effective_min = length
                effective_max = length
            else:
                effective_max = length

    if effective_min is not None and len(str_val) < effective_min:
        errors.append(f"Value too short: {len(str_val)} < {effective_min} (min)")

    if effective_max is not None and len(str_val) > effective_max:
        errors.append(f"Value too long: {len(str_val)} > {effective_max} (max)")

    # 3. FIN FORMAT check — only for block4 fields (not header blocks)
    # Skip fin_format check for header block sub-fields to avoid false positives
    if rule.fin_format and rule.block_name not in ('block1', 'block2', 'block3', 'block5'):
        # Only check character type, not length (length already checked above)
        fmt_error = _check_fin_format_type_only(str_val, rule.fin_format)
        if fmt_error:
            errors.append(fmt_error)

    # 4. PATTERN check
    if rule.pattern:
        try:
            if not re.match(rule.pattern, str_val):
                errors.append(f"Value '{str_val}' doesn't match pattern '{rule.pattern}'")
        except re.error:
            pass  # Invalid regex — skip

    # 5. TYPE check — only for numeric/date types
    if rule.element_type and rule.element_type in ('INTEGER', 'DECIMAL', 'DATE'):
        type_error = _check_type(str_val, rule.element_type)
        if type_error:
            errors.append(type_error)

    return errors


def _check_fin_format_type_only(value: str, fin_format: str) -> str:
    """Check only character type from fin_format, not length."""
    try:
        m = re.match(r'^(\d+)(!?)([a-zA-Z])$', fin_format.strip())
        if not m:
            return None
        ftype = m.group(3).lower()
        if ftype == 'n' and not value.isdigit():
            return f"Expected numeric value (fin_format: {fin_format}), got '{value}'"
        elif ftype == 'a' and not value.isalpha():
            return f"Expected alphabetic value (fin_format: {fin_format}), got '{value}'"
        elif ftype == 'd':
            if not re.match(r'^\d+,?\d*$', value):
                return f"Expected decimal value (fin_format: {fin_format}), got '{value}'"
    except Exception:
        pass
    return None


def _check_fin_format(value: str, fin_format: str) -> str:
    """Check SWIFT fin_format like 16x, 6!n, 3!a, 15d"""
    try:
        # Parse fin_format: optional length + optional ! + type
        m = re.match(r'^(\d+)(!?)([a-zA-Z])$', fin_format.strip())
        if not m:
            return None  # Unknown format — skip

        length = int(m.group(1))
        exact = m.group(2) == '!'
        ftype = m.group(3).lower()

        # Check length
        if exact and len(value) != length:
            return f"Expected exactly {length} chars (fin_format: {fin_format}), got {len(value)}"
        elif not exact and len(value) > length:
            return f"Expected max {length} chars (fin_format: {fin_format}), got {len(value)}"

        # Check character type
        if ftype == 'n' and not value.isdigit():
            return f"Expected numeric value (fin_format: {fin_format}), got '{value}'"
        elif ftype == 'a' and not value.isalpha():
            return f"Expected alphabetic value (fin_format: {fin_format}), got '{value}'"
        elif ftype == 'd':
            # Decimal — digits with optional comma
            if not re.match(r'^\d+,?\d*$', value):
                return f"Expected decimal value (fin_format: {fin_format}), got '{value}'"

    except Exception:
        pass
    return None


def _check_type(value: str, element_type: str) -> str:
    """Check element type."""
    if element_type == 'INTEGER':
        if not value.isdigit():
            return f"Expected integer, got '{value}'"
    elif element_type == 'DECIMAL':
        if not re.match(r'^\d+[,.]?\d*$', value):
            return f"Expected decimal, got '{value}'"
    elif element_type == 'DATE':
        # SWIFT date format YYMMDD
        if not re.match(r'^\d{6}$', value):
            return f"Expected date (YYMMDD format), got '{value}'"
    return None


def _rule_to_dict(rule: ValidationRule) -> dict:
    return {
        "id": rule.id,
        "mt_type": rule.mt_type,
        "block_name": rule.block_name,
        "field_tag": rule.field_tag,
        "field_name": rule.field_name,
        "mandatory": rule.mandatory,
        "min_length": rule.min_length,
        "max_length": rule.max_length,
        "fin_format": rule.fin_format,
        "pattern": rule.pattern,
        "element_type": rule.element_type,
        "description": rule.description
    }