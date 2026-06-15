"""Provider-neutral AI research-note generation."""

from ai.contracts import (
    GeneratedResearchNote,
    PriceSummary,
    ResearchNoteContext,
    ResearchNoteGenerator,
    SignalObservation,
    StockResearchContext,
)
from ai.openai_compatible import (
    AIProviderError,
    AIProviderResponseError,
    OpenAICompatibleResearchNoteGenerator,
)
from ai.prompts import PROMPT_VERSION
from ai.safety import UnsafeResearchNoteError, validate_generated_content

__all__ = [
    "AIProviderError",
    "AIProviderResponseError",
    "GeneratedResearchNote",
    "OpenAICompatibleResearchNoteGenerator",
    "PROMPT_VERSION",
    "PriceSummary",
    "ResearchNoteContext",
    "ResearchNoteGenerator",
    "SignalObservation",
    "StockResearchContext",
    "UnsafeResearchNoteError",
    "validate_generated_content",
]
