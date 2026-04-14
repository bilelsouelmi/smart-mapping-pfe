from pathlib import Path
import re

def fix_xml_file(filepath):
    """Fix common XML issues"""
    print(f"Fixing {filepath.name}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Backup
    backup_path = filepath.with_suffix('.xml.bak')
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"  Backup created: {backup_path.name}")
    
    # Fix common issues
    fixes = 0
    
    # 1. Fix & not in entities
    # Only replace & that are not part of &amp; &lt; &gt; &quot; &apos;
    def replace_ampersand(match):
        nonlocal fixes
        fixes += 1
        return '&amp;'
    
    # Find & not followed by amp; lt; gt; quot; apos; or #
    content = re.sub(r'&(?!(amp;|lt;|gt;|quot;|apos;|#))', replace_ampersand, content)
    
    # 2. Fix < and > in text (simple approach)
    # This is tricky - skipping for now
    
    # Write fixed content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  Fixed {fixes} issues")
    return fixes

# Fix all XML files
mappings_dir = Path("dataset/mappings")
xml_files = list(mappings_dir.glob("*.xml"))

total_fixes = 0
for xml_file in xml_files:
    fixes = fix_xml_file(xml_file)
    total_fixes += fixes

print(f"\n✅ Total fixes: {total_fixes}")
print("🔄 Now restart backend and try again!")