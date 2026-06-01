export type UserId = string & { readonly __brand: 'UserId' }
export type UniverseId = string & { readonly __brand: 'UniverseId' }

export interface UserResponse {
  readonly id: UserId
  readonly email: string
  readonly is_admin: boolean
  readonly created_at: string
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
