/** 研究终端主 Hook：负责运行、历史、回测、轻量记忆和演示场景。 */
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
  getProfilePreferences,
  getRunAuditSummary,
  getBacktest,
  getDataStatus,
  getRunArtifacts,
  getRunDetail,
  getRuntimeConfig,
  listBacktests,
  listRunHistory,
  listRuns,
  openRunEventStream,
  refreshDataStatus,
  retryRun,
  updateProfilePreferences,
} from "../lib/api";
import { splitLines } from "../lib/format";
import { getLocalePack } from "../lib/i18n";
import {
  buildMemoryFromParsedIntent,
  clearIntentMemory,
  getDemoScenarios,
  readIntentMemory,
  writeIntentMemory,
} from "../lib/terminalMemory";
import type {
  AgentMemoryContext,
  AgentFormState,
  ArtifactRecord,
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
  UserPreferenceSummary,
  UserProfile,
} from "../lib/types";

const TERMINAL_STATUSES = new Set(["completed", "failed", "needs_clarification", "cancelled"]);
const LOCALE_STORAGE_KEY = "financial-agent-locale";
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
    values?: Record<string, unknown>;
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

function needsBacktestUpgrade(detail: BacktestDetail | null): boolean {
  if (!detail) return false;
  const meta = (detail.meta || {}) as Record<string, unknown>;
  const schemaVersion = Number(meta.schema_version ?? 0);
  if (!Number.isFinite(schemaVersion) || schemaVersion < 2) return true;
  if ((detail.summary.requested_count || 0) <= 0) return true;
  if ((detail.summary.coverage_count || 0) <= 0) return true;
  return detail.positions.some((item) => !Array.isArray(item.timeseries) || item.timeseries.length === 0);
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
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [terminalMode, setTerminalMode] = useState<TerminalMode>(initialTerminalMode);
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);
  const [memoryPreview, setMemoryPreview] = useState(() => readIntentMemory(initialLocale()));
  const demoScenarios = getDemoScenarios(locale);

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
  const [isBacktestAutoUpgrading, setIsBacktestAutoUpgrading] = useState(false);

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

  const loadTerminalMeta = useEffectEvent(async () => {
    setProfileLoading(true);
    try {
      const [runtimeResponse, dataResponse, preferenceResponse] = await Promise.all([
        getRuntimeConfig(),
        getDataStatus(),
        getProfilePreferences(),
      ]);
      startTransition(() => {
        setRuntime(runtimeResponse);
        setDataStatus(dataResponse);
      });
      applyProfileResponse(preferenceResponse);
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : t("读取终端环境失败。", "Failed to load terminal runtime."));
    } finally {
      setProfileLoading(false);
    }
  });

  const loadHistory = useEffectEvent(async (nextFilters: HistoryFilters) => {
    setHistoryLoading(true);
    try {
      const response = await listRunHistory(nextFilters, 20).catch(() => listRuns(nextFilters, 20));
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
      const [detailResponse, artifactResponse, auditResponse] = await Promise.all([
        getRunDetail(runId),
        getRunArtifacts(runId),
        getRunAuditSummary(runId).catch(() => null),
      ]);
      startTransition(() => {
        setRunDetail(detailResponse);
        setArtifacts(artifactResponse.artifacts);
        setAuditSummary(auditResponse);
        setSelectedArtifactId((current) =>
          artifactResponse.artifacts.some((artifact) => artifact.id === current)
            ? current
            : artifactResponse.artifacts[0]?.id ?? null,
        );
        setMode(detailResponse.run.mode);
      });

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

      if (detailResponse.run.status === "completed") {
        const existing = await loadBacktest(runId);
        const result = detailResponse.result || {};
        const researchContext =
          result && typeof result === "object" ? ((result as Record<string, unknown>).research_context as Record<string, unknown> | undefined) : undefined;
        const researchMode = String(researchContext?.research_mode || "realtime");
        const runAsOfDate = String(researchContext?.as_of_date || "");
        if (existing && needsBacktestUpgrade(existing)) {
          setIsBacktestAutoUpgrading(true);
          try {
            const meta = (existing.meta || {}) as Record<string, unknown>;
            const backtestKind = String(meta.backtest_kind || (researchMode === "historical" ? "replay" : "reference")) as BacktestMode;
            const currentEntry = existing.summary.entry_date || referenceStartDate;
            const currentEnd = existing.summary.end_date || historicalBacktestEndDate || todayIso();
            if (backtestKind === "reference") {
              const safeEnd = currentEnd > currentEntry ? currentEnd : plusDaysIso(currentEntry, 1);
              await runBacktest(runId, "reference", currentEntry, safeEnd);
            } else {
              const anchor = runAsOfDate || asOfDate;
              const safeEnd = anchor && currentEnd <= anchor ? plusDaysIso(anchor, 1) : currentEnd;
              await runBacktest(runId, "replay", null, safeEnd);
            }
            await loadBacktest(runId);
          } finally {
            setIsBacktestAutoUpgrading(false);
          }
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
    setMemoryPreview(readIntentMemory(locale));
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
      await loadHistory({ ...filters, search: deferredSearch });
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
      setAuditSummary(null);
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

  const applyDemoScenario = (scenarioId: string) => {
    const scenario = demoScenarios.find((item) => item.id === scenarioId);
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
    isBacktestAutoUpgrading,
    selectedArtifactId,
    selectedArtifactKind,
    statusText,
    errorText,
    memoryPreview,
    demoScenarios,
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
    createAgentRun,
    createStructuredRun,
    retryActiveRun,
    cancelActiveRun,
    refreshData,
    clearHistory: clearHistoryItems,
    openRun,
    refreshHistory: () => loadHistory({ ...filters, search: deferredSearch }),
    loadBacktest,
    runBacktest,
    applyDemoScenario,
    fillAgentSample: () => applyDemoScenario(demoScenarios[0]?.id || "steady-income"),
    fillStructuredSample: () =>
      setStructuredFormState({
        ...DEFAULT_STRUCTURED_FORM,
        tickers: "JNJ, PG, KO",
      }),
  };
}
