/** 用户研究终端：提供四页化的正式研究前台。 */
import { type MouseEvent, useEffect, useMemo, useRef, useState } from "react";

import { BacktestPanel } from "../components/BacktestPanel";
import { MotionBackdrop } from "../components/MotionBackdrop";
import { ReportPanel } from "../components/ReportPanel";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Progress } from "../components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";
import { formatDateTime, formatRunStatus, formatRunTitle } from "../lib/format";
import { readMotionEnabled, writeMotionEnabled } from "../lib/motion";
import { useResearchConsole } from "../hooks";
import { buildTerminalHref, type TerminalPage, useTerminalNavigation } from "../hooks/useTerminalNavigation";
import type { UserPreferenceSummary } from "../lib/types";

type GenericRecord = Record<string, unknown>;

/** 拦截普通点击，保留新标签页等浏览器默认行为。 */
function shouldUseClientNavigation(event: MouseEvent<HTMLAnchorElement>) {
  return !(event.defaultPrevented || event.metaKey || event.altKey || event.ctrlKey || event.shiftKey || event.button !== 0);
}

/** 根据运行状态估算页面进度。 */
function computeProgress(status: string | undefined, stepCount: number, mode: string | undefined) {
  if (!status) return { percent: 0, tone: "neutral", textKey: "idle" };
  if (status === "queued") return { percent: 12, tone: "neutral", textKey: "queued" };
  if (status === "running") {
    const expected = mode === "structured" ? 3 : 4;
    const percent = Math.min(92, Math.max(18, Math.round((stepCount / expected) * 78)));
    return { percent, tone: "neutral", textKey: "running" };
  }
  if (status === "completed") return { percent: 100, tone: "positive", textKey: "completed" };
  if (status === "cancelled") return { percent: 100, tone: "negative", textKey: "cancelled" };
  if (status === "failed") return { percent: 100, tone: "negative", textKey: "failed" };
  if (status === "needs_clarification") return { percent: 100, tone: "neutral", textKey: "needs_clarification" };
  return { percent: 0, tone: "neutral", textKey: "idle" };
}

/** 把未知值转换为对象。 */
function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

/** 把未知值转换为对象数组。 */
function asArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? (value.filter((item) => item && typeof item === "object") as GenericRecord[]) : [];
}

/** 把未知值转换为字符串数组。 */
function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

/** 把未知值转换为文本。 */
function toText(value: unknown, fallback = "N/A"): string {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text : fallback;
}

/** 把内部字段名转换成用户可读名称。 */
function readableField(locale: "zh" | "en", value: string) {
  const zhMap: Record<string, string> = {
    capital_amount: "投入金额",
    risk_tolerance: "风险偏好",
    investment_horizon: "投资期限",
    investment_style: "投资风格",
    preferred_sectors: "偏好板块",
    preferred_industries: "偏好行业",
    explicit_tickers: "关注标的",
    fundamental_filters: "筛选条件",
  };
  const enMap: Record<string, string> = {
    capital_amount: "capital",
    risk_tolerance: "risk preference",
    investment_horizon: "horizon",
    investment_style: "investment style",
    preferred_sectors: "preferred sectors",
    preferred_industries: "preferred industries",
    explicit_tickers: "focus tickers",
    fundamental_filters: "filters",
  };
  return (locale === "zh" ? zhMap : enMap)[value] || value;
}

/** 把原始错误转换成用户可读文本。 */
function pickFriendlyError(message: string, locale: "zh" | "en") {
  const text = message.toLowerCase();
  if (!text) return "";
  if (text.includes("429") || text.includes("too many requests") || text.includes("rate limited")) {
    return locale === "zh"
      ? "数据源当前访问过多，系统会自动重试。建议稍后再次发起研究。"
      : "Data providers are temporarily rate-limited. The system will retry automatically. Please try again in a moment.";
  }
  if (text.includes("api key") || text.includes("unauthorized") || text.includes("forbidden")) {
    return locale === "zh"
      ? "当前环境缺少可用授权，请先检查 API Key 配置。"
      : "Authorization is missing or invalid. Please check your API key configuration.";
  }
  if (text.includes("end date") && text.includes("later")) {
    return locale === "zh"
      ? "结束日期需要晚于研究时点，请调整回测日期后重试。"
      : "End date must be later than the research anchor date. Please adjust and retry.";
  }
  return locale === "zh"
    ? "这次任务没有完成，建议先调整问题描述或稍后重试。"
    : "The run did not complete. Please refine the request or retry shortly.";
}

/** 把运行状态翻译成页面阶段描述。 */
function resolveUiStage(status: string | undefined, stepCount: number, locale: "zh" | "en"): string {
  if (!status) return locale === "zh" ? "等待开始" : "Waiting to start";
  if (status === "queued") return locale === "zh" ? "队列中" : "In queue";
  if (status === "running") {
    if (stepCount <= 1) return locale === "zh" ? "理解你的目标" : "Understanding your goal";
    if (stepCount <= 3) return locale === "zh" ? "聚合市场数据" : "Aggregating market data";
    return locale === "zh" ? "生成正式报告" : "Building the final report";
  }
  if (status === "completed") return locale === "zh" ? "已完成" : "Completed";
  if (status === "cancelled") return locale === "zh" ? "已撤回" : "Cancelled";
  if (status === "failed") return locale === "zh" ? "执行失败" : "Failed";
  if (status === "needs_clarification") return locale === "zh" ? "等待补充信息" : "Need clarification";
  return locale === "zh" ? "等待开始" : "Waiting to start";
}

/** 生成首屏摘要。 */
function buildDecisionSummary(
  result: Record<string, unknown> | null,
  copy: ReturnType<typeof useResearchConsole>["copy"],
  locale: "zh" | "en",
) {
  const reportBriefing = asRecord(asRecord(result)?.report_briefing);
  const executive = asRecord(reportBriefing?.executive);
  const macro = asRecord(reportBriefing?.macro);
  const riskRegister = asArray(reportBriefing?.risk_register);
  const validationSummary = asRecord(asRecord(reportBriefing?.meta)?.validation_summary);
  const evidenceSummary = asRecord(asRecord(reportBriefing?.meta)?.evidence_summary);

  if (!result || !reportBriefing) {
    return {
      conclusion:
        locale === "zh"
          ? "先输入投资目标，系统会把结论、风险和执行建议整理成一份正式研究。"
          : "Start with the investment goal and the system will turn it into a formal research recommendation.",
      conclusionNote:
        locale === "zh"
          ? "结论页会先告诉你该关注什么、风险在哪里、下一步怎么做。"
          : "The conclusion page highlights what to focus on, where the risk sits, and what to do next.",
      riskHeadline: copy.terminal.riskWaiting,
      nextAction: copy.terminal.nextActionWaiting,
      topPick: "N/A",
      fitScore: "N/A",
      stance: locale === "zh" ? "等待研究" : "Waiting",
    };
  }

  const riskFromRegister = asRecord(riskRegister[0]);
  return {
    conclusion: toText(executive?.display_call || executive?.primary_call, copy.terminal.decisionWaiting),
    conclusionNote:
      toText(validationSummary?.headline || evidenceSummary?.headline, "") ||
      (locale === "zh"
        ? "系统会优先给出最适合当前资金目标的结论，再展开完整理由。"
        : "The system surfaces the best-fit conclusion first, then expands into the full reasoning."),
    riskHeadline: toText(
      macro?.risk_headline || riskFromRegister?.summary || riskFromRegister?.category,
      copy.terminal.riskWaiting,
    ),
    nextAction: toText(executive?.display_action_summary || executive?.action_summary, copy.terminal.nextActionWaiting),
    topPick: toText(executive?.top_pick, "N/A"),
    fitScore: toText(executive?.mandate_fit_score, "N/A"),
    stance: toText(executive?.market_stance || macro?.regime, locale === "zh" ? "待更新" : "Pending"),
  };
}

/** 提取当前 run 对应的原始问题。 */
function extractBoundQuery(result: Record<string, unknown> | null, fallback: string, locale: "zh" | "en") {
  const queryText = toText(asRecord(result)?.query, "");
  if (queryText) return queryText;
  if (fallback.trim()) return fallback.trim();
  return locale === "zh" ? "这里会显示本次研究绑定的原始投资问题。" : "The original investment request will appear here.";
}

/** 计算研究上下文标签。 */
function buildContextChips(
  locale: "zh" | "en",
  terminalMode: "realtime" | "historical",
  asOfDate: string,
  referenceStartDate: string,
  runStatus?: string,
) {
  const chips = [
    terminalMode === "historical"
      ? locale === "zh"
        ? "历史研究"
        : "Historical research"
      : locale === "zh"
        ? "实时研究"
        : "Realtime research",
  ];

  if (terminalMode === "historical" && asOfDate) {
    chips.push(`as_of: ${asOfDate}`);
  }
  if (terminalMode === "realtime" && referenceStartDate) {
    chips.push(locale === "zh" ? `参考起点 ${referenceStartDate}` : `Reference ${referenceStartDate}`);
  }
  if (runStatus) chips.push(locale === "zh" ? `状态 ${runStatus}` : `Status ${runStatus}`);
  return chips;
}

/** 渲染顶部子页导航。 */
function TerminalRouteTabs({
  locale,
  activePage,
  activeRunId,
  onNavigate,
}: {
  locale: "zh" | "en";
  activePage: TerminalPage;
  activeRunId: string | null;
  onNavigate: (page: TerminalPage, runId?: string | null) => void;
}) {
  const items = [
    {
      key: "ask" as const,
      label: locale === "zh" ? "开始研究" : "Start Research",
    },
    {
      key: "conclusion" as const,
      label: locale === "zh" ? "研究结论" : "Research Conclusion",
    },
    {
      key: "backtest" as const,
      label: locale === "zh" ? "回测页" : "Backtest",
    },
    {
      key: "archive" as const,
      label: locale === "zh" ? "历史页" : "Archive",
    },
  ];

  return (
    <nav className="panel-surface terminal-route-tabs">
      {items.map((item) => (
        <a
          key={item.key}
          href={buildTerminalHref(item.key, activeRunId)}
          onClick={(event) => {
            if (!shouldUseClientNavigation(event)) return;
            event.preventDefault();
            onNavigate(item.key, activeRunId);
          }}
          className={item.key === activePage ? "terminal-route-tab active" : "terminal-route-tab"}
        >
          {item.label}
        </a>
      ))}
    </nav>
  );
}

/** 渲染结论页的首屏摘要。 */
function ConclusionSummary({
  locale,
  decisionSummary,
  activeRunId,
  queryText,
  contextChips,
  progress,
  uiStage,
  statusCopy,
  runUpdatedAt,
  onNavigate,
}: {
  locale: "zh" | "en";
  decisionSummary: ReturnType<typeof buildDecisionSummary>;
  activeRunId: string | null;
  queryText: string;
  contextChips: string[];
  progress: { percent: number; tone: string; textKey: string };
  uiStage: string;
  statusCopy: string;
  runUpdatedAt: string;
  onNavigate: (page: TerminalPage, runId?: string | null) => void;
}) {
  return (
    <section className="terminal-page-grid">
      <article className="panel-surface terminal-summary-panel">
        <div className="section-head terminal-page-head">
          <div>
            <p className="eyebrow">{locale === "zh" ? "研究结论" : "Research conclusion"}</p>
            <h1 className="terminal-summary-title">
              {decisionSummary.topPick !== "N/A"
                ? locale === "zh"
                  ? `优先关注 ${decisionSummary.topPick}`
                  : `Focus on ${decisionSummary.topPick}`
                : locale === "zh"
                  ? "等待研究结论"
                  : "Waiting for a conclusion"}
            </h1>
            <p className="lead-copy terminal-summary-lead">{decisionSummary.conclusion}</p>
          </div>
          <div className="terminal-summary-actions">
            <Button variant="secondary" size="sm" asChild>
              <a
                href={buildTerminalHref("backtest", activeRunId)}
                onClick={(event) => {
                  if (!shouldUseClientNavigation(event)) return;
                  event.preventDefault();
                  onNavigate("backtest", activeRunId);
                }}
              >
                {locale === "zh" ? "查看回测页" : "Open backtest"}
              </a>
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <a
                href={buildTerminalHref("archive", activeRunId)}
                onClick={(event) => {
                  if (!shouldUseClientNavigation(event)) return;
                  event.preventDefault();
                  onNavigate("archive", activeRunId);
                }}
              >
                {locale === "zh" ? "查看历史页" : "Open archive"}
              </a>
            </Button>
          </div>
        </div>

        <p className="section-note terminal-summary-note">{decisionSummary.conclusionNote}</p>

        <div className="terminal-summary-grid">
          <article className="mini-card terminal-highlight-card">
            <span className="mini-label">{locale === "zh" ? "本次结论" : "Verdict"}</span>
            <strong>{decisionSummary.conclusion}</strong>
          </article>
          <article className="mini-card">
            <span className="mini-label">{locale === "zh" ? "风险一句话" : "Risk in one line"}</span>
            <strong>{decisionSummary.riskHeadline}</strong>
          </article>
          <article className="mini-card">
            <span className="mini-label">{locale === "zh" ? "建议动作" : "Suggested action"}</span>
            <strong>{decisionSummary.nextAction}</strong>
          </article>
          <article className="mini-card">
            <span className="mini-label">{locale === "zh" ? "优先标的" : "Top pick"}</span>
            <strong>{decisionSummary.topPick}</strong>
          </article>
          <article className="mini-card">
            <span className="mini-label">{locale === "zh" ? "匹配度" : "Mandate fit"}</span>
            <strong>{decisionSummary.fitScore}</strong>
          </article>
          <article className="mini-card">
            <span className="mini-label">{locale === "zh" ? "市场姿态" : "Market stance"}</span>
            <strong>{decisionSummary.stance}</strong>
          </article>
        </div>
      </article>

      <aside className="terminal-side-stack">
        <article className="panel-surface terminal-query-card">
          <div className="section-head tight">
            <div>
              <p className="eyebrow">{locale === "zh" ? "你的投资需求" : "Your investment request"}</p>
              <h2>{locale === "zh" ? "本次研究绑定的问题" : "The request behind this run"}</h2>
            </div>
          </div>
          <div className="terminal-query-body">{queryText}</div>
          <div className="chip-row terminal-chip-wrap">
            {contextChips.map((item) => (
              <Badge key={item} variant="outline" className="trust-chip">
                {item}
              </Badge>
            ))}
          </div>
        </article>

        <article className={`panel-surface terminal-progress-panel progress-${progress.tone}`}>
          <div className="section-head tight">
            <div>
              <p className="eyebrow">{locale === "zh" ? "任务进度" : "Task progress"}</p>
              <h2>{uiStage}</h2>
            </div>
            <strong className="terminal-progress-percent">{progress.percent}%</strong>
          </div>
          <div className="terminal-progress-stage-row">
            <span>{locale === "zh" ? "当前阶段" : "Current stage"}</span>
            <strong>{uiStage}</strong>
          </div>
          <Progress value={progress.percent} className="terminal-progress-track-strong" />
          <p className="section-note terminal-progress-copy">{statusCopy}</p>
          <div className="terminal-progress-meta">
            <span>{locale === "zh" ? "最新更新时间" : "Latest update"}</span>
            <strong>{runUpdatedAt}</strong>
          </div>
        </article>
      </aside>
    </section>
  );
}

/** 渲染结论页没有绑定报告时的空状态。 */
function ConclusionEmptyState({
  locale,
  onNavigate,
}: {
  locale: "zh" | "en";
  onNavigate: (page: TerminalPage, runId?: string | null) => void;
}) {
  return (
    <section className="terminal-route-stack">
      <article className="panel-surface terminal-route-header terminal-empty-panel">
        <div className="section-head">
          <div>
            <p className="eyebrow">{locale === "zh" ? "研究结论" : "Research conclusion"}</p>
            <h1>{locale === "zh" ? "这里会展示正式研究结果" : "Formal research results appear here"}</h1>
            <p className="lead-copy">
              {locale === "zh"
                ? "先在“开始研究”页提出问题，或去历史页打开一条已有记录，系统会把结论和完整报告放在这里。"
                : "Start from the ask page or open a saved run from the archive. The conclusion and the full report will appear here."}
            </p>
          </div>
        </div>
        <div className="terminal-summary-actions">
          <Button variant="secondary" size="sm" asChild>
            <a
              href={buildTerminalHref("ask")}
              onClick={(event) => {
                if (!shouldUseClientNavigation(event)) return;
                event.preventDefault();
                onNavigate("ask", null);
              }}
            >
              {locale === "zh" ? "去开始研究" : "Go to start research"}
            </a>
          </Button>
          <Button variant="secondary" size="sm" asChild>
            <a
              href={buildTerminalHref("archive")}
              onClick={(event) => {
                if (!shouldUseClientNavigation(event)) return;
                event.preventDefault();
                onNavigate("archive", null);
              }}
            >
              {locale === "zh" ? "打开历史页" : "Open archive"}
            </a>
          </Button>
        </div>
      </article>
    </section>
  );
}

/** 渲染“补充信息后继续研究”的卡片。 */
function ClarificationContinueCard({
  locale,
  followUpQuestion,
  missingFields,
  clarificationAnswer,
  setClarificationAnswer,
  onContinue,
  creatingRun,
  profilePreferences,
}: {
  locale: "zh" | "en";
  followUpQuestion: string;
  missingFields: string[];
  clarificationAnswer: string;
  setClarificationAnswer: (value: string) => void;
  onContinue: () => void;
  creatingRun: boolean;
  profilePreferences: UserPreferenceSummary | null;
}) {
  const preferenceValues =
    profilePreferences && typeof profilePreferences.values === "object"
      ? (profilePreferences.values as Record<string, unknown>)
      : null;
  const latestPreferenceParts = [
    preferenceValues?.capital_amount
      ? locale === "zh"
        ? `资金 ${toText(preferenceValues.capital_amount)} ${toText(preferenceValues.currency, "USD")}`
        : `Capital ${toText(preferenceValues.capital_amount)} ${toText(preferenceValues.currency, "USD")}`
      : "",
    preferenceValues?.risk_tolerance
      ? locale === "zh"
        ? `风险 ${toText(preferenceValues.risk_tolerance)}`
        : `Risk ${toText(preferenceValues.risk_tolerance)}`
      : "",
    preferenceValues?.investment_horizon
      ? locale === "zh"
        ? `期限 ${toText(preferenceValues.investment_horizon)}`
        : `Horizon ${toText(preferenceValues.investment_horizon)}`
      : "",
    preferenceValues?.investment_style
      ? locale === "zh"
        ? `风格 ${toText(preferenceValues.investment_style)}`
        : `Style ${toText(preferenceValues.investment_style)}`
      : "",
  ].filter(Boolean);

  return (
    <section className="panel-surface terminal-clarification-panel">
      <div className="section-head">
        <div>
          <p className="eyebrow">{locale === "zh" ? "继续研究" : "Continue the research"}</p>
          <h2>{locale === "zh" ? "补一句关键信息，系统就能继续" : "Add one key detail and the run can continue"}</h2>
          <p className="section-note">{followUpQuestion}</p>
        </div>
      </div>
      {missingFields.length ? (
        <div className="chip-row terminal-chip-wrap">
          {missingFields.map((item) => (
            <Badge key={item} variant="outline" className="trust-chip">
              {item}
            </Badge>
          ))}
        </div>
      ) : null}
      {latestPreferenceParts.length ? (
        <p className="section-note terminal-clarification-note">
          {locale === "zh" ? "系统当前还能参考最近一次偏好：" : "The system can still reference your latest preferences: "}
          {latestPreferenceParts.join(" / ")}
        </p>
      ) : null}
      <label className="field">
        <span>{locale === "zh" ? "补充信息" : "Additional details"}</span>
        <textarea
          value={clarificationAnswer}
          placeholder={
            locale === "zh"
              ? "例如：我能承受中等波动，准备持有 3 到 5 年。"
              : "For example: I can tolerate medium volatility and plan to hold for 3 to 5 years."
          }
          onChange={(event) => setClarificationAnswer(event.target.value)}
        />
      </label>
      <div className="button-row">
        <Button type="button" className="terminal-primary-cta" disabled={!clarificationAnswer.trim() || creatingRun} onClick={onContinue}>
          {creatingRun ? (locale === "zh" ? "继续研究中..." : "Continuing...") : locale === "zh" ? "补充后继续研究" : "Continue research"}
        </Button>
      </div>
    </section>
  );
}

/** 渲染历史页。 */
function ArchivePage({
  locale,
  historyLoading,
  history,
  activeRunId,
  runDetail,
  auditSummary,
  onNavigate,
}: {
  locale: "zh" | "en";
  historyLoading: boolean;
  history: Array<{
    id: string;
    title: string;
    status: string;
    updated_at: string;
  }>;
  activeRunId: string | null;
  runDetail: ReturnType<typeof useResearchConsole>["runDetail"];
  auditSummary: ReturnType<typeof useResearchConsole>["auditSummary"];
  onNavigate: (page: TerminalPage, runId?: string | null) => void;
}) {
  const result = runDetail?.result || null;
  const boundQuery = extractBoundQuery(result, "", locale);

  return (
    <section className="terminal-route-stack">
      <article className="panel-surface terminal-route-header">
        <div className="section-head">
          <div>
            <p className="eyebrow">{locale === "zh" ? "历史页" : "Archive"}</p>
            <h1>{locale === "zh" ? "最近研究记录" : "Recent research runs"}</h1>
            <p className="lead-copy">
              {locale === "zh"
                ? "这里集中查看过去的研究任务，并直接打开对应的正式报告或回测页。"
                : "Review previous runs here and jump directly into the report or backtest page."}
            </p>
          </div>
        </div>
      </article>

      <section className="terminal-archive-layout">
      <article className="panel-surface terminal-archive-page">
        {historyLoading ? (
          <div className="empty-state small">{locale === "zh" ? "正在读取历史记录..." : "Loading archive..."}</div>
        ) : history.length ? (
          <div className="terminal-archive-list">
            {history.map((item) => (
              <article
                key={item.id}
                className={item.id === activeRunId ? "terminal-archive-row active" : "terminal-archive-row"}
              >
                <div className="terminal-archive-copy">
                  <p className="eyebrow">{formatRunStatus(item.status, locale)}</p>
                  <h3>{formatRunTitle(item.title, locale)}</h3>
                  <p className="section-note">{formatDateTime(item.updated_at, locale)}</p>
                </div>
                <div className="button-row compact terminal-archive-actions">
                  <Button variant="secondary" size="sm" asChild>
                    <a
                      href={buildTerminalHref("conclusion", item.id)}
                      onClick={(event) => {
                        if (!shouldUseClientNavigation(event)) return;
                        event.preventDefault();
                        onNavigate("conclusion", item.id);
                      }}
                    >
                      {locale === "zh" ? "打开报告" : "Open report"}
                    </a>
                  </Button>
                  <Button variant="secondary" size="sm" asChild>
                    <a
                      href={buildTerminalHref("backtest", item.id)}
                      onClick={(event) => {
                        if (!shouldUseClientNavigation(event)) return;
                        event.preventDefault();
                        onNavigate("backtest", item.id);
                      }}
                    >
                      {locale === "zh" ? "打开回测" : "Open backtest"}
                    </a>
                  </Button>
                </div>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state small">{locale === "zh" ? "暂无历史报告。" : "No archived report yet."}</div>
        )}
      </article>
      <aside className="panel-surface terminal-archive-insight">
        <div className="section-head tight">
          <div>
            <p className="eyebrow">{locale === "zh" ? "当前档案" : "Current archive detail"}</p>
            <h2>{locale === "zh" ? "这条研究记录包含什么" : "What this saved run contains"}</h2>
          </div>
        </div>
        {activeRunId && runDetail ? (
          <div className="terminal-archive-summary">
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "原始问题" : "Original request"}</span>
              <strong>{boundQuery}</strong>
            </div>
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "研究模式" : "Research mode"}</span>
              <strong>
                {auditSummary?.research_mode === "historical"
                  ? locale === "zh"
                    ? "历史研究"
                    : "Historical research"
                  : locale === "zh"
                    ? "实时研究"
                    : "Realtime research"}
              </strong>
              {auditSummary?.as_of_date ? <p className="section-note">{`as_of: ${auditSummary.as_of_date}`}</p> : null}
            </div>
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "优先标的" : "Top pick"}</span>
              <strong>{toText(auditSummary?.top_pick, "N/A")}</strong>
            </div>
            <div className="mini-card">
              <span className="mini-label">{locale === "zh" ? "可信度" : "Confidence"}</span>
              <strong>{toText(auditSummary?.confidence_level, "N/A")}</strong>
            </div>
            {asStringArray(auditSummary?.validation_flags).length ? (
              <div className="mini-card">
                <span className="mini-label">{locale === "zh" ? "校验提示" : "Validation flags"}</span>
                <ul className="compact-list terminal-trust-list">
                  {asStringArray(auditSummary?.validation_flags).slice(0, 3).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
            {asStringArray(auditSummary?.degraded_modules).length ? (
              <div className="mini-card">
                <span className="mini-label">{locale === "zh" ? "降级模块" : "Degraded modules"}</span>
                <ul className="compact-list terminal-trust-list">
                  {asStringArray(auditSummary?.degraded_modules).slice(0, 3).map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <div className="empty-state small">
            {locale === "zh" ? "先从左侧选择一条历史记录，这里会显示它的摘要。" : "Select a run from the left to preview its summary here."}
          </div>
        )}
      </aside>
      </section>
    </section>
  );
}

/** 渲染回测页。 */
function BacktestPage({
  locale,
  copy,
  activeRunId,
  runDetail,
  backtestDetail,
  backtestLoading,
  backtestCreating,
  terminalMode,
  historicalBacktestEndDate,
  setHistoricalBacktestEndDate,
  referenceStartDate,
  setReferenceStartDate,
  runBacktest,
}: {
  locale: "zh" | "en";
  copy: ReturnType<typeof useResearchConsole>["copy"];
  activeRunId: string | null;
  runDetail: ReturnType<typeof useResearchConsole>["runDetail"];
  backtestDetail: ReturnType<typeof useResearchConsole>["backtestDetail"];
  backtestLoading: boolean;
  backtestCreating: boolean;
  terminalMode: "realtime" | "historical";
  historicalBacktestEndDate: string;
  setHistoricalBacktestEndDate: (value: string) => void;
  referenceStartDate: string;
  setReferenceStartDate: (value: string) => void;
  runBacktest: ReturnType<typeof useResearchConsole>["runBacktest"];
}) {
  const result = runDetail?.result || null;
  const queryText = extractBoundQuery(result, "", locale);

  return (
    <section className="terminal-route-stack">
      <article className="panel-surface terminal-route-header">
        <div className="section-head">
          <div>
            <p className="eyebrow">{locale === "zh" ? "回测页" : "Backtest"}</p>
            <h1>{locale === "zh" ? "回看建议在真实市场中的表现" : "Review how the recommendation performed"}</h1>
            <p className="lead-copy">
              {locale === "zh"
                ? "这一页只保留回测结果、图表和单股时间序列，避免和正式报告挤在同一页。"
                : "This page is dedicated to replay metrics, charts and per-stock series only."}
            </p>
          </div>
        </div>
        <div className="terminal-route-meta">
          <div className="mini-card">
            <span className="mini-label">{locale === "zh" ? "当前绑定问题" : "Bound request"}</span>
            <strong>{queryText}</strong>
          </div>
        </div>
      </article>

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
    </section>
  );
}

/** 终端主组件。 */
export function TerminalView() {
  const {
    locale,
    setLocale,
    copy,
    terminalMode,
    setTerminalMode,
    asOfDate,
    setAsOfDate,
    referenceStartDate,
    setReferenceStartDate,
    historicalBacktestEndDate,
    setHistoricalBacktestEndDate,
    dataStatus,
    profilePreferences,
    auditSummary,
    agentForm,
    history,
    activeRunId,
    runDetail,
    backtestDetail,
    backtestLoading,
    backtestCreating,
    statusText,
    errorText,
    sampleScenarios,
    creatingRun,
    cancelingRun,
    historyLoading,
    runLoading,
    setAgentForm,
    createAgentRun,
    cancelActiveRun,
    openRun,
    loadBacktest,
    runBacktest,
    applySampleScenario,
  } = useResearchConsole("agent");
  const { terminalPage, routeRunId, navigateTerminal, replaceTerminalRun } = useTerminalNavigation(activeRunId);
  const [motionEnabled, setMotionEnabled] = useState<boolean>(() => readMotionEnabled());
  const [motionLevel, setMotionLevel] = useState<"high" | "low">(() => (readMotionEnabled() ? "high" : "low"));
  const [, setUiFeedbackState] = useState<
    "idle" | "queued" | "running" | "completed" | "failed" | "cancelled" | "needs_clarification"
  >("idle");
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [initialRunResolved, setInitialRunResolved] = useState(false);
  const previousRunStatusRef = useRef<string | null>(null);

  useEffect(() => {
    document.title = copy.terminal.title;
  }, [copy.terminal.title]);

  useEffect(() => {
    writeMotionEnabled(motionEnabled);
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-motion", motionEnabled ? "on" : "off");
    }
  }, [motionEnabled]);

  useEffect(() => {
    const status = runDetail?.run.status;
    if (!status) {
      setUiFeedbackState("idle");
      return;
    }
    if (
      status === "queued" ||
      status === "running" ||
      status === "completed" ||
      status === "failed" ||
      status === "cancelled" ||
      status === "needs_clarification"
    ) {
      setUiFeedbackState(status);
      return;
    }
    setUiFeedbackState("idle");
  }, [runDetail?.run.status]);

  useEffect(() => {
    if (historyLoading || initialRunResolved) return;
    setInitialRunResolved(true);
    if (routeRunId) {
      void openRun(routeRunId);
    }
  }, [historyLoading, initialRunResolved, openRun, routeRunId]);

  useEffect(() => {
    if (!initialRunResolved) return;
    replaceTerminalRun(activeRunId);
  }, [activeRunId, initialRunResolved, replaceTerminalRun]);

  useEffect(() => {
    if (!initialRunResolved || !routeRunId || routeRunId === activeRunId || runLoading) return;
    void openRun(routeRunId);
  }, [activeRunId, initialRunResolved, openRun, routeRunId, runLoading]);

  useEffect(() => {
    if (runDetail?.run.status !== "needs_clarification") {
      setClarificationAnswer("");
    }
  }, [runDetail?.run.status, activeRunId]);

  useEffect(() => {
    const currentStatus = runDetail?.run.status ?? null;
    const previousStatus = previousRunStatusRef.current;
    if (
      typeof window !== "undefined" &&
      terminalPage === "ask" &&
      activeRunId &&
      currentStatus === "completed" &&
      (previousStatus === "queued" || previousStatus === "running")
    ) {
      setAgentForm({ query: "" });
      navigateTerminal("conclusion", activeRunId);
    }
    previousRunStatusRef.current = currentStatus;
  }, [terminalPage, activeRunId, runDetail?.run.status, setAgentForm, navigateTerminal]);

  useEffect(() => {
    if (terminalPage !== "backtest" || !activeRunId || runDetail?.run.status !== "completed") return;
    void loadBacktest(activeRunId);
  }, [terminalPage, activeRunId, runDetail?.run.status, loadBacktest]);

  const progress = computeProgress(runDetail?.run.status, runDetail?.steps.length || 0, runDetail?.run.mode);
  const hasRunningTask = runDetail?.run.status === "queued" || runDetail?.run.status === "running";
  const friendlyError = pickFriendlyError(errorText, locale);
  const uiStage = resolveUiStage(runDetail?.run.status, runDetail?.steps.length || 0, locale);
  const result = runDetail?.result || null;
  const parsedIntent = asRecord(asRecord(result)?.parsed_intent);
  const agentControl = asRecord(parsedIntent?.agent_control);
  const followUpQuestion = toText(asRecord(result)?.follow_up_question, "");
  const missingFields = asStringArray(agentControl?.missing_critical_info).map((item) => readableField(locale, item));
  const decisionSummary = buildDecisionSummary(result, copy, locale);
  const queryText = extractBoundQuery(result, agentForm.query, locale);
  const contextChips = buildContextChips(locale, terminalMode, asOfDate, referenceStartDate, runDetail?.run.status);
  const runUpdatedAt = runDetail
    ? formatDateTime(runDetail.run.updated_at, locale)
    : locale === "zh"
      ? "尚未开始"
      : "Not started";

  const statusCopy = useMemo(() => {
    if (progress.textKey === "queued") return copy.terminal.queued;
    if (progress.textKey === "running") return `${copy.terminal.currentStage}: ${uiStage}`;
    if (progress.textKey === "completed") return copy.terminal.reportReady;
    if (progress.textKey === "cancelled") return copy.terminal.cancelled;
    if (progress.textKey === "failed") return copy.terminal.failed;
    if (progress.textKey === "needs_clarification") return copy.terminal.needClarification;
    return statusText || (locale === "zh" ? "等待任务开始。" : "Waiting to start.");
  }, [copy.terminal, progress.textKey, statusText, uiStage, locale]);

  const uiNotice = useMemo(() => {
    if (runDetail?.run.status === "completed") {
      return {
        tone: "positive",
        title: copy.terminal.uiNotice.successTitle,
        body: copy.terminal.uiNotice.successBody,
      };
    }
    if (runDetail?.run.status === "needs_clarification") {
      return {
        tone: "neutral",
        title: copy.terminal.uiNotice.clarifyTitle,
        body: copy.terminal.uiNotice.clarifyBody,
      };
    }
    if (runDetail?.run.status === "failed") {
      return {
        tone: "negative",
        title: copy.terminal.uiNotice.errorTitle,
        body: friendlyError || copy.terminal.uiNotice.errorBody,
      };
    }
    return null;
  }, [runDetail?.run.status, copy.terminal, friendlyError]);

  const onboardingSteps = [
    {
      title: copy.terminal.onboarding.step1Title,
      body: copy.terminal.onboarding.step1Body,
    },
    {
      title: copy.terminal.onboarding.step2Title,
      body: copy.terminal.onboarding.step2Body,
    },
    {
      title: copy.terminal.onboarding.step3Title,
      body: copy.terminal.onboarding.step3Body,
    },
  ];

  /** 切换动效开关。 */
  function toggleMotion() {
    setMotionEnabled((value) => {
      const next = !value;
      setMotionLevel(next ? "high" : "low");
      return next;
    });
  }

  function continueClarifiedResearch() {
    const baseQuery = extractBoundQuery(result, agentForm.query, locale);
    const extra = clarificationAnswer.trim();
    if (!extra) return;
    const nextQuery =
      locale === "zh"
        ? `${baseQuery}\n补充信息：${extra}`
        : `${baseQuery}\nAdditional details: ${extra}`;
    void createAgentRun(nextQuery);
  }

  return (
    <div className="terminal-route-shell">
      <MotionBackdrop enabled={motionEnabled} level={motionLevel} className="terminal-motion" />

      <header className="front-topbar terminal-topbar">
        <div className="front-brand">
          <p className="eyebrow">{copy.meta.brand}</p>
          <strong>{copy.terminal.title}</strong>
        </div>
        <div className="front-topbar-actions">
          <Button variant="secondary" size="sm" asChild>
            <a href="/">{locale === "zh" ? "返回首页" : "Home"}</a>
          </Button>
          <label className="field compact-field front-locale-field">
            <span>{copy.meta.languageLabel}</span>
            <select value={locale} onChange={(event) => setLocale(event.target.value as typeof locale)}>
              <option value="zh">{copy.meta.languageOptions.zh}</option>
              <option value="en">{copy.meta.languageOptions.en}</option>
            </select>
          </label>
          <Button variant="secondary" size="sm" className="compact-action" onClick={toggleMotion}>
            {locale === "zh" ? `动效${motionEnabled ? "开启" : "关闭"}` : `Motion ${motionEnabled ? "On" : "Off"}`}
          </Button>
        </div>
      </header>

      <TerminalRouteTabs
        locale={locale}
        activePage={terminalPage}
        activeRunId={activeRunId}
        onNavigate={navigateTerminal}
      />

      {terminalPage === "ask" ? (
        <>
          <section className="terminal-page-grid terminal-ask-grid">
            <article className="panel-surface terminal-ask-panel">
              <div className="section-head">
                <div>
                  <p className="eyebrow">{locale === "zh" ? "开始研究" : "Start research"}</p>
                  <h1 className="terminal-ask-title">
                    {locale === "zh" ? "直接写下你的投资问题" : "Ask your investment question directly"}
                  </h1>
                  <p className="section-note terminal-ask-note">
                    {locale === "zh"
                      ? "这一页只负责提问、查看进度和补充必要信息。系统理解、长期记忆和覆盖说明不再占用你的首屏。"
                      : "This page focuses on asking, tracking progress, and supplying follow-up details only. System-side context stays out of the way."}
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

              <div className="terminal-example-block">
                <div className="terminal-example-caption">{locale === "zh" ? "示例问题" : "Example prompts"}</div>
                <div className="terminal-sample-strip">
                  {sampleScenarios.map((scenario) => (
                    <button
                      key={scenario.id}
                      type="button"
                      className="terminal-sample-chip"
                      onClick={() => applySampleScenario(scenario.id)}
                    >
                      {scenario.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="button-row terminal-action-row">
                <Button
                  type="button"
                  className="terminal-primary-cta"
                  disabled={creatingRun || hasRunningTask}
                  onClick={() => void createAgentRun()}
                >
                  {creatingRun
                    ? copy.actions.running
                    : hasRunningTask
                      ? copy.actions.running
                      : terminalMode === "realtime"
                        ? copy.terminal.generateRealtime
                        : copy.terminal.generateHistorical}
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  disabled={!hasRunningTask || cancelingRun}
                  onClick={() => void cancelActiveRun()}
                >
                  {cancelingRun ? copy.actions.cancelling : copy.actions.cancel}
                </Button>
              </div>

              {uiNotice ? (
                <div className={`inline-notice ${uiNotice.tone}`}>
                  <strong>{uiNotice.title}</strong>
                  <p>{uiNotice.body}</p>
                </div>
              ) : null}

              <div className="terminal-details-stack">
                <details className="terminal-inline-details">
                  <summary>
                    <span>{copy.terminal.onboarding.title}</span>
                    <span className="terminal-details-summary-copy">
                      {locale === "zh" ? "非阻断式引导，随时展开查看。" : "Non-blocking guidance you can open anytime."}
                    </span>
                  </summary>
                  <div className="terminal-guide-list">
                    {onboardingSteps.map((item, index) => (
                      <article key={item.title} className="mini-card terminal-guide-item">
                        <span className="mini-label">{locale === "zh" ? `步骤 ${index + 1}` : `Step ${index + 1}`}</span>
                        <strong>{item.title}</strong>
                        <p>{item.body}</p>
                      </article>
                    ))}
                  </div>
                </details>

                <details className="terminal-inline-details">
                  <summary>
                    <span>{locale === "zh" ? "高级设置" : "Advanced settings"}</span>
                    <span className="terminal-details-summary-copy">
                      {terminalMode === "historical"
                        ? locale === "zh"
                          ? "当前为历史研究模式"
                          : "Currently using historical mode"
                        : locale === "zh"
                          ? "当前为实时研究模式"
                          : "Currently using realtime mode"}
                    </span>
                  </summary>
                  <div className="terminal-details-body">
                    <Tabs value={terminalMode} onValueChange={(value) => setTerminalMode(value as "realtime" | "historical")}>
                      <TabsList className="terminal-mode-tabs">
                        <TabsTrigger value="realtime">{copy.terminal.realtime}</TabsTrigger>
                        <TabsTrigger value="historical">{copy.terminal.historical}</TabsTrigger>
                      </TabsList>
                    </Tabs>

                    <div className="field-grid terminal-field-grid">
                      <label className="field compact-field">
                        <span>{copy.control.fields.maxResults}</span>
                        <input
                          type="number"
                          min={1}
                          max={5}
                          value={agentForm.maxResults}
                          onChange={(event) => setAgentForm({ maxResults: Number(event.target.value) || 5 })}
                        />
                      </label>

                      <label className="field compact-field">
                        <span>{locale === "zh" ? "仓位模式" : "Allocation mode"}</span>
                        <select
                          value={agentForm.allocationMode}
                          onChange={(event) =>
                            setAgentForm({ allocationMode: event.target.value as typeof agentForm.allocationMode })
                          }
                        >
                          <option value="score_weighted">{locale === "zh" ? "按评分配比（默认）" : "Score weighted (default)"}</option>
                          <option value="equal_weight">{locale === "zh" ? "等权配置" : "Equal weight"}</option>
                          <option value="custom_weight">{locale === "zh" ? "自定义仓位" : "Custom weights"}</option>
                        </select>
                      </label>

                      {terminalMode === "realtime" ? (
                        <label className="toggle-field">
                          <span>{copy.control.fields.liveData}</span>
                          <input
                            type="checkbox"
                            checked={agentForm.fetchLiveData}
                            onChange={(event) => setAgentForm({ fetchLiveData: event.target.checked })}
                          />
                        </label>
                      ) : (
                        <label className="field compact-field">
                          <span>{copy.terminal.asOfDate}</span>
                          <input type="date" value={asOfDate} onChange={(event) => setAsOfDate(event.target.value)} />
                        </label>
                      )}
                    </div>

                    {terminalMode === "realtime" ? (
                      <div className="field-grid terminal-field-grid">
                        <label className="field compact-field">
                          <span>{copy.terminal.referenceStartDate}</span>
                          <input
                            type="date"
                            value={referenceStartDate}
                            onChange={(event) => setReferenceStartDate(event.target.value)}
                          />
                        </label>
                        <div className="terminal-inline-note">{copy.terminal.realtimeBacktestNote}</div>
                      </div>
                    ) : (
                      <div className="field-grid terminal-field-grid">
                        <label className="field compact-field">
                          <span>{copy.terminal.historicalEndDate}</span>
                          <input
                            type="date"
                            value={historicalBacktestEndDate}
                            onChange={(event) => setHistoricalBacktestEndDate(event.target.value)}
                          />
                        </label>
                        <div className="terminal-inline-note">{copy.terminal.historicalModeNote}</div>
                      </div>
                    )}

                    {agentForm.allocationMode === "custom_weight" ? (
                      <label className="field">
                        <span>{locale === "zh" ? "自定义仓位（总和=100）" : "Custom weights (sum=100)"}</span>
                        <textarea
                          value={agentForm.customWeights}
                          placeholder={
                            locale === "zh" ? "例如：MSFT:40, NVDA:35, AAPL:25" : "Example: MSFT:40, NVDA:35, AAPL:25"
                          }
                          onChange={(event) => setAgentForm({ customWeights: event.target.value })}
                        />
                      </label>
                    ) : null}
                  </div>
                </details>
              </div>
            </article>

            <aside className="terminal-side-stack">
              <article className={`panel-surface terminal-progress-panel progress-${progress.tone}`}>
                <div className="section-head tight">
                  <div>
                    <p className="eyebrow">{locale === "zh" ? "任务进度" : "Task progress"}</p>
                    <h2>{uiStage}</h2>
                  </div>
                  <strong className="terminal-progress-percent">{progress.percent}%</strong>
                </div>
                <div className="terminal-progress-stage-row">
                  <span>{locale === "zh" ? "当前阶段" : "Current stage"}</span>
                  <strong>{uiStage}</strong>
                </div>
                <Progress value={progress.percent} className="terminal-progress-track-strong" />
                <p className="section-note terminal-progress-copy">{statusCopy}</p>
                <div className="terminal-progress-meta">
                  <span>{locale === "zh" ? "最新更新时间" : "Latest update"}</span>
                  <strong>{runUpdatedAt}</strong>
                </div>
              </article>

              <article className="panel-surface terminal-query-card">
                <div className="section-head tight">
                  <div>
                    <p className="eyebrow">{locale === "zh" ? "当前任务" : "Current task"}</p>
                    <h2>{locale === "zh" ? "这次研究绑定的问题" : "The request currently in scope"}</h2>
                  </div>
                </div>
                <div className="terminal-query-body">{queryText}</div>
                <div className="chip-row terminal-chip-wrap">
                  {contextChips.map((item) => (
                    <Badge key={item} variant="outline" className="trust-chip">
                      {item}
                    </Badge>
                  ))}
                </div>
              </article>
            </aside>
          </section>

          {runDetail?.run.status === "needs_clarification" ? (
            <ClarificationContinueCard
              locale={locale}
              followUpQuestion={followUpQuestion}
              missingFields={missingFields}
              clarificationAnswer={clarificationAnswer}
              setClarificationAnswer={setClarificationAnswer}
              onContinue={continueClarifiedResearch}
              creatingRun={creatingRun}
              profilePreferences={profilePreferences}
            />
          ) : null}

          {errorText ? (
            <div className="danger-banner terminal-wide-banner">
              <strong>{copy.terminal.errorHeadline}</strong>
              <p>{friendlyError || errorText}</p>
            </div>
          ) : null}
        </>
      ) : null}

      {terminalPage === "conclusion" ? (
        activeRunId ? (
          runLoading && !runDetail ? (
            <section className="terminal-route-stack">
              <article className="panel-surface terminal-route-header terminal-empty-panel">
                <div className="empty-state">{locale === "zh" ? "正在读取研究结论..." : "Loading research conclusion..."}</div>
              </article>
            </section>
          ) : (
            <>
              <ConclusionSummary
                locale={locale}
                decisionSummary={decisionSummary}
                activeRunId={activeRunId}
                queryText={queryText}
                contextChips={contextChips}
                progress={progress}
                uiStage={uiStage}
                statusCopy={statusCopy}
                runUpdatedAt={runUpdatedAt}
                onNavigate={navigateTerminal}
              />

              {errorText ? (
                <div className="danger-banner terminal-wide-banner">
                  <strong>{copy.terminal.errorHeadline}</strong>
                  <p>{friendlyError || errorText}</p>
                </div>
              ) : null}

              <div className="terminal-report-block">
                <ReportPanel
                  locale={locale}
                  copy={copy}
                  result={result}
                  dataStatus={dataStatus}
                  backtest={backtestDetail}
                  runId={activeRunId}
                  variant="terminal"
                />
              </div>
            </>
          )
        ) : (
          <ConclusionEmptyState locale={locale} onNavigate={navigateTerminal} />
        )
      ) : null}

      {terminalPage === "backtest" ? (
        <BacktestPage
          locale={locale}
          copy={copy}
          activeRunId={activeRunId}
          runDetail={runDetail}
          backtestDetail={backtestDetail}
          backtestLoading={backtestLoading}
          backtestCreating={backtestCreating}
          terminalMode={terminalMode}
          historicalBacktestEndDate={historicalBacktestEndDate}
          setHistoricalBacktestEndDate={setHistoricalBacktestEndDate}
          referenceStartDate={referenceStartDate}
          setReferenceStartDate={setReferenceStartDate}
          runBacktest={runBacktest}
        />
      ) : null}

      {terminalPage === "archive" ? (
        <ArchivePage
          locale={locale}
          historyLoading={historyLoading}
          history={history}
          activeRunId={activeRunId}
          runDetail={runDetail}
          auditSummary={auditSummary}
          onNavigate={navigateTerminal}
        />
      ) : null}
    </div>
  );
}
