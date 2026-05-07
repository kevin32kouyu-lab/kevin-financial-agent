# CONTEXT

## 当前正在做什么
- 本轮正在收尾 LangGraph `agent_v2` 上线后的项目整理：删除临时 worktree，更新 GitHub 可见架构图、数据流文档和开发者报告标识。
- 当前目标是让仓库主分支、README、架构文档和一次真实 run 的开发报告都能明确证明默认流程已是 LangGraph `agent_v2`。

## 上次停在哪个位置
- 项目内 `.worktrees/langgraph-agent-runtime` 已删除；主工作区保持在 `main`。
- 已确认旧版 `agent` 仍保留为 `AGENT_WORKFLOW_VERSION=v1` 回退路径，当前默认 workflow 仍是 `agent_v2`。

## 近期关键决定与原因
- 第一版只替换 Agent 编排层，不重写前端、数据源、RAG、报告、PDF 和回测；原因是降低重构风险。
- 默认使用新版 `agent_v2`，通过 `AGENT_WORKFLOW_VERSION=v1` 可回退旧版；原因是 smoke 和自动化测试已通过，但仍保留安全回退。
- 质量门第一版使用确定性规则，不用 LLM 判断；原因是金融研究需要可解释、可测试的阻断依据。
- GitHub 展示优先使用 README 和 `docs/data_flow.md` 的 Mermaid 图；原因是仓库中当前跟踪的 PDF 是旧计划文件，本轮不生成新的二进制报告。
- 开发者报告新增工作流引擎、`workflow_key` 和架构名；原因是用户无需查 SQLite，也能直接确认是否走 LangGraph。
