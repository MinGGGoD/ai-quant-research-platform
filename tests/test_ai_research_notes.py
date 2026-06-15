from typing import Any

import httpx
import pytest

from ai import (
    AIProviderResponseError,
    OpenAICompatibleResearchNoteGenerator,
    PriceSummary,
    ResearchNoteContext,
    SignalObservation,
    StockResearchContext,
    UnsafeResearchNoteError,
    validate_generated_content,
)
from ai.prompts import build_user_prompt


def research_context() -> ResearchNoteContext:
    return ResearchNoteContext(
        stock=StockResearchContext(
            symbol="600519",
            exchange="SSE",
            name="Synthetic Research Stock",
            status="active",
            list_date="2001-08-27",
        ),
        price_summary=PriceSummary(
            record_count=2,
            start_date="2026-06-11",
            end_date="2026-06-12",
            first_close=10.3,
            latest_close=10.9,
            close_change_percent=5.8252,
            period_high=11.0,
            period_low=9.8,
            average_volume=1750.0,
            sources=("synthetic_fixture",),
        ),
        technical_signals=(
            SignalObservation(
                id="signal-1",
                scanner_run_id="run-1",
                signal_date="2026-06-12",
                code="volume_spike",
                version=1,
                name="Volume Spike",
                matched_values={"volume_ratio": 2.5},
                explanation="A deterministic volume pattern was detected.",
            ),
        ),
        scanner_run_id="run-1",
    )


def test_prompt_contains_only_structured_research_context() -> None:
    prompt = build_user_prompt(research_context())

    assert '"symbol":"600519"' in prompt
    assert '"close_change_percent":5.8252' in prompt
    assert '"code":"volume_spike"' in prompt


def test_openai_compatible_generator_parses_content_and_metadata() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["Authorization"]
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            headers={"x-request-id": "provider-request-1"},
            json={
                "model": "synthetic-compatible-model",
                "choices": [
                    {
                        "message": {
                            "content": (
                                "Observations\nStored prices changed across two "
                                "sessions.\nTechnical patterns\nA volume pattern "
                                "was recorded.\nRisk factors\nThe history is "
                                "short.\nLimitations\nThis note uses stored data."
                            )
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        generator = OpenAICompatibleResearchNoteGenerator(
            base_url="https://model.example/v1",
            api_key="synthetic-secret",
            model="configured-model",
            timeout_seconds=5,
            max_attempts=2,
            max_output_tokens=500,
            client=client,
        )
        result = generator.generate(research_context())

    assert result.model_name == "synthetic-compatible-model"
    assert result.provider_metadata["request_id"] == "provider-request-1"
    assert result.provider_metadata["finish_reason"] == "stop"
    assert captured["authorization"] == "Bearer synthetic-secret"
    assert '"temperature":0.2' in captured["payload"]


def test_openai_compatible_generator_retries_transient_failure() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            request=request,
            json={
                "choices": [
                    {
                        "message": {"content": "Observations\nNeutral context."},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        generator = OpenAICompatibleResearchNoteGenerator(
            base_url="https://model.example/v1",
            api_key="synthetic-secret",
            model="configured-model",
            timeout_seconds=5,
            max_attempts=2,
            max_output_tokens=500,
            client=client,
        )
        generator.generate(research_context())

    assert attempts == 2


def test_openai_compatible_generator_rejects_malformed_response() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, request=request, json={"choices": []})
        )
    ) as client:
        generator = OpenAICompatibleResearchNoteGenerator(
            base_url="https://model.example/v1",
            api_key="synthetic-secret",
            model="configured-model",
            timeout_seconds=5,
            max_attempts=1,
            max_output_tokens=500,
            client=client,
        )

        with pytest.raises(AIProviderResponseError):
            generator.generate(research_context())


@pytest.mark.parametrize(
    "content",
    [
        "The reader should buy this stock.",
        "建议投资者卖出该证券。",
        "This setup offers guaranteed return.",
    ],
)
def test_safety_validation_rejects_action_or_guarantee_language(
    content: str,
) -> None:
    with pytest.raises(UnsafeResearchNoteError):
        validate_generated_content(content, max_characters=1000)


def test_safety_validation_rejects_empty_and_oversized_content() -> None:
    with pytest.raises(UnsafeResearchNoteError):
        validate_generated_content("  ", max_characters=1000)
    with pytest.raises(UnsafeResearchNoteError):
        validate_generated_content("x" * 1001, max_characters=1000)
