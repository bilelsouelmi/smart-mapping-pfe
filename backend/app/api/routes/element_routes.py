import re
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.message_description_element import MessageDescriptionElement

router = APIRouter()

# ── SWIFT standard field definitions ─────────────────────────────────────────
# fin_format → (min_length, max_length, element_type, description)
SWIFT_FIELD_STANDARDS = {
    # Block 1 sub-fields
    "ApplicationIdentifier":    ("1!a",   1,  1,  "STRING",    "F=FIN, A=GPA, L=LTA"),
    "ServiceIdentifier":        ("2!n",   2,  2,  "STRING",    "01=FIN/GPA, 21=ACK/NAK"),
    "LogicalTerminalAddress":   ("12!c",  12, 12, "STRING",    "BIC Logical Terminal Address"),
    "SessionNumber":            ("4!n",   4,  4,  "INTEGER",   "Session Number"),
    "SequenceNumber":           ("6!n",   6,  6,  "INTEGER",   "Sequence Number"),
    # Block 2 sub-fields
    "InputOutputIdentifier":    ("1!a",   1,  1,  "STRING",    "I=Input, O=Output"),
    "MessageType":              ("3!n",   3,  3,  "INTEGER",   "SWIFT Message Type (e.g. 103, 202)"),
    "DestinationAddress":       ("12!c",  12, 12, "STRING",    "Destination BIC Address"),
    "Priority":                 ("1!a",   1,  1,  "STRING",    "N=Normal, U=Urgent, S=System"),
    "InputTime":                ("4!n",   4,  4,  "STRING",    "Input Time HHMM"),
    "InputDate":                ("6!n",   6,  6,  "STRING",    "Input Date YYMMDD"),
    "OutputDate":               ("6!n",   6,  6,  "STRING",    "Output Date YYMMDD"),
    "OutputTime":               ("4!n",   4,  4,  "STRING",    "Output Time HHMM"),
}

# MT field tag display names
MT_TAG_NAMES = {
    "20": "Transaction Reference",
    "21": "Related Reference",
    "23B": "Bank Operation Code",
    "23E": "Instruction Code",
    "25": "Account Identification",
    "28C": "Statement Number",
    "32A": "Value Date/Currency/Amount",
    "33B": "Currency/Instructed Amount",
    "50K": "Ordering Customer",
    "50A": "Ordering Customer",
    "52A": "Ordering Institution",
    "56A": "Intermediary Institution",
    "57A": "Account With Institution",
    "58A": "Beneficiary Institution",
    "59": "Beneficiary Customer",
    "59A": "Beneficiary Customer",
    "60F": "Opening Balance",
    "60M": "Intermediate Opening Balance",
    "61": "Statement Line",
    "62F": "Closing Balance",
    "62M": "Intermediate Closing Balance",
    "70": "Remittance Information",
    "71A": "Details of Charges",
    "72": "Sender to Receiver Information",
    "86": "Information to Account Owner",
}

# MT field tag standards: tag → (fin_format, min_length, max_length, description)
MT_TAG_STANDARDS = {
    "20":  ("16x",        1,  16,  "Transaction Reference Number"),
    "21":  ("16x",        1,  16,  "Related Reference"),
    "23B": ("4!a",        4,  4,   "Bank Operation Code"),
    "23E": ("4!a[/30x]", 4,  35,  "Instruction Code"),
    "25":  ("35x",        1,  35,  "Account Identification"),
    "28C": ("5n/2n",      1,  8,   "Statement Number / Sequence Number"),
    "32A": ("6!n3!a15d",  14, 24,  "Value Date / Currency / Interbank Settled Amount"),
    "33B": ("3!a15d",     5,  18,  "Currency / Instructed Amount"),
    "50K": ("34x",        1,  35,  "Ordering Customer (Name/Address)"),
    "50A": ("34x",        1,  35,  "Ordering Customer (BIC)"),
    "52A": ("34x",        1,  35,  "Ordering Institution (BIC)"),
    "56A": ("34x",        1,  35,  "Intermediary Institution (BIC)"),
    "57A": ("34x",        1,  35,  "Account With Institution (BIC)"),
    "58A": ("34x",        1,  35,  "Beneficiary Institution (BIC)"),
    "59":  ("34x",        1,  35,  "Beneficiary Customer"),
    "59A": ("34x",        1,  35,  "Beneficiary Customer (BIC)"),
    "60F": ("1!a6!n3!a15d", 14, 25, "Opening Balance (D/C + Date + Currency + Amount)"),
    "60M": ("1!a6!n3!a15d", 14, 25, "Intermediate Opening Balance"),
    "61":  ("6!n[4!n]2a15d[//16x][34x]", 10, 65, "Statement Line"),
    "62F": ("1!a6!n3!a15d", 14, 25, "Closing Balance (D/C + Date + Currency + Amount)"),
    "62M": ("1!a6!n3!a15d", 14, 25, "Intermediate Closing Balance"),
    "70":  ("35x",        1,  140, "Remittance Information"),
    "71A": ("3!a",        3,  3,   "Details of Charges (SHA/OUR/BEN)"),
    "72":  ("6*35x",      1,  210, "Sender to Receiver Information"),
    "86":  ("65x",        1,  390, "Information to Account Owner"),
    "21":  ("16x",        1,  16,  "Related Reference"),
}

# Sub-field standards
SUB_FIELD_STANDARDS = {
    "Date":          ("6!n",  6,  6,  "DATE",    "Date in YYMMDD format"),
    "Currency":      ("3!a",  3,  3,  "STRING",  "ISO 4217 Currency Code"),
    "Amount":        ("15d",  1,  15, "DECIMAL", "Amount with comma as decimal separator"),
    "DebitCredit":   ("1!a",  1,  1,  "STRING",  "D=Debit, C=Credit"),
    "Account":       ("34x",  1,  34, "STRING",  "Account Number"),
    "Name":          ("35x",  1,  35, "STRING",  "Name"),
    "Address":       ("35x",  1,  35, "STRING",  "Address Line"),
    "BIC":           ("11!a", 8,  11, "STRING",  "BIC/SWIFT Code"),
    "StatementNumber":("5!n", 1,  5,  "INTEGER", "Statement Number"),
    "SequenceNumber": ("2!n", 1,  2,  "INTEGER", "Sequence Number"),
    "ValueDate":     ("6!n",  6,  6,  "DATE",    "Value Date YYMMDD"),
    "Reference":     ("16x",  1,  16, "STRING",  "Reference"),
    "Value":         ("35x",  1,  35, "STRING",  "Value"),
}


class ElementCreate(BaseModel):
    name: str
    element_type: Optional[str] = "STRING"
    field_tag: Optional[str] = None
    fin_format: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_occurs: Optional[int] = 1
    max_occurs: Optional[int] = None
    mandatory: Optional[bool] = True
    pattern: Optional[str] = None
    precision: Optional[int] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    separator: Optional[str] = None
    mandatory_separator: Optional[bool] = False
    description: Optional[str] = None
    example_value: Optional[str] = None
    parent_id: Optional[int] = None
    position: Optional[int] = 0


class ElementResponse(BaseModel):
    id: int
    message_description_id: int
    parent_id: Optional[int] = None
    name: str
    element_type: Optional[str] = None
    field_tag: Optional[str] = None
    fin_format: Optional[str] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_occurs: Optional[int] = None
    max_occurs: Optional[int] = None
    mandatory: Optional[bool] = None
    pattern: Optional[str] = None
    precision: Optional[int] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    separator: Optional[str] = None
    mandatory_separator: Optional[bool] = None
    description: Optional[str] = None
    example_value: Optional[str] = None
    position: Optional[int] = None
    children: List['ElementResponse'] = []

    class Config:
        from_attributes = True

ElementResponse.model_rebuild()


def sort_elements(elements):
    """Recursively sort elements and their children by position."""
    for el in elements:
        if el.children:
            el.children.sort(key=lambda x: x.position or 0)
            sort_elements(el.children)
    return sorted(elements, key=lambda x: x.position or 0)


@router.get("/message-descriptions/{md_id}/elements", response_model=List[ElementResponse])
async def get_elements(
    md_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    elements = db.query(MessageDescriptionElement).filter(
        MessageDescriptionElement.message_description_id == md_id,
        MessageDescriptionElement.parent_id == None
    ).order_by(MessageDescriptionElement.position).all()
    return sort_elements(elements)


@router.post("/message-descriptions/{md_id}/elements", response_model=ElementResponse)
async def create_element(
    md_id: int,
    data: ElementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    element = MessageDescriptionElement(
        message_description_id=md_id,
        **data.dict()
    )
    db.add(element)
    db.commit()
    db.refresh(element)
    return element


@router.put("/message-descriptions/{md_id}/elements/{element_id}", response_model=ElementResponse)
async def update_element(
    md_id: int,
    element_id: int,
    data: ElementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    element = db.query(MessageDescriptionElement).filter(
        MessageDescriptionElement.id == element_id,
        MessageDescriptionElement.message_description_id == md_id
    ).first()
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    for key, value in data.dict(exclude_none=True).items():
        setattr(element, key, value)
    db.commit()
    db.refresh(element)
    return element


@router.delete("/message-descriptions/{md_id}/elements/{element_id}")
async def delete_element(
    md_id: int,
    element_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    element = db.query(MessageDescriptionElement).filter(
        MessageDescriptionElement.id == element_id,
        MessageDescriptionElement.message_description_id == md_id
    ).first()
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    db.delete(element)
    db.commit()
    return {"message": "Element deleted"}


@router.post("/message-descriptions/{md_id}/elements/import-from-columns")
async def import_from_columns(
    md_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.message_description import MessageDescription
    md = db.query(MessageDescription).filter(
        MessageDescription.id == md_id,
        MessageDescription.user_id == current_user.id
    ).first()
    if not md:
        raise HTTPException(status_code=404, detail="MessageDescription not found")
    if not md.column_structure:
        raise HTTPException(status_code=400, detail="No column_structure found")

    db.query(MessageDescriptionElement).filter(
        MessageDescriptionElement.message_description_id == md_id
    ).delete()

    type_map = {
        "STRING": "STRING", "STR": "STRING", "VARCHAR": "STRING", "TEXT": "STRING",
        "INTEGER": "INTEGER", "INT": "INTEGER", "NUMBER": "INTEGER",
        "FLOAT": "DECIMAL", "DECIMAL": "DECIMAL", "DOUBLE": "DECIMAL",
        "DATE": "DATE", "DATETIME": "DATE", "TIMESTAMP": "DATE",
        "BOOLEAN": "BOOLEAN", "BOOL": "BOOLEAN",
        "OBJECT": "COMPOSITE", "DICT": "COMPOSITE", "ARRAY": "COMPOSITE",
    }

    created = 0
    for i, col in enumerate(md.column_structure):
        col_type = str(col.get("type", "STRING")).upper()
        element_type = type_map.get(col_type, "STRING")

        example = None
        if md.sample_data and len(md.sample_data) > 0:
            first_row = md.sample_data[0]
            if isinstance(first_row, dict):
                val = first_row.get(col.get("name", ""))
                if val is not None:
                    example = str(val)[:200]

        element = MessageDescriptionElement(
            message_description_id=md_id,
            parent_id=None,
            name=col.get("name", f"field_{i}"),
            element_type=element_type,
            field_tag=None,
            fin_format=col.get("format"),
            mandatory=True,
            example_value=example,
            position=i
        )
        db.add(element)
        created += 1

    db.commit()
    return {"message": f"Imported {created} elements from column structure", "count": created}


@router.post("/message-descriptions/{md_id}/elements/import-from-blocks")
async def import_from_mt_blocks(
    md_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from app.models.message_description import MessageDescription
    md = db.query(MessageDescription).filter(
        MessageDescription.id == md_id,
        MessageDescription.user_id == current_user.id
    ).first()
    if not md:
        raise HTTPException(status_code=404, detail="MessageDescription not found")
    if not md.mt_blocks:
        raise HTTPException(status_code=400, detail="No MT blocks found")

    # Delete existing elements
    db.query(MessageDescriptionElement).filter(
        MessageDescriptionElement.message_description_id == md_id
    ).delete()

    created = 0

    # SWIFT standard field order
    BLOCK1_ORDER = ["ApplicationIdentifier", "ServiceIdentifier", "LogicalTerminalAddress", "SessionNumber", "SequenceNumber"]
    BLOCK2_ORDER = ["InputOutputIdentifier", "MessageType", "DestinationAddress", "Priority", "DeliveryMonitoring", "ObsolescencePeriod", "InputTime", "InputDate", "OutputDate", "OutputTime"]

    def sort_sub_fields(sub_fields, order_list):
        """Sort sub_fields dict according to a predefined order list."""
        ordered = {}
        # First add fields in predefined order
        for key in order_list:
            if key in sub_fields:
                ordered[key] = sub_fields[key]
        # Then add remaining fields not in order list
        for key, val in sub_fields.items():
            if key not in ordered:
                ordered[key] = val
        return ordered

    def get_clean_tag(tag):
        """Remove index suffix: :61_1 → :61, 61_1 → 61"""
        import re
        return re.sub(r'_\d+$', '', tag)

    # Collect all elements first, then bulk insert with correct positions
    all_elements = []

    def collect_elements(name, tag, block, parent_idx, position, depth=0):
        raw_tag = tag.strip(':').strip('{}').strip()
        clean_tag = re.sub(r'_\d+$', '', raw_tag)  # remove _1, _2 suffix
        tag_std = MT_TAG_STANDARDS.get(clean_tag)
        block_type = block.get("type", "string")
        sub_fields = block.get("sub_fields", {})

        element_type = "COMPOSITE" if (block_type == "map" or sub_fields) else "STRING"
        fin_format = block.get("format")
        min_length = None
        max_length = None
        description = block.get("name", name)

        if tag_std:
            fin_format = fin_format or tag_std[0]
            min_length = tag_std[1]
            max_length = tag_std[2]
            description = tag_std[3]

        sub_std = SUB_FIELD_STANDARDS.get(name) or SWIFT_FIELD_STANDARDS.get(name)
        if sub_std and not tag_std:
            fin_format = fin_format or sub_std[0]
            min_length = sub_std[1]
            max_length = sub_std[2]
            element_type = sub_std[3] if len(sub_std) > 3 else element_type
            description = sub_std[4] if len(sub_std) > 4 else description

        example = str(block.get("value", ""))[:200] if block.get("value") else None

        my_idx = len(all_elements)
        all_elements.append({
            "name": name,
            # Block containers (block1..block5, depth 0) always keep their tag
            # so generate_mapping_elements can find "block4" by field_tag.
            # Nested elements only keep theirs when it's a real SWIFT field tag
            # (":57A", ":32A"...) — composite sub-components like "Date" or
            # "ApplicationIdentifier" are not independent tags and stay
            # untagged. Without this, every business field nested under
            # block4 (i.e. every SWIFT field in a .txt upload) lost its
            # field_tag entirely, forcing Mapping's resolve_tag() to guess
            # from the display name via an incomplete name_to_tag dict —
            # fields missing from that dict (e.g. "Account With Institution")
            # silently failed to map even when RAG data existed for them.
            # A dotted, colon-free tag (e.g. "CdtTrfTxInf.Dbtr.Nm") is the
            # XML-direction equivalent — extract_xml_source_fields() already
            # flattens the whole XML tree into these as dict keys, so real
            # SWIFT tags (":57A") and XML paths never collide.
            "tag": tag if (depth == 0 or tag.startswith(':') or '.' in tag) else None,
            "element_type": element_type,
            "fin_format": fin_format,
            "min_length": min_length,
            "max_length": max_length,
            "mandatory": block.get("mandatory", True),
            "description": description if description != name else None,
            "example_value": example,
            "position": int(position),
            "parent_idx": parent_idx,  # index in all_elements, not DB id
        })

        if sub_fields:
            # Apply standard ordering for known block types
            # Use stored order if available, then standard order, then dict order
            sub_fields_order = block.get("sub_fields_order", [])
            if sub_fields_order:
                ordered_sub = {k: sub_fields[k] for k in sub_fields_order if k in sub_fields}
                # Add any remaining keys not in order
                for k in sub_fields:
                    if k not in ordered_sub:
                        ordered_sub[k] = sub_fields[k]
            elif name == "block1":
                ordered_sub = sort_sub_fields(sub_fields, BLOCK1_ORDER)
            elif name == "block2":
                ordered_sub = sort_sub_fields(sub_fields, BLOCK2_ORDER)
            else:
                ordered_sub = sub_fields

            for child_pos, (sub_name, sub_field) in enumerate(list(ordered_sub.items())):
                if isinstance(sub_field, dict):
                    display_name = sub_name
                    if sub_name.startswith(":"):
                        clean_sub = re.sub(r'_\d+$', '', sub_name.strip(":"))
                        display_name = MT_TAG_NAMES.get(clean_sub, sub_name)
                    collect_elements(display_name, sub_name, sub_field, my_idx, child_pos, depth+1)

    def get_ordered_sub_fields(block_data, block_name):
        """Get sub_fields in correct order."""
        sf = block_data.get("sub_fields", {})
        order = block_data.get("sub_fields_order", [])
        if order:
            ordered = {k: sf[k] for k in order if k in sf}
            for k in sf:
                if k not in ordered:
                    ordered[k] = sf[k]
            return ordered
        return sf

    # Collect all
    for position, (tag, block) in enumerate(md.mt_blocks.items()):
        name = block.get("name", tag)
        if tag.startswith(":"):
            # Strip index suffix for name lookup: :61_1 → 61
            clean = re.sub(r'_\d+$', '', tag.strip(":"))
            name = MT_TAG_NAMES.get(clean, block.get("name", tag))
        collect_elements(name, tag, block, None, position)

    # Insert one by one in order, tracking DB ids
    db_ids = {}
    created = 0
    for idx, elem_data in enumerate(all_elements):
        parent_idx = elem_data["parent_idx"]
        parent_id = db_ids[parent_idx] if parent_idx is not None else None

        elem = MessageDescriptionElement(
            message_description_id=md_id,
            parent_id=parent_id,
            name=elem_data["name"],
            field_tag=elem_data["tag"],
            element_type=elem_data["element_type"],
            fin_format=elem_data["fin_format"],
            min_length=elem_data["min_length"],
            max_length=elem_data["max_length"],
            mandatory=elem_data["mandatory"],
            description=elem_data["description"],
            example_value=elem_data["example_value"],
            position=elem_data["position"],
        )
        db.add(elem)
        db.flush()
        db_ids[idx] = elem.id
        created += 1

    db.commit()
    return {"message": f"Imported {created} elements with SWIFT standards", "count": created}