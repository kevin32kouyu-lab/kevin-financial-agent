export type RunMode = "agent" | "structured";
export type RunStatus = "queued" | "running" | "completed" | "failed" | "needs_clarification" | "cancelled";
export type Locale = "zh" | "en";
export type TerminalMode = "realtime" | "historical";
export type BacktestMode = "replay" | "reference";

export interface BacktestCreateRequest {
  mode?: BacktestMode;
  source_run_id: string;
  entry_date?: string | null;
  end_date?: string | null;
}

export interface BacktestMetrics {
  initial_capital: number;
  final_value: number;
  benchmark_final_value: number;
  total_return_pct: number;
  benchmark_return_pct: number;
  excess_return_pct: number;
  annualized_return_pct?: number | null;
  max_drawdown_pct?: number | null;
  trading_days: number;
}

export interface BacktestSummary {
  id: string;
  source_run_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  entry_date: string;
  end_date: string;
  benchmark_ticker: string;
  metrics: BacktestMetrics;
  requested_count: number;
  coverage_count: number;
  dropped_tickers: Array<{
    ticker: string;
    reason: string;
  }>;
}

export interface BacktestPoint {
  point_date: string;
  portfolio_value: number;
  benchmark_value: number;
  portfolio_return_pct: number;
  benchmark_return_pct: number;
}

export interface BacktestPositionPoint {
  point_date: string;
  close_price: number;
  daily_return_pct: number;
  cumulative_return_pct: number;
  contribution_pct: number;
}

export interface BacktestPosition {
  timeseries: BacktestPositionPoint[];
  ticker: string;
  weight: number;
  verdict: string;
  entry_date: string;
  entry_price: number;
  latest_price: number;
  shares: number;
  invested_amount: number;
  current_value: number;
  return_pct: number;
  contribution_pct: number;
}

export interface BacktestDetail {
  summary: BacktestSummary;
  positions: BacktestPosition[];
  points: BacktestPoint[];
  meta: Record<string, unknown>;
}

export interface BacktestListResponse {
  items: BacktestSummary[];
}

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

export interface UserProfile {
  capital_amount: number | null;
  currency: string | null;
  risk_tolerance: string | null;
  investment_horizon: string | null;
  investment_style: string | null;
  preferred_sectors: string[];
  preferred_industries: string[];
}

export interface RunMemory {
  profile: UserProfile;
  applied_fields: string[];
  updated_fields: string[];
}

export interface ProfileResponse {
  client_id: string;
  profile: UserProfile;
  updated_at: string | null;
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
  research_context?: {
    research_mode: TerminalMode;
    as_of_date?: string | null;
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
