"""Metrics for evaluating privacy and utility tradeoffs."""

from dataclasses import dataclass
from pgm.db.tables import Memory
from pgm.risk.engine import RiskSnapshot
from pgm.maintenance.utility import UtilityEstimator

@dataclass
class EvalMetrics:
    total_memories: int
    total_utility: float
    average_utility: float
    aggregate_risk_bits: float
    k_anonymity: float
    reid_attack_success_prob: float


def compute_metrics(
    memories: list[Memory],
    snapshot: RiskSnapshot,
    utility_estimator: UtilityEstimator
) -> EvalMetrics:
    """Compute the evaluation metrics for a user's current memory state."""
    
    total_utility = 0.0
    for mem in memories:
        total_utility += utility_estimator.estimate_utility(mem, mem.current_level)
        
    avg_utility = total_utility / len(memories) if memories else 0.0
    
    # Re-identification attack success probability is roughly 1 / k_hat
    # (If k people share these traits, the chance of picking the right one is 1/k)
    k_hat = snapshot.k_hat
    if k_hat <= 1.0:
        reid_prob = 1.0
    else:
        reid_prob = 1.0 / k_hat
        
    return EvalMetrics(
        total_memories=len(memories),
        total_utility=total_utility,
        average_utility=avg_utility,
        aggregate_risk_bits=snapshot.r_agg_bits,
        k_anonymity=k_hat,
        reid_attack_success_prob=reid_prob
    )
