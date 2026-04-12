import os
import json
import yfinance as yf
from fastapi import APIRouter, Request
from typing import Dict, Any
from app.common.payload import parse_poffices_payload

router = APIRouter()

def fetch_macro_regime() -> Dict[str, Any]:
    try:
        # 定义要抓取的三个核心宏观指标
        tickers = {
            "SP500": "^GSPC",  # 标普500指数 (看大盘趋势)
            "VIX": "^VIX",     # 恐慌指数 (看市场情绪)
            "TNX": "^TNX"      # 十年期美债收益率 (看无风险利率/流动性)
        }

        macro_data = {}
        for name, symbol in tickers.items():
            stock = yf.Ticker(symbol)
            # 获取过去 5 天的数据以拿到最新收盘价
            hist = stock.history(period="5d")
            if not hist.empty:
                macro_data[name] = round(hist['Close'].iloc[-1], 2)
            else:
                macro_data[name] = "N/A"

        vix_val = macro_data.get("VIX", 0)
        sp500_val = macro_data.get("SP500", 0)
        tnx_val = macro_data.get("TNX", 0)

        # 宏观风控引擎 (Regime 判断逻辑)
        regime = "Neutral"
        risk_warning = "No major systemic risk detected."

        if isinstance(vix_val, float):
            if vix_val > 30.0:
                regime = "Extreme Risk-Off (Panic)"
                risk_warning = f"CRITICAL: VIX is at {vix_val}, indicating extreme market panic. Suggest drastic position reduction."
            elif vix_val > 20.0:
                regime = "Risk-Off (Caution)"
                risk_warning = f"WARNING: VIX is elevated at {vix_val}. Market volatility is increasing."
            elif vix_val < 15.0:
                regime = "Risk-On (Bullish)"
                risk_warning = "Market is calm. High liquidity environment favors equities."

        if isinstance(tnx_val, float) and tnx_val > 4.5:
            risk_warning += f" | NOTE: High 10Y Yield ({tnx_val}%) may pressure tech stock valuations."

        return {
            "Global_Regime": regime,
            "VIX_Volatility_Index": vix_val,
            "SP500_Level": sp500_val,
            "US10Y_Treasury_Yield": tnx_val,
            "Systemic_Risk_Warning": risk_warning,
            "Status": "Success"
        }
    except Exception as e:
        print(f"❌ [Macro API 报错]: {e}")
        return {"Global_Regime": "Unknown", "Status": f"Failed: {str(e)}"}

@router.post("/api/v1/fetch_macro_data")
async def fetch_macro_endpoint(request: Request):
    # Macro 不依赖具体的股票代码，它直接返回全局的系统性指标
    await parse_poffices_payload(request)
    macro_result = fetch_macro_regime()
    return {"macro_data": macro_result}
