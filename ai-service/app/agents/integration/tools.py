import json
import logging
import traceback
import yaml
from typing import Any, Optional

from pydantic import ValidationError

from app.agents.integration.prompts import ANALYZE_SPEC_PROMPT, ERROR_EXPLANATION_PROMPT, FEATURE_GAP_PROMPT
from app.agents.integration.schemas import (
    AuthInfo,
    DiscoveredEntityInfo,
    FeatureAnalysis,
    IntegrationMappingReport,
    PaginationInfo,
)
from app.application.dto.ai_dto import ChatRequest, MessageDTO
from app.core.model_registry import ModelRegistry
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)

CANONICAL_ENTITIES = {
    "product", "order", "customer", "category", "inventory",
    "coupon", "review", "shipment", "payment", "refund",
    "variant", "collection", "discount", "tax", "shipping_zone",
    "webhook", "blog_post", "page", "theme", "gift_card",
    "location", "store_setting", "redirect", "script_tag",
}

E_COMMERCE_FEATURES = [
    "product_catalog",
    "order_management",
    "customer_management",
    "inventory_management",
    "promo_codes_coupons",
    "discounts",
    "shipping",
    "taxes",
    "reviews_ratings",
    "payment_processing",
    "refunds",
    "fulfillment",
    "collections_categories",
    "gift_cards",
    "webhooks",
    "content_management",
    "multi_currency",
    "multi_language",
]


def _select_best_provider() -> tuple[BaseLLMProvider, str]:
    factory = LLMProviderFactory()
    preferred_models = [
        ("openrouter", "openai/gpt-4o-mini", 0.15),
        ("ollama", "llama3", 0.0),
        ("deepseek", "deepseek-chat", 0.14),
        ("openai", "gpt-4o-mini", 0.15),
    ]
    for provider_name, model_name, _ in preferred_models:
        try:
            info = ModelRegistry.get_model_info(model_name)
            if info and info.capabilities.json_mode and info.capabilities.tool_calling:
                provider = factory.get_provider(provider_name)
                health = provider.health_check()
                if health.status == "healthy":
                    return provider, model_name
        except Exception as e:
            logger.debug("Provider %s (%s) unavailable: %s", provider_name, model_name, e)
            continue
    return factory.get_provider("openai"), "gpt-4o-mini"


def _summarize_spec(spec: dict) -> dict:
    paths = spec.get("paths", {})
    schemas = (
        spec.get("components", {}).get("schemas", {})
        or spec.get("definitions", {})
    )
    auth_schemes = (
        spec.get("components", {}).get("securitySchemes", {})
        or spec.get("securityDefinitions", {})
    )
    servers = spec.get("servers", [])
    base_url = servers[0].get("url", "") if servers else ""
    if not base_url:
        host = spec.get("host", "")
        base_path = spec.get("basePath", "")
        scheme = (spec.get("schemes", []) or ["https"])[0]
        if host:
            base_url = f"{scheme}://{host}{base_path}"

    endpoints_summary = []
    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        for method, details in methods.items():
            if method.upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"):
                continue
            summary = details.get("summary") or details.get("operationId") or ""
            params = details.get("parameters", []) + methods.get("parameters", [])
            param_names = [p.get("name", "?") for p in params if isinstance(p, dict)]
            endpoints_summary.append(f"  {method.upper()} {path}")
            if summary:
                endpoints_summary[-1] += f"  # {summary}"
            if param_names:
                endpoints_summary[-1] += f"  params: {', '.join(param_names)}"

    schemas_summary = []
    for name, schema in schemas.items():
        if not isinstance(schema, dict):
            continue
        props = schema.get("properties", {})
        required = schema.get("required", [])
        field_list = []
        for fname, fdef in props.items():
            ftype = fdef.get("type", "unknown") if isinstance(fdef, dict) else "unknown"
            req = " *" if fname in required else ""
            field_list.append(f"{fname}: {ftype}{req}")
        schemas_summary.append(f"  {name}: {', '.join(field_list[:12])}")
        if len(field_list) > 12:
            schemas_summary[-1] += " ..."

    auth_summary = []
    for name, scheme in auth_schemes.items():
        if isinstance(scheme, dict):
            auth_summary.append(f"  {scheme.get('type', '?')} ({name})")

    return {
        "base_url": base_url,
        "endpoints_summary": "\n".join(endpoints_summary[:200]) if endpoints_summary else "  (none)",
        "schemas_summary": "\n".join(schemas_summary[:100]) if schemas_summary else "  (none)",
        "auth_summary": "\n".join(auth_summary) if auth_summary else "  (none)",
        "endpoint_count": len(endpoints_summary),
        "schema_count": len(schemas_summary),
        "spec_version": spec.get("openapi") or spec.get("swagger", "unknown"),
    }


def _extract_spec_format(spec: Any) -> str:
    if isinstance(spec, dict):
        return "json"
    if isinstance(spec, str):
        try:
            json.loads(spec)
            return "json"
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            yaml.safe_load(spec)
            return "yaml"
        except yaml.YAMLError:
            pass
    return "unknown"


def _ensure_dict(spec: Any) -> dict:
    if isinstance(spec, dict):
        return spec
    if isinstance(spec, str):
        try:
            return json.loads(spec)
        except (json.JSONDecodeError, ValueError):
            pass
        try:
            result = yaml.safe_load(spec)
            if isinstance(result, dict):
                return result
        except yaml.YAMLError:
            pass
    return {}


MAX_RETRIES = 3


def _build_fallback_report(summary: dict, platform_name: str) -> IntegrationMappingReport:
    return IntegrationMappingReport(
        platform_name=platform_name,
        base_url=summary.get("base_url", ""),
        api_version=summary.get("spec_version", "unknown"),
        spec_format="json",
        entities=[],
        auth=AuthInfo(),
        feature_analysis=FeatureAnalysis(),
        warnings=["LLM analysis failed; built from spec summary only."],
        errors=["Agent-parse failed after all retries."],
    )


async def analyze_spec_with_llm(
    spec: dict,
    platform_name: str,
    provider: Optional[BaseLLMProvider] = None,
    model: Optional[str] = None,
) -> IntegrationMappingReport:
    if provider is None:
        provider, model = _select_best_provider()
    if model is None:
        model = "gpt-4o-mini"

    summary = _summarize_spec(spec)

    analyze_prompt = ANALYZE_SPEC_PROMPT.format(
        platform_name=platform_name,
        endpoint_count=summary["endpoint_count"],
        schema_count=summary["schema_count"],
        spec_version=summary["spec_version"],
        endpoints_summary=summary["endpoints_summary"],
        schemas_summary=summary["schemas_summary"],
        auth_summary=summary["auth_summary"],
        base_url=summary["base_url"],
    )

    last_error = ""
    for attempt in range(MAX_RETRIES):
        try:
            messages = [
                MessageDTO(
                    role="system",
                    content="You are an e-commerce API integration expert. Return ONLY valid JSON matching the requested schema. No markdown, no explanation.",
                ),
            ]
            if last_error:
                messages.append(
                    MessageDTO(
                        role="user",
                        content=(
                            f"Your previous response failed validation:\n{last_error}\n\n"
                            f"Fix the errors above and return a complete valid JSON matching the schema exactly. "
                            f"Every required field must be present with the correct type.\n\n"
                            f"Original spec:\n{analyze_prompt}"
                        ),
                    )
                )
            else:
                messages.append(MessageDTO(role="user", content=analyze_prompt))

            request = ChatRequest(
                messages=messages,
                model=model,
                json_mode=True,
                temperature=0.1,
                max_tokens=8192,
            )

            response = await provider.structured_output(request, IntegrationMappingReport)
            raw = json.loads(response.message.content)
            report = IntegrationMappingReport(**raw)

            if not report.base_url:
                report.base_url = summary["base_url"]

            feature_gaps = await analyze_feature_gaps(
                entities=report.entities,
                endpoints_summary=summary["endpoints_summary"],
                provider=provider,
                model=model,
            )
            if feature_gaps:
                report.feature_analysis = feature_gaps

            return report

        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as e:
            last_error = f"{type(e).__name__}: {e}"
            logger.warning(
                "LLM response validation failed (attempt %d/%d): %s",
                attempt + 1, MAX_RETRIES, last_error,
            )
            if attempt == MAX_RETRIES - 1:
                logger.error("All %d retries exhausted for agent-parse", MAX_RETRIES)
                return _build_fallback_report(summary, platform_name)
        except Exception as e:
            logger.error("Unexpected error in agent-parse: %s", traceback.format_exc())
            return _build_fallback_report(summary, platform_name)

    return _build_fallback_report(summary, platform_name)


async def analyze_feature_gaps(
    entities: list,
    endpoints_summary: str,
    provider: BaseLLMProvider,
    model: str,
) -> Optional[FeatureAnalysis]:
    try:
        entities_summary = "\n".join(
            f"  {e.entity_type} [{e.display_name}]: list={e.list_path}, detail={e.detail_path}"
            for e in entities
        ) if entities else "  (none discovered)"

        prompt = FEATURE_GAP_PROMPT.format(
            endpoints_summary=endpoints_summary,
            entities_summary=entities_summary,
        )

        request = ChatRequest(
            messages=[
                MessageDTO(role="system", content="You are an e-commerce feature analyst. Return ONLY valid JSON. No markdown."),
                MessageDTO(role="user", content=prompt),
            ],
            model=model,
            json_mode=True,
            temperature=0.1,
            max_tokens=4096,
        )

        response = await provider.structured_output(request, FeatureAnalysis)
        raw = json.loads(response.message.content)
        return FeatureAnalysis(**raw)
    except Exception as e:
        logger.warning("Feature gap analysis failed: %s", e)
        return None


async def create_user_friendly_error(
    error: str,
    platform_name: str,
    spec: Any,
    provider: Optional[BaseLLMProvider] = None,
    model: Optional[str] = None,
) -> str:
    if provider is None:
        provider, model = _select_best_provider()
    if model is None:
        model = "gpt-4o-mini"

    spec_dict = _ensure_dict(spec)
    spec_format = _extract_spec_format(spec)
    summary = _summarize_spec(spec_dict)

    prompt = ERROR_EXPLANATION_PROMPT.format(
        error=error,
        platform_name=platform_name,
        has_endpoints="yes" if summary["endpoint_count"] > 0 else "no",
        has_auth="yes" if summary["auth_summary"].strip() != "(none)" else "no",
        has_schemas="yes" if summary["schema_count"] > 0 else "no",
        spec_format=spec_format,
    )

    request = ChatRequest(
        messages=[
            MessageDTO(role="system", content="You explain technical API integration issues in plain language for non-technical users."),
            MessageDTO(role="user", content=prompt),
        ],
        model=model,
        temperature=0.3,
        max_tokens=512,
    )

    response = await provider.chat(request)
    return response.message.content or "Something went wrong while processing your API specification."


async def detect_store_capabilities(
    report: IntegrationMappingReport,
    store_id: str,
) -> dict[str, bool]:
    unsupported_names = {f.feature_name for f in report.feature_analysis.unsupported_features}

    entity_types = {e.entity_type for e in report.entities}

    capabilities: dict[str, bool] = {
        "has_products": "product" in entity_types,
        "has_orders": "order" in entity_types,
        "has_customers": "customer" in entity_types or "user" in entity_types,
        "has_inventory": "inventory" in entity_types,
        "has_reviews": "review" in entity_types,
        "has_shipments": "shipment" in entity_types or "fulfillment" in entity_types,
        "has_payments": "payment" in entity_types,
        "has_webhooks": "webhook" in entity_types,
        "has_promo_codes": "promo_codes_coupons" not in unsupported_names and any(
            e.entity_type in ("coupon", "discount") for e in report.entities
        ),
        "has_gift_cards": "gift_card" in entity_types,
        "has_discounts": "discount" in entity_types,
        "has_taxes": "tax" in entity_types,
        "has_shipping_zones": "shipping_zone" in entity_types,
        "has_categories": "category" in entity_types or "collection" in entity_types,
        "has_variants": "variant" in entity_types,
        "has_refunds": "refund" in entity_types,
        "has_locations": "location" in entity_types,
        "has_content_management": "blog_post" in entity_types or "page" in entity_types,
        "has_store_settings": "store_setting" in entity_types,
        "has_analytics": "analytics" in entity_types,
        "has_email_marketing": "email_marketing" in entity_types,
        "has_abandoned_cart": "abandoned_cart" in entity_types,
        "has_wishlist": "wishlist" in entity_types,
    }
    return capabilities
