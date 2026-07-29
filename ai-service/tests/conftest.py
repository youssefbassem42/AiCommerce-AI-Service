import os
import sys
from typing import Any, AsyncGenerator, Dict, List, Optional

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["OPENAI_API_KEY"] = "test-openai-key"
os.environ["AZURE_OPENAI_KEY"] = "test-azure-key"
os.environ["AZURE_ENDPOINT"] = "https://test-endpoint.openai.azure.com"
os.environ["AZURE_DEPLOYMENT"] = "test-deployment"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["CLAUDE_API_KEY"] = "test-claude-key"
os.environ["OLLAMA_URL"] = "http://localhost:11434"
os.environ["DEEPSEEK_API_KEY"] = "test-deepseek-key"
os.environ["MISTRAL_API_KEY"] = "test-mistral-key"
os.environ["DEFAULT_PROVIDER"] = "openai"
os.environ["DEFAULT_MODEL"] = "gpt-4o-mini"
os.environ["REQUEST_TIMEOUT"] = "30.0"
os.environ["MAX_RETRIES"] = "1"


@pytest.fixture
def mock_provider():
    provider = AsyncMock()
    provider.chat = AsyncMock()
    provider.stream = AsyncMock()
    provider.embeddings = AsyncMock()
    provider.health_check = AsyncMock()
    provider.list_models = AsyncMock()
    provider.structured_output = AsyncMock()
    provider.tool_call = AsyncMock()
    return provider


@pytest.fixture
def mock_factory(mock_provider):
    factory = MagicMock()
    factory.get_provider.return_value = mock_provider
    return factory
