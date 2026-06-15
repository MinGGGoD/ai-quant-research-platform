import asyncio
import os
from collections.abc import Iterator, Mapping
from uuid import UUID

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.api.routes import configured_embedding_provider
from backend.app.database import DocumentChunk, KnowledgeDocument, Stock
from backend.app.database.session import get_db_session
from backend.app.main import app
from rag import LocalHashEmbeddingProvider


class AlternateLocalEmbeddingProvider(LocalHashEmbeddingProvider):
    @property
    def model_name(self) -> str:
        return "alternate-local-hash-v1"


@pytest.fixture(scope="module")
def migrated_engine() -> Iterator[Engine]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("TEST_DATABASE_URL is not configured")

    parsed_url = make_url(database_url)
    if parsed_url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg")
    if parsed_url.database is None or not parsed_url.database.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a database ending in _test")

    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        yield engine
    finally:
        engine.dispose()
        command.downgrade(config, "base")


@pytest.fixture()
def rag_api(
    migrated_engine: Engine,
) -> Iterator[tuple[sessionmaker[Session], int]]:
    session_factory = sessionmaker(
        bind=migrated_engine,
        class_=Session,
        expire_on_commit=False,
    )
    with migrated_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE document_chunks, knowledge_documents, stocks "
                "RESTART IDENTITY CASCADE"
            )
        )
    with session_factory() as session:
        stock = Stock(
            symbol="600519",
            exchange="SSE",
            name="Synthetic Research Stock",
            status="active",
        )
        session.add(stock)
        session.commit()
        stock_id = stock.id

    def override_get_db_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    provider = LocalHashEmbeddingProvider(dimensions=256)
    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[configured_embedding_provider] = lambda: provider
    try:
        yield session_factory, stock_id
    finally:
        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(configured_embedding_provider, None)


async def api_request(
    method: str,
    path: str,
    *,
    json: Mapping[str, object] | None = None,
    data: Mapping[str, str] | None = None,
    files: Mapping[str, tuple[str, bytes, str]] | None = None,
) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.request(
            method,
            path,
            json=json,
            data=data,
            files=files,
        )


def upload(
    *,
    content: str,
    filename: str,
    document_type: str,
    stock_id: int,
    rights_confirmed: bool = True,
) -> httpx.Response:
    return asyncio.run(
        api_request(
            "POST",
            "/api/v1/documents",
            data={
                "document_type": document_type,
                "stock_id": str(stock_id),
                "rights_confirmed": str(rights_confirmed).lower(),
            },
            files={"file": (filename, content.encode(), "text/plain")},
        )
    )


def search(payload: Mapping[str, object]) -> httpx.Response:
    return asyncio.run(api_request("POST", "/api/v1/documents/search", json=payload))


@pytest.mark.postgres
def test_document_upload_is_idempotent_and_semantic_search_returns_citations(
    rag_api: tuple[sessionmaker[Session], int],
) -> None:
    _, stock_id = rag_api
    annual_report = upload(
        content=(
            "Annual report observations. Revenue growth was recorded. "
            "Operating cash flow remained positive during the reporting period."
        ),
        filename="annual-report.txt",
        document_type="annual_report",
        stock_id=stock_id,
    )
    announcement = upload(
        content=(
            "Company announcement. The board meeting approved a director "
            "appointment and updated governance procedures."
        ),
        filename="announcement.txt",
        document_type="company_announcement",
        stock_id=stock_id,
    )
    duplicate = upload(
        content=(
            "Annual report observations. Revenue growth was recorded. "
            "Operating cash flow remained positive during the reporting period."
        ),
        filename="annual-report-copy.txt",
        document_type="annual_report",
        stock_id=stock_id,
    )

    assert annual_report.status_code == 201
    assert announcement.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.json()["created"] is False
    assert duplicate.json()["document"]["id"] == annual_report.json()["document"]["id"]

    response = search(
        {
            "query": "revenue growth and operating cash flow",
            "stock_id": stock_id,
            "limit": 5,
        }
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["embedding_model"] == "local-hash-v1"
    assert (
        payload["items"][0]["citation"]["document_id"]
        == (annual_report.json()["document"]["id"])
    )
    assert payload["items"][0]["citation"]["source_name"] == "annual-report.txt"
    assert payload["items"][0]["citation"]["stock"]["symbol"] == "600519"
    assert "Revenue growth" in payload["items"][0]["content"]


@pytest.mark.postgres
def test_document_search_filters_and_delete_cascades_chunks(
    rag_api: tuple[sessionmaker[Session], int],
) -> None:
    session_factory, stock_id = rag_api
    created = upload(
        content=(
            "Research note observations about liquidity, volume, and "
            "historical technical patterns."
        ),
        filename="research-note.md",
        document_type="research_note",
        stock_id=stock_id,
    )
    document_id = UUID(created.json()["document"]["id"])

    filtered = search(
        {
            "query": "liquidity volume technical patterns",
            "document_type": "annual_report",
            "limit": 5,
        }
    )
    assert filtered.status_code == 200
    assert filtered.json()["items"] == []

    detail = asyncio.run(api_request("GET", f"/api/v1/documents/{document_id}"))
    deleted = asyncio.run(api_request("DELETE", f"/api/v1/documents/{document_id}"))
    missing = asyncio.run(api_request("GET", f"/api/v1/documents/{document_id}"))

    assert detail.status_code == 200
    assert detail.json()["chunk_count"] == 1
    assert deleted.status_code == 204
    assert missing.status_code == 404
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(DocumentChunk)) == 0
        assert session.get(KnowledgeDocument, document_id) is None


@pytest.mark.postgres
def test_document_upload_requires_rights_confirmation(
    rag_api: tuple[sessionmaker[Session], int],
) -> None:
    _, stock_id = rag_api
    response = upload(
        content="Locally supplied research document.",
        filename="document.txt",
        document_type="other",
        stock_id=stock_id,
        rights_confirmed=False,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "document_rights_not_confirmed"


@pytest.mark.postgres
def test_duplicate_document_rejects_a_different_embedding_model(
    rag_api: tuple[sessionmaker[Session], int],
) -> None:
    _, stock_id = rag_api
    content = "A fixed local document used to verify embedding model isolation."
    created = upload(
        content=content,
        filename="model-isolation.txt",
        document_type="other",
        stock_id=stock_id,
    )
    app.dependency_overrides[configured_embedding_provider] = lambda: (
        AlternateLocalEmbeddingProvider(dimensions=256)
    )
    try:
        conflict = upload(
            content=content,
            filename="model-isolation.txt",
            document_type="other",
            stock_id=stock_id,
        )
        search_response = search({"query": "embedding model isolation"})
    finally:
        app.dependency_overrides[configured_embedding_provider] = lambda: (
            LocalHashEmbeddingProvider(dimensions=256)
        )

    assert created.status_code == 201
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "document_embedding_conflict"
    assert search_response.status_code == 200
    assert search_response.json()["items"] == []
