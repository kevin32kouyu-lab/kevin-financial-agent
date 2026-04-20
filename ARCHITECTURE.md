# ARCHITECTURE

## 模块职责

- `app/api/runs.py`：负责创建、查看、重试、撤回 run，并提供事件流。
- `app/api/profile.py`：负责当前浏览器长期偏好的读取、保存和清空。
- `app/agent_runtime/intent.py`：负责从用户这次输入里提取“明确说出来”的投资意图。
- `app/agent_runtime/memory.py`：负责把长期记忆补回本次请求，并在最后再补默认假设。
- `app/repositories/sqlite_profile_repository.py`：负责 `user_profiles` 表的 SQLite 读写。
- `app/services/profile_service.py`：负责长期偏好的清洗、覆盖更新和“显式输入写回记忆”。
- `app/services/agent_service.py`：负责自然语言主流程，并把 `parsed_intent` 和 `memory` 一起写入结果。
- `web/src/lib/clientIdentity.ts`：负责在浏览器本地生成并保存 `client_id`。
- `web/src/lib/api.ts`：负责统一给前端请求加上 `X-Client-Id`。
- `web/src/hooks/useResearchConsole.ts`：负责页面状态、profile 拉取保存和 run 打开后的同步刷新。
- `web/src/components/ProfileMemoryCard.tsx`：负责结果区长期偏好卡片的展示与编辑。

## 调用关系

1. 浏览器首次打开 `/terminal` 时，前端生成并保存本地 `client_id`。
2. 前端所有普通 API 请求都会带上 `X-Client-Id`。
3. `GET /api/v1/profile` 返回当前浏览器的长期偏好，用于初始化结果侧栏卡片。
4. 用户发起自然语言研究后，`RunService` 会把 `client_id` 放进 run 元数据。
5. `FinancialAgentWorkflow` 读取这个 `client_id`，再交给 `AgentService`。
6. `AgentService` 先提取本次显式意图，再把这些长期字段写回 profile。
7. 写回后的 profile 会反向补到本次请求里，只填空白字段，不覆盖用户这次明确输入。
8. 最后系统才补默认假设，并输出 `parsed_intent` 与 `memory` 给前端。

## 关键设计决定

- 长期记忆按浏览器隔离，不做登录，是为了先在当前产品形态下稳定落地。
- 长期记忆和 run 继续共用同一个 SQLite 文件，是为了不增加部署复杂度。
- 长期记忆只保存长期稳定字段，不保存 ticker 和一次性筛选条件，是为了避免记忆污染。
- 默认假设不会写回长期记忆，是为了保证记忆里只保留用户真实表达过的偏好。
- 前端把长期记忆放在结果区轻量卡片里，而不是新开设置页，是为了降低这轮开发体量并保持演示路径简洁。
