import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory


def make_alembic_config() -> Config:
    return Config("alembic.ini")


def test_price_sync_migration_is_the_only_head() -> None:
    scripts = ScriptDirectory.from_config(make_alembic_config())

    assert scripts.get_heads() == ["20260615_0004"]


def test_initial_migration_generates_postgresql_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config("alembic.ini")

    command.upgrade(config, "head", sql=True)

    sql = capsys.readouterr().out
    assert "CREATE TABLE stocks" in sql
    assert "CREATE TABLE daily_prices" in sql
    assert "CREATE TABLE daily_price_sync_ranges" in sql
    assert "CREATE TABLE scanner_runs" in sql
    assert "CREATE TABLE signal_definitions" in sql
    assert "CREATE TABLE technical_signals" in sql
    assert "CREATE TABLE research_notes" in sql
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "CREATE TABLE knowledge_documents" in sql
    assert "CREATE TABLE document_chunks" in sql
    assert "USING hnsw" in sql


def test_initial_migration_generates_downgrade_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "20260613_0001:base", sql=True)

    sql = capsys.readouterr().out
    assert "DROP TABLE technical_signals" in sql
    assert "DROP TABLE daily_prices" in sql
    assert "DROP TABLE scanner_runs" in sql
    assert "DROP TABLE signal_definitions" in sql
    assert "DROP TABLE stocks" in sql


def test_research_note_migration_generates_downgrade_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "20260613_0002:20260613_0001", sql=True)

    assert "DROP TABLE research_notes" in capsys.readouterr().out


def test_rag_migration_generates_downgrade_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "20260613_0003:20260613_0002", sql=True)

    sql = capsys.readouterr().out
    assert "DROP TABLE document_chunks" in sql
    assert "DROP TABLE knowledge_documents" in sql


def test_price_sync_migration_generates_downgrade_sql(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config("alembic.ini")

    command.downgrade(config, "20260615_0004:20260613_0003", sql=True)

    assert "DROP TABLE daily_price_sync_ranges" in capsys.readouterr().out


def test_alembic_accepts_percent_encoded_database_url(
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = Config("alembic.ini")
    config.attributes["database_url"] = (
        "postgresql+psycopg://ai_quant:pass%25word@localhost:5432/ai_quant"
    )

    command.upgrade(config, "head", sql=True)

    assert "CREATE TABLE stocks" in capsys.readouterr().out
