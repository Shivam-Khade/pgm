"""Ontology Registry for managing external knowledge bases.

For M2, we have migrated entirely away from mock dictionary adapters 
and use the LLMProposer for 100% dynamic, real-time ladder generation.
"""

from pgm.config import MemoryCategory

class OntologyRegistry:
    """Registry of ontology adapters."""
    
    def __init__(self) -> None:
        # We explicitly leave this empty so it always falls back to the LLMProposer
        self._adapters = []

    def get_adapters(self, category: MemoryCategory, slot_key: str) -> list:
        return []
        
    def propose_all(self, exact_text: str, category: MemoryCategory, slot_key: str) -> list:
        """Returns empty list to force fallback to LLMProposer."""
        return []
