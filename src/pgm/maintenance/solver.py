"""Privacy budget solver using a greedy heuristic."""

import logging
from typing import NamedTuple

from pgm.config import MemoryCategory
from pgm.db.tables import Memory, User
from pgm.risk.engine import RiskEngine, _bits
from pgm.maintenance.utility import UtilityEstimator
from pgm.storage.repository import MemoryRepository
from pgm.ladders.builder import LadderBuilder
from pgm.risk.population import PopulationEstimator

logger = logging.getLogger(__name__)


class MoveEvaluation(NamedTuple):
    memory_id: str
    current_level: int
    delta_risk: float
    delta_utility: float
    score: float


class GreedySolver:
    """Solves budget violations by iteratively generalizing memories."""
    
    def __init__(
        self,
        repository: MemoryRepository,
        risk_engine: RiskEngine,
        utility_estimator: UtilityEstimator,
        ladder_builder: LadderBuilder,
        population_estimator: PopulationEstimator,
    ) -> None:
        self._repo = repository
        self._risk = risk_engine
        self._utility = utility_estimator
        self._builder = ladder_builder
        self._pop = population_estimator

    async def _evaluate_moves(self, memories: list[Memory]) -> list[MoveEvaluation]:
        """Evaluate the cost/benefit of generalizing each memory by one level."""
        evals = []
        
        for mem in memories:
            cat = MemoryCategory(mem.category)
            
            # Get current ladder rungs
            rungs = await self._repo.get_ladder(str(mem.id))
            
            # If we don't have the next rung built, build it now
            current_level = mem.current_level
            next_level = current_level + 1
            
            has_next = any(r.level == next_level for r in rungs)
            if not has_next:
                # Try to build the rest of the ladder
                rungs = await self._builder.build_ladder_for_memory(mem, verify=True)
                
            next_rung = next((r for r in rungs if r.level == next_level), None)
            
            if not next_rung or next_rung.text is None:
                # Can't generalize further (top of ladder)
                continue
                
            # Compute current risk and utility
            curr_frac = await self._pop.estimate(mem.current_text, cat)
            curr_risk = _bits(curr_frac)
            curr_util = self._utility.estimate_utility(mem, current_level)
            
            # Compute next risk and utility
            next_frac = await self._pop.estimate(next_rung.text, cat)
            next_risk = _bits(next_frac)
            next_util = self._utility.estimate_utility(mem, next_level)
            
            # Delta Risk (should be positive, meaning risk is reduced)
            # Finer text -> smaller fraction -> higher bits.
            # Broader text -> larger fraction -> lower bits.
            # e.g., Pune (10 bits) -> India (3 bits). Delta = 7 bits.
            delta_risk = curr_risk - next_risk
            
            # Delta Utility (should be positive, meaning utility is lost)
            delta_util = curr_util - next_util
            
            if delta_risk <= 0:
                # Generalizing didn't reduce risk (or made it worse somehow), skip
                continue
                
            # Score: Risk reduced per unit of utility lost. Higher is better.
            # Add small epsilon to avoid division by zero
            score = delta_risk / (delta_util + 1e-9)
            
            evals.append(MoveEvaluation(
                memory_id=str(mem.id),
                current_level=current_level,
                delta_risk=delta_risk,
                delta_utility=delta_util,
                score=score
            ))
            
        # Sort descending by score
        evals.sort(key=lambda x: x.score, reverse=True)
        return evals

    async def solve(self, user_id: str) -> int:
        """
        Check if user is over budget. If so, generalize memories greedily 
        until budget is satisfied. Returns number of generalizations performed.
        """
        
        user = await self._repo.get_or_create_user(user_id)
        operations = 0
        
        while await self._risk.is_over_budget(user_id):
            memories = await self._risk._get_active_memories(user.id)
            if not memories:
                break
                
            moves = await self._evaluate_moves(memories)
            if not moves:
                logger.warning("User %s is over budget, but no memories can be generalized further.", user_id)
                # In a full system, we might start outright FORGETTING memories here.
                # For M4, we just stop.
                break
                
            best_move = moves[0]
            logger.info("Generalizing memory %s to level %d (Score: %.2f)", 
                        best_move.memory_id, best_move.current_level + 1, best_move.score)
                        
            await self._repo.generalize_memory(best_move.memory_id, best_move.current_level + 1)
            operations += 1
            
        return operations
