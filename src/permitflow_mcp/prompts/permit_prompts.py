"""MCP Prompt templates for PermitFlow workflows."""

from __future__ import annotations

import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("permitflow_mcp.prompts.permit_prompts")


def register_prompts(mcp: FastMCP) -> None:
    """Register all MCP prompt templates on the FastMCP server."""

    # ------------------------------------------------------------------
    # Prompt 1: daily_standup_briefing
    # ------------------------------------------------------------------
    @mcp.prompt()
    def daily_standup_briefing() -> str:
        """Prompt to prepare and conduct the daily morning permitting standup meeting.

        Directs the LLM to inspect portfolio priorities, overnight changes, and
        systemic blockers, then formulate a crisp standup agenda with assigned
        owners and actions.
        """
        return (
            "You are the Lead Permitting Operations Manager running today's morning permitting standup.\n\n"
            "Please follow these instructions:\n"
            "1. Call the `get_daily_manager_briefing` tool to retrieve the current portfolio health score, "
            "overnight deltas, systemic bottlenecks, and today's prioritized action matrix.\n"
            "2. Format a crisp, executive standup report structured as follows:\n"
            "   - **Portfolio Health Pulse**: Health score, total active permits, count of critical/blocked items.\n"
            "   - **Overnight Alerts & Changes**: New AHJ comments, status shifts, or newly expired certificates.\n"
            "   - **Today's Mission-Critical Actions**: Bulleted action list with assigned roles (Permit Coordinator, "
            "Structural Engineer, MEP Consultant), target permit, and specific deadline.\n"
            "   - **Systemic Blockers to Address**: Common patterns (e.g. insurance renewals or engineering stamps) "
            "that could delay multiple projects if not mitigated.\n"
            "   - **Next Checkpoint**: When the team should reconvene to verify today's filings.\n\n"
            "Ensure the tone is action-oriented, rigorous, and clearly identifies who owns what today."
        )

    # ------------------------------------------------------------------
    # Prompt 2: permit_readiness_audit
    # ------------------------------------------------------------------
    @mcp.prompt()
    def permit_readiness_audit(permit_id: str) -> str:
        """Prompt for conducting an exhaustive, audit-grade readiness check on a single permit.

        Directs the LLM to verify documents, check applicable requirements, inspect
        open reviewer comments, evaluate inspection milestones, and synthesize a go/no-go recommendation.
        """
        return (
            f"You are a Senior Permitting Specialist conducting an audit-grade readiness review for permit '{permit_id}'.\n\n"
            f"Please execute the following verification steps:\n"
            f"1. Call `check_permit_readiness` for permit '{permit_id}' to retrieve the composite readiness score (0-100), "
            f"status tier, missing/expired documents, and examiner comments.\n"
            f"2. If technical trade requirements are involved (e.g., HVAC, structural, electrical), call `search_permit_requirements` "
            f"to verify applicable local municipal code sections.\n"
            f"3. Synthesize your final audit report with:\n"
            f"   - **Executive Determination**: [GO / NO-GO / CONDITIONAL] with Readiness Score /100.\n"
            f"   - **Document Completeness & Expiry Matrix**: Table of required vs submitted documents with status.\n"
            f"   - **AHJ Reviewer Comments Analysis**: Outstanding examiner comments, severity, and required solutions.\n"
            f"   - **Code & Standards Compliance**: Applicable code citations from requirements documents.\n"
            f"   - **Immediate Action Checklist**: Prioritized steps required before human sign-off and filing.\n\n"
            f"Reminder: Explicitly enforce Human-in-the-Loop review before final submission."
        )

    # ------------------------------------------------------------------
    # Prompt 3: resubmission_strategy
    # ------------------------------------------------------------------
    @mcp.prompt()
    def resubmission_strategy(permit_id: str) -> str:
        """Prompt for crafting a tactical resubmission plan for a rejected or revision-required permit.

        Directs the LLM to create a plan addressing all examiner objections, preparing
        a written response matrix, and establishing a submission timeline.
        """
        return (
            f"You are a Construction Permitting Strategist tasked with resolving blocked/rejected permit '{permit_id}'.\n\n"
            f"Please perform the following analysis:\n"
            f"1. Call `generate_formal_ahj_response_packet` for permit '{permit_id}' to generate the official formal response letter, "
            f"comment-by-comment response matrix, and resubmission checklist.\n"
            f"2. Call `check_permit_readiness` for permit '{permit_id}' to verify all supporting documents and blockers.\n"
            f"3. Formulate an end-to-end Resubmission Strategy Package including:\n"
            f"   - **Root Cause Deconstruction**: Why the application was rejected or returned for revision.\n"
            f"   - **Written Comment-by-Comment Response Matrix**: Proposed responses to each plans examiner comment "
            f"explaining exactly how drawings or documents were modified.\n"
            f"   - **Drawing Revision Guidance**: Details on revision clouding, delta numbering, and engineer stamps.\n"
            f"   - **Resubmission Sequence & Timeline**: Step-by-step checklist ordered by dependency and priority.\n"
            f"   - **Risk Mitigation**: Precautions to ensure the permit is approved on this resubmission cycle without a 3rd round.\n\n"
            f"Ensure the strategy is professional, thorough, and ready to share with project executives and subcontractors."
        )

    # ------------------------------------------------------------------
    # Prompt 4: portfolio_risk_review
    # ------------------------------------------------------------------
    @mcp.prompt()
    def portfolio_risk_review(jurisdiction: Optional[str] = None) -> str:
        """Prompt for leadership-level quarterly/monthly permit portfolio risk review.

        Directs the LLM to evaluate all permits, surface systemic bottlenecks, detect
        schedule slippages, and recommend strategic operational improvements.
        """
        jurisdiction_filter_clause = f" for jurisdiction '{jurisdiction}'" if jurisdiction else ""
        return (
            f"You are the Director of Pre-Construction and Permitting delivering a Portfolio Risk Evaluation{jurisdiction_filter_clause}.\n\n"
            f"Please execute the following tasks:\n"
            f"1. Call `get_daily_manager_briefing` to inspect current portfolio health, overnight transitions, and immediate action tasks.\n"
            f"2. Inspect portfolio resources (`portfolio://summary` and `portfolio://priorities`) to evaluate risk tiers across all active permits.\n"
            f"3. Prepare a high-level Strategic Briefing covering:\n"
            f"   - **Portfolio Risk Distribution**: Tier breakdown (Critical, High, Medium, Low) and schedule exposure.\n"
            f"   - **Deep Dive on Top Critical Permits**: Specific blockers, target dates, and intervention plans.\n"
            f"   - **Systemic Bottleneck Diagnosis**: Cross-cutting issues (e.g. insurance lapses, structural stamps, energy models) "
            f"and their portfolio-wide cost/time impact.\n"
            f"   - **Process & Policy Recommendations**: Strategic changes to standard operating procedures to eliminate recurring rejections.\n"
            f"   - **Executive Action Roadmap**: Next 30-day milestones and leadership decisions needed.\n\n"
            f"Maintain an executive, high-impact tone suitable for construction developers and project executives."
        )
