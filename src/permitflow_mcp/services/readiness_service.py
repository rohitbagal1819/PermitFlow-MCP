"""Permit Readiness Analysis Service.

Computes a composite 0-100 pre-submission readiness score, categorizes risk tiers,
identifies missing/expired documents and open authority comments, and issues
a strict Go/No-Go submission verdict.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from permitflow_mcp.models.schemas import (
    ActionPriority,
    BlockerExplanation,
    ChecklistItem,
    DocumentIssue,
    DocumentIssueType,
    EvidenceItem,
    PermitReadinessResult,
    ReadinessStatus,
    RecommendedAction,
    ResubmissionChecklist,
)
from permitflow_mcp.services.permit_service import PermitService

logger = logging.getLogger("permitflow_mcp.readiness_service")


class ReadinessService:
    """Evaluates permit completeness, document compliance, and authority comments."""

    def __init__(self, permit_service: PermitService) -> None:
        self._ps = permit_service

    def check_readiness(self, permit_id: str) -> PermitReadinessResult:
        """Perform a comprehensive readiness audit for a permit."""
        permit = self._ps.get_permit(permit_id)
        if not permit:
            raise ValueError(f"Permit '{permit_id}' not found. Please verify the permit ID.")

        logger.info("[Readiness] Checking readiness for permit %s", permit_id)
        today = date.today()

        # 1. Document Auditing (Missing & Invalid)
        required_ids = set(permit.get("required_document_ids", []))
        submitted_ids = set(permit.get("submitted_document_ids", []))

        missing_docs: list[DocumentIssue] = []
        for doc_id in (required_ids - submitted_ids):
            doc = self._ps.get_document(doc_id)
            name = doc.get("document_name", doc_id) if doc else doc_id
            missing_docs.append(DocumentIssue(
                document_id=doc_id,
                document_name=name,
                document_type=doc.get("document_type", "unknown") if doc else "unknown",
                issue_type=DocumentIssueType.MISSING,
                detail=f"Required document '{name}' has not been submitted.",
            ))

        invalid_docs: list[DocumentIssue] = []
        for doc_id in submitted_ids:
            doc = self._ps.get_document(doc_id)
            if not doc:
                continue
            name = doc.get("document_name", doc_id)
            status = doc.get("status", "")
            expiry = doc.get("expiry_date")

            if expiry:
                try:
                    if datetime.strptime(expiry, "%Y-%m-%d").date() < today:
                        invalid_docs.append(DocumentIssue(
                            document_id=doc_id,
                            document_name=name,
                            document_type=doc.get("document_type", "unknown"),
                            issue_type=DocumentIssueType.EXPIRED,
                            detail=f"Document '{name}' expired on {expiry}. A current certificate is mandatory.",
                        ))
                        continue
                except ValueError:
                    pass

            if status == "rejected":
                invalid_docs.append(DocumentIssue(
                    document_id=doc_id,
                    document_name=name,
                    document_type=doc.get("document_type", "unknown"),
                    issue_type=DocumentIssueType.REJECTED,
                    detail=f"Document '{name}' was rejected by the examiner and requires revisions.",
                ))
            elif status == "revision_required":
                invalid_docs.append(DocumentIssue(
                    document_id=doc_id,
                    document_name=name,
                    document_type=doc.get("document_type", "unknown"),
                    issue_type=DocumentIssueType.REVISION_REQUIRED,
                    detail=f"Document '{name}' requires revisions per authority review comments.",
                ))

        # 2. Authority Comments & Inspections
        open_comments = self._ps.get_open_comments(permit_id)
        pending_inspections = self._ps.get_pending_inspections(permit_id)
        requirements = self._ps.get_requirements_for_permit(permit_id)

        comment_texts = [
            f"[{c.get('severity', 'info').upper()}] {c.get('reviewer', 'Unknown')}: {c.get('comment', '')}"
            for c in open_comments
        ]
        inspection_issues = [
            f"Inspection '{i.get('inspection_type', 'unknown')}' is {i.get('status', 'pending')} (scheduled: {i.get('scheduled_date', 'TBD')})"
            for i in pending_inspections
        ]

        # 3. Requirement Coverage
        valid_doc_types = {
            doc.get("document_type")
            for doc_id in submitted_ids
            if (doc := self._ps.get_document(doc_id)) and doc.get("status") not in ("rejected", "revision_required")
        }
        requirement_issues: list[str] = [
            f"Requirement '{req.get('requirement', '')[:70]}...' requires valid '{needed}'."
            for req in requirements
            for needed in req.get("document_types_needed", [])
            if needed not in valid_doc_types
        ]

        # 4. Synthesize Blockers & Warnings
        blockers: list[str] = [f"Missing: {d.document_name}" for d in missing_docs]
        warnings: list[str] = []

        for d in invalid_docs:
            label = f"{d.issue_type.value.replace('_', ' ').title()}: {d.document_name}"
            if d.issue_type in (DocumentIssueType.REJECTED, DocumentIssueType.EXPIRED):
                blockers.append(label)
            else:
                warnings.append(label)

        for c in open_comments:
            if c.get("severity") in ("critical", "major"):
                blockers.append(f"Authority comment ({c.get('severity')}): {c.get('comment', '')[:80]}...")

        blockers.extend(requirement_issues)

        # 5. Calculate Score & Status
        total_checks = max(len(required_ids) + len(requirements) + len(open_comments) + len(pending_inspections), 1)
        issue_penalty = len(missing_docs) * 20 + len(invalid_docs) * 25 + len(open_comments) * 15 + len(requirement_issues) * 10
        readiness_score = max(0, min(100, 100 - int(issue_penalty / total_checks * 1.5))) if blockers else 95

        if not blockers and not warnings and permit.get("status") == "approved":
            status = ReadinessStatus.READY
        elif not blockers and not warnings:
            status = ReadinessStatus.NEEDS_REVIEW
        elif any(c.get("severity") == "critical" for c in open_comments) or any(d.issue_type == DocumentIssueType.EXPIRED for d in invalid_docs):
            status = ReadinessStatus.BLOCKED
        else:
            status = ReadinessStatus.NOT_READY

        # 6. Generate Actionable Recommendations
        recommended_actions = self._build_recommendations(
            missing_docs, invalid_docs, open_comments, pending_inspections
        )

        summary = (
            f"Permit {permit_id} ({permit.get('project_name', '')}) is {status.value} (Score: {readiness_score}/100). "
            f"Flagged {len(blockers)} blocker(s), {len(missing_docs)} missing doc(s), "
            f"{len(invalid_docs)} invalid doc(s), and {len(open_comments)} open AHJ comment(s)."
        )

        return PermitReadinessResult(
            permit_id=permit_id,
            project_name=permit.get("project_name", ""),
            permit_type=permit.get("permit_type", ""),
            jurisdiction=permit.get("jurisdiction", ""),
            current_status=permit.get("status", ""),
            readiness_status=status,
            readiness_score=readiness_score,
            summary=summary,
            missing_documents=missing_docs,
            invalid_documents=invalid_docs,
            requirement_issues=requirement_issues,
            authority_comments=comment_texts,
            inspection_issues=inspection_issues,
            blockers=blockers,
            warnings=warnings,
            evidence=[EvidenceItem(source="Readiness Audit", detail=b) for b in blockers[:5]],
            recommended_actions=recommended_actions,
            human_review_required=True,
        )

    def explain_blockers(self, permit_id: str) -> BlockerExplanation:
        """Provide detailed root-cause explanation for all blockers preventing submission."""
        readiness = self.check_readiness(permit_id)
        permit = self._ps.get_permit(permit_id)
        if not permit:
            raise ValueError(f"Permit '{permit_id}' not found.")

        primary = readiness.blockers[0] if readiness.blockers else "No active blockers identified."
        fix_steps = [a.action for a in readiness.recommended_actions[:3]]
        rec_fix = "Recommended steps: " + "; ".join(fix_steps) if fix_steps else "Review requirements with plans examiner."

        return BlockerExplanation(
            permit_id=permit_id,
            project_name=permit.get("project_name", ""),
            primary_blocker=primary,
            blocker_details=readiness.blockers,
            supporting_evidence=readiness.evidence,
            related_requirements=[r.get("requirement", "")[:80] for r in self._ps.get_requirements_for_permit(permit_id)],
            related_authority_comments=[c.get("comment", "")[:80] for c in self._ps.get_open_comments(permit_id)],
            recommended_fix=rec_fix,
            estimated_effort="2-5 business days depending on revision cycles.",
        )

    def generate_checklist(self, permit_id: str) -> ResubmissionChecklist:
        """Generate a sequential, prioritized checklist for resubmission."""
        readiness = self.check_readiness(permit_id)
        permit = self._ps.get_permit(permit_id)
        if not permit:
            raise ValueError(f"Permit '{permit_id}' not found.")

        items = [
            ChecklistItem(
                step_number=idx,
                action=act.action,
                reason=act.reason,
                priority=act.priority,
                evidence_source="Readiness Audit",
            )
            for idx, act in enumerate(readiness.recommended_actions, 1)
        ]

        # Add mandatory final compliance gate
        items.append(ChecklistItem(
            step_number=len(items) + 1,
            action="Perform final Human-in-the-Loop review before municipal portal upload",
            reason="All AHJ resubmissions require sign-off by a licensed PE or Permit Coordinator.",
            priority=ActionPriority.MEDIUM,
        ))

        return ResubmissionChecklist(
            permit_id=permit_id,
            project_name=permit.get("project_name", ""),
            permit_type=permit.get("permit_type", ""),
            jurisdiction=permit.get("jurisdiction", ""),
            total_items=len(items),
            critical_items=sum(1 for i in items if i.priority == ActionPriority.CRITICAL),
            checklist=items,
            general_notes=[
                "Address all critical items before resubmitting.",
                "Highlight revisions using revision clouds on drawings.",
                "Ensure contractor insurance and ROC licenses remain active.",
            ],
            human_review_required=True,
        )

    def _build_recommendations(
        self,
        missing_docs: list[DocumentIssue],
        invalid_docs: list[DocumentIssue],
        open_comments: list[dict],
        pending_inspections: list[dict],
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        for doc in missing_docs:
            actions.append(RecommendedAction(
                action=f"Upload required document: {doc.document_name}",
                reason=doc.detail,
                priority=ActionPriority.CRITICAL,
            ))

        for doc in invalid_docs:
            prio = ActionPriority.CRITICAL if doc.issue_type in (DocumentIssueType.EXPIRED, DocumentIssueType.REJECTED) else ActionPriority.HIGH
            actions.append(RecommendedAction(
                action=f"Update/revise {doc.issue_type.value}: {doc.document_name}",
                reason=doc.detail,
                priority=prio,
            ))

        for cmt in open_comments:
            prio = ActionPriority.CRITICAL if cmt.get("severity") == "critical" else ActionPriority.HIGH
            actions.append(RecommendedAction(
                action=f"Resolve authority comment from {cmt.get('reviewer', 'Examiner')}: {cmt.get('comment', '')[:70]}...",
                reason=f"Open {cmt.get('severity', 'info')} comment blocks approval.",
                priority=prio,
            ))

        for insp in pending_inspections:
            actions.append(RecommendedAction(
                action=f"Complete scheduled inspection: {insp.get('inspection_type', 'Inspection')}",
                reason=f"Status: {insp.get('status', 'pending')} (scheduled: {insp.get('scheduled_date', 'TBD')})",
                priority=ActionPriority.MEDIUM,
            ))

        return actions
