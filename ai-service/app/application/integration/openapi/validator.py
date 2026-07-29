import logging
from dataclasses import dataclass, field
from typing import Optional

from app.application.integration.openapi.parser import IntegrationSchema

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


class SpecValidator:
    """Validates completeness of a parsed IntegrationSchema."""

    def validate(
        self,
        schema: IntegrationSchema,
        platform_name: Optional[str] = None,
    ) -> ValidationReport:
        report = ValidationReport()

        if not schema.endpoints:
            report.errors.append("Spec contains zero endpoints.")

        total_endpoints = len(schema.endpoints)
        if total_endpoints < 1:
            report.errors.append("At least one endpoint is required.")

        has_auth = len(schema.auth_methods) > 0
        if not has_auth:
            report.warnings.append(
                "No authentication scheme found in spec. "
                "This may limit the integration's usability."
            )

        if not schema.base_url:
            report.errors.append(
                "Base URL could not be extracted from spec. "
                "The platform will not be reachable."
            )

        if not schema.schemas:
            report.warnings.append(
                "No reusable schemas defined. "
                "Automatic entity/field discovery will be limited."
            )

        has_list_endpoint = any(
            ep.method == "GET" and "{" not in ep.path
            for ep in schema.endpoints
        )
        if not has_list_endpoint:
            report.warnings.append(
                "No simple GET list endpoint detected (no path params). "
                "Data synchronization may require additional configuration."
            )

        has_detail_endpoint = any(
            ep.method == "GET" and "{" in ep.path
            for ep in schema.endpoints
        )
        if not has_detail_endpoint:
            report.warnings.append(
                "No detail GET endpoint detected (with path params). "
                "Individual record lookups may not be supported."
            )

        for ep in schema.endpoints:
            self._validate_endpoint(ep, report)

        return report

    def _validate_endpoint(self, ep: "EndpointSchema", report: ValidationReport) -> None:
        if not ep.path.startswith("/"):
            report.warnings.append(
                f"Endpoint path '{ep.path}' should start with '/'."
            )
        if ep.method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
            report.warnings.append(
                f"Endpoint '{ep.method} {ep.path}' uses unusual HTTP method."
            )