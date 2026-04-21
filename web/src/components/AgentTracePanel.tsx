// 展示受控多智能体的交接时间线，仅用于 debug 工作台。
import type { Locale } from "../lib/types";

type GenericRecord = Record<string, unknown>;

interface AgentTracePanelProps {
  locale: Locale;
  trace: unknown;
  runId?: string | null;
  resumeBusyAgent?: string | null;
  onResumeFromAgent?: (agentName: string) => void;
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

export function AgentTracePanel({ locale, trace, runId, resumeBusyAgent, onResumeFromAgent }: AgentTracePanelProps) {
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
          decision: "决策",
          checkpoint: "恢复点",
          dependencies: "依赖",
          tools: "工具调用",
          debate: "论证引用",
          resume: "从这里继续",
          resuming: "正在恢复",
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
          decision: "Decision",
          checkpoint: "Checkpoint",
          dependencies: "Dependencies",
          tools: "Tool calls",
          debate: "Debate refs",
          resume: "Resume from here",
          resuming: "Resuming",
        };

  const toolRows = rows.flatMap((item) => asTraceRows(item.tool_calls).map((call) => ({ ...call, agent_name: item.agent_name })));
  const debateRows = rows.filter((item) => textList(item.debate_refs).length || text(item.agent_name).includes("Analyst") || text(item.agent_name).includes("Arbiter"));

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
        <div className="summary-grid two-up">
          {rows.map((item, index) => {
            const warnings = textList(item.warnings);
            const artifacts = textList(item.artifact_keys);
            const dependencies = textList(item.dependency_artifacts);
            const debateRefs = textList(item.debate_refs);
            const errorMessage = text(item.error_message, "");
            const agentName = text(item.agent_name);
            const canResume = Boolean(runId && onResumeFromAgent && item.rerunnable);
            return (
              <article className="mini-card" key={`${agentName}-${index}`}>
                <span className="mini-label">{agentName}</span>
                <strong>{`${labels.status}: ${text(item.status)}`}</strong>
                <p>{`${labels.elapsed}: ${elapsed(item.elapsed_ms)}`}</p>
                <p>{`${labels.evidence}: ${text(item.evidence_count, "0")}`}</p>
                <p>{`${labels.checkpoint}: ${text(item.checkpoint_id)}`}</p>
                {text(item.decision, "") ? <p>{`${labels.decision}: ${text(item.decision)}`}</p> : null}
                <p>{`${labels.input}: ${text(item.input_summary)}`}</p>
                <p>{`${labels.output}: ${text(item.output_summary)}`}</p>
                {artifacts.length ? <p>{`${labels.artifacts}: ${artifacts.join(", ")}`}</p> : null}
                {dependencies.length ? <p>{`${labels.dependencies}: ${dependencies.join(", ")}`}</p> : null}
                {debateRefs.length ? <p>{`${labels.debate}: ${debateRefs.join(", ")}`}</p> : null}
                {warnings.length ? <p>{`${labels.warnings}: ${warnings.join(locale === "zh" ? "；" : "; ")}`}</p> : null}
                {errorMessage ? <p>{`${labels.error}: ${errorMessage}`}</p> : null}
                {canResume ? (
                  <button
                    type="button"
                    className="secondary-button compact-action"
                    disabled={resumeBusyAgent === agentName}
                    onClick={() => onResumeFromAgent?.(agentName)}
                  >
                    {resumeBusyAgent === agentName ? labels.resuming : labels.resume}
                  </button>
                ) : null}
              </article>
            );
          })}
        </div>
      ) : null}
      {toolRows.length ? (
        <div className="panel-subsection">
          <p className="eyebrow">{labels.tools}</p>
          <div className="summary-grid two-up">
            {toolRows.map((item, index) => (
              <article className="mini-card" key={`${text(item.tool_name)}-${index}`}>
                <span className="mini-label">{text(item.agent_name)}</span>
                <strong>{`${text(item.tool_name)} · ${text(item.status)}`}</strong>
                <p>{`${labels.elapsed}: ${elapsed(item.elapsed_ms)}`}</p>
                <p>{`Scope: ${text(item.permission_scope)}`}</p>
                <p>{`Attempts: ${text(item.attempts, "0")}`}</p>
                {text(item.error_message, "") ? <p>{`${labels.error}: ${text(item.error_message)}`}</p> : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
      {debateRows.length ? (
        <div className="panel-subsection">
          <p className="eyebrow">{labels.debate}</p>
          <div className="summary-grid two-up">
            {debateRows.map((item, index) => (
              <article className="mini-card" key={`${text(item.agent_name)}-debate-${index}`}>
                <span className="mini-label">{text(item.agent_name)}</span>
                <strong>{text(item.decision, text(item.output_summary))}</strong>
                <p>{text(item.output_summary)}</p>
                {textList(item.warnings).length ? <p>{textList(item.warnings).join(locale === "zh" ? "；" : "; ")}</p> : null}
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
