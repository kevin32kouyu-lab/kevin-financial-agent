# CONTEXT

## 当前正在做什么
- DeepSeek 备用模型源已经接入并合入 `main`。
- 当前 LLM 路由为“火山主源 + DeepSeek 备用源”，火山请求失败时自动回退。
- DeepSeek 密钥已配置到 Railway 环境变量，不写入代码或文档。

## 上次停在哪个位置
- 后端测试已通过：32 个通过。
- 前端构建已通过：`npm run build` 成功。
- 路由轻量检查已通过：`/healthz`、`/terminal`、`/terminal/conclusion`、`/terminal/backtest`、`/terminal/archive` 都返回 200。
- GitHub `main` 已推送到提交 `d6ad016`。
- Railway production 部署 `60024bb5-d724-4c7d-825f-5901b6bbf7fe` 已成功，线上同样检查了 `/healthz` 和四个终端路由，均返回 200。
- 仍有一个原本就存在的未跟踪目录 `.npm-cache/`，本轮未处理。

## 近期关键决定与原因
- RAG 先采用本地 SQLite + FTS5，不接外部向量数据库，是为了保持 Railway 单服务部署稳定。
- 新闻只保存标题/摘要/链接/日期，SEC 只保存公开披露摘要和链接，避免保存受版权保护的全文。
- 结论页只展示用户能理解的证据摘要和引用入口，不恢复系统理解、长期记忆、覆盖说明等内部卡片。
- DeepSeek 密钥只通过 `DEEPSEEK_API_KEY` 配置，不写入代码或文档。
- 环境变量读取会清理可能混入的 BOM 字符，避免部署平台复制密钥时出现隐性鉴权失败。
