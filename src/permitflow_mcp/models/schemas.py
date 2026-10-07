"""Pydantic models for structured MCP tool outputs."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReadinessStatus(str, Enum):
    """Possible permit readiness statuses."""
    READY = "READY"
    NOT_READY = "NOT_READY"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DocumentIssueType(str, Enum):
    """Types of document issues."""
    MISSING = "missing"
    EXPIRED = "expired"
    REJECTED = "rejected"
    REVISION_REQUIRED = "revision_required"
    OUTDATED_VERSION = "outdated_version"


class ActionPriority(str, Enum):
    """Priority levels for recommended actions."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ---------------------------------------------------------------------------
# Evidence / citation models
# ---------------------------------------------------------------------------

class EvidenceItem(BaseModel):
    """A piece of evidence supporting a finding."""
    source: str = Field(description="Source of the evidence (document, authority comment, requirement, etc.)")
    detail: str = Field(description="The specific evidence text")
    reference: Optional[str] = Field(default=None, description="Code section or page reference")


class RAGChunk(BaseModel):
    """A retrieved chunk from the RAG pipeline."""
    text: str = Field(description="The retrieved text content")
    source: str = Field(description="Source document filename")
    section: Optional[str] = Field(default=None, description="Section heading if available")
    page: Optional[int] = Field(default=None, description="Page number if available")
    chunk_id: str = Field(description="Unique identifier for the chunk")
    relevance_score: float = Field(description="Similarity score (0-1, higher is better)")


# ---------------------------------------------------------------------------
# Document analysis models
# ---------------------------------------------------------------------------

class DocumentIssue(BaseModel):
    """An issue found with a permit document."""
    document_id: str
    document_name: str
    document_type: str
    issue_type: DocumentIssueType
    detail: str = Field(description="Human-readable explanation of the issue")
    evidence: Optional[EvidenceItem] = None


# ---------------------------------------------------------------------------
# Readiness analysis models
# ---------------------------------------------------------------------------

class RecommendedAction(BaseModel):
    """A recommended action for permit readiness."""
    action: str = Field(description="Description of the action to take")
    reason: str = Field(description="Why this action is needed")
    priority: ActionPriority
    evidence: Optional[EvidenceItem] = None


class PermitReadinessResult(BaseModel):
    """Complete result of a permit readiness check."""
    permit_id: str
    project_name: str
    permit_type: str
    jurisdiction: str
    current_status: str
    readiness_status: ReadinessStatus
    readiness_score: int = Field(
        ge=0, le=100,
        description="Score from 0 (not ready) to 100 (fully ready)",
    )
    summary: str = Field(description="Human-readable summary of readiness")
    missing_documents: list[DocumentIssue] = Field(default_factory=list)
    invalid_documents: list[DocumentIssue] = Field(default_factory=list)
    requirement_issues: list[str] = Field(default_factory=list)
    authority_comments: list[str] = Field(default_factory=list)
    inspection_issues: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    human_review_required: bool = Field(
        default=True,
        description="Whether human review is required before final submission",
    )


# ---------------------------------------------------------------------------
# Blocker analysis models
# ---------------------------------------------------------------------------

class BlockerExplanation(BaseModel):
    """Detailed explanation of a permit blocker."""
    permit_id: str
    project_name: str
    primary_blocker: str = Field(description="The main reason the permit is blocked")
    blocker_details: list[str] = Field(description="Detailed breakdown of blocking issues")
    supporting_evidence: list[EvidenceItem] = Field(default_factory=list)
    related_requirements: list[str] = Field(default_factory=list)
    related_authority_comments: list[str] = Field(default_factory=list)
    recommended_fix: str = Field(description="Recommended approach to resolve the blocker")
    estimated_effort: Optional[str] = Field(
        default=None,
        description="Rough estimate of effort to resolve (e.g., '2-3 business days')",
    )


# ---------------------------------------------------------------------------
# Resubmission checklist models
# ---------------------------------------------------------------------------

class ChecklistItem(BaseModel):
    """A single item in a resubmission checklist."""
    step_number: int
    action: str
    reason: str
    priority: ActionPriority
    evidence_source: Optional[str] = None
    notes: Optional[str] = None


class ResubmissionChecklist(BaseModel):
    """A prioritized resubmission checklist for a permit."""
    permit_id: str
    project_name: str
    permit_type: str
    jurisdiction: str
    total_items: int
    critical_items: int
    checklist: list[ChecklistItem]
    general_notes: list[str] = Field(default_factory=list)
    human_review_required: bool = Field(default=True)


# ---------------------------------------------------------------------------
# RAG search result models
# ---------------------------------------------------------------------------

class RequirementSearchResult(BaseModel):
    """Result from a RAG-based requirement search."""
    query: str
    jurisdiction: Optional[str] = None
    permit_type: Optional[str] = None
    results: list[RAGChunk] = Field(default_factory=list)
    total_results: int = 0
    summary: str = Field(default="", description="Human-readable summary of findings")


# ---------------------------------------------------------------------------
# Permit status model
# ---------------------------------------------------------------------------

class PermitStatusResult(BaseModel):
    """Current status of a permit."""
    permit_id: str
    project_id: str
    project_name: str
    permit_type: str
    jurisdiction: str
    status: str
    submission_date: Optional[str] = None
    target_date: Optional[str] = None
    last_updated: str
    documents_submitted: int
    documents_required: int
    open_comments: int
    inspection_status: str
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Portfolio-Level Intelligence Models
# ---------------------------------------------------------------------------

class RiskTier(str, Enum):
    """Portfolio risk tier classifications."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class PortfolioRankingFactor(BaseModel):
    """An individual factor contributing to a permit's portfolio risk score."""
    factor_name: str = Field(description="Name of the risk factor (e.g. 'Critical AHJ Comment')")
    impact_points: int = Field(description="Points added to the risk score")
    detail: str = Field(description="Human-readable description of this factor")
    evidence: Optional[EvidenceItem] = None


class PermitRiskRank(BaseModel):
    """A ranked permit inside the portfolio risk hierarchy."""
    rank: int = Field(description="Portfolio priority rank (1 = highest urgency)")
    permit_id: str
    project_name: str
    project_id: str
    permit_type: str
    jurisdiction: str
    status: str
    risk_score: int = Field(ge=0, le=100, description="Composite risk score from 0 (healthy) to 100 (critical)")
    risk_tier: RiskTier
    target_date: Optional[str] = None
    days_until_deadline: Optional[int] = None
    primary_risk_drivers: list[str] = Field(default_factory=list)
    factors: list[PortfolioRankingFactor] = Field(default_factory=list)
    recommended_first_step: str = Field(description="The single most important immediate action")


class PortfolioRankingReport(BaseModel):
    """Complete portfolio ranking analysis across all permits."""
    generated_at: str
    total_permits_analyzed: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    ranked_permits: list[PermitRiskRank]
    executive_summary: str


class PortfolioChangeType(str, Enum):
    """Categories of portfolio-level changes."""
    STATUS_CHANGE = "status_change"
    NEW_COMMENT = "new_comment"
    DOCUMENT_EXPIRED = "document_expired"
    INSPECTION_UPDATE = "inspection_update"
    BLOCKER_ADDED = "blocker_added"


class PortfolioChangeItem(BaseModel):
    """A specific change detected in the portfolio compared to previous state."""
    change_type: PortfolioChangeType
    permit_id: str
    project_name: str
    title: str
    detail: str
    severity: str = Field(default="medium", description="critical, high, medium, or low")
    timestamp: Optional[str] = None


class PortfolioChangeReport(BaseModel):
    """Report detailing changes across the portfolio since previous snapshot."""
    compared_date: str
    current_date: str
    total_changes: int
    changes_by_type: dict[str, int] = Field(default_factory=dict)
    changes: list[PortfolioChangeItem] = Field(default_factory=list)
    summary: str


class SystemicBottleneckItem(BaseModel):
    """A systemic bottleneck impacting multiple permits across the portfolio."""
    bottleneck_title: str
    category: str = Field(description="e.g., Insurance, Engineering Calculations, Code Compliance")
    affected_permits: list[str] = Field(description="List of permit IDs affected")
    affected_projects: list[str] = Field(description="List of project names affected")
    prevalence_percentage: float = Field(description="Percentage of active/blocked permits affected")
    root_cause: str = Field(description="Underlying reason causing this bottleneck")
    jurisdiction_patterns: list[str] = Field(default_factory=list)
    recommended_portfolio_fix: str = Field(description="Strategic operational fix to prevent this issue across all projects")


class SystemicBottlenecksReport(BaseModel):
    """Portfolio-wide systemic bottlenecks and pattern analysis."""
    total_permits_evaluated: int
    bottlenecks: list[SystemicBottleneckItem]
    strategic_recommendations: list[str]


class DailyActionTask(BaseModel):
    """A prioritized action item for permit managers and coordinators."""
    task_id: str
    priority_rank: int
    urgency: str = Field(description="'Urgent Today', 'This Week', or 'Scheduled'")
    permit_id: str
    project_name: str
    action: str
    rationale: str
    assigned_role: str = Field(description="Role responsible (e.g. 'Permit Coordinator', 'PE Mechanical')")
    deadline: Optional[str] = None
    blocking_factor: str


class DailyManagerBriefing(BaseModel):
    """Daily prioritized executive briefing for the permit manager."""
    briefing_date: str
    portfolio_health_score: int = Field(ge=0, le=100, description="Overall health (100 = all on track, 0 = severe distress)")
    total_active_permits: int
    permits_needing_immediate_attention: int
    top_actions_today: list[DailyActionTask]
    key_changes_since_yesterday: list[str]
    top_systemic_bottlenecks: list[str]
    executive_summary: str

