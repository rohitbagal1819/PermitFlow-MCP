# PermitFlow MCP: Portfolio Permitting Intelligence & Readiness Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Package Manager](https://img.shields.io/badge/package%20manager-uv-purple.svg)](https://docs.astral.sh/uv/)
[![Protocol](https://img.shields.io/badge/protocol-Model%20Context%20Protocol%20(MCP)-orange.svg)](https://modelcontextprotocol.io/)
[![Architecture](https://img.shields.io/badge/architecture-FastMCP%20%2B%20RAG-green.svg)](https://github.com/modelcontextprotocol/python-sdk)

> **Disclaimer**: This is an independent educational prototype inspired by PermitFlow's publicly described construction permitting workflow. It is built strictly for demonstration and assignment purposes, does not connect to PermitFlow's private production systems, and requires no proprietary credentials.

> 🎓 **Instructor Presentation & Live Demo**: For the complete 5-minute presentation script, exact copy-paste prompts, RAG document explanations, expected tool outputs, and Q&A cheat sheet, see **[`PRESENTATION_GUIDE.md`](PRESENTATION_GUIDE.md)**.

---

## 🌟 The Core Value Proposition: Portfolio-Level Intelligence

In commercial and residential construction, permitting coordinators typically monitor dozens of active permits across multiple municipalities (City of Phoenix, Tempe, Scottsdale, Mesa, Chandler).

Standard tools only answer single-permit lookup questions:
> *"Is permit P-1042 ready?"*

**PermitFlow MCP delivers Portfolio-Level Intelligence**, allowing project managers, general contractors, and developers to analyze all permits simultaneously:
> *"Which permits need attention first, why, and what should the team do today?"*

```
┌────────────────────────────────────────────────────────────────────────┐
│                        PORTFOLIO INTELLIGENCE                          │
├────────────────────────────────┬───────────────────────────────────────┤
│ 🚨 Multi-Factor Risk Ranking   │ Composite 0–100 risk scoring by       │
│                                │ deadlines, AHJ comments, and lapses   │
├────────────────────────────────┼───────────────────────────────────────┤
│ 🔍 Evidence-Backed Reasoning   │ Every rank explained with citations   │
│                                │ from examiners and checklists         │
├────────────────────────────────┼───────────────────────────────────────┤
│ ⚡ Day-over-Day Change Alerts  │ Detects overnight status transitions, │
│                                │ new comments, and newly expired docs  │
├────────────────────────────────┼───────────────────────────────────────┤
│ 🛡 Systemic Bottleneck Mining  │ Surfaces portfolio-wide failure trends│
│                                │ (e.g. 30% blocked by insurance certs) │
├────────────────────────────────┼───────────────────────────────────────┤
│ 📋 Daily Executive Action Plan │ Role-assigned task matrix for today's │
│                                │ permit coordinators and engineers     │
└────────────────────────────────┴───────────────────────────────────────┘
```

---

## 🏗 System Architecture

```mermaid
flowchart TB
    subgraph ClientLayer [MCP Host / AI Agent Layer]
        Claude[Claude Desktop / Claude Code]
        Cursor[Cursor IDE]
        Inspector[MCP Inspector]
    end

    subgraph ServerLayer [PermitFlow FastMCP Server]
        FastMCP[FastMCP Core Engine]
        
        subgraph Tools [MCP Tools (10 Tools)]
            T_Portfolio[Portfolio Tools: Priorities, Briefing, Changes, Bottlenecks]
            T_Readiness[Readiness Tools: Readiness Check, Missing Docs, Blockers, Runbooks]
            T_RAG[RAG Search: search_permit_requirements]
        end

        subgraph Resources [MCP Resources (9 URIs)]
            R_Portfolio[portfolio://summary, priorities, daily-action-plan, systemic-bottlenecks, changes]
            R_Permit[permit://{id}, project://{id}, requirements://{jur}/{type}, runbook://...]
        end

        subgraph Prompts [MCP Prompts (4 Workflows)]
            P_Standup[daily_standup_briefing]
            P_Audit[permit_readiness_audit]
            P_Resubmit[resubmission_strategy]
            P_Risk[portfolio_risk_review]
        end
    end

    subgraph ServiceLayer [Intelligence & Business Logic]
        PortService[PortfolioService]
        ReadService[ReadinessService]
        PermitService[PermitService]
        Retriever[Dual RAG Retriever: FAISS + BM25 Fallback]
    end

    subgraph DataLayer [Data & Knowledge Assets]
        MockData[(Mock Permit DB: Permits, Comments, Inspections, Projects, Snapshots)]
        Knowledge[(Regulatory Corpus: Building, Electrical, Mechanical, Guidelines)]
    end

    ClientLayer <-->|JSON-RPC / stdio or SSE| FastMCP
    FastMCP --> Tools
    FastMCP --> Resources
    FastMCP --> Prompts

    Tools --> PortService
    Tools --> ReadService
    Tools --> Retriever
    Resources --> PortService
    Resources --> ReadService
    Resources --> PermitService

    PortService --> ReadService
    PortService --> PermitService
    ReadService --> PermitService
    PermitService --> MockData
    Retriever --> Knowledge
```

---

## ⚡ Quickstart with `uv` (Recommended Package Manager)

This project is built and optimized for the **`uv`** package manager. `uv` installs dependencies 10–100× faster than `pip` and handles virtual environment isolation without manual overhead.

### 1. Install `uv` (if not already installed)

**macOS / Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Clone and Setup Environment

```bash
git clone https://github.com/example/PermitFlow-MCP.git
cd PermitFlow-MCP

# Create a virtual environment using uv
uv venv

# Synchronize all runtime and dev dependencies
uv sync --all-extras
```

### 3. Run the MCP Server Locally

```bash
# Start server using stdio transport (default for Claude Desktop / Cursor)
uv run permitflow-mcp

# Or start server over SSE transport
uv run permitflow-mcp --transport sse --port 8000
```

### 4. Run the Test Suite

```bash
uv run pytest -v
```

### 5. Build Document Embeddings (Optional RAG Ingestion)

```bash
uv run python scripts/ingest_documents.py
```
*(Note: The server features a resilient in-memory semantic fallback retriever that operates out-of-the-box even before building the offline FAISS index.)*

---

## 🔌 Connecting to MCP Clients

### Claude Desktop Configuration

Open your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the `permitflow-mcp` server:

```json
{
  "mcpServers": {
    "permitflow-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/absolute/path/to/PermitFlow-MCP",
        "run",
        "permitflow-mcp"
      ]
    }
  }
}
```

*Windows path example:*
```json
{
  "mcpServers": {
    "permitflow-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "D:\\PermitFlow-MCP",
        "run",
        "permitflow-mcp"
      ]
    }
  }
}
```

### Testing with MCP Inspector

You can test every tool, resource, and prompt interactively via the official web UI:

```bash
npx @modelcontextprotocol/inspector uv run permitflow-mcp
```

---

## 🛠 Complete MCP Tool Inventory

### A. Portfolio-Level Intelligence Tools

| Tool Name | Description | Key Arguments |
|:---|:---|:---|
| `analyze_portfolio_priorities` | Ranks all active permits by risk score (0–100) using deadlines, examiner comments, and lapses. Explains each ranking with evidence and next steps. | `limit: int` (default 10), `jurisdiction: Optional[str]` |
| `get_daily_manager_briefing` | Generates the morning executive briefing with portfolio health score, overnight changes, and role-assigned action matrix. | None |
| `detect_portfolio_changes` | Detects day-over-day changes across the portfolio (status transitions, new examiner comments, expired certificates). | `since_date: Optional[str]` |
| `analyze_systemic_bottlenecks` | Surfaces cross-cutting failure trends across multiple projects (e.g. insurance lapses, structural equipment support stamps). | None |

### B. Single-Permit Readiness & Analysis Tools

| Tool Name | Description | Key Arguments |
|:---|:---|:---|
| `check_permit_readiness` | Comprehensive readiness audit for a single permit (0–100 score, missing files, blockers, examiner comments). | `permit_id: str` |
| `find_missing_documents` | Detailed report on missing, expired, rejected, or outdated document versions. | `permit_id: str` |
| `search_permit_requirements` | Semantic RAG search over municipal code and requirement guidelines. | `query: str`, `jurisdiction: Optional[str]`, `permit_type: Optional[str]` |
| `explain_permit_blocker` | Root-cause analysis explaining why an application is blocked with citation evidence and recommended fix. | `permit_id: str` |
| `generate_resubmission_checklist`| Prioritized step-by-step resubmission runbook ordered by critical/high/medium priority. | `permit_id: str` |
| `get_permit_status` | Quick lookup of project details, dates, document counts, and reviewer notes. | `permit_id: str` |
| `update_permit_status` | Updates permit status (e.g. approved, submitted) and persists change to live database. | `permit_id: str`, `new_status: str`, `notes: Optional[str]` |
| `resolve_authority_comment` | Marks an examiner comment as resolved, unblocking readiness and dropping risk points. | `comment_id: str`, `resolution_notes: Optional[str]` |

---

## 📦 MCP Resources & Prompts

### Resources (Read-Only Context)
- `portfolio://summary` – Executive portfolio health KPIs and tier breakdown.
- `portfolio://priorities` – Complete ranked list of permits ordered by urgency.
- `portfolio://daily-action-plan` – Today's prioritized tasks for managers and coordinators.
- `portfolio://systemic-bottlenecks` – Cross-cutting failure patterns and strategic fixes.
- `portfolio://changes` – Delta report of changes since the previous day's snapshot.
- `permit://{permit_id}` – Complete structured permit record with documents and review comments.
- `project://{project_id}` – Project overview with all associated active permits.
- `requirements://{jurisdiction}/{permit_type}` – Municipal requirements for jurisdiction and trade.
- `runbook://permit-resubmission/{permit_id}` – JSON checklist for resubmission filing.

### Prompts (Structured LLM Workflows)
- `daily_standup_briefing` – Runs the morning team standup agenda with role assignments.
- `permit_readiness_audit` – Rigorous pre-filing audit of a single permit application.
- `resubmission_strategy` – Plans tactical comment-by-comment response packet for rejected permits.
- `portfolio_risk_review` – Executive quarterly/monthly review of portfolio schedule exposure.

---

## 📊 Sample Execution Outputs

### 1. Portfolio Priorities Output (`analyze_portfolio_priorities`)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                 PERMITFLOW PORTFOLIO RISK & PRIORITY RANKING                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

As of:              2026-07-06
Permits Analyzed:   10
Risk Breakdown:     🚨 CRITICAL: 3 | ⚠ HIGH: 2 | ℹ MEDIUM: 2 | ✓ LOW: 3

Executive Summary:  Analyzed 10 permits across the portfolio. Found 3 CRITICAL
and 2 HIGH risk permits requiring immediate manager intervention. Top priority
permits are: P-1042 (Phoenix Commercial Plaza), P-1003 (Maple Heights Apartments).

──────────────────────────────────────────────────────────────────────────────
RANKED PERMIT ACTION HIERARCHY
──────────────────────────────────────────────────────────────────────────────

#1 │ P-1042 — Phoenix Commercial Plaza [MECHANICAL]
   Status:       REVISION_REQUIRED | Jurisdiction: City of Phoenix
   Risk Score:   100/100 ➔ 🚨 [CRITICAL RISK]
   Target Date:  2026-07-01 (OVERDUE by 5 days)
   Key Drivers:  Past deadline by 5 days, 1 critical AHJ comment(s), 3 missing document(s)
   ► NEXT STEP:  Upload required document: HVAC Equipment Schedule
   Risk Evidence & Factors:
     • (+30 pts) Overdue Target Date: Target completion date was 2026-07-01 (5 days overdue).
     • (+25 pts) Critical AHJ Comments: 1 critical comment(s) from plans examiners.
       [Evidence: AHJ Comment CMT-401 — "The submitted HVAC design does not demonstrate compliance with ASHRAE 90.1-2019..."]
     • (+20 pts) Missing Required Documents: 3 mandatory document(s) not submitted.
     • (+15 pts) Formal Rejection History: Permit was previously rejected 1 time(s).

#2 │ P-1003 — Maple Heights Apartments [ELECTRICAL]
   Status:       REJECTED | Jurisdiction: City of Tempe
   Risk Score:   95/100 ➔ 🚨 [CRITICAL RISK]
   Target Date:  2026-05-01 (OVERDUE by 66 days)
   Key Drivers:  Past deadline by 66 days, 1 critical AHJ comment(s), Prior rejection on record
   ► NEXT STEP:  Address authority comment: Electrical load calculations do not comply with NEC 2023...
```

### 2. Systemic Bottlenecks Analysis (`analyze_systemic_bottlenecks`)

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                  PORTFOLIO SYSTEMIC BOTTLENECKS ANALYSIS                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

Permits Evaluated:  10
Bottlenecks Found:  4 cross-cutting failure modes identified

[1] GENERAL LIABILITY INSURANCE CERTIFICATE LAPSES & GAPS
    Category:        Insurance Compliance
    Portfolio Impact: 30.0% of active portfolio (3 permits)
    Affected Permits: P-1002, P-1042, P-1070
    Affected Projects:Phoenix Commercial Plaza, Maple Heights Apartments
    Jurisdictions:   City of Phoenix, City of Tempe
    Root Cause:      Contractors upload certificates without tracking 1-year expirations.
    ► RECOMMENDED FIX: Deploy automated 60-day advance insurance renewal alerts.

[2] MISSING LICENSED PE STAMPED STRUCTURAL DRAWINGS FOR EQUIPMENT SUPPORTS
    Category:        Engineering Calculations
    Portfolio Impact: 20.0% of active portfolio (2 permits)
    Affected Permits: P-1002, P-1042
    Affected Projects:Phoenix Commercial Plaza
    Jurisdictions:   City of Phoenix
    Root Cause:      Mechanical contractors submit equipment without coordinating PE roof support framing.
    ► RECOMMENDED FIX: Require structural review ticket before submitting units >1,000 lbs.
```

---

## 🗂 Project Directory Structure

```
PermitFlow-MCP/
├── .env.example                     # Sample environment configuration
├── pyproject.toml                   # uv & PEP 621 packaging configuration
├── README.md                        # Documentation and architecture guide
├── documents/                       # Municipal requirement guidelines (RAG corpus)
│   ├── building_permit_requirements.txt
│   ├── electrical_requirements.txt
│   ├── hvac_requirements.txt
│   ├── inspection_guidelines.txt
│   ├── resubmission_guidelines.md
│   └── structural_requirements.txt
├── mock_data/                       # Realistic operational datasets
│   ├── authority_comments.json      # AHJ review comments and severities
│   ├── inspections.json             # On-site inspections and milestones
│   ├── permits.json                 # Core permit database
│   ├── portfolio_snapshots.json     # Previous day portfolio state for diffs
│   ├── previous_cases.json          # Historical case studies and lessons learned
│   ├── projects.json                # Project and owner master records
│   └── submitted_documents.json     # Document versions, statuses, and expiration dates
├── scripts/
│   └── ingest_documents.py          # Offline RAG ingestion runner
├── src/
│   └── permitflow_mcp/
│       ├── __init__.py
│       ├── config.py                # Pydantic Settings configuration
│       ├── server.py                # Main FastMCP server instance and CLI
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py           # Pydantic models for readiness & portfolio intelligence
│       ├── prompts/
│       │   ├── __init__.py
│       │   └── permit_prompts.py    # MCP Prompt workflows (standup, audit, strategy, review)
│       ├── rag/
│       │   ├── __init__.py
│       │   ├── chunking.py          # Document chunking with section awareness
│       │   ├── ingest.py            # Sentence-transformers + FAISS vector ingestion
│       │   └── retriever.py         # Dual retriever: FAISS index + BM25 keyword fallback
│       ├── resources/
│       │   ├── __init__.py
│       │   ├── permit_resources.py  # Single-permit MCP resources
│       │   └── portfolio_resources.py # Portfolio-level MCP resources
│       ├── services/
│       │   ├── __init__.py
│       │   ├── permit_service.py    # Data layer querying permits and projects
│       │   ├── portfolio_service.py # Core portfolio intelligence engine
│       │   ├── readiness_service.py # Single-permit readiness calculation engine
│       │   └── token_service.py     # Token usage tracker
│       └── tools/
│           ├── __init__.py
│           ├── permit_tools.py      # Single-permit MCP tools
│           └── portfolio_tools.py   # Portfolio-level intelligence MCP tools
└── tests/
    ├── __init__.py
    ├── test_permit_service.py       # Unit tests for data services
    ├── test_portfolio_service.py    # Unit tests for portfolio rankings, diffs, bottlenecks
    ├── test_rag.py                  # Unit tests for chunking and retrieval
    ├── test_readiness_service.py    # Unit tests for readiness scoring
    └── test_tools.py                # Unit tests for FastMCP tool execution
```

---

## 🔒 Security & Safe Operations

- **Human-in-the-Loop Safeguard**: Every tool response and prompt explicitly notes: *"Human review and coordinator sign-off required prior to filing resubmissions."*
- **Offline & Private**: The prototype runs entirely in your local environment.
- **Zero Mock LLM Overhead**: All portfolio intelligence algorithms, scoring models, and delta engines execute deterministically in Python with zero third-party API dependencies required to run the server.

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
