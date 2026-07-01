export type UserId = string & { readonly __brand: 'UserId' }
export type UniverseId = string & { readonly __brand: 'UniverseId' }

export interface UserResponse {
  readonly id: UserId
  readonly email: string
  readonly is_admin: boolean
  readonly created_at: string
  readonly full_name: string | null
}

export interface SessionInfo {
  readonly id: string
  readonly created_at: string
  readonly expires_at: string
  readonly last_used_at: string | null
  readonly user_agent: string | null
  readonly ip: string | null
  readonly is_current: boolean
}

export interface TokenResponse {
  readonly access_token: string
  readonly token_type: string
  readonly user: UserResponse
}

export interface UniverseSummary {
  readonly id: UniverseId
  readonly name: string
  readonly display_name: string
  readonly is_system_managed: boolean
  readonly created_at: string
  readonly ticker_count: number
  readonly public_id: string | null
  readonly last_retrain_at: string | null
  readonly description: string | null
}

export interface TickerSummary {
  readonly id: string
  readonly symbol: string
  readonly name: string
  readonly exchange: string | null
  readonly asset_type: string
  readonly active: boolean
  readonly added_at?: string
}

export interface AddMembersRequest {
  readonly symbols: readonly string[]
}

export interface AddResult {
  readonly added: readonly string[]
  readonly already_present: readonly string[]
  readonly invalid: readonly string[]
}

export interface ImportResult extends AddResult {
  readonly parse_errors: readonly string[]
}

export interface UniverseDetail extends UniverseSummary {
  readonly tickers: readonly TickerSummary[]
}

export interface UniverseListResponse {
  readonly universes: readonly UniverseSummary[]
  readonly total: number
}

export interface ApiError {
  readonly error_code: string
  readonly message: string
  readonly details?: Record<string, unknown>
  readonly request_id?: string
}

// Data Ingestion / Monitoring

export interface IngestRunResponse {
  readonly id: string
  readonly triggered_by: string
  readonly triggered_at: string
  readonly completed_at: string | null
  readonly status: string
  readonly ohlcv_rows_inserted: number
  readonly macro_rows_inserted: number
  readonly failed_tickers: string[] | null
  readonly stale_macro: boolean
  readonly error_summary: string | null
}

export interface IngestionStatusResponse {
  readonly latest_run: IngestRunResponse | null
  readonly per_universe_freshness: readonly Record<string, unknown>[]
}

export interface IngestionTriggerResponse {
  readonly message: string
  readonly run_id: string | null
  readonly prefect_run_id: string | null
}

export interface ConvictionTicket {
  readonly id: string
  readonly ticker_id: string
  readonly universe_id: string
  readonly inference_date: string
  readonly horizon: string
  readonly direction: string
  readonly predicted_return: number
  readonly conviction_score: number
  readonly conformal_lower: number
  readonly conformal_upper: number
  readonly backtest_passes: number
  readonly backtest_pass_strategies: readonly string[]
  readonly status: string
  readonly resolution_date: string
  readonly actual_return: number | null
  readonly outcome: string | null
  readonly user_notes: string | null
  readonly created_at: string | null
  readonly updated_at: string | null
}

export interface TicketListResponse {
  readonly tickets: readonly ConvictionTicket[]
  readonly total: number
}

export interface TicketActionResponse {
  readonly message: string
  readonly ticket: ConvictionTicket
}

export interface BacktestRunInfo {
  readonly id: string
  readonly status: string
  readonly backtest_period_start: string
  readonly backtest_period_end: string
}

export interface TickerPassEntry {
  readonly ticker_id: string
  readonly symbol: string
  readonly passes: number
  readonly strategies: { readonly [key: string]: boolean }
}

export interface UniversePassSummary {
  readonly universe_id: string
  readonly run: BacktestRunInfo | null
  readonly tickers: readonly TickerPassEntry[]
}

export interface StrategyMetrics {
  readonly strategy_name: string
  readonly sharpe_ratio: number | null
  readonly max_drawdown: number | null
  readonly total_return: number | null
  readonly win_rate: number | null
  readonly profit_factor: number | null
  readonly total_trades: number | null
  readonly passed: boolean
  readonly equity_curve: readonly { readonly date: string; readonly value: number }[] | null
}

export interface TickerBacktestDetail {
  readonly ticker_id: string
  readonly symbol: string
  readonly strategies: readonly StrategyMetrics[]
}
