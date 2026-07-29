import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


# ---------- Ingestion Worker Tests ----------

class TestProcessDocumentTask:
    @patch("app.workers.ingestion.tasks.KnowledgeRepository")
    @patch("app.workers.ingestion.tasks.ExtractorFactory")
    @patch("app.workers.ingestion.tasks.ProcessingPipeline")
    @patch("app.workers.ingestion.tasks.DocumentProcessor")
    @patch("app.workers.ingestion.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.complete_job", new_callable=AsyncMock)
    def test_success(
        self, mock_complete, mock_progress, mock_processor_cls,
        mock_pipeline, mock_extractor, mock_repo_cls,
    ):
        from app.workers.ingestion.tasks import process_document_task

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.status = "processed"
        mock_doc.word_count = 100
        mock_doc.char_count = 500
        mock_doc.estimated_tokens = 125
        mock_doc.language = "en"

        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=mock_doc)
        mock_repo_cls.return_value = mock_repo

        mock_processor = MagicMock()
        mock_processor.process = AsyncMock(return_value=mock_doc)
        mock_processor_cls.return_value = mock_processor

        result = process_document_task.run("doc-1", "/tmp/file.pdf", "application/pdf", "job-1")

        assert result["document_id"] == "doc-1"
        assert result["status"] == "processed"
        assert result["word_count"] == 100

    @patch("app.workers.ingestion.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.KnowledgeRepository")
    @patch("app.workers.ingestion.tasks.fail_job", new_callable=AsyncMock)
    def test_document_not_found(self, mock_fail, mock_repo_cls, mock_progress):
        from app.workers.ingestion.tasks import process_document_task

        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        with pytest.raises(ValueError, match="not found"):
            process_document_task.run("doc-1", "/tmp/file.pdf", job_id="job-1")
    
    @patch("app.workers.ingestion.tasks.KnowledgeRepository")
    @patch("app.workers.ingestion.tasks.DocumentProcessor")
    @patch("app.workers.ingestion.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.complete_job", new_callable=AsyncMock)
    def test_success_without_job_id(self, mock_complete, mock_progress, mock_processor_cls, mock_repo_cls):
        from app.workers.ingestion.tasks import process_document_task

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"
        mock_doc.status = "processed"
        mock_doc.word_count = 0
        mock_doc.char_count = 0
        mock_doc.estimated_tokens = 0
        mock_doc.language = "en"

        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=mock_doc)
        mock_repo_cls.return_value = mock_repo

        with patch("app.workers.ingestion.tasks.DocumentProcessor") as mock_proc_cls:
            mock_proc = MagicMock()
            mock_proc.process = AsyncMock(return_value=mock_doc)
            mock_proc_cls.return_value = mock_proc

            result = process_document_task.run("doc-1", "/tmp/file.pdf")

            assert result["document_id"] == "doc-1"


class TestGenerateChunksTask:
    @patch("app.workers.ingestion.tasks.ChunkRepository")
    @patch("app.workers.ingestion.tasks.KnowledgeRepository")
    @patch("app.workers.ingestion.tasks.ChunkingService")
    @patch("app.workers.ingestion.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.complete_job", new_callable=AsyncMock)
    def test_success(
        self, mock_complete, mock_progress, mock_svc_cls, mock_knowledge_repo_cls, mock_chunk_repo_cls,
    ):
        from app.workers.ingestion.tasks import generate_chunks_task

        mock_doc = MagicMock()
        mock_doc.id = "doc-1"

        mock_knowledge_repo = MagicMock()
        mock_knowledge_repo.find_by_id = AsyncMock(return_value=mock_doc)
        mock_knowledge_repo_cls.return_value = mock_knowledge_repo

        mock_result = MagicMock()
        mock_result.document_id = "doc-1"
        mock_result.strategy = "recursive_character"
        mock_result.chunk_count = 5
        mock_result.chunks = [MagicMock(id="chunk-1"), MagicMock(id="chunk-2")]

        mock_svc = MagicMock()
        mock_svc.chunk_document = AsyncMock(return_value=mock_result)
        mock_svc_cls.return_value = mock_svc

        result = generate_chunks_task.run("doc-1", "recursive_character", 1000, 200, "job-1")

        assert result["document_id"] == "doc-1"
        assert result["chunk_count"] == 5
        assert len(result["chunk_ids"]) == 2

    @patch("app.workers.ingestion.tasks.ChunkRepository")
    @patch("app.workers.ingestion.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.ingestion.tasks.KnowledgeRepository")
    @patch("app.workers.ingestion.tasks.fail_job", new_callable=AsyncMock)
    def test_document_not_found(self, mock_fail, mock_repo_cls, mock_progress, mock_chunk_repo_cls):
        from app.workers.ingestion.tasks import generate_chunks_task

        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=None)
        mock_repo_cls.return_value = mock_repo

        with pytest.raises(ValueError, match="not found"):
            generate_chunks_task.run("doc-1", job_id="job-1")


# ---------- Summarization Worker Tests ----------

class TestGenerateSummaryTask:
    @patch("app.workers.summarization.tasks.KnowledgeRepository")
    @patch("app.workers.summarization.tasks.BusinessSummaryRepository")
    @patch("app.workers.summarization.tasks.LLMProviderFactory")
    @patch("app.workers.summarization.tasks.BusinessSummaryGenerationService")
    @patch("app.workers.summarization.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.summarization.tasks.complete_job", new_callable=AsyncMock)
    def test_success(
        self, mock_complete, mock_progress, mock_svc_cls, mock_factory_cls,
        mock_summary_repo_cls, mock_knowledge_repo_cls,
    ):
        from app.workers.summarization.tasks import generate_summary_task

        mock_summary = MagicMock()
        mock_summary.id = "sum-1"
        mock_summary.document_id = "doc-1"
        mock_summary.version_number = 1
        mock_summary.title = "Summary"

        mock_svc = MagicMock()
        mock_svc.generate = AsyncMock(return_value=mock_summary)
        mock_svc_cls.return_value = mock_svc

        result = generate_summary_task.run("store-1", "gpt-4o-mini", 0.3, 4096, "job-1")

        assert result["id"] == "sum-1"
        assert result["title"] == "Summary"
        assert result["version_number"] == 1


# ---------- Embedding Worker Tests ----------

class TestGenerateEmbeddingsTask:
    @patch("app.workers.embedding.tasks.ChunkRepository")
    @patch("app.workers.embedding.tasks.LLMProviderFactory")
    @patch("app.workers.embedding.tasks.ModelRegistry")
    @patch("app.workers.embedding.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.embedding.tasks.complete_job", new_callable=AsyncMock)
    def test_success(
        self, mock_complete, mock_progress, mock_registry, mock_factory_cls, mock_repo_cls,
    ):
        from app.workers.embedding.tasks import generate_embeddings_task

        mock_model_info = MagicMock()
        mock_model_info.provider = "openai"
        mock_registry.get_model_info.return_value = mock_model_info

        mock_provider = AsyncMock()
        mock_provider.embeddings = AsyncMock()
        mock_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2], [0.3, 0.4]])
        mock_factory = MagicMock()
        mock_factory.get_provider.return_value = mock_provider
        mock_factory_cls.return_value = mock_factory

        mock_chunk = MagicMock()
        mock_chunk.id = "chunk-1"
        mock_chunk.content = "Test content"
        mock_chunk.embedding_id = None

        mock_repo = MagicMock()
        mock_repo.find_by_id = AsyncMock(return_value=mock_chunk)
        mock_repo.update = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        result = generate_embeddings_task.run(["chunk-1", "chunk-2"], "text-embedding-3-small", "job-1")

        assert result["total_chunks"] == 2
        assert result["processed"] == 2
    @patch("app.workers.embedding.tasks.ChunkRepository")
    @patch("app.workers.embedding.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.embedding.tasks.ModelRegistry")
    @patch("app.workers.embedding.tasks.fail_job", new_callable=AsyncMock)
    def test_model_not_found(self, mock_fail, mock_registry, mock_progress, mock_chunk_repo_cls):
        from app.workers.embedding.tasks import generate_embeddings_task

        mock_registry.get_model_info.return_value = None

        with pytest.raises(ValueError, match="not found in registry"):
            generate_embeddings_task.run(["chunk-1"], "unknown-model", "job-1")



class TestSyncVectorsTask:
    @patch("app.workers.embedding.tasks.update_job_progress", new_callable=AsyncMock)
    @patch("app.workers.embedding.tasks.complete_job", new_callable=AsyncMock)
    def test_success(
        self, mock_complete, mock_progress,
    ):
        from app.workers.embedding.tasks import sync_vectors_task

        with patch("app.workers.embedding.tasks.ChunkRepository") as mock_repo_cls, \
             patch("app.workers.embedding.tasks.LLMProviderFactory") as mock_factory_cls, \
             patch("app.workers.embedding.tasks.ModelRegistry") as mock_registry, \
             patch("app.infrastructure.qdrant.provider.QdrantProvider") as mock_qdrant_cls:
            mock_model_info = MagicMock()
            mock_model_info.provider = "openai"
            mock_registry.get_model_info.return_value = mock_model_info

            mock_provider = AsyncMock()
            mock_provider.embeddings = AsyncMock()
            mock_provider.embeddings.return_value = MagicMock(embeddings=[[0.1, 0.2]])
            mock_factory = MagicMock()
            mock_factory.get_provider.return_value = mock_provider
            mock_factory_cls.return_value = mock_factory

            mock_chunk = MagicMock()
            mock_chunk.id = "chunk-1"
            mock_chunk.content = "Test"
            mock_chunk.document_id = "doc-1"
            mock_chunk.chunk_index = 0
            mock_chunk.metadata = {}

            mock_repo = MagicMock()
            mock_repo.find_by_id = AsyncMock(return_value=mock_chunk)
            mock_repo_cls.return_value = mock_repo

            mock_qdrant = AsyncMock()
            mock_qdrant.connect = AsyncMock()
            mock_qdrant.collection_exists = AsyncMock(return_value=True)
            mock_qdrant.upsert = AsyncMock(return_value=1)
            mock_qdrant.disconnect = AsyncMock()
            mock_qdrant_cls.return_value = mock_qdrant

            result = sync_vectors_task.run(["chunk-1"], "kb_default", "text-embedding-3-small", "job-1")

        assert result["synced"] == 1
        assert result["collection"] == "kb_default"

    @patch("app.workers.embedding.tasks.update_job_progress", new_callable=AsyncMock)
    def test_model_not_found(self, mock_progress):
        from app.workers.embedding.tasks import sync_vectors_task

        with patch("app.workers.embedding.tasks.ChunkRepository"):
            with patch("app.workers.embedding.tasks.ModelRegistry") as mock_registry:
                mock_registry.get_model_info.return_value = None

                with patch("app.workers.embedding.tasks.fail_job", new_callable=AsyncMock):
                    with pytest.raises(ValueError, match="not found in registry"):
                        sync_vectors_task.run(["chunk-1"], job_id="job-1")


# ---------- Scheduler Worker Tests ----------

class TestRetryFailedJobsTask:
    @patch("app.workers.scheduler.tasks.get_knowledge_jobs_collection")
    def test_requeues_stale_running_and_retryable(self, mock_collection_get):
        from app.workers.scheduler.tasks import retry_failed_jobs_task

        mock_stale = [
            {"_id": "id1", "status": "running"},
            {"_id": "id2", "status": "running"},
        ]
        mock_retryable = [
            {"_id": "id3", "status": "retrying"},
        ]

        mock_coll = MagicMock()
        mock_coll.find = MagicMock()
        mock_coll.find.return_value.to_list = AsyncMock(side_effect=[mock_stale, mock_retryable])
        mock_coll.update_one = AsyncMock()
        mock_collection_get.return_value = mock_coll

        result = retry_failed_jobs_task()

        assert result["stale_running_requeued"] == 2
        assert result["retryable_requeued"] == 1

    @patch("app.workers.scheduler.tasks.get_knowledge_jobs_collection")
    def test_no_jobs_to_requeue(self, mock_collection_get):
        from app.workers.scheduler.tasks import retry_failed_jobs_task

        mock_coll = MagicMock()
        mock_coll.find = MagicMock()
        mock_coll.find.return_value.to_list = AsyncMock(side_effect=[[], []])
        mock_coll.update_one = AsyncMock()
        mock_collection_get.return_value = mock_coll

        result = retry_failed_jobs_task()

        assert result["stale_running_requeued"] == 0
        assert result["retryable_requeued"] == 0


class TestCleanupDeadLettersTask:
    @patch("app.workers.scheduler.tasks.get_knowledge_jobs_collection")
    def test_dry_run(self, mock_collection_get):
        from app.workers.scheduler.tasks import cleanup_dead_letters_task

        mock_coll = MagicMock()
        mock_coll.find = MagicMock()
        mock_coll.find.return_value.to_list = AsyncMock(return_value=[{"_id": "dead-1"}, {"_id": "dead-2"}])
        mock_collection_get.return_value = mock_coll

        result = cleanup_dead_letters_task(dry_run=True)

        assert result["found_old_dead_letters"] == 2
        assert result["dry_run"] is True
        assert result["deleted"] == 0

    @patch("app.workers.scheduler.tasks.get_knowledge_jobs_collection")
    def test_actual_cleanup(self, mock_collection_get):
        from app.workers.scheduler.tasks import cleanup_dead_letters_task

        mock_coll = MagicMock()
        mock_coll.find = MagicMock()
        mock_coll.find.return_value.to_list = AsyncMock(return_value=[{"_id": "dead-1"}])
        mock_coll.delete_many = AsyncMock()
        mock_collection_get.return_value = mock_coll

        result = cleanup_dead_letters_task(dry_run=False)

        assert result["found_old_dead_letters"] == 1
        assert result["deleted"] == 1
        mock_coll.delete_many.assert_awaited_once()


# ---------- Cleanup Worker Tests ----------

class TestProcessDeadLetterQueueTask:
    @patch("app.workers.cleanup.tasks.get_knowledge_jobs_collection")
    @patch("app.workers.cleanup.tasks.requeue_dead_letter", new_callable=AsyncMock)
    def test_requeues_dead_letters(self, mock_requeue, mock_collection_get):
        from app.workers.cleanup.tasks import process_dead_letter_queue_task

        mock_coll = MagicMock()
        mock_coll.find = MagicMock()
        mock_coll.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(
            return_value=[{"_id": "dead-1"}, {"_id": "dead-2"}],
        )
        mock_collection_get.return_value = mock_coll

        result = process_dead_letter_queue_task.run(max_items=50)

        assert result["found"] == 2
        assert result["requeued"] == 2
        assert mock_requeue.await_count == 2

    @patch("app.workers.cleanup.tasks.get_knowledge_jobs_collection")
    @patch("app.workers.cleanup.tasks.requeue_dead_letter", new_callable=AsyncMock)
    def test_no_dead_letters(self, mock_requeue, mock_collection_get):
        from app.workers.cleanup.tasks import process_dead_letter_queue_task

        mock_coll = MagicMock()
        mock_coll.find = MagicMock()
        mock_coll.find.return_value.sort.return_value.limit.return_value.to_list = AsyncMock(return_value=[])
        mock_collection_get.return_value = mock_coll

        result = process_dead_letter_queue_task.run(max_items=50)

        assert result["found"] == 0
        assert result["requeued"] == 0
