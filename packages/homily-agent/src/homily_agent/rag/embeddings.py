"""
Embedding service for generating text embeddings using sentence-transformers.
"""

import os
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


class EmbeddingService:
    """
    Service for generating text embeddings.
    
    Uses sentence-transformers to generate embeddings for the theological corpus.
    
    Attributes:
        model_name: Name of the sentence-transformer model
        model: The loaded model instance
    """
    
    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None
    ):
        """
        Initialize the embedding service.
        
        Args:
            model_name: Name of the sentence-transformer model to use
            device: Device to use ('cpu', 'cuda', or None for auto-detection)
        """
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.device = device or ("cuda" if os.environ.get("CUDA_VISIBLE_DEVICES") else "cpu")
        self.model: Any | None = None
        
    def _ensure_model_loaded(self) -> None:
        """Lazy-load the model on first use."""
        if self.model is None:
            if SentenceTransformer is None:
                raise ImportError(
                    "sentence-transformers is required. Install with: pip install sentence-transformers"
                )
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
            logger.info(f"Embedding model loaded on device: {self.device}")
            
    def embed_text(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        self._ensure_model_loaded()
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        self._ensure_model_loaded()
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of the embedding vectors.
        
        Returns:
            Dimension of the embedding vectors
        """
        self._ensure_model_loaded()
        return self.model.get_sentence_embedding_dimension()