# CONTEXT

## 当前正在做什么
- “本地知识库 RAG + 结论校验”已经完成并合入 `main`。
- 本轮已新增 SQLite FTS5 知识库、RAG 入库/检索服务、报告后校验层和结论页证据引用展示。
- 新配置 `FINANCIAL_AGENT_KNOWLEDGE_DB_PATH` 已加入本地与 Railway 文档。
- 当前新增 DeepSeek 作为火山 LLM 的备用源，火山失败时自动回退。

## 上次停在哪个位置
- 后端测试已通过：27 个通过。
- 前端构建已通过：`npm run build` 成功。
- 路由轻量检查已通过：`/healthz`、`/terminal`、`/terminal/conclusion`、`/terminal/backtest`、`/terminal/archive` 都返回 200。
- GitHub `main` 已推送到提交 `e82abab`。
- Railway production 最新部署 `535e08e3-1233-41c2-a723-46c5d6f9f8cb` 已成功，线上同样检查了 `/healthz` 和四个终端路由，均返回 200。
- 仍有一个原本就存在的未跟踪目录 `.npm-cache/`，本轮未处理。

## 近期关键决定与原因
- RAG 先采用本地 SQLite + FTS5，不接外部向量数据库，是为了保持 Railway 单服务部署稳定。
- 新闻只保存标题/摘要/链接/日期，SEC 只保存公开披露摘要和链接，避免保存受版权保护的全文。
- 结论页只展示用户能理解的证据摘要和引用入口，不恢复系统理解、长期记忆、覆盖说明等内部卡片。
- DeepSeek 密钥只通过 `DEEPSEEK_API_KEY` 配置，不写入代码或文档。
