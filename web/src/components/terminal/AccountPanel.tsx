/** 账户面板：在终端前台提供登录、注册、退出和记忆同步入口。 */
import { useMemo, useState } from "react";
import type { AuthUser, Locale } from "../../lib/types";
import { Button } from "../ui/button";

interface AccountPanelProps {
  locale: Locale;
  currentAccount: AuthUser | null;
  loading: boolean;
  submitting: boolean;
  notice: string;
  onLogin: (email: string, password: string) => Promise<boolean>;
  onRegister: (email: string, password: string) => Promise<boolean>;
  onLogout: () => Promise<boolean>;
  onSyncMemory: () => Promise<boolean>;
}

/** 终端顶部账户面板。 */
export function AccountPanel({
  locale,
  currentAccount,
  loading,
  submitting,
  notice,
  onLogin,
  onRegister,
  onLogout,
  onSyncMemory,
}: AccountPanelProps) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const copy = useMemo(
    () =>
      locale === "zh"
        ? {
            toggle: "账户",
            title: "账户与记忆同步",
            subtitle: "登录后可跨设备继续使用同一份偏好和历史。",
            email: "邮箱",
            password: "密码",
            login: "登录",
            register: "创建账户",
            sync: "同步浏览器记忆",
            logout: "退出账户",
            loading: "正在读取账户...",
            signedIn: "当前账户",
            syncHint: "把当前浏览器已经学到的偏好并入账户。",
          }
        : {
            toggle: "Account",
            title: "Account and memory sync",
            subtitle: "Sign in to keep preferences and history available across devices.",
            email: "Email",
            password: "Password",
            login: "Sign in",
            register: "Create account",
            sync: "Sync browser memory",
            logout: "Sign out",
            loading: "Loading account...",
            signedIn: "Signed in as",
            syncHint: "Merge what this browser already learned into the account profile.",
          },
    [locale],
  );

  async function handleSubmit() {
    if (!email.trim() || !password.trim()) return;
    const ok = mode === "login" ? await onLogin(email.trim(), password) : await onRegister(email.trim(), password);
    if (ok) {
      setPassword("");
    }
  }

  return (
    <div className={`account-panel ${open ? "open" : ""}`}>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        className="compact-action"
        onClick={() => setOpen((value) => !value)}
      >
        {copy.toggle}
      </Button>

      {open ? (
        <div className="account-panel-sheet panel-surface">
          <div className="section-head tight">
            <div>
              <p className="eyebrow">{copy.title}</p>
              <h2>{copy.subtitle}</h2>
            </div>
          </div>

          {loading ? <p className="section-note">{copy.loading}</p> : null}

          {currentAccount ? (
            <div className="account-panel-stack">
              <div className="mini-card">
                <span className="mini-label">{copy.signedIn}</span>
                <strong>{currentAccount.email}</strong>
              </div>
              <div className="mini-card">
                <span className="mini-label">{locale === "zh" ? "记忆同步" : "Memory sync"}</span>
                <p>{copy.syncHint}</p>
              </div>
              <div className="button-row">
                <Button type="button" onClick={() => void onSyncMemory()} disabled={submitting}>
                  {copy.sync}
                </Button>
                <Button type="button" variant="secondary" onClick={() => void onLogout()} disabled={submitting}>
                  {copy.logout}
                </Button>
              </div>
            </div>
          ) : (
            <div className="account-panel-stack">
              <div className="account-panel-mode-row">
                <button
                  type="button"
                  className={mode === "login" ? "account-mode-pill active" : "account-mode-pill"}
                  onClick={() => setMode("login")}
                >
                  {copy.login}
                </button>
                <button
                  type="button"
                  className={mode === "register" ? "account-mode-pill active" : "account-mode-pill"}
                  onClick={() => setMode("register")}
                >
                  {copy.register}
                </button>
              </div>

              <label className="field">
                <span>{copy.email}</span>
                <input
                  aria-label={copy.email}
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                />
              </label>
              <label className="field">
                <span>{copy.password}</span>
                <input
                  aria-label={copy.password}
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <Button type="button" onClick={() => void handleSubmit()} disabled={submitting}>
                {mode === "login" ? copy.login : copy.register}
              </Button>
            </div>
          )}

          {notice ? <p className="section-note account-panel-note">{notice}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
