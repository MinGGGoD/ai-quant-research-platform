import { createRef } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ChanAnalysis, DailyPrice } from '../types'
import KlineChart from './KlineChart'
import type { KlineChartHandle } from './KlineChart'

function makePrices(count: number): DailyPrice[] {
  return Array.from({ length: count }, (_, index) => {
    const date = new Date('2026-01-01T00:00:00Z')
    date.setUTCDate(date.getUTCDate() + index)
    const open = 10 + index * 0.1
    const close = open + (index % 2 === 0 ? 0.2 : -0.1)
    return {
      trade_date: date.toISOString().slice(0, 10),
      open,
      high: Math.max(open, close) + 0.3,
      low: Math.min(open, close) - 0.3,
      close,
      volume: 1000 + index * 10,
      amount: close * (1000 + index * 10),
      source: 'synthetic_test',
    }
  })
}

function makeChanAnalysis(): ChanAnalysis {
  return {
    stock: {
      id: 1,
      symbol: '600519',
      exchange: 'SSE',
      name: 'Synthetic Research Stock',
    },
    frequency: 'daily',
    algorithm: {
      code: 'vespa314_chan_py',
      version: 1,
      parameters: {},
    },
    price_bar_count: 6,
    fractals: [
      {
        index: 1,
        bar_time: '2026-01-02',
        trade_date: '2026-01-02',
        kind: 'top',
        price: 10.6,
        status: 'confirmed',
      },
      {
        index: 3,
        bar_time: '2026-01-04',
        trade_date: '2026-01-04',
        kind: 'bottom',
        price: 9.7,
        status: 'confirmed',
      },
    ],
    strokes: [
      {
        start_index: 1,
        end_index: 3,
        start_time: '2026-01-02',
        end_time: '2026-01-04',
        direction: 'down',
        price_low: 9.7,
        price_high: 10.6,
        status: 'confirmed',
      },
    ],
    segments: [],
    centers: [
      {
        start_index: 1,
        end_index: 5,
        start_time: '2026-01-02',
        end_time: '2026-01-06',
        price_low: 9.8,
        price_high: 10.5,
        status: 'confirmed',
        stroke_indexes: [0, 1, 2],
      },
    ],
    observations: [
      {
        index: 1,
        bar_time: '2026-01-02',
        trade_date: '2026-01-02',
        kind: 'S1',
        side: 'sell',
        label: 'S1 observation',
        price: 10.6,
        status: 'confirmed',
        explanation: 'Synthetic top fractal observation.',
      },
      {
        index: 3,
        bar_time: '2026-01-04',
        trade_date: '2026-01-04',
        kind: 'B2',
        side: 'buy',
        label: 'B2 observation',
        price: 9.7,
        status: 'confirmed',
        explanation: 'Synthetic bottom fractal observation.',
      },
    ],
  }
}

function renderChart(
  prices: DailyPrice[],
  interval: '30m' | '1D' = '1D',
  chanAnalysis?: ChanAnalysis,
) {
  return render(
    <KlineChart
      prices={prices}
      chanAnalysis={chanAnalysis}
      interval={interval}
      onIntervalChange={vi.fn()}
    />,
  )
}

afterEach(cleanup)

describe('KlineChart', () => {
  it('zooms into a smaller bar window and resets to the full history', () => {
    renderChart(makePrices(40))

    expect(
      screen.getByRole('img', {
        name: 'Daily K-line chart with 40 price records',
      }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }))

    expect(
      screen.getByRole('img', {
        name: 'Daily K-line chart showing 32 of 40 price records',
      }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Zoom out' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: 'Reset' }))

    expect(
      screen.getByRole('img', {
        name: 'Daily K-line chart with 40 price records',
      }),
    ).toBeInTheDocument()
  })

  it('prevents page scrolling while zooming with the mouse wheel', () => {
    renderChart(makePrices(40))

    const chart = screen.getByRole('img', {
      name: 'Daily K-line chart with 40 price records',
    })
    const wheelEvent = new WheelEvent('wheel', {
      bubbles: true,
      cancelable: true,
      clientX: 520,
      deltaY: -100,
    })

    fireEvent(chart, wheelEvent)

    expect(wheelEvent.defaultPrevented).toBe(true)
    expect(
      screen.getByRole('img', {
        name: 'Daily K-line chart showing 32 of 40 price records',
      }),
    ).toBeInTheDocument()
  })

  it('clamps a stale crosshair when the visible data window changes', () => {
    const onIntervalChange = vi.fn()
    const { rerender } = render(
      <KlineChart
        prices={makePrices(40)}
        interval="1D"
        onIntervalChange={onIntervalChange}
      />,
    )
    const chart = screen.getByRole('img', {
      name: 'Daily K-line chart with 40 price records',
    })
    Object.defineProperty(chart, 'getBoundingClientRect', {
      value: () => ({
        bottom: 520,
        height: 520,
        left: 0,
        right: 1040,
        top: 0,
        width: 1040,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      }),
    })

    fireEvent.mouseMove(chart, { clientX: 1030, clientY: 120 })
    rerender(
      <KlineChart
        prices={makePrices(20)}
        interval="1D"
        onIntervalChange={onIntervalChange}
      />,
    )

    expect(
      screen.getByRole('img', {
        name: 'Daily K-line chart with 20 price records',
      }),
    ).toBeInTheDocument()
  })

  it('shows intraday timestamps for minute bars', () => {
    renderChart(
      [
        {
          trade_date: '2026-06-12',
          timestamp: '2026-06-12T10:00:00',
          open: 10,
          high: 11,
          low: 9.8,
          close: 10.5,
          volume: 1000,
          amount: 10500,
          source: 'synthetic_test',
        },
      ],
      '30m',
    )

    expect(screen.getAllByText('2026-06-12 10:00').length).toBeGreaterThan(0)
    expect(
      screen.getByRole('img', {
        name: '30-minute K-line chart with 1 price records',
      }),
    ).toBeInTheDocument()
  })

  it('renders Chan theory layer controls and observation labels', () => {
    renderChart(makePrices(6), '1D', makeChanAnalysis())

    expect(
      screen.getByRole('group', { name: 'Chan theory layers' }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Centers')).toBeChecked()
    expect(screen.queryByLabelText('Fractals')).not.toBeInTheDocument()
    expect(screen.getByText('B2')).toBeInTheDocument()
    expect(screen.getByText('S1')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('B/S'))

    expect(screen.getByLabelText('B/S')).not.toBeChecked()
  })

  it('zooms to a focused Chan observation', async () => {
    const prices = makePrices(80)
    const targetDate = prices[50].trade_date
    const analysis: ChanAnalysis = {
      ...makeChanAnalysis(),
      price_bar_count: prices.length,
      observations: [
        {
          index: 50,
          bar_time: targetDate,
          trade_date: targetDate,
          kind: 'B2',
          side: 'buy',
          label: 'B2 observation',
          price: prices[50].low,
          status: 'confirmed',
          explanation: 'Synthetic focused observation.',
        },
      ],
    }

    const chartRef = createRef<KlineChartHandle>()
    render(
      <KlineChart
        ref={chartRef}
        prices={prices}
        chanAnalysis={analysis}
        interval="1D"
        onIntervalChange={vi.fn()}
      />,
    )
    act(() => {
      chartRef.current?.focusObservation(targetDate)
    })

    expect(
      await screen.findByRole('img', {
        name: 'Daily K-line chart showing 40 of 80 price records',
      }),
    ).toBeInTheDocument()
  })
})
