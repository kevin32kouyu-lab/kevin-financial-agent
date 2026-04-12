import os
import json
import yfinance as yf
import pandas as pd
from fastapi import APIRouter, Request
from typing import Dict, Any
import asyncio
from app.common.payload import parse_poffices_payload
from app.common.executors import get_shared_executor

# === 可选全局代理注入（从环境变量读取） ===
PROXY_URL = os.getenv("PROXY_URL") or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
if PROXY_URL:
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
    if "http://" not in PROXY_URL and "https://" not in PROXY_URL:
        PROXY_URL = f"http://{PROXY_URL}"
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
# ========================================

router = APIRouter()

def fetch_tech_indicators(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="6mo")
        
        if df.empty: 
            return {"Ticker": ticker, "Status": "No Data"}

        close = df['Close'].squeeze()
        ma_20 = close.rolling(window=20).mean().iloc[-1]
        ma_50 = close.rolling(window=50).mean().iloc[-1]
        
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_14 = 100 - (100 / (1 + rs)).iloc[-1]

        current_price = close.iloc[-1]

        return {
            "Ticker": ticker,
            "Latest_Price": round(float(current_price), 2),
            "MA_20": round(float(ma_20), 2),
            "MA_50": round(float(ma_50), 2),
            "RSI_14": round(float(rsi_14), 2),
            "Status": "Success"
        }
    except Exception as e:
        return {"Ticker": ticker, "Status": f"Failed: {str(e)}"}

@router.post("/api/v1/fetch_tech_data")
async def fetch_tech_data(request: Request):
    try:
        data = await parse_poffices_payload(request)
        tickers = [item.get("Ticker") for item in data.get("comparison_matrix", []) if item.get("Ticker")]
        if not tickers: return {"error": "未收到有效股票代码"}

        tech_results = []
        loop = asyncio.get_running_loop()
        executor = get_shared_executor()
        for t in tickers:
            try:
                task = loop.run_in_executor(executor, fetch_tech_indicators, t)
                res = await asyncio.wait_for(task, timeout=8.0)
                tech_results.append(res)
            except Exception:
                tech_results.append({"Ticker": t, "Status": "Timeout"})

        return {"technical_data": tech_results}
    except Exception as e:
        return {"error": f"技术面抓取异常: {str(e)}"}
