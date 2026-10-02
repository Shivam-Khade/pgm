"""Embedding interface and adapters."""

from __future__ import annotations

import abc
from typing import Any

import numpy as np

from pgm.config import EmbedderProvider, Settings, get_settings


class Embedder(abc.ABC):
    """Abstract interface for computing text embeddings."""

    @property
    @abc.abstractmethod
    def dim(self) -> int:
        """Dimensionality of output vectors."""

    @abc.abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embedding vectors for each text."""

    async def embed_one(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]


class MockEmbedder(Embedder):
    """Deterministic mock: returns a hash-based vector for reproducible tests."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        results = []
        for text in texts:
            # Deterministic pseudo-random vector from text hash
            seed = hash(text) % (2**31)
            rng = np.random.RandomState(seed)
            vec = rng.randn(self._dim).astype(np.float32)
            # L2-normalize
            vec = vec / (np.linalg.norm(vec) + 1e-9)
            results.append(vec.tolist())
        return results


class SentenceTransformerEmbedder(Embedder):
    """Adapter for sentence-transformers models."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dim: int = 384) -> None:
        self._model_name = model_name
        self._dim = dim
        self._model = None

    def _get_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # type: ignore
            self._model = SentenceTransformer(self._model_name)
        return self._model

    @property
    def dim(self) -> int:
        return self._dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return list(embeddings.tolist())


def create_embedder(settings: Settings | None = None) -> Embedder:
    """Create the configured embedder."""
    settings = settings or get_settings()
    match settings.embedder_provider:
        case EmbedderProvider.MOCK:
            return MockEmbedder(dim=settings.embedding_dim)
        case EmbedderProvider.SENTENCE_TRANSFORMER:
            return SentenceTransformerEmbedder(
                model_name=settings.embedder_model,
                dim=settings.embedding_dim,
            )
        case _:
            raise ValueError(f"Unsupported embedder: {settings.embedder_provider}")
