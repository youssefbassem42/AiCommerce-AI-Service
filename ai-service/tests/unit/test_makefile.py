import os

import pytest

MAKEFILE_PATH = "Makefile"


@pytest.mark.unit
class TestMakefile:
    def test_makefile_exists(self):
        assert os.path.exists(MAKEFILE_PATH), "Makefile not found"

    def test_makefile_not_empty(self):
        size = os.path.getsize(MAKEFILE_PATH)
        assert size > 0, "Makefile is empty"

    def test_has_dev_target(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        assert "dev:" in content, "Missing 'dev' target"
        assert "uvicorn" in content, "'dev' should run uvicorn"

    def test_has_test_target(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        assert "test:" in content, "Missing 'test' target"
        assert "pytest" in content, "'test' should run pytest"

    def test_has_lint_target(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        assert "lint:" in content, "Missing 'lint' target"
        assert "ruff" in content, "'lint' should run ruff"

    def test_has_docker_targets(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        assert "docker-build:" in content, "Missing 'docker-build' target"
        assert "docker-up:" in content, "Missing 'docker-up' target"
        assert "docker-down:" in content, "Missing 'docker-down' target"

    def test_has_install_target(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        assert "install:" in content, "Missing 'install' target"

    def test_has_phony_declaration(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        first_line = content.strip().split("\n")[0]
        assert first_line.startswith(".PHONY"), "First line should be .PHONY"

    def test_phony_includes_core_targets(self):
        with open(MAKEFILE_PATH) as f:
            content = f.read()
        phony_line = [l for l in content.split("\n") if l.strip().startswith(".PHONY")]
        assert len(phony_line) > 0, "Missing .PHONY declaration"
        targets = phony_line[0].replace(".PHONY:", "").strip().split()
        for t in ["dev", "test", "lint", "docker-build", "docker-up", "docker-down"]:
            assert t in targets, f"Target {t} not declared .PHONY"
