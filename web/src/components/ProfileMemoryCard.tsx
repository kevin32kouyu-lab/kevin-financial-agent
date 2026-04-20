/*
 * 长期偏好卡片。
 * 展示当前浏览器保存的长期记忆，并允许轻量编辑。
 */

import { formatDateTime } from "../lib/format";
import type { Locale, UserProfile } from "../lib/types";

interface ProfileMemoryCardProps {
  locale: Locale;
  profile: UserProfile;
  draft: UserProfile;
  updatedAt: string | null;
  loading: boolean;
  saving: boolean;
  clearing: boolean;
  appliedFields: string[];
  updatedFields: string[];
  onChange: (patch: Partial<UserProfile>) => void;
  onSave: () => void;
  onReset: () => void;
  onClear: () => void;
}

function parseListInput(value: string) {
  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function hasProfileValue(profile: UserProfile) {
  return Boolean(
    profile.capital_amount ||
      profile.currency ||
      profile.risk_tolerance ||
      profile.investment_horizon ||
      profile.investment_style ||
      profile.preferred_sectors.length ||
      profile.preferred_industries.length,
  );
}

function fieldLabel(locale: Locale, field: string) {
  const zhMap: Record<string, string> = {
    capital_amount: "资金规模",
    currency: "币种",
    risk_tolerance: "风险偏好",
    investment_horizon: "持有期限",
    investment_style: "投资风格",
    preferred_sectors: "偏好板块",
    preferred_industries: "偏好行业",
  };
  const enMap: Record<string, string> = {
    capital_amount: "Capital",
    currency: "Currency",
    risk_tolerance: "Risk",
    investment_horizon: "Horizon",
    investment_style: "Style",
    preferred_sectors: "Sectors",
    preferred_industries: "Industries",
  };
  return locale === "zh" ? zhMap[field] || field : enMap[field] || field;
}

export function ProfileMemoryCard({
  locale,
  profile,
  draft,
  updatedAt,
  loading,
  saving,
  clearing,
  appliedFields,
  updatedFields,
  onChange,
  onSave,
  onReset,
  onClear,
}: ProfileMemoryCardProps) {
  const t = (zh: string, en: string) => (locale === "zh" ? zh : en);
  const isDirty = JSON.stringify(profile) !== JSON.stringify(draft);

  return (
    <section className="panel-surface profile-memory-card">
      <div className="section-head tight">
        <div>
          <p className="eyebrow">{t("长期记忆", "Long-term memory")}</p>
          <h3>{t("系统记住的偏好", "Saved preferences")}</h3>
        </div>
      </div>

      <p className="section-note">
        {loading
          ? t("正在读取当前浏览器保存的长期偏好。", "Loading the saved profile for this browser.")
          : hasProfileValue(profile)
            ? t("这些偏好会在后续自然语言研究里自动补全空缺信息。", "These fields will be reused to fill missing details in future research runs.")
            : t("当前还没有保存长期偏好。你可以在这里手动填写，或让系统在提问中自动学习。", "No long-term profile is saved yet. You can fill it here or let the system learn from your requests.")}
      </p>

      <div className="profile-memory-grid">
        <label className="field compact-field">
          <span>{t("资金规模", "Capital amount")}</span>
          <input
            type="number"
            min={0}
            value={draft.capital_amount ?? ""}
            onChange={(event) =>
              onChange({
                capital_amount: event.target.value.trim() ? Number(event.target.value) : null,
              })
            }
          />
        </label>

        <label className="field compact-field">
          <span>{t("币种", "Currency")}</span>
          <input
            type="text"
            value={draft.currency ?? ""}
            placeholder="USD"
            onChange={(event) => onChange({ currency: event.target.value.trim().toUpperCase() || null })}
          />
        </label>

        <label className="field compact-field">
          <span>{t("风险偏好", "Risk profile")}</span>
          <input
            type="text"
            value={draft.risk_tolerance ?? ""}
            placeholder={t("如 Low / Medium / High", "e.g. Low / Medium / High")}
            onChange={(event) => onChange({ risk_tolerance: event.target.value.trim() || null })}
          />
        </label>

        <label className="field compact-field">
          <span>{t("持有期限", "Horizon")}</span>
          <input
            type="text"
            value={draft.investment_horizon ?? ""}
            placeholder={t("如 Long-term", "e.g. Long-term")}
            onChange={(event) => onChange({ investment_horizon: event.target.value.trim() || null })}
          />
        </label>

        <label className="field compact-field profile-memory-full">
          <span>{t("投资风格", "Style")}</span>
          <input
            type="text"
            value={draft.investment_style ?? ""}
            placeholder={t("如 Dividend / Quality / Growth", "e.g. Dividend / Quality / Growth")}
            onChange={(event) => onChange({ investment_style: event.target.value.trim() || null })}
          />
        </label>

        <label className="field profile-memory-full">
          <span>{t("偏好板块", "Preferred sectors")}</span>
          <input
            type="text"
            value={draft.preferred_sectors.join(", ")}
            placeholder={t("用逗号分隔，例如 Healthcare, Consumer Defensive", "Comma separated, e.g. Healthcare, Consumer Defensive")}
            onChange={(event) => onChange({ preferred_sectors: parseListInput(event.target.value) })}
          />
        </label>

        <label className="field profile-memory-full">
          <span>{t("偏好行业", "Preferred industries")}</span>
          <input
            type="text"
            value={draft.preferred_industries.join(", ")}
            placeholder={t("用逗号分隔，例如 Software, Banks", "Comma separated, e.g. Software, Banks")}
            onChange={(event) => onChange({ preferred_industries: parseListInput(event.target.value) })}
          />
        </label>
      </div>

      <div className="profile-memory-meta">
        <span>{t("最近保存", "Last saved")}</span>
        <strong>{updatedAt ? formatDateTime(updatedAt, locale) : t("尚未保存", "Not saved yet")}</strong>
      </div>

      {appliedFields.length ? (
        <div className="warning-banner compact-banner">
          <strong>{t("本次自动沿用：", "Auto-applied this run:")}</strong>{" "}
          {appliedFields.map((field) => fieldLabel(locale, field)).join(locale === "zh" ? "、" : ", ")}
        </div>
      ) : null}

      {updatedFields.length ? (
        <div className="executive-banner compact-banner">
          <strong>{t("本次写回记忆：", "Saved from this run:")}</strong>{" "}
          {updatedFields.map((field) => fieldLabel(locale, field)).join(locale === "zh" ? "、" : ", ")}
        </div>
      ) : null}

      <div className="button-row compact profile-memory-actions">
        <button type="button" className="primary-button compact-action" disabled={saving || !isDirty} onClick={onSave}>
          {saving ? t("保存中", "Saving") : t("保存修改", "Save")}
        </button>
        <button type="button" className="secondary-button compact-action" disabled={!isDirty || saving} onClick={onReset}>
          {t("恢复当前值", "Reset draft")}
        </button>
        <button type="button" className="secondary-button compact-action" disabled={clearing} onClick={onClear}>
          {clearing ? t("清空中", "Clearing") : t("清空记忆", "Clear")}
        </button>
      </div>
    </section>
  );
}
