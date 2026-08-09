import json
import logging
from datetime import UTC, datetime
from typing import Any

from app.agents.integration.agent import IntegrationMappingAgent
from app.agents.integration.schemas import AuthInfo, IntegrationMappingReport
from app.application.integration.mapping.dto import (
    AuthConfigDTO,
    ConnectionCreateDTO,
    EntityMappingDTO,
    FieldMappingDTO,
    PaginationConfigDTO,
)
from app.application.integration.mapping.services import IntegrationApplicationService
from app.application.integration.sync.orchestrator import SyncOrchestrator
from app.domain.integration.entities.integration_connection import (
    ConnectionStatus,
    IntegrationConnection,
)
from app.domain.integration.value_objects.auth_config import AuthConfig, AuthType, CredentialsLocation
from app.domain.integration.value_objects.entity_mapping import EntityMapping
from app.domain.integration.value_objects.field_mapping import FieldMapping
from app.domain.integration.value_objects.pagination_config import PaginationConfig, PaginationStyle
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


def _infer_auth_from_spec(spec: dict) -> AuthConfigDTO | None:
    """Derive the auth config from the OpenAPI contract's security schemes.

    The API specification is the authoritative source for authentication:
    prefer it over the mapping agent's guess.
    """
    schemes = ((spec.get("components") or {}).get("securitySchemes") or {}).items()
    for _name, scheme in schemes:
        if not isinstance(scheme, dict):
            continue
        scheme_type = scheme.get("type")
        if scheme_type == "http":
            http_scheme = str(scheme.get("scheme", "")).lower()
            if http_scheme == "bearer":
                return AuthConfigDTO(type="bearer", credentials_location="header", scheme="bearer")
            if http_scheme == "basic":
                return AuthConfigDTO(type="basic", credentials_location="header", scheme="basic")
        elif scheme_type == "apiKey":
            return AuthConfigDTO(
                type="apiKey",
                credentials_location=str(scheme.get("in", "header")),
                name=str(scheme.get("name") or ""),
            )
        elif scheme_type == "oauth2":
            flows = scheme.get("flows") or {}
            flow = next(iter(flows), None) or "clientCredentials"
            token_url = str((flows.get(flow) or {}).get("tokenUrl") or "")
            return AuthConfigDTO(type="oauth2", token_url=token_url, flow=str(flow))
    return None


def _to_auth_config_dto(info: AuthInfo | None) -> AuthConfigDTO:
    if info is None:
        return AuthConfigDTO()
    return AuthConfigDTO(
        type=info.type or "apiKey",
        credentials_location=info.credentials_location or "header",
        scheme=info.scheme,
        name=info.name,
        token_url=info.token_url,
        flow=info.flow,
    )


PAGINATION_STYLES = {"none", "offset", "page", "cursor"}


def _normalize_pagination_style(style: str | None, page_param: str | None = None) -> str:
    """Map loose pagination style labels from the mapping agent onto the canonical enum."""
    candidate = (style or "none").strip().lower()
    if candidate in PAGINATION_STYLES:
        return candidate
    if candidate in {"pagination", "page-number", "per-page", "page_based"}:
        return "page"
    if candidate in {"offset-based", "limit-offset", "offset_based"}:
        return "offset"
    if page_param:
        return "page"
    return "none"


class IntegrationSyncResult:
    def __init__(self):
        self.connection_id: str | None = None
        self.mapping_report: IntegrationMappingReport | None = None
        self.capabilities: dict[str, bool] | None = None
        self.sync_result: dict | None = None
        self.error: str | None = None
        self.user_friendly_error: str | None = None
        self.started_at: datetime = datetime.now(UTC)
        self.completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "connection_id": self.connection_id,
            "mapping_report": self.mapping_report.model_dump() if self.mapping_report else None,
            "capabilities": self.capabilities,
            "sync_result": self.sync_result,
            "error": self.error,
            "user_friendly_error": self.user_friendly_error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class IntegrationWorkflow:
    def __init__(
        self,
        integration_service: IntegrationApplicationService,
        sync_orchestrator: SyncOrchestrator,
        llm: BaseLLMProvider | None = None,
        model: str | None = None,
    ):
        self._mapping_agent = IntegrationMappingAgent(llm=llm, model=model)
        self._integration_service = integration_service
        self._sync_orchestrator = sync_orchestrator

    async def run(
        self,
        raw_spec: Any,
        platform_name: str,
        store_id: str,
        organization_id: str,
        credentials: dict[str, str] | None = None,
        connection_name: str | None = None,
        auto_sync: bool = True,
    ) -> IntegrationSyncResult:
        result = IntegrationSyncResult()

        try:
            report, error, capabilities = await self._mapping_agent.analyze(
                raw_spec=raw_spec,
                platform_name=platform_name,
                store_id=store_id,
                organization_id=organization_id,
            )

            result.mapping_report = report
            result.capabilities = capabilities

            if error or report is None:
                result.error = error
                result.user_friendly_error = error
                result.completed_at = datetime.now(UTC)
                return result

            connection = await self._create_connection(
                raw_spec=raw_spec,
                report=report,
                platform_name=platform_name,
                store_id=store_id,
                organization_id=organization_id,
                credentials=credentials,
                connection_name=connection_name,
                capabilities=capabilities,
            )
            result.connection_id = connection.id

            if auto_sync and (
                connection.status == ConnectionStatus.ACTIVE
                or (
                    connection.status == ConnectionStatus.INACTIVE
                    and not connection.encrypted_credentials
                )
            ):
                sync = await self._sync_orchestrator.sync_connection(connection.id)
                result.sync_result = sync.to_dict()

        except Exception as e:
            logger.exception("Integration workflow failed")
            result.error = str(e)
            result.user_friendly_error = (
                "We couldn't complete the integration setup. "
                "The API specification was analyzed successfully, but something went wrong "
                "during the connection or sync process. Please try again or contact support."
            )

        result.completed_at = datetime.now(UTC)
        return result

    async def _create_connection(
        self,
        raw_spec: Any,
        report: IntegrationMappingReport,
        platform_name: str,
        store_id: str,
        organization_id: str,
        credentials: dict[str, str] | None,
        connection_name: str | None,
        capabilities: dict[str, bool] | None,
    ) -> IntegrationConnection:
        spec_dict = raw_spec if isinstance(raw_spec, dict) else {}
        auth_config = _infer_auth_from_spec(spec_dict) or _to_auth_config_dto(report.auth)
        creds = credentials or {}

        entity_mappings = []
        for entity in report.entities:
            if not entity.list_path and not entity.detail_path:
                continue
            entity_mappings.append(
                EntityMappingDTO(
                    entity_type=entity.entity_type,
                    list_path=entity.list_path,
                    list_method=entity.list_method,
                    detail_path=entity.detail_path,
                    detail_method=entity.detail_method,
                    id_field=entity.id_field,
                    pagination=PaginationConfigDTO(
                        style=_normalize_pagination_style(entity.pagination.style, entity.pagination.page_param),
                        page_param=entity.pagination.page_param,
                        limit_param=entity.pagination.limit_param,
                        default_limit=entity.pagination.default_limit or 20,
                        cursor_field=entity.pagination.cursor_field,
                        total_field=entity.pagination.total_field,
                        next_link_field=entity.pagination.next_link_field,
                    ),
                    field_mappings=[
                        FieldMappingDTO(
                            source=fm.source,
                            target=fm.target,
                            transformer=fm.transformer,
                            default_value=fm.default_value,
                            required=fm.required,
                        )
                        for fm in entity.field_mappings
                    ],
                )
            )

        dto = ConnectionCreateDTO(
            store_id=store_id,
            organization_id=organization_id,
            name=connection_name or f"{platform_name} Integration",
            platform_name=platform_name,
            raw_spec=spec_dict,
            auth_config=auth_config,
            credentials=creds,
            entity_mappings=entity_mappings,
        )

        response = await self._integration_service.create_connection(dto)

        connection = IntegrationConnection(
            id=response.id,
            store_id=response.store_id,
            organization_id=response.organization_id,
            name=response.name,
            platform_name=response.platform_name,
            status=ConnectionStatus.ACTIVE if creds else ConnectionStatus.INACTIVE,
            spec_version=response.spec_version,
            raw_spec=spec_dict,
            auth_config=AuthConfig(
                type=AuthType(auth_config.type) if auth_config.type else AuthType.APIKEY,
                credentials_location=CredentialsLocation(auth_config.credentials_location)
                if auth_config.credentials_location
                else CredentialsLocation.HEADER,
                scheme=auth_config.scheme,
                name=auth_config.name,
                token_url=auth_config.token_url,
                flow=auth_config.flow,
            ),
            encrypted_credentials=json.dumps(creds) if creds else None,
            entity_mappings=[
                EntityMapping(
                    entity_type=em.entity_type,
                    list_path=em.list_path,
                    list_method=em.list_method,
                    detail_path=em.detail_path,
                    detail_method=em.detail_method,
                    id_field=em.id_field,
                    pagination=PaginationConfig(
                        style=PaginationStyle(em.pagination.style) if em.pagination.style else PaginationStyle.NONE,
                        page_param=em.pagination.page_param,
                        limit_param=em.pagination.limit_param,
                        default_limit=em.pagination.default_limit or 20,
                        cursor_field=em.pagination.cursor_field,
                        total_field=em.pagination.total_field,
                        next_link_field=em.pagination.next_link_field,
                    ),
                    field_mappings=[
                        FieldMapping(
                            source=fm.source,
                            target=fm.target,
                            transformer=fm.transformer,
                            default_value=fm.default_value,
                            required=fm.required,
                        )
                        for fm in em.field_mappings
                    ],
                )
                for em in entity_mappings
            ],
            discovered_endpoints=[
                {"path": e.list_path, "method": e.list_method, "entity": e.entity_type}
                for e in report.entities
                if e.list_path
            ],
            discovered_schemas={
                e.entity_type: {
                    "fields": [
                        {"name": fm.target, "type": "string", "required": fm.required} for fm in e.field_mappings
                    ]
                }
                for e in report.entities
            },
        )
        return connection
