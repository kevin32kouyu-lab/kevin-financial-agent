# RAG Evaluation

Financial Agent 的 RAG 目标是让报告结论能追溯到证据，而不是只输出无法验证的观点。当前采用 SQLite + FTS5，本地可持久化，不依赖外部向量数据库。

## 评测目标

RAG 评测重点看五件事：

- 是否能按用户问题、ticker、日期和模式找回相关证据
- 引用是否包含来源、发布时间、链接和来源类型
- 历史模式是否排除 `as_of_date` 之后的证据
- 证据为空、过旧或降级时是否进入 `validation_checks`
- 报告结论是否与评分表、风险提示和证据一致

## Golden Dataset 口径

小型 golden dataset 应覆盖：

- 实时研究：有新闻、SEC、评分和宏观证据的常见股票
- 历史研究：只允许使用研究日期之前的证据
- 降级研究：新闻或 SEC 缺失时仍能输出谨慎提示
- 冲突研究：报告优先标的和评分排序不一致时应降低可信度

## 当前自动化覆盖

- `tests/test_knowledge_rag.py`：验证知识库建表、去重、FTS 检索和时间过滤
- `tests/test_report_builder.py`：验证结构化报告构建
- `tests/test_controlled_agents.py`：验证 agent trace 与校验字段

## 前台展示原则

普通用户只看到简洁的证据摘要和引用入口。系统理解、长期记忆、覆盖说明和内部降级细节保留在 `/debug` 或 artifact 中。
