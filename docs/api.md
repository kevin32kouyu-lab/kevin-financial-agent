# API Reference

本文列出 Financial Agent 当前对前端和集成方最重要的接口。公共路由保持稳定，内部 artifact 字段可能随着 agent 架构继续演进。

## 健康检查

### `GET /healthz`

返回服务是否存活，适合部署平台探活。

### `GET /readyz`

返回服务是否准备好处理请求，适合发布后自检。

## Run 生命周期

### `POST /api/runs`

创建一次研究任务。常用字段包括：

- `query`：用户原始问题
- `mode`：实时研究或历史研究
- `as_of_date`：历史研究日期
- `max_results`：候选数量上限

返回 `run_id`、状态和初始阶段信息。

### `GET /api/runs/{run_id}`

读取某次研究的当前状态、阶段、结果和主要 artifact。

### `GET /api/runs/{run_id}/events`

读取 SSE 事件流，用于前端进度条和状态更新。

### `POST /api/runs/{run_id}/cancel`

撤回正在执行的任务。撤回后 run 会进入 `cancelled` 状态。

### `POST /api/runs/{run_id}/retry`

基于同一次请求重试研究任务。

## 历史与导出

### `GET /api/v1/runs/history`

读取最近研究历史，用于历史页。

### `GET /api/v1/runs/{run_id}/audit-summary`

读取简化后的审计摘要，包括数据来源、降级提示、优先标的和主要风险。

### `GET /api/v1/runs/{run_id}/export/pdf`

导出真实 PDF 文件。后端会读取同一份 run 数据，用 Playwright/Chromium 生成 `application/pdf`。

可选查询参数：

- `kind=investment`：默认值，导出面向投资者的正式投资报告。
- `kind=development`：导出面向开源项目读者的开发报告，说明 Agent、RAG、校验、回测和降级路径如何支撑结论。

两种 PDF 都来自同一个 run 的 `report_outputs`，不会重新执行研究流程。

## 回测

### `POST /api/v1/backtests`

创建或刷新回测。支持 `replay` 和 `reference` 两种模式，并记录交易成本、滑点、分红、税费和再平衡口径。

### `GET /api/v1/backtests/{backtest_id}`

读取回测结果、收益曲线、基准对比、逐票贡献和口径说明。

## 长期偏好

### `GET /api/v1/profile/preferences`

读取当前浏览器或账户的长期偏好。

### `PATCH /api/v1/profile/preferences`

手动更新长期偏好。

### `DELETE /api/v1/profile/preferences`

清空当前长期偏好。

## 账户与审计

### `POST /api/v1/auth/register`

创建本地账户。

### `POST /api/v1/auth/login`

登录并建立会话。

### `POST /api/v1/auth/logout`

退出当前会话。

### `GET /api/v1/admin/audit-events`

读取管理员审计事件。生产环境应限制访问权限。

## 常见返回结构

- `research_plan`：本次研究目标、数据需求、工具候选、降级策略和预期产物。
- `agent_trace`：各 agent 的状态、耗时、输入摘要、输出摘要、证据数量和警告。
- `report_outputs.investment.markdown`：面向投资者的正式投资报告正文。
- `report_outputs.investment.charts`：投资报告的四类图表数据，包括推荐仓位、候选评分、回测曲线和风险贡献。
- `report_outputs.development.markdown`：面向开源项目读者的开发报告正文。
- `report_outputs.development.diagnostics`：Agent、RAG、校验、回测、fallback 等支撑摘要。
- `final_report`：兼容旧前端，继续指向投资报告正文。
- `retrieved_evidence`：RAG 检索到的证据摘要、来源、时间和链接。
- `citation_map`：报告段落与证据之间的引用映射。
- `validation_checks`：结论、评分、风险、数据降级和时间范围的一致性校验。
- `confidence_level`：由 ValidatorAgent 统一计算的可信度。
