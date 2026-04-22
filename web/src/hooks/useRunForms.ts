import {
  useState,
} from "react";
import { splitLines } from "../lib/format";
import { getLocalePack } from "../lib/i18n";
import type {
  AgentFormState,
  Locale,
  RunMode,
  StructuredFormState,
} from "../lib/types";

const AGENT_SAMPLES: Record<Locale, string> = {
  zh: "我有 50000 美元，想找适合长期持有的低风险分红股。请优先比较 JNJ、PG、KO，并给我一份正式的投资研究结论，包括估值、ROE、自由现金流、主要风险和执行建议。",
  en: "I have 50000 USD and want a long-term low-risk dividend portfolio. Compare JNJ, PG and KO, then give me a formal investment memo covering valuation, ROE, cash flow, key risks and execution advice.",
};

const DEFAULT_AGENT_FORM: AgentFormState = {
  query: "",
  maxResults: 5,
  fetchLiveData: true,
  allocationMode: "equal_weight",
  customWeights: "",
};

const DEFAULT_STRUCTURED_FORM: StructuredFormState = {
  tickers: "",
  sectors: "Healthcare, Consumer Defensive",
  industries: "",
  riskLevel: "medium",
  maxResults: 5,
  maxPe: "30",
  minRoe: "10",
  minDividendYield: "2",
  analystRating: "",
  requirePositiveFcf: true,
  fetchLiveData: true,
};

function toOptionalNumber(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function buildStructuredPayload(form: StructuredFormState) {
  return {
    risk_profile: { tolerance_level: form.riskLevel },
    investment_strategy: {
      preferred_sectors: splitLines(form.sectors),
      preferred_industries: splitLines(form.industries),
    },
    fundamental_filters: {
      max_pe_ratio: toOptionalNumber(form.maxPe),
      min_roe: toOptionalNumber(form.minRoe),
      min_dividend_yield: toOptionalNumber(form.minDividendYield),
      require_positive_fcf: form.requirePositiveFcf,
      analyst_rating: form.analystRating || null,
    },
    explicit_targets: {
      tickers: splitLines(form.tickers).map((item) => item.toUpperCase()),
    },
    portfolio_sizing: {},
    options: {
      fetch_live_data: form.fetchLiveData,
      max_results: form.maxResults,
    },
  };
}

export function useRunForms(
  locale: Locale,
  setLocale: (locale: Locale) => void,
) {
  const copy = getLocalePack(locale);
  const t = (zhText: string, enText: string) => (locale === "zh" ? zhText : enText);

  const [mode, setMode] = useState<RunMode>("agent");
  const [agentForm, setAgentFormState] = useState<AgentFormState>(DEFAULT_AGENT_FORM);
  const [structuredForm, setStructuredFormState] = useState<StructuredFormState>(DEFAULT_STRUCTURED_FORM);
  const [errorText, setErrorText] = useState("");
  const [creatingRun, setCreatingRun] = useState(false);

  const setAgentForm = (patch: Partial<AgentFormState>) =>
    setAgentFormState((current) => ({ ...current, ...patch }));

  const setStructuredForm = (patch: Partial<StructuredFormState>) =>
    setStructuredFormState((current) => ({ ...current, ...patch }));

  const fillAgentSample = () => {
    setAgentFormState({ ...DEFAULT_AGENT_FORM, query: AGENT_SAMPLES[locale] });
    setErrorText("");
  };

  const fillStructuredSample = () => {
    setStructuredFormState({
      ...DEFAULT_STRUCTURED_FORM,
      tickers: "JNJ, PG, KO",
    });
    setErrorText("");
  };

  const validateAgentForm = (): boolean => {
    if (!agentForm.query.trim()) {
      setErrorText(locale === "zh" ? "请先输入投资问题。" : "Please enter an investment request first.");
      return false;
    }
    setErrorText("");
    return true;
  };

  const validateStructuredForm = (): boolean => {
    setErrorText("");
    return true;
  };

  return {
    // State
    mode,
    setMode,
    agentForm,
    setAgentForm,
    structuredForm,
    setStructuredForm,
    errorText,
    setErrorText,
    creatingRun,
    setCreatingRun,

    // Actions
    fillAgentSample,
    fillStructuredSample,
    validateAgentForm,
    validateStructuredForm,
    buildStructuredPayload,

    // Helpers
    toOptionalNumber,
  };
}
