"""Builder: orchestrates ontology -> LLM -> verifier -> DB."""

import logging

from pgm.config import MemoryCategory
from pgm.db.tables import Ladder, Memory
from pgm.llm import LLMClient
from pgm.ladders.models import LadderRungProposal
from pgm.ladders.ontology import OntologyRegistry
from pgm.ladders.llm_proposer import LLMProposer
from pgm.ladders.verifier import RungVerifier
from pgm.storage.repository import MemoryRepository

logger = logging.getLogger(__name__)


class LadderBuilder:
    """Builds and verifies generalization ladders for memories."""

    def __init__(
        self,
        llm_client: LLMClient,
        repository: MemoryRepository,
        ontology_registry: OntologyRegistry | None = None,
        proposer: LLMProposer | None = None,
        verifier: RungVerifier | None = None,
    ) -> None:
        self._llm = llm_client
        self._repo = repository
        self._ontology = ontology_registry or OntologyRegistry()
        self._proposer = proposer or LLMProposer(llm_client)
        self._verifier = verifier or RungVerifier(llm_client)

    async def build_ladder_for_memory(
        self, 
        memory: Memory, 
        verify: bool = True
    ) -> list[Ladder]:
        """Generate, verify, and store ladder rungs for an existing memory."""
        
        # 1. Start with the level 0 text (the exact memory)
        ladder_rungs = await self._repo.get_ladder(str(memory.id))
        
        # If the ladder has already been built (more than just level 0), just return it
        if len(ladder_rungs) > 1:
            return ladder_rungs
            
        level_0 = next((r for r in ladder_rungs if r.level == 0), None)
        
        if not level_0 or not level_0.text:
            logger.error("Cannot build ladder: Memory %s has no Level 0 text", memory.id)
            return []

        exact_text = level_0.text
        category = MemoryCategory(memory.category)
        
        # 2. Try Ontology adapters first
        proposals = self._ontology.propose_all(exact_text, category, memory.slot_key)
        
        # 3. Fallback to LLM Proposer if ontology yields nothing
        if not proposals:
            logger.debug("Ontology missed %s/%s. Using LLM proposer.", category, memory.slot_key)
            proposals = await self._proposer.propose(exact_text, category, memory.slot_key)

        if not proposals:
            logger.warning("Could not generate any ladder proposals for Memory %s", memory.id)
            return []

        # 4. Verification and DB insertion
        valid_rungs: list[Ladder] = []
        current_specific_text = exact_text
        
        for prop in proposals:
            if verify:
                # Verify L entails L-1, is monotonic, has no leakage
                verdict = await self._verifier.verify(
                    specific_text=current_specific_text,
                    generalized_text=prop.text
                )
                
                prop.verification_passed = verdict.is_valid
                prop.verification_details = verdict.model_dump()
                
                if not verdict.is_valid:
                    logger.info(
                        "Proposal rejected: %s -> %s (Reason: %s)",
                        current_specific_text, prop.text, verdict.reasoning
                    )
                    # If a rung fails, we stop building higher rungs to preserve 
                    # the entailment chain.
                    break
            else:
                prop.verification_passed = True
                
            # Create the DB record
            import hashlib
            rung_db = Ladder(
                memory_id=memory.id,
                level=prop.level,
                text=prop.text,
                text_hash=hashlib.sha256(prop.text.encode()).hexdigest(),
                source=prop.source.value,
                verification_json=prop.verification_details,
            )
            self._repo._session.add(rung_db)
            valid_rungs.append(rung_db)
            
            # The next rung is verified against this rung
            current_specific_text = prop.text

        await self._repo._session.flush()
        return valid_rungs
