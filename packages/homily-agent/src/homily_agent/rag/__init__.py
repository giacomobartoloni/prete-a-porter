"""
RAG (Retrieval-Augmented Generation) package for Homily Agent.

Provides embedding generation and document retrieval for theological knowledge.
"""

from .embeddings import EmbeddingService
from .retrieval import RetrievalService, load_theological_corpus
from .bible_parser import BibleParser, Chunker, Verse, BibleChunk
from .catechism_parser import CatechismParser, Paragraph

__all__ = [
    "EmbeddingService", "RetrievalService", "load_theological_corpus",
    "BibleParser", "Chunker", "Verse", "BibleChunk",
    "CatechismParser", "Paragraph",
]