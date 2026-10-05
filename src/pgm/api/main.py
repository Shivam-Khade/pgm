"""FastAPI application for PGM Agent."""

import uuid
from typing import Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pgm.config import get_settings
from pgm.db.tables import Base, Memory
from pgm.llm import LLMClient, create_llm_client
from pgm.llm.embedder import create_embedder
from pgm.classification.secret_gate import SecretGate
from pgm.extraction.extractor import MemoryExtractor
from pgm.retrieval.retriever import MemoryRetriever
from pgm.storage.repository import MemoryRepository
from pgm.risk.engine import RiskEngine
from pgm.risk.population import PopulationEstimator
from pgm.maintenance.utility import UtilityEstimator
from pgm.ladders.builder import LadderBuilder
from pgm.ladders.ontology import OntologyRegistry
from pgm.maintenance.solver import GreedySolver
from pgm.agent.graph import PGMAgent

# ── Dependency Injection & Setup ──────────────────────────────────────────────

settings = get_settings()

# Ensure we use a pool for FastAPI
engine = create_async_engine(
    settings.database_url,
    pool_size=5,
    max_overflow=10,
    echo=False
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


from typing import Any, AsyncGenerator

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown events."""
    # Ensure tables exist (for prototype only; usually use Alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(title="PGM API", version="0.1.0", lifespan=lifespan)

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yields a DB session."""
    async with async_session_factory() as session:
        yield session


from functools import lru_cache

from pgm.llm.embedder import Embedder

@lru_cache(maxsize=1)
def get_cached_embedder() -> Embedder:
    return create_embedder(settings)

@lru_cache(maxsize=1)
def get_cached_llm() -> LLMClient:
    return create_llm_client(settings)

def get_agent(session: AsyncSession = Depends(get_db_session)) -> PGMAgent:
    """Assemble all components and return the agent."""
    
    llm = get_cached_llm()
    embedder = get_cached_embedder()
    
    gate = SecretGate(llm_client=llm)
    extractor = MemoryExtractor(llm, gate)
    repo = MemoryRepository(session, embedder, settings=settings)
    retriever = MemoryRetriever(session, embedder, repo, settings=settings)
    
    pop_est = PopulationEstimator(llm)
    risk_engine = RiskEngine(repo, pop_est, settings=settings)
    util_est = UtilityEstimator(settings)
    
    builder = LadderBuilder(llm, repo, OntologyRegistry())
    solver = GreedySolver(repo, risk_engine, util_est, builder, pop_est)
    
    return PGMAgent(llm, extractor, repo, retriever, solver)


# ── API Routes ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str
    message: str

class ChatResponse(BaseModel):
    answer: str
    maintenance_ops_run: int
    suggested_actions: list[str] = []
    confidence_score: float = 1.0

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, agent: PGMAgent = Depends(get_agent)) -> ChatResponse:
    """Send a message to the agent."""
    
    from sqlalchemy import select
    from pgm.db.tables import User
    
    # Ensure user exists to avoid foreign key violations
    session = agent._repo._session
    try:
        uid = uuid.UUID(request.user_id)
        user_stmt = select(User).where(User.id == uid)
        user_res = await session.execute(user_stmt)
        if user_res.scalars().first() is None:
            new_user = User(id=uid)
            session.add(new_user)
            await session.commit()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format (must be UUID)")
    
    initial_state = {
        "user_id": request.user_id,
        "message": request.message
    }
    
    try:
        # Run the graph
        result = await agent.graph.ainvoke(initial_state)
        
        # Commit the transaction because LangGraph doesn't know about SQLAlchemy sessions
        await agent._repo._session.commit()
        
        return ChatResponse(
            answer=result.get("answer", ""),
            maintenance_ops_run=result.get("maintenance_ops", 0),
            suggested_actions=result.get("suggested_actions", []),
            confidence_score=result.get("confidence_score", 1.0)
        )
    except Exception as e:
        import logging
        logging.exception("Chat endpoint crashed!")
        await agent._repo._session.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{user_id}")
async def get_memories(user_id: str, session: AsyncSession = Depends(get_db_session)) -> list[dict[str, Any]]:
    """Get all active memories for a user."""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from pgm.config import MemoryStatus
    
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format (must be UUID)")
        
    stmt = select(Memory).options(selectinload(Memory.ladder_rungs)).where(
        Memory.user_id == uid,
        Memory.status == MemoryStatus.ACTIVE.value
    )
    result = await session.execute(stmt)
    memories = result.scalars().all()
    
    return [
        {
            "id": str(m.id),
            "category": m.category,
            "slot_key": m.slot_key,
            "current_text": m.current_text,
            "current_level": m.current_level,
            "access_count": m.access_count,
            "last_accessed_at": m.last_accessed_at.isoformat() if m.last_accessed_at else m.created_at.isoformat(),
            "ladders": [
                {
                    "level": l.level,
                    "text": l.text,
                    "population_fraction": l.population_fraction,
                    "info_bits": l.info_bits
                }
                for l in m.ladder_rungs
            ]
        }
        for m in memories
    ]

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Manually delete a specific memory."""
    from sqlalchemy import select
    
    try:
        mem_uuid = uuid.UUID(memory_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid memory ID format (must be UUID)")
        
    stmt = select(Memory).where(Memory.id == mem_uuid)
    result = await session.execute(stmt)
    mem = result.scalars().first()
    
    if mem is None:
        raise HTTPException(status_code=404, detail="Memory not found")
        
    await session.delete(mem)
    await session.commit()
    return {"status": "success", "message": "Memory deleted"}

@app.get("/risk/{user_id}")
async def get_risk_metrics(user_id: str, session: AsyncSession = Depends(get_db_session)) -> dict[str, Any]:
    """Get the latest risk snapshots for a user."""
    from sqlalchemy import select
    from pgm.db.tables import RiskSnapshot, User
    
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid user ID format (must be UUID)")
        
    user_stmt = select(User).where(User.id == uid)
    user_res = await session.execute(user_stmt)
    user = user_res.scalars().first()
    
    budget = user.identification_budget_bits if user else 20.0
    
    stmt = select(RiskSnapshot).where(
        RiskSnapshot.user_id == uid
    ).order_by(RiskSnapshot.created_at.desc()).limit(10)
    
    result = await session.execute(stmt)
    snapshots = result.scalars().all()
    
    return {
        "budget_bits": budget,
        "history": [
            {
                "id": str(s.id),
                "created_at": s.created_at.isoformat(),
                "k_hat": s.k_hat,
                "r_agg_bits": s.r_agg_bits,
                "quasi_identifiers": s.quasi_identifiers_json
            }
            for s in snapshots
        ]
    }









