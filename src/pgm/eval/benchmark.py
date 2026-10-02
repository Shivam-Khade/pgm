"""Benchmark script to simulate privacy-utility tradeoffs."""

import logging
import uuid
from typing import TypedDict

from pgm.db.tables import User
from pgm.models import ExtractedMemory
from pgm.config import Settings
from pgm.storage.repository import MemoryRepository
from pgm.risk.engine import RiskEngine
from pgm.maintenance.utility import UtilityEstimator
from pgm.maintenance.solver import GreedySolver
from pgm.eval.metrics import compute_metrics, EvalMetrics

logger = logging.getLogger(__name__)


class BenchmarkResult(TypedDict):
    budget_bits: float
    metrics: dict
    operations_run: int
    memory_states: list[dict]


class BenchmarkRunner:
    """Runs privacy vs utility tradeoff experiments."""
    
    def __init__(
        self,
        repository: MemoryRepository,
        risk_engine: RiskEngine,
        utility_estimator: UtilityEstimator,
        solver: GreedySolver,
        settings: Settings
    ) -> None:
        self._repo = repository
        self._risk = risk_engine
        self._utility = utility_estimator
        self._solver = solver
        self._settings = settings

    async def run_experiment(
        self, 
        raw_facts: list[ExtractedMemory],
        budgets_to_test: list[float]
    ) -> list[BenchmarkResult]:
        """
        Simulate a user with a set of raw facts.
        Sweep over the provided budgets (descending), run the solver,
        and capture the metrics at each step.
        """
        # Ensure descending order so we can iteratively generalize
        budgets = sorted(budgets_to_test, reverse=True)
        
        user_id = str(uuid.uuid4())
        
        # Initialize user with the highest budget first
        user = User(id=user_id, identification_budget_bits=budgets[0])
        self._repo._session.add(user)
        
        # Load all raw facts as level-0 memories
        for fact in raw_facts:
            await self._repo.create_memory(fact, user_id)
            
        await self._repo._session.flush()
        
        results = []
        
        for budget in budgets:
            logger.info("Running benchmark step for budget: %.1f bits", budget)
            
            # Update user's budget
            user.identification_budget_bits = budget
            await self._repo._session.flush()
            
            # Run the solver until the new budget is met
            ops = await self._solver.solve(user_id)
            
            # Compute final metrics for this budget
            active_mems = await self._risk._get_active_memories(uuid.UUID(user_id))
            snapshot = await self._risk.compute_risk(user_id)
            
            metrics = compute_metrics(active_mems, snapshot, self._utility)
            
            # Capture exact states
            memory_states = [
                {
                    "category": m.category,
                    "slot": m.slot_key,
                    "level": m.current_level,
                    "text": m.current_text
                }
                for m in active_mems
            ]
            
            # Record result
            results.append(BenchmarkResult(
                budget_bits=budget,
                metrics={
                    "total_utility": metrics.total_utility,
                    "aggregate_risk_bits": metrics.aggregate_risk_bits,
                    "k_anonymity": metrics.k_anonymity,
                    "reid_attack_success_prob": metrics.reid_attack_success_prob
                },
                operations_run=ops,
                memory_states=memory_states
            ))
            
        return results
