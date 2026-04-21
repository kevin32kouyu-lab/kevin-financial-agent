# ARCHITECTURE

## 模块职责（一句话）

- `main.py`：项目根入口，负责启动 FastAPI 应用。
- `app/main.py`：注册页面路由、API 路由、健康检查和全局异常处理，并放行 `/terminal` 的子路由页面。
- `app/core/runtime.py`：把仓储、服务和工作流装配成可运行的应用运行时。
- `app/core/auth.py`：处理公开接口的 API Key 校验，并读取浏览器侧传来的 `X-Client-Id`。
- `app/integrations/llm_client.py`：封装火山主源、DeepSeek 备用源和自动回退请求。
- `app/api/runs.py`：处理 run 的创建、查询、重试、撤回和事件流。
- `app/api/backtests.py`：处理回测创建与回测结果查询。
- `app/api/profile.py`：提供当前浏览器长期偏好的读取、更新和清空接口。
- `app/api/history.py`：提供历史研究列表与单条研究审计摘要接口。
- `app/services/run_service.py`：管理 run 生命周期（含取消），并把任务交给对应 workflow。
- `app/workflows/financial_agent.py`：执行自然语言研究流程。
- `app/agent_runtime/memory.py`：把最近一次会话里的偏好补到当前问题中，但只补缺失字段。
- `app/services/agent_service.py`：把用户问题转为可执行分析请求，并产出报告结果。
- `app/services/analysis_service.py`：做筛选、数据聚合和研究快照拼装。
- `app/services/toolkit.py`：统一调度各类数据抓取器（价格、技术、新闻、审计、宏观等）。
- `app/tools/fetchers.py`：对接外部数据源并提供主源/备用源回退。
- `app/services/investment_memo.py`：把结构化研究结果整理成用户画像、依据、校验和安全摘要。
- `app/services/report_service.py`：把结构化分析结果转成正式报告文本，并把报告模式同步回摘要层。
- `app/services/rag_service.py`：把研究结果写入本地知识库，检索证据并校验报告结论一致性。
- `app/services/rag_validation.py`：检查最终报告是否遗漏优先标的、混入未来证据或与评分冲突。
- `app/services/backtest_service.py`：根据历史建议计算组合收益、基准对比和逐票贡献。
- `app/services/profile_service.py`：把长期偏好写入本地数据库，并提供读取、更新和清空能力。
- `app/services/run_audit_service.py`：把完整 run 结果压缩成历史页可读的简版审计摘要。
- `app/tools/fetchers/yfinance_proxy_router.py`：统一控制 yfinance 的直连/代理/自动重试路由。
- `app/repositories/sqlite_run_repository.py`：保存 run、stage、artifact、event、backtest 和最近偏好。
- `app/repositories/sqlite_knowledge_repository.py`：保存知识库证据文档，并用 SQLite FTS5 做本地全文检索。
- `web/src/views/Terminal.tsx`：面向用户的研究终端页面（四页结构：开始研究、研究结论、回测页、历史页）。
- `web/src/views/Landing.tsx`：首页入口页面（品牌主视觉、动态研究场景、三步引导、语言切换、进入终端）。
- `web/src/views/Workbench.tsx`：面向开发者的调试与诊断页面（四标签：概览/阶段/产物/原始 JSON）。
- `web/src/hooks/useResearchConsole.ts`：前端核心状态管理与 API 调用编排，并同步任务进度、历史和当前 run。
- `web/src/lib/terminalMemory.ts`：保存轻量记忆与三条标准演示问题，并支持按语言清空本地轻量记忆。
- `web/src/lib/clientIdentity.ts`：为每个浏览器生成并持久化 `client_id`，作为长期记忆的隔离单位。
- `web/src/components/ProfileMemoryCard.tsx`：调试或旧入口可复用的长期偏好编辑卡片。
- `web/src/components/MotionBackdrop.tsx`：全局动态背景层（粒子、流线、光晕）。
- `web/src/components/TerminalTrustPanels.tsx`：旧版可信度概览组件，用户终端前台不再直接使用。
- `web/src/components/ReportPanel.tsx`：展示正式研究报告、结论依据、证据引用、校验摘要和导出操作。
- `web/src/components/BacktestPanel.tsx`：展示回测参数、收益指标、曲线和逐票表格。
- `web/src/lib/motion.ts`：动效偏好读写（本地记忆 + 系统低动态检测）。
- `Dockerfile`：把前端和后端一起打包成单服务容器，并在启动时读取平台注入的 `PORT`。

## 模块调用关系

1. 用户先访问 `/` 查看首页，再进入 `/terminal`。
2. `/terminal` 默认进入开始研究页，只展示提问入口、进度和必要操作。
3. 研究完成后自动跳到 `/terminal/conclusion?run=<id>`，结论页只展示用户能理解的摘要、证据引用和正式报告。
4. 回测页通过 `/terminal/backtest` 独立查看组合与单股回测。
5. 历史页通过 `/terminal/archive` 独立查看最近报告并再次打开。
6. 前端调用 `POST /api/runs` 创建 run。
7. `RunService` 根据模式调度 `financial_agent` 或 `structured_analysis` workflow。
8. `AgentService` 完成意图解析后，调用 `AnalysisService` 拉取并组装多源数据。
9. 前端普通请求会自动带上 `X-Client-Id`，后端据此区分不同浏览器的长期记忆。
10. 如果当前问题没写清风险、期限或风格，`memory.py` 会把当前浏览器最近一次已知偏好补进来，但不会覆盖本次明确输入。
11. `financial_agent` workflow 会把这次研究形成的偏好快照交给 `ProfileService`，并按当前 `client_id` 写回数据库。
12. `useResearchConsole` 会在 run 完成或需要补充信息时同步当前 run 与偏好状态，供后续研究继续复用。
13. `investment_memo` 把分析结果整理成“用户画像 / 依据 / 校验 / 安全摘要”。
14. `KnowledgeRagService` 把本次研究的新闻摘要、SEC、评分、宏观和来源信息写入知识库，并按问题与股票检索证据。
15. `ReportService` 把检索证据加入报告输入，生成正式报告（模型可用则走模型，不可用则回退结构化报告），再用 RAG 校验层回写可信度。
16. 结果写入 SQLite（run/stage/artifact/event），并通过 SSE 推送给前端。
17. 用户触发回测时，前端调用 `POST /api/v1/backtests`。
18. `BacktestService` 从历史 run 恢复组合，优先用 `SPY` 作为基准，失败时自动切换备用基准后再持久化回测结果。
19. 历史页通过 `GET /api/v1/runs/{run_id}/audit-summary` 读取精简后的审计摘要，而不是直接消费原始大结果。
20. 用户可调用 `POST /api/runs/{run_id}/cancel` 撤回任务，run 状态更新为 `cancelled`。
21. 部署到 Railway 时，容器会启动 `main.py`，由运行时自动读取平台分配的 `PORT`，并通过 `/healthz` 提供健康检查。

## 关键设计决定与原因

- 保留 `/terminal` 与 `/debug` 双界面：用户体验和开发排障各自清晰，不互相干扰。
- 动效采用“高强度默认 + 手动开关 + 系统低动态自动降级”：保证演示质感，同时兼顾性能与可访问性。
- 长期记忆采用“浏览器本地 `client_id` + 后端按浏览器隔离保存 + 只补缺不覆盖”：先做出连续上下文体验，同时避免在没有登录系统时把不同人的偏好混在一起。
- 长期记忆继续复用现有 `user_preferences` 存储，而不是新开一套账户系统：这样改动最小，也最稳。
- 历史页单独消费审计摘要接口，而不是直接使用整份 run 结果：这样更稳定，也更适合前台展示。
- 当研究停在 `needs_clarification` 时，继续研究采用“沿用原问题 + 追加一句补充信息”的方式：减少用户重新填写整份输入的负担。
- 公开展示优先采用 Docker 单服务部署：因为前后端已经由同一个 FastAPI 服务托管，最适合直接在 Railway 这类平台上公开发布。
- Railway 的持久化卷挂到 `/app/data/runtime`：这样既能保留运行历史，也不会覆盖镜像里的 `data/seed` 种子文件。
- 知识库采用本地 SQLite + FTS5，而不是外部向量数据库：保持 Railway 单服务部署简单，同时让报告证据可持久化、可回查。
- LLM 路由采用“火山主源 + DeepSeek 备用源”：火山接口失败时自动回退，避免报告生成直接中断。
- 容器启动改为读取环境变量里的 `PORT`，并增加 `/healthz`：这样更适合 Railway、Render 这类平台做自动探活和公网发布。
- 可信度信息优先放到结论页前台，而不是只埋在正式报告里：让用户第一眼先判断“结论靠什么支撑、哪些地方要保守”。
- 澄清机制采用“一句短追问”而不是长段解释：减少用户把补充信息步骤误解成系统报错。
- 结论、依据、校验、安全摘要共用同一份结构化数据：保证页面、历史记录和导出内容一致。
- 首页与终端共享同一动态背景与玻璃层：保证视觉语言统一，不再出现“首页一套、终端一套”的割裂。
- 首页改为“品牌入口 + 强 CTA + 研究场景演示”：让第一次访问的用户先建立信任，再进入终端。
- Terminal 改为“四页终端”而不是“所有内容堆在一页”：让提问、结论、回测、历史各自清楚，不再互相挤压。
- 结论页首屏改为“摘要卡片”而不是“巨大标题海报”：让结论、风险、动作、原始问题都能一眼读清。
- 当前 run 通过地址参数保留：用户在结论页、回测页、历史页之间切换时，不会丢掉正在查看的那份报告。
- `/terminal` 只保留用户决策相关信息，过程性中间产物全部收口到 `/debug`。
- 回测分为 `replay` 和 `reference`：一个强调历史建议回放，一个强调历史表现参考，语义更清楚。
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
