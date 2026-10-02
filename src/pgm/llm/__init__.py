"""LLM client interface and adapters.

Never hardcode model names — they are read from config.
"""

from __future__ import annotations

import abc
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from pgm.config import LLMProvider, Settings, get_settings

logger = logging.getLogger(__name__)


class LLMClient(abc.ABC):
    """Abstract interface for LLM access."""

    @abc.abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """Return the text completion for *prompt*."""

    @abc.abstractmethod
    async def complete_json(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """Return parsed JSON from the LLM response."""


# ── Caching mixin ─────────────────────────────────────────────────────────────


class CachingMixin:
    """Disk-based caching for reproducible experiments."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_key(self, prompt: str, system: str, temperature: float | None) -> str:
        payload = f"{system}||{prompt}||{temperature}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def _read_cache(self, key: str) -> str | None:
        if not self._cache_dir:
            return None
        path = self._cache_dir / f"{key}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            response = data.get("response")
            return str(response) if response is not None else None
        return None

    def _write_cache(self, key: str, prompt: str, system: str, response: str) -> None:
        if not self._cache_dir:
            return
        path = self._cache_dir / f"{key}.json"
        path.write_text(
            json.dumps({"prompt": prompt, "system": system, "response": response}, indent=2),
            encoding="utf-8",
        )


# ── Groq Adapter ──────────────────────────────────────────────────────────────


class GroqAdapter(CachingMixin, LLMClient):
    """Adapter for Groq API (OpenAI-compatible)."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        cache_dir = settings.llm_cache_dir if settings.llm_cache_dir else None
        super().__init__(cache_dir=cache_dir)
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key
        self._default_temp = settings.llm_temperature
        self._default_max_tokens = settings.llm_max_tokens
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            from groq import AsyncGroq
            self._client = AsyncGroq(api_key=self._api_key)
        return self._client

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        temp = temperature if temperature is not None else self._default_temp
        cache_key = self._cache_key(prompt, system, temp)
        cached = self._read_cache(cache_key)
        if cached is not None:
            logger.debug("LLM cache hit: %s", cache_key[:12])
            return cached

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tokens or self._default_max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        client = self._get_client()
        resp = await client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""

        self._write_cache(cache_key, prompt, system, text)
        return text

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        raw = await self.complete(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return dict(json.loads(raw))


# ── OpenAI-compatible Adapter (Ollama / vLLM) ────────────────────────────────


class OpenAICompatibleAdapter(CachingMixin, LLMClient):
    """Adapter for any OpenAI-compatible endpoint (Ollama, vLLM, etc.)."""

    def __init__(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        cache_dir = settings.llm_cache_dir if settings.llm_cache_dir else None
        super().__init__(cache_dir=cache_dir)
        self._model = settings.llm_model
        self._api_key = settings.llm_api_key
        self._base_url = settings.llm_base_url
        self._default_temp = settings.llm_temperature
        self._default_max_tokens = settings.llm_max_tokens

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        import httpx

        temp = temperature if temperature is not None else self._default_temp
        cache_key = self._cache_key(prompt, system, temp)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temp,
            "max_tokens": max_tokens or self._default_max_tokens,
        }
        if response_format:
            body["response_format"] = response_format

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self._base_url}/v1/chat/completions",
                json=body,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["choices"][0]["message"]["content"]
        self._write_cache(cache_key, prompt, system, text)
        return str(text)

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        raw = await self.complete(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return dict(json.loads(raw))


# ── Mock LLM Client (for tests) ──────────────────────────────────────────────


class MockLLMClient(LLMClient):
    """Deterministic mock for unit tests.

    Provide *responses* as a list; they are popped in order.
    If exhausted, returns a default JSON response.
    """

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses: list[str] = list(responses or [])
        self.call_log: list[dict[str, Any]] = []

    def add_response(self, response: str) -> None:
        self._responses.append(response)

    async def complete(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        self.call_log.append({"prompt": prompt, "system": system})
        if self._responses:
            return self._responses.pop(0)
        return '{"memories": []}'

    async def complete_json(
        self,
        prompt: str,
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        raw = await self.complete(prompt, system=system, temperature=temperature)
        return dict(json.loads(raw))


# ── Factory ───────────────────────────────────────────────────────────────────


def create_llm_client(settings: Settings | None = None) -> LLMClient:
    """Create the configured LLM client."""
    settings = settings or get_settings()
    match settings.llm_provider:
        case LLMProvider.GROQ:
            return GroqAdapter(settings)
        case LLMProvider.OPENAI_COMPATIBLE:
            return OpenAICompatibleAdapter(settings)
        case LLMProvider.MOCK:
            return MockLLMClient()
        case _:
            raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
