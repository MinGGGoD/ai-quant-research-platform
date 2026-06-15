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

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function installSuccessfulFetch(): ReturnType<typeof vi.fn> {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
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
