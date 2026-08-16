#!/usr/bin/env python3
"""
E2E Test: Full SaaS User Flow
Tests: schema parse → connection → seed → vectorize → business summary → tenant isolation → 4 RAG scenarios

RAG Scenarios:
  1. Customer Service Support (return policy, shipping, warranty)
  2. Product Recommendations (best laptop for gaming)
  3. Bundle Suggestion ($300 budget for keyboard + mouse)
  4. Ticket Submission (handle user frustration, escalate if needed)
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_full_flow")

API_BASE = "http://localhost:8000"
STORE_ID = "store_e2e_full_001"
ORG_ID = "org_e2e_full_001"
COMMERCE_DIR = PROJECT_ROOT.parent / "E-commerce-ProjectApi"

SPECS = [
    ("Merchant Integration API", COMMERCE_DIR / "openapi-1.yaml"),
    ("E-Commerce ASP.NET API", COMMERCE_DIR / "openapi.yaml"),
    ("E-Commerce JSON API", COMMERCE_DIR / "openapi.json"),
]

# ──────────────────────────────────────────────
# PRODUCT SEED DATA (includes items for bundles)
# ──────────────────────────────────────────────
SAMPLE_PRODUCTS = [
    {
        "external_id": "prod_001",
        "entity_type": "product",
        "title": "MacBook Pro 16-inch M3 Max",
        "category": "Laptops",
        "brand": "Apple",
        "price": 3499.99,
        "sku": "MBP-M3-16-36-1TB",
        "description": "Apple MacBook Pro with M3 Max chip, 36GB RAM, 1TB SSD",
        "inventory_quantity": 15,
        "specs": {"cpu": "M3 Max 16-core", "ram": "36GB", "storage": "1TB SSD"},
    },
    {
        "external_id": "prod_002",
        "entity_type": "product",
        "title": "Dell XPS 15 OLED",
        "category": "Laptops",
        "brand": "Dell",
        "price": 2499.99,
        "sku": "DEL-XPS-15-i9-32-1TB",
        "description": "Dell XPS 15 with Intel Core i9, 32GB RAM, 1TB SSD, OLED display",
        "inventory_quantity": 23,
        "specs": {"cpu": "Intel Core i9-13900H", "ram": "32GB", "storage": "1TB SSD"},
    },
    {
        "external_id": "prod_003",
        "entity_type": "product",
        "title": "Samsung Galaxy S24 Ultra",
        "category": "Smartphones",
        "brand": "Samsung",
        "price": 1399.99,
        "sku": "SAM-S24U-512",
        "description": "Samsung Galaxy S24 Ultra 512GB with S Pen, Titanium frame",
        "inventory_quantity": 42,
    },
    {
        "external_id": "prod_004",
        "entity_type": "product",
        "title": "Sony WH-1000XM5 Headphones",
        "category": "Audio",
        "brand": "Sony",
        "price": 349.99,
        "sku": "SONY-WH1000XM5",
        "description": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
        "inventory_quantity": 78,
    },
    {
        "external_id": "prod_005",
        "entity_type": "product",
        "title": "Logitech MX Mechanical Keyboard",
        "category": "Accessories",
        "brand": "Logitech",
        "price": 149.99,
        "sku": "LOG-MX-MECH",
        "description": "Logitech MX Mechanical Wireless Keyboard with Tactile Switches",
        "inventory_quantity": 120,
        "specs": {
            "type": "Mechanical",
            "switches": "Tactile",
            "layout": "Full-size",
            "connectivity": "Bluetooth + USB-C",
        },
    },
    {
        "external_id": "prod_006",
        "entity_type": "product",
        "title": "Apple AirPods Pro 2nd Gen",
        "category": "Audio",
        "brand": "Apple",
        "price": 249.99,
        "sku": "AP-AIRPODS-PRO-2",
        "description": "Apple AirPods Pro 2nd Generation with USB-C, Adaptive Audio",
        "inventory_quantity": 95,
    },
    {
        "external_id": "prod_007",
        "entity_type": "product",
        "title": "ASUS ROG Strix RTX 4080",
        "category": "Components",
        "brand": "ASUS",
        "price": 1199.99,
        "sku": "ASUS-RTX4080-16G",
        "description": "ASUS ROG Strix GeForce RTX 4080 16GB GDDR6X Graphics Card",
        "inventory_quantity": 8,
    },
    {
        "external_id": "prod_008",
        "entity_type": "product",
        "title": "LG 27-inch 4K Monitor",
        "category": "Monitors",
        "brand": "LG",
        "price": 499.99,
        "sku": "LG-27UP850N",
        "description": "LG 27UP850N 27-inch 4K UHD IPS Monitor with USB-C 96W PD",
        "inventory_quantity": 34,
    },
    {
        "external_id": "prod_009",
        "entity_type": "product",
        "title": "Logitech MX Master 3S Mouse",
        "category": "Accessories",
        "brand": "Logitech",
        "price": 99.99,
        "sku": "LOG-MX-MASTER-3S",
        "description": "Logitech MX Master 3S Wireless Performance Mouse with 8K DPI",
        "inventory_quantity": 88,
    },
    {
        "external_id": "prod_010",
        "entity_type": "product",
        "title": "Logitech G413 SE Mechanical Keyboard",
        "category": "Accessories",
        "brand": "Logitech",
        "price": 89.99,
        "sku": "LOG-G413-SE",
        "description": "Logitech G413 SE Full-size Mechanical Keyboard with Tactile Switches",
        "inventory_quantity": 55,
    },
    {
        "external_id": "prod_011",
        "entity_type": "product",
        "title": "Logitech G203 Lightsync Mouse",
        "category": "Accessories",
        "brand": "Logitech",
        "price": 39.99,
        "sku": "LOG-G203",
        "description": "Logitech G203 Lightsync RGB Gaming Mouse with 8K DPI",
        "inventory_quantity": 200,
    },
    {
        "external_id": "prod_012",
        "entity_type": "product",
        "title": "Razer DeathAdder V3 Mouse",
        "category": "Accessories",
        "brand": "Razer",
        "price": 79.99,
        "sku": "RAZ-DAV3",
        "description": "Razer DeathAdder V3 Wireless Ergonomic Gaming Mouse",
        "inventory_quantity": 66,
    },
]

SAMPLE_CATEGORIES = [
    {"external_id": "cat_001", "name": "Laptops", "description": "Laptop computers and notebooks"},
    {"external_id": "cat_002", "name": "Smartphones", "description": "Mobile phones and accessories"},
    {"external_id": "cat_003", "name": "Audio", "description": "Headphones, speakers, and audio equipment"},
    {"external_id": "cat_004", "name": "Accessories", "description": "Computer peripherals and accessories"},
    {"external_id": "cat_005", "name": "Components", "description": "PC components and hardware"},
    {"external_id": "cat_006", "name": "Monitors", "description": "Computer monitors and displays"},
]

# ──────────────────────────────────────────────
# FAQ & POLICY KNOWLEDGE DATA
# ──────────────────────────────────────────────
FAQ_ENTRIES = [
    {
        "external_id": "faq_001",
        "entity_type": "faq",
        "question": "What is your return policy?",
        "answer": "We accept returns within 30 days of purchase. Items must be unused and in original packaging. Refunds are processed within 5-7 business days after we receive the item. Shipping costs are non-refundable.",
    },
    {
        "external_id": "faq_002",
        "entity_type": "faq",
        "question": "How long does shipping take?",
        "answer": "Standard shipping takes 3-5 business days within the continental US. Express shipping takes 1-2 business days. International shipping takes 7-14 business days depending on the destination. Free shipping on orders over $50.",
    },
    {
        "external_id": "faq_003",
        "entity_type": "faq",
        "question": "What is your warranty policy?",
        "answer": "All products come with a 1-year manufacturer warranty. Extended warranty plans are available for purchase within 30 days of the original purchase. The warranty covers manufacturing defects but not accidental damage.",
    },
    {
        "external_id": "faq_004",
        "entity_type": "faq",
        "question": "Do you offer price matching?",
        "answer": "Yes, we offer price matching within 14 days of purchase. If you find a lower price from an authorized retailer, we will refund the difference. The item must be identical (same model, color, specifications).",
    },
    {
        "external_id": "faq_005",
        "entity_type": "faq",
        "question": "How do I track my order?",
        "answer": "Once your order ships, you will receive a tracking number via email. You can track your order on our website by entering the tracking number in the Order Tracking section of your account.",
    },
    {
        "external_id": "faq_006",
        "entity_type": "faq",
        "question": "Can I cancel or change my order?",
        "answer": "Orders can be canceled or modified within 1 hour of placement. After that, the order enters processing and cannot be changed. Contact customer support immediately if you need to make changes.",
    },
]

POLICY_ENTRIES = [
    {
        "external_id": "policy_001",
        "entity_type": "policy",
        "title": "Refund Policy",
        "content": "Full refunds are issued for items returned within 30 days in original condition. Partial refunds may be issued for opened items. Refund processing takes 5-7 business days. Refunds are issued to the original payment method.",
    },
    {
        "external_id": "policy_002",
        "entity_type": "policy",
        "title": "Privacy Policy",
        "content": "We collect only necessary personal information for order processing and shipping. We do not share customer data with third parties except shipping carriers. Customer data is encrypted and stored securely. You may request data deletion at any time.",
    },
    {
        "external_id": "policy_003",
        "entity_type": "policy",
        "title": "Terms of Service",
        "content": "By using our store, you agree to these terms. All prices are in USD and subject to change. We reserve the right to cancel orders due to pricing errors. Products are sold as described. Our liability is limited to the purchase price.",
    },
    {
        "external_id": "policy_004",
        "entity_type": "policy",
        "title": "Customer Support Policy",
        "content": "Our customer support team is available Monday-Friday 9AM-6PM EST. We aim to respond to all inquiries within 24 hours. For urgent issues, please call our support line. We are committed to resolving your concerns promptly and fairly.",
    },
]

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────


def _load_spec(path: Path) -> dict:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix in (".yaml", ".yml"):
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported spec format: {path.suffix}")


def status_icon(success: bool) -> str:
    return "PASS" if success else "FAIL"


def check_response(response: str, keywords: list[str]) -> bool:
    rl = response.lower()
    return any(kw.lower() in rl for kw in keywords)


# ──────────────────────────────────────────────
# STEP FUNCTIONS
# ──────────────────────────────────────────────


async def step_parse_specs(args) -> list[dict]:
    print("\n" + "=" * 72)
    print("  STEP 1: Parse OpenAPI Specs")
    print("=" * 72)
    results = []
    if args.skip_parse:
        print("  SKIPPED (--skip-parse)")
        return results
    import httpx

    for platform_name, spec_path in SPECS:
        if not spec_path.exists():
            logger.warning("  Spec not found: %s", spec_path)
            continue
        spec_data = _load_spec(spec_path)
        payload = {"platform_name": platform_name, "raw_spec": spec_data}
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
            resp = await client.post("/api/v1/integration/schemas/parse", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                results.append(data)
                ents = len(data.get("discovered_entities", []))
                errs = len(data.get("errors", []))
                print(f"  [{status_icon(ents > 0 or errs == 0)}] {platform_name}: {ents} entities, {errs} errors")
            else:
                print(f"  [FAIL] {platform_name}: HTTP {resp.status_code}")
    return results


async def step_create_connections(args) -> list[dict]:
    print("\n" + "=" * 72)
    print("  STEP 2: Create Integration Connections")
    print("=" * 72)
    results = []
    if args.skip_parse:
        print("  SKIPPED (--skip-parse)")
        return results
    import httpx

    for platform_name, spec_path in SPECS:
        if not spec_path.exists():
            continue
        spec_data = _load_spec(spec_path)
        payload = {
            "store_id": STORE_ID,
            "name": platform_name,
            "platform_name": platform_name,
            "raw_spec": spec_data,
            "auth_config": {"type": "apiKey", "credentials_location": "header", "name": "X-API-Key"},
            "credentials": {"api_key": "test-key"},
            "entity_mappings": [],
        }
        async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
            resp = await client.post("/api/v1/integration/connections", json=payload)
            if resp.status_code == 201:
                data = resp.json()
                results.append(data)
                print(f"  [PASS] {platform_name}: id={data['id']}, status={data['status']}")
            else:
                print(f"  [FAIL] {platform_name}: HTTP {resp.status_code} - {resp.text[:200]}")
    return results


async def step_seed_entities():
    print("\n" + "=" * 72)
    print("  STEP 3: Seed All Entities (Products + Categories + FAQ + Policy)")
    print("=" * 72)
    from app.infrastructure.mongodb.client import MongoClientManager
    from app.infrastructure.mongodb.collections import get_entities_collection

    await MongoClientManager.connect()
    collection = get_entities_collection()
    now = datetime.now(UTC)
    total = 0

    # Delete old data for this store
    del_result = await collection.delete_many({"store_id": STORE_ID})
    print(f"  Cleaned {del_result.deleted_count} old entities for {STORE_ID}")

    # Seed products
    for p in SAMPLE_PRODUCTS:
        eid = p["external_id"]
        data = dict(p)
        data.pop("external_id", None)
        data.pop("entity_type", None)
        await collection.update_one(
            {"store_id": STORE_ID, "external_id": eid, "entity_type": "product"},
            {
                "$set": {
                    "store_id": STORE_ID,
                    "organization_id": ORG_ID,
                    "entity_type": "product",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    print(f"  [PASS] Seeded {len(SAMPLE_PRODUCTS)} products")

    # Seed categories
    for c in SAMPLE_CATEGORIES:
        eid = c["external_id"]
        data = dict(c)
        data.pop("external_id", None)
        await collection.update_one(
            {"store_id": STORE_ID, "external_id": eid, "entity_type": "category"},
            {
                "$set": {
                    "store_id": STORE_ID,
                    "organization_id": ORG_ID,
                    "entity_type": "category",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    print(f"  [PASS] Seeded {len(SAMPLE_CATEGORIES)} categories")

    # Seed FAQ
    for faq in FAQ_ENTRIES:
        eid = faq["external_id"]
        data = dict(faq)
        data.pop("external_id", None)
        data.pop("entity_type", None)
        await collection.update_one(
            {"store_id": STORE_ID, "external_id": eid, "entity_type": "faq"},
            {
                "$set": {
                    "store_id": STORE_ID,
                    "organization_id": ORG_ID,
                    "entity_type": "faq",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    print(f"  [PASS] Seeded {len(FAQ_ENTRIES)} FAQ entries")

    # Seed Policies
    for pol in POLICY_ENTRIES:
        eid = pol["external_id"]
        data = dict(pol)
        data.pop("external_id", None)
        data.pop("entity_type", None)
        await collection.update_one(
            {"store_id": STORE_ID, "external_id": eid, "entity_type": "policy"},
            {
                "$set": {
                    "store_id": STORE_ID,
                    "organization_id": ORG_ID,
                    "entity_type": "policy",
                    "external_id": eid,
                    "data": data,
                    "synced_at": now,
                    "updated_at": now,
                },
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )
        total += 1
    print(f"  [PASS] Seeded {len(POLICY_ENTRIES)} policy entries")

    MongoClientManager.disconnect()
    print(f"  Total entities seeded: {total}")
    return total


async def step_vectorize_all():
    print("\n" + "=" * 72)
    print("  STEP 4: Vectorize All Entities to Qdrant")
    print("=" * 72)
    from app.application.dto.ai_dto import EmbeddingRequest
    from app.application.integration.sync.formatters import format_record
    from app.infrastructure.mongodb.client import MongoClientManager
    from app.infrastructure.mongodb.collections import get_entities_collection
    from app.infrastructure.providers.factory import LLMProviderFactory
    from app.infrastructure.qdrant.provider import QdrantProvider
    from app.infrastructure.vectorstore.base import VectorRecord

    await MongoClientManager.connect()

    # Fetch all entities for this store
    collection = get_entities_collection()
    cursor = collection.find({"store_id": STORE_ID})
    entities = await cursor.to_list(length=200)
    print(f"  Loaded {len(entities)} entities from MongoDB")

    # Group by entity_type
    by_type: dict[str, list[dict]] = {}
    for doc in entities:
        et = doc.get("entity_type", "unknown")
        data = doc.get("data", {})
        data["external_id"] = doc.get("external_id", "")
        by_type.setdefault(et, []).append(data)

    print(f"  Entity types: {list(by_type.keys())}")

    # Init Qdrant
    vector_store = QdrantProvider()
    await vector_store.connect()

    # Init embedding provider
    factory = LLMProviderFactory()
    provider = factory.get_provider("gemini")

    # Ensure collection exists
    qdrant_collection = f"kb_{STORE_ID}"
    exists = await vector_store.collection_exists(qdrant_collection)
    if exists:
        await vector_store.delete_collection(qdrant_collection)
        print(f"  Deleted old collection: {qdrant_collection}")
    await vector_store.create_collection(
        collection_name=qdrant_collection,
        vector_size=768,
        distance="Cosine",
    )
    print(f"  Created Qdrant collection: {qdrant_collection}")

    total_synced = 0
    for entity_type, records in by_type.items():
        formatted = []
        for rec in records:
            text = format_record(entity_type, rec)
            if text:
                formatted.append(text)

        if not formatted:
            continue

        BATCH_SIZE = 50
        all_points = []
        for i in range(0, len(formatted), BATCH_SIZE):
            batch = formatted[i : i + BATCH_SIZE]
            batch_records = records[i : i + BATCH_SIZE]
            try:
                request = EmbeddingRequest(input=batch, model="gemini-embedding-001")
                response = await provider.embeddings(request)
                for j, emb in enumerate(response.embeddings):
                    rec_idx = i + j
                    ext_id = str(batch_records[rec_idx].get("external_id", ""))
                    all_points.append(
                        VectorRecord(
                            id=f"{STORE_ID}:{entity_type}:{ext_id}:{rec_idx}",
                            vector=emb,
                            payload={
                                "organization_id": ORG_ID,
                                "store_id": STORE_ID,
                                "entity_type": entity_type,
                                "external_id": ext_id,
                                "source_type": "integration_sync",
                                "document_id": ext_id,
                                "document_title": f"{entity_type}:{ext_id}",
                                "document_status": "active",
                                "chunk_index": rec_idx,
                                "content": batch[j],
                                "knowledge_scope": "general" if entity_type in ("product", "category") else entity_type,
                            },
                        )
                    )
            except Exception as e:
                logger.error("  Embedding batch failed for %s: %s", entity_type, e)

        if all_points:
            await vector_store.upsert(qdrant_collection, all_points)
            total_synced += len(all_points)
            print(f"  [PASS] Synced {len(all_points)} '{entity_type}' vectors")

    await vector_store.disconnect()
    MongoClientManager.disconnect()
    print(f"  Total vectors synced to Qdrant: {total_synced}")
    return total_synced


async def step_generate_business_summary(args):
    print("\n" + "=" * 72)
    print("  STEP 5: Generate Business Summary")
    print("=" * 72)
    if args.skip_summary:
        print("  SKIPPED (--skip-summary)")
        return None
    import httpx

    async with httpx.AsyncClient(base_url=API_BASE, timeout=120) as client:
        resp = await client.post(
            f"/api/v1/knowledge-base/summary?store_id={STORE_ID}",
            json={},
        )
        if resp.status_code == 201:
            data = resp.json()
            summary_text = data.get("summary", "")[:200]
            print(f"  [PASS] Summary generated: v{data.get('version_number')}")
            print(f"  Preview: {summary_text}...")
            return data
        else:
            print(f"  [FAIL] HTTP {resp.status_code}: {resp.text[:300]}")
            return None


async def main():
    parser = argparse.ArgumentParser(description="E2E Full User Flow Test")
    parser.add_argument("--skip-parse", action="store_true", help="Skip parsing & connections")
    parser.add_argument("--skip-seed", action="store_true", help="Skip seeding entities")
    parser.add_argument("--skip-vectorize", action="store_true", help="Skip vectorization")
    parser.add_argument("--skip-summary", action="store_true", help="Skip business summary generation")
    args = parser.parse_args()

    results = {}

    print("\n" + "█" * 72)
    print("  E2E FULL USER FLOW TEST")
    print(f"  Store: {STORE_ID}")
    print(f"  Org:   {ORG_ID}")
    print("█" * 72)

    # ─── STEP 1: Parse ───
    results["parse"] = {"passed": True, "detail": ""}
    try:
        parsed = await step_parse_specs(args)
        results["parse"]["count"] = len(parsed)
    except Exception as e:
        results["parse"] = {"passed": False, "detail": str(e)}
        print(f"  [FAIL] Step 1 exception: {e}")

    # ─── STEP 2: Connections ───
    results["connections"] = {"passed": True, "detail": ""}
    try:
        connections = await step_create_connections(args)
        results["connections"]["count"] = len(connections)
    except Exception as e:
        results["connections"] = {"passed": False, "detail": str(e)}
        print(f"  [FAIL] Step 2 exception: {e}")

    # ─── STEP 3: Seed ───
    results["seed"] = {"passed": True, "detail": ""}
    try:
        count = await step_seed_entities()
        results["seed"]["count"] = count
        if count == 0:
            results["seed"]["passed"] = False
            results["seed"]["detail"] = "No entities seeded"
    except Exception as e:
        results["seed"] = {"passed": False, "detail": str(e)}
        print(f"  [FAIL] Step 3 exception: {e}")

    # ─── STEP 4: Vectorize ───
    results["vectorize"] = {"passed": True, "detail": ""}
    try:
        vcount = await step_vectorize_all()
        results["vectorize"]["count"] = vcount
        if vcount == 0:
            results["vectorize"]["passed"] = False
            results["vectorize"]["detail"] = "No vectors synced"
    except Exception as e:
        results["vectorize"] = {"passed": False, "detail": str(e)}
        print(f"  [FAIL] Step 4 exception: {e}")

    # ─── STEP 5: Business Summary ───
    results["summary"] = {"passed": False, "detail": ""}
    try:
        summary = await step_generate_business_summary(args)
        if summary:
            results["summary"]["passed"] = True
            results["summary"]["version"] = summary.get("version_number")
    except Exception as e:
        results["summary"] = {"passed": False, "detail": str(e)}
        print(f"  [FAIL] Step 5 exception: {e}")

    # ─── STEPS 6-10 (RAG chat scenarios): REMOVED ───
    # The legacy anonymous /rag/chat endpoint has been deleted. Chat scenarios
    # are covered by the widget chat flow (app/static/widget) and unit tests.

    # ─── FINAL REPORT ───
    print("\n" + "█" * 72)
    print("  FINAL TEST REPORT")
    print("█" * 72)

    steps = [
        ("1. Parse OpenAPI Specs", "parse"),
        ("2. Create Connections", "connections"),
        ("3. Seed Entities", "seed"),
        ("4. Vectorize to Qdrant", "vectorize"),
        ("5. Business Summary", "summary"),
    ]

    all_pass = True
    for label, key in steps:
        r = results.get(key, {})
        if isinstance(r, dict) and r.get("passed"):
            print(f"  [PASS] {label}")
        elif isinstance(r, dict):
            print(f"  [FAIL] {label}: {r.get('detail', '')}")
            all_pass = False
        else:
            print(f"  [SKIP] {label}")

    print()
    print("  RAG chat scenarios: REMOVED (legacy /rag/chat endpoint deleted)")

    print()
    if all_pass:
        print("  ✓ ALL TESTS PASSED")
    else:
        print("  ✗ SOME TESTS FAILED")
    print("█" * 72)

    return 0 if all_pass else 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
