import os
import pytest

ENV_EXAMPLE_PATH = ".env.example"
ENV_PATH = ".env"


@pytest.mark.unit
class TestEnvExample:
    def test_env_example_exists(self):
        assert os.path.exists(ENV_EXAMPLE_PATH), ".env.example not found"

    def test_env_example_not_empty(self):
        size = os.path.getsize(ENV_EXAMPLE_PATH)
        assert size > 0, ".env.example is empty"

    def test_env_example_has_required_vars(self):
        with open(ENV_EXAMPLE_PATH) as f:
            content = f.read()
        required = [
            "OPENAI_API_KEY", "GEMINI_API_KEY", "CLAUDE_API_KEY",
            "DEEPSEEK_API_KEY", "MISTRAL_API_KEY", "OPENROUTER_API_KEY",
            "JWT_SECRET_KEY", "MONGO_URI", "MONGO_DB",
            "REDIS_URL", "QDRANT_URL",
            "DEFAULT_PROVIDER", "DEFAULT_MODEL",
        ]
        for var in required:
            assert var + "=" in content, f"Missing required var: {var}"

    def test_env_example_has_no_live_keys(self):
        with open(ENV_EXAMPLE_PATH) as f:
            content = f.read()
        suspicious_patterns = ["sk-", "AQ.", "sg-"]
        for pattern in suspicious_patterns:
            lines = [l for l in content.split("\n") if pattern in l and "=" in l]
            for line in lines:
                _, val = line.split("=", 1)
                if val.strip():
                    pytest.fail(f"Possible live key in .env.example: {line}")

    def test_env_gitignored(self):
        gitignore_path = os.path.join(os.path.dirname(ENV_EXAMPLE_PATH), ".gitignore")
        with open(gitignore_path) as f:
            content = f.read()
        lines = [l.strip() for l in content.split("\n")]
        assert ".env" in lines or ".env" in content, \
            ".env should be in .gitignore"


@pytest.mark.unit
class TestGitignore:
    def test_gitignore_has_common_patterns(self):
        gitignore_path = os.path.join(os.path.dirname(ENV_EXAMPLE_PATH), ".gitignore")
        with open(gitignore_path) as f:
            content = f.read()
        patterns = ["__pycache__", ".venv", ".env",
                     ".vscode", ".DS_Store"]
        for pat in patterns:
            assert pat in content, f".gitignore missing pattern: {pat}"
