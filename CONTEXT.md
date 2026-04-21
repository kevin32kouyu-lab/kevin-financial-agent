# CONTEXT

## 当前正在做什么
- 正在把自然语言研究从单一主流程升级为“可控多智能体投研流程”。
- 新流程由 Coordinator 串联 Intake、Planner、Data、Evidence、Report、Validator 六个固定角色 agent。
- 用户前台不展示内部 agent 细节，`research_plan` 和 `agent_trace` 主要给 debug、运行详情和论文说明使用。

## 上次停在哪个位置
- 已新增 `research_plan` artifact，用来保存 PlannerAgent 的研究计划。
- 已新增 `agent_trace` artifact，用来保存每个 agent 的交接记录。
- 后端测试已通过：35 个通过。
- 当前在隔离 worktree 分支 `codex/controlled-multi-agent` 开发。
- 原主目录仍有一个原本就存在的未跟踪目录 `.npm-cache/`，本轮未处理。

## 近期关键决定与原因
- 本阶段采用“可控多智能体”，不是完全自治多智能体：这样更稳定，也更适合演示和答辩。
- 保留旧 `AgentService` 导入兼容层，避免破坏现有 workflow 和 API。
- RAG 证据接入交给 EvidenceAgent，报告一致性校验交给 ValidatorAgent，但底层继续复用现有 RAG 与报告服务。
- 不新增公开用户 API；新产物继续通过现有 run detail / artifacts 返回。
- DeepSeek 仍作为火山 LLM 的备用源，密钥只通过环境变量配置。
