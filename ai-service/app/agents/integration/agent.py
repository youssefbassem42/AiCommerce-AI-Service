import logging
import time
from typing import Any

from langgraph.graph import END, StateGraph

from app.agents.integration.nodes import (
    analyze_entities_node,
    detect_capabilities_node,
    format_error_node,
    parse_spec_node,
)
from app.agents.integration.schemas import IntegrationMappingReport
from app.agents.integration.state import IntegrationMappingState
from app.core.ai_settings import ai_settings
from app.core.model_registry import ModelRegistry
from app.infrastructure.providers.base import BaseLLMProvider
from app.infrastructure.providers.factory import LLMProviderFactory

logger = logging.getLogger(__name__)


async def _select_best_model() -> tuple[BaseLLMProvider, str]:
    factory = LLMProviderFactory()
    preferred = [
        ("openrouter", "openai/gpt-4o-mini"),
        ("ollama", "llama3"),
        ("deepseek", "deepseek-chat"),
        ("openai", "gpt-4o-mini"),
    ]
    for provider_name, model_name in preferred:
        try:
            info = ModelRegistry.get_model_info(model_name)
            if info and info.capabilities.json_mode:
                provider = factory.get_provider(provider_name)
                health = await provider.health_check()
                if health.status == "healthy":
                    return provider, model_name
        except Exception:
            continue
    return factory.get_provider(ai_settings.DEFAULT_PROVIDER), ai_settings.DEFAULT_MODEL


def route_after_parse(state: IntegrationMappingState) -> str:
    if state.get("error"):
        return "format_error"
    return "analyze_entities"


def route_after_analysis(state: IntegrationMappingState) -> str:
    if state.get("error"):
        return "format_error"
    return "detect_capabilities"


def route_after_capabilities(state: IntegrationMappingState) -> str:
    return END


class IntegrationMappingAgent:
    def __init__(self, llm: BaseLLMProvider | None = None, model: str | None = None):
        self._llm = llm
        self._model = model
        self._graph: StateGraph | None = None

    def _build_graph(self) -> StateGraph:
        workflow = StateGraph(IntegrationMappingState)

        workflow.add_node("parse_spec", self._wrap(parse_spec_node))
        workflow.add_node("analyze_entities", self._wrap_analysis(analyze_entities_node))
        workflow.add_node("detect_capabilities", self._wrap(detect_capabilities_node))
        workflow.add_node("format_error", self._wrap(format_error_node))

        workflow.set_entry_point("parse_spec")

        workflow.add_conditional_edges(
            "parse_spec",
            route_after_parse,
            {"analyze_entities": "analyze_entities", "format_error": "format_error"},
        )
        workflow.add_conditional_edges(
            "analyze_entities",
            route_after_analysis,
            {"detect_capabilities": "detect_capabilities", "format_error": "format_error"},
        )
        workflow.add_conditional_edges(
            "detect_capabilities",
            route_after_capabilities,
            {END: END},
        )
        workflow.add_edge("format_error", END)

        return workflow.compile()

    def _wrap(self, node_fn):
        async def wrapped(state: IntegrationMappingState) -> dict[str, Any]:
            extra = {}
            if node_fn == parse_spec_node:
                extra["llm"] = self._llm
            elif node_fn in (detect_capabilities_node, format_error_node):
                pass
            return await node_fn(state, **extra)

        return wrapped

    def _wrap_analysis(self, node_fn):
        async def wrapped(state: IntegrationMappingState) -> dict[str, Any]:
            return await node_fn(state, llm=self._llm, model=self._model)

        return wrapped

    async def analyze(
        self, raw_spec: Any, platform_name: str, store_id: str, organization_id: str
    ) -> tuple[IntegrationMappingReport | None, str | None, dict | None]:
        start = time.perf_counter()

        if self._llm is None:
            self._llm, self._model = await _select_best_model()
        if self._graph is None:
            self._graph = self._build_graph()

        initial_state: IntegrationMappingState = {
            "raw_spec": raw_spec,
            "platform_name": platform_name,
            "store_id": store_id,
            "organization_id": organization_id,
            "spec_format": "unknown",
            "parsed_spec": None,
            "report": None,
            "capabilities": None,
            "error": None,
            "user_friendly_error": None,
            "connection_id": None,
        }

        result = await self._graph.ainvoke(initial_state)

        latency = (time.perf_counter() - start) * 1000
        logger.info("Integration mapping agent completed in %.0fms", latency)

        report = result.get("report")
        error = result.get("error")
        user_error = result.get("user_friendly_error")
        capabilities = result.get("capabilities")

        if error and not report:
            logger.warning("Agent failed: %s", error)

        return report, user_error or error, capabilities
