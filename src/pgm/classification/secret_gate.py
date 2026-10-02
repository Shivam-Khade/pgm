"""Secret Gate — hard filter that blocks credentials / keys / tokens / IDs.

Implemented via:
1. Regex patterns for known secret formats
2. Shannon entropy detector for high-entropy strings
3. LLM check as fallback for ambiguous cases

Secrets are NEVER persisted.  They are redacted before extraction.
"""

from __future__ import annotations

import hashlib
import math
from pgm.llm import LLMClient
import re
import logging
from collections import Counter
from dataclasses import dataclass

from pgm.models import SecretDetection, SecretGateResult

logger = logging.getLogger(__name__)


@dataclass
class _Pattern:
    name: str
    regex: re.Pattern[str]
    description: str


# ── Regex patterns ────────────────────────────────────────────────────────────

_PATTERNS: list[_Pattern] = [
    _Pattern(
        name="aws_access_key",
        regex=re.compile(r"(?<![A-Z0-9])(AKIA[0-9A-Z]{16})(?![A-Z0-9])"),
        description="AWS Access Key ID",
    ),
    _Pattern(
        name="aws_secret_key",
        regex=re.compile(r"(?<![A-Za-z0-9/+=])([A-Za-z0-9/+=]{40})(?![A-Za-z0-9/+=])"),
        description="AWS Secret Access Key (40-char base64)",
    ),
    _Pattern(
        name="github_token",
        regex=re.compile(
            r"(gh[pousr]_[A-Za-z0-9_]{36,255}|github_pat_[A-Za-z0-9_]{22,255})"
        ),
        description="GitHub personal access token",
    ),
    _Pattern(
        name="groq_api_key",
        regex=re.compile(r"(gsk_[A-Za-z0-9]{48,})"),
        description="Groq API key",
    ),
    _Pattern(
        name="openai_api_key",
        regex=re.compile(r"(sk-[A-Za-z0-9]{32,})"),
        description="OpenAI API key",
    ),
    _Pattern(
        name="anthropic_api_key",
        regex=re.compile(r"(sk-ant-[A-Za-z0-9\-]{32,})"),
        description="Anthropic API key",
    ),
    _Pattern(
        name="ssh_private_key",
        regex=re.compile(
            r"(-----BEGIN (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----)",
            re.DOTALL,
        ),
        description="SSH/PGP private key block",
    ),
    _Pattern(
        name="pgp_private_key",
        regex=re.compile(
            r"(-----BEGIN PGP PRIVATE KEY BLOCK-----[\s\S]*?-----END PGP PRIVATE KEY BLOCK-----)",
            re.DOTALL,
        ),
        description="PGP private key block",
    ),
    _Pattern(
        name="jwt_token",
        regex=re.compile(
            r"(eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
        ),
        description="JWT token",
    ),
    _Pattern(
        name="credit_card",
        regex=re.compile(
            r"(?<!\d)(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4})(?!\d)"
        ),
        description="Credit/debit card number (16 digits)",
    ),
    _Pattern(
        name="us_ssn",
        regex=re.compile(r"(?<!\d)(\d{3}-\d{2}-\d{4})(?!\d)"),
        description="US Social Security Number format",
    ),
    _Pattern(
        name="aadhaar",
        regex=re.compile(r"(?<!\d)(\d{4}\s\d{4}\s\d{4})(?!\d)"),
        description="Indian Aadhaar number format",
    ),
    _Pattern(
        name="generic_api_key",
        regex=re.compile(
            r"(?:api[_\-]?key|apikey|secret|token|password|passwd|authorization)\s*[:=]\s*['\"]?([A-Za-z0-9\-_./+=]{20,})['\"]?",
            re.IGNORECASE,
        ),
        description="Generic API key / secret in key=value format",
    ),
]


# ── Entropy detector ─────────────────────────────────────────────────────────


def _shannon_entropy(s: str) -> float:
    """Compute Shannon entropy in bits per character."""
    if not s:
        return 0.0
    counts = Counter(s)
    length = len(s)
    return -sum(
        (count / length) * math.log2(count / length)
        for count in counts.values()
        if count > 0
    )


def _find_high_entropy_tokens(
    text: str,
    *,
    min_length: int = 16,
    min_entropy: float = 4.0,
) -> list[tuple[int, int, str]]:
    """Find tokens (whitespace-separated) with suspiciously high entropy."""
    results: list[tuple[int, int, str]] = []
    for match in re.finditer(r"\S{" + str(min_length) + r",}", text):
        token = match.group()
        entropy = _shannon_entropy(token)
        if entropy >= min_entropy:
            results.append((match.start(), match.end(), token))
    return results


# ── Luhn check for credit cards ──────────────────────────────────────────────


def _luhn_check(number_str: str) -> bool:
    """Validate a credit card number using the Luhn algorithm."""
    digits = [int(d) for d in number_str if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# ── Secret Gate ───────────────────────────────────────────────────────────────


class SecretGate:
    """Hard gate that detects and redacts secrets from text.

    Usage::

        gate = SecretGate()
        result = await gate.scan(text)
        if result.contains_secrets:
            use result.cleaned_text instead of the original
    """

    PATTERNS = _PATTERNS  # allow extension

    def __init__(
        self,
        *,
        llm_client: LLMClient | None = None,
        entropy_min_length: int = 16,
        entropy_threshold: float = 4.0,
        use_llm_check: bool = True,
    ) -> None:
        self._llm = llm_client
        self._entropy_min_length = entropy_min_length
        self._entropy_threshold = entropy_threshold
        self._use_llm_check = use_llm_check and llm_client is not None

    async def scan(self, text: str) -> SecretGateResult:
        """Scan *text* for secrets.  Returns cleaned text with redactions."""
        detections: list[SecretDetection] = []

        # 1. Regex scan
        for pattern in self.PATTERNS:
            for match in pattern.regex.finditer(text):
                matched = match.group(1) if match.lastindex else match.group()

                # Extra validation for credit cards
                if pattern.name == "credit_card":
                    if not _luhn_check(matched):
                        continue

                det = SecretDetection(
                    pattern_name=pattern.name,
                    matched_text_hash=hashlib.sha256(matched.encode()).hexdigest(),
                    start=match.start(),
                    end=match.end(),
                    detection_method="regex",
                )
                detections.append(det)

        # 2. Entropy scan
        for start, end, token in _find_high_entropy_tokens(
            text,
            min_length=self._entropy_min_length,
            min_entropy=self._entropy_threshold,
        ):
            # Don't double-detect already found ranges
            if any(d.start <= start < d.end for d in detections):
                continue
            det = SecretDetection(
                pattern_name="high_entropy",
                matched_text_hash=hashlib.sha256(token.encode()).hexdigest(),
                start=start,
                end=end,
                detection_method="entropy",
            )
            detections.append(det)

        # 3. LLM check (for text that passed regex + entropy but might still
        #    contain secrets in natural-language form)
        if self._use_llm_check and self._llm is not None and not detections:
            llm_detections = await self._llm_secret_check(text)
            detections.extend(llm_detections)

        # Sort detections by position (reverse) for safe redaction
        detections.sort(key=lambda d: d.start, reverse=True)

        # Redact
        cleaned = text
        for det in detections:
            cleaned = cleaned[: det.start] + f"[REDACTED:{det.pattern_name}]" + cleaned[det.end:]

        return SecretGateResult(
            contains_secrets=len(detections) > 0,
            detections=sorted(detections, key=lambda d: d.start),
            cleaned_text=cleaned,
            original_text=text,
        )

    async def _llm_secret_check(self, text: str) -> list[SecretDetection]:
        """Use LLM to check for secrets not caught by regex/entropy."""
        if self._llm is None:
            return []

        system_prompt = (
            "You are a security classifier. Analyze the following text and identify any "
            "credentials, API keys, tokens, private keys, government IDs, or payment card "
            "numbers that should be redacted. Respond with JSON: "
            '{"secrets": [{"type": "...", "value": "...", "start": N, "end": N}]} '
            "If no secrets are found, respond with {\"secrets\": []}."
        )
        try:
            result = await self._llm.complete_json(text, system=system_prompt, temperature=0.0)
            detections = []
            for s in result.get("secrets", []):
                det = SecretDetection(
                    pattern_name=f"llm_{s.get('type', 'unknown')}",
                    matched_text_hash=hashlib.sha256(
                        s.get("value", "").encode()
                    ).hexdigest(),
                    start=s.get("start", 0),
                    end=s.get("end", 0),
                    detection_method="llm",
                )
                detections.append(det)
            return detections
        except Exception:
            logger.warning("LLM secret check failed; proceeding without it", exc_info=True)
            return []
