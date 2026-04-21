# Railway 公网部署说明

这份说明面向“我要把网站发给别人直接访问”的场景。

## 适用情况

- 你已经把项目推到 GitHub
- 你希望别人通过一个公网网址访问首页和 Terminal
- 你不想拆前端和后端，想一次性把整个项目部署出去

## 项目当前部署方式

这个项目已经支持：

- 使用根目录 `Dockerfile` 构建
- 容器内自动构建前端
- 启动时自动读取 `PORT`
- 提供健康检查地址：`/healthz`

因此在 Railway 上，直接按 Docker Web Service 部署即可。

## Railway 上线步骤

### 1. 准备 GitHub 仓库

先确认 GitHub 上是最新代码，尤其要包含：

- `Dockerfile`
- `docker-compose.yml`
- 最新的 `web/dist` 构建逻辑

### 2. 在 Railway 新建项目

1. 登录 Railway
2. 点击 `New Project`
3. 选择 `Deploy from GitHub repo`
4. 选择这个仓库

Railway 会自动识别根目录 `Dockerfile`。

### 3. 配置环境变量

最少需要填：

- `ARK_API_KEY`
- `ARK_BASE_URL`
- `ARK_MODEL`

如果火山 API 不稳定，建议同时填写 DeepSeek 备用源：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL=deepseek-chat`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`

建议同时填写：

- `ALPACA_API_KEY_ID`
- `ALPACA_API_SECRET_KEY`
- `FINNHUB_API_KEY`
- `ALPHA_VANTAGE_API_KEY`
- `FRED_API_KEY`
- `LONGBRIDGE_APP_KEY`
- `LONGBRIDGE_APP_SECRET`
- `LONGBRIDGE_ACCESS_TOKEN`

如需代理再填写：

- `MARKET_PROXY_MODE`
- `MARKET_PROXY_URL`

### 4. 配置数据存储

如果你希望保留：

- 历史研究记录
- 回测结果
- 最近一次用户偏好
- 本地知识库证据

建议在 Railway 给服务挂一个持久化卷，并把环境变量设成：

```text
FINANCIAL_AGENT_DB_PATH=/app/data/runtime/financial_agent_runs.sqlite3
FINANCIAL_AGENT_MARKET_DB_PATH=/app/data/runtime/financial_agent_market.sqlite3
FINANCIAL_AGENT_KNOWLEDGE_DB_PATH=/app/data/runtime/financial_agent_knowledge.sqlite3
```

如果不挂卷，服务重建后这些数据可能会丢失。

注意：

- Volume 要挂到 `/app/data/runtime`
- 不要挂到 `/app/data`
- 项目已经补了应用内备用种子文件，但正确挂载仍然是最稳的做法

### 5. 首次部署后检查

部署成功后，依次检查：

- `/healthz` 是否返回 `ok`
- `/` 首页是否正常打开
- `/terminal` 是否可进入
- 是否能生成 1 条中文研究
- 是否能生成 1 条英文研究
- 历史模式是否能进入回测页

## 建议的验收顺序

### 中文稳健型

```text
我有 50000 美元，想找适合长期持有的低风险分红股。请优先比较 JNJ、PG、KO，并给我一份正式的投资研究结论，包括估值、ROE、自由现金流、主要风险和执行建议。
```

### 英文成长型

```text
I have about $50,000 and want long-term growth with controlled risk. Compare Microsoft, Meta and Alphabet, then give me a formal investment memo with valuation, quality, risks and staged entry advice.
```

### 历史回测型

```text
我有 50000 美元，想找适合长期持有的低风险分红股。请优先比较 JNJ、PG、KO，并给我一份正式的投资研究结论，包括估值、ROE、自由现金流、主要风险和执行建议。
```

历史模式建议：

- `as_of_date`：设为过去至少 6 个月前
- 回测结束日：设为今天

## 常见问题

### 页面打开了，但跑不出报告

通常先检查：

- `ARK_API_KEY`
- `ARK_BASE_URL`
- `ARK_MODEL`

这三个变量是否都已在 Railway 面板中配置。

如果火山临时不可用，可以配置 `DEEPSEEK_API_KEY`，系统会在火山失败时自动切到 DeepSeek。

### 页面能打开，但回测失败

优先检查：

- Alpaca key 是否已配置
- 备用数据源 key 是否已配置
- 结束日期是否晚于历史研究时点

### 页面一直在加载

先看：

- `/healthz` 是否正常
- Railway 日志里是否有启动异常
- 是否有关键环境变量缺失

## 当前默认建议

- 公开展示优先选 Railway
- 部署方式优先选 Docker 单服务
- 环境变量只放 Railway 面板，不写进仓库
- 展示用环境建议挂持久化卷，避免历史记录丢失
