import { formatDuration, formatRunStatus, repairText } from "../lib/format";
import type { Locale, RunStepRecord } from "../lib/types";
import type { LocalePack } from "../lib/i18n";

interface StagePanelProps {
  locale: Locale;
  copy: LocalePack;
  steps: RunStepRecord[];
}

export function StagePanel({ locale, copy, steps }: StagePanelProps) {
  const resolveStageLabel = (stepKey: string, fallbackLabel: string) =>
    copy.debug.stageLabels[stepKey] || repairText(fallbackLabel);

  return (
    <section className="panel-surface debug-card">
      <div className="section-head">
        <div>
          <p className="eyebrow">{locale === "zh" ? "阶段" : "Stages"}</p>
          <h2>{copy.debug.stages}</h2>
        </div>
      </div>

      {steps.length ? (
        <div className="stage-list">
          {steps.map((step) => (
            <article key={`${step.step_key}-${step.position}`} className="stage-item">
              <div className="stage-head">
                <div>
                  <p className="stage-index">{locale === "zh" ? `阶段 ${step.position}` : `STEP ${step.position}`}</p>
                  <h3>{resolveStageLabel(step.step_key, step.label)}</h3>
                </div>
                <div className="chip-row">
                  <span className={`chip status-${step.status}`}>{formatRunStatus(step.status, locale)}</span>
                  <span className="chip">{formatDuration(step.elapsed_ms, locale)}</span>
                </div>
              </div>
              <p className="stage-summary">{repairText(step.summary, copy.debug.noStages)}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state small">{copy.debug.noStages}</div>
      )}
    </section>
  );
}
