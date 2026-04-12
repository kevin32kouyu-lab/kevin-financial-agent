import type { Locale, RunMode, RunStatus } from "./types";

const MOJIBAKE_PATTERN = /[闁煎瓨鐟ㄩ崜纭呯疀濞嗘帒绠洪柤鐓庢噽鐏忔鏌ㄥ顓犳▍闁告鍨电€垫洘绋婇崼鐔轰海婵炲矉绱曞﹢渚€宕橀幒妤佹櫢缂佸弶鎽穄]/;

function tryDecodeMojibake(text: string): string {
  if (!MOJIBAKE_PATTERN.test(text)) {
    return text;
  }
  try {
    return decodeURIComponent(escape(text));
  } catch {
    return text;
  }
}

function looksCorrupted(text: string): boolean {
  if (!text) {
    return false;
  }
  const questionMarks = [...text].filter((char) => char === "?").length;
  return text.includes("\ufffd") || (questionMarks >= 4 && questionMarks / text.length > 0.18);
}

export function repairText(value: unknown, fallback = "N/A"): string {
  const text = String(value ?? "").trim();
  if (!text) {
    return fallback;
  }
  return tryDecodeMojibake(text);
}

export function formatRunTitle(value: unknown, locale: Locale): string {
  const text = repairText(value, "");
  if (!text) {
    return locale === "zh" ? "未命名报告" : "Untitled report";
  }
  if (looksCorrupted(text)) {
    return locale === "zh" ? "历史报告（标题编码异常）" : "Archived report (title encoding issue)";
  }
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
  if (!text) {
    return locale === "zh" ? "暂无" : "N/A";
  }

  const date = new Date(text);
  if (Number.isNaN(date.getTime())) {
    return text;
  }

  return date.toLocaleString(locale === "zh" ? "zh-CN" : "en-US", { hour12: false });
}

export function formatDuration(value?: number | null, locale: Locale = "zh"): string {
  if (value === undefined || value === null || Number.isNaN(value)) {
    return locale === "zh" ? "暂无" : "N/A";
  }
  if (value < 1000) {
    return `${value.toFixed(0)} ms`;
  }
  return `${(value / 1000).toFixed(2)} s`;
}

export function formatRunMode(mode: RunMode, locale: Locale): string {
  if (locale === "zh") {
    return mode === "agent" ? "自然语言研究" : "结构化筛选";
  }
  return mode === "agent" ? "Research agent" : "Structured screener";
}

export function formatRunStatus(status: RunStatus | string, locale: Locale): string {
  const zhMapping: Record<string, string> = {
    queued: "排队中",
    running: "运行中",
    completed: "已完成",
    failed: "失败",
    needs_clarification: "需要补充信息",
    fallback: "备用输出",
  };
  const enMapping: Record<string, string> = {
    queued: "Queued",
    running: "Running",
    completed: "Completed",
    failed: "Failed",
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
  if (value === null || value === undefined) {
    return locale === "zh" ? "空" : "Empty";
  }
  if (typeof value === "string") {
    const text = repairText(value);
    return text.length > 120 ? `${text.slice(0, 120)}...` : text;
  }
  if (Array.isArray(value)) {
    return locale === "zh" ? `数组(${value.length})` : `Array(${value.length})`;
  }
  if (typeof value === "object") {
    return locale === "zh"
      ? `对象(${Object.keys(value as Record<string, unknown>).length})`
      : `Object(${Object.keys(value as Record<string, unknown>).length})`;
  }
  return repairText(value);
}

export function formatScore(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) {
    return "N/A";
  }
  return number.toFixed(1);
}

export function formatPercent(value: unknown): string {
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) {
    return "N/A";
  }
  return `${number.toFixed(1)}%`;
}
