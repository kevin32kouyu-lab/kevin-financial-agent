/*
 * 浏览器侧身份工具。
 * 用本地持久化的 client_id 作为长期记忆的隔离单位。
 */

const CLIENT_ID_STORAGE_KEY = "financial-agent-client-id";

function generateFallbackClientId() {
  return `fa-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function getClientId() {
  if (typeof window === "undefined") {
    return "";
  }

  const stored = window.localStorage.getItem(CLIENT_ID_STORAGE_KEY)?.trim();
  if (stored) {
    return stored;
  }

  const generated =
    typeof window.crypto !== "undefined" && typeof window.crypto.randomUUID === "function"
      ? window.crypto.randomUUID()
      : generateFallbackClientId();

  window.localStorage.setItem(CLIENT_ID_STORAGE_KEY, generated);
  return generated;
}
