"""Document ingestion pipeline – chunks documents, creates embeddings, and builds FAISS index."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np

from permitflow_mcp.config import settings
from permitflow_mcp.rag.chunking import DocumentChunk, chunk_directory

logger = logging.getLogger("permitflow_mcp.rag.ingest")

# Metadata filename stored alongside the FAISS index
METADATA_FILE = "chunk_metadata.json"


def _load_embedding_model(model_name: str):
    """Load a sentence-transformers model."""
    from sentence_transformers import SentenceTransformer
    logger.info("[RAG] Loading embedding model: %s", model_name)
    model = SentenceTransformer(model_name)
    logger.info("[RAG] Embedding model loaded (dimension=%d)", model.get_sentence_embedding_dimension())
    return model


def _embed_chunks(model, chunks: list[DocumentChunk]) -> np.ndarray:
    """Create embeddings for a list of chunks."""
    texts = [c.text for c in chunks]
    logger.info("[RAG] Embedding %d chunks ...", len(texts))
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    return np.array(embeddings, dtype=np.float32)


def _build_faiss_index(embeddings: np.ndarray):
    """Build a FAISS index from embeddings."""
    import faiss
    dimension = embeddings.shape[1]
    # Use IndexFlatIP (inner product) since we normalize embeddings → cosine similarity
    index = faiss.IndexFlatIP(dimension)
    index.add(embeddings)
    logger.info("[RAG] FAISS index built with %d vectors (dim=%d)", index.ntotal, dimension)
    return index


def _save_metadata(chunks: list[DocumentChunk], output_dir: Path) -> None:
    """Persist chunk metadata to JSON alongside the FAISS index."""
    records = []
    for i, chunk in enumerate(chunks):
        records.append({
            "index": i,
            "chunk_id": chunk.chunk_id,
            "source": chunk.source,
            "section": chunk.section,
            "page": chunk.page,
            "word_count": chunk.word_count,
            "text": chunk.text,
        })
    meta_path = output_dir / METADATA_FILE
    with open(meta_path, "w", encoding="utf-8") as fh:
        json.dump(records, fh, indent=2, ensure_ascii=False)
    logger.info("[RAG] Saved metadata for %d chunks to %s", len(records), meta_path)


def ingest_documents(
    documents_dir: Optional[str] = None,
    index_dir: Optional[str] = None,
    model_name: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> dict:
    """Run the full ingestion pipeline.

    1. Chunk all documents in the documents directory.
    2. Create embeddings using sentence-transformers.
    3. Build a FAISS index.
    4. Save the index and metadata.

    Returns:
        Summary dict with stats.
    """
    import faiss

    docs_dir = Path(documents_dir or settings.documents_dir)
    out_dir = Path(index_dir or settings.faiss_index_path)
    model_id = model_name or settings.embedding_model
    c_size = chunk_size or settings.chunk_size
    c_overlap = chunk_overlap or settings.chunk_overlap

    # 1. Chunk
    logger.info("[RAG] Chunking documents from %s (size=%d, overlap=%d)", docs_dir, c_size, c_overlap)
    chunks = chunk_directory(docs_dir, target_words=c_size, overlap_words=c_overlap)
    if not chunks:
        raise RuntimeError(f"No document chunks produced from {docs_dir}. Check that .txt or .md files exist.")
    logger.info("[RAG] Produced %d chunks", len(chunks))

    # 2. Embed
    model = _load_embedding_model(model_id)
    embeddings = _embed_chunks(model, chunks)

    # 3. Build index
    index = _build_faiss_index(embeddings)

    # 4. Save
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.faiss"
    faiss.write_index(index, str(index_path))
    logger.info("[RAG] FAISS index saved to %s", index_path)
    _save_metadata(chunks, out_dir)

    summary = {
        "documents_directory": str(docs_dir),
        "index_directory": str(out_dir),
        "total_chunks": len(chunks),
        "embedding_model": model_id,
        "embedding_dimension": embeddings.shape[1],
        "chunk_size_words": c_size,
        "chunk_overlap_words": c_overlap,
    }
    logger.info("[RAG] Ingestion complete: %s", summary)
    return summary
