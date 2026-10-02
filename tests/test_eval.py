"""Tests for the evaluation and benchmark suite."""

import pytest
import json
from typing import Any

from pgm.config import MemoryCategory, Settings
from pgm.models import ExtractedMemory
from pgm.eval.benchmark import BenchmarkRunner
from pgm.risk.engine import RiskEngine
from pgm.risk.population import PopulationEstimator
from pgm.maintenance.utility import UtilityEstimator
from pgm.maintenance.solver import GreedySolver
from pgm.ladders.builder import LadderBuilder
from pgm.ladders.ontology import OntologyRegistry
from pgm.ladders.verifier import RungVerifier
from pgm.llm import MockLLMClient

@pytest.mark.asyncio
async def test_benchmark_runner_sweep(repository: Any, session: Any) -> None:
    """Test that the benchmark runner collects metrics across descending budgets."""
    
    settings = Settings(database_url="mock", dependence_discount=1.0)
    
    # 1. Setup mock LLM for verifier (Pune -> Maharashtra -> India)
    llm = MockLLMClient([
        json.dumps({"entails": True, "monotonic": True, "no_leakage": True}), # Pune -> Maharashtra
        json.dumps({"entails": True, "monotonic": True, "no_leakage": True}), # Maharashtra -> India
    ])
    proposer_llm = MockLLMClient([]) # Empty so it just fails cleanly for others
    
    from pgm.ladders.llm_proposer import LLMProposer
    proposer = LLMProposer(proposer_llm)
    
    # 2. Setup mock population estimator
    pop = PopulationEstimator(llm)
    async def mock_estimate(text: str, category: MemoryCategory) -> float:
        t = text.lower()
        if "pune" in t: return 0.001       # 10 bits
        if "maharashtra" in t: return 0.015 # ~6 bits
        if "india" in t: return 0.17       # ~2.5 bits
        return 0.5                         # 1 bit
    pop.estimate = mock_estimate
    
    # 3. Component assembly
    risk_engine = RiskEngine(repository, pop, settings=settings)
    builder = LadderBuilder(
        llm_client=llm,
        repository=repository,
        ontology_registry=OntologyRegistry(), 
        proposer=proposer,
        verifier=RungVerifier(llm)
    )
    utility = UtilityEstimator(settings)
    solver = GreedySolver(repository, risk_engine, utility, builder, pop)
    
    runner = BenchmarkRunner(repository, risk_engine, utility, solver, settings)
    
    # 4. Input facts
    raw_facts = [
        ExtractedMemory(
            category=MemoryCategory.LOCATION,
            slot_key="city",
            value="Pune",
            confidence=0.9
        )
    ]
    
    # 5. Run sweep
    # Budget=15 (no generalizations needed)
    # Budget=8 (needs 1 generalization -> Maharashtra, bits=6)
    # Budget=4 (needs 2 generalizations -> India, bits=2.5)
    budgets = [15.0, 8.0, 4.0]
    
    results = await runner.run_experiment(raw_facts, budgets)
    
    assert len(results) == 3
    
    # Check Budget = 15
    res15 = results[0]
    assert res15["budget_bits"] == 15.0
    assert res15["operations_run"] == 0
    assert res15["metrics"]["aggregate_risk_bits"] > 9.0
    assert res15["memory_states"][0]["text"] == "Pune"
    
    # Check Budget = 8
    res8 = results[1]
    assert res8["budget_bits"] == 8.0
    assert res8["operations_run"] == 1
    assert res8["metrics"]["aggregate_risk_bits"] < 8.0
    assert res8["memory_states"][0]["text"] == "Maharashtra"
    assert res8["metrics"]["total_utility"] < res15["metrics"]["total_utility"]
    
    # Check Budget = 4
    res4 = results[2]
    assert res4["budget_bits"] == 4.0
    assert res4["operations_run"] == 1 # 1 operation *from the previous state*
    assert res4["metrics"]["aggregate_risk_bits"] < 4.0
    assert res4["memory_states"][0]["text"] == "India"
    assert res4["metrics"]["total_utility"] < res8["metrics"]["total_utility"]
    
    # Re-identification risk drops significantly!
    assert res4["metrics"]["reid_attack_success_prob"] < res15["metrics"]["reid_attack_success_prob"]
