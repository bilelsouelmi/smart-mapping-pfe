import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.qdrant_manager import qdrant_manager
from app.services.xml_chunker import xml_chunker
from app.services.xml_mapping_parser import XMLMappingParser

def main():
    print("🚀 Starting Qdrant indexation...")
    
    # Reset collection
    print("🔄 Resetting Qdrant collection...")
    qdrant_manager.initialize_collection(reset=True)
    print("✅ Collection reset")
    
    # Parse XML mappings
    dataset_dir = os.path.join(os.path.dirname(__file__), '../dataset/mappings')
    print(f"📖 Parsing XML mappings from {dataset_dir}...")
    
    try:
        # Create fresh parser instance (no cache)
        parser = XMLMappingParser(dataset_dir)
        mappings = parser.load_all_mappings()
        
        if not mappings:
            print("⚠️ No mappings found!")
            print(f"Directory: {dataset_dir}")
            print(f"Directory exists: {os.path.exists(dataset_dir)}")
            if os.path.exists(dataset_dir):
                files = os.listdir(dataset_dir)
                print(f"Files in directory: {files}")
            return
            
        print(f"✅ Parsed {len(mappings)} mappings")
        print(f"  Mapping IDs: {list(mappings.keys())}")
        
        # Chunk mappings
        print("\n✂️ Chunking mappings...")
        chunks = xml_chunker.chunk_all_mappings(mappings)
        print(f"✅ Created {len(chunks)} chunks")
        
        if not chunks:
            print("⚠️ No chunks created!")
            return

        # ── Vérification détaillée par mapping ──────────────────────────────
        print("\n📋 Chunks par mapping:")
        by_mapping = {}
        by_type_total = {}
        for chunk in chunks:
            mid = chunk.metadata.get('mapping_id', 'UNKNOWN')
            ct = chunk.chunk_type
            if mid not in by_mapping:
                by_mapping[mid] = {}
            by_mapping[mid][ct] = by_mapping[mid].get(ct, 0) + 1
            by_type_total[ct] = by_type_total.get(ct, 0) + 1

        for mid, types in by_mapping.items():
            print(f"  {mid}: {sum(types.values())} chunks")
            for ct, count in types.items():
                print(f"    - {ct}: {count}")

        print(f"\n📊 Total par type:")
        for ct, count in sorted(by_type_total.items()):
            print(f"  - {ct}: {count}")
        # ── Fin vérification ─────────────────────────────────────────────────

        # Index to Qdrant
        print("\n📤 Uploading chunks to Qdrant...")
        result = qdrant_manager.add_chunks(chunks)
        
        if result:
            print(f"✅ Successfully indexed {len(chunks)} chunks!")
        else:
            print("❌ Failed to index chunks")
            return
        
        # Verify with full scroll
        stats = qdrant_manager.get_collection_stats()
        print(f"\n📊 Collection Statistics (Qdrant):")
        print(f"  Total chunks: {stats.get('total_chunks', 0)}")
        print(f"  Collection: {stats.get('collection_name', 'N/A')}")
        print(f"  Status: {stats.get('status', 'N/A')}")
        
        if 'chunk_types' in stats:
            print(f"\n  Chunk types breakdown:")
            for chunk_type, count in sorted(stats['chunk_types'].items()):
                print(f"    - {chunk_type}: {count}")
        
        print("\n✅ Indexation complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()