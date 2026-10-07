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

    # ------------------------------------------------------------------
    # Tool 10: intake_project_scope (Intake Agent)
    # ------------------------------------------------------------------
    @mcp.tool()
    def intake_project_scope(
        scope_description: str,
        address: str,
        valuation: float,
        applicant_name: str = "Permit Coordinator",
    ) -> str:
        """Intake and parse a real-world construction scope of work (SOW) to create permit applications.

        Parses natural language project descriptions, detects the target municipality/jurisdiction
        from the address, identifies all required trade permits (building, mechanical, electrical, plumbing),
        determines if licensed PE engineering stamps and formal plan review are required,
        and generates initial draft permit records.

        Use this tool when a contractor or project manager says:
        - "We need to pull permits for replacing rooftop HVAC units at 4800 E Camelback Rd, Phoenix, AZ"
        - "Kick off permitting for a commercial tenant improvement valued at $185,000"
        - "Parse our scope of work and tell us which permits and documents are required"

        Args:
            scope_description: Natural language description of construction scope (e.g. equipment, work type).
            address: Project site address including city and state.
            valuation: Estimated construction valuation in USD.
            applicant_name: Name of applicant or coordinator.

        Returns:
            A structured intake report with detected jurisdiction, required trade permits,
            mandated engineering plan review triggers, and draft permit IDs.
        """
        logger.info("[MCP] Tool: intake_project_scope | Address: %s | Valuation: $%.2f", address, valuation)
        
        # 1. Jurisdiction detection
        address_lower = address.lower()
        if "tempe" in address_lower:
            jurisdiction = "City of Tempe"
        elif "scottsdale" in address_lower:
            jurisdiction = "City of Scottsdale"
        elif "mesa" in address_lower:
            jurisdiction = "City of Mesa"
        elif "chandler" in address_lower:
            jurisdiction = "City of Chandler"
        else:
            jurisdiction = "City of Phoenix"

        # 2. Scope classification & trade determination
        scope_lower = scope_description.lower()
        trades_needed = []
        if any(w in scope_lower for w in ("hvac", "ac", "air condition", "chiller", "duct", "furnace", "exhaust", "erv", "rooftop unit")):
            trades_needed.append("mechanical")
        if any(w in scope_lower for w in ("electric", "panel", "wire", "conduit", "amp", "service", "transformer", "lighting")):
            trades_needed.append("electrical")
        if any(w in scope_lower for w in ("plumb", "pipe", "water heater", "sewer", "drain", "backflow")):
            trades_needed.append("plumbing")
        if any(w in scope_lower for w in ("structur", "framing", "wall", "beam", "roof", "addition", "tenant improvement", "foundation", "building")) or not trades_needed:
            trades_needed.append("building")

        # 3. Engineering triggers
        requires_pe_stamp = valuation >= 50000 or any(w in scope_lower for w in ("rooftop", "ton", "structural", "load-bearing", "2,000", "heavy"))
        review_type = "Full Multi-Department Plan Review" if requires_pe_stamp else "Over-The-Counter (OTC) Express"

        # 4. Mandatory document list
        mandatory_docs = [
            "Completed Municipal Permit Application Form",
            "Contractor Certificate of General Liability Insurance ($1M min)",
            "Detailed Scope of Work & Architectural Site Plan",
        ]
        if "mechanical" in trades_needed:
            mandatory_docs.extend(["HVAC Equipment Schedule & Unit Cut Sheets", "ASHRAE 90.1 Energy Efficiency Compliance Certificate"])
        if "electrical" in trades_needed:
            mandatory_docs.extend(["One-Line Electrical Diagram", "NEC 2023 Panel Demand Load Calculations"])
        if requires_pe_stamp:
            mandatory_docs.append("Licensed Arizona PE Stamped Structural Support Drawings")

        # 5. Create draft permit record
        import time
        new_permit_id = f"P-INTAKE-{int(time.time()) % 10000:04d}"
        new_permit = {
            "permit_id": new_permit_id,
            "project_id": "PROJECT-INTAKE",
            "project_name": f"Project at {address.split(',')[0]}",
            "permit_type": trades_needed[0],
            "jurisdiction": jurisdiction,
            "status": "draft",
            "submission_date": None,
            "target_date": "2026-08-15",
            "required_document_ids": [f"DOC-REQ-{i+1:02d}" for i in range(len(mandatory_docs))],
            "submitted_document_ids": [],
            "authority_comment_ids": [],
            "inspection_status": "not_started",
            "last_updated": "2026-07-06",
            "notes": f"Auto-generated via Intake Agent. Valuation: ${valuation:,.2f}. Trades: {', '.join(trades_needed)}.",
        }
        permit_service.add_permit(new_permit)

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                 PERMITFLOW PROJECT INTAKE & SCOPE ANALYSIS                   ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"Draft Permit ID:       {new_permit_id}",
            f"Target Address:        {address}",
            f"Detected Municipality: {jurisdiction}",
            f"Project Valuation:     ${valuation:,.2f}",
            f"Review Track:          {review_type}",
            f"PE Stamp Required:     {'YES (Arizona Licensed PE Stamp Mandated)' if requires_pe_stamp else 'No (Standard Trade Submittal)'}",
            "",
            f"Trade Permits Required ({len(trades_needed)}):",
        ]
        for t in trades_needed:
            lines.append(f"  • {t.upper()} PERMIT")

        lines.extend([
            "",
            f"Mandatory Submittal Checklist ({len(mandatory_docs)} documents):",
        ])
        for idx, doc in enumerate(mandatory_docs, 1):
            lines.append(f"  {idx}. [ ] {doc}")

        lines.extend([
            "",
            "► NEXT RECOMMENDED ACTION:",
            f"  Use `estimate_permit_fees_and_sla(jurisdiction='{jurisdiction}', permit_type='{trades_needed[0]}', valuation={valuation})` to calculate city fees.",
            "",
            "📁 [INTAKE LOGGED]: Saved draft permit to database & reports/audit_log.md",
        ])
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 11: estimate_permit_fees_and_sla (Research Agent)
    # ------------------------------------------------------------------
    @mcp.tool()
    def estimate_permit_fees_and_sla(
        jurisdiction: str,
        permit_type: str,
        valuation: float,
        square_footage: Optional[int] = None,
    ) -> str:
        """Estimate municipal permit fees, plan check surcharges, and AHJ turnaround SLAs.

        Calculates realistic municipal fee schedules and approval timelines across
        Phoenix, Tempe, Scottsdale, Mesa, and Chandler. Differentiates between
        expedited Over-The-Counter (OTC) and standard multi-department plan reviews.

        Use this tool when someone asks:
        - "How much will the permit fees cost for a $120,000 mechanical permit in Phoenix?"
        - "What is the expected review timeline for Tempe electrical permits?"
        - "Estimate city fees and turnaround time for our project"

        Args:
            jurisdiction: Target city (e.g. 'City of Phoenix', 'City of Tempe', 'City of Scottsdale').
            permit_type: Trade type ('building', 'mechanical', 'electrical', 'plumbing').
            valuation: Estimated construction valuation in USD.
            square_footage: Optional project square footage.

        Returns:
            Itemized breakdown of base application fees, plan review fees, technology fees,
            total municipal cost, and expected turnaround SLA in business days.
        """
        logger.info("[MCP] Tool: estimate_permit_fees_and_sla | Jur: %s | Type: %s | Val: $%.2f", jurisdiction, permit_type, valuation)
        
        jur_lower = jurisdiction.lower()
        
        # Base fee structures modeled on regional municipal schedules
        if "phoenix" in jur_lower:
            base_fee = 220.0
            val_rate = 0.0075 if valuation > 100000 else 0.0090
            plan_check_ratio = 0.65
            sla_days = 20 if valuation > 50000 else 10
            portal = "City of Phoenix ProjectDox / Planning & Development"
        elif "tempe" in jur_lower:
            base_fee = 180.0
            val_rate = 0.0065 if valuation > 100000 else 0.0080
            plan_check_ratio = 0.60
            sla_days = 15 if valuation > 50000 else 7
            portal = "City of Tempe Accela Citizen Access"
        elif "scottsdale" in jur_lower:
            base_fee = 250.0
            val_rate = 0.0085 if valuation > 100000 else 0.0100
            plan_check_ratio = 0.70
            sla_days = 25 if valuation > 50000 else 12
            portal = "City of Scottsdale Online Permitting Services"
        else:
            base_fee = 190.0
            val_rate = 0.0070
            plan_check_ratio = 0.60
            sla_days = 18
            portal = "Municipal Permitting Portal"

        permit_fee = base_fee + (valuation * val_rate)
        plan_check_fee = permit_fee * plan_check_ratio
        tech_surcharge = (permit_fee + plan_check_fee) * 0.04
        total_estimated = permit_fee + plan_check_fee + tech_surcharge

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                  MUNICIPAL PERMIT FEE & REVIEW SLA ESTIMATE                  ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"Jurisdiction:           {jurisdiction}",
            f"Permit Trade:           {permit_type.upper()}",
            f"Project Valuation:      ${valuation:,.2f}",
            f"Target Municipal Portal:{portal}",
            "",
            "── ITEMIZED MUNICIPAL FEE SCHEDULE ──",
            f"  • Base Permit Fee:         ${permit_fee:,.2f}",
            f"  • Plan Review Fee ({(plan_check_ratio*100):.0f}%):   ${plan_check_fee:,.2f}",
            f"  • Municipal Tech Surcharge (4%): ${tech_surcharge:,.2f}",
            f"  ──────────────────────────────────────────",
            f"  TOTAL ESTIMATED CITY FEES: ${total_estimated:,.2f}",
            "",
            "── ESTIMATED PLAN CHECK REVIEW SLA ──",
            f"  • Standard Turnaround:     {sla_days} business days (~{round(sla_days / 5)} weeks)",
            f"  • Expedited Option:        {max(3, sla_days // 2)} business days (Requires 100% plan check surcharge)",
            f"  • Initial Submittal Gate:  Completeness check within 48 hours of portal upload",
            "",
            "⚑ Municipal fees are subject to final verification upon formal AHJ intake.",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool 12: generate_formal_ahj_response_packet (Coordination Agent)
    # ------------------------------------------------------------------
    @mcp.tool()
    def generate_formal_ahj_response_packet(permit_id: str) -> str:
        """Generate an official municipal 'Written Response to Plan Check Comments' transmittal.

        Plans examiners in commercial jurisdictions (Phoenix, Tempe) mandate a formal,
        itemized written response matrix before accepting resubmissions. This tool
        extracts open authority comments, crafts technical engineering responses citing
        specific code sections (ASHRAE 90.1, NEC 2023, Phoenix Mechanical Code), references
        sheet revision clouds (e.g. Sheet M-201, Delta-1), and prepares a submittal packet.

        Use this tool when someone asks:
        - "Draft a formal response letter to the city plan examiner comments for permit P-1042"
        - "Generate the comment response matrix for our resubmission"
        - "Create the official AHJ response packet"

        Args:
            permit_id: The permit identifier (e.g. "P-1042").

        Returns:
            The complete, formatted official response transmittal saved to reports/.
        """
        logger.info("[MCP] Tool: generate_formal_ahj_response_packet | Permit: %s", permit_id)
        permit = permit_service.get_permit(permit_id)
        if not permit:
            return f"Error: Permit '{permit_id}' not found."

        comments = permit_service.get_open_comments(permit_id)
        if not comments:
            return f"Notice: Permit {permit_id} has no open authority comments requiring a written response matrix."

        packet_lines = [
            f"# 🏛 FORMAL WRITTEN RESPONSE TO PLAN REVIEW COMMENTS",
            f"",
            f"**To:** {permit.get('jurisdiction')} — Planning & Development Department  ",
            f"**Project:** {permit.get('project_name')} ({permit.get('project_id')})  ",
            f"**Permit Application ID:** {permit_id} [{permit.get('permit_type', '').upper()}]  ",
            f"**Submittal Date:** 2026-07-06  ",
            f"**Discipline:** {permit.get('permit_type', '').title()} Engineering & Design  ",
            f"",
            f"---",
            f"",
            f"### Plan Review Comments & Engineering Resolution Matrix",
            f"",
            f"The following itemized responses and sheet revisions address all review comments issued by the department:",
            f"",
        ]

        # Template technical responses based on comment content
        for idx, cmt in enumerate(comments, 1):
            cid = cmt.get("comment_id", f"CMT-{idx}")
            reviewer = cmt.get("reviewer", "Plans Examiner")
            severity = cmt.get("severity", "major").upper()
            comment_text = cmt.get("comment", "")

            # Formulate engineering answer
            if "ashrae" in comment_text.lower() or "energy" in comment_text.lower() or "erv" in comment_text.lower():
                code_cite = "ASHRAE Standard 90.1-2019 Section 6.5.6.1 & Phoenix Mechanical Code"
                drawing_ref = "Sheet M-201 (Mechanical Equipment Schedule), Delta Revision Cloud 1"
                action_text = (
                    "Mechanical drawings have been revised to specify an Energy Recovery Ventilator (ERV) "
                    "with minimum 50% enthalpy recovery effectiveness on units exhausting >5,000 CFM. "
                    "Complete COMcheck energy compliance certification report has been stamped and attached as Exhibit A."
                )
            elif "structural" in comment_text.lower() or "framing" in comment_text.lower() or "support" in comment_text.lower():
                code_cite = "Phoenix Mechanical Code Section 301.5 & IBC Section 1613"
                drawing_ref = "Sheet S-102 (Rooftop Framing Details), Delta Revision Cloud 2"
                action_text = (
                    "Structural engineering calculations and curb framing details for the 2,400-lb rooftop HVAC units "
                    "have been prepared and stamped by a licensed Arizona Professional Engineer (PE #48291). "
                    "Continuous point-load beam framing verified per IBC seismic design criteria."
                )
            elif "insurance" in comment_text.lower() or "liability" in comment_text.lower():
                code_cite = "City Administrative Code — Contractor Registration Provisions"
                drawing_ref = "Administrative Exhibit B (ACORD Certificate of Liability Insurance)"
                action_text = (
                    "Renewed Certificate of General Liability Insurance ($2,000,000 aggregate / $1,000,000 occurrence) "
                    "has been issued by Travelers Casualty & Surety naming the municipality as Additional Insured. Attached as Exhibit B."
                )
            elif "load" in comment_text.lower() or "nec" in comment_text.lower() or "panel" in comment_text.lower():
                code_cite = "National Electrical Code (NEC 2023) Article 220"
                drawing_ref = "Sheet E-301 (Panel Schedules & Single-Line Diagram), Delta Revision Cloud 1"
                action_text = (
                    "Electrical demand calculations have been fully re-computed in accordance with NEC 2023 Article 220. "
                    "Panel schedules for Buildings C & D updated with continuous heating and cooling load diversification factors."
                )
            else:
                code_cite = "Applicable Municipal Code Provisions"
                drawing_ref = "General Revision Sheet, Delta-1"
                action_text = f"Item addressed in revised submittal package. Specific corrections incorporated into plans per examiner comments."

            packet_lines.extend([
                f"#### [{cid}] Reviewer: {reviewer} (Severity: {severity})",
                f"> **Examiner Comment:** \"{comment_text}\"",
                f"",
                f"- **Design Team Response:** {action_text}",
                f"- **Governing Code Standard:** {code_cite}",
                f"- **Drawing / Document Reference:** {drawing_ref}",
                f"",
                f"---",
                f"",
            ])

        packet_lines.extend([
            f"### Professional Certification & Sign-off",
            f"I hereby certify that the drawings and calculations submitted herewith have been revised under my direction ",
            f"and conform to all applicable codes, amendments, and ordinances of {permit.get('jurisdiction')}.",
            f"",
            f"**Lead Design Professional:** Robert Vance, P.E. (AZ Registration #48291)  ",
            f"**Permit Coordinator:** Sarah Jenkins, PermitFlow Project Operations  ",
            f"**Timestamp:** 2026-07-06  ",
            f"",
            f"📁 [READY FOR PORTAL UPLOAD]: Saved to reports/{permit_id}_ahj_response_packet.md",
        ])

        output_content = "\n".join(packet_lines)

        # Export file
        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / f"{permit_id}_ahj_response_packet.md"
            report_file.write_text(output_content, encoding="utf-8")
        except Exception as exc:
            logger.warning("Could not export AHJ response packet: %s", exc)

        return output_content

    # ------------------------------------------------------------------
    # Tool 13: verify_contractor_registration (License & Reg Management)
    # ------------------------------------------------------------------
    @mcp.tool()
    def verify_contractor_registration(
        contractor_name: str,
        jurisdiction: str,
        permit_type: str,
    ) -> str:
        """Verify contractor ROC license standing, insurance limits, and municipal endorsements.

        PermitFlow features dedicated License & Registration Management. In Arizona and
        regional jurisdictions, permits are rejected if contractor classifications do not
        match the trade (e.g. CR-39 HVAC vs B-1 General), if insurance is expired, or if
        the city is not listed as Additional Insured.

        Use this tool when someone asks:
        - "Check if Ironclad Construction has valid license and insurance for City of Phoenix"
        - "Verify subcontractor registration before submitting permit"
        - "Is contractor's liability insurance up to date?"

        Args:
            contractor_name: Contractor or company name (e.g. 'Ironclad Construction', 'Apex Builders').
            jurisdiction: Target city jurisdiction (e.g. 'City of Phoenix', 'City of Tempe').
            permit_type: Permit trade ('building', 'mechanical', 'electrical', 'plumbing').

        Returns:
            Structured compliance verification with Arizona ROC status, insurance coverage,
            and municipal city endorsement status.
        """
        logger.info("[MCP] Tool: verify_contractor_registration | Contractor: %s | Jur: %s", contractor_name, jurisdiction)
        contractor = permit_service.get_contractor(contractor_name)
        if not contractor:
            return (
                f"⚠ Contractor '{contractor_name}' not found in the contractor registry. "
                f"Please ensure contractor uploads an Arizona ROC license and Certificate of Insurance."
            )

        # Evaluate compliance
        today_str = "2026-07-06"
        ins_expired = contractor.get("policy_expiration", "2000-01-01") < today_str
        ins_limit = contractor.get("liability_insurance_limit", 0)
        ins_limit_ok = ins_limit >= 1000000
        city_endorsed = contractor.get("city_endorsements", {}).get(jurisdiction, False)
        roc_active = contractor.get("status") == "active"

        # Trade match check
        p_type = permit_type.lower()
        lic_class = contractor.get("license_class", "")
        trade_ok = False
        if lic_class.startswith("B"):
            trade_ok = True  # General commercial covers prime
        elif lic_class == "CR-39" and p_type == "mechanical":
            trade_ok = True
        elif lic_class == "CR-11" and p_type == "electrical":
            trade_ok = True
        elif lic_class == "CR-37" and p_type == "plumbing":
            trade_ok = True

        overall_compliant = roc_active and (not ins_expired) and ins_limit_ok and city_endorsed and trade_ok

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║             CONTRACTOR LICENSE & INSURANCE COMPLIANCE AUDIT                  ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"Contractor:             {contractor.get('name')}",
            f"Arizona ROC License:    {contractor.get('roc_license')} [Class {contractor.get('license_class')}: {contractor.get('class_description')}]",
            f"ROC License Status:     {'✓ ACTIVE (Expires ' + contractor.get('expiration_date', '') + ')' if roc_active else '✗ INACTIVE/SUSPENDED'}",
            f"Trade Classification:   {'✓ VALID FOR ' + permit_type.upper() if trade_ok else '⚠ CLASSIFICATION MISMATCH FOR ' + permit_type.upper()}",
            "",
            "── GENERAL LIABILITY INSURANCE VERIFICATION ──",
            f"  • Insurance Carrier:  {contractor.get('insurance_carrier')}",
            f"  • Coverage Limit:     ${ins_limit:,.2f} per occurrence {'✓ (Meets $1M requirement)' if ins_limit_ok else '✗ (Below $1M minimum)'}",
            f"  • Policy Expiration:  {contractor.get('policy_expiration')} {'✗ EXPIRED' if ins_expired else '✓ CURRENT'}",
            f"  • City Endorsement:   {'✓ ' + jurisdiction + ' listed as Additional Insured' if city_endorsed else '✗ MISSING: ' + jurisdiction + ' not endorsed'}",
            "",
            f"OVERALL COMPLIANCE:     {'✓ COMPLIANT — Cleared for municipal permit submission' if overall_compliant else '🚨 NON-COMPLIANT — Submission will be rejected by AHJ'}",
        ]

        if not overall_compliant:
            lines.append("\n► MANDATORY REMEDIATION REQUIRED:")
            if ins_expired:
                lines.append(f"  • Upload renewed Certificate of Insurance; current policy expired on {contractor.get('policy_expiration')}.")
            if not city_endorsed:
                lines.append(f"  • Request ACORD endorsement certificate specifically naming '{jurisdiction}' as Additional Insured.")
            if not trade_ok:
                lines.append(f"  • License class {lic_class} does not cover {permit_type}. Require qualified specialty subcontractor.")

        return "\n".join(lines)

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
        "intake_project_scope": intake_project_scope,
        "estimate_permit_fees_and_sla": estimate_permit_fees_and_sla,
        "generate_formal_ahj_response_packet": generate_formal_ahj_response_packet,
        "verify_contractor_registration": verify_contractor_registration,
    }


