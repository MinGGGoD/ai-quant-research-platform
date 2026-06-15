import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DailyPrice } from '../types'
import KlineChart from './KlineChart'

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

afterEach(cleanup)

describe('KlineChart', () => {
  it('zooms into a smaller bar window and resets to the full history', () => {
    render(<KlineChart prices={makePrices(40)} />)

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
    render(<KlineChart prices={makePrices(40)} />)

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
})
