/** 简单版投资报告：把展示母版渲染成网页和 PDF 一致的两页报告结构。 */
import { formatDateTime, formatPercent, repairText } from "../lib/format";
import type { BacktestDetail, Locale } from "../lib/types";

type GenericRecord = Record<string, unknown>;

interface SimpleInvestmentShowcaseProps {
  locale: Locale;
  result: GenericRecord;
  output: GenericRecord | null;
  charts: GenericRecord | null;
  backtest?: BacktestDetail | null;
}

/** 安全读取普通对象。 */
function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

/** 安全读取对象数组。 */
function asArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === "object") as GenericRecord[]) : [];
}

/** 安全读取字符串数组。 */
function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

/** 把未知值转换成可展示文本。 */
function toText(value: unknown, fallback = "N/A"): string {
  return repairText(value, fallback);
}

/** 把未知值转换成数字。 */
function toNumber(value: unknown): number | null {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

/** 把仓位数字转换成百分比文案。 */
function formatWeight(value: unknown, locale: Locale): string {
  const number = toNumber(value);
  if (number === null) return locale === "zh" ? "待定" : "Pending";
  return `${number.toFixed(1)}%`;
}

/** 根据分数返回展示色调。 */
function scoreTone(value: unknown): string {
  const number = toNumber(value);
  if (number === null) return "neutral";
  if (number >= 75) return "positive";
  if (number >= 55) return "neutral";
  return "negative";
}

/** 为旧 run 构造简单版展示母版兜底数据。 */
function buildFallbackModel(locale: Locale, result: GenericRecord, output: GenericRecord | null): GenericRecord {
  // 旧 run 可能没有展示母版，这里只从已有结构化结果里兜底，不编造新结论。
  const reportBriefing = asRecord(result.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const riskRegister = asArray(reportBriefing?.risk_register);
  const evidence = asArray(meta?.retrieved_evidence);
  const validationSummary = asRecord(meta?.validation_summary);
  const allocation = asArray(executive?.allocation_plan);
  const scoreboard = asArray(reportBriefing?.scoreboard);
  const holdings = (allocation.length ? allocation : scoreboard.slice(0, 4)).map((item) => ({
    ticker: item.ticker,
    company: item.company_name || item.ticker,
    weight: item.weight,
    role: item.verdict || item.verdict_label || (locale === "zh" ? "建议关注" : "Review"),
    reason: item.thesis || item.fit_reason || item.verdict_label || "",
  }));
  return {
    version: "simple_report_showcase_v1",
    layout: "two_page_showcase",
    title: locale === "zh" ? "简单版投资报告" : "Simple Investment Report",
    subtitle: locale === "zh" ? "先看结论，再看图表和证据。" : "Decision first, charts and evidence second.",
    query: result.query,
    generated_at: meta?.generated_at || result.updated_at,
    pages: [
      { id: "decision", title: locale === "zh" ? "第 1 页：决策总览" : "Decision page" },
      { id: "credibility", title: locale === "zh" ? "第 2 页：可信依据" : "Credibility page" },
    ],
    decision: {
      headline: executive?.display_call || executive?.primary_call,
      action: executive?.display_action_summary || executive?.action_summary,
      top_pick: executive?.top_pick,
      confidence: meta?.confidence_level,
      risk_summary: macro?.risk_headline || riskRegister[0]?.summary,
    },
    key_metrics: [
      { key: "mandate_fit", label: locale === "zh" ? "适配分" : "Mandate fit", value: executive?.mandate_fit_score, tone: scoreTone(executive?.mandate_fit_score) },
      { key: "evidence_count", label: locale === "zh" ? "证据数" : "Evidence", value: evidence.length, tone: "neutral" },
      { key: "candidate_count", label: locale === "zh" ? "候选数" : "Candidates", value: scoreboard.length, tone: "neutral" },
    ],
    holdings,
    chart_slots: defaultChartSlots(locale, output, null),
    reasons: holdings.map((item) => ({ ticker: item.ticker, company: item.company, text: item.reason })),
    risks: riskRegister.slice(0, 3),
    evidence: evidence.slice(0, 5).map((item) => ({
      title: item.title || item.summary,
      source: item.source_name || item.source_type || item.source,
      date: item.published_at || item.as_of_date,
      ticker: item.ticker,
      url: item.url,
    })),
    validation: { headline: validationSummary?.headline, items: asStringArray(validationSummary?.items).slice(0, 3) },
    footer_note: locale === "zh" ? "本报告仅用于研究辅助，不构成财务、法律或税务建议。" : "This report is for research support only and is not financial, legal, or tax advice.",
  };
}

/** 按当前图表可用性确定简单版三张核心图。 */
function defaultChartSlots(locale: Locale, output: GenericRecord | null, charts: GenericRecord | null): GenericRecord[] {
  const sourceCharts = charts || asRecord(output?.charts);
  const backtestChart = asRecord(sourceCharts?.portfolio_vs_benchmark_backtest);
  const hasBacktest = toText(backtestChart?.status, "") === "available" && asArray(backtestChart?.points).length >= 2;
  return [
    { key: "portfolio_allocation", title: locale === "zh" ? "推荐仓位" : "Recommended Portfolio Allocation", type: "bar" },
    { key: "candidate_score_comparison", title: locale === "zh" ? "候选评分" : "Candidate Score Comparison", type: "bar" },
    hasBacktest
      ? { key: "portfolio_vs_benchmark_backtest", title: locale === "zh" ? "组合 vs SPY" : "Portfolio vs Benchmark Backtest", type: "line" }
      : { key: "risk_contribution", title: locale === "zh" ? "风险来源" : "Risk Contribution", type: "bar" },
  ];
}

/** 读取展示母版，并用当前回测刷新关键指标和图表槽位。 */
function readModel(locale: Locale, result: GenericRecord, output: GenericRecord | null, charts: GenericRecord | null, backtest?: BacktestDetail | null): GenericRecord {
  const model = asRecord(output?.display_model) || buildFallbackModel(locale, result, output);
  return {
    ...model,
    chart_slots: defaultChartSlots(locale, output, charts),
    key_metrics: mergeBacktestMetrics(locale, asArray(model.key_metrics), backtest),
  };
}

/** 把当前已加载回测指标合并到第一页关键数字。 */
function mergeBacktestMetrics(locale: Locale, metrics: GenericRecord[], backtest?: BacktestDetail | null): GenericRecord[] {
  const backtestMetrics = backtest?.summary?.metrics;
  const base = metrics.filter((item) => !["portfolio_return", "excess_return", "backtest_status"].includes(toText(item.key, "")));
  if (!backtestMetrics) return metrics;
  const inserted = [
    {
      key: "portfolio_return",
      label: locale === "zh" ? "组合回测" : "Portfolio return",
      value: formatPercent(backtestMetrics.total_return_pct),
      tone: backtestMetrics.total_return_pct >= 0 ? "positive" : "negative",
    },
    {
      key: "excess_return",
      label: locale === "zh" ? "相对 SPY" : "Excess vs SPY",
      value: formatPercent(backtestMetrics.excess_return_pct),
      tone: backtestMetrics.excess_return_pct >= 0 ? "positive" : "negative",
    },
  ];
  return [...base.slice(0, 1), ...inserted, ...base.slice(1)].slice(0, 5);
}

/** 渲染第一页关键指标卡片。 */
function metricCards(locale: Locale, metrics: GenericRecord[]) {
  const visible = metrics.slice(0, 5);
  if (!visible.length) {
    return <div className="showcase-metric"><span>{locale === "zh" ? "暂无指标" : "No metrics"}</span><strong>N/A</strong></div>;
  }
  return visible.map((metric) => (
    <div key={toText(metric.key, toText(metric.label))} className={`showcase-metric ${toText(metric.tone, "neutral")}`}>
      <span>{toText(metric.label)}</span>
      <strong>{toText(metric.value)}</strong>
    </div>
  ));
}

/** 从图表行中读取数值。 */
function chartValue(item: GenericRecord, keys: string[]): number | null {
  for (const key of keys) {
    const value = toNumber(item[key]);
    if (value !== null) return value;
  }
  return null;
}

/** 从图表行中读取标签。 */
function chartLabel(item: GenericRecord, keys: string[]): string {
  for (const key of keys) {
    const value = toText(item[key], "");
    if (value) return value;
  }
  return "N/A";
}

/** 根据一组数值生成 SVG 折线路径。 */
function buildLinePath(values: number[], width: number, height: number, padding = 20): string {
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const spread = Math.max(max - min, 1);
  return values
    .map((value, index) => {
      const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y = height - padding - ((value - min) / spread) * (height - padding * 2);
      return `${index === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

/** 渲染简单版报告里的单张图表卡片。 */
function ShowcaseChart({ locale, slot, charts, backtest }: { locale: Locale; slot: GenericRecord; charts: GenericRecord | null; backtest?: BacktestDetail | null }) {
  const key = toText(slot.key, "");
  const title = toText(slot.title, key);
  const chart = asRecord(charts?.[key]);
  if (key === "portfolio_vs_benchmark_backtest") {
    const points = (backtest?.points?.length ? backtest.points : asArray(chart?.points))
      .map((item) => ({
        portfolio: toNumber(item.portfolio_value ?? item.portfolio_return_pct),
        benchmark: toNumber(item.benchmark_value ?? item.benchmark_return_pct),
      }))
      .filter((item): item is { portfolio: number; benchmark: number } => item.portfolio !== null && item.benchmark !== null);
    if (points.length < 2) {
      return <article className="showcase-chart-card"><h3>{title}</h3><p>{locale === "zh" ? "暂无可画出的回测曲线。" : "No drawable backtest series is available."}</p></article>;
    }
    const width = 330;
    const height = 170;
    const portfolioPath = buildLinePath(points.map((point) => point.portfolio), width, height);
    const benchmarkPath = buildLinePath(points.map((point) => point.benchmark), width, height);
    return (
      <article className="showcase-chart-card">
        <h3>{title}</h3>
        <svg viewBox={`0 0 ${width} ${height}`} className="showcase-chart" role="img" aria-label={title}>
          <rect x="0" y="0" width={width} height={height} rx="14" fill="rgba(15, 23, 42, 0.05)" />
          <path d={portfolioPath} fill="none" stroke="#17645e" strokeWidth="4" strokeLinecap="round" />
          <path d={benchmarkPath} fill="none" stroke="#a05d25" strokeWidth="3" strokeDasharray="8 6" strokeLinecap="round" />
        </svg>
        <div className="showcase-legend">
          <span className="portfolio" />
          <span>{locale === "zh" ? "组合" : "Portfolio"}</span>
          <span className="benchmark" />
          <span>{locale === "zh" ? "基准" : "Benchmark"}</span>
        </div>
      </article>
    );
  }

  const chartConfig: Record<string, { valueKeys: string[]; labelKeys: string[]; suffix: string }> = {
    portfolio_allocation: { valueKeys: ["weight", "weight_pct", "allocation"], labelKeys: ["ticker", "name"], suffix: "%" },
    candidate_score_comparison: { valueKeys: ["composite", "composite_score", "score"], labelKeys: ["ticker", "name"], suffix: "" },
    risk_contribution: { valueKeys: ["value", "risk", "risk_score", "weight"], labelKeys: ["name", "category", "ticker"], suffix: "" },
  };
  const config = chartConfig[key] || chartConfig.portfolio_allocation;
  const items = asArray(chart?.items);
  const maxValue = Math.max(1, ...items.map((item) => chartValue(item, config.valueKeys) || 0));
  return (
    <article className="showcase-chart-card">
      <h3>{title}</h3>
      {items.length ? (
        <div className="showcase-bars">
          {items.slice(0, 6).map((item, index) => {
            const value = chartValue(item, config.valueKeys) || 0;
            const width = `${Math.max(6, Math.min(100, (value / maxValue) * 100))}%`;
            const label = chartLabel(item, config.labelKeys);
            return (
              <div key={`${key}-${label}-${index}`} className="showcase-bar-row">
                <span>{label}</span>
                <div><i style={{ width }} /></div>
                <strong>{value.toFixed(1)}{config.suffix}</strong>
              </div>
            );
          })}
        </div>
      ) : (
        <p>{toText(chart?.message, locale === "zh" ? "暂无该图表数据。" : "No chart data is available.")}</p>
      )}
    </article>
  );
}

/** 渲染网页端简单版两页展示报告。 */
export function SimpleInvestmentShowcase({ locale, result, output, charts, backtest = null }: SimpleInvestmentShowcaseProps) {
  const model = readModel(locale, result, output, charts, backtest);
  const pages = asArray(model.pages);
  const decision = asRecord(model.decision);
  const holdings = asArray(model.holdings);
  const reasons = asArray(model.reasons);
  const risks = asArray(model.risks);
  const evidence = asArray(model.evidence);
  const validation = asRecord(model.validation);
  const chartSlots = asArray(model.chart_slots);
  const generatedLabel = formatDateTime(model.generated_at, locale);

  return (
    <div className="simple-showcase-report">
      <section id="report-overview" className="simple-showcase-page decision-page anchor-target">
        <div className="showcase-hero">
          <div>
            <p className="eyebrow">{toText(pages[0]?.title, locale === "zh" ? "第 1 页：决策总览" : "Decision page")}</p>
            <h3>{toText(model.title, locale === "zh" ? "简单版投资报告" : "Simple Investment Report")}</h3>
            <p className="section-note">{toText(model.subtitle, locale === "zh" ? "先看结论，再看图表和证据。" : "Decision first, charts and evidence second.")} · {generatedLabel}</p>
            <p className="showcase-verdict">{toText(decision?.headline, locale === "zh" ? "暂无结论。" : "No conclusion available.")}</p>
            <p className="showcase-action">{toText(decision?.action, locale === "zh" ? "暂无执行建议。" : "No action summary available.")}</p>
          </div>
          <div className="showcase-badges">
            <div><span>{locale === "zh" ? "首选" : "Top pick"}</span><strong>{toText(decision?.top_pick)}</strong></div>
            <div><span>{locale === "zh" ? "可信度" : "Confidence"}</span><strong>{toText(decision?.confidence)}</strong></div>
            <div><span>{locale === "zh" ? "主要风险" : "Main risk"}</span><strong>{toText(decision?.risk_summary)}</strong></div>
          </div>
        </div>

        <div className="showcase-query">
          <span>{locale === "zh" ? "原始问题" : "Original request"}</span>
          <p>{toText(model.query, locale === "zh" ? "暂无原始问题。" : "No original request.")}</p>
        </div>

        <div className="showcase-metric-grid">{metricCards(locale, asArray(model.key_metrics))}</div>

        <div className="showcase-holdings">
          <div className="showcase-section-head">
            <p className="eyebrow">{locale === "zh" ? "推荐组合" : "Recommended holdings"}</p>
            <h3>{locale === "zh" ? "仓位和角色" : "Sizing and role"}</h3>
          </div>
          <div className="showcase-holding-list">
            {holdings.length ? holdings.map((item, index) => (
              <div key={`${toText(item.ticker)}-${index}`} className="showcase-holding-row">
                <strong>{toText(item.ticker)}</strong>
                <span>{formatWeight(item.weight, locale)}</span>
                <div>
                  <b>{toText(item.role)}</b>
                  <p>{toText(item.company || item.reason, "")}</p>
                </div>
              </div>
            )) : <p className="section-note">{locale === "zh" ? "暂无推荐仓位。" : "No recommended holding is available."}</p>}
          </div>
        </div>

        <div id="report-charts" className="showcase-chart-grid anchor-target">
          {chartSlots.map((slot, index) => <ShowcaseChart key={`${toText(slot.key)}-${index}`} locale={locale} slot={slot} charts={charts} backtest={backtest} />)}
        </div>
      </section>

      <section id="report-evidence" className="simple-showcase-page credibility-page anchor-target">
        <div className="showcase-section-head">
          <p className="eyebrow">{toText(pages[1]?.title, locale === "zh" ? "第 2 页：可信依据" : "Credibility page")}</p>
          <h3>{locale === "zh" ? "为什么这个结论可信" : "Why this conclusion is credible"}</h3>
        </div>
        <div className="showcase-two-column">
          <article>
            <h3>{locale === "zh" ? "核心理由" : "Core reasons"}</h3>
            <ul>
              {reasons.length ? reasons.map((item, index) => <li key={`${toText(item.ticker)}-${index}`}><strong>{toText(item.ticker)}</strong>: {toText(item.text)}</li>) : <li>{locale === "zh" ? "暂无核心理由。" : "No core reason is available."}</li>}
            </ul>
          </article>
          <article>
            <h3>{locale === "zh" ? "关键风险" : "Key risks"}</h3>
            <ul>
              {risks.length ? risks.map((item, index) => (
                <li key={`${toText(item.category)}-${index}`}><strong>{toText(item.category)}{toText(item.ticker, "") ? ` / ${toText(item.ticker)}` : ""}</strong>: {toText(item.summary)}</li>
              )) : <li>{locale === "zh" ? "暂无关键风险。" : "No key risk is available."}</li>}
            </ul>
          </article>
        </div>
        <div className="showcase-two-column">
          <article>
            <h3>{locale === "zh" ? "证据快照" : "Evidence snapshot"}</h3>
            <ul>
              {evidence.length ? evidence.map((item, index) => {
                const url = toText(item.url, "");
                const title = toText(item.title);
                return (
                  <li key={`${title}-${index}`}>
                    {url.startsWith("http") ? <a href={url} target="_blank" rel="noreferrer">{title}</a> : title}
                    <span>{toText(item.source, "")}{toText(item.date, "") ? ` · ${toText(item.date)}` : ""}</span>
                  </li>
                );
              }) : <li>{locale === "zh" ? "暂无证据摘要。" : "No evidence summary is available."}</li>}
            </ul>
          </article>
          <article>
            <h3>{locale === "zh" ? "校验快照" : "Validation snapshot"}</h3>
            <p>{toText(validation?.headline, locale === "zh" ? "暂无校验摘要。" : "No validation summary available.")}</p>
            {asStringArray(validation?.items).length ? (
              <ul>{asStringArray(validation?.items).map((item) => <li key={item}>{item}</li>)}</ul>
            ) : null}
          </article>
        </div>
        <p className="showcase-footer-note">{toText(model.footer_note)}</p>
      </section>
    </div>
  );
}
