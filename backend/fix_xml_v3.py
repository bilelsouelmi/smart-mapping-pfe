from pathlib import Path
import re
import xml.etree.ElementTree as ET

def fix_xml_special_chars(filepath):
    """Fix < and > characters in XML text content"""
    print(f"Fixing {filepath.name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Backup
    backup_path = filepath.with_suffix('.xml.bak3')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    fixes = 0
    
    # Fix specific patterns we found:
    
    # 1. Fix "< 35" -> "&lt; 35" in text
    original = content
    content = re.sub(r'(<[^<>]+>)([^<>]*?)(<)(\s*\d+)([^<>]*?)(</[^<>]+>)', r'\1\2&lt;\4\5\6', content)
    if content != original:
        fixes += 1
    
    # 2. Fix "<5%" in attributes
    original = content
    content = content.replace('target="<', 'target="&lt;')
    content = content.replace("target='<", "target='&lt;")
    if content != original:
        fixes += 1
    
    # 3. Fix "IF ... < ... THEN" patterns
    original = content
    content = re.sub(r'(IF [^<>]+?)(<)([^<>]+?THEN)', r'\1&lt;\3', content)
    if content != original:
        fixes += 1
    
    # Write fixed
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Applied {fixes} fix patterns")
    
    # Verify
    try:
        ET.parse(filepath)
        print(f"  ✅ XML is now valid!")
        return True
    except ET.ParseError as e:
        print(f"  ❌ Still has errors: {e}")
        return False

# Fix all files except the one that's already valid
mappings_dir = Path("dataset/mappings")
xml_files = [f for f in mappings_dir.glob("*.xml") if f.name != "MT202_to_MT500.xml"]

success = 0
for xml_file in xml_files:
    if fix_xml_special_chars(xml_file):
        success += 1

print(f"\n✅ Fixed: {success} files")
print(f"✅ Already valid: 1 file (MT202_to_MT500.xml)")
print(f"✅ Total valid: {success + 1} files")