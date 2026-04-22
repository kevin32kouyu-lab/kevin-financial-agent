# CONTEXT

## 当前正在做什么
- 正在落地“双报告输出”：同一次研究同时生成投资报告和开发报告。
- 当前分支是 `codex/production-hardening`。
- 本轮重点是报告输出结构、结论页双标签、PDF `kind` 导出参数和文档同步。

## 上次停在哪个位置
- 已把 Terminal 四页切换改成前端内部导航，保留 URL 和 `run` 参数，但不再整页刷新。
- 已让结论页优先加载报告核心数据，artifacts、audit summary 和 backtest 延后加载。
- 已取消“打开历史结论页时自动创建回测”，只有进入回测页或用户主动触发时才加载/生成回测。
- 已删除临时展示材料，README 不再保留相关入口。
- 已补充 LICENSE、CONTRIBUTING、SECURITY、API、Quickstart、Tool Registry、RAG Evaluation 和 Production Governance 文档。
- 已新增统一验证脚本、CI 统一入口、密钥扫描脚本和 Tool Registry 单元测试。

## 近期关键决定与原因
- 账户系统先做本地邮箱密码，不接第三方 OAuth：实现快，适合单服务 Railway 部署。
- 税费只做简化 flat-rate，不做具体地区税务建议。
- 分红只在数据里有现金分红列时纳入，否则明确写入限制说明。
- 自动刷新任务默认关闭，用环境变量开启，避免部署资源不可控。
- `.npm-cache/` 仍是原本存在的未跟踪目录，本轮未处理。
- PDF 导出采用后端统一模板：保留用户原始问题、结论摘要、评分表、逐票卡、风险、完整 memo 和最近回测摘要，避免前端临时 HTML 与页面内容不一致。
- 面试开源项目优先：文档应聚焦产品能力、架构、运行方式和测试结果，不保留临时展示入口。
- Tool Registry 先落地为内部基础层：先统一权限、超时、重试、缓存和审计结果结构，再逐步把现有数据链路接入。
- 双报告来自同一次 run：`report_outputs.investment` 面向投资者，`report_outputs.development` 面向开源项目读者，`final_report` 继续指向投资报告正文以兼容旧逻辑。
- PDF 导出新增 `kind=investment/development`：不传时默认投资报告，开发报告用于说明 Agent、RAG、校验和回测支撑链路。
