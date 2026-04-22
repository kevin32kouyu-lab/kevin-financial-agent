# Tool Registry

Tool Registry 是 Financial Agent 的受控工具中台。它的目标不是让 agent 任意执行代码，而是让 agent 只能在白名单工具范围内取数、检索、校验和记录调用过程。

## 当前能力

- `ToolSpec`：定义工具名称、说明、权限、输入 schema、超时、重试次数和缓存时间。
- `ToolRegistry`：集中注册和查询工具，防止重名工具覆盖。
- `ToolRunner`：统一执行工具，并处理权限拒绝、超时、重试、缓存和审计回调。
- `ToolInvocationResult`：把每次调用整理成可写入 artifact 的结构化记录。

## 权限模型

每个工具只能声明一个权限域，例如：

- `market_data`
- `news`
- `sec`
- `macro`
- `rag`
- `validation`

agent 调用工具时必须传入 `allowed_permissions`。如果工具权限不在白名单内，调用会返回 `permission_denied`，不会执行真实工具。

## 失败处理

- 未注册工具返回 `not_found`
- 未授权工具返回 `permission_denied`
- 超时返回 `timeout`
- 普通异常返回 `error`
- 成功返回 `success`

失败结果不会直接抛到上层，而是进入统一结果结构，方便 debug 和恢复。

## 审计与缓存

`ToolRunner` 支持传入 `audit_sink`。每次调用结束后，结果都会进入 sink，后续可以写入 `tool_invocations` artifact。

带 `cache_ttl_seconds` 的工具会按工具名和 payload 缓存成功结果，避免同一 agent 阶段重复请求同一份数据。

## 当前边界

- 当前已经落地基础工具层和单元测试。
- 现有 Data/Evidence 链路仍在逐步接入 ToolRunner。
- 外部 MCP 服务暂未接入，本项目先使用内部 MCP/Skills-like 结构。
