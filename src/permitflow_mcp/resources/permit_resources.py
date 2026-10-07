"""MCP resources for exposing permit data as read-only context."""

from __future__ import annotations

import json
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.readiness_service import ReadinessService

logger = logging.getLogger("permitflow_mcp.resources.permit_resources")


def register_resources(
    mcp: FastMCP,
    permit_service: PermitService,
    readiness_service: ReadinessService,
) -> None:
    """Register MCP resources on the given FastMCP server instance."""

    # ------------------------------------------------------------------
    # Resource: permit://{permit_id}
    # ------------------------------------------------------------------
    @mcp.resource("permit://{permit_id}")
    def get_permit_resource(permit_id: str) -> str:
        """Get structured information for a specific permit.

        Returns permit details including project info, document status,
        authority comments, and inspection status as formatted text.
        """
        logger.info("[MCP] Resource: permit://%s", permit_id)
        permit = permit_service.get_permit(permit_id)
        if not permit:
            return f"Permit '{permit_id}' not found."

        comments = permit_service.get_comments_for_permit(permit_id)
        inspections = permit_service.get_inspections_for_permit(permit_id)
        required_docs = permit_service.get_required_documents(permit_id)
        submitted_docs = permit_service.get_submitted_documents(permit_id)

        data = {
            "permit": permit,
            "required_documents": required_docs,
            "submitted_documents": submitted_docs,
            "authority_comments": comments,
            "inspections": inspections,
        }

        return json.dumps(data, indent=2, default=str)

    # ------------------------------------------------------------------
    # Resource: project://{project_id}
    # ------------------------------------------------------------------
    @mcp.resource("project://{project_id}")
    def get_project_resource(project_id: str) -> str:
        """Get project information and all associated permits."""
        logger.info("[MCP] Resource: project://%s", project_id)
        project = permit_service.get_project(project_id)
        if not project:
            return f"Project '{project_id}' not found."

        # Find all permits for this project
        all_permits = permit_service.list_permits()
        project_permits = [p for p in all_permits if p.get("project_id") == project_id]

        data = {
            "project": project,
            "permits": project_permits,
        }

        return json.dumps(data, indent=2, default=str)

    # ------------------------------------------------------------------
    # Resource: requirements://{jurisdiction}/{permit_type}
    # ------------------------------------------------------------------
    @mcp.resource("requirements://{jurisdiction}/{permit_type}")
    def get_requirements_resource(jurisdiction: str, permit_type: str) -> str:
        """Get permit requirements for a specific jurisdiction and permit type."""
        # Convert URL-safe format back to readable format
        jurisdiction_readable = jurisdiction.replace("-", " ").title()
        if not jurisdiction_readable.startswith("City"):
            jurisdiction_readable = f"City of {jurisdiction_readable}"

        logger.info(
            "[MCP] Resource: requirements://%s/%s", jurisdiction_readable, permit_type
        )
        reqs = permit_service.get_requirements_by_jurisdiction(
            jurisdiction_readable, permit_type
        )

        if not reqs:
            return f"No requirements found for jurisdiction='{jurisdiction_readable}', permit_type='{permit_type}'."

        return json.dumps(reqs, indent=2, default=str)

    # ------------------------------------------------------------------
    # Resource: runbook://permit-resubmission/{permit_id}
    # ------------------------------------------------------------------
    @mcp.resource("runbook://permit-resubmission/{permit_id}")
    def get_resubmission_runbook(permit_id: str) -> str:
        """Get a resubmission runbook for a specific permit.

        Generates a step-by-step guide for resubmitting the permit,
        including all required corrections and documents.
        """
        logger.info("[MCP] Resource: runbook://permit-resubmission/%s", permit_id)
        try:
            checklist = readiness_service.generate_checklist(permit_id)
        except ValueError as exc:
            return f"Error: {exc}"

        return checklist.model_dump_json(indent=2)
