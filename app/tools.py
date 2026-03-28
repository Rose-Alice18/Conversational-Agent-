from langchain_core.tools import tool
from sqlalchemy import func, or_, select

from app.database import async_session
from app.models import BusinessInfo, Product


async def _get_currency(session) -> str:
    """Read currency from business_info; default to GHS."""
    row = (
        await session.execute(
            select(BusinessInfo).where(BusinessInfo.key == "currency")
        )
    ).scalars().first()
    return row.value.strip().upper() if row else "GHS"


@tool
async def search_products(query: str) -> str:
    """Search inventory by keyword across product name, description, category, and SKU.
    Use this for general product searches when the customer gives a keyword or phrase."""
    async with async_session() as session:
        def _build_stmt(q: str):
            return select(Product).where(
                or_(
                    Product.name.ilike(f"%{q}%"),
                    Product.description.ilike(f"%{q}%"),
                    Product.category.ilike(f"%{q}%"),
                    Product.sku.ilike(f"%{q}%"),
                )
            )

        results = (await session.execute(_build_stmt(query))).scalars().all()

        # If full phrase matched nothing, retry with each word individually
        if not results:
            seen_ids = set()
            for word in query.split():
                if len(word) < 3:
                    continue
                word_results = (await session.execute(_build_stmt(word))).scalars().all()
                for r in word_results:
                    if r.id not in seen_ids:
                        seen_ids.add(r.id)
                        results.append(r)

    if not results:
        return f"No products found matching '{query}'."

    async with async_session() as session:
        currency = await _get_currency(session)

    lines = []
    for item in results:
        stock = "in stock" if item.quantity > 0 else "out of stock"
        sku_part = f" [SKU: {item.sku}]" if item.sku else ""
        extra = ""
        if item.extra_data:
            extra_parts = [f"{k}: {v}" for k, v in item.extra_data.items()
                           if not str(v).startswith("http")]
            if extra_parts:
                extra = " | " + ", ".join(extra_parts)
        lines.append(
            f"- {item.name}{sku_part}: {currency} {item.price:.2f} "
            f"({stock}){extra} "
            f"[Category: {item.category}]"
        )
    return "\n".join(lines)


@tool
async def browse_by_category(category: str) -> str:
    """List all products in a specific category.
    Use this when the customer asks to see everything in a department or product type."""
    async with async_session() as session:
        stmt = select(Product).where(Product.category.ilike(f"%{category}%"))
        results = (await session.execute(stmt)).scalars().all()

    if not results:
        return f"No products found in category '{category}'."

    async with async_session() as session:
        currency = await _get_currency(session)

    lines = [f"Products in '{category}':"]
    for item in results:
        stock = "in stock" if item.quantity > 0 else "out of stock"
        lines.append(f"- {item.name}: {currency} {item.price:.2f} ({stock})")
    return "\n".join(lines)


@tool
async def filter_by_price(min_price: float, max_price: float) -> str:
    """Find products within a price range (inclusive on both ends).
    Use this when a customer specifies a budget or asks for products between two prices."""
    async with async_session() as session:
        stmt = (
            select(Product)
            .where(Product.price >= min_price, Product.price <= max_price)
            .order_by(Product.price)
        )
        results = (await session.execute(stmt)).scalars().all()

    async with async_session() as session:
        currency = await _get_currency(session)

    if not results:
        return f"No products found between {currency} {min_price:.2f} and {currency} {max_price:.2f}."

    lines = [f"Products priced between {currency} {min_price:.2f} and {currency} {max_price:.2f}:"]
    for item in results:
        lines.append(f"- {item.name}: {currency} {item.price:.2f} [{item.category}]")
    return "\n".join(lines)


@tool
async def check_product_stock(product_name: str) -> str:
    """Check the stock level for a specific product by name.
    Use this when the customer asks whether something is available or how many are left."""
    async with async_session() as session:
        stmt = select(Product.name, Product.quantity).where(
            Product.name.ilike(f"%{product_name}%")
        )
        results = (await session.execute(stmt)).all()

    if not results:
        return f"No product found matching '{product_name}'."

    lines = []
    for name, qty in results:
        status = "in stock" if qty > 0 else "out of stock"
        lines.append(f"- {name}: {status}")
    return "\n".join(lines)


@tool
async def get_product_details(product_name: str) -> str:
    """Get full details for a specific product including all fields and extra attributes.
    Use this when a customer wants complete information about a particular product,
    or when a customer asks for a photo or image of a product."""
    async with async_session() as session:
        results = (await session.execute(
            select(Product).where(Product.name.ilike(f"%{product_name}%"))
        )).scalars().all()

        # Fallback: retry word by word if full phrase matched nothing
        if not results:
            seen_ids = set()
            results = []
            for word in product_name.split():
                if len(word) < 3:
                    continue
                word_results = (await session.execute(
                    select(Product).where(Product.name.ilike(f"%{word}%"))
                )).scalars().all()
                for r in word_results:
                    if r.id not in seen_ids:
                        seen_ids.add(r.id)
                        results.append(r)

    if not results:
        return f"No product found matching '{product_name}'."

    async with async_session() as session:
        currency = await _get_currency(session)

    sections = []
    for item in results:
        stock_status = "in stock" if item.quantity > 0 else "out of stock"
        lines = [
            f"Name: {item.name}",
            f"Price: {currency} {item.price:.2f}",
            f"Category: {item.category}",
            f"Stock: {stock_status}",
            f"Description: {item.description}",
        ]
        if item.sku:
            lines.append(f"SKU: {item.sku}")
        if item.extra_data:
            for k, v in item.extra_data.items():
                is_image = any(kw in k.lower() for kw in ["image", "photo", "picture", "img", "url"])
                is_url = str(v).strip().startswith("http")
                if is_image and is_url:
                    lines.append(f"Image URL: [IMAGE:{str(v).strip()}]")
                else:
                    lines.append(f"{k.replace('_', ' ').title()}: {v}")
        sections.append("\n".join(lines))

    return "\n\n---\n\n".join(sections)


@tool
async def get_inventory_overview() -> str:
    """Get a high-level summary of the entire inventory: total products, categories,
    price range, and stock counts. Use this when a customer asks what the store sells
    or wants a general overview."""
    async with async_session() as session:
        stats = (
            await session.execute(
                select(
                    func.count(Product.id),
                    func.min(Product.price),
                    func.max(Product.price),
                    func.sum(Product.quantity),
                )
            )
        ).one()
        total, min_price, max_price, _ = stats

        out_of_stock = (
            await session.execute(
                select(func.count(Product.id)).where(Product.quantity == 0)
            )
        ).scalar_one()

        categories = [
            r[0]
            for r in (await session.execute(select(Product.category).distinct())).all()
        ]

        samples = [
            r[0]
            for r in (await session.execute(select(Product.name).limit(5))).all()
        ]

        currency = await _get_currency(session)

    if total == 0:
        return "The inventory is currently empty."

    in_stock = total - out_of_stock
    cat_list = ", ".join(sorted(categories))
    sample_list = ", ".join(samples)

    return (
        f"Inventory Overview:\n"
        f"- {total} products across {len(categories)} categories: {cat_list}\n"
        f"- Price range: {currency} {min_price:.2f} — {currency} {max_price:.2f}\n"
        f"- {in_stock} items in stock, {out_of_stock} out of stock\n"
        f"- Example products: {sample_list}"
    )


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


all_tools = [
    search_products,
    browse_by_category,
    filter_by_price,
    check_product_stock,
    get_product_details,
    get_inventory_overview,
    get_business_info,
]
