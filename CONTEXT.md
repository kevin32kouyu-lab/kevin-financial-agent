# CONTEXT

## 当前正在做什么
- 正在落地“受限自治 Multi-Agent 与工具中台”：让 agent 在白名单工具内自主调用，并保留 debug 可追踪过程。
- 普通 `/terminal` 继续保持清爽，复杂过程只放到 `/debug`、artifact 和日志。

## 上次停在哪个位置
- 已新增 `ToolRegistry` / `ToolRunner`，工具调用会记录权限、重试、耗时和审计。
- 已把流程升级为 Intake、Planner、Data、Evidence、Bull、Bear、Arbiter、Report、Validator 九角色链路。
- 已新增 `tool_invocations`、`debate_rounds`、`agent_checkpoints` 和 `/api/runs/{run_id}/resume-from-agent`。
- 已让历史模式记录新闻、smart money 等本地归档缺口，并进入校验提示。
- 当前在隔离 worktree 分支 `codex/limited-autonomy-agents` 开发。

## 近期关键决定与原因
- 多智能体升级为“受限自治”：agent 可以在 Planner 白名单内选工具和正反论证，但不允许任意调用函数或无限辩论。
- 细粒度恢复采用“从指定 agent 开始，重跑该 agent 及下游”：上游 checkpoint 复用，下游避免沿用旧依赖。
- `confidence_level` 由 ValidatorAgent 统一计算：避免多个模块各写各的可信度。
- 普通终端继续隐藏系统理解、长期记忆和覆盖说明；这些内部信息只放到 debug / artifact。
- 原主目录仍有原本存在的未跟踪目录 `.npm-cache/`，本轮未处理。
