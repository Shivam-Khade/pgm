"""Verifier: Checks entailment, monotonicity, and leakage for proposed rungs."""

import logging
from typing import Any

from pgm.llm import LLMClient
from pgm.ladders.models import VerificationResult

logger = logging.getLogger(__name__)

_VERIFIER_SYSTEM = """\
You are a privacy-preserving generalization verifier.
Given a specific text (Level L-1) and a proposed generalization (Level L), \
you must verify three properties:

1. Entails (entails): Is the generalization strictly logically entailed by the specific text? \
If L-1 is true, MUST L be true?
2. Monotonic (monotonic): Does the generalization remove or obscure information without \
introducing any NEW, unstated information?
3. No Leakage (no_leakage): Does the generalization obscure the unique identity? \
If L is "CEO of a major EV company", it leaks the identity of Elon Musk. \
If L is "Executive in automotive", it does not leak.

Evaluate each property and return a JSON object:
{{
  "entails": true/false,
  "monotonic": true/false,
  "no_leakage": true/false,
  "reasoning": "Brief explanation of your evaluation."
}}
"""

class RungVerifier:
    """Verifies ladder rung proposals using an LLM as a judge."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def verify(self, specific_text: str, generalized_text: str) -> VerificationResult:
        """Verify a generalized text against its more specific version."""
        
        prompt = f"Specific text (Level L-1): {specific_text}\nGeneralized text (Level L): {generalized_text}"
        
        try:
            response = await self._llm.complete_json(
                prompt,
                system=_VERIFIER_SYSTEM,
                temperature=0.0,
            )
            return self._parse_response(response)
        except Exception:
            logger.error("LLM Verifier failed to evaluate rung", exc_info=True)
            # Fail closed on verification errors
            return VerificationResult(
                is_valid=False,
                reasoning="Verification failed due to LLM error."
            )

    def _parse_response(self, response: dict[str, Any]) -> VerificationResult:
        """Parse LLM JSON response into VerificationResult."""
        entails = bool(response.get("entails", False))
        monotonic = bool(response.get("monotonic", False))
        no_leakage = bool(response.get("no_leakage", False))
        
        is_valid = entails and monotonic and no_leakage
        
        return VerificationResult(
            is_valid=is_valid,
            entails=entails,
            monotonic=monotonic,
            no_leakage=no_leakage,
            reasoning=str(response.get("reasoning", ""))
        )
