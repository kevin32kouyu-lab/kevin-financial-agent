import {
  startTransition,
  useDeferredValue,
} from "react";
import { splitLines } from "../lib/format";
import {
  getLocalePack
} from "../lib/i18n";
import type {
  AgentFormState,
  ArtifactRecord,
  BacktestDetail,
  BackrtestMode,
  DataStatus,
  HistoryFilters,
  Locale,
  RunDetailResponse,
  RunEvent,
  RunMode,
  RunSummary,
  RuntimeConfig,
  StructuredFormState,
  TerminalMode,
} from "../lib/types";

/**
 * This is the original implementation of useResearchConsole.
 * It has been refactored into specialized hooks for better maintainability.
 * This file is kept as backup/reference only.
 */

// Re-export from specialized hook
export { useResearchConsole as _originalUseResearchConsole } from "./useResearchConsole.v2_organized";

// Export for backward compatibility
export function useResearchConsole(defaultMode: RunMode = "agent") {
  return _originalUseResearchConsole(defaultMode);
}
