import logging
import re

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import build_agent, build_context_only_agent, build_tools_only_agent
from app.schemas import ChatRequest, ChatResponse, CUAChatRequest

logger = logging.getLogger(__name__)

router = APIRouter()

_agent = None
_tools_only_agent = None
_context_only_agent = None


def init_agent(context_text: str = "") -> None:
    global _agent
    _agent = build_agent(context_text)


def init_tools_only_agent(context_text: str = "") -> None:
    global _tools_only_agent
    _tools_only_agent = build_tools_only_agent(context_text)


def init_context_only_agent(context_text: str = "", catalog_text: str = "") -> None:
    global _context_only_agent
    _context_only_agent = build_context_only_agent(context_text, catalog_text)


async def reinit_agent(context_text: str = "") -> None:
    """Reload the hybrid agent after a successful ingest."""
    init_agent(context_text)


async def reinit_tools_only_agent(context_text: str = "") -> None:
    """Reload the tools-only agent after a successful ingest."""
    init_tools_only_agent(context_text)


async def reinit_context_only_agent(context_text: str = "", catalog_text: str = "") -> None:
    """Reload the context-only agent after a successful ingest."""
    init_context_only_agent(context_text, catalog_text)


def _extract_image_url(text: str) -> tuple[str, str | None]:
    """Extract [IMAGE:url] tags from agent reply.
    Returns (clean_reply, first_image_url) — ALL tags are stripped from the reply text."""
    matches = re.findall(r'\[IMAGE:(https?://[^\]]+)\]', text)
    image_url = matches[0].strip() if matches else None
    # Remove every [IMAGE:...] tag from the reply text
    clean = re.sub(r'\[IMAGE:https?://[^\]]+\]', '', text).strip()
    # Remove trailing label artifacts like "Lavender 256GB:  " left after tag removal
    clean = re.sub(r'[\w\s]+:\s*$', '', clean).strip()
    return clean, image_url


def _get_content(message) -> str:
    """Safely extract plain-text content from a LangChain message.
    Handles both str and list[dict] content (newer LangChain versions)."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        ]
        return " ".join(parts)
    return str(content)


def _build_lc_messages(request: ChatRequest):
    lc_messages = []
    for msg in request.messages:
        if msg.role.lower() == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role.lower() == "assistant":
            lc_messages.append(AIMessage(content=msg.content))
    return lc_messages


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Hybrid agent — uses both store context and tool calls."""
    try:
        lc_messages = _build_lc_messages(request)
        result = await _agent.ainvoke({"messages": lc_messages})
        raw = _get_content(result["messages"][-1]).replace("\n", " ").strip()
        reply, image_url = _extract_image_url(raw)
        return ChatResponse(message=reply, image_url=image_url)
    except Exception as exc:
        logger.exception("Error in /chat")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/tools-only", response_model=ChatResponse)
async def chat_tools_only(request: ChatRequest):
    """Tools-only agent — answers every question by querying the database directly."""
    try:
        lc_messages = _build_lc_messages(request)
        result = await _tools_only_agent.ainvoke({"messages": lc_messages})
        raw = _get_content(result["messages"][-1]).replace("\n", " ").strip()
        reply, image_url = _extract_image_url(raw)
        return ChatResponse(message=reply, image_url=image_url)
    except Exception as exc:
        logger.exception("Error in /chat/tools-only")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/context-only", response_model=ChatResponse)
async def chat_context_only(request: ChatRequest):
    """Context-only agent — answers only from the store context string, no tool calls."""
    try:
        lc_messages = _build_lc_messages(request)
        result = await _context_only_agent.ainvoke({"messages": lc_messages})
        raw = _get_content(result["messages"][-1]).replace("\n", " ").strip()
        reply, image_url = _extract_image_url(raw)
        return ChatResponse(message=reply, image_url=image_url)
    except Exception as exc:
        logger.exception("Error in /chat/context-only")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/chat/cua", response_model=ChatResponse)
async def chat_cua(request: CUAChatRequest):
    """CUA adapter endpoint — translates the CUA's conversation format and routes to the Hybrid agent."""
    try:
        customer_name = request.active_query.speaker
        lc_messages = []
        for entry in request.conversation_transcript:
            if entry.speaker == customer_name:
                lc_messages.append(HumanMessage(content=entry.content))
            else:
                lc_messages.append(AIMessage(content=entry.content))
        result = await _agent.ainvoke({"messages": lc_messages})
        raw = _get_content(result["messages"][-1]).replace("\n", " ").strip()
        reply, image_url = _extract_image_url(raw)
        return ChatResponse(message=reply, image_url=image_url)
    except Exception as exc:
        logger.exception("Error in /chat/cua")
        raise HTTPException(status_code=500, detail=str(exc))
