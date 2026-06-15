import type { DailyPrice } from './types'

export type ChartInterval = '1D' | '1W' | '1M'

export const MOVING_AVERAGE_PERIODS = [5, 10, 20, 30, 60] as const

export type MovingAveragePeriod = (typeof MOVING_AVERAGE_PERIODS)[number]

export interface ChartBar extends DailyPrice {
  interval_start: string
}

export type MovingAverageValues = Record<MovingAveragePeriod, number | null>

export interface ChartPoint {
  bar: ChartBar
  movingAverages: MovingAverageValues
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00Z`)
}

function formatDate(value: Date): string {
  return value.toISOString().slice(0, 10)
}

function intervalStart(tradeDate: string, interval: ChartInterval): string {
  if (interval === '1D') {
    return tradeDate
  }
  if (interval === '1M') {
    return `${tradeDate.slice(0, 7)}-01`
  }

  const date = parseDate(tradeDate)
  const day = date.getUTCDay()
  const daysSinceMonday = day === 0 ? 6 : day - 1
  date.setUTCDate(date.getUTCDate() - daysSinceMonday)
  return formatDate(date)
}

function aggregateGroup(group: DailyPrice[], start: string): ChartBar {
  const first = group[0]
  const last = group.at(-1) ?? first
  const amounts = group
    .map((price) => price.amount)
    .filter((amount): amount is number => amount !== null)

  return {
    trade_date: last.trade_date,
    interval_start: start,
    open: first.open,
    high: Math.max(...group.map((price) => price.high)),
    low: Math.min(...group.map((price) => price.low)),
    close: last.close,
    volume: group.reduce((total, price) => total + price.volume, 0),
    amount:
      amounts.length === 0
        ? null
        : amounts.reduce((total, amount) => total + amount, 0),
    source: Array.from(new Set(group.map((price) => price.source))).join(', '),
  }
}

export function aggregatePrices(
  prices: DailyPrice[],
  interval: ChartInterval,
): ChartBar[] {
  const ordered = [...prices].sort((left, right) =>
    left.trade_date.localeCompare(right.trade_date),
  )
  if (interval === '1D') {
    return ordered.map((price) => ({
      ...price,
      interval_start: price.trade_date,
    }))
  }

  const groups = new Map<string, DailyPrice[]>()
  for (const price of ordered) {
    const start = intervalStart(price.trade_date, interval)
    const group = groups.get(start)
    if (group) {
      group.push(price)
    } else {
      groups.set(start, [price])
    }
  }

  return Array.from(groups, ([start, group]) => aggregateGroup(group, start))
}

export function withMovingAverages(bars: ChartBar[]): ChartPoint[] {
  const sums = new Map<MovingAveragePeriod, number>(
    MOVING_AVERAGE_PERIODS.map((period) => [period, 0]),
  )

  return bars.map((bar, index) => {
    const values = {} as MovingAverageValues
    for (const period of MOVING_AVERAGE_PERIODS) {
      const previousSum = sums.get(period) ?? 0
      const removedClose = index >= period ? bars[index - period].close : 0
      const sum = previousSum + bar.close - removedClose
      sums.set(period, sum)
      values[period] = index + 1 >= period ? sum / period : null
    }
    return { bar, movingAverages: values }
  })
}
