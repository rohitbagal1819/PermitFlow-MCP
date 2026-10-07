"""Configuration for the PermitFlow MCP server."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


# Project root is two levels up from this file (src/permitflow_mcp/config.py -> project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    # RAG Configuration
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="HuggingFace model ID for sentence embeddings",
    )
    faiss_index_path: str = Field(
        default=str(PROJECT_ROOT / "faiss_index"),
        description="Path to the FAISS index directory",
    )
    chunk_size: int = Field(
        default=500,
        description="Target chunk size in words for document chunking",
    )
    chunk_overlap: int = Field(
        default=60,
        description="Overlap in words between consecutive chunks",
    )
    top_k_results: int = Field(
        default=4,
        description="Number of top results to return from RAG retrieval",
    )

    # Paths
    documents_dir: str = Field(
        default=str(PROJECT_ROOT / "documents"),
        description="Path to the documents directory for RAG ingestion",
    )
    mock_data_dir: str = Field(
        default=str(PROJECT_ROOT / "mock_data"),
        description="Path to the mock data directory",
    )
    reports_dir: str = Field(
        default=str(PROJECT_ROOT / "reports"),
        description="Path to the directory where exported reports and audit logs are written",
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Server
    mcp_server_name: str = Field(
        default="permitflow-mcp",
        description="MCP server name",
    )
    mcp_server_version: str = Field(default="0.1.0", description="MCP server version")

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()
