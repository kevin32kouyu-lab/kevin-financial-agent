import { useEffect, useMemo, useState } from "react";
import { formatCurrency, formatDate, formatPercent } from "../lib/format";
import type { Locale } from "../lib/types";
import type { LocalePack } from "../lib/i18n";
import type { BacktestDetail, BacktestMode } from "../lib/types";

interface BacktestPanelProps {
  locale: Locale;
  copy: LocalePack;
  activeRunId: string | null;
  runStatus?: string;
  backtest: BacktestDetail | null;
  mode: BacktestMode;
  endDate: string;
  entryDate?: string;
  loading: boolean;
  creating: boolean;
  onEndDateChange: (value: string) => void;
  onEntryDateChange?: (value: string) => void;
  onRunBacktest: (runId?: string, mode?: BacktestMode, entryDate?: string | null, endDate?: string | null) => void;
}

type BacktestRange = "1M" | "3M" | "6M" | "1Y" | "YTD" | "ALL";

interface ChartTick {
  value: number;
  y: number;
}

interface DateTick {
  index: number;
  x: number;
  date: string;
}

interface ChartGeometry {
  path: string;
  ticks: ChartTick[];
  dateTicks: DateTick[];
  zeroY: number;
}

function createGeometry(
  values: number[],
  allSeriesValues: number[],
  dates: string[],
  width: number,
  height: number,
  padding = 28,
): ChartGeometry {
  if (!values.length || !allSeriesValues.length || values.length !== dates.length) {
    return { path: "", ticks: [], dateTicks: [], zeroY: height - padding };
  }

  const rawMin = Math.min(...allSeriesValues, 0);
  const rawMax = Math.max(...allSeriesValues, 0);
  const range = Math.max(rawMax - rawMin, 1);
  const min = rawMin - range * 0.08;
  const max = rawMax + range * 0.08;
  const xStep = values.length > 1 ? (width - padding * 2) / (values.length - 1) : 0;
  const scaleY = (value: number) => height - padding - ((value - min) / (max - min)) * (height - padding * 2);

  const path = values
    .map((value, index) => {
      const x = padding + index * xStep;
      const y = scaleY(value);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");

  const tickCount = 5;
  const ticks: ChartTick[] = Array.from({ length: tickCount }, (_, idx) => {
    const value = min + ((max - min) * idx) / (tickCount - 1);
    return { value, y: scaleY(value) };
  });

  const dateTickCount = Math.min(6, dates.length);
  const dateTicks: DateTick[] = Array.from({ length: dateTickCount }, (_, idx) => {
    const ratio = dateTickCount === 1 ? 0 : idx / (dateTickCount - 1);
    const pointIndex = Math.round((dates.length - 1) * ratio);
    return {
      index: pointIndex,
      x: padding + pointIndex * xStep,
      date: dates[pointIndex] || "",
    };
  });

  return {
    path,
    ticks,
    dateTicks,
    zeroY: scaleY(0),
  };
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function numberValue(value: unknown): number | null {
  const next = Number(value);
  return Number.isFinite(next) ? next : null;
}

export function BacktestPanel({
  locale,
  copy,
  activeRunId,
  runStatus,
  backtest,
  mode,
  endDate,
  entryDate,
  loading,
  creating,
  onEndDateChange,
  onEntryDateChange,
  onRunBacktest,
}: BacktestPanelProps) {
  const [backtestRange, setBacktestRange] = useState<BacktestRange>("ALL");
  const [activeTicker, setActiveTicker] = useState<string>("");
  const summary = backtest?.summary;
  const metrics = summary?.metrics;
  const points = backtest?.points || [];
  const positions = backtest?.positions || [];
  const attributionSummary = Array.isArray(backtest?.meta?.attribution_summary)
    ? (backtest?.meta?.attribution_summary as Array<unknown>).map((item) => String(item || "")).filter(Boolean)
    : [];
  const assumptions = asRecord(backtest?.meta?.assumptions);
  const dividendCoverage = asRecord(backtest?.meta?.dividend_coverage);
  const taxSummary = asRecord(backtest?.meta?.tax_summary);
  const dataLimitations = Array.isArray(backtest?.meta?.data_limitations)
    ? (backtest?.meta?.data_limitations as Array<unknown>).map((item) => String(item || "")).filter(Boolean)
    : [];
  const transactionCostBps = numberValue(assumptions?.transaction_cost_bps);
  const slippageBps = numberValue(assumptions?.slippage_bps);
  const dividendIncluded = dividendCoverage?.dividend_included === true || assumptions?.dividend_included === true;
  const assumptionRows = assumptions
    ? [
        locale === "zh"
          ? `交易成本：${transactionCostBps ?? 0} bps，滑点：${slippageBps ?? 0} bps。`
          : `Transaction cost: ${transactionCostBps ?? 0} bps, slippage: ${slippageBps ?? 0} bps.`,
        locale === "zh"
          ? `分红：${dividendIncluded ? "已纳入" : "未纳入"}；模式：${String(assumptions.dividend_mode || "none")}。`
          : `Dividends: ${dividendIncluded ? "included" : "not included"}; mode: ${String(assumptions.dividend_mode || "none")}.`,
        locale === "zh"
          ? `税费：${String(assumptions.tax_mode || "none")}，税额估算 ${String(taxSummary?.tax_amount ?? 0)}。`
          : `Tax: ${String(assumptions.tax_mode || "none")}, estimated tax ${String(taxSummary?.tax_amount ?? 0)}.`,
        locale === "zh"
          ? `再平衡：${String(assumptions.rebalance || "none")}。`
          : `Rebalance: ${String(assumptions.rebalance || "none")}.`,
      ]
    : [];
  const rangeLabels = {
    "1M": copy.backtest.ranges.m1,
    "3M": copy.backtest.ranges.m3,
    "6M": copy.backtest.ranges.m6,
    "1Y": copy.backtest.ranges.y1,
    YTD: copy.backtest.ranges.ytd,
    ALL: copy.backtest.ranges.all,
  };

  useEffect(() => {
    if (!positions.length) {
      setActiveTicker("");
      return;
    }
    if (!activeTicker || !positions.some((item) => item.ticker === activeTicker)) {
      setActiveTicker(positions[0].ticker);
    }
  }, [positions, activeTicker]);

  const chartWidth = 760;
  const chartHeight = 260;
  const rangeStartDate = useMemo(() => {
    const latestPointDateText = points.length ? points[points.length - 1].point_date : null;
    if (!latestPointDateText) return null;
    const latestPointDate = new Date(latestPointDateText);
    if (Number.isNaN(latestPointDate.getTime())) return null;
    if (backtestRange === "1M") {
      return new Date(latestPointDate.getFullYear(), latestPointDate.getMonth() - 1, latestPointDate.getDate());
    }
    if (backtestRange === "3M") {
      return new Date(latestPointDate.getFullYear(), latestPointDate.getMonth() - 3, latestPointDate.getDate());
    }
    if (backtestRange === "6M") {
      return new Date(latestPointDate.getFullYear(), latestPointDate.getMonth() - 6, latestPointDate.getDate());
    }
    if (backtestRange === "1Y") {
      return new Date(latestPointDate.getFullYear() - 1, latestPointDate.getMonth(), latestPointDate.getDate());
    }
    if (backtestRange === "YTD") {
      return new Date(latestPointDate.getFullYear(), 0, 1);
    }
    return null;
  }, [backtestRange, points]);

  const chartPoints = useMemo(() => {
    if (!rangeStartDate) return points;
    const filteredPoints = points.filter((item) => {
      const pointDate = new Date(item.point_date);
      return !Number.isNaN(pointDate.getTime()) && pointDate >= rangeStartDate;
    });
    return filteredPoints.length ? filteredPoints : points;
  }, [points, rangeStartDate]);

  const { portfolioGeometry, benchmarkGeometry } = useMemo(() => {
    const dates = chartPoints.map((item) => item.point_date);
    const portfolioValues = chartPoints.map((item) => item.portfolio_return_pct);
    const benchmarkValues = chartPoints.map((item) => item.benchmark_return_pct);
    const combinedValues = [...portfolioValues, ...benchmarkValues];
    return {
      portfolioGeometry: createGeometry(portfolioValues, combinedValues, dates, chartWidth, chartHeight),
      benchmarkGeometry: createGeometry(benchmarkValues, combinedValues, dates, chartWidth, chartHeight),
    };
  }, [chartPoints]);

  const selectedPosition = useMemo(
    () => positions.find((item) => item.ticker === activeTicker) || positions[0],
    [activeTicker, positions],
  );
  const selectedTimeseries = useMemo(() => {
    const selectedTimeseriesRaw = Array.isArray(selectedPosition?.timeseries) ? selectedPosition.timeseries : [];
    if (!rangeStartDate) return selectedTimeseriesRaw;
    return selectedTimeseriesRaw.filter((item) => {
      const pointDate = new Date(item.point_date);
      return !Number.isNaN(pointDate.getTime()) && pointDate >= rangeStartDate;
    });
  }, [rangeStartDate, selectedPosition]);
  const stockGeometry = useMemo(() => {
    const stockSeriesValues = selectedTimeseries.map((item) => item.cumulative_return_pct);
    const stockSeriesDates = selectedTimeseries.map((item) => item.point_date);
    return createGeometry(stockSeriesValues, stockSeriesValues, stockSeriesDates, chartWidth, chartHeight);
  }, [selectedTimeseries]);

  const heading = mode === "reference" ? copy.backtest.referenceTitle : copy.backtest.replayTitle;
  const description = mode === "reference" ? copy.backtest.referenceDescription : copy.backtest.replayDescription;
  const cautionText = mode === "reference" ? copy.backtest.referenceCaution : copy.backtest.replayCaution;

  const blockedReason =
    runStatus === "needs_clarification"
      ? copy.backtest.blockedNeedClarification
      : runStatus === "failed"
        ? copy.backtest.blockedFailed
        : runStatus === "cancelled"
          ? copy.backtest.blockedCancelled
          : copy.backtest.blockedNotCompleted;

  return (
    <section className="panel-surface report-surface anchor-target" id="report-backtest">
      <div className="section-head">
        <div>
          <p className="eyebrow">{heading}</p>
          <h2>{copy.backtest.panelTitle}</h2>
          <p className="section-note">{description}</p>
          <p className="section-note">{cautionText}</p>
        </div>
        <div className="button-row compact">
          {mode === "reference" ? (
            <label className="field compact-field">
              <span>{copy.backtest.entryDate}</span>
              <input
                type="date"
                value={entryDate || ""}
                onChange={(event) => onEntryDateChange?.(event.target.value)}
              />
            </label>
          ) : null}
          <label className="field compact-field">
            <span>{copy.backtest.endDate}</span>
            <input
              type="date"
              value={endDate}
              disabled={mode === "reference"}
              onChange={(event) => onEndDateChange(event.target.value)}
            />
          </label>
          <button
            type="button"
            className="primary-button compact-action"
            disabled={!activeRunId || runStatus !== "completed" || creating}
            onClick={() => onRunBacktest(activeRunId || undefined, mode, entryDate || null, endDate || null)}
          >
            {creating
              ? copy.backtest.running
              : mode === "reference"
                ? copy.backtest.rerunReference
                : copy.backtest.rerunReplay}
          </button>
        </div>
      </div>

      {!activeRunId ? (
        <div className="empty-state small">{copy.backtest.openCompletedFirst}</div>
      ) : null}
      {activeRunId && runStatus !== "completed" ? (
        <div className="empty-state small">
          {blockedReason}
        </div>
      ) : null}
      {activeRunId && runStatus === "completed" && loading ? (
        <div className="empty-state small">{copy.backtest.loading}</div>
      ) : null}
      {activeRunId && runStatus === "completed" && !loading && !summary ? (
        <div className="empty-state small">{copy.backtest.empty}</div>
      ) : null}

      {summary && metrics ? (
        <>
          <div className="summary-grid backtest-kpi-grid">
            <div className="mini-card">
              <span className="mini-label">{copy.backtest.portfolioReturn}</span>
              <strong>{formatPercent(metrics.total_return_pct)}</strong>
              <p>{formatCurrency(metrics.final_value, locale)}</p>
            </div>
            <div className="mini-card">
              <span className="mini-label">{copy.backtest.benchmark}</span>
              <strong>{formatPercent(metrics.benchmark_return_pct)}</strong>
              <p>{formatCurrency(metrics.benchmark_final_value, locale)}</p>
            </div>
            <div className="mini-card">
              <span className="mini-label">{copy.backtest.excess}</span>
              <strong>{formatPercent(metrics.excess_return_pct)}</strong>
              <p>{copy.backtest.versusBenchmark}</p>
            </div>
            <div className="mini-card">
              <span className="mini-label">{copy.backtest.maxDrawdown}</span>
              <strong>{formatPercent(metrics.max_drawdown_pct)}</strong>
              <p>
                {metrics.annualized_return_pct != null
                  ? `${copy.backtest.annualized} ${formatPercent(metrics.annualized_return_pct)}`
                  : copy.backtest.shortSample}
              </p>
            </div>
          </div>

          {attributionSummary.length ? (
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "回测复盘说明" : "Backtest interpretation"}</span>
              {attributionSummary.map((item, index) => (
                <p key={`${item}-${index}`}>{item}</p>
              ))}
            </div>
          ) : null}

          {assumptionRows.length ? (
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "本次回测口径" : "Backtest assumptions"}</span>
              {assumptionRows.map((item, index) => (
                <p key={`${item}-${index}`}>{item}</p>
              ))}
              {dataLimitations.length ? (
                <ul className="compact-list">
                  {dataLimitations.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <div className="mini-card">
            <span className="mini-label">{copy.backtest.requestedCoverage}</span>
            <p>
              {locale === "zh"
                ? `目标 ${summary.requested_count || positions.length} 只，实际覆盖 ${summary.coverage_count || positions.length} 只。`
                : `Requested ${summary.requested_count || positions.length}, covered ${summary.coverage_count || positions.length}.`}
            </p>
            {summary.dropped_tickers?.length ? (
              <p>
                <strong>{copy.backtest.droppedTickerReason}：</strong>
                {summary.dropped_tickers.map((item) => `${item.ticker}(${item.reason})`).join(locale === "zh" ? "，" : ", ")}
              </p>
            ) : (
              <p>{copy.backtest.noDroppedTickers}</p>
            )}
          </div>

          <div className="backtest-meta-row">
            <span className="chip neutral">
              {`${copy.backtest.entryDay} ${formatDate(summary.entry_date, locale)}`}
            </span>
            <span className="chip neutral">
              {`${copy.backtest.endDay} ${formatDate(summary.end_date, locale)}`}
            </span>
            <span className="chip neutral">
              {`${copy.backtest.tradingDays} ${metrics.trading_days}`}
            </span>
          </div>

          <div className="backtest-range-row">
            {(["1M", "3M", "6M", "1Y", "YTD", "ALL"] as BacktestRange[]).map((item) => (
              <button
                key={item}
                type="button"
                className={backtestRange === item ? "range-pill active" : "range-pill"}
                onClick={() => setBacktestRange(item)}
              >
                {rangeLabels[item]}
              </button>
            ))}
          </div>

          <div className="chart-card chart-wide">
            <div className="chart-head">
              <div>
                <p className="eyebrow">{copy.backtest.curveSubtitle}</p>
                <h3>{copy.backtest.curveTitle}</h3>
                <p className="section-note">
                  {locale === "zh" ? "横轴=日期，纵轴=累计收益率（%）" : "X-axis = date, Y-axis = cumulative return (%)"}
                </p>
              </div>
            </div>
            <svg viewBox="0 0 760 260" className="backtest-chart" role="img" aria-label="Backtest chart">
              {portfolioGeometry.ticks.map((tick, index) => (
                <g key={`y-grid-${index}`}>
                  <line x1={28} y1={tick.y} x2={732} y2={tick.y} className="backtest-grid-line" />
                  <text x={8} y={tick.y + 4} className="backtest-axis-label">
                    {`${tick.value.toFixed(1)}%`}
                  </text>
                </g>
              ))}
              {portfolioGeometry.dateTicks.map((tick) => (
                <g key={`x-grid-${tick.index}`}>
                  <line x1={tick.x} y1={28} x2={tick.x} y2={232} className="backtest-grid-line vertical" />
                  <text x={tick.x} y={252} textAnchor="middle" className="backtest-axis-label">
                    {formatDate(tick.date, locale)}
                  </text>
                </g>
              ))}
              <line x1={28} y1={portfolioGeometry.zeroY} x2={732} y2={portfolioGeometry.zeroY} className="backtest-zero-line" />
              <path d={portfolioGeometry.path} className="backtest-line portfolio" />
              <path d={benchmarkGeometry.path} className="backtest-line benchmark" />
            </svg>
            <div className="chip-row">
              <span className="chip positive">{copy.backtest.portfolio}</span>
              <span className="chip neutral">{summary.benchmark_ticker}</span>
            </div>
          </div>

          <div className="chart-card chart-wide">
            <div className="chart-head">
              <div>
                <p className="eyebrow">{copy.backtest.stockSeriesSubtitle}</p>
                <h3>{copy.backtest.stockSeriesTitle}</h3>
                <p className="section-note">
                  {locale === "zh" ? "横轴=日期，纵轴=单股累计收益率（%）" : "X-axis = date, Y-axis = stock cumulative return (%)"}
                </p>
              </div>
              <div className="chip-row">
                {positions.map((item) => (
                  <button
                    key={item.ticker}
                    type="button"
                    className={activeTicker === item.ticker ? "range-pill active" : "range-pill"}
                    onClick={() => setActiveTicker(item.ticker)}
                  >
                    {item.ticker}
                  </button>
                ))}
              </div>
            </div>
            <svg viewBox="0 0 760 260" className="backtest-chart" role="img" aria-label="Backtest stock chart">
              {stockGeometry.ticks.map((tick, index) => (
                <g key={`stock-y-grid-${index}`}>
                  <line x1={28} y1={tick.y} x2={732} y2={tick.y} className="backtest-grid-line" />
                  <text x={8} y={tick.y + 4} className="backtest-axis-label">
                    {`${tick.value.toFixed(1)}%`}
                  </text>
                </g>
              ))}
              {stockGeometry.dateTicks.map((tick) => (
                <g key={`stock-x-grid-${tick.index}`}>
                  <line x1={tick.x} y1={28} x2={tick.x} y2={232} className="backtest-grid-line vertical" />
                  <text x={tick.x} y={252} textAnchor="middle" className="backtest-axis-label">
                    {formatDate(tick.date, locale)}
                  </text>
                </g>
              ))}
              <line x1={28} y1={stockGeometry.zeroY} x2={732} y2={stockGeometry.zeroY} className="backtest-zero-line" />
              <path d={stockGeometry.path} className="backtest-line portfolio" />
            </svg>
            {!selectedTimeseries.length ? (
              <p className="section-note">
                {locale === "zh"
                  ? "当前单股时间序列为空，系统会尝试自动升级旧回测数据。"
                  : "No per-stock timeseries is available yet. The app will try to auto-upgrade legacy backtest data."}
              </p>
            ) : null}
          </div>

          <div className="report-table-wrap">
            <table className="report-table">
              <thead>
                <tr>
                  <th>Ticker</th>
                  <th>{copy.backtest.weight}</th>
                  <th>{copy.backtest.entryPrice}</th>
                  <th>{copy.backtest.latestPrice}</th>
                  <th>{copy.backtest.investedAmount}</th>
                  <th>{copy.backtest.currentValue}</th>
                  <th>{copy.backtest.return}</th>
                  <th>{copy.backtest.contribution}</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((item) => (
                  <tr key={item.ticker}>
                    <td>{item.ticker}</td>
                    <td>{formatPercent(item.weight)}</td>
                    <td>{formatCurrency(item.entry_price, locale)}</td>
                    <td>{formatCurrency(item.latest_price, locale)}</td>
                    <td>{formatCurrency(item.invested_amount, locale)}</td>
                    <td>{formatCurrency(item.current_value, locale)}</td>
                    <td>{formatPercent(item.return_pct)}</td>
                    <td>{formatPercent(item.contribution_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {selectedPosition ? (
            <div className="report-table-wrap">
              <p className="section-note">{`${copy.backtest.stockTabTitle}: ${selectedPosition.ticker}`}</p>
              <table className="report-table">
                <thead>
                  <tr>
                    <th>{copy.backtest.stockSeriesDate}</th>
                    <th>{copy.backtest.stockSeriesClose}</th>
                    <th>{copy.backtest.stockSeriesDaily}</th>
                    <th>{copy.backtest.stockSeriesCum}</th>
                    <th>{copy.backtest.stockSeriesContribution}</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedTimeseries.map((item) => (
                    <tr key={`${selectedPosition.ticker}-${item.point_date}`}>
                      <td>{formatDate(item.point_date, locale)}</td>
                      <td>{formatCurrency(item.close_price, locale)}</td>
                      <td>{formatPercent(item.daily_return_pct)}</td>
                      <td>{formatPercent(item.cumulative_return_pct)}</td>
                      <td>{formatPercent(item.contribution_pct)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
