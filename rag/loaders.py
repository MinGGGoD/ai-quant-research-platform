from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from rag.chunking import normalize_text


class DocumentLoadError(ValueError):
    """Raised when a supported local document cannot be read."""


class UnsupportedDocumentError(DocumentLoadError):
    """Raised when a document format is outside the approved local formats."""


@dataclass(frozen=True)
class LoadedDocument:
    text: str
    mime_type: str
    page_count: int | None


TEXT_SUFFIXES = {".txt": "text/plain", ".md": "text/markdown"}


def load_local_document(path: Path) -> LoadedDocument:
    return load_document_bytes(
        data=path.read_bytes(),
        filename=path.name,
        content_type=None,
    )


def load_document_bytes(
    *,
    data: bytes,
    filename: str,
    content_type: str | None,
) -> LoadedDocument:
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return _load_text(data, content_type or TEXT_SUFFIXES[suffix])
    if suffix == ".pdf" or content_type == "application/pdf":
        return _load_pdf(data)
    raise UnsupportedDocumentError(
        "Supported local document formats are .txt, .md, and text-based .pdf."
    )


def _load_text(data: bytes, mime_type: str) -> LoadedDocument:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise DocumentLoadError("Text documents must use UTF-8 encoding.") from error
    normalized = normalize_text(text)
    if not normalized:
        raise DocumentLoadError("The document does not contain readable text.")
    return LoadedDocument(text=normalized, mime_type=mime_type, page_count=None)


def _load_pdf(data: bytes) -> LoadedDocument:
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise DocumentLoadError("Encrypted PDF documents are not supported.")
        pages = [normalize_text(page.extract_text() or "") for page in reader.pages]
    except (PdfReadError, OSError, ValueError) as error:
        if isinstance(error, DocumentLoadError):
            raise
        raise DocumentLoadError("The PDF document could not be read.") from error

    text = "\n\n".join(page for page in pages if page).strip()
    if not text:
        raise DocumentLoadError(
            "The PDF contains no extractable text; scanned-image OCR is not enabled."
        )
    return LoadedDocument(
        text=text,
        mime_type="application/pdf",
        page_count=len(reader.pages),
    )
