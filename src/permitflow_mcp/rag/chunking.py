"""Document chunking for the RAG pipeline.

Strategy:
- Split documents into chunks of approximately 400-600 words
- Overlap ~60 words between consecutive chunks
- Preserve metadata: source file, section heading, page-like reference, chunk ID
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DocumentChunk:
    """A chunk of text with associated metadata."""
    text: str
    source: str  # filename
    section: Optional[str] = None
    page: Optional[int] = None
    chunk_id: str = ""
    word_count: int = 0

    def __post_init__(self) -> None:
        self.word_count = len(self.text.split())
        if not self.chunk_id:
            digest = hashlib.md5(
                f"{self.source}:{self.section}:{self.text[:200]}".encode()
            ).hexdigest()[:12]
            self.chunk_id = f"chunk-{digest}"


def _detect_sections(text: str) -> list[tuple[str, str]]:
    """Split text into (section_heading, section_body) pairs.

    Recognises:
    - Markdown headings (# / ## / ###)
    - ALL-CAPS headings followed by a newline
    - Lines of '=' or '-' used as underlines
    """
    # Patterns for section headers
    heading_re = re.compile(
        r"^(?:#{1,4}\s+(.+)|([A-Z][A-Z \-:()0-9]{4,})\s*$|(?:={3,}|-{3,})\s*$)",
        re.MULTILINE,
    )

    sections: list[tuple[str, str]] = []
    current_heading = "Introduction"
    last_pos = 0

    for match in heading_re.finditer(text):
        # Grab text before this heading
        chunk_text = text[last_pos : match.start()].strip()
        if chunk_text:
            sections.append((current_heading, chunk_text))

        # Determine new heading
        md_heading = match.group(1)
        caps_heading = match.group(2)
        if md_heading:
            current_heading = md_heading.strip()
        elif caps_heading:
            current_heading = caps_heading.strip()
        # Skip bare separator lines (===, ---)

        last_pos = match.end()

    # Remaining text
    remaining = text[last_pos:].strip()
    if remaining:
        sections.append((current_heading, remaining))

    # If we found nothing, return the whole document
    if not sections:
        sections = [("Full Document", text)]

    return sections


def chunk_text(
    text: str,
    source: str,
    target_words: int = 500,
    overlap_words: int = 60,
) -> list[DocumentChunk]:
    """Chunk a document into overlapping segments.

    Args:
        text: Full document text.
        source: Filename of the source document.
        target_words: Target chunk size in words.
        overlap_words: Number of overlapping words between chunks.

    Returns:
        List of DocumentChunk objects.
    """
    sections = _detect_sections(text)
    chunks: list[DocumentChunk] = []
    page_estimate = 1  # rough page counter (~500 words per page)

    for heading, body in sections:
        words = body.split()

        if len(words) <= target_words:
            # Small section → single chunk
            chunks.append(
                DocumentChunk(
                    text=body,
                    source=source,
                    section=heading,
                    page=page_estimate,
                )
            )
            page_estimate += max(1, len(words) // 500)
            continue

        # Sliding window
        start = 0
        while start < len(words):
            end = min(start + target_words, len(words))
            chunk_words = words[start:end]
            chunk_text_str = " ".join(chunk_words)

            chunks.append(
                DocumentChunk(
                    text=chunk_text_str,
                    source=source,
                    section=heading,
                    page=page_estimate,
                )
            )

            if end >= len(words):
                break

            start = end - overlap_words
            page_estimate += max(1, target_words // 500)

    return chunks


def chunk_file(
    filepath: str | Path,
    target_words: int = 500,
    overlap_words: int = 60,
) -> list[DocumentChunk]:
    """Read a file and chunk its content."""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {filepath}")

    text = path.read_text(encoding="utf-8")
    return chunk_text(text, source=path.name, target_words=target_words, overlap_words=overlap_words)


def chunk_directory(
    directory: str | Path,
    target_words: int = 500,
    overlap_words: int = 60,
    extensions: tuple[str, ...] = (".txt", ".md"),
) -> list[DocumentChunk]:
    """Chunk all documents in a directory."""
    dir_path = Path(directory)
    if not dir_path.exists():
        raise FileNotFoundError(f"Documents directory not found: {directory}")

    all_chunks: list[DocumentChunk] = []
    for ext in extensions:
        for fpath in sorted(dir_path.glob(f"*{ext}")):
            file_chunks = chunk_file(fpath, target_words=target_words, overlap_words=overlap_words)
            all_chunks.extend(file_chunks)

    return all_chunks
