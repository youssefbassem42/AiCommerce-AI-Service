from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class ModelCapabilities(BaseModel):
    vision: bool = False
    json_mode: bool = False
    tool_calling: bool = False
    streaming: bool = True
    embedding: bool = False

class ModelPricing(BaseModel):
    prompt_cost_per_1m: float = 0.0
    completion_cost_per_1m: float = 0.0

class ModelInfo(BaseModel):
    name: str
    provider: str
    capabilities: ModelCapabilities
    context_length: int
    pricing: ModelPricing

class ModelRegistry:
    # Class-level registry of supported models
    _registry: Dict[str, ModelInfo] = {
        # OpenAI Models
        "gpt-4o": ModelInfo(
            name="gpt-4o",
            provider="openai",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=5.00, completion_cost_per_1m=15.00)
        ),
        "gpt-4o-mini": ModelInfo(
            name="gpt-4o-mini",
            provider="openai",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=0.150, completion_cost_per_1m=0.600)
        ),
        "o1-mini": ModelInfo(
            name="o1-mini",
            provider="openai",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=False, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=3.00, completion_cost_per_1m=12.00)
        ),
        "text-embedding-3-small": ModelInfo(
            name="text-embedding-3-small",
            provider="openai",
            capabilities=ModelCapabilities(embedding=True, streaming=False),
            context_length=8191,
            pricing=ModelPricing(prompt_cost_per_1m=0.02, completion_cost_per_1m=0.0)
        ),
        "text-embedding-3-large": ModelInfo(
            name="text-embedding-3-large",
            provider="openai",
            capabilities=ModelCapabilities(embedding=True, streaming=False),
            context_length=8191,
            pricing=ModelPricing(prompt_cost_per_1m=0.13, completion_cost_per_1m=0.0)
        ),

        # Azure OpenAI Models (Mapped to OpenAI model definitions)
        "azure/gpt-4o": ModelInfo(
            name="gpt-4o",
            provider="azure",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=5.00, completion_cost_per_1m=15.00)
        ),
        "azure/gpt-4o-mini": ModelInfo(
            name="gpt-4o-mini",
            provider="azure",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=0.150, completion_cost_per_1m=0.600)
        ),

        # Google Gemini Models
        "gemini-2.5-flash": ModelInfo(
            name="gemini-2.5-flash",
            provider="gemini",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=1048576,
            pricing=ModelPricing(prompt_cost_per_1m=0.075, completion_cost_per_1m=0.30)
        ),
        "gemini-flash-lite-latest": ModelInfo(
            name="gemini-flash-lite-latest",
            provider="gemini",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=1048576,
            pricing=ModelPricing(prompt_cost_per_1m=0.075, completion_cost_per_1m=0.30)
        ),
        "gemini-2.5-pro": ModelInfo(
            name="gemini-2.5-pro",
            provider="gemini",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=2097152,
            pricing=ModelPricing(prompt_cost_per_1m=1.25, completion_cost_per_1m=5.00)
        ),
        "gemini-2.0-flash": ModelInfo(
            name="gemini-2.0-flash",
            provider="gemini",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=1048576,
            pricing=ModelPricing(prompt_cost_per_1m=0.075, completion_cost_per_1m=0.30)
        ),
        "gemini-flash-latest-flash": ModelInfo(
            name="gemini-flash-latest-flash",
            provider="gemini",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=1048576,
            pricing=ModelPricing(prompt_cost_per_1m=0.075, completion_cost_per_1m=0.30)
        ),
        "gemini-flash-latest-pro": ModelInfo(
            name="gemini-flash-latest-pro",
            provider="gemini",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=2097152,
            pricing=ModelPricing(prompt_cost_per_1m=1.25, completion_cost_per_1m=5.00)
        ),
        "gemini-embedding-001": ModelInfo(
            name="gemini-embedding-001",
            provider="gemini",
            capabilities=ModelCapabilities(embedding=True, streaming=False),
            context_length=3072,
            pricing=ModelPricing(prompt_cost_per_1m=0.025, completion_cost_per_1m=0.0)
        ),

        # Anthropic Claude Models
        "claude-3-5-sonnet-latest": ModelInfo(
            name="claude-3-5-sonnet-latest",
            provider="claude",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=200000,
            pricing=ModelPricing(prompt_cost_per_1m=3.00, completion_cost_per_1m=15.00)
        ),
        "claude-3-5-haiku-latest": ModelInfo(
            name="claude-3-5-haiku-latest",
            provider="claude",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=True, streaming=True),
            context_length=200000,
            pricing=ModelPricing(prompt_cost_per_1m=0.80, completion_cost_per_1m=4.00)
        ),
        "claude-3-opus-latest": ModelInfo(
            name="claude-3-opus-latest",
            provider="claude",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=200000,
            pricing=ModelPricing(prompt_cost_per_1m=15.00, completion_cost_per_1m=75.00)
        ),

        # OpenRouter Models (routed through openrouter.ai)
        "openai/gpt-4o-mini": ModelInfo(
            name="openai/gpt-4o-mini",
            provider="openrouter",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=0.150, completion_cost_per_1m=0.600)
        ),
        "openai/gpt-4o": ModelInfo(
            name="openai/gpt-4o",
            provider="openrouter",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=2.50, completion_cost_per_1m=10.00)
        ),
        "google/gemini-2.0-flash-001": ModelInfo(
            name="google/gemini-2.0-flash-001",
            provider="openrouter",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=1048576,
            pricing=ModelPricing(prompt_cost_per_1m=0.10, completion_cost_per_1m=0.40)
        ),
        "anthropic/claude-3-5-haiku": ModelInfo(
            name="anthropic/claude-3-5-haiku",
            provider="openrouter",
            capabilities=ModelCapabilities(vision=True, json_mode=True, tool_calling=True, streaming=True),
            context_length=200000,
            pricing=ModelPricing(prompt_cost_per_1m=0.80, completion_cost_per_1m=4.00)
        ),
        "mistralai/mistral-small-3.1-24b-instruct": ModelInfo(
            name="mistralai/mistral-small-3.1-24b-instruct",
            provider="openrouter",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=0.0, completion_cost_per_1m=0.0)
        ),

        # DeepSeek Models
        "deepseek-chat": ModelInfo(
            name="deepseek-chat",
            provider="deepseek",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=True, streaming=True),
            context_length=64000,
            pricing=ModelPricing(prompt_cost_per_1m=0.14, completion_cost_per_1m=0.28)
        ),
        "deepseek-reasoner": ModelInfo(
            name="deepseek-reasoner",
            provider="deepseek",
            capabilities=ModelCapabilities(vision=False, json_mode=False, tool_calling=False, streaming=True),
            context_length=64000,
            pricing=ModelPricing(prompt_cost_per_1m=0.55, completion_cost_per_1m=2.19)
        ),

        # Mistral Models
        "mistral-large-latest": ModelInfo(
            name="mistral-large-latest",
            provider="mistral",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=True, streaming=True),
            context_length=128000,
            pricing=ModelPricing(prompt_cost_per_1m=2.00, completion_cost_per_1m=6.00)
        ),
        "open-mixtral-8x22b": ModelInfo(
            name="open-mixtral-8x22b",
            provider="mistral",
            capabilities=ModelCapabilities(vision=False, json_mode=False, tool_calling=True, streaming=True),
            context_length=64000,
            pricing=ModelPricing(prompt_cost_per_1m=2.00, completion_cost_per_1m=6.00)
        ),
        "mistral-embed": ModelInfo(
            name="mistral-embed",
            provider="mistral",
            capabilities=ModelCapabilities(embedding=True, streaming=False),
            context_length=8192,
            pricing=ModelPricing(prompt_cost_per_1m=0.10, completion_cost_per_1m=0.0)
        ),

        # Ollama Models (Default local capabilities, pricing is $0.0 because it is hosted locally)
        "llama3": ModelInfo(
            name="llama3",
            provider="ollama",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=True, streaming=True),
            context_length=8192,
            pricing=ModelPricing(prompt_cost_per_1m=0.0, completion_cost_per_1m=0.0)
        ),
        "mistral": ModelInfo(
            name="mistral",
            provider="ollama",
            capabilities=ModelCapabilities(vision=False, json_mode=True, tool_calling=True, streaming=True),
            context_length=8192,
            pricing=ModelPricing(prompt_cost_per_1m=0.0, completion_cost_per_1m=0.0)
        ),
        "nomic-embed-text": ModelInfo(
            name="nomic-embed-text",
            provider="ollama",
            capabilities=ModelCapabilities(embedding=True, streaming=False),
            context_length=8192,
            pricing=ModelPricing(prompt_cost_per_1m=0.0, completion_cost_per_1m=0.0)
        )
    }

    @classmethod
    def get_model_info(cls, model_name: str) -> Optional[ModelInfo]:
        return cls._registry.get(model_name)

    @classmethod
    def list_models_by_provider(cls, provider: str) -> List[ModelInfo]:
        return [info for info in cls._registry.values() if info.provider == provider]

    @classmethod
    def list_all_models(cls) -> List[ModelInfo]:
        return list(cls._registry.values())
