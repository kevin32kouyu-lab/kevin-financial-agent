/** 账户档案中心：展示登录状态、长期偏好、关键偏好确认和记忆同步入口。 */
import { useMemo, useState } from "react";
import { Cloud, LogOut, RefreshCw, RotateCcw, Save, ShieldCheck, Trash2, UserCircle } from "lucide-react";
import { formatDateTime } from "../../lib/format";
import type { AuthUser, Locale, UserProfile } from "../../lib/types";
import { Button } from "../ui/button";

type ProfilePatch = Partial<UserProfile>;

interface AccountPanelProps {
  locale: Locale;
  currentAccount: AuthUser | null;
  loading: boolean;
  submitting: boolean;
  notice: string;
  profile: UserProfile;
  profileDraft: UserProfile;
  profileUpdatedAt: string | null;
  profileSaving: boolean;
  profileClearing: boolean;
  onProfileChange: (patch: ProfilePatch) => void;
  onProfileSave: () => void;
  onProfileReset: () => void;
  onProfileClear: () => void;
  onLogin: (email: string, password: string) => Promise<boolean>;
  onRegister: (email: string, password: string) => Promise<boolean>;
  onLogout: () => Promise<boolean>;
  onSyncMemory: () => Promise<boolean>;
}

const PROFILE_FIELD_LABELS_ZH: Record<string, string> = {
  capital_amount: "资金规模",
  capital_range_min: "资金下限",
  capital_range_max: "资金上限",
  risk_tolerance: "风险偏好",
  investment_goal: "投资目标",
  investment_horizon: "投资期限",
  investment_style: "投资风格",
  default_market: "默认市场",
  preferred_sectors: "偏好行业",
  preferred_industries: "偏好细分行业",
  excluded_sectors: "禁投方向",
  excluded_industries: "不感兴趣行业",
  excluded_tickers: "排除标的",
  explicit_tickers: "关注标的",
};

const PROFILE_FIELD_LABELS_EN: Record<string, string> = {
  capital_amount: "Capital",
  capital_range_min: "Capital min",
  capital_range_max: "Capital max",
  risk_tolerance: "Risk",
  investment_goal: "Goal",
  investment_horizon: "Horizon",
  investment_style: "Style",
  default_market: "Default market",
  preferred_sectors: "Preferred sectors",
  preferred_industries: "Preferred industries",
  excluded_sectors: "Excluded sectors",
  excluded_industries: "Excluded industries",
  excluded_tickers: "Excluded tickers",
  explicit_tickers: "Focus tickers",
};

/** 把逗号或换行分隔的输入转成列表。 */
function parseListInput(value: string): string[] {
  return value
    .split(/[\n,;，；]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

/** 把列表字段转成文本输入内容。 */
function formatListInput(value: string[]): string {
  return value.join(", ");
}

/** 把数字输入转成可保存的数值。 */
function parseNumberInput(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** 判断档案是否已有可展示内容。 */
function hasProfileValue(profile: UserProfile): boolean {
  return Boolean(
    profile.capital_amount ||
      profile.capital_range_min ||
      profile.capital_range_max ||
      profile.risk_tolerance ||
      profile.investment_goal ||
      profile.investment_horizon ||
      profile.investment_style ||
      profile.default_market ||
      profile.preferred_sectors.length ||
      profile.preferred_industries.length ||
      profile.excluded_sectors.length ||
      profile.excluded_industries.length ||
      profile.excluded_tickers.length ||
      profile.explicit_tickers.length,
  );
}

/** 生成字段名的用户可读标签。 */
function fieldLabel(locale: Locale, key: string): string {
  return (locale === "zh" ? PROFILE_FIELD_LABELS_ZH : PROFILE_FIELD_LABELS_EN)[key] || key;
}

/** 显示待确认值。 */
function formatPendingValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join(", ");
  if (value === null || value === undefined || value === "") return "N/A";
  return String(value);
}

/** 把待确认关键偏好填入草稿，等待用户保存确认。 */
function buildPendingPatch(profile: UserProfile): ProfilePatch {
  const pending = profile.pending_confirmations;
  const keys = Object.keys(pending);
  const patch: ProfilePatch = {
    confirmed_fields: Array.from(new Set([...profile.confirmed_fields, ...keys])),
  };
  for (const key of keys) {
    const value = pending[key];
    if (
      key === "capital_amount" ||
      key === "capital_range_min" ||
      key === "capital_range_max" ||
      key === "risk_tolerance" ||
      key === "investment_goal"
    ) {
      (patch as Record<string, unknown>)[key] = value;
    }
  }
  return patch;
}

/** 账户档案中心。 */
export function AccountPanel({
  locale,
  currentAccount,
  loading,
  submitting,
  notice,
  profile,
  profileDraft,
  profileUpdatedAt,
  profileSaving,
  profileClearing,
  onProfileChange,
  onProfileSave,
  onProfileReset,
  onProfileClear,
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
            toggle: "档案",
            title: "个人投研档案中心",
            subtitle: "账户档案会优先用于个性化研究，关键偏好需要你确认后才保存。",
            email: "邮箱",
            password: "密码",
            login: "登录",
            register: "创建账户",
            sync: "同步浏览器记忆",
            logout: "退出账户",
            loading: "正在读取账户...",
            signedIn: "当前账户",
            syncTitle: "记忆同步",
            syncHint: "未登录时使用浏览器临时记忆；登录后优先使用账户档案，浏览器记忆只会在你点击同步后并入账户。",
            savedAt: "档案更新时间",
            empty: "当前账户还没有长期偏好。",
            pendingTitle: "待确认关键偏好",
            pendingHint: "这些内容来自最近一次研究，先填入草稿，再保存后才会写入账户档案。",
            applyPending: "填入待确认值",
            save: "保存并确认",
            reset: "还原草稿",
            clear: "清空账户偏好",
            clearTitle: "清空",
            clearConfirm: "确定要清空账户长期偏好吗？",
            accountProfile: "账户档案",
            profileStatus: "当前长期偏好",
          }
        : {
            toggle: "Account",
            title: "Investor Profile Center",
            subtitle: "Account preferences personalize research. Critical preferences are saved only after confirmation.",
            email: "Email",
            password: "Password",
            login: "Sign in",
            register: "Create account",
            sync: "Sync browser memory",
            logout: "Sign out",
            loading: "Loading account...",
            signedIn: "Signed in as",
            syncTitle: "Memory sync",
            syncHint:
              "Before sign-in, this browser keeps temporary memory. After sign-in, the account profile is used first. Browser memory is merged only when you sync it.",
            savedAt: "Profile updated",
            empty: "No long-term preferences saved yet.",
            pendingTitle: "Critical preferences pending confirmation",
            pendingHint: "These came from the latest run. Fill them into the draft, then save to confirm.",
            applyPending: "Use pending values",
            save: "Save and confirm",
            reset: "Reset draft",
            clear: "Clear account profile",
            clearTitle: "Clear",
            clearConfirm: "Clear the saved account preferences?",
            accountProfile: "Account profile",
            profileStatus: "Current long-term preferences",
          },
    [locale],
  );
  const pendingEntries = Object.entries(profile.pending_confirmations || {});
  const disabled = submitting || profileSaving || profileClearing;

  async function handleSubmit() {
    if (!email.trim() || !password.trim()) return;
    const ok = mode === "login" ? await onLogin(email.trim(), password) : await onRegister(email.trim(), password);
    if (ok) {
      setPassword("");
    }
  }

  function handleClearProfile() {
    if (typeof window !== "undefined" && !window.confirm(copy.clearConfirm)) return;
    onProfileClear();
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
        <UserCircle aria-hidden="true" />
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
              <div className="account-memory-strip">
                <div>
                  <span className="mini-label">{copy.signedIn}</span>
                  <strong>{currentAccount.email}</strong>
                </div>
                <div>
                  <span className="mini-label">{copy.savedAt}</span>
                  <strong>{formatDateTime(profileUpdatedAt, locale)}</strong>
                </div>
              </div>

              <div className="account-sync-note">
                <Cloud aria-hidden="true" />
                <div>
                  <strong>{copy.syncTitle}</strong>
                  <p>{copy.syncHint}</p>
                </div>
              </div>

              <div className="account-profile-status">
                <span className="mini-label">{copy.profileStatus}</span>
                {hasProfileValue(profile) ? (
                  <div className="account-profile-chip-row">
                    {profile.capital_amount ? <span>{`${fieldLabel(locale, "capital_amount")} ${profile.capital_amount}`}</span> : null}
                    {profile.risk_tolerance ? <span>{`${fieldLabel(locale, "risk_tolerance")} ${profile.risk_tolerance}`}</span> : null}
                    {profile.investment_goal ? <span>{`${fieldLabel(locale, "investment_goal")} ${profile.investment_goal}`}</span> : null}
                    {profile.investment_horizon ? <span>{`${fieldLabel(locale, "investment_horizon")} ${profile.investment_horizon}`}</span> : null}
                    {profile.default_market ? <span>{`${fieldLabel(locale, "default_market")} ${profile.default_market}`}</span> : null}
                  </div>
                ) : (
                  <p>{copy.empty}</p>
                )}
              </div>

              {pendingEntries.length ? (
                <div className="account-pending-list">
                  <div>
                    <strong>{copy.pendingTitle}</strong>
                    <p>{copy.pendingHint}</p>
                  </div>
                  <div className="account-profile-chip-row">
                    {pendingEntries.map(([key, value]) => (
                      <span key={key}>{`${fieldLabel(locale, key)}: ${formatPendingValue(value)}`}</span>
                    ))}
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => onProfileChange(buildPendingPatch(profile))}
                    disabled={disabled}
                  >
                    <ShieldCheck aria-hidden="true" />
                    {copy.applyPending}
                  </Button>
                </div>
              ) : null}

              <div className="account-profile-form">
                <div className="section-head tight">
                  <div>
                    <p className="eyebrow">{copy.accountProfile}</p>
                    <h3>{locale === "zh" ? "长期偏好" : "Long-term preferences"}</h3>
                  </div>
                </div>
                <div className="account-profile-grid">
                  <label className="field">
                    <span>{fieldLabel(locale, "capital_amount")}</span>
                    <input
                      type="number"
                      value={profileDraft.capital_amount ?? ""}
                      onChange={(event) => onProfileChange({ capital_amount: parseNumberInput(event.target.value) })}
                    />
                  </label>
                  <label className="field">
                    <span>{locale === "zh" ? "币种" : "Currency"}</span>
                    <input
                      value={profileDraft.currency ?? ""}
                      placeholder="USD"
                      onChange={(event) => onProfileChange({ currency: event.target.value.trim() || null })}
                    />
                  </label>
                  <label className="field">
                    <span>{fieldLabel(locale, "capital_range_min")}</span>
                    <input
                      type="number"
                      value={profileDraft.capital_range_min ?? ""}
                      onChange={(event) => onProfileChange({ capital_range_min: parseNumberInput(event.target.value) })}
                    />
                  </label>
                  <label className="field">
                    <span>{fieldLabel(locale, "capital_range_max")}</span>
                    <input
                      type="number"
                      value={profileDraft.capital_range_max ?? ""}
                      onChange={(event) => onProfileChange({ capital_range_max: parseNumberInput(event.target.value) })}
                    />
                  </label>
                  <label className="field">
                    <span>{fieldLabel(locale, "risk_tolerance")}</span>
                    <select
                      value={profileDraft.risk_tolerance ?? ""}
                      onChange={(event) => onProfileChange({ risk_tolerance: event.target.value || null })}
                    >
                      <option value="">{locale === "zh" ? "未设置" : "Not set"}</option>
                      <option value="low">{locale === "zh" ? "低风险" : "Low"}</option>
                      <option value="medium">{locale === "zh" ? "中等风险" : "Medium"}</option>
                      <option value="high">{locale === "zh" ? "高风险" : "High"}</option>
                    </select>
                  </label>
                  <label className="field">
                    <span>{fieldLabel(locale, "default_market")}</span>
                    <select
                      value={profileDraft.default_market ?? ""}
                      onChange={(event) => onProfileChange({ default_market: event.target.value || null })}
                    >
                      <option value="">{locale === "zh" ? "未设置" : "Not set"}</option>
                      <option value="US">US</option>
                      <option value="HK">HK</option>
                      <option value="CN">CN</option>
                      <option value="Global">Global</option>
                    </select>
                  </label>
                  <label className="field account-profile-full">
                    <span>{fieldLabel(locale, "investment_goal")}</span>
                    <input
                      value={profileDraft.investment_goal ?? ""}
                      onChange={(event) => onProfileChange({ investment_goal: event.target.value.trim() || null })}
                    />
                  </label>
                  <label className="field">
                    <span>{fieldLabel(locale, "investment_horizon")}</span>
                    <input
                      value={profileDraft.investment_horizon ?? ""}
                      onChange={(event) => onProfileChange({ investment_horizon: event.target.value.trim() || null })}
                    />
                  </label>
                  <label className="field">
                    <span>{fieldLabel(locale, "investment_style")}</span>
                    <input
                      value={profileDraft.investment_style ?? ""}
                      onChange={(event) => onProfileChange({ investment_style: event.target.value.trim() || null })}
                    />
                  </label>
                  <label className="field account-profile-full">
                    <span>{fieldLabel(locale, "preferred_sectors")}</span>
                    <textarea
                      rows={2}
                      value={formatListInput(profileDraft.preferred_sectors)}
                      onChange={(event) => onProfileChange({ preferred_sectors: parseListInput(event.target.value) })}
                    />
                  </label>
                  <label className="field account-profile-full">
                    <span>{fieldLabel(locale, "preferred_industries")}</span>
                    <textarea
                      rows={2}
                      value={formatListInput(profileDraft.preferred_industries)}
                      onChange={(event) => onProfileChange({ preferred_industries: parseListInput(event.target.value) })}
                    />
                  </label>
                  <label className="field account-profile-full">
                    <span>{fieldLabel(locale, "excluded_sectors")}</span>
                    <textarea
                      rows={2}
                      value={formatListInput(profileDraft.excluded_sectors)}
                      onChange={(event) => onProfileChange({ excluded_sectors: parseListInput(event.target.value) })}
                    />
                  </label>
                  <label className="field account-profile-full">
                    <span>{fieldLabel(locale, "excluded_tickers")}</span>
                    <textarea
                      rows={2}
                      value={formatListInput(profileDraft.excluded_tickers)}
                      onChange={(event) => onProfileChange({ excluded_tickers: parseListInput(event.target.value) })}
                    />
                  </label>
                </div>
              </div>

              <div className="button-row account-profile-actions">
                <Button type="button" onClick={() => onProfileSave()} disabled={disabled}>
                  <Save aria-hidden="true" />
                  {copy.save}
                </Button>
                <Button type="button" variant="secondary" onClick={() => onProfileReset()} disabled={disabled}>
                  <RotateCcw aria-hidden="true" />
                  {copy.reset}
                </Button>
                <Button type="button" variant="secondary" onClick={() => void onSyncMemory()} disabled={disabled}>
                  <RefreshCw aria-hidden="true" />
                  {copy.sync}
                </Button>
                <Button type="button" variant="secondary" onClick={() => void onLogout()} disabled={disabled}>
                  <LogOut aria-hidden="true" />
                  {copy.logout}
                </Button>
                <Button type="button" variant="destructive" onClick={handleClearProfile} disabled={disabled}>
                  <Trash2 aria-hidden="true" />
                  {copy.clearTitle}
                </Button>
              </div>
            </div>
          ) : (
            <div className="account-panel-stack">
              <div className="account-sync-note">
                <Cloud aria-hidden="true" />
                <div>
                  <strong>{copy.accountProfile}</strong>
                  <p>{copy.syncHint}</p>
                </div>
              </div>
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
