from app.utils.token_utils import calculate_tokens, calculate_cost, estimate_price
from app.core.model_registry import ModelRegistry

def test_calculate_tokens():
    text = "Hello world! This is a token calculation test."
    # Since tiktoken is installed, it should return > 0
    tokens = calculate_tokens(text, "gpt-4o")
    assert tokens > 0
    
    # Fallback to len(text)/4 for Gemini
    tokens_gemini = calculate_tokens(text, "gemini-2.5-flash")
    assert tokens_gemini == len(text) // 4


def test_calculate_cost():
    # gpt-4o price: prompt = $5/1M, completion = $15/1M
    prompt_tokens = 100_000
    completion_tokens = 50_000
    
    expected_cost = (100_000 / 1_000_000.0 * 5.0) + (50_000 / 1_000_000.0 * 15.0)
    cost = calculate_cost(prompt_tokens, completion_tokens, "gpt-4o")
    assert cost == expected_cost


def test_estimate_price():
    text = "Hello world!"
    price = estimate_price(text, is_completion=False, model_name="gpt-4o")
    assert price > 0.0
