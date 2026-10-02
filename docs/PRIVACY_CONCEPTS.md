# PGM — Privacy Concepts: Applicability Analysis

This document states, for each major privacy concept, whether it applies
to PGM's per-user memory store and why.

## 1. k-Anonymity

**Partially applicable — used as an analogy, not a guarantee.**

- Classic k-anonymity requires that each record in a *released dataset* be
  indistinguishable from at least k−1 other records on quasi-identifiers.
- PGM does NOT release a dataset. The memory store is per-user and private.
- However, PGM uses k-anonymity *reasoning* to estimate re-identification
  risk: we compute `k_hat`, the estimated anonymity set size of the user
  against a reference population, given the quasi-identifiers stored in
  memory. When `k_hat < k_min`, the system triggers generalization.
- This is a *risk estimation heuristic*, not a formal k-anonymity guarantee.
  The reference population is approximate, and the independence assumption
  between quasi-identifiers introduces error (see `docs/ASSUMPTIONS.md` A2).

## 2. l-Diversity

**Not directly applicable.**

- l-diversity requires that each equivalence class in a released dataset
  contain at least l "well-represented" values of the sensitive attribute.
- PGM stores one user's memories, not a multi-record dataset. There is no
  equivalence class to diversify.
- The concept is relevant as a *future consideration*: if PGM's memory
  store were ever shared or aggregated across users, l-diversity would
  become relevant.

## 3. t-Closeness

**Not applicable.**

- t-closeness requires that the distribution of a sensitive attribute in
  each equivalence class be close to its distribution in the overall table.
- Same reasoning as l-diversity: not applicable to a single-user store.

## 4. Differential Privacy (DP)

**NOT claimed. Does not apply to per-user memory.**

- DP provides a mathematical guarantee that the presence or absence of any
  individual's data does not significantly affect the output of a query.
- PGM's memory store IS the individual's data. Adding DP noise to a single
  user's memories does not provide meaningful privacy (the "database" has
  one person).
- DP would be relevant if PGM were used to compute aggregate statistics
  across multiple users' memories. This is out of scope for v1.
- **PGM does NOT claim differential privacy at any point.** Any mention of
  DP in related work is for comparison only.

## 5. Membership Inference Attacks

**Relevant as a threat model.**

- An attacker with access to the memory store (or query access to the agent)
  may try to determine whether a specific fact was ever stored.
- PGM mitigates this through:
  - Generalization (the original fact may no longer be stored)
  - Deletion of finer ladder levels after generalization
  - Deletion of old embeddings on generalization
- PGM does NOT provide formal membership inference resistance.
  The eval harness includes membership inference attacks to measure
  empirical resistance.

## 6. Attribute Inference Attacks

**Relevant as a threat model.**

- An attacker may try to infer specific attribute values (e.g., exact city)
  from the generalized memory store.
- PGM mitigates this through:
  - Progressive generalization (city → state → country)
  - Aggregate risk monitoring (correlated attributes trigger further
    generalization)
  - Leakage probes during ladder verification
- The eval harness includes attribute inference attacks.

## 7. Linkage Attacks

**The primary threat PGM is designed to mitigate.**

- An attacker combines multiple quasi-identifiers (location, employer,
  education, etc.) to narrow down a user's identity.
- PGM's aggregate risk computation directly models this: `k_hat` estimates
  the anonymity set size under linkage of all active quasi-identifiers.
- The generalization policy explicitly targets linkage risk by generalizing
  or forgetting memories when `k_hat` drops below `k_min`.

## 8. Reconstruction from Embeddings

**Relevant as a threat model; mitigated by design.**

- Dense embeddings can leak information about the source text. An attacker
  with access to embeddings might reconstruct original memories.
- PGM mitigates this by:
  - Recomputing embeddings from generalized text after each generalization
  - Physically deleting old embedding vectors
  - Never storing original text alongside generalized embeddings
- The eval harness includes embedding reconstruction attacks to verify.

## Summary Table

| Concept               | Applies? | Role in PGM                              |
|-----------------------|----------|------------------------------------------|
| k-Anonymity           | Analogy  | Risk estimation, not formal guarantee     |
| l-Diversity           | No       | Single-user store, no equivalence classes |
| t-Closeness           | No       | Single-user store                         |
| Differential Privacy  | No       | Cannot apply to single-user data          |
| Membership Inference  | Threat   | Empirically tested, not formally resisted |
| Attribute Inference   | Threat   | Mitigated via generalization + probes     |
| Linkage Attacks       | Primary  | Core threat; aggregate risk models this   |
| Embedding Recon.      | Threat   | Mitigated by re-embedding + deletion      |
