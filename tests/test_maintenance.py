"""Tests for the maintenance module (utility and solver)."""

import json
import pytest
from datetime import datetime, timezone, timedelta
from typing import Any

from pgm.config import MemoryCategory, Settings
from pgm.db.tables import Memory, User
from pgm.models import ExtractedMemory
from pgm.maintenance.utility import UtilityEstimator, _now
from pgm.maintenance.solver import GreedySolver
from pgm.risk.engine import RiskEngine
from pgm.risk.population import PopulationEstimator
from pgm.ladders.builder import LadderBuilder
from pgm.ladders.ontology import OntologyRegistry
from pgm.ladders.verifier import RungVerifier
from pgm.llm import MockLLMClient


class TestUtilityEstimator:
    def test_precision_penalty(self) -> None:
        est = UtilityEstimator()
        
        # Mock memory
        mem = Memory(
            category=MemoryCategory.PREFERENCES.value,
            access_count=0,
            last_accessed_at=_now()
        )
        
        # Base utility for preferences is 1.0, access_bonus=0, recency=1.0 -> 1.0
        u0 = est.estimate_utility(mem, level=0)
        u1 = est.estimate_utility(mem, level=1)
        u2 = est.estimate_utility(mem, level=2)
        
        assert u0 == 1.0
        assert u1 == 0.5
        assert u2 == 0.3  # tau_utility_floor is 0.3

    def test_access_bonus(self) -> None:
        est = UtilityEstimator()
        mem_low = Memory(
            category=MemoryCategory.PREFERENCES.value,
            access_count=0,
            last_accessed_at=_now()
        )
        mem_high = Memory(
            category=MemoryCategory.PREFERENCES.value,
            access_count=10,
            last_accessed_at=_now()
        )
        
        u_low = est.estimate_utility(mem_low, level=0)
        u_high = est.estimate_utility(mem_high, level=0)
        
        assert u_high > u_low
        assert u_high > 1.0

    def test_recency_decay(self) -> None:
        est = UtilityEstimator()
        
        now = _now()
        mem_new = Memory(
            category=MemoryCategory.PREFERENCES.value,
            access_count=10,
            last_accessed_at=now
        )
        mem_old = Memory(
            category=MemoryCategory.PREFERENCES.value,
            access_count=10,
            last_accessed_at=now - timedelta(days=30)
        )
        
        u_new = est.estimate_utility(mem_new, level=0)
        u_old = est.estimate_utility(mem_old, level=0)
        
        # Old memory should have half the usage bonus
        assert u_new > u_old


class TestGreedySolver:
    @pytest.mark.asyncio
    async def test_solver_generalizes_until_budget_met(self, repository: Any, session: Any, user_id: str) -> None:
        # We need a custom settings to lower the budget so it triggers easily
        settings = Settings(
            database_url="mock",
            default_budget_bits=10.0,  # Strict budget
            dependence_discount=1.0    # No discount for simpler math
        )
        
        # User
        user = User(id=user_id, identification_budget_bits=settings.default_budget_bits)
        session.add(user)
        
        # 1. Create memory
        mem = ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9
        )
        memory = await repository.create_memory(mem, user_id)
        await session.flush()
        
        # 2. Setup components
        llm = MockLLMClient([
            json.dumps({"entails": True, "monotonic": True, "no_leakage": True}), # Verifier pass
        ])
        
        pop = PopulationEstimator(llm)
        # Mock estimator to return specific values for our test
        # Pune -> ~0.001 (10 bits)
        # Maharashtra -> ~0.015 (~6 bits)
        async def mock_estimate(text: str, category: MemoryCategory) -> float:
            if "pune" in text.lower(): return 0.001
            if "maharashtra" in text.lower(): return 0.015
            if "india" in text.lower(): return 0.17
            return 0.5
            
        pop.estimate = mock_estimate
        
        # Separate mocks so they don't consume each other's responses
        verifier_llm = MockLLMClient([
            json.dumps({"entails": True, "monotonic": True, "no_leakage": True}), # For Pune -> Maharashtra
            json.dumps({"entails": True, "monotonic": True, "no_leakage": True}), # For Maharashtra -> India
        ])
        
        proposer_llm = MockLLMClient([]) # Empty so it just fails cleanly for SE
        from pgm.ladders.llm_proposer import LLMProposer
        proposer = LLMProposer(proposer_llm)
        
        builder = LadderBuilder(
            llm_client=verifier_llm,  # fallback
            repository=repository,
            ontology_registry=OntologyRegistry(), 
            proposer=proposer,
            verifier=RungVerifier(verifier_llm)
        )
        utility = UtilityEstimator(settings)
        engine = RiskEngine(repository, pop, settings=settings)
        
        solver = GreedySolver(repository, engine, utility, builder, pop)
        
        # Verify initially over budget (1 memory = 10 bits, but wait, budget is 10.0. 
        # Let's add another memory to definitely push it over).
        mem2 = ExtractedMemory(
            category=MemoryCategory.EMPLOYMENT,
            slot_key="role",
            value="Software Engineer",
            confidence=0.9
        )
        await repository.create_memory(mem2, user_id)
        await session.flush()
        
        # 3. Run solver
        ops = await solver.solve(user_id)
        
        # 4. Verify results
        assert ops > 0
        
        # Fetch the updated location memory
        updated_mem = await repository._session.get(Memory, memory.id)
        assert updated_mem.current_level > 0
        assert updated_mem.current_text in ("Maharashtra", "India")
        
        # Verify we are now under budget
        assert await engine.is_over_budget(user_id) is False
