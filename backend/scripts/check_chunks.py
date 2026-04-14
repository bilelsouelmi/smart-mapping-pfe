import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.xml_mapping_parser import XMLMappingParser
from app.services.xml_chunker import xml_chunker

dataset_dir = os.path.join(os.path.dirname(__file__), '../dataset/mappings')
parser = XMLMappingParser(dataset_dir)
mappings = parser.load_all_mappings()

for mid, m in mappings.items():
    chunks = xml_chunker.chunk_mapping(m)
    by_type = {}
    for c in chunks:
        by_type[c.chunk_type] = by_type.get(c.chunk_type, 0) + 1
    print(f"\n{mid}: {len(chunks)} chunks total")
    for t, count in by_type.items():
        print(f"  {t}: {count}")