import { useCallback, useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import {
  ApiError,
  getScannerRuns,
  getStockPrices,
  getStockSignals,
  getStocks,
  syncStockPrices,
} from './api'
import './App.css'
import KlineChart from './components/KlineChart'
import type {
  DailyPrice,
  Pagination,
  ScannerRun,
  Stock,
  StockPriceSyncMetadata,
  StockPriceSyncResponse,
  StockPricesResponse,
  TechnicalSignal,
} from './types'

const EMPTY_PAGINATION: Pagination = { limit: 30, offset: 0, total: 0 }
const RECENT_STOCKS_KEY = 'ai-quant-recent-stocks'
const RECENT_STOCK_LIMIT = 6

interface SelectedDateRange {
  fromDate: string
  toDate: string
}

type DetailRequestMode = 'cache' | 'sync'

function localIsoDate(value: Date): string {
  const year = value.getFullYear()
  const month = String(value.getMonth() + 1).padStart(2, '0')
  const day = String(value.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function defaultDateRange(): SelectedDateRange {
  const end = new Date()
  const start = new Date(end)
  start.setFullYear(start.getFullYear() - 2)
  return {
    fromDate: localIsoDate(start),
    toDate: localIsoDate(end),
  }
}

function loadRecentStocks(): Stock[] {
  try {
    const value = window.localStorage.getItem(RECENT_STOCKS_KEY)
    if (!value) {
      return []
    }
    const stocks = JSON.parse(value) as unknown
    if (!Array.isArray(stocks)) {
      return []
    }
    return stocks
      .filter(
        (stock): stock is Stock =>
          typeof stock === 'object' &&
          stock !== null &&
          typeof stock.id === 'number' &&
          typeof stock.symbol === 'string' &&
          (stock.exchange === 'SSE' ||
            stock.exchange === 'SZSE' ||
            stock.exchange === 'BSE') &&
          typeof stock.name === 'string',
      )
      .slice(0, RECENT_STOCK_LIMIT)
  } catch {
    return []
  }
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
  }).format(value)
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

function humanize(value: string): string {
  return value.replaceAll('_', ' ')
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.requestId
      ? `${error.message} Request ID: ${error.requestId}`
      : error.message
  }
  return 'The research data could not be loaded.'
}

function hasSyncMetadata(
  response: StockPricesResponse | StockPriceSyncResponse,
): response is StockPriceSyncResponse {
  return 'sync' in response
}

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [stockPagination, setStockPagination] =
    useState<Pagination>(EMPTY_PAGINATION)
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null)
  const [prices, setPrices] = useState<DailyPrice[]>([])
  const [signals, setSignals] = useState<TechnicalSignal[]>([])
  const [scannerRuns, setScannerRuns] = useState<ScannerRun[]>([])
  const [syncMetadata, setSyncMetadata] =
    useState<StockPriceSyncMetadata | null>(null)
  const [recentStocks, setRecentStocks] = useState<Stock[]>(loadRecentStocks)
  const [searchInput, setSearchInput] = useState('')
  const [activeQuery, setActiveQuery] = useState('')
  const [stockOffset, setStockOffset] = useState(0)
  const [stocksLoading, setStocksLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [runsLoading, setRunsLoading] = useState(true)
  const [stocksError, setStocksError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [syncWarning, setSyncWarning] = useState<string | null>(null)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [dateRangeError, setDateRangeError] = useState<string | null>(null)
  const [dateRange, setDateRange] =
    useState<SelectedDateRange>(defaultDateRange)
  const [appliedDateRange, setAppliedDateRange] =
    useState<SelectedDateRange>(dateRange)
  const [detailRequestMode, setDetailRequestMode] =
    useState<DetailRequestMode>('cache')
  const [stockReloadToken, setStockReloadToken] = useState(0)
  const [detailReloadToken, setDetailReloadToken] = useState(0)
  const [runsReloadToken, setRunsReloadToken] = useState(0)
  const pendingSearchSync = useRef(false)
  const today = localIsoDate(new Date())

  const rememberStock = useCallback((stock: Stock) => {
    setRecentStocks((current) => {
      const next = [
        stock,
        ...current.filter(
          (item) =>
            item.symbol !== stock.symbol || item.exchange !== stock.exchange,
        ),
      ].slice(0, RECENT_STOCK_LIMIT)
      try {
        window.localStorage.setItem(RECENT_STOCKS_KEY, JSON.stringify(next))
      } catch {
        // Recent shortcuts remain available for this session.
      }
      return next
    })
  }, [])

  const selectStock = useCallback(
    (
      stock: Stock | null,
      remember = true,
      requestMode: DetailRequestMode = 'sync',
    ) => {
      setSelectedStock(stock)
      setDetailError(null)
      setSyncWarning(null)
      setSyncMetadata(null)
      if (stock) {
        setDetailLoading(true)
        setDetailRequestMode(requestMode)
        setDetailReloadToken((value) => value + 1)
        if (remember) {
          rememberStock(stock)
        }
      } else {
        setDetailLoading(false)
        setPrices([])
        setSignals([])
      }
    },
    [rememberStock],
  )

  useEffect(() => {
    const controller = new AbortController()

    getStocks(activeQuery, stockOffset, controller.signal)
      .then((response) => {
        setStocks(response.items)
        setStockPagination(response.pagination)
        const shouldSync = pendingSearchSync.current && stockOffset === 0
        selectStock(
          response.items[0] ?? null,
          activeQuery.length > 0 && stockOffset === 0,
          shouldSync ? 'sync' : 'cache',
        )
        pendingSearchSync.current = false
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setStocks([])
        selectStock(null)
        pendingSearchSync.current = false
        setStocksError(errorMessage(error))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setStocksLoading(false)
        }
      })

    return () => controller.abort()
  }, [activeQuery, selectStock, stockOffset, stockReloadToken])

  useEffect(() => {
    const controller = new AbortController()

    getScannerRuns(controller.signal)
      .then((response) => setScannerRuns(response.items))
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setScannerRuns([])
        setRunsError(errorMessage(error))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setRunsLoading(false)
        }
      })

    return () => controller.abort()
  }, [runsReloadToken])

  useEffect(() => {
    if (!selectedStock) {
      return
    }

    const controller = new AbortController()

    Promise.all([
      detailRequestMode === 'sync'
        ? syncStockPrices(
            selectedStock.symbol,
            selectedStock.exchange,
            appliedDateRange.fromDate,
            appliedDateRange.toDate,
            controller.signal,
          )
        : getStockPrices(
            selectedStock.symbol,
            selectedStock.exchange,
            appliedDateRange.fromDate,
            appliedDateRange.toDate,
            controller.signal,
          ),
      getStockSignals(
        selectedStock.symbol,
        selectedStock.exchange,
        appliedDateRange.fromDate,
        appliedDateRange.toDate,
        controller.signal,
      ),
    ])
      .then(([priceResponse, signalResponse]) => {
        setPrices(priceResponse.items)
        setSignals(signalResponse.items)
        setSyncMetadata(
          hasSyncMetadata(priceResponse) ? priceResponse.sync : null,
        )
      })
      .catch(async (error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        if (detailRequestMode === 'sync') {
          try {
            const [cachedPriceResponse, signalResponse] = await Promise.all([
              getStockPrices(
                selectedStock.symbol,
                selectedStock.exchange,
                appliedDateRange.fromDate,
                appliedDateRange.toDate,
                controller.signal,
              ),
              getStockSignals(
                selectedStock.symbol,
                selectedStock.exchange,
                appliedDateRange.fromDate,
                appliedDateRange.toDate,
                controller.signal,
              ),
            ])
            setPrices(cachedPriceResponse.items)
            setSignals(signalResponse.items)
            setSyncMetadata(null)
            setSyncWarning(
              `${errorMessage(error)} Showing cached records instead.`,
            )
            return
          } catch (fallbackError: unknown) {
            if (
              fallbackError instanceof DOMException &&
              fallbackError.name === 'AbortError'
            ) {
              return
            }
            error = fallbackError
          }
        }
        setPrices([])
        setSignals([])
        setDetailError(errorMessage(error))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setDetailLoading(false)
        }
      })

    return () => controller.abort()
  }, [appliedDateRange, detailReloadToken, detailRequestMode, selectedStock])

  const submitSearch = useCallback(
    (event: FormEvent<HTMLFormElement>) => {
      event.preventDefault()
      if (
        !dateRange.fromDate ||
        !dateRange.toDate ||
        dateRange.fromDate > dateRange.toDate
      ) {
        setDateRangeError('Start date must not be later than end date.')
        return
      }
      if (dateRange.toDate > today) {
        setDateRangeError('End date must not be later than today.')
        return
      }
      setDateRangeError(null)
      setAppliedDateRange(dateRange)
      pendingSearchSync.current = true
      setStocksLoading(true)
      setStocksError(null)
      setStockOffset(0)
      setActiveQuery(searchInput.trim())
      if (activeQuery === searchInput.trim() && stockOffset === 0) {
        setStockReloadToken((value) => value + 1)
      }
    },
    [activeQuery, dateRange, searchInput, stockOffset, today],
  )

  const latestPrice = prices.at(-1)
  const previousPrice = prices.at(-2)
  const priceChange =
    latestPrice && previousPrice
      ? latestPrice.close - previousPrice.close
      : null
  const canGoBack = stockPagination.offset > 0
  const canGoForward =
    stockPagination.offset + stockPagination.limit < stockPagination.total

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <p className="eyebrow">A-share research workspace</p>
          <h1>Quant Research Dashboard</h1>
        </div>
        <div className="research-boundary">
          <span className="status-dot" aria-hidden="true" />
          Research and education only
        </div>
      </header>

      <main className="dashboard">
        <aside className="panel stock-panel" aria-labelledby="stocks-heading">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Market universe</p>
              <h2 id="stocks-heading">Stocks</h2>
            </div>
            <span className="count-badge">{stockPagination.total}</span>
          </div>

          <form className="stock-search" onSubmit={submitSearch}>
            <label htmlFor="stock-query">Search stocks</label>
            <div className="search-row">
              <input
                id="stock-query"
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Code or name"
              />
              <button type="submit">Search</button>
            </div>
            <fieldset className="date-range">
              <legend>Daily price period</legend>
              <label htmlFor="price-from-date">
                From
                <input
                  id="price-from-date"
                  type="date"
                  value={dateRange.fromDate}
                  max={dateRange.toDate || today}
                  required
                  onChange={(event) =>
                    setDateRange((current) => ({
                      ...current,
                      fromDate: event.target.value,
                    }))
                  }
                />
              </label>
              <label htmlFor="price-to-date">
                To
                <input
                  id="price-to-date"
                  type="date"
                  value={dateRange.toDate}
                  min={dateRange.fromDate}
                  max={today}
                  required
                  onChange={(event) =>
                    setDateRange((current) => ({
                      ...current,
                      toDate: event.target.value,
                    }))
                  }
                />
              </label>
            </fieldset>
            {dateRangeError && (
              <p className="date-range-error" role="alert">
                {dateRangeError}
              </p>
            )}
          </form>

          {recentStocks.length > 0 && (
            <div
              className="recent-stocks"
              aria-label="Recently searched stocks"
            >
              <span>Recent</span>
              <div>
                {recentStocks.map((stock) => (
                  <button
                    type="button"
                    key={`${stock.exchange}:${stock.symbol}`}
                    title={`${stock.symbol} / ${stock.exchange}`}
                    aria-label={`Open recent stock ${stock.name} (${stock.symbol})`}
                    onClick={() => selectStock(stock)}
                  >
                    {stock.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {stocksLoading ? (
            <div className="loading-state" role="status">
              Loading stocks...
            </div>
          ) : stocksError ? (
            <div className="error-state" role="alert">
              <p>{stocksError}</p>
              <button
                onClick={() => {
                  setStocksLoading(true)
                  setStocksError(null)
                  setStockReloadToken((value) => value + 1)
                }}
              >
                Retry
              </button>
            </div>
          ) : stocks.length === 0 ? (
            <div className="empty-state">No stocks match this search.</div>
          ) : (
            <div className="stock-list" role="listbox" aria-label="Stocks">
              {stocks.map((stock) => (
                <button
                  className={
                    stock.id === selectedStock?.id
                      ? 'stock-item selected'
                      : 'stock-item'
                  }
                  key={stock.id}
                  onClick={() => selectStock(stock)}
                  role="option"
                  aria-selected={stock.id === selectedStock?.id}
                >
                  <span>
                    <strong>{stock.symbol}</strong>
                    <small>{stock.name}</small>
                  </span>
                  <span className="exchange-tag">{stock.exchange}</span>
                </button>
              ))}
            </div>
          )}

          <div className="pagination-controls">
            <button
              disabled={!canGoBack}
              onClick={() => {
                setStocksLoading(true)
                setStocksError(null)
                setStockOffset((offset) =>
                  Math.max(0, offset - stockPagination.limit),
                )
              }}
            >
              Previous
            </button>
            <span>
              {stockPagination.total === 0
                ? '0'
                : `${stockPagination.offset + 1}-${Math.min(
                    stockPagination.offset + stockPagination.limit,
                    stockPagination.total,
                  )}`}
            </span>
            <button
              disabled={!canGoForward}
              onClick={() => {
                setStocksLoading(true)
                setStocksError(null)
                setStockOffset((offset) => offset + stockPagination.limit)
              }}
            >
              Next
            </button>
          </div>
        </aside>

        <section className="main-column">
          <section
            className="panel chart-panel"
            aria-labelledby="chart-heading"
          >
            {selectedStock ? (
              <>
                <div className="stock-summary">
                  <div>
                    <p className="section-kicker">
                      {selectedStock.exchange} / {selectedStock.symbol}
                    </p>
                    <h2 id="chart-heading">{selectedStock.name}</h2>
                  </div>
                  <div className="market-summary" aria-label="Latest price">
                    <span>Latest close</span>
                    <strong>
                      {latestPrice ? latestPrice.close.toFixed(2) : '--'}
                    </strong>
                    {priceChange !== null && (
                      <small
                        className={priceChange >= 0 ? 'positive' : 'negative'}
                      >
                        {priceChange >= 0 ? '+' : ''}
                        {priceChange.toFixed(2)}
                      </small>
                    )}
                  </div>
                </div>

                {detailLoading ? (
                  <div className="loading-state chart-loading" role="status">
                    {detailRequestMode === 'sync'
                      ? 'Synchronizing missing price history...'
                      : 'Loading cached price history and technical signals...'}
                  </div>
                ) : detailError ? (
                  <div className="error-state chart-error" role="alert">
                    <p>{detailError}</p>
                    <button
                      onClick={() => {
                        setDetailLoading(true)
                        setDetailError(null)
                        setDetailReloadToken((value) => value + 1)
                      }}
                    >
                      Retry
                    </button>
                  </div>
                ) : (
                  <>
                    {syncWarning && (
                      <div className="sync-warning" role="status">
                        {syncWarning}
                      </div>
                    )}
                    <KlineChart
                      key={`${selectedStock.exchange}:${selectedStock.symbol}`}
                      prices={prices}
                    />
                    <div className="chart-footer">
                      <span>
                        {prices.length} stored daily record
                        {prices.length === 1 ? '' : 's'}
                      </span>
                      <span>
                        Source: {latestPrice?.source ?? 'No price source'}
                      </span>
                      <span>Adjustment: source defined</span>
                      {syncMetadata && (
                        <span>
                          {syncMetadata.cache_hit
                            ? 'Requested period already cached'
                            : `Fetched ${syncMetadata.fetched_ranges.length} missing range${syncMetadata.fetched_ranges.length === 1 ? '' : 's'}; cached ${syncMetadata.prices_inserted} new record${syncMetadata.prices_inserted === 1 ? '' : 's'}`}
                        </span>
                      )}
                    </div>
                  </>
                )}
              </>
            ) : (
              <div className="empty-state chart-empty">
                Select a stock to inspect its daily price history.
              </div>
            )}
          </section>

          <section
            className="panel signals-panel"
            aria-labelledby="signals-heading"
          >
            <div className="panel-heading">
              <div>
                <p className="section-kicker">Deterministic findings</p>
                <h2 id="signals-heading">Technical signals</h2>
              </div>
              <span className="count-badge">{signals.length}</span>
            </div>

            {!selectedStock ? (
              <div className="empty-state">Select a stock to view signals.</div>
            ) : detailLoading ? (
              <div className="loading-state" role="status">
                Loading technical signals...
              </div>
            ) : detailError ? (
              <div className="empty-state">
                Signals are unavailable while stock details cannot be loaded.
              </div>
            ) : signals.length === 0 ? (
              <div className="empty-state">
                No technical signals are stored for this stock.
              </div>
            ) : (
              <div className="signal-list">
                {signals.map((signal) => (
                  <article className="signal-card" key={signal.id}>
                    <div className="signal-title">
                      <div>
                        <strong>{signal.signal.name}</strong>
                        <span>
                          {signal.signal.code} v{signal.signal.version}
                        </span>
                      </div>
                      <time dateTime={signal.signal_date}>
                        {signal.signal_date}
                      </time>
                    </div>
                    <p>{signal.explanation}</p>
                    <dl className="matched-values">
                      {Object.entries(signal.matched_values)
                        .slice(0, 4)
                        .map(([key, value]) => (
                          <div key={key}>
                            <dt>{humanize(key)}</dt>
                            <dd>
                              {typeof value === 'number'
                                ? formatNumber(value)
                                : String(value)}
                            </dd>
                          </div>
                        ))}
                    </dl>
                  </article>
                ))}
              </div>
            )}
          </section>
        </section>

        <aside className="panel runs-panel" aria-labelledby="runs-heading">
          <div className="panel-heading">
            <div>
              <p className="section-kicker">Execution history</p>
              <h2 id="runs-heading">Recent scanner runs</h2>
            </div>
          </div>

          {runsLoading ? (
            <div className="loading-state" role="status">
              Loading scanner runs...
            </div>
          ) : runsError ? (
            <div className="error-state" role="alert">
              <p>{runsError}</p>
              <button
                onClick={() => {
                  setRunsLoading(true)
                  setRunsError(null)
                  setRunsReloadToken((value) => value + 1)
                }}
              >
                Retry
              </button>
            </div>
          ) : scannerRuns.length === 0 ? (
            <div className="empty-state">No scanner runs are stored yet.</div>
          ) : (
            <div className="run-list">
              {scannerRuns.map((run) => (
                <article className="run-card" key={run.id}>
                  <div className="run-title">
                    <span className={`run-status ${run.status}`}>
                      {humanize(run.status)}
                    </span>
                    <time dateTime={run.started_at}>
                      {formatDateTime(run.started_at)}
                    </time>
                  </div>
                  <strong>{run.universe_name}</strong>
                  <span className="run-date">Market date {run.data_date}</span>
                  <dl className="run-metrics">
                    <div>
                      <dt>Processed</dt>
                      <dd>
                        {run.processed_stocks}/{run.total_stocks}
                      </dd>
                    </div>
                    <div>
                      <dt>Matched</dt>
                      <dd>{run.matched_stocks}</dd>
                    </div>
                    <div>
                      <dt>Warnings</dt>
                      <dd>{run.warning_count}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          )}
        </aside>
      </main>

      <footer>
        Technical signals describe deterministic historical conditions. They are
        not investment recommendations or trading instructions.
      </footer>
    </div>
  )
}

export default App
