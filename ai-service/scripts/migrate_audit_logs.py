#!/usr/bin/env python3
"""
Migration: rename audit_logs.tenant_id -> store_id.

Copies tenant_id values into the new store_id field and drops the old field.
Idempotent: documents already carrying store_id (or without tenant_id) are skipped.
"""

import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_audit_logs")

COLLECTION = "audit_logs"


async def run_migration():
    logger.info("Connecting to MongoDB...")
    client = AsyncIOMotorClient(
        settings.MONGO_SETTINGS.MONGO_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
    )

    try:
        await client.admin.command("ping")
        logger.info("Connection verified.")
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return

    db = client[settings.MONGO_SETTINGS.MONGO_DB]
    coll = db[COLLECTION]

    result = await coll.update_many(
        {"tenant_id": {"$exists": True}},
        [
            {"$set": {"store_id": "$tenant_id"}},
            {"$unset": "tenant_id"},
        ],
    )
    logger.info(f"Updated {result.modified_count} audit log documents (tenant_id -> store_id).")

    remaining = await coll.count_documents({"tenant_id": {"$exists": True}})
    logger.info(f"Documents still carrying tenant_id: {remaining}")

    client.close()
    logger.info("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run_migration())
