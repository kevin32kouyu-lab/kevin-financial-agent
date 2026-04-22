import {
  startTransition,
  useEffect,
  useEffectEvent,
  useState,
} from "react";
import {
  listBacktests,
  getBacktest,
  createBacktest,
} from "../lib/api";
import { getLocalePack } from "../lib/i18n";
import type {
  BacktestDetail,
  BacktestMode,
  Locale,
  RunDetailResponse,
} from "../lib/types";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number) {
  const value = new Date();
  value.setDate(value.getDate() - days);
  return value.toISOString().slice(0, 10);
}

function plusDaysIso(value: string, days: number) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return todayIso();
  parsed.setDate(parsed.getDate() + days);
  return parsed.toISOString().slice(0, 10);
}

export function useBacktestManagement(
  locale: Locale,
  runDetail: RunDetailResponse | null,
  terminalMode: "realtime" | "historical",
  activeRunId: string | null,
) {
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);

  const [backtestDetail, setBacktestDetail] = useState<BacktestDetail | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestCreating, setBacktestCreating] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [statusText, setStatusText] = useState(copy.status.ready);

  // Initialize historical dates
  const [asOfDate, setAsOfDate] = useState<string>(() => daysAgoIso(180));
  const [referenceStartDate, setReferenceStartDate] = useState<string>(() => daysAgoIso(180));
  const [historicalBacktestEndDate, setHistoricalBacktestEndDate] = useState<string>(() => todayIso());

  // Update historical dates when terminal mode changes
  useEffect(() => {
    if (terminalMode !== "historical") return;
    const today = todayIso();
    if (!asOfDate || asOfDate >= today) {
      setAsOfDate(daysAgoIso(180));
    }
    if (!historicalBacktestEndDate || historicalBacktestEndDate < today) {
      setHistoricalBacktestEndDate(today);
    }
  }, [terminalMode]);

  const loadBacktest = useEffectEvent(async (runId: string) => {
    setBacktestLoading(true);
    setErrorText("");
    try {
      const response = await listBacktests(runId, 1);
      if (!response.items.length) {
        startTransition(() => setBacktestDetail(null));
        return null;
      }
      const detail = await getBacktest(response.items[0].id);
      startTransition(() => setBacktestDetail(detail));
      return detail;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取回测结果失败。", "Failed to load backtest result."));
      return null;
    } finally {
      setBacktestLoading(false);
    }
  });

  const runBacktest = useEffectEvent(
    async (
      runId?: string,
      modeOverride?: BacktestMode,
      entryDateOverride?: string | null,
      endDateOverride?: string | null,
    ) => {
      const target = runId || activeRunId;
      if (!target) return null;

      const mode = modeOverride || (terminalMode === "historical" ? "replay" : "reference");
      const entryDate = entryDateOverride ?? (mode === "reference" ? referenceStartDate : null);
      const endDate = endDateOverride ?? (mode === "replay" ? historicalBacktestEndDate : todayIso());

      const result = runDetail?.result;
      const researchContext =
        result && typeof result === "object"
          ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined)
          : undefined;
      const replayAnchor = String(researchContext?.as_of_date || asOfDate || "");

      // Validation
      if (mode === "reference" && entryDate && endDate && entryDate >= endDate) {
        setErrorText(locale === "zh" ? "历史表现参考的买入起点需要早于结束日期。" : "Entry date must be earlier than end date.");
        return null;
      }
      if (mode === "replay" && replayAnchor && endDate && endDate <= replayAnchor) {
        setErrorText(
          locale === "zh"
            ? "历史回放结束日期需要晚于历史研究时点。"
            : "Replay end date must be later than historical as-of date.",
        );
        return null;
      }

      setBacktestCreating(true);
      setErrorText("");
      try {
        const detail = await createBacktest({
          mode,
          source_run_id: target,
          entry_date: entryDate || null,
          end_date: endDate || null,
        });
        startTransition(() => setBacktestDetail(detail));

        setStatusText(
          mode === "replay"
            ? locale === "zh"
              ? "历史建议回放已更新。"
              : "Historical replay updated."
            : locale === "zh"
              ? "历史表现参考已更新。"
              : "Historical performance reference updated.",
        );
        return detail;
      } catch (error) {
        setErrorText(error instanceof Error ? error.message : t("生成回测失败。", "Failed to run backtest."));
        return null;
      } finally {
        setBacktestCreating(false);
      }
    },
  );

  // Auto-load backtest when run detail is available and completed
  useEffect(() => {
    if (!runDetail || runDetail.run.status !== "completed" || !activeRunId) {
      startTransition(() => setBacktestDetail(null));
      setStatusText(copy.status.ready);
      return;
    }

    const result = runDetail.result || {};
    const researchContext =
      result && typeof result === "object"
        ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined)
        : undefined;
    const researchMode = String(researchContext?.research_mode || "realtime");

    if (researchMode === "historical") {
      if (backtestDetail && String(backtestDetail.meta?.backtest_kind || "") === "replay") {
        // Don't reload if already in replay mode
        return;
      }
      void loadBacktest(activeRunId);
    } else {
      startTransition(() => setBacktestDetail(null));
      setStatusText(copy.status.ready);
    }
  }, [runDetail, activeRunId, terminalMode]);

  return {
    // State
    backtestDetail,
    backtestLoading,
    backtestCreating,
    asOfDate,
    setAsOfDate,
    referenceStartDate,
    setReferenceStartDate,
    historicalBacktestEndDate,
    setHistoricalBacktestEndDate,
    statusText,
    errorText,

    // Actions
    loadBacktest,
    runBacktest,

    // Helpers
    plusDaysIso,
  };
}
