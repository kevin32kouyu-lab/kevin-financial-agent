# CONTEXT

## 当前正在做什么
- 本轮正在把自然语言研究流程上线为 LangGraph 版 `agent_v2`，旧版 `agent` 保留为回退路径。
- 当前目标是降低串联中间产物错误向后扩散的风险，让流程具备节点状态、质量门、阻断和 checkpoint。

## 上次停在哪个位置
- 已新增 `app/agent_graph/`、`LangGraphFinancialAgentWorkflow`、`agent_v2` runtime 注册和确定性质量门测试。
- 已用真实 `agent_v2` smoke run 验证调度、质量门、报告输出和 trace；当前默认 workflow 已切到 `v2`。

## 近期关键决定与原因
- 第一版只替换 Agent 编排层，不重写前端、数据源、RAG、报告、PDF 和回测；原因是降低重构风险。
- 默认使用新版 `agent_v2`，通过 `AGENT_WORKFLOW_VERSION=v1` 可回退旧版；原因是 smoke 和自动化测试已通过，但仍保留安全回退。
- 质量门第一版使用确定性规则，不用 LLM 判断；原因是金融研究需要可解释、可测试的阻断依据。
