#!/usr/bin/env python3
"""
Comprehensive seed: populates ALL collections for 2 demo stores.

Collections seeded:
  products, categories, customers, orders, inventory,
  conversations, messages, ticket_analysis, recommendations,
  bundle_suggestions, bundle_tracking, dashboard_insights,
  api_keys, store_capabilities, audit_logs, entities,
  knowledge_documents, knowledge_chunks, knowledge_uploads,
  knowledge_versions, integration_connections

Collections NOT seeded (app-managed or runtime):
  prompts, prompt_history, runtime_logs, knowledge_jobs,
  knowledge_business_summaries
"""

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from app.core.config import settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_all")

NOW = datetime.now(UTC)
TENANTS = {
    "store_elec_002": {"name": "TechPro Electronics", "org_id": "org_elec_002", "currency": "USD"},
    "store_fashion_001": {"name": "StyleHub Fashion", "org_id": "org_fashion_001", "currency": "USD"},
}

# ─────────────────────────────────────────────
#  DATA: PRODUCTS, CATEGORIES, CUSTOMERS, etc.
# ─────────────────────────────────────────────

ELECTRONICS = {
    "products": [
        {
            "title": "MacBook Pro 16-inch M3 Max",
            "external_id": "prod_elec_001",
            "handle": "macbook-pro-16-m3-max",
            "status": "active",
            "vendor": "Apple",
            "product_type": "Laptop",
            "tags": ["premium", "laptop", "apple"],
            "variants": [
                {
                    "id": "var_elec_001",
                    "sku": "MBP-M3-16-36-1TB",
                    "title": "M3 Max / 36GB / 1TB",
                    "price": {"amount": 3499.99, "currency": "USD"},
                    "inventory_quantity": 15,
                }
            ],
            "category_id": "cat_elec_001",
            "max_discount_pct": 10.0,
        },
        {
            "title": "Dell XPS 15 OLED",
            "external_id": "prod_elec_002",
            "handle": "dell-xps-15-oled",
            "status": "active",
            "vendor": "Dell",
            "product_type": "Laptop",
            "tags": ["laptop", "dell"],
            "variants": [
                {
                    "id": "var_elec_002",
                    "sku": "DEL-XPS-15-i9-32-1TB",
                    "title": "i9 / 32GB / 1TB",
                    "price": {"amount": 2499.99, "currency": "USD"},
                    "inventory_quantity": 23,
                }
            ],
            "category_id": "cat_elec_001",
            "max_discount_pct": 15.0,
        },
        {
            "title": "LG 27-inch 4K Monitor",
            "external_id": "prod_elec_003",
            "handle": "lg-27-4k-monitor",
            "status": "active",
            "vendor": "LG",
            "product_type": "Monitor",
            "tags": ["monitor", "4k", "lg"],
            "variants": [
                {
                    "id": "var_elec_003",
                    "sku": "LG-27UP850N",
                    "title": "27-inch 4K IPS",
                    "price": {"amount": 499.99, "currency": "USD"},
                    "inventory_quantity": 34,
                }
            ],
            "category_id": "cat_elec_002",
            "max_discount_pct": 12.0,
        },
        {
            "title": "Logitech MX Mechanical Keyboard",
            "external_id": "prod_elec_004",
            "handle": "logitech-mx-mechanical",
            "status": "active",
            "vendor": "Logitech",
            "product_type": "Accessory",
            "tags": ["keyboard", "mechanical", "logitech"],
            "variants": [
                {
                    "id": "var_elec_004",
                    "sku": "LOG-MX-MECH",
                    "title": "Tactile Switches",
                    "price": {"amount": 149.99, "currency": "USD"},
                    "inventory_quantity": 120,
                }
            ],
            "category_id": "cat_elec_003",
            "max_discount_pct": 15.0,
        },
        {
            "title": "Sony WH-1000XM5 Headphones",
            "external_id": "prod_elec_005",
            "handle": "sony-wh1000xm5",
            "status": "active",
            "vendor": "Sony",
            "product_type": "Audio",
            "tags": ["headphones", "noise-cancelling", "sony"],
            "variants": [
                {
                    "id": "var_elec_005",
                    "sku": "SONY-WH1000XM5",
                    "title": "Black",
                    "price": {"amount": 349.99, "currency": "USD"},
                    "inventory_quantity": 78,
                }
            ],
            "category_id": "cat_elec_004",
            "max_discount_pct": 10.0,
        },
    ],
    "categories": [
        {"external_id": "cat_elec_001", "name": "Laptops", "description": "Laptop computers", "handle": "laptops"},
        {"external_id": "cat_elec_002", "name": "Monitors", "description": "Monitors & displays", "handle": "monitors"},
        {
            "external_id": "cat_elec_003",
            "name": "Accessories",
            "description": "Peripherals & accessories",
            "handle": "accessories",
        },
        {"external_id": "cat_elec_004", "name": "Audio", "description": "Headphones & audio", "handle": "audio"},
    ],
    "customers": [
        {
            "external_id": "cust_elec_001",
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "Johnson",
            "phone": "+1-555-0101",
            "accepts_marketing": True,
        },
        {
            "external_id": "cust_elec_002",
            "email": "bob@example.com",
            "first_name": "Bob",
            "last_name": "Smith",
            "phone": "+1-555-0102",
            "accepts_marketing": False,
        },
    ],
    "tickets": [
        {
            "ticket_id": "tkt_elec_001",
            "customer_id": "cust_elec_001",
            "sentiment": "negative",
            "category": "shipping_delay",
            "summary": "Order #ORD-E001 delayed by 5 days beyond promised delivery window",
            "priority": "high",
            "status": "open",
            "suggested_response": "We apologize for the delay. We have escalated this to our shipping team and will update you within 24 hours.",
        },
    ],
}

FASHION = {
    "products": [
        {
            "title": "Classic Leather Jacket",
            "external_id": "prod_fash_001",
            "handle": "classic-leather-jacket",
            "status": "active",
            "vendor": "UrbanEdge",
            "product_type": "Outerwear",
            "tags": ["leather", "jacket", "premium"],
            "variants": [
                {
                    "id": "var_fash_001",
                    "sku": "FASH-LJ-001",
                    "title": "Black / Medium",
                    "price": {"amount": 299.99, "currency": "USD"},
                    "inventory_quantity": 25,
                }
            ],
            "category_id": "cat_fash_001",
            "max_discount_pct": 15.0,
        },
        {
            "title": "Designer Denim Jeans",
            "external_id": "prod_fash_002",
            "handle": "designer-denim-jeans",
            "status": "active",
            "vendor": "UrbanEdge",
            "product_type": "Bottoms",
            "tags": ["denim", "jeans", "designer"],
            "variants": [
                {
                    "id": "var_fash_002",
                    "sku": "FASH-DJ-001",
                    "title": "Blue / 32W x 34L",
                    "price": {"amount": 89.99, "currency": "USD"},
                    "inventory_quantity": 80,
                }
            ],
            "category_id": "cat_fash_002",
            "max_discount_pct": 20.0,
        },
        {
            "title": "Merino Wool Sweater",
            "external_id": "prod_fash_003",
            "handle": "merino-wool-sweater",
            "status": "active",
            "vendor": "CozyLuxe",
            "product_type": "Tops",
            "tags": ["wool", "sweater", "merino"],
            "variants": [
                {
                    "id": "var_fash_003",
                    "sku": "FASH-MW-001",
                    "title": "Charcoal / Medium",
                    "price": {"amount": 129.99, "currency": "USD"},
                    "inventory_quantity": 50,
                }
            ],
            "category_id": "cat_fash_003",
            "max_discount_pct": 15.0,
        },
        {
            "title": "Leather Crossbody Bag",
            "external_id": "prod_fash_004",
            "handle": "leather-crossbody-bag",
            "status": "active",
            "vendor": "UrbanEdge",
            "product_type": "Bags",
            "tags": ["leather", "bag", "crossbody"],
            "variants": [
                {
                    "id": "var_fash_004",
                    "sku": "FASH-CB-001",
                    "title": "Tan",
                    "price": {"amount": 159.99, "currency": "USD"},
                    "inventory_quantity": 35,
                }
            ],
            "category_id": "cat_fash_004",
            "max_discount_pct": 12.0,
        },
        {
            "title": "Aviator Sunglasses",
            "external_id": "prod_fash_005",
            "handle": "aviator-sunglasses",
            "status": "active",
            "vendor": "EleganceStudio",
            "product_type": "Accessories",
            "tags": ["sunglasses", "aviator", "polarized"],
            "variants": [
                {
                    "id": "var_fash_005",
                    "sku": "FASH-AS-001",
                    "title": "Gold / Green Polarized",
                    "price": {"amount": 149.99, "currency": "USD"},
                    "inventory_quantity": 75,
                }
            ],
            "category_id": "cat_fash_005",
            "max_discount_pct": 15.0,
        },
    ],
    "categories": [
        {"external_id": "cat_fash_001", "name": "Outerwear", "description": "Jackets & coats", "handle": "outerwear"},
        {"external_id": "cat_fash_002", "name": "Bottoms", "description": "Jeans & pants", "handle": "bottoms"},
        {"external_id": "cat_fash_003", "name": "Tops", "description": "Shirts & sweaters", "handle": "tops"},
        {"external_id": "cat_fash_004", "name": "Bags", "description": "Handbags & backpacks", "handle": "bags"},
        {
            "external_id": "cat_fash_005",
            "name": "Accessories",
            "description": "Scarves, belts & sunglasses",
            "handle": "accessories",
        },
    ],
    "customers": [
        {
            "external_id": "cust_fash_001",
            "email": "carol@example.com",
            "first_name": "Carol",
            "last_name": "Davis",
            "phone": "+1-555-0201",
            "accepts_marketing": True,
        },
        {
            "external_id": "cust_fash_002",
            "email": "dave@example.com",
            "first_name": "Dave",
            "last_name": "Wilson",
            "phone": "+1-555-0202",
            "accepts_marketing": True,
        },
    ],
    "tickets": [
        {
            "ticket_id": "tkt_fash_001",
            "customer_id": "cust_fash_001",
            "sentiment": "neutral",
            "category": "size_exchange",
            "summary": "Ordered size M leather jacket but need size L — request exchange",
            "priority": "medium",
            "status": "in_progress",
            "suggested_response": "We can process an exchange for size L. Please confirm the item is unworn with tags attached.",
        },
    ],
}


def build_doc(store_id: str, org_id: str, data: dict, extra: dict | None = None) -> dict:
    doc = {
        "store_id": store_id,
        "organization_id": org_id,
        "created_at": NOW,
        "updated_at": NOW,
        **data,
    }
    if extra:
        doc.update(extra)
    return doc


async def clean_and_seed(collection, filter_key: str, store_id: str, docs: list[dict]):
    count = len(docs)
    if count == 0:
        return 0
    await collection.delete_many({filter_key: store_id})
    if docs:
        await collection.insert_many(docs, ordered=False)
    logger.info("  [%s] %d docs seeded", collection.name, count)
    return count


async def seed_prompts(db):
    """Seed default prompts into the prompts collection."""
    from app.infrastructure.prompts.seed import DEFAULT_PROMPTS

    existing_keys = set()
    async for d in db["prompts"].find({}, {"key": 1}):
        existing_keys.add(d["key"])

    docs = []
    for key, data in DEFAULT_PROMPTS.items():
        if key in existing_keys:
            continue
        docs.append(
            {
                "key": key,
                "type": data.get("type", "system"),
                "content": data["content"],
                "description": data.get("description", ""),
                "tags": data.get("tags", []),
                "version": 1,
                "is_active": True,
                "variables": data.get("variables", []),
                "created_at": NOW,
                "updated_at": NOW,
            }
        )
    if docs:
        await db["prompts"].insert_many(docs, ordered=False)
    logger.info("  [prompts] %d new docs seeded (%d existed)", len(docs), len(existing_keys))
    return len(docs)


async def seed_all():
    client = AsyncIOMotorClient(
        settings.MONGO_SETTINGS.MONGO_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
    )
    db = client[settings.MONGO_SETTINGS.MONGO_DB]
    total = 0

    total += await seed_prompts(db)

    for store_id, cfg in TENANTS.items():
        org_id = cfg["org_id"]
        name = cfg["name"]
        currency = cfg["currency"]
        logger.info("── Seeding %s (%s) ──", name, store_id)

        is_elec = "elec" in store_id
        data = ELECTRONICS if is_elec else FASHION

        # ── 1. Products ──
        product_docs = []
        for p in data["products"]:
            doc = build_doc(
                store_id,
                org_id,
                {
                    "external_id": p["external_id"],
                    "title": p["title"],
                    "description": p.get("description", ""),
                    "handle": p["handle"],
                    "status": p["status"],
                    "vendor": p["vendor"],
                    "product_type": p["product_type"],
                    "tags": p["tags"],
                    "variants": p["variants"],
                    "category_id": p["category_id"],
                    "metadata": {"max_discount_pct": p["max_discount_pct"]},
                },
            )
            product_docs.append(doc)
        total += await clean_and_seed(db["products"], "store_id", store_id, product_docs)

        # ── 2. Categories ──
        cat_docs = []
        for c in data["categories"]:
            doc = build_doc(
                store_id,
                org_id,
                {
                    "external_id": c["external_id"],
                    "name": c["name"],
                    "description": c["description"],
                    "handle": c["handle"],
                    "org_id": org_id,
                },
            )
            cat_docs.append(doc)
        total += await clean_and_seed(db["categories"], "store_id", store_id, cat_docs)

        # ── 3. Customers ──
        cust_docs = []
        for c in data["customers"]:
            doc = build_doc(
                store_id,
                org_id,
                {
                    "external_id": c["external_id"],
                    "email": c["email"],
                    "first_name": c["first_name"],
                    "last_name": c["last_name"],
                    "phone": c["phone"],
                    "tags": [],
                    "accepts_marketing": c["accepts_marketing"],
                    "metadata": {},
                },
            )
            cust_docs.append(doc)
        total += await clean_and_seed(db["customers"], "store_id", store_id, cust_docs)

        # ── 4. Orders ──
        prefix = "E" if is_elec else "F"
        prod = data["products"]
        cust = data["customers"]
        order_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "external_id": f"ORD-{prefix}001",
                    "customer_id": cust[0]["external_id"],
                    "customer_email": cust[0]["email"],
                    "line_items": [
                        {
                            "id": f"li_{prefix}001",
                            "variant_id": prod[0]["variants"][0]["id"],
                            "product_id": prod[0]["external_id"],
                            "title": prod[0]["title"],
                            "quantity": 1,
                            "price": prod[0]["variants"][0]["price"],
                        }
                    ],
                    "subtotal_price": {"amount": prod[0]["variants"][0]["price"]["amount"], "currency": currency},
                    "total_price": {"amount": prod[0]["variants"][0]["price"]["amount"] * 1.08, "currency": currency},
                    "total_tax": {
                        "amount": round(prod[0]["variants"][0]["price"]["amount"] * 0.08, 2),
                        "currency": currency,
                    },
                    "financial_status": "paid",
                    "fulfillment_status": "fulfilled",
                    "currency": currency,
                    "shipping_address": {
                        "first_name": cust[0]["first_name"],
                        "last_name": cust[0]["last_name"],
                        "line1": "123 Main St",
                        "city": "Portland",
                        "state": "OR",
                        "zip": "97201",
                        "country": "US",
                    },
                    "billing_address": {
                        "first_name": cust[0]["first_name"],
                        "last_name": cust[0]["last_name"],
                        "line1": "123 Main St",
                        "city": "Portland",
                        "state": "OR",
                        "zip": "97201",
                        "country": "US",
                    },
                    "tags": ["seed"],
                },
            ),
        ]
        total += await clean_and_seed(db["orders"], "store_id", store_id, order_docs)

        # ── 5. Inventory ──
        inv_docs = []
        for p in prod:
            for v in p["variants"]:
                inv_docs.append(
                    build_doc(
                        store_id,
                        org_id,
                        {
                            "product_id": p["external_id"],
                            "variant_id": v["id"],
                            "external_id": f"inv_{v['id']}",
                            "quantity": v["inventory_quantity"],
                            "available": v["inventory_quantity"],
                            "committed": 0,
                            "incoming": 0,
                            "location_name": "Main Warehouse",
                            "low_stock_threshold": 5,
                        },
                    )
                )
        total += await clean_and_seed(db["inventory"], "store_id", store_id, inv_docs)

        # ── 6. Conversations + Messages ──
        prefix_l = "elec" if is_elec else "fash"
        conv_id = f"conv_{prefix_l}_001"
        conv_docs = [
            {
                "store_id": store_id,
                "customer_id": cust[0]["external_id"],
                "status": "active",
                "created_at": NOW,
                "updated_at": NOW,
            }
        ]
        await db["conversations"].delete_many({"store_id": store_id})
        await db["conversations"].insert_many(conv_docs, ordered=False)
        logger.info("  [conversations] 1 doc seeded")
        total += 1

        msg_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "conversation_id": conv_id,
                    "role": "user",
                    "content": f"Hi, I'm interested in your {prod[0]['title']}. Can you tell me more?",
                    "sender": "user",
                    "timestamp": NOW,
                    "metadata": {},
                },
            ),
            build_doc(
                store_id,
                org_id,
                {
                    "conversation_id": conv_id,
                    "role": "assistant",
                    "content": f"Of course! The {prod[0]['title']} is one of our best-selling items. It's priced at ${prod[0]['variants'][0]['price']['amount']:.2f} and available in stock. Would you like to know more about the specifications?",
                    "sender": "assistant",
                    "timestamp": NOW + timedelta(seconds=5),
                    "metadata": {},
                },
            ),
        ]
        total += await clean_and_seed(db["messages"], "store_id", store_id, msg_docs)

        # ── 7. Ticket Analysis ──
        ticket_docs = []
        for t in data["tickets"]:
            ticket_docs.append(
                build_doc(
                    store_id,
                    org_id,
                    {
                        "ticket_id": t["ticket_id"],
                        "customer_id": t["customer_id"],
                        "sentiment": t["sentiment"],
                        "category": t["category"],
                        "summary": t["summary"],
                        "priority": t["priority"],
                        "status": t.get("status", "open"),
                        "suggested_response": t["suggested_response"],
                        "analyzed_at": NOW,
                    },
                )
            )
        total += await clean_and_seed(db["ticket_analysis"], "store_id", store_id, ticket_docs)

        # ── 8. Recommendations ──
        rec_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "conversation_id": conv_id,
                    "customer_id": cust[0]["external_id"],
                    "recommended_product_ids": [p["external_id"] for p in prod[:3]],
                    "accepted": True,
                    "rationale": f"Based on browsing history and popular items in {name}",
                    "created_at": NOW,
                },
            ),
        ]
        total += await clean_and_seed(db["recommendations"], "store_id", store_id, rec_docs)

        # ── 9. Bundle Suggestions ──
        bundle_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "title": f"Starter Kit ({name})",
                    "product_ids": [p["external_id"] for p in prod[:2]],
                    "total_price": round(sum(p["variants"][0]["price"]["amount"] for p in prod[:2]), 2),
                    "discount_percentage": 10.0,
                    "status": "active",
                },
            ),
        ]
        total += await clean_and_seed(db["bundle_suggestions"], "store_id", store_id, bundle_docs)

        # ── 10. Bundle Tracking ──
        tracking_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "bundle_key": f"starter_kit_{prefix_l}",
                    "product_ids": [p["external_id"] for p in prod[:2]],
                    "discount_pct": 10.0,
                    "total_original": round(sum(p["variants"][0]["price"]["amount"] for p in prod[:2]), 2),
                    "total_discount": round(sum(p["variants"][0]["price"]["amount"] for p in prod[:2]) * 0.1, 2),
                    "promo_code": f"STARTER{prefix}",
                    "copy_count": 42,
                    "is_top": True,
                    "first_copied_at": NOW - timedelta(days=30),
                    "last_copied_at": NOW - timedelta(hours=2),
                },
            ),
        ]
        total += await clean_and_seed(db["bundle_tracking"], "store_id", store_id, tracking_docs)

        # ── 11. Dashboard Insights ──
        insight_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "recommendations": [
                        f"Stock refill needed for {prod[0]['title']} — only {prod[0]['variants'][0]['inventory_quantity']} units left",
                        f"Bundle promotion on {prod[0]['title']} + {prod[1]['title']} has 42 copies this month",
                    ],
                    "metadata": {"total_products": len(prod), "total_customers": len(cust)},
                },
            ),
        ]
        total += await clean_and_seed(db["dashboard_insights"], "store_id", store_id, insight_docs)

        # ── 12. API Keys ──
        api_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "key_hash": f"hash_{store_id}_admin",
                    "key_prefix": f"ak_{store_id.split('_')[1][:5]}",
                    "name": f"Admin Key - {name}",
                    "scopes": ["admin:read", "admin:write", "commerce:read", "commerce:write"],
                    "is_active": True,
                    "created_at": NOW,
                    "updated_at": NOW,
                },
            ),
        ]
        total += await clean_and_seed(db["api_keys"], "store_id", store_id, api_docs)

        # ── 13. Store Capabilities ──
        caps_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "capabilities": {
                        "ai_assistant": True,
                        "knowledge_base": True,
                        "bundle_discounts": True,
                        "ticket_analysis": True,
                        "product_recommendations": True,
                        "dashboard_insights": True,
                    },
                    "auto_detected": {
                        "has_products": True,
                        "has_categories": True,
                        "has_orders": True,
                        "has_customers": True,
                    },
                },
            ),
        ]
        total += await clean_and_seed(db["store_capabilities"], "store_id", store_id, caps_docs)

        # ── 14. Audit Logs ──
        audit_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "action": "seed.data",
                    "actor_id": "system",
                    "actor_type": "system",
                    "resource_type": "seed",
                    "resource_id": store_id,
                    "tenant_id": store_id,
                    "details": {"script": "seed_all_data.py", "timestamp": NOW.isoformat()},
                    "outcome": "success",
                    "timestamp": NOW,
                },
            ),
        ]
        total += await clean_and_seed(db["audit_logs"], "store_id", store_id, audit_docs)

        # ── 15. Knowledge Documents ──
        doc_id = f"doc_{prefix_l}_001"
        kb_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "title": f"{name} Shipping Policy",
                    "source_url": None,
                    "status": "active",
                    "language": "en",
                    "chunking_strategy": "semantic",
                    "metadata": {"store_name": name},
                },
            ),
        ]
        await db["knowledge_documents"].delete_many({"store_id": store_id})
        await db["knowledge_documents"].insert_many(kb_docs, ordered=False)
        logger.info("  [knowledge_documents] 1 doc seeded")
        total += 1

        # ── 16. Knowledge Chunks ──
        content = (
            "We offer free standard shipping on all orders over $50. Standard shipping takes 3-5 business days."
            if is_elec
            else "Free standard shipping on orders over $75. Standard delivery takes 4-7 business days."
        )
        chunk_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "document_id": doc_id,
                    "content": content,
                    "chunk_index": 0,
                    "embedding_id": None,
                    "metadata": {"doc_title": f"{name} Shipping Policy"},
                },
            ),
        ]
        total += await clean_and_seed(db["knowledge_chunks"], "store_id", store_id, chunk_docs)

        # ── 17. Knowledge Uploads ──
        upload_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "original_filename": "shipping_policy.pdf",
                    "stored_filename": f"shipping_policy_{prefix_l}.pdf",
                    "file_path": f"/data/uploads/{store_id}/shipping_policy.pdf",
                    "file_size": 24576,
                    "mime_type": "application/pdf",
                    "extension": "pdf",
                    "checksum": f"sha256_{prefix_l}_001",
                    "content_type": "policy",
                    "uploaded_by": "system",
                    "organization_id": org_id,
                    "knowledge_scope": "store",
                    "status": "uploaded",
                    "document_metadata": {"title": f"{name} Shipping Policy"},
                    "virus_scan_status": "clean",
                },
            ),
        ]
        total += await clean_and_seed(db["knowledge_uploads"], "store_id", store_id, upload_docs)

        # ── 18. Knowledge Versions ──
        version_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "organization_id": org_id,
                    "knowledge_scope": "store",
                    "version_number": 1,
                    "status": "active",
                    "metadata": {"store_name": name, "seeded_at": NOW.isoformat()},
                },
            ),
        ]
        total += await clean_and_seed(db["knowledge_versions"], "store_id", store_id, version_docs)

        # ── 19. Integration Connections ──
        integ_docs = [
            build_doc(
                store_id,
                org_id,
                {
                    "organization_id": org_id,
                    "name": f"{name} Shopify Sync",
                    "platform_name": "shopify",
                    "status": "connected",
                    "spec_version": "2024-01",
                    "audit": {"created_at": NOW, "updated_at": NOW, "updated_by": "system"},
                },
            ),
        ]
        total += await clean_and_seed(db["integration_connections"], "store_id", store_id, integ_docs)

    # ── Entities (shared FAQ/policy per tenant) ──
    FAQ_ENTRIES = [
        {
            "external_id": "faq_001",
            "question": "What is your return policy?",
            "answer": "We accept returns within 30 days of purchase.",
        },
        {
            "external_id": "faq_002",
            "question": "How long does shipping take?",
            "answer": "Standard shipping 3-5 business days; Express 1-2 business days.",
        },
        {
            "external_id": "faq_003",
            "question": "What payment methods do you accept?",
            "answer": "Visa, Mastercard, Amex, PayPal, and Apple Pay.",
        },
    ]
    POLICY_ENTRIES = [
        {
            "external_id": "policy_001",
            "title": "Refund Policy",
            "content": "Full refunds within 30 days in original condition.",
        },
        {
            "external_id": "policy_002",
            "title": "Privacy Policy",
            "content": "We do not share customer data with third parties except shipping carriers.",
        },
    ]

    for store_id, cfg in TENANTS.items():
        org_id = cfg["org_id"]
        prefix_empty = await db["entities"].count_documents({"store_id": store_id})
        if prefix_empty > 0:
            await db["entities"].delete_many({"store_id": store_id})
        now = NOW
        entity_docs = []
        for faq in FAQ_ENTRIES:
            entity_docs.append(
                {
                    "store_id": store_id,
                    "organization_id": org_id,
                    "entity_type": "faq",
                    "external_id": faq["external_id"],
                    "data": {"question": faq["question"], "answer": faq["answer"]},
                    "synced_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        for pol in POLICY_ENTRIES:
            entity_docs.append(
                {
                    "store_id": store_id,
                    "organization_id": org_id,
                    "entity_type": "policy",
                    "external_id": pol["external_id"],
                    "data": {"title": pol["title"], "content": pol["content"]},
                    "synced_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if entity_docs:
            await db["entities"].insert_many(entity_docs, ordered=False)
            logger.info("  [entities] %d docs seeded for %s", len(entity_docs), cfg["name"])
            total += len(entity_docs)

    client.close()
    return total


async def main():
    print("\n" + "=" * 72)
    print("  SEED ALL DATA: 2 Tenants x 20+ Collections + Prompts")
    print("=" * 72)

    try:
        count = await seed_all()
        print(f"\n  [PASS] {count} total documents seeded across all collections")
    except Exception as e:
        print(f"\n  [FAIL] {e}")
        raise
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
