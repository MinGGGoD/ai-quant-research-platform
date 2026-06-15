export interface Pagination {
  limit: number
  offset: number
  total: number
}

export interface Stock {
  id: number
  symbol: string
  exchange: 'SSE' | 'SZSE' | 'BSE'
  name: string
  list_date: string | null
  delist_date: string | null
  status: string
}

export interface StockReference {
  id: number
  symbol: string
  exchange: string
  name: string
}

export interface DailyPrice {
  trade_date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  amount: number | null
  source: string
}

export interface ScannerRun {
  id: string
  status: string
  data_date: string
  universe_name: string
  started_at: string
  finished_at: string | null
  total_stocks: number
  processed_stocks: number
  matched_stocks: number
  warning_count: number
  error_count: number
}

export interface SignalDefinition {
  code: string
  version: number
  name: string
}

export interface TechnicalSignal {
  id: string
  scanner_run_id: string
  signal_date: string
  signal: SignalDefinition
  matched_values: Record<string, unknown>
  explanation: string
}

export interface StockListResponse {
  items: Stock[]
  pagination: Pagination
}

export interface StockPricesResponse {
  stock: StockReference
  price_adjustment: string
  items: DailyPrice[]
}

export interface DateRange {
  from_date: string
  to_date: string
}

export interface StockPriceSyncMetadata {
  requested_range: DateRange
  effective_range: DateRange | null
  cache_hit: boolean
  fetched_ranges: DateRange[]
  prices_inserted: number
  prices_updated: number
}

export interface StockPriceSyncResponse extends StockPricesResponse {
  sync: StockPriceSyncMetadata
}

export interface ScannerRunListResponse {
  items: ScannerRun[]
  pagination: Pagination
}

export interface StockSignalsResponse {
  stock: StockReference
  items: TechnicalSignal[]
  pagination: Pagination
}

export interface ApiErrorPayload {
  error?: {
    code?: string
    message?: string
    request_id?: string
  }
}
