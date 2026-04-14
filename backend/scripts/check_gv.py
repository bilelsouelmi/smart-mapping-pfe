import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.xml_mapping_parser import XMLMappingParser

dataset_dir = os.path.join(os.path.dirname(__file__), '../dataset/mappings')
parser = XMLMappingParser(dataset_dir)
mappings = parser.load_all_mappings()

print(f"Total mappings: {len(mappings)}")
for mid, m in mappings.items():
    gv = m.get('general_information', {}).get('global_variables', {})
    print(f"  {mid}: {len(gv)} GlobalVariables")