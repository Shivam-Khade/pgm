# PGM — Assumptions

This document records assumptions made during implementation.
Researchers should review each and confirm or revise.

## A1. Reference Population

- **Default**: India, N_ref = 1,400,000,000.
- **Rationale**: Need a concrete population for identifiability computations.
  The reference population should match the user's geographic/demographic context.
- **Configurable**: Per-user via `users.config_json` and global via env `REFERENCE_POPULATION`.

## A2. Independence of Quasi-Identifiers

- **Assumption**: Population fractions of quasi-identifiers are independent:
  `k_hat = N_ref * Π p_i`.
- **Known limitation**: Attributes like city + employer are correlated
  (e.g., most employees of a Pune-based company live in Pune).
- **Mitigation**: A conservative `DEPENDENCE_DISCOUNT` factor (default 0.1) reduces
  `k_hat` by `k_hat_adjusted = k_hat * (1 - discount)^(n_qi - 1)` where `n_qi` is
  the number of quasi-identifiers. This is a heuristic, not a proven bound.
- **TODO**: Investigate copula-based dependence modeling in future work.

## A3. Sensitivity Tier Defaults

- Tiers S0–S3 are assigned per category with configurable defaults:
  - S0 (low): preferences, other
  - S1 (moderate): location, employment, education
  - S2 (elevated): relationships
  - S3 (high): health, finance, identity
- These defaults are our best-effort mapping based on the sources listed in
  `docs/TAXONOMY.md`. They are NOT derived from a specific regulatory framework.

## A4. Embedding Dimension

- Default: 384 (matches `sentence-transformers/all-MiniLM-L6-v2`).
- When pgvector extension is not available, vector search falls back to
  in-application cosine similarity computed via NumPy.
- **Configurable**: via `EMBEDDING_DIM` env var.

## A5. Secret Gate Patterns

- The regex-based secret detector covers common patterns (AWS keys, GitHub tokens,
  SSH/PGP private key blocks, credit card numbers, SSN-like patterns, JWTs, 
  high-entropy hex/base64 strings).
- This is NOT exhaustive. The gate is a defense-in-depth layer; the LLM check
  provides a second opinion.
- **Extensible**: Add patterns to `SecretGate.PATTERNS` list.

## A6. LLM as Extractor

- Memory extraction relies on an LLM to parse dialogue turns into structured
  (category, slot_key, value, confidence) tuples.
- The LLM may hallucinate memories or miss them. Confidence scores are LLM-estimated
  and should be calibrated against ground truth in evaluation.

## A7. PostgreSQL pgvector

- The schema uses pgvector's `vector` type for embeddings.
- If the pgvector extension is not installed, the migration will fail.
  A fallback stores embeddings as JSON arrays and computes similarity in Python.
- **Recommendation**: Install pgvector for production use.

## A8. Population Fraction Estimates

- For location: derived from GeoNames/Wikidata population data.
- For employer/education: derived from Wikidata entity counts or configurable
  reference tables.
- **Fallback**: When no data source is available, use a conservative default
  (configurable, default `p_fallback = 1e-6` meaning ~1400 people in India).
- **Source tracking**: Each estimate records its source for auditability.

## A9. Groq as LLM Provider

- M1 uses Groq API with `llama-3.3-70b-versatile` model.
- The LLM interface is provider-agnostic; switching to Anthropic, OpenAI-compatible,
  or local models requires only config changes.
- Model name is read from config, never hardcoded.

## A10. Database: PostgreSQL 18

- Using locally-installed PostgreSQL 18 (user's environment).
- Spec called for PostgreSQL 16; version 18 is backward-compatible for our usage.
- All SQL is standard; no PG18-specific features are relied upon.
