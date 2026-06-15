import type {
  ApiErrorPayload,
  ScannerRunListResponse,
  StockListResponse,
  StockPriceSyncResponse,
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

async function requestJson<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      Accept: 'application/json',
      ...options.headers,
    },
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
  fromDate?: string,
  toDate?: string,
): string {
  const params = new URLSearchParams({
    exchange,
    limit: String(limit),
  })
  if (fromDate) {
    params.set('from_date', fromDate)
  }
  if (toDate) {
    params.set('to_date', toDate)
  }
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
  return requestJson(`/api/v1/stocks?${params}`, { signal })
}

export function getStockPrices(
  symbol: string,
  exchange: string,
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<StockPricesResponse> {
  return requestJson(
    stockResourcePath(symbol, exchange, 'prices', 1000, fromDate, toDate),
    { signal },
  )
}

export function syncStockPrices(
  symbol: string,
  exchange: string,
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<StockPriceSyncResponse> {
  const params = new URLSearchParams({ exchange })
  return requestJson(
    `/api/v1/stocks/${encodeURIComponent(symbol)}/prices/sync?${params}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        from_date: fromDate,
        to_date: toDate,
      }),
      signal,
    },
  )
}

export function getStockSignals(
  symbol: string,
  exchange: string,
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<StockSignalsResponse> {
  return requestJson(
    stockResourcePath(symbol, exchange, 'signals', 50, fromDate, toDate),
    { signal },
  )
}

export function getScannerRuns(
  signal?: AbortSignal,
): Promise<ScannerRunListResponse> {
  return requestJson('/api/v1/scanner-runs?limit=8', { signal })
}
