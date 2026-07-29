import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from pymongo.errors import WriteError, DuplicateKeyError, PyMongoError

from app.core.exceptions import (
    DatabaseValidationException,
    ConcurrencyException,
    InfrastructureException
)
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository
from app.infrastructure.mongodb.documents.base_document import BaseMongoDocument
from app.shared.kernel.entity import Entity
from app.infrastructure.mongodb.uow import MongoUnitOfWork

class TestEntity(Entity[str]):
    name: str

class TestDocument(BaseMongoDocument):
    name: str

    def to_entity(self) -> TestEntity:
        return TestEntity(id=self.id, name=self.name)

    @classmethod
    def from_entity(cls, entity: TestEntity) -> "TestDocument":
        return cls(_id=entity.id, name=entity.name)

@pytest.fixture
def mock_collection():
    return AsyncMock()

@pytest.fixture
def repository(mock_collection):
    return BaseMongoRepository(collection=mock_collection, doc_class=TestDocument)

@pytest.mark.asyncio
async def test_create_success(repository, mock_collection):
    entity = TestEntity(id=str(ObjectId()), name="Test Entity")
    
    mock_collection.insert_one = AsyncMock(return_value=MagicMock())
    
    result = await repository.create(entity)
    
    assert result == entity
    mock_collection.insert_one.assert_called_once()
    inserted_arg = mock_collection.insert_one.call_args[0][0]
    assert inserted_arg["name"] == "Test Entity"
    assert inserted_arg["_id"] == ObjectId(entity.id)

@pytest.mark.asyncio
async def test_create_validation_failure(repository, mock_collection):
    entity = TestEntity(id=str(ObjectId()), name="Test Entity")
    
    write_error = WriteError("Document failed schema validation", code=121, details={})
    mock_collection.insert_one = AsyncMock(side_effect=write_error)
    
    with pytest.raises(DatabaseValidationException) as excinfo:
        await repository.create(entity)
        
    assert "validation" in str(excinfo.value)
    mock_collection.insert_one.assert_called_once()

@pytest.mark.asyncio
async def test_update_concurrency_failure(repository, mock_collection):
    entity = TestEntity(id=str(ObjectId()), name="Test Entity")
    
    dup_error = DuplicateKeyError("Duplicate key error")
    mock_collection.replace_one = AsyncMock(side_effect=dup_error)
    
    with pytest.raises(ConcurrencyException) as excinfo:
        await repository.update(entity)
        
    assert "conflict" in str(excinfo.value)
    mock_collection.replace_one.assert_called_once()

@pytest.mark.asyncio
async def test_find_by_id_invalid_objectid(repository, mock_collection):
    result = await repository.find_by_id("invalid-id")
    
    assert result is None
    mock_collection.find_one.assert_not_called()

@pytest.mark.asyncio
async def test_find_by_id_success(repository, mock_collection):
    entity_id = str(ObjectId())
    mock_collection.find_one = AsyncMock(return_value={
        "_id": ObjectId(entity_id),
        "name": "Found Entity",
        "created_at": "2026-07-14T12:00:00Z",
        "updated_at": "2026-07-14T12:00:00Z"
    })
    
    result = await repository.find_by_id(entity_id)
    
    assert result is not None
    assert result.id == entity_id
    assert result.name == "Found Entity"
    mock_collection.find_one.assert_called_once_with({"_id": ObjectId(entity_id)}, session=None)

@pytest.mark.asyncio
@patch("app.infrastructure.mongodb.uow.MongoClientManager")
async def test_uow_commit_on_success(mock_client_manager):
    mock_db = MagicMock()
    mock_client = AsyncMock()
    mock_session = AsyncMock()
    
    mock_db.client = mock_client
    mock_client_manager.get_database.return_value = mock_db
    mock_client.start_session = AsyncMock(return_value=mock_session)
    
    async with MongoUnitOfWork() as uow:
        pass
        
    mock_client.start_session.assert_called_once()
    mock_session.start_transaction.assert_called_once()
    mock_session.commit_transaction.assert_called_once()
    mock_session.abort_transaction.assert_not_called()
    mock_session.end_session.assert_called_once()

@pytest.mark.asyncio
@patch("app.infrastructure.mongodb.uow.MongoClientManager")
async def test_uow_rollback_on_failure(mock_client_manager):
    mock_db = MagicMock()
    mock_client = AsyncMock()
    mock_session = AsyncMock()
    
    mock_db.client = mock_client
    mock_client_manager.get_database.return_value = mock_db
    mock_client.start_session = AsyncMock(return_value=mock_session)
    
    try:
        async with MongoUnitOfWork() as uow:
            raise ValueError("Something went wrong")
    except ValueError:
        pass
        
    mock_client.start_session.assert_called_once()
    mock_session.start_transaction.assert_called_once()
    mock_session.commit_transaction.assert_not_called()
    mock_session.abort_transaction.assert_called_once()
    mock_session.end_session.assert_called_once()
