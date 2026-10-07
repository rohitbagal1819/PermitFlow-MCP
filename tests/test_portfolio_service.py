"""Unit tests for PortfolioService (Portfolio-Level Intelligence)."""

import pytest
from permitflow_mcp.models.schemas import RiskTier
from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.portfolio_service import PortfolioService
from permitflow_mcp.services.readiness_service import ReadinessService


@pytest.fixture
def portfolio_service():
    ps = PermitService()
    ps.load_data()
    rs = ReadinessService(ps)
    return PortfolioService(ps, rs)


def test_rank_permits(portfolio_service):
    report = portfolio_service.rank_permits()
    assert report.total_permits_analyzed >= 5
    assert len(report.ranked_permits) == report.total_permits_analyzed

    # Ranking 1..N order
    for idx, item in enumerate(report.ranked_permits, 1):
        assert item.rank == idx

    # Highest risk score at top
    assert report.ranked_permits[0].risk_score >= report.ranked_permits[-1].risk_score

    # Check top permits are high or critical tier
    top_permit = report.ranked_permits[0]
    assert top_permit.risk_tier in (RiskTier.CRITICAL, RiskTier.HIGH)
    assert len(top_permit.factors) > 0
    assert top_permit.recommended_first_step != ""


def test_detect_changes(portfolio_service):
    report = portfolio_service.detect_changes()
    assert report.compared_date != ""
    assert report.total_changes >= 1
    assert len(report.changes) == report.total_changes
    # Status changes or comments should be found
    assert any(c.change_type.value == "status_change" for c in report.changes)


def test_identify_systemic_bottlenecks(portfolio_service):
    report = portfolio_service.identify_systemic_bottlenecks()
    assert report.total_permits_evaluated >= 5
    assert len(report.bottlenecks) >= 3
    # Insurance bottleneck should be surfaced
    assert any("Insurance" in b.category for b in report.bottlenecks)
    assert len(report.strategic_recommendations) > 0


def test_generate_daily_action_plan(portfolio_service):
    tasks = portfolio_service.generate_daily_action_plan()
    assert len(tasks) >= 3
    # Critical urgent tasks should be first
    assert tasks[0].urgency == "Urgent Today"
    assert tasks[0].assigned_role != ""
    assert tasks[0].blocking_factor != ""


def test_get_daily_briefing(portfolio_service):
    briefing = portfolio_service.get_daily_briefing()
    assert 0 <= briefing.portfolio_health_score <= 100
    assert briefing.total_active_permits >= 5
    assert len(briefing.top_actions_today) > 0
    assert len(briefing.key_changes_since_yesterday) > 0
    assert len(briefing.top_systemic_bottlenecks) > 0
