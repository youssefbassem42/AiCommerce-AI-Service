import os
from pydantic_settings import BaseSettings


class OpenAISettings(BaseSettings):
    """OpenAI API settings using pydantic-settings."""
    OPEN_AI_API_KEY: str = os.getenv("OPEN_AI_API_KEY", "")
