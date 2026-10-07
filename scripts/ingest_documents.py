#!/usr/bin/env python3
"""Script to run the RAG document ingestion pipeline."""

import logging
import sys
from pathlib import Path

# Add src to pythonpath
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "src"))

from permitflow_mcp.rag.ingest import ingest_documents

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def main():
    print("==================================================")
    print("  PermitFlow MCP: Document Ingestion Pipeline")
    print("==================================================")
    try:
        summary = ingest_documents()
        print("\nIngestion succeeded!")
        for k, v in summary.items():
            print(f"  {k}: {v}")
    except Exception as exc:
        print(f"\nIngestion failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
