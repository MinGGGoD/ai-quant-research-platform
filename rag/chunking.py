import re
from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    start_character: int
    end_character: int


def normalize_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in normalized.splitlines()]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def split_text(
    text: str,
    *,
    max_characters: int = 1200,
    overlap_characters: int = 200,
) -> list[TextChunk]:
    if max_characters < 1:
        raise ValueError("max_characters must be positive.")
    if overlap_characters < 0 or overlap_characters >= max_characters:
        raise ValueError(
            "overlap_characters must be non-negative and smaller than max_characters."
        )

    normalized = normalize_text(text)
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    while start < len(normalized):
        target_end = min(start + max_characters, len(normalized))
        end = _preferred_boundary(normalized, start, target_end)
        raw_content = normalized[start:end]
        content = raw_content.strip()
        if content:
            leading_whitespace = len(raw_content) - len(raw_content.lstrip())
            content_start = start + leading_whitespace
            chunks.append(
                TextChunk(
                    index=len(chunks),
                    content=content,
                    start_character=content_start,
                    end_character=content_start + len(content),
                )
            )
        if end >= len(normalized):
            break

        next_start = max(end - overlap_characters, start + 1)
        while next_start < end and normalized[next_start].isspace():
            next_start += 1
        start = next_start

    return chunks


def _preferred_boundary(text: str, start: int, target_end: int) -> int:
    if target_end >= len(text):
        return len(text)

    minimum_boundary = start + ((target_end - start) // 2)
    candidates = [
        text.rfind("\n\n", minimum_boundary, target_end),
        text.rfind("\u3002", minimum_boundary, target_end),
        text.rfind(". ", minimum_boundary, target_end),
        text.rfind("\n", minimum_boundary, target_end),
        text.rfind(" ", minimum_boundary, target_end),
    ]
    boundary = max(candidates)
    if boundary < minimum_boundary:
        return target_end
    if text[boundary : boundary + 2] in {"\n\n", ". "}:
        return boundary + 1
    if text[boundary] == "\u3002":
        return boundary + 1
    return boundary
