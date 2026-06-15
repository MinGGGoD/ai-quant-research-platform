from __future__ import annotations

from typing import Any

import httpx

from ai.contracts import GeneratedResearchNote, ResearchNoteContext
from ai.prompts import SYSTEM_PROMPT, build_user_prompt


class AIProviderError(RuntimeError):
    """Raised when the configured model provider cannot complete a request."""


class AIProviderResponseError(AIProviderError):
    """Raised when a provider returns an unusable response."""


class OpenAICompatibleResearchNoteGenerator:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float,
        max_attempts: int,
        max_output_tokens: int,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._max_output_tokens = max_output_tokens
        self._client = client

    def generate(self, context: ResearchNoteContext) -> GeneratedResearchNote:
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        owns_client = self._client is None
        try:
            response = self._request(client, context)
        finally:
            if owns_client:
                client.close()

        try:
            payload = response.json()
        except ValueError as error:
            raise AIProviderResponseError(
                "The model provider returned invalid JSON."
            ) from error

        content = self._extract_content(payload)
        model_name = payload.get("model")
        if not isinstance(model_name, str) or not model_name.strip():
            model_name = self._model

        metadata: dict[str, Any] = {}
        request_id = response.headers.get("x-request-id")
        if request_id:
            metadata["request_id"] = request_id
        usage = payload.get("usage")
        if isinstance(usage, dict):
            metadata["usage"] = usage
        finish_reason = self._extract_finish_reason(payload)
        if finish_reason:
            metadata["finish_reason"] = finish_reason

        return GeneratedResearchNote(
            content=content,
            model_name=model_name,
            provider_metadata=metadata,
        )

    def _request(
        self,
        client: httpx.Client,
        context: ResearchNoteContext,
    ) -> httpx.Response:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(context)},
            ],
            "temperature": 0.2,
            "max_tokens": self._max_output_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            try:
                response = client.post(self._url, headers=headers, json=payload)
            except httpx.RequestError as error:
                last_error = error
                if attempt + 1 < self._max_attempts:
                    continue
                raise AIProviderError(
                    "The model provider could not be reached."
                ) from error

            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < self._max_attempts:
                    continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise AIProviderError(
                    "The model provider rejected the generation request."
                ) from error
            return response

        message = "The model provider could not complete the request."
        raise AIProviderError(message) from last_error

    @staticmethod
    def _extract_content(payload: Any) -> str:
        if not isinstance(payload, dict):
            raise AIProviderResponseError(
                "The model provider returned an invalid response object."
            )
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AIProviderResponseError(
                "The model provider response does not contain a completion."
            )
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise AIProviderResponseError(
                "The model provider returned an invalid completion."
            )
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise AIProviderResponseError(
                "The model provider returned an invalid message."
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AIProviderResponseError(
                "The model provider returned empty research content."
            )
        return content

    @staticmethod
    def _extract_finish_reason(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return None
        finish_reason = first_choice.get("finish_reason")
        return finish_reason if isinstance(finish_reason, str) else None
