import { useEffect } from "react";

import { ArtifactPanel } from "../components/ArtifactPanel";
import { ControlPanel } from "../components/ControlPanel";
import { HistoryPanel } from "../components/HistoryPanel";
import { ReportPanel } from "../components/ReportPanel";
import { RunSummary } from "../components/RunSummary";
import { StagePanel } from "../components/StagePanel";
import { formatJson } from "../lib/format";
import { useResearchConsole } from "../hooks/useResearchConsole";

export function WorkbenchView() {
  const {
    locale,
    setLocale,
    copy,
    mode,
    setMode,
    runtime,
    dataStatus,
    agentForm,
    structuredForm,
    history,
    filters,
    activeRunId,
    runDetail,
    artifacts,
    events,
    selectedArtifactId,
    selectedArtifactKind,
    statusText,
    errorText,
    creatingRun,
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
    createAgentRun,
    createStructuredRun,
    retryActiveRun,
    refreshData,
    clearHistory,
    openRun,
    refreshHistory,
    fillAgentSample,
    fillStructuredSample,
  } = useResearchConsole("agent");

  useEffect(() => {
    document.title = locale === "zh" ? "金融 Agent 调试台" : "Financial Agent Debug Console";
  }, [locale]);

  return (
    <div className="terminal-shell">
      <header className="terminal-header">
        <div>
          <p className="eyebrow">{copy.meta.brand}</p>
          <h1>{copy.debug.title}</h1>
          <p className="terminal-subtitle">{copy.debug.subtitle}</p>
        </div>

        <div className="terminal-header-actions">
          <label className="field compact-field">
            <span>{copy.meta.languageLabel}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as typeof locale)}>
              <option value="zh">{copy.meta.languageOptions.zh}</option>
              <option value="en">{copy.meta.languageOptions.en}</option>
            </select>
          </label>
        </div>
      </header>

      <section className="terminal-banner">
        <div>
          <p className="eyebrow">{copy.meta.debugMode}</p>
          <h2>{statusText}</h2>
          <p className="section-note">
            {locale === "zh"
              ? "这里保留完整运行态、阶段时间线、中间产物和原始快照，适合内部联调与问题排查。"
              : "This view keeps the full runtime, stage timeline, artifacts and raw snapshots for internal debugging."}
          </p>
        </div>
        <div className="chip-row">
          {runtime ? <span className="chip">{runtime.route_mode}</span> : null}
          {runtime ? <span className="chip">{runtime.model}</span> : null}
          <span className="chip">{mode === "agent" ? copy.control.tabs.agent : copy.control.tabs.structured}</span>
        </div>
      </section>

      {errorText ? <div className="danger-banner terminal-alert">{errorText}</div> : null}

      <div className="terminal-grid">
        <aside className="launchpad-column">
          <ControlPanel
            locale={locale}
            copy={copy}
            mode={mode}
            runtime={runtime}
            dataStatus={dataStatus}
            agentForm={agentForm}
            structuredForm={structuredForm}
            busy={creatingRun}
            refreshingData={refreshingData}
            onModeChange={setMode}
            onAgentChange={setAgentForm}
            onStructuredChange={setStructuredForm}
            onSubmitAgent={() => void createAgentRun()}
            onSubmitStructured={() => void createStructuredRun()}
            onFillAgentSample={fillAgentSample}
            onFillStructuredSample={fillStructuredSample}
            onRefreshData={() => void refreshData()}
          />
        </aside>

        <main className="research-column">
          <RunSummary
            locale={locale}
            copy={copy}
            detail={runDetail}
            events={events}
            loading={runLoading}
            retrying={retryingRun}
            onRetry={() => void retryActiveRun()}
          />
          <ReportPanel locale={locale} copy={copy} result={runDetail?.result || null} dataStatus={dataStatus} variant="debug" />
        </main>

        <aside className="monitor-column">
          <HistoryPanel
            locale={locale}
            copy={copy}
            items={history}
            filters={filters}
            activeRunId={activeRunId}
            loading={historyLoading}
            mutating={historyMutating}
            onFilterChange={setFilters}
            onRefresh={() => void refreshHistory()}
            onClear={() => void clearHistory()}
            onOpen={(runId) => void openRun(runId)}
          />
        </aside>
      </div>

      <section className="debug-zone">
        <div className="section-head">
          <div>
            <p className="eyebrow">{copy.meta.debugMode}</p>
            <h2>{copy.debug.title}</h2>
            <p className="section-note">{copy.debug.subtitle}</p>
          </div>
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
          <summary>{copy.debug.rawJson}</summary>
          <pre className="json-viewer">{formatJson(runDetail?.result || null)}</pre>
        </details>
      </section>
    </div>
  );
}
