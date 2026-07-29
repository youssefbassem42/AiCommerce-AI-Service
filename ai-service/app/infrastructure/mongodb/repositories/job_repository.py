from datetime import UTC, datetime

from bson import ObjectId

from app.domain.job.entities.knowledge_job import KnowledgeJob
from app.domain.job.repositories.job_repository import JobRepository as IJobRepository
from app.domain.job.value_objects import JobStatus, JobType
from app.infrastructure.mongodb.collections import get_knowledge_jobs_collection
from app.infrastructure.mongodb.documents.job_document import KnowledgeJobDocument
from app.infrastructure.mongodb.repositories.base_repository import BaseMongoRepository


class JobRepository(
    BaseMongoRepository[KnowledgeJobDocument, KnowledgeJob],
    IJobRepository,
):
    def __init__(self):
        super().__init__(get_knowledge_jobs_collection(), KnowledgeJobDocument)

    async def create(self, entity: KnowledgeJob) -> KnowledgeJob:
        doc = KnowledgeJobDocument.from_entity(entity)
        collection = get_knowledge_jobs_collection()
        await collection.insert_one(doc.to_mongo_dict())
        return entity

    async def find_by_status(
        self,
        status: JobStatus,
        limit: int = 50,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        docs = await self.find_many(
            filters={"status": status.value},
            limit=limit,
            skip=skip,
        )
        return docs

    async def find_by_type_and_status(
        self,
        job_type: JobType,
        status: JobStatus,
        limit: int = 50,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        docs = await self.find_many(
            filters={"job_type": job_type.value, "status": status.value},
            limit=limit,
            skip=skip,
        )
        return docs

    async def find_dead_letters(
        self,
        limit: int = 50,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        docs = await self.find_many(
            filters={"status": JobStatus.DEAD_LETTER.value},
            limit=limit,
            skip=skip,
        )
        return docs

    async def update_progress(
        self,
        job_id: str,
        progress: float,
        status: JobStatus | None = None,
    ) -> None:
        collection = get_knowledge_jobs_collection()
        update: dict = {
            "$set": {
                "progress": progress,
                "updated_at": datetime.now(UTC),
            }
        }
        if status:
            update["$set"]["status"] = status.value
            if status == JobStatus.RUNNING:
                update["$set"]["started_at"] = datetime.now(UTC)
        await collection.update_one({"_id": ObjectId(job_id)}, update)

    async def mark_completed(
        self,
        job_id: str,
        result: dict | None = None,
    ) -> None:
        collection = get_knowledge_jobs_collection()
        update: dict = {
            "$set": {
                "status": JobStatus.COMPLETED.value,
                "progress": 1.0,
                "result": result or {},
                "completed_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        }
        await collection.update_one({"_id": ObjectId(job_id)}, update)

    async def mark_failed(
        self,
        job_id: str,
        error_message: str,
        status: JobStatus = JobStatus.FAILED,
    ) -> None:
        collection = get_knowledge_jobs_collection()
        update: dict = {
            "$set": {
                "status": status.value,
                "error_message": error_message,
                "completed_at": datetime.now(UTC),
                "updated_at": datetime.now(UTC),
            }
        }
        await collection.update_one({"_id": ObjectId(job_id)}, update)

    async def update(self, entity: KnowledgeJob) -> KnowledgeJob:
        collection = get_knowledge_jobs_collection()
        doc = KnowledgeJobDocument.from_entity(entity)
        await collection.replace_one({"_id": ObjectId(entity.id)}, doc.to_mongo_dict())
        return entity

    async def delete(self, id: str) -> bool:
        collection = get_knowledge_jobs_collection()
        result = await collection.delete_one({"_id": ObjectId(id)})
        return result.deleted_count > 0

    async def find_by_id(self, id: str) -> KnowledgeJob | None:
        collection = get_knowledge_jobs_collection()
        doc_data = await collection.find_one({"_id": ObjectId(id)})
        if not doc_data:
            return None
        doc = KnowledgeJobDocument.from_mongo_dict(doc_data)
        return doc.to_entity()

    async def find_many(
        self,
        filters: dict,
        limit: int = 100,
        skip: int = 0,
    ) -> list[KnowledgeJob]:
        collection = get_knowledge_jobs_collection()
        cursor = collection.find(filters).sort("created_at", -1).skip(skip).limit(limit)
        results = []
        async for doc_data in cursor:
            doc = KnowledgeJobDocument.from_mongo_dict(doc_data)
            results.append(doc.to_entity())
        return results

    async def paginate(
        self,
        filters: dict,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[KnowledgeJob], int]:
        collection = get_knowledge_jobs_collection()
        skip = (page - 1) * page_size
        total = await collection.count_documents(filters)
        cursor = collection.find(filters).sort("created_at", -1).skip(skip).limit(page_size)
        results = []
        async for doc_data in cursor:
            doc = KnowledgeJobDocument.from_mongo_dict(doc_data)
            results.append(doc.to_entity())
        return results, total

    async def exists(self, id: str) -> bool:
        collection = get_knowledge_jobs_collection()
        count = await collection.count_documents({"_id": ObjectId(id)}, limit=1)
        return count > 0

    async def bulk_insert(self, entities: list[KnowledgeJob]) -> int:
        if not entities:
            return 0
        collection = get_knowledge_jobs_collection()
        docs = [KnowledgeJobDocument.from_entity(e).to_mongo_dict() for e in entities]
        result = await collection.insert_many(docs)
        return len(result.inserted_ids)

    async def bulk_update(self, entities: list[KnowledgeJob]) -> int:
        if not entities:
            return 0
        count = 0
        for entity in entities:
            await self.update(entity)
            count += 1
        return count
