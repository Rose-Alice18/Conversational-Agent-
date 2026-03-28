from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.database import async_session, engine
from app.models import Base, ProductCatalog, StoreContext
from app.routes.chat import init_agent, init_context_only_agent, init_tools_only_agent
from app.routes.chat import router as chat_router
from app.routes.ingest import router as ingest_router
from app.routes.reset import router as reset_router
from app.routes.test_ui import router as test_ui_router
from app.routes.compare_ui import router as compare_ui_router


async def _startup() -> None:
    # Ensure all tables exist on every startup (idempotent — safe if tables already exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Load the most recent store context and inject into the agent
    context_text = ""
    catalog_text = ""
    async with async_session() as session:
        ctx_row = (await session.execute(
            select(StoreContext).order_by(StoreContext.id.desc()).limit(1)
        )).scalars().first()
        if ctx_row:
            context_text = ctx_row.context_text

        cat_row = (await session.execute(
            select(ProductCatalog).order_by(ProductCatalog.id.desc()).limit(1)
        )).scalars().first()
        if cat_row:
            catalog_text = cat_row.catalog_text

    init_agent(context_text)
    init_tools_only_agent(context_text)
    init_context_only_agent(context_text, catalog_text)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _startup()
    yield


app = FastAPI(title="Shop Assistant", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router, prefix="/api")
app.include_router(ingest_router, prefix="/api")
app.include_router(reset_router, prefix="/api")
app.include_router(test_ui_router)
app.include_router(compare_ui_router)
