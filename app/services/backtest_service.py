from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
import time
import io
from typing import Any
from uuid import uuid4

import pandas as pd
import requests
import yfinance as yf
from fastapi import HTTPException

from app.core.config import AppSettings
from app.domain.contracts import BacktestCreateRequest
from app.repositories.sqlite_run_repository import SqliteRunRepository
from app.tools.fetchers import fetch_alpaca_daily_bars, fetch_longbridge_daily_bars
from app.tools.fetchers.base import _load_cached_snapshot, _store_cached_snapshot
from app.tools.fetchers.yfinance_proxy_router import (
    classify_yfinance_exception,
    run_yfinance_call,
    yfinance_failure_message,
)


ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"
BENCHMARK_TICKER = "SPY"
STOOQ_DAILY_URL = "https://stooq.com/q/d/l/"
BENCHMARK_CANDIDATES = ["SPY", "VOO", "IVV", "QQQ", "DIA"]


@dataclass(slots=True)
class PortfolioPosition:
    ticker: str
    weight: float
    verdict: str
    entry_price: float
    shares: float
    invested_amount: float


class BacktestService:
    def __init__(self, repository: SqliteRunRepository, settings: AppSettings):
        self.repository = repository
        self.settings = settings
        self._last_alpha_request_at = 0.0
        self._recent_yfinance_errors: list[Exception] = []
        self._last_price_routes: dict[str, str] = {}
        self._last_degraded_modules: list[str] = []
        self._last_cache_age_minutes: float | None = None

    def list_backtests(self, *, source_run_id: str | None = None, limit: int = 20) -> dict[str, Any]:
        return {
            "items": [
                item.model_dump()
                for item in self.repository.list_backtests(source_run_id=source_run_id, limit=limit)
            ]
        }

    def get_backtest_or_404(self, backtest_id: str) -> dict[str, Any]:
        detail = self.repository.get_backtest(backtest_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Backtest result not found.")
        return detail.model_dump()

    def create_backtest(self, payload: BacktestCreateRequest) -> dict[str, Any]:
        self._recent_yfinance_errors = []
        self._last_price_routes = {}
        self._last_degraded_modules = []
        self._last_cache_age_minutes = None
        run_detail = self.repository.build_run_detail(payload.source_run_id)
        if run_detail is None:
            raise HTTPException(status_code=404, detail="Historical report not found.")
        if run_detail.run.status != "completed":
            raise HTTPException(status_code=400, detail="Only completed reports can be replayed.")
        if not isinstance(run_detail.result, dict):
            raise HTTPException(status_code=400, detail="This report does not contain a usable result snapshot.")

        result = run_detail.result
        report_briefing = result.get("report_briefing") or {}
        executive = report_briefing.get("executive") or {}
        scoreboard = report_briefing.get("scoreboard") or []
        positions_seed = self._build_positions_seed(
            executive=executive,
            scoreboard=scoreboard,
            report_briefing=report_briefing,
        )
        requested_count = len(positions_seed)
        if not positions_seed:
            raise HTTPException(status_code=400, detail="No investable tickers were found in this report.")

        capital_amount, currency = self._resolve_capital_and_currency(result)
        run_result = run_detail.result if isinstance(run_detail.result, dict) else {}
        research_context = run_result.get("research_context") or {}
        research_mode = str(research_context.get("research_mode") or "realtime")
        as_of_date_raw = research_context.get("as_of_date")
        signal_date = self._resolve_signal_date(run_detail.run.finished_at or run_detail.run.updated_at)
        run_metadata = run_detail.run.metadata or {}
        as_of_candidates = [
            as_of_date_raw,
            run_result.get("research_as_of_date"),
            report_briefing.get("research_as_of_date"),
            run_metadata.get("as_of_date"),
            run_metadata.get("research_as_of_date"),
        ]
        if research_mode == "historical":
            for raw_date in as_of_candidates:
                if not raw_date:
                    continue
                try:
                    signal_date = date.fromisoformat(str(raw_date))
                    break
                except ValueError:
                    continue
        requested_end_date = payload.end_date or date.today()

        mode = payload.mode or "replay"
        if mode not in {"replay", "reference"}:
            raise HTTPException(status_code=400, detail="Backtest mode must be replay or reference.")

        if mode == "replay":
            start_anchor_date = signal_date
            include_start = False
            entry_rule = "next_trading_day_open"
        else:
            if payload.entry_date is None:
                raise HTTPException(status_code=400, detail="entry_date is required when mode=reference.")
            start_anchor_date = payload.entry_date
            include_start = True
            entry_rule = "selected_start_day_open"

        if requested_end_date <= start_anchor_date:
            raise HTTPException(status_code=400, detail="End date must be later than the selected start date.")

        symbols = [item["ticker"] for item in positions_seed]
        price_frames, missing_tickers = self._load_price_frames(symbols, start_anchor_date, requested_end_date)
        dropped_tickers: list[dict[str, Any]] = []
        if missing_tickers:
            dropped_tickers = [
                {
                    "ticker": ticker,
                    "reason": "no_usable_historical_prices",
                }
                for ticker in missing_tickers
            ]
            positions_seed = [item for item in positions_seed if item["ticker"] not in missing_tickers]
            if not positions_seed:
                hint = self._build_backtest_fetch_failure_hint()
                advice = (
                    " Backup sources are not fully configured: set ALPACA_API_KEY_ID, ALPACA_API_SECRET_KEY, and ALPHA_VANTAGE_API_KEY."
                    if (not self.settings.alpaca_configured or not self.settings.alpha_vantage_api_key)
                    else " Backup sources were attempted but still returned no usable prices."
                )
                raise HTTPException(
                    status_code=400,
                    detail=f"Selected symbols have no usable historical prices for this period. {hint}{advice}",
                )

        benchmark_ticker, benchmark_frame, benchmark_warning = self._resolve_benchmark_frame(
            start_date=start_anchor_date,
            end_date=requested_end_date,
            price_frames=price_frames,
        )
        if benchmark_warning:
            run_warnings = (
                ((run_result.get("analysis") or {}).get("debug_summary") or {}).get("warning_flags")
                or []
            )
            run_warnings = [*run_warnings, benchmark_warning]
        else:
            run_warnings = (
                ((run_result.get("analysis") or {}).get("debug_summary") or {}).get("warning_flags")
                or []
            )

        common_dates = self._find_common_dates(
            price_frames,
            start_anchor_date,
            requested_end_date,
            include_start=include_start,
            benchmark_frame=benchmark_frame,
        )
        if not common_dates:
            raise HTTPException(
                status_code=400,
                detail="Historical price data is insufficient. Try choosing an older start date or a later end date.",
            )

        entry_date = common_dates[0]
        effective_end_date = common_dates[-1]
        benchmark_entry_price = (
            float(benchmark_frame.loc[pd.Timestamp(entry_date), "Open"])
            if benchmark_frame is not None
            else None
        )
        backtest_assumptions = self._build_backtest_assumptions()

        portfolio_positions = self._materialize_portfolio_positions(
            positions_seed=positions_seed,
            capital_amount=capital_amount,
            entry_date=entry_date,
            price_frames=price_frames,
            assumptions=backtest_assumptions,
        )
        points, benchmark_final_value = self._build_backtest_points(
            positions=portfolio_positions,
            price_frames=price_frames,
            benchmark_frame=benchmark_frame,
            common_dates=common_dates,
            capital_amount=capital_amount,
            benchmark_entry_price=benchmark_entry_price,
        )

        final_point = points[-1]
        final_value = final_point["portfolio_value"]
        metrics = {
            "initial_capital": round(capital_amount, 2),
            "final_value": round(final_value, 2),
            "benchmark_final_value": round(benchmark_final_value, 2),
            "total_return_pct": round(final_point["portfolio_return_pct"], 2),
            "benchmark_return_pct": round(final_point["benchmark_return_pct"], 2),
            "excess_return_pct": round(final_point["portfolio_return_pct"] - final_point["benchmark_return_pct"], 2),
            "annualized_return_pct": self._annualized_return_pct(
                initial_value=capital_amount,
                final_value=final_value,
                start_date=entry_date,
                end_date=effective_end_date,
            ),
            "max_drawdown_pct": self._max_drawdown_pct(points),
            "trading_days": len(points),
        }
        positions_payload = self._build_position_payloads(
            positions=portfolio_positions,
            price_frames=price_frames,
            end_date=effective_end_date,
            capital_amount=capital_amount,
            entry_date=entry_date,
            common_dates=common_dates,
        )
        report_language = str((((run_result.get("parsed_intent") or {}).get("system_context") or {}).get("language") or "en"))
        attribution_summary = self._build_attribution_summary(
            language_code=report_language,
            metrics=metrics,
            positions=positions_payload,
            benchmark_ticker=benchmark_ticker,
        )

        backtest_id = uuid4().hex
        meta = {
            "schema_version": 2,
            "source_run": {
                "id": run_detail.run.id,
                "title": run_detail.run.title,
                "created_at": run_detail.run.created_at,
                "finished_at": run_detail.run.finished_at,
                "report_mode": run_detail.run.report_mode,
            },
            "benchmark_ticker": benchmark_ticker,
            "entry_rule": entry_rule,
            "backtest_kind": mode,
            "research_mode": research_mode,
            "as_of_date": research_context.get("as_of_date"),
            "warning_flags": run_warnings,
            "allocation_rule": "allocation_plan_or_equal_weight",
            "return_basis": backtest_assumptions["return_basis"],
            "assumptions": backtest_assumptions,
            "currency": currency,
            "attribution_summary": attribution_summary,
            "requested_count": requested_count,
            "coverage_count": len(positions_payload),
            "dropped_tickers": dropped_tickers,
            "data_route_used": list(dict.fromkeys(self._last_price_routes.values())),
            "degraded_modules": self._last_degraded_modules,
            "cache_age_minutes": round(self._last_cache_age_minutes, 2) if self._last_cache_age_minutes is not None else None,
        }
        if missing_tickers:
            meta["warning_flags"] = list(dict.fromkeys([*meta["warning_flags"], f"dropped_tickers_no_price:{','.join(missing_tickers)}"]))

        self.repository.replace_backtest(
            backtest_id=backtest_id,
            source_run_id=payload.source_run_id,
            title=(
                f"{run_detail.run.title} - Backtest Replay"
                if mode == "replay"
                else f"{run_detail.run.title} - Historical Performance Reference"
            ),
            status="completed",
            entry_date=entry_date.isoformat(),
            end_date=effective_end_date.isoformat(),
            metrics=metrics,
            positions=positions_payload,
            points=points,
            meta=meta,
            benchmark_ticker=benchmark_ticker,
        )
        return self.get_backtest_or_404(backtest_id)

    def _resolve_capital_and_currency(self, result: dict[str, Any]) -> tuple[float, str]:
        parsed_intent = result.get("parsed_intent") or {}
        portfolio_sizing = parsed_intent.get("portfolio_sizing") or {}
        capital_amount = portfolio_sizing.get("capital_amount")
        currency = str(portfolio_sizing.get("currency") or "USD").upper()
        try:
            capital = float(capital_amount)
        except (TypeError, ValueError):
            capital = 10000.0
        if capital <= 0:
            capital = 10000.0
        return capital, currency

    def _resolve_signal_date(self, timestamp: str) -> date:
        text = (timestamp or "").replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return date.today() - timedelta(days=30)

    def _build_positions_seed(
        self,
        *,
        executive: dict[str, Any],
        scoreboard: list[dict[str, Any]],
        report_briefing: dict[str, Any],
    ) -> list[dict[str, Any]]:
        max_results = 5
        try:
            summary = report_briefing.get("screening_summary") or report_briefing.get("meta") or {}
            candidate_value = summary.get("requested_max_results") or summary.get("requestedMaxResults")
            if candidate_value is not None:
                max_results = max(1, min(int(candidate_value), 5))
        except (TypeError, ValueError):
            max_results = 5
        allocation_plan = executive.get("allocation_plan") or []
        positions: list[dict[str, Any]] = []
        if isinstance(allocation_plan, list):
            for item in allocation_plan:
                if not isinstance(item, dict):
                    continue
                ticker = str(item.get("ticker") or "").upper().strip()
                if not ticker:
                    continue
                positions.append(
                    {
                        "ticker": ticker,
                        "weight": float(item.get("weight") or 0),
                        "verdict": str(item.get("verdict") or ""),
                    }
                )
        positions = positions[:max_results]

        if not positions:
            tickers = [
                str(item.get("ticker") or "").upper().strip()
                for item in scoreboard
                if isinstance(item, dict) and str(item.get("ticker") or "").strip()
            ]
            tickers = tickers[:max_results]
            if not tickers:
                verdicts = report_briefing.get("verdicts") or []
                tickers = [
                    str(item.get("ticker") or "").upper().strip()
                    for item in verdicts
                    if isinstance(item, dict)
                    and str(item.get("ticker") or "").strip()
                    and not bool(item.get("veto"))
                ]
                tickers = tickers[:max_results]
            if not tickers:
                price_action = report_briefing.get("price_action") or []
                tickers = [
                    str(item.get("ticker") or "").upper().strip()
                    for item in price_action
                    if isinstance(item, dict) and str(item.get("ticker") or "").strip()
                ]
                tickers = tickers[:max_results]
            if not tickers:
                return []
            weight = 100 / len(tickers)
            positions = [{"ticker": ticker, "weight": weight, "verdict": "Equal weight"} for ticker in tickers]

        total_weight = sum(item["weight"] for item in positions if item["weight"] > 0)
        if total_weight <= 0:
            equal_weight = 100 / len(positions)
            for item in positions:
                item["weight"] = equal_weight
        else:
            for item in positions:
                item["weight"] = item["weight"] / total_weight * 100
        return positions

    def _load_price_frames(
        self,
        tickers: list[str],
        start_date: date,
        end_date: date,
    ) -> tuple[dict[str, pd.DataFrame], list[str]]:
        normalized = [ticker.upper().strip() for ticker in tickers if ticker.strip()]
        if not normalized:
            return {}, []

        cache_key = self._price_cache_key(start_date, end_date)
        cache_ages: list[float] = []
        frames: dict[str, pd.DataFrame] = {}
        missing_tickers: list[str] = []

        alpaca_frames = self._load_alpaca_frames_bulk(normalized, start_date, end_date)
        for ticker, frame in alpaca_frames.items():
            frames[ticker] = frame.sort_index()
            self._last_price_routes[ticker] = "alpaca_iex"
            self._store_cached_price_frame(ticker, cache_key, frames[ticker])
        if not alpaca_frames:
            self._last_degraded_modules.append("alpaca_unavailable")

        pending_after_alpaca = [ticker for ticker in normalized if ticker not in frames]
        longbridge_frames = self._load_longbridge_frames_bulk(pending_after_alpaca, start_date, end_date)
        for ticker, frame in longbridge_frames.items():
            if frame.empty:
                continue
            frames[ticker] = frame.sort_index()
            self._last_price_routes[ticker] = "longbridge_daily"
            self._store_cached_price_frame(ticker, cache_key, frames[ticker])

        pending_after_longbridge = [ticker for ticker in pending_after_alpaca if ticker not in frames]
        yfinance_bulk_frames = self._load_yfinance_frames_bulk(pending_after_longbridge, start_date, end_date)
        for ticker, frame in yfinance_bulk_frames.items():
            if frame.empty:
                continue
            frames[ticker] = frame.sort_index()
            self._last_price_routes[ticker] = "yfinance_bulk"
            self._store_cached_price_frame(ticker, cache_key, frames[ticker])

        for ticker in normalized:
            frame = frames.get(ticker, pd.DataFrame())
            if frame.empty:
                frame = self._load_longbridge_frame(ticker, start_date, end_date)
                if not frame.empty:
                    self._last_price_routes[ticker] = "longbridge_single"
            if frame.empty:
                frame = self._load_yfinance_frame(ticker, start_date, end_date)
                if not frame.empty:
                    self._last_price_routes[ticker] = "yfinance_single"
            if frame.empty:
                frame = self._load_alpha_vantage_frame(ticker, start_date, end_date)
                if not frame.empty:
                    self._last_price_routes[ticker] = "alpha_vantage"
            if frame.empty:
                frame, cache_age = self._load_cached_price_frame(ticker, cache_key)
                if not frame.empty:
                    self._last_price_routes[ticker] = "cache_6h"
                if cache_age is not None:
                    cache_ages.append(cache_age)
            if frame.empty:
                missing_tickers.append(ticker)
                frames.pop(ticker, None)
                continue
            frames[ticker] = frame.sort_index()
            if self._last_price_routes.get(ticker) != "cache_6h":
                self._store_cached_price_frame(ticker, cache_key, frames[ticker])

        if not self.settings.alpaca_configured:
            self._last_degraded_modules.append("alpaca_not_configured")
        if not self.settings.longbridge_configured:
            self._last_degraded_modules.append("longbridge_not_configured")
        if self._recent_yfinance_errors:
            self._last_degraded_modules.append("yfinance_rate_limited_or_unavailable")
        if any(route.startswith("longbridge") for route in self._last_price_routes.values()):
            self._last_degraded_modules.append("longbridge_fallback")
        if any(route == "alpha_vantage" for route in self._last_price_routes.values()):
            self._last_degraded_modules.append("alpha_vantage_fallback")
        if any(route == "cache_6h" for route in self._last_price_routes.values()):
            self._last_degraded_modules.append("cache_fallback_used")
        if missing_tickers:
            self._last_degraded_modules.append("partial_price_missing")
        self._last_degraded_modules = list(dict.fromkeys(self._last_degraded_modules))
        if cache_ages:
            self._last_cache_age_minutes = round(max(cache_ages), 2)

        return frames, missing_tickers

    def _resolve_benchmark_frame(
        self,
        *,
        start_date: date,
        end_date: date,
        price_frames: dict[str, pd.DataFrame],
    ) -> tuple[str, pd.DataFrame | None, str | None]:
        benchmark_alpaca = self._load_alpaca_frames_bulk(BENCHMARK_CANDIDATES, start_date, end_date)
        benchmark_longbridge = self._load_longbridge_frames_bulk(BENCHMARK_CANDIDATES, start_date, end_date)
        cache_key = self._price_cache_key(start_date, end_date)
        for candidate in BENCHMARK_CANDIDATES:
            frame = price_frames.get(candidate, pd.DataFrame())
            if frame.empty:
                frame = benchmark_alpaca.get(candidate, pd.DataFrame())
                if not frame.empty:
                    self._last_price_routes[candidate] = "alpaca_iex_benchmark"
            if frame.empty:
                frame = benchmark_longbridge.get(candidate, pd.DataFrame())
                if not frame.empty:
                    self._last_price_routes[candidate] = "longbridge_benchmark"
            if frame.empty:
                frame = self._load_yfinance_frame(candidate, start_date, end_date)
                if not frame.empty:
                    self._last_price_routes[candidate] = "yfinance_benchmark"
            if frame.empty:
                frame = self._load_alpha_vantage_frame(candidate, start_date, end_date)
                if not frame.empty:
                    self._last_price_routes[candidate] = "alpha_vantage_benchmark"
            if frame.empty:
                frame, cache_age = self._load_cached_price_frame(candidate, cache_key)
                if not frame.empty:
                    self._last_price_routes[candidate] = "cache_6h_benchmark"
                if cache_age is not None:
                    self._last_cache_age_minutes = (
                        cache_age
                        if self._last_cache_age_minutes is None
                        else max(self._last_cache_age_minutes, cache_age)
                    )
            if frame.empty and candidate == BENCHMARK_TICKER:
                frame = self._load_stooq_frame("SPY.US", start_date, end_date)
                if not frame.empty:
                    self._last_price_routes[candidate] = "stooq_benchmark"
            if frame.empty:
                continue
            price_frames[candidate] = frame.sort_index()
            self._store_cached_price_frame(candidate, cache_key, price_frames[candidate])
            if candidate != BENCHMARK_TICKER:
                return candidate, price_frames[candidate], f"benchmark_fallback:{candidate}"
            return candidate, price_frames[candidate], None
        return "CASH_PROXY", None, "benchmark_unavailable_fallback:cash_proxy"

    def _load_alpaca_frames_bulk(self, tickers: list[str], start_date: date, end_date: date) -> dict[str, pd.DataFrame]:
        if not self.settings.alpaca_configured:
            return {}
        normalized = [ticker.upper().strip() for ticker in tickers if ticker.strip()]
        if not normalized:
            return {}
        try:
            bars_map = fetch_alpaca_daily_bars(
                self.settings,
                normalized,
                start_date - timedelta(days=7),
                end_date + timedelta(days=3),
                feed="iex",
            )
        except Exception:
            return {}

        frames: dict[str, pd.DataFrame] = {}
        for ticker in normalized:
            records = bars_map.get(ticker) or []
            frame = self._frame_from_price_records(records)
            if frame.empty:
                continue
            frames[ticker] = frame
        return frames

    def _load_longbridge_frames_bulk(self, tickers: list[str], start_date: date, end_date: date) -> dict[str, pd.DataFrame]:
        """批量读取长桥日线数据并转成 DataFrame。"""
        if not self.settings.longbridge_configured:
            return {}
        normalized = [ticker.upper().strip() for ticker in tickers if ticker.strip()]
        if not normalized:
            return {}
        try:
            bars_map = fetch_longbridge_daily_bars(
                self.settings,
                normalized,
                start_date - timedelta(days=7),
                end_date + timedelta(days=3),
            )
        except Exception:
            return {}

        frames: dict[str, pd.DataFrame] = {}
        for ticker in normalized:
            records = bars_map.get(ticker) or []
            frame = self._frame_from_price_records(records)
            if frame.empty:
                continue
            frames[ticker] = frame
        return frames

    def _load_longbridge_frame(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        """单票读取长桥日线数据，失败时返回空表。"""
        frames = self._load_longbridge_frames_bulk([ticker], start_date, end_date)
        symbol = str(ticker or "").upper().strip()
        return frames.get(symbol, pd.DataFrame())

    def _load_yfinance_frames_bulk(self, tickers: list[str], start_date: date, end_date: date) -> dict[str, pd.DataFrame]:
        normalized = [ticker.upper().strip() for ticker in tickers if ticker.strip()]
        if not normalized:
            return {}
        frames: dict[str, pd.DataFrame] = {}
        batch_size = 5
        for offset in range(0, len(normalized), batch_size):
            batch = normalized[offset:offset + batch_size]
            history = pd.DataFrame()
            for attempt in range(2):
                try:
                    history = run_yfinance_call(
                        self.settings,
                        operation=f"backtest_bulk_download:{len(batch)}",
                        call=lambda batch=batch: yf.download(
                            tickers=" ".join(batch),
                            start=(start_date - timedelta(days=7)).isoformat(),
                            end=(end_date + timedelta(days=3)).isoformat(),
                            auto_adjust=False,
                            actions=False,
                            progress=False,
                            group_by="ticker",
                            threads=False,
                        ),
                    )
                    if history is not None and not history.empty:
                        break
                except Exception as exc:
                    self._remember_yfinance_error(exc)
                    history = pd.DataFrame()
                if attempt == 0:
                    time.sleep(0.8)
            if history is None or history.empty:
                continue

            if len(batch) == 1:
                frame = history[["Open", "Close"]].dropna().copy()
                frame.index = pd.to_datetime(frame.index).tz_localize(None)
                if not frame.empty:
                    frames[batch[0]] = frame
            else:
                for ticker in batch:
                    try:
                        if ticker not in history.columns.get_level_values(0):
                            continue
                        frame = history[ticker][["Open", "Close"]].dropna().copy()
                        frame.index = pd.to_datetime(frame.index).tz_localize(None)
                        if frame.empty:
                            continue
                        frames[ticker] = frame
                    except Exception:
                        continue

            if offset + batch_size < len(normalized):
                time.sleep(0.35)
        return frames

    def _load_yfinance_frame(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        try:
            frame = run_yfinance_call(
                self.settings,
                operation=f"backtest_single_history:{ticker}",
                call=lambda: yf.Ticker(ticker).history(
                    start=(start_date - timedelta(days=7)).isoformat(),
                    end=(end_date + timedelta(days=3)).isoformat(),
                    auto_adjust=False,
                    actions=False,
                ),
            )
        except Exception as exc:
            self._remember_yfinance_error(exc)
            return pd.DataFrame()
        if frame.empty:
            return pd.DataFrame()
        trimmed = frame[["Open", "Close"]].dropna().copy()
        trimmed.index = pd.to_datetime(trimmed.index).tz_localize(None)
        return trimmed

    def _load_alpha_vantage_frame(self, ticker: str, start_date: date, end_date: date) -> pd.DataFrame:
        api_key = self.settings.alpha_vantage_api_key
        if not api_key:
            return pd.DataFrame()
        self._respect_alpha_rate_limit()
        try:
            response = requests.get(
                ALPHA_VANTAGE_URL,
                params={
                    "function": "TIME_SERIES_DAILY",
                    "symbol": ticker,
                    "outputsize": "compact",
                    "apikey": api_key,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            return pd.DataFrame()
        series = payload.get("Time Series (Daily)") or {}
        records: list[dict[str, Any]] = []
        for point_date, raw in series.items():
            try:
                parsed_date = datetime.strptime(point_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            if parsed_date < start_date - timedelta(days=7) or parsed_date > end_date + timedelta(days=3):
                continue
            try:
                records.append(
                    {
                        "Date": parsed_date,
                        "Open": float(raw["1. open"]),
                        "Close": float(raw["4. close"]),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        if not records:
            return pd.DataFrame()
        frame = pd.DataFrame.from_records(records).set_index("Date").sort_index()
        frame.index = pd.to_datetime(frame.index)
        return frame

    def _price_cache_key(self, start_date: date, end_date: date) -> str:
        return f"backtest_price:{start_date.isoformat()}:{end_date.isoformat()}"

    def _load_cached_price_frame(self, ticker: str, cache_key: str) -> tuple[pd.DataFrame, float | None]:
        payload = _load_cached_snapshot(
            self.settings,
            ticker,
            cache_key,
            ttl_minutes=360,
        )
        if not isinstance(payload, dict):
            return pd.DataFrame(), None
        records = payload.get("records")
        if not isinstance(records, list):
            return pd.DataFrame(), None

        frame = self._frame_from_price_records(records)
        if frame.empty:
            return pd.DataFrame(), None

        cached_at_text = str(payload.get("cached_at") or "").strip().replace("Z", "+00:00")
        cache_age: float | None = None
        if cached_at_text:
            try:
                cached_at = datetime.fromisoformat(cached_at_text).replace(tzinfo=None)
                cache_age = max((datetime.utcnow() - cached_at).total_seconds() / 60, 0.0)
            except ValueError:
                cache_age = None
        return frame, cache_age

    def _store_cached_price_frame(self, ticker: str, cache_key: str, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        rows = frame.reset_index()
        date_column = rows.columns[0]
        records: list[dict[str, Any]] = []
        for _, row in rows.iterrows():
            try:
                point_date = pd.Timestamp(row[date_column]).date().isoformat()
                open_price = float(row["Open"])
                close_price = float(row["Close"])
            except (TypeError, ValueError, KeyError):
                continue
            records.append({"Date": point_date, "Open": open_price, "Close": close_price})
        if not records:
            return
        _store_cached_snapshot(
            self.settings,
            ticker,
            cache_key,
            {
                "records": records,
                "cached_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            },
        )

    def _frame_from_price_records(self, records: list[dict[str, Any]]) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                continue
            raw_date = record.get("Date") or record.get("date")
            try:
                point_date = pd.Timestamp(raw_date).date()
            except Exception:
                continue
            try:
                open_price = float(record.get("Open", record.get("open")))
                close_price = float(record.get("Close", record.get("close")))
            except (TypeError, ValueError):
                continue
            rows.append({"Date": point_date, "Open": open_price, "Close": close_price})
        if not rows:
            return pd.DataFrame()
        frame = pd.DataFrame.from_records(rows).drop_duplicates(subset=["Date"], keep="last")
        frame = frame.set_index("Date").sort_index()
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        return frame

    def _load_stooq_frame(self, symbol: str, start_date: date, end_date: date) -> pd.DataFrame:
        try:
            response = requests.get(
                STOOQ_DAILY_URL,
                params={"s": symbol.lower(), "i": "d"},
                timeout=15,
            )
            response.raise_for_status()
        except Exception:
            return pd.DataFrame()
        text = response.text.strip()
        if not text or "No data" in text:
            return pd.DataFrame()
        try:
            raw = pd.read_csv(io.StringIO(text))
        except Exception:
            return pd.DataFrame()
        required = {"Date", "Open", "Close"}
        if raw.empty or not required.issubset(set(raw.columns)):
            return pd.DataFrame()
        try:
            raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
            raw["Open"] = pd.to_numeric(raw["Open"], errors="coerce")
            raw["Close"] = pd.to_numeric(raw["Close"], errors="coerce")
            raw = raw.dropna(subset=["Date", "Open", "Close"])
        except Exception:
            return pd.DataFrame()
        if raw.empty:
            return pd.DataFrame()
        lower = pd.Timestamp(start_date - timedelta(days=7))
        upper = pd.Timestamp(end_date + timedelta(days=3))
        raw = raw[(raw["Date"] >= lower) & (raw["Date"] <= upper)]
        if raw.empty:
            return pd.DataFrame()
        frame = raw.set_index("Date")[["Open", "Close"]].sort_index()
        frame.index = pd.to_datetime(frame.index).tz_localize(None)
        return frame

    def _respect_alpha_rate_limit(self) -> None:
        if not self.settings.alpha_vantage_api_key:
            return
        elapsed = time.monotonic() - self._last_alpha_request_at
        if elapsed < 1.1:
            time.sleep(1.1 - elapsed)
        self._last_alpha_request_at = time.monotonic()

    def _remember_yfinance_error(self, exc: Exception) -> None:
        """记录最近的 yfinance 异常，供回测失败提示使用。"""
        self._recent_yfinance_errors.append(exc)
        if len(self._recent_yfinance_errors) > 8:
            self._recent_yfinance_errors = self._recent_yfinance_errors[-8:]

    def _build_backtest_fetch_failure_hint(self) -> str:
        """根据最近异常生成可读的失败原因。"""
        hints: list[str] = []
        if not self.settings.alpaca_configured:
            hints.append("Alpaca is not configured.")
        if not self.settings.alpha_vantage_api_key:
            hints.append("Alpha Vantage API key is missing.")
        if not self._recent_yfinance_errors:
            if hints:
                return " ".join(hints) + " Yahoo returned no usable data."
            return "Yahoo returned no usable data."

        reason_codes = {
            classify_yfinance_exception(error)
            for error in self._recent_yfinance_errors
        }
        if "yahoo_rate_limited" in reason_codes:
            hints.append("Yahoo rate-limited requests (429).")
        if "proxy_connection_failed" in reason_codes:
            hints.append("Proxy route failed before Yahoo returned data.")
        if "proxy_not_configured" in reason_codes:
            hints.append("Proxy mode is enabled but MARKET_PROXY_URL is missing.")
        if hints:
            return " ".join(hints) + " "
        first_error = self._recent_yfinance_errors[-1]
        return f"{yfinance_failure_message(first_error)} "

    def _find_common_dates(
        self,
        price_frames: dict[str, pd.DataFrame],
        start_date: date,
        end_date: date,
        *,
        include_start: bool = False,
        benchmark_frame: pd.DataFrame | None = None,
    ) -> list[date]:
        date_sets: list[set[date]] = []
        for frame in price_frames.values():
            dates = {
                item.date()
                for item in pd.to_datetime(frame.index)
                if (item.date() >= start_date if include_start else item.date() > start_date) and item.date() <= end_date
            }
            if not dates:
                return []
            date_sets.append(dates)
        if benchmark_frame is not None:
            benchmark_dates = {
                item.date()
                for item in pd.to_datetime(benchmark_frame.index)
                if (item.date() >= start_date if include_start else item.date() > start_date) and item.date() <= end_date
            }
            if not benchmark_dates:
                return []
            date_sets.append(benchmark_dates)
        if not date_sets:
            return []
        common_dates = sorted(set.intersection(*date_sets))
        if common_dates:
            return common_dates

        latest_common = sorted(
            set.intersection(*[{item.date() for item in pd.to_datetime(frame.index) if item.date() <= end_date} for frame in price_frames.values()])
        )
        if include_start:
            return [point for point in latest_common if point >= start_date]
        return [point for point in latest_common if point > start_date]

    def _materialize_portfolio_positions(
        self,
        *,
        positions_seed: list[dict[str, Any]],
        capital_amount: float,
        entry_date: date,
        price_frames: dict[str, pd.DataFrame],
        assumptions: dict[str, Any] | None = None,
    ) -> list[PortfolioPosition]:
        """把权重转换成持仓，并按需要计入保守交易口径。"""
        assumptions = assumptions or {}
        transaction_cost_bps = max(float(assumptions.get("transaction_cost_bps") or 0.0), 0.0)
        slippage_bps = max(float(assumptions.get("slippage_bps") or 0.0), 0.0)
        positions: list[PortfolioPosition] = []
        for item in positions_seed:
            ticker = item["ticker"]
            frame = price_frames[ticker]
            raw_entry_price = float(frame.loc[pd.Timestamp(entry_date), "Open"])
            entry_price = raw_entry_price * (1 + slippage_bps / 10000)
            gross_amount = capital_amount * (item["weight"] / 100)
            invested_amount = max(gross_amount * (1 - transaction_cost_bps / 10000), 0.0)
            shares = invested_amount / entry_price if entry_price > 0 else 0
            positions.append(
                PortfolioPosition(
                    ticker=ticker,
                    weight=round(float(item["weight"]), 4),
                    verdict=item["verdict"] or "Portfolio position",
                    entry_price=entry_price,
                    shares=shares,
                    invested_amount=invested_amount,
                )
            )
        return positions

    @staticmethod
    def _build_backtest_assumptions() -> dict[str, Any]:
        """生成回测 V1.5 的默认保守口径。"""
        return {
            "transaction_cost_bps": 10,
            "slippage_bps": 5,
            "dividend_treatment": "excluded_unless_source_provides_total_return",
            "dividend_included": False,
            "rebalance": "none_buy_and_hold",
            "benchmark_costs_applied": False,
            "return_basis": "price_return_after_entry_costs_vs_benchmark_price_return",
        }

    def _build_backtest_points(
        self,
        *,
        positions: list[PortfolioPosition],
        price_frames: dict[str, pd.DataFrame],
        benchmark_frame: pd.DataFrame | None,
        common_dates: list[date],
        capital_amount: float,
        benchmark_entry_price: float | None,
    ) -> tuple[list[dict[str, Any]], float]:
        benchmark_shares = (
            capital_amount / benchmark_entry_price
            if benchmark_frame is not None and benchmark_entry_price is not None and benchmark_entry_price > 0
            else 0
        )
        points: list[dict[str, Any]] = []
        for point_date in common_dates:
            point_ts = pd.Timestamp(point_date)
            portfolio_value = sum(
                position.shares * float(price_frames[position.ticker].loc[point_ts, "Close"])
                for position in positions
            )
            if benchmark_frame is not None and benchmark_shares > 0:
                benchmark_value = benchmark_shares * float(benchmark_frame.loc[point_ts, "Close"])
            else:
                benchmark_value = capital_amount
            points.append(
                {
                    "point_date": point_date.isoformat(),
                    "portfolio_value": round(portfolio_value, 2),
                    "benchmark_value": round(benchmark_value, 2),
                    "portfolio_return_pct": round((portfolio_value / capital_amount - 1) * 100, 2),
                    "benchmark_return_pct": round((benchmark_value / capital_amount - 1) * 100, 2),
                }
            )
        return points, points[-1]["benchmark_value"]

    def _build_position_payloads(
        self,
        *,
        positions: list[PortfolioPosition],
        price_frames: dict[str, pd.DataFrame],
        end_date: date,
        capital_amount: float,
        entry_date: date,
        common_dates: list[date],
    ) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for position in positions:
            latest_price = float(price_frames[position.ticker].loc[pd.Timestamp(end_date), "Close"])
            current_value = position.shares * latest_price
            return_pct = (current_value / position.invested_amount - 1) * 100 if position.invested_amount else 0.0
            contribution_pct = (current_value - position.invested_amount) / capital_amount * 100 if capital_amount else 0.0
            series: list[dict[str, Any]] = []
            previous_close: float | None = None
            for point_date in common_dates:
                close_price = float(price_frames[position.ticker].loc[pd.Timestamp(point_date), "Close"])
                position_value = position.shares * close_price
                cumulative_return_pct = (position_value / position.invested_amount - 1) * 100 if position.invested_amount else 0.0
                contribution_point = (position_value - position.invested_amount) / capital_amount * 100 if capital_amount else 0.0
                daily_return_pct = 0.0
                if previous_close and previous_close > 0:
                    daily_return_pct = (close_price / previous_close - 1) * 100
                previous_close = close_price
                series.append(
                    {
                        "point_date": point_date.isoformat(),
                        "close_price": round(close_price, 4),
                        "daily_return_pct": round(daily_return_pct, 4),
                        "cumulative_return_pct": round(cumulative_return_pct, 4),
                        "contribution_pct": round(contribution_point, 4),
                    }
                )
            payloads.append(
                {
                    "ticker": position.ticker,
                    "weight": round(position.weight, 2),
                    "verdict": position.verdict,
                    "entry_date": entry_date.isoformat(),
                    "entry_price": round(position.entry_price, 4),
                    "latest_price": round(latest_price, 4),
                    "shares": round(position.shares, 6),
                    "invested_amount": round(position.invested_amount, 2),
                    "current_value": round(current_value, 2),
                    "return_pct": round(return_pct, 2),
                    "contribution_pct": round(contribution_pct, 2),
                    "timeseries": series,
                }
            )
        return payloads

    def _build_attribution_summary(
        self,
        *,
        language_code: str,
        metrics: dict[str, Any],
        positions: list[dict[str, Any]],
        benchmark_ticker: str,
    ) -> list[str]:
        """生成回测结果解释，帮助用户理解为何跑赢或跑输。"""
        total_return = float(metrics.get("total_return_pct") or 0.0)
        benchmark_return = float(metrics.get("benchmark_return_pct") or 0.0)
        excess = float(metrics.get("excess_return_pct") or 0.0)
        drawdown = metrics.get("max_drawdown_pct")
        top_contributor = None
        if positions:
            top_contributor = max(positions, key=lambda item: float(item.get("contribution_pct") or 0.0))
        if language_code == "zh":
            lines = [
                (
                    f"组合区间收益 {total_return:.2f}%，基准 {benchmark_ticker} 为 {benchmark_return:.2f}%，"
                    f"超额收益 {excess:.2f}%。"
                )
            ]
            if top_contributor:
                lines.append(
                    f"主要贡献来自 {top_contributor.get('ticker')}，贡献约 {float(top_contributor.get('contribution_pct') or 0.0):.2f}% 。"
                )
            if isinstance(drawdown, (int, float)):
                lines.append(f"区间最大回撤约 {float(drawdown):.2f}%，建议结合回撤承受能力评估执行节奏。")
            return lines
        lines = [
            (
                f"Portfolio return was {total_return:.2f}% versus {benchmark_ticker} at {benchmark_return:.2f}%, "
                f"with excess return of {excess:.2f}%."
            )
        ]
        if top_contributor:
            lines.append(
                f"Top contribution came from {top_contributor.get('ticker')} at about {float(top_contributor.get('contribution_pct') or 0.0):.2f}%."
            )
        if isinstance(drawdown, (int, float)):
            lines.append(f"Max drawdown was around {float(drawdown):.2f}%, which should be matched against risk tolerance.")
        return lines

    @staticmethod
    def _annualized_return_pct(
        *,
        initial_value: float,
        final_value: float,
        start_date: date,
        end_date: date,
    ) -> float | None:
        days = max((end_date - start_date).days, 0)
        if initial_value <= 0 or final_value <= 0 or days < 30:
            return None
        annualized = (final_value / initial_value) ** (365 / days) - 1
        return round(annualized * 100, 2)

    @staticmethod
    def _max_drawdown_pct(points: list[dict[str, Any]]) -> float | None:
        if not points:
            return None
        peak = points[0]["portfolio_value"]
        max_drawdown = 0.0
        for point in points:
            value = point["portfolio_value"]
            peak = max(peak, value)
            if peak <= 0:
                continue
            drawdown = (value / peak - 1) * 100
            max_drawdown = min(max_drawdown, drawdown)
        return round(max_drawdown, 2)
