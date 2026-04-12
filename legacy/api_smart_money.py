import os
import json
import yfinance as yf
from fastapi import APIRouter, Request
from typing import Dict, Any
import asyncio
from app.common.payload import parse_poffices_payload
from app.common.executors import get_shared_executor

router = APIRouter()

def fetch_smart_money_data(ticker: str) -> Dict[str, Any]:
    try:
        stock = yf.Ticker(ticker)
        info = stock.info

        # 抓取机构持股比例 (如 0.65 代表 65%)
        inst_holdings_raw = info.get('heldPercentInstitutions')
        # 抓取做空比例 (如 0.15 代表流通股中有 15% 被做空)
        short_float_raw = info.get('shortPercentOfFloat')
        # 抓取空头回补天数 (Short Ratio)
        short_ratio = info.get('shortRatio', "N/A")

        inst_holdings = round(inst_holdings_raw * 100, 2) if isinstance(inst_holdings_raw, float) else "N/A"
        short_float = round(short_float_raw * 100, 2) if isinstance(short_float_raw, float) else "N/A"

        # 聪明资金与空头博弈逻辑
        smart_money_signal = "Neutral"

        if isinstance(short_float, float) and isinstance(inst_holdings, float):
            # 核心逻辑：机构重仓且空头比例极高 = 巨大的逼空 (Short Squeeze) 潜力
            if short_float > 15.0 and inst_holdings > 50.0:
                smart_money_signal = f"🔥 HIGH SHORT SQUEEZE POTENTIAL (Short: {short_float}%, Inst: {inst_holdings}%)"
            elif short_float > 10.0:
                smart_money_signal = f"Heavy Bearish Betting (Short: {short_float}%)"
            elif inst_holdings > 80.0:
                smart_money_signal = f"Highly Institutionalized (Inst: {inst_holdings}%)"
            else:
                smart_money_signal = "Retail Driven / Normal Positioning"

        return {
            "Ticker": ticker,
            "Institution_Holding_Pct": inst_holdings,
            "Short_Percent_of_Float": short_float,
            "Short_Ratio_Days": short_ratio,
            "Smart_Money_Signal": smart_money_signal,
            "Status": "Success"
        }
    except Exception as e:
        print(f"❌ [Smart Money API 报错] {ticker}: {e}")
        return {"Ticker": ticker, "Status": f"Failed: {str(e)}"}

@router.post("/api/v1/fetch_smart_money_data")
async def fetch_smart_money_endpoint(request: Request):
    data = await parse_poffices_payload(request)
    tickers = [item.get("Ticker") for item in data.get("comparison_matrix", []) if item.get("Ticker")]
    if not tickers: return {"error": "未收到有效股票代码"}

    results = []
    loop = asyncio.get_running_loop()
    executor = get_shared_executor()
    for t in tickers:
        try:
            task = loop.run_in_executor(executor, fetch_smart_money_data, t)
            res = await asyncio.wait_for(task, timeout=8.0)
            results.append(res)
        except Exception:
            results.append({"Ticker": t, "Status": "Timeout"})
    return {"smart_money_data": results}
