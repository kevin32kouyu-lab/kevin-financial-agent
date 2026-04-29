# ROSE5780 Final Report Outline

Working title: **Financial Agent: A Multi-Agent GenAI System for Evidence-Based Stock Research**

Subtitle: **From a confident answer to a traceable research workflow**

## Page Plan

1. **Cover**
   - Project title, course name, student information, date, and a clean financial technology visual style.

2. **Abstract**
   - One-page overview of the agent, the problem it solves, core GenAI techniques, and final outputs.

3. **Problem Statement and Personal Motivation**
   - Personal reason for building the agent.
   - Problem: general AI answers can sound confident but hide evidence, data freshness, risk, and historical performance.

4. **Literature Survey**
   - BloombergGPT and FinGPT as financial LLM references.
   - FinRobot and TradingAgents as financial agent references.
   - FinMem as memory-based financial agent reference.
   - FinRL as a traditional algorithmic trading and backtesting framework reference.

5. **System Overview and Project Idea**
   - Project idea: turn one investment question into a traceable research workflow.
   - Architecture: user interface, FastAPI backend, multi-agent workflow, data sources, RAG evidence layer, reports, PDF export, and backtesting.

6. **Methodology**
   - Intake, Planner, Data, Evidence, Bull, Bear, Arbiter, Report, and Validator agents.
   - Planner-controlled tool use.
   - RAG evidence storage and retrieval.
   - Bull/Bear reasoning and Arbiter summary.
   - Validator checks for evidence, risk, ranking, data freshness, and historical gaps.
   - Memory, history, and report automation.

7. **Experimental Design and Experimental Results**
   - Experiment 1: real-time investment research.
   - Experiment 2: historical backtest research.
   - Experiment 3: incomplete user request and clarification.
   - Experiment 4: report generation and PDF export.

8. **Results**
   - User terminal.
   - Research progress.
   - Simple investor report.
   - Professional report.
   - Developer report is mentioned as a technical output, but debug trace is excluded.
   - RAG evidence and validation summary.
   - Backtesting result.
   - PDF export.

9. **Limitations and Reflection**
   - Not investment advice.
   - Free/public data sources can degrade or be rate-limited.
   - Backtesting is conservative but not a professional trading engine.
   - Local SQLite RAG is simple and deployable, not a full vector database platform.

10. **Conclusion and Demo Link**
    - Summary of what was built.
    - Demo video link and QR code area.

## Style Direction

- Full English report.
- A4 size, font 12, single line spacing.
- Maximum 20 pages, target 16-18 pages.
- Use a polished product-report style: clear cover, section dividers, diagrams, tables, and screenshots.
- Keep the first-person motivation short and natural.
- Avoid generic AI wording. Make the project sound like a real system that was designed, built, tested, and reflected on.
