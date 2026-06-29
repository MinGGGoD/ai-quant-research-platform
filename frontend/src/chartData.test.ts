import { describe, expect, it } from 'vitest'

import { aggregatePrices, withMovingAverages } from './chartData'
import type { DailyPrice } from './types'

function price(
  tradeDate: string,
  open: number,
  high: number,
  low: number,
  close: number,
  volume = 100,
): DailyPrice {
  return {
    trade_date: tradeDate,
    open,
    high,
    low,
    close,
    volume,
    amount: close * volume,
    source: 'synthetic_test',
  }
}

describe('chart data', () => {
  it('aggregates daily prices into calendar weeks', () => {
    const weekly = aggregatePrices(
      [
        price('2026-06-08', 10, 11, 9, 10.5, 100),
        price('2026-06-09', 10.5, 12, 10, 11.5, 200),
        price('2026-06-15', 11.5, 13, 11, 12.5, 300),
      ],
      '1W',
    )

    expect(weekly).toHaveLength(2)
    expect(weekly[0]).toMatchObject({
      interval_start: '2026-06-08',
      trade_date: '2026-06-09',
      open: 10,
      high: 12,
      low: 9,
      close: 11.5,
      volume: 300,
    })
    expect(weekly[1].interval_start).toBe('2026-06-15')
  })

  it('orders intraday prices by timestamp', () => {
    const bars = aggregatePrices(
      [
        {
          ...price('2026-06-15', 10.5, 11, 10, 10.8),
          timestamp: '2026-06-15T10:30:00',
        },
        {
          ...price('2026-06-15', 10, 10.6, 9.9, 10.5),
          timestamp: '2026-06-15T10:00:00',
        },
      ],
      '30m',
    )

    expect(bars.map((bar) => bar.interval_start)).toEqual([
      '2026-06-15T10:00:00',
      '2026-06-15T10:30:00',
    ])
  })


  it('aggregates daily prices into calendar months', () => {
    const monthly = aggregatePrices(
      [
        price('2026-05-29', 9, 10, 8, 9.5),
        price('2026-06-01', 10, 11, 9.5, 10.5),
        price('2026-06-30', 10.5, 12, 10, 11.5),
      ],
      '1M',
    )

    expect(monthly).toHaveLength(2)
    expect(monthly[1]).toMatchObject({
      interval_start: '2026-06-01',
      trade_date: '2026-06-30',
      open: 10,
      high: 12,
      low: 9.5,
      close: 11.5,
    })
  })

  it('calculates MA5 through MA60 without partial-window values', () => {
    const bars = aggregatePrices(
      Array.from({ length: 60 }, (_, index) => {
        const date = new Date('2026-01-01T00:00:00Z')
        date.setUTCDate(date.getUTCDate() + index)
        return price(
          date.toISOString().slice(0, 10),
          index + 1,
          index + 2,
          index,
          index + 1,
        )
      }),
      '1D',
    )
    const points = withMovingAverages(bars)

    expect(points[3].movingAverages[5]).toBeNull()
    expect(points[4].movingAverages[5]).toBe(3)
    expect(points[59].movingAverages[60]).toBe(30.5)
  })
})
