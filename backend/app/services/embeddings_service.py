"""
Embeddings Service
Generates embeddings using Ollama for RAG system
"""

import logging
import requests
from typing import List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingsService:
    """
    Service to generate embeddings using Ollama
    """
    
    def __init__(
        self,
        base_url: str = None,
        model: str = "nomic-embed-text",
        timeout: int = 30
    ):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model
        self.timeout = timeout
        self.embeddings_endpoint = f"{self.base_url}/api/embeddings"
        
        logger.info(f"Initialized EmbeddingsService with model: {self.model}")
    
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector, or None if failed
        """
        try:
            payload = {
                "model": self.model,
                "prompt": text
            }
            
            response = requests.post(
                self.embeddings_endpoint,
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                embedding = result.get('embedding')
                
                if embedding:
                    logger.debug(f"Generated embedding of dimension: {len(embedding)}")
                    return embedding
                else:
                    logger.error("No embedding in response")
                    return None
            else:
                logger.error(f"Embedding request failed: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            logger.error(f"Embedding request timed out after {self.timeout}s")
            return None
        except Exception as e:
            logger.error(f"Error generating embedding: {str(e)}")
            return None
    
    def generate_embeddings_batch(
        self, 
        texts: List[str],
        show_progress: bool = True
    ) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            show_progress: Whether to log progress
            
        Returns:
            List of embeddings (same order as input texts)
        """
        embeddings = []
        total = len(texts)
        
        for i, text in enumerate(texts, 1):
            if show_progress and i % 10 == 0:
                logger.info(f"Generating embeddings: {i}/{total}")
            
            embedding = self.generate_embedding(text)
            embeddings.append(embedding)
        
        # Count successes
        success_count = sum(1 for e in embeddings if e is not None)
        logger.info(f"Generated {success_count}/{total} embeddings successfully")
        
        return embeddings
    
    def test_connection(self) -> bool:
        """
        Test if Ollama embeddings endpoint is available
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test with a simple text
            test_text = "test connection"
            embedding = self.generate_embedding(test_text)
            
            if embedding:
                logger.info(f"✅ Embeddings service connected successfully (dimension: {len(embedding)})")
                return True
            else:
                logger.warning("⚠️ Embeddings service responded but no embedding generated")
                return False
                
        except Exception as e:
            logger.error(f"❌ Embeddings service connection failed: {str(e)}")
            return False
    
    def get_embedding_dimension(self) -> Optional[int]:
        """
        Get the dimension of embeddings produced by the model
        
        Returns:
            Dimension of embedding vectors, or None if failed
        """
        try:
            test_embedding = self.generate_embedding("test")
            if test_embedding:
                return len(test_embedding)
            return None
        except Exception as e:
            logger.error(f"Error getting embedding dimension: {str(e)}")
            return None


# Singleton instance
embeddings_service = EmbeddingsService()