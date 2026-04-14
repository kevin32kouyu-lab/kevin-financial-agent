import { getDataStatus, getRuntimeConfig, createRun, refreshDataStatus } from "../lib/api";
import { getLocalePack } from "../lib/i18n";
import type {
  AgentFormState,
  DataStatus,
  Locale,
  RunMode,
  RuntimeConfig,
  TerminalMode,
} from "../lib/types";

// Import specialized hooks
import { useRunManagement } from "./useRunManagement";
import { useRunHistory } from "./useRunHistory";
import { useBacktestManagement } from "./useBacktestManagement";
import { useRunForms } from "./useRunForms";

const LOCALE_STORAGE_KEY = "financial-agent-locale";
const MODE_STORAGE_KEY = "financial-agent-terminal-mode";

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

export function useResearchConsole(defaultMode: RunMode = "agent") {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const [terminalMode, setTerminalMode] = useState<TerminalMode>(initialTerminalMode);
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);

  // Use specialized hooks
  const runManagement = useRunManagement(locale, setLocale, terminalMode, setTerminalMode);
  const runHistory = useRunHistory(locale, setLocale);
  const backtestManagement = useBacktestManagement(
    locale,
    runManagement.runDetail,
    terminalMode,
    runManagement.activeRunId,
  );
  const runForms = useRunForms(locale, setLocale);

  // Additional sync state
  const [mode, setMode] = useState<RunMode>(defaultMode);
  const [refreshingData, setRefreshingData] = useState(false);

  const deferredSearch = useDeferredValue(runHistory.filters.search);

  // Sync terminal mode between hooks
  useEffect(() => {
    setTerminalMode(runManagement.terminalMode);
    runManagement.setAsOfDate(runManagement.asOfDate);
    backtestManagement.setHistoricalBacktestEndDate(backtestManagement.historicalBacktestEndDate);
  }, [runManagement.terminalMode]);

  const refreshData = async () => {
    setRefreshingData(true);
    runForms.setErrorText("");
    try {
      const nextStatus = await refreshDataStatus();
      runManagement.setDataStatus(nextStatus);
      setStatusText(locale === "zh" ? "市场数据已刷新。" : "Market data refreshed.");
    } catch (error) {
      runForms.setErrorText(
        error instanceof Error ? error.message : t("刷新市场数据失败。", "Failed to refresh market data.")
      );
    } finally {
      setRefreshingData(false);
    }
  };

  const createAgentRun = async () => {
    if (!runForms.validateAgentForm()) return;

    // Additional checks
    if (
      runManagement.runDetail?.run.status === "queued" ||
      runManagement.runDetail?.run.status === "running"
    ) {
      runForms.setErrorText(
        locale === "zh"
          ? "当前已有任务在运行中。请等待完成，或先点击"撤回任务"。"
          : "A run is already in progress. Wait for completion or cancel the current run first.",
      );
      return;
    }
    if (terminalMode === "historical" && !runManagement.asOfDate) {
      runForms.setErrorText(locale === "zh" ? "历史模式需要填写 as_of_date。" : "Historical mode requires an as-of date.");
      return;
    }
    if (
      terminalMode === "historical" &&
      backtestManagement.historicalBacktestEndDate <= runManagement.asOfDate
    ) {
      runForms.setErrorText(
        locale === "zh"
          ? "历史回放结束日期必须晚于历史研究时点。"
          : "Historical replay end date must be later than historical as-of date.",
      );
      return;
    }

    runForms.setCreatingRun(true);
    runForms.setErrorText("");
    setStatusText(copy.status.creatingAgent);
    try {
      const detail = await createRun({
        mode: "agent",
        agent: {
          query: runForms.agentForm.query.trim(),
          options: {
            fetch_live_data: terminalMode === "historical" ? true : runForms.agentForm.fetchLiveData,
            max_results: runForms.agentForm.maxResults,
          },
          research_context: {
            research_mode: terminalMode,
            as_of_date: terminalMode === "historical" ? runManagement.asOfDate || null : null,
          },
          llm: {},
        },
      });
      runManagement.setActiveRunId(detail.run.id);
      await runHistory.loadHistory({ ...runHistory.filters, search: deferredSearch });
      runManagement.loadRunBundle(detail.run.id);
      runManagement.connectRunEvents(detail.run.id);
    } catch (error) {
      runForms.setErrorText(
        error instanceof Error ? error.message : t("创建报告失败。", "Failed to create report.")
      );
    } finally {
      runForms.setCreatingRun(false);
    }
  };

  const createStructuredRun = async () => {
    runForms.setCreatingRun(true);
    runForms.setErrorText("");
    setStatusText(copy.status.creatingStructured);
    try {
      const detail = await createRun({
        mode: "structured",
        structured: runForms.buildStructuredPayload(runForms.structuredForm),
      });
      runManagement.setActiveRunId(detail.run.id);
      await runHistory.loadHistory({ ...runHistory.filters, search: deferredSearch });
      runManagement.loadRunBundle(detail.run.id);
      runManagement.connectRunEvents(detail.run.id);
    } catch (error) {
      runForms.setErrorText(
        error instanceof Error ? error.message : t("创建结构化任务失败。", "Failed to create structured run.")
      );
    } finally {
      runForms.setCreatingRun(false);
    }
  };

  // Persist locale and terminal mode
  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  }, [locale]);

  useEffect(() => {
    if (typeof window !== "undefined") window.localStorage.setItem(MODE_STORAGE_KEY, terminalMode);
  }, [terminalMode]);

  // Initialize terminal metadata on mount
  useEffect(() => {
    void loadTerminalMeta();
  }, []);

  // Update status text when state changes
  useEffect(() => {
    if (!runManagement.activeRunId) setStatusText(copy.status.ready);
  }, [locale, runManagement.activeRunId, copy.status.ready]);

  async function loadTerminalMeta() {
    try {
      const [runtimeResponse, dataResponse] = await Promise.all([getRuntimeConfig(), getDataStatus()]);
      runManagement.setRuntime(runtimeResponse);
      runManagement.setDataStatus(dataResponse);
    } catch (error) {
      runForms.setErrorText(
        error instanceof Error ? error.message : t("读取终端环境失败。", "Failed to load terminal runtime.")
      );
    }
  }

  return {
    // Locale and Terminal Mode
    locale,
    setLocale,
    terminalMode,
    setTerminalMode,

    // From runManagement
    ...runManagement,

    // From runHistory
    ...runHistory,

    // From backtestManagement
    ...backtestManagement,

    // From runForms
    ...runForms,

    // Combined actions
    createAgentRun,
    createStructuredRun,
    refreshData,
    refreshingData,

    // Derived state
    deferredSearch,
  };
}
