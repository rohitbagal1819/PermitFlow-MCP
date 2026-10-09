"""Simple Section-Aware Document RAG Retriever.

Loads municipal building codes and guidelines directly from the documents directory,
chunks them by section headings, and performs fast semantic keyword & BM25-style
relevance retrieval with zero heavy ML dependencies (pure Python, no FAISS, no PyTorch).
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path
from typing import Optional

from permitflow_mcp.config import settings
from permitflow_mcp.models.schemas import RAGChunk
from permitflow_mcp.rag.chunking import DocumentChunk, chunk_directory

logger = logging.getLogger("permitflow_mcp.rag.retriever")


class Retriever:
    """Lightweight in-memory document retriever for municipal building codes."""

    def __init__(
        self,
        documents_dir: Optional[str] = None,
    ) -> None:
        self._documents_dir = Path(documents_dir or settings.documents_dir)
        self._chunks: list[DocumentChunk] = []
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def load(self) -> None:
        """Load and chunk documents from the documents directory."""
        if not self._documents_dir.exists():
            logger.warning("[RAG] Documents directory not found: %s", self._documents_dir)
            self._loaded = True
            return

        logger.info("[RAG] Loading and chunking documents from %s", self._documents_dir)
        self._chunks = chunk_directory(
            self._documents_dir,
            target_words=settings.chunk_size,
            overlap_words=settings.chunk_overlap,
        )
        self._loaded = True
        logger.info("[RAG] In-memory retriever loaded %d document chunks", len(self._chunks))

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        source_filter: Optional[str] = None,
    ) -> list[RAGChunk]:
        """Retrieve top-k relevant chunks using BM25-style term weighting & section boosting."""
        self._ensure_loaded()
        if not self._chunks:
            return []

        k = top_k or settings.top_k_results

        # Tokenize query
        query_words = re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", query.lower())
        stopwords = {
            "what", "which", "where", "when", "does", "have", "that", "this",
            "from", "with", "about", "into", "over", "after", "before", "required",
            "permit", "permits", "requirement", "requirements", "please", "find",
            "code", "codes", "rules", "rule",
        }
        keywords = [w for w in query_words if w not in stopwords] or query_words

        scored: list[tuple[float, DocumentChunk]] = []

        for chunk in self._chunks:
            if source_filter and source_filter.lower() not in chunk.source.lower():
                continue

            chunk_text_lower = chunk.text.lower()
            section_lower = (chunk.section or "").lower()

            score = 0.0

            # Exact query phrase match bonus
            if query.lower() in chunk_text_lower:
                score += 5.0

            for kw in keywords:
                # Frequency match in text body
                matches = len(re.findall(r"\b" + re.escape(kw) + r"\b", chunk_text_lower))
                if matches > 0:
                    score += 1.0 + math.log(1 + matches)
                elif kw in chunk_text_lower:
                    score += 0.5

                # Heavy boost for appearance in section heading
                if kw in section_lower:
                    score += 3.5

            if score > 0.0:
                # Normalize score to 0.50..0.99 range
                normalized_score = min(0.99, round(0.55 + (score / (score + 5.0)) * 0.44, 4))
                scored.append((normalized_score, chunk))

        # Sort descending by score
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
        """Retrieve plain text of top-k chunks."""
        chunks = self.retrieve(query, top_k=top_k)
        return [c.text for c in chunks]

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def total_chunks(self) -> int:
        return len(self._chunks)
