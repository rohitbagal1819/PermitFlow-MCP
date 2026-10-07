"""PermitFlow MCP Server.

Provides FastMCP server instance for PermitFlow permit readiness analysis
and portfolio-level intelligence.
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from mcp.server.fastmcp import FastMCP

from permitflow_mcp.config import settings
from permitflow_mcp.prompts.permit_prompts import register_prompts
from permitflow_mcp.rag.retriever import Retriever
from permitflow_mcp.resources.permit_resources import register_resources
from permitflow_mcp.resources.portfolio_resources import register_portfolio_resources
from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.portfolio_service import PortfolioService
from permitflow_mcp.services.readiness_service import ReadinessService
from permitflow_mcp.tools.permit_tools import register_tools
from permitflow_mcp.tools.portfolio_tools import register_portfolio_tools

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("permitflow_mcp.server")


def create_server(
    data_dir: Optional[str] = None,
    index_dir: Optional[str] = None,
    documents_dir: Optional[str] = None,
) -> FastMCP:
    """Create and configure the PermitFlow FastMCP server instance."""
    logger.info("Initializing PermitFlow MCP server (version %s)", settings.mcp_server_version)

    # 1. Initialize core services
    permit_service = PermitService(data_dir=data_dir)
    permit_service.load_data()

    readiness_service = ReadinessService(permit_service=permit_service)

    retriever = Retriever(
        index_dir=index_dir,
        documents_dir=documents_dir,
    )

    portfolio_service = PortfolioService(
        permit_service=permit_service,
        readiness_service=readiness_service,
        data_dir=data_dir,
    )

    # 2. Create FastMCP server
    mcp = FastMCP(
        settings.mcp_server_name,
        instructions=(
            "PermitFlow MCP provides construction permitting intelligence for contractors and developers.\n\n"
            "Capabilities:\n"
            "1. Single-Permit Readiness: Check readiness scores, identify missing/expired documents, "
            "explain blockers, search municipal requirements via RAG, and generate resubmission runbooks.\n"
            "2. Portfolio-Level Intelligence: Rank all permits by risk/priority, detect day-over-day changes, "
            "surface cross-project systemic bottlenecks, and generate daily executive action plans for managers."
        ),
    )

    # 3. Register tools
    logger.info("Registering single-permit readiness tools...")
    register_tools(
        mcp=mcp,
        permit_service=permit_service,
        readiness_service=readiness_service,
        retriever=retriever,
    )

    logger.info("Registering portfolio intelligence tools...")
    register_portfolio_tools(
        mcp=mcp,
        portfolio_service=portfolio_service,
    )

    # 4. Register resources
    logger.info("Registering permit and portfolio resources...")
    register_resources(
        mcp=mcp,
        permit_service=permit_service,
        readiness_service=readiness_service,
    )
    register_portfolio_resources(
        mcp=mcp,
        portfolio_service=portfolio_service,
    )

    # 5. Register prompts
    logger.info("Registering MCP prompts...")
    register_prompts(mcp=mcp)

    logger.info("PermitFlow MCP server successfully configured.")
    return mcp


# Module-level server instance for MCP CLI execution (e.g. `mcp run src/permitflow_mcp/server.py`)
mcp = create_server()


def main() -> None:
    """Main entry point for running the MCP server."""
    parser = argparse.ArgumentParser(description="PermitFlow MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport protocol (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    args = parser.parse_args()

    logger.info("Starting PermitFlow MCP server using %s transport...", args.transport)
    if args.transport == "sse":
        if hasattr(mcp, "settings") and hasattr(mcp.settings, "port"):
            mcp.settings.port = args.port
        try:
            mcp.run(transport="sse")
        except TypeError:
            mcp.run("sse")
    else:
        try:
            mcp.run(transport="stdio")
        except TypeError:
            mcp.run()



if __name__ == "__main__":
    main()
