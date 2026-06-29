# Frontend

React and TypeScript MVP dashboard for the AI Quant Research Platform.

The dashboard consumes the FastAPI `/api/v1` read endpoints and displays active
stocks, interactive K-line and volume data, stored technical signals, and recent
scanner runs. A scanner run can be opened to inspect its configuration, market
date, lifecycle status, warnings or errors, summary counts, and matched signal
evidence. Daily records can be viewed directly or aggregated into weekly and
monthly bars, and local BaoStock cache files can be viewed as 30-minute or
60-minute bars. The chart includes MA5, MA10, MA20, MA30, MA60, hover
crosshairs, OHLC/indicator readouts, wheel/button zoom, and drag-to-pan while
zoomed. The stock search keeps up to six recently opened search results in
local browser storage for quick access. A start/end date picker defaults to the
past two years. Submitting a search or actively selecting a stock asks the
backend to cache only missing daily trading sessions for that period before
rendering the chart. When the selected stock is backed by the local BaoStock
daily CSV cache, the backend refreshes the CSV tail if the requested end date is
newer than the file's latest cached date.
The backend's default `auto` provider mode uses BaoStock for SSE/SZSE when an
AShareHub key is not configured, so local searches do not require credentials.

Weekly and monthly bars are derived from stored daily records. The 30-minute
view reads `data/cache/baostock/30m_qfq/`; the 60-minute view reads
`60m_qfq/` when present and otherwise derives 60-minute bars from paired
30-minute records.

It is a research viewer and contains no login, broker connection, trade
execution, AI report, or RAG functionality.

Run commands from this directory:

```sh
npm ci
npm run dev
npm run lint
npm run typecheck
npm test
npm run build
```

Set `VITE_API_BASE_URL` when the backend is not available at
`http://localhost:8000`.
