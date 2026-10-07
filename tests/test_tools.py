"""Unit tests for MCP Tools."""

import pytest
from mcp.server.fastmcp import FastMCP
from permitflow_mcp.rag.retriever import Retriever
from permitflow_mcp.services.permit_service import PermitService
from permitflow_mcp.services.portfolio_service import PortfolioService
from permitflow_mcp.services.readiness_service import ReadinessService
from permitflow_mcp.tools.permit_tools import register_tools
from permitflow_mcp.tools.portfolio_tools import register_portfolio_tools


@pytest.fixture
def test_setup():
    mcp = FastMCP("test-server")
    ps = PermitService()
    ps.load_data()
    rs = ReadinessService(ps)
    retriever = Retriever()
    portfolio_service = PortfolioService(ps, rs)

    tools = register_tools(mcp, ps, rs, retriever)
    portfolio_tools = register_portfolio_tools(mcp, portfolio_service)

    return {
        "mcp": mcp,
        "tools": tools,
        "portfolio_tools": portfolio_tools,
        "ps": ps,
        "rs": rs,
        "portfolio_service": portfolio_service,
        "retriever": retriever,
    }


def test_tool_check_permit_readiness(test_setup):
    fn = test_setup["tools"]["check_permit_readiness"]
    output = fn("P-1042")
    assert "PERMIT READINESS REPORT" in output
    assert "P-1042" in output
    assert "Score:" in output


def test_tool_find_missing_documents(test_setup):
    fn = test_setup["tools"]["find_missing_documents"]
    output = fn("P-1042")
    assert "DOCUMENT STATUS REPORT" in output


def test_tool_explain_permit_blocker(test_setup):
    fn = test_setup["tools"]["explain_permit_blocker"]
    output = fn("P-1042")
    assert "BLOCKER ANALYSIS" in output
    assert "Primary Blocker" in output


def test_tool_search_permit_requirements(test_setup):
    fn = test_setup["tools"]["search_permit_requirements"]
    output = fn("HVAC requirements commercial")
    assert "REQUIREMENT SEARCH RESULTS" in output
    assert "Results found:" in output


def test_tool_generate_resubmission_checklist(test_setup):
    fn = test_setup["tools"]["generate_resubmission_checklist"]
    output = fn("P-1042")
    assert "RESUBMISSION CHECKLIST" in output
    assert "Step 1:" in output


def test_tool_get_permit_status(test_setup):
    fn = test_setup["tools"]["get_permit_status"]
    output = fn("P-1001")
    assert "PERMIT STATUS" in output
    assert "P-1001" in output


def test_tool_analyze_portfolio_priorities(test_setup):
    fn = test_setup["portfolio_tools"]["analyze_portfolio_priorities"]
    output = fn(limit=5)
    assert "PORTFOLIO RISK & PRIORITY RANKING" in output
    assert "#1" in output
    assert "Risk Score:" in output
    assert "NEXT STEP:" in output


def test_tool_get_daily_manager_briefing(test_setup):
    fn = test_setup["portfolio_tools"]["get_daily_manager_briefing"]
    output = fn()
    assert "DAILY MANAGER EXECUTIVE BRIEFING" in output
    assert "Portfolio Health Score:" in output
    assert "TODAY'S PRIORITIZED ACTION TASK MATRIX" in output


def test_tool_detect_portfolio_changes(test_setup):
    fn = test_setup["portfolio_tools"]["detect_portfolio_changes"]
    output = fn()
    assert "PORTFOLIO DAY-OVER-DAY CHANGE REPORT" in output
    assert "Total Changes:" in output


def test_tool_analyze_systemic_bottlenecks(test_setup):
    fn = test_setup["portfolio_tools"]["analyze_systemic_bottlenecks"]
    output = fn()
    assert "PORTFOLIO SYSTEMIC BOTTLENECKS ANALYSIS" in output
    assert "INSURANCE" in output.upper()


def test_tool_update_permit_status(test_setup):
    fn = test_setup["tools"]["update_permit_status"]
    output = fn("P-1003", "approved", notes="Revisions accepted by City of Tempe")
    assert "successfully updated" in output
    assert "APPROVED" in output

    # Verify live update reflected in permit service
    permit = test_setup["ps"].get_permit("P-1003")
    assert permit["status"] == "approved"


def test_tool_resolve_authority_comment(test_setup):
    fn = test_setup["tools"]["resolve_authority_comment"]
    output = fn("CMT-301", resolution_notes="Electrical calculations recalculated per NEC 2023")
    assert "RESOLVED" in output
    assert "CMT-301" in output


def test_tool_update_document_status(test_setup):
    fn = test_setup["tools"]["update_document_status"]
    output = fn("DOC-301", "approved", notes="Revised drawings accepted")
    assert "DOC-301" in output
    assert "APPROVED" in output
    doc = test_setup["ps"].get_document("DOC-301")
    assert doc["status"] == "approved"


def test_tool_intake_project_scope(test_setup):
    fn = test_setup["tools"]["intake_project_scope"]
    output = fn(
        scope_description="Replacing two 7.5-ton rooftop HVAC units with new ductwork",
        address="4800 E Camelback Rd, Phoenix, AZ",
        valuation=185000.0,
    )
    assert "PROJECT INTAKE & SCOPE ANALYSIS" in output
    assert "City of Phoenix" in output
    assert "MECHANICAL" in output
    assert "Draft Permit ID:" in output


def test_tool_estimate_permit_fees_and_sla(test_setup):
    fn = test_setup["tools"]["estimate_permit_fees_and_sla"]
    output = fn(
        jurisdiction="City of Phoenix",
        permit_type="mechanical",
        valuation=120000.0,
    )
    assert "MUNICIPAL PERMIT FEE & REVIEW SLA ESTIMATE" in output
    assert "TOTAL ESTIMATED CITY FEES:" in output
    assert "business days" in output


def test_tool_generate_formal_ahj_response_packet(test_setup):
    fn = test_setup["tools"]["generate_formal_ahj_response_packet"]
    output = fn("P-1042")
    assert "FORMAL WRITTEN RESPONSE TO PLAN REVIEW COMMENTS" in output
    assert "CMT-401" in output
    assert "ASHRAE Standard 90.1" in output


def test_tool_verify_contractor_registration(test_setup):
    fn = test_setup["tools"]["verify_contractor_registration"]
    output = fn(
        contractor_name="Ironclad Construction",
        jurisdiction="City of Phoenix",
        permit_type="building",
    )
    assert "CONTRACTOR LICENSE & INSURANCE COMPLIANCE AUDIT" in output
    assert "Ironclad Construction" in output
    assert "ROC-329482" in output


