.PHONY: dev test lint typecheck docker-build docker-up docker-down clean install eval

dev:
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	pytest tests/ -v --cov=app --cov-report=term-missing

test-unit:
	pytest tests/unit -v

test-integration:
	pytest tests/integration -v

test-e2e:
	pytest tests/e2e -v

eval:
	pytest tests/eval -v -m eval

lint:
	ruff check . --fix
	ruff format . --check

lint-fix:
	ruff check . --fix
	ruff format .

typecheck:
	pyright app/

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .ruff_cache

install:
	pip install -e ".[dev]"
