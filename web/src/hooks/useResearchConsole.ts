/** 研究终端主 Hook：负责运行、历史、回测、轻量记忆和示例场景。 */
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
  clearProfilePreferences,
  clearRuns,
  createBacktest,
  createRun,
  getCurrentAccount,
  getProfilePreferences,
  getRunAuditSummary,
  getBacktest,
  getDataStatus,
  getRunArtifacts,
  getRunDetail,
  getRuntimeConfig,
  linkClientMemory,
  listBacktests,
  listRunHistory,
  listRuns,
  loginAccount,
  openRunEventStream,
  refreshDataStatus,
  registerAccount,
  retryRun,
  logoutAccount,
  updateProfilePreferences,
} from "../lib/api";
import {
  DEMO_GUIDE_RUN_ID,
  createDemoGuideAuditSummary,
  createDemoGuideBacktest,
  createDemoGuideRunDetail,
  getDemoGuideQuery,
} from "../lib/demoResearch";
import { splitLines } from "../lib/format";
import { getLocalePack } from "../lib/i18n";
import { readLocale, syncDocumentLocale, writeLocale } from "../lib/locale";
import { buildFollowUpQuery } from "../lib/terminalExperience";
import {
  buildMemoryFromParsedIntent,
  clearIntentMemory,
  getSampleScenarios,
  readIntentMemory,
  writeIntentMemory,
} from "../lib/terminalMemory";
import type {
  AgentMemoryContext,
  AgentFormState,
  ArtifactRecord,
  AuthUser,
  BacktestDetail,
  BacktestMode,
  DataStatus,
  HistoryFilters,
  Locale,
  RunAuditSummary,
  RunDetailResponse,
  RunEvent,
  RunMode,
  RunSummary,
  RuntimeConfig,
  StructuredFormState,
  TerminalMode,
  PreferenceValues,
  UserPreferenceSummary,
  UserProfile,
} from "../lib/types";

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_clarification", "cancelled"]);
const MODE_STORAGE_KEY = "financial-agent-terminal-mode";

const DEFAULT_AGENT_FORM: AgentFormState = {
  query: "",
  maxResults: 5,
  fetchLiveData: true,
  allocationMode: "score_weighted",
  customWeights: "",
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

interface RunBundleCacheEntry {
  detail: RunDetailResponse;
  artifacts: ArtifactRecord[];
  auditSummary: RunAuditSummary | null;
  supplementalLoaded: boolean;
}

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

function initialTerminalMode(): TerminalMode {
  if (typeof window === "undefined") return "realtime";
  const stored = window.localStorage.getItem(MODE_STORAGE_KEY);
  return stored === "historical" ? "historical" : "realtime";
}

function cloneProfile(profile: UserProfile): UserProfile {
  return {
    ...profile,
    preferred_sectors: [...profile.preferred_sectors],
    preferred_industries: [...profile.preferred_industries],
  };
}

function toOptionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseCustomWeights(raw: string): Record<string, number> {
  const parsed: Record<string, number> = {};
  const chunks = raw
    .split(/[\n,;，；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
  for (const chunk of chunks) {
    const parts = chunk.split(/[:：=]/).map((item) => item.trim());
    if (parts.length < 2) continue;
    const ticker = parts[0]?.toUpperCase();
    const weight = Number(parts[1]);
    if (!ticker || !Number.isFinite(weight) || weight < 0) continue;
    parsed[ticker] = weight;
  }
  return parsed;
}

function toMemoryRequest(memory: ReturnType<typeof readIntentMemory>): AgentMemoryContext | null {
  if (!memory) return null;
  return {
    capital_amount: memory.capital_amount || null,
    currency: memory.currency || null,
    risk_tolerance: memory.risk_tolerance || null,
    investment_horizon: memory.investment_horizon || null,
    investment_style: memory.investment_style || null,
    preferred_sectors: memory.preferred_sectors || [],
    preferred_industries: memory.preferred_industries || [],
    explicit_tickers: memory.explicit_tickers || [],
  };
}

function toStoredMemoryFromPreferences(
  locale: Locale,
  payload: {
    updated_at?: string | null;
    values?: Partial<PreferenceValues>;
  } | null,
) {
  const values = payload?.values || {};
  if (!payload) return null;
  return {
    locale,
    capital_amount: Number(values.capital_amount || 0) || null,
    currency: String(values.currency || "").trim() || null,
    risk_tolerance: String(values.risk_tolerance || "").trim() || null,
    investment_horizon: String(values.investment_horizon || "").trim() || null,
    investment_style: String(values.investment_style || "").trim() || null,
    preferred_sectors: Array.isArray(values.preferred_sectors) ? values.preferred_sectors.map(String) : [],
    preferred_industries: Array.isArray(values.preferred_industries) ? values.preferred_industries.map(String) : [],
    explicit_tickers: Array.isArray(values.explicit_tickers) ? values.explicit_tickers.map(String) : [],
    savedAt: String(payload.updated_at || new Date().toISOString()),
  };
}

function toUserProfile(payload: UserPreferenceSummary | null): UserProfile {
  const values = payload?.values || {};
  return {
    capital_amount: Number(values.capital_amount || 0) || null,
    currency: String(values.currency || "").trim() || null,
    risk_tolerance: String(values.risk_tolerance || "").trim() || null,
    investment_horizon: String(values.investment_horizon || "").trim() || null,
    investment_style: String(values.investment_style || "").trim() || null,
    preferred_sectors: Array.isArray(values.preferred_sectors) ? values.preferred_sectors.map(String) : [],
    preferred_industries: Array.isArray(values.preferred_industries) ? values.preferred_industries.map(String) : [],
  };
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

export function useResearchConsole(defaultMode: RunMode = "agent") {
  const [locale, setLocale] = useState<Locale>(readLocale);
  const [terminalMode, setTerminalMode] = useState<TerminalMode>(initialTerminalMode);
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);
  const [memoryPreview, setMemoryPreview] = useState(() => readIntentMemory(readLocale()));
  const sampleScenarios = getSampleScenarios(locale);

  const [mode, setMode] = useState<RunMode>(defaultMode);
  const [runtime, setRuntime] = useState<RuntimeConfig | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [profilePreferences, setProfilePreferences] = useState<UserPreferenceSummary | null>(null);
  const [auditSummary, setAuditSummary] = useState<RunAuditSummary | null>(null);
  const [profile, setProfile] = useState<UserProfile>(cloneProfile(EMPTY_PROFILE));
  const [profileDraft, setProfileDraftState] = useState<UserProfile>(cloneProfile(EMPTY_PROFILE));
  const [profileUpdatedAt, setProfileUpdatedAt] = useState<string | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileClearing, setProfileClearing] = useState(false);
  const [currentAccount, setCurrentAccount] = useState<AuthUser | null>(null);
  const [accountLoading, setAccountLoading] = useState(false);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [accountNotice, setAccountNotice] = useState("");

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

  const deferredSearch = useDeferredValue(filters.search);
  const eventSourceRef = useRef<EventSource | null>(null);
  const refreshTimerRef = useRef<number | null>(null);
  const runBundleCacheRef = useRef<Map<string, RunBundleCacheEntry>>(new Map());
  const backtestCacheRef = useRef<Map<string, BacktestDetail | null>>(new Map());
  const historyLoadedRef = useRef(false);

  const closeEventSource = useEffectEvent(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  });

  const applyProfileResponse = useEffectEvent((response: UserPreferenceSummary) => {
    const nextProfile = cloneProfile(toUserProfile(response));
    const nextMemory = toStoredMemoryFromPreferences(
      String(response.locale || locale) === "en" ? "en" : "zh",
      response,
    );

    startTransition(() => {
      setProfilePreferences(response);
      setProfile(nextProfile);
      setProfileDraftState(cloneProfile(nextProfile));
      setProfileUpdatedAt(response.updated_at ?? null);
      if (nextMemory && nextMemory.locale === locale) {
        setMemoryPreview(nextMemory);
      }
    });

    if (nextMemory) {
      writeIntentMemory(nextMemory);
    }
  });

  const applyAccountUser = useEffectEvent((user: AuthUser | null) => {
    startTransition(() => setCurrentAccount(user));
  });

  const loadTerminalMeta = useEffectEvent(async () => {
    setProfileLoading(true);
    setAccountLoading(true);
    try {
      const [runtimeResponse, dataResponse, preferenceResponse, accountResponse] = await Promise.all([
        getRuntimeConfig(),
        getDataStatus(),
        getProfilePreferences(),
        getCurrentAccount(),
      ]);
      startTransition(() => {
        setRuntime(runtimeResponse);
        setDataStatus(dataResponse);
      });
      applyProfileResponse(preferenceResponse);
      applyAccountUser(accountResponse.user);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取终端环境失败。", "Failed to load terminal runtime."));
    } finally {
      setProfileLoading(false);
      setAccountLoading(false);
    }
  });

  const loadHistory = useEffectEvent(async (nextFilters: HistoryFilters) => {
    setHistoryLoading(true);
    try {
      const response = await listRunHistory(nextFilters, 20).catch(() => listRuns(nextFilters, 20));
      historyLoadedRef.current = true;
      startTransition(() => setHistory(response.items));
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取历史报告失败。", "Failed to load report history."));
    } finally {
      setHistoryLoading(false);
    }
  });

  const refreshHistory = useEffectEvent(async () => {
    await loadHistory({ ...filters, search: deferredSearch });
  });

  const loadBacktest = useEffectEvent(async (runId: string, force = false) => {
    if (runId === DEMO_GUIDE_RUN_ID) {
      const demoBacktest = createDemoGuideBacktest(locale);
      backtestCacheRef.current.set(runId, demoBacktest);
      startTransition(() => setBacktestDetail(demoBacktest));
      return demoBacktest;
    }
    if (!force && backtestCacheRef.current.has(runId)) {
      const cached = backtestCacheRef.current.get(runId) ?? null;
      startTransition(() => setBacktestDetail(cached));
      return cached;
    }
    setBacktestLoading(true);
    try {
      const response = await listBacktests(runId, 1);
      if (!response.items.length) {
        backtestCacheRef.current.set(runId, null);
        startTransition(() => setBacktestDetail(null));
        return null;
      }
      const detail = await getBacktest(response.items[0].id);
      backtestCacheRef.current.set(runId, detail);
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
      const targetRunId = runId || activeRunId;
      if (!targetRunId) return null;
      if (targetRunId === DEMO_GUIDE_RUN_ID) {
        const demoBacktest = createDemoGuideBacktest(locale);
        backtestCacheRef.current.set(targetRunId, demoBacktest);
        startTransition(() => setBacktestDetail(demoBacktest));
        setStatusText(locale === "zh" ? "示例回测已载入。" : "Demo backtest loaded.");
        return demoBacktest;
      }
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
        backtestCacheRef.current.set(targetRunId, detail);
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

  const loadRunSupplemental = useEffectEvent(async (runId: string) => {
    try {
      const [artifactResponse, auditResponse] = await Promise.all([
        getRunArtifacts(runId),
        getRunAuditSummary(runId).catch(() => null),
      ]);
      startTransition(() => {
        setArtifacts(artifactResponse.artifacts);
        setAuditSummary(auditResponse);
        setSelectedArtifactId((current) =>
          artifactResponse.artifacts.some((artifact) => artifact.id === current)
            ? current
            : artifactResponse.artifacts[0]?.id ?? null,
        );
      });
      const current = runBundleCacheRef.current.get(runId);
      if (current) {
        runBundleCacheRef.current.set(runId, {
          ...current,
          artifacts: artifactResponse.artifacts,
          auditSummary: auditResponse,
          supplementalLoaded: true,
        });
      }
    } catch {
      // 补充调试数据不应阻塞正式报告阅读。
    }
  });

  const installDemoGuideRun = useEffectEvent(() => {
    const detail = createDemoGuideRunDetail(locale);
    const backtest = createDemoGuideBacktest(locale);
    const audit = createDemoGuideAuditSummary(locale);
    const artifacts: ArtifactRecord[] = [];
    runBundleCacheRef.current.set(DEMO_GUIDE_RUN_ID, {
      detail,
      artifacts,
      auditSummary: audit,
      supplementalLoaded: true,
    });
    backtestCacheRef.current.set(DEMO_GUIDE_RUN_ID, backtest);
    closeEventSource();
    startTransition(() => {
      setActiveRunId(DEMO_GUIDE_RUN_ID);
      setRunDetail(detail);
      setArtifacts(artifacts);
      setAuditSummary(audit);
      setSelectedArtifactId(null);
      setSelectedArtifactKind("all");
      setBacktestDetail(backtest);
      setMode("agent");
      setTerminalMode("realtime");
      setAgentFormState((current) => ({
        ...current,
        query: getDemoGuideQuery(locale),
        fetchLiveData: true,
        maxResults: 3,
        allocationMode: "score_weighted",
        customWeights: "",
      }));
    });
    setErrorText("");
    setStatusText(locale === "zh" ? "示例报告已载入，可以继续查看结论和回测。" : "Demo report loaded. You can continue to the conclusion and backtest.");
    return detail;
  });

  const loadRunBundle = useEffectEvent(async (runId: string) => {
    if (runId === DEMO_GUIDE_RUN_ID) {
      return installDemoGuideRun();
    }
    const cached = runBundleCacheRef.current.get(runId);
    const cachedStatus = cached?.detail.run.status;
    if (cached && cachedStatus && TERMINAL_STATUSES.has(cachedStatus)) {
      startTransition(() => {
        setRunDetail(cached.detail);
        setArtifacts(cached.artifacts);
        setAuditSummary(cached.auditSummary);
        setSelectedArtifactId((current) =>
          cached.artifacts.some((artifact) => artifact.id === current)
            ? current
            : cached.artifacts[0]?.id ?? null,
        );
        setMode(cached.detail.run.mode);
        setBacktestDetail(backtestCacheRef.current.has(runId) ? backtestCacheRef.current.get(runId) ?? null : null);
      });
      setRunLoading(false);
      if (!cached.supplementalLoaded) {
        void loadRunSupplemental(runId);
      }
      return cached.detail;
    }

    setRunLoading(true);
    try {
      const detailResponse = await getRunDetail(runId);
      const previousCache = runBundleCacheRef.current.get(runId);
      const previousStatus = previousCache?.detail.run.status;
      const transitionedToTerminal =
        TERMINAL_STATUSES.has(detailResponse.run.status) && (!previousStatus || !TERMINAL_STATUSES.has(previousStatus));
      const shouldLoadSupplemental = !previousCache?.supplementalLoaded || transitionedToTerminal;
      startTransition(() => {
        setRunDetail(detailResponse);
        setMode(detailResponse.run.mode);
        setBacktestDetail(backtestCacheRef.current.has(runId) ? backtestCacheRef.current.get(runId) ?? null : null);
      });
      runBundleCacheRef.current.set(runId, {
        detail: detailResponse,
        artifacts: previousCache?.artifacts ?? [],
        auditSummary: previousCache?.auditSummary ?? null,
        supplementalLoaded: previousCache?.supplementalLoaded && !transitionedToTerminal ? true : false,
      });
      if (shouldLoadSupplemental) {
        void loadRunSupplemental(runId);
      }

      const resultRecord = (detailResponse.result || {}) as Record<string, unknown>;
      const storedPreferences =
        resultRecord.stored_preferences && typeof resultRecord.stored_preferences === "object"
          ? (resultRecord.stored_preferences as UserPreferenceSummary)
          : null;
      const parsedIntent =
        resultRecord.parsed_intent && typeof resultRecord.parsed_intent === "object"
          ? (resultRecord.parsed_intent as Record<string, unknown>)
          : null;
      const systemContext =
        parsedIntent?.system_context && typeof parsedIntent.system_context === "object"
          ? (parsedIntent.system_context as Record<string, unknown>)
          : null;
      const intentLocale = String(systemContext?.language || locale) === "en" ? "en" : "zh";
      const nextMemory = buildMemoryFromParsedIntent(parsedIntent, intentLocale);
      const nextMemoryFromServer = toStoredMemoryFromPreferences(intentLocale, storedPreferences);
      if (detailResponse.run.mode === "agent" && (detailResponse.run.status === "completed" || detailResponse.run.status === "needs_clarification")) {
        if (storedPreferences) {
          applyProfileResponse(storedPreferences);
        }
      }
      if ((nextMemoryFromServer || nextMemory) && detailResponse.run.mode === "agent" && (detailResponse.run.status === "completed" || detailResponse.run.status === "needs_clarification")) {
        const finalMemory = nextMemoryFromServer || nextMemory;
        if (finalMemory) {
          writeIntentMemory(finalMemory);
          startTransition(() => {
            if (finalMemory.locale === locale) {
              setMemoryPreview(finalMemory);
            }
          });
        }
      } else if (nextMemory && detailResponse.run.mode === "agent" && detailResponse.run.status === "completed") {
        writeIntentMemory(nextMemory);
        startTransition(() => {
          if (nextMemory.locale === locale) {
            setMemoryPreview(nextMemory);
          }
        });
      }

      if (detailResponse.run.status !== "completed") {
        startTransition(() => setBacktestDetail(null));
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
      if (historyLoadedRef.current) {
        void loadHistory({ ...filters, search: deferredSearch });
      }
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
    if (runId === DEMO_GUIDE_RUN_ID) {
      installDemoGuideRun();
      setStatusText(locale === "zh" ? "正在查看示例报告。" : "Viewing the demo report.");
      return;
    }
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
    writeLocale(locale);
    syncDocumentLocale(locale);
  }, [locale]);

  useEffect(() => {
    setMemoryPreview(readIntentMemory(locale));
  }, [locale]);

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(MODE_STORAGE_KEY, terminalMode);
  }, [terminalMode]);

  useEffect(() => {
    void loadTerminalMeta();
  }, []);

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
    if (typeof window === "undefined" || !activeRunId) return;
    const status = runDetail?.run.status;
    if (status !== "queued" && status !== "running") return;
    const timer = window.setInterval(() => {
      void loadRunBundle(activeRunId);
    }, 1000);
    return () => window.clearInterval(timer);
  }, [activeRunId, runDetail?.run.status]);

  useEffect(() => {
    return () => {
      closeEventSource();
      if (refreshTimerRef.current) window.clearTimeout(refreshTimerRef.current);
    };
  }, []);

  const createAgentRun = async (queryOverride?: string) => {
    const effectiveQuery = (queryOverride ?? agentForm.query).trim();
    if (!effectiveQuery) {
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
    const customWeights = agentForm.allocationMode === "custom_weight" ? parseCustomWeights(agentForm.customWeights) : {};
    if (agentForm.allocationMode === "custom_weight") {
      const values = Object.values(customWeights);
      const total = values.reduce((sum, item) => sum + item, 0);
      if (!values.length) {
        setErrorText(locale === "zh" ? "请先填写自定义仓位，例如 MSFT:40, NVDA:60" : "Please set custom weights first, e.g. MSFT:40, NVDA:60.");
        return;
      }
      if (Math.abs(total - 100) > 0.1) {
        setErrorText(
          locale === "zh"
            ? "自定义仓位总和需要等于 100%。"
            : "Custom weights must sum to 100%.",
        );
        return;
      }
    }

    setCreatingRun(true);
    setErrorText("");
    setStatusText(copy.status.creatingAgent);
    try {
      const detail = await createRun({
        mode: "agent",
        agent: {
          query: effectiveQuery,
          options: {
            fetch_live_data: terminalMode === "historical" ? true : agentForm.fetchLiveData,
            max_results: Math.min(5, Math.max(1, Number(agentForm.maxResults) || 5)),
            allocation_mode: agentForm.allocationMode,
            custom_weights: agentForm.allocationMode === "custom_weight" ? customWeights : undefined,
          },
          research_context: {
            research_mode: terminalMode,
            as_of_date: terminalMode === "historical" ? asOfDate || null : null,
          },
          memory_context: toMemoryRequest(memoryPreview),
          llm: {},
        },
      });
      setActiveRunId(detail.run.id);
      setRunDetail(detail);
      setArtifacts([]);
      setEvents([]);
      setAuditSummary(null);
      setBacktestDetail(null);
      setSelectedArtifactId(null);
      setMode("agent");
      if (historyLoadedRef.current) void loadHistory({ ...filters, search: deferredSearch });
      void loadRunBundle(detail.run.id);
      connectRunEvents(detail.run.id);
      if (queryOverride) {
        setAgentFormState((current) => ({ ...current, query: effectiveQuery }));
      }
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
      setAuditSummary(null);
      setBacktestDetail(null);
      setSelectedArtifactId(null);
      setMode("structured");
      if (historyLoadedRef.current) void loadHistory({ ...filters, search: deferredSearch });
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
      setAuditSummary(null);
      setBacktestDetail(null);
      setSelectedArtifactId(null);
      setMode(detail.run.mode);
      if (historyLoadedRef.current) void loadHistory({ ...filters, search: deferredSearch });
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
      if (historyLoadedRef.current) void loadHistory({ ...filters, search: deferredSearch });
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

  const saveProfileDraft = async () => {
    setProfileSaving(true);
    setErrorText("");
    try {
      const response = await updateProfilePreferences({
        capital_amount: profileDraft.capital_amount,
        currency: profileDraft.currency,
        risk_tolerance: profileDraft.risk_tolerance,
        investment_horizon: profileDraft.investment_horizon,
        investment_style: profileDraft.investment_style,
        preferred_sectors: profileDraft.preferred_sectors,
        preferred_industries: profileDraft.preferred_industries,
        locale,
      });
      applyProfileResponse(response);
      setStatusText(locale === "zh" ? "长期偏好已保存。" : "Saved long-term preferences.");
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("保存长期偏好失败。", "Failed to save long-term preferences."));
    } finally {
      setProfileSaving(false);
    }
  };

  const resetProfileDraft = () => {
    startTransition(() => setProfileDraftState(cloneProfile(profile)));
  };

  const clearStoredProfile = async () => {
    setProfileClearing(true);
    setErrorText("");
    try {
      const response = await clearProfilePreferences();
      applyProfileResponse(response);
      clearIntentMemory(locale);
      startTransition(() => {
        setMemoryPreview(null);
      });
      setStatusText(locale === "zh" ? "长期偏好已清空。" : "Long-term preferences cleared.");
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("清空长期偏好失败。", "Failed to clear long-term preferences."));
    } finally {
      setProfileClearing(false);
    }
  };

  const loginWithAccount = async (email: string, password: string) => {
    setAuthSubmitting(true);
    setAccountNotice("");
    try {
      const response = await loginAccount({ email, password });
      applyAccountUser(response.user);
      applyProfileResponse(await getProfilePreferences());
      setAccountNotice(locale === "zh" ? "已登录并同步账户偏好。" : "Signed in and synced account preferences.");
      return true;
    } catch (error) {
      setAccountNotice(error instanceof Error ? error.message : t("登录失败。", "Sign-in failed."));
      return false;
    } finally {
      setAuthSubmitting(false);
    }
  };

  const registerWithAccount = async (email: string, password: string) => {
    setAuthSubmitting(true);
    setAccountNotice("");
    try {
      const response = await registerAccount({ email, password });
      applyAccountUser(response.user);
      applyProfileResponse(await getProfilePreferences());
      setAccountNotice(locale === "zh" ? "账户已创建并自动登录。" : "Account created and signed in.");
      return true;
    } catch (error) {
      setAccountNotice(error instanceof Error ? error.message : t("注册失败。", "Registration failed."));
      return false;
    } finally {
      setAuthSubmitting(false);
    }
  };

  const logoutCurrentAccount = async () => {
    setAuthSubmitting(true);
    setAccountNotice("");
    try {
      await logoutAccount();
      applyAccountUser(null);
      applyProfileResponse(await getProfilePreferences());
      setAccountNotice(locale === "zh" ? "已退出账户。" : "Signed out.");
      return true;
    } catch (error) {
      setAccountNotice(error instanceof Error ? error.message : t("退出失败。", "Sign-out failed."));
      return false;
    } finally {
      setAuthSubmitting(false);
    }
  };

  const syncBrowserMemoryToAccount = async () => {
    if (!currentAccount) {
      setAccountNotice(locale === "zh" ? "请先登录账户。" : "Please sign in first.");
      return false;
    }
    setAuthSubmitting(true);
    setAccountNotice("");
    try {
      const response = await linkClientMemory() as UserPreferenceSummary & { error?: string };
      if (response.error) {
        throw new Error(response.error);
      }
      applyProfileResponse(response);
      setAccountNotice(locale === "zh" ? "浏览器记忆已同步到账户。" : "Memory synced.");
      return true;
    } catch (error) {
      setAccountNotice(error instanceof Error ? error.message : t("记忆同步失败。", "Memory sync failed."));
      return false;
    } finally {
      setAuthSubmitting(false);
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

  const applySampleScenario = (scenarioId: string) => {
    const scenario = sampleScenarios.find((item) => item.id === scenarioId);
    if (!scenario) return;
    setTerminalMode(scenario.terminalMode);
    setAgentFormState({
      ...DEFAULT_AGENT_FORM,
      query: scenario.query,
    });
    if (scenario.referenceStartDate) {
      setReferenceStartDate(scenario.referenceStartDate);
    }
    if (scenario.terminalMode === "historical") {
      setAsOfDate(scenario.asOfDate || daysAgoIso(180));
      setHistoricalBacktestEndDate(scenario.historicalEndDate || todayIso());
    }
  };

  const continueFromRun = async (runId: string) => {
    const detail = await loadRunBundle(runId);
    if (!detail) return false;
    const resultRecord = (detail.result || {}) as Record<string, unknown>;
    const topPick = String(
      (
        ((resultRecord.report_briefing as Record<string, unknown> | undefined)?.executive as Record<string, unknown> | undefined)
          ?.top_pick
      ) || "",
    );
    const baseQuery = String(resultRecord.query || "");
    startTransition(() => {
      setTerminalMode("realtime");
      setActiveRunId(null);
      setRunDetail(null);
      setArtifacts([]);
      setBacktestDetail(null);
      setAuditSummary(null);
      setEvents([]);
      setAgentFormState((current) => ({
        ...current,
        query: buildFollowUpQuery(baseQuery, locale, topPick),
      }));
    });
    setStatusText(locale === "zh" ? "已把上一份研究带回提问页。" : "Loaded the previous thesis back into the ask page.");
    return true;
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
    profilePreferences,
    profile,
    profileDraft,
    profileUpdatedAt,
    profileLoading,
    profileSaving,
    profileClearing,
    currentAccount,
    accountLoading,
    authSubmitting,
    accountNotice,
    auditSummary,
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
    memoryPreview,
    sampleScenarios,
    creatingRun,
    cancelingRun,
    retryingRun,
    refreshingData,
    historyLoading,
    historyMutating,
    runLoading,
    setAgentForm: (patch: Partial<AgentFormState>) => setAgentFormState((current) => ({ ...current, ...patch })),
    setProfileDraft: (patch: Partial<UserProfile>) =>
      setProfileDraftState((current) => ({
        ...current,
        ...patch,
        preferred_sectors: patch.preferred_sectors ? [...patch.preferred_sectors] : current.preferred_sectors,
        preferred_industries: patch.preferred_industries ? [...patch.preferred_industries] : current.preferred_industries,
      })),
    setStructuredForm: (patch: Partial<StructuredFormState>) =>
      setStructuredFormState((current) => ({ ...current, ...patch })),
    setFilters: (patch: Partial<HistoryFilters>) => setFiltersState((current) => ({ ...current, ...patch })),
    setSelectedArtifactId,
    setSelectedArtifactKind,
    saveProfileDraft,
    resetProfileDraft,
    clearStoredProfile,
    loginWithAccount,
    registerWithAccount,
    logoutCurrentAccount,
    syncBrowserMemoryToAccount,
    createAgentRun,
    createStructuredRun,
    retryActiveRun,
    cancelActiveRun,
    refreshData,
    clearHistory: clearHistoryItems,
    openRun,
    refreshHistory,
    loadBacktest,
    runBacktest,
    continueFromRun,
    applySampleScenario,
    prepareDemoGuideRun: () => installDemoGuideRun().run.id,
    fillAgentSample: () => applySampleScenario(sampleScenarios[0]?.id || "steady-income"),
    fillStructuredSample: () =>
      setStructuredFormState({
        ...DEFAULT_STRUCTURED_FORM,
        tickers: "JNJ, PG, KO",
      }),
  };
}
