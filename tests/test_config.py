"""Tests for the configuration system."""

import pytest

from pgm.config import (
    DEFAULT_CATEGORY_TIERS,
    MemoryCategory,
    SensitivityTier,
    Settings,
    MemoryStatus,
    EventType,
    LadderSource,
    LLMProvider,
    EmbedderProvider,
)


class TestSettings:
    def test_defaults(self) -> None:
        """Settings load with sane defaults."""
        s = Settings(
            database_url="postgresql+asyncpg://test:test@localhost/test",
            _env_file=None,
        )
        assert s.reference_population == 1_400_000_000
        assert s.default_budget_bits == 20.0
        assert s.default_k_min == 100
        assert s.embedding_dim == 384

    def test_category_tiers_default(self) -> None:
        """Default tiers match the documented mapping."""
        s = Settings(_env_file=None)
        assert s.get_tier(MemoryCategory.HEALTH) == SensitivityTier.S3
        assert s.get_tier(MemoryCategory.PREFERENCES) == SensitivityTier.S0
        assert s.get_tier(MemoryCategory.LOCATION) == SensitivityTier.S1
        assert s.get_tier(MemoryCategory.RELATIONSHIPS) == SensitivityTier.S2

    def test_category_tier_override(self) -> None:
        """Category tiers can be overridden via config."""
        s = Settings(
            _env_file=None,
            category_tiers={"location": 3, "preferences": 2},
        )
        assert s.get_tier(MemoryCategory.LOCATION) == SensitivityTier.S3
        assert s.get_tier(MemoryCategory.PREFERENCES) == SensitivityTier.S2

    def test_feature_flags_default_true(self) -> None:
        """All feature flags default to True."""
        s = Settings(_env_file=None)
        assert s.enable_sensitivity is True
        assert s.enable_freshness is True
        assert s.enable_aggregate_risk is True
        assert s.enable_progressive_generalization is True


class TestEnums:
    def test_memory_category_values(self) -> None:
        """All 9 categories exist."""
        assert len(MemoryCategory) == 9
        assert MemoryCategory.HEALTH.value == "health"

    def test_sensitivity_tier_ordering(self) -> None:
        """Tiers S0 < S1 < S2 < S3."""
        assert SensitivityTier.S0 < SensitivityTier.S1
        assert SensitivityTier.S1 < SensitivityTier.S2
        assert SensitivityTier.S2 < SensitivityTier.S3

    def test_memory_status_values(self) -> None:
        assert MemoryStatus.ACTIVE.value == "active"
        assert MemoryStatus.SUPERSEDED.value == "superseded"
        assert MemoryStatus.FORGOTTEN.value == "forgotten"

    def test_event_types(self) -> None:
        assert len(EventType) == 7

    def test_default_category_tiers_complete(self) -> None:
        """Every category has a default tier."""
        for cat in MemoryCategory:
            assert cat in DEFAULT_CATEGORY_TIERS
