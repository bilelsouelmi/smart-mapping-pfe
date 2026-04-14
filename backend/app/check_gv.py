import sys
sys.path.insert(0, '/app')
from app.services.xml_mapping_parser import XMLMappingParser

parser = XMLMappingParser('/app/dataset/mappings')
mappings = parser.load_all_mappings()
print(f"Total mappings: {len(mappings)}")
for mid, m in mappings.items():
    gv = m.get('general_information', {}).get('global_variables', {})
    print(f"  {mid}: {len(gv)} GlobalVariables")