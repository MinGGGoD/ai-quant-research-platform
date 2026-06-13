# AI Quant Research Platform

## Product Requirements Document

### 1. Product Vision

The AI Quant Research Platform is a research and education system for exploring
A-share market data through repeatable stock scans, transparent technical signal
detection, persisted research results, and a web dashboard.

The product should help users move from fragmented scripts and manual chart
review to a structured workflow where scan conditions, signal definitions,
execution status, and historical results are visible and reproducible.

The platform does not execute trades, connect to brokers, or direct users toward
specific investment actions.

### 2. Target Users

- Quantitative research learners studying market data and technical indicators.
- Individual researchers testing rule-based stock-screening ideas.
- Developers learning how to build maintainable market-research systems.
- Educators demonstrating data pipelines, signal detection, and result analysis.
- Small research teams that need a shared view of repeatable scan results.

### 3. Core User Problems

- A-share market data and research scripts are often scattered across files and
  tools, making experiments difficult to reproduce.
- Manual review of a large stock universe is slow and inconsistent.
- Technical signal definitions may be unclear or implemented differently across
  experiments.
- Scan outputs are frequently temporary, with limited history, traceability, or
  comparison between runs.
- Researchers lack a simple dashboard for filtering signals and inspecting why a
  stock matched a rule.
- Failures caused by missing, stale, or invalid data are not always visible.

### 4. MVP Scope

The MVP will provide an end-to-end research workflow for scanning stocks,
detecting technical signals, storing results, and displaying them in a web
dashboard.

#### 4.1 Market Data Inputs

- Support an initial configurable A-share stock universe.
- Ingest or load historical market data from a non-broker data source.
- Validate required fields and identify missing or stale data.
- Track the effective market date and data source metadata used by each scan.

#### 4.2 Stock Scanning

- Run scans manually through a supported application interface.
- Apply configurable, deterministic screening rules to the selected universe.
- Record scan lifecycle states, including pending, running, completed, and
  failed.
- Capture scan parameters, timestamps, data date, and summary statistics.

#### 4.3 Technical Signal Detection

- Detect a small initial set of clearly documented technical signals.
- Define each signal using explicit, testable calculation rules.
- Store the signal name, matched stock, calculation date, relevant values, and
  an explanation of the rule match.
- Distinguish insufficient data from a valid non-match.

#### 4.4 Result Storage

- Persist stocks, market-data references, scan runs, signal definitions, and
  signal results in PostgreSQL.
- Preserve historical scan results for later comparison.
- Prevent accidental duplication for the same scan, stock, signal, and date.
- Expose stored results through versioned backend APIs.

#### 4.5 Web Dashboard

- Display recent scan runs and their status.
- Show matched stocks and detected signals for a selected run.
- Filter results by date, stock code or name, and signal type.
- Provide a stock-level detail view with the values that caused each match.
- Clearly display the market-data date and scan execution time.
- Present neutral research data without action-oriented language.

#### 4.6 Operational Baseline

- Run the MVP services locally with Docker Compose.
- Provide structured logging and visible error states.
- Include automated tests for signal calculations, persistence, and core API
  behavior.
- Document local setup, supported workflows, and known limitations.

### 5. Out-of-Scope Features

The following are explicitly outside the MVP:

- Real-money or paper-trading order execution.
- Broker API connections, account access, portfolio synchronization, or order
  management.
- Position sizing, automated allocation, or execution optimization.
- Personalized investment recommendations or action prompts.
- Return guarantees, price forecasts presented as certain outcomes, or stock
  ranking framed as a directive.
- AI-generated research reports.
- AI agents, autonomous workflows, or LangGraph orchestration.
- RAG pipelines, document ingestion, embeddings, semantic retrieval, or vector
  databases.
- Full strategy backtesting and portfolio-level performance simulation.
- Real-time streaming quotes or intraday low-latency scanning.
- Mobile applications, social features, billing, or multi-tenant administration.

### 6. Main User Workflows

#### Workflow A: Run a Stock Scan

1. The user opens the dashboard and selects an available stock universe.
2. The user selects one or more supported technical signals.
3. The user starts a scan.
4. The platform validates the required market data and records the scan run.
5. The scanner evaluates each eligible stock using deterministic rules.
6. The platform stores matches, non-match summaries, and errors.
7. The dashboard displays the completed status and result totals.

#### Workflow B: Review Signal Results

1. The user opens a completed scan.
2. The dashboard lists matched stocks and signal types.
3. The user filters the results by date, stock, or signal.
4. The user opens a result to inspect the rule definition and matched values.
5. The user uses the information for independent research or education.

#### Workflow C: Review Scan History

1. The user opens the scan history view.
2. The dashboard shows previous runs, parameters, data dates, and statuses.
3. The user selects a run to review its stored results.
4. The user compares result counts and research observations across runs.

#### Workflow D: Investigate a Failed or Incomplete Scan

1. The platform marks the scan as failed or completed with warnings.
2. The dashboard displays a concise error or data-quality summary.
3. The user identifies affected stocks, dates, or missing fields.
4. The user corrects the input data or configuration and runs a new scan.

### 7. Success Criteria

The MVP is successful when:

- A user can complete the scan-to-dashboard workflow without manually querying
  the database.
- Supported technical signals produce deterministic results for identical data
  and configuration.
- Every displayed match can be traced to a scan run, data date, signal
  definition, and relevant calculation values.
- Completed scan results remain available after service restarts.
- Missing or invalid data produces visible, actionable research-system errors
  rather than silent or misleading matches.
- Core signal, persistence, and API paths are covered by automated tests.
- The documented Docker Compose setup can start the required local services.
- The interface contains no trade execution, broker connection, or personalized
  action features.

### 8. Future Expansion Ideas

Future phases may include:

- Additional technical indicators, composite signals, and user-defined rules.
- Scheduled scans and research notifications.
- Broader data-quality monitoring and source comparison.
- Reproducible strategy backtesting using historical data.
- Portfolio research and risk-analysis tools without execution capabilities.
- AI-generated summaries that describe stored research results using an
  OpenAI-compatible LLM interface.
- RAG-based retrieval across research notes, filings, announcements, and
  educational material.
- LangGraph-based research agents with explicit human review and bounded tools.
- Saved dashboards, experiment comparison, and collaborative research notes.
- Additional markets and asset classes after A-share workflows are stable.

All future capabilities must preserve the platform's research-only boundaries:
no broker connectivity, no order execution, and no personalized investment
direction.
