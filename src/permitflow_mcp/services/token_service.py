"""Token counting service for context efficiency comparison."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("permitflow_mcp.token_service")


def estimate_tokens(text: str) -> int:
    """Estimate token count using a word-based heuristic.

    A common approximation is ~0.75 words per token for English text,
    or equivalently ~1.33 tokens per word.  We use the slightly more
    conservative 1.3 multiplier which is well within the accepted range.
    """
    word_count = len(text.split())
    return int(word_count * 1.3)


def count_tokens_tiktoken(text: str, model: str = "cl100k_base") -> int:
    """Count tokens using tiktoken (OpenAI tokenizer).

    Falls back to word-based estimate if tiktoken is unavailable.
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding(model)
        return len(enc.encode(text))
    except Exception:
        logger.debug("tiktoken unavailable, falling back to word-based estimate")
        return estimate_tokens(text)


def compare_token_usage(
    full_text: str,
    rag_chunks: list[str],
    use_tiktoken: bool = True,
) -> dict:
    """Compare token usage between full document and RAG-retrieved chunks.

    Returns a dictionary with token counts and reduction percentage.
    """
    combined_chunks = "\n\n---\n\n".join(rag_chunks)

    if use_tiktoken:
        counter = count_tokens_tiktoken
    else:
        counter = estimate_tokens

    full_tokens = counter(full_text)
    rag_tokens = counter(combined_chunks)
    reduction = ((full_tokens - rag_tokens) / full_tokens * 100) if full_tokens > 0 else 0.0

    return {
        "full_document_tokens": full_tokens,
        "rag_context_tokens": rag_tokens,
        "token_reduction_percent": round(reduction, 1),
        "full_document_words": len(full_text.split()),
        "rag_context_words": len(combined_chunks.split()),
        "num_chunks_used": len(rag_chunks),
        "method": "tiktoken" if use_tiktoken else "word_estimate",
    }


def load_all_documents(documents_dir: str) -> str:
    """Load and concatenate all documents from the documents directory."""
    docs_path = Path(documents_dir)
    if not docs_path.exists():
        return ""

    all_text: list[str] = []
    for ext in ("*.txt", "*.md"):
        for fpath in sorted(docs_path.glob(ext)):
            all_text.append(fpath.read_text(encoding="utf-8"))

    return "\n\n".join(all_text)


class TokenService:
    """Service for estimating and comparing token usage."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count using word-based heuristic."""
        return estimate_tokens(text)

    @staticmethod
    def count_tokens_tiktoken(text: str, model: str = "cl100k_base") -> int:
        """Count tokens using tiktoken (fallback to heuristic)."""
        return count_tokens_tiktoken(text, model)

    @staticmethod
    def compare_token_usage(
        full_text: str,
        rag_chunks: list[str],
        use_tiktoken: bool = True,
    ) -> dict:
        """Compare token usage between full document and retrieved chunks."""
        return compare_token_usage(full_text, rag_chunks, use_tiktoken)

    @staticmethod
    def load_all_documents(documents_dir: str) -> str:
        """Load and concatenate all documents from the documents directory."""
        return load_all_documents(documents_dir)

