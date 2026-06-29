#!/usr/bin/env python3
"""
CLI orchestrator: parse Bibbia CEI 2008 and CCC, chunk, and ingest into ChromaDB corpus.

Usage:
    python scripts/ingest_corpus.py [--reset] [--bible-dir PATH] [--ccc-path PATH]
"""

import argparse
import logging
from pathlib import Path

from homily_agent.rag import RetrievalService, BibleParser, Chunker, CatechismParser

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_BIBLE_DIR = PROJECT_ROOT / "support" / "bibbia2008" / "bcei2008"
DEFAULT_CCC_PATH = (
    PROJECT_ROOT / "support" / "catechismo" / "catechismo-della-chiesa-cattolica.pdf"
)


def main():
    parser = argparse.ArgumentParser(description="Ingest theological sources into ChromaDB corpus")
    parser.add_argument("--reset", action="store_true", help="Reset the collection before ingesting")
    parser.add_argument("--bible-dir", type=str, default=str(DEFAULT_BIBLE_DIR))
    parser.add_argument("--ccc-path", type=str, default=str(DEFAULT_CCC_PATH))
    args = parser.parse_args()

    retrieval = RetrievalService()

    if args.reset:
        retrieval.reset_collection()
        logger.info("Collection reset")

    # Bible
    logger.info("Parsing Bible CEI 2008...")
    bible_parser = BibleParser(args.bible_dir)
    verses = bible_parser.parse_all()
    logger.info("Parsed %d verses across %d files", len(verses), len(sorted(Path(args.bible_dir).glob("*.htm"))))

    chunker = Chunker()
    bible_chunks = chunker.chunk_verses(verses)
    logger.info("Created %d Bible chunks", len(bible_chunks))

    retrieval.add_documents(
        documents=[c.text for c in bible_chunks],
        ids=[c.id for c in bible_chunks],
        metadatas=[c.metadata for c in bible_chunks],
    )
    ingested = retrieval.get_document_count()
    logger.info("Ingested %d Bible chunks (total in corpus: %d)", len(bible_chunks), ingested)

    # CCC
    logger.info("Parsing Catechismo...")
    ccc_parser = CatechismParser(args.ccc_path)
    paragraphs = ccc_parser.parse()
    logger.info("Parsed %d CCC paragraphs", len(paragraphs))

    seen_nums: set[int] = set()
    ccc_docs = []
    ccc_ids = []
    ccc_metas = []
    for p in paragraphs:
        if p.paragraph_num in seen_nums:
            continue
        seen_nums.add(p.paragraph_num)
        ccc_docs.append(p.text)
        ccc_ids.append(f"ccc_{p.paragraph_num}")
        ccc_metas.append({
            "source": "CCC",
            "part": p.part,
            "part_title": p.part_title,
            "section": p.section,
            "section_title": p.section_title,
            "chapter": p.chapter,
            "chapter_title": p.chapter_title,
            "subsection": p.subsection,
            "subsection_title": p.subsection_title,
            "paragraph_num": p.paragraph_num,
            "paragraph_title": p.paragraph_title,
        })

    logger.info("Deduplicated to %d unique CCC paragraphs", len(ccc_docs))
    retrieval.add_documents(documents=ccc_docs, ids=ccc_ids, metadatas=ccc_metas)
    total = retrieval.get_document_count()
    logger.info("Ingested %d CCC paragraphs (total in corpus: %d)", len(ccc_docs), total)

    logger.info("Ingestion complete. Corpus contains %d documents", total)


if __name__ == "__main__":
    main()
