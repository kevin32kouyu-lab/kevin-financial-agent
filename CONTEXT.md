# CONTEXT

## 当前正在做什么
- 正在做项目展示准备：整理根目录、归档旧文档，并让 README 更适合 ChatGPT 阅读和生成展示 PPT。
- 当前本地 `main` 已合入 `codex/production-hardening` 的生产化补强和真 PDF 导出更新。

## 上次停在哪个位置
- 已新增本地账户注册/登录/退出、会话、管理员审计事件。
- 已让长期记忆支持账户档案，并保留浏览器 `client_id` 兼容。
- 已扩展回测 V2：交易成本、滑点、分红模式、简化税费、月度/季度再平衡和数据限制说明。
- 已新增数据刷新任务记录、`/readyz`、GitHub Actions 和 Playwright smoke test。
- 已新增 `/api/v1/runs/{run_id}/export/pdf`，由后端 Playwright/Chromium 生成真实 PDF，不再使用浏览器打印假 PDF。
- 已重写 README：突出项目定位、演示路线、核心能力、架构、运行部署、测试和当前限制，方便 Web 端 ChatGPT 读取仓库后理解项目。
- 已把旧总结文档归档到 `docs/archive/`，把本地临时脚本和运行产物集中到 `tmp/` 下，根目录只保留入口、配置和核心文档。
- 已优化 README 的系统架构图和 Data Flow，使其和当前 `RunService -> WorkflowRunner -> AgentCoordinator -> Agent roles -> Services -> SQLite` 的真实结构一致。
- 已把 `ARCHITECTURE.md` 移到 `docs/architecture.md`，减少 GitHub 根目录散落文档。

## 近期关键决定与原因
- 账户系统先做本地邮箱密码，不接第三方 OAuth：实现快，适合单服务 Railway 部署。
- 税费只做简化 flat-rate，不做具体地区税务建议。
- 分红只在数据里有现金分红列时纳入，否则明确写入限制说明。
- 自动刷新任务默认关闭，用环境变量开启，避免部署资源不可控。
- `.npm-cache/` 仍是原本存在的未跟踪目录，本轮未处理。
- PDF 导出采用后端统一模板：保留用户原始问题、结论摘要、评分表、逐票卡、风险、完整 memo 和最近回测摘要，避免前端临时 HTML 与页面内容不一致。
- README 不再按开发日志堆叠功能，改为先讲展示叙事，再讲技术细节，便于生成答辩 PPT。
- 根目录整理不删除本地文件，只移动到归档或临时目录；`.venv`、`node_modules`、缓存目录仍保留在本地用于运行。
- 根目录中的 Docker、Python、Node、Vite、Tailwind、Playwright 配置继续保留，因为这些工具默认从项目根目录读取。
