"""LangGraph conversational agent with PGM integrated."""

import logging
from typing import Annotated, Sequence
from typing_extensions import TypedDict

from langgraph.graph import StateGraph, START, END

from pgm.config import MemoryCategory
from pgm.extraction.extractor import MemoryExtractor
from pgm.retrieval.retriever import MemoryRetriever
from pgm.storage.repository import MemoryRepository
from pgm.maintenance.solver import GreedySolver
from pgm.llm import LLMClient

logger = logging.getLogger(__name__)


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    """The state dictionary passed between nodes."""
    user_id: str
    message: str
    
    # Populated by nodes
    extracted_memories: list[str]  # Just IDs or strings for logging
    retrieved_context: list[str]
    answer: str
    maintenance_ops: int


# ── Nodes ─────────────────────────────────────────────────────────────────────

class PGMAgent:
    """Conversational agent backed by Progressive Generalization Memory."""
    
    def __init__(
        self,
        llm: LLMClient,
        extractor: MemoryExtractor,
        repository: MemoryRepository,
        retriever: MemoryRetriever,
        solver: GreedySolver,
    ) -> None:
        self._llm = llm
        self._extractor = extractor
        self._repo = repository
        self._retriever = retriever
        self._solver = solver
        
        # Build the LangGraph
        builder = StateGraph(AgentState)  # type: ignore
        
        builder.add_node("extract", self._node_extract)
        builder.add_node("retrieve", self._node_retrieve)
        builder.add_node("answer", self._node_answer)
        builder.add_node("maintenance", self._node_maintenance)
        
        builder.add_edge(START, "extract")
        builder.add_edge("extract", "retrieve")
        builder.add_edge("retrieve", "answer")
        
        # We branch after answer: return to user immediately, 
        # but in a real system we'd run maintenance asynchronously.
        # Here we just run it synchronously as the final node.
        builder.add_edge("answer", "maintenance")
        builder.add_edge("maintenance", END)
        
        self.graph = builder.compile()

    async def _node_extract(self, state: AgentState) -> dict:
        """Extract facts from the user message and save to memory."""
        extracted = await self._extractor.extract(state["message"])
        
        ids = []
        for mem in extracted.memories:
            stored = await self._repo.create_memory(mem, state["user_id"])
            ids.append(str(stored.id))
            
        if ids:
            await self._repo._session.flush()
            
        return {"extracted_memories": ids}

    async def _node_retrieve(self, state: AgentState) -> dict:
        """Retrieve relevant context for the user's message."""
        results = await self._retriever.search(
            state["message"], 
            state["user_id"], 
            top_k=5, 
            update_access=True
        )
        
        # Format the context
        context = []
        for r in results:
            context.append(f"- {r.memory.slot_key}: {r.memory.current_text}")
            
        await self._repo._session.flush()
            
        return {"retrieved_context": context}

    async def _node_answer(self, state: AgentState) -> dict:
        """Generate the final answer to the user."""
        
        context_str = "\n".join(state.get("retrieved_context", []))
        if not context_str:
            context_str = "(No relevant memory found.)"
            
        system_prompt = f"""You are a helpful conversational AI.
You have access to a privacy-preserving long-term memory system.
Use the provided memory context to answer the user naturally. Do not mention the memory system itself.

Memory Context:
{context_str}
"""
        
        answer = await self._llm.complete(
            state["message"],
            system=system_prompt,
            temperature=0.7
        )
        
        return {"answer": answer}

    async def _node_maintenance(self, state: AgentState) -> dict:
        """Run the privacy budget solver if new memories were added."""
        ops = 0
        if state.get("extracted_memories"):
            # Only run if we actually extracted something
            ops = await self._solver.solve(state["user_id"])
            
        return {"maintenance_ops": ops}
