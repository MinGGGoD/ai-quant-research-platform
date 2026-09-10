import type { Metadata } from 'next'
import { notFound } from 'next/navigation'

import App from '../../../../../App'
import type { StockRouteSelection } from '../../../../../App'

interface StockPageProps {
  params: Promise<{
    exchange: string
    symbol: string
  }>
}

function isExchange(value: string): value is StockRouteSelection['exchange'] {
  return value === 'SSE' || value === 'SZSE' || value === 'BSE'
}

export async function generateMetadata({
  params,
}: StockPageProps): Promise<Metadata> {
  const { exchange, symbol } = await params
  return { title: `${symbol} / ${exchange}` }
}

export default async function StockPage({ params }: StockPageProps) {
  const { exchange, symbol } = await params
  if (!isExchange(exchange) || !symbol.trim()) {
    notFound()
  }

  const initialStock = { exchange, symbol }
  return (
    <App
      key={`${initialStock.exchange}:${initialStock.symbol}`}
      initialStock={initialStock}
    />
  )
}
