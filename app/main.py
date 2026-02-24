from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.database import async_session, engine
from app.models import Base, StoreContext
from app.routes.chat import init_agent
from app.routes.chat import router as chat_router
from app.routes.ingest import router as ingest_router


async def _startup() -> None:
    # Ensure all tables exist on every startup (idempotent — safe if tables already exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Load the most recent store context and inject into the agent
    context_text = ""
    async with async_session() as session:
        stmt = select(StoreContext).order_by(StoreContext.id.desc()).limit(1)
        row = (await session.execute(stmt)).scalars().first()
        if row:
            context_text = row.context_text

    init_agent(context_text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    yield


app = FastAPI(title="Shop Assistant", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
