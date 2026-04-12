import { formatDateTime, formatRunMode, formatRunStatus, formatRunTitle } from "../lib/format";
import type { HistoryFilters, Locale, RunSummary } from "../lib/types";
import type { LocalePack } from "../lib/i18n";

interface HistoryPanelProps {
  locale: Locale;
  copy: LocalePack;
  items: RunSummary[];
  filters: HistoryFilters;
  activeRunId: string | null;
  loading: boolean;
  mutating: boolean;
  onFilterChange: (patch: Partial<HistoryFilters>) => void;
  onRefresh: () => void;
  onClear: () => void;
  onOpen: (runId: string) => void;
}

export function HistoryPanel({
  locale,
  copy,
  items,
  filters,
  activeRunId,
  loading,
  mutating,
  onFilterChange,
  onRefresh,
  onClear,
  onOpen,
}: HistoryPanelProps) {
  return (
    <section className="panel-surface monitor-surface">
      <div className="section-head tight">
        <div>
          <p className="eyebrow">{copy.history.eyebrow}</p>
          <h2>{copy.history.title}</h2>
        </div>
        <div className="button-row compact">
          <button type="button" className="secondary-button" disabled={loading} onClick={onRefresh}>
            {copy.actions.refresh}
          </button>
          <button type="button" className="ghost-danger-button" disabled={mutating} onClick={onClear}>
            {copy.actions.clear}
          </button>
        </div>
      </div>

      <div className="history-toolbar">
        <label className="field">
          <span>{copy.history.search}</span>
          <input
            value={filters.search}
            onChange={(event) => onFilterChange({ search: event.target.value })}
            placeholder={locale === "zh" ? "按标题或 run id 搜索" : "Search by title or run id"}
          />
        </label>

        <div className="field-grid">
          <label className="field compact-field">
            <span>{copy.history.mode}</span>
            <select value={filters.mode} onChange={(event) => onFilterChange({ mode: event.target.value })}>
              <option value="">{copy.history.all}</option>
              <option value="agent">{formatRunMode("agent", locale)}</option>
              <option value="structured">{formatRunMode("structured", locale)}</option>
            </select>
          </label>

          <label className="field compact-field">
            <span>{copy.history.status}</span>
            <select value={filters.status} onChange={(event) => onFilterChange({ status: event.target.value })}>
              <option value="">{copy.history.all}</option>
              <option value="queued">{formatRunStatus("queued", locale)}</option>
              <option value="running">{formatRunStatus("running", locale)}</option>
              <option value="completed">{formatRunStatus("completed", locale)}</option>
              <option value="failed">{formatRunStatus("failed", locale)}</option>
              <option value="needs_clarification">{formatRunStatus("needs_clarification", locale)}</option>
            </select>
          </label>
        </div>
      </div>

      <div className="monitor-meta">
        <span>{copy.history.latestRuns}</span>
        <span>{loading ? copy.history.sync : `${items.length}`}</span>
      </div>

      <div className="history-list">
        {items.length ? (
          items.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === activeRunId ? "history-item active" : "history-item"}
              onClick={() => onOpen(item.id)}
            >
              <div className="history-title-row">
                <strong>{formatRunTitle(item.title, locale)}</strong>
                <span className={`status-badge status-${item.status}`}>{formatRunStatus(item.status, locale)}</span>
              </div>
              <div className="history-meta-row">
                <span>{formatRunMode(item.mode, locale)}</span>
                <span>{formatDateTime(item.created_at, locale)}</span>
              </div>
              <p className="history-id">{item.id}</p>
            </button>
          ))
        ) : (
          <div className="empty-state small">{copy.history.empty}</div>
        )}
      </div>
    </section>
  );
}
