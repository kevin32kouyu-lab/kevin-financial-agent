/** 终端内部导航：保持 URL 可分享，同时避免四个子页切换时整页刷新。 */
import { useCallback, useEffect, useState } from "react";

export type TerminalPage = "ask" | "conclusion" | "backtest" | "archive";

interface TerminalRouteState {
  page: TerminalPage;
  runId: string | null;
}

/** 根据路由判断当前终端页。 */
export function getTerminalPage(pathname: string): TerminalPage {
  if (pathname.startsWith("/terminal/conclusion")) return "conclusion";
  if (pathname.startsWith("/terminal/backtest")) return "backtest";
  if (pathname.startsWith("/terminal/archive")) return "archive";
  return "ask";
}

/** 生成终端子页地址，并保留当前 run。 */
export function buildTerminalHref(page: TerminalPage, runId?: string | null): string {
  const base =
    page === "conclusion"
      ? "/terminal/conclusion"
      : page === "backtest"
        ? "/terminal/backtest"
        : page === "archive"
          ? "/terminal/archive"
          : "/terminal";
  if (!runId) return base;
  const params = new URLSearchParams();
  params.set("run", runId);
  return `${base}?${params.toString()}`;
}

/** 读取浏览器当前终端路由。 */
function readTerminalRoute(): TerminalRouteState {
  if (typeof window === "undefined") return { page: "ask", runId: null };
  return {
    page: getTerminalPage(window.location.pathname),
    runId: new URLSearchParams(window.location.search).get("run"),
  };
}

/** 管理终端四页的内部导航状态。 */
export function useTerminalNavigation(activeRunId: string | null) {
  const [routeState, setRouteState] = useState<TerminalRouteState>(() => readTerminalRoute());

  useEffect(() => {
    const handlePopState = () => setRouteState(readTerminalRoute());
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const navigateTerminal = useCallback(
    (page: TerminalPage, runId: string | null = activeRunId, replace = false) => {
      if (typeof window === "undefined") return;
      const href = buildTerminalHref(page, runId);
      const current = `${window.location.pathname}${window.location.search}`;
      if (href !== current) {
        window.history[replace ? "replaceState" : "pushState"]({}, "", href);
      }
      setRouteState({ page, runId });
    },
    [activeRunId],
  );

  const replaceTerminalRun = useCallback(
    (runId: string | null) => {
      if (typeof window === "undefined") return;
      const page = getTerminalPage(window.location.pathname);
      const nextRunId = runId || new URLSearchParams(window.location.search).get("run");
      const href = buildTerminalHref(page, nextRunId);
      const current = `${window.location.pathname}${window.location.search}`;
      if (href !== current) {
        window.history.replaceState({}, "", href);
      }
      setRouteState({ page, runId: nextRunId });
    },
    [],
  );

  return {
    terminalPage: routeState.page,
    routeRunId: routeState.runId,
    navigateTerminal,
    replaceTerminalRun,
  };
}
