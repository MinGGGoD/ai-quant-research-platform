import math
from io import BytesIO

import httpx
import pytest
from pypdf import PdfWriter

from rag import (
    DocumentLoadError,
    EmbeddingProviderError,
    LocalHashEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    UnsupportedDocumentError,
    load_document_bytes,
    normalize_text,
    split_text,
)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        math.sqrt(sum(value * value for value in left))
        * math.sqrt(sum(value * value for value in right))
    )


def test_chunking_normalizes_text_and_preserves_bounded_overlap() -> None:
    text = "Revenue increased during the reporting period.\n\n" + (
        "Operating cash flow remained positive. " * 8
    )

    chunks = split_text(text, max_characters=120, overlap_characters=20)

    assert len(chunks) > 1
    assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
    assert all(0 < len(chunk.content) <= 120 for chunk in chunks)
    assert all(
        current.start_character < previous.end_character
        for previous, current in zip(chunks, chunks[1:], strict=False)
    )
    normalized = normalize_text(text)
    assert all(
        normalized[chunk.start_character : chunk.end_character] == chunk.content
        for chunk in chunks
    )


def test_chunking_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        split_text("research text", max_characters=100, overlap_characters=100)


def test_text_loader_accepts_utf8_markdown_and_rejects_unknown_format() -> None:
    loaded = load_document_bytes(
        data=b"# Annual report\n\nRevenue observations.",
        filename="annual-report.md",
        content_type="text/markdown",
    )

    assert loaded.mime_type == "text/markdown"
    assert "Revenue observations" in loaded.text
    with pytest.raises(UnsupportedDocumentError):
        load_document_bytes(
            data=b"unsupported",
            filename="paid-report.docx",
            content_type=None,
        )


def test_text_loader_rejects_non_utf8_content() -> None:
    with pytest.raises(DocumentLoadError, match="UTF-8"):
        load_document_bytes(
            data=b"\xff\xfe\x00",
            filename="research-note.txt",
            content_type="text/plain",
        )


def test_pdf_loader_rejects_image_only_or_empty_pdf() -> None:
    buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(buffer)

    with pytest.raises(DocumentLoadError, match="no extractable text"):
        load_document_bytes(
            data=buffer.getvalue(),
            filename="scan.pdf",
            content_type="application/pdf",
        )


def test_local_hash_embeddings_rank_shared_research_terms_higher() -> None:
    provider = LocalHashEmbeddingProvider(dimensions=256)
    query, relevant, unrelated = provider.embed_texts(
        [
            "revenue growth operating cash flow",
            "annual revenue growth and operating cash flow observations",
            "board meeting appointment and governance announcement",
        ]
    )

    assert len(query) == 256
    assert cosine_similarity(query, relevant) > cosine_similarity(query, unrelated)


def test_openai_compatible_embedding_provider_orders_and_validates_vectors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleEmbeddingProvider(
            base_url="https://embedding.example/v1",
            api_key="synthetic-secret",
            model="synthetic-embedding",
            dimensions=2,
            timeout_seconds=5,
            max_attempts=1,
            client=client,
        )
        result = provider.embed_texts(["first", "second"])

    assert result == [[1.0, 0.0], [0.0, 1.0]]


def test_openai_compatible_embedding_provider_rejects_wrong_dimension() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                request=request,
                json={"data": [{"index": 0, "embedding": [1.0]}]},
            )
        )
    ) as client:
        provider = OpenAICompatibleEmbeddingProvider(
            base_url="https://embedding.example/v1",
            api_key="synthetic-secret",
            model="synthetic-embedding",
            dimensions=2,
            timeout_seconds=5,
            max_attempts=1,
            client=client,
        )

        with pytest.raises(EmbeddingProviderError, match="unexpected dimension"):
            provider.embed_texts(["research"])
