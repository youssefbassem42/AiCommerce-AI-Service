import os
import pytest


DOCKERFILE_PATH = "Dockerfile"
COMPOSE_PATH = "docker-compose.yml"


@pytest.mark.unit
class TestDockerfile:
    def test_dockerfile_exists(self):
        assert os.path.exists(DOCKERFILE_PATH), "Dockerfile not found"

    def test_dockerfile_not_empty(self):
        size = os.path.getsize(DOCKERFILE_PATH)
        assert size > 0, "Dockerfile is empty"

    def test_dockerfile_has_python_base(self):
        with open(DOCKERFILE_PATH) as f:
            content = f.read()
        assert "python:" in content, "Dockerfile must use python base image"
        assert "3.12" in content, "Dockerfile must use Python 3.12"

    def test_dockerfile_multi_stage(self):
        with open(DOCKERFILE_PATH) as f:
            content = f.read()
        assert "AS builder" in content, "Dockerfile should have a builder stage"
        assert "AS runtime" in content, "Dockerfile should have a runtime stage"

    def test_dockerfile_exposes_port(self):
        with open(DOCKERFILE_PATH) as f:
            content = f.read()
        assert "EXPOSE" in content and "8000" in content, \
            "Dockerfile must EXPOSE port 8000"

    def test_dockerfile_has_healthcheck(self):
        with open(DOCKERFILE_PATH) as f:
            content = f.read()
        assert "HEALTHCHECK" in content, "Dockerfile must have HEALTHCHECK"
        assert "curl" in content, "HEALTHCHECK should use curl"

    def test_dockerfile_cmd_runs_uvicorn(self):
        with open(DOCKERFILE_PATH) as f:
            content = f.read()
        assert "uvicorn" in content, "CMD must run uvicorn"
        assert "app.main:app" in content, "Must point to app.main:app"


@pytest.mark.unit
class TestDockerCompose:
    def test_compose_exists(self):
        assert os.path.exists(COMPOSE_PATH), "docker-compose.yml not found"

    def test_compose_not_empty(self):
        size = os.path.getsize(COMPOSE_PATH)
        assert size > 0, "docker-compose.yml is empty"

    def test_required_services(self):
        import yaml
        with open(COMPOSE_PATH) as f:
            config = yaml.safe_load(f)
        services = config.get("services", {})
        required = ["ai-service", "celery-worker", "celery-beat",
                     "mongodb", "redis", "qdrant"]
        for svc in required:
            assert svc in services, f"Missing required service: {svc}"

    def test_ai_service_has_build(self):
        import yaml
        with open(COMPOSE_PATH) as f:
            config = yaml.safe_load(f)
        ai = config["services"]["ai-service"]
        assert "build" in ai, "ai-service must have build config"
        assert ai["build"] == ".", "build context should be current dir"

    def test_ai_service_exposes_port(self):
        import yaml
        with open(COMPOSE_PATH) as f:
            config = yaml.safe_load(f)
        ports = config["services"]["ai-service"].get("ports", [])
        assert any("8000" in p for p in ports), "ai-service must expose port 8000"

    def test_shared_env_variables(self):
        import yaml
        with open(COMPOSE_PATH) as f:
            config = yaml.safe_load(f)
        x_shared = config.get("x-shared-env", {})
        critical = ["MONGO_URI", "REDIS_URL", "QDRANT_URL",
                     "JWT_SECRET_KEY", "OPENAI_API_KEY"]
        for var in critical:
            assert var in x_shared, f"Missing shared env var: {var}"

    def test_volumes_defined(self):
        import yaml
        with open(COMPOSE_PATH) as f:
            config = yaml.safe_load(f)
        volumes = config.get("volumes", {})
        required = ["mongo_data", "redis_data", "qdrant_storage"]
        for vol in required:
            assert vol in volumes, f"Missing required volume: {vol}"

    def test_mongodb_has_healthcheck(self):
        import yaml
        with open(COMPOSE_PATH) as f:
            config = yaml.safe_load(f)
        mongo = config["services"]["mongodb"]
        assert "healthcheck" in mongo, "mongodb should have healthcheck"
