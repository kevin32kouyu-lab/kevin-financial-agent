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
    WorkflowRunner --> LangGraphWorkflow["LangGraphFinancialAgentWorkflow<br/>agent_v2 默认"]
    WorkflowRunner -.-> AgentWorkflow["FinancialAgentWorkflow<br/>v1 回退"]
    WorkflowRunner --> StructuredWorkflow["StructuredAnalysisWorkflow"]

    LangGraphWorkflow --> ProfileService
    LangGraphWorkflow --> Graph["LangGraph StateGraph<br/>节点状态 / 条件路由 / checkpoint"]
    AgentWorkflow --> AgentCoordinator["AgentCoordinator<br/>旧版九角色链路"]
    StructuredWorkflow --> AnalysisService["AnalysisService"]

    Graph --> Intake["IntakeNode<br/>理解问题并合并记忆"]
    Intake --> Planner["PlannerNode<br/>生成计划、质量门和节点任务"]
    Planner --> MarketNode["MarketDataNode"]
    Planner --> FundamentalsNode["FundamentalsNode"]
    Planner --> NewsNode["NewsNode"]
    Planner --> SecMacroNode["SecMacroNode"]
    MarketNode --> MergeData["DataMergeNode"]
    FundamentalsNode --> MergeData
    NewsNode --> MergeData
    SecMacroNode --> MergeData
    MergeData --> DataQualityGate["DataQualityGate<br/>候选、行情和缺口检查"]
    DataQualityGate --> EvidenceNode["EvidenceNode"]
    EvidenceNode --> EvidenceQualityGate["EvidenceQualityGate<br/>证据和引用检查"]
    EvidenceQualityGate --> Bull["BullCaseNode"]
    EvidenceQualityGate --> Bear["BearCaseNode"]
    EvidenceQualityGate --> RiskCase["RiskCaseNode"]
    Bull --> Arbiter["ArbiterNode"]
    Bear --> Arbiter
    RiskCase --> Arbiter
    Arbiter --> ReportNode["ReportNode"]
    ReportNode --> ReportQualityGate["ReportQualityGate"]
    ReportQualityGate --> Finalize["FinalizeNode"]
    Finalize --> ReportOutputs["report_outputs.py<br/>简单版 / 专业版 / 开发者报告<br/>display_model"]
    AgentCoordinator --> ReportOutputs

    Planner --> ToolRunner["ToolRegistry / ToolRunner<br/>权限、重试、超时、审计"]
    MarketNode --> ToolRunner
    FundamentalsNode --> ToolRunner
    NewsNode --> ToolRunner
    SecMacroNode --> ToolRunner
    EvidenceNode --> ToolRunner
    ReportNode --> ToolRunner
    AgentCoordinator --> ToolRunner

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
    Graph --> CheckpointRepo["LangGraph Checkpoint SQLite<br/>只负责图执行恢复"]
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

    Debug --> ResumeRequest["旧版按 agent checkpoint 恢复"]
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
    participant LG as LangGraph agent_v2
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
    RS->>WR: 按 AGENT_WORKFLOW_VERSION 调度 workflow
    WR->>LG: 默认启动 LangGraphFinancialAgentWorkflow

    LG->>LG: IntakeNode 解析意图，必要时直接进入 finalize 追问
    LG->>LG: PlannerNode 生成 research_plan、图节点和质量门策略
    LG->>TR: market / fundamentals / news / sec_macro 数据节点并行取数
    TR->>AS: 权限检查后运行结构化分析
    AS->>EXT: 拉取股票池、价格、技术面、新闻、SEC、宏观和仓位代理
    EXT-->>AS: 返回实时或历史数据，失败时降级并记录 warning
    AS-->>TR: 返回候选股、评分、研究快照和数据诊断
    TR-->>LG: 返回四类数据包和工具审计
    LG->>LG: DataMergeNode 合并数据包
    LG->>LG: DataQualityGate 检查候选、核心行情和关键缺口

    LG->>TR: EvidenceNode 请求 report.build_package 和 rag.attach_evidence
    TR->>RAG: 写入研究证据，检索引用，生成 citation_map
    RAG-->>TR: 返回证据、时效和来源可靠性
    TR-->>LG: 返回报告输入包和证据包
    LG->>LG: EvidenceQualityGate 检查证据数量和引用可用性

    LG->>LG: BullCaseNode / BearCaseNode / RiskCaseNode 形成观点和风险说明
    LG->>LG: ArbiterNode 汇总结论、风险和可执行裁决
    LG->>TR: ReportNode 请求 report.render
    TR->>LLM: 调用 DeepSeek 生成正式报告，失败则回退结构化报告
    LLM-->>TR: 返回报告正文或错误信息
    TR-->>LG: 返回 final_report 和 llm_raw

    LG->>TR: ReportQualityGate 复用 report.validate 校验
    TR->>RAG: 校验证据时效、评分排序、风险覆盖和时间范围
    RAG-->>TR: 返回 validation_checks 和可信度
    TR-->>LG: 返回校验后的报告包
    LG->>OUT: FinalizeNode 生成简单版、专业版、开发者报告和 display_model
    LG->>DB: 保存 snapshot、stages、agent_trace、tool_invocations、report_outputs
    LG->>DB: 写入独立 LangGraph checkpoint，用于图执行恢复
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
| agent 交接记录 | LangGraph 节点或旧版 `AgentCoordinator` | `agent_trace`、`agent_checkpoints` artifact，Debug 页面读取 |
| 图执行恢复状态 | `LangGraphFinancialAgentWorkflow` | 独立 LangGraph checkpoint SQLite，只用于 `agent_v2` 图恢复 |
| 工具调用审计 | `ToolRunner` | `tool_invocations` artifact，记录权限、耗时、重试和错误 |
| 市场数据 | `MarketToolKit`、fetchers | 研究快照、Market SQLite、本地缓存 |
| RAG 证据 | `KnowledgeRagService` | Knowledge SQLite FTS5、citation map、报告引用 |
| 报告输出 | `report_outputs.py` | 简单版、专业版、开发者报告和 PDF 共用的 `display_model` |
| 回测结果 | `BacktestService` | Run SQLite 的 backtest 记录，结论页和回测页读取 |
| PDF 文件 | `PdfExportService` | 即时生成并返回，不作为运行主结果写回 |

## 旁路流程

- 示例引导走 `web/src/lib/demoResearch.ts`，只在前端注入固定示例，不创建真实 run，不写入后端历史。
- 结构化模式走 `StructuredAnalysisWorkflow`，直接进入 `AnalysisService`，不经过 `agent_v2` 图节点。
- 旧版自然语言流程仍可通过 `AGENT_WORKFLOW_VERSION=v1` 回退到 `AgentCoordinator`。
- `/debug` 目前继续支持旧版按 agent checkpoint 恢复；`agent_v2` 使用独立 LangGraph checkpoint 保存图执行状态。
- 历史页优先读取审计摘要，不直接消费完整 run 原始结果，避免前台展示过重。
