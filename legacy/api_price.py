import os
import json
import yfinance as yf
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

def fetch_only_price(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty: return {"Ticker": ticker, "Status": "No Data"}
        trend = [round(price, 2) for price in hist['Close'].tolist()]
        return {"Ticker": ticker, "Latest_Price": trend[-1], "Trend_5D": trend, "Status": "Success"}
    except Exception as e:
        return {"Ticker": ticker, "Status": f"Failed: {str(e)}"}

@router.post("/api/v1/fetch_stock_prices")
async def fetch_stock_prices(request: Request):
    try:
        data = await parse_poffices_payload(request)
        tickers = [item.get("Ticker") for item in data.get("comparison_matrix", []) if item.get("Ticker")]
        if not tickers: return {"error": "未收到有效股票代码"}

        price_results = []
        loop = asyncio.get_running_loop()
        executor = get_shared_executor()
        for t in tickers:
            try:
                task = loop.run_in_executor(executor, fetch_only_price, t)
                res = await asyncio.wait_for(task, timeout=8.0)
                price_results.append(res)
            except Exception:
                price_results.append({"Ticker": t, "Status": "Timeout"})

        return {"price_data": price_results}
    except Exception as e:
        return {"error": f"价格抓取异常: {str(e)}"}
