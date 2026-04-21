// 展示受控多智能体的交接时间线，仅用于 debug 工作台。
import type { Locale } from "../lib/types";

type GenericRecord = Record<string, unknown>;

interface AgentTracePanelProps {
  locale: Locale;
  trace: unknown;
}

function asTraceRows(value: unknown): GenericRecord[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is GenericRecord => Boolean(item) && typeof item === "object" && !Array.isArray(item));
}

function text(value: unknown, fallback = "N/A"): string {
  const next = String(value ?? "").trim();
  return next || fallback;
}

function textList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item ?? "").trim()).filter(Boolean) : [];
}

function elapsed(value: unknown): string {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "N/A";
  }
  if (number < 1000) {
    return `${number.toFixed(0)} ms`;
  }
  return `${(number / 1000).toFixed(2)} s`;
}

export function AgentTracePanel({ locale, trace }: AgentTracePanelProps) {
  const rows = asTraceRows(trace);
  const labels =
    locale === "zh"
      ? {
          eyebrow: "Agent Trace",
          title: "多智能体交接记录",
          empty: "暂无 agent trace。运行一次自然语言研究后，这里会显示每个 agent 的输入、输出和耗时。",
          status: "状态",
          elapsed: "耗时",
          evidence: "证据数",
          input: "输入",
          output: "输出",
          artifacts: "产物",
          warnings: "提醒",
          error: "失败原因",
        }
      : {
          eyebrow: "Agent Trace",
          title: "Multi-agent handoffs",
          empty: "No agent trace yet. Run a natural-language study to see each agent input, output, and duration.",
          status: "Status",
          elapsed: "Elapsed",
          evidence: "Evidence",
          input: "Input",
          output: "Output",
          artifacts: "Artifacts",
          warnings: "Warnings",
          error: "Error",
        };

  return (
    <section className="panel-surface">
      <div className="section-head tight">
        <div>
          <p className="eyebrow">{labels.eyebrow}</p>
          <h3>{labels.title}</h3>
        </div>
      </div>
      {!rows.length ? <div className="empty-state small">{labels.empty}</div> : null}
      {rows.length ? (
        <div className="summary-grid">
          {rows.map((item, index) => {
            const warnings = textList(item.warnings);
            const artifacts = textList(item.artifact_keys);
            const errorMessage = text(item.error_message, "");
            return (
              <article className="mini-card" key={`${text(item.agent_name)}-${index}`}>
                <span className="mini-label">{text(item.agent_name)}</span>
                <strong>{`${labels.status}: ${text(item.status)}`}</strong>
                <p>{`${labels.elapsed}: ${elapsed(item.elapsed_ms)}`}</p>
                <p>{`${labels.evidence}: ${text(item.evidence_count, "0")}`}</p>
                <p>{`${labels.input}: ${text(item.input_summary)}`}</p>
                <p>{`${labels.output}: ${text(item.output_summary)}`}</p>
                {artifacts.length ? <p>{`${labels.artifacts}: ${artifacts.join(", ")}`}</p> : null}
                {warnings.length ? <p>{`${labels.warnings}: ${warnings.join(locale === "zh" ? "；" : "; ")}`}</p> : null}
                {errorMessage ? <p>{`${labels.error}: ${errorMessage}`}</p> : null}
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
