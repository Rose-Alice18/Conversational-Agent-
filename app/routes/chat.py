from fastapi import APIRouter
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import build_agent
from app.schemas import ChatRequest, ChatResponse

router = APIRouter()

_agent = None


def init_agent(context_text: str = "") -> None:
    global _agent
    _agent = build_agent(context_text)


async def reinit_agent(context_text: str = "") -> None:
    """Reload the agent singleton with a new context string.
    Called by the ingest route after a successful upload."""
    init_agent(context_text)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    lc_messages = []
    for msg in request.messages:
        if msg.role.lower() == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role.lower() == "assistant":
            lc_messages.append(AIMessage(content=msg.content))

    result = await _agent.ainvoke({"messages": lc_messages})

    ai_reply = result["messages"][-1].content
    return ChatResponse(reply=ai_reply)
