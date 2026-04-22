# Quickstart

本文用于从零启动 Financial Agent。本地开发建议先跑后端和前端构建，再打开 `/terminal` 进行研究。

## 1. 准备环境

需要：

- Python 3.11
- Node.js 22
- npm
- Chromium（由 Playwright 安装）

## 2. 安装依赖

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
npm install
npx playwright install chromium
```

## 3. 配置环境变量

复制 `.env.example` 为 `.env`，至少配置一个模型 Key：

```powershell
$env:ARK_API_KEY="your-key"
```

如果使用备用模型，可以配置：

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-key"
```

可选数据源：

```powershell
$env:ALPHA_VANTAGE_API_KEY="your-alpha-key"
$env:FINNHUB_API_KEY="your-finnhub-key"
$env:FRED_API_KEY="your-fred-key"
```

## 4. 启动服务

```powershell
.\.venv\Scripts\python.exe main.py
```

默认访问：

- `http://127.0.0.1:8001/`
- `http://127.0.0.1:8001/terminal`
- `http://127.0.0.1:8001/debug`
- `http://127.0.0.1:8001/healthz`

## 5. 运行验证

快速验证：

```powershell
.\scripts\verify.ps1 -SkipE2E
```

完整验证：

```powershell
.\scripts\verify.ps1
```

完整验证会运行后端测试、密钥扫描、前端类型检查、生产构建和浏览器端到端测试。

## 6. Docker 启动

```powershell
docker compose up --build
```

Docker 会把前端和后端打包到同一个服务里，并使用 `/healthz` 做健康检查。
