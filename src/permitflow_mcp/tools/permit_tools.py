"""MCP tools for permit readiness and analysis.

Each tool is registered with the FastMCP server via the register_tools() function.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP

from permitflow_mcp.config import settings
from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.readiness_service import ReadinessService
from permitflow_mcp.rag.retriever import Retriever

logger = logging.getLogger("permitflow_mcp.tools.permit_tools")


def register_tools(
    mcp: FastMCP,
    permit_service: PermitService,
    readiness_service: ReadinessService,
    retriever: Retriever,
) -> dict[str, Any]:
    """Register all MCP tools on the given FastMCP server instance and return tool map."""

    # ------------------------------------------------------------------
    # Tool 1: check_permit_readiness
    # ------------------------------------------------------------------
    @mcp.tool()
    def check_permit_readiness(permit_id: str) -> str:
        """Check whether a construction permit is ready for submission or resubmission.

        This tool inspects the permit's documents, requirements, authority comments,
        and inspection status to determine overall readiness. It returns a structured
        readiness report including missing documents, blockers, warnings, evidence,
        and recommended next actions.

        Use this tool when someone asks: "Is permit X ready?", "Can we submit permit X?",
        or "What is the readiness status of permit X?"

        Args:
            permit_id: The permit identifier (e.g., "P-1042").

        Returns:
            A structured readiness report with status, score, blockers, and actions.
        """
        logger.info("[MCP] Tool: check_permit_readiness | Permit: %s", permit_id)
        try:
            result = readiness_service.check_readiness(permit_id)
        except ValueError as exc:
            return f"Error: {exc}"

        # Format as human-readable structured text
        lines = [
            f"═══ PERMIT READINESS REPORT ═══",
            f"",
            f"Permit ID:        {result.permit_id}",
            f"Project:          {result.project_name}",
            f"Type:             {result.permit_type}",
            f"Jurisdiction:     {result.jurisdiction}",
            f"Current Status:   {result.current_status}",
            f"",
            f"▸ Readiness:      {result.readiness_status.value}",
            f"▸ Score:          {result.readiness_score}/100",
            f"",
            f"Summary: {result.summary}",
        ]

        if result.missing_documents:
            lines.append(f"\n── Missing Documents ({len(result.missing_documents)}) ──")
            for doc in result.missing_documents:
                lines.append(f"  ✗ {doc.document_name} ({doc.document_type})")
                lines.append(f"    → {doc.detail}")

        if result.invalid_documents:
            lines.append(f"\n── Invalid Documents ({len(result.invalid_documents)}) ──")
            for doc in result.invalid_documents:
                lines.append(f"  ⚠ {doc.document_name} [{doc.issue_type.value}]")
                lines.append(f"    → {doc.detail}")

        if result.authority_comments:
            lines.append(f"\n── Authority Comments ({len(result.authority_comments)}) ──")
            for cmt in result.authority_comments:
                lines.append(f"  • {cmt}")

        if result.inspection_issues:
            lines.append(f"\n── Inspection Issues ({len(result.inspection_issues)}) ──")
            for issue in result.inspection_issues:
                lines.append(f"  • {issue}")

        if result.blockers:
            lines.append(f"\n── Blockers ({len(result.blockers)}) ──")
            for b in result.blockers:
                lines.append(f"  🚫 {b}")

        if result.warnings:
            lines.append(f"\n── Warnings ({len(result.warnings)}) ──")
            for w in result.warnings:
                lines.append(f"  ⚠ {w}")

        if result.recommended_actions:
            lines.append(f"\n── Recommended Actions ({len(result.recommended_actions)}) ──")
            for i, action in enumerate(result.recommended_actions, 1):
                lines.append(f"  {i}. [{action.priority.value.upper()}] {action.action}")
                lines.append(f"     Reason: {action.reason[:120]}")

        lines.append(f"\n⚑ Human review required before final submission.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 2: find_missing_documents
    # ------------------------------------------------------------------
    @mcp.tool()
    def find_missing_documents(permit_id: str) -> str:
        """Find all missing, expired, rejected, or outdated documents for a permit.

        Compares the required documents against submitted documents and checks
        each submitted document's status and expiry date. Returns a detailed
        report of all document issues.

        Use this tool when someone asks: "What documents are missing for permit X?",
        "Are all documents submitted?", or "Which documents need attention?"

        Args:
            permit_id: The permit identifier (e.g., "P-1042").

        Returns:
            A report listing all document issues with details and recommended fixes.
        """
        logger.info("[MCP] Tool: find_missing_documents | Permit: %s", permit_id)
        try:
            result = readiness_service.check_readiness(permit_id)
        except ValueError as exc:
            return f"Error: {exc}"

        permit = permit_service.get_permit(permit_id)
        all_issues = result.missing_documents + result.invalid_documents

        lines = [
            f"═══ DOCUMENT STATUS REPORT ═══",
            f"",
            f"Permit: {permit_id} ({permit.get('project_name', '')})",
            f"Required documents: {len(permit.get('required_document_ids', []))}",
            f"Submitted documents: {len(permit.get('submitted_document_ids', []))}",
            f"Issues found: {len(all_issues)}",
        ]

        if not all_issues:
            lines.append(f"\n✓ All required documents are submitted and valid.")
        else:
            if result.missing_documents:
                lines.append(f"\n── Missing Documents ──")
                for doc in result.missing_documents:
                    lines.append(f"  ✗ [{doc.document_id}] {doc.document_name}")
                    lines.append(f"    Type: {doc.document_type}")
                    lines.append(f"    Action needed: Upload this document")

            if result.invalid_documents:
                lines.append(f"\n── Documents With Issues ──")
                for doc in result.invalid_documents:
                    lines.append(f"  ⚠ [{doc.document_id}] {doc.document_name}")
                    lines.append(f"    Issue: {doc.issue_type.value.replace('_', ' ').title()}")
                    lines.append(f"    Detail: {doc.detail}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 3: search_permit_requirements
    # ------------------------------------------------------------------
    @mcp.tool()
    def search_permit_requirements(
        query: str,
        jurisdiction: Optional[str] = None,
        permit_type: Optional[str] = None,
    ) -> str:
        """Search permit requirement documents using the RAG pipeline.

        This tool uses semantic search (vector similarity) to find the most relevant
        sections of requirement documents for a given natural-language query.
        It does NOT simply keyword-search; it understands the meaning of the query.

        Use this tool when someone asks about specific requirements, code sections,
        compliance rules, or best practices for permit submissions.

        Examples:
        - "What are the HVAC requirements for commercial permits?"
        - "What is the minimum insurance coverage required?"
        - "What does ASHRAE 90.1 require for energy recovery?"

        Args:
            query: A natural language question about permit requirements.
            jurisdiction: Optional jurisdiction filter (e.g., "City of Phoenix").
            permit_type: Optional permit type filter (e.g., "mechanical").

        Returns:
            Relevant requirement excerpts with source citations.
        """
        logger.info(
            "[MCP] Tool: search_permit_requirements | Query: %s | Jurisdiction: %s | Type: %s",
            query[:80], jurisdiction, permit_type,
        )

        try:
            chunks = retriever.retrieve(query, top_k=4)
        except FileNotFoundError as exc:
            return f"Error: {exc}"

        if not chunks:
            return "No relevant requirements found for the given query. Try rephrasing your question."

        lines = [
            f"═══ REQUIREMENT SEARCH RESULTS ═══",
            f"",
            f"Query: \"{query}\"",
        ]
        if jurisdiction:
            lines.append(f"Jurisdiction filter: {jurisdiction}")
        if permit_type:
            lines.append(f"Permit type filter: {permit_type}")
        lines.append(f"Results found: {len(chunks)}")

        for i, chunk in enumerate(chunks, 1):
            lines.append(f"\n── Result {i} (relevance: {chunk.relevance_score:.2f}) ──")
            lines.append(f"Source: {chunk.source}")
            if chunk.section:
                lines.append(f"Section: {chunk.section}")
            if chunk.page:
                lines.append(f"Page: {chunk.page}")
            lines.append(f"")
            # Truncate very long chunks for readability
            text = chunk.text
            if len(text) > 1200:
                text = text[:1200] + " [...]"
            lines.append(text)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 4: explain_permit_blocker
    # ------------------------------------------------------------------
    @mcp.tool()
    def explain_permit_blocker(permit_id: str) -> str:
        """Explain why a permit is blocked or not ready for submission.

        Provides a detailed explanation of the primary blocker and all related
        issues, including supporting evidence from documents, authority comments,
        and applicable requirements. Also provides a recommended fix.

        Use this tool when someone asks: "Why is permit X blocked?",
        "Why can't we submit permit X?", or "What's stopping permit X?"

        Args:
            permit_id: The permit identifier (e.g., "P-1042").

        Returns:
            A detailed blocker explanation with evidence and recommended fixes.
        """
        logger.info("[MCP] Tool: explain_permit_blocker | Permit: %s", permit_id)
        try:
            result = readiness_service.explain_blockers(permit_id)
        except ValueError as exc:
            return f"Error: {exc}"

        lines = [
            f"═══ BLOCKER ANALYSIS ═══",
            f"",
            f"Permit: {result.permit_id} ({result.project_name})",
            f"",
            f"▸ Primary Blocker:",
            f"  {result.primary_blocker}",
        ]

        if result.blocker_details:
            lines.append(f"\n── All Blocking Issues ({len(result.blocker_details)}) ──")
            for i, detail in enumerate(result.blocker_details, 1):
                lines.append(f"  {i}. {detail}")

        if result.supporting_evidence:
            lines.append(f"\n── Supporting Evidence ──")
            for ev in result.supporting_evidence[:5]:
                lines.append(f"  • Source: {ev.source}")
                detail_text = ev.detail[:200] + ("..." if len(ev.detail) > 200 else "")
                lines.append(f"    {detail_text}")
                if ev.reference:
                    lines.append(f"    Ref: {ev.reference}")

        if result.related_authority_comments:
            lines.append(f"\n── Related Authority Comments ──")
            for cmt in result.related_authority_comments:
                lines.append(f"  • {cmt}")

        if result.related_requirements:
            lines.append(f"\n── Related Requirements ──")
            for req in result.related_requirements[:5]:
                lines.append(f"  • {req}")

        lines.append(f"\n▸ Recommended Fix:")
        lines.append(f"  {result.recommended_fix}")
        if result.estimated_effort:
            lines.append(f"\n▸ Estimated Effort: {result.estimated_effort}")

        lines.append(f"\n⚑ Human review required before final submission.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 5: generate_resubmission_checklist
    # ------------------------------------------------------------------
    @mcp.tool()
    def generate_resubmission_checklist(permit_id: str) -> str:
        """Generate a prioritized resubmission checklist for a permit.

        Creates a step-by-step checklist ordered by priority (critical → high →
        medium → low) that the contractor should follow before resubmitting
        the permit application. Each step includes the action, reason, and source.

        Use this tool when someone asks: "What do I need to do to resubmit permit X?",
        "Generate a checklist for permit X", or "How do I fix permit X?"

        Args:
            permit_id: The permit identifier (e.g., "P-1042").

        Returns:
            A prioritized checklist with reasons and evidence sources.
        """
        logger.info("[MCP] Tool: generate_resubmission_checklist | Permit: %s", permit_id)
        try:
            result = readiness_service.generate_checklist(permit_id)
        except ValueError as exc:
            return f"Error: {exc}"

        lines = [
            f"═══ RESUBMISSION CHECKLIST ═══",
            f"",
            f"Permit: {result.permit_id} ({result.project_name})",
            f"Type: {result.permit_type}",
            f"Jurisdiction: {result.jurisdiction}",
            f"Total items: {result.total_items}",
            f"Critical items: {result.critical_items}",
        ]

        current_priority = None
        for item in result.checklist:
            if item.priority != current_priority:
                current_priority = item.priority
                lines.append(f"\n── {current_priority.value.upper()} Priority ──")

            lines.append(f"")
            lines.append(f"  Step {item.step_number}: {item.action}")
            lines.append(f"  Reason: {item.reason[:150]}")
            if item.evidence_source:
                lines.append(f"  Source: {item.evidence_source}")
            if item.notes:
                lines.append(f"  Note: {item.notes}")

        if result.general_notes:
            lines.append(f"\n── General Notes ──")
            for note in result.general_notes:
                lines.append(f"  • {note}")

        lines.append(f"\n⚑ Human review required before final submission.")

        # Auto-export checklist to reports folder
        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / f"{permit_id}_resubmission_checklist.md"
            report_file.write_text(
                f"# 📋 Resubmission Checklist: {result.permit_id}\n\n"
                f"**Project:** {result.project_name}  \n"
                f"**Type:** {result.permit_type}  \n"
                f"**Jurisdiction:** {result.jurisdiction}  \n"
                f"**Total Items:** {result.total_items} ({result.critical_items} Critical)  \n\n"
                + "\n".join(lines),
                encoding="utf-8",
            )
            lines.append(f"\n📁 [SAVED TO FOLDER]: reports/{permit_id}_resubmission_checklist.md")
        except Exception as exc:
            logger.warning("Could not export checklist to file: %s", exc)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 6 (optional): get_permit_status
    # ------------------------------------------------------------------
    @mcp.tool()
    def get_permit_status(permit_id: str) -> str:
        """Get the current status and summary information for a permit.

        Returns basic permit information including project details, submission dates,
        document counts, and inspection status. This is a quick-lookup tool for
        general permit information.

        Use this tool when someone asks: "What is the status of permit X?",
        "Show me permit X details", or "When was permit X submitted?"

        Args:
            permit_id: The permit identifier (e.g., "P-1042").

        Returns:
            A summary of the permit's current status and key information.
        """
        logger.info("[MCP] Tool: get_permit_status | Permit: %s", permit_id)
        permit = permit_service.get_permit(permit_id)
        if not permit:
            return f"Error: Permit '{permit_id}' not found. Please verify the permit ID."

        open_comments = permit_service.get_open_comments(permit_id)

        lines = [
            f"═══ PERMIT STATUS ═══",
            f"",
            f"Permit ID:      {permit['permit_id']}",
            f"Project:        {permit.get('project_name', 'N/A')} ({permit.get('project_id', '')})",
            f"Type:           {permit.get('permit_type', 'N/A')}",
            f"Jurisdiction:   {permit.get('jurisdiction', 'N/A')}",
            f"Status:         {permit.get('status', 'N/A')}",
            f"Submitted:      {permit.get('submission_date', 'Not submitted')}",
            f"Target date:    {permit.get('target_date', 'N/A')}",
            f"Last updated:   {permit.get('last_updated', 'N/A')}",
            f"",
            f"Documents required:  {len(permit.get('required_document_ids', []))}",
            f"Documents submitted: {len(permit.get('submitted_document_ids', []))}",
            f"Open comments:       {len(open_comments)}",
            f"Inspection status:   {permit.get('inspection_status', 'N/A')}",
        ]

        if permit.get("notes"):
            lines.append(f"\nNotes: {permit['notes']}")

        if permit.get("rejection_history"):
            lines.append(f"\n── Rejection History ──")
            for rej in permit["rejection_history"]:
                lines.append(f"  Date: {rej.get('date', 'N/A')}")
                lines.append(f"  Reviewer: {rej.get('reviewer', 'N/A')}")
                lines.append(f"  Reason: {rej.get('reason', 'N/A')}")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 7: update_permit_status
    # ------------------------------------------------------------------
    @mcp.tool()
    def update_permit_status(
        permit_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> str:
        """Update the status of a permit (e.g. 'approved', 'under_review', 'submitted', 'revision_required').

        Use this tool when someone states that a permit's status has changed, when an issue
        has been resolved, or when approving a permit so it is no longer marked at risk.

        Args:
            permit_id: The permit identifier (e.g. "P-1003").
            new_status: The new status string (e.g. "approved", "under_review", "submitted").
            notes: Optional updated notes or resolution remarks.

        Returns:
            Confirmation message of the updated permit status.
        """
        logger.info("[MCP] Tool: update_permit_status | Permit: %s | Status: %s", permit_id, new_status)
        permit = permit_service.update_permit_status(permit_id, new_status, notes=notes)
        if not permit:
            return f"Error: Permit '{permit_id}' not found."

        return (
            f"✓ Permit {permit_id} ({permit.get('project_name', '')}) status successfully updated to '{new_status.upper()}'.\n"
            f"Last updated timestamp: {permit.get('last_updated')}\n"
            f"Notes: {permit.get('notes', 'None')}\n"
            f"Portfolio risk models will reflect this updated status on the next evaluation.\n"
            f"📁 [AUDIT LOG UPDATED]: reports/audit_log.md"
        )

    # ------------------------------------------------------------------
    # Tool 8: resolve_authority_comment
    # ------------------------------------------------------------------
    @mcp.tool()
    def resolve_authority_comment(
        comment_id: str,
        resolution_notes: Optional[str] = None,
    ) -> str:
        """Mark an open AHJ authority comment as resolved.

        Use this tool when the contractor or engineer has addressed an examiner comment,
        clearing the objection so it no longer contributes risk points or blocks readiness.

        Args:
            comment_id: The comment identifier (e.g. "CMT-301", "CMT-302").
            resolution_notes: Optional notes on how the comment was addressed.

        Returns:
            Confirmation message of the resolved comment.
        """
        logger.info("[MCP] Tool: resolve_authority_comment | Comment: %s", comment_id)
        comment = permit_service.resolve_comment(comment_id, resolution_notes=resolution_notes)
        if not comment:
            return f"Error: Authority comment '{comment_id}' not found."

        return (
            f"✓ Authority comment {comment_id} (Permit {comment.get('permit_id')}) has been marked RESOLVED.\n"
            f"Reviewer: {comment.get('reviewer', 'Unknown')}\n"
            f"Original issue: {comment.get('comment', '')[:120]}...\n"
            f"This comment will no longer block readiness or increase portfolio risk.\n"
            f"📁 [AUDIT LOG UPDATED]: reports/audit_log.md"
        )

    # ------------------------------------------------------------------
    # Tool 9: update_document_status
    # ------------------------------------------------------------------
    @mcp.tool()
    def update_document_status(
        document_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> str:
        """Update the status of a submitted blueprint or document (e.g. 'approved', 'rejected', 'revision_required').

        Use this tool when a contractor uploads accepted replacement blueprints,
        structural calculations, or insurance certificates to mark the document approved.

        Args:
            document_id: The document identifier (e.g. "DOC-301", "DOC-302", "DOC-404").
            new_status: The new status string (e.g. "approved", "rejected", "submitted").
            notes: Optional notes regarding the document update.

        Returns:
            Confirmation message of the updated document.
        """
        logger.info("[MCP] Tool: update_document_status | Doc: %s | Status: %s", document_id, new_status)
        doc = permit_service.update_document_status(document_id, new_status, notes=notes)
        if not doc:
            return f"Error: Document '{document_id}' not found."

        return (
            f"✓ Document {document_id} ({doc.get('document_name')}) status updated to '{new_status.upper()}'.\n"
            f"Permit: {doc.get('permit_id')}\n"
            f"📁 [AUDIT LOG UPDATED]: reports/audit_log.md"
        )

    return {
        "check_permit_readiness": check_permit_readiness,
        "find_missing_documents": find_missing_documents,
        "search_permit_requirements": search_permit_requirements,
        "explain_permit_blocker": explain_permit_blocker,
        "generate_resubmission_checklist": generate_resubmission_checklist,
        "get_permit_status": get_permit_status,
        "update_permit_status": update_permit_status,
        "resolve_authority_comment": resolve_authority_comment,
        "update_document_status": update_document_status,
    }


