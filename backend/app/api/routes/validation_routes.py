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
    # Use mt_type if available, fallback to file_type for CSV/JSON/Excel/XML
    # For flat files (CSV/Excel/JSON), try to detect MT type from column names
    detected_mt = md.mt_type
    if not detected_mt and md.column_structure:
        # Check if columns contain block2.MessageType value
        if md.sample_data and len(md.sample_data) > 0:
            row = md.sample_data[0]
            for k, v in row.items():
                k_lower = str(k).lower().replace('.', '').replace('_', '')
                if 'messagetype' in k_lower and v and str(v).strip().isdigit():
                    detected_mt = f"MT{str(v).strip()}"
                    break
    rule_type = detected_mt or md.file_type
    if not rule_type:
        raise HTTPException(status_code=400, detail="MessageDescription has no MT type or file type")


    # Delete existing rules for this (mt_type, file_type) combination only —
    # NOT every rule sharing mt_type, since a real MT text upload and an
    # ISO 20022 XML upload can disambiguate to the same mt_type (e.g. both
    # "MT103") while being structurally incompatible rule sets. Wiping by
    # mt_type alone meant importing rules from one silently destroyed the
    # other's rules, and validation/transform gates checking mt_type alone
    # would silently validate a file against the wrong kind of reference.
    db.query(ValidationRule).filter(
        ValidationRule.mt_type == rule_type,
        ValidationRule.source_file_type == md.file_type
    ).delete()

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
        if elem.name in NAME_TO_TAG:
            return NAME_TO_TAG[elem.name]
        return None

    MULTILINE_FIELDS = {
        'Ordering Customer', 'Beneficiary Customer', 'Beneficiary Institution',
        'Remittance Information', 'Sender to Receiver Information',
        'Information to Account Owner', 'Statement Line',
        'Ordering Institution', 'Intermediary Institution',
        'Account With Institution'
    }

    COMPOUND_FIELDS = {
        'Statement Number': 12,
        'Opening Balance': 25,
        'Closing Balance': 25,
        'Intermediate Opening Balance': 25,
        'Intermediate Closing Balance': 25,
    }

    added_tags = set()
    created = 0

    for elem in elements:
        block_name = _get_block_name(elem, elements)
        field_tag = get_field_tag(elem)

        max_length = elem.max_length
        if elem.name in MULTILINE_FIELDS:
            max_length = max(max_length or 35, 140)
        elif elem.name in COMPOUND_FIELDS:
            max_length = max(max_length or 0, COMPOUND_FIELDS[elem.name])

        if elem.example_value and max_length:
            max_length = max(max_length, len(str(elem.example_value)) + 10)
        elif elem.example_value and not max_length:
            max_length = max(35, len(str(elem.example_value)) + 10)

        rule = ValidationRule(
            mt_type=rule_type,
            source_file_type=md.file_type,
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

        if field_tag and re.search(r'_\d+$', field_tag):
            base_tag = re.sub(r'_\d+$', '', field_tag)
            if base_tag not in added_tags:
                added_tags.add(base_tag)
                base_rule = ValidationRule(
                    mt_type=rule_type,
                    source_file_type=md.file_type,
                    block_name=block_name,
                    field_tag=base_tag,
                    field_name=elem.name,
                    mandatory=False,
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

    return {"message": f"Imported {created} validation rules for {rule_type}", "count": created}


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
    """Validate a client SWIFT/data file against stored rules."""
    # Save uploaded file
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    file_path = UPLOAD_DIR / unique_filename
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    return validate_file_at_path(str(file_path), file.filename, db)


def validate_file_at_path(file_path: str, file_name: str, db: Session) -> dict:
    """Core validation logic, shared between the /validate endpoint and any
    other caller that needs to check a file against stored rules before
    proceeding with it (e.g. transform_mapping.py's pre-transform gate —
    see that module's _validate_before_transform). Takes a path to an
    already-saved file rather than an UploadFile so it can be called
    without going through a second HTTP request. Raises HTTPException on
    "no rules configured" or a parse failure; returns the same result dict
    shape as the /validate endpoint (including is_valid=False, which is a
    normal return, not an exception — callers that want to BLOCK on a
    failed validation must check is_valid themselves)."""
    from app.services.file_processor import FileProcessor

    try:
        # Route based on file type
        file_info = FileProcessor.process_file(str(file_path))
        file_type = file_info.get("file_type")
        mt_info = file_info.get("mt_info")

        # ── SWIFT MT files (TXT or XML_MT) ────────────────────────────────────
        if file_type == "XML_MT" and mt_info:
            mt_type = mt_info.get("mt_type")
            mt_blocks = mt_info.get("mt_blocks", {})

            if not mt_type:
                raise HTTPException(status_code=400, detail="Could not detect MT type from file")

            # Load validation rules — prefer ones imported from the same
            # kind of file (source_file_type == file_type): mt_type alone
            # can be shared by an XML-sourced and an MT-text-sourced
            # reference (see the source_file_type column's docstring on
            # ValidationRule), and checking an MT text file against
            # XML-shaped rules (or vice versa) would report every field as
            # missing regardless of the file's actual correctness. Falls
            # back to any rule under this mt_type for rows predating this
            # column (source_file_type is nullable).
            rules = db.query(ValidationRule).filter(
                ValidationRule.mt_type == mt_type,
                ValidationRule.source_file_type == file_type
            ).all()
            if not rules:
                # Legacy rows only (source_file_type is nullable) — a rule
                # set that DOES have a source_file_type, just a different
                # one than this file's, must never match here, or an MT
                # text file gets checked against XML-shaped field tags (or
                # vice versa) and every field is reported as missing.
                rules = db.query(ValidationRule).filter(
                    ValidationRule.mt_type == mt_type,
                    ValidationRule.source_file_type.is_(None)
                ).all()

            if not rules:
                # Check if rules exist for a different MT type — mismatch
                all_rule_types = [r.mt_type for r in db.query(ValidationRule.mt_type).distinct().all()]
                if all_rule_types:
                    raise HTTPException(
                        status_code=400,
                        detail=f"MT type mismatch: file is {mt_type} but available standards are {', '.join(all_rule_types)}. Please select the correct reference standard."
                    )
                raise HTTPException(
                    status_code=404,
                    detail=f"No validation rules found for {mt_type}. Please generate a Message Description first."
                )

            field_map = _build_field_map(mt_blocks)
            errors, warnings, passed = _run_validation(rules, field_map, mt_type, is_mt_text=True)

            return {
                "mt_type": mt_type,
                "file_name": file_name,
                "file_type": file_type,
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

        # ── CSV / Excel / JSON / XML ──────────────────────────────────────────
        else:
            columns = file_info.get("columns", [])
            sample_data = file_info.get("sample_data", [])

            if not columns:
                raise HTTPException(status_code=400, detail="Could not extract columns from file")

            # Try to detect MT type from the data itself
            raw_map_preview = sample_data[0] if sample_data else {}
            detected_mt_type = None

            # An ISO 20022 XML upload (file_type == "XML_ISO20022") already
            # carries its detected mt_type in mt_info — the same detection
            # iso20022_parser ran when this file's own Message Description
            # was generated (see file_processor.py). Reference rules
            # imported from an XML-sourced MD (import_rules_from_md) are
            # stored under exactly that mt_type, not under the literal
            # string "XML_ISO20022" — checking mt_info first, before the
            # block2.MessageType column-scan below (which only ever matches
            # flattened MT-tag data, never a real XML upload), is what lets
            # an XML file validate against its own XML-sourced reference at
            # all instead of always hitting "no rules found for
            # XML_ISO20022 files".
            if mt_info and mt_info.get("mt_type"):
                detected_mt_type = mt_info["mt_type"]

            # Look for block2.MessageType or similar fields that indicate MT
            # type — covers flattened CSV/JSON exports of MT-tag data.
            if not detected_mt_type:
                for k, v in raw_map_preview.items():
                    k_lower = str(k).lower()
                    if 'messagetype' in k_lower.replace('_', '').replace('.', '') or k_lower in ('block2.messagetype', 'block2_messagetype'):
                        if v and str(v).strip().isdigit():
                            detected_mt_type = f"MT{str(v).strip()}"
                            break

            # Rule lookup order: detected MT type → file type
            pseudo_mt_type = file_type  # fallback e.g. "CSV", "JSON", "Excel"
            rules = []

            if detected_mt_type:
                # Prefer rules imported from the same file_type as this
                # upload — see the source_file_type filtering note in the
                # XML_MT branch above; same reasoning applies here for an
                # XML_ISO20022 upload matching against XML-sourced rules
                # specifically, not whichever rule set happens to occupy
                # this mt_type right now.
                rules = db.query(ValidationRule).filter(
                    ValidationRule.mt_type == detected_mt_type,
                    ValidationRule.source_file_type == file_type
                ).all()
                if not rules:
                    # Legacy rows only — see the same fallback in the
                    # XML_MT branch above for why this must not drop the
                    # source_file_type filter entirely.
                    rules = db.query(ValidationRule).filter(
                        ValidationRule.mt_type == detected_mt_type,
                        ValidationRule.source_file_type.is_(None)
                    ).all()
                if rules:
                    pseudo_mt_type = detected_mt_type
                    logger.info(f"Using MT rules for detected type: {detected_mt_type}")

            if not rules:
                rules = db.query(ValidationRule).filter(
                    ValidationRule.mt_type == file_type
                ).all()

            if not rules:
                raise HTTPException(
                    status_code=404,
                    detail=f"No validation rules found for {pseudo_mt_type} files. Please import rules from Message Description first."
                )

            # Build enriched field map from first sample row
            # Handles dot-notation keys like "block1.SessionNumber"
            raw_map = sample_data[0] if sample_data else {}
            field_map = {}
            for k, v in raw_map.items():
                field_map[k] = v
                k_str = str(k)
                # Handle dot notation: "block1.SessionNumber" -> also store "SessionNumber"
                if '.' in k_str:
                    parts = k_str.split('.')
                    field_map[parts[-1]] = v
                # Handle underscore notation: "block1_SessionNumber" -> also store "SessionNumber"
                if '_' in k_str:
                    parts = k_str.split('_')
                    field_map[parts[-1]] = v
                    # Also try last two parts joined: "32A_Date" -> "Date"
                    if len(parts) >= 2:
                        field_map[parts[-1]] = v
                # Store without colon prefix for SWIFT-style tags: ":20" -> "20"
                if k_str.startswith(':'):
                    field_map[k_str.lstrip(':')] = v
            errors, warnings, passed = _run_validation(rules, field_map, pseudo_mt_type, is_mt_text=False)

            return {
                "mt_type": pseudo_mt_type,
                "file_name": file_name,
                "file_type": file_type,
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


# ── Shared validation logic ───────────────────────────────────────────────────

def _run_validation(rules, field_map, mt_type, is_mt_text: bool = False):
    """Run all rules against a field_map. Returns (errors, warnings, passed)."""
    errors = []
    warnings = []
    passed = []

    SENTINEL = object()

    for rule in rules:
        field_key = rule.field_tag or rule.field_name

        # Use SENTINEL to distinguish missing key from falsy value (e.g. "0", 0, False)
        def _get(key):
            if key is None:
                return SENTINEL
            v = field_map.get(key, SENTINEL)
            return v

        value = SENTINEL
        # Build all possible lookup keys — block_name may have spaces (e.g. "Ordering Institution")
        block_no_space = rule.block_name.replace(" ", "") if rule.block_name else None
        lookup_keys = [
            rule.field_tag,
            rule.field_name,
            f"{rule.block_name}.{rule.field_name}" if rule.block_name else None,
            f"{block_no_space}.{rule.field_name}" if block_no_space else None,
            rule.field_tag.lstrip(':') if rule.field_tag else None,
        ]
        for key in lookup_keys:
            v = _get(key)
            if v is not SENTINEL:
                value = v
                break

        if value is SENTINEL:
            value = None

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

    # Warn about unknown fields — only meaningful for real SWIFT MT text,
    # where field_map keys are SWIFT tags ("block4.:20") the "block"-prefix
    # / known_fields matching below is built for. mt_type ALWAYS reads as
    # an MT-equivalent string ("MT103") even for an ISO 20022 XML upload —
    # see the mt_info-first rule-lookup fix elsewhere in this file — so
    # mt_type.startswith("MT") can't tell the two apart; that used to make
    # every XML validation run this SWIFT-only heuristic against XML
    # dotted paths it was never designed to recognize, misreporting
    # legitimate, correctly-covered fields as "unknown".
    if is_mt_text:
        known_fields = set()
        for r in rules:
            if r.field_tag: known_fields.add(r.field_tag)
            if r.field_name: known_fields.add(r.field_name)
            if r.block_name and r.field_name:
                known_fields.add(f"{r.block_name}.{r.field_name}")

        warned = set()
        for field_key, value in field_map.items():
            if field_key in known_fields or field_key.startswith("block"):
                continue
            parts = field_key.split(".")
            if len(parts) == 2 and parts[1] in known_fields:
                continue
            base_key = parts[-1] if "." in field_key else field_key
            if base_key not in warned:
                warned.add(base_key)
                warnings.append({
                    "field": field_key,
                    "value": value,
                    "message": f"Unknown field '{field_key}' not in standard {mt_type}"
                })

    return errors, warnings, passed


def _build_field_map(mt_blocks: dict) -> dict:
    """Flatten mt_blocks into a multi-key value map."""
    field_map = {}

    def recurse(blocks, block_name=None):
        for tag, block in blocks.items():
            if not isinstance(block, dict):
                continue

            value = block.get("value")
            field_tag = block.get("tag", tag)
            name = block.get("name", tag)

            if value and field_tag:
                field_map[field_tag] = value
            if value and name and name != field_tag:
                field_map[name] = value
            if value and block_name and name:
                field_map[f"{block_name}.{name}"] = value

            sub_fields = block.get("sub_fields", {})
            if sub_fields:
                current_block = name if block.get("type") == "map" else block_name
                for sub_name, sub_field in sub_fields.items():
                    if isinstance(sub_field, dict):
                        sub_val = sub_field.get("value")
                        sub_tag = sub_field.get("tag", sub_name)

                        if sub_val:
                            field_map[sub_name] = sub_val
                        if sub_val and sub_tag and sub_tag != sub_name:
                            field_map[sub_tag] = sub_val
                        if sub_val and current_block:
                            field_map[f"{current_block}.{sub_name}"] = sub_val
                            # Also store without spaces for XML tag matching
                            no_space = current_block.replace(" ", "")
                            if no_space != current_block:
                                field_map[f"{no_space}.{sub_name}"] = sub_val

                        if sub_field.get("sub_fields"):
                            recurse({sub_name: sub_field}, current_block)

    recurse(mt_blocks)
    return field_map


def _validate_field(rule: ValidationRule, value) -> List[str]:
    """Validate a single field value against its rule."""
    errors = []

    if rule.element_type == 'COMPOSITE':
        return []

    if rule.field_name in ('block1', 'block2', 'block2Input', 'block2Output', 'block3', 'block4', 'block5'):
        return []

    # Treat None and empty string as missing — but NOT "0" or 0
    is_missing = value is None or (isinstance(value, str) and value.strip() == "")

    if rule.mandatory and is_missing:
        errors.append(f"Field is mandatory but missing")
        return errors

    if is_missing:
        return []

    str_val = str(value).strip()

    # ── SWIFT field-specific validations (per SWIFT Standards Reference Guide) ─
    import re as _re2
    clean_tag = (rule.field_tag or '').lstrip(':')

    # 1. Reference fields (:20:, :21:) — format 16x
    #    Max 16 chars, must not start/end with slash, no double slash (T26 rule)
    if clean_tag in ('20', '21'):
        if len(str_val) > 16:
            errors.append(f"Field :{clean_tag}: too long: max 16 chars, got {len(str_val)}")
            return errors
        if str_val.startswith('/') or str_val.endswith('/'):
            errors.append(f"Field :{clean_tag}: must not start or end with '/' (SWIFT T26 rule)")
            return errors
        if '//' in str_val:
            errors.append(f"Field :{clean_tag}: must not contain '//' (SWIFT T26 rule)")
            return errors
        if _re2.search(r'[a-z]', str_val):
            errors.append(
                f"Field :{clean_tag}: must use uppercase only (SWIFT Character Set X). "
                f"Got lowercase in: '{str_val}'"
            )
            return errors

    # 2. Bank Operation Code (:23B:) — format 4!a — exactly 4 uppercase letters
    #    Valid: CRED, CRTS, SPAY, SPRI, SSTD, DEBT
    if clean_tag == '23B':
        valid_23b = {'CRED', 'CRTS', 'SPAY', 'SPRI', 'SSTD', 'DEBT'}
        if not _re2.match(r'^[A-Z]{4}$', str_val):
            errors.append(f"Field :23B: must be exactly 4 uppercase letters. Got: '{str_val}'")
            return errors
        if str_val not in valid_23b:
            errors.append(f"Field :23B: invalid code '{str_val}'. Valid: {', '.join(sorted(valid_23b))}")
            return errors

    # 3. Details of Charges (:71A:) — format 3!a — exactly SHA, OUR or BEN
    if clean_tag == '71A':
        if str_val not in ('SHA', 'OUR', 'BEN'):
            errors.append(f"Field :71A: must be SHA, OUR, or BEN. Got: '{str_val}'")
            return errors

    # 4. Date sub-fields — format 6!n — YYMMDD
    if rule.field_name == 'Date' and rule.element_type in ('DATE', 'STRING'):
        if _re2.match(r'^[0-9]{6}$', str_val):
            mm = int(str_val[2:4])
            dd = int(str_val[4:6])
            if not (1 <= mm <= 12):
                errors.append(f"Invalid month {mm} in date '{str_val}' (expected 01-12)")
            if not (1 <= dd <= 31):
                errors.append(f"Invalid day {dd} in date '{str_val}' (expected 01-31)")
        elif len(str_val) != 6 or not str_val.isdigit():
            errors.append(f"Invalid date format '{str_val}': expected YYMMDD (6 digits)")

    # 5. Currency — format 3!a — exactly 3 uppercase letters (ISO 4217)
    if rule.field_name == 'Currency':
        if not _re2.match(r'^[A-Z]{3}$', str_val):
            errors.append(f"Invalid currency '{str_val}': expected 3 uppercase letters (ISO 4217)")

    # 6. Amount — format 15d — digits with optional comma/dot decimal, max 15 digits
    if rule.field_name == 'Amount' and rule.element_type == 'DECIMAL':
        if not _re2.match(r'^[0-9]{1,15}([,.][0-9]{0,2})?$', str_val):
            errors.append(f"Invalid amount '{str_val}': expected digits with optional decimal (max 15 digits)")

    # 7. BIC — format 4!a2!a2!c[3!c] — 8 or 11 uppercase alphanumeric chars
    if rule.field_name == 'BIC':
        if not _re2.match(r'^[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}([A-Z0-9]{3})?$', str_val):
            errors.append(f"Invalid BIC '{str_val}': expected 8 or 11 uppercase alphanumeric (4!a2!a2!c[3!c])")

    # 8. DebitCredit indicator — C, D, RC or RD
    if rule.field_name == 'DebitCredit':
        if str_val not in ('D', 'C', 'RD', 'RC'):
            errors.append(f"Invalid D/C indicator '{str_val}': expected C, D, RC, or RD")
    # ─────────────────────────────────────────────────────────────────────────

    effective_min = rule.min_length
    effective_max = rule.max_length

    if rule.fin_format and (effective_min is None and effective_max is None):
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

    if rule.fin_format and rule.block_name not in ('block1', 'block2', 'block3', 'block5'):
        fmt_error = _check_fin_format_type_only(str_val, rule.fin_format)
        if fmt_error:
            errors.append(fmt_error)

    if rule.pattern:
        try:
            if not re.match(rule.pattern, str_val):
                errors.append(f"Value '{str_val}' doesn't match pattern '{rule.pattern}'")
        except re.error:
            pass

    if rule.element_type and rule.element_type in ('INTEGER', 'DECIMAL', 'DATE'):
        type_error = _check_type(str_val, rule.element_type)
        if type_error:
            errors.append(type_error)

    return errors


# Fields requiring strict uppercase SWIFT Character Set (no lowercase)
SWIFT_UPPERCASE_FIELDS = {'20', '21', '23B', '71A'}


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
        m = re.match(r'^(\d+)(!?)([a-zA-Z])$', fin_format.strip())
        if not m:
            return None

        length = int(m.group(1))
        exact = m.group(2) == '!'
        ftype = m.group(3).lower()

        if exact and len(value) != length:
            return f"Expected exactly {length} chars (fin_format: {fin_format}), got {len(value)}"
        elif not exact and len(value) > length:
            return f"Expected max {length} chars (fin_format: {fin_format}), got {len(value)}"

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


def _check_type(value: str, element_type: str) -> str:
    """Check element type."""
    if element_type == 'INTEGER':
        if not value.isdigit():
            return f"Expected integer, got '{value}'"
    elif element_type == 'DECIMAL':
        if not re.match(r'^\d+[,.]?\d*$', value):
            return f"Expected decimal, got '{value}'"
    elif element_type == 'DATE':
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