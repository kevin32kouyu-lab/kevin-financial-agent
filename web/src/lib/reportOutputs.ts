/** 报告输出辅助：统一读取三报告产物、诊断字段和有效图表。 */
import type { BacktestDetail } from "./types";

export type ReportOutputKind = "simple_investment" | "professional_investment" | "investment" | "development";
export type GenericRecord = Record<string, unknown>;

/** 把未知值安全转换成对象。 */
export function asReportRecord(value: unknown): GenericRecord | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as GenericRecord) : null;
}

/** 读取指定类型的报告输出。 */
export function getReportOutput(result: Record<string, unknown> | GenericRecord, kind: ReportOutputKind): GenericRecord | null {
  const outputs = asReportRecord(result.report_outputs);
  const direct = asReportRecord(outputs?.[kind]);
  if (direct) return direct;
  if (kind === "simple_investment" || kind === "professional_investment") {
    return asReportRecord(outputs?.investment);
  }
  return null;
}

/** 统一读取开发报告诊断字段，并兼容旧字段别名。 */
export function readDevelopmentDiagnostic(diagnostics: GenericRecord | null, key: "agent_count" | "evidence_count" | "validation_check_count" | "backtest_status") {
  if (!diagnostics) return null;
  if (key === "evidence_count") {
    return diagnostics.evidence_count ?? diagnostics.rag_evidence_count ?? null;
  }
  if (key === "validation_check_count") {
    return diagnostics.validation_check_count ?? diagnostics.validation_warning_count ?? null;
  }
  return diagnostics[key] ?? null;
}

/** 用已加载回测临时覆盖投资报告里的回测图，保证页面与回测页一致。 */
export function getEffectiveInvestmentCharts(
  result: Record<string, unknown> | GenericRecord,
  backtest?: BacktestDetail | null,
): GenericRecord | null {
  const investmentOutput = getReportOutput(result, "simple_investment");
  const baseCharts = asReportRecord(investmentOutput?.charts);
  if (!backtest?.summary || !Array.isArray(backtest.points) || !backtest.points.length) {
    return baseCharts;
  }

  const merged = { ...(baseCharts || {}) };
  merged.portfolio_vs_benchmark_backtest = {
    status: "available",
    summary: backtest.summary,
    points: backtest.points,
    message: "",
  };
  return merged;
}
