import logging
from typing import Any, TypeVar

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorCollection
from pymongo import ReplaceOne
from pymongo.errors import DuplicateKeyError, PyMongoError, WriteError

from app.core.exceptions import ConcurrencyException, DatabaseValidationException, InfrastructureException
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.shared.events.event_bus import EventBus
from app.shared.kernel.aggregate_root import AggregateRoot
from app.shared.kernel.entity import Entity
from app.shared.kernel.repository import AsyncRepository

logger = logging.getLogger(__name__)

DocType = TypeVar("DocType", bound=BaseMongoDocument)
EntityType = TypeVar("EntityType", bound=Entity)


class BaseMongoRepository[DocType: BaseMongoDocument, EntityType: Entity](AsyncRepository[EntityType, str]):
    """
    Generic MongoDB Repository implementation implementing standard CRUD,
    pagination, bulk operations, logging, exception mapping, transaction sessions,
    and automatic domain event flushing.
    """

    def __init__(
        self,
        collection: AsyncIOMotorCollection,
        doc_class: type[DocType],
        event_bus: EventBus | None = None,
    ):
        self.collection = collection
        self.doc_class = doc_class
        self._event_bus = event_bus

    async def _flush_domain_events(self, entity: EntityType) -> None:
        if not self._event_bus:
            return
        if not isinstance(entity, AggregateRoot):
            return
        events = entity.get_domain_events()
        if not events:
            return
        for event in events:
            try:
                await self._event_bus.publish(event)
            except Exception as e:
                logger.error(
                    "Failed to publish event %s from %s: %s",
                    type(event).__name__,
                    type(entity).__name__,
                    str(e),
                )
                raise
        entity.clear_domain_events()

    def _handle_db_error(self, e: Exception) -> None:
        """Handle and map PyMongo exceptions to clean architecture domain/infra exceptions."""
        logger.error(f"Database operation failed in repository {self.__class__.__name__}: {str(e)}", exc_info=True)
        if isinstance(e, DuplicateKeyError):
            raise ConcurrencyException(f"Write conflict or unique key constraint violation: {str(e)}")
        if isinstance(e, WriteError):
            if e.code == 121:
                raise DatabaseValidationException(f"Document failed collection schema validation: {str(e.details)}")
            raise InfrastructureException(f"Database write operation failed: {str(e)}")
        if isinstance(e, PyMongoError):
            raise InfrastructureException(f"Database driver infrastructure failure: {str(e)}")
        raise e

    async def create(self, entity: EntityType, session: Any = None) -> EntityType:
        try:
            doc = self.doc_class.from_entity(entity)
            data = doc.to_mongo_dict()
            result = await self.collection.insert_one(data, session=session)
            entity.id = str(result.inserted_id)
            await self._flush_domain_events(entity)
            return entity
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def update(self, entity: EntityType, session: Any = None) -> EntityType:
        if not ObjectId.is_valid(entity.id):
            raise ValueError(f"Entity contains an invalid ObjectId format: {entity.id}")
        try:
            doc = self.doc_class.from_entity(entity)
            data = doc.to_mongo_dict()
            await self.collection.replace_one({"_id": ObjectId(entity.id)}, data, upsert=True, session=session)
            await self._flush_domain_events(entity)
            return entity
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def delete(self, id: str, session: Any = None) -> bool:
        if not ObjectId.is_valid(id):
            logger.warning(f"Aborting delete: ID is not a valid ObjectId: {id}")
            return False
        try:
            result = await self.collection.delete_one({"_id": ObjectId(id)}, session=session)
            return result.deleted_count > 0
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def find_by_id(self, id: str, session: Any = None) -> EntityType | None:
        if not ObjectId.is_valid(id):
            logger.debug(f"find_by_id returned None: ID is not a valid ObjectId: {id}")
            return None
        try:
            data = await self.collection.find_one({"_id": ObjectId(id)}, session=session)
            if not data:
                return None
            doc = self.doc_class.from_mongo_dict(data)
            return doc.to_entity()
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def find_many(self, filters: dict, limit: int = 100, skip: int = 0, session: Any = None) -> list[EntityType]:
        try:
            cursor = self.collection.find(filters, session=session).skip(skip).limit(limit)
            results = []
            async for data in cursor:
                doc = self.doc_class.from_mongo_dict(data)
                results.append(doc.to_entity())
            return results
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def paginate(
        self, filters: dict, page: int = 1, page_size: int = 20, session: Any = None
    ) -> tuple[list[EntityType], int]:
        try:
            skip = (page - 1) * page_size
            total = await self.collection.count_documents(filters, session=session)
            cursor = self.collection.find(filters, session=session).skip(skip).limit(page_size)
            items = []
            async for data in cursor:
                doc = self.doc_class.from_mongo_dict(data)
                items.append(doc.to_entity())
            return items, total
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def bulk_insert(self, entities: list[EntityType], session: Any = None) -> int:
        if not entities:
            return 0
        try:
            docs = [self.doc_class.from_entity(e).to_mongo_dict() for e in entities]
            result = await self.collection.insert_many(docs, session=session)
            for entity in entities:
                await self._flush_domain_events(entity)
            return len(result.inserted_ids)
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def bulk_update(self, entities: list[EntityType], session: Any = None) -> int:
        if not entities:
            return 0
        try:
            operations = []
            for e in entities:
                if not ObjectId.is_valid(e.id):
                    raise ValueError(f"Entity contains an invalid ObjectId format: {e.id}")
                doc = self.doc_class.from_entity(e)
                data = doc.to_mongo_dict()
                operations.append(ReplaceOne({"_id": ObjectId(e.id)}, data))
            result = await self.collection.bulk_write(operations, session=session)
            for entity in entities:
                await self._flush_domain_events(entity)
            return result.modified_count
        except Exception as e:
            self._handle_db_error(e)
            raise

    async def exists(self, id: str, session: Any = None) -> bool:
        if not ObjectId.is_valid(id):
            return False
        try:
            count = await self.collection.count_documents({"_id": ObjectId(id)}, limit=1, session=session)
            return count > 0
        except Exception as e:
            self._handle_db_error(e)
            raise
