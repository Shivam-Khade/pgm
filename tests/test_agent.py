"""Tests for LangGraph agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from typing import Any, cast

from pgm.agent.graph import PGMAgent, AgentState
from pgm.db.tables import Memory
from pgm.config import MemoryCategory

@pytest.fixture
def agent(repository: Any) -> PGMAgent:
    llm = AsyncMock()
    llm.complete.return_value = "This is a test response."
    
    extractor = AsyncMock()
    
    mock_result = MagicMock()
    mock_result.memories = []
    extractor.extract.return_value = mock_result
    
    retriever = AsyncMock()
    retriever_result = MagicMock()
    retriever_result.memory = MagicMock()
    retriever_result.memory.slot_key = "city"
    retriever_result.memory.current_text = "Pune"
    retriever.search.return_value = [retriever_result]
    
    solver = AsyncMock()
    solver.solve.return_value = 0
    
    return PGMAgent(llm, extractor, repository, retriever, solver)

@pytest.mark.asyncio
async def test_agent_graph_execution(agent: PGMAgent, user_id: str) -> None:
    """Test the full agent execution path."""
    state = {
        "user_id": user_id,
        "message": "I live in Pune."
    }
    
    result = await agent.graph.ainvoke(state)
    
    assert "answer" in result
    assert result["answer"] == "This is a test response."
    assert "retrieved_context" in result
    
    cast(AsyncMock, agent._extractor.extract).assert_called_once_with("I live in Pune.")
    cast(AsyncMock, agent._retriever.search).assert_called_once()
    cast(AsyncMock, agent._llm.complete).assert_called_once()
    
    # In this mock, extractor returns [], so extracted_memories should be []
    # Thus maintenance ops might not run, or it might be called and return 0
    # Let's check the state
    if result.get("extracted_memories"):
        cast(AsyncMock, agent._solver.solve).assert_called_once_with(user_id)
