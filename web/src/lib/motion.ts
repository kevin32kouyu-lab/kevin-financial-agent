/** 动效配置工具：负责读取和写入用户的动效偏好。 */
export const MOTION_PREF_KEY = "financial-agent-motion-enabled";

/** 检测系统是否偏好低动态。 */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
    return false;
  }
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** 读取本地动效偏好，未设置时按系统偏好决定默认值。 */
export function readMotionEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const saved = window.localStorage.getItem(MOTION_PREF_KEY);
  if (saved === "true") return true;
  if (saved === "false") return false;
  return !prefersReducedMotion();
}

/** 写入本地动效偏好。 */
export function writeMotionEnabled(enabled: boolean): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(MOTION_PREF_KEY, String(enabled));
}

