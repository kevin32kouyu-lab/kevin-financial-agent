import os
import json
import requests
import xml.etree.ElementTree as ET
from fastapi import APIRouter, Request
from typing import Dict, Any, List
import asyncio
from app.common.payload import parse_poffices_payload
from app.common.executors import get_shared_executor

router = APIRouter()

# 🔥 使用稳健的 Yahoo RSS 接口代替 yfinance
def fetch_rss_news(ticker: str) -> List[Dict[str, Any]]:
    news_items = []
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        # 设置请求头伪装成浏览器
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            root = ET.fromstring(response.content)
            # 解析 XML 找出新闻条目
            for item in root.findall('./channel/item')[:5]: # 每只股票最多抓5条
                title = item.find('title').text if item.find('title') is not None else ""
                link = item.find('link').text if item.find('link') is not None else ""
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                
                news_items.append({
                    "ticker": ticker,
                    "title": title,
                    "link": link,
                    "published_at": pubDate
                })
    except Exception as e:
        print(f"[{ticker}] RSS 新闻抓取失败: {e}")
    
    return news_items

@router.post("/api/v1/fetch_raw_news")
async def fetch_raw_news(request: Request):
    try:
        data = await parse_poffices_payload(request)
        tickers = [item.get("Ticker") for item in data.get("comparison_matrix", []) if item.get("Ticker")]
        if not tickers: return {"error": "未收到有效股票代码"}

        all_news = []
        loop = asyncio.get_running_loop()
        executor = get_shared_executor()

        for t in tickers:
            try:
                task = loop.run_in_executor(executor, fetch_rss_news, t)
                news = await asyncio.wait_for(task, timeout=8.0)
                all_news.extend(news)
            except Exception: pass

        # 返回适合 Ranking 节点的标准数组格式
        return {"raw_news_list": all_news}
    except Exception as e:
        return {"error": f"新闻抓取异常: {str(e)}"}
