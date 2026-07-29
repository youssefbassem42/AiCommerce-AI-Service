from fastapi import Depends

from app.application.knowledge.processing.pipeline import ProcessingPipeline
from app.application.knowledge.processing.processor import DocumentProcessor
from app.infrastructure.knowledge.extractors import ExtractorFactory
from app.infrastructure.mongodb.repositories.knowledge_repository import KnowledgeRepository


def get_knowledge_repository() -> KnowledgeRepository:
    return KnowledgeRepository()


def get_extractor_factory() -> ExtractorFactory:
    return ExtractorFactory()


def get_processing_pipeline() -> ProcessingPipeline:
    return ProcessingPipeline()


def get_document_processor(
    repository: KnowledgeRepository = Depends(get_knowledge_repository),
    extractor_factory: ExtractorFactory = Depends(get_extractor_factory),
    pipeline: ProcessingPipeline = Depends(get_processing_pipeline),
) -> DocumentProcessor:
    return DocumentProcessor(
        repository=repository,
        extractor_factory=extractor_factory,
        pipeline=pipeline,
    )
