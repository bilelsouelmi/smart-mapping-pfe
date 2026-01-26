import chromadb
import logging
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    Service pour interagir avec ChromaDB (RAG - Retrieval Augmented Generation)
    """
    
    def __init__(self):
        self.client = None
        self.collection = None
        
        try:
            # Connect to ChromaDB
            self.client = chromadb.HttpClient(
                host=settings.CHROMADB_HOST,
                port=settings.CHROMADB_PORT
            )
            
            # Get or create collection for mappings
            self.collection = self.client.get_or_create_collection(
                name="mapping_knowledge_base",
                metadata={"description": "Store successful mapping formulas for RAG"}
            )
            
            logger.info("✅ RAG Service initialized successfully")
            
        except Exception as e:
            logger.warning(f"⚠️  RAG Service initialization failed: {e}")
            logger.warning("⚠️  RAG Service will operate in degraded mode (no similarity search)")
    
    def _is_available(self) -> bool:
        """Check if RAG service is available"""
        return self.client is not None and self.collection is not None
    
    def add_mapping(
        self,
        mapping_id: str,
        source_column: str,
        target_column: str,
        transformation_type: str,
        transformation_rule: str,
        business_domain: Optional[str] = None,
        success_rate: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Ajoute un mapping dans la knowledge base
        """
        if not self._is_available():
            logger.debug("RAG not available, skipping add_mapping")
            return False
            
        try:
            # Create document text for embedding
            document = f"""
Mapping: {source_column} → {target_column}
Type: {transformation_type}
Rule: {transformation_rule}
Domain: {business_domain or 'General'}
Success Rate: {success_rate:.2%}
"""
            
            # Prepare metadata
            meta = {
                "source_column": source_column,
                "target_column": target_column,
                "transformation_type": transformation_type,
                "business_domain": business_domain or "general",
                "success_rate": success_rate,
            }
            
            if metadata:
                meta.update(metadata)
            
            # Add to ChromaDB
            self.collection.add(
                documents=[document],
                metadatas=[meta],
                ids=[mapping_id]
            )
            
            logger.info(f"Mapping {mapping_id} added to knowledge base")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add mapping: {e}")
            return False
    
    def search_similar_mappings(
        self,
        source_column: str,
        target_column: str,
        business_domain: Optional[str] = None,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recherche des mappings similaires dans la knowledge base
        """
        if not self._is_available():
            logger.debug("RAG not available, returning empty results")
            return []
            
        try:
            # Create query text
            query = f"Mapping from {source_column} to {target_column}"
            if business_domain:
                query += f" in {business_domain} domain"
            
            # Search in ChromaDB
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"business_domain": business_domain} if business_domain else None
            )
            
            # Format results
            similar_mappings = []
            
            if results and results.get('metadatas') and len(results['metadatas']) > 0:
                metadatas = results['metadatas'][0]
                distances = results.get('distances', [[]])[0]
                
                for i, meta in enumerate(metadatas):
                    similar_mappings.append({
                        "source_column": meta.get('source_column'),
                        "target_column": meta.get('target_column'),
                        "transformation_type": meta.get('transformation_type'),
                        "business_domain": meta.get('business_domain'),
                        "success_rate": meta.get('success_rate', 0.0),
                        "similarity_score": 1 - distances[i] if i < len(distances) else 0.0
                    })
            
            logger.info(f"Found {len(similar_mappings)} similar mappings")
            return similar_mappings
            
        except Exception as e:
            logger.error(f"Failed to search similar mappings: {e}")
            return []
    
    def update_mapping_success_rate(
        self,
        mapping_id: str,
        new_success_rate: float
    ) -> bool:
        """
        Met à jour le taux de succès d'un mapping
        """
        if not self._is_available():
            logger.debug("RAG not available, skipping update")
            return False
            
        try:
            # Get existing mapping
            result = self.collection.get(ids=[mapping_id])
            
            if not result or not result.get('metadatas'):
                logger.warning(f"Mapping {mapping_id} not found")
                return False
            
            # Update metadata
            metadata = result['metadatas'][0]
            metadata['success_rate'] = new_success_rate
            
            # Update in ChromaDB
            self.collection.update(
                ids=[mapping_id],
                metadatas=[metadata]
            )
            
            logger.info(f"Updated success rate for mapping {mapping_id}: {new_success_rate:.2%}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update mapping success rate: {e}")
            return False
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Récupère les statistiques de la collection
        """
        if not self._is_available():
            return {
                "total_mappings": 0,
                "status": "unavailable",
                "error": "ChromaDB not connected"
            }
            
        try:
            count = self.collection.count()
            
            return {
                "total_mappings": count,
                "collection_name": self.collection.name,
                "status": "available"
            }
            
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"total_mappings": 0, "status": "error", "error": str(e)}