from __future__ import annotations

import os
import threading
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from typing import Any

from app.core.config import AppSettings
from app.repositories.sqlite_market_repository import SqliteMarketRepository

import requests
import yfinance as yf


REQUEST_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (academic-research)",
}

SEC_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 research-contact@example.com",
}

FRED_HEADERS = {
    "User-Agent": "FinancialAgentLab/1.0 (macro-research)",
}

FRED_SERIES = {
    "SP500_Level": "SP500",
    "VIX_Volatility_Index": "VIXCLS",
    "US10Y_Treasury_Yield": "DGS10",
    "Fed_Funds_Rate": "FEDFUNDS",
    "US_CPI_Index": "CPIAUCSL",
    "US_Unemployment_Rate": "UNRATE",
}

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"

_CIK_MAPPING_CACHE: dict[str, int] = {}
_CIK_MAPPING_LOCK = threading.Lock()


def _market_repository(settings: AppSettings) -> SqliteMarketRepository:
    return SqliteMarketRepository(settings.market_db_path)


def _load_cached_snapshot(
    settings: AppSettings,
    ticker: str,
    snapshot_key: str,
    *,
    ttl_minutes: float,
) -> Any:
    try:
        return _market_repository(settings).get_cached_snapshot(ticker, snapshot_key, ttl_minutes=ttl_minutes)
    except Exception:
        return None


def _store_cached_snapshot(settings: AppSettings, ticker: str, snapshot_key: str, payload: Any) -> None:
    try:
        _market_repository(settings).upsert_cached_snapshot(ticker, snapshot_key, payload)
    except Exception:
        pass


def _get_alpha_vantage_api_key(settings: AppSettings) -> str:
    return settings.alpha_vantage_api_key or ""


def _get_finnhub_api_key(settings: AppSettings) -> str:
    return settings.finnhub_api_key or ""


def _get_alpaca_api_key(settings: AppSettings) -> str:
    return settings.alpaca_api_key or ""


def _get_alpaca_api_secret(settings: AppSettings) -> str:
    return settings.alpaca_api_secret or ""


def _get_alpaca_assets_url(settings: AppSettings) -> str:
    return settings.alpaca_assets_url


def has_alpaca_credentials(settings: AppSettings) -> bool:
    return settings.alpaca_configured


def fetch_alpaca_us_equities(settings: AppSettings) -> list[dict[str, Any]]:
    if not has_alpaca_credentials(settings):
        return []

    response = requests.get(
        _get_alpaca_assets_url(settings),
        params={
            "status": "active",
            "asset_class": "us_equity",
        },
        headers={
            **REQUEST_HEADERS,
            "APCA-API-KEY-ID": _get_alpaca_api_key(settings),
            "APCA-API-SECRET-KEY": _get_alpaca_api_secret(settings),
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []

    equities: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").upper().strip().replace(".", "-")
        exchange = str(item.get("exchange") or "").upper().strip()
        if not symbol:
            continue
        if exchange not in {"NYSE", "NASDAQ", "AMEX", "ARCA", "BATS"}:
            continue
        equities.append(
            {
                "ticker": symbol,
                "name": item.get("name"),
                "exchange": exchange,
                "asset_class": item.get("class") or item.get("asset_class") or "us_equity",
                "asset_status": item.get("status") or "active",
                "tradable": bool(item.get("tradable")),
                "marginable": bool(item.get("marginable")),
                "shortable": bool(item.get("shortable")),
                "easy_to_borrow": bool(item.get("easy_to_borrow")),
                "fractionable": bool(item.get("fractionable")),
            }
        )
    return equities


def provider_statuses(settings: AppSettings) -> list[dict[str, Any]]:
    return [
        {"provider": "yfinance", "role": "price_tech_macro_primary", "configured": True},
        {"provider": "yahoo_rss", "role": "news_primary", "configured": True},
        {"provider": "sec_edgar", "role": "fundamental_primary", "configured": True},
        {"provider": "alpaca", "role": "universe_primary", "configured": has_alpaca_credentials(settings)},
        {"provider": "wikipedia", "role": "universe_backup", "configured": True},
        {"provider": "alpha_vantage", "role": "price_tech_backup", "configured": bool(_get_alpha_vantage_api_key(settings))},
        {"provider": "finnhub", "role": "news_backup", "configured": bool(_get_finnhub_api_key(settings))},
        {"provider": "fred", "role": "macro_backup", "configured": bool(_get_fred_api_key(settings))},
    ]


def _fetch_alpha_vantage_daily_prices(ticker: str, settings: AppSettings | None = None) -> list[float]:
    api_key = _get_alpha_vantage_api_key(settings or AppSettings.from_env())
    if not api_key:
        return []

    response = requests.get(
        ALPHA_VANTAGE_URL,
        params={
            "function": "TIME_SERIES_DAILY",
            "symbol": ticker,
            "outputsize": "compact",
            "apikey": api_key,
        },
        headers=REQUEST_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    series = payload.get("Time Series (Daily)") or {}
    ordered_dates = sorted(series.keys())
    closes: list[float] = []
    for item_date in ordered_dates:
        close_raw = (series.get(item_date) or {}).get("4. close")
        if close_raw is None:
            continue
        closes.append(float(close_raw))
    return closes


def _compute_rsi(values: list[float], period: int = 14) -> float | None:
    if len(values) < period + 1:
        return None
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(values)):
        delta = values[index] - values[index - 1]
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    recent_gains = gains[-period:]
    recent_losses = losses[-period:]
    avg_gain = sum(recent_gains) / period
    avg_loss = sum(recent_losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _fetch_only_price_from_alpha_vantage(ticker: str, settings: AppSettings | None = None) -> dict[str, Any]:
    prices = _fetch_alpha_vantage_daily_prices(ticker, settings)
    if len(prices) < 1:
        return {"Ticker": ticker, "Status": "No Data", "Source": "alpha_vantage"}

    trend = [round(price, 2) for price in prices[-5:]]
    return {
        "Ticker": ticker,
        "Latest_Price": trend[-1],
        "Trend_5D": trend,
        "Status": "Success",
        "Source": "alpha_vantage",
    }


def _fetch_tech_from_alpha_vantage(ticker: str, settings: AppSettings | None = None) -> dict[str, Any]:
    prices = _fetch_alpha_vantage_daily_prices(ticker, settings)
    if len(prices) < 60:
        return {"Ticker": ticker, "Status": "No Data", "Source": "alpha_vantage"}

    latest_price = prices[-1]
    ma_20 = sum(prices[-20:]) / 20
    ma_50 = sum(prices[-50:]) / 50
    rsi_14 = _compute_rsi(prices, 14)
    return {
        "Ticker": ticker,
        "Latest_Price": round(latest_price, 2),
        "MA_20": round(ma_20, 2),
        "MA_50": round(ma_50, 2),
        "RSI_14": round(rsi_14, 2) if rsi_14 is not None else None,
        "Status": "Success",
        "Source": "alpha_vantage",
    }


def _build_technical_payload_from_prices(ticker: str, prices: list[float], source: str) -> dict[str, Any]:
    if len(prices) < 60:
        return {"Ticker": ticker, "Status": "No Data", "Source": source}

    latest_price = prices[-1]
    ma_20 = sum(prices[-20:]) / 20
    ma_50 = sum(prices[-50:]) / 50
    rsi_14 = _compute_rsi(prices, 14)
    return {
        "Ticker": ticker,
        "Latest_Price": round(latest_price, 2),
        "MA_20": round(ma_20, 2),
        "MA_50": round(ma_50, 2),
        "RSI_14": round(rsi_14, 2) if rsi_14 is not None else None,
        "Status": "Success",
        "Source": source,
    }


def fetch_bulk_tech_indicators(tickers: list[str]) -> list[dict[str, Any]]:
    settings = AppSettings.from_env()
    normalized = [str(ticker).upper().strip() for ticker in tickers if str(ticker).strip()]
    if not normalized:
        return []

    results: dict[str, dict[str, Any]] = {}
    try:
        history = yf.download(
            tickers=" ".join(normalized),
            period="6mo",
            group_by="ticker",
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        history = None

    if history is not None and not history.empty:
        for ticker in normalized:
            try:
                if len(normalized) == 1:
                    close = history["Close"].dropna().tolist()
                else:
                    if ticker not in history.columns.get_level_values(0):
                        continue
                    close = history[ticker]["Close"].dropna().tolist()
                payload = _build_technical_payload_from_prices(ticker, [float(item) for item in close], "yfinance_batch")
                if payload.get("Status") == "Success":
                    _store_cached_snapshot(settings, ticker, "technical", payload)
                results[ticker] = payload
            except Exception:
                continue

    final_results: list[dict[str, Any]] = []
    for ticker in normalized:
        if ticker in results and results[ticker].get("Status") == "Success":
            final_results.append(results[ticker])
            continue
        final_results.append(fetch_tech_indicators(ticker))
    return final_results


def _fetch_finnhub_company_news(ticker: str, settings: AppSettings) -> list[dict[str, Any]]:
    api_key = _get_finnhub_api_key(settings)
    if not api_key:
        return []

    end_date = date.today()
    start_date = end_date - timedelta(days=10)
    response = requests.get(
        f"{FINNHUB_BASE_URL}/company-news",
        params={
            "symbol": ticker,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "token": api_key,
        },
        headers=REQUEST_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []

    news_items: list[dict[str, Any]] = []
    for item in payload[:5]:
        title = str(item.get("headline") or "").strip()
        if not title:
            continue
        news_items.append(
            {
                "ticker": ticker,
                "title": title,
                "link": item.get("url") or "",
                "published_at": item.get("datetime") or "",
                "source": "finnhub",
            }
        )
    return news_items


def fetch_only_price(ticker: str) -> dict[str, Any]:
    settings = AppSettings.from_env()
    try:
        history = yf.Ticker(ticker).history(period="5d")
        if history.empty:
            backup = _fetch_only_price_from_alpha_vantage(ticker, settings)
            if backup.get("Status") == "Success":
                return backup
            return {"Ticker": ticker, "Status": "No Data", "Source": "yfinance"}
        trend = [round(float(price), 2) for price in history["Close"].tolist()]
        return {
            "Ticker": ticker,
            "Latest_Price": trend[-1],
            "Trend_5D": trend,
            "Status": "Success",
            "Source": "yfinance",
        }
    except Exception as exc:
        backup = _fetch_only_price_from_alpha_vantage(ticker, settings)
        if backup.get("Status") == "Success":
            backup["Fallback_Reason"] = str(exc)
            return backup
        return {"Ticker": ticker, "Status": f"Failed: {exc}", "Source": "yfinance"}


def fetch_rss_news(ticker: str) -> list[dict[str, Any]]:
    settings = AppSettings.from_env()
    news_items: list[dict[str, Any]] = []
    try:
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=6)
        if response.status_code != 200:
            news_items = []
        else:
            root = ET.fromstring(response.content)
            for item in root.findall("./channel/item")[:5]:
                title = item.findtext("title", default="")
                if not title:
                    continue
                news_items.append(
                    {
                        "ticker": ticker,
                        "title": title,
                        "link": item.findtext("link", default=""),
                        "published_at": item.findtext("pubDate", default=""),
                        "source": "yahoo_rss",
                    }
                )
    except Exception:
        news_items = []

    try:
        finnhub_items = _fetch_finnhub_company_news(ticker, settings)
    except Exception:
        finnhub_items = []

    merged: list[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for item in [*news_items, *finnhub_items]:
        title = str(item.get("title") or "").strip().lower()
        if not title or title in seen_titles:
            continue
        seen_titles.add(title)
        merged.append(item)
    merged = merged[:6]
    if merged:
        _store_cached_snapshot(settings, ticker, "news", merged)
        return merged

    cached = _load_cached_snapshot(settings, ticker, "news", ttl_minutes=360)
    return cached if isinstance(cached, list) else []


def fetch_tech_indicators(ticker: str) -> dict[str, Any]:
    settings = AppSettings.from_env()
    try:
        history = yf.Ticker(ticker).history(period="6mo")
        if history.empty:
            backup = _fetch_tech_from_alpha_vantage(ticker, settings)
            if backup.get("Status") == "Success":
                _store_cached_snapshot(settings, ticker, "technical", backup)
                return backup
            cached = _load_cached_snapshot(settings, ticker, "technical", ttl_minutes=1440)
            if isinstance(cached, dict):
                cached["Status"] = "Cached (primary source unavailable)"
                cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
                return cached
            return {"Ticker": ticker, "Status": "No Data", "Source": "yfinance"}

        close = history["Close"].squeeze()
        ma_20 = close.rolling(window=20).mean().iloc[-1]
        ma_50 = close.rolling(window=50).mean().iloc[-1]

        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi_14 = 100 - (100 / (1 + rs)).iloc[-1]

        payload = {
            "Ticker": ticker,
            "Latest_Price": round(float(close.iloc[-1]), 2),
            "MA_20": round(float(ma_20), 2),
            "MA_50": round(float(ma_50), 2),
            "RSI_14": round(float(rsi_14), 2),
            "Status": "Success",
            "Source": "yfinance",
        }
        _store_cached_snapshot(settings, ticker, "technical", payload)
        return payload
    except Exception as exc:
        backup = _fetch_tech_from_alpha_vantage(ticker, settings)
        if backup.get("Status") == "Success":
            backup["Fallback_Reason"] = str(exc)
            _store_cached_snapshot(settings, ticker, "technical", backup)
            return backup
        cached = _load_cached_snapshot(settings, ticker, "technical", ttl_minutes=1440)
        if isinstance(cached, dict):
            cached["Status"] = "Cached (live source rate-limited)"
            cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
            cached["Fallback_Reason"] = str(exc)
            return cached
        return {"Ticker": ticker, "Status": f"Failed: {exc}", "Source": "yfinance"}


def _get_fred_api_key(settings: AppSettings) -> str:
    return settings.fred_api_key or ""


def _fetch_fred_latest_value(series_id: str, api_key: str) -> float | None:
    response = requests.get(
        FRED_OBSERVATIONS_URL,
        headers=FRED_HEADERS,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 10,
        },
        timeout=12,
    )
    response.raise_for_status()
    observations = response.json().get("observations", [])
    for item in observations:
        value = str(item.get("value", "")).strip()
        if not value or value == ".":
            continue
        return float(value)
    return None


def _fetch_macro_regime_from_fred(api_key: str) -> dict[str, Any]:
    macro: dict[str, Any] = {}
    for field_name, series_id in FRED_SERIES.items():
        macro[field_name] = _fetch_fred_latest_value(series_id, api_key)

    vix_value = macro.get("VIX_Volatility_Index")
    tnx_value = macro.get("US10Y_Treasury_Yield")
    regime = "Neutral"
    warning = "No major systemic risk detected."

    if isinstance(vix_value, float):
        if vix_value > 30:
            regime = "Extreme Risk-Off (Panic)"
            warning = f"CRITICAL: VIX is at {vix_value:.2f}, indicating extreme market panic."
        elif vix_value > 20:
            regime = "Risk-Off (Caution)"
            warning = f"WARNING: VIX is elevated at {vix_value:.2f}. Market volatility is increasing."
        elif vix_value < 15:
            regime = "Risk-On (Bullish)"
            warning = "Market is calm. High liquidity environment favors equities."

    if isinstance(tnx_value, float) and tnx_value > 4.5:
        warning += f" | NOTE: High 10Y Yield ({tnx_value:.2f}%) may pressure tech stock valuations."

    return {
        **macro,
        "Global_Regime": regime,
        "Systemic_Risk_Warning": warning,
        "Status": "Success",
        "Source": "fred",
    }


def _fetch_macro_regime_from_yfinance() -> dict[str, Any]:
    symbols = {
        "SP500_Level": "^GSPC",
        "VIX_Volatility_Index": "^VIX",
        "US10Y_Treasury_Yield": "^TNX",
    }
    macro: dict[str, Any] = {}

    for name, symbol in symbols.items():
        history = yf.Ticker(symbol).history(period="5d")
        macro[name] = round(float(history["Close"].iloc[-1]), 2) if not history.empty else None

    vix_value = macro.get("VIX_Volatility_Index")
    tnx_value = macro.get("US10Y_Treasury_Yield")
    regime = "Neutral"
    warning = "No major systemic risk detected."

    if isinstance(vix_value, float):
        if vix_value > 30:
            regime = "Extreme Risk-Off (Panic)"
            warning = f"CRITICAL: VIX is at {vix_value:.2f}, indicating extreme market panic."
        elif vix_value > 20:
            regime = "Risk-Off (Caution)"
            warning = f"WARNING: VIX is elevated at {vix_value:.2f}. Market volatility is increasing."
        elif vix_value < 15:
            regime = "Risk-On (Bullish)"
            warning = "Market is calm. High liquidity environment favors equities."

    if isinstance(tnx_value, float) and tnx_value > 4.5:
        warning += f" | NOTE: High 10Y Yield ({tnx_value:.2f}%) may pressure tech stock valuations."

    return {
        **macro,
        "Fed_Funds_Rate": None,
        "US_CPI_Index": None,
        "US_Unemployment_Rate": None,
        "Global_Regime": regime,
        "Systemic_Risk_Warning": warning,
        "Status": "Success",
        "Source": "yfinance_primary",
    }


def fetch_macro_regime(settings: AppSettings) -> dict[str, Any]:
    try:
        macro = _fetch_macro_regime_from_yfinance()
        macro["Backup_Source"] = "fred" if _get_fred_api_key(settings) else "none"
        return macro
    except Exception as exc:
        try:
            fred_api_key = _get_fred_api_key(settings)
            if not fred_api_key:
                raise RuntimeError(f"Primary source failed and FRED API key is not configured: {exc}") from exc

            macro = _fetch_macro_regime_from_fred(fred_api_key)
            macro["Fallback_Reason"] = str(exc)
            macro["Primary_Source"] = "yfinance"
            return macro
        except Exception as fallback_exc:
            return {
                "Global_Regime": "Unknown",
                "Status": f"Failed: {fallback_exc}",
                "Source": "unavailable",
            }


def fetch_smart_money_data(ticker: str) -> dict[str, Any]:
    settings = AppSettings.from_env()
    try:
        info = yf.Ticker(ticker).info
        inst_raw = info.get("heldPercentInstitutions")
        short_float_raw = info.get("shortPercentOfFloat")
        short_ratio = info.get("shortRatio", "N/A")

        inst = round(inst_raw * 100, 2) if isinstance(inst_raw, float) else "N/A"
        short_float = round(short_float_raw * 100, 2) if isinstance(short_float_raw, float) else "N/A"

        signal = "Neutral"
        if isinstance(short_float, float) and isinstance(inst, float):
            if short_float > 15 and inst > 50:
                signal = f"High short squeeze potential (Short: {short_float}%, Inst: {inst}%)"
            elif short_float > 10:
                signal = f"Heavy bearish betting (Short: {short_float}%)"
            elif inst > 80:
                signal = f"Highly institutionalized (Inst: {inst}%)"
            else:
                signal = "Public positioning is broadly normal"

        payload = {
            "Ticker": ticker,
            "Institution_Holding_Pct": inst,
            "Short_Percent_of_Float": short_float,
            "Short_Ratio_Days": short_ratio,
            "Smart_Money_Signal": signal,
            "Status": "Success",
            "Source": "yfinance_proxy",
        }
        _store_cached_snapshot(settings, ticker, "smart_money", payload)
        return payload
    except Exception as exc:
        cached = _load_cached_snapshot(settings, ticker, "smart_money", ttl_minutes=1440)
        if isinstance(cached, dict):
            cached["Status"] = "Cached (live source rate-limited)"
            cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
            cached["Fallback_Reason"] = str(exc)
            return cached
        return {
            "Ticker": ticker,
            "Status": "Temporarily unavailable (provider rate-limited)",
            "Source": "yfinance_proxy",
            "Fallback_Reason": str(exc),
            "Smart_Money_Signal": "Public positioning proxy is temporarily unavailable.",
        }


def _get_cik_mapping() -> dict[str, int]:
    global _CIK_MAPPING_CACHE
    if _CIK_MAPPING_CACHE:
        return _CIK_MAPPING_CACHE

    with _CIK_MAPPING_LOCK:
        # Double-check after acquiring lock
        if _CIK_MAPPING_CACHE:
            return _CIK_MAPPING_CACHE
        try:
            response = requests.get(
                "https://www.sec.gov/files/company_tickers.json",
                headers=SEC_HEADERS,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            _CIK_MAPPING_CACHE = {str(item["ticker"]).upper(): int(item["cik_str"]) for item in data.values()}
        except Exception:
            _CIK_MAPPING_CACHE = {}
    return _CIK_MAPPING_CACHE


def _extract_latest_fact(facts: dict[str, Any], tags: list[str]) -> float | int | None:
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    for tag in tags:
        if tag not in us_gaap:
            continue
        try:
            data_points = us_gaap[tag].get("units", {}).get("USD", [])
            valid_points = [point for point in data_points if point.get("form") in {"10-K", "10-Q"}]
            valid_points.sort(key=lambda point: point.get("end", ""))
            if valid_points:
                return valid_points[-1].get("val")
        except Exception:
            continue
    return None


def _fetch_recent_filings(cik: int) -> list[dict[str, Any]]:
    response = requests.get(
        f"https://data.sec.gov/submissions/CIK{str(cik).zfill(10)}.json",
        headers=SEC_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    payload = response.json()
    recent = payload.get("filings", {}).get("recent", {})
    forms = recent.get("form", []) or []
    filing_dates = recent.get("filingDate", []) or []
    accession_numbers = recent.get("accessionNumber", []) or []
    primary_documents = recent.get("primaryDocument", []) or []

    filings: list[dict[str, Any]] = []
    for index, form_type in enumerate(forms[:8]):
        accession_number = accession_numbers[index] if index < len(accession_numbers) else ""
        primary_document = primary_documents[index] if index < len(primary_documents) else ""
        filed_at = filing_dates[index] if index < len(filing_dates) else ""
        archive_accession = accession_number.replace("-", "")
        filing_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/{archive_accession}/{primary_document}"
            if archive_accession and primary_document
            else ""
        )
        filings.append(
            {
                "form": form_type,
                "filed_at": filed_at,
                "accession_number": accession_number,
                "primary_document": primary_document,
                "filing_url": filing_url,
            }
        )
    return filings


def fetch_sec_audit_data(ticker: str) -> dict[str, Any]:
    try:
        cik = _get_cik_mapping().get(str(ticker).upper())
        if not cik:
            return {"Ticker": ticker, "Status": "Not Found in SEC", "Source": "sec_edgar"}

        recent_filings = _fetch_recent_filings(cik)
        filing_summary = ", ".join(
            f"{item['form']} ({item['filed_at']})" for item in recent_filings[:3] if item.get("form")
        )

        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{str(cik).zfill(10)}.json"
        response = requests.get(facts_url, headers=SEC_HEADERS, timeout=12)
        if response.status_code != 200:
            return {
                "Ticker": ticker,
                "Status": f"SEC API Rejected: {response.status_code}",
                "Recent_Filings": recent_filings,
                "Recent_Filing_Summary": filing_summary or "No recent filings found.",
                "Source": "sec_edgar",
            }

        facts = response.json()
        equity = _extract_latest_fact(facts, ["StockholdersEquity", "LiabilitiesAndStockholdersEquity"])
        debt = _extract_latest_fact(facts, ["LongTermDebt", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligations"]) or 0
        current_assets = _extract_latest_fact(facts, ["AssetsCurrent"])
        current_liabilities = _extract_latest_fact(facts, ["LiabilitiesCurrent"])
        retained_earnings = _extract_latest_fact(facts, ["RetainedEarningsAccumulatedDeficit", "RetainedEarnings"])

        base_payload = {
            "Ticker": ticker,
            "Recent_Filings": recent_filings,
            "Recent_Filing_Summary": filing_summary or "No recent filings found.",
            "Latest_Filing_Date": recent_filings[0]["filed_at"] if recent_filings else None,
            "Recent_Filing_Forms": [item["form"] for item in recent_filings[:3]],
            "Source": "sec_edgar",
        }

        if not current_assets or not current_liabilities or not equity:
            return {
                **base_payload,
                "Status": "Data Tag Mismatch",
            }

        de_ratio = round(debt / equity, 2) if equity > 0 else "N/A"
        current_ratio = round(current_assets / current_liabilities, 2) if current_liabilities > 0 else "N/A"
        retained_b = round(retained_earnings / 1_000_000_000, 2) if retained_earnings else "N/A"

        risk_flags: list[str] = []
        if isinstance(de_ratio, float) and de_ratio > 2.0:
            risk_flags.append(f"High leverage (D/E: {de_ratio})")
        if isinstance(current_ratio, float) and current_ratio < 1.0:
            risk_flags.append(f"Liquidity pressure (Current Ratio: {current_ratio})")
        if isinstance(retained_b, float) and retained_b < -1.0:
            risk_flags.append(f"Large accumulated deficit ({retained_b}B USD)")

        overall_risk = "High Risk" if len(risk_flags) >= 2 else ("Medium Risk" if risk_flags else "Safe")
        return {
            **base_payload,
            "Debt_to_Equity": de_ratio,
            "Current_Ratio": current_ratio,
            "Retained_Earnings_B": retained_b,
            "Risk_Flags": risk_flags or ["No material audit flags"],
            "Overall_Risk_Level": overall_risk,
            "Status": "Success",
        }
    except Exception as exc:
        return {"Ticker": ticker, "Status": f"Failed: {exc}", "Source": "sec_edgar"}
