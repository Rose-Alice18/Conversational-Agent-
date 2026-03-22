import io
import json
import re
from typing import Any

import pandas as pd
from langchain_openai import ChatOpenAI
from sqlalchemy import func, select, text

from app.config import settings
from app.database import async_session, engine
from app.models import Base, BusinessInfo, Product, ProductCatalog, StoreContext

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROLE_KEYWORDS: dict[str, list[str]] = {
    "name":        ["name", "product", "item", "title"],
    "price":       ["price", "cost", "rate", "amount", "selling"],
    "quantity":    ["qty", "quantity", "stock", "count", "units", "available"],
    "category":    ["category", "type", "group", "dept"],
    "description": ["desc", "description", "notes", "details"],
    "sku":         ["sku", "code", "barcode", "ref", "part"],
    "color":       ["colour", "color"],
    "variant":     ["variant", "size", "model"],
}

INFO_KEYWORDS = ["info", "about", "business", "contact", "company", "store", "shop"]

CATALOG_SHEET_KEYWORDS = ["catalog", "catalogue"]


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ProductsNotEmptyError(Exception):
    """Raised when the products table already contains rows."""


# ---------------------------------------------------------------------------
# Sheet loading
# ---------------------------------------------------------------------------

def _load_sheets(file_bytes: bytes) -> dict[str, pd.DataFrame]:
    buf = io.BytesIO(file_bytes)
    raw: dict = pd.read_excel(buf, sheet_name=None, header=None, dtype=str)
    cleaned = {}
    for name, df in raw.items():
        df = df.dropna(how="all").fillna("")
        if not df.empty:
            cleaned[name] = df
    return cleaned


# ---------------------------------------------------------------------------
# Sheet classifier
# ---------------------------------------------------------------------------

def _is_info_sheet(sheet_name: str, df: pd.DataFrame) -> bool:
    """Return True if this sheet looks like a key-value business info sheet."""
    if any(kw in sheet_name.lower() for kw in INFO_KEYWORDS):
        return True
    # 2-column heuristic: looks like a key → value list
    non_empty_cols = [c for c in df.columns if df[c].astype(str).str.strip().any()]
    if len(non_empty_cols) == 2:
        first_col_vals = df.iloc[:, 0].astype(str).str.strip()
        non_empty = first_col_vals[first_col_vals != ""]
        if not non_empty.empty and non_empty.str.len().mean() < 40:
            return True
    return False


def _is_catalog_sheet(sheet_name: str) -> bool:
    """Return True if this sheet is a pre-written product catalog."""
    return any(kw in sheet_name.lower() for kw in CATALOG_SHEET_KEYWORDS)


def _read_catalog_sheet(df: pd.DataFrame) -> list[str]:
    """Extract product sentences from a pre-written catalog sheet.

    Reads each row and takes the first non-empty cell value.
    The Catalog sheet should contain only sentences — no title rows,
    no category headers, no subtitles.
    """
    sentences = []
    for _, row in df.iterrows():
        for val in row:
            stripped = str(val).strip()
            if stripped and stripped.lower() not in ("nan", "none", ""):
                sentences.append(stripped)
                break
    return sentences


# ---------------------------------------------------------------------------
# Column role detector
# ---------------------------------------------------------------------------

def _normalize(col: str) -> str:
    return re.sub(r"[^a-z0-9]", "", col.lower())


def _detect_column_roles(columns: list[str]) -> dict[str, str]:
    """Map each column name to a recognised role via keyword matching.
    Any column that cannot be matched is sent to a single LLM batch call."""
    role_map: dict[str, str] = {}
    unrecognized: list[str] = []

    for col in columns:
        norm = _normalize(col)
        matched = None
        for role, keywords in ROLE_KEYWORDS.items():
            if any(kw in norm for kw in keywords):
                matched = role
                break
        if matched:
            role_map[col] = matched
        else:
            unrecognized.append(col)

    if unrecognized:
        role_map.update(_llm_classify_columns(unrecognized))

    return role_map


def _llm_classify_columns(columns: list[str]) -> dict[str, str]:
    """One synchronous LLM call to classify ambiguous column names.
    Returns only columns the LLM can confidently map to a valid role."""
    valid_roles = list(ROLE_KEYWORDS.keys())
    prompt = (
        f"You are classifying spreadsheet column names into product data roles.\n"
        f"Valid roles: {', '.join(valid_roles)}.\n"
        f"For each column name below, return the best matching role, "
        f"or 'unknown' if it does not match any role.\n"
        f"Respond ONLY with a JSON object like: {{\"col_name\": \"role\", ...}}\n\n"
        f"Columns: {json.dumps(columns)}"
    )
    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )
    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        raw = json.loads(response.content)
        return {col: role for col, role in raw.items() if role in valid_roles}
    except Exception:
        return {}  # safe fallback — unrecognised columns go into extra_data


# ---------------------------------------------------------------------------
# Row parser
# ---------------------------------------------------------------------------

def _parse_product_row(row: pd.Series, role_map: dict[str, str]) -> dict[str, Any] | None:
    """Map a DataFrame row to Product field values using the detected role map.
    Returns None if the row has no usable product name."""
    core_roles = {"name", "price", "quantity", "category", "description", "sku"}

    # Build role → first matching column mapping and track which columns are primary
    role_to_col: dict[str, str] = {}
    primary_cols: set[str] = set()
    for col, role in role_map.items():
        if role not in role_to_col:
            role_to_col[role] = col
            if role in core_roles:
                primary_cols.add(col)

    def get(role: str) -> str:
        col = role_to_col.get(role)
        return str(row[col]).strip() if col and col in row.index else ""

    name = get("name")
    if not name or name.lower() in ("nan", "none", ""):
        return None

    # Price: strip currency symbols, parse as float
    price_raw = get("price")
    price = 0.0
    if price_raw:
        cleaned = re.sub(r"[^\d.]", "", price_raw)
        try:
            price = float(cleaned) if cleaned else 0.0
        except ValueError:
            price = 0.0

    # Quantity: int(float(...)) handles "5.0"; regex fallback for "50 units"
    qty_raw = get("quantity")
    quantity = 0
    if qty_raw:
        try:
            quantity = int(float(qty_raw))
        except ValueError:
            cleaned = re.sub(r"[^\d]", "", qty_raw)
            try:
                quantity = int(cleaned) if cleaned else 0
            except ValueError:
                quantity = 0

    category = get("category") or "general"
    if category.lower() in ("nan", "none", ""):
        category = "general"

    description = get("description") or ""
    if description.lower() in ("nan", "none"):
        description = ""

    sku_val = get("sku")
    sku = sku_val if sku_val and sku_val.lower() not in ("nan", "none", "") else None

    # Collect extra columns:
    # - Columns not assigned as primary for a core role go into extra_data
    # - This includes duplicate price/quantity columns (e.g. refurbished price, refurb units)
    extra_data: dict[str, str] = {}
    for col in row.index:
        if col in primary_cols:
            continue  # already used as a primary core field
        col_role = role_map.get(col)
        val = str(row[col]).strip()
        if val and val.lower() not in ("nan", "none", ""):
            # Non-core roles use role name as key; duplicate core roles use original column name
            if col_role and col_role not in core_roles:
                key = col_role
            else:
                key = str(col)
            extra_data[key] = val

    return {
        "name": name,
        "description": description,
        "price": price,
        "quantity": quantity,
        "category": category,
        "sku": sku,
        "extra_data": extra_data if extra_data else None,
    }


# ---------------------------------------------------------------------------
# Info sheet parser
# ---------------------------------------------------------------------------

def _parse_info_sheet(df: pd.DataFrame) -> list[dict[str, str]]:
    """Extract key-value pairs from a 2-column info sheet."""
    pairs = []
    for _, row in df.iterrows():
        values = [
            str(v).strip()
            for v in row
            if str(v).strip() and str(v).strip().lower() != "nan"
        ]
        if len(values) >= 2:
            key_raw = values[0]
            value = " ".join(values[1:])
            key = re.sub(r"[^a-z0-9]+", "_", key_raw.lower()).strip("_")
            if key and value:
                pairs.append({"key": key, "value": value})
    return pairs


# ---------------------------------------------------------------------------
# Context string builder
# ---------------------------------------------------------------------------

async def _build_context_string(session) -> str:
    """Query DB within the current open session and build a plain-English summary."""
    store_name_row = (
        await session.execute(
            select(BusinessInfo).where(BusinessInfo.key == "store_name")
        )
    ).scalars().first()
    store_name = store_name_row.value if store_name_row else "this store"

    all_info = (await session.execute(select(BusinessInfo))).scalars().all()
    info_lines = [f"{r.key}: {r.value}" for r in all_info if r.key != "store_name"]

    total, min_price, max_price, _ = (
        await session.execute(
            select(
                func.count(Product.id),
                func.min(Product.price),
                func.max(Product.price),
                func.sum(Product.quantity),
            )
        )
    ).one()

    out_of_stock = (
        await session.execute(
            select(func.count(Product.id)).where(Product.quantity == 0)
        )
    ).scalar_one()

    categories = [
        r[0] for r in (await session.execute(select(Product.category).distinct())).all()
    ]
    samples = [
        r[0] for r in (await session.execute(select(Product.name).limit(5))).all()
    ]

    in_stock = (total or 0) - (out_of_stock or 0)
    cat_list = ", ".join(sorted(categories)) if categories else "none"
    sample_list = ", ".join(samples) if samples else "none"
    min_p = f"${min_price:.2f}" if min_price is not None else "N/A"
    max_p = f"${max_price:.2f}" if max_price is not None else "N/A"

    lines = [f"Store: {store_name}"]
    lines.extend(info_lines)
    lines.append("")
    lines.append("Inventory Overview:")
    lines.append(f"- {total} products across {len(categories)} categories: {cat_list}")
    lines.append(f"- Price range: {min_p} — {max_p}")
    lines.append(f"- {in_stock} items in stock, {out_of_stock} out of stock")
    lines.append(f"- Example products: {sample_list}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Product catalog builder
# ---------------------------------------------------------------------------

def _fmt_price(price, currency: str) -> str:
    """Format a price as a clean integer with currency, e.g. '10,999 GHS'."""
    try:
        f = float(price)
        return f"{int(f):,} {currency}" if f == int(f) else f"{f:,.2f} {currency}"
    except (TypeError, ValueError):
        return str(price)


def _llm_generate_product_sentences(products: list, currency: str = "GHS") -> list[str]:
    """Use LLM to convert a batch of product records to natural language sentences."""
    lines = []
    for idx, p in enumerate(products, 1):
        # Format extra_data prices with currency too
        raw_extra = p.extra_data or {}
        formatted_extra: dict = {}
        for k, v in raw_extra.items():
            try:
                fv = float(v)
                formatted_extra[k] = _fmt_price(fv, currency)
            except (TypeError, ValueError):
                formatted_extra[k] = v
        extra = json.dumps(formatted_extra) if formatted_extra else "{}"

        lines.append(
            f"{idx}. Name: {p.name}, Category: {p.category or 'N/A'}, "
            f"Price: {_fmt_price(p.price, currency)}, Quantity: {p.quantity or 0}, "
            f"SKU: {p.sku or 'N/A'}, Description: {p.description or 'N/A'}, "
            f"Additional fields: {extra}"
        )

    product_list = "\n".join(lines)
    prompt = (
        "Convert each product record below into one natural, friendly sentence a shop assistant would say.\n"
        f"All prices are already formatted with the correct currency ({currency}) — use them exactly as shown, do not add or change the currency symbol.\n"
        "Rules:\n"
        "- Include the exact product name, color, storage/variant if present.\n"
        "- State the new/regular price exactly as given and say 'currently in stock' if Quantity > 0, or 'currently out of stock' if Quantity is 0.\n"
        "- If 'Additional fields' contains a refurbished price (any key with 'refurb' or 'refurbished' in the name), "
        "explicitly state the refurbished price too and use the same currency. Then check for a refurbished quantity key (any key with 'refurb' "
        "in the name that looks like a count/units/qty). If that refurb quantity > 0 say 'refurbished units currently in stock', "
        "otherwise say 'refurbished units currently out of stock'.\n"
        "- If 'Additional fields' is empty or '{}', only mention the regular price and stock status.\n"
        "- Do not use markdown, bullet points, or dashes.\n"
        "- Do not group multiple products together — each numbered entry must produce exactly one sentence.\n"
        "- Return exactly one sentence per product, numbered to match the input (e.g. '1. We have...').\n\n"
        f"{product_list}"
    )

    llm = ChatOpenAI(
        model=settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0,
    )

    try:
        response = llm.invoke([{"role": "user", "content": prompt}])
        raw = response.content.strip()

        sentence_map: dict[int, str] = {}
        for line in raw.split("\n"):
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)[.)]\s+(.+)$', line)
            if match:
                sentence_map[int(match.group(1))] = match.group(2).strip()

        return [
            sentence_map.get(idx, f"We have {p.name} available in our store.")
            for idx, p in enumerate(products, 1)
        ]
    except Exception:
        return [
            f"We have {p.name} in the {p.category} category, priced at {p.price}."
            for p in products
        ]


async def _build_product_catalog(session) -> tuple[str, int]:
    """Query all products and generate one natural language sentence per product."""
    result = await session.execute(select(Product).order_by(Product.id))
    products = result.scalars().all()

    if not products:
        return "", 0

    # Read currency from business_info; default to GHS if not set
    currency_row = (
        await session.execute(
            select(BusinessInfo).where(BusinessInfo.key == "currency")
        )
    ).scalars().first()
    currency = currency_row.value.strip().upper() if currency_row else "GHS"

    all_sentences: list[str] = []
    batch_size = 50

    for i in range(0, len(products), batch_size):
        batch = products[i:i + batch_size]
        sentences = _llm_generate_product_sentences(batch, currency=currency)
        all_sentences.extend(sentences)

    catalog_text = "\n\n".join(all_sentences)
    return catalog_text, len(all_sentences)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_ingest(file_bytes: bytes) -> dict[str, Any]:
    # Ensure all tables exist before any query (safe to run even if tables already exist)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Guard: reject if products table already has data
    async with async_session() as session:
        count = (
            await session.execute(select(func.count()).select_from(Product))
        ).scalar_one()
    if count > 0:
        raise ProductsNotEmptyError

    # Load all non-empty sheets
    sheets = _load_sheets(file_bytes)
    if not sheets:
        raise ValueError("The uploaded Excel file appears to be empty.")

    product_rows: list[Product] = []
    info_pairs: dict[str, str] = {}
    all_role_maps: dict[str, dict] = {}
    catalog_sentences_from_sheet: list[str] = []

    for sheet_name, df in sheets.items():
        # Pre-written catalog sheet — read sentences directly, skip further processing
        if _is_catalog_sheet(sheet_name):
            catalog_sentences_from_sheet = _read_catalog_sheet(df)
            continue

        if _is_info_sheet(sheet_name, df):
            for pair in _parse_info_sheet(df):
                info_pairs[pair["key"]] = pair["value"]
            continue

        # Detect whether first row is a column header
        header_row = df.iloc[0].tolist()
        non_numeric = sum(
            1 for v in header_row
            if str(v).strip() and not re.match(r"^[\d.,\s$%]+$", str(v).strip())
        )
        if non_numeric > len(header_row) / 2:
            df.columns = df.iloc[0].astype(str).str.strip()
            df = df.iloc[1:].reset_index(drop=True)
        else:
            df.columns = [f"col_{i}" for i in range(len(df.columns))]

        df = df[df.apply(lambda r: any(str(v).strip() for v in r), axis=1)]
        if df.empty:
            continue

        columns = [str(c) for c in df.columns]
        role_map = _detect_column_roles(columns)
        all_role_maps[sheet_name] = role_map

        # Skip sheet if no name column was detected
        if "name" not in role_map.values():
            continue

        for _, row in df.iterrows():
            parsed = _parse_product_row(row, role_map)
            if parsed is None:
                continue
            product_rows.append(
                Product(
                    name=parsed["name"],
                    description=parsed["description"],
                    price=parsed["price"],
                    quantity=parsed["quantity"],
                    category=parsed["category"],
                    sku=parsed["sku"],
                    extra_data=parsed["extra_data"],
                )
            )

    if not product_rows and not info_pairs:
        raise ValueError(
            "No recognisable product or business data was found in the uploaded file."
        )

    # Write everything in one atomic transaction
    async with async_session() as session:
        await session.execute(text("DELETE FROM business_info"))

        session.add_all(product_rows)
        for key, value in info_pairs.items():
            session.add(BusinessInfo(key=key, value=value))

        # Flush makes new rows visible to queries within this session
        await session.flush()

        context_text = await _build_context_string(session)

        if catalog_sentences_from_sheet:
            # Use pre-written sentences from the Catalog sheet — no LLM calls needed
            catalog_text = "\n\n".join(catalog_sentences_from_sheet)
            sentence_count = len(catalog_sentences_from_sheet)
        else:
            # Fall back to LLM-generated sentences
            catalog_text, sentence_count = await _build_product_catalog(session)

        combined_roles: dict[str, str] = {}
        for sheet_roles in all_role_maps.values():
            combined_roles.update(sheet_roles)

        session.add(StoreContext(context_text=context_text, column_roles=combined_roles))
        session.add(ProductCatalog(catalog_text=catalog_text, sentence_count=sentence_count))
        await session.commit()

    return {
        "inventory_count": len(product_rows),
        "business_info_count": len(info_pairs),
        "context_text": context_text,
        "catalog_text": catalog_text,
        "catalog_sentence_count": sentence_count,
    }
