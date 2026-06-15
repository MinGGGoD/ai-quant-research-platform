from __future__ import annotations

import math
import re
from hashlib import sha256
from typing import Any, Protocol

import httpx


class EmbeddingProviderError(RuntimeError):
    """Raised when embeddings cannot be generated or validated."""


class EmbeddingProvider(Protocol):
    @property
    def model_name(self) -> str:
        """Stable model identifier stored with indexed documents."""

    @property
    def dimensions(self) -> int:
        """Embedding vector dimensions."""

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate one embedding per supplied text."""


class LocalHashEmbeddingProvider:
    def __init__(self, *, dimensions: int = 256) -> None:
        self._dimensions = dimensions

    @property
    def model_name(self) -> str:
        return "local-hash-v1"

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        tokens = _tokens(text)
        if not tokens:
            raise EmbeddingProviderError(
                "Embedding input must contain searchable text."
            )

        vector = [0.0] * self._dimensions
        for token in tokens:
            digest = sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self._dimensions
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign

        magnitude = math.sqrt(sum(value * value for value in vector))
        if magnitude == 0:
            raise EmbeddingProviderError("Embedding input produced an empty vector.")
        return [value / magnitude for value in vector]


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_seconds: float,
        max_attempts: int,
        client: httpx.Client | None = None,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._model = model
        self._dimensions = dimensions
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._client = client

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        owns_client = self._client is None
        try:
            response = self._request(client, texts)
        finally:
            if owns_client:
                client.close()

        try:
            payload = response.json()
        except ValueError as error:
            raise EmbeddingProviderError(
                "The embedding provider returned invalid JSON."
            ) from error
        return self._parse_embeddings(payload, expected_count=len(texts))

    def _request(self, client: httpx.Client, texts: list[str]) -> httpx.Response:
        payload = {
            "model": self._model,
            "input": texts,
            "dimensions": self._dimensions,
            "encoding_format": "float",
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
                raise EmbeddingProviderError(
                    "The embedding provider could not be reached."
                ) from error
            if response.status_code == 429 or response.status_code >= 500:
                if attempt + 1 < self._max_attempts:
                    continue
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as error:
                raise EmbeddingProviderError(
                    "The embedding provider rejected the request."
                ) from error
            return response
        raise EmbeddingProviderError(
            "The embedding provider could not complete the request."
        ) from last_error

    def _parse_embeddings(
        self,
        payload: Any,
        *,
        expected_count: int,
    ) -> list[list[float]]:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise EmbeddingProviderError(
                "The embedding provider returned an invalid response object."
            )
        ordered: list[tuple[int, list[float]]] = []
        for item in payload["data"]:
            if not isinstance(item, dict):
                raise EmbeddingProviderError(
                    "The embedding provider returned an invalid data item."
                )
            index = item.get("index")
            embedding = item.get("embedding")
            if not isinstance(index, int) or not isinstance(embedding, list):
                raise EmbeddingProviderError(
                    "The embedding provider returned invalid embedding fields."
                )
            try:
                vector = [float(value) for value in embedding]
            except (TypeError, ValueError) as error:
                raise EmbeddingProviderError(
                    "The embedding provider returned non-numeric values."
                ) from error
            if len(vector) != self._dimensions:
                raise EmbeddingProviderError(
                    "The embedding provider returned an unexpected dimension."
                )
            ordered.append((index, vector))

        ordered.sort(key=lambda item: item[0])
        if [index for index, _ in ordered] != list(range(expected_count)):
            raise EmbeddingProviderError(
                "The embedding provider returned incomplete embedding results."
            )
        return [vector for _, vector in ordered]


def _tokens(text: str) -> list[str]:
    normalized = text.casefold()
    tokens = re.findall(r"[a-z0-9]+", normalized)
    for sequence in re.findall(r"[\u3400-\u9fff]+", normalized):
        tokens.extend(sequence)
        tokens.extend(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens
