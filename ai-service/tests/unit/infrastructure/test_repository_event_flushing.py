import pytest
from unittest.mock import AsyncMock, MagicMock
from bson import ObjectId

from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.shared.kernel.domain_event import DomainEvent
from app.shared.kernel.aggregate_root import AggregateRoot


class TestAggregateEvent(DomainEvent):
    event_name: str


class TestAggregateRoot(AggregateRoot[str]):
    name: str


class TestDocument(BaseMongoDocument):
    name: str

    def to_entity(self) -> TestAggregateRoot:
        return TestAggregateRoot(id=self.id, name=self.name)

    @classmethod
    def from_entity(cls, entity: TestAggregateRoot) -> "TestDocument":
        return cls(_id=entity.id, name=entity.name)


@pytest.mark.asyncio
class TestRepositoryEventFlushing:
    async def test_create_flushes_domain_events(self):
        event_bus = AsyncMock()
        collection = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=TestDocument,
            event_bus=event_bus,
        )

        entity = TestAggregateRoot(id=str(ObjectId()), name="test")
        entity.add_domain_event(TestAggregateEvent(event_name="created"))

        await repo.create(entity)

        event_bus.publish.assert_called_once()
        assert entity.get_domain_events() == []

    async def test_create_no_event_bus_skips_flush(self):
        collection = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=TestDocument,
        )

        entity = TestAggregateRoot(id=str(ObjectId()), name="test")
        entity.add_domain_event(TestAggregateEvent(event_name="created"))

        await repo.create(entity)

        assert len(entity.get_domain_events()) == 1

    async def test_update_flushes_domain_events(self):
        event_bus = AsyncMock()
        collection = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=TestDocument,
            event_bus=event_bus,
        )

        entity = TestAggregateRoot(id=str(ObjectId()), name="test")
        entity.add_domain_event(TestAggregateEvent(event_name="updated"))

        await repo.update(entity)

        event_bus.publish.assert_called_once()
        assert entity.get_domain_events() == []

    async def test_bulk_insert_flushes_domain_events(self):
        event_bus = AsyncMock()
        collection = AsyncMock()
        collection.insert_many = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=TestDocument,
            event_bus=event_bus,
        )

        entity1 = TestAggregateRoot(id=str(ObjectId()), name="e1")
        entity1.add_domain_event(TestAggregateEvent(event_name="bulk1"))
        entity2 = TestAggregateRoot(id=str(ObjectId()), name="e2")
        entity2.add_domain_event(TestAggregateEvent(event_name="bulk2"))

        await repo.bulk_insert([entity1, entity2])

        assert event_bus.publish.call_count == 2
        assert entity1.get_domain_events() == []
        assert entity2.get_domain_events() == []

    async def test_bulk_update_flushes_domain_events(self):
        event_bus = AsyncMock()
        collection = AsyncMock()
        collection.bulk_write = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=TestDocument,
            event_bus=event_bus,
        )

        entity1 = TestAggregateRoot(id=str(ObjectId()), name="e1")
        entity1.add_domain_event(TestAggregateEvent(event_name="upd1"))
        entity2 = TestAggregateRoot(id=str(ObjectId()), name="e2")
        entity2.add_domain_event(TestAggregateEvent(event_name="upd2"))

        await repo.bulk_update([entity1, entity2])

        assert event_bus.publish.call_count == 2
        assert entity1.get_domain_events() == []
        assert entity2.get_domain_events() == []

    async def test_non_aggregate_entity_skips_flush(self):
        class PlainEntity:
            def __init__(self, id):
                self.id = id

        class PlainDoc(BaseMongoDocument):
            name: str

            def to_entity(self):
                return PlainEntity(id=self.id)

            @classmethod
            def from_entity(cls, entity):
                return cls(_id=entity.id, name="plain")

        event_bus = AsyncMock()
        collection = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=PlainDoc,
            event_bus=event_bus,
        )

        entity = PlainEntity(id=str(ObjectId()))

        # This should not fail even though entity is not an AggregateRoot
        await repo.create(entity)

        event_bus.publish.assert_not_called()

    async def test_create_event_bus_failure_raises(self):
        event_bus = AsyncMock()
        event_bus.publish.side_effect = RuntimeError("bus down")
        collection = AsyncMock()
        repo = BaseMongoRepository(
            collection=collection,
            doc_class=TestDocument,
            event_bus=event_bus,
        )

        entity = TestAggregateRoot(id=str(ObjectId()), name="test")
        entity.add_domain_event(TestAggregateEvent(event_name="fail"))

        with pytest.raises(RuntimeError, match="bus down"):
            await repo.create(entity)
