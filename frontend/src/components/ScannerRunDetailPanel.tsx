import {
  formatDateTime,
  formatJson,
  formatNumber,
  humanize,
} from '../formatters'
import type { ScannerRunDetail, TechnicalSignal } from '../types'

interface ScannerRunDetailPanelProps {
  selectedRunId: string | null
  detail: ScannerRunDetail | null
  signals: TechnicalSignal[]
  filteredSignals: TechnicalSignal[]
  signalCodes: string[]
  signalQuery: string
  signalCode: string
  loading: boolean
  error: string | null
  onClose: () => void
  onRetry: () => void
  onSignalQueryChange: (value: string) => void
  onSignalCodeChange: (value: string) => void
}

export default function ScannerRunDetailPanel({
  selectedRunId,
  detail,
  signals,
  filteredSignals,
  signalCodes,
  signalQuery,
  signalCode,
  loading,
  error,
  onClose,
  onRetry,
  onSignalQueryChange,
  onSignalCodeChange,
}: ScannerRunDetailPanelProps) {
  return (
    <section
      className="panel run-detail-panel"
      aria-labelledby="run-detail-heading"
    >
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Execution detail</p>
          <h2 id="run-detail-heading">Scanner run detail</h2>
        </div>
        {selectedRunId && (
          <button className="secondary-action" type="button" onClick={onClose}>
            Close
          </button>
        )}
      </div>

      {!selectedRunId ? (
        <div className="empty-state">
          Select a scanner run to inspect its configuration, status, and matched
          technical signals.
        </div>
      ) : loading ? (
        <div className="loading-state" role="status">
          Loading scanner run detail...
        </div>
      ) : error ? (
        <div className="error-state" role="alert">
          <p>{error}</p>
          <button onClick={onRetry}>Retry</button>
        </div>
      ) : detail ? (
        <div className="run-detail-content">
          <div className="run-detail-header">
            <div>
              <span className={`run-status ${detail.status}`}>
                {humanize(detail.status)}
              </span>
              <h3>{detail.universe_name}</h3>
              <p>
                Market date {detail.data_date} - Started{' '}
                {formatDateTime(detail.started_at)}
              </p>
            </div>
            <div className="run-id-block">
              <span>Run ID</span>
              <code>{detail.id}</code>
            </div>
          </div>

          <dl className="run-detail-metrics">
            <div>
              <dt>Total</dt>
              <dd>{detail.summary.total_stocks}</dd>
            </div>
            <div>
              <dt>Processed</dt>
              <dd>{detail.summary.processed_stocks}</dd>
            </div>
            <div>
              <dt>Matched</dt>
              <dd>{detail.summary.matched_stocks}</dd>
            </div>
            <div>
              <dt>Warnings</dt>
              <dd>{detail.summary.warning_count}</dd>
            </div>
            <div>
              <dt>Errors</dt>
              <dd>{detail.summary.error_count}</dd>
            </div>
          </dl>

          {detail.error_message && (
            <div className="sync-warning" role="status">
              {detail.error_message}
            </div>
          )}

          <div className="run-parameters">
            <span>Parameters</span>
            <pre>{formatJson(detail.parameters)}</pre>
          </div>

          <div className="run-signal-heading">
            <div>
              <p className="section-kicker">Run matched signals</p>
              <h3>Detected signals</h3>
            </div>
            <span className="count-badge">
              {filteredSignals.length}/{signals.length}
            </span>
          </div>

          {signals.length > 0 && (
            <div className="run-signal-filters">
              <label htmlFor="run-signal-query">
                Filter run signals
                <input
                  id="run-signal-query"
                  type="search"
                  value={signalQuery}
                  placeholder="Stock, code, or explanation"
                  onChange={(event) => onSignalQueryChange(event.target.value)}
                />
              </label>
              <label htmlFor="run-signal-code">
                Signal type
                <select
                  id="run-signal-code"
                  value={signalCode}
                  onChange={(event) => onSignalCodeChange(event.target.value)}
                >
                  <option value="">All signals</option>
                  {signalCodes.map((code) => (
                    <option value={code} key={code}>
                      {humanize(code)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          )}

          {signals.length === 0 ? (
            <div className="empty-state">
              No signals are stored for this scanner run.
            </div>
          ) : filteredSignals.length === 0 ? (
            <div className="empty-state">No run signals match this filter.</div>
          ) : (
            <div className="signal-list">
              {filteredSignals.map((signal) => (
                <article className="signal-card" key={signal.id}>
                  <div className="signal-title">
                    <div>
                      <strong>{signal.signal.name}</strong>
                      <span>
                        {signal.signal.code} v{signal.signal.version}
                      </span>
                      {signal.stock && (
                        <span className="signal-stock">
                          {signal.stock.symbol} / {signal.stock.exchange} -{' '}
                          {signal.stock.name}
                        </span>
                      )}
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
        </div>
      ) : null}
    </section>
  )
}
