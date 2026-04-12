import { useEffect } from "react";

import { ArtifactPanel } from "../components/ArtifactPanel";
import { ReportPanel } from "../components/ReportPanel";
import { StagePanel } from "../components/StagePanel";
import { formatDateTime, formatJson, formatRunStatus, formatRunTitle, repairText } from "../lib/format";
import { useResearchConsole } from "../hooks/useResearchConsole";

type GenericRecord = Record<string, unknown>;

function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

function toText(value: unknown, fallback = "N/A"): string {
  return repairText(value, fallback);
}

export function TerminalView() {
  const {
    locale,
    setLocale,
    dataStatus,
    copy,
    agentForm,
    history,
    activeRunId,
    runDetail,
    artifacts,
    selectedArtifactId,
    selectedArtifactKind,
    errorText,
    creatingRun,
    refreshingData,
    historyLoading,
    runLoading,
    setAgentForm,
    setSelectedArtifactId,
    setSelectedArtifactKind,
    createAgentRun,
    refreshData,
    openRun,
    fillAgentSample,
  } = useResearchConsole("agent");

  useEffect(() => {
    if (!activeRunId && !historyLoading && history.length) {
      void openRun(history[0].id);
    }
  }, [activeRunId, historyLoading, history, openRun]);

  useEffect(() => {
    document.title = locale === "zh" ? "金融研究终端" : "Investment Research Terminal";
  }, [locale]);

  const result = runDetail?.result || null;
  const parsedIntent = asRecord(result?.parsed_intent);
  const agentControl = asRecord(parsedIntent?.agent_control);
  const portfolioSizing = asRecord(parsedIntent?.portfolio_sizing);
  const riskProfile = asRecord(parsedIntent?.risk_profile);
  const investmentStrategy = asRecord(parsedIntent?.investment_strategy);
  const explicitTargets = asRecord(parsedIntent?.explicit_targets);
  const reportBriefing = asRecord(result?.report_briefing);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const meta = asRecord(reportBriefing?.meta);
  const dataProvenance = asRecord(meta?.data_provenance);

  const liveSourceCount = dataStatus?.live_sources.length ?? 0;
  const exchangeSummaryEntries = Object.entries(dataStatus?.exchange_summary || {}).slice(0, 6);
  const archivePreview = history.slice(0, 5);
  const assumptions = asStringArray(meta?.assumptions || result?.assumptions);
  const watchlist = asStringArray(executive?.watchlist);
  const avoidList = asStringArray(executive?.avoid_list);
  const missingInfo = asStringArray(agentControl?.missing_critical_info);

  const topPick = toText(executive?.top_pick, locale === "zh" ? "等待研究结果" : "Awaiting research result");
  const primaryCall = toText(
    executive?.primary_call,
    locale === "zh"
      ? "输入你的投资目标后，这里会给出最重要的结论。"
      : "Enter an investment goal to see the primary research call.",
  );
  const actionSummary = toText(
    executive?.action_summary,
    locale === "zh" ? "当前还没有完成的研究结果。" : "No completed research result is available yet.",
  );
  const mandateFit = toText(executive?.mandate_fit_score, "N/A");
  const marketStance = toText(executive?.market_stance, locale === "zh" ? "待研究" : "Pending");
  const regime = toText(macro?.regime || dataStatus?.macro_status?.regime, locale === "zh" ? "待刷新" : "Pending");
  const macroSource = toText(dataStatus?.macro_status?.source, locale === "zh" ? "待刷新" : "Pending");

  const requestStatus = !agentControl
    ? locale === "zh"
      ? "等待识别"
      : "Waiting"
    : agentControl?.is_intent_clear
      ? locale === "zh"
        ? "可直接分析"
        : "Ready"
      : agentControl?.is_intent_usable
        ? locale === "zh"
          ? "已带默认假设继续分析"
          : "Usable with assumptions"
        : locale === "zh"
          ? "需要补充信息"
          : "Needs clarification";

  const intentBrief = [
    {
      label: locale === "zh" ? "资金规模" : "Capital",
      value:
        portfolioSizing?.capital_amount && portfolioSizing?.currency
          ? `${toText(portfolioSizing.capital_amount)} ${toText(portfolioSizing.currency)}`
          : locale === "zh"
            ? "未识别"
            : "Not detected",
    },
    {
      label: locale === "zh" ? "风险偏好" : "Risk",
      value: toText(riskProfile?.tolerance_level, locale === "zh" ? "未识别" : "Not detected"),
    },
    {
      label: locale === "zh" ? "持有期限" : "Horizon",
      value: toText(investmentStrategy?.horizon, locale === "zh" ? "未识别" : "Not detected"),
    },
    {
      label: locale === "zh" ? "投资风格" : "Style",
      value: toText(investmentStrategy?.style, locale === "zh" ? "未识别" : "Not detected"),
    },
    {
      label: locale === "zh" ? "明确标的" : "Targets",
      value: asStringArray(explicitTargets?.tickers).join(", ") || (locale === "zh" ? "未指定" : "None"),
    },
  ];

  const frontStatusText = creatingRun
    ? locale === "zh"
      ? "正在生成新的投资研究报告，请稍等。"
      : "Generating a new investment research memo."
    : runLoading
      ? locale === "zh"
        ? "正在加载最新研究结果。"
        : "Loading the latest research result."
      : runDetail
        ? locale === "zh"
          ? "当前显示的是最近一次研究结果。你可以继续细化需求，或基于新目标重新生成报告。"
          : "You are viewing the latest research result. Refine the mandate or generate a new report."
        : locale === "zh"
          ? "输入投资目标后，即可生成正式研究报告。"
          : "Enter an investment goal to generate a formal research report.";

  return (
    <div className="terminal-front-shell">
      <header className="front-topbar">
        <div className="front-brand">
          <p className="eyebrow">{copy.meta.brand}</p>
          <strong>{locale === "zh" ? "金融研究终端" : "Investment Research Terminal"}</strong>
        </div>

        <div className="front-topbar-actions">
          <nav className="front-topbar-nav">
            <a href="#terminal-market">{locale === "zh" ? "市场" : "Market"}</a>
            <a href="#report-overview">{locale === "zh" ? "报告" : "Report"}</a>
            <a href="#terminal-archive">{locale === "zh" ? "历史" : "Archive"}</a>
          </nav>
          <label className="field compact-field front-locale-field">
            <span>{copy.meta.languageLabel}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as typeof locale)}>
              <option value="zh">{copy.meta.languageOptions.zh}</option>
              <option value="en">{copy.meta.languageOptions.en}</option>
            </select>
          </label>
          <a className="front-quiet-link" href="/debug">
            {locale === "zh" ? "调试台" : "Debug"}
          </a>
        </div>
      </header>

      <section className="front-market-strip terminal-market-header" id="terminal-market">
        <article className="panel-surface market-strip-card">
          <span className="mini-label">{locale === "zh" ? "股票池规模" : "Coverage"}</span>
          <strong>{dataStatus?.records ?? "N/A"}</strong>
          <p>{toText(dataStatus?.source, locale === "zh" ? "待初始化" : "Pending")}</p>
        </article>
        <article className="panel-surface market-strip-card">
          <span className="mini-label">{locale === "zh" ? "覆盖范围" : "Universe"}</span>
          <strong>{toText(dataStatus?.universe_scope, locale === "zh" ? "待确认" : "Pending")}</strong>
          <p>{exchangeSummaryEntries.map(([exchange, count]) => `${exchange} ${count}`).join(" | ") || "N/A"}</p>
        </article>
        <article className="panel-surface market-strip-card">
          <span className="mini-label">{locale === "zh" ? "宏观环境" : "Macro"}</span>
          <strong>{regime}</strong>
          <p>{macroSource}</p>
        </article>
        <article className="panel-surface market-strip-card market-strip-action">
          <span className="mini-label">{locale === "zh" ? "最近刷新" : "Last refresh"}</span>
          <strong>{formatDateTime(dataStatus?.last_refresh_at, locale)}</strong>
          <p>{locale === "zh" ? `数据源 ${liveSourceCount}` : `${liveSourceCount} live sources`}</p>
          <div className="button-row compact">
            <button type="button" className="secondary-button compact-action" disabled={refreshingData} onClick={() => void refreshData()}>
              {refreshingData ? copy.actions.running : locale === "zh" ? "刷新市场数据" : "Refresh market data"}
            </button>
          </div>
        </article>
      </section>

      <section className="front-query-grid">
        <article className="panel-surface front-query-card">
          <div className="section-head">
            <div>
              <p className="eyebrow">{locale === "zh" ? "投资目标" : "Investment goal"}</p>
              <h2>{locale === "zh" ? "告诉我您想解决什么投资问题" : "Describe the investment question to solve"}</h2>
              <p className="section-note">
                {locale === "zh"
                  ? "尽量写清资金规模、风险偏好、持有期限和想比较的标的，系统会自动生成正式研究报告。"
                  : "Include capital, risk, horizon and target names when possible. The desk will convert it into a formal memo."}
              </p>
            </div>
          </div>

          <label className="field">
            <span>{copy.control.fields.query}</span>
            <textarea
              value={agentForm.query}
              placeholder={copy.control.placeholders.query}
              onChange={(event) => setAgentForm({ query: event.target.value })}
            />
          </label>

          <div className="field-grid">
            <label className="field compact-field">
              <span>{copy.control.fields.maxResults}</span>
              <input
                type="number"
                min={1}
                max={12}
                value={agentForm.maxResults}
                onChange={(event) => setAgentForm({ maxResults: Number(event.target.value) || 5 })}
              />
            </label>
            <label className="toggle-field">
              <span>{copy.control.fields.liveData}</span>
              <input
                type="checkbox"
                checked={agentForm.fetchLiveData}
                onChange={(event) => setAgentForm({ fetchLiveData: event.target.checked })}
              />
            </label>
          </div>

          <div className="button-row">
            <button type="button" className="primary-button" disabled={creatingRun} onClick={() => void createAgentRun()}>
              {creatingRun ? copy.actions.running : locale === "zh" ? "开始研究" : "Start research"}
            </button>
            <button type="button" className="secondary-button" onClick={fillAgentSample}>
              {locale === "zh" ? "填入示例" : "Use sample"}
            </button>
          </div>

          <div className="front-example-row">
            <button
              type="button"
              className="front-example-chip"
              onClick={() =>
                setAgentForm({
                  query:
                    locale === "zh"
                      ? "我有 100000 美元，希望找能在风险可控前提下长期持有的高质量蓝筹股，并给出分批建仓建议。"
                      : "I have 100000 USD and want high-quality blue chips for long-term holding with controlled risk. Give me staged entry advice.",
                })
              }
            >
              {locale === "zh" ? "长期核心持仓" : "Long-term core holdings"}
            </button>
            <button
              type="button"
              className="front-example-chip"
              onClick={() =>
                setAgentForm({
                  query:
                    locale === "zh"
                      ? "请比较美国消费防御板块里适合低波动分红策略的候选股，并标出应回避的名字。"
                      : "Compare defensive consumer names in the US that fit a low-volatility dividend strategy and flag which ones to avoid.",
                })
              }
            >
              {locale === "zh" ? "分红防御策略" : "Dividend defense"}
            </button>
            <button
              type="button"
              className="front-example-chip"
              onClick={() =>
                setAgentForm({
                  query:
                    locale === "zh"
                      ? "我想做一份适合展示的投资研究报告，请给出结论、风险和图表化摘要。"
                      : "Generate a presentation-ready investment memo with verdicts, risks and visual summaries.",
                })
              }
            >
              {locale === "zh" ? "展示型研究报告" : "Presentation memo"}
            </button>
          </div>
        </article>

        <article className="panel-surface front-brief-card">
          <p className="eyebrow">{locale === "zh" ? "本次建议" : "Current recommendation"}</p>
          <h2>{topPick}</h2>
          <p className="lead-copy">{primaryCall}</p>
          <p className="section-note">{actionSummary}</p>

          {(watchlist.length || avoidList.length) ? (
            <div className="chip-row">
              {watchlist.map((item) => (
                <span key={`watch-${item}`} className="chip positive">
                  {locale === "zh" ? "关注" : "Watch"} {item}
                </span>
              ))}
              {avoidList.map((item) => (
                <span key={`avoid-${item}`} className="chip negative">
                  {locale === "zh" ? "回避" : "Avoid"} {item}
                </span>
              ))}
            </div>
          ) : null}

          <div className="front-idea-grid front-kpi-grid">
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "市场环境" : "Market stance"}</span>
              <strong>{marketStance}</strong>
              <p>{locale === "zh" ? `宏观 ${regime}` : `Macro: ${regime}`}</p>
            </div>
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "目标匹配度" : "Mandate fit"}</span>
              <strong>{mandateFit}</strong>
              <p>{locale === "zh" ? "当前结论与投资目标的匹配程度" : "How well the recommendation fits the mandate"}</p>
            </div>
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "需求识别" : "Mandate status"}</span>
              <strong>{requestStatus}</strong>
              <p>{locale === "zh" ? "当前信息是否足够直接完成分析" : "Whether the request is ready for direct analysis"}</p>
            </div>
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "执行方式" : "Execution mode"}</span>
              <strong>{assumptions.length ? (locale === "zh" ? "带默认假设分析" : "Assumption-assisted") : topPick}</strong>
              <p>{locale === "zh" ? `实时源 ${liveSourceCount}` : `${liveSourceCount} live sources`}</p>
            </div>
          </div>
        </article>
      </section>

      {errorText ? <div className="danger-banner">{errorText}</div> : null}
      <div className="executive-banner">{frontStatusText}</div>

      <nav className="front-section-nav">
        <a href="#terminal-market" className="front-section-link">{locale === "zh" ? "市场" : "Market"}</a>
        <a href="#report-overview" className="front-section-link">{locale === "zh" ? "结论" : "Verdict"}</a>
        <a href="#report-scoreboard" className="front-section-link">{locale === "zh" ? "候选池" : "Coverage"}</a>
        <a href="#report-risks" className="front-section-link">{locale === "zh" ? "风险" : "Risk"}</a>
        <a href="#terminal-archive" className="front-section-link">{locale === "zh" ? "历史报告" : "Archive"}</a>
        <a href="#terminal-evidence" className="front-section-link">{locale === "zh" ? "数据依据" : "Evidence"}</a>
      </nav>

      <section className="front-main-grid">
        <div className="front-report-column">
          <ReportPanel locale={locale} copy={copy} result={result} dataStatus={dataStatus} variant="terminal" />
        </div>

        <aside className="front-side-column">
          <section className="panel-surface front-side-card">
            <div className="section-head tight">
              <div>
                <p className="eyebrow">{locale === "zh" ? "需求识别" : "Mandate brief"}</p>
                <h2>{locale === "zh" ? "系统如何理解你的目标" : "How the system reads your request"}</h2>
              </div>
            </div>

            <div className="front-quick-list">
              {intentBrief.map((item) => (
                <div key={item.label} className="front-quick-item">
                  <span>{item.label}</span>
                  <strong>{item.value}</strong>
                </div>
              ))}
            </div>

            {assumptions.length ? (
              <div className="warning-banner compact-banner">
                <strong>{locale === "zh" ? "本次采用的默认假设：" : "Assumptions:"}</strong> {assumptions.join(locale === "zh" ? "；" : "; ")}
              </div>
            ) : null}

            {!agentControl?.is_intent_usable && missingInfo.length ? (
              <div className="danger-banner compact-banner">
                {locale === "zh" ? "仍需补充：" : "Still missing:"} {missingInfo.join(", ")}
              </div>
            ) : null}
          </section>

          <section className="panel-surface front-side-card">
            <div className="section-head tight">
              <div>
                <p className="eyebrow">{locale === "zh" ? "报告状态" : "Report status"}</p>
                <h2>{locale === "zh" ? "当前结果概览" : "Current result snapshot"}</h2>
              </div>
            </div>

            <div className="front-quick-list">
              <div className="front-quick-item">
                <span>{locale === "zh" ? "标题" : "Title"}</span>
                <strong>{runDetail ? formatRunTitle(runDetail.run.title, locale) : locale === "zh" ? "暂无" : "N/A"}</strong>
              </div>
              <div className="front-quick-item">
                <span>{locale === "zh" ? "状态" : "Status"}</span>
                <strong>{runDetail ? formatRunStatus(runDetail.run.status, locale) : locale === "zh" ? "待运行" : "Waiting"}</strong>
              </div>
              <div className="front-quick-item">
                <span>{locale === "zh" ? "更新时间" : "Updated"}</span>
                <strong>{runDetail ? formatDateTime(runDetail.run.updated_at, locale) : formatDateTime(undefined, locale)}</strong>
              </div>
              <div className="front-quick-item">
                <span>{locale === "zh" ? "主要数据源" : "Primary source"}</span>
                <strong>{toText(dataProvenance?.source || dataStatus?.source)}</strong>
              </div>
            </div>
          </section>

          <details id="terminal-archive" className="panel-surface front-side-card archive-drawer anchor-target" open>
            <summary className="archive-drawer-head">
              <div>
                <p className="eyebrow">{locale === "zh" ? "历史报告" : "Archive"}</p>
                <h2>{locale === "zh" ? "最近研究记录" : "Recent reports"}</h2>
              </div>
              <span className="chip neutral">{archivePreview.length}</span>
            </summary>

            <div className="front-archive-list">
              {archivePreview.length ? (
                archivePreview.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className={item.id === activeRunId ? "front-archive-item active" : "front-archive-item"}
                    onClick={() => void openRun(item.id)}
                  >
                    <div className="history-title-row">
                      <strong>{formatRunTitle(item.title, locale)}</strong>
                      <span className={`status-badge status-${item.status}`}>{formatRunStatus(item.status, locale)}</span>
                    </div>
                    <p className="mini-copy">{formatDateTime(item.updated_at, locale)}</p>
                  </button>
                ))
              ) : (
                <div className="empty-state small">{locale === "zh" ? "暂时还没有可打开的历史报告。" : "No archived research is available yet."}</div>
              )}
            </div>
          </details>
        </aside>
      </section>

      <details id="terminal-evidence" className="panel-surface evidence-drawer anchor-target">
        <summary>
          <div>
            <p className="eyebrow">{locale === "zh" ? "数据依据" : "Evidence"}</p>
            <h2>{locale === "zh" ? "查看数据来源与分析依据" : "Inspect the data sources and analysis basis"}</h2>
          </div>
        </summary>

        <div className="evidence-drawer-body">
          <div className="button-row compact">
            <a className="secondary-button compact-action" href="/debug">
              {locale === "zh" ? "进入开发者视图" : "Open developer view"}
            </a>
          </div>

          <div className="debug-grid">
            <StagePanel locale={locale} copy={copy} steps={runDetail?.steps || []} />
            <ArtifactPanel
              locale={locale}
              copy={copy}
              artifacts={artifacts}
              selectedArtifactId={selectedArtifactId}
              selectedKind={selectedArtifactKind}
              onSelectArtifact={setSelectedArtifactId}
              onSelectKind={setSelectedArtifactKind}
            />
          </div>

          <details className="raw-details">
            <summary>{locale === "zh" ? "查看当前结果的 JSON 快照" : "View the current result as JSON"}</summary>
            <pre className="json-viewer">{formatJson(runDetail?.result || null)}</pre>
          </details>
        </div>
      </details>
    </div>
  );
}
