# PGM — Sensitivity Category Taxonomy

This document lists the sources and rationale behind PGM's sensitivity
category and tier assignments. **Researchers must verify each cited source
against the original document.**

## Categories

| Category       | Description                                  | Default Tier |
|---------------|----------------------------------------------|-------------|
| `location`     | Geographic information (city, address, etc.)  | S1          |
| `employment`   | Employer, job title, work history             | S1          |
| `education`    | Schools, degrees, academic history            | S1          |
| `finance`      | Income, assets, debts, transactions           | S3          |
| `health`       | Medical conditions, medications, disabilities | S3          |
| `relationships`| Family, partners, social connections          | S2          |
| `identity`     | Name, age, gender, ethnicity, nationality     | S3          |
| `preferences`  | Likes, dislikes, hobbies, dietary choices     | S0          |
| `other`        | Anything not fitting above categories         | S0          |

## Tier Definitions

| Tier | Label      | Semantics                                                  |
|------|-----------|-------------------------------------------------------------|
| S0   | Low        | Generally non-sensitive; low re-identification risk alone   |
| S1   | Moderate   | Could contribute to re-identification in combination        |
| S2   | Elevated   | Sensitive in many social contexts; handle with care          |
| S3   | High       | Highly sensitive; maximum protection short of secret gate    |

## Sources to Verify

The following sources informed the category/tier design. Each is labeled
**TO VERIFY** — researchers must confirm the cited concepts against the
original documents.

### 1. GDPR Special Categories of Data (Article 9)
- **TO VERIFY**: GDPR identifies "special categories" including racial/ethnic
  origin, political opinions, religious beliefs, trade union membership,
  genetic data, biometric data, health data, sex life/orientation.
- **Source URL**: https://gdpr-info.eu/art-9-gdpr/
- **How it informed PGM**: Health and identity categories at S3 are partly
  motivated by GDPR's treatment of health and biometric data as requiring
  extra protection. PGM does NOT claim GDPR compliance.

### 2. NIST SP 800-122: Guide to Protecting PII
- **TO VERIFY**: NIST defines PII and discusses confidentiality impact levels
  for PII (low, moderate, high) based on potential harm from disclosure.
- **Source URL**: https://csrc.nist.gov/pubs/sp/800/122/final
- **How it informed PGM**: The tiered approach (S0–S3) is loosely inspired
  by NIST's impact-level framework. We do NOT claim to implement NIST's
  specific assessment methodology.

### 3. Contextual Integrity (Nissenbaum)
- **TO VERIFY**: Helen Nissenbaum's contextual integrity framework argues
  that privacy norms are context-dependent, not absolute.
- **Reference**: Nissenbaum, H. "Privacy as Contextual Integrity" (2004).
  Exact citation must be verified by researchers.
- **How it informed PGM**: The per-user tier overrides and per-context
  sensitivity adjustment are motivated by the idea that sensitivity depends
  on context. PGM does NOT implement full contextual integrity analysis.

### 4. ISO/IEC 27701 — Privacy Information Management
- **TO VERIFY**: This standard extends ISO 27001 with privacy-specific
  controls including PII classification.
- **How it informed PGM**: General inspiration for structured PII
  categorization. No specific mapping claimed.

## Notes

- The categories are NOT a complete PII taxonomy. They are designed for
  the common types of personal information that emerge in conversational
  agent memory.
- The tier defaults are starting points. Per-user customization is
  essential for real deployment.
- The secret gate (credentials, keys, tokens, government IDs) is a
  separate hard filter, NOT a tier level. See `classification/secret_gate.py`.
