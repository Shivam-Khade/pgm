Privacy-Aware Progressive Generalization of Long-Term Memory in LLM Agents
Problem Statement, Proposed Solution and Literature Survey
1. Introduction
LLM-based agents increasingly rely on long-term memory to personalize their behaviour across sessions. Remembering a user's preferences, location, projects and habits makes an agent more useful, but it also means the agent accumulates personal information for as long as the memory store exists. Most current systems either keep every memory indefinitely or delete it outright once it is judged unimportant.
2. Problem Statement
Existing agent memory systems treat forgetting as a binary choice: a memory is either kept in full detail or removed completely. This creates three problems.
Privacy exposure. Precise personal facts (an exact city, employer or health detail) stay in storage long after they stop being needed, increasing the harm of a leak, misuse or over-sharing by the agent.
Loss of utility. Deleting a memory removes everything it offered. An agent that forgets the user lives in India, because the exact city was deleted, personalizes worse than one that remembers the coarse fact.
Blunt protection methods. Masking and placeholder approaches hide values but also remove task-relevant meaning, and they are applied once rather than evolving as a memory ages or loses relevance.
Core question: Can an agent reduce the precision of a stored memory over time, in proportion to its sensitivity and usefulness, so that privacy risk falls while most of the utility is preserved?
3. Proposed Solution
3.1 Key idea
Instead of keeping or deleting a memory, the system lets it fade in precision. Each fact is linked to a generalization ladder that runs from specific to vague, and a lifecycle engine moves the fact one rung up the ladder when the evidence says its detail is no longer worth the risk.
Example ladder: Pune → Maharashtra → India → Asia → forgotten.
Another example: “Works at Infosys on a fraud-detection project” → “Works in IT” → “Has a technical job” → forgotten.
3.2 Architecture
The pipeline extends the original memory-lifecycle design with a generalization step:
Memory extraction: pulls candidate facts from the conversation and attaches an entity type (location, employer, preference, deadline, health).
Ladder construction: builds a generalization ladder for each fact using a knowledge hierarchy or an LLM, and checks that each step is strictly less identifying.
Memory evaluation: scores each fact on the six factors in the table below.
Lifecycle engine: chooses an action per memory: keep, generalize one step, update, retain with context, expire or forget.
Memory store and agent: stores only the current precision level; the agent retrieves from it like any other memory.
Memory Manager (UI): shows each memory, its current precision, the factor scores behind the last decision and when it will next coarsen.
3.3 Decision factors

3.4 Worked scenario
A user says they are moving to Pune. While they plan the move, the city is frequently used and stays precise. After the move is settled and the agent stops referring to it, the usage factor drops and sensitivity stays high, so the memory becomes “Maharashtra” and later “India”. The agent can still say “as someone based in India”, but it can no longer reveal the exact city. A time-bound fact such as “project deadline is October 5” is handled by an expiry rule once the date passes.
3.5 Intended contributions
A time-driven, per-fact generalization mechanism for agent memory, driven by sensitivity, usage, freshness, confidence and contradiction risk.
A measured privacy-utility tradeoff showing how much task accuracy is retained as leakage falls.
An explainable Memory Manager that shows why each memory was kept, generalized or removed.
4. Literature Survey of Existing Systems
The table summarizes related work found in arXiv and Google Scholar searches. Details are taken from paper abstracts and summaries; the full papers should be read before final citation.


Also to review: “MemGov: Policy-Governed Memory Lifecycle Management for Enterprise LLM Agents” and “LifeSide: Benchmarking Agents as Lifelong Digital Companions” appeared in the Google Scholar results for our title search, but their contents have not yet been examined.
5. Research Gap and Novelty
Across the surveyed work, forgetting is applied to whole memories (decay, eviction, summarization) or privacy is applied once at write time (masking, placeholders). No paper found so far makes stored facts progressively less precise over time under sensitivity-aware scheduling.
Versus decay systems (FadeMem, MemoryBank): we lower detail, not existence.
Versus MemPrivacy and AgentCrypt: we generalize gradually rather than masking once.
Versus MaRS and Oblivion: our goal is privacy-driven precision loss, not token savings or accessibility.
Related prior idea: generalization hierarchies from classical data anonymization (such as k-anonymity), which we extend to a temporal, agent-memory setting.
This is a gap in the sources checked, not a proof that no related work exists. Patent databases and the newest preprints should still be searched.
6. Proposed Evaluation
Utility: accuracy on personalization and long-term memory question answering at each precision level.
Privacy: leakage and re-identification rates, including attacks that combine several coarse facts.
Baselines: keep-all, delete-by-decay (FadeMem-style), summary compression (MaRS-style) and placeholder masking (MemPrivacy-style).
Ablations: remove each of the six factors to show the joint scheduler outperforms single-signal policies.
User study: whether the Memory Manager explanations improve user understanding and trust.
7. Open Challenges
Building reliable generalization ladders automatically for arbitrary fact types.
Preventing re-identification when several coarse facts are combined.
Choosing coarsening rates without hurting active tasks.
Obtaining or constructing a benchmark with conflicting, expiring and sensitive memories.
References
Packer et al. (2023). MemGPT: Towards LLMs as Operating Systems.
Zhong et al. (2024). MemoryBank: Enhancing Large Language Models with Long-Term Memory.
FadeMem: Biologically-Inspired Forgetting for Efficient Agent Memory. arXiv:2601.18642 (2026).
Kumar, Ba, Pan. MemArchitect: A Policy Driven Memory Governance Layer. arXiv:2603.18330 (2026).
Alqithami. Forgetful but Faithful: A Cognitive Memory Architecture and Benchmark for Privacy-Aware Generative Agents. arXiv:2512.12856 (2025).
Rana et al. Oblivion: Self-Adaptive Agentic Memory Control through Decay-Driven Activation. arXiv:2604.00131 (2026).
Adaptive Memory Admission Control for LLM Agents. arXiv:2603.04549 (2026).
Fofadiya et al. Novel Memory Forgetting Techniques for Autonomous AI Agents. arXiv:2604.02280 (2026).
Governing Evolving Memory in LLM Agents (SSGM). arXiv:2603.11768 (2026).
Chen et al. MemPrivacy: Privacy-preserving personalized memory management for edge-cloud agents. arXiv:2605.09530 (2026).
Xu et al. Toward Personalized LLM-Powered Agents: Foundations, Evaluation, and Future Directions. arXiv:2602.22680 (2026).
Karthikeyan et al. AgentCrypt: Advancing Privacy and (Secure) Computation in AI Agent Collaboration. arXiv:2512.08104 (2025).