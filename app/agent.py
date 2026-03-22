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
    "- Never use line breaks or newlines — write everything as one flowing, connected response\n"
    "- Never start with a heading or a label like 'iPhone 17 Pricing:'\n"
    "- Write in plain, natural sentences as if you are texting a customer\n"
    "- Always state prices accurately — do not guess or round them\n"
    "- Never reveal stock numbers or unit counts to the customer — never say things like '18 units available' or '12 in stock'\n"
    "- Only say whether something is available or not — for example 'we have that in stock' or 'that one is currently unavailable'\n"
    "- When a product has multiple storage sizes, give each storage tier's price, then group colors within that tier (e.g. 'The 128GB is GHS 7,999 — Blue and Starlight are in stock, Midnight is unavailable')\n"
    "- Never use dashes or hyphens as separators between items — write in flowing connected sentences\n"
    "- Be warm and end with an offer to help further if appropriate\n"
    "- When a customer asks for a photo or image of a specific product and you have an image URL, include it at the very end of your reply in this exact format: [IMAGE:https://...] — nothing else after it\n"
    "- CRITICAL: image URLs must ONLY appear in [IMAGE:https://...] format — NEVER as markdown links like [text](url), NEVER embedded in sentences\n"
    "- When a customer asks to see images of a specific product (e.g. 'show me iPhone 17 images'), pick the single most representative image URL and place it at the very end as [IMAGE:https://...]\n"
    "- When a customer asks to see all images or images without naming a specific product, do NOT fetch or share any image URLs — instead ask them to name the specific product they want to see"
)


def build_agent(context_text: str = ""):
    """Existing hybrid agent — uses both context string and tools."""
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


def build_tools_only_agent(context_text: str = ""):
    """Agent that relies entirely on tool calls for product data.
    Receives store context only for background details like currency and store name."""
    if context_text:
        system_prompt = (
            f"{_BASE_PROMPT}\n\n"
            f"Here is background information about this store (currency, name, policies). "
            f"Use tools for all product queries — use this only for store-level context:\n\n"
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


def build_context_only_agent(context_text: str = "", catalog_text: str = ""):
    """Agent that relies entirely on the context string and product catalog — no tools available."""
    if context_text or catalog_text:
        system_prompt = (
            f"{_BASE_PROMPT}\n\n"
            f"Here is everything you know about this store. "
            f"Use only this information to answer questions. "
            f"Do not attempt to look anything up — answer only from what is provided below.\n\n"
            f"Additional rules for product answers:\n"
            f"- When a product comes in multiple storage sizes, treat each storage size as its own tier and give its price.\n"
            f"- Within each storage tier, group the colors together: mention which colors are in stock and which are unavailable, rather than listing every color as a separate sentence.\n"
            f"- Example of good format: 'The 128GB is GHS 7,999 — Blue and Starlight are in stock, while Midnight and Red are currently unavailable. The 256GB is GHS 9,499 — Pink and Red are available.'\n"
            f"- If a product also has a Refurbished version, state the refurbished price and whether it is in stock after the new price.\n"
            f"- Never use dashes or bullet points to separate items — write in flowing sentences.\n"
            f"- Keep responses concise — do not repeat the product name before every color.\n\n"
        )
        if context_text:
            system_prompt += f"STORE SUMMARY:\n{context_text}\n\n"
        if catalog_text:
            system_prompt += f"FULL PRODUCT CATALOG:\n{catalog_text}"
    else:
        system_prompt = _BASE_PROMPT

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return create_react_agent(
        model=llm,
        tools=[],
        prompt=system_prompt,
    )
