# AI Quant Research Platform

## API Design

### 1. Scope

The FastAPI backend provides a simple REST API for the MVP dashboard. It exposes
stock metadata, daily K-line data, scanner history, and detected technical
signals stored in PostgreSQL.

The API is for research and education. It contains no brokerage, account,
portfolio, order, or real-money execution endpoints.

### 2. General Conventions

- Base path: `/api/v1`
- Content type: `application/json`
- Field names: `snake_case`
- Dates: ISO 8601 calendar dates, for example `2026-06-12`
- Timestamps: ISO 8601 UTC timestamps, for example `2026-06-13T02:03:18Z`
- Identifiers: numeric IDs for stocks and signal definitions; UUIDs for scanner
  runs and detected signals
- Pagination: `limit` and `offset`
- Default page size: `50`
- Maximum page size: `200`
- List ordering should be deterministic and documented per endpoint.
- Empty list queries return `200` with an empty `items` array.
- Decimal database values are serialized as JSON numbers in API examples. The
  frontend must not assume more precision than the API contract provides.

Authentication is not required for the local single-user MVP. If the API becomes
network-accessible or multi-user, authentication and authorization must be
designed before deployment.

### 3. Common Response Shapes

#### Paginated Collection

```json
{
  "items": [],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 0
  }
}
```

#### Error Response

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more request parameters are invalid.",
    "details": [
      {
        "field": "from_date",
        "message": "from_date must not be later than to_date"
      }
    ],
    "request_id": "4e94b9f7-3b37-4ad4-b73a-0be26464a440"
  }
}
```

Expected error status codes:

- `400 Bad Request`: invalid parameter combinations or unsupported operations
- `404 Not Found`: requested stock, run, or other resource does not exist
- `409 Conflict`: request conflicts with current scanner state
- `413 Payload Too Large`: uploaded document exceeds the configured limit
- `415 Unsupported Media Type`: uploaded document format is unsupported
- `422 Unprocessable Entity`: request does not match the declared schema
- `502 Bad Gateway`: configured AI or embedding provider failed
- `500 Internal Server Error`: unexpected application failure
- `503 Service Unavailable`: database or required local service is unavailable

Validation errors should use the common error shape instead of exposing
framework-internal response details.

### 4. Endpoint Summary

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness check |
| `GET` | `/api/v1/health` | API and database readiness check |
| `GET` | `/api/v1/stocks` | List and filter stocks |
| `GET` | `/api/v1/stocks/{symbol}` | Get one stock |
| `GET` | `/api/v1/stocks/{symbol}/prices` | Get daily K-line data |
| `POST` | `/api/v1/stocks/{symbol}/prices/sync` | Cache missing daily K-line data |
| `GET` | `/api/v1/scanner-runs` | List scanner runs |
| `GET` | `/api/v1/scanner-runs/{run_id}` | Get one scanner run |
| `GET` | `/api/v1/signals` | List detected signals |
| `GET` | `/api/v1/stocks/{symbol}/signals` | Get signals for one stock |
| `POST` | `/api/v1/scanner-runs` | Optionally trigger a local scan |
| `POST` | `/api/v1/documents` | Upload and index an approved local document |
| `POST` | `/api/v1/documents/search` | Search indexed document chunks |
| `GET` | `/api/v1/documents/{document_id}` | Get document metadata |
| `DELETE` | `/api/v1/documents/{document_id}` | Delete a document and its chunks |

The `/api/v1` paths are canonical. Phase 5 also exposes hidden, unversioned
aliases for the implemented read resources, such as `/stocks` and
`/scanner-runs`, for local compatibility. They use the same handlers and are not
separate API contracts.

### 5. Health Check

#### 5.1 Liveness

**Method and path**

`GET /health`

**Request parameters**

None.

**Response example: `200 OK`**

```json
{
  "status": "ok"
}
```

**Error cases**

- No application-level error response is expected. If the process cannot serve
  the request, the connection fails.

**Frontend usage**

- The frontend does not need to call this endpoint during normal use.
- Docker Compose and container health checks use it to determine whether the
  FastAPI process is alive.

#### 5.2 Readiness

**Method and path**

`GET /api/v1/health`

**Request parameters**

None.

**Response example: `200 OK`**

```json
{
  "status": "ready",
  "service": "backend",
  "version": "0.1.0",
  "database": "available"
}
```

**Error example: `503 Service Unavailable`**

```json
{
  "error": {
    "code": "database_unavailable",
    "message": "The database is not available.",
    "details": [],
    "request_id": "c4f7aaed-7127-47a8-88d4-4846b29268dc"
  }
}
```

**Frontend usage**

- Call during application startup or after a connection failure.
- Show a general service-unavailable state rather than repeatedly retrying every
  dashboard request.

### 6. List Stocks

**Method and path**

`GET /api/v1/stocks`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `query` | Query | `string` | No | Case-insensitive symbol or name search |
| `exchange` | Query | `string` | No | Exact exchange filter: `SSE`, `SZSE`, or `BSE` |
| `status` | Query | `string` | No | `active`, `suspended`, or `delisted`; defaults to `active` |
| `limit` | Query | `integer` | No | Page size from 1 to 200; defaults to 50 |
| `offset` | Query | `integer` | No | Non-negative page offset; defaults to 0 |

Results are ordered by `exchange`, then `symbol`.

**Response example: `200 OK`**

```json
{
  "items": [
    {
      "id": 1,
      "symbol": "600519",
      "exchange": "SSE",
      "name": "Kweichow Moutai",
      "list_date": "2001-08-27",
      "delist_date": null,
      "status": "active"
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

**Error cases**

- `400`: unsupported `exchange` or `status`
- `422`: invalid `limit` or `offset` type
- `503`: database unavailable

**Frontend usage**

- Use for stock search, filter controls, and stock-detail navigation.
- Debounce free-text search in the browser.
- Do not load the full stock universe when a paginated search is sufficient.

### 7. Get One Stock and Daily K-Line Data

#### 7.1 Get One Stock

**Method and path**

`GET /api/v1/stocks/{symbol}`

`symbol` may be an exchange-local code such as `600519`, with an optional
`exchange=SSE` query parameter, or a suffixed code such as `600519.SH`.
Supported suffix mappings are `.SH` to `SSE`, `.SZ` to `SZSE`, and `.BJ` to
`BSE`.

The response uses the same stock object as the stock-list endpoint.

**Error cases**

- `400`: unsupported suffix, exchange, or conflicting suffix and exchange
- `404`: stock does not exist
- `409`: the local symbol is ambiguous and no exchange was supplied
- `503`: database unavailable

#### 7.2 Get Daily K-Line Data

**Method and path**

`GET /api/v1/stocks/{symbol}/prices`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `symbol` | Path | `string` | Yes | Local or suffixed stock code |
| `exchange` | Query | `string` | No | `SSE`, `SZSE`, or `BSE`; useful with a local code |
| `from_date` | Query | `date` | No | Inclusive start trading date |
| `to_date` | Query | `date` | No | Inclusive end trading date |
| `limit` | Query | `integer` | No | Maximum rows from 1 to 1000; defaults to 250 |

If no date range is provided, return the most recent `limit` records, sorted
chronologically in the response. If dates are provided, `from_date` must not be
later than `to_date`.

**Response example: `200 OK`**

```json
{
  "stock": {
    "id": 1,
    "symbol": "600519",
    "exchange": "SSE",
    "name": "Kweichow Moutai"
  },
  "price_adjustment": "source_defined",
  "items": [
    {
      "trade_date": "2026-06-11",
      "open": 1402.5,
      "high": 1418.8,
      "low": 1398.2,
      "close": 1412.1,
      "volume": 3012200,
      "amount": 4248900000.0,
      "source": "sample_daily_feed"
    },
    {
      "trade_date": "2026-06-12",
      "open": 1410.0,
      "high": 1432.5,
      "low": 1402.1,
      "close": 1426.8,
      "volume": 3254100,
      "amount": 4625180000.0,
      "source": "sample_daily_feed"
    }
  ]
}
```

The values above are illustrative.

**Error cases**

- `400`: `from_date` is later than `to_date`, or requested range exceeds an
  implementation-defined safety limit
- `404`: stock does not exist
- `422`: malformed date or invalid limit
- `503`: database unavailable

**Frontend usage**

- Use the response directly for daily candlestick and volume charts.
- The frontend may aggregate ordered daily rows into calendar-week and
  calendar-month research views. It must label these as derived from daily data.
- Calculate display-only moving averages in the browser when no shared backend
  indicator contract is required.
- Preserve chronological order when passing data to the chart library.
- Display the data source and adjustment convention near the chart.
- An empty `items` array means the stock exists but has no data in the requested
  period.

#### 7.3 Synchronize Daily K-Line Data

`POST /api/v1/stocks/{symbol}/prices/sync`

The request body requires inclusive `from_date` and `to_date` values. The range
must not exceed 1,096 days or extend beyond today. `exchange` is accepted as the
same optional query parameter used by the read endpoint.

The backend compares the requested period with stored prices, synchronization
coverage, and the provider trade calendar. It fetches only missing trading
session ranges, upserts them, stores completed historical coverage, and returns
the full cached period. The response extends the normal price response with:

- `cache_hit`: no missing provider price range was required.
- `fetched_ranges`: inclusive ranges requested from AShareHub.
- `prices_inserted` and `prices_updated`: persistence counts for this request.
- `requested_range` and listing-date-clamped `effective_range`.

Provider credentials remain server-side. Errors include `400` for an invalid
range, `502` for an AShareHub failure, and `503` when synchronization is not
configured.

### 8. List Scanner Runs

**Method and path**

`GET /api/v1/scanner-runs`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `status` | Query | `string` | No | Filter by one scanner-run status |
| `from_date` | Query | `date` | No | Inclusive minimum `data_date` |
| `to_date` | Query | `date` | No | Inclusive maximum `data_date` |
| `limit` | Query | `integer` | No | Page size from 1 to 200; defaults to 50 |
| `offset` | Query | `integer` | No | Non-negative page offset; defaults to 0 |

Results are ordered by `started_at` descending.

**Response example: `200 OK`**

```json
{
  "items": [
    {
      "id": "c62d4313-9199-4f27-a8f7-c64284e78792",
      "status": "completed_with_warnings",
      "data_date": "2026-06-12",
      "universe_name": "a_share_sample",
      "started_at": "2026-06-13T02:00:00Z",
      "finished_at": "2026-06-13T02:03:18Z",
      "total_stocks": 100,
      "processed_stocks": 98,
      "matched_stocks": 7,
      "warning_count": 2,
      "error_count": 0
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

**Error cases**

- `400`: unsupported status or invalid date range
- `422`: malformed parameters
- `503`: database unavailable

**Frontend usage**

- Use for the scan-history table and dashboard summary.
- Poll only runs in `pending` or `running` state, using a modest interval such as
  five seconds.
- Stop polling once a terminal status is returned.

### 9. Get Scanner Run Details

**Method and path**

`GET /api/v1/scanner-runs/{run_id}`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `run_id` | Path | `UUID` | Yes | Scanner-run identifier |

**Response example: `200 OK`**

```json
{
  "id": "c62d4313-9199-4f27-a8f7-c64284e78792",
  "status": "completed_with_warnings",
  "data_date": "2026-06-12",
  "universe_name": "a_share_sample",
  "parameters": {
    "signals": [
      {
        "code": "moving_average_cross",
        "version": 1
      }
    ]
  },
  "started_at": "2026-06-13T02:00:00Z",
  "finished_at": "2026-06-13T02:03:18Z",
  "summary": {
    "total_stocks": 100,
    "processed_stocks": 98,
    "matched_stocks": 7,
    "warning_count": 2,
    "error_count": 0
  },
  "error_message": null
}
```

**Error cases**

- `404`: scanner run does not exist
- `422`: `run_id` is not a valid UUID
- `503`: database unavailable

**Frontend usage**

- Use for the run-detail header, configuration summary, progress, and error
  state.
- Load matching signal rows through `GET /api/v1/signals?scanner_run_id=...`
  rather than embedding an unbounded result list in this response.

### 10. List Detected Signals

**Method and path**

`GET /api/v1/signals`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `scanner_run_id` | Query | `UUID` | No | Filter by scanner run |
| `stock_id` | Query | `integer` | No | Filter by stock |
| `signal_code` | Query | `string` | No | Filter by stable signal code |
| `from_date` | Query | `date` | No | Inclusive minimum signal date |
| `to_date` | Query | `date` | No | Inclusive maximum signal date |
| `limit` | Query | `integer` | No | Page size from 1 to 200; defaults to 50 |
| `offset` | Query | `integer` | No | Non-negative page offset; defaults to 0 |

Results are ordered by `signal_date` descending, then stock symbol and signal
code.

**Response example: `200 OK`**

```json
{
  "items": [
    {
      "id": "9a694b1c-255b-4708-b47b-f0e35b2ad1f0",
      "scanner_run_id": "c62d4313-9199-4f27-a8f7-c64284e78792",
      "signal_date": "2026-06-12",
      "stock": {
        "id": 1,
        "symbol": "600519",
        "exchange": "SSE",
        "name": "Kweichow Moutai"
      },
      "signal": {
        "code": "moving_average_cross",
        "version": 1,
        "name": "Moving Average Cross"
      },
      "matched_values": {
        "ma_5": 1418.42,
        "ma_20": 1415.08,
        "previous_ma_5": 1412.1,
        "previous_ma_20": 1413.72
      },
      "explanation": "The 5-day moving average crossed above the 20-day moving average on the evaluated date."
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

**Error cases**

- `400`: invalid date range or unsupported signal code
- `404`: supplied scanner run or stock filter refers to a missing resource
- `422`: malformed UUID, date, or pagination parameter
- `503`: database unavailable

**Frontend usage**

- Use for the dashboard result table and run-detail result list.
- Render `explanation` as rule evidence, not as an action prompt.
- Treat `matched_values` as signal-specific data; display known fields through
  signal-aware components and provide a generic fallback.

### 11. Get Signals for One Stock

**Method and path**

`GET /api/v1/stocks/{symbol}/signals`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `symbol` | Path | `string` | Yes | Local or suffixed stock code |
| `exchange` | Query | `string` | No | `SSE`, `SZSE`, or `BSE`; useful with a local code |
| `signal_code` | Query | `string` | No | Filter by stable signal code |
| `from_date` | Query | `date` | No | Inclusive minimum signal date |
| `to_date` | Query | `date` | No | Inclusive maximum signal date |
| `limit` | Query | `integer` | No | Page size from 1 to 200; defaults to 50 |
| `offset` | Query | `integer` | No | Non-negative page offset; defaults to 0 |

Results are ordered by `signal_date` descending.

**Response example: `200 OK`**

```json
{
  "stock": {
    "id": 1,
    "symbol": "600519",
    "exchange": "SSE",
    "name": "Kweichow Moutai"
  },
  "items": [
    {
      "id": "9a694b1c-255b-4708-b47b-f0e35b2ad1f0",
      "scanner_run_id": "c62d4313-9199-4f27-a8f7-c64284e78792",
      "signal_date": "2026-06-12",
      "signal": {
        "code": "moving_average_cross",
        "version": 1,
        "name": "Moving Average Cross"
      },
      "matched_values": {
        "ma_5": 1418.42,
        "ma_20": 1415.08
      },
      "explanation": "The 5-day moving average crossed above the 20-day moving average on the evaluated date."
    }
  ],
  "pagination": {
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

**Error cases**

- `400`: invalid date range or unsupported signal code
- `404`: stock does not exist
- `422`: malformed parameters
- `503`: database unavailable

**Frontend usage**

- Use alongside daily prices on the stock-detail page.
- Overlay signal dates on the K-line chart when the chart library supports it.
- Keep the wording descriptive and informational.

### 12. Optional Local Scan Trigger

The canonical MVP execution path is the scanner CLI. This endpoint is an
optional local-development convenience and is not required for the first
release. It should be disabled by default through configuration.

**Method and path**

`POST /api/v1/scanner-runs`

**Request body**

```json
{
  "data_date": "2026-06-12",
  "universe_name": "a_share_sample",
  "signals": [
    {
      "code": "moving_average_cross",
      "version": 1
    }
  ]
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `data_date` | `date` | Yes | Market date to evaluate |
| `universe_name` | `string` | Yes | Configured local stock universe |
| `signals` | `array` | Yes | One or more active signal code/version pairs |

**Response example: `202 Accepted`**

```json
{
  "id": "a12607b2-a78d-4be9-b6c5-ac1c80d0ac42",
  "status": "pending",
  "data_date": "2026-06-12",
  "universe_name": "a_share_sample",
  "created_at": "2026-06-13T03:15:00Z",
  "status_url": "/api/v1/scanner-runs/a12607b2-a78d-4be9-b6c5-ac1c80d0ac42"
}
```

**Error cases**

- `400`: unknown universe, inactive signal definition, unsupported data date, or
  required local market data is unavailable
- `403`: endpoint is disabled by local configuration
- `409`: an equivalent run already exists or the local runner permits only one
  active scan
- `422`: invalid request body
- `503`: scanner runner or database unavailable

**Frontend usage**

- Show this action only when backend capabilities indicate the endpoint is
  enabled.
- Disable repeat submission while the request is pending.
- After a `202`, poll the returned `status_url` until the run reaches a terminal
  status.

**Implementation boundary**

- The endpoint must invoke the same scanner application service used by the CLI;
  it must not duplicate signal logic in the backend route.
- A simple in-process or local subprocess runner may be acceptable for
  development, but it is not durable across backend restarts.
- Do not expose Docker socket access to the backend merely to launch the scanner
  container.
- If durable scheduling becomes necessary, design a worker and queue as a later
  phase.
- This endpoint performs research scans only. It cannot place orders or access
  brokerage systems.

### 13. Generate and Retrieve Research Notes

Phase 7 adds optional research-note endpoints. Model input is assembled by the
backend from stored data; callers cannot submit a free-form prompt.

#### 13.1 Generate a Research Note

**Method and path**

`POST /api/v1/stocks/{symbol}/research-notes`

**Request parameters**

| Name | Location | Type | Required | Description |
|---|---|---|---|---|
| `symbol` | Path | `string` | Yes | Local or suffixed stock code |
| `exchange` | Query | `string` | No | `SSE`, `SZSE`, or `BSE` |
| `scanner_run_id` | Body | `UUID` | No | Restrict signal context to one stored run |
| `price_window` | Body | `integer` | No | Recent daily records to summarize, 1-120; default 20 |
| `signal_limit` | Body | `integer` | No | Maximum stored signals to include, 1-50; default 20 |

**Request example**

```json
{
  "scanner_run_id": "c62d4313-9199-4f27-a8f7-c64284e78792",
  "price_window": 20,
  "signal_limit": 20
}
```

**Response example: `201 Created`**

```json
{
  "id": "b9572374-b8da-4d22-bbf3-91a8d0c97a97",
  "stock": {
    "id": 1,
    "symbol": "600519",
    "exchange": "SSE",
    "name": "Kweichow Moutai"
  },
  "scanner_run_id": "c62d4313-9199-4f27-a8f7-c64284e78792",
  "title": "Research observations for 600519 through 2026-06-12",
  "content": "Observations\nThe stored period shows measurable price variation.\nTechnical patterns\nA deterministic volume pattern was recorded.\nRisk factors\nHistorical patterns may not persist.\nLimitations\nThe note uses only the bounded stored context.",
  "source_type": "ai_generated",
  "model_name": "configured-compatible-model",
  "prompt_version": "research-note-v1",
  "metadata": {
    "context": {
      "price_summary": {
        "record_count": 20,
        "end_date": "2026-06-12"
      }
    },
    "generation": {
      "request_id": "provider-request-id"
    }
  },
  "created_at": "2026-06-13T12:00:00Z",
  "updated_at": "2026-06-13T12:00:00Z"
}
```

**Error cases**

- `404`: stock or supplied scanner run does not exist
- `409`: the stock has no stored daily price context
- `422`: malformed body or parameter
- `502`: provider failure, malformed response, or output safety rejection
- `503`: generation is disabled, incompletely configured, or the database is
  unavailable

The note is committed only after output validation succeeds. Provider secrets
and the full request prompt are not stored.

#### 13.2 List Notes for One Stock

**Method and path**

`GET /api/v1/stocks/{symbol}/research-notes`

Supports `exchange`, `limit`, and `offset`. Results are ordered by creation time
descending and return the normal `items` plus `pagination` envelope with a
`stock` reference.

#### 13.3 Get One Research Note

**Method and path**

`GET /api/v1/research-notes/{note_id}`

Returns the same research-note response contract used by generation. A missing
identifier returns `404 research_note_not_found`. Retrieval does not require a
configured model provider.

**Frontend usage**

- Display generated content as informational observations with model and prompt
  provenance.
- Keep stored source context available for inspection.
- Show provider failures separately from missing market data.
- Do not imply that generated text changes deterministic scanner results.

### 14. Research Document Knowledge Base

Phase 8 adds optional local document ingestion and semantic search. It accepts
only caller-supplied files and does not scrape or download paid reports.

#### 14.1 Upload and Index a Document

**Method and path**

`POST /api/v1/documents`

**Content type**

`multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | UTF-8 `.txt`, UTF-8 `.md`, or text-based `.pdf` |
| `document_type` | string | Yes | `company_announcement`, `annual_report`, `research_note`, or `other` |
| `rights_confirmed` | boolean | Yes | Confirms the file may be stored and processed locally |
| `title` | string | No | Defaults to the source filename without its extension |
| `stock_id` | integer | No | Optional related stock identifier |

**Response example: `201 Created`**

```json
{
  "created": true,
  "document": {
    "id": "d6f21111-5d0f-4556-a389-3cd2c7acaa30",
    "stock": {
      "id": 1,
      "symbol": "600519",
      "exchange": "SSE",
      "name": "Kweichow Moutai"
    },
    "document_type": "annual_report",
    "title": "Illustrative 2025 Annual Report",
    "source_name": "illustrative-annual-report.pdf",
    "source_uri": null,
    "mime_type": "application/pdf",
    "content_sha256": "9e20f3...",
    "byte_size": 284120,
    "character_count": 184532,
    "page_count": 96,
    "embedding_model": "local-hash-v1",
    "embedding_dimensions": 256,
    "metadata": {
      "ingestion": "local_upload",
      "rights_confirmed": true
    },
    "chunk_count": 173,
    "created_at": "2026-06-13T12:00:00Z",
    "updated_at": "2026-06-13T12:00:00Z"
  }
}
```

Uploading content with an existing normalized-text hash is idempotent and
returns `200 OK` with `created: false`.

**Error cases**

- `400`: rights not confirmed, empty or unreadable document, or unsupported
  document type
- `404`: supplied `stock_id` does not exist
- `409`: identical content is already indexed with another embedding model
- `413`: file exceeds the configured byte limit
- `415`: file format is unsupported
- `502`: embedding provider failed
- `503`: RAG configuration or database is unavailable

#### 14.2 Search Documents

**Method and path**

`POST /api/v1/documents/search`

**Request example**

```json
{
  "query": "operating cash flow and revenue observations",
  "document_type": "annual_report",
  "stock_id": 1,
  "limit": 10,
  "minimum_score": 0.0
}
```

`query` is required. `document_type` and `stock_id` are optional filters.
`limit` is from 1 to 50 and defaults to 10. `minimum_score` is from 0 to 1 and
defaults to 0.

**Response example: `200 OK`**

```json
{
  "query": "operating cash flow and revenue observations",
  "embedding_model": "local-hash-v1",
  "items": [
    {
      "score": 0.73,
      "content": "Illustrative operating cash flow observations...",
      "citation": {
        "document_id": "d6f21111-5d0f-4556-a389-3cd2c7acaa30",
        "title": "Illustrative 2025 Annual Report",
        "document_type": "annual_report",
        "source_name": "illustrative-annual-report.pdf",
        "source_uri": null,
        "stock": {
          "id": 1,
          "symbol": "600519",
          "exchange": "SSE",
          "name": "Kweichow Moutai"
        },
        "chunk_id": "fefc90cd-9c95-4201-a7bd-3ca10dbf1ac8",
        "chunk_index": 0
      }
    }
  ]
}
```

Results are ordered by pgvector cosine similarity. Scores compare vectors from
the configured provider and must not be interpreted as factual confidence.

**Error cases**

- `400`: empty query or unsupported document type
- `404`: supplied `stock_id` does not exist
- `422`: invalid limit, score, or body type
- `502`: embedding provider failed
- `503`: RAG configuration or database is unavailable

#### 14.3 Get Document Metadata

`GET /api/v1/documents/{document_id}` returns the document object from the
upload response. It does not return every chunk or the original binary file.
A missing identifier returns `404 document_not_found`.

#### 14.4 Delete a Document

`DELETE /api/v1/documents/{document_id}` returns `204 No Content`. Deletion
cascades to every stored chunk and vector so the source no longer appears in
search. A missing identifier returns `404 document_not_found`.

**Frontend usage**

- Display citations and source names with every retrieved chunk.
- Treat search as research-document discovery, not advice or factual
  verification.
- Require explicit rights confirmation before upload.
- Show ingestion and provider failures independently from empty search results.

### 15. Frontend and Browser Considerations

- Configure CORS only for explicit local frontend origins, such as
  `http://localhost:5173`; do not use unrestricted origins outside isolated
  development.
- Keep API base URLs configurable through frontend environment settings.
- Use request IDs from error responses when showing diagnostic details.
- Represent loading, empty, failed, and completed-with-warning states
  independently.
- Do not infer that a missing signal is a calculation success unless the
  associated scanner run confirms the stock was processed.
- Display dates and timestamps clearly; market dates are not execution times.

### 16. Non-Goals

The MVP API does not include:

- Broker connections, credentials, balances, positions, or orders.
- Real-money or paper-trading execution.
- Personalized recommendations or action-oriented stock rankings.
- Real-time quote streaming or WebSocket feeds.
- AI chat or multi-agent workflows.
- OCR, paid-report scraping, and unattended remote document downloading.
- User accounts, roles, or public internet deployment controls.
