import os
from unittest.mock import patch

import pytest

from app.core.config import Settings, REQUIRED_SECRETS, AI_PROVIDER_KEYS


class TestSettings:
    def test_default_project_name(self):
        s = Settings()
        assert s.PROJECT_NAME == "AI Commerce Platform"

    def test_cors_defaults_to_all(self):
        s = Settings()
        assert s.CORS_ORIGINS == ["*"]

    def test_has_all_sub_settings(self):
        s = Settings()
        assert s.MONGO_SETTINGS is not None
        assert s.OPEN_AI_SETTINGS is not None
        assert s.QDRANT_SETTINGS is not None
        assert s.REDIS_SETTINGS is not None

    def test_validate_required_returns_warnings_when_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            s = Settings()
            warnings = s.validate_required()
            jwt_warnings = [w for w in warnings if "JWT_SECRET_KEY" in w]
            assert len(jwt_warnings) == 1

    def test_validate_required_no_warnings_when_set(self):
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
            "OPENAI_API_KEY": "sk-test-key",
        }, clear=True):
            s = Settings()
            warnings = s.validate_required()
            assert len(warnings) == 0

    def test_validate_required_warns_when_no_ai_key(self):
        with patch.dict(os.environ, {
            "JWT_SECRET_KEY": "test-secret-key-that-is-long-enough-for-hs256",
        }, clear=True):
            s = Settings()
            warnings = s.validate_required()
            ai_warnings = [w for w in warnings if "AI provider" in w]
            assert len(ai_warnings) == 1

    def test_validate_required_accepts_any_provider_key(self):
        providers = ["OPENAI_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY",
                      "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY"]
        for key in providers:
            with patch.dict(os.environ, {
                "JWT_SECRET_KEY": "test-secret",
                key: "some-api-key",
            }, clear=True):
                s = Settings()
                warnings = s.validate_required()
                assert len([w for w in warnings if "AI provider" in w]) == 0, \
                    f"Failed for {key}"

    def test_required_secrets_defined(self):
        assert len(REQUIRED_SECRETS) >= 1
        names = [r[0] for r in REQUIRED_SECRETS]
        assert "JWT_SECRET_KEY" in names

    def test_ai_provider_keys_defined(self):
        assert len(AI_PROVIDER_KEYS) >= 6
        providers = dict(AI_PROVIDER_KEYS)
        assert "OPENAI_API_KEY" in providers
        assert "GEMINI_API_KEY" in providers
        assert "OPENROUTER_API_KEY" in providers
