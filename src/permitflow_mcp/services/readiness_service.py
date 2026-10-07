"""Readiness analysis service – the core analysis engine."""

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
    """Analyses permit data and determines readiness for submission."""

    def __init__(self, permit_service: PermitService) -> None:
        self._ps = permit_service

    # ------------------------------------------------------------------
    # Document analysis helpers
    # ------------------------------------------------------------------

    def _find_missing_documents(self, permit_id: str) -> list[DocumentIssue]:
        """Identify documents that are required but not submitted."""
        permit = self._ps.get_permit(permit_id)
        if not permit:
            return []

        required_ids = set(permit.get("required_document_ids", []))
        submitted_ids = set(permit.get("submitted_document_ids", []))
        missing_ids = required_ids - submitted_ids

        issues: list[DocumentIssue] = []
        for doc_id in missing_ids:
            doc = self._ps.get_document(doc_id)
            if doc:
                issues.append(
                    DocumentIssue(
                        document_id=doc_id,
                        document_name=doc.get("document_name", doc_id),
                        document_type=doc.get("document_type", "unknown"),
                        issue_type=DocumentIssueType.MISSING,
                        detail=f"Required document '{doc.get('document_name', doc_id)}' has not been submitted.",
                    )
                )
            else:
                issues.append(
                    DocumentIssue(
                        document_id=doc_id,
                        document_name=doc_id,
                        document_type="unknown",
                        issue_type=DocumentIssueType.MISSING,
                        detail=f"Required document {doc_id} has not been submitted and no metadata is available.",
                    )
                )
        return issues

    def _find_invalid_documents(self, permit_id: str) -> list[DocumentIssue]:
        """Identify documents that are expired, rejected, or need revision."""
        permit = self._ps.get_permit(permit_id)
        if not permit:
            return []

        submitted_ids = set(permit.get("submitted_document_ids", []))
        issues: list[DocumentIssue] = []
        today = date.today()

        for doc_id in submitted_ids:
            doc = self._ps.get_document(doc_id)
            if not doc:
                continue

            status = doc.get("status", "")

            # Expired document
            expiry = doc.get("expiry_date")
            if expiry:
                try:
                    expiry_date = datetime.strptime(expiry, "%Y-%m-%d").date()
                    if expiry_date < today:
                        issues.append(
                            DocumentIssue(
                                document_id=doc_id,
                                document_name=doc.get("document_name", doc_id),
                                document_type=doc.get("document_type", "unknown"),
                                issue_type=DocumentIssueType.EXPIRED,
                                detail=(
                                    f"Document '{doc.get('document_name', doc_id)}' expired on {expiry}. "
                                    "A current, valid document must be provided."
                                ),
                                evidence=EvidenceItem(
                                    source="Document metadata",
                                    detail=f"Expiry date: {expiry}",
                                ),
                            )
                        )
                        continue
                except ValueError:
                    pass

            # Rejected document
            if status == "rejected":
                issues.append(
                    DocumentIssue(
                        document_id=doc_id,
                        document_name=doc.get("document_name", doc_id),
                        document_type=doc.get("document_type", "unknown"),
                        issue_type=DocumentIssueType.REJECTED,
                        detail=f"Document '{doc.get('document_name', doc_id)}' was rejected and must be revised and resubmitted.",
                    )
                )

            # Revision required
            elif status == "revision_required":
                issues.append(
                    DocumentIssue(
                        document_id=doc_id,
                        document_name=doc.get("document_name", doc_id),
                        document_type=doc.get("document_type", "unknown"),
                        issue_type=DocumentIssueType.REVISION_REQUIRED,
                        detail=f"Document '{doc.get('document_name', doc_id)}' requires revision per authority comments.",
                    )
                )

        return issues

    # ------------------------------------------------------------------
    # Main readiness check
    # ------------------------------------------------------------------

    def check_readiness(self, permit_id: str) -> PermitReadinessResult:
        """Perform a comprehensive readiness check for a permit."""
        permit = self._ps.get_permit(permit_id)
        if not permit:
            raise ValueError(f"Permit '{permit_id}' not found. Please verify the permit ID.")

        logger.info("[Readiness] Checking readiness for permit %s", permit_id)

        # Gather issues
        missing_docs = self._find_missing_documents(permit_id)
        invalid_docs = self._find_invalid_documents(permit_id)
        open_comments = self._ps.get_open_comments(permit_id)
        pending_inspections = self._ps.get_pending_inspections(permit_id)
        requirements = self._ps.get_requirements_for_permit(permit_id)

        # Build authority comment summaries
        comment_texts: list[str] = []
        for cmt in open_comments:
            comment_texts.append(
                f"[{cmt.get('severity', 'info').upper()}] {cmt.get('reviewer', 'Unknown')}: {cmt.get('comment', '')}"
            )

        # Build inspection issues
        inspection_issues: list[str] = []
        for insp in pending_inspections:
            inspection_issues.append(
                f"Inspection '{insp.get('inspection_type', 'unknown')}' is {insp.get('status', 'unknown')} "
                f"(scheduled: {insp.get('scheduled_date', 'TBD')})"
            )

        # Check requirement coverage
        requirement_issues: list[str] = []
        submitted_doc_types = set()
        for doc_id in permit.get("submitted_document_ids", []):
            doc = self._ps.get_document(doc_id)
            if doc and doc.get("status") not in ("rejected", "revision_required"):
                submitted_doc_types.add(doc.get("document_type"))

        for req in requirements:
            needed_types = req.get("document_types_needed", [])
            for needed_type in needed_types:
                if needed_type not in submitted_doc_types:
                    requirement_issues.append(
                        f"Requirement '{req.get('requirement', '')[:80]}...' "
                        f"(Ref: {req.get('reference', 'N/A')}) needs a valid '{needed_type}' document."
                    )

        # Build blockers list
        blockers: list[str] = []
        warnings: list[str] = []
        evidence: list[EvidenceItem] = []

        for doc_issue in missing_docs:
            blockers.append(f"Missing: {doc_issue.document_name}")
            evidence.append(
                EvidenceItem(source="Document check", detail=doc_issue.detail)
            )

        for doc_issue in invalid_docs:
            if doc_issue.issue_type in (DocumentIssueType.REJECTED, DocumentIssueType.EXPIRED):
                blockers.append(f"{doc_issue.issue_type.value.replace('_', ' ').title()}: {doc_issue.document_name}")
            else:
                warnings.append(f"{doc_issue.issue_type.value.replace('_', ' ').title()}: {doc_issue.document_name}")
            evidence.append(
                EvidenceItem(source="Document check", detail=doc_issue.detail)
            )

        for cmt in open_comments:
            if cmt.get("severity") in ("critical", "major"):
                blockers.append(f"Authority comment ({cmt.get('severity')}): {cmt.get('comment', '')[:100]}...")
            evidence.append(
                EvidenceItem(
                    source=f"Authority comment by {cmt.get('reviewer', 'Unknown')}",
                    detail=cmt.get("comment", ""),
                    reference=cmt.get("comment_id"),
                )
            )

        for ri in requirement_issues:
            blockers.append(ri)

        # Rejection history
        for rejection in permit.get("rejection_history", []):
            evidence.append(
                EvidenceItem(
                    source=f"Rejection by {rejection.get('reviewer', 'Unknown')} on {rejection.get('date', 'N/A')}",
                    detail=rejection.get("reason", ""),
                )
            )

        # Calculate readiness score
        total_checks = max(
            len(permit.get("required_document_ids", []))
            + len(requirements)
            + (1 if open_comments else 0)
            + (1 if pending_inspections else 0),
            1,
        )
        issues_count = len(missing_docs) + len(invalid_docs) + len(requirement_issues) + len(open_comments)
        readiness_score = max(0, int(100 * (1 - issues_count / total_checks)))

        # Determine overall status
        if not blockers and not warnings and permit.get("status") == "approved":
            readiness_status = ReadinessStatus.READY
        elif not blockers and not warnings:
            readiness_status = ReadinessStatus.NEEDS_REVIEW
        elif any(c.get("severity") == "critical" for c in open_comments):
            readiness_status = ReadinessStatus.BLOCKED
        else:
            readiness_status = ReadinessStatus.NOT_READY

        # Generate recommended actions
        recommended_actions = self._build_recommendations(
            missing_docs, invalid_docs, open_comments, requirement_issues, pending_inspections
        )

        # Build summary
        if readiness_status == ReadinessStatus.READY:
            summary = (
                f"Permit {permit_id} for '{permit.get('project_name', '')}' is READY. "
                f"All required documents are submitted and valid. No outstanding authority comments."
            )
        else:
            summary = (
                f"Permit {permit_id} for '{permit.get('project_name', '')}' is {readiness_status.value}. "
                f"Found {len(blockers)} blocker(s) and {len(warnings)} warning(s). "
                f"{len(missing_docs)} missing document(s), {len(invalid_docs)} invalid document(s), "
                f"{len(open_comments)} open authority comment(s)."
            )

        return PermitReadinessResult(
            permit_id=permit_id,
            project_name=permit.get("project_name", ""),
            permit_type=permit.get("permit_type", ""),
            jurisdiction=permit.get("jurisdiction", ""),
            current_status=permit.get("status", ""),
            readiness_status=readiness_status,
            readiness_score=readiness_score,
            summary=summary,
            missing_documents=missing_docs,
            invalid_documents=invalid_docs,
            requirement_issues=requirement_issues,
            authority_comments=comment_texts,
            inspection_issues=inspection_issues,
            blockers=blockers,
            warnings=warnings,
            evidence=evidence,
            recommended_actions=recommended_actions,
            human_review_required=True,
        )

    # ------------------------------------------------------------------
    # Blocker explanation
    # ------------------------------------------------------------------

    def explain_blockers(self, permit_id: str) -> BlockerExplanation:
        """Explain why a permit is blocked."""
        readiness = self.check_readiness(permit_id)
        permit = self._ps.get_permit(permit_id)
        if not permit:
            raise ValueError(f"Permit '{permit_id}' not found.")

        if not readiness.blockers:
            primary = "No blockers found – permit may be ready for submission or review."
        else:
            primary = readiness.blockers[0]

        # Collect requirement references
        requirements = self._ps.get_requirements_for_permit(permit_id)
        related_reqs = [
            f"{r.get('reference', 'N/A')}: {r.get('requirement', '')[:100]}"
            for r in requirements
        ]

        comments = self._ps.get_open_comments(permit_id)
        related_comments = [
            f"[{c.get('comment_id')}] {c.get('reviewer', 'Unknown')}: {c.get('comment', '')[:120]}..."
            for c in comments
        ]

        # Build fix recommendation
        if readiness.recommended_actions:
            fix_parts = [a.action for a in readiness.recommended_actions[:3]]
            recommended_fix = "Recommended steps: " + "; ".join(fix_parts)
        else:
            recommended_fix = "No specific fix identified. Please review the permit requirements and authority comments."

        return BlockerExplanation(
            permit_id=permit_id,
            project_name=permit.get("project_name", ""),
            primary_blocker=primary,
            blocker_details=readiness.blockers,
            supporting_evidence=readiness.evidence,
            related_requirements=related_reqs,
            related_authority_comments=related_comments,
            recommended_fix=recommended_fix,
            estimated_effort="2-5 business days (depending on document preparation time)",
        )

    # ------------------------------------------------------------------
    # Resubmission checklist
    # ------------------------------------------------------------------

    def generate_checklist(self, permit_id: str) -> ResubmissionChecklist:
        """Generate a prioritized resubmission checklist."""
        readiness = self.check_readiness(permit_id)
        permit = self._ps.get_permit(permit_id)
        if not permit:
            raise ValueError(f"Permit '{permit_id}' not found.")

        items: list[ChecklistItem] = []
        step = 0

        # Critical actions first
        for action in readiness.recommended_actions:
            if action.priority == ActionPriority.CRITICAL:
                step += 1
                items.append(
                    ChecklistItem(
                        step_number=step,
                        action=action.action,
                        reason=action.reason,
                        priority=ActionPriority.CRITICAL,
                        evidence_source=action.evidence.source if action.evidence else None,
                    )
                )

        # High priority
        for action in readiness.recommended_actions:
            if action.priority == ActionPriority.HIGH:
                step += 1
                items.append(
                    ChecklistItem(
                        step_number=step,
                        action=action.action,
                        reason=action.reason,
                        priority=ActionPriority.HIGH,
                        evidence_source=action.evidence.source if action.evidence else None,
                    )
                )

        # Medium priority
        for action in readiness.recommended_actions:
            if action.priority == ActionPriority.MEDIUM:
                step += 1
                items.append(
                    ChecklistItem(
                        step_number=step,
                        action=action.action,
                        reason=action.reason,
                        priority=ActionPriority.MEDIUM,
                        evidence_source=action.evidence.source if action.evidence else None,
                    )
                )

        # Low priority
        for action in readiness.recommended_actions:
            if action.priority == ActionPriority.LOW:
                step += 1
                items.append(
                    ChecklistItem(
                        step_number=step,
                        action=action.action,
                        reason=action.reason,
                        priority=ActionPriority.LOW,
                        evidence_source=action.evidence.source if action.evidence else None,
                    )
                )

        # Always add a final human review step
        step += 1
        items.append(
            ChecklistItem(
                step_number=step,
                action="Submit revised application for human review",
                reason="All permit submissions require human review by the authority having jurisdiction before approval.",
                priority=ActionPriority.MEDIUM,
                notes="Human review required before final submission.",
            )
        )

        critical_count = sum(1 for i in items if i.priority == ActionPriority.CRITICAL)

        general_notes = [
            "Address all critical items before resubmission.",
            "Include a written response to each authority comment.",
            "Use revision clouds to highlight changes on drawings.",
            "Verify all documents are current and not expired.",
            "Human review required before final submission.",
        ]

        return ResubmissionChecklist(
            permit_id=permit_id,
            project_name=permit.get("project_name", ""),
            permit_type=permit.get("permit_type", ""),
            jurisdiction=permit.get("jurisdiction", ""),
            total_items=len(items),
            critical_items=critical_count,
            checklist=items,
            general_notes=general_notes,
            human_review_required=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_recommendations(
        self,
        missing_docs: list[DocumentIssue],
        invalid_docs: list[DocumentIssue],
        open_comments: list[dict],
        requirement_issues: list[str],
        pending_inspections: list[dict],
    ) -> list[RecommendedAction]:
        actions: list[RecommendedAction] = []

        # Missing documents → critical
        for doc in missing_docs:
            actions.append(
                RecommendedAction(
                    action=f"Upload required document: {doc.document_name}",
                    reason=doc.detail,
                    priority=ActionPriority.CRITICAL,
                    evidence=EvidenceItem(source="Document check", detail=doc.detail),
                )
            )

        # Expired documents → critical
        for doc in invalid_docs:
            if doc.issue_type == DocumentIssueType.EXPIRED:
                actions.append(
                    RecommendedAction(
                        action=f"Provide a current, non-expired version of: {doc.document_name}",
                        reason=doc.detail,
                        priority=ActionPriority.CRITICAL,
                        evidence=EvidenceItem(source="Document check", detail=doc.detail),
                    )
                )
            elif doc.issue_type == DocumentIssueType.REJECTED:
                actions.append(
                    RecommendedAction(
                        action=f"Revise and resubmit rejected document: {doc.document_name}",
                        reason=doc.detail,
                        priority=ActionPriority.CRITICAL,
                        evidence=EvidenceItem(source="Document check", detail=doc.detail),
                    )
                )
            elif doc.issue_type == DocumentIssueType.REVISION_REQUIRED:
                actions.append(
                    RecommendedAction(
                        action=f"Revise document per authority comments: {doc.document_name}",
                        reason=doc.detail,
                        priority=ActionPriority.HIGH,
                        evidence=EvidenceItem(source="Document check", detail=doc.detail),
                    )
                )

        # Authority comments → high
        for cmt in open_comments:
            actions.append(
                RecommendedAction(
                    action=f"Address authority comment: {cmt.get('comment', '')[:80]}...",
                    reason=f"Open {cmt.get('severity', 'info')} comment from {cmt.get('reviewer', 'Unknown')}",
                    priority=(
                        ActionPriority.CRITICAL
                        if cmt.get("severity") == "critical"
                        else ActionPriority.HIGH
                    ),
                    evidence=EvidenceItem(
                        source=f"Authority comment {cmt.get('comment_id', '')}",
                        detail=cmt.get("comment", ""),
                    ),
                )
            )

        # Pending inspections → medium
        for insp in pending_inspections:
            actions.append(
                RecommendedAction(
                    action=f"Complete pending inspection: {insp.get('inspection_type', 'unknown')}",
                    reason=f"Inspection is {insp.get('status', 'pending')} (scheduled: {insp.get('scheduled_date', 'TBD')})",
                    priority=ActionPriority.MEDIUM,
                )
            )

        return actions
