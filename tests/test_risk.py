"""Tests for the risk engine and population estimator."""

import json
import pytest
from typing import Any
from typing import Any

from pgm.config import MemoryCategory
from pgm.llm import MockLLMClient
from pgm.models import ExtractedMemory
from pgm.risk.population import PopulationEstimator
from pgm.risk.engine import RiskEngine, _bits


class TestPopulationEstimator:
    @pytest.mark.asyncio
    async def test_heuristic_cache(self) -> None:
        """Uses hardcoded values for common traits."""
        est = PopulationEstimator(MockLLMClient())
        assert await est.estimate("India", MemoryCategory.LOCATION) == 0.17
        assert await est.estimate("Software Engineer", MemoryCategory.EMPLOYMENT) == 0.003
        
    @pytest.mark.asyncio
    async def test_llm_fallback(self) -> None:
        """Calls LLM when heuristic misses."""
        llm = MockLLMClient([json.dumps({"fraction": 0.02})])
        est = PopulationEstimator(llm)
        
        val = await est.estimate("Unknown City", MemoryCategory.LOCATION)
        assert val == 0.02
        assert len(llm.call_log) == 1

    @pytest.mark.asyncio
    async def test_llm_failure_returns_default(self) -> None:
        llm = MockLLMClient(["Invalid JSON"])
        est = PopulationEstimator(llm)
        val = await est.estimate("Weird Trait", MemoryCategory.OTHER)
        assert val == 0.01  # Safe default fallback

    def test_bits_calculation(self) -> None:
        assert _bits(0.5) == 1.0
        assert _bits(0.25) == 2.0
        assert _bits(1.0) == 0.0


class TestRiskEngine:
    @pytest.mark.asyncio
    async def test_compute_risk(self, repository: Any, session: Any, user_id: str, test_settings: Any) -> None:
        # Setup: Create some memories
        mem1 = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="India",  # frac = 0.17 -> ~2.55 bits
            confidence=0.9
        )
        mem2 = ExtractedMemory(
            category=MemoryCategory.EMPLOYMENT,
            slot_key="role",
            value="Software Engineer",  # frac = 0.003 -> ~8.38 bits
            confidence=0.9
        )
        await repository.create_memory(mem1, user_id)
        await repository.create_memory(mem2, user_id)
        await session.flush()
        
        est = PopulationEstimator(MockLLMClient())
        engine = RiskEngine(repository, est, settings=test_settings)
        
        snapshot = await engine.compute_risk(user_id)
        
        # Bits = (2.55 + 8.38) * discount(0.1) = ~1.09 bits
        assert snapshot.r_agg_bits > 1.0
        assert snapshot.r_agg_bits < 1.2
        
        # k_hat = 1.4B * 0.17 * 0.003 = ~714,000
        assert snapshot.k_hat > 700_000
        assert snapshot.k_hat < 720_000
        
        # Both are QIs
        assert len(snapshot.quasi_identifiers_json) == 2

    @pytest.mark.asyncio
    async def test_is_over_budget(self, repository: Any, session: Any, user_id: str, test_settings: Any) -> None:
        # Add a highly identifying memory
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="exact",
            value="Very rare thing",
            confidence=0.9
        )
        await repository.create_memory(mem, user_id)
        await session.flush()
        
        # Mock estimator to return an incredibly tiny fraction
        class RareEstimator(PopulationEstimator):
            async def estimate(self, text: str, category: MemoryCategory) -> float:
                return 0.000000001 # 1 in a billion, ~30 bits
                
        engine = RiskEngine(repository, RareEstimator(MockLLMClient()), settings=test_settings)
        
        # 30 bits > 20 bits default limit -> True
        assert await engine.is_over_budget(user_id) is True
