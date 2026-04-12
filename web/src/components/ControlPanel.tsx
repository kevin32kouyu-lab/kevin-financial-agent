import type { AgentFormState, DataStatus, Locale, RunMode, RuntimeConfig, StructuredFormState } from "../lib/types";
import type { LocalePack } from "../lib/i18n";
import { formatDateTime, repairText } from "../lib/format";

interface ControlPanelProps {
  locale: Locale;
  copy: LocalePack;
  mode: RunMode;
  runtime: RuntimeConfig | null;
  dataStatus: DataStatus | null;
  agentForm: AgentFormState;
  structuredForm: StructuredFormState;
  busy: boolean;
  refreshingData: boolean;
  onModeChange: (mode: RunMode) => void;
  onAgentChange: (patch: Partial<AgentFormState>) => void;
  onStructuredChange: (patch: Partial<StructuredFormState>) => void;
  onSubmitAgent: () => void;
  onSubmitStructured: () => void;
  onFillAgentSample: () => void;
  onFillStructuredSample: () => void;
  onRefreshData: () => void;
}

function boolText(value: boolean, locale: Locale) {
  return locale === "zh" ? (value ? "已开启" : "已关闭") : value ? "On" : "Off";
}

function dataRefreshButtonText(locale: Locale, refreshingData: boolean) {
  if (refreshingData) {
    return locale === "zh" ? "刷新中..." : "Refreshing...";
  }
  return locale === "zh" ? "刷新市场缓存" : "Refresh market cache";
}

export function ControlPanel({
  locale,
  copy,
  mode,
  runtime,
  dataStatus,
  agentForm,
  structuredForm,
  busy,
  refreshingData,
  onModeChange,
  onAgentChange,
  onStructuredChange,
  onSubmitAgent,
  onSubmitStructured,
  onFillAgentSample,
  onFillStructuredSample,
  onRefreshData,
}: ControlPanelProps) {
  return (
    <section className="panel-surface launchpad-surface">
      <div className="section-copy">
        <p className="eyebrow">{copy.control.launchpad}</p>
        <h2>{copy.control.launchpadTitle}</h2>
        <p className="section-note">{copy.control.launchpadNote}</p>
      </div>

      <div className="mode-switch">
        <button
          type="button"
          className={mode === "agent" ? "mode-button active" : "mode-button"}
          onClick={() => onModeChange("agent")}
        >
          {copy.control.tabs.agent}
        </button>
        <button
          type="button"
          className={mode === "structured" ? "mode-button active" : "mode-button"}
          onClick={() => onModeChange("structured")}
        >
          {copy.control.tabs.structured}
        </button>
      </div>

      {runtime ? (
        <section className="subsurface-card">
          <div className="subsurface-head">
            <div>
              <p className="eyebrow">{copy.control.runtime}</p>
              <h3>{copy.control.runtimeTitle}</h3>
            </div>
          </div>
          <div className="chip-row">
            <span className="chip">{runtime.provider}</span>
            <span className="chip">{runtime.route_mode}</span>
            <span className="chip">{runtime.billing_mode}</span>
            <span className={runtime.api_key_configured ? "chip positive" : "chip negative"}>
              {runtime.api_key_configured
                ? locale === "zh"
                  ? "API Key 已配置"
                  : "API Key Ready"
                : locale === "zh"
                  ? "API Key 未配置"
                  : "API Key Missing"}
            </span>
          </div>
          <div className="meta-stack">
            <div className="meta-line">
              <span>Model</span>
              <strong>{repairText(runtime.model)}</strong>
            </div>
            <div className="meta-line">
              <span>Base URL</span>
              <strong>{repairText(runtime.base_url)}</strong>
            </div>
          </div>
        </section>
      ) : null}

      {dataStatus ? (
        <section className="subsurface-card">
          <div className="subsurface-head">
            <div>
              <p className="eyebrow">{copy.control.data}</p>
              <h3>{copy.control.dataTitle}</h3>
            </div>
            <button
              type="button"
              className="secondary-button compact-action"
              disabled={refreshingData}
              onClick={onRefreshData}
            >
              {dataRefreshButtonText(locale, refreshingData)}
            </button>
          </div>
          <div className="meta-stack">
            <div className="meta-line">
              <span>{copy.report.labels.source}</span>
              <strong>{repairText(dataStatus.source)}</strong>
            </div>
            <div className="meta-line">
              <span>{locale === "zh" ? "股票池范围" : "Universe scope"}</span>
              <strong>{repairText(dataStatus.universe_scope || "N/A")}</strong>
            </div>
            <div className="meta-line">
              <span>{locale === "zh" ? "股票池规模" : "Universe size"}</span>
              <strong>{dataStatus.records}</strong>
            </div>
            <div className="meta-line">
              <span>{copy.report.labels.lastRefresh}</span>
              <strong>{formatDateTime(dataStatus.last_refresh_at, locale)}</strong>
            </div>
            <div className="meta-line">
              <span>{locale === "zh" ? "CSV 兜底" : "CSV fallback"}</span>
              <strong>{boolText(dataStatus.fallback_enabled, locale)}</strong>
            </div>
            <div className="meta-line">
              <span>{locale === "zh" ? "宏观主源" : "Macro source"}</span>
              <strong>{repairText(dataStatus.macro_status?.source || "N/A")}</strong>
            </div>
            <div className="meta-line">
              <span>{locale === "zh" ? "宏观刷新" : "Macro refresh"}</span>
              <strong>{formatDateTime(dataStatus.macro_status?.last_refresh_at || null, locale)}</strong>
            </div>
            <div className="meta-line">
              <span>{locale === "zh" ? "SEC 披露缓存" : "SEC filing cache"}</span>
              <strong>
                {dataStatus.sec_filings_status
                  ? `${dataStatus.sec_filings_status.records} / ${dataStatus.sec_filings_status.covered_tickers}`
                  : "N/A"}
              </strong>
            </div>
          </div>
          {dataStatus.exchange_summary && Object.keys(dataStatus.exchange_summary).length ? (
            <div className="chip-row">
              {Object.entries(dataStatus.exchange_summary).map(([exchange, count]) => (
                <span key={exchange} className="chip">
                  {exchange}: {count}
                </span>
              ))}
            </div>
          ) : null}
          <div className="chip-row">
            {dataStatus.live_sources.map((source) => (
              <span key={source} className="chip neutral">
                {source}
              </span>
            ))}
          </div>
          {dataStatus.provider_statuses?.length ? (
            <div className="chip-row">
              {dataStatus.provider_statuses.map((item) => (
                <span
                  key={`${item.provider}-${item.role}`}
                  className={item.configured ? "chip positive" : "chip neutral"}
                  title={item.role}
                >
                  {item.provider}
                  {item.configured
                    ? locale === "zh"
                      ? " 已配置"
                      : " configured"
                    : locale === "zh"
                      ? " 可接入"
                      : " available"}
                </span>
              ))}
            </div>
          ) : null}
          <p className="section-note compact">{copy.control.dataNote}</p>
        </section>
      ) : null}

      {mode === "agent" ? (
        <section className="subsurface-card">
          <div className="subsurface-head">
            <div>
              <p className="eyebrow">{locale === "zh" ? "研究任务" : "Research task"}</p>
              <h3>{copy.control.tabs.agent}</h3>
            </div>
          </div>

          <label className="field">
            <span>{copy.control.fields.query}</span>
            <textarea
              value={agentForm.query}
              onChange={(event) => onAgentChange({ query: event.target.value })}
              placeholder={copy.control.placeholders.query}
            />
          </label>

          <div className="field-grid">
            <label className="field compact-field">
              <span>{copy.control.fields.maxResults}</span>
              <input
                type="number"
                min={1}
                max={20}
                value={agentForm.maxResults}
                onChange={(event) => onAgentChange({ maxResults: Number(event.target.value) })}
              />
            </label>
            <label className="toggle-field">
              <span>{copy.control.fields.liveData}</span>
              <input
                type="checkbox"
                checked={agentForm.fetchLiveData}
                onChange={(event) => onAgentChange({ fetchLiveData: event.target.checked })}
              />
            </label>
          </div>

          <p className="section-note compact">{copy.control.helperAgent}</p>
          <div className="button-row">
            <button type="button" className="primary-button" disabled={busy} onClick={onSubmitAgent}>
              {busy ? copy.actions.running : copy.actions.runAgent}
            </button>
            <button type="button" className="secondary-button" disabled={busy} onClick={onFillAgentSample}>
              {copy.actions.sample}
            </button>
          </div>
        </section>
      ) : (
        <section className="subsurface-card">
          <div className="subsurface-head">
            <div>
              <p className="eyebrow">{locale === "zh" ? "结构化筛选" : "Structured screener"}</p>
              <h3>{copy.control.tabs.structured}</h3>
            </div>
          </div>

          <label className="field">
            <span>{copy.control.fields.tickers}</span>
            <textarea
              value={structuredForm.tickers}
              onChange={(event) => onStructuredChange({ tickers: event.target.value })}
              placeholder={copy.control.placeholders.tickers}
            />
          </label>

          <div className="field-grid">
            <label className="field">
              <span>{copy.control.fields.sectors}</span>
              <textarea
                value={structuredForm.sectors}
                onChange={(event) => onStructuredChange({ sectors: event.target.value })}
                placeholder={copy.control.placeholders.sectors}
              />
            </label>
            <label className="field">
              <span>{copy.control.fields.industries}</span>
              <textarea
                value={structuredForm.industries}
                onChange={(event) => onStructuredChange({ industries: event.target.value })}
                placeholder={copy.control.placeholders.industries}
              />
            </label>
          </div>

          <div className="field-grid">
            <label className="field compact-field">
              <span>{copy.control.fields.risk}</span>
              <select
                value={structuredForm.riskLevel}
                onChange={(event) => onStructuredChange({ riskLevel: event.target.value })}
              >
                <option value="conservative">{copy.options.riskLow}</option>
                <option value="medium">{copy.options.riskMedium}</option>
                <option value="aggressive">{copy.options.riskHigh}</option>
              </select>
            </label>
            <label className="field compact-field">
              <span>{copy.control.fields.maxResults}</span>
              <input
                type="number"
                min={1}
                max={20}
                value={structuredForm.maxResults}
                onChange={(event) => onStructuredChange({ maxResults: Number(event.target.value) })}
              />
            </label>
          </div>

          <div className="field-grid">
            <label className="field compact-field">
              <span>{copy.control.fields.maxPe}</span>
              <input
                type="number"
                step="0.1"
                value={structuredForm.maxPe}
                onChange={(event) => onStructuredChange({ maxPe: event.target.value })}
              />
            </label>
            <label className="field compact-field">
              <span>{copy.control.fields.minRoe}</span>
              <input
                type="number"
                step="0.1"
                value={structuredForm.minRoe}
                onChange={(event) => onStructuredChange({ minRoe: event.target.value })}
              />
            </label>
          </div>

          <div className="field-grid">
            <label className="field compact-field">
              <span>{copy.control.fields.minDividend}</span>
              <input
                type="number"
                step="0.1"
                value={structuredForm.minDividendYield}
                onChange={(event) => onStructuredChange({ minDividendYield: event.target.value })}
              />
            </label>
            <label className="field compact-field">
              <span>{copy.control.fields.analyst}</span>
              <select
                value={structuredForm.analystRating}
                onChange={(event) => onStructuredChange({ analystRating: event.target.value })}
              >
                <option value="">{copy.options.analystAny}</option>
                <option value="buy">{copy.options.analystBuy}</option>
                <option value="strong_buy">{copy.options.analystStrongBuy}</option>
              </select>
            </label>
          </div>

          <div className="field-grid">
            <label className="toggle-field">
              <span>{copy.control.fields.positiveFcf}</span>
              <input
                type="checkbox"
                checked={structuredForm.requirePositiveFcf}
                onChange={(event) => onStructuredChange({ requirePositiveFcf: event.target.checked })}
              />
            </label>
            <label className="toggle-field">
              <span>{copy.control.fields.liveData}</span>
              <input
                type="checkbox"
                checked={structuredForm.fetchLiveData}
                onChange={(event) => onStructuredChange({ fetchLiveData: event.target.checked })}
              />
            </label>
          </div>

          <p className="section-note compact">{copy.control.helperStructured}</p>
          <div className="button-row">
            <button type="button" className="primary-button" disabled={busy} onClick={onSubmitStructured}>
              {busy ? copy.actions.running : copy.actions.runStructured}
            </button>
            <button type="button" className="secondary-button" disabled={busy} onClick={onFillStructuredSample}>
              {copy.actions.sample}
            </button>
          </div>
        </section>
      )}
    </section>
  );
}
