"""Risk Engine: Computes re-identification risk metrics."""

import math
import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from pgm.config import MemoryCategory, Settings, get_settings
from pgm.db.tables import RiskSnapshot, Memory, User
from pgm.risk.population import PopulationEstimator
from pgm.storage.repository import MemoryRepository

logger = logging.getLogger(__name__)


def _bits(fraction: float) -> float:
    """Convert a population fraction into information bits (-log2)."""
    if fraction <= 0.0:
        return 0.0
    return -math.log2(fraction)


class RiskEngine:
    """Computes k-anonymity (k_hat) and aggregate risk (R_agg)."""
    
    # Categories considered "quasi-identifiers" for k-anonymity.
    # Updated to include Finance and Identity based on strict privacy needs.
    QUASI_IDENTIFIERS = {
        MemoryCategory.LOCATION,
        MemoryCategory.EMPLOYMENT,
        MemoryCategory.EDUCATION,
        MemoryCategory.HEALTH,
        MemoryCategory.FINANCE,
        MemoryCategory.IDENTITY,
    }

    def __init__(
        self,
        repository: MemoryRepository,
        estimator: PopulationEstimator,
        settings: Settings | None = None,
    ) -> None:
        self._repo = repository
        self._estimator = estimator
        self._settings = settings or get_settings()

    async def _get_active_memories(self, user_id: uuid.UUID) -> list[Memory]:
        """Fetch all active memories for a user."""
        return await self._repo.get_user_memories(str(user_id))

    async def compute_risk(self, user_id: str) -> RiskSnapshot:
        """Compute the current risk metrics for the user and save a snapshot.
        
        R_agg = Sum(bits(memory_fraction)) * dependence_discount
        k_hat = ReferencePopulation * Product(qi_fractions)
        """
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        memories = await self._get_active_memories(uid)
        
        total_bits = 0.0
        qi_fractions: dict[str, float] = {}
        qi_product = 1.0
        
        # We need the population fractions for all current memory texts
        for mem in memories:
            text = mem.current_text
            category = MemoryCategory(mem.category)
            
            # Get or compute fraction
            # Ideally this is cached on the Ladder rung, but for simplicity
            # we'll compute it dynamically if not known
            frac = await self._estimator.estimate(text, category)
            
            # Aggregate bits (with simple dependence discount later if needed)
            total_bits += _bits(frac)
            
            # Track Quasi-Identifiers for k-anonymity
            if category in self.QUASI_IDENTIFIERS:
                qi_fractions[mem.current_text] = frac
                qi_product *= frac

        # Apply dependence discount (traits are rarely independent)
        r_agg = total_bits * self._settings.dependence_discount
        
        # Compute k_hat (how many people share ALL these quasi-identifiers)
        k_hat = self._settings.reference_population * qi_product
        
        # Create DB snapshot
        snapshot = RiskSnapshot(
            user_id=uid,
            k_hat=k_hat,
            r_agg_bits=r_agg,
            quasi_identifiers_json=qi_fractions,
        )
        self._repo._session.add(snapshot)
        await self._repo._session.flush()
        
        return snapshot
        
    async def is_over_budget(self, user_id: str) -> bool:
        """Check if the user's memory store exceeds their identification budget."""
        user = await self._repo.get_or_create_user(user_id)
        snapshot = await self.compute_risk(user_id)
        
        return (
            snapshot.r_agg_bits > user.identification_budget_bits or 
            snapshot.k_hat < user.k_min
        )
