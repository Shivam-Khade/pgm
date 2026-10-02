"""Population fraction estimator.

Estimates P(x), the fraction of the reference population that satisfies memory x.
For M3, we use a simple set of heuristic probabilities and an LLM fallback
to estimate rarity of a given trait.
"""

import logging
from typing import Any

from pgm.config import MemoryCategory
from pgm.llm import LLMClient

logger = logging.getLogger(__name__)

_ESTIMATOR_SYSTEM = """\
You are a demographic statistician.
Given a specific attribute and its value, estimate the percentage of the global \
population (or a large reference population) that shares this exact trait.

Return a JSON object with a single float field `fraction` (between 0.0 and 1.0).
For example, if 5% of people have this trait, return 0.05.

Respond ONLY with valid JSON:
{"fraction": 0.05}
"""

class PopulationEstimator:
    """Estimates population fraction for a given memory text."""
    
    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    async def estimate(self, text: str, category: MemoryCategory) -> float:
        """Estimate the population fraction for `text`."""
        
        # LLM estimation
        prompt = f"Category: {category.value}\nTrait: {text}"
        
        try:
            response = await self._llm.complete_json(
                prompt,
                system=_ESTIMATOR_SYSTEM,
                temperature=0.0
            )
            return self._parse_response(response)
        except Exception:
            logger.warning("LLM Population Estimator failed for %s. Using default 0.01", text)
            # Safe fallback: assume somewhat rare (1%) if we can't estimate
            return 0.01

    def _parse_response(self, response: dict[str, Any]) -> float:
        """Parse LLM JSON into a float fraction."""
        try:
            fraction = float(response.get("fraction", 0.01))
            # Clamp between a minimum (1 in 8 billion) and 1.0
            return max(1e-10, min(1.0, fraction))
        except (ValueError, TypeError):
            return 0.01
