from pathlib import Path
import xml.etree.ElementTree as ET

def fix_xml_with_cdata(filepath):
    """Wrap text content in CDATA if it contains special chars"""
    print(f"Fixing {filepath.name}...")
    
    # Backup
    backup_path = filepath.with_suffix('.xml.bak2')
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Backup: {backup_path.name}")
    
    try:
        # Try to parse
        tree = ET.parse(filepath)
        print(f"  ✅ XML is valid!")
        return True
    except ET.ParseError as e:
        print(f"  ❌ Parse error: {e}")
        
        # Read as text and try to fix
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        error_line = e.position[0] - 1
        error_col = e.position[1]
        
        if error_line < len(lines):
            problem_line = lines[error_line]
            print(f"  Problem line {error_line + 1}: {problem_line.strip()[:100]}...")
            
            # Simple fix: escape < and >
            fixed_line = problem_line.replace('<', '&lt;').replace('>', '&gt;')
            # But not in tags
            if '<' in problem_line and '>' in problem_line:
                # This is complex, skip for now
                print(f"  ⚠️ Manual fix needed at line {error_line + 1}")
                return False
        
        return False

# Fix all files
mappings_dir = Path("dataset/mappings")
xml_files = list(mappings_dir.glob("*.xml"))

success = 0
failed = 0

for xml_file in xml_files:
    if fix_xml_with_cdata(xml_file):
        success += 1
    else:
        failed += 1

print(f"\n✅ Valid: {success}")
print(f"❌ Need manual fix: {failed}")