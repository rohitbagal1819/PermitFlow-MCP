#!/usr/bin/env python3
"""Generate a professional PDF guide containing 4 structured testing sets for tutor evaluation."""

import os
from pathlib import Path
import fitz  # PyMuPDF

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PDF = PROJECT_ROOT / "reports" / "PermitFlow_MCP_Testing_Questions.pdf"


def create_pdf():
    doc = fitz.open()
    PAGE_WIDTH = 612  # Letter width in points
    PAGE_HEIGHT = 792  # Letter height in points
    MARGIN_X = 40
    MARGIN_TOP = 45
    MARGIN_BOTTOM = 45
    USABLE_WIDTH = PAGE_WIDTH - (2 * MARGIN_X)

    # Palette
    COLOR_PRIMARY = fitz.pdfcolor["blue"]  # or hex
    COLOR_NAVY = (0.06, 0.10, 0.20)      # #0F1A33
    COLOR_BLUE = (0.04, 0.48, 1.00)      # #0A7AFF
    COLOR_DARK = (0.12, 0.14, 0.18)      # #1F242E
    COLOR_GREY = (0.40, 0.44, 0.52)      # #667085
    COLOR_LIGHT_BG = (0.96, 0.97, 0.99)  # #F5F7FB
    COLOR_BORDER = (0.85, 0.88, 0.93)    # #D8E0ED
    COLOR_WHITE = (1.0, 1.0, 1.0)
    COLOR_TAG_BG = (0.90, 0.94, 1.00)

    # Document data structure: 4 Sets
    sets_data = [
        {
            "set_num": "SET 1",
            "title": "Portfolio Executive Intelligence & Morning Standup",
            "objective": "Tests portfolio-wide synthesis, health scoring, overnight deltas, and cross-project bottleneck mining across all 10 active permits.",
            "questions": [
                {
                    "q_num": "Test 1.1",
                    "title": "Daily Morning Standup Briefing",
                    "prompt": "Give me today's permitting standup briefing. What is our portfolio health score, what changed overnight, and what are today's top priorities?",
                    "tool": "get_daily_manager_briefing",
                    "expected": "Returns 0-100 health score (49/100), flags 5 critical/high permits, lists overnight status shifts, and outputs role-assigned action tasks.",
                    "tutor_point": "Show your tutor that the MCP operates as an executive dashboard across all projects rather than an isolated single-permit lookup."
                },
                {
                    "q_num": "Test 1.2",
                    "title": "Portfolio Multi-Factor Risk Ranking",
                    "prompt": "Which permits in our portfolio need attention first, why did they get that rank, and what should we do next?",
                    "tool": "analyze_portfolio_priorities(limit=5)",
                    "expected": "Ranks permits #1 to #5. Identifies P-1042 (Score: 100/100, Critical) and P-1003 (Score: 95/100) with mathematical breakdown (+30 overdue, +25 AHJ comments).",
                    "tutor_point": "Highlight the deterministic 0-100 scoring algorithm. Every rank is justified with concrete evidence citations."
                },
                {
                    "q_num": "Test 1.3",
                    "title": "Day-over-Day Overnight Velocity Tracking",
                    "prompt": "What changed across our permit portfolio since yesterday? List any new comments or status transitions.",
                    "tool": "detect_portfolio_changes",
                    "expected": "Detects 9 overnight deltas: 3 status transitions, 5 new examiner comments (CMT-401, CMT-402), 1 expired insurance cert (P-1070).",
                    "tutor_point": "Demonstrates temporal awareness: compares current DB against portfolio_snapshots.json to catch changes before the site sits idle."
                },
                {
                    "q_num": "Test 1.4",
                    "title": "Portfolio Systemic Bottleneck Mining",
                    "prompt": "Are we repeatedly failing on the same documents or codes across multiple projects? Analyze our systemic bottlenecks.",
                    "tool": "analyze_systemic_bottlenecks",
                    "expected": "Surfaces 4 cross-cutting patterns: 30% of projects stalled by insurance lapses; Phoenix rooftop PE stamp gaps; ASHRAE 90.1 energy calculation issues.",
                    "tutor_point": "Proves the server finds macro patterns across projects and recommends preventive standard operating policies."
                }
            ]
        },
        {
            "set_num": "SET 2",
            "title": "Single-Permit Deep Dive, Blockers & Building Code RAG",
            "objective": "Tests granular application auditing, document validity checks, root-cause blocker diagnosis, and vector search over municipal building codes.",
            "questions": [
                {
                    "q_num": "Test 2.1",
                    "title": "Pre-Submission Readiness Audit",
                    "prompt": "Check the readiness of permit P-1042. Is it ready to submit, what is its score, and what are the blockers?",
                    "tool": "check_permit_readiness(permit_id='P-1042')",
                    "expected": "Readiness: BLOCKED (Score: 0/100). Lists 3 missing mandatory documents, 3 open AHJ comments, and returns human review required safeguard.",
                    "tutor_point": "Shows the pre-flight gatekeeper function preventing contractors from submitting incomplete files that trigger rejections."
                },
                {
                    "q_num": "Test 2.2",
                    "title": "Missing & Invalid Document Audit",
                    "prompt": "Which documents are missing, expired, or rejected for permit P-1042?",
                    "tool": "find_missing_documents(permit_id='P-1042')",
                    "expected": "Flags missing Equipment Schedule (DOC-403) and Energy Calculations (DOC-405), plus rejected/missing Liability Insurance Certificate (DOC-407).",
                    "tutor_point": "Illustrates differential document checking: comparing required checklist IDs against submitted file metadata and expiration timestamps."
                },
                {
                    "q_num": "Test 2.3",
                    "title": "Root-Cause Blocker Explanation",
                    "prompt": "Why is permit P-1042 blocked, who blocked it, and what is the recommended fix?",
                    "tool": "explain_permit_blocker(permit_id='P-1042')",
                    "expected": "Pinpoints primary blocker: Examiner Patricia Nguyen's comment on ASHRAE 90.1 energy compliance and David Chen's comment on rooftop structural supports.",
                    "tutor_point": "Shows root-cause diagnostics with citation evidence and realistic business-day resolution effort estimates."
                },
                {
                    "q_num": "Test 2.4",
                    "title": "Municipal Code RAG Vector Search",
                    "prompt": "What does the Phoenix mechanical code require for rooftop equipment over 1,000 lbs, and what are the energy recovery requirements?",
                    "tool": "search_permit_requirements(query=...)",
                    "expected": "Retrieves exact excerpts from structural_requirements.txt (Sec 301.5: PE stamped framing calculations) and hvac_requirements.txt (ASHRAE 90.1 ERV rules).",
                    "tutor_point": "Demonstrates the RAG pipeline saving ~82.9% context space (fetching top 4 chunks = ~1,680 tokens vs. dumping ~9,850 tokens)."
                }
            ]
        },
        {
            "set_num": "SET 3",
            "title": "PermitFlow AI Workforce: Intake, Fees, ROC & Transmittals",
            "objective": "Tests the real-world operational agents: natural language scope intake, city fee calculation, Arizona ROC licensing verification, and city response letters.",
            "questions": [
                {
                    "q_num": "Test 3.1",
                    "title": "Scope-of-Work (SOW) Intake (Intake Agent)",
                    "prompt": "We need to replace two 7.5-ton rooftop HVAC units, upgrade the 400A electrical service, and add roof curb framing at 4800 E Camelback Rd, Phoenix, AZ. Estimated valuation $185,000. Intake this project.",
                    "tool": "intake_project_scope(scope_description=..., address=..., valuation=185000)",
                    "expected": "Detects City of Phoenix, flags Mechanical & Electrical trades, triggers PE Stamping requirement (> $50k commercial), and generates draft permit P-INTAKE-XXXX.",
                    "tutor_point": "Proves the MCP handles unstructured contractor proposals and auto-configures a municipal submittal pipeline."
                },
                {
                    "q_num": "Test 3.2",
                    "title": "Municipal Fee & SLA Calculator (Research Agent)",
                    "prompt": "Estimate city permit fees, plan check surcharges, and review timeline for a $120,000 mechanical permit in the City of Phoenix.",
                    "tool": "estimate_permit_fees_and_sla(jurisdiction='City of Phoenix', permit_type='mechanical', valuation=120000)",
                    "expected": "Itemizes Base Fee ($1,120), 65% Plan Review ($728), Tech Surcharge ($73.92) -> Total: $1,921.92. Predicts SLA turnaround of 20 business days (~4 weeks).",
                    "tutor_point": "Demonstrates municipal financial estimation and schedule forecasting tailored to city fee schedules."
                },
                {
                    "q_num": "Test 3.3",
                    "title": "Contractor ROC & Insurance Audit (License Management)",
                    "prompt": "Verify if Ironclad Construction has valid license standing and insurance coverage to pull commercial permits in the City of Phoenix.",
                    "tool": "verify_contractor_registration(contractor_name='Ironclad Construction', jurisdiction='City of Phoenix', permit_type='building')",
                    "expected": "Audits ROC #329482 (Class B-1), $2M limit, but flags NON-COMPLIANT: Insurance expired on 2026-05-15 and City of Phoenix is NOT listed as Additional Insured.",
                    "tutor_point": "Directly mirrors PermitFlow's /license-registration-management product to prevent instant municipal rejection."
                },
                {
                    "q_num": "Test 3.4",
                    "title": "City Comment-Response Transmittal (Coordination Agent)",
                    "prompt": "Generate the official written plan check response packet for permit P-1042 so we can submit it to the City of Phoenix plans examiners.",
                    "tool": "generate_formal_ahj_response_packet(permit_id='P-1042')",
                    "expected": "Generates complete transmittal letter citing Sheet M-201, Delta Clouds, ASHRAE 90.1, licensed PE sign-off block, and saves to reports/P-1042_ahj_response_packet.md.",
                    "tutor_point": "Real cities mandate formal written response matrices. Show that your server outputs submittal-ready transmittal letters."
                }
            ]
        },
        {
            "set_num": "SET 4",
            "title": "Live State Mutations, Re-evaluation & Real-Time Audit Log",
            "objective": "Tests two-way interactive state changes, unblocking permits, dropping risk points, and proving compliance accountability via reports/audit_log.md.",
            "questions": [
                {
                    "q_num": "Test 4.1",
                    "title": "Resolving Authority Comments",
                    "prompt": "We revised the drawings and added the ERV energy calculations. Resolve comment CMT-401 for permit P-1042 with notes: 'ASHRAE 90.1 calculations stamped and added to Sheet M-201'.",
                    "tool": "resolve_authority_comment(comment_id='CMT-401', resolution_notes=...)",
                    "expected": "Marks CMT-401 as resolved, drops permit risk points, updates authority_comments.json, and appends a record to reports/audit_log.md.",
                    "tutor_point": "Proves the server is interactive and stateful: clearing objections directly affects future readiness checks."
                },
                {
                    "q_num": "Test 4.2",
                    "title": "Permit Status Transition Mutation",
                    "prompt": "Update the status of permit P-1042 to under_review with notes: 'Resubmitted complete response packet with engineer stamps'.",
                    "tool": "update_permit_status(permit_id='P-1042', new_status='under_review', notes=...)",
                    "expected": "Updates status in permits.json, updates last_updated timestamp to today, and logs the transition into reports/audit_log.md.",
                    "tutor_point": "Demonstrates two-way database mutation through the MCP protocol."
                },
                {
                    "q_num": "Test 4.3",
                    "title": "Portfolio Re-evaluation & Risk Drop Verification",
                    "prompt": "Now re-run the portfolio priority analysis. How has permit P-1042's ranking and risk score changed?",
                    "tool": "analyze_portfolio_priorities",
                    "expected": "Shows P-1042 risk score dropped significantly (no longer penalized by revision_required status or open critical comment CMT-401).",
                    "tutor_point": "Confirms live reactivity: actions taken in the previous step immediately reflect in executive portfolio ranking."
                },
                {
                    "q_num": "Test 4.4",
                    "title": "Audit Trail Inspection",
                    "prompt": "Show me the real-time activity and audit log. Confirm that our status updates and comment resolutions were recorded.",
                    "tool": "Read reports/audit_log.md directly",
                    "expected": "Contains timestamped markdown entries for every mutation: old status vs new status, reviewer notes, and permit IDs.",
                    "tutor_point": "Open reports/audit_log.md in front of your tutor to show enterprise-grade auditability and compliance logging."
                }
            ]
        }
    ]

    # Helper function to draw wrapped text
    def draw_text_box(page, rect, text, fontname="helv", fontsize=10, color=COLOR_DARK, align=0):
        return page.insert_textbox(rect, text, fontname=fontname, fontsize=fontsize, color=color, align=align)

    # PAGE 1: Cover & Architecture Overview + SET 1
    # Page 1
    page1 = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)

    # Top Header Banner
    header_rect = fitz.Rect(0, 0, PAGE_WIDTH, 90)
    page1.draw_rect(header_rect, color=None, fill=COLOR_NAVY)

    page1.insert_text((MARGIN_X, 35), "PERMITFLOW MCP SERVER", fontname="helv", fontsize=18, color=COLOR_WHITE)
    page1.insert_text((MARGIN_X, 55), "Official Tutor Testing Guide & Demonstration Script", fontname="helv", fontsize=12, color=COLOR_BLUE)
    page1.insert_text((MARGIN_X, 73), "Built for Real Startup Workflow: PermitFlow (YC S22) | 4 Comprehensive Testing Sets", fontname="helv", fontsize=9, color=COLOR_WHITE)

    # Intro overview card
    intro_rect = fitz.Rect(MARGIN_X, 105, PAGE_WIDTH - MARGIN_X, 185)
    page1.draw_rect(intro_rect, color=COLOR_BORDER, fill=COLOR_LIGHT_BG, radius=6)
    
    page1.insert_text((MARGIN_X + 15, 125), "EXECUTIVE DEMO SUMMARY & EVALUATION OBJECTIVES", fontname="helv", fontsize=10, color=COLOR_NAVY)
    intro_desc = (
        "This document contains 4 structured testing sets designed to prove full compliance with the assignment rubric:\n"
        "• Rule 1 (Work beyond Claude): Tested on Claude Desktop, Cursor IDE, and MCP Inspector.\n"
        "• Rule 2 (Fit into a bigger workflow): Sits between pre-con estimating and groundbreaking; enforces human-in-the-loop.\n"
        "• Rule 3 (Smart with space): RAG vector search cuts context tokens by ~82.9% (top 4 chunks = ~1,680 vs ~9,850 tokens).\n"
        "Each test below provides the exact prompt to copy-paste, the backend tool invoked, and what to point out to your tutor."
    )
    page1.insert_textbox(fitz.Rect(MARGIN_X + 15, 132, PAGE_WIDTH - MARGIN_X - 15, 180), intro_desc, fontname="helv", fontsize=8.5, color=COLOR_DARK)

    # Render SET 1 on Page 1
    cur_y = 195
    set1 = sets_data[0]
    
    # Set Banner
    set_banner = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + 32)
    page1.draw_rect(set_banner, color=None, fill=COLOR_BLUE, radius=4)
    page1.insert_text((MARGIN_X + 10, cur_y + 16), f"{set1['set_num']}: {set1['title'].upper()}", fontname="helv", fontsize=10, color=COLOR_WHITE)
    page1.insert_text((MARGIN_X + 10, cur_y + 27), set1['objective'], fontname="helv", fontsize=7.5, color=COLOR_WHITE)
    cur_y += 38

    # Render questions of Set 1
    for q in set1["questions"]:
        box_h = 120
        q_box = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + box_h)
        page1.draw_rect(q_box, color=COLOR_BORDER, fill=COLOR_WHITE, radius=4)

        # Header tag
        tag_rect = fitz.Rect(MARGIN_X + 8, cur_y + 8, MARGIN_X + 60, cur_y + 22)
        page1.draw_rect(tag_rect, color=None, fill=COLOR_NAVY, radius=2)
        page1.insert_text((MARGIN_X + 12, cur_y + 18), q["q_num"], fontname="helv", fontsize=8, color=COLOR_WHITE)
        page1.insert_text((MARGIN_X + 68, cur_y + 18), q["title"], fontname="helv", fontsize=9.5, color=COLOR_NAVY)
        page1.insert_text((PAGE_WIDTH - MARGIN_X - 180, cur_y + 18), f"Tool: {q['tool']}", fontname="helv", fontsize=8, color=COLOR_BLUE)

        # Content lines
        p_text = f"💬 PROMPT TO ASK:\n\"{q['prompt']}\"\n\n✓ EXPECTED RESULT: {q['expected']}\n\n★ TUTOR TALKING POINT: {q['tutor_point']}"
        page1.insert_textbox(fitz.Rect(MARGIN_X + 10, cur_y + 24, PAGE_WIDTH - MARGIN_X - 10, cur_y + box_h - 4), p_text, fontname="helv", fontsize=7.5, color=COLOR_DARK)

        cur_y += box_h + 8

    # Footer Page 1
    page1.insert_text((MARGIN_X, PAGE_HEIGHT - 25), "PermitFlow MCP Testing Guide — Page 1 of 4", fontname="helv", fontsize=8, color=COLOR_GREY)
    page1.insert_text((PAGE_WIDTH - MARGIN_X - 150, PAGE_HEIGHT - 25), "GitHub: rohitbagal1819/PermitFlow-MCP", fontname="helv", fontsize=8, color=COLOR_GREY)


    # PAGE 2: SET 2
    page2 = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page2.draw_rect(fitz.Rect(0, 0, PAGE_WIDTH, 50), color=None, fill=COLOR_NAVY)
    page2.insert_text((MARGIN_X, 32), "PERMITFLOW MCP: SET 2 TESTING GUIDE", fontname="helv", fontsize=14, color=COLOR_WHITE)

    cur_y = 65
    set2 = sets_data[1]

    set_banner = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + 32)
    page2.draw_rect(set_banner, color=None, fill=COLOR_BLUE, radius=4)
    page2.insert_text((MARGIN_X + 10, cur_y + 16), f"{set2['set_num']}: {set2['title'].upper()}", fontname="helv", fontsize=10, color=COLOR_WHITE)
    page2.insert_text((MARGIN_X + 10, cur_y + 27), set2['objective'], fontname="helv", fontsize=7.5, color=COLOR_WHITE)
    cur_y += 42

    for q in set2["questions"]:
        box_h = 145
        q_box = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + box_h)
        page2.draw_rect(q_box, color=COLOR_BORDER, fill=COLOR_WHITE, radius=4)

        tag_rect = fitz.Rect(MARGIN_X + 8, cur_y + 8, MARGIN_X + 60, cur_y + 22)
        page2.draw_rect(tag_rect, color=None, fill=COLOR_NAVY, radius=2)
        page2.insert_text((MARGIN_X + 12, cur_y + 18), q["q_num"], fontname="helv", fontsize=8, color=COLOR_WHITE)
        page2.insert_text((MARGIN_X + 68, cur_y + 18), q["title"], fontname="helv", fontsize=9.5, color=COLOR_NAVY)
        page2.insert_text((PAGE_WIDTH - MARGIN_X - 190, cur_y + 18), f"Tool: {q['tool'][:30]}", fontname="helv", fontsize=8, color=COLOR_BLUE)

        p_text = f"💬 PROMPT TO ASK:\n\"{q['prompt']}\"\n\n✓ EXPECTED RESULT: {q['expected']}\n\n★ TUTOR TALKING POINT: {q['tutor_point']}"
        page2.insert_textbox(fitz.Rect(MARGIN_X + 10, cur_y + 24, PAGE_WIDTH - MARGIN_X - 10, cur_y + box_h - 4), p_text, fontname="helv", fontsize=7.8, color=COLOR_DARK)

        cur_y += box_h + 12

    # RAG Token Callout Box on Page 2
    callout_rect = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + 55)
    page2.draw_rect(callout_rect, color=COLOR_BORDER, fill=COLOR_LIGHT_BG, radius=4)
    page2.insert_text((MARGIN_X + 10, cur_y + 18), "🧠 RAG TOKEN SAVINGS PROOF (Rule 3 Rubric):", fontname="helv", fontsize=8.5, color=COLOR_NAVY)
    page2.insert_text((MARGIN_X + 10, cur_y + 32), "• Full regulatory corpus dump: ~7,250 words / ~9,850 tokens across 6 building code guides.", fontname="helv", fontsize=7.5, color=COLOR_DARK)
    page2.insert_text((MARGIN_X + 10, cur_y + 44), "• RAG retrieved context (Top 4 chunks): ~1,250 words / ~1,680 tokens -> ~82.9% TOKEN REDUCTION SAVED!", fontname="helv", fontsize=7.5, color=COLOR_BLUE)

    page2.insert_text((MARGIN_X, PAGE_HEIGHT - 25), "PermitFlow MCP Testing Guide — Page 2 of 4", fontname="helv", fontsize=8, color=COLOR_GREY)
    page2.insert_text((PAGE_WIDTH - MARGIN_X - 150, PAGE_HEIGHT - 25), "GitHub: rohitbagal1819/PermitFlow-MCP", fontname="helv", fontsize=8, color=COLOR_GREY)


    # PAGE 3: SET 3
    page3 = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page3.draw_rect(fitz.Rect(0, 0, PAGE_WIDTH, 50), color=None, fill=COLOR_NAVY)
    page3.insert_text((MARGIN_X, 32), "PERMITFLOW MCP: SET 3 TESTING GUIDE", fontname="helv", fontsize=14, color=COLOR_WHITE)

    cur_y = 65
    set3 = sets_data[2]

    set_banner = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + 32)
    page3.draw_rect(set_banner, color=None, fill=COLOR_BLUE, radius=4)
    page3.insert_text((MARGIN_X + 10, cur_y + 16), f"{set3['set_num']}: {set3['title'].upper()}", fontname="helv", fontsize=10, color=COLOR_WHITE)
    page3.insert_text((MARGIN_X + 10, cur_y + 27), set3['objective'], fontname="helv", fontsize=7.5, color=COLOR_WHITE)
    cur_y += 42

    for q in set3["questions"]:
        box_h = 150
        q_box = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + box_h)
        page3.draw_rect(q_box, color=COLOR_BORDER, fill=COLOR_WHITE, radius=4)

        tag_rect = fitz.Rect(MARGIN_X + 8, cur_y + 8, MARGIN_X + 60, cur_y + 22)
        page3.draw_rect(tag_rect, color=None, fill=COLOR_NAVY, radius=2)
        page3.insert_text((MARGIN_X + 12, cur_y + 18), q["q_num"], fontname="helv", fontsize=8, color=COLOR_WHITE)
        page3.insert_text((MARGIN_X + 68, cur_y + 18), q["title"], fontname="helv", fontsize=9.5, color=COLOR_NAVY)
        page3.insert_text((PAGE_WIDTH - MARGIN_X - 190, cur_y + 18), f"Tool: {q['tool'][:28]}", fontname="helv", fontsize=8, color=COLOR_BLUE)

        p_text = f"💬 PROMPT TO ASK:\n\"{q['prompt']}\"\n\n✓ EXPECTED RESULT: {q['expected']}\n\n★ TUTOR TALKING POINT: {q['tutor_point']}"
        page3.insert_textbox(fitz.Rect(MARGIN_X + 10, cur_y + 24, PAGE_WIDTH - MARGIN_X - 10, cur_y + box_h - 4), p_text, fontname="helv", fontsize=7.8, color=COLOR_DARK)

        cur_y += box_h + 12

    page3.insert_text((MARGIN_X, PAGE_HEIGHT - 25), "PermitFlow MCP Testing Guide — Page 3 of 4", fontname="helv", fontsize=8, color=COLOR_GREY)
    page3.insert_text((PAGE_WIDTH - MARGIN_X - 150, PAGE_HEIGHT - 25), "GitHub: rohitbagal1819/PermitFlow-MCP", fontname="helv", fontsize=8, color=COLOR_GREY)


    # PAGE 4: SET 4 & Compliance Verification
    page4 = doc.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    page4.draw_rect(fitz.Rect(0, 0, PAGE_WIDTH, 50), color=None, fill=COLOR_NAVY)
    page4.insert_text((MARGIN_X, 32), "PERMITFLOW MCP: SET 4 TESTING GUIDE", fontname="helv", fontsize=14, color=COLOR_WHITE)

    cur_y = 65
    set4 = sets_data[3]

    set_banner = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + 32)
    page4.draw_rect(set_banner, color=None, fill=COLOR_BLUE, radius=4)
    page4.insert_text((MARGIN_X + 10, cur_y + 16), f"{set4['set_num']}: {set4['title'].upper()}", fontname="helv", fontsize=10, color=COLOR_WHITE)
    page4.insert_text((MARGIN_X + 10, cur_y + 27), set4['objective'], fontname="helv", fontsize=7.5, color=COLOR_WHITE)
    cur_y += 42

    for q in set4["questions"]:
        box_h = 138
        q_box = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + box_h)
        page4.draw_rect(q_box, color=COLOR_BORDER, fill=COLOR_WHITE, radius=4)

        tag_rect = fitz.Rect(MARGIN_X + 8, cur_y + 8, MARGIN_X + 60, cur_y + 22)
        page4.draw_rect(tag_rect, color=None, fill=COLOR_NAVY, radius=2)
        page4.insert_text((MARGIN_X + 12, cur_y + 18), q["q_num"], fontname="helv", fontsize=8, color=COLOR_WHITE)
        page4.insert_text((MARGIN_X + 68, cur_y + 18), q["title"], fontname="helv", fontsize=9.5, color=COLOR_NAVY)
        page4.insert_text((PAGE_WIDTH - MARGIN_X - 190, cur_y + 18), f"Tool: {q['tool'][:28]}", fontname="helv", fontsize=8, color=COLOR_BLUE)

        p_text = f"💬 PROMPT TO ASK:\n\"{q['prompt']}\"\n\n✓ EXPECTED RESULT: {q['expected']}\n\n★ TUTOR TALKING POINT: {q['tutor_point']}"
        page4.insert_textbox(fitz.Rect(MARGIN_X + 10, cur_y + 24, PAGE_WIDTH - MARGIN_X - 10, cur_y + box_h - 4), p_text, fontname="helv", fontsize=7.8, color=COLOR_DARK)

        cur_y += box_h + 10

    # Final Verification Box
    final_rect = fitz.Rect(MARGIN_X, cur_y, PAGE_WIDTH - MARGIN_X, cur_y + 60)
    page4.draw_rect(final_rect, color=COLOR_BORDER, fill=COLOR_LIGHT_BG, radius=4)
    page4.insert_text((MARGIN_X + 10, cur_y + 18), "📋 FINAL TUTOR VERIFICATION CHECKLIST (Show these files):", fontname="helv", fontsize=8.5, color=COLOR_NAVY)
    page4.insert_text((MARGIN_X + 10, cur_y + 32), "1. reports/audit_log.md -> Live timestamped transaction ledger showing all status mutations.", fontname="helv", fontsize=7.5, color=COLOR_DARK)
    page4.insert_text((MARGIN_X + 10, cur_y + 44), "2. reports/P-1042_ahj_response_packet.md -> Generated official municipal comment response matrix.", fontname="helv", fontsize=7.5, color=COLOR_DARK)
    page4.insert_text((MARGIN_X + 10, cur_y + 55), "3. mock_data/contractors.json -> Arizona Registrar of Contractors (ROC) and insurance registry.", fontname="helv", fontsize=7.5, color=COLOR_DARK)

    page4.insert_text((MARGIN_X, PAGE_HEIGHT - 25), "PermitFlow MCP Testing Guide — Page 4 of 4", fontname="helv", fontsize=8, color=COLOR_GREY)
    page4.insert_text((PAGE_WIDTH - MARGIN_X - 150, PAGE_HEIGHT - 25), "GitHub: rohitbagal1819/PermitFlow-MCP", fontname="helv", fontsize=8, color=COLOR_GREY)

    # Save PDF
    OUTPUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(OUTPUT_PDF))
    doc.close()
    print(f"Successfully generated PDF: {OUTPUT_PDF}")


if __name__ == "__main__":
    create_pdf()
