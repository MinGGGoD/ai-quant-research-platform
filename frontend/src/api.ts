import type {
  ApiErrorPayload,
  ScannerRunListResponse,
  StockListResponse,
  StockPricesResponse,
  StockSignalsResponse,
} from './types'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
).replace(/\/$/, '')

export class ApiError extends Error {
  readonly requestId?: string

  constructor(message: string, requestId?: string) {
    super(message)
    this.name = 'ApiError'
    this.requestId = requestId
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
  })

  if (!response.ok) {
    let payload: ApiErrorPayload = {}
    try {
      payload = (await response.json()) as ApiErrorPayload
    } catch {
      // Keep the status-based fallback for non-JSON failures.
    }
    throw new ApiError(
      payload.error?.message ??
        `Request failed with status ${response.status}.`,
      payload.error?.request_id,
    )
  }

  return (await response.json()) as T
}

function stockResourcePath(
  symbol: string,
  exchange: string,
  resource: 'prices' | 'signals',
  limit: number,
): string {
  const params = new URLSearchParams({
    exchange,
    limit: String(limit),
  })
  return `/api/v1/stocks/${encodeURIComponent(symbol)}/${resource}?${params}`
}

export function getStocks(
  query: string,
  offset: number,
  signal?: AbortSignal,
): Promise<StockListResponse> {
  const params = new URLSearchParams({
    status: 'active',
    limit: '30',
    offset: String(offset),
  })
  if (query.trim()) {
    params.set('query', query.trim())
  }
  return getJson(`/api/v1/stocks?${params}`, signal)
}

export function getStockPrices(
  symbol: string,
  exchange: string,
  signal?: AbortSignal,
): Promise<StockPricesResponse> {
  return getJson(stockResourcePath(symbol, exchange, 'prices', 1000), signal)
}

export function getStockSignals(
  symbol: string,
  exchange: string,
  signal?: AbortSignal,
): Promise<StockSignalsResponse> {
  return getJson(stockResourcePath(symbol, exchange, 'signals', 50), signal)
}

export function getScannerRuns(
  signal?: AbortSignal,
): Promise<ScannerRunListResponse> {
  return getJson('/api/v1/scanner-runs?limit=8', signal)
}
