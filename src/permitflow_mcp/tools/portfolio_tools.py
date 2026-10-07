"""MCP tools for Portfolio-Level Intelligence.

Exposes tools that analyze all permits together:
1. analyze_portfolio_priorities – Rank permits by risk with evidence and next steps.
2. get_daily_manager_briefing – Daily prioritized executive action plan and health metrics.
3. detect_portfolio_changes – Day-over-day changes, status transitions, and new comments.
4. analyze_systemic_bottlenecks – Common bottlenecks affecting multiple permits across projects.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

from mcp.server.fastmcp import FastMCP

from permitflow_mcp.config import settings
from permitflow_mcp.services.portfolio_service import PortfolioService

logger = logging.getLogger("permitflow_mcp.tools.portfolio_tools")


def register_portfolio_tools(
    mcp: FastMCP,
    portfolio_service: PortfolioService,
) -> dict[str, Any]:
    """Register all Portfolio-Level Intelligence MCP tools and return tool map."""

    # ------------------------------------------------------------------
    # Tool: analyze_portfolio_priorities
    # ------------------------------------------------------------------
    @mcp.tool()
    def analyze_portfolio_priorities(
        limit: int = 10,
        jurisdiction: Optional[str] = None,
    ) -> str:
        """Analyze all permits in the portfolio and rank them by risk and urgency.

        Instead of checking one permit at a time, this tool performs portfolio-wide
        risk scoring and answers: "Which permits need attention first, why, and what
        should I do?"

        Evaluates deadline proximity, critical/major AHJ comments, missing or
        expired documents, inspection hurdles, and historical rejection records.
        For each permit, explains exactly why it received its priority with supporting
        evidence and the single most critical immediate action to take.

        Args:
            limit: Maximum number of ranked permits to return (default: 10).
            jurisdiction: Optional filter by jurisdiction (e.g., "City of Phoenix", "City of Tempe").

        Returns:
            A formatted executive portfolio priority report with ranked permits,
            risk scores, primary drivers, detailed factors, and immediate actions.
        """
        logger.info("[MCP] Tool: analyze_portfolio_priorities | limit=%d | jurisdiction=%s", limit, jurisdiction)
        report = portfolio_service.rank_permits(limit=limit, jurisdiction=jurisdiction)

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                 PERMITFLOW PORTFOLIO RISK & PRIORITY RANKING                 ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"As of:              {report.generated_at}",
            f"Permits Analyzed:   {report.total_permits_analyzed}",
            f"Risk Breakdown:     🚨 CRITICAL: {report.critical_count} | ⚠ HIGH: {report.high_count} | ℹ MEDIUM: {report.medium_count} | ✓ LOW: {report.low_count}",
            "",
            f"Executive Summary:  {report.executive_summary}",
            "",
            "──────────────────────────────────────────────────────────────────────────────",
            "RANKED PERMIT ACTION HIERARCHY",
            "──────────────────────────────────────────────────────────────────────────────",
        ]

        for item in report.ranked_permits:
            tier_badge = {
                "CRITICAL": "🚨 [CRITICAL RISK]",
                "HIGH": "⚠ [HIGH RISK]",
                "MEDIUM": "ℹ [MEDIUM RISK]",
                "LOW": "✓ [LOW RISK / STABLE]",
            }.get(item.risk_tier.value, item.risk_tier.value)

            deadline_text = item.target_date or "N/A"
            if item.days_until_deadline is not None:
                if item.days_until_deadline < 0:
                    deadline_text += f" (OVERDUE by {abs(item.days_until_deadline)} days)"
                elif item.days_until_deadline == 0:
                    deadline_text += " (DUE TODAY)"
                else:
                    deadline_text += f" ({item.days_until_deadline} days remaining)"

            lines.extend([
                "",
                f"#{item.rank} │ {item.permit_id} — {item.project_name} [{item.permit_type.upper()}]",
                f"   Status:       {item.status.upper()} | Jurisdiction: {item.jurisdiction}",
                f"   Risk Score:   {item.risk_score}/100 ➔ {tier_badge}",
                f"   Target Date:  {deadline_text}",
                f"   Key Drivers:  {', '.join(item.primary_risk_drivers)}",
                f"   ► NEXT STEP:  {item.recommended_first_step}",
            ])

            if item.factors:
                lines.append("   Risk Evidence & Factors:")
                for f in item.factors:
                    lines.append(f"     • (+{f.impact_points} pts) {f.factor_name}: {f.detail}")
                    if f.evidence:
                        lines.append(f"       [Evidence: {f.evidence.source} — \"{f.evidence.detail[:90]}...\"]")

        lines.extend([
            "",
            "──────────────────────────────────────────────────────────────────────────────",
            "⚑ Human review and coordinator sign-off required prior to filing resubmissions.",
        ])

        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / "portfolio_risk_ranking.md"
            report_file.write_text(
                f"# 🚨 PermitFlow Portfolio Risk & Priority Ranking\n\n"
                f"**Generated:** {report.generated_at}  \n"
                f"**Permits Evaluated:** {report.total_permits_analyzed}  \n"
                f"**Summary:** {report.executive_summary}  \n\n"
                + "\n".join(lines),
                encoding="utf-8",
            )
            lines.append("\n📁 [SAVED TO FOLDER]: reports/portfolio_risk_ranking.md")
        except Exception as exc:
            logger.warning("Could not export risk ranking to file: %s", exc)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool: get_daily_manager_briefing
    # ------------------------------------------------------------------
    @mcp.tool()
    def get_daily_manager_briefing() -> str:
        """Generate the daily executive briefing and prioritized action list for permit managers.

        Synthesizes portfolio health, overnight changes, critical systemic bottlenecks,
        and provides an itemized task matrix with assigned roles, deadlines, and
        exact steps to unblock delayed permits.

        Use this tool during morning standups or management planning sessions when asked:
        "Give me today's permit briefing", "What should the team work on today?", or
        "What are our top permitting priorities?"

        Returns:
            A comprehensive daily briefing with portfolio health score, key changes,
            and an itemized action task list.
        """
        logger.info("[MCP] Tool: get_daily_manager_briefing")
        briefing = portfolio_service.get_daily_briefing()

        health_bar = "█" * (briefing.portfolio_health_score // 10) + "░" * (10 - briefing.portfolio_health_score // 10)

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                  PERMITFLOW DAILY MANAGER EXECUTIVE BRIEFING                 ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"Date:                   {briefing.briefing_date}",
            f"Portfolio Health Score: {briefing.portfolio_health_score}/100 [{health_bar}]",
            f"Active Permits:         {briefing.total_active_permits}",
            f"Requiring Attention:    {briefing.permits_needing_immediate_attention} permits (Critical + High)",
            "",
            f"Executive Overview:     {briefing.executive_summary}",
            "",
            "─── KEY CHANGES SINCE YESTERDAY ───",
        ]

        if briefing.key_changes_since_yesterday:
            for change in briefing.key_changes_since_yesterday:
                lines.append(f"  • {change}")
        else:
            lines.append("  • No major overnight changes detected.")

        lines.extend([
            "",
            "─── TOP SYSTEMIC PORTFOLIO BOTTLENECKS ───",
        ])
        for b in briefing.top_systemic_bottlenecks:
            lines.append(f"  ⚠ {b}")

        lines.extend([
            "",
            "─── TODAY'S PRIORITIZED ACTION TASK MATRIX ───",
        ])

        current_urgency = None
        for task in briefing.top_actions_today:
            if task.urgency != current_urgency:
                current_urgency = task.urgency
                lines.append(f"\n▶ [{current_urgency.upper()}]")

            lines.extend([
                f"  [{task.priority_rank}] {task.task_id} │ Permit: {task.permit_id} ({task.project_name})",
                f"      Action:   {task.action}",
                f"      Owner:    {task.assigned_role} | Due: {task.deadline or 'ASAP'}",
                f"      Blocker:  {task.blocking_factor}",
                f"      Why:      {task.rationale}",
            ])

        lines.extend([
            "",
            "──────────────────────────────────────────────────────────────────────────────",
            "⚑ All permit resubmissions require human review before final submittal.",
        ])

        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / "daily_manager_briefing.md"
            report_file.write_text(
                f"# 📊 PermitFlow Daily Executive Briefing\n\n"
                f"**Date:** {briefing.briefing_date}  \n"
                f"**Portfolio Health Score:** {briefing.portfolio_health_score}/100  \n"
                f"**Requiring Attention:** {briefing.permits_needing_immediate_attention} permits  \n\n"
                + "\n".join(lines),
                encoding="utf-8",
            )
            lines.append("\n📁 [SAVED TO FOLDER]: reports/daily_manager_briefing.md")
        except Exception as exc:
            logger.warning("Could not export daily briefing to file: %s", exc)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool: detect_portfolio_changes
    # ------------------------------------------------------------------
    @mcp.tool()
    def detect_portfolio_changes(since_date: Optional[str] = None) -> str:
        """Detect what changed across the permit portfolio since yesterday or a specified date.

        Identifies:
        - Permit status transitions (e.g., under_review ➔ revision_required, or draft ➔ submitted)
        - Newly received AHJ authority comments from plans examiners
        - Newly expired contractor insurance or licenses
        - Inspection updates and new inspection appointments
        - Newly introduced submission blockers

        Use this tool when someone asks: "What changed in our permits since yesterday?",
        "Any updates overnight?", or "What comments came in recently?"

        Args:
            since_date: Optional ISO date string (default: previous day snapshot).

        Returns:
            A detailed day-over-day change report categorized by severity and event type.
        """
        logger.info("[MCP] Tool: detect_portfolio_changes | since_date=%s", since_date)
        report = portfolio_service.detect_changes(since_date=since_date)

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                    PORTFOLIO DAY-OVER-DAY CHANGE REPORT                      ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"Compared Snapshot:  {report.compared_date}",
            f"Current Analysis:   {report.current_date}",
            f"Total Changes:      {report.total_changes}",
            "",
            f"Summary: {report.summary}",
            "",
            "─── ITEMIZED PORTFOLIO DELTAS ───",
        ]

        if not report.changes:
            lines.append("✓ No changes detected since previous snapshot.")
        else:
            for idx, ch in enumerate(report.changes, 1):
                sev_icon = {
                    "critical": "🚨 [CRITICAL]",
                    "high": "⚠ [HIGH]",
                    "medium": "ℹ [MEDIUM]",
                    "low": "• [LOW]",
                }.get(ch.severity.lower(), "•")

                lines.extend([
                    f"\n{idx}. {sev_icon} {ch.title}",
                    f"   Permit:    {ch.permit_id} ({ch.project_name})",
                    f"   Category:  {ch.change_type.value.replace('_', ' ').title()}",
                    f"   Detail:    {ch.detail}",
                ])

        try:
            reports_dir = Path(settings.reports_dir)
            reports_dir.mkdir(parents=True, exist_ok=True)
            report_file = reports_dir / "overnight_change_report.md"
            report_file.write_text(
                f"# 🔄 PermitFlow Overnight Change Report\n\n"
                f"**Compared Snapshot:** {report.compared_date}  \n"
                f"**Current Date:** {report.current_date}  \n"
                f"**Total Changes:** {report.total_changes}  \n\n"
                + "\n".join(lines),
                encoding="utf-8",
            )
            lines.append("\n📁 [SAVED TO FOLDER]: reports/overnight_change_report.md")
        except Exception as exc:
            logger.warning("Could not export change report to file: %s", exc)

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool: analyze_systemic_bottlenecks
    # ------------------------------------------------------------------
    @mcp.tool()
    def analyze_systemic_bottlenecks() -> str:
        """Identify systemic problems and cross-cutting bottlenecks affecting multiple permits.

        Analyzes repetitive patterns across the entire project portfolio to answer:
        "Are we repeatedly failing on the same documents or requirements?"
        "Which jurisdictions or reviewer requirements cause the most friction?"

        Detects patterns such as:
        - Common missing/expired document types (e.g. general liability insurance certificates)
        - Regional engineering code bottlenecks (e.g. ASHRAE 90.1 energy modeling, NEC load calculations)
        - Equipment support engineering requirements (e.g. stamped PE rooftop support calculations)
        - Multi-agency review bottlenecks

        Returns:
            A systemic bottleneck report with prevalence statistics, root-cause analyses,
            and portfolio-wide preventive recommendations.
        """
        logger.info("[MCP] Tool: analyze_systemic_bottlenecks")
        report = portfolio_service.identify_systemic_bottlenecks()

        lines = [
            "╔══════════════════════════════════════════════════════════════════════════════╗",
            "║                  PORTFOLIO SYSTEMIC BOTTLENECKS ANALYSIS                     ║",
            "╚══════════════════════════════════════════════════════════════════════════════╝",
            "",
            f"Permits Evaluated:  {report.total_permits_evaluated}",
            f"Bottlenecks Found:  {len(report.bottlenecks)} cross-cutting failure modes identified",
            "",
            "─── IDENTIFIED SYSTEMIC BOTTLENECKS ───",
        ]

        for idx, b in enumerate(report.bottlenecks, 1):
            lines.extend([
                f"\n[{idx}] {b.bottleneck_title.upper()}",
                f"    Category:        {b.category}",
                f"    Portfolio Impact: {b.prevalence_percentage}% of active portfolio ({len(b.affected_permits)} permits)",
                f"    Affected Permits:{', '.join(b.affected_permits)}",
                f"    Affected Projects:{', '.join(b.affected_projects)}",
                f"    Jurisdictions:   {', '.join(b.jurisdiction_patterns)}",
                f"    Root Cause:      {b.root_cause}",
                f"    ► RECOMMENDED FIX: {b.recommended_portfolio_fix}",
            ])

        lines.extend([
            "",
            "──────────────────────────────────────────────────────────────────────────────",
            "STRATEGIC PORTFOLIO RECOMMENDATIONS FOR PERMIT MANAGERS",
            "──────────────────────────────────────────────────────────────────────────────",
        ])
        for r in report.strategic_recommendations:
            lines.append(f"  {r}")

        return "\n".join(lines)

    return {
        "analyze_portfolio_priorities": analyze_portfolio_priorities,
        "get_daily_manager_briefing": get_daily_manager_briefing,
        "detect_portfolio_changes": detect_portfolio_changes,
        "analyze_systemic_bottlenecks": analyze_systemic_bottlenecks,
    }

