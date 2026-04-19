import type { Locale, RunMode, RunStatus } from "./types";

export function repairText(value: unknown, fallback = "N/A"): string {
  const text = String(value ?? "").trim();
  if (!text) return fallback;

  const repaired = text
    .replace(/�/g, "")
    .replace(/銆/g, "。")
    .replace(/鈥/g, "\"")
    .replace(/锛/g, "，")
    .replace(/锟/g, "");
  if (!repaired.trim()) return fallback;
  return repaired;
}

export function formatRunTitle(value: unknown, locale: Locale): string {
  const text = repairText(value, "");
  if (!text) return locale === "zh" ? "未命名报告" : "Untitled report";
  return text;
}

export function splitLines(value: string): string[] {
  return String(value || "")
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function formatDateTime(value: unknown, locale: Locale): string {
  const text = repairText(value, "");
  if (!text) return locale === "zh" ? "暂无" : "N/A";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return date.toLocaleString(locale === "zh" ? "zh-CN" : "en-US", { hour12: false });
}

export function formatDate(value: unknown, locale: Locale): string {
  const text = repairText(value, "");
  if (!text) return locale === "zh" ? "暂无" : "N/A";
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return date.toLocaleDateString(locale === "zh" ? "zh-CN" : "en-US");
}

export function formatDuration(value?: number | null, locale: Locale = "zh"): string {
  if (value === undefined || value === null || Number.isNaN(value)) return locale === "zh" ? "暂无" : "N/A";
  if (value < 1000) return `${value.toFixed(0)} ms`;
  return `${(value / 1000).toFixed(2)} s`;
}

export function formatRunMode(mode: RunMode, locale: Locale): string {
  if (locale === "zh") return mode === "agent" ? "自然语言研究" : "结构化筛选";
  return mode === "agent" ? "Research agent" : "Structured screener";
}

export function formatRunStatus(status: RunStatus | string, locale: Locale): string {
  const zhMapping: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    cancelled: "已撤回",
    needs_clarification: "需要补充信息",
    fallback: "备选输出",
  };
  const enMapping: Record<string, string> = {
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
    cancelled: "Cancelled",
    needs_clarification: "Needs clarification",
    fallback: "Fallback",
  };
  const mapping = locale === "zh" ? zhMapping : enMapping;
  return mapping[status] || repairText(status, locale === "zh" ? "未知" : "Unknown");
}

export function formatJson(value: unknown): string {
  return JSON.stringify(value ?? null, null, 2);
}

export function summarizeValue(value: unknown, locale: Locale): string {
  if (value === null || value === undefined) return locale === "zh" ? "空" : "Empty";
  if (typeof value === "string") {
    const text = repairText(value);
    return text.length > 120 ? `${text.slice(0, 120)}...` : text;
  }
  if (Array.isArray(value)) return locale === "zh" ? `数组(${value.length})` : `Array(${value.length})`;
  if (typeof value === "object") {
    const size = Object.keys(value as Record<string, unknown>).length;
    return locale === "zh" ? `对象(${size})` : `Object(${size})`;
  }
  return repairText(value);
}

export function formatScore(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return "N/A";
  return number.toFixed(1);
}

export function formatPercent(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return "N/A";
  return `${number.toFixed(1)}%`;
}

export function formatCurrency(value: unknown, locale: Locale, currency = "USD"): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) return "N/A";
  try {
    return new Intl.NumberFormat(locale === "zh" ? "zh-CN" : "en-US", {
      style: "currency",
      currency,
      maximumFractionDigits: 2,
    }).format(number);
  } catch {
    return `${currency} ${number.toFixed(2)}`;
  }
}
