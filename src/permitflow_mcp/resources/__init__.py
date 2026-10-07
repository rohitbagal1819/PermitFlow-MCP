"""Resources package for PermitFlow MCP."""

from permitflow_mcp.resources.permit_resources import register_resources
from permitflow_mcp.resources.portfolio_resources import register_portfolio_resources

__all__ = [
    "register_resources",
    "register_portfolio_resources",
]
