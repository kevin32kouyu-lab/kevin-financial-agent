/** 终端体验辅助：负责生成提问引导、可信度摘要和连续研究文案。 */
import { repairText } from "./format";
import type { BacktestDetail, Locale } from "./types";

type GenericRecord = Record<string, unknown>;

export interface PromptChip {
  label: string;
  text: string;
}

export type ResearchEntryMode = "single" | "portfolio" | "monitor";

export interface ResearchEntryModeOption {
  key: ResearchEntryMode;
  label: string;
  body: string;
  placeholder: string;
}

export interface PreviewStep {
  title: string;
  body: string;
}

export interface RecommendedHolding {
  ticker: string;
  weight: number | null;
  verdict: string;
}

export interface TrustSummary {
  evidenceCount: number;
  latestEvidenceDate: string;
  confidenceLevel: string;
  candidateCount: number;
  validationLabel: string;
  backtestLabel: string;
  degradedModules: string[];
  holdings: RecommendedHolding[];
}

/** 安全读取对象。 */
export function asTerminalRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

/** 安全读取对象数组。 */
export function asTerminalRecordArray(value: unknown): GenericRecord[] {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") as GenericRecord[] : [];
}

/** 安全读取字符串数组。 */
export function asTerminalStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => repairText(item, "")).filter(Boolean) : [];
}

/** 生成开始研究页的三种起点。 */
export function buildResearchEntryModes(locale: Locale): ResearchEntryModeOption[] {
  if (locale === "zh") {
    return [
      {
        key: "single",
        label: "单次问题",
        body: "先提出一个清晰问题，系统会帮你筛选、验证并给出可执行结论。",
        placeholder: "例如：我有 10 万美元，风险偏中等，想找未来 3 到 5 年值得配置的美股。",
      },
      {
        key: "portfolio",
        label: "组合研究",
        body: "按组合角度给出仓位，而不是只回答一只股票值不值得买。",
        placeholder: "例如：我想用 20 万美元做一个偏稳健的美股组合，请给我 3 到 5 只核心持仓和建议权重。",
      },
      {
        key: "monitor",
        label: "持续跟踪",
        body: "把上一条观点带回来，继续判断现在有没有必要调整结论。",
        placeholder: "例如：继续跟踪我上次关于 MSFT 和 NVDA 的研究，告诉我最近哪些变化会影响原结论。",
      },
    ];
  }
  return [
    {
      key: "single",
      label: "Single question",
      body: "Start with one clear investment question and let the system narrow it down.",
      placeholder: "For example: I have $100k, medium risk tolerance, and want US stocks to hold for 3 to 5 years.",
    },
    {
      key: "portfolio",
      label: "Portfolio research",
      body: "Get a sized basket instead of a single ticker.",
      placeholder: "For example: Build a conservative US equity portfolio for $200k with 3 to 5 core holdings and suggested weights.",
    },
    {
      key: "monitor",
      label: "Ongoing tracking",
      body: "Bring back an earlier thesis and monitor what changed.",
      placeholder: "For example: Continue monitoring my MSFT and NVDA thesis and explain what has changed since the last run.",
    },
  ];
}

/** 生成开始研究页的结构化补充 chips。 */
export function buildPromptChips(locale: Locale, mode: ResearchEntryMode = "single"): PromptChip[] {
  if (locale === "zh") {
    const base = [
      { label: "低风险", text: "我更偏向低风险、回撤小的配置。" },
      { label: "长期", text: "我准备至少持有 3 年以上。" },
      { label: "分红", text: "我更看重稳定分红和现金流质量。" },
      { label: "成长", text: "我接受更高波动，优先看成长性。" },
    ];
    if (mode === "portfolio") {
      return [
        ...base,
        { label: "分散配置", text: "请把建议分散到几只核心持仓，不要只推荐一只股票。" },
        { label: "仓位建议", text: "请给出建议仓位和调仓顺序。" },
      ];
    }
    if (mode === "monitor") {
      return [
        ...base,
        { label: "继续跟踪", text: "请重点说明和上一次研究相比，哪些结论变了，哪些没有变。" },
        { label: "变化信号", text: "请列出后续最值得持续跟踪的信号。" },
      ];
    }
    return [
      ...base,
      { label: "估值优先", text: "请优先考虑估值和安全边际。" },
      { label: "单票深挖", text: "请把最适合我的优先标的讲清楚。" },
    ];
  }
  const base = [
    { label: "Low risk", text: "I prefer a lower-risk allocation with smaller drawdowns." },
    { label: "Long term", text: "I plan to hold for at least 3 years." },
    { label: "Dividend", text: "Please prioritize durable dividends and cash-flow quality." },
    { label: "Growth", text: "I can accept more volatility for stronger growth." },
  ];
  if (mode === "portfolio") {
    return [
      ...base,
      { label: "Diversify", text: "Please spread the recommendation across a few core holdings instead of only one stock." },
      { label: "Sizing", text: "Please include suggested weights and execution order." },
    ];
  }
  if (mode === "monitor") {
    return [
      ...base,
      { label: "Follow-up", text: "Please focus on what changed versus the last research run and what has stayed intact." },
      { label: "Signals", text: "Please list the signals I should keep monitoring next." },
    ];
  }
  return [
    ...base,
    { label: "Valuation", text: "Please prioritize valuation and downside protection." },
    { label: "Deep dive", text: "Please explain the best-fit primary pick in detail." },
  ];
}

/** 生成开始研究页的四步预览。 */
export function buildResearchPreview(locale: Locale, mode: ResearchEntryMode = "single"): PreviewStep[] {
  if (locale === "zh") {
    return [
      {
        title: "筛选股票池",
        body:
          mode === "portfolio"
            ? "先按你的风险和目标划出适合组合的候选范围。"
            : mode === "monitor"
              ? "先回看上次的核心观点和当前需要跟踪的标的。"
              : "先按你的风险、期限和偏好缩小候选范围。",
      },
      { title: "拉取关键数据", body: "再取价格、新闻、SEC、评分和宏观信息。" },
      {
        title: "交叉验证依据",
        body: mode === "monitor" ? "重点看新变化是否足以推翻原结论。" : "检查证据日期、降级情况和结论一致性。",
      },
      {
        title: "生成双报告",
        body: mode === "portfolio" ? "最后给组合建议、执行顺序和双报告。" : "最后给投资报告、开发报告和可导出 PDF。",
      },
    ];
  }
  return [
    {
      title: "Screen the universe",
      body:
        mode === "portfolio"
          ? "Shape a candidate set that fits the whole portfolio goal first."
          : mode === "monitor"
            ? "Re-open the earlier thesis and the names that need monitoring."
            : "Narrow the candidate list around your mandate first.",
    },
    { title: "Pull market evidence", body: "Fetch price, news, SEC, score, and macro inputs." },
    {
      title: "Cross-check evidence",
      body:
        mode === "monitor"
          ? "Check whether the new evidence changes the earlier thesis."
          : "Check freshness, fallbacks, and conclusion consistency.",
    },
    {
      title: "Generate both reports",
      body:
        mode === "portfolio"
          ? "Deliver sizing guidance, an execution plan, and both reports."
          : "Deliver the investment report, development report, and export-ready PDF.",
    },
  ];
}

/** 把结构化提示安全追加到问题里。 */
export function appendPromptChip(query: string, chipText: string): string {
  const base = repairText(query, "").trim();
  if (!base) return chipText;
  if (base.includes(chipText)) return base;
  return `${base}\n${chipText}`.trim();
}

/** 构建继续跟进用的问题模板。 */
export function buildFollowUpQuery(baseQuery: string, locale: Locale, topPick = ""): string {
  const query = repairText(baseQuery, "").trim();
  const pick = repairText(topPick, "").trim();
  if (locale === "zh") {
    const suffix = pick
      ? `请基于最新数据继续跟进这次研究，重点看 ${pick} 的结论有没有变化，并给出新的执行建议。`
      : "请基于最新数据继续跟进这次研究，说明结论是否变化，并给出新的执行建议。";
    return [query, suffix].filter(Boolean).join("\n");
  }
  const suffix = pick
    ? `Please continue monitoring this thesis with the latest data, focus on whether the view on ${pick} has changed, and give an updated action plan.`
    : "Please continue monitoring this thesis with the latest data, explain whether the conclusion has changed, and give an updated action plan.";
  return [query, suffix].filter(Boolean).join("\n");
}

/** 从报告结果里提取用户可读的可信度摘要。 */
export function buildTrustSummary(
  result: Record<string, unknown> | null,
  backtest?: BacktestDetail | null,
  locale: Locale = "en",
): TrustSummary {
  const reportBriefing = asTerminalRecord(asTerminalRecord(result)?.report_briefing);
  const meta = asTerminalRecord(reportBriefing?.meta);
  const executive = asTerminalRecord(reportBriefing?.executive);
  const scoreboard = asTerminalRecordArray(reportBriefing?.scoreboard);
  const evidence = asTerminalRecordArray(meta?.retrieved_evidence);
  const validationChecks = asTerminalRecordArray(meta?.validation_checks);
  const degradedModules = asTerminalStringArray(asTerminalRecord(meta?.safety_summary)?.degraded_modules);
  const latestEvidenceDate = evidence
    .map((item) => repairText(item.published_at || item.as_of_date, ""))
    .filter(Boolean)
    .sort();
  const holdings = asTerminalRecordArray(executive?.allocation_plan)
    .slice(0, 5)
    .map((item) => ({
      ticker: repairText(item.ticker, "N/A"),
      weight: Number.isFinite(Number(item.weight)) ? Number(item.weight) : null,
      verdict: repairText(item.verdict, locale === "zh" ? "建议持有" : "Included"),
    }));
  const confidence = repairText(meta?.confidence_level, locale === "zh" ? "待校验" : "Pending");
  const validationLabel =
    validationChecks.length || degradedModules.length
      ? locale === "zh"
        ? "已校验，带提醒"
        : "Checked with caveats"
      : locale === "zh"
        ? "已校验"
        : "Checked";
  const investmentOutput = asTerminalRecord(asTerminalRecord(result)?.report_outputs)?.investment;
  const investmentCharts = asTerminalRecord(asTerminalRecord(investmentOutput)?.charts);
  const backtestChart = asTerminalRecord(investmentCharts?.portfolio_vs_benchmark_backtest);
  const backtestAvailable = Boolean(backtest?.summary) || repairText(backtestChart?.status, "") === "available";

  return {
    evidenceCount: evidence.length,
    latestEvidenceDate: latestEvidenceDate[latestEvidenceDate.length - 1] || (locale === "zh" ? "未标注" : "Undated"),
    confidenceLevel: confidence,
    candidateCount: Number(meta?.ticker_count) || scoreboard.length,
    validationLabel,
    backtestLabel: backtestAvailable
      ? locale === "zh"
        ? "可查看"
        : "Available"
      : locale === "zh"
        ? "未生成"
        : "Not ready",
    degradedModules,
    holdings,
  };
}
