"""Tests for FastAPI backend."""

import pytest
from httpx import ASGITransport, AsyncClient
from typing import Any

from pgm.api.main import app, get_db_session

@pytest.mark.asyncio
async def test_chat_endpoint(session: Any, user_id: str) -> None:
    """Test the /chat endpoint."""
    app.dependency_overrides[get_db_session] = lambda: session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/chat", 
            json={"user_id": user_id, "message": "My favorite color is blue."}
        )
        
        if response.status_code != 200:
            print("ERROR RESPONSE:", response.json())
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "maintenance_ops_run" in data
        assert "blue" in data["answer"].lower() or "remember" in data["answer"].lower()

@pytest.mark.asyncio
async def test_get_memories_endpoint(session: Any, user_id: str) -> None:
    """Test the /memories endpoint."""
    app.dependency_overrides[get_db_session] = lambda: session
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/memories/{user_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
