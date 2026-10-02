"""LLM Proposer: generates generalization ladders when ontologies fail."""

import json
import logging
from typing import Any

from pgm.config import MemoryCategory, LadderSource
from pgm.llm import LLMClient
from pgm.ladders.models import LadderRungProposal

logger = logging.getLogger(__name__)

_PROPOSER_SYSTEM = """\
You are an expert at generalizing personal information to preserve privacy.
Given a specific personal fact (category, attribute, and value), you must produce \
a "generalization ladder" of exactly 3 levels that progressively obscure the exact details.

Level 0 is the exact text.
Level 1 is a moderate generalization (e.g., city -> state, specific car -> car brand, specific age -> age bracket).
Level 2 is a broad generalization (e.g., state -> country, car brand -> vehicle type, age bracket -> generation).
Level 3 is the broadest meaningful category (e.g., country -> continent, vehicle type -> transport, generation -> adult).

Rules for generalization:
- The generalized text MUST logically entail the finer text (if I live in Pune, I definitely live in Maharashtra).
- Do NOT introduce new, unstated information.
- Avoid "leakage" (e.g., generalizing "CEO of Tesla" to "CEO of a major EV company" is still uniquely identifying. Generalize to "Executive in automotive").

Return JSON in this exact format:
{{
  "ladder": [
    {{"level": 1, "text": "moderate generalization"}},
    {{"level": 2, "text": "broad generalization"}},
    {{"level": 3, "text": "broadest category"}}
  ]
}}
"""

class LLMProposer:
    """Proposes ladder rungs using an LLM."""
    
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def propose(
        self, 
        text: str, 
        category: MemoryCategory, 
        slot_key: str
    ) -> list[LadderRungProposal]:
        """Ask the LLM to generate a generalization ladder."""
        
        prompt = f"Category: {category.value}\nAttribute: {slot_key}\nExact Value: {text}"
        
        try:
            response = await self._llm.complete_json(
                prompt,
                system=_PROPOSER_SYSTEM,
                temperature=0.3,
            )
            return self._parse_response(response)
        except Exception:
            logger.error("LLM Proposer failed to generate ladder", exc_info=True)
            return []

    def _parse_response(self, response: dict[str, Any]) -> list[LadderRungProposal]:
        """Parse LLM JSON into LadderRungProposal objects."""
        proposals = []
        for item in response.get("ladder", []):
            try:
                level = int(item["level"])
                text = str(item["text"])
                if level > 0 and text:
                    proposals.append(
                        LadderRungProposal(
                            level=level,
                            text=text,
                            source=LadderSource.LLM
                        )
                    )
            except (KeyError, ValueError):
                continue
                
        # Ensure ordered by level
        proposals.sort(key=lambda x: x.level)
        return proposals
