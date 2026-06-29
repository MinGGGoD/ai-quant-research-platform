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
          frequency: 'daily',
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
      const frequency = url.searchParams.get('frequency') ?? 'daily'
      const items =
        frequency === '30m' || frequency === '60m'
          ? pricesBySymbol[symbol].map((price, index) => ({
              ...price,
              timestamp: `${price.trade_date}T${String(10 + index).padStart(
                2,
                '0',
              )}:00:00`,
            }))
          : pricesBySymbol[symbol]
      return Promise.resolve(
        jsonResponse({
          stock: stocks.find((stock) => stock.symbol === symbol),
          frequency,
          price_adjustment: 'source_defined',
          items,
        }),
      )
    }
    if (url.pathname.endsWith('/chan-analysis')) {
      const symbol = url.pathname.split('/').at(-2) as keyof typeof pricesBySymbol
      const stock = stocks.find((item) => item.symbol === symbol)
      return Promise.resolve(
        jsonResponse({
          stock,
          frequency: url.searchParams.get('frequency') ?? 'daily',
          algorithm: {
            code: 'vespa314_chan_py',
            version: 1,
            parameters: {},
          },
          price_bar_count: pricesBySymbol[symbol].length,
          fractals: [],
          strokes: [],
          segments: [],
          centers: [],
          observations:
            symbol === '600519'
              ? [
                  {
                    index: 1,
                    bar_time: '2026-06-12',
                    trade_date: '2026-06-12',
                    timestamp: null,
                    kind: 'B2',
                    side: 'buy',
                    label: 'B2 observation',
                    price: 10.1,
                    status: 'confirmed',
                    explanation: 'Synthetic buy point.',
                  },
                  {
                    index: 0,
                    bar_time: '2026-06-11',
                    trade_date: '2026-06-11',
                    timestamp: null,
                    kind: 'S1',
                    side: 'sell',
                    label: 'S1 observation',
                    price: 10.5,
                    status: 'confirmed',
                    explanation: 'Synthetic sell point.',
                  },
                ]
              : [],
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
  it('loads the dashboard and displays chart, signals, and Chan buy/sell points', async () => {
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
    expect(
      screen.getByRole('heading', { name: 'Buy/sell points' }),
    ).toBeInTheDocument()
    expect(screen.getAllByText('B2').length).toBeGreaterThan(0)
    expect(screen.getByText(/Second-class buy point/i)).toBeInTheDocument()
    expect(screen.queryByText('Execution history')).not.toBeInTheDocument()
    expect(screen.queryByText('Execution detail')).not.toBeInTheDocument()
    expect(
      screen.getByText(
        /not investment recommendations or trading instructions/i,
      ),
    ).toBeInTheDocument()
  })

  it('focuses the chart when a Chan buy/sell point is selected', async () => {
    installSuccessfulFetch()

    render(<App />)

    await screen.findByRole('img', {
      name: 'Daily K-line chart with 2 price records',
    })
    fireEvent.click(
      screen.getByRole('button', {
        name: 'Focus B2 buy point at 2026-06-12',
      }),
    )

    expect(
      screen.getByRole('button', {
        name: 'Focus B2 buy point at 2026-06-12',
      }),
    ).toHaveAttribute('aria-pressed', 'true')
    expect(
      screen.getByRole('img', {
        name: 'Daily K-line chart with 2 price records',
      }),
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

  it('requests cached intraday prices when switching to 30-minute bars', async () => {
    const fetchMock = installSuccessfulFetch()
    render(<App />)

    await screen.findByRole('img', {
      name: 'Daily K-line chart with 2 price records',
    })
    fireEvent.click(screen.getByRole('button', { name: '30m' }))

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('frequency=30m'),
        expect.objectContaining({
          headers: { Accept: 'application/json' },
        }),
      )
    })
    expect(
      await screen.findByRole('img', {
        name: '30-minute K-line chart with 2 price records',
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
    fireEvent.click(recentShortcut)
    expect(screen.getByLabelText('Search stocks')).toHaveValue('000001')

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
