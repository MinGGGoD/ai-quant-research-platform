from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from backend.app.database import (
    Base,
    DailyPrice,
    DocumentChunk,
    KnowledgeDocument,
    ResearchNote,
    ScannerRun,
    SignalDefinition,
    Stock,
    TechnicalSignal,
)

EXPECTED_TABLES = {
    "stocks",
    "daily_prices",
    "document_chunks",
    "knowledge_documents",
    "scanner_runs",
    "research_notes",
    "signal_definitions",
    "technical_signals",
}


def test_metadata_contains_phase_two_tables() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_documented_unique_constraints_are_present() -> None:
    stocks = Base.metadata.tables["stocks"]
    daily_prices = Base.metadata.tables["daily_prices"]
    signal_definitions = Base.metadata.tables["signal_definitions"]
    technical_signals = Base.metadata.tables["technical_signals"]
    knowledge_documents = Base.metadata.tables["knowledge_documents"]
    document_chunks = Base.metadata.tables["document_chunks"]

    unique_columns = {
        tuple(constraint.columns.keys())
        for table in (
            stocks,
            daily_prices,
            signal_definitions,
            technical_signals,
            knowledge_documents,
            document_chunks,
        )
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("exchange", "symbol") in unique_columns
    assert ("stock_id", "trade_date") in unique_columns
    assert ("code", "version") in unique_columns
    assert (
        "scanner_run_id",
        "stock_id",
        "signal_definition_id",
        "signal_date",
    ) in unique_columns
    assert ("content_sha256",) in unique_columns
    assert ("document_id", "chunk_index") in unique_columns


def test_daily_price_and_scanner_constraints_are_present() -> None:
    daily_prices = Base.metadata.tables["daily_prices"]
    scanner_runs = Base.metadata.tables["scanner_runs"]

    daily_checks = {
        constraint.name
        for constraint in daily_prices.constraints
        if isinstance(constraint, CheckConstraint)
    }
    scanner_checks = {
        constraint.name
        for constraint in scanner_runs.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert daily_checks == {
        "ck_daily_prices_non_negative_prices",
        "ck_daily_prices_non_negative_volume",
        "ck_daily_prices_valid_high",
        "ck_daily_prices_valid_low",
    }
    assert scanner_checks == {
        "ck_scanner_runs_non_negative_counts",
        "ck_scanner_runs_valid_finished_at",
        "ck_scanner_runs_valid_status",
    }


def test_research_note_constraints_are_present() -> None:
    research_notes = Base.metadata.tables["research_notes"]
    checks = {
        constraint.name
        for constraint in research_notes.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert checks == {
        "ck_research_notes_generated_metadata_present",
        "ck_research_notes_has_context_reference",
        "ck_research_notes_valid_source_type",
    }


def test_rag_document_constraints_are_present() -> None:
    documents = Base.metadata.tables["knowledge_documents"]
    chunks = Base.metadata.tables["document_chunks"]
    document_checks = {
        constraint.name
        for constraint in documents.constraints
        if isinstance(constraint, CheckConstraint)
    }
    chunk_checks = {
        constraint.name
        for constraint in chunks.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert document_checks == {
        "ck_knowledge_documents_supported_embedding_dimensions",
        "ck_knowledge_documents_valid_document_type",
        "ck_knowledge_documents_valid_page_count",
        "ck_knowledge_documents_valid_size",
    }
    assert chunk_checks == {
        "ck_document_chunks_non_negative_chunk_index",
        "ck_document_chunks_positive_character_count",
        "ck_document_chunks_valid_character_range",
    }


def test_models_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()  # type: ignore[no-untyped-call]

    for table in Base.metadata.sorted_tables:
        ddl = str(CreateTable(table).compile(dialect=dialect))
        assert f"CREATE TABLE {table.name}" in ddl


def test_model_relationships_can_be_constructed() -> None:
    stock = Stock(
        symbol="600519",
        exchange="SSE",
        name="Example Stock",
        status="active",
    )
    price = DailyPrice(
        trade_date=date(2026, 6, 12),
        open=Decimal("10.0000"),
        high=Decimal("10.5000"),
        low=Decimal("9.8000"),
        close=Decimal("10.3000"),
        volume=1000,
        amount=Decimal("10250.0000"),
        source="synthetic_fixture",
    )
    scanner_run = ScannerRun(
        status="completed",
        data_date=date(2026, 6, 12),
        universe_name="test_universe",
        parameters={},
        started_at=datetime(2026, 6, 13, tzinfo=UTC),
    )
    definition = SignalDefinition(
        code="ma_cross_up",
        version=1,
        name="Moving Average Upward Cross",
        description="Synthetic rule definition.",
        parameters={"short_window": 5, "long_window": 20},
    )
    signal = TechnicalSignal(
        signal_date=date(2026, 6, 12),
        matched_values={"ma_5": 10.2, "ma_20": 10.1},
        explanation="Synthetic research signal.",
    )
    note = ResearchNote(
        title="Synthetic research observations",
        content="Neutral observations from deterministic fixtures.",
        source_type="ai_generated",
        model_name="synthetic-model",
        prompt_version="research-note-v1",
        generation_metadata={"fixture": True},
    )
    document = KnowledgeDocument(
        document_type="annual_report",
        title="Synthetic annual report",
        source_name="annual-report.txt",
        mime_type="text/plain",
        content_sha256="a" * 64,
        byte_size=100,
        character_count=100,
        embedding_model="local-hash-v1",
        embedding_dimensions=256,
        source_metadata={"fixture": True},
    )
    chunk = DocumentChunk(
        chunk_index=0,
        content="Synthetic annual report observations.",
        content_sha256="b" * 64,
        start_character=0,
        end_character=37,
        character_count=37,
        embedding=[0.0] * 255 + [1.0],
        chunk_metadata={},
    )

    stock.daily_prices.append(price)
    stock.technical_signals.append(signal)
    scanner_run.technical_signals.append(signal)
    definition.technical_signals.append(signal)
    stock.research_notes.append(note)
    scanner_run.research_notes.append(note)
    stock.knowledge_documents.append(document)
    document.chunks.append(chunk)

    assert price.stock is stock
    assert signal.stock is stock
    assert signal.scanner_run is scanner_run
    assert signal.signal_definition is definition
    assert note.stock is stock
    assert note.scanner_run is scanner_run
    assert document.stock is stock
    assert chunk.document is document
