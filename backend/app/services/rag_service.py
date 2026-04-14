"""
RAG Service - Compatibility wrapper for qdrant_manager
Provides backward compatibility while using Qdrant instead of ChromaDB
"""
import logging
from typing import List, Dict, Any, Optional
from app.services.qdrant_manager import qdrant_manager

logger = logging.getLogger(__name__)


class RAGService:
    """
    Service pour interagir avec Qdrant (RAG - Retrieval Augmented Generation)
    Wrapper around qdrant_manager for backward compatibility
    """
    
    def __init__(self):
        self.manager = qdrant_manager
        logger.info("✅ RAG Service initialized (using Qdrant)")
    
    def _is_available(self) -> bool:
        """Check if RAG service is available"""
        return self.manager.collection is not None
    
    def query(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Query the RAG system with semantic search"""
        if not self._is_available():
            logger.debug("RAG not available")
            return None

        try:
            results = self.manager.search(
                query=query,
                n_results=n_results,
                filter_metadata=filter_metadata
            )
            
            if results:
                logger.info(f"Query returned {len(results.get('ids', [[]])[0])} results")
            
            return results
        except Exception as e:
            logger.error(f"Query failed: {e}")
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get RAG statistics"""
        if not self._is_available():
            return {"total_chunks": 0, "status": "unavailable"}

        try:
            return self.manager.get_collection_stats()
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {"total_chunks": 0, "status": "error"}
    
    def search_similar_mappings(
        self,
        source_column: str,
        target_column: str,
        business_domain: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Recherche des mappings similaires"""
        query_text = f"Mapping from {source_column} to {target_column}"
        if business_domain:
            query_text += f" in {business_domain} domain"
        
        results = self.query(query_text, n_results)
        if not results:
            return []
        
        similar_mappings = []
        if results.get('metadatas') and len(results['metadatas']) > 0:
            metadatas = results['metadatas'][0]
            distances = results.get('distances', [[]])[0]

            for i, meta in enumerate(metadatas):
                similar_mappings.append({
                    "source_column": meta.get('source_field'),
                    "target_column": meta.get('target_field'),
                    "transformation_type": meta.get('formula_type'),
                    "mapping_id": meta.get('mapping_id'),
                    "similarity_score": 1 - distances[i] if i < len(distances) else 0.0
                })
        
        return similar_mappings


# Singleton instance
rag_service = RAGService()