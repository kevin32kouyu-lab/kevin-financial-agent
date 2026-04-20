/** 统一管理前端界面语言的默认值与本地存储。 */
import type { Locale } from "./types";

export const LOCALE_STORAGE_KEY = "financial-agent-locale";
export const DEFAULT_LOCALE: Locale = "en";

/** 读取当前界面语言，默认英文。 */
export function readLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const saved = window.localStorage.getItem(LOCALE_STORAGE_KEY);
  return saved === "zh" || saved === "en" ? saved : DEFAULT_LOCALE;
}

/** 保存当前界面语言。 */
export function writeLocale(locale: Locale) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
}

/** 同步页面语言标记，避免页面跳转后残留旧状态。 */
export function syncDocumentLocale(locale: Locale) {
  if (typeof document === "undefined") return;
  document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
}
