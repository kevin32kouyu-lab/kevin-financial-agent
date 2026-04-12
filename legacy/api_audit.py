import os
import json
import re
import requests
from fastapi import APIRouter, Request
from typing import Dict, Any
import asyncio
from app.common.payload import parse_poffices_payload
from app.common.executors import get_shared_executor

router = APIRouter()

# 🛡️ SEC 官方通行证：使用你的 CUHK 邮箱，声明学术量化研究身份
SEC_HEADERS = {
    "User-Agent": "CUHK_Quant_Research 1155247304@link.cuhk.edu.hk"
}

# 全局缓存 CIK 字典（带线程安全锁）
CIK_MAPPING_CACHE = {}
CIK_MAPPING_LOCK = None

def get_cik_mapping():
    global CIK_MAPPING_CACHE
    if CIK_MAPPING_CACHE:
        return CIK_MAPPING_CACHE
    try:
        res = requests.get("https://www.sec.gov/files/company_tickers.json", headers=SEC_HEADERS)
        data = res.json()
        CIK_MAPPING_CACHE = {v['ticker']: v['cik_str'] for k, v in data.items()}
    except Exception as e:
        print(f"❌ 获取 SEC CIK 映射失败: {e}")
    return CIK_MAPPING_CACHE

def extract_latest_fact(facts: dict, tags: list):
    """从 SEC 庞大的 XBRL 数据树中，提取最新一期的时点财报数据"""
    us_gaap = facts.get('facts', {}).get('us-gaap', {})
    for tag in tags:
        if tag in us_gaap:
            try:
                data_points = us_gaap[tag].get('units', {}).get('USD', [])
                if not data_points: continue
                # 过滤出 10-K(年报) 或 10-Q(季报)，并按日期排序
                valid_points = [p for p in data_points if p.get('form') in ['10-K', '10-Q']]
                valid_points.sort(key=lambda x: x['end'])
                if valid_points:
                    return valid_points[-1]['val']
            except Exception:
                continue
    return None

def fetch_sec_audit_data(ticker: str) -> Dict[str, Any]:
    try:
        mapping = get_cik_mapping()
        cik = mapping.get(ticker.upper())
        if not cik:
            return {"Ticker": ticker, "Status": "Not Found in SEC"}

        cik_padded = str(cik).zfill(10)
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"

        res = requests.get(facts_url, headers=SEC_HEADERS, timeout=10)
        if res.status_code != 200:
            return {"Ticker": ticker, "Status": f"SEC API Rejected: {res.status_code}"}

        facts = res.json()

        # 核心脏活：定义 US-GAAP 标签字典 (专注于绝对不会错位的时点数据)
        equity_tags = ['StockholdersEquity', 'LiabilitiesAndStockholdersEquity']
        debt_tags = ['LongTermDebt', 'DebtCurrent', 'LongTermDebtAndCapitalLeaseObligations']
        current_assets_tags = ['AssetsCurrent']
        current_liabilities_tags = ['LiabilitiesCurrent']
        # 【新增】留存收益 / 累计亏损
        retained_earnings_tags = ['RetainedEarningsAccumulatedDeficit', 'RetainedEarnings']

        # 提取数据
        equity = extract_latest_fact(facts, equity_tags)
        long_term_debt = extract_latest_fact(facts, debt_tags) or 0
        current_assets = extract_latest_fact(facts, current_assets_tags)
        current_liabilities = extract_latest_fact(facts, current_liabilities_tags)
        retained_earnings = extract_latest_fact(facts, retained_earnings_tags)

        if not current_assets or not current_liabilities or not equity:
            return {"Ticker": ticker, "Status": "Data Tag Mismatch"}

        # 财务指标计算
        de_ratio = round(long_term_debt / equity, 2) if equity > 0 else "N/A"
        current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else "N/A"
        # 转换为十亿美元 (Billion) 方便风控阅读
        re_b = round(retained_earnings / 1000000000, 2) if retained_earnings else "N/A"

        # 审计师自动排雷逻辑 (硬性风控)
        risk_flags = []
        if isinstance(de_ratio, float) and de_ratio > 2.0:
            risk_flags.append(f"高负债预警 (D/E: {de_ratio} > 2.0)")
        if isinstance(current_ratio, float) and current_ratio < 1.0:
            risk_flags.append(f"短期流动性危机 (Current Ratio: {current_ratio} < 1.0)")
        if isinstance(re_b, float) and re_b < -1.0:
            risk_flags.append(f"巨额历史累计亏损 (Retained Earnings: {re_b}B USD)")

        overall_risk = "High Risk" if len(risk_flags) >= 2 else ("Medium Risk" if len(risk_flags) == 1 else "Safe")

        return {
            "Ticker": ticker,
            "Debt_to_Equity": de_ratio,
            "Current_Ratio": current_ratio,
            "Retained_Earnings_B": re_b,
            "Risk_Flags": risk_flags if risk_flags else ["无明显财务违约风险"],
            "Overall_Risk_Level": overall_risk,
            "Status": "Success"
        }
    except Exception as e:
        print(f"❌ [{ticker}] SEC 抓取失败: {e}")
        return {"Ticker": ticker, "Status": f"Failed: {str(e)}"}

@router.post("/api/v1/fetch_audit_data")
async def fetch_audit_endpoint(request: Request):
    try:
        data = await parse_poffices_payload(request)
        tickers = [item.get("Ticker") for item in data.get("comparison_matrix", []) if item.get("Ticker")]
        if not tickers: return {"error": "未收到有效股票代码"}

        audit_results = []
        loop = asyncio.get_running_loop()
        executor = get_shared_executor()
        for t in tickers:
            try:
                task = loop.run_in_executor(executor, fetch_sec_audit_data, t)
                # SEC 接口数据包较大，超时时间设定为 15 秒
                res = await asyncio.wait_for(task, timeout=15.0)
                audit_results.append(res)
            except Exception:
                audit_results.append({"Ticker": t, "Status": "Timeout"})

        return {"audit_data": audit_results}
    except Exception as e:
        return {"error": f"财务审计抓取异常: {str(e)}"}
