# PGM — Related Work: Papers and Topics to Verify

**IMPORTANT**: This document lists papers and topics relevant to PGM.
DO NOT treat any description below as an accurate summary. Each entry
must be verified against the original paper by the research team.

## Papers to Verify

### 1. MemoryBank
- **TO VERIFY**: A system for long-term memory in LLM-based agents.
- **Why relevant**: Likely addresses memory storage and retrieval patterns
  for conversational agents.
- **Action**: Find the paper, read it, and document how PGM differs.

### 2. FadeMem
- **TO VERIFY**: A memory system with forgetting mechanisms for LLM agents.
- **Why relevant**: May implement time-based decay or importance-based
  forgetting — compare with PGM's generalization approach.
- **Action**: Find the paper, read it, and document comparison.

### 3. MemPrivacy
- **TO VERIFY**: Work on privacy in LLM memory systems.
- **Why relevant**: Directly relevant to PGM's privacy-preserving goals.
- **Action**: Find the paper, verify claims, and compare threat models.

### 4. MaRS
- **TO VERIFY**: Memory and Retrieval System (or similar).
- **Why relevant**: May address structured memory retrieval for agents.
- **Action**: Find the paper, verify the full name and approach.

### 5. Oblivion
- **TO VERIFY**: Potentially related to machine unlearning or memory
  deletion in LLMs.
- **Why relevant**: PGM's forgetting mechanism is conceptually related
  to unlearning.
- **Action**: Find the paper and compare with PGM's approach (PGM does
  NOT claim to implement machine unlearning).

## Topics to Survey

Each topic below should have 3-5 key references identified by the
research team:

### 1. Agent Memory Privacy
- How do existing LLM agent frameworks handle privacy of stored memories?
- What threat models are considered?

### 2. Memory Extraction Attacks
- Prompt injection and extraction attacks on LLM memory.
- Jailbreak-style attacks to retrieve stored personal information.

### 3. Unlearning for LLM Memory
- Machine unlearning techniques applicable to parametric vs. non-parametric
  (retrieval-based) memory.
- PGM's generalization is non-parametric; how does it compare?

### 4. Contextual Privacy
- Nissenbaum's contextual integrity and its application to AI systems.
- Context-dependent privacy norms in conversational agents.

### 5. Re-identification Risk
- Statistical re-identification attacks and defenses.
- Population-based anonymity estimation methods.
- Linkage attacks on quasi-identifiers.

## Template for Verified Entries

When a researcher verifies a paper, update the entry to:

```
### N. Paper Title
- **VERIFIED**: [date, by whom]
- **Full citation**: Authors, Title, Venue, Year. DOI/URL.
- **Summary**: [1-2 sentence summary from reading the actual paper]
- **Relevance to PGM**: [specific comparison points]
- **Key differences**: [how PGM's approach differs]
```
