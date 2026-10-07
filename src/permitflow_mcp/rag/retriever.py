"""RAG retriever – queries the FAISS index or document corpus and returns relevant chunks."""

from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Optional

from permitflow_mcp.config import settings
from permitflow_mcp.models.schemas import RAGChunk
from permitflow_mcp.rag.chunking import DocumentChunk, chunk_directory
from permitflow_mcp.rag.ingest import METADATA_FILE

logger = logging.getLogger("permitflow_mcp.rag.retriever")


class Retriever:
    """Loads a FAISS index + metadata or falls back to in-memory semantic keyword matching."""

    def __init__(
        self,
        index_dir: Optional[str] = None,
        model_name: Optional[str] = None,
        documents_dir: Optional[str] = None,
    ) -> None:
        self._index_dir = Path(index_dir or settings.faiss_index_path)
        self._model_name = model_name or settings.embedding_model
        self._documents_dir = Path(documents_dir or settings.documents_dir)
        self._index = None
        self._metadata: list[dict] = []
        self._model = None
        self._fallback_chunks: list[DocumentChunk] = []
        self._use_faiss = False
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self.load()

    def load(self) -> None:
        """Attempt to load FAISS index; fall back to chunked document corpus if unavailable."""
        index_path = self._index_dir / "index.faiss"
        meta_path = self._index_dir / METADATA_FILE

        if index_path.exists() and meta_path.exists():
            try:
                import faiss
                import numpy as np
                from sentence_transformers import SentenceTransformer

                logger.info("[RAG] Loading FAISS index from %s", index_path)
                self._index = faiss.read_index(str(index_path))
                with open(meta_path, "r", encoding="utf-8") as fh:
                    self._metadata = json.load(fh)
                logger.info("[RAG] Loading embedding model: %s", self._model_name)
                self._model = SentenceTransformer(self._model_name)
                self._use_faiss = True
                self._loaded = True
                logger.info("[RAG] FAISS retriever loaded with %d vectors", self._index.ntotal)
                return
            except Exception as exc:
                logger.warning("[RAG] FAISS / sentence-transformers loading failed (%s). Falling back to direct document index.", exc)

        # Fallback to direct document chunking
        logger.info("[RAG] Initializing in-memory retriever from documents directory: %s", self._documents_dir)
        if self._documents_dir.exists():
            self._fallback_chunks = chunk_directory(
                self._documents_dir,
                target_words=settings.chunk_size,
                overlap_words=settings.chunk_overlap,
            )
            logger.info("[RAG] In-memory retriever loaded %d document chunks", len(self._fallback_chunks))
        else:
            logger.warning("[RAG] Documents directory not found: %s", self._documents_dir)

        self._use_faiss = False
        self._loaded = True

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        source_filter: Optional[str] = None,
    ) -> list[RAGChunk]:
        """Retrieve the top-k most relevant chunks for a query.

        Uses FAISS vector similarity when available, or semantic keyword & BM25-like
        term scoring across document sections as fallback.
        """
        self._ensure_loaded()
        k = top_k or settings.top_k_results

        if self._use_faiss and self._index is not None and self._model is not None:
            return self._retrieve_faiss(query, k, source_filter)
        return self._retrieve_fallback(query, k, source_filter)

    def _retrieve_faiss(
        self,
        query: str,
        k: int,
        source_filter: Optional[str] = None,
    ) -> list[RAGChunk]:
        import numpy as np

        query_vec = self._model.encode([query], normalize_embeddings=True)
        query_vec = np.array(query_vec, dtype=np.float32)

        scores, indices = self._index.search(query_vec, min(k * 3, self._index.ntotal))

        results: list[RAGChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self._metadata):
                continue
            meta = self._metadata[idx]

            if source_filter and source_filter.lower() not in meta.get("source", "").lower():
                continue

            results.append(
                RAGChunk(
                    text=meta["text"],
                    source=meta["source"],
                    section=meta.get("section"),
                    page=meta.get("page"),
                    chunk_id=meta["chunk_id"],
                    relevance_score=round(float(score), 4),
                )
            )

            if len(results) >= k:
                break

        return results

    def _retrieve_fallback(
        self,
        query: str,
        k: int,
        source_filter: Optional[str] = None,
    ) -> list[RAGChunk]:
        """BM25-style keyword matching and section relevance scoring."""
        if not self._fallback_chunks:
            return []

        # Tokenize query
        query_words = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", query.lower())
        stopwords = {
            "what", "which", "where", "when", "does", "have", "that", "this",
            "from", "with", "about", "into", "over", "after", "before", "required",
            "permit", "permits", "requirement", "requirements",
        }
        keywords = [w for w in query_words if w not in stopwords] or query_words

        scored: list[tuple[float, DocumentChunk]] = []

        for chunk in self._fallback_chunks:
            if source_filter and source_filter.lower() not in chunk.source.lower():
                continue

            chunk_text_lower = chunk.text.lower()
            section_lower = (chunk.section or "").lower()

            score = 0.0
            for kw in keywords:
                # Count in body
                matches = len(re.findall(r"\b" + re.escape(kw) + r"\b", chunk_text_lower))
                if matches > 0:
                    score += 1.0 + math.log(1 + matches)
                elif kw in chunk_text_lower:
                    score += 0.5

                # Heavy boost for appearance in section title
                if kw in section_lower:
                    score += 3.0

            if score > 0.0:
                # Normalize score to 0..1 range approx
                normalized_score = min(0.99, round(0.5 + (score / (score + 5.0)) * 0.49, 4))
                scored.append((normalized_score, chunk))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[RAGChunk] = []
        for norm_score, chunk in scored[:k]:
            results.append(
                RAGChunk(
                    text=chunk.text,
                    source=chunk.source,
                    section=chunk.section,
                    page=chunk.page,
                    chunk_id=chunk.chunk_id,
                    relevance_score=norm_score,
                )
            )

        return results

    def retrieve_text(self, query: str, top_k: Optional[int] = None) -> list[str]:
        chunks = self.retrieve(query, top_k=top_k)
        return [c.text for c in chunks]

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_chunks(self) -> int:
        if self._use_faiss and self._index is not None:
            return self._index.ntotal
        return len(self._fallback_chunks)
