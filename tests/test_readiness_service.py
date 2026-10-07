"""Unit tests for ReadinessService."""

import pytest
from permitflow_mcp.models.schemas import ReadinessStatus
from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.readiness_service import ReadinessService


@pytest.fixture
def readiness_service():
    ps = PermitService()
    ps.load_data()
    return ReadinessService(ps)


def test_check_readiness_approved_permit(readiness_service):
    # P-1001 is approved and has all required documents
    result = readiness_service.check_readiness("P-1001")
    assert result.permit_id == "P-1001"
    assert result.readiness_status == ReadinessStatus.READY
    assert result.readiness_score >= 90
    assert len(result.missing_documents) == 0


def test_check_readiness_revision_required_permit(readiness_service):
    # P-1042 is revision_required, missing documents, open comments
    result = readiness_service.check_readiness("P-1042")
    assert result.permit_id == "P-1042"
    assert result.readiness_status in (ReadinessStatus.BLOCKED, ReadinessStatus.NOT_READY)
    assert len(result.missing_documents) > 0
    assert len(result.authority_comments) > 0
    assert len(result.blockers) > 0
    assert len(result.recommended_actions) > 0


def test_explain_blockers(readiness_service):
    blocker_info = readiness_service.explain_blockers("P-1042")
    assert blocker_info.permit_id == "P-1042"
    assert len(blocker_info.blocker_details) > 0
    assert blocker_info.recommended_fix != ""


def test_generate_checklist(readiness_service):
    checklist = readiness_service.generate_checklist("P-1042")
    assert checklist.permit_id == "P-1042"
    assert checklist.total_items > 0
    assert checklist.critical_items > 0
    assert any(item.priority.value == "critical" for item in checklist.checklist)
