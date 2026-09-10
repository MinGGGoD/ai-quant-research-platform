'use client'

import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'

import {
  getScannerRunDetail,
  getScannerRuns,
  getSignalsForScannerRun,
  getStockPrices,
  getStockSignals,
  getStocks,
  syncStockPrices,
} from './api'
import type { ChartInterval } from './chartData'
import ScannerRunDetailPanel from './components/ScannerRunDetailPanel'
import ScannerRunsPanel from './components/ScannerRunsPanel'
import StockPanel from './components/StockPanel'
import type { SelectedDateRange } from './components/StockPanel'
import StockResearchPanel from './components/StockResearchPanel'
import { errorMessage } from './formatters'
import type {
  DailyPrice,
  Pagination,
  PriceFrequency,
  ScannerRun,
  ScannerRunDetail,
  Stock,
  StockPriceSyncMetadata,
  StockPriceSyncResponse,
  StockPricesResponse,
  TechnicalSignal,
} from './types'

const EMPTY_PAGINATION: Pagination = { limit: 30, offset: 0, total: 0 }
const RECENT_STOCKS_KEY = 'ai-quant-recent-stocks'
const RECENT_STOCK_LIMIT = 6

type DetailRequestMode = 'cache' | 'sync'

export interface StockRouteSelection {
  symbol: string
  exchange: Stock['exchange']
}

interface AppProps {
  initialStock?: StockRouteSelection
  initialScannerRunId?: string
}

function frequencyForChartInterval(interval: ChartInterval): PriceFrequency {
  return interval === '30m' || interval === '60m' ? interval : 'daily'
}

function utcIsoDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function defaultDateRange(): SelectedDateRange {
  const end = new Date()
  const start = new Date(end)
  start.setUTCFullYear(start.getUTCFullYear() - 2)
  return {
    fromDate: utcIsoDate(start),
    toDate: utcIsoDate(end),
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

function hasSyncMetadata(
  response: StockPricesResponse | StockPriceSyncResponse,
): response is StockPriceSyncResponse {
  return 'sync' in response
}

function stockPath(stock: StockRouteSelection): string {
  return `/stocks/${stock.exchange}/${encodeURIComponent(stock.symbol)}`
}

export default function App({ initialStock, initialScannerRunId }: AppProps) {
  const router = useRouter()
  const pendingRouteStock = useRef<StockRouteSelection | null>(
    initialStock ?? null,
  )
  const [stocks, setStocks] = useState<Stock[]>([])
  const [stockPagination, setStockPagination] =
    useState<Pagination>(EMPTY_PAGINATION)
  const [selectedStock, setSelectedStock] = useState<Stock | null>(null)
  const [prices, setPrices] = useState<DailyPrice[]>([])
  const [chartInterval, setChartInterval] = useState<ChartInterval>('1D')
  const [priceAdjustment, setPriceAdjustment] = useState('source_defined')
  const [signals, setSignals] = useState<TechnicalSignal[]>([])
  const [scannerRuns, setScannerRuns] = useState<ScannerRun[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string | null>(
    initialScannerRunId ?? null,
  )
  const [selectedRunDetail, setSelectedRunDetail] =
    useState<ScannerRunDetail | null>(null)
  const [selectedRunSignals, setSelectedRunSignals] = useState<
    TechnicalSignal[]
  >([])
  const [syncMetadata, setSyncMetadata] =
    useState<StockPriceSyncMetadata | null>(null)
  const [recentStocks, setRecentStocks] = useState<Stock[]>([])
  const [searchInput, setSearchInput] = useState(initialStock?.symbol ?? '')
  const [activeQuery, setActiveQuery] = useState(initialStock?.symbol ?? '')
  const [stockOffset, setStockOffset] = useState(0)
  const [stocksLoading, setStocksLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [runsLoading, setRunsLoading] = useState(true)
  const [runDetailLoading, setRunDetailLoading] = useState(
    Boolean(initialScannerRunId),
  )
  const [stocksError, setStocksError] = useState<string | null>(null)
  const [detailError, setDetailError] = useState<string | null>(null)
  const [syncWarning, setSyncWarning] = useState<string | null>(null)
  const [runsError, setRunsError] = useState<string | null>(null)
  const [runDetailError, setRunDetailError] = useState<string | null>(null)
  const [dateRangeError, setDateRangeError] = useState<string | null>(null)
  const [runSignalQuery, setRunSignalQuery] = useState('')
  const [runSignalCode, setRunSignalCode] = useState('')
  const [dateRange, setDateRange] =
    useState<SelectedDateRange>(defaultDateRange)
  const [appliedDateRange, setAppliedDateRange] =
    useState<SelectedDateRange>(dateRange)
  const [detailRequestMode, setDetailRequestMode] =
    useState<DetailRequestMode>('cache')
  const [stockReloadToken, setStockReloadToken] = useState(0)
  const [detailReloadToken, setDetailReloadToken] = useState(0)
  const [runsReloadToken, setRunsReloadToken] = useState(0)
  const [runDetailReloadToken, setRunDetailReloadToken] = useState(0)
  const pendingSearchSync = useRef(false)
  const today = utcIsoDate(new Date())
  const priceFrequency = frequencyForChartInterval(chartInterval)

  useEffect(() => {
    // Browser storage is loaded after hydration so the server and first client render match.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setRecentStocks(loadRecentStocks())
  }, [])

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
        setPriceAdjustment('source_defined')
        setSignals([])
      }
    },
    [rememberStock],
  )

  const openStock = useCallback(
    (stock: Stock) => {
      selectStock(stock)
      router.push(stockPath(stock))
    },
    [router, selectStock],
  )

  const changeChartInterval = useCallback(
    (nextInterval: ChartInterval) => {
      const currentFrequency = frequencyForChartInterval(chartInterval)
      const nextFrequency = frequencyForChartInterval(nextInterval)
      setChartInterval(nextInterval)
      if (selectedStock && nextFrequency !== currentFrequency) {
        setDetailLoading(true)
        setDetailError(null)
        setSyncWarning(null)
        setSyncMetadata(null)
        setDetailReloadToken((value) => value + 1)
      }
    },
    [chartInterval, selectedStock],
  )

  const selectScannerRun = useCallback(
    (runId: string) => {
      setSelectedRunId(runId)
      setSelectedRunDetail(null)
      setSelectedRunSignals([])
      setRunDetailError(null)
      setRunDetailLoading(true)
      setRunSignalQuery('')
      setRunSignalCode('')
      setRunDetailReloadToken((value) => value + 1)
      router.push(`/scanner-runs/${encodeURIComponent(runId)}`)
    },
    [router],
  )

  const closeScannerRun = useCallback(() => {
    setSelectedRunId(null)
    setSelectedRunDetail(null)
    setSelectedRunSignals([])
    setRunDetailError(null)
    setRunDetailLoading(false)
    setRunSignalQuery('')
    setRunSignalCode('')
    router.push('/')
  }, [router])

  useEffect(() => {
    const controller = new AbortController()

    getStocks(activeQuery, stockOffset, controller.signal)
      .then((response) => {
        setStocks(response.items)
        setStockPagination(response.pagination)
        const routeStock = pendingRouteStock.current
        const nextStock = routeStock
          ? (response.items.find(
              (stock) =>
                stock.symbol === routeStock.symbol &&
                stock.exchange === routeStock.exchange,
            ) ?? null)
          : (response.items[0] ?? null)
        pendingRouteStock.current = null
        const shouldSync = pendingSearchSync.current && stockOffset === 0
        selectStock(
          nextStock,
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
    if (!selectedRunId) {
      return
    }

    const controller = new AbortController()

    Promise.all([
      getScannerRunDetail(selectedRunId, controller.signal),
      getSignalsForScannerRun(selectedRunId, controller.signal),
    ])
      .then(([runDetail, signalResponse]) => {
        setSelectedRunDetail(runDetail)
        setSelectedRunSignals(signalResponse.items)
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        setSelectedRunDetail(null)
        setSelectedRunSignals([])
        setRunDetailError(errorMessage(error))
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setRunDetailLoading(false)
        }
      })

    return () => controller.abort()
  }, [runDetailReloadToken, selectedRunId])

  useEffect(() => {
    if (!selectedStock) {
      return
    }

    const controller = new AbortController()
    const shouldSynchronizeDaily =
      priceFrequency === 'daily' && detailRequestMode === 'sync'

    Promise.all([
      shouldSynchronizeDaily
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
            priceFrequency,
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
        setPriceAdjustment(priceResponse.price_adjustment)
        setSignals(signalResponse.items)
        setSyncMetadata(
          hasSyncMetadata(priceResponse) ? priceResponse.sync : null,
        )
      })
      .catch(async (error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') {
          return
        }
        if (shouldSynchronizeDaily) {
          try {
            const [cachedPriceResponse, signalResponse] = await Promise.all([
              getStockPrices(
                selectedStock.symbol,
                selectedStock.exchange,
                appliedDateRange.fromDate,
                appliedDateRange.toDate,
                'daily',
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
            setPriceAdjustment(cachedPriceResponse.price_adjustment)
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
  }, [
    appliedDateRange,
    detailReloadToken,
    detailRequestMode,
    priceFrequency,
    selectedStock,
  ])

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

  const openRecentStock = useCallback(
    (stock: Stock) => {
      setSearchInput(stock.symbol)
      openStock(stock)
    },
    [openStock],
  )

  const runSignalCodes = useMemo(
    () =>
      Array.from(
        new Set(selectedRunSignals.map((signal) => signal.signal.code)),
      ).sort(),
    [selectedRunSignals],
  )

  const filteredRunSignals = useMemo(() => {
    const query = runSignalQuery.trim().toLowerCase()
    return selectedRunSignals.filter((signal) => {
      const matchesCode = !runSignalCode || signal.signal.code === runSignalCode
      if (!matchesCode) {
        return false
      }
      if (!query) {
        return true
      }
      const stockText = signal.stock
        ? `${signal.stock.symbol} ${signal.stock.exchange} ${signal.stock.name}`
        : ''
      return [
        stockText,
        signal.signal.name,
        signal.signal.code,
        signal.explanation,
        signal.signal_date,
      ]
        .join(' ')
        .toLowerCase()
        .includes(query)
    })
  }, [runSignalCode, runSignalQuery, selectedRunSignals])

  return (
    <main className="dashboard">
      <StockPanel
        stocks={stocks}
        pagination={stockPagination}
        selectedStock={selectedStock}
        recentStocks={recentStocks}
        searchInput={searchInput}
        dateRange={dateRange}
        today={today}
        dateRangeError={dateRangeError}
        loading={stocksLoading}
        error={stocksError}
        onSearchInputChange={setSearchInput}
        onDateRangeChange={setDateRange}
        onSubmit={submitSearch}
        onRetry={() => {
          setStocksLoading(true)
          setStocksError(null)
          setStockReloadToken((value) => value + 1)
        }}
        onSelectStock={openStock}
        onOpenRecentStock={openRecentStock}
        onPreviousPage={() => {
          setStocksLoading(true)
          setStocksError(null)
          setStockOffset((offset) =>
            Math.max(0, offset - stockPagination.limit),
          )
        }}
        onNextPage={() => {
          setStocksLoading(true)
          setStocksError(null)
          setStockOffset((offset) => offset + stockPagination.limit)
        }}
      />

      <section className="main-column">
        <StockResearchPanel
          selectedStock={selectedStock}
          prices={prices}
          priceAdjustment={priceAdjustment}
          chartInterval={chartInterval}
          priceFrequency={priceFrequency}
          signals={signals}
          syncMetadata={syncMetadata}
          syncWarning={syncWarning}
          loading={detailLoading}
          error={detailError}
          requestMode={detailRequestMode}
          onIntervalChange={changeChartInterval}
          onRetry={() => {
            setDetailLoading(true)
            setDetailError(null)
            setDetailReloadToken((value) => value + 1)
          }}
        />
        <ScannerRunDetailPanel
          selectedRunId={selectedRunId}
          detail={selectedRunDetail}
          signals={selectedRunSignals}
          filteredSignals={filteredRunSignals}
          signalCodes={runSignalCodes}
          signalQuery={runSignalQuery}
          signalCode={runSignalCode}
          loading={runDetailLoading}
          error={runDetailError}
          onClose={closeScannerRun}
          onRetry={() => {
            setRunDetailLoading(true)
            setRunDetailError(null)
            setRunDetailReloadToken((value) => value + 1)
          }}
          onSignalQueryChange={setRunSignalQuery}
          onSignalCodeChange={setRunSignalCode}
        />
      </section>

      <ScannerRunsPanel
        runs={scannerRuns}
        selectedRunId={selectedRunId}
        loading={runsLoading}
        error={runsError}
        onRetry={() => {
          setRunsLoading(true)
          setRunsError(null)
          setRunsReloadToken((value) => value + 1)
        }}
        onSelectRun={selectScannerRun}
      />
    </main>
  )
}
