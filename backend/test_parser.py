from pathlib import Path
import xml.etree.ElementTree as ET

# Test 1: Vérifie les fichiers
mappings_dir = Path("dataset/mappings")
print(f"📁 Checking directory: {mappings_dir.absolute()}")
print(f"✅ Exists: {mappings_dir.exists()}")

xml_files = list(mappings_dir.glob("*.xml"))
print(f"\n📄 Found {len(xml_files)} XML files:")
for f in xml_files:
    print(f"  - {f.name}")

# Test 2: Parse un fichier
if xml_files:
    test_file = xml_files[0]
    print(f"\n🔍 Testing parse of: {test_file.name}")
    try:
        tree = ET.parse(test_file)
        root = tree.getroot()
        print(f"✅ Root tag: {root.tag}")
        print(f"✅ Namespace: {root.attrib}")
    except Exception as e:
        print(f"❌ Error: {e}")