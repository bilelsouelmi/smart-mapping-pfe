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
    qdrant_manager.reset_collection()
    print("✅ Collection reset")
    
    # Parse XML mappings
    dataset_dir = os.path.join(os.path.dirname(__file__), '../dataset/mappings')
    print(f"📖 Parsing XML mappings from {dataset_dir}...")
    
    try:
        # Create parser instance
        parser = XMLMappingParser(dataset_dir)
        
        # Load all mappings (correct method name!)
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
        
        # Show mapping IDs
        print(f"  Mapping IDs: {list(mappings.keys())}")
        
        # Chunk mappings
        print("\n✂️ Chunking mappings...")
        chunks = xml_chunker.chunk_all_mappings(mappings)
        print(f"✅ Created {len(chunks)} chunks")
        
        if not chunks:
            print("⚠️ No chunks created!")
            return
        
        # Show sample chunks with source/target
        print("\n📋 Sample chunks (checking source/target):")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n  Chunk {i+1}:")
            print(f"    ID: {chunk.chunk_id}")
            print(f"    Type: {chunk.chunk_type}")
            print(f"    Source: {chunk.metadata.get('source')}")
            print(f"    Target: {chunk.metadata.get('target')}")
        
        # Index to Qdrant
        print("\n📤 Uploading chunks to Qdrant...")
        result = qdrant_manager.add_chunks(chunks)
        
        if result:
            print(f"✅ Successfully indexed {len(chunks)} chunks!")
        else:
            print("❌ Failed to index chunks")
            return
        
        # Verify
        stats = qdrant_manager.get_collection_stats()
        print(f"\n📊 Collection Statistics:")
        print(f"  Total chunks: {stats.get('total_chunks', 0)}")
        print(f"  Collection: {stats.get('collection_name', 'N/A')}")
        print(f"  Status: {stats.get('status', 'N/A')}")
        
        if 'chunk_types' in stats:
            print(f"\n  Chunk types breakdown:")
            for chunk_type, count in stats['chunk_types'].items():
                print(f"    - {chunk_type}: {count}")
        
        print("\n✅ Indexation complete!")
        print(f"\n🌐 Check Qdrant UI: http://localhost:6333/dashboard")
        print(f"   Look for 'source' and 'target' fields in the payload!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()