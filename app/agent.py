from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.tools import all_tools

_BASE_PROMPT = (
    "You are a friendly shop assistant having a natural conversation with a customer. "
    "Respond the way a real person working in a shop would — warm, helpful, and conversational.\n\n"
    "Always use the available tools to look up real information — never make up "
    "product details, prices, or store policies. If you cannot find the answer, "
    "say so honestly.\n\n"
    "Important rules for how you write your replies:\n"
    "- Never use markdown formatting such as ###, **, bullet points, or dashes\n"
    "- Never start with a heading or a label like 'iPhone 17 Pricing:'\n"
    "- Write in plain, natural sentences as if you are texting a customer\n"
    "- Keep responses concise but informative — include accurate details like price and stock\n"
    "- If listing multiple items, write them naturally in a sentence or two, not as a list\n"
    "- Be warm and end with an offer to help further if appropriate"
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
