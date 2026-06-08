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
