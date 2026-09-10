import type { FormEvent } from 'react'

import type { Pagination, Stock } from '../types'

export interface SelectedDateRange {
  fromDate: string
  toDate: string
}

interface StockPanelProps {
  stocks: Stock[]
  pagination: Pagination
  selectedStock: Stock | null
  recentStocks: Stock[]
  searchInput: string
  dateRange: SelectedDateRange
  today: string
  dateRangeError: string | null
  loading: boolean
  error: string | null
  onSearchInputChange: (value: string) => void
  onDateRangeChange: (value: SelectedDateRange) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  onRetry: () => void
  onSelectStock: (stock: Stock) => void
  onOpenRecentStock: (stock: Stock) => void
  onPreviousPage: () => void
  onNextPage: () => void
}

export default function StockPanel({
  stocks,
  pagination,
  selectedStock,
  recentStocks,
  searchInput,
  dateRange,
  today,
  dateRangeError,
  loading,
  error,
  onSearchInputChange,
  onDateRangeChange,
  onSubmit,
  onRetry,
  onSelectStock,
  onOpenRecentStock,
  onPreviousPage,
  onNextPage,
}: StockPanelProps) {
  const canGoBack = pagination.offset > 0
  const canGoForward = pagination.offset + pagination.limit < pagination.total

  return (
    <aside className="panel stock-panel" aria-labelledby="stocks-heading">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Market universe</p>
          <h2 id="stocks-heading">Stocks</h2>
        </div>
        <span className="count-badge">{pagination.total}</span>
      </div>

      <form className="stock-search" onSubmit={onSubmit}>
        <label htmlFor="stock-query">Search stocks</label>
        <div className="search-row">
          <input
            id="stock-query"
            type="search"
            value={searchInput}
            onChange={(event) => onSearchInputChange(event.target.value)}
            placeholder="Code or name"
          />
          <button type="submit">Search</button>
        </div>
        <fieldset className="date-range">
          <legend>Price period</legend>
          <label htmlFor="price-from-date">
            From
            <input
              id="price-from-date"
              type="date"
              value={dateRange.fromDate}
              max={dateRange.toDate || today}
              required
              onChange={(event) =>
                onDateRangeChange({
                  ...dateRange,
                  fromDate: event.target.value,
                })
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
                onDateRangeChange({
                  ...dateRange,
                  toDate: event.target.value,
                })
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
        <div className="recent-stocks" aria-label="Recently searched stocks">
          <span>Recent</span>
          <div>
            {recentStocks.map((stock) => (
              <button
                type="button"
                key={`${stock.exchange}:${stock.symbol}`}
                title={`${stock.symbol} / ${stock.exchange}`}
                aria-label={`Open recent stock ${stock.name} (${stock.symbol})`}
                onClick={() => onOpenRecentStock(stock)}
              >
                {stock.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-state" role="status">
          Loading stocks...
        </div>
      ) : error ? (
        <div className="error-state" role="alert">
          <p>{error}</p>
          <button onClick={onRetry}>Retry</button>
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
              onClick={() => onSelectStock(stock)}
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
        <button disabled={!canGoBack} onClick={onPreviousPage}>
          Previous
        </button>
        <span>
          {pagination.total === 0
            ? '0'
            : `${pagination.offset + 1}-${Math.min(
                pagination.offset + pagination.limit,
                pagination.total,
              )}`}
        </span>
        <button disabled={!canGoForward} onClick={onNextPage}>
          Next
        </button>
      </div>
    </aside>
  )
}
