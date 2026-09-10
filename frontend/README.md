# Frontend

Next.js App Router, React, and TypeScript dashboard for the AI Quant Research
Platform. The application uses Server Components for route and layout shells,
and explicit Client Components for API-driven dashboard state and interactive
charts.

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

It is a research viewer and contains no login, broker connection, or trade
execution functionality.

The App Router exposes these browser routes:

- `/`: dashboard summary and the default stock view
- `/stocks/[exchange]/[symbol]`: directly addressable stock research view
- `/scanner-runs/[runId]`: directly addressable scanner-run detail
- `/documents`: server-rendered route shell for a later document workflow
- `/research-notes`: server-rendered route shell for a later notes workflow

Run commands from this directory:

```sh
pnpm install --frozen-lockfile
pnpm run dev
pnpm run lint
pnpm run typecheck
pnpm test
pnpm run build
pnpm run start
```

Open `http://localhost:3000` during development. Set
`NEXT_PUBLIC_API_BASE_URL` before building when the browser should call a
backend other than `http://localhost:8000`. Server Components use
`BACKEND_INTERNAL_URL`; Docker Compose sets it to `http://backend:8000`.

`NEXT_PUBLIC_API_BASE_URL` is embedded in the browser bundle during the Next.js
build. Changing it therefore requires rebuilding the frontend image.
