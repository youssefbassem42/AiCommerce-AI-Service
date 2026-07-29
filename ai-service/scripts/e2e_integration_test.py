#!/usr/bin/env python3
"""
End-to-end test of the schema-agnostic integration pipeline.

1. Parse all 3 OpenAPI specs
2. Create connections
3. Seed sample product data into entities collection
4. Vectorize through CommerceKnowledgeBridge
5. Test RAG with price-range query
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e_test")

# --- Constants ---
API_BASE = "http://localhost:8000"
STORE_ID = "store_elec_001"
ORG_ID = "org_elec_001"
COMMERCE_DIR = PROJECT_ROOT.parent / "E-commerce-ProjectApi"

SPECS = [
    ("Merchant Integration API", COMMERCE_DIR / "openapi-1.yaml"),
    ("E-Commerce ASP.NET API", COMMERCE_DIR / "openapi.yaml"),
    ("E-Commerce JSON API", COMMERCE_DIR / "openapi.json"),
]

SAMPLE_PRODUCTS = [
    {
        "external_id": "prod_001",
        "title": "MacBook Pro 16-inch M3 Max",
        "description": "Apple MacBook Pro with M3 Max chip, 36GB RAM, 1TB SSD",
        "price": 3499.99,
        "sku": "MBP-M3-16-36-1TB",
        "category": "Laptops",
        "brand": "Apple",
        "inventory_quantity": 15,
        "specs": {"cpu": "M3 Max 16-core", "ram": "36GB", "storage": "1TB SSD", "display": "16-inch Liquid Retina XDR"},
    },
    {
        "external_id": "prod_002",
        "title": "Dell XPS 15 OLED",
        "description": "Dell XPS 15 with Intel Core i9, 32GB RAM, 1TB SSD, OLED display",
        "price": 2499.99,
        "sku": "DEL-XPS-15-i9-32-1TB",
        "category": "Laptops",
        "brand": "Dell",
        "inventory_quantity": 23,
        "specs": {"cpu": "Intel Core i9-13900H", "ram": "32GB", "storage": "1TB SSD", "display": "15.6-inch OLED"},
    },
    {
        "external_id": "prod_003",
        "title": "Samsung Galaxy S24 Ultra",
        "description": "Samsung Galaxy S24 Ultra 512GB with S Pen, Titanium frame",
        "price": 1399.99,
        "sku": "SAM-S24U-512",
        "category": "Smartphones",
        "brand": "Samsung",
        "inventory_quantity": 42,
        "specs": {"cpu": "Snapdragon 8 Gen 3", "ram": "12GB", "storage": "512GB", "display": "6.8-inch Dynamic AMOLED"},
    },
    {
        "external_id": "prod_004",
        "title": "Sony WH-1000XM5 Headphones",
        "description": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
        "price": 349.99,
        "sku": "SONY-WH1000XM5",
        "category": "Audio",
        "brand": "Sony",
        "inventory_quantity": 78,
        "specs": {"type": "Over-ear", "battery": "30 hours", "noise_cancelling": "Adaptive", "connectivity": "Bluetooth 5.2"},
    },
    {
        "external_id": "prod_005",
        "title": "Logitech MX Mechanical Keyboard",
        "description": "Logitech MX Mechanical Wireless Keyboard with Tactile Switches",
        "price": 149.99,
        "sku": "LOG-MX-MECH",
        "category": "Accessories",
        "brand": "Logitech",
        "inventory_quantity": 120,
        "specs": {"type": "Mechanical", "switches": "Tactile", "layout": "Full-size", "connectivity": "Bluetooth + USB-C"},
    },
    {
        "external_id": "prod_006",
        "title": "Apple AirPods Pro 2nd Gen",
        "description": "Apple AirPods Pro 2nd Generation with USB-C, Adaptive Audio",
        "price": 249.99,
        "sku": "AP-AIRPODS-PRO-2",
        "category": "Audio",
        "brand": "Apple",
        "inventory_quantity": 95,
        "specs": {"type": "In-ear", "chip": "H2", "anc": "Adaptive", "connectivity": "Bluetooth 5.3"},
    },
    {
        "external_id": "prod_007",
        "title": "ASUS ROG Strix RTX 4080",
        "description": "ASUS ROG Strix GeForce RTX 4080 16GB GDDR6X Graphics Card",
        "price": 1199.99,
        "sku": "ASUS-RTX4080-16G",
        "category": "Components",
        "brand": "ASUS",
        "inventory_quantity": 8,
        "specs": {"gpu": "RTX 4080", "vram": "16GB GDDR6X", "interface": "PCIe 4.0", "ports": "HDMI 2.1 + DP 1.4a"},
    },
    {
        "external_id": "prod_008",
        "title": "LG 27-inch 4K Monitor",
        "description": "LG 27UP850N 27-inch 4K UHD IPS Monitor with USB-C",
        "price": 499.99,
        "sku": "LG-27UP850N",
        "category": "Monitors",
        "brand": "LG",
        "inventory_quantity": 34,
        "specs": {"resolution": "3840x2160", "panel": "IPS", "size": "27-inch", "ports": "USB-C 96W PD, HDMI, DP"},
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


async def parse_spec(platform_name: str, spec_path: Path) -> dict:
    import httpx
    spec_data = _load_spec(spec_path)
    payload = {"platform_name": platform_name, "raw_spec": spec_data}
    logger.info("  POST /api/v1/integration/schemas/parse — %s (%s)", platform_name, spec_path.name)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        resp = await client.post("/api/v1/integration/schemas/parse", json=payload)
        resp.raise_for_status()
        data = resp.json()
        entities_count = len(data.get("discovered_entities", []))
        warnings = data.get("warnings", [])
        errors = data.get("errors", [])
        logger.info("  → entities: %d, warnings: %d, errors: %d", entities_count, len(warnings), len(errors))
        for e in data.get("discovered_entities", []):
            logger.info("    • %s (confidence=%.4f) — %s %s", e["entity_type"], e["confidence"], e["endpoint_method"], e["endpoint_path"])
        if errors:
            logger.warning("  Errors: %s", errors[:3])
        return data


async def create_connection(store_id: str, name: str, platform_name: str, spec_path: Path) -> dict:
    import httpx
    spec_data = _load_spec(spec_path)
    payload = {
        "store_id": store_id,
        "name": name,
        "platform_name": platform_name,
        "raw_spec": spec_data,
        "auth_config": {"type": "apiKey", "credentials_location": "header", "name": "X-API-Key"},
        "credentials": {"api_key": "test-key"},
        "entity_mappings": [],
    }
    logger.info("  POST /api/v1/integration/connections — %s", name)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=30) as client:
        resp = await client.post("/api/v1/integration/connections", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("  → connection_id: %s, status: %s", data["id"], data["status"])
        return data


async def seed_entities():
    from motor.motor_asyncio import AsyncIOMotorClient
    from app.infrastructure.mongodb.collections import get_entities_collection
    from app.core.config import settings
    import app.infrastructure.mongodb.client as mongo_client_mod
    from app.infrastructure.mongodb.client import MongoClientManager

    await MongoClientManager.connect()

    collection = get_entities_collection()
    now = datetime.now(UTC)

    # Insert products
    prod_count = 0
    for p in SAMPLE_PRODUCTS:
        await collection.update_one(
            {"store_id": STORE_ID, "external_id": p["external_id"]},
            {"$set": {
                "store_id": STORE_ID,
                "organization_id": ORG_ID,
                "entity_type": "product",
                "external_id": p["external_id"],
                "data": p,
                "synced_at": now,
                "updated_at": now,
            }, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        prod_count += 1
    logger.info("  Seeded %d products", prod_count)

    # Insert categories
    cat_count = 0
    for c in SAMPLE_CATEGORIES:
        await collection.update_one(
            {"store_id": STORE_ID, "external_id": c["external_id"]},
            {"$set": {
                "store_id": STORE_ID,
                "organization_id": ORG_ID,
                "entity_type": "category",
                "external_id": c["external_id"],
                "data": c,
                "synced_at": now,
                "updated_at": now,
            }, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        cat_count += 1
    logger.info("  Seeded %d categories", cat_count)

    MongoClientManager.disconnect()
    return prod_count + cat_count


async def run_knowledge_bridge():
    """Use CommerceKnowledgeBridge to vectorize seeded entities into Qdrant."""
    from app.application.dto.ai_dto import EmbeddingRequest
    from app.application.integration.sync.formatters import format_record
    from app.infrastructure.mongodb.client import MongoClientManager
    from app.infrastructure.mongodb.collections import get_entities_collection
    from app.infrastructure.qdrant.provider import QdrantProvider
    from app.infrastructure.providers.factory import LLMProviderFactory
    from app.infrastructure.vectorstore.base import VectorRecord

    await MongoClientManager.connect()

    # Fetch seeded entities
    collection = get_entities_collection()
    cursor = collection.find({"store_id": STORE_ID})
    entities = await cursor.to_list(length=200)
    logger.info("  Loaded %d entities from entities collection", len(entities))

    # Group by entity_type
    by_type: dict[str, list[dict]] = {}
    for doc in entities:
        et = doc.get("entity_type", "unknown")
        data = doc.get("data", {})
        data["external_id"] = doc.get("external_id", "")
        by_type.setdefault(et, []).append(data)

    # Init Qdrant
    vector_store = QdrantProvider()
    await vector_store.connect()

    # Init LLM provider for embeddings
    factory = LLMProviderFactory()
    provider = factory.get_provider("gemini")

    # Ensure collection exists
    qdrant_collection = f"kb_{STORE_ID}"
    exists = await vector_store.collection_exists(qdrant_collection)
    if not exists:
        await vector_store.create_collection(
            collection_name=qdrant_collection,
            vector_size=768,
            distance="Cosine",
        )
        logger.info("  Created Qdrant collection: %s", qdrant_collection)

    total_synced = 0
    for entity_type, records in by_type.items():
        logger.info("  Processing %d %s records...", len(records), entity_type)
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
            batch = formatted[i:i + BATCH_SIZE]
            batch_records = records[i:i + BATCH_SIZE]
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
                            },
                        )
                    )
            except Exception as e:
                logger.error("  Embedding batch failed: %s", e)

        if all_points:
            await vector_store.upsert(qdrant_collection, all_points)
            total_synced += len(all_points)
            logger.info("  Synced %d vectors for '%s'", len(all_points), entity_type)

    await vector_store.disconnect()
    MongoClientManager.disconnect()
    logger.info("  Total vectors synced: %d", total_synced)
    return total_synced


async def test_rag_query(query: str, store_id: str = STORE_ID, org_id: str = ORG_ID):
    """Test RAG via the /rag/chat endpoint."""
    import httpx
    payload = {
        "message": query,
        "store_id": store_id,
        "organization_id": org_id,
        "top_k": 10,
        "score_threshold": 0.0,
        "use_hybrid": False,
        "use_mmr": False,
        "rerank": False,
    }
    logger.info("  POST /rag/chat — query: '%s'", query)
    async with httpx.AsyncClient(base_url=API_BASE, timeout=60) as client:
        resp = await client.post("/rag/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()
        logger.info("  Response: %s", data.get("response", "")[:500])
        logger.info("  Citations: %s", data.get("citations", []))
        logger.info("  Confidence: %s", data.get("confidence_score"))
        logger.info("  Latency: %s ms", data.get("latency_ms"))
        return data


def _load_spec(path: Path) -> dict:
    if path.suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix in (".yaml", ".yml"):
        import yaml
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    raise ValueError(f"Unsupported spec format: {path.suffix}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-parse", action="store_true", help="Skip parsing OpenAPI specs")
    parser.add_argument("--skip-seed", action="store_true", help="Skip seeding product data")
    parser.add_argument("--skip-vectorize", action="store_true", help="Skip vectorization step")
    args = parser.parse_args()

    os.environ["RAG_LLM_PROVIDER"] = "gemini"

    print("\n" + "=" * 72)
    print("  E2E Integration Pipeline Test")
    print("=" * 72)

    # ---- STEP 1: Parse specs ----
    if not args.skip_parse:
        print("\n--- Parsing OpenAPI specs ---")
        for platform_name, spec_path in SPECS:
            if not spec_path.exists():
                logger.warning("  Spec not found: %s", spec_path)
                continue
            try:
                result = await parse_spec(platform_name, spec_path)
                print(f"  ✓ {platform_name}: {len(result['discovered_entities'])} entities detected")
            except Exception as e:
                logger.error("  Failed to parse %s: %s", platform_name, e)

    # ---- STEP 2: Create connections ----
    if not args.skip_parse:
        print("\n--- Creating integration connections ---")
        for platform_name, spec_path in SPECS:
            if not spec_path.exists():
                continue
            try:
                result = await create_connection(STORE_ID, platform_name, platform_name, spec_path)
                print(f"  ✓ Connection created: {result['id']}")
            except Exception as e:
                logger.error("  Failed to create connection for %s: %s", platform_name, e)

    # ---- STEP 3: Seed entities ----
    if not args.skip_seed:
        print("\n--- Seeding sample product data ---")
        count = await seed_entities()
        print(f"  ✓ Seeded {count} entities")

    # ---- STEP 4: Vectorize ----
    if not args.skip_vectorize:
        print("\n--- Vectorizing entities into Qdrant ---")
        total = await run_knowledge_bridge()
        print(f"  ✓ Synced {total} vectors to Qdrant")

    # ---- STEP 5: Test RAG ----
    print("\n" + "=" * 72)
    print("  Testing RAG with price-range queries")
    print("=" * 72)

    queries = [
        "I need a laptop between $1000 and $2000, what do you recommend?",
        "Find me audio products under $300",
        "What products do you have between $100 and $200?",
        "Show me products over $1000",
        "I'm looking for a budget-friendly keyboard or monitor under $500",
        "What laptops are available and which one has the best value?",
    ]

    for q in queries:
        print(f"\n--- Query: {q} ---")
        try:
            data = await test_rag_query(q)
            response = data.get("response", "")
            citations = data.get("citations", [])

            # Check if the response mentions product names or prices
            has_product_ref = any(
                keyword in response.lower()
                for keyword in ["macbook", "dell", "samsung", "sony", "logitech", "airpods", "asus", "lg"]
            )
            has_price_ref = "$" in response or "dollar" in response.lower() or "price" in response.lower()

            print(f"  Product references: {'✓' if has_product_ref else '✗'}")
            print(f"  Price references: {'✓' if has_price_ref else '✗'}")
            print(f"  Citations: {len(citations)}")
        except Exception as e:
            logger.error("  RAG query failed: %s", e)

    print("\n" + "=" * 72)
    print("  E2E test complete")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
