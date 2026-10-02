"""Category assignment and sensitivity tier logic."""

from __future__ import annotations

from pgm.config import DEFAULT_CATEGORY_TIERS, MemoryCategory, SensitivityTier, Settings, get_settings


def assign_tier(
    category: MemoryCategory,
    *,
    user_overrides: dict[str, int] | None = None,
    settings: Settings | None = None,
) -> SensitivityTier:
    """Return the sensitivity tier for *category*, applying user overrides first.

    Priority: user_overrides > settings.category_tiers > DEFAULT_CATEGORY_TIERS
    """
    # 1. Check user-specific overrides
    if user_overrides and category.value in user_overrides:
        return SensitivityTier(user_overrides[category.value])

    # 2. Check settings (may have been overridden globally)
    settings = settings or get_settings()
    if category.value in settings.category_tiers:
        return SensitivityTier(settings.category_tiers[category.value])

    # 3. Fallback to hardcoded defaults
    return DEFAULT_CATEGORY_TIERS.get(category, SensitivityTier.S0)


def all_categories() -> list[MemoryCategory]:
    """Return all memory categories."""
    return list(MemoryCategory)


def tier_weight(tier: SensitivityTier) -> float:
    """Map sensitivity tier to a numeric weight for risk calculations.

    S0 → 0.25, S1 → 0.5, S2 → 0.75, S3 → 1.0
    """
    return 0.25 * (tier.value + 1)
