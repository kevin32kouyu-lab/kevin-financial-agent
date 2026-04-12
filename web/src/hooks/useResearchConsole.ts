import {
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";

import {
  clearRuns,
  createRun,
  getDataStatus,
  getRunArtifacts,
  getRunDetail,
  getRuntimeConfig,
  listRuns,
  openRunEventStream,
  refreshDataStatus,
  retryRun,
} from "../lib/api";
import { splitLines } from "../lib/format";
import { getLocalePack } from "../lib/i18n";
import type {
  AgentFormState,
  ArtifactRecord,
  DataStatus,
  HistoryFilters,
  Locale,
  RunDetailResponse,
  RunEvent,
  RunMode,
  RunSummary,
  RuntimeConfig,
  StructuredFormState,
} from "../lib/types";

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_clarification"]);
const LOCALE_STORAGE_KEY = "financial-agent-locale";

const AGENT_SAMPLES: Record<Locale, string> = {
  zh: "我有 50000 美元，想找适合长期持有的低风险分红股。请优先比较 JNJ、PG、KO，并给我一份正式的投资研究结论，包括估值、ROE、自由现金流、主要风险和执行建议。",
  en: "I have 50000 USD and want a long-term low-risk dividend portfolio. Compare JNJ, PG and KO, then give me a formal investment memo covering valuation, ROE, cash flow, key risks and execution advice.",
};

const DEFAULT_AGENT_FORM: AgentFormState = {
  query: "",
  maxResults: 5,
  fetchLiveData: true,
};

const DEFAULT_STRUCTURED_FORM: StructuredFormState = {
  tickers: "",
  sectors: "Healthcare, Consumer Defensive",
  industries: "",
  riskLevel: "medium",
  maxResults: 5,
  maxPe: "30",
  minRoe: "10",
  minDividendYield: "2",
  analystRating: "",
  requirePositiveFcf: true,
  fetchLiveData: true,
};

const DEFAULT_FILTERS: HistoryFilters = {
  search: "",
  mode: "",
  status: "",
};

function initialLocale(): Locale {
  if (typeof window === "undefined") {
    return "zh";
  }
  const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return stored === "en" ? "en" : "zh";
}

function toOptionalNumber(value: string): number | null {
  if (!value.trim()) {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildStructuredPayload(form: StructuredFormState) {
  return {
    risk_profile: {
      tolerance_level: form.riskLevel,
    },
    investment_strategy: {
      preferred_sectors: splitLines(form.sectors),
      preferred_industries: splitLines(form.industries),
    },
    fundamental_filters: {
      max_pe_ratio: toOptionalNumber(form.maxPe),
      min_roe: toOptionalNumber(form.minRoe),
      min_dividend_yield: toOptionalNumber(form.minDividendYield),
      require_positive_fcf: form.requirePositiveFcf,
      analyst_rating: form.analystRating || null,
    },
    explicit_targets: {
      tickers: splitLines(form.tickers).map((item) => item.toUpperCase()),
    },
    portfolio_sizing: {},
    options: {
      fetch_live_data: form.fetchLiveData,
      max_results: form.maxResults,
    },
  };
}

function buildAgentPayload(form: AgentFormState) {
  return {
    query: form.query.trim(),
    options: {
      fetch_live_data: form.fetchLiveData,
      max_results: form.maxResults,
    },
    llm: {},
  };
}

export function useResearchConsole(defaultMode: RunMode = "agent") {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const copy = getLocalePack(locale);
  const [mode, setMode] = useState<RunMode>(defaultMode);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [agentForm, setAgentFormState] = useState<AgentFormState>(DEFAULT_AGENT_FORM);
  const [structuredForm, setStructuredFormState] = useState<StructuredFormState>(DEFAULT_STRUCTURED_FORM);
  const [history, setHistory] = useState<RunSummary[]>([]);
  const [filters, setFiltersState] = useState<HistoryFilters>(DEFAULT_FILTERS);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<number | null>(null);
  const [selectedArtifactKind, setSelectedArtifactKind] = useState("all");
  const [statusText, setStatusText] = useState(copy.status.ready);
  const [errorText, setErrorText] = useState("");
  const [creatingRun, setCreatingRun] = useState(false);
  const [retryingRun, setRetryingRun] = useState(false);
  const [refreshingData, setRefreshingData] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMutating, setHistoryMutating] = useState(false);
  const [runLoading, setRunLoading] = useState(false);

  const deferredSearch = useDeferredValue(filters.search);
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
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "读取终端环境失败。" : "Failed to load terminal metadata.");
    }
  });

  const loadHistory = useEffectEvent(async (nextFilters: HistoryFilters) => {
    setHistoryLoading(true);
    try {
      const response = await listRuns(nextFilters, 20);
      startTransition(() => {
        setHistory(response.items);
      });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "读取历史记录失败。" : "Failed to load run history.");
    } finally {
      setHistoryLoading(false);
    }
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
      return detailResponse;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "读取报告详情失败。" : "Failed to load run detail.");
      return null;
    } finally {
      setRunLoading(false);
    }
  });

  const scheduleRunRefresh = useEffectEvent((runId: string) => {
    if (refreshTimerRef.current) {
      window.clearTimeout(refreshTimerRef.current);
    }
    refreshTimerRef.current = window.setTimeout(() => {
      void loadRunBundle(runId);
      void loadHistory({ ...filters, search: deferredSearch });
    }, 160);
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

  const openRun = useEffectEvent(async (runId: string) => {
    setActiveRunId(runId);
    setStatusText(copy.status.openingRun(runId));
    setErrorText("");
    const detail = await loadRunBundle(runId);
    if (detail) {
      setStatusText(copy.status.viewingRun(runId));
      connectRunEvents(runId);
    }
  });

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
    }
  }, [locale]);

  useEffect(() => {
    void loadTerminalMeta();
  }, []);

  useEffect(() => {
    const nextFilters = {
      ...filters,
      search: deferredSearch,
    };
    void loadHistory(nextFilters);
  }, [filters.mode, filters.status, deferredSearch]);

  useEffect(() => {
    if (!activeRunId) {
      setStatusText(copy.status.ready);
    }
  }, [locale, activeRunId, copy.status.ready]);

  useEffect(() => {
    return () => {
      closeEventSource();
      if (refreshTimerRef.current) {
        window.clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  const createAgentRun = async () => {
    if (!agentForm.query.trim()) {
      setErrorText(locale === "zh" ? "请先输入投资问题。" : "Please enter an investment request first.");
      return;
    }

    setCreatingRun(true);
    setErrorText("");
    setStatusText(copy.status.creatingAgent);
    try {
      const detail = await createRun({
        mode: "agent",
        agent: buildAgentPayload(agentForm),
      });
      setActiveRunId(detail.run.id);
      setRunDetail(detail);
      setArtifacts([]);
      setEvents([]);
      setSelectedArtifactId(null);
      setMode("agent");
      await loadHistory({ ...filters, search: deferredSearch });
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "创建报告失败。" : "Failed to create run.");
    } finally {
      setCreatingRun(false);
    }
  };

  const createStructuredRun = async () => {
    setCreatingRun(true);
    setErrorText("");
    setStatusText(copy.status.creatingStructured);
    try {
      const detail = await createRun({
        mode: "structured",
        structured: buildStructuredPayload(structuredForm),
      });
      setActiveRunId(detail.run.id);
      setRunDetail(detail);
      setArtifacts([]);
      setEvents([]);
      setSelectedArtifactId(null);
      setMode("structured");
      await loadHistory({ ...filters, search: deferredSearch });
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "创建结构化任务失败。" : "Failed to create run.");
    } finally {
      setCreatingRun(false);
    }
  };

  const retryActiveRun = async () => {
    if (!activeRunId) {
      return;
    }
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
      await loadHistory({ ...filters, search: deferredSearch });
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "重试失败。" : "Failed to retry run.");
    } finally {
      setRetryingRun(false);
    }
  };

  const refreshData = async () => {
    setRefreshingData(true);
    setErrorText("");
    try {
      const nextStatus = await refreshDataStatus();
      setDataStatus(nextStatus);
      setStatusText(
        locale === "zh"
          ? "市场数据已刷新，新报告会优先使用最新缓存。"
          : "Market data refreshed. New runs will use the latest cache.",
      );
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "刷新市场数据失败。" : "Failed to refresh market data.");
    } finally {
      setRefreshingData(false);
    }
  };

  const clearHistoryItems = async () => {
    if (!window.confirm(copy.history.clearConfirm)) {
      return;
    }
    setHistoryMutating(true);
    setErrorText("");
    try {
      const response = await clearRuns({ ...filters, search: deferredSearch });
      setStatusText(copy.status.clearedHistory(response.deleted_count));
      await loadHistory({ ...filters, search: deferredSearch });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : locale === "zh" ? "清理历史记录失败。" : "Failed to clear history.");
    } finally {
      setHistoryMutating(false);
    }
  };

  return {
    locale,
    setLocale,
    copy,
    mode,
    setMode,
    runtime,
    dataStatus,
    agentForm,
    structuredForm,
    history,
    filters,
    activeRunId,
    runDetail,
    artifacts,
    events,
    selectedArtifactId,
    selectedArtifactKind,
    statusText,
    errorText,
    creatingRun,
    retryingRun,
    refreshingData,
    historyLoading,
    historyMutating,
    runLoading,
    setAgentForm: (patch: Partial<AgentFormState>) => setAgentFormState((current) => ({ ...current, ...patch })),
    setStructuredForm: (patch: Partial<StructuredFormState>) =>
      setStructuredFormState((current) => ({ ...current, ...patch })),
    setFilters: (patch: Partial<HistoryFilters>) => setFiltersState((current) => ({ ...current, ...patch })),
    setSelectedArtifactId,
    setSelectedArtifactKind,
    createAgentRun,
    createStructuredRun,
    retryActiveRun,
    refreshData,
    clearHistory: clearHistoryItems,
    openRun,
    refreshHistory: () => loadHistory({ ...filters, search: deferredSearch }),
    fillAgentSample: () => setAgentFormState({ ...DEFAULT_AGENT_FORM, query: AGENT_SAMPLES[locale] }),
    fillStructuredSample: () =>
      setStructuredFormState({
        ...DEFAULT_STRUCTURED_FORM,
        tickers: "JNJ, PG, KO",
      }),
  };
}
