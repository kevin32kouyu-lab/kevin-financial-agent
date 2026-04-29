# CONTEXT

## 当前正在做什么
- 本轮正在把当前所有分支更新并合并回 `main`。
- 远端信息已更新；除 `codex/limited-autonomy-agents` 外，其他本地分支已并入 `main`。
- 当前合并重点是把受限自治 Multi-Agent、工具审计、正反论证和 checkpoint 恢复合入现有三报告终端主线。

## 上次停在哪个位置
- 已修复历史页闪烁问题：后台刷新时保留已有历史列表，只在首次加载时显示加载提示。
- 已完成终端视觉与回测图例的前端优化，并通过前端类型检查、终端回归测试和生产构建。
- 合并前已用 stash 临时保存当前未提交改动，避免覆盖已有前端修改。

## 近期关键决定与原因
- 合并旧分支时保留当前 `main` 的三报告、PDF、账户入口、示例引导和历史页刷新修复，避免旧分支让产品能力倒退。
- `codex/limited-autonomy-agents` 的有效新增能力要进入主线：受限自治 agent、ToolRegistry/ToolRunner、工具调用审计、Bull/Bear/Arbiter 论证、agent checkpoint 和按 agent 恢复。
- 模型供应商继续采用当前主线的 DeepSeek-only 配置，不恢复旧的多供应商回退说明。
