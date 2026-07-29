from app.application.knowledge.dto import (
    BusinessSummaryDTO,
    DocumentMetadataDTO,
    DocumentVersionDTO,
    KnowledgeChunkDTO,
    KnowledgeDocumentDTO,
)
from app.domain.knowledge.entities.business_summary import BusinessSummary
from app.domain.knowledge.entities.knowledge_chunk import KnowledgeChunk
from app.domain.knowledge.entities.knowledge_document import KnowledgeDocument
from app.infrastructure.mongodb.documents.business_summary_document import BusinessSummaryDocument
from app.infrastructure.mongodb.documents.knowledge_chunk_document import KnowledgeChunkDocument
from app.infrastructure.mongodb.documents.knowledge_document import KnowledgeDocumentModel


class KnowledgeMapper:
    """Maps knowledge documents, chunks, and summaries across layers."""

    @staticmethod
    def to_document_entity(doc: KnowledgeDocumentModel) -> KnowledgeDocument:
        return doc.to_entity()

    @staticmethod
    def to_chunk_entity(doc: KnowledgeChunkDocument) -> KnowledgeChunk:
        return doc.to_entity()

    @staticmethod
    def to_summary_entity(doc: BusinessSummaryDocument) -> BusinessSummary:
        return doc.to_entity()

    @staticmethod
    def to_document_dto(entity: KnowledgeDocument) -> KnowledgeDocumentDTO:
        return KnowledgeDocumentDTO(
            id=entity.id,
            store_id=entity.store_id,
            title=entity.title,
            description=entity.description,
            source_url=entity.source_url,
            status=entity.status,
            language=entity.language,
            metadata=DocumentMetadataDTO(**entity.metadata.model_dump()),
            versions=[DocumentVersionDTO(**version.model_dump()) for version in entity.versions],
            current_version=entity.current_version,
            chunks=[KnowledgeChunkDTO(**chunk.model_dump()) for chunk in entity.chunks],
            chunking_strategy=entity.chunking_strategy,
            processed_text=entity.processed_text,
            page_count=entity.page_count,
            word_count=entity.word_count,
            char_count=entity.char_count,
            estimated_tokens=entity.estimated_tokens,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
            deleted_at=entity.deleted_at,
        )

    @staticmethod
    def to_chunk_dto(entity: KnowledgeChunk) -> KnowledgeChunkDTO:
        return KnowledgeChunkDTO(**entity.model_dump())

    @staticmethod
    def to_summary_dto(entity: BusinessSummary) -> BusinessSummaryDTO:
        return BusinessSummaryDTO(**entity.model_dump())
