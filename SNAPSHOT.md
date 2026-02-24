# Project Snapshot — Shop Assistant API (v0.1 baseline)

This document captures the exact state of every file in the project at the
end of the initial build. Use it to restore this baseline if needed.

---

## What was built

A stateless conversational agent API for a small shop. A client sends a
conversation history and gets a reply. The agent uses OpenAI GPT and two
LangGraph tools to query a PostgreSQL database for real inventory and business
information — it never makes things up.

**Stack:** FastAPI · LangGraph (`create_react_agent`) · langchain-openai ·
SQLAlchemy (async) · asyncpg · PostgreSQL · Alembic · pydantic-settings

---

## Project structure

```
shop-assistant/
├── pyproject.toml
├── alembic.ini
├── seed.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/           (empty — no migrations generated yet)
└── app/
    ├── __init__.py
    ├── config.py
    ├── database.py
    ├── models.py
    ├── tools.py
    ├── agent.py
    ├── schemas.py
    ├── main.py
    └── routes/
        ├── __init__.py
        └── chat.py
```

---

## File-by-file contents

---

### `pyproject.toml`

```toml
[project]
name = "shop-assistant"
version = "0.1.0"
description = "Conversational shop assistant API powered by LangGraph and FastAPI"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "langgraph>=0.4",
    "langchain-openai>=0.3",
    "langchain-core>=0.3",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "pydantic-settings>=2.0",
    "alembic>=1.14",
    "python-dotenv>=1.0",
]

[tool.setuptools.packages.find]
include = ["app*"]
```

> The `[tool.setuptools.packages.find]` section was added after the initial
> build to fix a setuptools error caused by both `app/` and `alembic/` being
> discovered as top-level packages. It restricts packaging to `app` only.

---

### `alembic.ini`

Standard Alembic config. The `sqlalchemy.url` line should be set to your
local database URL or left as a placeholder — **do not commit real credentials
here**.

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://postgres:PASSWORD@localhost:5432/shop

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

---

### `alembic/env.py`

Configures Alembic to run async migrations using the URL from `app/config.py`
(i.e., from `.env`), not from `alembic.ini` at runtime.

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

---

### `app/config.py`

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/shop"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    model_config = {"env_file": ".env"}


settings = Settings()
```

Reads from a `.env` file at the project root. Required keys:
- `DATABASE_URL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, defaults to `gpt-4o-mini`)

---

### `app/database.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

Creates a single shared async engine and session factory. The tools in
`tools.py` use `async_session` directly (not FastAPI dependency injection,
since LangGraph tools are not FastAPI-aware).

---

### `app/models.py`

Two tables.

```python
from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    quantity: Mapped[int] = mapped_column(default=0)
    category: Mapped[str] = mapped_column(String(100), default="general")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BusinessInfo(Base):
    __tablename__ = "business_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True)
    value: Mapped[str] = mapped_column(Text)
```

- **`inventory`** — product catalogue (name, description, price, quantity, category)
- **`business_info`** — key-value store for arbitrary shop details (hours,
  location, return policy, contact, etc.)

---

### `app/tools.py`

The two tools the agent can call. Each opens its own async DB session.

```python
from langchain_core.tools import tool
from sqlalchemy import or_, select

from app.database import async_session
from app.models import BusinessInfo, Inventory


@tool
async def search_inventory(query: str) -> str:
    """Search the shop inventory by product name, category, or keyword.
    Use this when a customer asks about products, prices, or availability."""
    async with async_session() as session:
        stmt = select(Inventory).where(
            or_(
                Inventory.name.ilike(f"%{query}%"),
                Inventory.category.ilike(f"%{query}%"),
                Inventory.description.ilike(f"%{query}%"),
            )
        )
        results = (await session.execute(stmt)).scalars().all()

    if not results:
        return f"No products found matching '{query}'."

    lines = []
    for item in results:
        stock = "in stock" if item.quantity > 0 else "out of stock"
        lines.append(
            f"- {item.name}: ${item.price:.2f} ({stock}, {item.quantity} available) "
            f"[Category: {item.category}] — {item.description}"
        )
    return "\n".join(lines)


@tool
async def get_business_info(topic: str) -> str:
    """Look up business information such as store hours, location,
    return policy, contact info, or store name.
    The topic should be a short keyword like 'hours', 'location', 'returns'."""
    async with async_session() as session:
        stmt = select(BusinessInfo).where(BusinessInfo.key.ilike(f"%{topic}%"))
        results = (await session.execute(stmt)).scalars().all()

    if not results:
        return f"No business information found for '{topic}'."

    return "\n".join(f"{r.key}: {r.value}" for r in results)


all_tools = [search_inventory, get_business_info]
```

---

### `app/agent.py`

```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.tools import all_tools

SYSTEM_PROMPT = (
    "You are a helpful shop assistant. You help customers find products "
    "and answer questions about the store.\n\n"
    "Always use the available tools to look up real information — never make up "
    "product details, prices, or store policies. If you cannot find the answer, "
    "say so honestly.\n\n"
    "Be friendly, concise, and helpful."
)


def build_agent():
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
    return create_react_agent(
        model=llm,
        tools=all_tools,
        prompt=SYSTEM_PROMPT,
    )
```

`build_agent()` is called once at server startup (in `lifespan`). The returned
agent object is reused for every request.

---

### `app/schemas.py`

```python
from pydantic import BaseModel


class Message(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


class ChatResponse(BaseModel):
    reply: str
```

The client is responsible for maintaining conversation history and sending it
with every request. The server is fully stateless.

---

### `app/main.py`

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routes.chat import init_agent
from app.routes.chat import router as chat_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_agent()
    yield


app = FastAPI(title="Shop Assistant", version="0.1.0", lifespan=lifespan)
app.include_router(chat_router, prefix="/api")
```

---

### `app/routes/chat.py`

```python
from fastapi import APIRouter
from langchain_core.messages import AIMessage, HumanMessage

from app.agent import build_agent
from app.schemas import ChatRequest, ChatResponse

router = APIRouter()

_agent = None


def init_agent():
    global _agent
    _agent = build_agent()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    lc_messages = []
    for msg in request.messages:
        if msg.role == "user":
            lc_messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            lc_messages.append(AIMessage(content=msg.content))

    result = await _agent.ainvoke({"messages": lc_messages})

    ai_reply = result["messages"][-1].content
    return ChatResponse(reply=ai_reply)
```

Single endpoint: `POST /api/chat`. Converts the incoming message list to
LangChain message objects, invokes the agent, and returns the final AI message.

---

### `app/routes/__init__.py` and `app/__init__.py`

Both are empty files. Required to make their directories Python packages.

---

### `seed.py`

Populates the database with sample data. Run once after the database is ready.
Also calls `Base.metadata.create_all` so it can be used instead of Alembic
for the initial table creation if preferred.

**Sample inventory (6 products):**
| Name | Price | Qty | Category |
|---|---|---|---|
| Wireless Mouse | $29.99 | 50 | electronics |
| Mechanical Keyboard | $79.99 | 30 | electronics |
| USB-C Hub | $45.00 | 25 | electronics |
| Notebook A5 | $8.99 | 100 | stationery |
| Ballpoint Pen Pack | $4.50 | 200 | stationery |
| Laptop Stand | $39.99 | 15 | accessories |

**Sample business info (6 entries):**
| Key | Value |
|---|---|
| store_name | TechShop |
| hours | Mon-Fri 9am-6pm, Sat 10am-4pm, Sun Closed |
| location | 123 Main Street, Springfield, IL 62701 |
| return_policy | 30-day returns with original receipt |
| contact | support@techshop.com \| (555) 123-4567 |
| payment_methods | Cash, Visa, Mastercard, Apple Pay, Google Pay |

---

## Environment variables (`.env`)

Create a `.env` file in the project root with:

```
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/shop
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

---

## How to run from this state

```bash
# 1. Install dependencies
pip install -e .

# 2. Create .env from the template above

# 3. Create the database tables and seed sample data
python seed.py

# 4. Start the server
uvicorn app.main:app --reload

# 5. Test
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "What products do you have?"}]}'
```

---

## Known issues fixed during this session

- `pip install -e .` failed with *"Multiple top-level packages discovered in a
  flat-layout"* because setuptools found both `app/` and `alembic/` at the
  root. Fixed by adding `[tool.setuptools.packages.find] include = ["app*"]`
  to `pyproject.toml`.

---

## What this version deliberately does NOT include

- Conversation persistence (client sends full history each request)
- Authentication or middleware
- Streaming responses
- Vector search / RAG
- Custom LangGraph graph nodes (uses `create_react_agent` prebuilt)
