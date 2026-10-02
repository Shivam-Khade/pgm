"""Tests for the memory extraction pipeline."""

import json
import pytest
from typing import Any, Callable

from pgm.config import MemoryCategory
from pgm.extraction.extractor import MemoryExtractor
from pgm.classification.secret_gate import SecretGate
from pgm.llm import MockLLMClient


class TestMemoryExtractor:
    @pytest.fixture
    def extractor_with_response(self) -> Callable[[dict[str, Any]], MemoryExtractor]:
        """Create an extractor with a pre-loaded LLM response."""
        def _factory(response: dict[str, Any]) -> MemoryExtractor:
            mock_llm = MockLLMClient([json.dumps(response)])
            gate = SecretGate(use_llm_check=False)
            return MemoryExtractor(mock_llm, gate)
        return _factory

    @pytest.mark.asyncio
    async def test_basic_extraction(self, extractor_with_response: Callable[[dict[str, Any]], MemoryExtractor]) -> None:
        """Extract a simple personal fact."""
        ext = extractor_with_response({
            "memories": [
                {
                    "category": "location",
                    "slot_key": "city",
                    "value": "Pune",
                    "confidence": 0.95,
                }
            ]
        })
        result = await ext.extract("I live in Pune.")
        assert len(result.memories) == 1
        m = result.memories[0]
        assert m.category == MemoryCategory.LOCATION
        assert m.slot_key == "city"
        assert m.value == "Pune"
        assert m.confidence == 0.95
        assert len(result.redacted_secrets) == 0

    @pytest.mark.asyncio
    async def test_multiple_memories(self, extractor_with_response: Callable[[dict[str, Any]], MemoryExtractor]) -> None:
        """Extract multiple facts from one message."""
        ext = extractor_with_response({
            "memories": [
                {"category": "location", "slot_key": "city", "value": "Pune", "confidence": 0.9},
                {"category": "employment", "slot_key": "employer", "value": "Infosys", "confidence": 0.85},
            ]
        })
        result = await ext.extract("I live in Pune and work at Infosys.")
        assert len(result.memories) == 2

    @pytest.mark.asyncio
    async def test_secret_redacted_before_extraction(self) -> None:
        """Secrets are redacted before LLM sees the text."""
        llm_responses = [json.dumps({"memories": []})]
        mock_llm = MockLLMClient(llm_responses)
        gate = SecretGate(use_llm_check=False)
        ext = MemoryExtractor(mock_llm, gate)

        text = "My API key is AKIAIOSFODNN7EXAMPLE and I live in Pune."
        result = await ext.extract(text)

        # Secret was redacted
        assert len(result.redacted_secrets) > 0

        # LLM received cleaned text (no raw secret)
        llm_prompt = mock_llm.call_log[0]["prompt"]
        assert "AKIAIOSFODNN7EXAMPLE" not in llm_prompt
        assert "[REDACTED:" in llm_prompt

    @pytest.mark.asyncio
    async def test_invalid_category_falls_back(self, extractor_with_response: Callable[[dict[str, Any]], MemoryExtractor]) -> None:
        """Unknown category falls back to 'other'."""
        ext = extractor_with_response({
            "memories": [
                {"category": "invalid_cat", "slot_key": "foo", "value": "bar", "confidence": 0.5}
            ]
        })
        result = await ext.extract("Something")
        assert len(result.memories) == 1
        assert result.memories[0].category == MemoryCategory.OTHER

    @pytest.mark.asyncio
    async def test_confidence_clamped(self, extractor_with_response: Callable[[dict[str, Any]], MemoryExtractor]) -> None:
        """Confidence is clamped to [0, 1]."""
        ext = extractor_with_response({
            "memories": [
                {"category": "location", "slot_key": "city", "value": "Pune", "confidence": 1.5}
            ]
        })
        result = await ext.extract("I live in Pune")
        assert result.memories[0].confidence == 1.0

    @pytest.mark.asyncio
    async def test_empty_extraction(self, extractor_with_response: Callable[[dict[str, Any]], MemoryExtractor]) -> None:
        """No memories extracted from irrelevant text."""
        ext = extractor_with_response({"memories": []})
        result = await ext.extract("What's the weather like?")
        assert len(result.memories) == 0

    @pytest.mark.asyncio
    async def test_llm_failure_returns_empty(self) -> None:
        """LLM failure returns empty result, not an error."""
        mock_llm = MockLLMClient(["not valid json {{{"])
        gate = SecretGate(use_llm_check=False)
        ext = MemoryExtractor(mock_llm, gate)

        result = await ext.extract("I live in Pune")
        # Should not raise, just return empty
        assert len(result.memories) == 0
