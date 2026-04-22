# Production Governance

本文记录 Financial Agent 作为单服务开源项目运行时的生产治理口径。

## 部署与自检

- 推荐使用 Docker 单服务部署。
- 健康检查使用 `GET /healthz`。
- 就绪检查使用 `GET /readyz`。
- Railway 持久化卷建议挂到 `/app/data/runtime`，避免覆盖镜像内种子数据。

## 配置与密钥

- 所有密钥通过环境变量或 `.env` 注入。
- `.env.example` 只能保留占位符。
- CI 会运行 `scripts/check_secrets.py`，拦截明显的 API Key 和 token。
- 密钥泄露后应立即轮换，并把旧密钥视为不可再用。

## 访问与审计

- 普通用户入口是 `/` 和 `/terminal`。
- `/debug` 和管理员审计接口面向开发与运维排查，不应作为公开用户入口。
- 管理员操作应写入审计事件，保留“谁在什么时候做了什么”的记录。

## 错误与监控

当前项目提供结构化日志、健康检查和就绪检查。生产环境建议额外接入：

- 平台日志告警
- 5xx 错误报警
- 数据源失败率监控
- PDF 导出失败监控
- 回测任务耗时监控

## 数据保留

- SQLite run、market、knowledge 数据库默认放在 `data/runtime`。
- 导出 PDF、浏览器快照、测试报告和缓存文件不应提交到仓库。
- 历史研究可能包含用户 query 和偏好，应按敏感数据处理。
