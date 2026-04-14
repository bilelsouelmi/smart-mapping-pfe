import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.xml_mapping_parser import XMLMappingParser

dataset_dir = os.path.join(os.path.dirname(__file__), '../dataset/mappings')
parser = XMLMappingParser(dataset_dir)
mappings = parser.load_all_mappings()

for mid, m in mappings.items():
    field_mappings = m.get('field_mappings', [])
    missing = [fm['id'] for fm in field_mappings if not fm.get('formula_expression')]
    has = [fm['id'] for fm in field_mappings if fm.get('formula_expression')]
    print(f'{mid}:')
    print(f'  Has formula: {len(has)}')
    print(f'  Missing formula: {len(missing)} -> {missing}')