from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.tools import all_tools

_BASE_PROMPT = (
    "You are a helpful shop assistant. You help customers find products "
    "and answer questions about the store.\n\n"
    "Always use the available tools to look up real information — never make up "
    "product details, prices, or store policies. If you cannot find the answer, "
    "say so honestly.\n\n"
    "Be friendly, concise, and helpful."
)


def build_agent(context_text: str = ""):
    if context_text:
        system_prompt = (
            f"{_BASE_PROMPT}\n\n"
            f"Here is a summary of the current store inventory and business information. "
            f"Use this to answer general overview questions without always calling tools:\n\n"
            f"{context_text}"
        )
    else:
        system_prompt = _BASE_PROMPT

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return create_react_agent(
        model=llm,
        tools=all_tools,
        prompt=system_prompt,
    )
