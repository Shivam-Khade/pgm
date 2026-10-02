"""Memory extractor: secret gate → LLM extraction → structured output.

The pipeline:
1. Run the secret gate on raw text → redacted text
2. Send redacted text to LLM for memory extraction
3. Parse LLM response into structured ExtractedMemory objects
4. Return ExtractionResult with memories + redaction info
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pgm.classification.secret_gate import SecretGate
from pgm.config import MemoryCategory
from pgm.llm import LLMClient
from pgm.models import ExtractedMemory, ExtractionResult

logger = logging.getLogger(__name__)

# System prompt for memory extraction
_EXTRACTION_SYSTEM = """\
You are a memory extraction system. Given a dialogue turn from a user, extract \
personal facts that should be remembered for future conversations.

For each fact, output:
- category: one of {categories}
- slot_key: a short attribute key (e.g., "city", "employer", "favorite_food")
- value: the extracted value as stated by the user
- confidence: your confidence that this is a real personal fact (0.0–1.0)

Rules:
- Only extract facts the user explicitly states about themselves.
- Do NOT extract opinions about third parties, hypotheticals, or questions.
- Do NOT extract anything that looks like a credential, password, API key, or secret.
- If the user corrects a previous statement, extract the NEW value with high confidence.
- Use the most specific category that fits.

Respond with JSON: {{"memories": [{{...}}, ...]}}
If no personal facts are found, respond with {{"memories": []}}.
"""


class MemoryExtractor:
    """Extract structured memories from dialogue text.

    Secret gate runs BEFORE extraction — secrets are redacted from the text
    sent to the LLM.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        secret_gate: SecretGate | None = None,
    ) -> None:
        self._llm = llm_client
        self._gate = secret_gate or SecretGate(llm_client=llm_client)

    async def extract(self, text: str) -> ExtractionResult:
        """Extract memories from *text*.

        Returns an ExtractionResult containing:
        - memories: list of extracted facts
        - redacted_secrets: descriptions of any secrets found (NOT the secrets)
        - original_text: the raw input
        - cleaned_text: text after secret redaction
        """
        # 1. Secret gate
        gate_result = await self._gate.scan(text)
        cleaned = gate_result.cleaned_text

        redacted_descriptions = [
            f"Redacted {d.pattern_name} at position {d.start}-{d.end}"
            for d in gate_result.detections
        ]

        # 2. LLM extraction on cleaned text
        categories = ", ".join(c.value for c in MemoryCategory)
        system_prompt = _EXTRACTION_SYSTEM.format(categories=categories)

        try:
            response = await self._llm.complete_json(
                f"User message:\n{cleaned}",
                system=system_prompt,
                temperature=0.0,
            )
        except Exception:
            logger.error("LLM extraction failed", exc_info=True)
            return ExtractionResult(
                memories=[],
                redacted_secrets=redacted_descriptions,
                original_text=text,
                cleaned_text=cleaned,
            )

        # 3. Parse into structured objects
        memories = self._parse_response(response)

        return ExtractionResult(
            memories=memories,
            redacted_secrets=redacted_descriptions,
            original_text=text,
            cleaned_text=cleaned,
        )

    def _parse_response(self, response: dict[str, Any]) -> list[ExtractedMemory]:
        """Parse LLM JSON response into ExtractedMemory objects."""
        memories: list[ExtractedMemory] = []

        for item in response.get("memories", []):
            try:
                # Validate category
                raw_cat = item.get("category", "other").lower()
                try:
                    category = MemoryCategory(raw_cat)
                except ValueError:
                    category = MemoryCategory.OTHER

                memory = ExtractedMemory(
                    category=category,
                    slot_key=str(item.get("slot_key", "unknown")),
                    value=str(item.get("value", "")),
                    confidence=max(0.0, min(1.0, float(item.get("confidence", 0.5)))),
                )
                memories.append(memory)
            except Exception:
                logger.warning("Failed to parse extracted memory: %s", item, exc_info=True)
                continue

        return memories
