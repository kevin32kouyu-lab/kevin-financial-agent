import {
  startTransition,
  useDeferredValue,
  useEffect,
  useEffectEvent,
  useState,
} from "react";
import {
  listRuns,
  clearRuns,
} from "../lib/api";
import { getLocalePack } from "../lib/i18n";
import type {
  HistoryFilters,
  Locale,
  RunSummary,
} from "../lib/types";

const DEFAULT_FILTERS: HistoryFilters = {
  search: "",
  mode: "",
  status: "",
};

export function useRunHistory(
  locale: Locale,
  setLocale: (locale: Locale) => void,
) {
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);

  const [history, setHistory] = useState<RunSummary[]>([]);
  const [filters, setFiltersState] = useState<HistoryFilters>(DEFAULT_FILTERS);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyMutating, setHistoryMutating] = useState(false);

  const deferredSearch = useDeferredValue(filters.search);

  const loadHistory = useEffectEvent(async (nextFilters: HistoryFilters) => {
    setHistoryLoading(true);
    try {
      const response = await listRuns(nextFilters, 20);
      startTransition(() => setHistory(response.items));
    } catch (error) {
      throw error; // Let caller handle the error
    } finally {
      setHistoryLoading(false);
    }
  });

  const clearHistoryItems = async () => {
    if (!window.confirm(copy.history.clearConfirm)) return;
    setHistoryMutating(true);
    try {
      const response = await clearRuns({ ...filters, search: deferredSearch });
      await loadHistory({ ...filters, search: deferredSearch });
      return response.deleted_count;
    } catch (error) {
      throw error; // Let caller handle the error
    } finally {
      setHistoryMutating(false);
    }
  };

  const refreshHistory = () => {
    void loadHistory({ ...filters, search: deferredSearch });
  };

  // Trigger history load when filters change
  useEffect(() => {
    const nextFilters = { ...filters, search: deferredSearch };
    void loadHistory(nextFilters);
  }, [filters.mode, filters.status, deferredSearch]);

  return {
    // State
    history,
    filters,
    historyLoading,
    historyMutating,

    // Actions
    setFilters: (patch: Partial<HistoryFilters>) => setFiltersState((current) => ({ ...current, ...patch })),
    clearHistory: clearHistoryItems,
    refreshHistory,
  };
}
