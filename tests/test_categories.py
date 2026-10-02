"""Tests for category assignment and tier logic."""

import pytest

from pgm.config import MemoryCategory, SensitivityTier, Settings
from pgm.classification.categories import assign_tier, tier_weight


class TestAssignTier:
    def test_default_tiers(self) -> None:
        """Default tiers match the documented mapping."""
        s = Settings(_env_file=None)
        assert assign_tier(MemoryCategory.HEALTH, settings=s) == SensitivityTier.S3
        assert assign_tier(MemoryCategory.FINANCE, settings=s) == SensitivityTier.S3
        assert assign_tier(MemoryCategory.IDENTITY, settings=s) == SensitivityTier.S3
        assert assign_tier(MemoryCategory.RELATIONSHIPS, settings=s) == SensitivityTier.S2
        assert assign_tier(MemoryCategory.LOCATION, settings=s) == SensitivityTier.S1
        assert assign_tier(MemoryCategory.EMPLOYMENT, settings=s) == SensitivityTier.S1
        assert assign_tier(MemoryCategory.EDUCATION, settings=s) == SensitivityTier.S1
        assert assign_tier(MemoryCategory.PREFERENCES, settings=s) == SensitivityTier.S0
        assert assign_tier(MemoryCategory.OTHER, settings=s) == SensitivityTier.S0

    def test_user_override(self) -> None:
        """User-level overrides take precedence over defaults."""
        overrides = {"location": 3, "preferences": 2}
        tier = assign_tier(MemoryCategory.LOCATION, user_overrides=overrides)
        assert tier == SensitivityTier.S3

    def test_settings_override(self) -> None:
        """Settings-level overrides work."""
        s = Settings(_env_file=None, category_tiers={"health": 1})
        tier = assign_tier(MemoryCategory.HEALTH, settings=s)
        assert tier == SensitivityTier.S1

    def test_user_override_beats_settings(self) -> None:
        """User overrides take precedence over settings."""
        s = Settings(_env_file=None, category_tiers={"health": 1})
        overrides = {"health": 0}
        tier = assign_tier(MemoryCategory.HEALTH, user_overrides=overrides, settings=s)
        assert tier == SensitivityTier.S0


class TestTierWeight:
    def test_weights(self) -> None:
        assert tier_weight(SensitivityTier.S0) == 0.25
        assert tier_weight(SensitivityTier.S1) == 0.5
        assert tier_weight(SensitivityTier.S2) == 0.75
        assert tier_weight(SensitivityTier.S3) == 1.0

    def test_monotonic(self) -> None:
        """Weights are strictly increasing with tier."""
        weights = [tier_weight(SensitivityTier(i)) for i in range(4)]
        for i in range(len(weights) - 1):
            assert weights[i] < weights[i + 1]
