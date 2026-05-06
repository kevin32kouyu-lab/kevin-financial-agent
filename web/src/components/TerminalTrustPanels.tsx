/** 结论页可信度概览：展示系统理解、依据、风险和轻量记忆。 */
import { Badge } from "./ui/badge";
import type { StoredIntentMemory } from "../lib/terminalMemory";
import type { Locale } from "../lib/types";

type GenericRecord = Record<string, unknown>;

interface TerminalTrustPanelsProps {
  locale: Locale;
  result: Record<string, unknown> | null;
  memoryPreview: StoredIntentMemory | null;
}

/** 把未知值安全转换成对象。 */
function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

/** 把未知值安全转换成字符串数组。 */
function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}

/** 把未知值安全转换成对象数组。 */
function asRecordArray(value: unknown): GenericRecord[] {
  return Array.isArray(value)
    ? value.filter((item) => item && typeof item === "object") as GenericRecord[]
    : [];
}

/** 把未知值转换成可读文本。 */
function toText(value: unknown, fallback = "N/A"): string {
  const text = String(value ?? "").trim();
  return text || fallback;
}

/** 把内部缺失字段转成用户可读标签。 */
function formatMissingField(locale: Locale, value: string): string {
  const mappingZh: Record<string, string> = {
    capital_amount: "投入金额",
    risk_tolerance: "风险偏好",
    investment_goal: "投资目标",
    investment_horizon: "投资期限",
    investment_style: "投资风格",
    default_market: "默认市场",
    preferred_sectors: "偏好板块",
    preferred_industries: "偏好行业",
    excluded_sectors: "禁投方向",
    excluded_industries: "不感兴趣行业",
    excluded_tickers: "排除标的",
    explicit_tickers: "关注标的",
    fundamental_filters: "筛选条件",
  };
  const mappingEn: Record<string, string> = {
    capital_amount: "capital",
    risk_tolerance: "risk preference",
    investment_goal: "goal",
    investment_horizon: "horizon",
    investment_style: "style",
    preferred_sectors: "sectors",
    preferred_industries: "industries",
    default_market: "default market",
    excluded_sectors: "excluded sectors",
    excluded_industries: "excluded industries",
    excluded_tickers: "excluded tickers",
    explicit_tickers: "focus tickers",
    fundamental_filters: "filters",
  };
  const mapping = locale === "zh" ? mappingZh : mappingEn;
  return mapping[value] || value;
}

/** 说明本次记忆来源。 */
function formatMemorySource(locale: Locale, value: string): string {
  if (value === "account_or_browser_profile") {
    return locale === "zh" ? "来源：账户档案或浏览器记忆" : "Source: account profile or browser memory";
  }
  if (value === "current_input_only") {
    return locale === "zh" ? "来源：仅使用本次输入" : "Source: current input only";
  }
  return "";
}

/** 说明为什么没有使用长期记忆。 */
function formatSkippedReason(locale: Locale, value: string): string {
  if (value === "current_query_too_vague") {
    return locale === "zh"
      ? "本次问题过于模糊，系统没有用长期记忆直接补成投资建议。"
      : "The request was too vague, so long-term memory was not used to produce an investment recommendation.";
  }
  return value;
}

/** 提取前台需要的用户目标快照。 */
function buildMandateSnapshot(locale: Locale, result: Record<string, unknown> | null) {
  const reportBriefing = asRecord(asRecord(result)?.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const userProfile = asRecord(meta?.user_profile);
  const parsedIntent = asRecord(asRecord(result)?.parsed_intent);
  const portfolioSizing = asRecord(parsedIntent?.portfolio_sizing);
  const riskProfile = asRecord(parsedIntent?.risk_profile);
  const strategy = asRecord(parsedIntent?.investment_strategy);
  const explicitTargets = asRecord(parsedIntent?.explicit_targets);

  const capitalAmount = userProfile?.capital_amount ?? portfolioSizing?.capital_amount;
  const currency = userProfile?.currency ?? portfolioSizing?.currency;
  const riskTolerance = userProfile?.risk_tolerance ?? riskProfile?.tolerance_level;
  const horizon = userProfile?.investment_horizon ?? strategy?.horizon;
  const style = userProfile?.investment_style ?? strategy?.style;
  const explicitTickers = asStringArray(userProfile?.explicit_tickers ?? explicitTargets?.tickers);
  const preferredSectors = asStringArray(userProfile?.preferred_sectors ?? strategy?.preferred_sectors);
  const preferredIndustries = asStringArray(userProfile?.preferred_industries ?? strategy?.preferred_industries);

  const facts = [
    capitalAmount
      ? locale === "zh"
        ? `资金 ${capitalAmount} ${toText(currency, "USD")}`
        : `Capital ${capitalAmount} ${toText(currency, "USD")}`
      : null,
    riskTolerance
      ? locale === "zh"
        ? `风险 ${riskTolerance}`
        : `Risk ${riskTolerance}`
      : null,
    horizon
      ? locale === "zh"
        ? `期限 ${horizon}`
        : `Horizon ${horizon}`
      : null,
    style
      ? locale === "zh"
        ? `风格 ${style}`
        : `Style ${style}`
      : null,
  ].filter(Boolean) as string[];

  return {
    summary: toText(
      userProfile?.summary,
      locale === "zh" ? "系统会在这里总结它理解到的资金、风险、期限和关注方向。" : "The system will summarize the mandate here.",
    ),
    facts,
    explicitTickers,
    preferredSectors,
    preferredIndustries,
  };
}

/** 生成轻量记忆可读说明。 */
function buildMemoryFallback(locale: Locale, memoryPreview: StoredIntentMemory | null) {
  if (!memoryPreview) return null;
  const parts = [
    memoryPreview.risk_tolerance
      ? locale === "zh"
        ? `风险 ${memoryPreview.risk_tolerance}`
        : `risk ${memoryPreview.risk_tolerance}`
      : "",
    memoryPreview.investment_horizon
      ? locale === "zh"
        ? `期限 ${memoryPreview.investment_horizon}`
        : `horizon ${memoryPreview.investment_horizon}`
      : "",
    memoryPreview.investment_style
      ? locale === "zh"
        ? `风格 ${memoryPreview.investment_style}`
        : `style ${memoryPreview.investment_style}`
      : "",
  ].filter(Boolean);
  if (!parts.length) return null;
  return locale === "zh"
    ? `如果这次问题没有写清楚，系统会优先沿用最近一次的偏好：${parts.join(" / ")}。`
    : `If the new request omits key preferences, the system will reuse your latest settings first: ${parts.join(" / ")}.`;
}

/** 结论页可信度概览组件。 */
export function TerminalTrustPanels({ locale, result, memoryPreview }: TerminalTrustPanelsProps) {
  const reportBriefing = asRecord(asRecord(result)?.report_briefing);
  const meta = asRecord(reportBriefing?.meta);
  const parsedIntent = asRecord(asRecord(result)?.parsed_intent);
  const agentControl = asRecord(parsedIntent?.agent_control);
  const evidenceSummary = asRecord(meta?.evidence_summary);
  const validationSummary = asRecord(meta?.validation_summary);
  const safetySummary = asRecord(meta?.safety_summary);
  const memorySummary = asRecord(asRecord(result)?.memory_summary);
  const memoryUsageSummary = asRecord(asRecord(result)?.memory_usage_summary);
  const evidenceObjects = asRecordArray(meta?.evidence_items);
  const memoryAppliedLabels = asStringArray(memoryUsageSummary?.applied_labels);
  const memoryAppliedFields = (
    memoryAppliedLabels.length
      ? memoryAppliedLabels
      : asStringArray(memoryUsageSummary?.applied_fields).length
        ? asStringArray(memoryUsageSummary?.applied_fields).map((item) => formatMissingField(locale, item))
        : asStringArray(asRecord(result)?.memory_applied_fields).map((item) => formatMissingField(locale, item))
  );
  const missingNotAssumed = asStringArray(memoryUsageSummary?.unused_missing_fields).map((item) => formatMissingField(locale, item));
  const memorySource = formatMemorySource(locale, String(memoryUsageSummary?.source || ""));
  const memorySkippedReason = formatSkippedReason(locale, String(memoryUsageSummary?.skipped_reason || ""));
  const coverageFlags = asStringArray(meta?.coverage_flags);
  const confidenceLevel = toText(meta?.confidence_level, "");
  const followUpQuestion = toText(asRecord(result)?.follow_up_question, "");
  const missingFields = asStringArray(agentControl?.missing_critical_info).map((item) => formatMissingField(locale, item));
  const snapshot = buildMandateSnapshot(locale, result);
  const evidenceItems = asStringArray(evidenceSummary?.items);
  const evidenceSources = asStringArray(evidenceSummary?.source_points);
  const validationItems = asStringArray(validationSummary?.items);
  const degradedModules = asStringArray(safetySummary?.degraded_modules);
  const usedSources = asStringArray(safetySummary?.used_sources);
  const memoryNote = toText(
    memoryUsageSummary?.note,
    toText(
      memorySummary?.note,
      buildMemoryFallback(locale, memoryPreview) ||
        (locale === "zh" ? "如果问题缺少风险、期限或风格，系统会优先复用最近一次的偏好。" : "The system can reuse recent preferences when risk, horizon or style is omitted."),
    ),
  );

  return (
    <section className="terminal-trust-grid">
      <article className="mini-card terminal-trust-card">
        <div className="section-head tight">
          <div>
            <p className="eyebrow">{locale === "zh" ? "系统理解" : "System understanding"}</p>
            <h3>{locale === "zh" ? "这次研究会按什么目标来做" : "How this run is being framed"}</h3>
          </div>
        </div>
        <p className="terminal-trust-summary">{snapshot.summary}</p>
        {snapshot.facts.length ? (
          <div className="chip-row terminal-chip-wrap">
            {snapshot.facts.map((item) => (
              <Badge key={item} variant="outline" className="trust-chip">
                {item}
              </Badge>
            ))}
          </div>
        ) : null}
        {snapshot.explicitTickers.length ? (
          <div className="terminal-trust-tag-group">
            <span className="terminal-trust-tag-label">{locale === "zh" ? "关注标的" : "Focus tickers"}</span>
            <div className="chip-row terminal-chip-wrap">
              {snapshot.explicitTickers.map((item) => (
                <Badge key={item} variant="outline" className="trust-chip">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        {snapshot.preferredSectors.length || snapshot.preferredIndustries.length ? (
          <div className="terminal-trust-tag-group">
            <span className="terminal-trust-tag-label">{locale === "zh" ? "偏好方向" : "Preferred areas"}</span>
            <div className="chip-row terminal-chip-wrap">
              {snapshot.preferredSectors.map((item) => (
                <Badge key={`sector-${item}`} variant="outline" className="trust-chip">
                  {item}
                </Badge>
              ))}
              {snapshot.preferredIndustries.map((item) => (
                <Badge key={`industry-${item}`} variant="outline" className="trust-chip">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </article>

      <article className="mini-card terminal-trust-card">
        <div className="section-head tight">
          <div>
            <p className="eyebrow">{locale === "zh" ? "依据摘要" : "Evidence"}</p>
            <h3>{locale === "zh" ? "系统为什么给出这个结论" : "Why the system reached this verdict"}</h3>
          </div>
        </div>
        <p className="terminal-trust-summary">
          {toText(
            evidenceSummary?.headline,
            locale === "zh" ? "完成研究后，这里会显示本次结论最主要的依据。" : "The strongest supporting evidence will appear here after the run completes.",
          )}
        </p>
        {evidenceItems.length ? (
          <ul className="compact-list terminal-trust-list">
            {evidenceItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
        {evidenceObjects.length ? (
          <ul className="compact-list terminal-trust-list">
            {evidenceObjects.slice(0, 3).map((item, index) => {
              const summary = toText(item.summary, "");
              const sourceLabel = toText(item.source_label, locale === "zh" ? "未知来源" : "Unknown source");
              const timeHint = toText(item.time_hint, "");
              const confidence = toText(item.confidence, "");
              if (!summary) return null;
              return (
                <li key={`${sourceLabel}-${index}`}>
                  {summary}
                  <br />
                  <span className="terminal-trust-footnote">
                    {sourceLabel}
                    {timeHint ? ` · ${timeHint}` : ""}
                    {confidence ? ` · ${locale === "zh" ? "可信度" : "Confidence"} ${confidence}` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : null}
        {evidenceSources.length ? (
          <div className="terminal-trust-source-list">
            {evidenceSources.map((item) => (
              <span key={item} className="terminal-source-pill">
                {item}
              </span>
            ))}
          </div>
        ) : null}
      </article>

      <article className="mini-card terminal-trust-card">
        <div className="section-head tight">
          <div>
            <p className="eyebrow">{locale === "zh" ? "谨慎提示" : "Caveats"}</p>
            <h3>{locale === "zh" ? "使用结论前先看这几条" : "Read these caveats before acting"}</h3>
          </div>
        </div>
        <p className="terminal-trust-summary">
          {toText(
            validationSummary?.headline,
            locale === "zh" ? "研究完成后，这里会总结需要保守解读的地方。" : "This section summarizes where the result should be read conservatively.",
          )}
        </p>
        {validationItems.length ? (
          <ul className="compact-list terminal-trust-list">
            {validationItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
        {degradedModules.length ? (
          <div className="terminal-trust-subnote">
            <strong>{locale === "zh" ? "数据降级" : "Degraded coverage"}</strong>
            <ul className="compact-list terminal-trust-list">
              {degradedModules.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
        {coverageFlags.length ? (
          <div className="terminal-trust-subnote">
            <strong>{locale === "zh" ? "覆盖提醒" : "Coverage flags"}</strong>
            <ul className="compact-list terminal-trust-list">
              {coverageFlags.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </article>

      <article className="mini-card terminal-trust-card">
        <div className="section-head tight">
          <div>
            <p className="eyebrow">{locale === "zh" ? "记忆与覆盖" : "Memory & coverage"}</p>
            <h3>{locale === "zh" ? "系统沿用了什么、这次用了哪些数据" : "What was reused and which data was used"}</h3>
          </div>
        </div>
        <p className="terminal-trust-summary">{memoryNote}</p>
        {memorySource ? <p className="terminal-trust-footnote">{memorySource}</p> : null}
        {usedSources.length ? (
          <div className="terminal-trust-source-list">
            {usedSources.map((item) => (
              <span key={item} className="terminal-source-pill">
                {item}
              </span>
            ))}
          </div>
        ) : null}
        {memoryAppliedFields.length ? (
          <div className="terminal-trust-subnote">
            <strong>{locale === "zh" ? "本次沿用的偏好" : "Reused preferences"}</strong>
            <div className="chip-row terminal-chip-wrap">
              {memoryAppliedFields.map((item) => (
                <Badge key={item} variant="outline" className="trust-chip">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        {missingNotAssumed.length ? (
          <div className="terminal-trust-subnote">
            <strong>{locale === "zh" ? "本次没有自动假设的信息" : "Missing details not assumed"}</strong>
            <div className="chip-row terminal-chip-wrap">
              {missingNotAssumed.map((item) => (
                <Badge key={item} variant="outline" className="trust-chip">
                  {item}
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
        {memorySkippedReason ? <p className="terminal-trust-footnote">{memorySkippedReason}</p> : null}
        {confidenceLevel ? (
          <p className="terminal-trust-footnote">
            {locale === "zh" ? "当前可信度等级" : "Current confidence level"}: {confidenceLevel}
          </p>
        ) : null}
        <p className="terminal-trust-footnote">
          {toText(
            safetySummary?.headline,
            locale === "zh"
              ? "系统会明确标出哪些数据源可用、哪些模块需要保守解读。"
              : "The system will explicitly show which data sources were used and where coverage was degraded.",
          )}
        </p>
      </article>

      {followUpQuestion || missingFields.length ? (
        <article className="mini-card terminal-trust-card terminal-clarify-card">
          <div className="section-head tight">
            <div>
              <p className="eyebrow">{locale === "zh" ? "补充追问" : "Clarification"}</p>
              <h3>{locale === "zh" ? "还差这一点信息，系统就能继续" : "One more detail and the run can continue"}</h3>
            </div>
          </div>
          <p className="terminal-trust-summary">
            {followUpQuestion ||
              (locale === "zh"
                ? "请补充下面这些核心条件后继续。"
                : "Please fill the missing core details below.")}
          </p>
          {missingFields.length ? (
            <div className="chip-row terminal-chip-wrap">
              {missingFields.map((item) => (
                <Badge key={item} variant="outline" className="trust-chip">
                  {item}
                </Badge>
              ))}
            </div>
          ) : null}
        </article>
      ) : null}
    </section>
  );
}
