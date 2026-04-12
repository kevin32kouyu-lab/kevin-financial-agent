export type RunMode = "agent" | "structured";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "needs_clarification";
export type Locale = "zh" | "en";

export interface RuntimeConfig {
  provider: string;
  api_key_configured: boolean;
  model: string;
  base_url: string;
  route_mode: string;
  billing_mode: string;
  official_sdk: string;
}

export interface DataStatus {
  dataset: string;
  records: number;
  source: string;
  universe_scope?: string;
  exchange_summary?: Record<string, number>;
  last_refresh_at?: string | null;
  last_refresh_count: number;
  seed_path: string;
  database_path: string;
  fallback_enabled: boolean;
  live_sources: string[];
  provider_statuses?: Array<{
    provider: string;
    role: string;
    configured: boolean;
  }>;
  macro_status?: {
    source: string;
    last_refresh_at?: string | null;
    last_refresh_count: number;
    status?: string | null;
    regime?: string | null;
  };
  sec_filings_status?: {
    source: string;
    last_refresh_at?: string | null;
    last_refresh_count: number;
    records: number;
    covered_tickers: number;
  };
  refresh_summary?: {
    universe_source?: string | null;
    macro_source?: string | null;
  };
}

export interface RunCreateRequest {
  mode: RunMode;
  agent?: AgentRunRequest;
  structured?: StructuredRunRequest;
}

export interface AgentRunRequest {
  query: string;
  options: {
    fetch_live_data: boolean;
    max_results: number;
  };
  llm?: {
    model?: string | null;
    base_url?: string | null;
  };
}

export interface StructuredRunRequest {
  risk_profile: {
    tolerance_level?: string | null;
  };
  investment_strategy: {
    horizon?: string | null;
    style?: string | null;
    preferred_sectors: string[];
    preferred_industries: string[];
  };
  fundamental_filters: {
    max_pe_ratio?: number | null;
    min_roe?: number | null;
    min_dividend_yield?: number | null;
    require_positive_fcf: boolean;
    analyst_rating?: string | null;
  };
  explicit_targets: {
    tickers: string[];
  };
  portfolio_sizing: Record<string, unknown>;
  options: {
    fetch_live_data: boolean;
    max_results: number;
  };
}

export interface RunSummary {
  id: string;
  mode: RunMode;
  workflow_key: string;
  status: RunStatus;
  title: string;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  parent_run_id?: string | null;
  error_message?: string | null;
  report_mode?: string | null;
  attempt_count: number;
  metadata: Record<string, unknown>;
}

export interface RunStepRecord {
  step_key: string;
  label: string;
  status: string;
  elapsed_ms?: number | null;
  summary?: string | null;
  position: number;
  created_at: string;
  updated_at: string;
  input_data?: unknown;
  output_data?: unknown;
  error_data?: unknown;
}

export interface ArtifactRecord {
  id: number;
  kind: string;
  name: string;
  created_at: string;
  updated_at: string;
  content: unknown;
}

export interface ArtifactMeta {
  id: number;
  kind: string;
  name: string;
  created_at: string;
  updated_at: string;
}

export interface RunDetailResponse {
  run: RunSummary;
  steps: RunStepRecord[];
  artifacts: ArtifactMeta[];
  result: Record<string, unknown> | null;
}

export interface RunArtifactsResponse {
  run_id: string;
  artifacts: ArtifactRecord[];
}

export interface RunListResponse {
  items: RunSummary[];
}

export interface DeleteRunsResponse {
  deleted_count: number;
}

export interface RunEvent {
  id?: number;
  event_type: string;
  payload: Record<string, unknown>;
}

export interface HistoryFilters {
  search: string;
  mode: string;
  status: string;
}

export interface AgentFormState {
  query: string;
  maxResults: number;
  fetchLiveData: boolean;
}

export interface StructuredFormState {
  tickers: string;
  sectors: string;
  industries: string;
  riskLevel: string;
  maxResults: number;
  maxPe: string;
  minRoe: string;
  minDividendYield: string;
  analystRating: string;
  requirePositiveFcf: boolean;
  fetchLiveData: boolean;
}
