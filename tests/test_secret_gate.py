"""Tests for the secret gate.

Covers: regex patterns, entropy detector, Luhn validation, redaction, LLM fallback.
"""

import pytest
from typing import Any

from pgm.classification.secret_gate import SecretGate, _shannon_entropy, _luhn_check
from pgm.llm import MockLLMClient


class TestShannonEntropy:
    def test_empty_string(self) -> None:
        assert _shannon_entropy("") == 0.0

    def test_single_char(self) -> None:
        assert _shannon_entropy("aaaa") == 0.0

    def test_high_entropy(self) -> None:
        # Random-looking string should have high entropy
        s = "aB3$xZ9!kM7@pQ2&"
        entropy = _shannon_entropy(s)
        assert entropy > 3.5

    def test_low_entropy(self) -> None:
        s = "aaaaabbbbb"
        entropy = _shannon_entropy(s)
        assert entropy < 1.1


class TestLuhnCheck:
    def test_valid_visa(self) -> None:
        assert _luhn_check("4111111111111111") is True

    def test_valid_mastercard(self) -> None:
        assert _luhn_check("5500000000000004") is True

    def test_invalid(self) -> None:
        assert _luhn_check("1234567890123456") is False

    def test_too_short(self) -> None:
        assert _luhn_check("123456") is False


class TestSecretGateRegex:
    @pytest.fixture
    def gate(self) -> Any:
        return SecretGate(use_llm_check=False)

    @pytest.mark.asyncio
    async def test_aws_access_key(self, gate: Any) -> None:
        text = "My AWS key is AKIAIOSFODNN7EXAMPLE and it works."
        result = await gate.scan(text)
        assert result.contains_secrets
        assert any(d.pattern_name == "aws_access_key" for d in result.detections)
        assert "AKIAIOSFODNN7EXAMPLE" not in result.cleaned_text
        assert "[REDACTED:aws_access_key]" in result.cleaned_text

    @pytest.mark.asyncio
    async def test_github_token(self, gate: Any) -> None:
        text = "Use this token: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"
        result = await gate.scan(text)
        assert result.contains_secrets
        assert any(d.pattern_name == "github_token" for d in result.detections)

    @pytest.mark.asyncio
    async def test_groq_api_key(self, gate: Any) -> None:
        text = "My Groq key: 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"
        result = await gate.scan(text)
        assert result.contains_secrets
        assert any(d.pattern_name == "groq_api_key" for d in result.detections)

    @pytest.mark.asyncio
    async def test_openai_key(self, gate: Any) -> None:
        text = "export OPENAI_API_KEY=sk-1234567890abcdefghijklmnopqrstuv"
        result = await gate.scan(text)
        assert result.contains_secrets

    @pytest.mark.asyncio
    async def test_ssh_private_key(self, gate: Any) -> None:
        text = "Here's my key:\n-----BEGIN RSA PRIVATE KEY-----\nMIIBogI...\n-----END RSA PRIVATE KEY-----\n"
        result = await gate.scan(text)
        assert result.contains_secrets
        assert any(d.pattern_name == "ssh_private_key" for d in result.detections)

    @pytest.mark.asyncio
    async def test_jwt_token(self, gate: Any) -> None:
        text = "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        result = await gate.scan(text)
        assert result.contains_secrets

    @pytest.mark.asyncio
    async def test_credit_card_valid_luhn(self, gate: Any) -> None:
        text = "My card: 4111 1111 1111 1111"
        result = await gate.scan(text)
        assert result.contains_secrets
        assert any(d.pattern_name == "credit_card" for d in result.detections)

    @pytest.mark.asyncio
    async def test_credit_card_invalid_luhn(self, gate: Any) -> None:
        """Invalid Luhn should NOT be flagged as credit card."""
        text = "The code is 1234 5678 9012 3456"
        result = await gate.scan(text)
        # Should not detect as credit card (fails Luhn)
        cc_detections = [d for d in result.detections if d.pattern_name == "credit_card"]
        assert len(cc_detections) == 0

    @pytest.mark.asyncio
    async def test_us_ssn(self, gate: Any) -> None:
        text = "My SSN is 123-45-6789"
        result = await gate.scan(text)
        assert result.contains_secrets
        assert any(d.pattern_name == "us_ssn" for d in result.detections)

    @pytest.mark.asyncio
    async def test_aadhaar(self, gate: Any) -> None:
        text = "Aadhaar: 1234 5678 9012"
        result = await gate.scan(text)
        assert result.contains_secrets

    @pytest.mark.asyncio
    async def test_generic_api_key(self, gate: Any) -> None:
        text = 'config.api_key = "abcdefghijklmnopqrstuvwxyz1234567890"'
        result = await gate.scan(text)
        assert result.contains_secrets

    @pytest.mark.asyncio
    async def test_no_secrets(self, gate: Any) -> None:
        text = "I live in Pune and work at Infosys. I like biryani."
        result = await gate.scan(text)
        assert not result.contains_secrets
        assert result.cleaned_text == text

    @pytest.mark.asyncio
    async def test_hash_stored_not_raw(self, gate: Any) -> None:
        """Detections store hash of matched text, never the raw text."""
        text = "Key: AKIAIOSFODNN7EXAMPLE"
        result = await gate.scan(text)
        for det in result.detections:
            assert len(det.matched_text_hash) == 64  # SHA-256
            assert "AKIAIOSFODNN7EXAMPLE" != det.matched_text_hash


class TestSecretGateEntropy:
    @pytest.mark.asyncio
    async def test_high_entropy_string(self) -> None:
        gate = SecretGate(use_llm_check=False, entropy_threshold=4.0, entropy_min_length=16)
        # Generate a high-entropy string
        text = f"Store this: {'aB3xZ9kM7pQ2nR5tY8wE1sD4fG6hJ0'}"
        result = await gate.scan(text)
        # Should detect at least via entropy
        assert result.contains_secrets or len(result.detections) > 0


class TestSecretGateLLMFallback:
    @pytest.mark.asyncio
    async def test_llm_check_called_when_no_regex_match(self) -> None:
        """When regex finds nothing, LLM check is invoked."""
        mock_llm = MockLLMClient([
            '{"secrets": [{"type": "password", "value": "mypass", "start": 10, "end": 16}]}'
        ])
        gate = SecretGate(llm_client=mock_llm, use_llm_check=True)
        text = "Safe text without patterns"
        result = await gate.scan(text)
        # LLM was called
        assert len(mock_llm.call_log) == 1

    @pytest.mark.asyncio
    async def test_llm_not_called_when_regex_matches(self) -> None:
        """When regex finds secrets, LLM check is skipped."""
        mock_llm = MockLLMClient()
        gate = SecretGate(llm_client=mock_llm, use_llm_check=True)
        text = "Key: AKIAIOSFODNN7EXAMPLE"
        result = await gate.scan(text)
        assert result.contains_secrets
        assert len(mock_llm.call_log) == 0  # LLM not called
