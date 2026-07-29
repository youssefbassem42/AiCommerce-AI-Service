from app.domain.recommendation.entities.store_capabilities import StoreCapabilities
from app.infrastructure.mongodb.documents.store_capabilities_document import StoreCapabilitiesDocument


class StoreCapabilitiesMapper:
    @staticmethod
    def to_entity(doc: StoreCapabilitiesDocument) -> StoreCapabilities:
        return doc.to_entity()

    @staticmethod
    def to_document(entity: StoreCapabilities) -> StoreCapabilitiesDocument:
        return StoreCapabilitiesDocument.from_entity(entity)

    @staticmethod
    def capabilities_to_dict(entity: StoreCapabilities) -> dict[str, bool]:
        return dict(entity.capabilities)
