"""
RAG Initializer
Loads XML mappings and populates ChromaDB
"""

import logging
from typing import Dict, Any
from app.services.xml_mapping_parser import xml_parser
from app.services.xml_chunker import xml_chunker
from app.services.qdrant_manager import qdrant_manager as chromadb_manager
from app.services.embeddings_service import embeddings_service

logger = logging.getLogger(__name__)


class RAGInitializer:
    """
    Initializes the RAG system by loading XML mappings into ChromaDB
    """
    
    def __init__(self):
        self.initialized = False
    
    def initialize(self, reset: bool = False) -> Dict[str, Any]:
        """
        Initialize the RAG system
        
        Args:
            reset: If True, reset ChromaDB collection before loading
            
        Returns:
            Dictionary with initialization results
        """
        logger.info("🚀 Starting RAG system initialization...")
        
        results = {
            "success": False,
            "steps": {},
            "errors": []
        }
        
        try:
            # Step 1: Test Embeddings Service
            logger.info("Step 1: Testing embeddings service...")
            if not embeddings_service.test_connection():
                results["errors"].append("Embeddings service not available")
                return results
            results["steps"]["embeddings"] = "✅ Connected"
            
            # Step 2: Initialize ChromaDB
            logger.info("Step 2: Initializing ChromaDB...")
            if not chromadb_manager.initialize_collection(reset=reset):
                results["errors"].append("Failed to initialize ChromaDB")
                return results
            results["steps"]["chromadb"] = "✅ Initialized"
            
            # Step 3: Load XML Mappings
            logger.info("Step 3: Loading XML mappings...")
            mappings = xml_parser.load_all_mappings()
            if not mappings or len(mappings) == 0:
                logger.error(f"No XML mappings loaded! Mappings dict: {mappings}")
                results["errors"].append("No XML mappings found")
                return results
            results["steps"]["xml_loading"] = f"✅ Loaded {len(mappings)} mappings"
            
            # Step 4: Chunk Mappings
            logger.info("Step 4: Chunking mappings...")
            all_chunks = xml_chunker.chunk_all_mappings(mappings)
            if not all_chunks:
                results["errors"].append("Failed to chunk mappings")
                return results
            results["steps"]["chunking"] = f"✅ Created {len(all_chunks)} chunks"
            
            # Step 5: Add to ChromaDB
            logger.info("Step 5: Adding chunks to ChromaDB...")
            if not chromadb_manager.add_chunks(all_chunks):
                results["errors"].append("Failed to add chunks to ChromaDB")
                return results
            results["steps"]["chromadb_population"] = f"✅ Added {len(all_chunks)} chunks"
            
            # Step 6: Verify
            logger.info("Step 6: Verifying...")
            stats = chromadb_manager.get_collection_stats()
            results["steps"]["verification"] = f"✅ {stats['total_chunks']} chunks in DB"
            results["stats"] = stats
            
            results["success"] = True
            self.initialized = True
            logger.info("🎉 RAG system initialized successfully!")
            
        except Exception as e:
            logger.error(f"❌ RAG initialization failed: {str(e)}")
            results["errors"].append(str(e))
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get current status of RAG system
        
        Returns:
            Dictionary with system status
        """
        return {
            "initialized": self.initialized,
            "embeddings_available": embeddings_service.test_connection(),
            "chromadb_stats": chromadb_manager.get_collection_stats()
        }


# Singleton instance
rag_initializer = RAGInitializer()