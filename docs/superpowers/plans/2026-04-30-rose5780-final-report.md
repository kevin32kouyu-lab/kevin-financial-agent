# ROSE5780 Final Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create an English DOCX final report for ROSE5780 that presents Financial Agent as a polished, evidence-based multi-agent GenAI project.

**Architecture:** The report will be built as a generated DOCX with a separate source script and supporting assets. Literature sources, project screenshots, diagrams, and report text are collected first, then assembled into an A4, font-12, single-line-spacing document under the 20-page limit.

**Tech Stack:** Python, python-docx, bundled document renderer, Playwright/browser screenshots when needed, local project documentation, and verified web literature sources.

---

### Task 1: Source and Content Preparation

**Files:**
- Create: `docs/reports/rose5780/rose5780_final_report_sources.md`
- Create: `docs/reports/rose5780/report_outline.md`

- [ ] **Step 1: Confirm report structure**

Use the approved structure:

1. Cover
2. Abstract
3. Problem Statement and Personal Motivation
4. Literature Survey
5. System Overview and Project Idea
6. Methodology
7. Experimental Design and Experimental Results
8. Results
9. Limitations and Reflection
10. Conclusion and Demo Link

- [ ] **Step 2: Verify literature sources**

Use primary sources where possible:

- BloombergGPT paper
- FinGPT paper and GitHub repository
- FinRobot paper and GitHub repository
- TradingAgents paper and GitHub repository
- FinMem paper
- FinRL paper and GitHub repository

- [ ] **Step 3: Save source notes**

Write a short source note for each cited work, including title, year, URL, and how it relates to Financial Agent.

### Task 2: Project Evidence and Visual Assets

**Files:**
- Create directory: `docs/reports/rose5780/assets/`

- [ ] **Step 1: Collect existing project facts**

Read `README.md`, `ARCHITECTURE.md`, and `CONTEXT.md` to keep the report aligned with actual implemented features.

- [ ] **Step 2: Capture or create visuals**

Prepare visual material for:

- System architecture
- User workflow
- Multi-agent methodology
- Report outputs
- Backtesting output
- Evidence and validation output

- [ ] **Step 3: Avoid developer-only visuals**

Exclude debug trace from the final report, because the report should focus on product-level results and understandable technical evidence.

### Task 3: Draft English Report Text

**Files:**
- Create: `docs/reports/rose5780/report_draft.md`

- [ ] **Step 1: Write the narrative**

Use a natural first-person opening in the problem section, then transition into a formal technical report.

- [ ] **Step 2: Keep the tone human**

Avoid generic claims such as "AI is transforming finance" unless they support a specific project decision.

- [ ] **Step 3: Keep content under 20 pages**

Use concise paragraphs, tables, diagrams, and screenshots instead of dense text.

### Task 4: Generate the DOCX

**Files:**
- Create: `scripts/build_rose5780_report.py`
- Create: `docs/reports/rose5780/Financial_Agent_ROSE5780_Final_Report.docx`

- [ ] **Step 1: Build document styles**

Set A4 page size, 12 pt body font, single line spacing, consistent headings, captions, page numbers, and a polished cover style.

- [ ] **Step 2: Insert text and visuals**

Insert all approved sections, literature references, project diagrams, output screenshots, and final demo link placeholder if the link is not available yet.

- [ ] **Step 3: Add final references**

Add a compact references section using human-readable citations and URLs.

### Task 5: Render and Verify

**Files:**
- Create directory: `tmp/rose5780_report_render/`

- [ ] **Step 1: Render the DOCX**

Run the bundled document renderer:

```powershell
<bundled-python> <documents-skill>/render_docx.py docs/reports/rose5780/Financial_Agent_ROSE5780_Final_Report.docx --output_dir tmp/rose5780_report_render --renderer artifact-tool
```

- [ ] **Step 2: Inspect every rendered page**

Check all page PNGs for clipped text, unreadable tables, broken images, overlap, and page count.

- [ ] **Step 3: Iterate until clean**

Fix layout issues in the generator script, rebuild, and re-render until the document is visually clean.

### Task 6: Project Record Update

**Files:**
- Modify: `CONTEXT.md`

- [ ] **Step 1: Update current progress**

Record that the ROSE5780 final report draft DOCX has been created and where it is stored.

- [ ] **Step 2: Keep the note short**

Do not expand README or ARCHITECTURE unless report work changes project behavior, dependencies, or core design.
