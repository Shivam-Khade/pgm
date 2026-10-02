"""PGM configuration — all tuneable parameters read from env / config files."""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings


# ── Enums ────────────────────────────────────────────────────────────────────


class MemoryCategory(str, enum.Enum):
    """Categories of personal information stored in memory."""

    LOCATION = "location"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    FINANCE = "finance"
    HEALTH = "health"
    RELATIONSHIPS = "relationships"
    IDENTITY = "identity"
    PREFERENCES = "preferences"
    OTHER = "other"


class SensitivityTier(int, enum.Enum):
    """Sensitivity tiers S0–S3.  Higher = more sensitive."""

    S0 = 0
    S1 = 1
    S2 = 2
    S3 = 3


# Default tier mapping (see docs/TAXONOMY.md for rationale).
DEFAULT_CATEGORY_TIERS: dict[MemoryCategory, SensitivityTier] = {
    MemoryCategory.LOCATION: SensitivityTier.S1,
    MemoryCategory.EMPLOYMENT: SensitivityTier.S1,
    MemoryCategory.EDUCATION: SensitivityTier.S1,
    MemoryCategory.FINANCE: SensitivityTier.S3,
    MemoryCategory.HEALTH: SensitivityTier.S3,
    MemoryCategory.RELATIONSHIPS: SensitivityTier.S2,
    MemoryCategory.IDENTITY: SensitivityTier.S3,
    MemoryCategory.PREFERENCES: SensitivityTier.S0,
    MemoryCategory.OTHER: SensitivityTier.S0,
}


class MemoryStatus(str, enum.Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    FORGOTTEN = "forgotten"


class EventType(str, enum.Enum):
    CREATED = "created"
    ACCESSED = "accessed"
    GENERALIZED = "generalized"
    FORGOTTEN = "forgotten"
    SUPERSEDED = "superseded"
    PINNED = "pinned"
    REJECTED = "rejected"


class LadderSource(str, enum.Enum):
    ONTOLOGY = "ontology"
    LLM = "llm"


class LLMProvider(str, enum.Enum):
    GROQ = "groq"
    OPENAI_COMPATIBLE = "openai_compatible"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class EmbedderProvider(str, enum.Enum):
    SENTENCE_TRANSFORMER = "sentence_transformer"
    MOCK = "mock"


# ── Settings ─────────────────────────────────────────────────────────────────


class Settings(BaseSettings):
    """Central configuration.  Values come from .env / environment variables."""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    # ── Database ──────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pgm"

    # ── LLM ───────────────────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.MOCK
    llm_model: str = "llama-3.3-70b-versatile"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.0
    llm_max_tokens: int = 2048

    # ── Embeddings ────────────────────────────────────────
    embedder_provider: EmbedderProvider = EmbedderProvider.MOCK
    embedder_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # ── PGM parameters ───────────────────────────────────
    reference_population: int = 1_400_000_000
    default_budget_bits: float = 20.0
    default_k_min: int = 100
    dependence_discount: float = 0.1
    population_fraction_fallback: float = 1e-6

    # ── Optimization weights ─────────────────────────────
    lambda_risk: float = 1.0
    mu_cost: float = 0.1
    rho_aggregate: float = 5.0
    tau_utility_floor: float = 0.3

    # ── Sensitivity tier defaults ────────────────────────
    category_tiers: dict[str, int] = Field(
        default_factory=lambda: {k.value: v.value for k, v in DEFAULT_CATEGORY_TIERS.items()}
    )

    # ── Server ────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Paths ─────────────────────────────────────────────
    llm_cache_dir: Path = Path("llm_cache")

    # ── Feature flags ────────────────────────────────────
    enable_sensitivity: bool = True
    enable_freshness: bool = True
    enable_usage: bool = True
    enable_confidence: bool = True
    enable_contradiction_handling: bool = True
    enable_aggregate_risk: bool = True
    enable_utility_constraint: bool = True
    enable_progressive_generalization: bool = True

    def get_tier(self, category: MemoryCategory) -> SensitivityTier:
        """Return the sensitivity tier for a category, respecting overrides."""
        raw = self.category_tiers.get(category.value, 0)
        return SensitivityTier(raw)


def get_settings() -> Settings:
    """Construct settings (call once and cache or use dependency injection)."""
    return Settings()
