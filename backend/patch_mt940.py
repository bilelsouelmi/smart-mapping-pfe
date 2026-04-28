import xml.etree.ElementTree as ET

# Target paths for each field tag
TARGET_PATHS = {
    "20":  ("STMT_REF",   "GrpHdr.MsgId"),
    "25":  ("ACCT_IBAN",  "Stmt.Acct.Id.IBAN"),
    "28C": ("STMT_ID",    "Stmt.Id"),
    "60F": ("OPNG_BAL",   "Stmt.Bal.OPBD"),
    "61":  ("STMT_ENTRY", "Stmt.Ntry"),
    "86":  ("TX_DETAILS", "Stmt.Ntry.NtryDtls.TxDtls.RmtInf.Ustrd"),
    "62F": ("CLSG_BAL",   "Stmt.Bal.CLBD"),
    "64":  ("AVAIL_BAL",  "Stmt.Bal.CLAV"),
}

# Read original file
with open('/app/dataset/mappings/MT940_to_camt053.xml', 'r') as f:
    content = f.read()

# Add ElementId and TargetPath to each source Field
for tag, (elem_id, target_path) in TARGET_PATHS.items():
    swift_tag = f":{tag}:"
    # Find the field block and add after ExampleValue or last closing element
    marker = f"<FieldTag>{swift_tag}</FieldTag>"
    if marker not in content:
        print(f"Tag not found: {swift_tag}")
        continue
    # Find the closing </Field> after this marker
    idx = content.index(marker)
    # Find end of this field block
    end_idx = content.index("</Field>", idx)
    # Check if already has ElementId
    field_block = content[idx:end_idx]
    if "<ElementId>" in field_block:
        print(f"Already has ElementId for {swift_tag}")
        continue
    # Insert before </Field>
    insertion = f"        <ElementId>{elem_id}</ElementId>\n        <TargetPath>{target_path}</TargetPath>\n      "
    content = content[:end_idx] + insertion + content[end_idx:]
    print(f"✅ Added {elem_id} -> {target_path} for {swift_tag}")

with open('/app/dataset/mappings/MT940_to_camt053.xml', 'w') as f:
    f.write(content)

print("Done! Total lines:", len(content.splitlines()))