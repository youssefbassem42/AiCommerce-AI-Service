import json
import logging
import yaml
from typing import Any, Dict

from app.agents.integration.state import IntegrationMappingState
from app.agents.integration.tools import (
    _ensure_dict,
    _extract_spec_format,
    _select_best_provider,
    analyze_spec_with_llm,
    create_user_friendly_error,
    detect_store_capabilities,
)
from app.infrastructure.providers.base import BaseLLMProvider

logger = logging.getLogger(__name__)


async def parse_spec_node(state: IntegrationMappingState, llm: BaseLLMProvider) -> Dict[str, Any]:
    try:
        raw = state["raw_spec"]
        spec_format = _extract_spec_format(raw)
        parsed = _ensure_dict(raw)

        if not parsed:
            error_msg = "Could not parse the API specification file."
            friendly = await create_user_friendly_error(
                error=error_msg,
                platform_name=state["platform_name"],
                spec=raw,
                provider=llm,
            )
            return {"error": error_msg, "user_friendly_error": friendly, "spec_format": spec_format}

        if "openapi" not in parsed and "swagger" not in parsed:
            error_msg = "This doesn't appear to be a valid OpenAPI or Swagger specification."
            friendly = await create_user_friendly_error(
                error=error_msg,
                platform_name=state["platform_name"],
                spec=raw,
                provider=llm,
            )
            return {"error": error_msg, "user_friendly_error": friendly, "spec_format": spec_format}

        return {
            "parsed_spec": parsed,
            "spec_format": spec_format,
            "error": None,
            "user_friendly_error": None,
        }
    except Exception as e:
        logger.error("Spec parsing failed: %s", e, exc_info=True)
        friendly = await create_user_friendly_error(
            error=str(e),
            platform_name=state["platform_name"],
            spec=state.get("raw_spec", {}),
            provider=llm,
        )
        return {"error": str(e), "user_friendly_error": friendly}


async def analyze_entities_node(state: IntegrationMappingState, llm: BaseLLMProvider, model: str) -> Dict[str, Any]:
    try:
        spec = state.get("parsed_spec")
        if not spec:
            return {"error": "No parsed spec available for analysis."}

        report = await analyze_spec_with_llm(
            spec=spec,
            platform_name=state["platform_name"],
            provider=llm,
            model=model,
        )

        return {"report": report, "error": None}
    except Exception as e:
        logger.error("Entity analysis failed: %s", e, exc_info=True)
        friendly = await create_user_friendly_error(
            error=str(e),
            platform_name=state["platform_name"],
            spec=state.get("raw_spec", {}),
            provider=llm,
        )
        return {"error": str(e), "user_friendly_error": friendly}


async def detect_capabilities_node(state: IntegrationMappingState) -> Dict[str, Any]:
    report = state.get("report")
    if not report:
        return {"capabilities": {}}

    try:
        capabilities = await detect_store_capabilities(report, state["store_id"])
        return {"capabilities": capabilities}
    except Exception as e:
        logger.warning("Capability detection failed: %s", e)
        return {"capabilities": {}}


async def format_error_node(state: IntegrationMappingState) -> Dict[str, Any]:
    error = state.get("error", "Unknown error occurred.")
    friendly = state.get("user_friendly_error") or (
        "We couldn't process your API specification. Please check that the file is a valid OpenAPI or Swagger specification "
        "and try again. If the problem persists, contact support with the details above."
    )
    return {"user_friendly_error": friendly, "error": error}
