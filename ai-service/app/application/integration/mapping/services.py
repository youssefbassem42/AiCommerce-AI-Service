import json
import logging
from typing import Any, Optional
from bson import ObjectId

from app.application.integration.discovery.endpoint_classifier import EndpointClassifier
from app.application.integration.discovery.entity_detector import EntityDetector
from app.application.integration.discovery.field_suggester import FieldSuggester
from app.application.integration.discovery.schema_discovery import SchemaDiscovery
from app.application.integration.mapping.discovery import MappingSuggestor
from app.application.integration.mapping.dto import (
    AuthConfigDTO,
    ConnectionCreateDTO,
    ConnectionResponseDTO,
    EntityMappingDTO,
    EndpointSchemaDTO,
    FieldMappingDTO,
    PaginationConfigDTO,
    ParseSpecRequestDTO,
    ParseSpecResponseDTO,
)
from app.application.integration.openapi.parser import OpenApiParser
from app.application.integration.openapi.resolver import RefResolver
from app.application.integration.openapi.validator import SpecValidator
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.exceptions import (
    DuplicateConnectionException,
    IntegrationConnectionNotFoundException,
)
from app.domain.integration.repositories.integration_connection_repository import (
    IntegrationConnectionRepository,
)
from app.domain.integration.value_objects.auth_config import (
    AuthConfig,
    AuthType,
    CredentialsLocation,
)
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig
from app.infrastructure.security.key_manager import KeyManager
from app.agents.integration.agent import IntegrationMappingAgent
from app.agents.integration.schemas import IntegrationMappingReport

logger = logging.getLogger(__name__)


class IntegrationApplicationService:
    def __init__(
        self,
        repository: IntegrationConnectionRepository,
        parser: Optional[OpenApiParser] = None,
        validator: Optional[SpecValidator] = None,
        classifier: Optional[EndpointClassifier] = None,
        entity_detector: Optional[EntityDetector] = None,
        field_suggester: Optional[FieldSuggester] = None,
        mapping_suggestor: Optional[MappingSuggestor] = None,
        key_manager: Optional[KeyManager] = None,
    ):
        self._repository = repository
        self._parser = parser or OpenApiParser()
        self._validator = validator or SpecValidator()
        self._classifier = classifier or EndpointClassifier()
        self._entity_detector = entity_detector or EntityDetector()
        self._field_suggester = field_suggester or FieldSuggester()
        self._mapping_suggestor = mapping_suggestor or MappingSuggestor()
        self._key_manager = key_manager or KeyManager()
        self._agent = IntegrationMappingAgent()

    async def parse_spec(self, request: ParseSpecRequestDTO) -> ParseSpecResponseDTO:
        integration_schema = self._parser.parse(
            spec=request.raw_spec,
            platform_name=request.platform_name,
        )

        report = self._validator.validate(integration_schema)

        resolver = RefResolver(integration_schema.schemas)
        schema_discovery = SchemaDiscovery(resolver)
        discovered_schemas = schema_discovery.discover(integration_schema.endpoints)

        endpoint_dtos = [
            EndpointSchemaDTO(
                path=ep.path,
                method=ep.method,
                operation_id=ep.operation_id,
                summary=ep.summary,
                parameters=ep.parameters,
                response_schema_ref=ep.response_schema_ref,
            )
            for ep in integration_schema.endpoints
        ]

        auth_dtos = [
            AuthConfigDTO(
                type=a.type.value,
                credentials_location=a.credentials_location.value,
                scheme=a.scheme,
                name=a.name,
                token_url=a.token_url,
                flow=a.flow,
            )
            for a in integration_schema.auth_methods
        ]

        discovered_entities: list[dict] = []
        for ds in discovered_schemas:
            result = self._entity_detector.detect(ds.field_names)
            if result.entity_type:
                discovered_entities.append({
                    "entity_type": result.entity_type,
                    "confidence": result.confidence,
                    "matched_fields": result.matched_fields,
                    "endpoint_path": ds.endpoint.path,
                    "endpoint_method": ds.endpoint.method,
                })

        suggested_entity_mappings: list[EntityMappingDTO] = []
        for de in discovered_entities:
            field_mappings = self._mapping_suggestor.suggest_mappings(
                external_fields=set(de["matched_fields"]),
                entity_type=de["entity_type"],
            )
            if field_mappings:
                suggested_entity_mappings.append(
                    EntityMappingDTO(
                        entity_type=de["entity_type"],
                        list_path=de["endpoint_path"],
                        id_field="id",
                        field_mappings=[
                            FieldMappingDTO(
                                source=fm.source,
                                target=fm.target,
                                transformer=fm.transformer,
                                required=fm.required,
                            )
                            for fm in field_mappings
                        ],
                    )
                )

        return ParseSpecResponseDTO(
            platform_name=integration_schema.platform_name,
            base_url=integration_schema.base_url,
            api_version=integration_schema.api_version,
            endpoints=endpoint_dtos,
            schemas=integration_schema.schemas,
            auth_methods=auth_dtos,
            discovered_entities=discovered_entities,
            suggested_mappings=suggested_entity_mappings,
            warnings=report.warnings,
            errors=report.errors,
        )

    async def parse_spec_with_agent(
        self,
        raw_spec: Any,
        platform_name: str,
        store_id: str,
        organization_id: str,
    ) -> tuple[Optional[IntegrationMappingReport], Optional[str], Optional[dict]]:
        return await self._agent.analyze(
            raw_spec=raw_spec,
            platform_name=platform_name,
            store_id=store_id,
            organization_id=organization_id,
        )

    async def create_connection(self, data: ConnectionCreateDTO) -> ConnectionResponseDTO:
        existing = await self._repository.find_by_store_and_name(
            store_id=data.store_id, name=data.name
        )
        if existing is not None:
            raise DuplicateConnectionException(
                f"Connection with name '{data.name}' already exists in store '{data.store_id}'."
            )

        raw_spec_dict = self._parser.normalize_spec(data.raw_spec)
        integration_schema = self._parser.parse(raw_spec_dict, data.platform_name)
        auth_config = self._dto_to_auth_config(data.auth_config)

        encrypted = self._encrypt_credentials(data.credentials)

        entity_mappings = [self._dto_to_entity_mapping(em) for em in data.entity_mappings]

        resolver = RefResolver(integration_schema.schemas)
        schema_discovery = SchemaDiscovery(resolver)
        discovered_schemas = schema_discovery.discover(integration_schema.endpoints)

        discovered_endpoints = [
            {
                "path": ep.path,
                "method": ep.method,
                "operation_id": ep.operation_id,
                "summary": ep.summary,
            }
            for ep in integration_schema.endpoints
        ]

        discovered_schemas_dict: dict = {}
        for ds in discovered_schemas:
            key = f"{ds.endpoint.method} {ds.endpoint.path}"
            discovered_schemas_dict[key] = {
                "fields": [{"name": f.name, "type": f.field_type, "required": f.required} for f in ds.resolved.fields],
            }

        entity = IntegrationConnection(
            id=str(ObjectId()),
            store_id=data.store_id,
            organization_id=data.organization_id,
            name=data.name,
            platform_name=data.platform_name,
            status=ConnectionStatus.INACTIVE,
            spec_version=integration_schema.api_version,
            raw_spec=raw_spec_dict,
            auth_config=auth_config,
            encrypted_credentials=encrypted,
            entity_mappings=entity_mappings,
            discovered_endpoints=discovered_endpoints,
            discovered_schemas=discovered_schemas_dict,
        )

        created = await self._repository.create(entity)
        return self._entity_to_response_dto(created)

    async def get_connection(self, connection_id: str) -> ConnectionResponseDTO:
        entity = await self._repository.find_by_id(connection_id)
        if entity is None:
            raise IntegrationConnectionNotFoundException(connection_id)
        return self._entity_to_response_dto(entity)

    async def list_connections(
        self, store_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[ConnectionResponseDTO], int]:
        items, total = await self._repository.find_by_store(
            store_id=store_id, page=page, page_size=page_size
        )
        return [self._entity_to_response_dto(item) for item in items], total

    async def update_mappings(
        self,
        connection_id: str,
        entity_mappings: list[EntityMappingDTO],
    ) -> ConnectionResponseDTO:
        entity = await self._repository.find_by_id(connection_id)
        if entity is None:
            raise IntegrationConnectionNotFoundException(connection_id)
        mappings = [self._dto_to_entity_mapping(em) for em in entity_mappings]
        entity.update_mappings(mappings)
        updated = await self._repository.update(entity)
        return self._entity_to_response_dto(updated)

    async def update_credentials(
        self,
        connection_id: str,
        auth_config_dto: AuthConfigDTO,
        credentials: dict[str, str],
    ) -> ConnectionResponseDTO:
        entity = await self._repository.find_by_id(connection_id)
        if entity is None:
            raise IntegrationConnectionNotFoundException(connection_id)
        auth_config = self._dto_to_auth_config(auth_config_dto)
        encrypted = self._encrypt_credentials(credentials)
        entity.set_credentials(auth_config, encrypted)
        entity.activate()
        updated = await self._repository.update(entity)
        return self._entity_to_response_dto(updated)

    async def delete_connection(self, connection_id: str) -> bool:
        entity = await self._repository.find_by_id(connection_id)
        if entity is None:
            raise IntegrationConnectionNotFoundException(connection_id)
        return await self._repository.delete(connection_id)

    def _encrypt_credentials(self, credentials: dict[str, str]) -> str:
        return self._key_manager.encrypt_secret(json.dumps(credentials))

    @staticmethod
    def _dto_to_auth_config(dto: AuthConfigDTO) -> AuthConfig:
        return AuthConfig(
            type=AuthType(dto.type),
            credentials_location=CredentialsLocation(dto.credentials_location),
            scheme=dto.scheme,
            name=dto.name,
            token_url=dto.token_url,
            flow=dto.flow,
        )

    @staticmethod
    def _dto_to_entity_mapping(dto: EntityMappingDTO) -> EntityMapping:
        return EntityMapping(
            entity_type=dto.entity_type,
            list_path=dto.list_path,
            list_method=dto.list_method,
            detail_path=dto.detail_path,
            detail_method=dto.detail_method,
            id_field=dto.id_field,
            pagination=PaginationConfig(
                style=dto.pagination.style,
                page_param=dto.pagination.page_param,
                limit_param=dto.pagination.limit_param,
                default_limit=dto.pagination.default_limit,
                cursor_field=dto.pagination.cursor_field,
                total_field=dto.pagination.total_field,
                next_link_field=dto.pagination.next_link_field,
            ),
            field_mappings=[
                FieldMapping(
                    source=fm.source,
                    target=fm.target,
                    transformer=fm.transformer,
                    default_value=fm.default_value,
                    required=fm.required,
                )
                for fm in dto.field_mappings
            ],
        )

    @staticmethod
    def _entity_to_response_dto(entity: IntegrationConnection) -> ConnectionResponseDTO:
        return ConnectionResponseDTO(
            id=entity.id,
            store_id=entity.store_id,
            organization_id=entity.organization_id,
            name=entity.name,
            platform_name=entity.platform_name,
            status=entity.status.value,
            spec_version=entity.spec_version,
            auth_config=AuthConfigDTO(
                type=entity.auth_config.type.value,
                credentials_location=entity.auth_config.credentials_location.value,
                scheme=entity.auth_config.scheme,
                name=entity.auth_config.name,
                token_url=entity.auth_config.token_url,
                flow=entity.auth_config.flow,
            ),
            entity_mappings=[
                EntityMappingDTO(
                    entity_type=em.entity_type,
                    list_path=em.list_path,
                    list_method=em.list_method,
                    detail_path=em.detail_path,
                    detail_method=em.detail_method,
                    id_field=em.id_field,
                    pagination=PaginationConfigDTO(
                        style=em.pagination.style.value,
                        page_param=em.pagination.page_param,
                        limit_param=em.pagination.limit_param,
                        default_limit=em.pagination.default_limit,
                        cursor_field=em.pagination.cursor_field,
                        total_field=em.pagination.total_field,
                        next_link_field=em.pagination.next_link_field,
                    ),
                    field_mappings=[
                        FieldMappingDTO(
                            source=fm.source,
                            target=fm.target,
                            transformer=fm.transformer,
                            default_value=fm.default_value,
                            required=fm.required,
                        )
                        for fm in em.field_mappings
                    ],
                )
                for em in entity.entity_mappings
            ],
            discovered_endpoints=entity.discovered_endpoints,
            discovered_schemas=entity.discovered_schemas,
            last_sync_at=entity.last_sync_at,
            last_sync_status=entity.last_sync_status,
            error_message=entity.error_message,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
