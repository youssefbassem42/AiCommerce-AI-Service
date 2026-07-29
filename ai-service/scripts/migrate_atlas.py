import asyncio
import logging

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

from app.core.config import settings
from app.infrastructure.mongodb.validators import VALIDATORS_MAP
from app.infrastructure.mongodb.indexes import setup_database_indexes

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("migrate_atlas")


COMMERCE_COLLECTIONS = ["products", "categories", "orders", "inventory"]


async def run_migration():
    logger.info("Connecting to MongoDB Atlas...")
    client = AsyncIOMotorClient(
        settings.MONGO_SETTINGS.MONGO_URI,
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
        retryWrites=True,
        retryReads=True,
    )

    try:
        await client.admin.command("ping")
        logger.info("Connection to Atlas verified.")
    except Exception as e:
        logger.error(f"Failed to connect to Atlas: {e}")
        return

    db = client[settings.MONGO_SETTINGS.MONGO_DB]
    existing = await db.list_collection_names()
    logger.info(f"Existing collections in '{settings.MONGO_SETTINGS.MONGO_DB}': {existing}")

    # Step 1: Create / update schema validators (also creates collections)
    for coll_name, schema in VALIDATORS_MAP.items():
        try:
            if coll_name not in existing:
                await db.create_collection(coll_name, validator=schema)
                logger.info(f"  Created collection '{coll_name}' with validator.")
            else:
                await db.command("collMod", coll_name, validator=schema)
                logger.info(f"  Updated validator for '{coll_name}'.")
        except OperationFailure as e:
            logger.warning(f"  Could not modify '{coll_name}': {e}")

    # Step 2: Ensure commerce collections exist (no validators)
    existing = await db.list_collection_names()
    for coll in COMMERCE_COLLECTIONS:
        if coll not in existing:
            try:
                await db.create_collection(coll)
                logger.info(f"  Created commerce collection '{coll}'.")
            except OperationFailure as e:
                logger.warning(f"  Could not create '{coll}': {e}")

    # Step 3: Create all indexes
    logger.info("Creating indexes...")
    try:
        await setup_database_indexes(db)
        logger.info("All indexes created successfully.")
    except Exception as e:
        logger.error(f"Index creation failed: {e}")

    # Step 4: Verify final state
    all_collections = await db.list_collection_names()
    expected = set(VALIDATORS_MAP.keys()) | set(COMMERCE_COLLECTIONS)
    missing = expected - set(all_collections)
    if missing:
        logger.warning(f"Missing collections after migration: {missing}")
    else:
        logger.info(f"All {len(expected)} collections are present.")

    for coll in sorted(all_collections):
        idx_cursor = db[coll].list_indexes()
        indexes = await idx_cursor.to_list(length=20)
        idx_names = [ix["name"] for ix in indexes]
        logger.info(f"  {coll}: indexes={idx_names}")

    client.close()
    logger.info("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run_migration())
