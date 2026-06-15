# AI Quant Research Platform

## Database Design

### 1. Scope and Principles

PostgreSQL is the MVP system of record for stock metadata, daily K-line data,
scanner history, and detected technical signals. Later optional phases add
research notes and an approved-document knowledge base without changing the
Phase 1-6 scanner and dashboard contract.

The schema follows these principles:

- Optimize for daily batch research, not real-time or high-frequency trading.
- Preserve enough context to reproduce and explain every detected signal.
- Use ordinary relational tables, constraints, and indexes before specialized
  time-series or partitioning features.
- Store timestamps as `TIMESTAMPTZ` and market trading days as `DATE`.
- Use `NUMERIC` for prices and traded amounts to avoid floating-point rounding.
- Keep flexible configuration and calculated values in bounded `JSONB` fields.
- Store no brokerage accounts, orders, positions, or execution data.

### 2. Entity Relationships

```mermaid
erDiagram
    STOCKS ||--o{ DAILY_PRICES : has
    STOCKS ||--o{ TECHNICAL_SIGNALS : matches
    SIGNAL_DEFINITIONS ||--o{ TECHNICAL_SIGNALS : classifies
    SCANNER_RUNS ||--o{ TECHNICAL_SIGNALS : produces
    STOCKS ||--o{ RESEARCH_NOTES : concerns
    SCANNER_RUNS ||--o{ RESEARCH_NOTES : contextualizes
    STOCKS ||--o{ KNOWLEDGE_DOCUMENTS : concerns
    KNOWLEDGE_DOCUMENTS ||--o{ DOCUMENT_CHUNKS : contains
```

### 3. Table: `stocks`

Stores one record for each supported A-share security.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BIGINT` | Primary key, generated identity | Internal stable identifier |
| `symbol` | `VARCHAR(16)` | Not null | Exchange-local code such as `600519` |
| `exchange` | `VARCHAR(8)` | Not null | Exchange code such as `SSE`, `SZSE`, or `BSE` |
| `name` | `VARCHAR(128)` | Not null | Display name |
| `list_date` | `DATE` | Nullable | Listing date when known |
| `delist_date` | `DATE` | Nullable | Delisting date when applicable |
| `status` | `VARCHAR(16)` | Not null, default `active` | `active`, `suspended`, or `delisted` |
| `created_at` | `TIMESTAMPTZ` | Not null | Record creation time |
| `updated_at` | `TIMESTAMPTZ` | Not null | Last metadata update time |

**Keys and constraints**

- Primary key: `id`
- Unique constraint: (`exchange`, `symbol`)
- Check constraint: `delist_date` is null or not earlier than `list_date`

**Index suggestions**

- Unique B-tree index on (`exchange`, `symbol`) for exact lookup.
- B-tree index on `name` if name filtering becomes common.
- B-tree index on `status` only if inactive stocks form a meaningful subset.

**Example record**

| `id` | `symbol` | `exchange` | `name` | `list_date` | `delist_date` | `status` |
|---:|---|---|---|---|---|---|
| 1 | `600519` | `SSE` | `Kweichow Moutai` | `2001-08-27` | null | `active` |

### 4. Table: `daily_prices`

Stores canonical daily OHLCV records used by charts and signal calculations.
All records for a given dataset must use a documented and consistent price
adjustment convention.

The initial `synthetic_csv_v1` development source uses unadjusted synthetic
prices, synthetic CNY-denominated price and amount values, and volume measured
in shares. These records are fixtures rather than market statements.

The `asharehub_raw` source contains unadjusted AShareHub prices. Its adapter
normalizes provider units before persistence: volume is converted from lots to
shares and amount from CNY thousands to CNY. All persisted `daily_prices`
records therefore use shares and CNY regardless of provider.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BIGINT` | Primary key, generated identity | Internal row identifier |
| `stock_id` | `BIGINT` | Not null, foreign key | References `stocks.id` |
| `trade_date` | `DATE` | Not null | Market trading date |
| `open` | `NUMERIC(18,4)` | Not null | Opening price |
| `high` | `NUMERIC(18,4)` | Not null | Highest price |
| `low` | `NUMERIC(18,4)` | Not null | Lowest price |
| `close` | `NUMERIC(18,4)` | Not null | Closing price |
| `volume` | `BIGINT` | Not null | Traded volume normalized to shares |
| `amount` | `NUMERIC(24,4)` | Nullable | Traded amount normalized to CNY |
| `source` | `VARCHAR(64)` | Not null | Non-broker data-source identifier |
| `created_at` | `TIMESTAMPTZ` | Not null | Initial ingestion time |
| `updated_at` | `TIMESTAMPTZ` | Not null | Last corrected or refreshed time |

**Keys and constraints**

- Primary key: `id`
- Foreign key: `stock_id` references `stocks.id` with delete restricted
- Unique constraint: (`stock_id`, `trade_date`)
- Check constraints:
  - OHLC prices are non-negative.
  - `volume` is non-negative.
  - `high` is greater than or equal to `open`, `low`, and `close`.
  - `low` is less than or equal to `open`, `high`, and `close`.

**Index suggestions**

- Unique B-tree index on (`stock_id`, `trade_date`).
- B-tree index on `trade_date` for market-wide date queries.
- No time-based partitioning for the MVP; add it only if measured data volume
  or maintenance cost justifies it.

**Example record**

| `id` | `stock_id` | `trade_date` | `open` | `high` | `low` | `close` | `volume` | `amount` | `source` |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---|
| 1001 | 1 | `2026-06-12` | 1410.0000 | 1432.5000 | 1402.1000 | 1426.8000 | 3254100 | 4625180000.0000 | `sample_daily_feed` |

The values above are illustrative fixture data, not a market statement.

### 5. Table: `daily_price_sync_ranges`

Stores historical date intervals that were checked against the AShareHub trade
calendar for one stock. Coverage records prevent repeated provider calls for
weekends, holidays, suspended sessions, and already cached prices.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BIGINT` | Primary key, generated identity | Coverage identifier |
| `stock_id` | `BIGINT` | Not null, foreign key | References `stocks.id` |
| `source` | `VARCHAR(64)` | Not null | Provider identifier |
| `start_date` | `DATE` | Not null | Inclusive checked date |
| `end_date` | `DATE` | Not null | Inclusive checked date |
| `created_at` | `TIMESTAMPTZ` | Not null | Coverage creation time |

Ranges are merged when they overlap or are adjacent. `end_date` must not be
earlier than `start_date`. An open current session remains refreshable until its
daily bar is available; closed current dates may be cached immediately.

### 6. Table: `signal_definitions`

Stores the identity and version of each deterministic technical signal. Keeping
definitions separate from matches allows historical runs to remain traceable
when a rule changes.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `BIGINT` | Primary key, generated identity | Signal-version identifier |
| `code` | `VARCHAR(64)` | Not null | Stable machine-readable signal code |
| `version` | `INTEGER` | Not null | Positive rule version |
| `name` | `VARCHAR(128)` | Not null | Human-readable signal name |
| `description` | `TEXT` | Not null | Neutral explanation of the rule |
| `parameters` | `JSONB` | Not null, default `{}` | Documented calculation parameters |
| `is_active` | `BOOLEAN` | Not null, default `true` | Whether new scans may use this version |
| `created_at` | `TIMESTAMPTZ` | Not null | Definition creation time |

**Keys and constraints**

- Primary key: `id`
- Unique constraint: (`code`, `version`)
- Check constraint: `version` is greater than zero

**Index suggestions**

- Unique B-tree index on (`code`, `version`).
- Optional partial index on `code` where `is_active = true` if active-definition
  lookup becomes frequent.

**Example record**

| `id` | `code` | `version` | `name` | `parameters` | `is_active` |
|---:|---|---:|---|---|---|
| 10 | `moving_average_cross` | 1 | `Moving Average Cross` | `{"short_window": 5, "long_window": 20, "directions": ["above", "below"]}` | true |

The initial Phase 4 definitions are:

- `moving_average_cross` version 1: 5-day versus 20-day crossing in either
  direction.
- `recent_breakout` version 1: close above the preceding 20-session high.
- `volume_spike` version 1: volume at least 2 times the preceding 20-session
  average.

Each definition requires 21 bars including the evaluated date. Changing a
calculation rule or parameter requires a new version rather than updating an
existing definition in place.

### 7. Table: `scanner_runs`

Stores the lifecycle, configuration, and summary of each CLI scanner execution.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary key | Scanner-run identifier generated by the application |
| `status` | `VARCHAR(32)` | Not null | Run lifecycle state |
| `data_date` | `DATE` | Not null | Latest market date evaluated by the run |
| `universe_name` | `VARCHAR(128)` | Not null | Human-readable stock-universe name |
| `parameters` | `JSONB` | Not null, default `{}` | Signal codes, versions, and other run configuration |
| `started_at` | `TIMESTAMPTZ` | Not null | Execution start time |
| `finished_at` | `TIMESTAMPTZ` | Nullable | Execution completion time |
| `total_stocks` | `INTEGER` | Not null, default `0` | Stocks selected for evaluation |
| `processed_stocks` | `INTEGER` | Not null, default `0` | Stocks fully evaluated by every selected rule |
| `matched_stocks` | `INTEGER` | Not null, default `0` | Distinct stocks with at least one match |
| `warning_count` | `INTEGER` | Not null, default `0` | Data-quality or non-fatal warning count |
| `error_count` | `INTEGER` | Not null, default `0` | Processing error count |
| `error_message` | `TEXT` | Nullable | Concise run-level failure summary |
| `created_at` | `TIMESTAMPTZ` | Not null | Record creation time |

**Keys and constraints**

- Primary key: `id`
- Check constraint: `status` is one of `pending`, `running`, `completed`,
  `completed_with_warnings`, or `failed`
- Check constraints: all count fields are non-negative
- Check constraint: `finished_at` is null or not earlier than `started_at`

**Index suggestions**

- B-tree index on `started_at` descending for scan-history pages.
- B-tree index on (`data_date`, `status`) for date and state filtering.
- A `JSONB` GIN index is not needed for the MVP unless configuration searches
  become a demonstrated use case.

**Example record**

| Field | Example value |
|---|---|
| `id` | `c62d4313-9199-4f27-a8f7-c64284e78792` |
| `status` | `completed_with_warnings` |
| `data_date` | `2026-06-12` |
| `universe_name` | `a_share_sample` |
| `parameters` | `{"signals": [{"code": "moving_average_cross", "version": 1}], "stock_selection": "all_active_and_suspended", "max_history_bars": 21}` |
| `started_at` | `2026-06-13T02:00:00Z` |
| `finished_at` | `2026-06-13T02:03:18Z` |
| `total_stocks` | `100` |
| `processed_stocks` | `98` |
| `matched_stocks` | `7` |
| `warning_count` | `2` |
| `error_count` | `0` |

### 8. Table: `technical_signals`

Stores positive signal matches produced by scanner runs. Valid non-matches are
represented by run summary counts rather than one row per stock and rule.

The implementation uses `technical_signals` as the table name to match the
Phase 2 domain terminology. It has the same role as the earlier
`detected_signals` proposal.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary key | Detected-signal identifier |
| `scanner_run_id` | `UUID` | Not null, foreign key | References `scanner_runs.id` |
| `stock_id` | `BIGINT` | Not null, foreign key | References `stocks.id` |
| `signal_definition_id` | `BIGINT` | Not null, foreign key | References `signal_definitions.id` |
| `signal_date` | `DATE` | Not null | Trading date on which the rule matched |
| `matched_values` | `JSONB` | Not null, default `{}` | Indicator values supporting the match |
| `explanation` | `TEXT` | Not null | Neutral, deterministic match explanation |
| `created_at` | `TIMESTAMPTZ` | Not null | Persistence time |

**Keys and constraints**

- Primary key: `id`
- Foreign key: `scanner_run_id` references `scanner_runs.id`
- Foreign key: `stock_id` references `stocks.id` with delete restricted
- Foreign key: `signal_definition_id` references `signal_definitions.id` with
  delete restricted
- Unique constraint:
  (`scanner_run_id`, `stock_id`, `signal_definition_id`, `signal_date`)

Deleting a scanner run may cascade to its detected signals if deletion is
explicitly supported. Normal application behavior should preserve scan history.

**Index suggestions**

- B-tree index on (`scanner_run_id`, `signal_date`) for run-detail pages.
- B-tree index on (`stock_id`, `signal_date` descending) for stock history.
- B-tree index on (`signal_definition_id`, `signal_date` descending) for signal
  filtering.
- No GIN index on `matched_values` for the MVP because it is displayed as
  evidence rather than used as a primary filter.

**Example record**

| Field | Example value |
|---|---|
| `id` | `9a694b1c-255b-4708-b47b-f0e35b2ad1f0` |
| `scanner_run_id` | `c62d4313-9199-4f27-a8f7-c64284e78792` |
| `stock_id` | `1` |
| `signal_definition_id` | `10` |
| `signal_date` | `2026-06-12` |
| `matched_values` | `{"direction": "above", "short_window": 5, "long_window": 20, "previous_short_ma": 1412.10, "previous_long_ma": 1413.72, "current_short_ma": 1418.42, "current_long_ma": 1415.08}` |
| `explanation` | `The 5-day moving average crossed above the 20-day moving average on the evaluated date. This is a descriptive technical signal for research.` |

This record describes a rule match for research inspection. It is not an action
or recommendation.

### 9. Table: `research_notes`

Phase 7 creates this table for traceable manual or AI-generated research
summaries. It remains an optional extension to the Phase 1-6 MVP.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary key | Research-note identifier |
| `stock_id` | `BIGINT` | Nullable, foreign key | Optional reference to `stocks.id` |
| `scanner_run_id` | `UUID` | Nullable, foreign key | Optional reference to `scanner_runs.id` |
| `title` | `VARCHAR(256)` | Not null | Note title |
| `content` | `TEXT` | Not null | Informational research content |
| `source_type` | `VARCHAR(32)` | Not null | `manual` or `ai_generated` |
| `model_name` | `VARCHAR(128)` | Nullable | Model identifier for generated content |
| `prompt_version` | `VARCHAR(64)` | Nullable | Prompt or workflow version |
| `metadata` | `JSONB` | Not null, default `{}` | Citations, generation settings, or provenance |
| `created_at` | `TIMESTAMPTZ` | Not null | Note creation time |
| `updated_at` | `TIMESTAMPTZ` | Not null | Last note update time |

**Keys and constraints**

- Primary key: `id`
- Foreign key: `stock_id` references `stocks.id` with delete restricted
- Foreign key: `scanner_run_id` references `scanner_runs.id` with delete
  restricted
- Check constraint: `source_type` is `manual` or `ai_generated`
- At least one of `stock_id` or `scanner_run_id` should be present
- `model_name` and `prompt_version` should be populated for AI-generated notes

**Index suggestions**

- B-tree index on (`stock_id`, `created_at` descending).
- B-tree index on (`scanner_run_id`, `created_at` descending).
- Full-text or vector indexes are deferred until search requirements are
  documented.

**Example record**

| Field | Example value |
|---|---|
| `id` | `b9572374-b8da-4d22-bbf3-91a8d0c97a97` |
| `stock_id` | `1` |
| `scanner_run_id` | `c62d4313-9199-4f27-a8f7-c64284e78792` |
| `title` | `Scan result summary for 2026-06-12` |
| `content` | `Informational summary of the stored signal values and data-quality context.` |
| `source_type` | `ai_generated` |
| `model_name` | `openai-compatible-model` |
| `prompt_version` | `research-summary-v1` |

### 10. Table: `knowledge_documents`

Phase 8 stores provenance and ingestion metadata for user-supplied local
documents. The application accepts approved text, Markdown, and text-based PDF
files; it does not download or scrape paid research.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary key | Knowledge-document identifier |
| `stock_id` | `BIGINT` | Nullable, foreign key | Optional reference to `stocks.id` |
| `document_type` | `VARCHAR(32)` | Not null | `company_announcement`, `annual_report`, `research_note`, or `other` |
| `title` | `VARCHAR(256)` | Not null | Human-readable document title |
| `source_name` | `VARCHAR(512)` | Not null | Original local filename or source label |
| `source_uri` | `VARCHAR(2048)` | Nullable | Optional source locator for future approved loaders |
| `mime_type` | `VARCHAR(128)` | Not null | Normalized source media type |
| `content_sha256` | `VARCHAR(64)` | Not null, unique | Hash of normalized extracted text |
| `byte_size` | `BIGINT` | Not null | Uploaded file size |
| `character_count` | `INTEGER` | Not null | Normalized extracted-text length |
| `page_count` | `INTEGER` | Nullable | PDF page count when applicable |
| `embedding_model` | `VARCHAR(128)` | Not null | Embedding model used for all chunks |
| `embedding_dimensions` | `INTEGER` | Not null | Fixed at 256 in this schema version |
| `metadata` | `JSONB` | Not null, default `{}` | Provenance and rights-confirmation metadata |
| `created_at` | `TIMESTAMPTZ` | Not null | Initial ingestion time |
| `updated_at` | `TIMESTAMPTZ` | Not null | Last metadata update time |

**Keys and constraints**

- Primary key: `id`
- Foreign key: `stock_id` references `stocks.id` with delete restricted
- Unique constraint: `content_sha256`
- Check constraints:
  - `document_type` is one of the four supported values.
  - `byte_size` is non-negative and `character_count` is positive.
  - `page_count` is null or positive.
  - `embedding_dimensions` equals 256.

**Index suggestions**

- Unique B-tree index on `content_sha256` for idempotent ingestion.
- B-tree index on (`stock_id`, `created_at` descending).
- B-tree index on (`document_type`, `created_at` descending).

**Example record**

| Field | Example value |
|---|---|
| `id` | `d6f21111-5d0f-4556-a389-3cd2c7acaa30` |
| `stock_id` | `1` |
| `document_type` | `annual_report` |
| `title` | `Illustrative 2025 Annual Report` |
| `source_name` | `illustrative-annual-report.pdf` |
| `mime_type` | `application/pdf` |
| `content_sha256` | `9e20f3...` |
| `byte_size` | `284120` |
| `character_count` | `184532` |
| `page_count` | `96` |
| `embedding_model` | `local-hash-v1` |
| `embedding_dimensions` | `256` |
| `metadata` | `{"ingestion": "local_upload", "rights_confirmed": true}` |

### 11. Table: `document_chunks`

Stores normalized document segments and their vectors. Chunk text is retained
so every search result can include a stable citation and inspectable evidence.

| Field | Type | Constraints | Description |
|---|---|---|---|
| `id` | `UUID` | Primary key | Chunk identifier |
| `document_id` | `UUID` | Not null, foreign key | References `knowledge_documents.id` |
| `chunk_index` | `INTEGER` | Not null | Zero-based order within the document |
| `content` | `TEXT` | Not null | Normalized chunk text |
| `content_sha256` | `VARCHAR(64)` | Not null | Hash of the chunk text |
| `start_character` | `INTEGER` | Not null | Inclusive offset in normalized document text |
| `end_character` | `INTEGER` | Not null | Exclusive offset in normalized document text |
| `character_count` | `INTEGER` | Not null | Chunk text length |
| `embedding` | `VECTOR(256)` | Not null | Embedding used for cosine similarity |
| `metadata` | `JSONB` | Not null, default `{}` | Chunk-level extraction metadata |
| `created_at` | `TIMESTAMPTZ` | Not null | Chunk creation time |

**Keys and constraints**

- Primary key: `id`
- Foreign key: `document_id` references `knowledge_documents.id` with delete
  cascade
- Unique constraint: (`document_id`, `chunk_index`)
- Check constraints:
  - `chunk_index` and `start_character` are non-negative.
  - `end_character` is greater than `start_character`.
  - `character_count` is positive.

**Index suggestions**

- B-tree index on `document_id` for document retrieval and deletion.
- HNSW index on `embedding vector_cosine_ops` for semantic search.
- Do not add full-text or per-stock vector indexes until measured query patterns
  justify them.

**Example record**

| Field | Example value |
|---|---|
| `id` | `fefc90cd-9c95-4201-a7bd-3ca10dbf1ac8` |
| `document_id` | `d6f21111-5d0f-4556-a389-3cd2c7acaa30` |
| `chunk_index` | `0` |
| `content` | `Illustrative operating cash flow observations...` |
| `start_character` | `0` |
| `end_character` | `1148` |
| `character_count` | `1148` |
| `embedding` | `[0.012, -0.041, ...]` |

### 11. Design Rationale

#### Surrogate Keys with Domain Uniqueness

Generated `BIGINT` and application-generated `UUID` primary keys keep
relationships stable, while unique constraints enforce domain rules such as one
daily record per stock and date.

#### Separate Signal Definitions and Matches

Signal logic will evolve. Referencing a versioned definition ensures a
historical match remains explainable without copying the full rule into every
result row.

#### `JSONB` for Bounded Variable Data

Scanner parameters and matched indicator values vary by signal. `JSONB` avoids
frequent schema changes while core searchable fields remain relational. These
documents should stay small, validated by the application, and versioned through
their surrounding records.

#### Positive Matches Only

Persisting every non-match would grow the database without improving the main
dashboard workflow. Run-level counts provide coverage information, while
detected matches retain detailed evidence.

#### No Premature Time-Series Optimization

Daily A-share data is manageable with a composite B-tree index. Partitioning,
TimescaleDB, compression, and read replicas should be considered only after
measurement shows a real need.

#### Future Notes Without MVP Dependencies

The research-notes shape records provenance needed for future generated content,
but the MVP scanner, backend, database migrations, and dashboard must not depend
on it.

#### PostgreSQL and pgvector Together

Phase 8 uses the `vector` extension in the existing PostgreSQL service rather
than introducing a separate vector database. This keeps local deployment,
transactions, foreign keys, deletion, and backups simple. The 256-dimensional
schema is intentionally fixed; changing dimensions requires an explicit
migration and re-embedding workflow.

#### Traceable and Rights-Aware Documents

Normalized content hashes make repeated ingestion idempotent. Source metadata
records that local processing rights were confirmed, while stored chunk text
and offsets make retrieval results inspectable. This is a provenance aid, not a
substitute for legal review or permission to ingest copyrighted material.

### 12. Migration and Data Integrity Guidance

- Manage schema changes through version-controlled SQLAlchemy migrations.
- Apply migrations explicitly before starting the backend or scanner.
- Write daily-price imports as upserts keyed by (`stock_id`, `trade_date`).
- Wrap scanner-run status updates and result writes in transactions.
- Preserve completed scanner runs and their signal definitions for auditability.
- Use UTC for system timestamps and exchange-local dates for `trade_date`.
- Keep fixture records synthetic or clearly labeled as illustrative.
- Enable the PostgreSQL `vector` extension before creating Phase 8 tables.
- Delete document chunks with their parent document so removed sources cannot
  remain searchable.
- Re-embed all affected chunks through a migration workflow before changing an
  embedding model or dimension contract.
- Add retention or archival policies only after actual storage requirements are
  measured.
