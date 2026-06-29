from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Pagination(ApiModel):
    limit: int
    offset: int
    total: int


class HealthResponse(ApiModel):
    status: Literal["ok"]


class ReadinessResponse(ApiModel):
    status: Literal["ready"]
    service: Literal["backend"]
    version: str
    database: Literal["available"]


class StockResponse(ApiModel):
    id: int
    symbol: str
    exchange: str
    name: str
    list_date: date | None
    delist_date: date | None
    status: str


class StockReference(ApiModel):
    id: int
    symbol: str
    exchange: str
    name: str


class StockListResponse(ApiModel):
    items: list[StockResponse]
    pagination: Pagination


class DailyPriceResponse(ApiModel):
    trade_date: date
    timestamp: datetime | None = None
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float | None
    source: str


class StockPricesResponse(ApiModel):
    stock: StockReference
    frequency: Literal["daily", "30m", "60m"] = "daily"
    price_adjustment: Literal["source_defined", "front_adjusted"] = "source_defined"
    items: list[DailyPriceResponse]


class StockPriceSyncRequest(ApiModel):
    from_date: date
    to_date: date


class DateRangeResponse(ApiModel):
    from_date: date
    to_date: date


class StockPriceSyncMetadata(ApiModel):
    requested_range: DateRangeResponse
    effective_range: DateRangeResponse | None
    cache_hit: bool
    fetched_ranges: list[DateRangeResponse]
    prices_inserted: int
    prices_updated: int


class StockPriceSyncResponse(StockPricesResponse):
    sync: StockPriceSyncMetadata


class ChanAlgorithmResponse(ApiModel):
    code: str
    version: int
    parameters: dict[str, Any]


class ChanFractalResponse(ApiModel):
    index: int
    bar_time: str
    trade_date: date
    timestamp: datetime | None = None
    kind: Literal["top", "bottom"]
    price: float
    status: Literal["confirmed", "provisional"]


class ChanStrokeResponse(ApiModel):
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    direction: Literal["up", "down", "neutral"]
    price_low: float
    price_high: float
    status: Literal["confirmed", "provisional"]


class ChanSegmentResponse(ApiModel):
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    direction: Literal["up", "down", "neutral"]
    price_low: float
    price_high: float
    status: Literal["confirmed", "provisional"]
    stroke_indexes: list[int]


class ChanCenterResponse(ApiModel):
    start_index: int
    end_index: int
    start_time: str
    end_time: str
    price_low: float
    price_high: float
    status: Literal["confirmed", "provisional"]
    stroke_indexes: list[int]


class ChanObservationResponse(ApiModel):
    index: int
    bar_time: str
    trade_date: date
    timestamp: datetime | None = None
    kind: str
    side: Literal["buy", "sell"]
    label: str
    price: float
    status: Literal["confirmed", "provisional"]
    explanation: str


class ChanAnalysisResponse(ApiModel):
    stock: StockReference
    frequency: Literal["daily", "30m", "60m"] = "daily"
    algorithm: ChanAlgorithmResponse
    price_bar_count: int
    fractals: list[ChanFractalResponse]
    strokes: list[ChanStrokeResponse]
    segments: list[ChanSegmentResponse]
    centers: list[ChanCenterResponse]
    observations: list[ChanObservationResponse]


class ScannerRunResponse(ApiModel):
    id: UUID
    status: str
    data_date: date
    universe_name: str
    started_at: datetime
    finished_at: datetime | None
    total_stocks: int
    processed_stocks: int
    matched_stocks: int
    warning_count: int
    error_count: int


class ScannerRunListResponse(ApiModel):
    items: list[ScannerRunResponse]
    pagination: Pagination


class ScannerRunCounts(ApiModel):
    total_stocks: int
    processed_stocks: int
    matched_stocks: int
    warning_count: int
    error_count: int


class ScannerRunDetailResponse(ApiModel):
    id: UUID
    status: str
    data_date: date
    universe_name: str
    parameters: dict[str, Any]
    started_at: datetime
    finished_at: datetime | None
    summary: ScannerRunCounts
    error_message: str | None


class SignalDefinitionReference(ApiModel):
    code: str
    version: int
    name: str


class SignalResponse(ApiModel):
    id: UUID
    scanner_run_id: UUID
    signal_date: date
    stock: StockReference
    signal: SignalDefinitionReference
    matched_values: dict[str, Any]
    explanation: str


class StockSignalResponse(ApiModel):
    id: UUID
    scanner_run_id: UUID
    signal_date: date
    signal: SignalDefinitionReference
    matched_values: dict[str, Any]
    explanation: str


class SignalListResponse(ApiModel):
    items: list[SignalResponse]
    pagination: Pagination


class StockSignalsResponse(ApiModel):
    stock: StockReference
    items: list[StockSignalResponse]
    pagination: Pagination


class ResearchNoteGenerationRequest(ApiModel):
    scanner_run_id: UUID | None = None
    price_window: int = Field(default=20, ge=1, le=120)
    signal_limit: int = Field(default=20, ge=1, le=50)


class ResearchNoteResponse(ApiModel):
    id: UUID
    stock: StockReference | None
    scanner_run_id: UUID | None
    title: str
    content: str
    source_type: str
    model_name: str | None
    prompt_version: str | None
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class ResearchNoteListResponse(ApiModel):
    stock: StockReference
    items: list[ResearchNoteResponse]
    pagination: Pagination


class KnowledgeDocumentResponse(ApiModel):
    id: UUID
    stock: StockReference | None
    document_type: str
    title: str
    source_name: str
    source_uri: str | None
    mime_type: str
    content_sha256: str
    byte_size: int
    character_count: int
    page_count: int | None
    embedding_model: str
    embedding_dimensions: int
    metadata: dict[str, Any]
    chunk_count: int
    created_at: datetime
    updated_at: datetime


class DocumentIngestionResponse(ApiModel):
    created: bool
    document: KnowledgeDocumentResponse


class DocumentSearchRequest(ApiModel):
    query: str = Field(min_length=1, max_length=2000)
    document_type: str | None = None
    stock_id: int | None = Field(default=None, ge=1)
    limit: int = Field(default=10, ge=1, le=50)
    minimum_score: float = Field(default=0.0, ge=0.0, le=1.0)


class DocumentCitation(ApiModel):
    document_id: UUID
    title: str
    document_type: str
    source_name: str
    source_uri: str | None
    stock: StockReference | None
    chunk_id: UUID
    chunk_index: int


class DocumentSearchResultResponse(ApiModel):
    score: float
    content: str
    citation: DocumentCitation


class DocumentSearchResponse(ApiModel):
    query: str
    embedding_model: str
    items: list[DocumentSearchResultResponse]


class ErrorDetail(ApiModel):
    field: str | None = None
    message: str


class ErrorBody(ApiModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: UUID


class ErrorResponse(ApiModel):
    error: ErrorBody
