# ARCHITECTURE

## 模块职责（一句话）

- `main.py`：项目根入口，负责启动 FastAPI 应用。
- `app/main.py`：注册页面路由、API 路由、健康检查和全局异常处理，并放行 `/terminal` 的子路由页面。
- `app/core/runtime.py`：把仓储、服务和工作流装配成可运行的应用运行时。
- `app/core/auth.py`：处理 API Key、账户会话、管理员权限，并读取浏览器侧传来的 `X-Client-Id`。
- `app/integrations/llm_client.py`：封装 DeepSeek 模型配置、公开运行视图和报告生成请求。
- `app/api/runs.py`：处理 run 的创建、查询、重试、撤回和事件流。
- `app/api/backtests.py`：处理回测创建与回测结果查询。
- `app/api/profile.py`：提供当前浏览器长期偏好的读取、更新和清空接口。
- `app/api/history.py`：提供历史研究列表、单条研究审计摘要和 PDF 导出接口。
- `app/services/run_service.py`：管理 run 生命周期（含取消），并把任务交给对应 workflow。
- `app/workflows/financial_agent.py`：执行自然语言研究流程。
- `app/agent_runtime/controlled_agents.py`：定义 Intake、Planner、Data、Evidence、Report、Validator 六个固定角色 agent，以及增强版计划和交接记录。
- `app/agent_runtime/memory.py`：把最近一次会话里的偏好补到当前问题中，但只补缺失字段。
- `app/services/agent_coordinator.py`：串联六个角色 agent，发布 `research_plan`、`agent_trace`、stage 和 artifact。
- `app/services/agent_service.py`：保留旧导入兼容层，实际指向 `AgentCoordinator`。
- `app/services/analysis_service.py`：做筛选、数据聚合和研究快照拼装。
- `app/services/toolkit.py`：统一调度各类数据抓取器（价格、技术、新闻、审计、宏观等）。
- `app/tools/fetchers.py`：对接外部数据源并提供主源/备用源回退。
- `app/services/investment_memo.py`：把结构化研究结果整理成用户画像、依据、校验和安全摘要。
- `app/services/report_service.py`：提供报告包构建、RAG 证据接入、正式报告生成和最终校验入口。
- `app/services/report_outputs.py`：把同一次 run 的结构化结果整理成简单版投资报告、专业版投资报告和开发者报告，并让 `final_report` 继续兼容简单版正文。
- `app/services/pdf_export_service.py`：按 `kind=simple_investment/professional_investment/development` 把 run 的报告数据整理成打印版 HTML，并调用 Playwright 生成真实 PDF；旧 `kind=investment` 继续映射到简单版。
- `app/services/rag_service.py`：把研究结果写入本地知识库，检索证据，并标记证据时效、来源可靠性和引用映射。
- `app/services/rag_validation.py`：统一计算报告可信度，并检查证据时效、优先标的、评分排序、风险覆盖、数据降级和时间范围。
- `app/services/tool_registry.py`：提供受控工具注册、权限检查、超时、重试、缓存和调用审计的基础层。
- `app/services/auth_service.py`：管理本地用户、会话 token、密码哈希和账户审计事件。
- `app/services/backtest_service.py`：根据历史建议计算组合收益、基准对比、逐票贡献和回测 V2 口径。
- `app/services/profile_service.py`：把长期偏好写入浏览器档案或账户档案，并支持登录后绑定浏览器记忆。
- `app/services/run_audit_service.py`：把完整 run 结果压缩成历史页可读的简版审计摘要。
- `app/tools/fetchers/yfinance_proxy_router.py`：统一控制 yfinance 的直连/代理/自动重试路由。
- `app/repositories/sqlite_run_repository.py`：保存 run、stage、artifact、event、backtest、账户、会话、审计和最近偏好。
- `app/repositories/sqlite_knowledge_repository.py`：保存知识库证据文档，并用 SQLite FTS5 做本地全文检索。
- `web/src/views/Terminal.tsx`：面向用户的研究终端页面（四页结构：开始研究、研究结论、回测页、历史页）。
- `web/src/views/Landing.tsx`：首页入口页面（品牌主视觉、动态研究场景、三步引导、语言切换、进入终端）。
- `web/src/views/Workbench.tsx`：面向开发者的调试与诊断页面（五标签：概览/阶段/智能体/产物/原始 JSON）。
- `web/src/hooks/useResearchConsole.ts`：前端核心状态管理与 API 调用编排，并用轻量缓存同步任务进度、历史、当前 run 和回测。
- `web/src/components/terminal/AccountPanel.tsx`：终端顶部账户入口，负责登录、注册、退出和浏览器记忆同步。
- `web/src/components/terminal/ProductTour.tsx`：终端首次用户引导，负责欢迎弹窗、功能区高亮、分步说明和重新播放。
- `web/src/hooks/useTerminalNavigation.ts`：管理 Terminal 四页内部导航，保留 URL 与 `run` 参数，同时避免整页刷新。
- `web/src/lib/productTour.ts`：保存用户是否已经完成新版产品引导的本地状态。
- `web/src/lib/terminalProgress.ts`：按已完成阶段推断当前运行阶段和更贴近真实感受的进度百分比，避免报告阶段假卡住。
- `web/src/lib/terminalExperience.ts`：生成开始研究页的结构化补充 chips、四步预览、可信度摘要和继续跟进文案。
- `web/src/lib/followedRuns.ts`：在浏览器本地保存持续跟踪列表，让旧研究可以被快速找回和继续跟进。
- `web/src/lib/terminalMemory.ts`：保存轻量记忆与三条标准示例问题，并支持按语言清空本地轻量记忆。
- `web/src/lib/reportOutputs.ts`：统一读取三报告输出、开发报告 diagnostics 字段，并在前端把已加载回测临时合成到结论页图表里。
- `web/src/lib/clientIdentity.ts`：为每个浏览器生成并持久化 `client_id`，作为长期记忆的隔离单位。
- `web/src/components/ProfileMemoryCard.tsx`：调试或旧入口可复用的长期偏好编辑卡片。
- `web/src/components/MotionBackdrop.tsx`：全局动态背景层（粒子、流线、光晕）。
- `web/src/components/TerminalTrustPanels.tsx`：旧版可信度概览组件，用户终端前台不再直接使用。
- `web/src/components/ReportPanel.tsx`：展示简单版投资报告 / 专业版投资报告 / 开发者报告三标签、结论依据、证据引用、校验摘要和导出操作。
- `web/src/components/AgentTracePanel.tsx`：展示 debug 专用的 agent 交接时间线、耗时、证据数量和警告。
- `web/src/components/BacktestPanel.tsx`：展示回测参数、收益指标、曲线、逐票表格、税费/分红/再平衡和本次回测口径。
- `web/e2e/terminal-smoke.spec.ts`：用 Playwright 验证 Terminal 四个主路由、首次用户引导、内部切换、回测延迟加载和 PDF 后端导出。
- `web/src/lib/motion.ts`：动效偏好读写（本地记忆 + 系统低动态检测）。
- `Dockerfile`：把前端和后端一起打包成单服务容器，安装 Chromium，并在启动时读取平台注入的 `PORT`。
- `scripts/verify.py`：统一运行后端测试、密钥扫描、前端类型检查、前端构建和端到端测试。
- `scripts/check_secrets.py`：扫描仓库中的疑似密钥，避免真实 token 被提交。

## 模块调用关系

1. 用户先访问 `/` 查看首页，再进入 `/terminal`。
2. `/terminal` 默认进入开始研究页，只展示提问入口、进度和必要操作。
3. Terminal 顶部的 `AccountPanel` 会读取当前用户状态，并允许把浏览器记忆同步到账户。
4. `ProductTour` 会在用户首次进入终端时展示欢迎弹窗，并用分步浮层指向开始研究、进度、结论、回测、历史和账户入口；完成或跳过后写入本地状态。
5. 开始研究页会通过 `terminalExperience.ts` 提供三种起点、结构化补充 chips 和“四步预览”，让用户在点击前就知道系统会筛选、取数、校验并生成三份报告。
6. 研究完成后自动跳到 `/terminal/conclusion?run=<id>`，结论页默认展示简单版投资报告，并可切换到专业版投资报告和开发者报告。
7. 结论页首屏会先展示可信度摘要和推荐持仓预览；如果用户希望持续关注，可把当前研究加入本地持续跟踪列表。
8. 回测页通过 `/terminal/backtest` 独立查看组合与单股回测。
9. 历史页通过 `/terminal/archive` 独立查看最近报告、持续跟踪列表，并把旧研究一键带回提问页继续跟进。
10. 前端调用 `POST /api/runs` 创建 run。
11. `RunService` 根据模式调度 `financial_agent` 或 `structured_analysis` workflow。
12. `AgentCoordinator` 启动可控多智能体流程，并先由 `IntakeAgent` 完成意图解析。
13. 前端普通请求会自动带上 `X-Client-Id`，登录后还会通过账户会话识别用户。
14. 未登录时后端继续按浏览器隔离长期记忆；登录后 `ProfileService` 优先使用账户档案。
15. 如果当前问题没写清风险、期限或风格，`memory.py` 会把最近一次已知偏好补进来，但不会覆盖本次明确输入。
16. `financial_agent` workflow 会把这次研究形成的偏好快照交给 `ProfileService`，并写回浏览器或账户档案。
17. `useResearchConsole` 会在 run 完成或需要补充信息时同步当前 run、账户和偏好状态，供后续研究继续复用。
18. `PlannerAgent` 生成 `research_plan`，明确本次研究目标、数据需求、候选工具、失败降级策略和预期输出。
19. `ToolRegistry` 定义工具权限、超时、重试、缓存和审计口径，供后续 agent 工具调用统一接入。
20. `DataAgent` 调用 `AnalysisService` 拉取并组装多源数据。
21. `investment_memo` 把分析结果整理成“用户画像 / 依据 / 校验 / 安全摘要”。
22. `EvidenceAgent` 通过 `ReportService` 和 `KnowledgeRagService` 写入知识库、检索证据并生成引用映射。
23. `ReportAgent` 生成正式报告（模型可用则走模型，不可用则回退结构化报告）。
24. `ValidatorAgent` 校验报告与结构化数据、RAG 证据是否一致，并统一回写可信度。
25. `report_outputs.py` 基于同一份 run 生成三份输出：简单版投资报告给普通用户快速决策，专业版投资报告保留机构研究深度，开发者报告说明 Agent、RAG、校验和回测支撑链路。
26. `AgentCoordinator` 汇总 `agent_trace`，每个 agent 的状态、开始/结束时间、耗时、输入、输出、证据数量、警告和产物都会进入 artifact。
27. 结果写入 SQLite（run/stage/artifact/event），并通过 SSE 推送给前端。
28. Terminal 四页切换由 `useTerminalNavigation` 在前端内部完成，URL 仍保留 `/terminal/...` 与 `?run=<id>`。
29. 结论页优先加载 run detail；artifact、audit summary 和 backtest 不阻塞正式报告阅读。
30. `terminalProgress.ts` 会根据已完成阶段推断“当前阶段”和进度百分比，所以即使 step 只在阶段结束后落库，前台也不会在报告生成阶段假卡住。
31. 用户进入回测页或手动触发回测时，前端才调用回测相关接口。
32. `BacktestService` 从历史 run 恢复组合，按回测 V2 口径计入交易成本、滑点、分红、简化税费和再平衡，优先用 `SPY` 作为基准，失败时自动切换备用基准后再持久化回测结果。
33. 历史页通过 `GET /api/v1/runs/{run_id}/audit-summary` 读取精简后的审计摘要，而不是直接消费原始大结果。
34. 用户点击 PDF 导出时，前端调用 `GET /api/v1/runs/{run_id}/export/pdf?kind=...`，后端读取同一份 run 数据和最近回测，用统一的“有效图表”逻辑生成更短的投资 PDF，再交给 Playwright/Chromium 返回真实 PDF 文件。
35. 用户可调用 `POST /api/runs/{run_id}/cancel` 撤回任务，run 状态更新为 `cancelled`。
36. 数据刷新可通过 `/api/v1/data/refresh/universe`、`/api/v1/data/refresh/macro`、`/api/v1/data/refresh/all` 手动触发，并在刷新任务表中留痕。
37. 部署到 Railway 时，容器会启动 `main.py`，由运行时自动读取平台分配的 `PORT`，并通过 `/healthz` 与 `/readyz` 提供探活。

## 关键设计决定与原因

- 保留 `/terminal` 与 `/debug` 双界面：用户体验和开发排障各自清晰，不互相干扰。
- 动效采用“高强度默认 + 手动开关 + 系统低动态自动降级”：保证视觉质感，同时兼顾性能与可访问性。
- 长期记忆采用“浏览器本地 `client_id` + 后端按浏览器隔离保存 + 只补缺不覆盖”：先做出连续上下文体验，同时避免在没有登录系统时把不同人的偏好混在一起。
- 账户系统采用本地邮箱密码与会话 token：先解决跨设备记忆和权限隔离，后续再接 OAuth。
- 长期记忆继续复用 `user_preferences`，账户档案用 `user:<id>` 命名：减少迁移成本，并保留浏览器兼容。
- 历史页单独消费审计摘要接口，而不是直接使用整份 run 结果：这样更稳定，也更适合前台展示。
- 当研究停在 `needs_clarification` 时，继续研究采用“沿用原问题 + 追加一句补充信息”的方式：减少用户重新填写整份输入的负担。
- 公开发布优先采用 Docker 单服务部署：因为前后端已经由同一个 FastAPI 服务托管，最适合直接在 Railway 这类平台上公开发布。
- Railway 的持久化卷挂到 `/app/data/runtime`：这样既能保留运行历史，也不会覆盖镜像里的 `data/seed` 种子文件。
- 知识库采用本地 SQLite + FTS5，而不是外部向量数据库：保持 Railway 单服务部署简单，同时让报告证据可持久化、可回查。
- 多智能体采用“可控多角色”而不是完全自治辩论：每个 agent 有固定职责和交接记录，稳定性优先。
- `agent_trace` 记录时间、状态、证据数量和错误原因：这样 debug 能看到每个环节是否真的执行，以及慢点或失败点在哪里。
- 保留 `AgentService` 兼容导入：旧 workflow 和外部调用不用跟着重命名，实际执行已经切到 `AgentCoordinator`。
- LLM 路由统一使用 DeepSeek：减少供应商分叉，避免报告生成时出现主备模型口径不一致。
- 容器启动改为读取环境变量里的 `PORT`，并增加 `/healthz`：这样更适合 Railway、Render 这类平台做自动探活和公网发布。
- 可信度信息优先放到结论页前台，而不是只埋在正式报告里：让用户第一眼先判断“结论靠什么支撑、哪些地方要保守”。
- `ValidatorAgent` 统一计算 `confidence_level`：避免多个模块各写各的可信度，减少前后不一致。
- 澄清机制采用“一句短追问”而不是长段解释：减少用户把补充信息步骤误解成系统报错。
- 结论、依据、校验、安全摘要共用同一份结构化数据：保证页面、历史记录和导出内容一致。
- 三报告输出共用同一次 run：简单版、专业版和开发者报告不会各跑一遍研究，避免结论互相打架。
- 开发报告 diagnostics 采用“主字段 + 历史别名兼容”：新前端优先读 `evidence_count`、`validation_check_count`，历史 run 仍可回退旧字段。
- 结论页回测图采用“前端临时合成”而不是回写 run：这样不会偷偷改历史 run，又能让页面、导出和回测页尽量一致。
- 终端进度采用“阶段加权”而不是“步数占比”：因为 run 的 step 只在阶段结束后落库，直接按数量算会让用户误以为系统卡住。
- PDF 导出放到后端统一生成：避免浏览器 `window.print()` 造成的假 PDF、样式偏差和内容缺失。
- 投资 PDF 采用“平衡版”而不是重复整份长 memo：PDF 负责可读、可分享，详细长内容继续留在网页、HTML 和 Markdown 导出里。
- PDF 图表和结论页共用“有效图表”逻辑：如果已有回测，就优先展示组合 vs 基准回测；没有回测时，自动改放风险贡献图，避免页面和导出内容打架。
- 首页与终端共享同一动态背景与玻璃层：保证视觉语言统一，不再出现“首页一套、终端一套”的割裂。
- 首页改为“品牌入口 + 强 CTA + 研究场景预览”：让第一次访问的用户先建立信任，再进入终端。
- Terminal 改为“四页终端”而不是“所有内容堆在一页”：让提问、结论、回测、历史各自清楚，不再互相挤压。
- 首次用户引导采用本地一次性弹窗 + 可重播浮层：第一次使用能快速理解功能区，后续不会反复打扰。
- 结论页首屏改为“摘要卡片”而不是“巨大标题海报”：让结论、风险、动作、原始问题都能一眼读清。
- 当前 run 通过地址参数保留：用户在结论页、回测页、历史页之间切换时，不会丢掉正在查看的那份报告。
- Terminal 子页切换采用前端内部导航：保留可分享 URL，同时避免整页刷新造成的等待和状态闪烁。
- 结论页不自动创建回测：报告阅读优先保持轻快，回测只在进入回测页或用户主动触发时加载。
- 前台账户入口采用“轻面板而不是独立页面”：减少跳转，让登录、注册和记忆同步都发生在研究终端里。
- 持续跟踪先落地为浏览器本地列表：先解决“下一次怎么继续用”的问题，再考虑后端订阅和提醒系统。
- `/terminal` 只保留用户决策相关信息，过程性中间产物全部收口到 `/debug`。
- 回测分为 `replay` 和 `reference`：一个强调历史建议回放，一个强调历史表现参考，语义更清楚。
- 回测升级为 V2 可配置口径：默认保守，但允许显式开启分红、简化税费和再平衡，避免用户把样例结果当成精确收益。
- 历史模式严格限制 `as_of_date`：宁可降级提示，也不混入未来数据，保证结论可信。
- 外部数据采用主源 + 备用源 + 缓存：面对免费数据源限流时，系统仍可稳定输出结果。
- 价格链路统一为“Alpaca -> yfinance -> Alpha Vantage -> 6小时缓存”：实时研究、历史研究和回测口径保持一致。
- yfinance 采用“代理隔离路由 + 自动接管”：默认 `auto` 先直连，失败后自动尝试系统代理，且不污染其他数据源的网络设置。
- 回测基准采用“SPY 优先 + 备用 ETF + 现金代理兜底”：避免基准源单点失败导致整单回测不可用。
- 配置读取改为自动加载 `.env`：减少“本地已配置但服务未读取”的隐性失败。
- 任务撤回采用“即时状态反馈 + 最佳努力停止”：前端即时可见，后端避免状态卡死。
- 股票池种子新增“配置路径优先 + 应用内备用副本”双路径：这样即使 Railway 的卷误挂到 `/app/data`，服务仍能启动。
- 筛选结果强制不超过 `max_results`：无论用户额外输入多少股票，最终候选都按量化分数截断，保护稳定性和回测速度。
- 同公司多代码默认按发行主体去重（GOOG/GOOGL、FOX/FOXA、NWS/NWSA）：避免同主体重复入池导致结果失真；若用户明确点名多个代码则保留。
- 逐票卡片采用“技术面 + 新闻面”分开展示，并提供可点击新闻与 SEC 披露链接，提升报告可验证性。
- 回测结果新增“复盘解释”文本（超额收益、主要贡献、回撤提示），降低“只看数字看不懂原因”的门槛。
- `app/api/auth.py`：提供本地账户注册、登录、退出和当前用户查询接口。
- `app/api/admin.py`：提供管理员审计事件查询接口。
