import {
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useRef,
  useState,
} from "react";

import {
  cancelRun,
  clearProfile,
  clearRuns,
  createBacktest,
  createRun,
  getBacktest,
  getDataStatus,
  getProfile,
  getRunArtifacts,
  getRunDetail,
  getRuntimeConfig,
  listBacktests,
  listRuns,
  openRunEventStream,
  refreshDataStatus,
  retryRun,
  updateProfile,
} from "../lib/api";
import { splitLines } from "../lib/format";
import { getLocalePack } from "../lib/i18n";
import type {
  AgentFormState,
  ArtifactRecord,
  BacktestDetail,
  BacktestMode,
  DataStatus,
  HistoryFilters,
  Locale,
  ProfileResponse,
  RunDetailResponse,
  RunEvent,
  RunMode,
  RunSummary,
  RuntimeConfig,
  StructuredFormState,
  TerminalMode,
  UserProfile,
} from "../lib/types";

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_clarification", "cancelled"]);
const LOCALE_STORAGE_KEY = "financial-agent-locale";
const MODE_STORAGE_KEY = "financial-agent-terminal-mode";

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

const EMPTY_PROFILE: UserProfile = {
  capital_amount: null,
  currency: null,
  risk_tolerance: null,
  investment_horizon: null,
  investment_style: null,
  preferred_sectors: [],
  preferred_industries: [],
};

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

function toOptionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildStructuredPayload(form: StructuredFormState) {
  return {
    risk_profile: { tolerance_level: form.riskLevel },
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

function cloneProfile(profile: UserProfile): UserProfile {
  return {
    ...profile,
    preferred_sectors: [...profile.preferred_sectors],
    preferred_industries: [...profile.preferred_industries],
  };
}

export function useResearchConsole(defaultMode: RunMode = "agent") {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [terminalMode, setTerminalMode] = useState<TerminalMode>(initialTerminalMode);
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);

  const [mode, setMode] = useState<RunMode>(defaultMode);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);

  const [agentForm, setAgentFormState] = useState<AgentFormState>(DEFAULT_AGENT_FORM);
  const [structuredForm, setStructuredFormState] = useState<StructuredFormState>(DEFAULT_STRUCTURED_FORM);
  const [asOfDate, setAsOfDate] = useState<string>(() => daysAgoIso(180));
  const [referenceStartDate, setReferenceStartDate] = useState<string>(() => daysAgoIso(180));
  const [historicalBacktestEndDate, setHistoricalBacktestEndDate] = useState<string>(() => todayIso());

  const [history, setHistory] = useState<RunSummary[]>([]);
  const [filters, setFiltersState] = useState<HistoryFilters>(DEFAULT_FILTERS);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null);
  const [artifacts, setArtifacts] = useState<ArtifactRecord[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<number | null>(null);
  const [selectedArtifactKind, setSelectedArtifactKind] = useState("all");
  const [backtestDetail, setBacktestDetail] = useState<BacktestDetail | null>(null);
  const [backtestLoading, setBacktestLoading] = useState(false);
  const [backtestCreating, setBacktestCreating] = useState(false);

  const [statusText, setStatusText] = useState(copy.status.ready);
  const [errorText, setErrorText] = useState("");
  const [creatingRun, setCreatingRun] = useState(false);
  const [cancelingRun, setCancelingRun] = useState(false);
  const [retryingRun, setRetryingRun] = useState(false);
  const [refreshingData, setRefreshingData] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMutating, setHistoryMutating] = useState(false);
  const [runLoading, setRunLoading] = useState(false);
  const [profile, setProfile] = useState<UserProfile>(cloneProfile(EMPTY_PROFILE));
  const [profileDraft, setProfileDraftState] = useState<UserProfile>(cloneProfile(EMPTY_PROFILE));
  const [profileUpdatedAt, setProfileUpdatedAt] = useState<string | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileClearing, setProfileClearing] = useState(false);

  const deferredSearch = useDeferredValue(filters.search);
  const eventSourceRef = useRef<EventSource | null>(null);
  const refreshTimerRef = useRef<number | null>(null);

  const closeEventSource = useEffectEvent(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  });

  const applyProfileResponse = useEffectEvent((response: ProfileResponse) => {
    const nextProfile = cloneProfile(response.profile);
    startTransition(() => {
      setProfile(nextProfile);
      setProfileDraftState(cloneProfile(nextProfile));
      setProfileUpdatedAt(response.updated_at);
    });
  });

  const loadProfileState = useEffectEvent(async () => {
    setProfileLoading(true);
    try {
      const response = await getProfile();
      applyProfileResponse(response);
      return response;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取长期偏好失败。", "Failed to load saved preferences."));
      return null;
    } finally {
      setProfileLoading(false);
    }
  });

  const loadTerminalMeta = useEffectEvent(async () => {
    try {
      const [runtimeResponse, dataResponse, profileResponse] = await Promise.all([
        getRuntimeConfig(),
        getDataStatus(),
        getProfile(),
      ]);
      startTransition(() => {
        setRuntime(runtimeResponse);
        setDataStatus(dataResponse);
      });
      applyProfileResponse(profileResponse);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取终端环境失败。", "Failed to load terminal runtime."));
    }
  });

  const loadHistory = useEffectEvent(async (nextFilters: HistoryFilters) => {
    setHistoryLoading(true);
    try {
      const response = await listRuns(nextFilters, 20);
      startTransition(() => setHistory(response.items));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取历史报告失败。", "Failed to load report history."));
    } finally {
      setHistoryLoading(false);
    }
  });

  const loadBacktest = useEffectEvent(async (runId: string) => {
    setBacktestLoading(true);
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
      const message = error instanceof Error ? error.message : "";
      if (message.includes("Not Found") || message.includes("404")) {
        startTransition(() => setBacktestDetail(null));
        return undefined;
      }
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
      const targetRunId = runId || activeRunId;
      if (!targetRunId) return null;
      const modeSelected = modeOverride || (terminalMode === "historical" ? "replay" : "reference");
      const entryDate = entryDateOverride ?? (modeSelected === "reference" ? referenceStartDate : null);
      const endDate = endDateOverride ?? (modeSelected === "replay" ? historicalBacktestEndDate : todayIso());
      const result = runDetail?.result;
      const researchContext =
        result && typeof result === "object"
          ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined)
          : undefined;
      const replayAnchor = String(researchContext?.as_of_date || asOfDate || "");

      if (modeSelected === "reference" && entryDate && endDate && entryDate >= endDate) {
        setErrorText(locale === "zh" ? "历史表现参考的买入起点需要早于结束日期。" : "Entry date must be earlier than end date.");
        return null;
      }
      if (modeSelected === "replay" && replayAnchor && endDate && endDate <= replayAnchor) {
        setErrorText(
          locale === "zh"
            ? "历史回放结束日期需要晚于历史研究时点。"
            : "Replay end date must be later than the historical as-of date.",
        );
        return null;
      }

      setBacktestCreating(true);
      setErrorText("");
      try {
        const detail = await createBacktest({
          mode: modeSelected,
          source_run_id: targetRunId,
          entry_date: entryDate || null,
          end_date: endDate || null,
        });
        startTransition(() => setBacktestDetail(detail));
        setStatusText(
          modeSelected === "replay"
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

      if (detailResponse.run.status === "completed") {
        const existing = await loadBacktest(runId);
        const result = detailResponse.result || {};
        const researchContext =
          result && typeof result === "object" ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined) : undefined;
        const researchMode = String(researchContext?.research_mode || "realtime");
        const runAsOfDate = String(researchContext?.as_of_date || "");

        if (existing === undefined) {
          return detailResponse;
        }

        if (!existing && researchMode === "historical") {
          let replayEnd = historicalBacktestEndDate || todayIso();
          if (runAsOfDate && replayEnd <= runAsOfDate) {
            replayEnd = todayIso() > runAsOfDate ? todayIso() : plusDaysIso(runAsOfDate, 1);
            startTransition(() => setHistoricalBacktestEndDate(replayEnd));
          }
          await runBacktest(runId, "replay", null, replayEnd);
        }
      } else {
        startTransition(() => setBacktestDetail(null));
      }
      if (
        detailResponse.run.mode === "agent" &&
        (detailResponse.run.status === "completed" || detailResponse.run.status === "needs_clarification")
      ) {
        await loadProfileState();
      }
      return detailResponse;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取报告详情失败。", "Failed to load report detail."));
      return null;
    } finally {
      setRunLoading(false);
    }
  });

  const scheduleRunRefresh = useEffectEvent((runId: string) => {
    if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = window.setTimeout(() => {
      void loadRunBundle(runId);
      void loadHistory({ ...filters, search: deferredSearch });
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

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(MODE_STORAGE_KEY, terminalMode);
  }, [terminalMode]);

  useEffect(() => {
    void loadTerminalMeta();
  }, []);

  useEffect(() => {
    const nextFilters = { ...filters, search: deferredSearch };
    void loadHistory(nextFilters);
  }, [filters.mode, filters.status, deferredSearch]);

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

  useEffect(() => {
    if (!activeRunId) setStatusText(copy.status.ready);
  }, [locale, activeRunId, copy.status.ready]);

  useEffect(() => {
    return () => {
      closeEventSource();
      if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    };
  }, []);

  const createAgentRun = async () => {
    if (!agentForm.query.trim()) {
      setErrorText(locale === "zh" ? "请先输入投资问题。" : "Please enter an investment request first.");
      return;
    }
    if (runDetail?.run.status === "queued" || runDetail?.run.status === "running") {
      setErrorText(
        locale === "zh"
          ? "当前已有任务在运行中。请等待完成，或先点击“撤回任务”。"
          : "A run is already in progress. Wait for completion or cancel the current run first.",
      );
      return;
    }
    if (terminalMode === "historical" && !asOfDate) {
      setErrorText(locale === "zh" ? "历史模式需要填写 as_of_date。" : "Historical mode requires an as-of date.");
      return;
    }
    if (terminalMode === "historical" && historicalBacktestEndDate <= asOfDate) {
      setErrorText(
        locale === "zh"
          ? "历史回放结束日期必须晚于历史研究时点。"
          : "Historical replay end date must be later than as-of date.",
      );
      return;
    }

    setCreatingRun(true);
    setErrorText("");
    setStatusText(copy.status.creatingAgent);
    try {
      const detail = await createRun({
        mode: "agent",
        agent: {
          query: agentForm.query.trim(),
          options: {
            fetch_live_data: terminalMode === "historical" ? true : agentForm.fetchLiveData,
            max_results: agentForm.maxResults,
          },
          research_context: {
            research_mode: terminalMode,
            as_of_date: terminalMode === "historical" ? asOfDate || null : null,
          },
          llm: {},
        },
      });
      setActiveRunId(detail.run.id);
      setRunDetail(detail);
      setArtifacts([]);
      setEvents([]);
      setBacktestDetail(null);
      setSelectedArtifactId(null);
      setMode("agent");
      await loadHistory({ ...filters, search: deferredSearch });
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("创建报告失败。", "Failed to create report."));
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
      setBacktestDetail(null);
      setSelectedArtifactId(null);
      setMode("structured");
      await loadHistory({ ...filters, search: deferredSearch });
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("创建结构化任务失败。", "Failed to create structured run."));
    } finally {
      setCreatingRun(false);
    }
  };

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
      setBacktestDetail(null);
      setSelectedArtifactId(null);
      setMode(detail.run.mode);
      await loadHistory({ ...filters, search: deferredSearch });
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
      await loadHistory({ ...filters, search: deferredSearch });
      closeEventSource();
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("撤回任务失败。", "Failed to cancel run."));
    } finally {
      setCancelingRun(false);
    }
  };

  const refreshData = async () => {
    setRefreshingData(true);
    setErrorText("");
    try {
      const nextStatus = await refreshDataStatus();
      setDataStatus(nextStatus);
      setStatusText(locale === "zh" ? "市场数据已刷新。" : "Market data refreshed.");
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("刷新市场数据失败。", "Failed to refresh market data."));
    } finally {
      setRefreshingData(false);
    }
  };

  const clearHistoryItems = async () => {
    if (!window.confirm(copy.history.clearConfirm)) return;
    setHistoryMutating(true);
    setErrorText("");
    try {
      const response = await clearRuns({ ...filters, search: deferredSearch });
      setStatusText(copy.status.clearedHistory(response.deleted_count));
      await loadHistory({ ...filters, search: deferredSearch });
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("清理历史失败。", "Failed to clear history."));
    } finally {
      setHistoryMutating(false);
    }
  };

  const saveProfileDraft = async () => {
    setProfileSaving(true);
    setErrorText("");
    try {
      const response = await updateProfile(profileDraft);
      applyProfileResponse(response);
      setStatusText(locale === "zh" ? "长期偏好已保存。" : "Saved preferences updated.");
      return response;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("保存长期偏好失败。", "Failed to save preferences."));
      return null;
    } finally {
      setProfileSaving(false);
    }
  };

  const resetProfileDraft = () => {
    startTransition(() => setProfileDraftState(cloneProfile(profile)));
    setStatusText(locale === "zh" ? "已恢复为当前保存的偏好。" : "Draft reset to the saved profile.");
  };

  const clearStoredProfile = async () => {
    setProfileClearing(true);
    setErrorText("");
    try {
      const response = await clearProfile();
      applyProfileResponse(response);
      setStatusText(locale === "zh" ? "长期偏好已清空。" : "Saved preferences cleared.");
      return response;
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("清空长期偏好失败。", "Failed to clear preferences."));
      return null;
    } finally {
      setProfileClearing(false);
    }
  };

  return {
    locale,
    setLocale,
    terminalMode,
    setTerminalMode,
    asOfDate,
    setAsOfDate,
    referenceStartDate,
    setReferenceStartDate,
    historicalBacktestEndDate,
    setHistoricalBacktestEndDate,
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
    backtestDetail,
    backtestLoading,
    backtestCreating,
    selectedArtifactId,
    selectedArtifactKind,
    statusText,
    errorText,
    creatingRun,
    cancelingRun,
    retryingRun,
    refreshingData,
    historyLoading,
    historyMutating,
    runLoading,
    profile,
    profileDraft,
    profileUpdatedAt,
    profileLoading,
    profileSaving,
    profileClearing,
    setAgentForm: (patch: Partial<AgentFormState>) => setAgentFormState((current) => ({ ...current, ...patch })),
    setStructuredForm: (patch: Partial<StructuredFormState>) =>
      setStructuredFormState((current) => ({ ...current, ...patch })),
    setFilters: (patch: Partial<HistoryFilters>) => setFiltersState((current) => ({ ...current, ...patch })),
    setProfileDraft: (patch: Partial<UserProfile>) =>
      setProfileDraftState((current) => ({
        ...current,
        ...patch,
        preferred_sectors: patch.preferred_sectors ?? current.preferred_sectors,
        preferred_industries: patch.preferred_industries ?? current.preferred_industries,
      })),
    setSelectedArtifactId,
    setSelectedArtifactKind,
    createAgentRun,
    createStructuredRun,
    retryActiveRun,
    cancelActiveRun,
    refreshData,
    clearHistory: clearHistoryItems,
    saveProfileDraft,
    resetProfileDraft,
    clearStoredProfile,
    openRun,
    refreshHistory: () => loadHistory({ ...filters, search: deferredSearch }),
    loadBacktest,
    runBacktest,
    fillAgentSample: () => setAgentFormState({ ...DEFAULT_AGENT_FORM, query: AGENT_SAMPLES[locale] }),
    fillStructuredSample: () =>
      setStructuredFormState({
        ...DEFAULT_STRUCTURED_FORM,
        tickers: "JNJ, PG, KO",
      }),
  };
}
