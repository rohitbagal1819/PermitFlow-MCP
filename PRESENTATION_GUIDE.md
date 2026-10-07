# 🎓 PermitFlow MCP: Instructor Presentation & Live Demo Guide

This guide gives you an **exact, step-by-step script**, **copy-paste demo prompts**, **RAG document explanations**, and **expected outputs** to deliver a presentation to your instructor or evaluators.

---

## ⏱ 5-Minute Presentation Agenda

| Time | Segment | What to Show |
|:---|:---|:---|
| **0:00 - 1:00** | **The Hook & Problem Statement** | The PermitFlow context & why single-permit lookup is not enough |
| **1:00 - 2:30** | **Portfolio-Level Intelligence Demo** | Daily Standup Briefing, Risk Ranking, Overnight Changes, Systemic Bottlenecks |
| **2:30 - 4:00** | **Deep Dive on Blocked Permit & RAG** | Drill-down on `P-1042`, RAG semantic search on HVAC codes, Blocker Explanation |
| **4:00 - 4:45** | **Actionable Resubmission Runbook** | Generating the prioritized checklist with Human-in-the-Loop safeguard |
| **4:45 - 5:00** | **Architecture & Q&A** | FastMCP architecture, `uv` packaging, dual RAG fallback, and closing |

---

## 🎙 Act 1: The Elevator Pitch (0:00 - 1:00)

### 🗣 Talk Track for You:
> *"Good morning/afternoon. Today I am presenting **PermitFlow MCP**, an AI-powered Model Context Protocol server built for construction pre-construction and permitting workflows.*
>
> *PermitFlow is a YC company helping general contractors and developers manage permits across multiple municipal jurisdictions like Phoenix, Tempe, and Scottsdale.*
>
> *Existing tools only answer one narrow question: **'Is permit P-1042 ready?'***
>
> *Our breakthrough is **Portfolio-Level Intelligence**. Instead of forcing coordinators to check dozens of permits one by one, our MCP analyzes the entire portfolio simultaneously to answer: **'Which permits need attention first, why, and what concrete actions should the team take today?'***
>
> *It's built with Python 3.11+, FastMCP, the ultra-fast `uv` package manager, and a RAG pipeline grounded in municipal building codes."*

---

## 📚 The Documents Used for the RAG Demo

Show the instructor the files in the [`documents/`](file:///d:/PermitFlow-MCP/documents) folder. These documents form the knowledge corpus:

| Document | Primary Topics & Code Standards | Why It Matters for the Demo |
|:---|:---|:---|
| [`documents/hvac_requirements.txt`](file:///d:/PermitFlow-MCP/documents/hvac_requirements.txt) | **ASHRAE 90.1-2019**, Climate Zone 2B cooling efficiency (SEER/EER), Energy Recovery Ventilation (>5,000 CFM threshold), duct insulation. | **Grounds the failure of Permit P-1042.** Explains why examiner Patricia Nguyen rejected the mechanical plan. |
| [`documents/structural_requirements.txt`](file:///d:/PermitFlow-MCP/documents/structural_requirements.txt) | **Phoenix Mechanical Code Section 301.5**, PE stamped framing calculations for rooftop equipment >1,000 lbs, seismic bracing. | Explains why heavy rooftop units require stamped structural drawings from a PE engineer. |
| [`documents/building_permit_requirements.txt`](file:///d:/PermitFlow-MCP/documents/building_permit_requirements.txt) | Architectural stamps, site plans, **General Liability Insurance ($1M per occurrence)**, municipal licensing. | Proves why 30% of projects are delayed due to missing or expired insurance certificates. |
| [`documents/resubmission_guidelines.md`](file:///d:/PermitFlow-MCP/documents/resubmission_guidelines.md) | Written Comment Response Matrix, revision clouding, delta triangles, and engineer re-stamping protocols. | Drives the step-by-step resubmission checklist generation. |

---

## 🚀 Live Demo: Step-by-Step Prompts & Expected Outputs

Run these prompts in Claude Desktop, Cursor, or the MCP Inspector.

---

### Step 1: The Morning Standup & Portfolio Health Pulse

#### 💬 Prompt to Type:
```
Give me today's permitting standup briefing. What is our portfolio health, what changed overnight, and what are today's top priorities?
```

#### ⚙️ Behind the Scenes:
- Invokes MCP tool: `get_daily_manager_briefing`
- Synthesizes portfolio health, overnight status diffs, and assigns urgent tasks by role.

#### 🖥 Expected Output on Screen:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                  PERMITFLOW DAILY MANAGER EXECUTIVE BRIEFING                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Date:                   2026-07-06
Portfolio Health Score: 49/100 [████░░░░░░]
Active Permits:         10
Requiring Attention:    5 permits (3 Critical + 2 High)

Executive Overview:     Daily Portfolio Health Score: 49/100. Of 10 active permits,
5 require immediate management intervention. Primary portfolio risks stem from
insurance renewal lapses affecting 30% of projects and commercial energy/structural
compliance comments in City of Phoenix. 8 prioritized action tasks generated.

─── KEY CHANGES SINCE YESTERDAY ───
  • Permit Status Transitioned: under_review ➔ revision_required (P-1042)
  • 3 New AHJ Comment(s) Received (P-1042: CMT-401, CMT-402, CMT-403)
  • 1 New AHJ Comment(s) Received (P-1002: CMT-201)
  • 1 Document(s) Expired (P-1070: Insurance Certificate)

─── TODAY'S PRIORITIZED ACTION TASK MATRIX ───
▶ [URGENT TODAY]
  [1] TASK-001 │ Permit: P-1042 (Phoenix Commercial Plaza)
      Action:   Commission PE Mechanical engineer for revised ASHRAE 90.1 energy calculations & ERV specs
      Owner:    MEP Engineering Lead | Due: 2026-07-08
      Blocker:  AHJ Comment CMT-401 (Energy compliance)
  [2] TASK-002 │ Permit: P-1042 (Phoenix Commercial Plaza)
      Action:   Obtain stamped structural drawing for 2,000+ lb rooftop HVAC unit supports
      Owner:    Structural Engineer | Due: 2026-07-09
      Blocker:  AHJ Comment CMT-402 (Structural supports)
  [3] TASK-003 │ Permit: P-1042 (Phoenix Commercial Plaza)
      Action:   Upload renewed $1M General Liability Insurance Certificate for Ironclad Construction
      Owner:    Permit Coordinator | Due: 2026-07-07
      Blocker:  Missing Insurance Certificate
```

#### 🗣 What to Say to the Instructor:
> *"Notice that before even asking about an individual permit, the system delivers complete situational awareness for the project executive. It assigns owners—MEP Lead, Structural Engineer, Permit Coordinator—with exact deadlines to unblock projects before the job site sits idle."*

---

### Step 2: Multi-Factor Risk Ranking across the Portfolio

#### 💬 Prompt to Type:
```
Which permits in our portfolio need attention first, why did they get that rank, and what should we do next?
```

#### ⚙️ Behind the Scenes:
- Invokes MCP tool: `analyze_portfolio_priorities(limit=5)`
- Evaluates deadline proximity, AHJ comment severity, missing/expired files, inspections, and past rejections.

#### 🖥 Expected Output on Screen:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                 PERMITFLOW PORTFOLIO RISK & PRIORITY RANKING                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Permits Analyzed:   10
Risk Breakdown:     🚨 CRITICAL: 3 | ⚠ HIGH: 2 | ℹ MEDIUM: 2 | ✓ LOW: 3

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

#### 🗣 What to Say to the Instructor:
> *"Here you can see our multi-factor scoring model. Each permit's rank is accompanied by clear evidence—examiner citations, days overdue, and the single next action required."*

---

### Step 3: Mining Systemic Portfolio Bottlenecks

#### 💬 Prompt to Type:
```
What systemic bottlenecks or recurring failure patterns are affecting multiple permits across our portfolio?
```

#### ⚙️ Behind the Scenes:
- Invokes MCP tool: `analyze_systemic_bottlenecks`
- Mines cross-cutting trends across Phoenix, Tempe, and Mesa projects.

#### 🖥 Expected Output on Screen:
```
╔══════════════════════════════════════════════════════════════════════════════╗
║                  PORTFOLIO SYSTEMIC BOTTLENECKS ANALYSIS                     ║
╚══════════════════════════════════════════════════════════════════════════════╝

Permits Evaluated:  10
Bottlenecks Found:  4 cross-cutting failure modes identified

[1] GENERAL LIABILITY INSURANCE CERTIFICATE LAPSES & GAPS
    Category:        Insurance Compliance
    Portfolio Impact: 30.0% of active portfolio (3 permits: P-1002, P-1042, P-1070)
    Affected Projects:Phoenix Commercial Plaza, Maple Heights Apartments
    Jurisdictions:   City of Phoenix, City of Tempe
    Root Cause:      Contractors upload annual certificates without tracking 1-year expirations.
    ► RECOMMENDED FIX: Deploy automated 60-day advance insurance renewal alerts.

[2] MISSING LICENSED PE STAMPED STRUCTURAL DRAWINGS FOR EQUIPMENT SUPPORTS
    Category:        Engineering Calculations
    Portfolio Impact: 20.0% of active portfolio (2 permits: P-1002, P-1042)
    Jurisdictions:   City of Phoenix
    Root Cause:      Mechanical contractors submit rooftop equipment without coordinating PE roof support framing.
    ► RECOMMENDED FIX: Require structural review ticket before submitting units >1,000 lbs.
```

#### 🗣 What to Say to the Instructor:
> *"This is the unique differentiator. In real-world permitting, contractors lose weeks because subcontractors repeatedly fail on the exact same requirement—like annual insurance renewals or structural rooftop stamps. The MCP diagnoses this pattern automatically."*

---

### Step 4: Single-Permit Drill-down & Semantic RAG Search

#### 💬 Prompt to Type:
```
Why is permit P-1042 blocked, and what does the local energy code require for commercial rooftop HVAC units?
```

#### ⚙️ Behind the Scenes:
- Invokes `explain_permit_blocker("P-1042")`
- Performs semantic RAG vector retrieval via `search_permit_requirements("ASHRAE 90.1 rooftop HVAC energy efficiency Climate Zone 2B")` against [`hvac_requirements.txt`](file:///d:/PermitFlow-MCP/documents/hvac_requirements.txt).

#### 🖥 Expected Output on Screen:
```
═══ BLOCKER ANALYSIS ═══

Permit: P-1042 (Phoenix Commercial Plaza)

▸ Primary Blocker:
  Missing: HVAC Equipment Schedule

── All Blocking Issues (4) ──
  1. Missing: HVAC Equipment Schedule
  2. Missing: Structural Drawing - Mechanical Supports
  3. Authority comment (critical): The submitted HVAC design does not demonstrate compliance with ASHRAE 90.1-2019...
  4. Missing: General Liability Insurance Certificate

═══ REQUIREMENT SEARCH RESULTS (RAG RETRIEVER) ═══

Query: "ASHRAE 90.1 rooftop HVAC energy efficiency Climate Zone 2B"
Results found: 2

── Result 1 (relevance: 0.88) ──
Source: hvac_requirements.txt
Section: SECTION 3: ENERGY EFFICIENCY & ASHRAE 90.1 COMPLIANCE
Text: All commercial HVAC installations in Climate Zone 2B must comply with ASHRAE Standard
90.1-2019. Rooftop unitary air conditioners must meet minimum SEER 14.0 for units under 65,000
Btu/h, and minimum 11.0 EER / 12.0 IEER for units 65,000 to 135,000 Btu/h.

── Result 2 (relevance: 0.82) ──
Source: hvac_requirements.txt
Section: SECTION 4: VENTILATION & ENERGY RECOVERY
Text: Systems with supply air capacity greater than 5,000 CFM and minimum outdoor air greater
than 70% must include Energy Recovery Ventilation (ERV) with minimum 50% enthalpy recovery.
```

#### 🗣 What to Say to the Instructor:
> *"Notice the RAG integration. The AI does not hallucinate arbitrary building codes; it retrieves the exact municipal code clause (ASHRAE 90.1-2019 Climate Zone 2B, 5,000 CFM threshold) from our regulatory document repository."*

---

### Step 5: Prioritized Resubmission Runbook & Safety Guardrail

#### 💬 Prompt to Type:
```
Generate a prioritized resubmission checklist for permit P-1042.
```

#### ⚙️ Behind the Scenes:
- Invokes `generate_resubmission_checklist("P-1042")`
- Groups actions into Critical, High, and Medium tiers.
- Enforces the **Human-in-the-Loop** sign-off safeguard.

#### 🖥 Expected Output on Screen:
```
═══ RESUBMISSION CHECKLIST ═══

Permit: P-1042 (Phoenix Commercial Plaza)
Type: mechanical | Jurisdiction: City of Phoenix
Total items: 6 | Critical items: 4

── CRITICAL Priority ──
  Step 1: Upload required document: HVAC Equipment Schedule
  Reason: Required document has not been submitted.
  Source: Document check

  Step 2: Upload required document: Structural Drawing - Mechanical Supports
  Reason: Structural drawings for rooftop mechanical unit supports are required per Section 301.5.
  Source: Document check

  Step 3: Upload required document: Insurance Certificate - Ironclad Construction
  Reason: Current $1M insurance certificate required before processing.
  Source: Document check

  Step 4: Address authority comment: The submitted HVAC design does not demonstrate compliance with ASHRAE 90.1-2019...
  Reason: Open critical comment from Patricia Nguyen, Plans Examiner.
  Source: Authority comment CMT-401

── HIGH Priority ──
  Step 5: Address authority comment: Structural drawings for rooftop mechanical unit supports...
  Reason: Open major comment from David Ramirez, Plans Examiner.

── MEDIUM Priority ──
  Step 6: Submit revised application for human review
  Reason: All permit submissions require human review by the authority having jurisdiction.
  Note: Human review required before final submission.

⚑ Human review required before final submission.
```

#### 🗣 What to Say to the Instructor:
> *"And finally, notice our safety principle. The MCP doesn't blindly submit files. Every checklist item concludes with mandatory human review and verification before filing with the municipality."*

---

### Step 6: Live Interactive Update (Resolving Risk in Real-Time)

#### 💬 Prompt to Type:
```
The electrical load calculations for permit P-1003 were recalculated per NEC 2023, panel schedules were completed, and the City of Tempe just approved the permit. Please update permit P-1003's status to approved, resolve comments CMT-301 and CMT-302, and re-run the portfolio risk ranking.
```

#### ⚙️ Behind the Scenes:
- Claude calls `update_permit_status(permit_id="P-1003", new_status="approved")`
- Claude calls `resolve_authority_comment("CMT-301")` & `resolve_authority_comment("CMT-302")`
- Claude calls `analyze_portfolio_priorities()`

#### 🖥 Expected Output on Screen:
```
✓ Permit P-1003 (Maple Heights Apartments) status successfully updated to 'APPROVED'.
✓ Authority comment CMT-301 has been marked RESOLVED.
✓ Authority comment CMT-302 has been marked RESOLVED.

╔══════════════════════════════════════════════════════════════════════════════╗
║                 PERMITFLOW PORTFOLIO RISK & PRIORITY RANKING                 ║
╚══════════════════════════════════════════════════════════════════════════════╝

Permits Analyzed:   10
Risk Breakdown:     🚨 CRITICAL: 2 (Down from 3!) | ⚠ HIGH: 2 | ℹ MEDIUM: 2 | ✓ LOW: 4

Notice: Permit P-1003 has dropped from the #2 Critical Risk position (was 95/100)
all the way down to LOW RISK / APPROVED (0/100 risk score).
```

#### 🗣 What to Say to the Instructor:
> *"This demonstrates that our MCP is not just a static read-only dashboard. It is an active two-way operational control plane. As project teams resolve objections in the field, natural language commands immediately update the database and recalculate portfolio risk in real time."*

---

### Step 7: Live File Proof in the Workspace (`reports/` Folder)

Show the instructor the files physically generated inside your IDE workspace:

1. **Open [`reports/audit_log.md`](file:///d:/PermitFlow-MCP/reports/audit_log.md):**
   - Point to the live timestamps showing when `P-1003` was approved, `CMT-301` & `CMT-302` were resolved, and blueprints updated.
   - Explain: *"Every action executed through Claude writes an immutable, timestamped audit log entry directly to disk."*

2. **Open [`reports/P-1042_resubmission_checklist.md`](file:///d:/PermitFlow-MCP/reports/P-1042_resubmission_checklist.md):**
   - Show the generated Markdown runbook that the MCP saved into the folder when you requested the checklist.
   - Explain: *"The AI immediately generates persistent, production-ready markdown artifacts in the project folder for the project manager to email to subcontractors."*

---

## 🎯 Instructor Q&A: Prepared Answers

### Q1: *"Why did you use the `uv` package manager instead of `pip`?"*
> **Answer**: *"We chose Astral's `uv` because it is written in Rust, resolves dependencies 10 to 100 times faster, supports deterministic lockfiles, and allows running tools directly with `uv run permitflow-mcp` without manually configuring or activating virtual environments."*

### Q2: *"How does your RAG system handle situations where FAISS or PyTorch is not available?"*
> **Answer**: *"We engineered a dual-layer retriever in `retriever.py`. In production, it uses dense sentence embeddings with FAISS vector similarity (`IndexFlatIP`). If the environment lacks heavy C++ libraries, it automatically falls back to an in-memory BM25-style keyword and section retriever over the document corpus, guaranteeing 100% uptime without crashing."*

### Q3: *"How does the risk scoring formula work?"*
> **Answer**: *"The risk score in `portfolio_service.py` is a composite 0–100 index evaluated across 6 factors: target deadline proximity (up to 30 pts for overdue dates), examiner comment severity (+25 pts for critical, +12 for major), missing/expired documents (+20 pts each), prior rejection history (+15 pts), and permit status. Scores above 75 trigger the CRITICAL tier."*

### Q4: *"How does day-over-day change detection work?"*
> **Answer**: *"We maintain portfolio snapshots in `mock_data/portfolio_snapshots.json`. The `detect_changes` engine compares today's live state against the previous snapshot to detect status transitions (e.g. `under_review` to `revision_required`), new comments, newly lapsed certificates, and newly scheduled inspections."*

---

## 🛠 Terminal Commands for Live Demonstration

If the instructor wants to see tests and commands run in terminal:

```bash
# 1. Run all unit & integration tests
uv run pytest -v

# 2. Run the offline RAG document ingestion pipeline
uv run python scripts/ingest_documents.py

# 3. Start the PermitFlow MCP Server (stdio transport for Claude)
uv run permitflow-mcp
```
