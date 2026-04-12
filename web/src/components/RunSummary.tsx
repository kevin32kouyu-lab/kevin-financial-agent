import { formatDateTime, formatRunMode, formatRunStatus, formatRunTitle, formatScore, repairText } from "../lib/format";
import type { Locale, RunDetailResponse, RunEvent } from "../lib/types";
import type { LocalePack } from "../lib/i18n";

interface RunSummaryProps {
  locale: Locale;
  copy: LocalePack;
  detail: RunDetailResponse | null;
  events: RunEvent[];
  loading: boolean;
  retrying: boolean;
  onRetry: () => void;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

function toText(value: unknown, fallback = "N/A"): string {
  return repairText(value, fallback);
}

export function RunSummary({ locale, copy, detail, events, loading, retrying, onRetry }: RunSummaryProps) {
  if (!detail) {
    return <section className="panel-surface hero-surface empty-state">{copy.run.empty}</section>;
  }

  const result = detail.result || {};
  const runtime = asRecord(result.runtime);
  const reportBriefing = asRecord(result.report_briefing);
  const executive = asRecord(reportBriefing?.executive);
  const followUpQuestion = typeof result.follow_up_question === "string" ? repairText(result.follow_up_question) : "";
  const errorMessage = repairText(detail.run.error_message || result.report_error, "");
  const recentEvents = events.slice(-6).reverse();
  const watchlist = asStringArray(executive?.watchlist);
  const avoidList = asStringArray(executive?.avoid_list);

  return (
    <section className="panel-surface hero-surface">
      <div className="section-head">
        <div>
          <p className="eyebrow">{copy.run.eyebrow}</p>
          <h2>{formatRunTitle(detail.run.title, locale)}</h2>
          <p className="section-note lead-copy">
            {typeof result.query === "string"
              ? repairText(result.query)
              : locale === "zh"
                ? "当前任务已经打开，下面会优先显示研究结论、图表和执行建议。"
                : "The current run is open. Research conclusions, charts and execution advice are shown below."}
          </p>
        </div>

        <div className="button-row compact">
          <button type="button" className="secondary-button" disabled={retrying || loading} onClick={onRetry}>
            {retrying ? copy.actions.retrying : copy.actions.retry}
          </button>
        </div>
      </div>

      <div className="chip-row">
        <span className="chip">{formatRunMode(detail.run.mode, locale)}</span>
        <span className={`chip status-${detail.run.status}`}>{formatRunStatus(detail.run.status, locale)}</span>
        <span className="chip">{locale === "zh" ? `第 ${detail.run.attempt_count} 次` : `Attempt ${detail.run.attempt_count}`}</span>
        {detail.run.report_mode ? <span className="chip">{repairText(detail.run.report_mode)}</span> : null}
      </div>

      <div className="summary-grid">
        <article className="mini-card">
          <p className="mini-label">{copy.run.currentView}</p>
          <h3>{copy.run.summary}</h3>
          <p>{copy.run.runtimeFields.runId}: {detail.run.id}</p>
          <p>{copy.run.runtimeFields.createdAt}: {formatDateTime(detail.run.created_at, locale)}</p>
          <p>{copy.run.runtimeFields.startedAt}: {formatDateTime(detail.run.started_at, locale)}</p>
          <p>{copy.run.runtimeFields.finishedAt}: {formatDateTime(detail.run.finished_at, locale)}</p>
        </article>

        <article className="mini-card">
          <p className="mini-label">{copy.run.execution}</p>
          <h3>{copy.run.research}</h3>
          <p>{copy.run.runtimeFields.steps}: {detail.steps.length}</p>
          <p>{copy.run.runtimeFields.events}: {events.length}</p>
          <p>{copy.run.runtimeFields.artifacts}: {detail.artifacts.length}</p>
          <p>{copy.run.runtimeFields.marketStance}: {toText(executive?.market_stance)}</p>
        </article>

        <article className="mini-card">
          <p className="mini-label">{copy.run.research}</p>
          <h3>{copy.run.runtimeFields.topPick}</h3>
          <p>{copy.run.runtimeFields.topPick}: {toText(executive?.top_pick)}</p>
          <p>{copy.run.runtimeFields.verdict}: {toText(executive?.top_pick_verdict)}</p>
          <p>{copy.run.runtimeFields.mandateFit}: {formatScore(executive?.mandate_fit_score)}</p>
          <p>{copy.run.runtimeFields.marketStance}: {toText(executive?.market_stance)}</p>
        </article>

        <article className="mini-card">
          <p className="mini-label">{copy.run.runtime}</p>
          <h3>{copy.run.runtime}</h3>
          <p>{copy.run.runtimeFields.provider}: {toText(runtime?.provider)}</p>
          <p>{copy.run.runtimeFields.model}: {toText(runtime?.model)}</p>
          <p>{copy.run.runtimeFields.route}: {toText(runtime?.route_mode)}</p>
          <p>{copy.run.runtimeFields.billing}: {toText(runtime?.billing_mode)}</p>
        </article>
      </div>

      {executive?.primary_call ? <div className="executive-banner">{toText(executive.primary_call)}</div> : null}
      {followUpQuestion ? <div className="warning-banner">{copy.run.followUp}: {followUpQuestion}</div> : null}
      {errorMessage ? <div className="danger-banner">{copy.run.error}: {errorMessage}</div> : null}

      {(watchlist.length > 0 || avoidList.length > 0) && (
        <div className="watch-grid">
          <div className="watch-card">
            <span className="label-pill">{copy.run.watchlist}</span>
            <div className="chip-row">
              {watchlist.length ? watchlist.map((item) => <span key={item} className="chip positive">{item}</span>) : <span className="chip">N/A</span>}
            </div>
          </div>
          <div className="watch-card">
            <span className="label-pill negative">{copy.run.avoid}</span>
            <div className="chip-row">
              {avoidList.length ? avoidList.map((item) => <span key={item} className="chip negative">{item}</span>) : <span className="chip">N/A</span>}
            </div>
          </div>
        </div>
      )}

      <div className="event-feed">
        <div className="section-head tight">
          <div>
            <p className="eyebrow">{locale === "zh" ? "事件流" : "Live events"}</p>
            <h3>{copy.run.liveEvents}</h3>
          </div>
        </div>

        {recentEvents.length ? (
          <div className="event-list">
            {recentEvents.map((event, index) => (
              <div key={`${event.id ?? "live"}-${index}`} className="event-item">
                <strong>{repairText(event.event_type)}</strong>
                <span>{formatDateTime(event.payload.created_at || detail.run.updated_at, locale)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state small">{copy.run.noEvents}</div>
        )}
      </div>
    </section>
  );
}
