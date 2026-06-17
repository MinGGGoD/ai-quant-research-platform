import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import App from './App'

const stocks = [
  {
    id: 1,
    symbol: '600519',
    exchange: 'SSE',
    name: 'Synthetic Alpha',
    list_date: '2001-08-27',
    delist_date: null,
    status: 'active',
  },
  {
    id: 2,
    symbol: '000001',
    exchange: 'SZSE',
    name: 'Synthetic Beta',
    list_date: '1991-04-03',
    delist_date: null,
    status: 'active',
  },
]

const pricesBySymbol = {
  '600519': [
    {
      trade_date: '2026-06-11',
      open: 10,
      high: 10.5,
      low: 9.8,
      close: 10.2,
      volume: 1000,
      amount: 10200,
      source: 'synthetic_test',
    },
    {
      trade_date: '2026-06-12',
      open: 10.2,
      high: 11,
      low: 10.1,
      close: 10.9,
      volume: 2500,
      amount: 26750,
      source: 'synthetic_test',
    },
  ],
  '000001': [
    {
      trade_date: '2026-06-12',
      open: 20,
      high: 20.5,
      low: 19.5,
      close: 20.1,
      volume: 800,
      amount: 16080,
      source: 'synthetic_test',
    },
  ],
}

const signal = {
  id: 'signal-1',
  scanner_run_id: 'run-1',
  signal_date: '2026-06-12',
  signal: {
    code: 'volume_spike',
    version: 1,
    name: 'Volume Spike',
  },
  matched_values: {
    current_volume: 2500,
    volume_ratio: 2.5,
  },
  explanation: 'Technical volume signal detected for research inspection.',
}

const runSignal = {
  ...signal,
  stock: {
    id: 1,
    symbol: '600519',
    exchange: 'SSE',
    name: 'Synthetic Alpha',
  },
}

const scannerRun = {
  id: 'run-1',
  status: 'completed_with_warnings',
  data_date: '2026-06-12',
  universe_name: 'synthetic_universe',
  started_at: '2026-06-13T02:00:00Z',
  finished_at: '2026-06-13T02:01:00Z',
  total_stocks: 2,
  processed_stocks: 1,
  matched_stocks: 1,
  warning_count: 1,
  error_count: 0,
}

const scannerRunDetail = {
  id: scannerRun.id,
  status: scannerRun.status,
  data_date: scannerRun.data_date,
  universe_name: scannerRun.universe_name,
  parameters: {
    signals: [{ code: 'volume_spike', version: 1 }],
    universe: 'synthetic_universe',
  },
  started_at: scannerRun.started_at,
  finished_at: scannerRun.finished_at,
  summary: {
    total_stocks: scannerRun.total_stocks,
    processed_stocks: scannerRun.processed_stocks,
    matched_stocks: scannerRun.matched_stocks,
    warning_count: scannerRun.warning_count,
    error_count: scannerRun.error_count,
  },
  error_message: 'One stock had insufficient lookback history.',
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function expectedDefaultDateRange(): {
  fromDate: string
  toDate: string
} {
  const end = new Date()
  const start = new Date(end)
  start.setFullYear(start.getFullYear() - 2)
  const format = (value: Date) =>
    [
      value.getFullYear(),
      String(value.getMonth() + 1).padStart(2, '0'),
      String(value.getDate()).padStart(2, '0'),
    ].join('-')
  return { fromDate: format(start), toDate: format(end) }
}

function installSuccessfulFetch(syncStatus = 200): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input))

    if (url.pathname === '/api/v1/stocks') {
      return Promise.resolve(
        jsonResponse({
          items: stocks,
          pagination: { limit: 30, offset: 0, total: 2 },
        }),
      )
    }
    if (url.pathname === '/api/v1/scanner-runs') {
      return Promise.resolve(
        jsonResponse({
          items: [scannerRun],
          pagination: { limit: 8, offset: 0, total: 1 },
        }),
      )
    }
    if (url.pathname === '/api/v1/scanner-runs/run-1') {
      return Promise.resolve(jsonResponse(scannerRunDetail))
    }
    if (url.pathname === '/api/v1/signals') {
      return Promise.resolve(
        jsonResponse({
          items:
            url.searchParams.get('scanner_run_id') === 'run-1'
              ? [runSignal]
              : [],
          pagination: { limit: 200, offset: 0, total: 1 },
        }),
      )
    }
    if (url.pathname.endsWith('/prices/sync')) {
      if (syncStatus !== 200) {
        return Promise.resolve(
          jsonResponse(
            {
              error: {
                code: 'market_data_provider_unavailable',
                message: 'AShareHub price synchronization is not configured.',
                request_id: 'request-sync-unavailable',
              },
            },
            syncStatus,
          ),
        )
      }
      const symbol = url.pathname
        .split('/')
        .at(-3) as keyof typeof pricesBySymbol
      const body = JSON.parse(String(init?.body)) as {
        from_date: string
        to_date: string
      }
      return Promise.resolve(
        jsonResponse({
          stock: stocks.find((stock) => stock.symbol === symbol),
          price_adjustment: 'source_defined',
          items: pricesBySymbol[symbol],
          sync: {
            requested_range: body,
            effective_range: body,
            cache_hit: false,
            fetched_ranges: [body],
            prices_inserted: pricesBySymbol[symbol].length,
            prices_updated: 0,
          },
        }),
      )
    }
    if (url.pathname.endsWith('/prices')) {
      const symbol = url.pathname
        .split('/')
        .at(-2) as keyof typeof pricesBySymbol
      return Promise.resolve(
        jsonResponse({
          stock: stocks.find((stock) => stock.symbol === symbol),
          price_adjustment: 'source_defined',
          items: pricesBySymbol[symbol],
        }),
      )
    }
    if (url.pathname.endsWith('/signals')) {
      const symbol = url.pathname.split('/').at(-2)
      return Promise.resolve(
        jsonResponse({
          stock: stocks.find((stock) => stock.symbol === symbol),
          items: symbol === '600519' ? [signal] : [],
          pagination: {
            limit: 50,
            offset: 0,
            total: symbol === '600519' ? 1 : 0,
          },
        }),
      )
    }
    return Promise.reject(new Error(`Unexpected URL: ${url}`))
  })

  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('loads the dashboard and displays chart, signals, and scanner runs', async () => {
    installSuccessfulFetch()

    render(<App />)

    expect(screen.getByText('Loading stocks...')).toBeInTheDocument()
    expect(
      await screen.findByRole('heading', { name: 'Synthetic Alpha' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('img', {
        name: 'Daily K-line chart with 2 price records',
      }),
    ).toBeInTheDocument()
    expect(screen.getByText('MA5 --')).toBeInTheDocument()
    expect(screen.getByText(/Only 2 stored daily records/i)).toBeInTheDocument()
    expect(screen.getByText('Volume Spike')).toBeInTheDocument()
    expect(screen.getByText('synthetic_universe')).toBeInTheDocument()
    expect(
      screen.getByText(
        /not investment recommendations or trading instructions/i,
      ),
    ).toBeInTheDocument()
  })

  it('opens scanner-run detail and filters its matched signals', async () => {
    installSuccessfulFetch()

    render(<App />)

    await screen.findByRole('heading', { name: 'Synthetic Alpha' })
    fireEvent.click(
      await screen.findByRole('button', {
        name: 'Open scanner run synthetic_universe from 2026-06-12',
      }),
    )

    const detail = screen.getByRole('region', { name: 'Scanner run detail' })
    expect(
      await within(detail).findByText(
        'One stock had insufficient lookback history.',
      ),
    ).toBeInTheDocument()
    expect(within(detail).getByText('synthetic_universe')).toBeInTheDocument()
    expect(
      within(detail).getByText('600519 / SSE - Synthetic Alpha'),
    ).toBeInTheDocument()
    expect(within(detail).getByText(/"volume_spike"/)).toBeInTheDocument()
    expect(within(detail).getByText('1/1')).toBeInTheDocument()

    fireEvent.change(within(detail).getByLabelText('Filter run signals'), {
      target: { value: 'Beta' },
    })

    expect(
      within(detail).getByText('No run signals match this filter.'),
    ).toBeInTheDocument()
  })

  it('defaults the daily price period to the past two years', () => {
    installSuccessfulFetch()
    const expected = expectedDefaultDateRange()

    render(<App />)

    expect(screen.getByLabelText('From')).toHaveValue(expected.fromDate)
    expect(screen.getByLabelText('To')).toHaveValue(expected.toDate)
  })

  it('switches daily data into weekly and monthly chart levels', async () => {
    installSuccessfulFetch()
    render(<App />)

    await screen.findByRole('img', {
      name: 'Daily K-line chart with 2 price records',
    })
    fireEvent.click(screen.getByRole('button', { name: '1W' }))
    expect(
      screen.getByRole('img', {
        name: 'Weekly K-line chart with 1 price records',
      }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '1M' }))
    expect(
      screen.getByRole('img', {
        name: 'Monthly K-line chart with 1 price records',
      }),
    ).toBeInTheDocument()
  })

  it('loads a new chart and empty signal state when another stock is selected', async () => {
    installSuccessfulFetch()
    render(<App />)

    await screen.findByRole('heading', { name: 'Synthetic Alpha' })
    fireEvent.click(
      screen.getByRole('option', { name: /000001Synthetic BetaSZSE/i }),
    )

    expect(
      await screen.findByRole('heading', { name: 'Synthetic Beta' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('img', {
        name: 'Daily K-line chart with 1 price records',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText('No technical signals are stored for this stock.'),
    ).toBeInTheDocument()
  })

  it('falls back to cached prices when synchronization is unavailable', async () => {
    installSuccessfulFetch(503)
    render(<App />)

    await screen.findByRole('heading', { name: 'Synthetic Alpha' })
    fireEvent.click(
      screen.getByRole('option', { name: /000001Synthetic BetaSZSE/i }),
    )

    expect(
      await screen.findByRole('img', {
        name: 'Daily K-line chart with 1 price records',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Showing cached records instead/i),
    ).toBeInTheDocument()
  })

  it('submits a stock search through the API client', async () => {
    const fetchMock = installSuccessfulFetch()
    render(<App />)

    await screen.findByRole('heading', { name: 'Synthetic Alpha' })
    fireEvent.change(screen.getByLabelText('Search stocks'), {
      target: { value: '600519' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Search' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('query=600519'),
        expect.objectContaining({
          headers: { Accept: 'application/json' },
        }),
      )
    })

    const expected = expectedDefaultDateRange()
    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining(
          '/api/v1/stocks/600519/prices/sync?exchange=SSE',
        ),
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({
            from_date: expected.fromDate,
            to_date: expected.toDate,
          }),
        }),
      )
    })
  })

  it('keeps recently opened stocks as persistent shortcuts', async () => {
    installSuccessfulFetch()
    render(<App />)

    await screen.findByRole('heading', { name: 'Synthetic Alpha' })
    fireEvent.click(
      screen.getByRole('option', { name: /000001Synthetic BetaSZSE/i }),
    )

    const recentShortcut = await screen.findByRole('button', {
      name: 'Open recent stock Synthetic Beta (000001)',
    })
    expect(recentShortcut).toBeInTheDocument()

    cleanup()
    render(<App />)

    expect(
      screen.getByRole('button', {
        name: 'Open recent stock Synthetic Beta (000001)',
      }),
    ).toBeInTheDocument()
  })

  it('limits persisted recent stock shortcuts to six items', () => {
    window.localStorage.setItem(
      'ai-quant-recent-stocks',
      JSON.stringify(
        Array.from({ length: 7 }, (_, index) => ({
          id: index + 10,
          symbol: `00000${index}`,
          exchange: 'SZSE',
          name: `Recent ${index}`,
          list_date: null,
          delist_date: null,
          status: 'active',
        })),
      ),
    )
    installSuccessfulFetch()

    render(<App />)

    const recentStocks = screen.getByLabelText('Recently searched stocks')
    expect(within(recentStocks).getAllByRole('button')).toHaveLength(6)
  })

  it('shows structured backend errors without exposing framework details', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = new URL(String(input))
        if (url.pathname === '/api/v1/stocks') {
          return Promise.resolve(
            jsonResponse(
              {
                error: {
                  code: 'database_unavailable',
                  message: 'The database is not available.',
                  request_id: 'request-123',
                },
              },
              503,
            ),
          )
        }
        return Promise.resolve(
          jsonResponse({
            items: [],
            pagination: { limit: 8, offset: 0, total: 0 },
          }),
        )
      }),
    )

    render(<App />)

    expect(
      await screen.findByText(
        'The database is not available. Request ID: request-123',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})
