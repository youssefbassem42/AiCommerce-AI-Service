from typing import Any, TypedDict

from app.agents.integration.schemas import IntegrationMappingReport


class IntegrationMappingState(TypedDict):
    raw_spec: Any
    platform_name: str
    store_id: str
    organization_id: str
    spec_format: str
    parsed_spec: dict | None
    report: IntegrationMappingReport | None
    capabilities: dict[str, bool] | None
    error: str | None
    user_friendly_error: str | None
    connection_id: str | None
