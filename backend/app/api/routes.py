from datetime import date
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ai import (
    AIProviderError,
    OpenAICompatibleResearchNoteGenerator,
    ResearchNoteGenerator,
    UnsafeResearchNoteError,
)
from backend.app.api.errors import ApiError, error_responses
from backend.app.api.repository import (
    find_stocks,
    list_prices,
    list_research_notes,
    list_scanner_runs,
    list_signals,
    list_stocks,
)
from backend.app.api.schemas import (
    DailyPriceResponse,
    DocumentCitation,
    DocumentIngestionResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSearchResultResponse,
    KnowledgeDocumentResponse,
    Pagination,
    ReadinessResponse,
    ResearchNoteGenerationRequest,
    ResearchNoteListResponse,
    ResearchNoteResponse,
    ScannerRunCounts,
    ScannerRunDetailResponse,
    ScannerRunListResponse,
    ScannerRunResponse,
    SignalDefinitionReference,
    SignalListResponse,
    SignalResponse,
    StockListResponse,
    StockPricesResponse,
    StockReference,
    StockResponse,
    StockSignalResponse,
    StockSignalsResponse,
)
from backend.app.config import get_settings
from backend.app.database import (
    KnowledgeDocument,
    ResearchNote,
    ScannerRun,
    SignalDefinition,
    Stock,
)
from backend.app.database.session import get_db_session
from backend.app.main_constants import APP_VERSION
from backend.app.services.rag_documents import (
    DocumentEmbeddingConflictError,
    EmptyDocumentError,
    RagConfigurationError,
    delete_document,
    ingest_document,
    semantic_search,
)
from backend.app.services.research_notes import (
    ResearchContextUnavailableError,
    generate_and_store_research_note,
)
from rag import (
    EMBEDDING_DIMENSIONS,
    DocumentLoadError,
    EmbeddingProvider,
    EmbeddingProviderError,
    LocalHashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    UnsupportedDocumentError,
    load_document_bytes,
)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_PRICE_LIMIT = 1000
VALID_EXCHANGES = {"SSE", "SZSE", "BSE"}
VALID_STOCK_STATUSES = {"active", "suspended", "delisted"}
VALID_RUN_STATUSES = {
    "pending",
    "running",
    "completed",
    "completed_with_warnings",
    "failed",
}
VALID_DOCUMENT_TYPES = {
    "company_announcement",
    "annual_report",
    "research_note",
    "other",
}
EXCHANGE_BY_SUFFIX = {"SH": "SSE", "SZ": "SZSE", "BJ": "BSE"}

DatabaseSession = Annotated[Session, Depends(get_db_session)]
PageLimit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
PageOffset = Annotated[int, Query(ge=0)]

api_router = APIRouter()
resource_router = APIRouter()


def configured_research_note_generator() -> ResearchNoteGenerator:
    settings = get_settings()
    api_key = (
        settings.ai_api_key.get_secret_value().strip()
        if settings.ai_api_key is not None
        else ""
    )
    model = settings.ai_model.strip() if settings.ai_model else ""
    if settings.ai_provider != "openai_compatible" or not api_key or not model:
        raise ApiError(
            status_code=503,
            code="ai_provider_unavailable",
            message=("Research-note generation is disabled or not fully configured."),
        )
    return OpenAICompatibleResearchNoteGenerator(
        base_url=settings.ai_base_url,
        api_key=api_key,
        model=model,
        timeout_seconds=settings.ai_timeout_seconds,
        max_attempts=settings.ai_max_attempts,
        max_output_tokens=settings.ai_max_output_tokens,
    )


ResearchNoteGeneratorDependency = Annotated[
    ResearchNoteGenerator,
    Depends(configured_research_note_generator),
]


def configured_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.rag_embedding_dimensions != EMBEDDING_DIMENSIONS:
        raise ApiError(
            status_code=503,
            code="rag_configuration_error",
            message=f"RAG embedding dimensions must be {EMBEDDING_DIMENSIONS}.",
        )
    if settings.rag_embedding_provider == "local_hash":
        return LocalHashEmbeddingProvider(dimensions=EMBEDDING_DIMENSIONS)

    api_key = (
        settings.rag_embedding_api_key.get_secret_value().strip()
        if settings.rag_embedding_api_key is not None
        else ""
    )
    model = settings.rag_embedding_model.strip()
    if not api_key or not model or model == "local-hash-v1":
        raise ApiError(
            status_code=503,
            code="embedding_provider_unavailable",
            message="The embedding provider is not fully configured.",
        )
    return OpenAICompatibleEmbeddingProvider(
        base_url=settings.rag_embedding_base_url,
        api_key=api_key,
        model=model,
        dimensions=EMBEDDING_DIMENSIONS,
        timeout_seconds=settings.rag_embedding_timeout_seconds,
        max_attempts=settings.rag_embedding_max_attempts,
    )


EmbeddingProviderDependency = Annotated[
    EmbeddingProvider,
    Depends(configured_embedding_provider),
]


def research_note_response(note: ResearchNote) -> ResearchNoteResponse:
    return ResearchNoteResponse(
        id=note.id,
        stock=StockReference.model_validate(note.stock) if note.stock else None,
        scanner_run_id=note.scanner_run_id,
        title=note.title,
        content=note.content,
        source_type=note.source_type,
        model_name=note.model_name,
        prompt_version=note.prompt_version,
        metadata=note.generation_metadata,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


def knowledge_document_response(
    document: KnowledgeDocument,
) -> KnowledgeDocumentResponse:
    return KnowledgeDocumentResponse(
        id=document.id,
        stock=(
            StockReference.model_validate(document.stock) if document.stock else None
        ),
        document_type=document.document_type,
        title=document.title,
        source_name=document.source_name,
        source_uri=document.source_uri,
        mime_type=document.mime_type,
        content_sha256=document.content_sha256,
        byte_size=document.byte_size,
        character_count=document.character_count,
        page_count=document.page_count,
        embedding_model=document.embedding_model,
        embedding_dimensions=document.embedding_dimensions,
        metadata=document.source_metadata,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def normalize_document_type(document_type: str | None) -> str | None:
    if document_type is None:
        return None
    normalized = document_type.strip().lower()
    if normalized not in VALID_DOCUMENT_TYPES:
        raise ApiError(
            status_code=400,
            code="unsupported_document_type",
            message=(
                "document_type must be company_announcement, annual_report, "
                "research_note, or other."
            ),
        )
    return normalized


def validate_date_range(from_date: date | None, to_date: date | None) -> None:
    if from_date and to_date and from_date > to_date:
        raise ApiError(
            status_code=400,
            code="invalid_date_range",
            message="from_date must not be later than to_date.",
        )


def normalize_exchange(exchange: str | None) -> str | None:
    if exchange is None:
        return None
    normalized = exchange.strip().upper()
    if normalized not in VALID_EXCHANGES:
        raise ApiError(
            status_code=400,
            code="unsupported_exchange",
            message="exchange must be SSE, SZSE, or BSE.",
        )
    return normalized


def stock_locator(symbol: str, exchange: str | None) -> tuple[str, str | None]:
    normalized_symbol = symbol.strip().upper()
    inferred_exchange: str | None = None
    if "." in normalized_symbol:
        local_symbol, suffix = normalized_symbol.rsplit(".", maxsplit=1)
        inferred_exchange = EXCHANGE_BY_SUFFIX.get(suffix)
        if inferred_exchange is None:
            raise ApiError(
                status_code=400,
                code="unsupported_stock_symbol",
                message="Stock suffix must be .SH, .SZ, or .BJ.",
            )
        normalized_symbol = local_symbol

    normalized_exchange = normalize_exchange(exchange)
    if (
        normalized_exchange is not None
        and inferred_exchange is not None
        and normalized_exchange != inferred_exchange
    ):
        raise ApiError(
            status_code=400,
            code="conflicting_exchange",
            message="The stock suffix and exchange parameter do not match.",
        )
    if not normalized_symbol:
        raise ApiError(
            status_code=400,
            code="invalid_stock_symbol",
            message="A stock symbol is required.",
        )
    return normalized_symbol, normalized_exchange or inferred_exchange


def resolve_stock(
    session: Session,
    symbol: str,
    exchange: str | None,
) -> Stock:
    normalized_symbol, normalized_exchange = stock_locator(symbol, exchange)
    matches = find_stocks(
        session,
        symbol=normalized_symbol,
        exchange=normalized_exchange,
    )
    if not matches:
        raise ApiError(
            status_code=404,
            code="stock_not_found",
            message="The requested stock does not exist.",
        )
    if len(matches) > 1:
        raise ApiError(
            status_code=409,
            code="ambiguous_stock_symbol",
            message="The symbol exists on multiple exchanges; provide exchange.",
        )
    return matches[0]


def validate_signal_code(session: Session, signal_code: str | None) -> None:
    if signal_code is None:
        return
    exists = session.scalar(
        select(SignalDefinition.id).where(SignalDefinition.code == signal_code).limit(1)
    )
    if exists is None:
        raise ApiError(
            status_code=400,
            code="unsupported_signal_code",
            message="The requested signal code is not defined.",
        )


@api_router.get("/health", response_model=ReadinessResponse, tags=["health"])
def readiness(session: DatabaseSession) -> ReadinessResponse:
    session.execute(text("SELECT 1"))
    return ReadinessResponse(
        status="ready",
        service="backend",
        version=APP_VERSION,
        database="available",
    )


@resource_router.get(
    "/stocks",
    response_model=StockListResponse,
    responses=error_responses(),
    tags=["stocks"],
)
def get_stocks(
    session: DatabaseSession,
    query: str | None = Query(default=None, max_length=128),
    exchange: str | None = None,
    status: str = "active",
    limit: PageLimit = DEFAULT_LIMIT,
    offset: PageOffset = 0,
) -> StockListResponse:
    normalized_status = status.strip().lower()
    if normalized_status not in VALID_STOCK_STATUSES:
        raise ApiError(
            status_code=400,
            code="unsupported_stock_status",
            message="status must be active, suspended, or delisted.",
        )
    stocks, total = list_stocks(
        session,
        query=query.strip() if query and query.strip() else None,
        exchange=normalize_exchange(exchange),
        status=normalized_status,
        limit=limit,
        offset=offset,
    )
    return StockListResponse(
        items=[StockResponse.model_validate(stock) for stock in stocks],
        pagination=Pagination(limit=limit, offset=offset, total=total),
    )


@resource_router.get(
    "/stocks/{symbol}/prices",
    response_model=StockPricesResponse,
    responses=error_responses(),
    tags=["stocks"],
)
def get_stock_prices(
    symbol: str,
    session: DatabaseSession,
    exchange: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = Query(default=250, ge=1, le=MAX_PRICE_LIMIT),
) -> StockPricesResponse:
    validate_date_range(from_date, to_date)
    stock = resolve_stock(session, symbol, exchange)
    prices = list_prices(
        session,
        stock_id=stock.id,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
    )
    return StockPricesResponse(
        stock=StockReference.model_validate(stock),
        items=[DailyPriceResponse.model_validate(price) for price in prices],
    )


@resource_router.get(
    "/stocks/{symbol}/signals",
    response_model=StockSignalsResponse,
    responses=error_responses(),
    tags=["signals"],
)
def get_stock_signals(
    symbol: str,
    session: DatabaseSession,
    exchange: str | None = None,
    signal_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: PageLimit = DEFAULT_LIMIT,
    offset: PageOffset = 0,
) -> StockSignalsResponse:
    validate_date_range(from_date, to_date)
    stock = resolve_stock(session, symbol, exchange)
    validate_signal_code(session, signal_code)
    rows, total = list_signals(
        session,
        scanner_run_id=None,
        stock_id=stock.id,
        signal_code=signal_code,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    items = [
        StockSignalResponse(
            id=technical_signal.id,
            scanner_run_id=technical_signal.scanner_run_id,
            signal_date=technical_signal.signal_date,
            signal=SignalDefinitionReference.model_validate(definition),
            matched_values=technical_signal.matched_values,
            explanation=technical_signal.explanation,
        )
        for technical_signal, _, definition in rows
    ]
    return StockSignalsResponse(
        stock=StockReference.model_validate(stock),
        items=items,
        pagination=Pagination(limit=limit, offset=offset, total=total),
    )


@resource_router.get(
    "/stocks/{symbol}",
    response_model=StockResponse,
    responses=error_responses(),
    tags=["stocks"],
)
def get_stock(
    symbol: str,
    session: DatabaseSession,
    exchange: str | None = None,
) -> StockResponse:
    return StockResponse.model_validate(resolve_stock(session, symbol, exchange))


@resource_router.get(
    "/scanner-runs",
    response_model=ScannerRunListResponse,
    responses=error_responses(),
    tags=["scanner-runs"],
)
def get_scanner_runs(
    session: DatabaseSession,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: PageLimit = DEFAULT_LIMIT,
    offset: PageOffset = 0,
) -> ScannerRunListResponse:
    validate_date_range(from_date, to_date)
    normalized_status = status.strip().lower() if status else None
    if normalized_status and normalized_status not in VALID_RUN_STATUSES:
        raise ApiError(
            status_code=400,
            code="unsupported_scanner_run_status",
            message="The requested scanner-run status is not supported.",
        )
    runs, total = list_scanner_runs(
        session,
        status=normalized_status,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    return ScannerRunListResponse(
        items=[ScannerRunResponse.model_validate(run) for run in runs],
        pagination=Pagination(limit=limit, offset=offset, total=total),
    )


@resource_router.get(
    "/scanner-runs/{run_id}",
    response_model=ScannerRunDetailResponse,
    responses=error_responses(),
    tags=["scanner-runs"],
)
def get_scanner_run(run_id: UUID, session: DatabaseSession) -> ScannerRunDetailResponse:
    scanner_run = session.get(ScannerRun, run_id)
    if scanner_run is None:
        raise ApiError(
            status_code=404,
            code="scanner_run_not_found",
            message="The requested scanner run does not exist.",
        )
    return ScannerRunDetailResponse(
        id=scanner_run.id,
        status=scanner_run.status,
        data_date=scanner_run.data_date,
        universe_name=scanner_run.universe_name,
        parameters=scanner_run.parameters,
        started_at=scanner_run.started_at,
        finished_at=scanner_run.finished_at,
        summary=ScannerRunCounts.model_validate(scanner_run),
        error_message=scanner_run.error_message,
    )


@resource_router.get(
    "/signals",
    response_model=SignalListResponse,
    responses=error_responses(),
    tags=["signals"],
)
def get_signals(
    session: DatabaseSession,
    scanner_run_id: UUID | None = None,
    stock_id: int | None = Query(default=None, ge=1),
    signal_code: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: PageLimit = DEFAULT_LIMIT,
    offset: PageOffset = 0,
) -> SignalListResponse:
    validate_date_range(from_date, to_date)
    validate_signal_code(session, signal_code)
    if scanner_run_id and session.get(ScannerRun, scanner_run_id) is None:
        raise ApiError(
            status_code=404,
            code="scanner_run_not_found",
            message="The requested scanner run does not exist.",
        )
    if stock_id and session.get(Stock, stock_id) is None:
        raise ApiError(
            status_code=404,
            code="stock_not_found",
            message="The requested stock does not exist.",
        )

    rows, total = list_signals(
        session,
        scanner_run_id=scanner_run_id,
        stock_id=stock_id,
        signal_code=signal_code,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        offset=offset,
    )
    items = [
        SignalResponse(
            id=technical_signal.id,
            scanner_run_id=technical_signal.scanner_run_id,
            signal_date=technical_signal.signal_date,
            stock=StockReference.model_validate(stock),
            signal=SignalDefinitionReference.model_validate(definition),
            matched_values=technical_signal.matched_values,
            explanation=technical_signal.explanation,
        )
        for technical_signal, stock, definition in rows
    ]
    return SignalListResponse(
        items=items,
        pagination=Pagination(limit=limit, offset=offset, total=total),
    )


@resource_router.post(
    "/stocks/{symbol}/research-notes",
    response_model=ResearchNoteResponse,
    status_code=201,
    responses=error_responses(),
    tags=["research-notes"],
)
def create_research_note(
    symbol: str,
    request: ResearchNoteGenerationRequest,
    session: DatabaseSession,
    generator: ResearchNoteGeneratorDependency,
    exchange: str | None = None,
) -> ResearchNoteResponse:
    stock = resolve_stock(session, symbol, exchange)
    if (
        request.scanner_run_id is not None
        and session.get(ScannerRun, request.scanner_run_id) is None
    ):
        raise ApiError(
            status_code=404,
            code="scanner_run_not_found",
            message="The requested scanner run does not exist.",
        )

    settings = get_settings()
    try:
        note = generate_and_store_research_note(
            session,
            stock=stock,
            scanner_run_id=request.scanner_run_id,
            price_window=request.price_window,
            signal_limit=request.signal_limit,
            max_output_characters=settings.ai_max_output_characters,
            generator=generator,
        )
    except ResearchContextUnavailableError as error:
        raise ApiError(
            status_code=409,
            code="insufficient_research_context",
            message=str(error),
        ) from error
    except UnsafeResearchNoteError as error:
        raise ApiError(
            status_code=502,
            code="unsafe_ai_output",
            message="The generated content did not pass research safety checks.",
        ) from error
    except AIProviderError as error:
        raise ApiError(
            status_code=502,
            code="ai_provider_error",
            message="The configured model provider could not generate a note.",
        ) from error
    return research_note_response(note)


@resource_router.get(
    "/stocks/{symbol}/research-notes",
    response_model=ResearchNoteListResponse,
    responses=error_responses(),
    tags=["research-notes"],
)
def get_stock_research_notes(
    symbol: str,
    session: DatabaseSession,
    exchange: str | None = None,
    limit: PageLimit = 20,
    offset: PageOffset = 0,
) -> ResearchNoteListResponse:
    stock = resolve_stock(session, symbol, exchange)
    notes, total = list_research_notes(
        session,
        stock_id=stock.id,
        limit=limit,
        offset=offset,
    )
    return ResearchNoteListResponse(
        stock=StockReference.model_validate(stock),
        items=[research_note_response(note) for note in notes],
        pagination=Pagination(limit=limit, offset=offset, total=total),
    )


@resource_router.get(
    "/research-notes/{note_id}",
    response_model=ResearchNoteResponse,
    responses=error_responses(),
    tags=["research-notes"],
)
def get_research_note(
    note_id: UUID,
    session: DatabaseSession,
) -> ResearchNoteResponse:
    note = session.get(ResearchNote, note_id)
    if note is None:
        raise ApiError(
            status_code=404,
            code="research_note_not_found",
            message="The requested research note does not exist.",
        )
    return research_note_response(note)


@resource_router.post(
    "/documents",
    response_model=DocumentIngestionResponse,
    status_code=201,
    responses=error_responses(),
    tags=["documents"],
)
def upload_document(
    response: Response,
    session: DatabaseSession,
    embedding_provider: EmbeddingProviderDependency,
    file: Annotated[UploadFile, File()],
    document_type: Annotated[str, Form()],
    rights_confirmed: Annotated[bool, Form()],
    title: Annotated[str | None, Form()] = None,
    stock_id: Annotated[int | None, Form(ge=1)] = None,
) -> DocumentIngestionResponse:
    if not rights_confirmed:
        raise ApiError(
            status_code=400,
            code="document_rights_not_confirmed",
            message=(
                "Confirm that the document may be stored and processed for "
                "local research."
            ),
        )
    normalized_type = normalize_document_type(document_type)
    assert normalized_type is not None

    stock = session.get(Stock, stock_id) if stock_id is not None else None
    if stock_id is not None and stock is None:
        raise ApiError(
            status_code=404,
            code="stock_not_found",
            message="The requested stock does not exist.",
        )

    settings = get_settings()
    filename = Path(file.filename or "document.txt").name
    raw_data = file.file.read(settings.rag_max_document_bytes + 1)
    if len(raw_data) > settings.rag_max_document_bytes:
        raise ApiError(
            status_code=413,
            code="document_too_large",
            message="The uploaded document exceeds the configured size limit.",
        )
    try:
        loaded = load_document_bytes(
            data=raw_data,
            filename=filename,
            content_type=file.content_type,
        )
        result = ingest_document(
            session,
            loaded=loaded,
            raw_byte_size=len(raw_data),
            document_type=normalized_type,
            title=(title.strip() if title and title.strip() else Path(filename).stem),
            source_name=filename,
            source_uri=None,
            stock_id=stock.id if stock else None,
            source_metadata={
                "ingestion": "local_upload",
                "rights_confirmed": True,
            },
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
            embedding_provider=embedding_provider,
        )
    except UnsupportedDocumentError as error:
        raise ApiError(
            status_code=415,
            code="unsupported_document_format",
            message=str(error),
        ) from error
    except (DocumentLoadError, EmptyDocumentError) as error:
        raise ApiError(
            status_code=400,
            code="invalid_document",
            message=str(error),
        ) from error
    except DocumentEmbeddingConflictError as error:
        raise ApiError(
            status_code=409,
            code="document_embedding_conflict",
            message=str(error),
        ) from error
    except RagConfigurationError as error:
        raise ApiError(
            status_code=503,
            code="rag_configuration_error",
            message=str(error),
        ) from error
    except EmbeddingProviderError as error:
        raise ApiError(
            status_code=502,
            code="embedding_provider_error",
            message="The configured embedding provider could not index the document.",
        ) from error

    if not result.created:
        response.status_code = 200
    return DocumentIngestionResponse(
        created=result.created,
        document=knowledge_document_response(result.document),
    )


@resource_router.post(
    "/documents/search",
    response_model=DocumentSearchResponse,
    responses=error_responses(),
    tags=["documents"],
)
def search_documents(
    request: DocumentSearchRequest,
    session: DatabaseSession,
    embedding_provider: EmbeddingProviderDependency,
) -> DocumentSearchResponse:
    query = request.query.strip()
    if not query:
        raise ApiError(
            status_code=400,
            code="empty_search_query",
            message="A non-empty document search query is required.",
        )
    document_type = normalize_document_type(request.document_type)
    if request.stock_id and session.get(Stock, request.stock_id) is None:
        raise ApiError(
            status_code=404,
            code="stock_not_found",
            message="The requested stock does not exist.",
        )
    try:
        results = semantic_search(
            session,
            query=query,
            document_type=document_type,
            stock_id=request.stock_id,
            limit=request.limit,
            minimum_score=request.minimum_score,
            embedding_provider=embedding_provider,
        )
    except RagConfigurationError as error:
        raise ApiError(
            status_code=503,
            code="rag_configuration_error",
            message=str(error),
        ) from error
    except EmbeddingProviderError as error:
        raise ApiError(
            status_code=502,
            code="embedding_provider_error",
            message="The configured embedding provider could not search documents.",
        ) from error

    return DocumentSearchResponse(
        query=query,
        embedding_model=embedding_provider.model_name,
        items=[
            DocumentSearchResultResponse(
                score=result.score,
                content=result.chunk.content,
                citation=DocumentCitation(
                    document_id=result.document.id,
                    title=result.document.title,
                    document_type=result.document.document_type,
                    source_name=result.document.source_name,
                    source_uri=result.document.source_uri,
                    stock=(
                        StockReference.model_validate(result.stock)
                        if result.stock
                        else None
                    ),
                    chunk_id=result.chunk.id,
                    chunk_index=result.chunk.chunk_index,
                ),
            )
            for result in results
        ],
    )


@resource_router.get(
    "/documents/{document_id}",
    response_model=KnowledgeDocumentResponse,
    responses=error_responses(),
    tags=["documents"],
)
def get_document(
    document_id: UUID,
    session: DatabaseSession,
) -> KnowledgeDocumentResponse:
    document = session.get(KnowledgeDocument, document_id)
    if document is None:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message="The requested research document does not exist.",
        )
    return knowledge_document_response(document)


@resource_router.delete(
    "/documents/{document_id}",
    status_code=204,
    responses=error_responses(),
    tags=["documents"],
)
def remove_document(
    document_id: UUID,
    session: DatabaseSession,
) -> Response:
    document = session.get(KnowledgeDocument, document_id)
    if document is None:
        raise ApiError(
            status_code=404,
            code="document_not_found",
            message="The requested research document does not exist.",
        )
    delete_document(session, document)
    return Response(status_code=204)
