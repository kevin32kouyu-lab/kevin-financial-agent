"""yfinance data fetcher.

Provides primary source for:
- Price and technical indicators
- Smart money (institutional holding) data
- Macro regime (VIX, S&P 500, 10Y Treasury)
"""

from concurrent.futures import ALL_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import date, timedelta
import time
from typing import Any, Callable, Iterable

from app.core.config import AppSettings
from .base import (
    _build_technical_payload_from_prices,
    _load_cached_snapshot,
    _store_cached_snapshot,
)
from .alpaca_fetcher import (
    fetch_alpaca_bulk_price_snapshots,
    fetch_alpaca_price_snapshot,
)
from .longbridge_fetcher import (
    fetch_longbridge_bulk_price_snapshots,
    fetch_longbridge_price_snapshot,
)
from .yfinance_proxy_router import run_yfinance_call, yfinance_failure_message, yfinance_route_debug
import yfinance as yf


def _dedupe_tickers(tickers: list[str]) -> list[str]:
    """对 ticker 去重并标准化。"""
    normalized = [str(ticker).upper().strip() for ticker in tickers if str(ticker).strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for ticker in normalized:
        if ticker in seen:
            continue
        seen.add(ticker)
        deduped.append(ticker)
    return deduped


def _iter_chunks(items: list[str], chunk_size: int) -> Iterable[list[str]]:
    """把列表拆成固定大小的小批次。"""
    if chunk_size <= 0:
        chunk_size = 1
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def _apply_route_debug(payload: dict[str, Any], exc: Exception | None = None) -> dict[str, Any]:
    """给结果补充 yfinance 路由追踪信息。"""
    debug = yfinance_route_debug(exc)
    payload["Route_Attempts"] = debug.get("route_attempts") or []
    payload["Route_Final"] = debug.get("route_final")
    payload["Failure_Reason_Code"] = debug.get("failure_reason_code")
    if debug.get("proxy_url_source"):
        payload["Proxy_Source"] = debug.get("proxy_url_source")
    return payload


def _collect_in_batches_with_timeout(
    tickers: list[str],
    worker: Callable[[str], dict[str, Any]],
    *,
    timeout_seconds: float,
    max_workers: int,
    batch_size: int,
    pause_seconds: float,
) -> dict[str, dict[str, Any]]:
    """按批并发抓取，并对单批设置超时保护。"""
    outputs: dict[str, dict[str, Any]] = {}
    for chunk_index, chunk in enumerate(_iter_chunks(tickers, batch_size)):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Future[dict[str, Any]], str] = {
                executor.submit(worker, ticker): ticker for ticker in chunk
            }
            done, pending = wait(
                list(futures.keys()),
                timeout=timeout_seconds,
                return_when=ALL_COMPLETED,
            )
            for future in done:
                ticker = futures[future]
                try:
                    outputs[ticker] = future.result()
                except Exception as exc:
                    outputs[ticker] = {
                        "Ticker": ticker,
                        "Status": f"Failed: {exc}",
                        "Source": "yfinance_batch_worker",
                    }
            for future in pending:
                ticker = futures[future]
                future.cancel()
                outputs[ticker] = {
                    "Ticker": ticker,
                    "Status": "Failed: Timeout in batch worker",
                    "Source": "yfinance_batch_worker",
                }
        if chunk_index < (len(tickers) - 1) // batch_size:
            time.sleep(max(0.0, pause_seconds))
    return outputs


def fetch_only_price(ticker: str) -> dict[str, Any]:
    """Fetch latest price and 5-day trend from yfinance.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with latest price and trend data
    """
    from .alpha_vantage_fetcher import _fetch_only_price_from_alpha_vantage

    settings = AppSettings.from_env()
    normalized_ticker = str(ticker or "").upper().strip()
    alpaca_error: Exception | None = None
    longbridge_error: Exception | None = None
    try:
        alpaca_payload = fetch_alpaca_price_snapshot(normalized_ticker, settings)
        if alpaca_payload.get("Status") == "Success":
            _store_cached_snapshot(settings, normalized_ticker, "price", alpaca_payload)
            return alpaca_payload
    except Exception as exc:
        alpaca_error = exc

    try:
        longbridge_payload = fetch_longbridge_price_snapshot(normalized_ticker, settings)
        if longbridge_payload.get("Status") == "Success":
            if alpaca_error is not None:
                longbridge_payload["Fallback_Reason"] = "Alpaca unavailable, switched to Longbridge."
            _store_cached_snapshot(settings, normalized_ticker, "price", longbridge_payload)
            return longbridge_payload
    except Exception as exc:
        longbridge_error = exc

    try:
        history = run_yfinance_call(
            settings,
            operation=f"fetch_only_price:{normalized_ticker}",
            call=lambda: yf.Ticker(normalized_ticker).history(period="5d"),
        )
        if history.empty:
            try:
                backup = _fetch_only_price_from_alpha_vantage(normalized_ticker, settings)
            except Exception:
                backup = {"Ticker": normalized_ticker, "Status": "No Data", "Source": "alpha_vantage"}
            if backup.get("Status") == "Success":
                if alpaca_error is not None:
                    backup["Fallback_Reason"] = f"Alpaca unavailable; {backup.get('Fallback_Reason') or 'switch to alpha vantage'}"
                _store_cached_snapshot(settings, normalized_ticker, "price", backup)
                return backup
            cached = _load_cached_snapshot(settings, normalized_ticker, "price", ttl_minutes=360)
            if isinstance(cached, dict):
                cached["Status"] = "Cached (primary source unavailable)"
                cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
                return cached
            return {"Ticker": normalized_ticker, "Status": "No Data", "Source": "yfinance"}
        trend = [round(float(price), 2) for price in history["Close"].tolist()]
        payload = {
            "Ticker": normalized_ticker,
            "Latest_Price": trend[-1],
            "Trend_5D": trend,
            "Status": "Success",
            "Source": "yfinance",
        }
        _apply_route_debug(payload)
        _store_cached_snapshot(settings, normalized_ticker, "price", payload)
        return payload
    except Exception as exc:
        try:
            backup = _fetch_only_price_from_alpha_vantage(normalized_ticker, settings)
        except Exception:
            backup = {"Ticker": normalized_ticker, "Status": "No Data", "Source": "alpha_vantage"}
        if backup.get("Status") == "Success":
            backup["Fallback_Reason"] = yfinance_failure_message(exc)
            if alpaca_error is not None:
                backup["Fallback_Reason"] = f"Alpaca unavailable; {backup['Fallback_Reason']}"
            if longbridge_error is not None:
                backup["Fallback_Reason"] = f"Longbridge unavailable; {backup['Fallback_Reason']}"
            _apply_route_debug(backup, exc)
            _store_cached_snapshot(settings, normalized_ticker, "price", backup)
            return backup
        cached = _load_cached_snapshot(settings, normalized_ticker, "price", ttl_minutes=360)
        if isinstance(cached, dict):
            cached["Status"] = "Cached (live source rate-limited)"
            cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
            cached["Fallback_Reason"] = yfinance_failure_message(exc)
            _apply_route_debug(cached, exc)
            return cached
        if alpaca_error is not None or longbridge_error is not None:
            payload = {
                "Ticker": normalized_ticker,
                "Status": f"Failed: primary sources unavailable and {yfinance_failure_message(exc)}",
                "Source": "multi_source_fallback",
            }
            return _apply_route_debug(payload, exc)
        payload = {"Ticker": normalized_ticker, "Status": f"Failed: {yfinance_failure_message(exc)}", "Source": "yfinance"}
        return _apply_route_debug(payload, exc)


def fetch_bulk_only_price(tickers: list[str]) -> list[dict[str, Any]]:
    """Fetch latest prices for multiple symbols with Alpaca-first fallback."""
    settings = AppSettings.from_env()
    deduped = _dedupe_tickers(tickers)
    if not deduped:
        return []

    alpaca_success_map: dict[str, dict[str, Any]] = {}
    try:
        alpaca_payloads = fetch_alpaca_bulk_price_snapshots(deduped, settings)
        for payload in alpaca_payloads:
            symbol = str(payload.get("Ticker") or "").upper().strip()
            if not symbol:
                continue
            if payload.get("Status") == "Success":
                alpaca_success_map[symbol] = payload
    except Exception:
        alpaca_success_map = {}

    longbridge_success_map: dict[str, dict[str, Any]] = {}
    remaining_after_alpaca = [ticker for ticker in deduped if ticker not in alpaca_success_map]
    try:
        longbridge_payloads = fetch_longbridge_bulk_price_snapshots(remaining_after_alpaca, settings)
        for payload in longbridge_payloads:
            symbol = str(payload.get("Ticker") or "").upper().strip()
            if not symbol:
                continue
            if payload.get("Status") == "Success":
                longbridge_success_map[symbol] = payload
    except Exception:
        longbridge_success_map = {}

    outputs: list[dict[str, Any]] = []
    for ticker in deduped:
        if ticker in alpaca_success_map:
            outputs.append(alpaca_success_map[ticker])
            continue
        if ticker in longbridge_success_map:
            outputs.append(longbridge_success_map[ticker])
            continue
        outputs.append(fetch_only_price(ticker))
    return outputs


def fetch_tech_indicators(ticker: str) -> dict[str, Any]:
    """Fetch technical indicators (MA20, MA50, RSI) from yfinance.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with technical indicators
    """
    from .alpha_vantage_fetcher import _fetch_tech_from_alpha_vantage

    settings = AppSettings.from_env()
    try:
        history = run_yfinance_call(
            settings,
            operation=f"fetch_tech_indicators:{ticker}",
            call=lambda: yf.Ticker(ticker).history(period="6mo"),
        )
        if history.empty:
            try:
                backup = _fetch_tech_from_alpha_vantage(ticker, settings)
            except Exception:
                backup = {"Ticker": ticker, "Status": "No Data", "Source": "alpha_vantage"}
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
        _apply_route_debug(payload)
        _store_cached_snapshot(settings, ticker, "technical", payload)
        return payload
    except Exception as exc:
        try:
            backup = _fetch_tech_from_alpha_vantage(ticker, settings)
        except Exception:
            backup = {"Ticker": ticker, "Status": "No Data", "Source": "alpha_vantage"}
        if backup.get("Status") == "Success":
            backup["Fallback_Reason"] = yfinance_failure_message(exc)
            _apply_route_debug(backup, exc)
            _store_cached_snapshot(settings, ticker, "technical", backup)
            return backup
        cached = _load_cached_snapshot(settings, ticker, "technical", ttl_minutes=1440)
        if isinstance(cached, dict):
            cached["Status"] = "Cached (live source rate-limited)"
            cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
            cached["Fallback_Reason"] = yfinance_failure_message(exc)
            _apply_route_debug(cached, exc)
            return cached
        payload = {
            "Ticker": ticker,
            "Latest_Price": None,
            "MA_20": None,
            "MA_50": None,
            "RSI_14": None,
            "Status": "Degraded (technical data unavailable)",
            "Source": "technical_fallback",
            "Fallback_Reason": yfinance_failure_message(exc),
        }
        return _apply_route_debug(payload, exc)


def fetch_smart_money_data(ticker: str) -> dict[str, Any]:
    """Fetch institutional holding and short interest data from yfinance.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dictionary with smart money positioning data
    """
    settings = AppSettings.from_env()
    try:
        info = run_yfinance_call(
            settings,
            operation=f"fetch_smart_money_data:{ticker}",
            call=lambda: yf.Ticker(ticker).info,
        )
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
        _apply_route_debug(payload)
        _store_cached_snapshot(settings, ticker, "smart_money", payload)
        return payload
    except Exception as exc:
        cached = _load_cached_snapshot(settings, ticker, "smart_money", ttl_minutes=1440)
        if isinstance(cached, dict):
            cached["Status"] = "Cached (live source rate-limited)"
            cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
            cached["Fallback_Reason"] = yfinance_failure_message(exc)
            _apply_route_debug(cached, exc)
            return cached
        payload = {
            "Ticker": ticker,
            "Status": "Temporarily unavailable (provider rate-limited)",
            "Source": "yfinance_proxy",
            "Fallback_Reason": yfinance_failure_message(exc),
            "Smart_Money_Signal": "Public positioning proxy is temporarily unavailable.",
        }
        return _apply_route_debug(payload, exc)


def fetch_bulk_tech_indicators(tickers: list[str]) -> list[dict[str, Any]]:
    """Fetch technical indicators for multiple tickers in batch.

    Args:
        tickers: List of stock ticker symbols

    Returns:
        List of technical indicator dictionaries
    """
    settings = AppSettings.from_env()
    normalized = _dedupe_tickers(tickers)
    if not normalized:
        return []

    results: dict[str, dict[str, Any]] = {}
    for batch_index, chunk in enumerate(_iter_chunks(normalized, 4)):
        try:
            history = run_yfinance_call(
                settings,
                operation=f"fetch_bulk_tech_indicators:{len(chunk)}:batch_{batch_index + 1}",
                call=lambda chunk=chunk: yf.download(
                    tickers=" ".join(chunk),
                    period="6mo",
                    group_by="ticker",
                    auto_adjust=False,
                    progress=False,
                    threads=False,
                ),
            )
        except Exception:
            history = None
        if history is None or history.empty:
            time.sleep(0.25)
            continue
        for ticker in chunk:
            try:
                if len(chunk) == 1:
                    close = history["Close"].dropna().tolist()
                else:
                    if ticker not in history.columns.get_level_values(0):
                        continue
                    close = history[ticker]["Close"].dropna().tolist()
                payload = _build_technical_payload_from_prices(ticker, [float(item) for item in close], "yfinance_batch")
                if payload.get("Status") == "Success":
                    _apply_route_debug(payload)
                    _store_cached_snapshot(settings, ticker, "technical", payload)
                results[ticker] = payload
            except Exception:
                continue
        time.sleep(0.25)

    fallback_tickers = [ticker for ticker in normalized if results.get(ticker, {}).get("Status") != "Success"]
    if fallback_tickers:
        fallback_map = _collect_in_batches_with_timeout(
            fallback_tickers,
            fetch_tech_indicators,
            timeout_seconds=12.0,
            max_workers=2,
            batch_size=2,
            pause_seconds=0.2,
        )
        for ticker in fallback_tickers:
            if ticker in fallback_map:
                results[ticker] = fallback_map[ticker]

    final_results: list[dict[str, Any]] = []
    for ticker in normalized:
        if ticker in results:
            final_results.append(results[ticker])
            continue
        cached = _load_cached_snapshot(settings, ticker, "technical", ttl_minutes=1440)
        if isinstance(cached, dict):
            cached["Status"] = "Cached (bulk fallback)"
            cached["Source"] = f"{cached.get('Source', 'cache')}_cache"
            final_results.append(cached)
        else:
            final_results.append({"Ticker": ticker, "Status": "No Data", "Source": "multi_source_fallback"})
    return final_results


def fetch_bulk_smart_money_data(tickers: list[str]) -> list[dict[str, Any]]:
    """批量抓取 smart money，失败按单票隔离返回。"""
    normalized = _dedupe_tickers(tickers)
    if not normalized:
        return []
    result_map = _collect_in_batches_with_timeout(
        normalized,
        fetch_smart_money_data,
        timeout_seconds=10.0,
        max_workers=2,
        batch_size=2,
        pause_seconds=0.25,
    )
    return [result_map.get(ticker, {"Ticker": ticker, "Status": "No Data", "Source": "smart_money_batch"}) for ticker in normalized]


def _load_yfinance_history_window(ticker: str, start_date: date, end_date: date) -> list[float]:
    """Load historical price data from yfinance for a date range.

    Args:
        ticker: Stock ticker symbol
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of closing prices
    """
    settings = AppSettings.from_env()
    try:
        history = run_yfinance_call(
            settings,
            operation=f"history_window:{ticker}",
            call=lambda: yf.Ticker(ticker).history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                actions=False,
            ),
        )
    except Exception:
        return []
    if history.empty:
        return []
    series = history["Close"].dropna()
    return [float(item) for item in series.tolist()]


def _fetch_macro_regime_from_yfinance() -> dict[str, Any]:
    """Fetch macro regime indicators from yfinance.

    Returns:
        Dictionary with VIX, S&P 500, 10Y Treasury and regime analysis
    """
    symbols = {
        "SP500_Level": "^GSPC",
        "VIX_Volatility_Index": "^VIX",
        "US10Y_Treasury_Yield": "^TNX",
    }
    settings = AppSettings.from_env()
    macro: dict[str, Any] = {}

    for name, symbol in symbols.items():
        history = run_yfinance_call(
            settings,
            operation=f"macro_snapshot:{symbol}",
            call=lambda symbol=symbol: yf.Ticker(symbol).history(period="5d"),
        )
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


def _fetch_macro_regime_from_yfinance_as_of(as_of_date: date) -> dict[str, Any]:
    """Fetch macro regime from yfinance as of a specific historical date.

    Args:
        as_of_date: Historical date to fetch data for

    Returns:
        Dictionary with macro indicators as of the specified date
    """
    from .base import _history_window_start

    symbols = {
        "SP500_Level": "^GSPC",
        "VIX_Volatility_Index": "^VIX",
        "US10Y_Treasury_Yield": "^TNX",
    }
    settings = AppSettings.from_env()
    macro: dict[str, Any] = {}

    for name, symbol in symbols.items():
        history = run_yfinance_call(
            settings,
            operation=f"macro_historical:{symbol}",
            call=lambda symbol=symbol: yf.Ticker(symbol).history(
                start=_history_window_start(as_of_date, 30).isoformat(),
                end=(as_of_date + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                actions=False,
            ),
        )
        if history.empty:
            macro[name] = None
            continue
        series = history["Close"].dropna()
        macro[name] = round(float(series.iloc[-1]), 2) if not series.empty else None

    vix_value = macro.get("VIX_Volatility_Index")
    tnx_value = macro.get("US10Y_Treasury_Yield")
    regime = "Neutral"
    warning = "No major systemic risk detected."

    if isinstance(vix_value, float):
        if vix_value > 30:
            regime = "Extreme Risk-Off (Panic)"
            warning = f"CRITICAL: VIX was at {vix_value:.2f}, indicating extreme market panic."
        elif vix_value > 20:
            regime = "Risk-Off (Caution)"
            warning = f"WARNING: VIX was elevated at {vix_value:.2f}. Market volatility was increasing."
        elif vix_value < 15:
            regime = "Risk-On (Bullish)"
            warning = "Market was calm. Liquidity conditions favored equities."

    if isinstance(tnx_value, float) and tnx_value > 4.5:
        warning += f" | NOTE: High 10Y Yield ({tnx_value:.2f}%) likely pressured growth valuations."

    return {
        **macro,
        "Fed_Funds_Rate": None,
        "US_CPI_Index": None,
        "US_Unemployment_Rate": None,
        "Global_Regime": regime,
        "Systemic_Risk_Warning": warning,
        "Status": "Success",
        "Source": "yfinance_historical",
        "As_Of_Date": as_of_date.isoformat(),
    }
