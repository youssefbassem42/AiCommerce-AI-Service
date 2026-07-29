import logging
from typing import Dict, Any, Union
from app.core.model_registry import ModelRegistry

logger = logging.getLogger("ai_service")

# Try importing tiktoken, fallback to basic estimator if it fails
try:
    import tiktoken
except ImportError:
    tiktoken = None  # type: ignore

def calculate_tokens(text: str, model_name: str = "gpt-4o") -> int:
    """
    Calculate the number of tokens in a text string.
    Uses tiktoken for OpenAI/Azure/DeepSeek models and falls back to character/word-based estimation for others.
    """
    if not text:
        return 0

    model_info = ModelRegistry.get_model_info(model_name)
    provider = model_info.provider if model_info else ""

    # If it is OpenAI/Azure/DeepSeek, use tiktoken if available
    if tiktoken and provider in ["openai", "azure", "deepseek"]:
        try:
            # We map model names to tiktoken encodings
            encoding_name = "cl100k_base"
            if "gpt-4" in model_name or "gpt-3.5" in model_name:
                encoding_name = "cl100k_base"
            elif "o1" in model_name:
                encoding_name = "cl100k_base"
            
            encoding = tiktoken.get_encoding(encoding_name)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Error tokenizing with tiktoken: {e}. Falling back to estimation.")
    
    # Fallback/estimate for Gemini, Claude, Ollama, Mistral or if tiktoken failed
    # Standard estimate: ~4 characters per token
    return max(1, int(len(text) / 4))


def calculate_cost(prompt_tokens: int, completion_tokens: int, model_name: str) -> float:
    """
    Calculate cost in USD based on prompt and completion token counts and model pricing.
    """
    model_info = ModelRegistry.get_model_info(model_name)
    if not model_info:
        return 0.0

    prompt_cost = (prompt_tokens / 1_000_000.0) * model_info.pricing.prompt_cost_per_1m
    completion_cost = (completion_tokens / 1_000_000.0) * model_info.pricing.completion_cost_per_1m
    return prompt_cost + completion_cost


def estimate_price(text: str, is_completion: bool, model_name: str) -> float:
    """
    Estimate price in USD for a given text input before sending it to a provider.
    """
    tokens = calculate_tokens(text, model_name)
    model_info = ModelRegistry.get_model_info(model_name)
    if not model_info:
        return 0.0

    cost_per_1m = (
        model_info.pricing.completion_cost_per_1m
        if is_completion
        else model_info.pricing.prompt_cost_per_1m
    )
    return (tokens / 1_000_000.0) * cost_per_1m
