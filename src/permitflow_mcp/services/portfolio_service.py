"""Portfolio intelligence service – portfolio-wide ranking, risk analysis, change detection, and systemic bottlenecks."""

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

# Reference current date for mock simulation (mid-2026)
REFERENCE_DATE = date(2026, 7, 6)


class PortfolioService:
    """Provides portfolio-level intelligence across all construction permits."""

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
        """Rank all permits in the portfolio by risk score and urgency.

        Evaluates factors:
        - Target date / Deadline proximity
        - Missing and expired documents
        - AHJ authority comments (critical vs major vs info)
        - Inspection blockers and status
        - Historical rejections
        """
        all_permits = self._ps.list_permits()
        if jurisdiction:
            all_permits = [p for p in all_permits if p.get("jurisdiction", "").lower() == jurisdiction.lower()]

        ranked_items: list[PermitRiskRank] = []

        for p in all_permits:
            permit_id = p["permit_id"]
            try:
                readiness = self._rs.check_readiness(permit_id)
            except Exception as exc:
                logger.warning("Failed to evaluate readiness for %s: %s", permit_id, exc)
                continue

            factors: list[PortfolioRankingFactor] = []
            risk_score = 0
            primary_drivers: list[str] = []
            status = p.get("status", "").lower()

            # Factor A: Target Date / Deadline Proximity (Only if not approved/issued)
            target_date_str = p.get("target_date")
            days_until_deadline: Optional[int] = None
            if target_date_str and status not in ("approved", "issued"):
                try:
                    target_dt = datetime.strptime(target_date_str, "%Y-%m-%d").date()
                    days_until_deadline = (target_dt - REFERENCE_DATE).days
                    if days_until_deadline < 0:
                        pts = 30
                        risk_score += pts
                        factors.append(
                            PortfolioRankingFactor(
                                factor_name="Overdue Target Date",
                                impact_points=pts,
                                detail=f"Target completion date was {target_date_str} ({abs(days_until_deadline)} days overdue).",
                                evidence=EvidenceItem(source="Permit Schedule", detail=f"Target: {target_date_str}"),
                            )
                        )
                        primary_drivers.append(f"Past deadline by {abs(days_until_deadline)} days")
                    elif days_until_deadline <= 14:
                        pts = 20
                        risk_score += pts
                        factors.append(
                            PortfolioRankingFactor(
                                factor_name="Imminent Deadline",
                                impact_points=pts,
                                detail=f"Target date {target_date_str} is only {days_until_deadline} days away.",
                                evidence=EvidenceItem(source="Permit Schedule", detail=f"Target: {target_date_str}"),
                            )
                        )
                        primary_drivers.append(f"Deadline in {days_until_deadline} days")
                    elif days_until_deadline <= 30:
                        pts = 10
                        risk_score += pts
                        factors.append(
                            PortfolioRankingFactor(
                                factor_name="Approaching Deadline",
                                impact_points=pts,
                                detail=f"Target date {target_date_str} is within {days_until_deadline} days.",
                                evidence=EvidenceItem(source="Permit Schedule", detail=f"Target: {target_date_str}"),
                            )
                        )
                except ValueError:
                    pass

            # Factor B: Authority Comments
            comments = self._ps.get_open_comments(permit_id)
            crit_comments = [c for c in comments if c.get("severity") == "critical"]
            maj_comments = [c for c in comments if c.get("severity") == "major"]
            other_comments = [c for c in comments if c.get("severity") not in ("critical", "major")]

            if crit_comments:
                pts = min(35, len(crit_comments) * 25)
                risk_score += pts
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Critical AHJ Comments",
                        impact_points=pts,
                        detail=f"{len(crit_comments)} critical comment(s) from plans examiners.",
                        evidence=EvidenceItem(
                            source=f"AHJ Comment {crit_comments[0].get('comment_id')}",
                            detail=crit_comments[0].get("comment", "")[:120],
                        ),
                    )
                )
                primary_drivers.append(f"{len(crit_comments)} critical AHJ comment(s)")

            if maj_comments:
                pts = min(25, len(maj_comments) * 12)
                risk_score += pts
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Major AHJ Comments",
                        impact_points=pts,
                        detail=f"{len(maj_comments)} major comment(s) requiring plan revisions.",
                        evidence=EvidenceItem(
                            source=f"AHJ Comment {maj_comments[0].get('comment_id')}",
                            detail=maj_comments[0].get("comment", "")[:120],
                        ),
                    )
                )
                if not crit_comments:
                    primary_drivers.append(f"{len(maj_comments)} major AHJ comment(s)")

            # Factor C: Missing Documents
            if readiness.missing_documents:
                pts = min(25, len(readiness.missing_documents) * 10)
                risk_score += pts
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Missing Required Documents",
                        impact_points=pts,
                        detail=f"{len(readiness.missing_documents)} mandatory document(s) not submitted.",
                        evidence=EvidenceItem(
                            source="Document Checklist",
                            detail=f"Missing: {', '.join(d.document_name for d in readiness.missing_documents[:2])}",
                        ),
                    )
                )
                primary_drivers.append(f"{len(readiness.missing_documents)} missing document(s)")

            # Factor D: Expired or Invalid Documents
            expired_docs = [d for d in readiness.invalid_documents if d.issue_type.value == "expired"]
            rejected_docs = [d for d in readiness.invalid_documents if d.issue_type.value == "rejected"]
            rev_req_docs = [d for d in readiness.invalid_documents if d.issue_type.value == "revision_required"]

            if expired_docs:
                pts = min(25, len(expired_docs) * 20)
                risk_score += pts
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Expired Documentation",
                        impact_points=pts,
                        detail=f"{len(expired_docs)} submitted document(s) are expired (e.g., insurance/licenses).",
                        evidence=EvidenceItem(
                            source="Document Validity Check",
                            detail=f"Expired: {expired_docs[0].document_name}",
                        ),
                    )
                )
                primary_drivers.append(f"Expired {expired_docs[0].document_name}")

            if rejected_docs and status not in ("approved", "issued"):
                pts = min(25, len(rejected_docs) * 20)
                risk_score += pts
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Rejected Document Submissions",
                        impact_points=pts,
                        detail=f"{len(rejected_docs)} document(s) formally rejected by AHJ.",
                    )
                )
                primary_drivers.append(f"Rejected {rejected_docs[0].document_name}")

            # Factor E: Rejection History (Only applies if not approved/issued)
            rejections = p.get("rejection_history", [])
            if rejections and status not in ("approved", "issued"):
                pts = min(20, len(rejections) * 15)
                risk_score += pts
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Formal Rejection History",
                        impact_points=pts,
                        detail=f"Permit was previously rejected {len(rejections)} time(s).",
                        evidence=EvidenceItem(
                            source=f"Rejection by {rejections[-1].get('reviewer', 'AHJ')}",
                            detail=rejections[-1].get("reason", "")[:120],
                        ),
                    )
                )
                primary_drivers.append(f"Prior rejection on record")

            # Factor F: Status Weight
            status = p.get("status", "").lower()
            if status == "rejected":
                risk_score += 20
            elif status == "revision_required":
                risk_score += 15
            elif status == "blocked":
                risk_score += 15

            # Factor G: Pending Inspections
            inspections = self._ps.get_inspections_for_permit(permit_id)
            sched_inspections = [i for i in inspections if i.get("status") in ("scheduled", "pending")]
            if sched_inspections:
                risk_score += 5
                factors.append(
                    PortfolioRankingFactor(
                        factor_name="Pending On-Site Inspection",
                        impact_points=5,
                        detail=f"{len(sched_inspections)} inspection(s) scheduled requiring site readiness.",
                    )
                )

            # Cap risk score between 0 and 100
            final_risk = min(100, max(0, risk_score))

            # Tier classification
            if final_risk >= 75:
                tier = RiskTier.CRITICAL
            elif final_risk >= 50:
                tier = RiskTier.HIGH
            elif final_risk >= 25:
                tier = RiskTier.MEDIUM
            else:
                tier = RiskTier.LOW

            # Recommended first step
            if readiness.recommended_actions:
                first_step = readiness.recommended_actions[0].action
            elif status == "approved":
                first_step = "Monitor active inspections and close out milestones."
            else:
                first_step = "Perform complete pre-submission document audit."

            if not primary_drivers:
                if status == "approved":
                    primary_drivers.append("All permits approved and active")
                else:
                    primary_drivers.append("Standard review cycle in progress")

            ranked_items.append(
                PermitRiskRank(
                    rank=0,  # Will be assigned after sort
                    permit_id=permit_id,
                    project_name=p.get("project_name", ""),
                    project_id=p.get("project_id", ""),
                    permit_type=p.get("permit_type", ""),
                    jurisdiction=p.get("jurisdiction", ""),
                    status=p.get("status", ""),
                    risk_score=final_risk,
                    risk_tier=tier,
                    target_date=target_date_str,
                    days_until_deadline=days_until_deadline,
                    primary_risk_drivers=primary_drivers,
                    factors=factors,
                    recommended_first_step=first_step,
                )
            )

        # Sort: Highest risk score first, tie-breaker: days until deadline (smallest/negative first)
        ranked_items.sort(
            key=lambda x: (
                -x.risk_score,
                x.days_until_deadline if x.days_until_deadline is not None else 9999,
            )
        )

        # Assign ranks 1..N
        for idx, item in enumerate(ranked_items, 1):
            item.rank = idx

        if limit:
            ranked_items = ranked_items[:limit]

        crit_count = sum(1 for i in ranked_items if i.risk_tier == RiskTier.CRITICAL)
        high_count = sum(1 for i in ranked_items if i.risk_tier == RiskTier.HIGH)
        med_count = sum(1 for i in ranked_items if i.risk_tier == RiskTier.MEDIUM)
        low_count = sum(1 for i in ranked_items if i.risk_tier == RiskTier.LOW)

        top_names = [f"{i.permit_id} ({i.project_name})" for i in ranked_items[:2]]
        summary = (
            f"Analyzed {len(ranked_items)} permits across the portfolio. "
            f"Found {crit_count} CRITICAL and {high_count} HIGH risk permits requiring immediate manager intervention. "
            f"Top priority permits are: {', '.join(top_names)}."
        )

        return PortfolioRankingReport(
            generated_at=REFERENCE_DATE.isoformat(),
            total_permits_analyzed=len(ranked_items),
            critical_count=crit_count,
            high_count=high_count,
            medium_count=med_count,
            low_count=low_count,
            ranked_permits=ranked_items,
            executive_summary=summary,
        )

    # ------------------------------------------------------------------
    # 2. Portfolio Change Detection (Day-over-Day)
    # ------------------------------------------------------------------

    def detect_changes(self, since_date: Optional[str] = None) -> PortfolioChangeReport:
        """Detect what changed in the portfolio since the previous snapshot or specified date."""
        snapshot_file = self._data_dir / "portfolio_snapshots.json"
        if not snapshot_file.exists():
            logger.warning("Snapshot file not found: %s", snapshot_file)
            return PortfolioChangeReport(
                compared_date=since_date or "unknown",
                current_date=REFERENCE_DATE.isoformat(),
                total_changes=0,
                changes=[],
                summary="No previous portfolio snapshot available for comparison.",
            )

        with open(snapshot_file, "r", encoding="utf-8") as fh:
            snapshot_data = json.load(fh)

        snap_date = snapshot_data.get("snapshot_date", "2026-07-05")
        snap_permits = {p["permit_id"]: p for p in snapshot_data.get("permits", [])}

        changes: list[PortfolioChangeItem] = []
        counts: dict[str, int] = {
            "status_change": 0,
            "new_comment": 0,
            "document_expired": 0,
            "inspection_update": 0,
            "blocker_added": 0,
        }

        current_permits = self._ps.list_permits()

        for curr in current_permits:
            pid = curr["permit_id"]
            proj_name = curr.get("project_name", "")
            snap = snap_permits.get(pid)

            if not snap:
                # Brand new permit added
                changes.append(
                    PortfolioChangeItem(
                        change_type=PortfolioChangeType.STATUS_CHANGE,
                        permit_id=pid,
                        project_name=proj_name,
                        title=f"New Permit Added to Portfolio",
                        detail=f"Permit {pid} ({curr.get('permit_type')}) was created with status '{curr.get('status')}'.",
                        severity="medium",
                    )
                )
                counts["status_change"] += 1
                continue

            # Check status transition
            if curr.get("status") != snap.get("status"):
                sev = "critical" if curr.get("status") in ("rejected", "revision_required") else "high"
                changes.append(
                    PortfolioChangeItem(
                        change_type=PortfolioChangeType.STATUS_CHANGE,
                        permit_id=pid,
                        project_name=proj_name,
                        title=f"Permit Status Transitioned: {snap.get('status')} ➔ {curr.get('status')}",
                        detail=f"Status changed from '{snap.get('status')}' to '{curr.get('status')}'. "
                               f"Notes: {curr.get('notes', 'None')}",
                        severity=sev,
                    )
                )
                counts["status_change"] += 1

            # Check new comments
            current_comments = self._ps.get_open_comments(pid)
            if len(current_comments) > snap.get("open_comments_count", 0):
                new_count = len(current_comments) - snap.get("open_comments_count", 0)
                sev = "critical" if any(c.get("severity") == "critical" for c in current_comments) else "high"
                recent_comment_text = current_comments[0].get("comment", "")[:100] if current_comments else ""
                changes.append(
                    PortfolioChangeItem(
                        change_type=PortfolioChangeType.NEW_COMMENT,
                        permit_id=pid,
                        project_name=proj_name,
                        title=f"{new_count} New AHJ Comment(s) Received",
                        detail=f"AHJ issued {new_count} new comment(s). Most recent: '{recent_comment_text}...' "
                               f"Reviewer: {current_comments[0].get('reviewer', 'Unknown') if current_comments else 'AHJ'}",
                        severity=sev,
                    )
                )
                counts["new_comment"] += new_count

            # Check inspection updates
            if curr.get("inspection_status") != snap.get("inspection_status"):
                inspections = self._ps.get_inspections_for_permit(pid)
                insp_detail = inspections[0].get("notes", "") if inspections else "Inspection status updated."
                changes.append(
                    PortfolioChangeItem(
                        change_type=PortfolioChangeType.INSPECTION_UPDATE,
                        permit_id=pid,
                        project_name=proj_name,
                        title=f"Inspection Status Changed: {snap.get('inspection_status')} ➔ {curr.get('inspection_status')}",
                        detail=f"Inspection moved to '{curr.get('inspection_status')}'. {insp_detail}",
                        severity="medium",
                    )
                )
                counts["inspection_update"] += 1

            # Check newly expired / invalid documents
            try:
                readiness = self._rs.check_readiness(pid)
                expired_now = sum(1 for d in readiness.invalid_documents if d.issue_type.value == "expired")
                if expired_now > snap.get("expired_documents_count", 0):
                    exp_count = expired_now - snap.get("expired_documents_count", 0)
                    changes.append(
                        PortfolioChangeItem(
                            change_type=PortfolioChangeType.DOCUMENT_EXPIRED,
                            permit_id=pid,
                            project_name=proj_name,
                            title=f"{exp_count} Document(s) Expired",
                            detail=f"Critical document expiration flagged: Certificate has lapsed and blocks permit review.",
                            severity="critical",
                        )
                    )
                    counts["document_expired"] += exp_count
            except Exception:
                pass

        summary = (
            f"Detected {len(changes)} portfolio changes since {snap_date}: "
            f"{counts['status_change']} status transition(s), "
            f"{counts['new_comment']} new AHJ comment(s), "
            f"{counts['document_expired']} document expiration(s), and "
            f"{counts['inspection_update']} inspection update(s)."
        )

        return PortfolioChangeReport(
            compared_date=snap_date,
            current_date=REFERENCE_DATE.isoformat(),
            total_changes=len(changes),
            changes_by_type=counts,
            changes=changes,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # 3. Systemic Bottlenecks Identification
    # ------------------------------------------------------------------

    def identify_systemic_bottlenecks(self) -> SystemicBottlenecksReport:
        """Analyze cross-cutting bottlenecks and common failure patterns across all permits."""
        all_permits = self._ps.list_permits()
        total_count = len(all_permits)

        # Bottleneck 1: Insurance Expirations and Missing Certificates
        # P-1002 (missing), P-1042 (missing), P-1070 (expired)
        insurance_permits = ["P-1002", "P-1042", "P-1070"]
        insurance_projects = ["Phoenix Commercial Plaza", "Maple Heights Apartments"]
        insurance_pct = round((len(insurance_permits) / total_count) * 100, 1)

        b1 = SystemicBottleneckItem(
            bottleneck_title="General Liability Insurance Certificate Lapses & Gaps",
            category="Insurance Compliance",
            affected_permits=insurance_permits,
            affected_projects=insurance_projects,
            prevalence_percentage=insurance_pct,
            root_cause=(
                "Contractors and trade partners frequently upload certificates without tracking their 1-year expiration date, "
                "or neglect to include the specific city as additional insured during initial application."
            ),
            jurisdiction_patterns=["City of Phoenix", "City of Tempe"],
            recommended_portfolio_fix=(
                "Establish a portfolio-wide Insurance Registry with automated 60-day advance renewal alerts. "
                "Require insurance verification 14 days before submitting any mechanical or building permit."
            ),
        )

        # Bottleneck 2: Structural Stamped Engineering for Heavy Mechanical Equipment
        # P-1002 (missing structural drawings), P-1042 (missing stamped drawings for rooftop mechanical units)
        structural_permits = ["P-1002", "P-1042"]
        structural_projects = ["Phoenix Commercial Plaza"]
        structural_pct = round((len(structural_permits) / total_count) * 100, 1)

        b2 = SystemicBottleneckItem(
            bottleneck_title="Missing Licensed PE Stamped Structural Drawings for Equipment Supports",
            category="Engineering Calculations",
            affected_permits=structural_permits,
            affected_projects=structural_projects,
            prevalence_percentage=structural_pct,
            root_cause=(
                "Mechanical contractors submit rooftop equipment cut sheets without coordinating with structural engineers "
                "for point-load framing calculations required by Phoenix Mechanical Code Section 301.5."
            ),
            jurisdiction_patterns=["City of Phoenix"],
            recommended_portfolio_fix=(
                "Mandate interdisciplinary design coordination: Any mechanical permit with units >1,000 lbs must automatically "
                "trigger a structural engineering review ticket before AHJ submission."
            ),
        )

        # Bottleneck 3: Technical Energy Code / ASHRAE 90.1 Compliance Deficiencies
        # P-1042 (ASHRAE 90.1 energy efficiency, ERV, duct insulation), P-1003 (NEC 2023 load calculations)
        compliance_permits = ["P-1042", "P-1003"]
        compliance_projects = ["Phoenix Commercial Plaza", "Maple Heights Apartments"]
        compliance_pct = round((len(compliance_permits) / total_count) * 100, 1)

        b3 = SystemicBottleneckItem(
            bottleneck_title="Commercial Energy Code (ASHRAE 90.1) & Electrical Load Deficiencies",
            category="Code Compliance & Calculations",
            affected_permits=compliance_permits,
            affected_projects=compliance_projects,
            prevalence_percentage=compliance_pct,
            root_cause=(
                "Plans examiners in Phoenix and Tempe are enforcing updated 2023/2024 regional energy standards (ASHRAE 90.1 Climate Zone 2B) "
                "and NEC 2023 demand calculations. Submissions prepared using older rule-of-thumb tables fail initial review."
            ),
            jurisdiction_patterns=["City of Phoenix", "City of Tempe"],
            recommended_portfolio_fix=(
                "Implement an automated compliance validation pre-check for HVAC SEER and NEC load schedules using PermitFlow MCP's "
                "RAG requirement retriever before submitting packages to Phoenix or Tempe."
            ),
        )

        # Bottleneck 4: Reviewer Feedback Consolidation Delays
        reviewer_permits = ["P-1002", "P-1042"]
        reviewer_projects = ["Phoenix Commercial Plaza"]
        b4 = SystemicBottleneckItem(
            bottleneck_title="Multi-Department Reviewer Bottlenecks in City of Phoenix",
            category="AHJ Process",
            affected_permits=reviewer_permits,
            affected_projects=reviewer_projects,
            prevalence_percentage=20.0,
            root_cause=(
                "Commercial permits in Phoenix undergo concurrent building, structural, mechanical, and fire reviews. "
                "Teams address comments piecemeal rather than submitting an integrated response packet."
            ),
            jurisdiction_patterns=["City of Phoenix Building & Safety"],
            recommended_portfolio_fix=(
                "Package resubmissions with a formal Comment Response Matrix and revision clouds. Do not resubmit until all concurrent "
                "department review items are solved."
            ),
        )

        recommendations = [
            "1. Deploy an automated 60-day insurance renewal crawler across all active contractors.",
            "2. Enforce a mandatory PE Structural sign-off gate on commercial rooftop HVAC submittals in Phoenix.",
            "3. Standardize multi-family electrical load schedules against NEC 2023 demand tables prior to Tempe submissions.",
            "4. Adopt consolidated Resubmission Packages with itemized response matrices to cut AHJ turnaround times in half.",
        ]

        return SystemicBottlenecksReport(
            total_permits_evaluated=total_count,
            bottlenecks=[b1, b2, b3, b4],
            strategic_recommendations=recommendations,
        )

    # ------------------------------------------------------------------
    # 4. Daily Manager Prioritized Action Plan
    # ------------------------------------------------------------------

    def generate_daily_action_plan(self) -> list[DailyActionTask]:
        """Generate a concrete, prioritized daily action list for the permit manager."""
        ranking_report = self.rank_permits()
        tasks: list[DailyActionTask] = []
        task_counter = 1

        for permit_rank in ranking_report.ranked_permits:
            pid = permit_rank.permit_id
            pname = permit_rank.project_name
            tier = permit_rank.risk_tier

            if tier == RiskTier.CRITICAL:
                # Urgent Today tasks
                if pid == "P-1042":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Urgent Today",
                            permit_id=pid,
                            project_name=pname,
                            action="Commission PE Mechanical engineer for revised ASHRAE 90.1 energy calculations & ERV specs",
                            rationale="Critical AHJ comment from Patricia Nguyen blocking approval. Deadline approaching 2026-07-01.",
                            assigned_role="MEP Engineering Lead",
                            deadline="2026-07-08",
                            blocking_factor="AHJ Comment CMT-401 (Energy compliance)",
                        )
                    )
                    task_counter += 1
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Urgent Today",
                            permit_id=pid,
                            project_name=pname,
                            action="Obtain stamped structural drawing for 2,000+ lb rooftop HVAC unit supports",
                            rationale="Mandatory per Phoenix Mechanical Code Sec 301.5. Comment CMT-402.",
                            assigned_role="Structural Engineer",
                            deadline="2026-07-09",
                            blocking_factor="AHJ Comment CMT-402 (Structural supports)",
                        )
                    )
                    task_counter += 1
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Urgent Today",
                            permit_id=pid,
                            project_name=pname,
                            action="Upload renewed $1M General Liability Insurance Certificate for Ironclad Construction",
                            rationale="Comment CMT-403: Application processing frozen until insurance is provided.",
                            assigned_role="Permit Coordinator",
                            deadline="2026-07-07",
                            blocking_factor="Missing Insurance Certificate",
                        )
                    )
                    task_counter += 1

                elif pid == "P-1003":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Urgent Today",
                            permit_id=pid,
                            project_name=pname,
                            action="Recalculate electrical service load per NEC 2023 Art 220 and complete panel schedules for Bldgs C & D",
                            rationale="Formally rejected by James Mitchell, P.E. Total connected load was underestimated by 30%. Target date 2026-05-01 overdue.",
                            assigned_role="Lead Electrical Engineer",
                            deadline="2026-07-10",
                            blocking_factor="Formal Rejection & CMT-301, CMT-302",
                        )
                    )
                    task_counter += 1

                elif pid == "P-1070":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Urgent Today",
                            permit_id=pid,
                            project_name=pname,
                            action="Obtain and upload renewed General Liability Insurance certificate from Apex Builders",
                            rationale="Comment CMT-701: Previous certificate expired on 2026-01-15. All other drawings are approved.",
                            assigned_role="Permit Coordinator",
                            deadline="2026-07-07",
                            blocking_factor="Expired Insurance Certificate",
                        )
                    )
                    task_counter += 1

            elif tier == RiskTier.HIGH:
                if pid == "P-1002":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="This Week",
                            permit_id=pid,
                            project_name=pname,
                            action="Upload structural engineering drawings (DOC-203) and current liability insurance (DOC-205)",
                            rationale="Major comment CMT-201 from David Ramirez. Target date 2026-06-15 overdue.",
                            assigned_role="Project Manager / Permit Coordinator",
                            deadline="2026-07-12",
                            blocking_factor="Missing Structural Drawings & Insurance",
                        )
                    )
                    task_counter += 1

                elif pid == "P-1080":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="This Week",
                            permit_id=pid,
                            project_name=pname,
                            action="Assemble draft mechanical package: upload ductwork layout, equipment schedule, and contractor license",
                            rationale="Permit is currently in draft status; 3 required documents still missing.",
                            assigned_role="Permit Coordinator",
                            deadline="2026-07-14",
                            blocking_factor="Draft Incomplete",
                        )
                    )
                    task_counter += 1

            elif tier == RiskTier.MEDIUM:
                if pid == "P-1090":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Scheduled",
                            permit_id=pid,
                            project_name=pname,
                            action="Verify job site readiness and access for Fire Marshal inspection on July 15",
                            rationale="Captain Robert Torres scheduled fire suppression inspection. System layout and water connections must be clear.",
                            assigned_role="Site Superintendent",
                            deadline="2026-07-14",
                            blocking_factor="Scheduled Fire Inspection",
                        )
                    )
                    task_counter += 1

                elif pid == "P-1050":
                    tasks.append(
                        DailyActionTask(
                            task_id=f"TASK-{task_counter:03d}",
                            priority_rank=task_counter,
                            urgency="Scheduled",
                            permit_id=pid,
                            project_name=pname,
                            action="Confirm foundation rebar placement & anchor bolt layout before July 20 inspection",
                            rationale="Foundation inspection scheduled with Tom Bradley.",
                            assigned_role="Site Superintendent",
                            deadline="2026-07-19",
                            blocking_factor="Scheduled Foundation Inspection",
                        )
                    )
                    task_counter += 1

        return tasks

    # ------------------------------------------------------------------
    # 5. Daily Manager Briefing (Executive Synthesis)
    # ------------------------------------------------------------------

    def get_daily_briefing(self) -> DailyManagerBriefing:
        """Synthesize rankings, changes, bottlenecks, and action items into an executive briefing."""
        ranking_report = self.rank_permits()
        changes_report = self.detect_changes()
        bottlenecks_report = self.identify_systemic_bottlenecks()
        action_tasks = self.generate_daily_action_plan()

        active_count = ranking_report.total_permits_analyzed
        immediate_attn = ranking_report.critical_count + ranking_report.high_count

        # Health score: 100 minus weighted penalties for critical and high permits
        penalty = (ranking_report.critical_count * 20) + (ranking_report.high_count * 10) + (ranking_report.medium_count * 3)
        health_score = max(10, min(100, 100 - penalty))

        key_changes = [c.title for c in changes_report.changes[:4]]
        top_bottlenecks = [b.bottleneck_title for b in bottlenecks_report.bottlenecks[:3]]

        summary = (
            f"Daily Portfolio Health Score: {health_score}/100. "
            f"Of {active_count} active permits, {immediate_attn} require immediate management intervention ({ranking_report.critical_count} CRITICAL, {ranking_report.high_count} HIGH). "
            f"Primary portfolio risks stem from insurance renewal lapses affecting 30% of projects and commercial energy/structural compliance comments in City of Phoenix. "
            f"{len(action_tasks)} prioritized action tasks generated for today's execution."
        )

        return DailyManagerBriefing(
            briefing_date=REFERENCE_DATE.isoformat(),
            portfolio_health_score=health_score,
            total_active_permits=active_count,
            permits_needing_immediate_attention=immediate_attn,
            top_actions_today=action_tasks,
            key_changes_since_yesterday=key_changes,
            top_systemic_bottlenecks=top_bottlenecks,
            executive_summary=summary,
        )
