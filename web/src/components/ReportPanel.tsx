/** 正式报告面板：负责渲染报告正文、依据摘要、逐票研究卡与导出入口。 */
import { useEffect, useRef, useState } from "react";
import { formatDateTime, formatJson, formatScore, repairText } from "../lib/format";
import { exportReport } from "../lib/reportExport";
import type { BacktestDetail, DataStatus, Locale } from "../lib/types";
import type { LocalePack } from "../lib/i18n";
import { ResearchCharts } from "./ResearchCharts";

type GenericRecord = Record<string, unknown>;

interface ReportPanelProps {
  locale: Locale;
  copy: LocalePack;
  result: Record<string, unknown> | null;
  dataStatus: DataStatus | null;
  backtest?: BacktestDetail | null;
  variant?: "terminal" | "debug";
}

function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

function asArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === "object") as GenericRecord[]) : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

function asRecordArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") as GenericRecord[] : [];
}

function toNumber(value: unknown): number | null {
  const number = typeof value === "number" ? value : Number(value);
  return Number.isFinite(number) ? number : null;
}

function toText(value: unknown, fallback = "N/A"): string {
  return repairText(value, fallback);
}

function hasText(value: unknown): boolean {
  return !!repairText(value, "").trim();
}

function parseTableRow(line: string): string[] {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function verdictTone(verdict: string): string {
  const lowered = verdict.toLowerCase();
  if (lowered.includes("buy") || lowered.includes("accumulate") || lowered.includes("优先") || lowered.includes("布局")) {
    return "positive";
  }
  if (lowered.includes("watch") || lowered.includes("hold") || lowered.includes("观察")) {
    return "neutral";
  }
  return "negative";
}

function scoreTone(score: number | null): string {
  if (score === null) return "neutral";
  if (score >= 75) return "positive";
  if (score >= 55) return "neutral";
  return "negative";
}

function sourceAlias(locale: Locale, raw: unknown): string {
  const source = toText(raw, "").toLowerCase();
  if (!source) return locale === "zh" ? "未知来源" : "Unknown source";
  const mapZh: Record<string, string> = {
    yfinance: "Yahoo Finance",
    yfinance_batch: "Yahoo Finance",
    yfinance_proxy: "Yahoo Finance",
    yahoo_rss: "Yahoo Finance 新闻",
    finnhub: "Finnhub 新闻",
    sec_edgar: "SEC EDGAR 披露",
    alpha_vantage: "Alpha Vantage",
    alpaca_iex: "Alpaca Market Data",
    longbridge_daily: "Longbridge 行情",
    historical_unavailable: "历史数据暂不可用",
    none: "暂无覆盖",
    unavailable: "暂不可用",
  };
  const mapEn: Record<string, string> = {
    yfinance: "Yahoo Finance",
    yfinance_batch: "Yahoo Finance",
    yfinance_proxy: "Yahoo Finance",
    yahoo_rss: "Yahoo Finance News",
    finnhub: "Finnhub News",
    sec_edgar: "SEC EDGAR Filings",
    alpha_vantage: "Alpha Vantage",
    alpaca_iex: "Alpaca Market Data",
    longbridge_daily: "Longbridge Market Data",
    historical_unavailable: "Historical data unavailable",
    none: "No coverage",
    unavailable: "Unavailable",
  };
  const map = locale === "zh" ? mapZh : mapEn;
  return map[source] || String(raw);
}

function formatMissingField(locale: Locale, value: string): string {
  const mappingZh: Record<string, string> = {
    capital_amount: "投入金额",
    risk_tolerance: "风险偏好",
    investment_horizon: "投资期限",
    investment_style: "投资风格",
    preferred_sectors: "偏好板块",
    fundamental_filters: "筛选条件",
  };
  const mappingEn: Record<string, string> = {
    capital_amount: "capital",
    risk_tolerance: "risk preference",
    investment_horizon: "horizon",
    investment_style: "investment style",
    preferred_sectors: "sector preference",
    fundamental_filters: "filters",
  };
  const mapping = locale === "zh" ? mappingZh : mappingEn;
  return mapping[value] || value;
}

function buildProfileFacts(locale: Locale, userProfile: GenericRecord | null): string[] {
  if (!userProfile) return [];
  return [
    userProfile.capital_amount
      ? locale === "zh"
        ? `资金 ${toText(userProfile.capital_amount)} ${toText(userProfile.currency, "USD")}`
        : `Capital ${toText(userProfile.capital_amount)} ${toText(userProfile.currency, "USD")}`
      : "",
    userProfile.risk_tolerance
      ? locale === "zh"
        ? `风险 ${toText(userProfile.risk_tolerance)}`
        : `Risk ${toText(userProfile.risk_tolerance)}`
      : "",
    userProfile.investment_horizon
      ? locale === "zh"
        ? `期限 ${toText(userProfile.investment_horizon)}`
        : `Horizon ${toText(userProfile.investment_horizon)}`
      : "",
    userProfile.investment_style
      ? locale === "zh"
        ? `风格 ${toText(userProfile.investment_style)}`
        : `Style ${toText(userProfile.investment_style)}`
      : "",
  ].filter(Boolean);
}

function renderReportMarkdown(text: string) {
  const lines = repairText(text, "").split(/\r?\n/);
  const blocks: Array<
    | { type: "h1" | "h2" | "h3"; text: string }
    | { type: "list"; items: string[] }
    | { type: "paragraph"; text: string }
    | { type: "table"; rows: string[][] }
  > = [];

  for (let index = 0; index < lines.length; ) {
    const line = lines[index].trim();
    if (!line) {
      index += 1;
      continue;
    }

    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (index < lines.length && lines[index].trim().startsWith("|")) {
        const row = parseTableRow(lines[index]);
        if (!row.every((cell) => /^:?-{3,}:?$/.test(cell))) {
          rows.push(row);
        }
        index += 1;
      }
      if (rows.length) {
        blocks.push({ type: "table", rows });
      }
      continue;
    }

    if (line.startsWith("### ")) {
      blocks.push({ type: "h3", text: line.slice(4).trim() });
      index += 1;
      continue;
    }
    if (line.startsWith("## ")) {
      blocks.push({ type: "h2", text: line.slice(3).trim() });
      index += 1;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push({ type: "h1", text: line.slice(2).trim() });
      index += 1;
      continue;
    }

    if (line.startsWith("- ")) {
      const items: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith("- ")) {
        items.push(lines[index].trim().slice(2).trim());
        index += 1;
      }
      blocks.push({ type: "list", items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length) {
      const current = lines[index].trim();
      if (!current || current.startsWith("#") || current.startsWith("- ") || current.startsWith("|")) {
        break;
      }
      paragraphLines.push(current);
      index += 1;
    }
    blocks.push({ type: "paragraph", text: paragraphLines.join(" ") });
  }

  return blocks.map((block, index) => {
    if (block.type === "h1") return <h1 key={index}>{block.text}</h1>;
    if (block.type === "h2") return <h2 key={index}>{block.text}</h2>;
    if (block.type === "h3") return <h3 key={index}>{block.text}</h3>;
    if (block.type === "paragraph") return <p key={index}>{block.text}</p>;
    if (block.type === "list") {
      return (
        <ul key={index}>
          {block.items.map((item, itemIndex) => (
            <li key={itemIndex}>{item}</li>
          ))}
        </ul>
      );
    }
    return (
      <div key={index} className="report-table-wrap">
        <table className="report-table">
          <thead>
            <tr>
              {block.rows[0].map((cell, cellIndex) => (
                <th key={cellIndex}>{cell}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.slice(1).map((row, rowIndex) => (
              <tr key={rowIndex}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  });
}

function ClarificationState({
  locale,
  copy,
  result,
  variant,
}: {
  locale: Locale;
  copy: LocalePack;
  result: GenericRecord;
  variant: "terminal" | "debug";
}) {
  const parsedIntent = asRecord(result.parsed_intent);
  const agentControl = asRecord(parsedIntent?.agent_control);
  const explicitTargets = asRecord(parsedIntent?.explicit_targets);
  const missing = asStringArray(agentControl?.missing_critical_info).map((item) => formatMissingField(locale, item));
  const tickers = asStringArray(explicitTargets?.tickers);
  const followUpQuestion = toText(result.follow_up_question, copy.report.empty);

  return (
    <section className="panel-surface report-surface">
      <div className="section-head">
        <div>
          <p className="eyebrow">{copy.report.clarificationEyebrow}</p>
          <h2>{copy.report.clarificationTitle}</h2>
        </div>
        <span className="chip neutral">{locale === "zh" ? "待补充信息" : "Follow-up needed"}</span>
      </div>

      <div className="clarification-hero">
        <h3>{followUpQuestion}</h3>
        <p className="section-note">
          {locale === "zh"
            ? "如果只是轻微缺项，系统会带着默认假设继续分析；只有资金、风险、期限这些核心约束不足时，才会停在这里等待你确认。"
            : "If only minor details are missing, the system will continue with explicit assumptions. It stops here only when core constraints such as capital, risk, or horizon are still missing."}
        </p>
      </div>

      <div className="summary-grid two-up">
        <div className="mini-card">
          <h3>{copy.report.clarificationMissing}</h3>
          <div className="chip-row">
            {missing.length ? missing.map((item) => <span key={item} className="chip neutral">{item}</span>) : <span className="chip">N/A</span>}
          </div>
        </div>
        <div className="mini-card">
          <h3>{copy.report.clarificationTickers}</h3>
          <div className="chip-row">
            {tickers.length ? tickers.map((item) => <span key={item} className="chip positive">{item}</span>) : <span className="chip">N/A</span>}
          </div>
        </div>
      </div>

      {variant === "debug" ? (
        <details className="json-details">
          <summary>{copy.report.clarificationJson}</summary>
          <pre className="json-viewer">{formatJson(parsedIntent)}</pre>
        </details>
      ) : null}
    </section>
  );
}

function StructuredSnapshot({ locale, copy, result }: { locale: Locale; copy: LocalePack; result: GenericRecord }) {
  const debugSummary = asRecord(result.debug_summary);
  const comparisonMatrix = asArray(result.comparison_matrix);

  return (
    <section className="panel-surface report-surface">
      <div className="section-head">
        <div>
          <p className="eyebrow">{copy.report.structuredEyebrow}</p>
          <h2>{copy.report.structuredTitle}</h2>
        </div>
      </div>

      <div className="summary-grid two-up">
        <div className="mini-card">
          <h3>{copy.report.structuredSummary}</h3>
          <p>{locale === "zh" ? "候选数量" : "Candidates"}: {toText(debugSummary?.selected_ticker_count)}</p>
          <p>{locale === "zh" ? "实时数据" : "Live data"}: {toText(debugSummary?.live_data_enabled)}</p>
          <p>{locale === "zh" ? "阶段数" : "Stages"}: {toText(debugSummary?.stage_count)}</p>
        </div>
        <div className="mini-card">
          <h3>{copy.report.structuredPositioning}</h3>
          <p>
            {locale === "zh"
              ? "这个 run 主要用于验证股票池、筛选逻辑和外部数据链路，不会生成完整的研究长文。"
              : "This run is mainly for validating the screener, the universe and external data ingestion rather than generating a full memo."}
          </p>
        </div>
      </div>

      {comparisonMatrix.length ? (
        <div className="report-table-wrap">
          <table className="report-table">
            <thead>
              <tr>
                <th>Ticker</th>
                <th>{copy.report.labels.company}</th>
                <th>Sector</th>
                <th>PE</th>
                <th>ROE</th>
                <th>Dividend</th>
                <th>Quant Score</th>
              </tr>
            </thead>
            <tbody>
              {comparisonMatrix.map((row, index) => (
                <tr key={`${toText(row.Ticker)}-${index}`}>
                  <td>{toText(row.Ticker)}</td>
                  <td>{toText(row.Company_Name)}</td>
                  <td>{toText(row.Sector)}</td>
                  <td>{toText(row.PE_Ratio)}</td>
                  <td>{toText(row.ROE)}</td>
                  <td>{toText(row.Dividend_Yield)}</td>
                  <td>{toText(row.Total_Quant_Score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="empty-state small">{copy.report.noTable}</div>
      )}
    </section>
  );
}

export function ReportPanel({ locale, copy, result, dataStatus, backtest = null, variant = "debug" }: ReportPanelProps) {
  const [activeMetricHelpId, setActiveMetricHelpId] = useState<string | null>(null);
  const metricHelpRootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    function onDocumentMouseDown(event: MouseEvent) {
      if (!activeMetricHelpId) {
        return;
      }
      if (metricHelpRootRef.current && event.target instanceof Node && !metricHelpRootRef.current.contains(event.target)) {
        setActiveMetricHelpId(null);
      }
    }

    function onDocumentKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setActiveMetricHelpId(null);
      }
    }

    document.addEventListener("mousedown", onDocumentMouseDown);
    document.addEventListener("keydown", onDocumentKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocumentMouseDown);
      document.removeEventListener("keydown", onDocumentKeyDown);
    };
  }, [activeMetricHelpId]);

  if (!result) {
    return <section className="panel-surface report-surface empty-state">{copy.report.empty}</section>;
  }

  const status = toText(result.status, "");
  if (status === "needs_clarification") {
    return <ClarificationState locale={locale} copy={copy} result={result} variant={variant} />;
  }

  const reportBriefing = asRecord(result.report_briefing);
  if (!reportBriefing) {
    const comparisonMatrix = asArray(result.comparison_matrix);
    if (comparisonMatrix.length) {
      return <StructuredSnapshot locale={locale} copy={copy} result={result} />;
    }
    return <section className="panel-surface report-surface empty-state">{copy.report.empty}</section>;
  }

  const meta = asRecord(reportBriefing.meta);
  const executive = asRecord(reportBriefing.executive);
  const macro = asRecord(reportBriefing.macro);
  const parsedIntent = asRecord(result.parsed_intent);
  const agentControl = asRecord(parsedIntent?.agent_control);
  const researchContext = asRecord(result.research_context);
  const analysis = asRecord(result.analysis);
  const debugSummary = asRecord(analysis?.debug_summary);
  const charts = asRecord(reportBriefing.charts);
  const scoreboard = asArray(reportBriefing.scoreboard);
  const tickerCards = asArray(reportBriefing.ticker_cards);
  const riskRegister = asArray(reportBriefing.risk_register);
  const ranking = asArray(charts?.ranking);
  const dimensions = asArray(charts?.dimensions);
  const allocation = asArray(charts?.allocation);
  const dataProvenance = asRecord(meta?.data_provenance);
  const scoreGuide = asRecord(meta?.score_guide);
  const finalReport = typeof result.final_report === "string" ? repairText(result.final_report, "") : "";
  const reportMode = toText(result.report_mode, "unknown");
  const reportError = toText(result.report_error, "");
  const watchlist = asStringArray(executive?.watchlist);
  const avoidList = asStringArray(executive?.avoid_list);
  const allocationPlan = asArray(executive?.allocation_plan);
  const assumptions = asStringArray(meta?.assumptions || result.assumptions);
  const warningFlags = asStringArray(meta?.warning_flags || debugSummary?.warning_flags);
  const missingInfo = asStringArray(agentControl?.missing_critical_info);
  const intentUsable = Boolean(agentControl?.is_intent_usable);
  const severeMacro = Boolean(macro?.severe_warning);
  const researchMode = toText(meta?.research_mode || researchContext?.research_mode, "realtime");
  const asOfDate = toText(meta?.as_of_date || researchContext?.as_of_date, "");
  const userProfile = asRecord(meta?.user_profile);
  const evidenceSummary = asRecord(meta?.evidence_summary);
  const validationSummary = asRecord(meta?.validation_summary);
  const safetySummary = asRecord(meta?.safety_summary);
  const memorySummary = asRecord(result.memory_summary);
  const profileFacts = buildProfileFacts(locale, userProfile);
  const headerTitle = locale === "zh" ? "机构级投资研究报告" : "Institutional Investment Research Report";
  const headerSubtitle = locale === "zh" ? "研究终端 / 投资决策备忘录" : "Research terminal / portfolio decision memo";

  const effectiveDataStatus = dataProvenance || (dataStatus as unknown as GenericRecord | null);
  const mandateSummary = toText(meta?.mandate_summary, locale === "zh" ? "暂无 mandate 摘要。" : "Mandate summary unavailable.");

  return (
    <section className="panel-surface report-surface">
      <div className="section-head">
        <div>
          <p className="eyebrow">{copy.report.reportEyebrow}</p>
          <h2>{headerTitle}</h2>
          <p className="section-note">{headerSubtitle}</p>
        </div>
        <div className="report-toolbar">
          <div className="chip-row">
            <span className="chip">
              {copy.report.labels.mode}: {researchMode === "historical" ? copy.terminal.historical : copy.terminal.realtime}
            </span>
            {asOfDate ? <span className="chip">{`as_of: ${asOfDate}`}</span> : null}
            {variant === "debug" ? <span className="chip">{copy.report.reportMode}: {reportMode}</span> : null}
            <span className={`chip ${scoreTone(toNumber(executive?.mandate_fit_score))}`}>
              {copy.report.mandateFit} {formatScore(executive?.mandate_fit_score)}
            </span>
            {meta?.ticker_count ? <span className="chip">{copy.report.candidates} {toText(meta.ticker_count)}</span> : null}
          </div>
          <div className="button-row compact">
            {variant === "terminal" ? (
              <>
                <button type="button" className="secondary-button compact-action" onClick={() => exportReport(result, locale, "pdf", backtest)}>
                  {locale === "zh" ? "导出 PDF" : "Export PDF"}
                </button>
                <button type="button" className="secondary-button compact-action" onClick={() => exportReport(result, locale, "html", backtest)}>
                  {locale === "zh" ? "下载 HTML" : "Download HTML"}
                </button>
              </>
            ) : (
              <>
                <button type="button" className="secondary-button compact-action" onClick={() => exportReport(result, locale, "markdown", backtest)}>
                  {locale === "zh" ? "下载 Markdown" : "Download Markdown"}
                </button>
                <button type="button" className="secondary-button compact-action" onClick={() => exportReport(result, locale, "html", backtest)}>
                  {locale === "zh" ? "下载 HTML" : "Download HTML"}
                </button>
                <button type="button" className="secondary-button compact-action" onClick={() => exportReport(result, locale, "json", backtest)}>
                  {locale === "zh" ? "下载证据包" : "Download evidence"}
                </button>
              </>
            )}
          </div>
        </div>
      </div>

      {variant === "terminal" ? (
        <nav className="report-anchor-nav">
          <a href="#report-overview" className="anchor-chip">{copy.report.labels.overview}</a>
          <a href="#report-charts" className="anchor-chip">{copy.report.labels.charts}</a>
          <a href="#report-scoreboard" className="anchor-chip">{locale === "zh" ? "候选池" : "Scoreboard"}</a>
          <a href="#report-coverage" className="anchor-chip">{copy.report.labels.coverage}</a>
          <a href="#report-risks" className="anchor-chip">{copy.report.labels.riskExecution}</a>
          {finalReport ? <a href="#report-memo" className="anchor-chip">{copy.report.labels.fullMemo}</a> : null}
        </nav>
      ) : null}

      {severeMacro ? <div className="warning-banner">{toText(macro?.risk_headline)}</div> : null}
      {reportError ? <div className="danger-banner">{reportError}</div> : null}
      {assumptions.length ? (
        <div className="warning-banner assumption-banner">
          <strong>{copy.report.labels.assumptions}:</strong> {assumptions.join(locale === "zh" ? "；" : "; ")}
        </div>
      ) : null}
      {warningFlags.length ? (
        <div className="warning-banner assumption-banner">
          <strong>{copy.report.labels.dataWarnings}:</strong> {warningFlags.join(locale === "zh" ? "；" : "; ")}
        </div>
      ) : null}
      {!assumptions.length && !agentControl?.is_intent_clear && intentUsable ? (
        <div className="warning-banner assumption-banner">
          {locale === "zh"
            ? "当前需求并非完全结构化，但系统已按可用信息继续完成分析。"
            : "The mandate was not fully explicit, but the system proceeded using the available information."}
        </div>
      ) : null}
      {!agentControl?.is_intent_clear && missingInfo.length ? (
        <div className="section-note">
          {copy.report.labels.stillNeedClarify} {missingInfo.join(", ")}
        </div>
      ) : null}

      <div className="summary-grid three-up">
        <div className="mini-card">
          <h3>{locale === "zh" ? "系统理解到的目标" : "What the system understood"}</h3>
          <p>{toText(userProfile?.summary, locale === "zh" ? "暂无用户画像。" : "No mandate summary yet.")}</p>
          {profileFacts.length ? (
            <div className="chip-row">
              {profileFacts.map((item) => (
                <span key={item} className="chip neutral">{item}</span>
              ))}
            </div>
          ) : null}
          {hasText(memorySummary?.note) ? <p>{toText(memorySummary?.note)}</p> : null}
        </div>
        <div className="mini-card">
          <h3>{locale === "zh" ? "本次结论依据" : "Why this conclusion"}</h3>
          <p>{toText(evidenceSummary?.headline, locale === "zh" ? "暂无依据摘要。" : "No evidence summary yet.")}</p>
          {asStringArray(evidenceSummary?.items).length ? (
            <ul className="compact-list">
              {asStringArray(evidenceSummary?.items).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          {asStringArray(evidenceSummary?.source_points).length ? (
            <div className="chip-row">
              {asStringArray(evidenceSummary?.source_points).map((item) => (
                <span key={item} className="chip neutral">{item}</span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="mini-card">
          <h3>{locale === "zh" ? "先看这些谨慎提示" : "Read these caveats first"}</h3>
          <p>{toText(validationSummary?.headline, locale === "zh" ? "暂无校验摘要。" : "No validation summary yet.")}</p>
          {asStringArray(validationSummary?.items).length ? (
            <ul className="compact-list">
              {asStringArray(validationSummary?.items).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      <div className="summary-grid two-up">
        <div className="mini-card">
          <h3>{locale === "zh" ? "安全与数据覆盖" : "Safety & data coverage"}</h3>
          <p>{toText(safetySummary?.headline, locale === "zh" ? "暂无安全摘要。" : "No safety summary yet.")}</p>
          {asStringArray(safetySummary?.used_sources).length ? (
            <div className="chip-row">
              {asStringArray(safetySummary?.used_sources).map((item) => (
                <span key={item} className="chip neutral">{item}</span>
              ))}
            </div>
          ) : null}
        </div>
        <div className="mini-card">
          <h3>{locale === "zh" ? "需要保守解读的地方" : "Areas with degraded coverage"}</h3>
          {asStringArray(safetySummary?.degraded_modules).length ? (
            <ul className="compact-list">
              {asStringArray(safetySummary?.degraded_modules).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>{locale === "zh" ? "本次研究没有明显的数据降级提示。" : "No major degraded-data caveat was detected in this run."}</p>
          )}
        </div>
      </div>

      <div id="report-overview" className="executive-grid anchor-target">
        <article className="executive-card">
          <p className="eyebrow">{locale === "zh" ? "执行结论" : "Executive verdict"}</p>
          <h3>{toText(executive?.presentation_call || executive?.primary_call, copy.report.empty)}</h3>
          <p>{toText(executive?.presentation_action_summary || executive?.action_summary, copy.report.empty)}</p>
          <div className="chip-row">
            {watchlist.map((item) => (
              <span key={item} className="chip positive">{item}</span>
            ))}
            {avoidList.map((item) => (
              <span key={item} className="chip negative">{item}</span>
            ))}
          </div>
        </article>

        <div className="macro-grid">
          <div className="mini-card">
            <h3>{copy.report.labels.investorMandate}</h3>
            <p>{mandateSummary}</p>
            <p>{copy.report.labels.topPick}: {toText(executive?.top_pick)}</p>
            <p>{copy.report.labels.score}: {formatScore(executive?.mandate_fit_score)}</p>
          </div>
          <div className="mini-card">
            <h3>{copy.report.labels.marketStance}</h3>
            <p>{copy.report.labels.regime}: {toText(macro?.regime)}</p>
            <p>{copy.report.labels.vix}: {toText(macro?.vix)}</p>
            <p>{copy.report.labels.topPick}: {toText(executive?.top_pick)}</p>
            <p>{copy.report.labels.fit}: {formatScore(executive?.mandate_fit_score)}</p>
          </div>
          <div className="mini-card">
            <h3>{copy.report.labels.dataProvenance}</h3>
            <p>{copy.report.labels.source}: {toText(effectiveDataStatus?.source)}</p>
            <p>{copy.report.labels.universeSize}: {toText(effectiveDataStatus?.records)}</p>
            <p>{copy.report.labels.lastRefresh}: {formatDateTime(effectiveDataStatus?.last_refresh_at, locale)}</p>
            {variant === "debug" ? <p>Route: {toText(asRecord(result.runtime)?.route_mode)}</p> : null}
          </div>
        </div>
      </div>

      <div id="report-charts" className="anchor-target">
        <ResearchCharts locale={locale} copy={copy} ranking={ranking} dimensions={dimensions} allocation={allocation} />
      </div>

      <div id="report-scoreboard" className="section-head report-subhead anchor-target">
        <div>
          <p className="eyebrow">{locale === "zh" ? "评分表" : "Scoreboard"}</p>
          <h3>{copy.report.scoreboard}</h3>
        </div>
      </div>
      <div className="report-table-wrap">
        <table className="report-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>{copy.report.labels.company}</th>
              <th>{copy.report.labels.latestPrice}</th>
              <th>{copy.report.labels.score}</th>
              <th>{copy.report.labels.fit}</th>
              <th>{copy.report.labels.valuation}</th>
              <th>{copy.report.labels.quality}</th>
              <th>{copy.report.labels.momentum}</th>
              <th>{copy.report.labels.risk}</th>
              <th>{copy.report.labels.verdict}</th>
            </tr>
          </thead>
          <tbody>
            {scoreboard.map((item) => {
              const verdict = toText(item.verdict_label);
              return (
                <tr key={toText(item.ticker)}>
                  <td>{toText(item.ticker)}</td>
                  <td>{toText(item.company_name)}</td>
                  <td>{toText(item.latest_price)}</td>
                  <td>{formatScore(item.composite_score)}</td>
                  <td>{formatScore(item.suitability_score)}</td>
                  <td>{formatScore(item.valuation_score)}</td>
                  <td>{formatScore(item.quality_score)}</td>
                  <td>{formatScore(item.momentum_score)}</td>
                  <td>{formatScore(item.risk_score)}</td>
                  <td><span className={`chip ${verdictTone(verdict)}`}>{verdict}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div id="report-coverage" className="section-head report-subhead anchor-target">
        <div>
          <p className="eyebrow">{locale === "zh" ? "逐票覆盖" : "Coverage"}</p>
          <h3>{copy.report.tickerCards}</h3>
        </div>
      </div>
      <div className="ticker-card-grid" ref={metricHelpRootRef}>
        {tickerCards.map((item) => {
          const ticker = toText(item.ticker);
          const verdict = toText(item.verdict_label);
          const catalysts = asStringArray(item.catalysts);
          return (
            <article key={ticker} className="candidate-card">
              <div className="candidate-head">
                <div>
                  <p className="candidate-ticker">{ticker}</p>
                  <h3>{toText(item.company_name, ticker)}</h3>
                  <p className="mini-copy">{toText(item.sector)}</p>
                </div>
                <span className={`chip ${verdictTone(verdict)}`}>{verdict}</span>
              </div>

              <div className="candidate-score-row">
                {[
                  { key: "composite", label: copy.report.labels.score, value: item.composite_score },
                  { key: "fit", label: copy.report.labels.fit, value: item.suitability_score },
                  { key: "valuation", label: copy.report.labels.valuation, value: item.valuation_score },
                  { key: "quality", label: copy.report.labels.quality, value: item.quality_score },
                  { key: "momentum", label: copy.report.labels.momentum, value: item.momentum_score },
                  { key: "risk", label: copy.report.labels.risk, value: item.risk_score },
                ].map((metric) => (
                  <div key={metric.label} className={`score-pill ${scoreTone(toNumber(metric.value))}`}>
                    <div className="score-pill-head">
                      <span>{metric.label}</span>
                      {toText(scoreGuide?.[metric.key], "") ? (
                        (() => {
                          const helpId = `${ticker}-${metric.key}`;
                          const isOpen = activeMetricHelpId === helpId;
                          return (
                            <div className="metric-help">
                              <button
                                type="button"
                                className="metric-help-trigger"
                                aria-label={locale === "zh" ? "查看指标说明" : "View metric guide"}
                                onClick={() => setActiveMetricHelpId(isOpen ? null : helpId)}
                              >
                                !
                              </button>
                              {isOpen ? <div className="metric-help-popover">{toText(scoreGuide?.[metric.key], "")}</div> : null}
                            </div>
                          );
                        })()
                      ) : null}
                    </div>
                    <strong>{formatScore(metric.value)}</strong>
                  </div>
                ))}
              </div>

              <div className="candidate-section-stack">
                <section className="candidate-section">
                  <span className="candidate-section-label">{copy.report.labels.thesis}</span>
                  <p className="candidate-copy">{toText(item.thesis)}</p>
                </section>
                <section className="candidate-section">
                  <span className="candidate-section-label">{copy.report.labels.fitReason}</span>
                  <p className="candidate-copy">{toText(item.fit_reason)}</p>
                </section>
              </div>

              {asStringArray(item.evidence_points).length ? (
                <section className="candidate-section">
                  <span className="candidate-section-label">{locale === "zh" ? "依据摘要" : "Evidence summary"}</span>
                  <ul className="compact-list">
                    {asStringArray(item.evidence_points).map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <div className="candidate-detail-grid">
                <section className="candidate-section">
                  <span className="candidate-section-label">{copy.report.labels.technical}</span>
                  <p className="candidate-copy">{toText(item.technical_summary)}</p>
                </section>
                <section className="candidate-section">
                  <span className="candidate-section-label">{copy.report.labels.news}</span>
                  <p className="candidate-copy">
                    {toText(item.news_narrative, toText(item.news_label))}
                    {toText(item.alignment, "") ? ` · ${toText(item.alignment)}` : ""}
                  </p>
                </section>
                <section className="candidate-section">
                  <span className="candidate-section-label">{copy.report.labels.smartMoney}</span>
                  <p className="candidate-copy">{toText(item.smart_money_positioning)}</p>
                </section>
                <section className="candidate-section">
                  <span className="candidate-section-label">{copy.report.labels.audit}</span>
                  <p className="candidate-copy">{toText(item.audit_summary)}</p>
                  {asRecordArray(item.audit_links).length ? (
                    <p className="candidate-copy candidate-link-list">
                      {asRecordArray(item.audit_links).slice(0, 3).map((entry, index) => {
                        const url = toText(entry.filing_url, "");
                        const label = `${toText(entry.form, "SEC")}${toText(entry.filed_at, "") ? ` (${toText(entry.filed_at)})` : ""}`;
                        if (!url) return <span key={`${label}-${index}`}>{label}{index < 2 ? " · " : ""}</span>;
                        return (
                          <span key={`${label}-${index}`}>
                            <a href={url} target="_blank" rel="noreferrer">{label}</a>
                            {index < 2 ? " · " : ""}
                          </span>
                        );
                      })}
                    </p>
                  ) : null}
                </section>
              </div>

              {asStringArray(item.caution_points).length ? (
                <section className="candidate-section">
                  <span className="candidate-section-label">{locale === "zh" ? "谨慎提示" : "Caveats"}</span>
                  <ul className="compact-list">
                    {asStringArray(item.caution_points).map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </section>
              ) : null}

              <div className="candidate-meta-row">
                {toText(item.share_class, "") ? (
                  <span className="chip neutral">
                    {copy.report.labels.shareClass}: {toText(item.share_class)}
                    {toText(item.share_class_note, "") ? ` · ${toText(item.share_class_note)}` : ""}
                  </span>
                ) : null}
                <span className="candidate-source-note">
                  <strong>{copy.report.labels.source}:</strong>{" "}
                  {toText(
                    item.source_summary,
                    locale === "zh"
                      ? `技术 ${sourceAlias(locale, item.technical_source)} | 新闻 ${sourceAlias(locale, item.news_source)} | 资金面 ${sourceAlias(locale, item.smart_money_source)}`
                      : `Tech ${sourceAlias(locale, item.technical_source)} | News ${sourceAlias(locale, item.news_source)} | Smart ${sourceAlias(locale, item.smart_money_source)}`,
                  )}
                </span>
              </div>

              <section className="candidate-section candidate-execution">
                <span className="candidate-section-label">{copy.report.labels.execution}</span>
                <p className="candidate-copy">{toText(item.execution)}</p>
              </section>

              {asRecordArray(item.news_items).length ? (
                <div className="candidate-catalysts">
                  {asRecordArray(item.news_items).slice(0, 3).map((entry, index) => {
                    const title = toText(entry.title, locale === "zh" ? "新闻链接" : "News");
                    const url = toText(entry.url, "");
                    if (!url) {
                      return <span key={`${title}-${index}`} className="catalyst-tag">{title}</span>;
                    }
                    return (
                      <a key={`${title}-${index}`} className="catalyst-tag" href={url} target="_blank" rel="noreferrer">
                        {title}
                      </a>
                    );
                  })}
                </div>
              ) : catalysts.length ? (
                <div className="candidate-catalysts">
                  {catalysts.map((catalyst) => (
                    <span key={catalyst} className="catalyst-tag">{catalyst}</span>
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>

      <div id="report-risks" className="risk-allocation-grid anchor-target">
        <section className="mini-panel">
          <div className="section-head tight">
            <div>
              <p className="eyebrow">{locale === "zh" ? "风险登记" : "Risk register"}</p>
              <h3>{copy.report.risks}</h3>
            </div>
          </div>
          {riskRegister.length ? (
            <div className="risk-list">
              {riskRegister.map((item, index) => (
                <div key={`${toText(item.category)}-${index}`} className="risk-item">
                  <strong>{toText(item.category)}{item.ticker ? ` / ${toText(item.ticker)}` : ""}</strong>
                  <p>{toText(item.summary)}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state small">{copy.report.noRisk}</div>
          )}
        </section>

        <section className="mini-panel">
          <div className="section-head tight">
            <div>
              <p className="eyebrow">{locale === "zh" ? "执行计划" : "Execution"}</p>
              <h3>{copy.report.execution}</h3>
            </div>
          </div>
          <p className="section-note">
            {locale === "zh"
              ? `候选 ${toText(meta?.ticker_count, "0")} 只；执行持仓 ${allocationPlan.length} 只。`
              : `Candidates ${toText(meta?.ticker_count, "0")}; execution positions ${allocationPlan.length}.`}
          </p>
          {allocationPlan.length ? (
            <div className="allocation-list">
              {allocationPlan.map((item) => (
                <div key={toText(item.ticker)} className="allocation-line">
                  <div className="allocation-meta">
                    <strong>{toText(item.ticker)}</strong>
                    <span>{toText(item.verdict)}</span>
                  </div>
                  <div className="allocation-track">
                    <div className="allocation-bar" style={{ width: `${Math.min(toNumber(item.weight) || 0, 100)}%` }} />
                  </div>
                  <span>{toNumber(item.weight)?.toFixed(1) ?? "N/A"}%</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state small">{copy.report.noAllocation}</div>
          )}
        </section>
      </div>

      {finalReport ? (
        <details id="report-memo" className="report-details anchor-target">
          <summary>{copy.report.fullReport}</summary>
          <article className="report-prose">{renderReportMarkdown(finalReport)}</article>
        </details>
      ) : null}

      {variant === "debug" ? (
        <details className="json-details">
          <summary>{copy.report.reportJson}</summary>
          <pre className="json-viewer">{formatJson(reportBriefing)}</pre>
        </details>
      ) : null}
    </section>
  );
}
