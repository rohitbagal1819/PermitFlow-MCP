"""Unit tests for RAG Chunking and Retriever."""

from pathlib import Path
import pytest
from permitflow_mcp.config import settings
from permitflow_mcp.rag.chunking import chunk_directory, chunk_text
from permitflow_mcp.rag.retriever import Retriever


def test_chunk_text():
    sample_text = (
        "# General Requirements\n\n"
        "All commercial building permit applications must submit complete structural calculations, "
        "energy compliance certifications, and valid certificates of insurance.\n\n"
        "## Mechanical Code\n\n"
        "Mechanical equipment must conform to ASHRAE 90.1 standards for cooling efficiency."
    )
    chunks = chunk_text(sample_text, source="test.txt", target_words=20, overlap_words=5)
    assert len(chunks) >= 1
    assert chunks[0].source == "test.txt"
    assert chunks[0].chunk_id != ""


def test_chunk_directory():
    docs_dir = Path(settings.documents_dir)
    chunks = chunk_directory(docs_dir, target_words=400, overlap_words=40)
    assert len(chunks) > 0
    sources = {c.source for c in chunks}
    assert "building_permit_requirements.txt" in sources or "hvac_requirements.txt" in sources


def test_retriever_query():
    retriever = Retriever()
    chunks = retriever.retrieve("HVAC energy efficiency ASHRAE", top_k=3)
    assert len(chunks) > 0
    assert chunks[0].text != ""
    assert chunks[0].relevance_score > 0
