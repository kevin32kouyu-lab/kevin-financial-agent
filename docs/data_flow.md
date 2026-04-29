# Data Flow

本文按当前项目结构重新整理 Financial Agent 的完整数据流。README 里保留简版图，这里保留更完整的 GitHub Mermaid 图，方便后续评审、演示和排查。

## 总览图

```mermaid
flowchart TD
    User["用户"] --> Landing["/ 首页"]
    User --> Terminal["/terminal 研究终端"]
    Developer["开发者"] --> Debug["/debug 调试台"]

    Landing --> ApiClient["web/src/lib/api.ts"]
    Terminal --> BrowserState["浏览器本地状态<br/>client_id / 轻量记忆 / 引导状态 / 持续跟踪"]
    Terminal --> ApiClient
    Debug --> ApiClient
    ApiClient --> FastAPI["app/main.py<br/>FastAPI 页面与 API 入口"]

    FastAPI --> AuthApi["auth/profile API<br/>登录、会话、长期偏好"]
    FastAPI --> RunsApi["runs API<br/>创建、查询、事件流、取消、重试、恢复"]
    FastAPI --> HistoryApi["history API<br/>历史、审计摘要、PDF 导出"]
    FastAPI --> BacktestApi["backtests API<br/>回测创建与查询"]
    FastAPI --> DataApi["tools/admin API<br/>数据状态与刷新"]

    AuthApi --> AuthService["AuthService"]
    AuthApi --> ProfileService["ProfileService"]
    RunsApi --> RunService["RunService"]
    HistoryApi --> RunService
    HistoryApi --> PdfExportService["PdfExportService"]
    BacktestApi --> BacktestService["BacktestService"]
    DataApi --> MarketDataService["MarketDataService"]

    RunService --> RunRepo["Run SQLite<br/>runs / stages / artifacts / events<br/>backtests / users / sessions / audit / preferences"]
    AuthService --> RunRepo
    ProfileService --> RunRepo
    BacktestService --> RunRepo
    PdfExportService --> RunRepo

    RunService --> WorkflowRunner["WorkflowRunner"]
    WorkflowRunner --> AgentWorkflow["FinancialAgentWorkflow"]
    WorkflowRunner --> StructuredWorkflow["StructuredAnalysisWorkflow"]

    AgentWorkflow --> ProfileService
    AgentWorkflow --> AgentCoordinator["AgentCoordinator"]
    StructuredWorkflow --> AnalysisService["AnalysisService"]

    AgentCoordinator --> Intake["IntakeAgent<br/>理解问题并合并记忆"]
    Intake --> Planner["PlannerAgent<br/>生成计划和工具白名单"]
    Planner --> DataAgent["DataAgent"]
    DataAgent --> EvidenceAgent["EvidenceAgent"]
    EvidenceAgent --> Bull["BullAnalystAgent"]
    EvidenceAgent --> Bear["BearAnalystAgent"]
    Bull --> Arbiter["ArbiterAgent"]
    Bear --> Arbiter
    Arbiter --> ReportAgent["ReportAgent"]
    ReportAgent --> Validator["ValidatorAgent"]
    Validator --> ReportOutputs["report_outputs.py<br/>简单版 / 专业版 / 开发者报告<br/>display_model"]

    Planner --> ToolRunner["ToolRegistry / ToolRunner<br/>权限、重试、超时、审计"]
    DataAgent --> ToolRunner
    EvidenceAgent --> ToolRunner
    ReportAgent --> ToolRunner
    Validator --> ToolRunner

    ToolRunner --> AnalysisService
    AnalysisService --> Screener["analysis_runtime.screener<br/>股票池筛选"]
    AnalysisService --> Toolkit["MarketToolKit<br/>价格、技术、新闻、SEC、宏观、仓位代理"]
    AnalysisService --> MarketDataService

    MarketDataService --> MarketRepo["Market SQLite / 本地缓存"]
    MarketDataService --> SeedData["data/seed<br/>备用股票池"]
    Toolkit --> Fetchers["app/tools/fetchers<br/>Alpaca / yfinance / SEC EDGAR<br/>Yahoo RSS / Alpha Vantage / Finnhub / FRED"]
    Fetchers --> ExternalData["外部市场与研究数据"]
    Fetchers --> MarketRepo

    ToolRunner --> ReportService["ReportService"]
    ReportService --> RagService["KnowledgeRagService"]
    RagService --> KnowledgeRepo["Knowledge SQLite FTS5<br/>证据文档、引用映射、时效标记"]
    ReportService --> LLM["DeepSeek Chat Completions<br/>OpenAI compatible API"]
    ReportService --> Validation["rag_validation.py<br/>评分、风险、证据和时间范围校验"]

    ReportOutputs --> RunRepo
    AgentCoordinator --> RunRepo
    WorkflowRunner --> RunRepo

    RunRepo --> EventStream["SSE 事件流<br/>/api/runs/{run_id}/events"]
    EventStream --> Terminal
    RunRepo --> ResultViews["结论页 / 历史页 / Debug 产物"]
    ResultViews --> Terminal
    ResultViews --> Debug

    Terminal --> PdfRequest["PDF 导出请求"]
    PdfRequest --> HistoryApi
    PdfExportService --> PdfFile["真实 PDF 文件"]
    PdfFile --> Terminal

    Terminal --> BacktestRequest["回测请求"]
    BacktestRequest --> BacktestApi
    BacktestService --> BacktestResult["组合收益、SPY 基准、回撤、逐票贡献"]
    BacktestResult --> RunRepo
    BacktestResult --> Terminal

    Debug --> ResumeRequest["按 agent checkpoint 恢复"]
    ResumeRequest --> RunsApi
    RunsApi --> WorkflowRunner
```

## 一次自然语言研究的顺序

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant T as Terminal
    participant API as FastAPI API
    participant RS as RunService
    participant DB as Run SQLite
    participant WR as WorkflowRunner
    participant AC as AgentCoordinator
    participant TR as ToolRunner
    participant AS as AnalysisService
    participant EXT as 外部数据源
    participant RAG as RAG 知识库
    participant LLM as DeepSeek
    participant OUT as 报告/PDF/回测

    U->>T: 输入投资目标、风险、期限或历史日期
    T->>API: POST /api/runs，自动带 X-Client-Id
    API->>RS: 创建 run，并传入当前账户或浏览器标识
    RS->>DB: 保存 run、原始输入、创建事件和审计记录
    RS->>DB: 读取长期偏好，补齐本次问题缺失字段
    RS->>WR: 调度 agent 或 structured workflow
    WR->>AC: 启动 FinancialAgentWorkflow

    AC->>AC: IntakeAgent 解析意图，必要时返回一句补充追问
    AC->>AC: PlannerAgent 生成 research_plan、任务图和工具白名单
    AC->>TR: DataAgent 请求 market.research_package
    TR->>AS: 权限检查后运行结构化分析
    AS->>EXT: 拉取股票池、价格、技术面、新闻、SEC、宏观和仓位代理
    EXT-->>AS: 返回实时或历史数据，失败时降级并记录 warning
    AS-->>TR: 返回候选股、评分、研究快照和数据诊断
    TR-->>AC: 返回 DataAgent 工具审计

    AC->>TR: EvidenceAgent 请求 report.build_package 和 rag.attach_evidence
    TR->>RAG: 写入研究证据，检索引用，生成 citation_map
    RAG-->>TR: 返回证据、时效和来源可靠性
    TR-->>AC: 返回报告输入包和证据包

    AC->>AC: BullAnalystAgent 与 BearAnalystAgent 形成正反观点
    AC->>AC: ArbiterAgent 汇总结论、风险和可执行裁决
    AC->>TR: ReportAgent 请求 report.render
    TR->>LLM: 调用 DeepSeek 生成正式报告，失败则回退结构化报告
    LLM-->>TR: 返回报告正文或错误信息
    TR-->>AC: 返回 final_report 和 llm_raw

    AC->>TR: ValidatorAgent 请求 report.validate
    TR->>RAG: 校验证据时效、评分排序、风险覆盖和时间范围
    RAG-->>TR: 返回 validation_checks 和可信度
    TR-->>AC: 返回校验后的报告包
    AC->>OUT: 生成简单版、专业版、开发者报告和 display_model
    AC->>DB: 保存 snapshot、stages、agent_trace、tool_invocations、report_outputs
    WR->>DB: 标记 run 为 completed、failed 或 needs_clarification
    DB-->>T: SSE 推送阶段、产物和最终状态
    T->>API: 读取 run detail、artifacts、audit summary
    API-->>T: 展示结论页、历史页和 Debug 产物

    T->>API: 可选 POST /api/v1/backtests
    API->>OUT: BacktestService 生成组合 vs SPY、回撤和逐票贡献
    OUT->>DB: 保存 backtest
    T->>API: 可选 GET /api/v1/runs/{run_id}/export/pdf
    API->>OUT: PdfExportService 读取 display_model 和最近回测
    OUT-->>T: 返回真实 PDF
```

## 关键数据落点

| 数据 | 产生位置 | 保存或使用位置 |
| --- | --- | --- |
| 用户问题、风险、期限、历史日期 | `/terminal` 表单 | `RunCreateRequest`、run input artifact |
| 浏览器身份 | `web/src/lib/clientIdentity.ts` | 请求头 `X-Client-Id`，用于隔离长期偏好 |
| 账户与会话 | `app/api/auth.py`、`AuthService` | Run SQLite 的用户、会话和审计表 |
| 长期偏好 | `ProfileService`、`AgentMemoryContext` | Run SQLite 的偏好表，下一次研究只补缺失字段 |
| 运行阶段 | `WorkflowContext.add_stage` | Run SQLite 的 stage/event，前端通过 SSE 和详情接口读取 |
| agent 交接记录 | `AgentCoordinator` | `agent_trace`、`agent_checkpoints` artifact，Debug 页面读取 |
| 工具调用审计 | `ToolRunner` | `tool_invocations` artifact，记录权限、耗时、重试和错误 |
| 市场数据 | `MarketToolKit`、fetchers | 研究快照、Market SQLite、本地缓存 |
| RAG 证据 | `KnowledgeRagService` | Knowledge SQLite FTS5、citation map、报告引用 |
| 报告输出 | `report_outputs.py` | 简单版、专业版、开发者报告和 PDF 共用的 `display_model` |
| 回测结果 | `BacktestService` | Run SQLite 的 backtest 记录，结论页和回测页读取 |
| PDF 文件 | `PdfExportService` | 即时生成并返回，不作为运行主结果写回 |

## 旁路流程

- 示例引导走 `web/src/lib/demoResearch.ts`，只在前端注入固定示例，不创建真实 run，不写入后端历史。
- 结构化模式走 `StructuredAnalysisWorkflow`，直接进入 `AnalysisService`，不经过九个 agent。
- `/debug` 可从某个可恢复 agent 的 checkpoint 开始重跑，系统会复用上游结果并重跑该 agent 及下游。
- 历史页优先读取审计摘要，不直接消费完整 run 原始结果，避免前台展示过重。
