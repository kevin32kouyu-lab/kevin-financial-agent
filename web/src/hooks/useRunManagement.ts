import {
  startTransition,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";
import {
  getDataStatus,
  getRuntimeConfig,
  getRunDetail,
  getRunArtifacts,
  openRunEventStream,
  retryRun,
  cancelRun,
} from "../lib/api";
import { getLocalePack } from "../lib/i18n";
import type {
  ArtifactRecord,
  DataStatus,
  Locale,
  RunDetailResponse,
  RunEvent,
  RuntimeConfig,
  RunMode,
  TerminalMode,
} from "../lib/types";

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_clarification", "cancelled"]);
const LOCALE_STORAGE_KEY = "financial-agent-locale";
const MODE_STORAGE_KEY = "financial-agent-terminal-mode";

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

function initialLocale(): Locale {
  if (typeof window === "undefined") return "zh";
  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return stored === "en" ? "en" : "zh";
}

function initialTerminalMode(): TerminalMode {
  if (typeof window === "undefined") return "realtime";
  const stored = window.localStorage.getItem(MODE_STORAGE_KEY);
  return stored === "historical" ? "historical" : "realtime";
}

export function useRunManagement(
  locale: Locale,
  setLocale: (locale: Locale) => void,
  terminalMode: TerminalMode,
  setTerminalMode: (mode: TerminalMode) => void,
) {
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);

  const [mode, setMode] = useState<RunMode>("agent");
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<number | null>(null);
  const [selectedArtifactKind, setSelectedArtifactKind] = useState("all");

  const [asOfDate, setAsOfDate] = useState<string>(() => daysAgoIso(180));
  const [historicalBacktestEndDate, setHistoricalBacktestEndDate] = useState<string>(() => todayIso());

  const [statusText, setStatusText] = useState(copy.status.ready);
  const [errorText, setErrorText] = useState("");
  const [creatingRun, setCreatingRun] = useState(false);
  const [cancelingRun, setCancelingRun] = useState(false);
  const [retryingRun, setRetryingRun] = useState(false);
  const [runLoading, setRunLoading] = useState(false);

  const eventSourceRef = useRef<EventSource | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  const closeEventSource = useEffectEvent(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  });

  const loadTerminalMeta = useEffectEvent(async () => {
    try {
      const [runtimeResponse, dataResponse] = await Promise.all([getRuntimeConfig(), getDataStatus()]);
      startTransition(() => {
        setRuntime(runtimeResponse);
        setDataStatus(dataResponse);
      });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取终端环境失败。", "Failed to load terminal runtime."));
    }
  });

  const scheduleRunRefresh = useEffectEvent((runId: string) => {
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = window.setTimeout(() => {
      void loadRunBundle(runId);
    }, 200);
  });

  const connectRunEvents = useEffectEvent((runId: string) => {
    closeEventSource();
    setEvents([]);
    const source = openRunEventStream(
      runId,
      (event) => {
        startTransition(() => {
          setEvents((current) => {
            if (event.id && current.some((item) => item.id === event.id && item.event_type === event.event_type)) {
              return current;
            }
            return [...current, event];
          });
        });
        setStatusText(copy.status.eventReceived(event.event_type));
        scheduleRunRefresh(runId);
      },
      () => {
        const status = runDetail?.run.status;
        if (!status || !TERMINAL_STATUSES.has(status)) {
          setStatusText(copy.status.eventStreamClosed);
        }
      },
    );
    eventSourceRef.current = source;
  });

  const loadRunBundle = useEffectEvent(async (runId: string) => {
    setRunLoading(true);
    try {
      const [detailResponse, artifactResponse] = await Promise.all([getRunDetail(runId), getRunArtifacts(runId)]);
      startTransition(() => {
        setRunDetail(detailResponse);
        setArtifacts(artifactResponse.artifacts);
        setSelectedArtifactId((current) =>
          artifactResponse.artifacts.some((artifact) => artifact.id === current)
            ? current
            : artifactResponse.artifacts[0]?.id ?? null,
        );
        setMode(detailResponse.run.mode);
      });

      // Update terminal mode based on research context
      if (detailResponse.run.status === "completed") {
        const result = detailResponse.result || {};
        const researchContext =
          result && typeof result === "object"
            ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined)
            : undefined;
        const researchMode = String(researchContext?.research_mode || "realtime");
        const runAsOfDate = String(researchContext?.as_of_date || "");

        startTransition(() => setTerminalMode(researchMode === "historical" ? "historical" : "realtime"));

        // Update historical dates if in historical mode
        if (researchMode === "historical" && runAsOfDate) {
          startTransition(() => setAsOfDate(runAsOfDate));
        }
      }
      return detailResponse;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取报告详情失败。", "Failed to load report detail."));
      return null;
    } finally {
      setRunLoading(false);
    }
  });

  const openRun = useEffectEvent(async (runId: string) => {
    setActiveRunId(runId);
    setStatusText(copy.status.openingRun(runId));
    setErrorText("");
    const detail = await loadRunBundle(runId);
    if (detail) {
      const result = detail.result || {};
      const researchContext =
        result && typeof result === "object" ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined) : undefined;
      const researchMode = String(researchContext?.research_mode || "realtime");
      const runAsOfDate = String(researchContext?.as_of_date || "");
      startTransition(() => setTerminalMode(researchMode === "historical" ? "historical" : "realtime"));
      if (researchMode === "historical" && runAsOfDate) {
        startTransition(() => setAsOfDate(runAsOfDate));
      }
      setStatusText(copy.status.viewingRun(runId));
      connectRunEvents(runId);
    }
  });

  const retryActiveRun = async () => {
    if (!activeRunId) return;
    setRetryingRun(true);
    setErrorText("");
    setStatusText(copy.status.retryingRun(activeRunId));
    try {
      const detail = await retryRun(activeRunId);
      setActiveRunId(detail.run.id);
      setRunDetail(detail);
      setArtifacts([]);
      setEvents([]);
      setSelectedArtifactId(null);
      setMode(detail.run.mode);
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("重试失败。", "Retry failed."));
    } finally {
      setRetryingRun(false);
    }
  };

  const cancelActiveRun = async () => {
    if (!activeRunId) return;
    setCancelingRun(true);
    setErrorText("");
    try {
      const detail = await cancelRun(activeRunId);
      setRunDetail(detail);
      setStatusText(locale === "zh" ? "任务已撤回。" : "Run cancelled.");
      closeEventSource();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("撤回任务失败。", "Failed to cancel run."));
    } finally {
      setCancelingRun(false);
    }
  };

  const closeCurrentRun = () => {
    closeEventSource();
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
  };

  // Initialize terminal metadata on mount
  useEffect(() => {
    void loadTerminalMeta();
  }, []);

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

  // Cleanup on unmount
  useEffect(() => {
    return () => closeCurrentRun();
  }, []);

  return {
    // State
    mode,
    setMode,
    runtime,
    dataStatus,
    activeRunId,
    runDetail,
    artifacts,
    events,
    selectedArtifactId,
    selectedArtifactKind,
    setSelectedArtifactId,
    setSelectedArtifactKind,
    asOfDate,
    setAsOfDate,
    historicalBacktestEndDate,
    setHistoricalBacktestEndDate,
    statusText,
    errorText,
    creatingRun,
    setCreatingRun,
    cancelingRun,
    retryingRun,
    runLoading,

    // Actions
    openRun,
    retryActiveRun,
    cancelActiveRun,
    closeCurrentRun,
    loadRunBundle,

    // Helpers
    plusDaysIso,
  };
}
