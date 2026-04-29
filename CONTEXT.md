# CONTEXT

## 当前正在做什么
- 本轮已把当前所有分支更新并合并回 `main`；远端信息已刷新，本地已无未合并分支。
- 本轮继续保留并提交合并前的前端未提交改动，包括历史页闪烁修复、终端视觉优化和回测图例优化。
- 当前已把本地 `main` 推送到 GitHub 远端。
- 当前主线同时包含三报告终端和受限自治 Multi-Agent 能力。

## 上次停在哪个位置
- 已合并 `codex/limited-autonomy-agents`，并解决 `CONTEXT.md`、`README.md`、`agent_coordinator.py`、`run_service.py`、测试和前端 API 的冲突。
- 已把受限自治 agent、ToolRegistry/ToolRunner、工具调用审计、Bull/Bear/Arbiter 论证、agent checkpoint 和按 agent 恢复接入主线。
- 合并后后端完整测试 128 项通过，前端类型检查通过，生产构建通过，历史页回归测试 25 项通过。

## 近期关键决定与原因
- 合并旧分支时保留当前 `main` 的三报告、PDF、账户入口、示例引导和历史页刷新修复，避免旧分支让产品能力倒退。
- `codex/limited-autonomy-agents` 的新增能力作为主线能力保留，但文档和运行配置继续沿用当前 DeepSeek-only 口径。
- 合并前的未提交改动通过 stash 保护并已恢复；这些改动属于本轮历史页和界面修复，因此已单独提交并推送。
