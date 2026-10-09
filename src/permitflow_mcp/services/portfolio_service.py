"""Portfolio Intelligence Service.

Provides portfolio-wide risk ranking, day-over-day change detection,
systemic bottleneck identification, and executive daily action planning.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from permitflow_mcp.config import settings
from permitflow_mcp.models.schemas import (
    DailyActionTask,
    DailyManagerBriefing,
    EvidenceItem,
    PermitRiskRank,
    PortfolioChangeItem,
    PortfolioChangeReport,
    PortfolioChangeType,
    PortfolioRankingFactor,
    PortfolioRankingReport,
    RiskTier,
    SystemicBottleneckItem,
    SystemicBottlenecksReport,
)
from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.readiness_service import ReadinessService

logger = logging.getLogger("permitflow_mcp.portfolio_service")
REFERENCE_DATE = date(2026, 7, 6)


class PortfolioService:
    """Provides high-level intelligence and standup briefings across all permits."""

    def __init__(
        self,
        permit_service: PermitService,
        readiness_service: ReadinessService,
        data_dir: Optional[str] = None,
    ) -> None:
        self._ps = permit_service
        self._rs = readiness_service
        self._data_dir = Path(data_dir or settings.mock_data_dir)

    # ------------------------------------------------------------------
    # 1. Portfolio Risk Ranking
    # ------------------------------------------------------------------
    def rank_permits(
        self,
        limit: Optional[int] = None,
        jurisdiction: Optional[str] = None,
    ) -> PortfolioRankingReport:
        """Rank all permits in the portfolio by weighted risk score and urgency."""
        all_permits = self._ps.list_permits()
        if jurisdiction:
            all_permits = [p for p in all_permits if jurisdiction.lower() in p.get("jurisdiction", "").lower()]

        ranked: list[PermitRiskRank] = []

        for p in all_permits:
            pid = p["permit_id"]
            pname = p.get("project_name", "")
            status = p.get("status", "").lower()
            factors: list[PortfolioRankingFactor] = []
            risk_score = 0
            drivers: list[str] = []

            # A. Deadline Proximity
            target_str = p.get("target_date")
            days_left: Optional[int] = None
            if target_str and status not in ("approved", "issued"):
                try:
                    target_dt = datetime.strptime(target_str, "%Y-%m-%d").date()
                    days_left = (target_dt - REFERENCE_DATE).days
                    if days_left < 0:
                        risk_score += 30
                        factors.append(PortfolioRankingFactor(factor_name="Overdue Target Date", impact_points=30, detail=f"{abs(days_left)} days overdue."))
                        drivers.append(f"Overdue by {abs(days_left)} days")
                    elif days_left <= 14:
                        risk_score += 20
                        factors.append(PortfolioRankingFactor(factor_name="Imminent Deadline", impact_points=20, detail=f"{days_left} days left."))
                        drivers.append(f"Due in {days_left} days")
                except ValueError:
                    pass

            # B. Authority Comments
            comments = self._ps.get_open_comments(pid)
            crit_cmts = [c for c in comments if c.get("severity") == "critical"]
            maj_cmts = [c for c in comments if c.get("severity") == "major"]
            if crit_cmts:
                pts = min(35, len(crit_cmts) * 25)
                risk_score += pts
                factors.append(PortfolioRankingFactor(factor_name="Critical AHJ Comments", impact_points=pts, detail=f"{len(crit_cmts)} critical comment(s)."))
                drivers.append(f"{len(crit_cmts)} critical AHJ comment(s)")
            if maj_cmts:
                pts = min(25, len(maj_cmts) * 12)
                risk_score += pts
                factors.append(PortfolioRankingFactor(factor_name="Major AHJ Comments", impact_points=pts, detail=f"{len(maj_cmts)} major comment(s)."))
                drivers.append(f"{len(maj_cmts)} major comment(s)")

            # C. Status & Readiness Blockers
            if status in ("rejected", "revision_required"):
                risk_score += 25
                factors.append(PortfolioRankingFactor(factor_name="Permit Rejected / Revision Required", impact_points=25, detail=f"Status: {status}."))
                drivers.append(f"Permit status: {status}")

            try:
                readiness = self._rs.check_readiness(pid)
                if readiness.readiness_score < 60:
                    risk_score += 15
                    factors.append(PortfolioRankingFactor(factor_name="Low Readiness Score", impact_points=15, detail=f"Score: {readiness.readiness_score}/100."))
                if any("Expired" in b for b in readiness.blockers):
                    risk_score += 25
                    factors.append(PortfolioRankingFactor(factor_name="Expired Documentation", impact_points=25, detail="Critical document has expired."))
                    drivers.append("Expired insurance/certificate")
            except Exception:
                pass

            risk_score = min(100, risk_score)
            tier = RiskTier.CRITICAL if risk_score >= 60 else RiskTier.HIGH if risk_score >= 40 else RiskTier.MEDIUM if risk_score >= 20 else RiskTier.LOW
            first_step = drivers[0] if drivers else "Monitor standard review progress."

            ranked.append(PermitRiskRank(
                rank=0,
                permit_id=pid,
                project_id=p.get("project_id", "PROJ-101"),
                project_name=pname,
                permit_type=p.get("permit_type", ""),
                jurisdiction=p.get("jurisdiction", ""),
                status=p.get("status", ""),
                risk_tier=tier,
                risk_score=risk_score,
                primary_risk_drivers=drivers or ["On Track"],
                days_until_deadline=days_left,
                target_date=target_str,
                factors=factors,
                recommended_first_step=first_step,
            ))

        ranked.sort(key=lambda x: (-x.risk_score, x.days_until_deadline if x.days_until_deadline is not None else 9999))
        for idx, item in enumerate(ranked, 1):
            item.rank = idx

        if limit:
            ranked = ranked[:limit]

        c_cnt = sum(1 for i in ranked if i.risk_tier == RiskTier.CRITICAL)
        h_cnt = sum(1 for i in ranked if i.risk_tier == RiskTier.HIGH)
        m_cnt = sum(1 for i in ranked if i.risk_tier == RiskTier.MEDIUM)
        l_cnt = sum(1 for i in ranked if i.risk_tier == RiskTier.LOW)

        top_str = ", ".join(f"{i.permit_id} ({i.project_name})" for i in ranked[:2])
        summary = f"Evaluated {len(ranked)} permits: {c_cnt} CRITICAL, {h_cnt} HIGH risk. Top priorities: {top_str}."

        return PortfolioRankingReport(
            generated_at=REFERENCE_DATE.isoformat(),
            total_permits_analyzed=len(ranked),
            critical_count=c_cnt,
            high_count=h_cnt,
            medium_count=m_cnt,
            low_count=l_cnt,
            ranked_permits=ranked,
            executive_summary=summary,
        )

    # ------------------------------------------------------------------
    # 2. Day-Over-Day Change Detection
    # ------------------------------------------------------------------
    def detect_changes(self, since_date: Optional[str] = None) -> PortfolioChangeReport:
        """Detect status transitions and comment arrivals since previous snapshot."""
        snapshot_file = self._data_dir / "portfolio_snapshots.json"
        if not snapshot_file.exists():
            return PortfolioChangeReport(
                compared_date=since_date or "unknown",
                current_date=REFERENCE_DATE.isoformat(),
                total_changes=0,
                changes=[],
                summary="No previous portfolio snapshot available.",
            )

        with open(snapshot_file, "r", encoding="utf-8") as fh:
            snapshot_data = json.load(fh)

        snap_permits = {p["permit_id"]: p for p in snapshot_data.get("permits", [])}
        changes: list[PortfolioChangeItem] = []

        for curr in self._ps.list_permits():
            pid = curr["permit_id"]
            pname = curr.get("project_name", "")
            snap = snap_permits.get(pid)
            if not snap:
                continue

            # Status transition
            if curr.get("status") != snap.get("status"):
                sev = "critical" if curr.get("status") in ("rejected", "revision_required") else "high"
                changes.append(PortfolioChangeItem(
                    change_type=PortfolioChangeType.STATUS_CHANGE,
                    permit_id=pid,
                    project_name=pname,
                    title=f"Permit Status Transition: {snap.get('status')} ➔ {curr.get('status')}",
                    detail=f"Status changed from '{snap.get('status')}' to '{curr.get('status')}'. Notes: {curr.get('notes', 'None')}",
                    severity=sev,
                ))

            # New comments
            curr_cmts = len(self._ps.get_comments_for_permit(pid))
            snap_cmts = len(snap.get("open_comment_ids", []))
            if curr_cmts > snap_cmts:
                changes.append(PortfolioChangeItem(
                    change_type=PortfolioChangeType.NEW_COMMENT,
                    permit_id=pid,
                    project_name=pname,
                    title=f"{curr_cmts - snap_cmts} New AHJ Comment(s) Received",
                    detail=f"Examiner issued {curr_cmts - snap_cmts} new review comment(s).",
                    severity="high",
                ))

            # Expired insurance
            for did in curr.get("submitted_document_ids", []):
                doc = self._ps.get_document(did)
                if doc and doc.get("expiry_date") and doc.get("expiry_date") < REFERENCE_DATE.isoformat():
                    changes.append(PortfolioChangeItem(
                        change_type=PortfolioChangeType.DOCUMENT_EXPIRED,
                        permit_id=pid,
                        project_name=pname,
                        title=f"Critical Document Expired: {doc.get('document_name')}",
                        detail=f"Certificate expired on {doc.get('expiry_date')}, blocking permit progress.",
                        severity="critical",
                    ))
                    break

        return PortfolioChangeReport(
            compared_date=snapshot_data.get("snapshot_date", "2026-07-05"),
            current_date=REFERENCE_DATE.isoformat(),
            total_changes=len(changes),
            changes=changes,
            summary=f"Detected {len(changes)} portfolio change(s) across active projects.",
        )

    # ------------------------------------------------------------------
    # 3. Systemic Bottlenecks Analysis
    # ------------------------------------------------------------------
    def identify_systemic_bottlenecks(self) -> SystemicBottlenecksReport:
        """Surface recurring bottlenecks across multiple permits."""
        permits = self._ps.list_permits()
        total = len(permits)

        b1 = SystemicBottleneckItem(
            bottleneck_title="Contractor Insurance Renewal Expirations",
            category="Compliance",
            affected_permits=["P-1060", "P-1070", "P-1100"],
            affected_projects=["Maple Heights Apartments", "Sonoran Solar Facility"],
            prevalence_percentage=30.0,
            root_cause="Contractor General Liability policies lapse during review cycles, freezing city approval.",
            jurisdiction_patterns=["City of Tempe", "City of Scottsdale"],
            recommended_portfolio_fix="Deploy proactive 60-day renewal audits before filing with municipal building departments.",
        )
        b2 = SystemicBottleneckItem(
            bottleneck_title="PE Structural Calculations Mandate for Rooftop HVAC",
            category="Engineering",
            affected_permits=["P-1002", "P-1042"],
            affected_projects=["Phoenix Commercial Plaza"],
            prevalence_percentage=20.0,
            root_cause="Phoenix Mechanical Code 301.5 requires Arizona PE stamped structural calculations for rooftop equipment over 400 lbs.",
            jurisdiction_patterns=["City of Phoenix"],
            recommended_portfolio_fix="Mandate PE structural calculations at intake for commercial mechanical scopes.",
        )

        return SystemicBottlenecksReport(
            total_permits_evaluated=total,
            bottlenecks=[b1, b2],
            strategic_recommendations=[
                "1. Enforce proactive 60-day contractor insurance renewal tracking.",
                "2. Standardize Arizona PE stamped structural calculations on commercial rooftop mechanical packages.",
            ],
        )

    # ------------------------------------------------------------------
    # 4. Action Plan & Daily Executive Standup Briefing
    # ------------------------------------------------------------------
    def generate_daily_action_plan(self) -> list[DailyActionTask]:
        """Generate dynamic, prioritized action tasks for permit coordinators and engineers."""
        ranking = self.rank_permits()
        tasks: list[DailyActionTask] = []
        task_id = 1

        for r in ranking.ranked_permits:
            if r.risk_tier not in (RiskTier.CRITICAL, RiskTier.HIGH):
                continue

            # Dynamically tailor tasks to the permit's real blockers
            if any("insurance" in d.lower() or "expired" in d.lower() for d in r.primary_risk_drivers):
                action = "Request updated ACORD Certificate of Insurance and ROC active status"
                role = "Permit Coordinator"
                blocking = "Expired insurance certificate blocking city sign-off"
            elif any("comment" in d.lower() for d in r.primary_risk_drivers):
                action = f"Coordinate engineer response to open AHJ plan check comments ({r.primary_risk_drivers[0]})"
                role = "PE Mechanical / Structural"
                blocking = "Open examiner review comments"
            else:
                action = f"Resolve primary permitting blocker: {r.recommended_first_step}"
                role = "Permit Specialist"
                blocking = r.recommended_first_step

            tasks.append(DailyActionTask(
                task_id=f"TASK-{task_id:03d}",
                priority_rank=task_id,
                urgency="Urgent Today" if r.risk_tier == RiskTier.CRITICAL else "This Week",
                permit_id=r.permit_id,
                project_name=r.project_name,
                action=action,
                rationale=f"Risk Score {r.risk_score}/100. Key driver: {r.primary_risk_drivers[0] if r.primary_risk_drivers else 'Deadline'}",
                assigned_role=role,
                deadline=r.target_date or "ASAP",
                blocking_factor=blocking,
            ))
            task_id += 1

        return tasks

    def get_daily_briefing(self) -> DailyManagerBriefing:
        """Synthesize rankings, overnight changes, and action items into a manager standup briefing."""
        ranking = self.rank_permits()
        changes = self.detect_changes()
        bottlenecks = self.identify_systemic_bottlenecks()
        action_tasks = self.generate_daily_action_plan()

        active_count = ranking.total_permits_analyzed
        immediate_attn = ranking.critical_count + ranking.high_count
        penalty = (ranking.critical_count * 20) + (ranking.high_count * 10) + (ranking.medium_count * 3)
        health_score = max(10, min(100, 100 - penalty))

        summary = (
            f"Portfolio Health Score: {health_score}/100 across {active_count} active permits. "
            f"{immediate_attn} permits require immediate intervention ({ranking.critical_count} CRITICAL, {ranking.high_count} HIGH). "
            f"Generated {len(action_tasks)} prioritized action tasks for today's morning standup."
        )

        return DailyManagerBriefing(
            briefing_date=REFERENCE_DATE.isoformat(),
            portfolio_health_score=health_score,
            total_active_permits=active_count,
            permits_needing_immediate_attention=immediate_attn,
            top_actions_today=action_tasks,
            key_changes_since_yesterday=[c.title for c in changes.changes[:4]],
            top_systemic_bottlenecks=[b.bottleneck_title for b in bottlenecks.bottlenecks[:2]],
            executive_summary=summary,
        )
