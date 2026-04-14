"""
ChromaDB Manager
Manages vector database for RAG system
"""

import logging
import chromadb
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.services.embeddings_service import embeddings_service
from app.services.xml_chunker import XMLChunk

logger = logging.getLogger(__name__)


class ChromaDBManager:
    """
    Manager for ChromaDB vector database
    Handles storage and retrieval of XML mapping chunks
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = "xml_mappings"
    ):
        self.host = host or settings.CHROMADB_HOST
        self.port = port or settings.CHROMADB_PORT
        self.collection_name = collection_name
        self.collection = None
        
        # Initialize ChromaDB client
        logger.info(f"Initializing ChromaDB client at {self.host}:{self.port}")
        try:
            self.client = chromadb.HttpClient(
                host=self.host,
                port=self.port
            )
            
            # ← AJOUTE CETTE LIGNE : Initialize collection automatically
            self.initialize_collection()
            
        except Exception as e:
            logger.error(f"❌ ChromaDB client initialization failed: {e}")
            self.client = None
    
    def initialize_collection(self, reset: bool = False) -> bool:
        """
        Initialize or get the collection
        
        Args:
            reset: If True, delete existing collection and create new one
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if reset:
                logger.info(f"Resetting collection: {self.collection_name}")
                try:
                    self.client.delete_collection(name=self.collection_name)
                    logger.info("✅ Deleted existing collection")
                except Exception as e:
                    logger.debug(f"Collection didn't exist or couldn't be deleted: {e}")
            
            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "XML Mapping chunks for FinTech conversions",
                    "created_at": datetime.now().isoformat()
                }
            )
            
            count = self.collection.count()
            logger.info(f"✅ Collection '{self.collection_name}' initialized ({count} documents)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize collection: {str(e)}")
            return False
    
    def add_chunks(self, chunks: List[XMLChunk]) -> bool:
        """
        Add chunks to ChromaDB with embeddings
        
        Args:
            chunks: List of XMLChunk objects
            
        Returns:
            True if successful, False otherwise
        """
        if not self.collection:
            logger.error("Collection not initialized")
            return False
        
        if not chunks:
            logger.warning("No chunks to add")
            return True
        
        try:
            logger.info(f"Adding {len(chunks)} chunks to ChromaDB...")
            
            # Prepare data
            documents = []
            metadatas = []
            ids = []
            
            for chunk in chunks:
                documents.append(chunk.content)
                metadatas.append(chunk.metadata)
                ids.append(chunk.chunk_id)
            
            # Generate embeddings
            logger.info("Generating embeddings...")
            embeddings = embeddings_service.generate_embeddings_batch(
                documents,
                show_progress=True
            )
            
            # Filter out failed embeddings
            valid_data = [
                (doc, meta, id_, emb) 
                for doc, meta, id_, emb in zip(documents, metadatas, ids, embeddings)
                if emb is not None
            ]
            
            if not valid_data:
                logger.error("No valid embeddings generated")
                return False
            
            # Unzip valid data
            valid_docs, valid_metas, valid_ids, valid_embs = zip(*valid_data)
            
            # Add to ChromaDB
            self.collection.add(
                documents=list(valid_docs),
                metadatas=list(valid_metas),
                ids=list(valid_ids),
                embeddings=list(valid_embs)
            )
            
            success_count = len(valid_data)
            total_count = len(chunks)
            logger.info(f"✅ Added {success_count}/{total_count} chunks to ChromaDB")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to add chunks: {str(e)}")
            return False
    
    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for relevant chunks using semantic similarity
        
        Args:
            query: Search query text
            n_results: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            Search results with documents, metadatas, distances
        """
        if not self.collection:
            logger.error("Collection not initialized")
            return None
        
        try:
            # Generate query embedding
            query_embedding = embeddings_service.generate_embedding(query)
            
            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return None
            
            # Search
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=filter_metadata
            )
            
            logger.info(f"Found {len(results['ids'][0])} results for query")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            return None
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection
        
        Returns:
            Dictionary with collection statistics
        """
        if not self.collection:
            return {"error": "Collection not initialized"}
        
        try:
            count = self.collection.count()
            
            # Get sample to analyze chunk types
            sample = self.collection.peek(limit=min(count, 100))
            
            chunk_types = {}
            if sample and sample.get('metadatas'):
                for meta in sample['metadatas']:
                    chunk_type = meta.get('chunk_type', 'UNKNOWN')
                    chunk_types[chunk_type] = chunk_types.get(chunk_type, 0) + 1
            
            return {
                "total_chunks": count,
                "collection_name": self.collection_name,
                "chunk_types": chunk_types,
                "status": "healthy"
            }
            
        except Exception as e:
            logger.error(f"Failed to get stats: {str(e)}")
            return {"error": str(e)}
    
    def delete_by_mapping_id(self, mapping_id: str) -> bool:
        """
        Delete all chunks for a specific mapping
        
        Args:
            mapping_id: The mapping ID to delete
            
        Returns:
            True if successful
        """
        if not self.collection:
            logger.error("Collection not initialized")
            return False
        
        try:
            self.collection.delete(
                where={"mapping_id": mapping_id}
            )
            logger.info(f"Deleted chunks for mapping: {mapping_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete chunks: {str(e)}")
            return False
    
    def reset_collection(self) -> bool:
        """
        Reset the entire collection (delete all data)
        
        Returns:
            True if successful
        """
        return self.initialize_collection(reset=True)


# Singleton instance
chromadb_manager = ChromaDBManager()