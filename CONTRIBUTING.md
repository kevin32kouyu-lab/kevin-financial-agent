# Contributing

感谢你愿意参与 Financial Agent。这个项目按“正式开源 agent 项目”维护：提交应尽量小、可验证、可回滚。

## 本地准备

1. 安装 Python 3.11、Node.js 22 和 npm。
2. 安装后端依赖：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

3. 安装前端依赖：

```powershell
npm install
npx playwright install chromium
```

4. 复制 `.env.example` 为 `.env`，只填写本地密钥，不要提交真实密钥。

## 开发流程

- 新功能请从单一职责的小改动开始，不要把重构、功能和样式混在一个提交里。
- 普通用户页面保持简洁，agent 过程、工具调用、审计和排障信息放在 `/debug`。
- 涉及投资结论、回测、RAG 或外部数据源时，必须说明数据降级、缓存和时间范围限制。
- 新增配置项要同步更新 `.env.example` 和 README。

## 验证要求

提交前至少运行：

```powershell
.\scripts\verify.ps1 -SkipE2E
```

如果改动影响 Terminal、报告页、PDF、回测或历史页，请运行完整验证：

```powershell
.\scripts\verify.ps1
```

## Pull Request 检查清单

- 代码、文档和测试范围一致。
- 没有提交 `.env`、SQLite 数据库、浏览器快照、导出报告或真实 API Key。
- README、ARCHITECTURE、CONTEXT 只在职责变化、运行方式变化或重要设计变化时更新。
- 对用户可见的中文和英文文案都检查过，不出现混杂或内部调试术语。
