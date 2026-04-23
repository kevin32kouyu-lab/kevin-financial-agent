/** 本地持续跟踪列表：让用户把想继续看的研究保存在浏览器里。 */
export interface FollowedRunEntry {
  runId: string;
  title: string;
  query: string;
  topPick: string;
  updatedAt: string;
}

const FOLLOWED_RUNS_KEY = "financial-agent-followed-runs";

/** 读取本地持续跟踪列表。 */
export function readFollowedRuns(): FollowedRunEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(FOLLOWED_RUNS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((item) => item && typeof item === "object") as FollowedRunEntry[] : [];
  } catch {
    return [];
  }
}

/** 保存本地持续跟踪列表。 */
export function writeFollowedRuns(items: FollowedRunEntry[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(FOLLOWED_RUNS_KEY, JSON.stringify(items.slice(0, 12)));
}

/** 切换单条研究的持续跟踪状态。 */
export function toggleFollowedRun(items: FollowedRunEntry[], nextItem: FollowedRunEntry) {
  const exists = items.some((item) => item.runId === nextItem.runId);
  const next = exists
    ? items.filter((item) => item.runId !== nextItem.runId)
    : [nextItem, ...items.filter((item) => item.runId !== nextItem.runId)];
  writeFollowedRuns(next);
  return next;
}

/** 判断某条研究是否已被持续跟踪。 */
export function isFollowedRun(items: FollowedRunEntry[], runId: string | null) {
  if (!runId) return false;
  return items.some((item) => item.runId === runId);
}
