import type { ChartInterval } from '../chartData'
import { formatNumber, humanize } from '../formatters'
import type {
  DailyPrice,
  PriceFrequency,
  Stock,
  StockPriceSyncMetadata,
  TechnicalSignal,
} from '../types'
import KlineChart from './KlineChart'

type DetailRequestMode = 'cache' | 'sync'

interface StockResearchPanelProps {
  selectedStock: Stock | null
  prices: DailyPrice[]
  priceAdjustment: string
  chartInterval: ChartInterval
  priceFrequency: PriceFrequency
  signals: TechnicalSignal[]
  syncMetadata: StockPriceSyncMetadata | null
  syncWarning: string | null
  loading: boolean
  error: string | null
  requestMode: DetailRequestMode
  onIntervalChange: (interval: ChartInterval) => void
  onRetry: () => void
}

function priceFrequencyLabel(frequency: PriceFrequency): string {
  if (frequency === '30m') {
    return '30-minute'
  }
  if (frequency === '60m') {
    return '60-minute'
  }
  return 'daily'
}

export default function StockResearchPanel({
  selectedStock,
  prices,
  priceAdjustment,
  chartInterval,
  priceFrequency,
  signals,
  syncMetadata,
  syncWarning,
  loading,
  error,
  requestMode,
  onIntervalChange,
  onRetry,
}: StockResearchPanelProps) {
  const latestPrice = prices.at(-1)
  const previousPrice = prices.at(-2)
  const priceChange =
    latestPrice && previousPrice
      ? latestPrice.close - previousPrice.close
      : null

  return (
    <>
      <section className="panel chart-panel" aria-labelledby="chart-heading">
        {selectedStock ? (
          <>
            <div className="stock-summary">
              <div>
                <p className="section-kicker">
                  {selectedStock.exchange} / {selectedStock.symbol}
                </p>
                <h2 id="chart-heading">{selectedStock.name}</h2>
              </div>
              <div className="market-summary" aria-label="Latest price">
                <span>Latest close</span>
                <strong>
                  {latestPrice ? latestPrice.close.toFixed(2) : '--'}
                </strong>
                {priceChange !== null && (
                  <small className={priceChange >= 0 ? 'positive' : 'negative'}>
                    {priceChange >= 0 ? '+' : ''}
                    {priceChange.toFixed(2)}
                  </small>
                )}
              </div>
            </div>

            {loading ? (
              <div className="loading-state chart-loading" role="status">
                {priceFrequency !== 'daily'
                  ? `Loading ${priceFrequencyLabel(priceFrequency)} price history...`
                  : requestMode === 'sync'
                    ? 'Synchronizing missing price history...'
                    : 'Loading cached price history and technical signals...'}
              </div>
            ) : error ? (
              <div className="error-state chart-error" role="alert">
                <p>{error}</p>
                <button onClick={onRetry}>Retry</button>
              </div>
            ) : (
              <>
                {syncWarning && (
                  <div className="sync-warning" role="status">
                    {syncWarning}
                  </div>
                )}
                <KlineChart
                  key={`${selectedStock.exchange}:${selectedStock.symbol}`}
                  prices={prices}
                  interval={chartInterval}
                  onIntervalChange={onIntervalChange}
                />
                <div className="chart-footer">
                  <span>
                    {prices.length} stored {priceFrequencyLabel(priceFrequency)}{' '}
                    record{prices.length === 1 ? '' : 's'}
                  </span>
                  <span>
                    Source: {latestPrice?.source ?? 'No price source'}
                  </span>
                  <span>
                    Adjustment:{' '}
                    {priceAdjustment === 'front_adjusted'
                      ? 'Front adjusted'
                      : 'Source defined'}
                  </span>
                  {syncMetadata && (
                    <span>
                      {syncMetadata.cache_hit
                        ? 'Requested period already cached'
                        : `Fetched ${syncMetadata.fetched_ranges.length} missing range${syncMetadata.fetched_ranges.length === 1 ? '' : 's'}; cached ${syncMetadata.prices_inserted} new record${syncMetadata.prices_inserted === 1 ? '' : 's'}`}
                    </span>
                  )}
                </div>
              </>
            )}
          </>
        ) : (
          <div className="empty-state chart-empty">
            Select a stock to inspect its price history.
          </div>
        )}
      </section>

      <section
        className="panel signals-panel"
        aria-labelledby="signals-heading"
      >
        <div className="panel-heading">
          <div>
            <p className="section-kicker">Deterministic findings</p>
            <h2 id="signals-heading">Technical signals</h2>
          </div>
          <span className="count-badge">{signals.length}</span>
        </div>

        {!selectedStock ? (
          <div className="empty-state">Select a stock to view signals.</div>
        ) : loading ? (
          <div className="loading-state" role="status">
            Loading technical signals...
          </div>
        ) : error ? (
          <div className="empty-state">
            Signals are unavailable while stock details cannot be loaded.
          </div>
        ) : signals.length === 0 ? (
          <div className="empty-state">
            No technical signals are stored for this stock.
          </div>
        ) : (
          <div className="signal-list">
            {signals.map((signal) => (
              <article className="signal-card" key={signal.id}>
                <div className="signal-title">
                  <div>
                    <strong>{signal.signal.name}</strong>
                    <span>
                      {signal.signal.code} v{signal.signal.version}
                    </span>
                  </div>
                  <time dateTime={signal.signal_date}>
                    {signal.signal_date}
                  </time>
                </div>
                <p>{signal.explanation}</p>
                <dl className="matched-values">
                  {Object.entries(signal.matched_values)
                    .slice(0, 4)
                    .map(([key, value]) => (
                      <div key={key}>
                        <dt>{humanize(key)}</dt>
                        <dd>
                          {typeof value === 'number'
                            ? formatNumber(value)
                            : String(value)}
                        </dd>
                      </div>
                    ))}
                </dl>
              </article>
            ))}
          </div>
        )}
      </section>
    </>
  )
}
