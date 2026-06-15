from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.database import DocumentChunk, KnowledgeDocument, Stock
from rag import (
    EMBEDDING_DIMENSIONS,
    EmbeddingProvider,
    LoadedDocument,
    split_text,
)


class RagConfigurationError(ValueError):
    """Raised when runtime embedding settings do not match stored vectors."""


class EmptyDocumentError(ValueError):
    """Raised when extraction or chunking produces no indexable text."""


class DocumentEmbeddingConflictError(ValueError):
    """Raised when duplicate content was indexed with another embedding model."""


@dataclass(frozen=True)
class DocumentIngestionResult:
    document: KnowledgeDocument
    created: bool


@dataclass(frozen=True)
class DocumentSearchResult:
    chunk: DocumentChunk
    document: KnowledgeDocument
    stock: Stock | None
    score: float


def ingest_document(
    session: Session,
    *,
    loaded: LoadedDocument,
    raw_byte_size: int,
    document_type: str,
    title: str,
    source_name: str,
    source_uri: str | None,
    stock_id: int | None,
    source_metadata: dict[str, Any],
    chunk_size: int,
    chunk_overlap: int,
    embedding_provider: EmbeddingProvider,
) -> DocumentIngestionResult:
    _validate_dimensions(embedding_provider)
    content_sha256 = sha256(loaded.text.encode("utf-8")).hexdigest()
    existing = session.scalar(
        select(KnowledgeDocument).where(
            KnowledgeDocument.content_sha256 == content_sha256
        )
    )
    if existing is not None:
        if (
            existing.embedding_model != embedding_provider.model_name
            or existing.embedding_dimensions != embedding_provider.dimensions
        ):
            raise DocumentEmbeddingConflictError(
                "The document is already indexed with a different embedding "
                "configuration. Delete and re-upload it before changing providers."
            )
        return DocumentIngestionResult(document=existing, created=False)

    chunks = split_text(
        loaded.text,
        max_characters=chunk_size,
        overlap_characters=chunk_overlap,
    )
    if not chunks:
        raise EmptyDocumentError("The document produced no indexable text chunks.")

    session.rollback()
    embeddings = _embed_in_batches(
        embedding_provider,
        [chunk.content for chunk in chunks],
    )
    if len(embeddings) != len(chunks):
        raise RagConfigurationError(
            "The embedding provider did not return one vector per chunk."
        )

    document = KnowledgeDocument(
        stock_id=stock_id,
        document_type=document_type,
        title=title,
        source_name=source_name,
        source_uri=source_uri,
        mime_type=loaded.mime_type,
        content_sha256=content_sha256,
        byte_size=raw_byte_size,
        character_count=len(loaded.text),
        page_count=loaded.page_count,
        embedding_model=embedding_provider.model_name,
        embedding_dimensions=embedding_provider.dimensions,
        source_metadata=source_metadata,
    )
    document.chunks.extend(
        DocumentChunk(
            chunk_index=chunk.index,
            content=chunk.content,
            content_sha256=sha256(chunk.content.encode("utf-8")).hexdigest(),
            start_character=chunk.start_character,
            end_character=chunk.end_character,
            character_count=len(chunk.content),
            embedding=embedding,
            chunk_metadata={},
        )
        for chunk, embedding in zip(chunks, embeddings, strict=True)
    )
    session.add(document)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(KnowledgeDocument).where(
                KnowledgeDocument.content_sha256 == content_sha256
            )
        )
        if existing is None:
            raise
        return DocumentIngestionResult(document=existing, created=False)

    session.refresh(document)
    return DocumentIngestionResult(document=document, created=True)


def semantic_search(
    session: Session,
    *,
    query: str,
    document_type: str | None,
    stock_id: int | None,
    limit: int,
    minimum_score: float,
    embedding_provider: EmbeddingProvider,
) -> list[DocumentSearchResult]:
    _validate_dimensions(embedding_provider)
    query_embeddings = embedding_provider.embed_texts([query])
    if len(query_embeddings) != 1:
        raise RagConfigurationError(
            "The embedding provider did not return one vector for the query."
        )
    query_vector = query_embeddings[0]
    if len(query_vector) != embedding_provider.dimensions:
        raise RagConfigurationError(
            "The embedding provider returned an unexpected query dimension."
        )
    distance = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")
    filters = [
        distance <= 1.0 - minimum_score,
        KnowledgeDocument.embedding_model == embedding_provider.model_name,
        KnowledgeDocument.embedding_dimensions == embedding_provider.dimensions,
    ]
    if document_type:
        filters.append(KnowledgeDocument.document_type == document_type)
    if stock_id:
        filters.append(KnowledgeDocument.stock_id == stock_id)

    rows = (
        session.execute(
            select(DocumentChunk, KnowledgeDocument, Stock, distance)
            .join(
                KnowledgeDocument,
                DocumentChunk.document_id == KnowledgeDocument.id,
            )
            .outerjoin(Stock, KnowledgeDocument.stock_id == Stock.id)
            .where(*filters)
            .order_by(distance, KnowledgeDocument.id, DocumentChunk.chunk_index)
            .limit(limit)
        )
        .tuples()
        .all()
    )
    return [
        DocumentSearchResult(
            chunk=chunk,
            document=document,
            stock=stock,
            score=round(max(0.0, min(1.0, 1.0 - float(row_distance))), 6),
        )
        for chunk, document, stock, row_distance in rows
    ]


def delete_document(session: Session, document: KnowledgeDocument) -> None:
    session.delete(document)
    session.commit()


def _validate_dimensions(embedding_provider: EmbeddingProvider) -> None:
    if embedding_provider.dimensions != EMBEDDING_DIMENSIONS:
        raise RagConfigurationError(
            f"Embedding dimensions must be {EMBEDDING_DIMENSIONS}."
        )


def _embed_in_batches(
    embedding_provider: EmbeddingProvider,
    texts: list[str],
    *,
    batch_size: int = 32,
) -> list[list[float]]:
    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = embedding_provider.embed_texts(texts[start : start + batch_size])
        for vector in batch:
            if len(vector) != embedding_provider.dimensions:
                raise RagConfigurationError(
                    "The embedding provider returned an unexpected dimension."
                )
        embeddings.extend(batch)
    return embeddings
