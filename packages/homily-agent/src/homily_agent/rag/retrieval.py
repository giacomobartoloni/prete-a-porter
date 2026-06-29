"""
Retrieval service for querying the theological knowledge base.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
except ImportError:
    chromadb = None
    Settings = None
    ONNXMiniLM_L6_V2 = None


@dataclass
class RetrievedDocument:
    """
    A document retrieved from the knowledge base.
    
    Attributes:
        content: The text content of the document
        source: Source of the document (file name or source name)
        score: Similarity score (0-1, higher is better)
        metadata: Additional metadata about the document
    """
    content: str
    source: str
    score: float
    metadata: dict


class RetrievalService:
    """
    Service for retrieving relevant documents from the theological knowledge base.
    
    Uses ChromaDB for vector storage and similarity search.
    
    Attributes:
        collection_name: Name of the ChromaDB collection
        top_k: Number of documents to retrieve
        min_similarity: Minimum similarity threshold (0-1)
    """
    
    def __init__(
        self,
        persist_directory: str = "data/chroma_db",
        collection_name: str = "corpus",
        top_k: int | None = None,
        min_similarity: float | None = None
    ):
        """
        Initialize the retrieval service.
        
        Args:
            persist_directory: Directory to persist the ChromaDB database
            collection_name: Name of the collection
            top_k: Number of documents to retrieve
            min_similarity: Minimum similarity threshold
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.top_k = top_k if top_k is not None else int(os.getenv("RAG_TOP_K", "5"))
        self.min_similarity = min_similarity if min_similarity is not None else float(os.getenv("RAG_MIN_SIMILARITY", "0.7"))
        
        self.client = None
        self.collection = None
        
    def _ensure_initialized(self) -> None:
        """Ensure the ChromaDB client and collection are initialized."""
        if self.client is None:
            if chromadb is None:
                raise ImportError(
                    "chromadb is required. Install with: pip install chromadb"
                )
            
            os.makedirs(self.persist_directory, exist_ok=True)
            
            self.client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False),
            )
            
            ef = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"]) if ONNXMiniLM_L6_V2 is not None else None
            try:
                self.collection = self.client.get_collection(
                    self.collection_name,
                    embedding_function=ef,
                )
                logger.info(f"Loaded existing collection: {self.collection_name}")
            except Exception:
                self.collection = self.client.create_collection(
                    self.collection_name,
                    metadata={"hnsw:space": "cosine"},
                    embedding_function=ef,
                )
                logger.info(f"Created new collection: {self.collection_name}")
                
    def add_documents(
        self,
        documents: list[str],
        ids: list[str],
        metadatas: Optional[list[dict]] = None
    ) -> None:
        """
        Add documents to the knowledge base.
        
        Args:
            documents: List of document texts
            ids: List of unique IDs for the documents
            metadatas: Optional list of metadata dictionaries
        """
        self._ensure_initialized()
        
        if metadatas is None:
            metadatas = [{"source": doc_id} for doc_id in ids]
            
        self.collection.add(
            documents=documents,
            ids=ids,
            metadatas=metadatas
        )
        logger.info(f"Added {len(documents)} documents to collection")
        
    def retrieve(self, query: str) -> list[RetrievedDocument]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: The search query
            
        Returns:
            List of RetrievedDocument objects, sorted by similarity score
        """
        self._ensure_initialized()
        
        results = self.collection.query(
            query_texts=[query],
            n_results=self.top_k
        )
        
        documents = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results["distances"] else 0.0
                score = 1.0 - distance
                
                if score >= self.min_similarity:
                    metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                    documents.append(RetrievedDocument(
                        content=doc,
                        source=metadata.get("source", "unknown"),
                        score=score,
                        metadata=metadata
                    ))
                    
        logger.debug(f"Retrieved {len(documents)} documents for query: {query[:50]}...")
        return documents
    
    def get_document_count(self) -> int:
        """
        Get the number of documents in the collection.
        
        Returns:
            Number of documents
        """
        self._ensure_initialized()
        return self.collection.count()
    
    def reset_collection(self) -> None:
        """
        Delete and recreate the collection.
        """
        if self.client is not None:
            try:
                self.client.delete_collection(self.collection_name)
            except Exception:
                pass
            ef = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"]) if ONNXMiniLM_L6_V2 is not None else None
            self.collection = self.client.create_collection(
                self.collection_name,
                metadata={"hnsw:space": "cosine"},
                embedding_function=ef,
            )
            logger.info(f"Reset collection: {self.collection_name}")

    def delete_collection(self) -> None:
        """
        Delete the collection and all its documents.
        """
        if self.client is not None:
            self.client.delete_collection(self.collection_name)
            self.collection = None
            logger.info(f"Deleted collection: {self.collection_name}")


def load_theological_corpus(
    corpus_directory: str = "data/theological_corpus",
    retrieval_service: Optional[RetrievalService] = None
) -> RetrievalService:
    """
    Load documents from the theological corpus directory into ChromaDB.
    
    Args:
        corpus_directory: Path to the corpus directory
        retrieval_service: Optional existing retrieval service to use
        
    Returns:
        The populated RetrievalService instance
    """
    if retrieval_service is None:
        retrieval_service = RetrievalService()
    
    corpus_path = Path(corpus_directory)
    if not corpus_path.exists():
        logger.warning(f"Corpus directory not found: {corpus_directory}")
        return retrieval_service
    
    documents = []
    ids = []
    metadatas = []
    
    for file_path in corpus_path.rglob("*.txt"):
        try:
            content = file_path.read_text(encoding="utf-8")
            doc_id = f"doc_{file_path.stem}"
            
            relative_path = file_path.relative_to(corpus_path)
            metadata = {
                "source": str(relative_path),
                "type": "theological_document"
            }
            
            chunks = _chunk_text(content, chunk_size=1000, overlap=100)
            for i, chunk in enumerate(chunks):
                documents.append(chunk)
                ids.append(f"{doc_id}_chunk_{i}")
                metadatas.append(metadata.copy())
                
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
    
    if documents:
        retrieval_service.add_documents(documents, ids, metadatas)
        logger.info(f"Loaded {len(documents)} document chunks from corpus")
    
    return retrieval_service


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """
    Split text into overlapping chunks.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum size of each chunk
        overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        
    return chunks