import { useEffect, useState } from "react";

import { ArtifactPanel } from "../components/ArtifactPanel";
import { AgentTracePanel } from "../components/AgentTracePanel";
import { BacktestPanel } from "../components/BacktestPanel";
import { ReportPanel } from "../components/ReportPanel";
import { StagePanel } from "../components/StagePanel";
import { resumeRunFromAgent } from "../lib/api";
import { formatDateTime, formatJson, formatRunStatus, formatRunTitle } from "../lib/format";
import { useResearchConsole } from "../hooks";

type GenericRecord = Record<string, unknown>;

function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

export function WorkbenchView() {
  const {
    locale,
    setLocale,
    copy,
    terminalMode,
    asOfDate,
    referenceStartDate,
    historicalBacktestEndDate,
    runtime,
    dataStatus,
    mode,
    setMode,
    agentForm,
    structuredForm,
    history,
    filters,
    activeRunId,
    runDetail,
    artifacts,
    events,
    backtestDetail,
    backtestLoading,
    backtestCreating,
    selectedArtifactId,
    selectedArtifactKind,
    statusText,
    errorText,
    creatingRun,
    cancelingRun,
    retryingRun,
    refreshingData,
    historyLoading,
    historyMutating,
    runLoading,
    setAgentForm,
    setStructuredForm,
    setFilters,
    setSelectedArtifactId,
    setSelectedArtifactKind,
    setReferenceStartDate,
    setHistoricalBacktestEndDate,
    createAgentRun,
    createStructuredRun,
    retryActiveRun,
    cancelActiveRun,
    refreshData,
    clearHistory,
    openRun,
    refreshHistory,
    runBacktest,
    fillAgentSample,
    fillStructuredSample,
  } = useResearchConsole("agent");

  useEffect(() => {
    document.title = copy.debug.title;
  }, [copy.debug.title]);

  const result = runDetail?.result as GenericRecord | null;
  const researchContext = asRecord(result?.research_context);
  const analysis = asRecord(result?.analysis);
  const debugSummary = asRecord(analysis?.debug_summary);
  const backtestMeta = asRecord(backtestDetail?.meta);
  const warningFlags = Array.isArray(debugSummary?.warning_flags) ? debugSummary?.warning_flags.join(", ") : "N/A";
  const [debugTab, setDebugTab] = useState<"overview" | "agents" | "stages" | "artifacts" | "raw">("overview");
  const [resumeBusyAgent, setResumeBusyAgent] = useState<string | null>(null);

  const handleResumeFromAgent = async (agentName: string) => {
    if (!activeRunId || resumeBusyAgent) {
      return;
    }
    setResumeBusyAgent(agentName);
    try {
      const detail = await resumeRunFromAgent(activeRunId, {
        agent_name: agentName,
        reason: "debug resume from agent trace",
      });
      await openRun(detail.run.id);
      setDebugTab("agents");
    } finally {
      setResumeBusyAgent(null);
    }
  };

  return (
    <div className="workspace-shell">
      <header className="workspace-header">
        <div>
          <p className="eyebrow">{copy.meta.brand}</p>
          <h1>{copy.debug.title}</h1>
          <p className="section-note">{copy.debug.subtitle}</p>
        </div>
        <div className="header-actions">
          <label className="field compact-field">
            <span>{copy.meta.languageLabel}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as typeof locale)}>
              <option value="zh">{copy.meta.languageOptions.zh}</option>
              <option value="en">{copy.meta.languageOptions.en}</option>
            </select>
          </label>
          <a className="secondary-button compact-action" href="/terminal">
            {locale === "zh" ? "返回用户前台" : "Back to terminal"}
          </a>
        </div>
      </header>

      {errorText ? <div className="danger-banner">{errorText}</div> : null}
      <div className="executive-banner">{statusText}</div>

      <section className="workspace-layout">
        <aside className="workspace-sidebar">
          <section className="panel-surface">
            <div className="section-head tight">
              <div>
                <p className="eyebrow">{copy.control.launchpad}</p>
                <h2>{copy.control.launchpadTitle}</h2>
              </div>
            </div>
            <div className="button-row compact">
              <button
                type="button"
                className={mode === "agent" ? "primary-button compact-action" : "secondary-button compact-action"}
                onClick={() => setMode("agent")}
              >
                {copy.control.tabs.agent}
              </button>
              <button
                type="button"
                className={mode === "structured" ? "primary-button compact-action" : "secondary-button compact-action"}
                onClick={() => setMode("structured")}
              >
                {copy.control.tabs.structured}
              </button>
            </div>

            {mode === "agent" ? (
              <>
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
                  <button type="button" className="primary-button compact-action" disabled={creatingRun} onClick={() => void createAgentRun()}>
                    {creatingRun ? copy.actions.running : copy.actions.runAgent}
                  </button>
                  <button type="button" className="secondary-button compact-action" onClick={fillAgentSample}>
                    {copy.actions.sample}
                  </button>
                </div>
              </>
            ) : (
              <>
                <label className="field">
                  <span>{copy.control.fields.tickers}</span>
                  <textarea value={structuredForm.tickers} onChange={(event) => setStructuredForm({ tickers: event.target.value })} />
                </label>
                <div className="button-row">
                  <button type="button" className="primary-button compact-action" disabled={creatingRun} onClick={() => void createStructuredRun()}>
                    {creatingRun ? copy.actions.running : copy.actions.runStructured}
                  </button>
                  <button type="button" className="secondary-button compact-action" onClick={fillStructuredSample}>
                    {copy.actions.sample}
                  </button>
                </div>
              </>
            )}
          </section>

          <section className="panel-surface">
            <div className="section-head tight">
              <div>
                <p className="eyebrow">{copy.history.eyebrow}</p>
                <h2>{copy.history.title}</h2>
              </div>
            </div>
            <div className="field-grid">
              <label className="field compact-field">
                <span>{copy.history.search}</span>
                <input value={filters.search} onChange={(event) => setFilters({ search: event.target.value })} />
              </label>
              <label className="field compact-field">
                <span>{copy.history.mode}</span>
                <select value={filters.mode} onChange={(event) => setFilters({ mode: event.target.value })}>
                  <option value="">{copy.history.all}</option>
                  <option value="agent">agent</option>
                  <option value="structured">structured</option>
                </select>
              </label>
              <label className="field compact-field">
                <span>{copy.history.status}</span>
                <select value={filters.status} onChange={(event) => setFilters({ status: event.target.value })}>
                  <option value="">{copy.history.all}</option>
                  <option value="queued">queued</option>
                  <option value="running">running</option>
                  <option value="completed">completed</option>
                  <option value="failed">failed</option>
                  <option value="cancelled">cancelled</option>
                  <option value="needs_clarification">needs_clarification</option>
                </select>
              </label>
            </div>
            <div className="button-row compact">
              <button type="button" className="secondary-button compact-action" disabled={historyLoading} onClick={() => void refreshHistory()}>
                {historyLoading ? copy.history.sync : copy.actions.refresh}
              </button>
              <button type="button" className="danger-button compact-action" disabled={historyMutating} onClick={() => void clearHistory()}>
                {historyMutating ? copy.actions.running : copy.actions.clear}
              </button>
            </div>
            <div className="history-list">
              {history.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={item.id === activeRunId ? "history-item active" : "history-item"}
                  onClick={() => void openRun(item.id)}
                >
                  <div className="history-title-row">
                    <strong>{formatRunTitle(item.title, locale)}</strong>
                    <span className={`status-badge status-${item.status}`}>{formatRunStatus(item.status, locale)}</span>
                  </div>
                  <p>{formatDateTime(item.updated_at, locale)}</p>
                </button>
              ))}
            </div>
          </section>
        </aside>

        <main className="workspace-main">
          <section className="panel-surface">
            <div className="section-head">
              <div>
                <p className="eyebrow">{copy.run.eyebrow}</p>
                <h2>{runDetail ? formatRunTitle(runDetail.run.title, locale) : copy.run.empty}</h2>
              </div>
              <div className="button-row compact">
                <button type="button" className="secondary-button compact-action" disabled={!activeRunId || retryingRun} onClick={() => void retryActiveRun()}>
                  {retryingRun ? copy.actions.retrying : copy.actions.retry}
                </button>
                <button
                  type="button"
                  className="ghost-danger-button compact-action"
                  disabled={!activeRunId || !(runDetail?.run.status === "queued" || runDetail?.run.status === "running") || cancelingRun}
                  onClick={() => void cancelActiveRun()}
                >
                  {cancelingRun ? copy.actions.cancelling : copy.actions.cancel}
                </button>
                <button type="button" className="secondary-button compact-action" disabled={refreshingData} onClick={() => void refreshData()}>
                  {refreshingData ? copy.actions.running : copy.actions.refresh}
                </button>
              </div>
            </div>

            <div className="summary-grid">
              <div className="mini-card">
                <span className="mini-label">{copy.debug.fieldLabels.researchMode}</span>
                <strong>{String(researchContext?.research_mode || terminalMode)}</strong>
                <p>{copy.debug.fieldLabels.asOfDate}: {String(researchContext?.as_of_date || asOfDate || "N/A")}</p>
              </div>
              <div className="mini-card">
                <span className="mini-label">{copy.debug.fieldLabels.backtestKind}</span>
                <strong>{String(backtestMeta?.backtest_kind || "N/A")}</strong>
                <p>{copy.debug.fieldLabels.warningFlags}: {String(backtestMeta?.warning_flags || warningFlags)}</p>
              </div>
              <div className="mini-card">
                <span className="mini-label">{copy.debug.fieldLabels.runtime}</span>
                <strong>{runtime?.provider || "N/A"}</strong>
                <p>{copy.debug.fieldLabels.routeBilling}: {runtime?.route_mode || "N/A"} / {runtime?.billing_mode || "N/A"}</p>
              </div>
              <div className="mini-card">
                <span className="mini-label">{copy.debug.fieldLabels.market}</span>
                <strong>{dataStatus?.source || "N/A"}</strong>
                <p>{copy.debug.fieldLabels.records}: {dataStatus?.records || 0}</p>
              </div>
            </div>
          </section>

          <section className="panel-surface">
            <div className="front-side-tab-header">
              <button
                type="button"
                className={debugTab === "overview" ? "side-tab active" : "side-tab"}
                onClick={() => setDebugTab("overview")}
              >
                {copy.debug.tabs.overview}
              </button>
              <button
                type="button"
                className={debugTab === "stages" ? "side-tab active" : "side-tab"}
                onClick={() => setDebugTab("stages")}
              >
                {copy.debug.tabs.stages}
              </button>
              <button
                type="button"
                className={debugTab === "agents" ? "side-tab active" : "side-tab"}
                onClick={() => setDebugTab("agents")}
              >
                {copy.debug.tabs.agents}
              </button>
              <button
                type="button"
                className={debugTab === "artifacts" ? "side-tab active" : "side-tab"}
                onClick={() => setDebugTab("artifacts")}
              >
                {copy.debug.tabs.artifacts}
              </button>
              <button
                type="button"
                className={debugTab === "raw" ? "side-tab active" : "side-tab"}
                onClick={() => setDebugTab("raw")}
              >
                {copy.debug.tabs.rawJson}
              </button>
            </div>
          </section>

          {debugTab === "overview" ? (
            <>
              <section className="panel-surface">
                <div className="section-head tight">
                  <div>
                    <p className="eyebrow">{copy.debug.overviewTitle}</p>
                    <h3>{copy.debug.overviewSubtitle}</h3>
                  </div>
                </div>
              </section>
              <ReportPanel locale={locale} copy={copy} result={result} dataStatus={dataStatus} variant="debug" />
              <BacktestPanel
                locale={locale}
                copy={copy}
                activeRunId={activeRunId}
                runStatus={runDetail?.run.status}
                backtest={backtestDetail}
                mode={terminalMode === "historical" ? "replay" : "reference"}
                endDate={terminalMode === "historical" ? historicalBacktestEndDate : new Date().toISOString().slice(0, 10)}
                entryDate={terminalMode === "realtime" ? referenceStartDate : undefined}
                loading={backtestLoading}
                creating={backtestCreating}
                onEndDateChange={terminalMode === "historical" ? setHistoricalBacktestEndDate : () => {}}
                onEntryDateChange={terminalMode === "realtime" ? setReferenceStartDate : undefined}
                onRunBacktest={runBacktest}
              />
            </>
          ) : null}

          {debugTab === "stages" ? <StagePanel locale={locale} copy={copy} steps={runDetail?.steps || []} /> : null}

          {debugTab === "agents" ? (
            <AgentTracePanel
              locale={locale}
              trace={result?.agent_trace}
              runId={activeRunId}
              resumeBusyAgent={resumeBusyAgent}
              onResumeFromAgent={handleResumeFromAgent}
            />
          ) : null}

          {debugTab === "artifacts" ? (
            <ArtifactPanel
              locale={locale}
              copy={copy}
              artifacts={artifacts}
              selectedArtifactId={selectedArtifactId}
              selectedKind={selectedArtifactKind}
              onSelectArtifact={setSelectedArtifactId}
              onSelectKind={setSelectedArtifactKind}
            />
          ) : null}

          {debugTab === "raw" ? (
            <section className="panel-surface">
              <div className="section-head tight">
                <div>
                  <p className="eyebrow">{copy.run.liveEvents}</p>
                  <h3>{copy.debug.tabs.rawJson}</h3>
                </div>
              </div>
              <pre className="json-viewer">{formatJson({ events, result, run: runDetail?.run, runLoading })}</pre>
            </section>
          ) : null}
        </main>
      </section>
    </div>
  );
}
