import { formatDateTime, humanize } from '../formatters'
import type { ScannerRun } from '../types'

interface ScannerRunsPanelProps {
  runs: ScannerRun[]
  selectedRunId: string | null
  loading: boolean
  error: string | null
  onRetry: () => void
  onSelectRun: (runId: string) => void
}

export default function ScannerRunsPanel({
  runs,
  selectedRunId,
  loading,
  error,
  onRetry,
  onSelectRun,
}: ScannerRunsPanelProps) {
  return (
    <aside className="panel runs-panel" aria-labelledby="runs-heading">
      <div className="panel-heading">
        <div>
          <p className="section-kicker">Execution history</p>
          <h2 id="runs-heading">Recent scanner runs</h2>
        </div>
      </div>

      {loading ? (
        <div className="loading-state" role="status">
          Loading scanner runs...
        </div>
      ) : error ? (
        <div className="error-state" role="alert">
          <p>{error}</p>
          <button onClick={onRetry}>Retry</button>
        </div>
      ) : runs.length === 0 ? (
        <div className="empty-state">No scanner runs are stored yet.</div>
      ) : (
        <div className="run-list">
          {runs.map((run) => (
            <button
              className={
                run.id === selectedRunId ? 'run-card selected' : 'run-card'
              }
              key={run.id}
              type="button"
              aria-label={`Open scanner run ${run.universe_name} from ${run.data_date}`}
              aria-pressed={run.id === selectedRunId}
              onClick={() => onSelectRun(run.id)}
            >
              <div className="run-title">
                <span className={`run-status ${run.status}`}>
                  {humanize(run.status)}
                </span>
                <time dateTime={run.started_at}>
                  {formatDateTime(run.started_at)}
                </time>
              </div>
              <strong>{run.universe_name}</strong>
              <span className="run-date">Market date {run.data_date}</span>
              <dl className="run-metrics">
                <div>
                  <dt>Processed</dt>
                  <dd>
                    {run.processed_stocks}/{run.total_stocks}
                  </dd>
                </div>
                <div>
                  <dt>Matched</dt>
                  <dd>{run.matched_stocks}</dd>
                </div>
                <div>
                  <dt>Warnings</dt>
                  <dd>{run.warning_count}</dd>
                </div>
              </dl>
            </button>
          ))}
        </div>
      )}
    </aside>
  )
}
