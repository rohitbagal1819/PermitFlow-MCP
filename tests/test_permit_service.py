"""Unit tests for PermitService."""

import pytest
from permitflow_mcp.services.permit_service import PermitService


@pytest.fixture
def permit_service():
    service = PermitService()
    service.load_data()
    return service


def test_load_data(permit_service):
    permits = permit_service.list_permits()
    assert len(permits) >= 5
    assert any(p["permit_id"] == "P-1042" for p in permits)


def test_get_permit_existing(permit_service):
    permit = permit_service.get_permit("P-1042")
    assert permit is not None
    assert permit["permit_id"] == "P-1042"
    assert permit["project_id"] == "PROJECT-001"
    assert permit["jurisdiction"] == "City of Phoenix"


def test_get_permit_nonexistent(permit_service):
    permit = permit_service.get_permit("P-NONEXISTENT")
    assert permit is None


def test_get_project(permit_service):
    project = permit_service.get_project("PROJECT-001")
    assert project is not None
    assert project["project_name"] == "Phoenix Commercial Plaza"


def test_get_documents_for_permit(permit_service):
    docs = permit_service.get_documents_for_permit("P-1042")
    assert len(docs) > 0


def test_get_open_comments(permit_service):
    comments = permit_service.get_open_comments("P-1042")
    assert len(comments) >= 3
    assert any(c["comment_id"] == "CMT-401" for c in comments)


def test_get_inspections(permit_service):
    inspections = permit_service.get_inspections_for_permit("P-1050")
    assert len(inspections) >= 1
    assert inspections[0]["inspection_type"] == "foundation"


def test_get_requirements(permit_service):
    reqs = permit_service.get_requirements_for_permit("P-1042")
    assert len(reqs) >= 1

    by_jur = permit_service.get_requirements_by_jurisdiction("City of Phoenix", "mechanical")
    assert len(by_jur) >= 1
    assert any("HVAC" in r["requirement"] or "mechanical" in r.get("permit_type", "") for r in by_jur)

    # Test flexible case-insensitive matching
    by_case = permit_service.get_requirements_by_jurisdiction("phoenix", "mechanical")
    assert len(by_case) >= 1


def test_get_contractor(permit_service):
    contractor = permit_service.get_contractor("Ironclad Construction")
    assert contractor is not None
    assert contractor["roc_license"] == "ROC-329482"
    assert contractor["license_class"] == "B-1"

    # Test by ROC number
    by_roc = permit_service.get_contractor("ROC-284719")
    assert by_roc is not None
    assert by_roc["name"] == "SunState Electric"


