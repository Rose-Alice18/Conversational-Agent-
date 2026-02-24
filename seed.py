"""Populate the database with sample inventory and business info."""

import asyncio

from app.database import async_session, engine
from app.models import Base, BusinessInfo, Inventory


async def seed():
    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        products = [
            Inventory(
                name="Wireless Mouse",
                description="Ergonomic wireless mouse with USB receiver",
                price=29.99,
                quantity=50,
                category="electronics",
            ),
            Inventory(
                name="Mechanical Keyboard",
                description="RGB mechanical keyboard with blue switches",
                price=79.99,
                quantity=30,
                category="electronics",
            ),
            Inventory(
                name="USB-C Hub",
                description="7-in-1 USB-C hub with HDMI and ethernet",
                price=45.00,
                quantity=25,
                category="electronics",
            ),
            Inventory(
                name="Notebook A5",
                description="Lined A5 notebook, 200 pages",
                price=8.99,
                quantity=100,
                category="stationery",
            ),
            Inventory(
                name="Ballpoint Pen Pack",
                description="Pack of 10 blue ballpoint pens",
                price=4.50,
                quantity=200,
                category="stationery",
            ),
            Inventory(
                name="Laptop Stand",
                description="Adjustable aluminum laptop stand",
                price=39.99,
                quantity=15,
                category="accessories",
            ),
        ]

        info = [
            BusinessInfo(key="store_name", value="TechShop"),
            BusinessInfo(
                key="hours", value="Monday-Friday 9am-6pm, Saturday 10am-4pm, Sunday Closed"
            ),
            BusinessInfo(key="location", value="123 Main Street, Springfield, IL 62701"),
            BusinessInfo(
                key="return_policy",
                value="30-day returns with original receipt. Items must be unused and in original packaging.",
            ),
            BusinessInfo(
                key="contact",
                value="Email: support@techshop.com | Phone: (555) 123-4567",
            ),
            BusinessInfo(
                key="payment_methods",
                value="Cash, Visa, Mastercard, Apple Pay, Google Pay",
            ),
        ]

        session.add_all(products + info)
        await session.commit()
        print(f"Seeded {len(products)} products and {len(info)} business info entries.")


if __name__ == "__main__":
    asyncio.run(seed())
