"""
Qdrant Manager
Manages vector database for RAG system
"""

import logging
import uuid
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any, Optional
from datetime import datetime
from app.config import settings
from app.services.embeddings_service import embeddings_service
from app.services.xml_chunker import XMLChunk

logger = logging.getLogger(__name__)


class QdrantManager:
    """
    Manager for Qdrant vector database
    Handles storage and retrieval of XML mapping chunks
    """
    
    def __init__(
        self,
        host: str = None,
        port: int = None,
        collection_name: str = "xml_mappings_v2"
    ):
        self.host = host or settings.QDRANT_HOST
        self.port = port or settings.QDRANT_PORT
        self.collection_name = collection_name
        self.collection = None
        
        # Initialize Qdrant client
        logger.info(f"Initializing Qdrant client at {self.host}:{self.port}")
        try:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                timeout=10
            )
            
            # Initialize collection automatically
            self.initialize_collection()
            
        except Exception as e:
            logger.error(f"❌ Qdrant client initialization failed: {e}")
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
                    self.client.delete_collection(collection_name=self.collection_name)
                    logger.info("✅ Deleted existing collection")
                except Exception as e:
                    logger.debug(f"Collection didn't exist: {e}")
            
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_exists = any(c.name == self.collection_name for c in collections)
            
            if not collection_exists:
                # Create collection
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=768,  # nomic-embed-text dimension
                        distance=Distance.COSINE
                    )
                )
                logger.info(f"✅ Created collection: {self.collection_name}")
            
            # Get collection info
            collection_info = self.client.get_collection(self.collection_name)
            count = collection_info.points_count
            
            logger.info(f"✅ Collection '{self.collection_name}' ready ({count} points)")
            self.collection = True  # Mark as initialized
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize collection: {str(e)}")
            return False
    
    def add_chunks(self, chunks: List[XMLChunk]) -> bool:
        """
        Add chunks to Qdrant with embeddings
        
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
            logger.info(f"Adding {len(chunks)} chunks to Qdrant...")
            
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
            
            # Prepare points for Qdrant
            # Deterministic ID derived from chunk_id so re-indexing the same
            # reference XML upserts (replaces) the existing point instead of
            # accumulating a duplicate with stale content alongside it.
            points = []
            for doc, meta, id_, emb in valid_data:
                points.append(
                    PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_DNS, id_)),
                        vector=emb,
                        payload={
                            "content": doc,
                            "chunk_id": id_,
                            **meta  # Unpack metadata into payload
                        }
                    )
                )
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            success_count = len(valid_data)
            total_count = len(chunks)
            logger.info(f"✅ Added {success_count}/{total_count} chunks to Qdrant")
            
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
            Search results in ChromaDB-compatible format
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
            
            # Build filter if provided
            query_filter = None
            if filter_metadata:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                conditions = []
                for key, value in filter_metadata.items():
                    conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )
                if conditions:
                    query_filter = Filter(must=conditions)
            
            # Search in Qdrant
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=n_results,
                query_filter=query_filter
            )
            
            # Convert to ChromaDB-compatible format
            ids = [[]]
            documents = [[]]
            metadatas = [[]]
            distances = [[]]
            
            for hit in results:
                ids[0].append(hit.id)
                documents[0].append(hit.payload.get('content', ''))
                
                # Extract metadata (remove content from payload)
                metadata = {k: v for k, v in hit.payload.items() if k != 'content'}
                metadatas[0].append(metadata)
                
                distances[0].append(hit.score)
            
            logger.info(f"Found {len(results)} results for query")
            
            return {
                'ids': ids,
                'documents': documents,
                'metadatas': metadatas,
                'distances': distances
            }
            
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
            collection_info = self.client.get_collection(self.collection_name)
            count = collection_info.points_count
            
            # ── FIX : scroll ALL points avec pagination ──────────────────────
            # Ancien code : limit=min(count, 100) manquait les points au-delà de 100
            all_points = []
            offset = None

            while True:
                batch, next_offset = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=1000,
                    offset=offset
                )
                all_points.extend(batch)
                if next_offset is None:
                    break
                offset = next_offset
            # ── FIN FIX ────────────────────────────────────────────────────────

            chunk_types = {}
            for point in all_points:
                chunk_type = point.payload.get('chunk_type', 'UNKNOWN')
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
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="mapping_id",
                            match=MatchValue(value=mapping_id)
                        )
                    ]
                )
            )
            logger.info(f"Deleted chunks for mapping: {mapping_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete chunks: {str(e)}")
            return False
    
    def add_user_chunk(
        self,
        field_id: str,
        field_name: str,
        mapping_formula: Dict[str, Any],
        suggestion: Dict[str, Any],
        user_id: int
    ) -> bool:
        """
        Ajoute un chunk utilisateur dans Qdrant (modification manuelle).
        Le chunk original n'est pas supprimé — les deux coexistent.
        Le chunk utilisateur a un chunk_type USER_MAPPING pour priorité.

        Args:
            field_id: ID du champ (ex: transaction_reference)
            field_name: Nom du champ
            mapping_formula: Objet {pseudocode, expression, details: {global_variables, conditions}}
            suggestion: La suggestion complète
            user_id: ID de l'utilisateur

        Returns:
            True si succès
        """
        if not self.collection:
            logger.error("Collection not initialized")
            return False

        try:
            # Construire le contenu textuel du chunk
            pseudocode = mapping_formula.get('pseudocode', '') if mapping_formula else ''
            expression = mapping_formula.get('expression', '') if mapping_formula else ''
            details = mapping_formula.get('details', {}) if mapping_formula else {}
            global_vars = details.get('global_variables', {})
            conditions = details.get('conditions', {})

            content_parts = [
                f"User-defined Mapping: {field_id}",
                f"Field Name: {field_name}",
                f"Target: {suggestion.get('target', '')}",
                f"Element ID: {suggestion.get('element_id', '')}",
                ""
            ]

            if pseudocode:
                content_parts.extend(["Mapping Formula (PseudoCode):", pseudocode, ""])

            if expression:
                content_parts.extend([f"Expression: {expression}", ""])

            if global_vars:
                gv_str = ", ".join([f"{k}={v}" for k, v in global_vars.items()])
                content_parts.append(f"Global Variables Used: {gv_str}")

            if conditions:
                content_parts.extend(["", f"Conditions ({len(conditions)}):"])
                for key, expr in conditions.items():
                    content_parts.append(f"  {key}: {expr}")

            content = "\n".join(content_parts)

            # Chunk ID unique pour cette modification utilisateur
            chunk_id = f"USER_{user_id}_{field_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Metadata du chunk
            metadata = {
                "chunk_type": "USER_MAPPING",
                "chunk_id": chunk_id,
                "field_id": field_id,
                "field_name": field_name,
                "source": field_id,
                "target": suggestion.get('target', ''),
                "element_id": suggestion.get('element_id', ''),
                "mapping_formula": mapping_formula,
                "criticality": suggestion.get('criticality', 'MEDIUM'),
                "user_id": user_id,
                "user_defined": True,
                "created_at": datetime.now().isoformat()
            }

            # Générer embedding
            embedding = embeddings_service.generate_embedding(content)
            if not embedding:
                logger.error("Failed to generate embedding for user chunk")
                return False

            # Upsert dans Qdrant (sans toucher aux chunks existants)
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "content": content,
                    "chunk_id": chunk_id,
                    **metadata
                }
            )

            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            logger.info(f"✅ User chunk added to Qdrant: {chunk_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to add user chunk: {str(e)}")
            return False

    def reset_collection(self) -> bool:
        """
        Reset the entire collection (delete all data)
        
        Returns:
            True if successful
        """
        return self.initialize_collection(reset=True)


# Singleton instance
qdrant_manager = QdrantManager()