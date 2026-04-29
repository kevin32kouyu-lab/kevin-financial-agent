/** 终端进度辅助：按真实阶段推断当前进度和文案，避免卡在固定百分比。 */

import type { Locale } from "./types";

type GenericRecord = Record<string, unknown>;

export interface TerminalProgressState {
  percent: number;
  tone: "neutral" | "positive" | "negative";
  textKey: "idle" | "queued" | "running" | "completed" | "cancelled" | "failed" | "needs_clarification";
}

const STAGE_ORDER = [
  "intent_analysis",
  "assumption_fill",
  "research_plan",
  "structured_analysis",
  "evidence_retrieval",
  "final_report",
  "validation",
] as const;

const RUNNING_STAGE_PROGRESS: Record<string, number> = {
  intent_analysis: 18,
  assumption_fill: 24,
  research_plan: 38,
  structured_analysis: 58,
  evidence_retrieval: 72,
  final_report: 84,
  validation: 97,
};

const STAGE_LABELS = {
  zh: {
    idle: "等待开始",
    queued: "队列中",
    intent_analysis: "开始理解你的问题",
    assumption_fill: "补齐必要默认假设",
    research_plan: "整理研究计划",
    structured_analysis: "聚合市场数据",
    evidence_retrieval: "交叉验证依据",
    final_report: "生成正式报告",
    validation: "校验最终结论",
    completed: "已完成",
    cancelled: "已撤回",
    failed: "执行失败",
    needs_clarification: "等待补充信息",
  },
  en: {
    idle: "Waiting to start",
    queued: "In queue",
    intent_analysis: "Understanding your request",
    assumption_fill: "Filling safe default assumptions",
    research_plan: "Preparing the research plan",
    structured_analysis: "Aggregating market data",
    evidence_retrieval: "Cross-checking evidence",
    final_report: "Building the final report",
    validation: "Validating the conclusion",
    completed: "Completed",
    cancelled: "Cancelled",
    failed: "Failed",
    needs_clarification: "Need clarification",
  },
} as const;

/** 安全读取步骤键。 */
function readStepKey(step: GenericRecord): string {
  const value = step.step_key ?? step.key;
  return typeof value === "string" ? value.trim() : "";
}

/** 安全读取步骤状态。 */
function readStepStatus(step: GenericRecord): string {
  const value = step.status;
  return typeof value === "string" ? value.trim() : "";
}

/** 过滤已经落库的有效阶段。 */
function readOrderedStepKeys(steps: unknown): string[] {
  if (!Array.isArray(steps)) return [];
  const keys = steps
    .filter((item) => item && typeof item === "object")
    .map((item) => item as GenericRecord)
    .filter((item) => {
      const status = readStepStatus(item);
      return status === "completed" || status === "fallback";
    })
    .map(readStepKey)
    .filter(Boolean);
  return keys.sort((left, right) => STAGE_ORDER.indexOf(left as never) - STAGE_ORDER.indexOf(right as never));
}

/** 推断当前正在执行的阶段。 */
function inferRunningStage(stepKeys: string[]): string {
  if (!stepKeys.length) return "intent_analysis";
  const latest = stepKeys[stepKeys.length - 1];
  const currentIndex = STAGE_ORDER.indexOf(latest as never);
  if (currentIndex < 0) return "structured_analysis";
  if (currentIndex >= STAGE_ORDER.length - 1) return "validation";
  return STAGE_ORDER[currentIndex + 1];
}

/** 计算更贴近真实感受的终端进度。 */
export function computeTerminalProgress(status: string | undefined, steps: unknown): TerminalProgressState {
  if (!status) return { percent: 0, tone: "neutral", textKey: "idle" };
  if (status === "queued") return { percent: 12, tone: "neutral", textKey: "queued" };
  if (status === "running") {
    const stage = inferRunningStage(readOrderedStepKeys(steps));
    return {
      percent: RUNNING_STAGE_PROGRESS[stage] || 42,
      tone: "neutral",
      textKey: "running",
    };
  }
  if (status === "completed") return { percent: 100, tone: "positive", textKey: "completed" };
  if (status === "cancelled") return { percent: 100, tone: "negative", textKey: "cancelled" };
  if (status === "failed") return { percent: 100, tone: "negative", textKey: "failed" };
  if (status === "needs_clarification") return { percent: 100, tone: "neutral", textKey: "needs_clarification" };
  return { percent: 0, tone: "neutral", textKey: "idle" };
}

/** 解析当前阶段对应的人类可读文案。 */
export function resolveTerminalStage(status: string | undefined, steps: unknown, locale: Locale): string {
  const labels = STAGE_LABELS[locale];
  if (!status) return labels.idle;
  if (status === "queued") return labels.queued;
  if (status === "running") {
    const stage = inferRunningStage(readOrderedStepKeys(steps));
    return labels[stage as keyof typeof labels] || labels.structured_analysis;
  }
  if (status === "completed") return labels.completed;
  if (status === "cancelled") return labels.cancelled;
  if (status === "failed") return labels.failed;
  if (status === "needs_clarification") return labels.needs_clarification;
  return labels.idle;
}
