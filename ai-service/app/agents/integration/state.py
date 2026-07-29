from typing import Any, Optional, TypedDict

from app.agents.integration.schemas import IntegrationMappingReport


class IntegrationMappingState(TypedDict):
    raw_spec: Any
    platform_name: str
    store_id: str
    organization_id: str
    spec_format: str
    parsed_spec: Optional[dict]
    report: Optional[IntegrationMappingReport]
    capabilities: Optional[dict[str, bool]]
    error: Optional[str]
    user_friendly_error: Optional[str]
    connection_id: Optional[str]
