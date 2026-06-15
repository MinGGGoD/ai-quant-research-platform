"""Local research-document ingestion, embedding, and retrieval."""

from rag.chunking import TextChunk, normalize_text, split_text
from rag.embeddings import (
    EmbeddingProvider,
    EmbeddingProviderError,
    LocalHashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)
from rag.loaders import (
    DocumentLoadError,
    LoadedDocument,
    UnsupportedDocumentError,
    load_document_bytes,
    load_local_document,
)

EMBEDDING_DIMENSIONS = 256

__all__ = [
    "EMBEDDING_DIMENSIONS",
    "DocumentLoadError",
    "EmbeddingProvider",
    "EmbeddingProviderError",
    "LoadedDocument",
    "LocalHashEmbeddingProvider",
    "OpenAICompatibleEmbeddingProvider",
    "TextChunk",
    "UnsupportedDocumentError",
    "load_document_bytes",
    "load_local_document",
    "normalize_text",
    "split_text",
]
