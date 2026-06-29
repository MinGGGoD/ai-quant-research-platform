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

export type PriceFrequency = 'daily' | '30m' | '60m'

export interface DailyPrice {
  trade_date: string
  timestamp?: string | null
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

export interface ScannerRunSummary {
  total_stocks: number
  processed_stocks: number
  matched_stocks: number
  warning_count: number
  error_count: number
}

export interface ScannerRunDetail {
  id: string
  status: string
  data_date: string
  universe_name: string
  parameters: Record<string, unknown>
  started_at: string
  finished_at: string | null
  summary: ScannerRunSummary
  error_message: string | null
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
  stock?: StockReference
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
  frequency: PriceFrequency
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

export interface ChanAlgorithm {
  code: string
  version: number
  parameters: Record<string, unknown>
}

export type ChanStatus = 'confirmed' | 'provisional'
export type ChanDirection = 'up' | 'down' | 'neutral'

export interface ChanFractal {
  index: number
  bar_time: string
  trade_date: string
  timestamp?: string | null
  kind: 'top' | 'bottom'
  price: number
  status: ChanStatus
}

export interface ChanStroke {
  start_index: number
  end_index: number
  start_time: string
  end_time: string
  direction: ChanDirection
  price_low: number
  price_high: number
  status: ChanStatus
}

export interface ChanSegment {
  start_index: number
  end_index: number
  start_time: string
  end_time: string
  direction: ChanDirection
  price_low: number
  price_high: number
  status: ChanStatus
  stroke_indexes: number[]
}

export interface ChanCenter {
  start_index: number
  end_index: number
  start_time: string
  end_time: string
  price_low: number
  price_high: number
  status: ChanStatus
  stroke_indexes: number[]
}

export interface ChanObservation {
  index: number
  bar_time: string
  trade_date: string
  timestamp?: string | null
  kind: string
  side: 'buy' | 'sell'
  label: string
  price: number
  status: ChanStatus
  explanation: string
}

export interface ChanAnalysis {
  stock: StockReference
  frequency: PriceFrequency
  algorithm: ChanAlgorithm
  price_bar_count: number
  fractals: ChanFractal[]
  strokes: ChanStroke[]
  segments: ChanSegment[]
  centers: ChanCenter[]
  observations: ChanObservation[]
}

export interface ScannerRunListResponse {
  items: ScannerRun[]
  pagination: Pagination
}

export interface SignalListResponse {
  items: TechnicalSignal[]
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
