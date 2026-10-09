"""MCP resources for exposing Portfolio-Level Intelligence as read-only context."""

from __future__ import annotations

import json
import logging
from mcp.server.fastmcp import FastMCP

from permitflow_mcp.services.portfolio_service import PortfolioService

logger = logging.getLogger("permitflow_mcp.resources.portfolio_resources")


def register_portfolio_resources(
    mcp: FastMCP,
    portfolio_service: PortfolioService,
) -> None:
    """Register all Portfolio-Level Intelligence MCP resources."""

    # ------------------------------------------------------------------
    # Resource: portfolio://summary
    # ------------------------------------------------------------------
    @mcp.resource("portfolio://summary")
    def get_portfolio_summary_resource() -> str:
        """Get high-level portfolio health KPIs, risk breakdown, and active permit counts."""
        logger.info("[MCP] Resource: portfolio://summary")
        briefing = portfolio_service.get_daily_briefing()
        return briefing.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Resource: portfolio://priorities
    # ------------------------------------------------------------------
    @mcp.resource("portfolio://priorities")
    def get_portfolio_priorities_resource() -> str:
        """Get full ranked list of permits ordered by risk and urgency."""
        logger.info("[MCP] Resource: portfolio://priorities")
        ranking = portfolio_service.rank_permits()
        return ranking.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Resource: portfolio://daily-action-plan
    # ------------------------------------------------------------------
    @mcp.resource("portfolio://daily-action-plan")
    def get_portfolio_action_plan_resource() -> str:
        """Get today's prioritized executive action tasks for the permit management team."""
        logger.info("[MCP] Resource: portfolio://daily-action-plan")
        tasks = portfolio_service.generate_daily_action_plan()
        data = {
            "date": "2026-07-06",
            "total_tasks": len(tasks),
            "tasks": [t.model_dump() for t in tasks],
        }
        return json.dumps(data, indent=2, default=str)

    # ------------------------------------------------------------------
    # Resource: portfolio://systemic-bottlenecks
    # ------------------------------------------------------------------
    @mcp.resource("portfolio://systemic-bottlenecks")
    def get_portfolio_systemic_bottlenecks_resource() -> str:
        """Get identified cross-cutting bottlenecks, prevalence, root causes, and fixes."""
        logger.info("[MCP] Resource: portfolio://systemic-bottlenecks")
        bottlenecks = portfolio_service.identify_systemic_bottlenecks()
        return bottlenecks.model_dump_json(indent=2)

    # ------------------------------------------------------------------
    # Resource: portfolio://changes
    # ------------------------------------------------------------------
    @mcp.resource("portfolio://changes")
    def get_portfolio_changes_resource() -> str:
        """Get day-over-day changes detected across the permit portfolio."""
        logger.info("[MCP] Resource: portfolio://changes")
        changes = portfolio_service.detect_changes()
        return changes.model_dump_json(indent=2)
