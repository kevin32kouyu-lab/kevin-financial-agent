/** 终端轻量记忆与标准示例问题。 */
import type { AgentMemoryContext, Locale, TerminalMode } from "./types";

const MEMORY_STORAGE_KEY = "financial-agent-intent-memory-v1";

type GenericRecord = Record<string, unknown>;

export interface StoredIntentMemory extends AgentMemoryContext {
  locale: Locale;
  savedAt: string;
}

export interface SampleScenario {
  id: string;
  label: string;
  query: string;
  terminalMode: TerminalMode;
  asOfDate?: string;
  historicalEndDate?: string;
  referenceStartDate?: string;
}

function asRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.map((item) => String(item || "").trim()).filter(Boolean)
    : [];
}

function normalizeMemory(memory: StoredIntentMemory | null): StoredIntentMemory | null {
  if (!memory) return null;
  return {
    locale: memory.locale,
    capital_amount: memory.capital_amount || null,
    capital_range_min: memory.capital_range_min || null,
    capital_range_max: memory.capital_range_max || null,
    currency: memory.currency || null,
    risk_tolerance: memory.risk_tolerance || null,
    investment_goal: memory.investment_goal || null,
    investment_horizon: memory.investment_horizon || null,
    investment_style: memory.investment_style || null,
    default_market: memory.default_market || null,
    preferred_sectors: Array.from(new Set(asStringArray(memory.preferred_sectors))),
    preferred_industries: Array.from(new Set(asStringArray(memory.preferred_industries))),
    excluded_sectors: Array.from(new Set(asStringArray(memory.excluded_sectors))),
    excluded_industries: Array.from(new Set(asStringArray(memory.excluded_industries))),
    excluded_tickers: Array.from(new Set(asStringArray(memory.excluded_tickers))),
    explicit_tickers: Array.from(new Set(asStringArray(memory.explicit_tickers))),
    savedAt: memory.savedAt,
  };
}

/** 读取当前语言对应的轻量记忆。 */
export function readIntentMemory(locale: Locale): StoredIntentMemory | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(MEMORY_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Record<string, StoredIntentMemory>;
    return normalizeMemory(parsed[locale] || null);
  } catch {
    return null;
  }
}

/** 保存当前语言对应的轻量记忆。 */
export function writeIntentMemory(memory: StoredIntentMemory) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(MEMORY_STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as Record<string, StoredIntentMemory>) : {};
    parsed[memory.locale] = normalizeMemory(memory) || memory;
    window.localStorage.setItem(MEMORY_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // 忽略本地存储失败，避免打断主流程。
  }
}

/** 清空当前语言对应的轻量记忆。 */
export function clearIntentMemory(locale: Locale) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(MEMORY_STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Record<string, StoredIntentMemory>;
    delete parsed[locale];
    window.localStorage.setItem(MEMORY_STORAGE_KEY, JSON.stringify(parsed));
  } catch {
    // 忽略本地存储失败，避免打断主流程。
  }
}

/** 从解析后的意图中提取可复用的轻量记忆。 */
export function buildMemoryFromParsedIntent(parsedIntent: unknown, locale: Locale): StoredIntentMemory | null {
  const intent = asRecord(parsedIntent);
  const portfolioSizing = asRecord(intent?.portfolio_sizing);
  const riskProfile = asRecord(intent?.risk_profile);
  const strategy = asRecord(intent?.investment_strategy);
  const explicitTargets = asRecord(intent?.explicit_targets);

  const memory: StoredIntentMemory = {
    locale,
    capital_amount: Number(portfolioSizing?.capital_amount || 0) || null,
    capital_range_min: Number(portfolioSizing?.capital_range_min || 0) || null,
    capital_range_max: Number(portfolioSizing?.capital_range_max || 0) || null,
    currency: String(portfolioSizing?.currency || "").trim() || null,
    risk_tolerance: String(riskProfile?.tolerance_level || "").trim() || null,
    investment_goal: String(strategy?.goal || strategy?.investment_goal || "").trim() || null,
    investment_horizon: String(strategy?.horizon || "").trim() || null,
    investment_style: String(strategy?.style || "").trim() || null,
    default_market: String(strategy?.default_market || intent?.default_market || "").trim() || null,
    preferred_sectors: asStringArray(strategy?.preferred_sectors),
    preferred_industries: asStringArray(strategy?.preferred_industries),
    excluded_sectors: asStringArray(strategy?.excluded_sectors),
    excluded_industries: asStringArray(strategy?.excluded_industries),
    excluded_tickers: asStringArray(explicitTargets?.excluded_tickers),
    explicit_tickers: asStringArray(explicitTargets?.tickers),
    savedAt: new Date().toISOString(),
  };

  if (
    !memory.capital_amount &&
    !memory.capital_range_min &&
    !memory.capital_range_max &&
    !memory.risk_tolerance &&
    !memory.investment_goal &&
    !memory.investment_horizon &&
    !memory.investment_style &&
    !memory.default_market &&
    !(memory.preferred_sectors || []).length &&
    !(memory.preferred_industries || []).length &&
    !(memory.excluded_sectors || []).length &&
    !(memory.excluded_industries || []).length &&
    !(memory.excluded_tickers || []).length &&
    !(memory.explicit_tickers || []).length
  ) {
    return null;
  }
  return normalizeMemory(memory);
}

/** 返回 3 条适合快速试用的标准问题。 */
export function getSampleScenarios(locale: Locale): SampleScenario[] {
  return [
    {
      id: "steady-income",
      label: locale === "zh" ? "中文稳健型" : "Chinese defensive",
      terminalMode: "realtime",
      referenceStartDate: "2025-10-21",
      query:
        "我有 50000 美元，想找适合长期持有的低风险分红股。请优先比较 JNJ、PG、KO，并给我正式研究结论，包括估值、ROE、自由现金流、主要风险和分批建仓建议。",
    },
    {
      id: "growth-english",
      label: locale === "zh" ? "英文成长型" : "English growth",
      terminalMode: "realtime",
      referenceStartDate: "2025-10-21",
      query:
        "I have $100,000 and want long-term growth with controlled risk. Please compare MSFT, GOOGL, AMZN and META, then give me a formal investment memo with staged entry advice.",
    },
    {
      id: "historical-replay",
      label: locale === "zh" ? "历史回测型" : "Historical replay",
      terminalMode: "historical",
      asOfDate: "2025-10-01",
      historicalEndDate: "2026-04-13",
      query:
        locale === "zh"
          ? "请以 2025-10-01 作为历史研究时点，给出同样风格的投资建议，并回放到 2026-04-13，展示组合收益与 SPY 对比。"
          : "Use 2025-10-01 as the historical research date, then replay the recommendation to 2026-04-13 and compare the portfolio with SPY.",
    },
  ];
}
