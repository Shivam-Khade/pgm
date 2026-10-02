"""Utility estimator for memories."""

import math
from datetime import datetime, timezone

from pgm.config import MemoryCategory, Settings, get_settings
from pgm.db.tables import Memory

def _now() -> datetime:
    return datetime.now(timezone.utc)

class UtilityEstimator:
    """Estimates the expected utility of a memory at a given precision level."""
    
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def estimate_utility(self, memory: Memory, level: int = 0) -> float:
        """
        Calculate expected utility:
        U = BaseImportance * UsageFactor * PrecisionPenalty
        """
        
        # 1. Base Importance (derived from Category Tier)
        # Tier S0 (Preferences) might be less critical than S3 (Identity) for functional tasks,
        # or vice versa depending on the agent's goal. For general persona agents,
        # preferences are highly useful. We'll use a simple heuristic based on tier weights.
        # Here we invert it: lower sensitivity (S0) = higher utility for casual chat.
        # But for now, we assign fixed base values.
        category = MemoryCategory(memory.category)
        base_importance = {
            MemoryCategory.PREFERENCES: 1.0,
            MemoryCategory.LOCATION: 0.8,
            MemoryCategory.EMPLOYMENT: 0.8,
            MemoryCategory.EDUCATION: 0.7,
            MemoryCategory.RELATIONSHIPS: 0.9,
            MemoryCategory.HEALTH: 0.6,
            MemoryCategory.FINANCE: 0.5,
            MemoryCategory.IDENTITY: 0.4,
            MemoryCategory.OTHER: 0.5,
        }.get(category, 0.5)

        # 2. Usage Factor (Access count + Recency)
        # Add 1.0 to avoid zeroing out unused memories
        access_bonus = math.log1p(memory.access_count)
        
        # Time decay
        last_time = memory.last_accessed_at or memory.created_at
        age_days = (_now() - last_time).total_seconds() / 86400
        # Half-life of 30 days
        recency_multiplier = math.exp(-math.log(2) * age_days / 30.0)
        
        usage_factor = 1.0 + (access_bonus * recency_multiplier)

        # 3. Precision Penalty
        # Utility drops as we climb the generalization ladder
        # Level 0 = 1.0, Level 1 = 0.5, Level 2 = 0.25
        precision_penalty = 1.0 / (2 ** level)
        
        utility = base_importance * usage_factor * precision_penalty
        
        # Ensure it doesn't fall below a floor unless it's truly useless
        return max(self._settings.tau_utility_floor, utility)
