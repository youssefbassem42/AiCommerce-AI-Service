#!/usr/bin/env python3
"""
Seed a fake order (store 74101cf9-3827-4bb1-9587-4d2b0f064925) into 'orders'
and dummy notifications into 'ticket_notifications'.
"""

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.infrastructure.mongodb.collections import (  # noqa: E402
    get_orders_collection,
    get_ticket_notifications_collection,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_fake_order")

STORE_ID = "74101cf9-3827-4bb1-9587-4d2b0f064925"
CUSTOMER_ID = "cust_demo_001"
ORDER_ID = STORE_ID

FAKE_ORDER = {
    "_id": ORDER_ID,
    "store_id": STORE_ID,
    "org_id": "",
    "external_id": "ORD-FAKE-001",
    "customer_id": CUSTOMER_ID,
    "customer_email": "demo@example.com",
    "line_items": [
        {
            "id": "li_demo_001",
            "variant_id": None,
            "product_id": "prod_demo_001",
            "title": "Wireless Headphones",
            "quantity": 1,
            "price": {"amount": 129.99, "currency": "USD"},
            "tax_lines": [],
            "discount_allocations": [],
        },
        {
            "id": "li_demo_002",
            "variant_id": None,
            "product_id": "prod_demo_002",
            "title": "USB-C Cable 2m",
            "quantity": 2,
            "price": {"amount": 19.99, "currency": "USD"},
            "tax_lines": [],
            "discount_allocations": [],
        },
    ],
    "shipping_address": {
        "first_name": "Demo",
        "last_name": "Customer",
        "line1": "123 Demo Street",
        "line2": None,
        "city": "Riyadh",
        "state": "Riyadh",
        "zip": "12345",
        "country": "SA",
        "phone": "+966500000000",
    },
    "billing_address": {
        "first_name": "Demo",
        "last_name": "Customer",
        "line1": "123 Demo Street",
        "line2": None,
        "city": "Riyadh",
        "state": "Riyadh",
        "zip": "12345",
        "country": "SA",
        "phone": "+966500000000",
    },
    "subtotal_price": {"amount": 169.97, "currency": "USD"},
    "total_price": {"amount": 169.97, "currency": "USD"},
    "total_tax": {"amount": 0.0, "currency": "USD"},
    "total_discount": {"amount": 0.0, "currency": "USD"},
    "shipping_price": {"amount": 0.0, "currency": "USD"},
    "financial_status": "paid",
    "fulfillment_status": "fulfilled",
    "currency": "USD",
    "notes": "Fake order for demo/testing.",
    "tags": ["demo", "test"],
    "cancelled_at": None,
    "audit": {
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
        "updated_by": "seed_fake_order",
    },
    "metadata": {"source": "seed_fake_order"},
    "created_at": datetime.now(UTC),
    "updated_at": datetime.now(UTC),
    "deleted_at": None,
}

FAKE_NOTIFICATIONS = [
    {
        "_id": "notif_demo_001",
        "ticket_id": "tkt_demo_001",
        "store_id": STORE_ID,
        "customer_id": CUSTOMER_ID,
        "message": "Your refund request is being processed by the finance team.",
        "eta": datetime.now(UTC) + timedelta(hours=8),
        "read": False,
        "created_at": datetime.now(UTC),
    },
    {
        "_id": "notif_demo_002",
        "ticket_id": "tkt_demo_001",
        "store_id": STORE_ID,
        "customer_id": CUSTOMER_ID,
        "message": "A specialist will follow up with you shortly.",
        "eta": datetime.now(UTC) + timedelta(hours=2),
        "read": True,
        "read_at": datetime.now(UTC),
        "created_at": datetime.now(UTC) - timedelta(hours=1),
    },
]


async def main() -> None:
    orders = get_orders_collection()
    notifications = get_ticket_notifications_collection()

    existing_order = await orders.find_one({"_id": ORDER_ID})
    if existing_order:
        logger.info("Order %s already exists; skipping insert.", ORDER_ID)
    else:
        await orders.insert_one(FAKE_ORDER)
        logger.info("Inserted fake order %s.", ORDER_ID)

    for doc in FAKE_NOTIFICATIONS:
        existing = await notifications.find_one({"_id": doc["_id"]})
        if existing:
            logger.info("Notification %s already exists; skipping.", doc["_id"])
            continue
        await notifications.insert_one(doc)
        logger.info("Inserted notification %s.", doc["_id"])

    counts = {
        "orders": await orders.count_documents({"store_id": STORE_ID}),
        "ticket_notifications": await notifications.count_documents({"store_id": STORE_ID}),
    }
    logger.info("Done. Counts for store %s: %s", STORE_ID, counts)


if __name__ == "__main__":
    asyncio.run(main())
