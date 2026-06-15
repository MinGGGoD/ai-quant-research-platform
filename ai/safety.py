import re


class UnsafeResearchNoteError(ValueError):
    """Raised when generated content crosses the research-only boundary."""


PROHIBITED_PATTERNS = (
    re.compile(r"\b(?:buy|sell|hold)\b", re.IGNORECASE),
    re.compile(r"(?:买入|卖出|持有|建仓|加仓|减仓)"),
    re.compile(r"\bguaranteed\s+(?:profit|return)\b", re.IGNORECASE),
)


def validate_generated_content(content: str, *, max_characters: int) -> str:
    normalized = content.strip()
    if not normalized:
        raise UnsafeResearchNoteError("The generated research note is empty.")
    if len(normalized) > max_characters:
        raise UnsafeResearchNoteError(
            "The generated research note exceeds the configured size limit."
        )
    if any(pattern.search(normalized) for pattern in PROHIBITED_PATTERNS):
        raise UnsafeResearchNoteError(
            "The generated research note contains action-oriented language."
        )
    return normalized
