from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.database import async_session
from app.routes.chat import init_agent, init_context_only_agent, init_tools_only_agent

router = APIRouter()


class ResetResponse(BaseModel):
    message: str


@router.post("/reset", response_model=ResetResponse)
async def reset_database():
    """Delete all ingested data and reset all agents to their empty state.
    Call this before re-uploading a new Excel file."""
    async with async_session() as session:
        await session.execute(text("DELETE FROM product_catalog"))
        await session.execute(text("DELETE FROM store_context"))
        await session.execute(text("DELETE FROM products"))
        await session.execute(text("DELETE FROM business_info"))
        await session.commit()

    # Reset all three agents to empty state (no context, no catalog)
    init_agent("")
    init_tools_only_agent()
    init_context_only_agent("", "")

    return ResetResponse(message="Database cleared. All agents reset. You can now upload a new Excel file.")
