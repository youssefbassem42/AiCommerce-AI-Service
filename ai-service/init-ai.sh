#!/bin/bash

# ==============================================================================
# AI Commerce Platform - Project Initialization Script
# ==============================================================================
# This script generates the complete folder structure and boilerplate files
# for a production-ready AI Commerce Platform utilizing FastAPI, DDD, CQRS,
# Vertical Slice Architecture, LangGraph Agents, RAG, and an EDA pattern.
#
# Constraints & Guidelines:
# - Avoids duplicated code using reusable helper functions.
# - Uses ANSI colors for status logging.
# - Validates commands and environment before execution.
# - Exits immediately on any errors (set -euo pipefail).
# - Never overwrites existing files.
# ==============================================================================

set -euo pipefail

# ANSI Color Codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Progress & Status Loggers
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Command Validation
log_info "Validating environment and required tools..."
for cmd in mkdir touch; do
    if ! command -v "$cmd" &> /dev/null; then
        log_error "Required system command '$cmd' is missing. Please install it and try again."
        exit 1
    fi
done
log_success "Environment validation passed."

# Helper functions to avoid duplication and prevent overwriting
create_dir() {
    local dir_path="$1"
    if [ ! -d "$dir_path" ]; then
        mkdir -p "$dir_path"
        log_success "Created directory: $dir_path"
    else
        log_warn "Directory already exists, skipping: $dir_path"
    fi
}

create_file() {
    local file_path="$1"
    if [ ! -f "$file_path" ]; then
        # Ensure parent directory exists
        local parent_dir
        parent_dir=$(dirname "$file_path")
        if [ ! -d "$parent_dir" ]; then
            mkdir -p "$parent_dir"
        fi
        touch "$file_path"
        log_success "Created file: $file_path"
    else
        log_warn "File already exists, skipping: $file_path"
    fi
}

# ==============================================================================
# 1. TOP-LEVEL STRUCTURE & CONFIGURATION FILES
# ==============================================================================
log_info "Initializing top-level directories..."
create_dir "app"
create_dir "docs"
create_dir "scripts"
create_dir "tests"
create_dir "logs"
create_dir "data"
create_dir "models"
create_dir "qdrant_storage"

log_info "Initializing root-level configuration files..."
create_file "Dockerfile"
create_file "docker-compose.yml"
create_file "README.md"
create_file ".env"
create_file ".env.example"
create_file ".gitignore"
create_file "pyproject.toml"
create_file "Makefile"
create_file "poetry.lock"

# ==============================================================================
# 2. CORE APP INITIALIZATION
# ==============================================================================
log_info "Creating core application packages..."
create_file "app/__init__.py"
create_file "app/main.py"

# ==============================================================================
# 3. API FEATURE ROUTING
# ==============================================================================
log_info "Creating API layer with feature-based routing..."
create_file "app/api/__init__.py"

for feature in conversation recommendation knowledge analytics marketing ticket chat auth admin health webhooks ingestion; do
    create_dir "app/api/$feature"
    create_file "app/api/$feature/__init__.py"
    create_file "app/api/$feature/router.py"
    create_file "app/api/$feature/schemas.py"
    create_file "app/api/$feature/dependencies.py"
done

# ==============================================================================
# 4. APPLICATION LAYER (CQRS + DDD CONTEXTS)
# ==============================================================================
log_info "Creating Application layer bounded contexts..."
create_file "app/application/__init__.py"

for context in conversation knowledge recommendation analytics marketing ticket; do
    create_dir "app/application/$context"
    create_file "app/application/$context/__init__.py"
    
    # Subdirectories for clean CQRS separation
    for sub in commands queries dto validators mappers interfaces; do
        create_dir "app/application/$context/$sub"
        create_file "app/application/$context/$sub/__init__.py"
    done
    
    # Command-specific files
    create_file "app/application/$context/commands/command.py"
    create_file "app/application/$context/commands/handler.py"
    create_file "app/application/$context/commands/validator.py"
    
    # Query-specific files
    create_file "app/application/$context/queries/query.py"
    create_file "app/application/$context/queries/handler.py"
done

# ==============================================================================
# 5. DOMAIN LAYER (AGGREGATES, ENTITIES & DOMAIN SERVICES)
# ==============================================================================
log_info "Creating Domain layer bounded contexts..."
create_file "app/domain/__init__.py"

for context in conversation knowledge recommendation analytics marketing ticket customer shared; do
    create_dir "app/domain/$context"
    create_file "app/domain/$context/__init__.py"
    
    for sub in entities value_objects events repositories services; do
        create_dir "app/domain/$context/$sub"
        create_file "app/domain/$context/$sub/__init__.py"
    done
    
    create_file "app/domain/$context/exceptions.py"
done

# ==============================================================================
# 6. INFRASTRUCTURE LAYER
# ==============================================================================
log_info "Creating Infrastructure components..."
create_file "app/infrastructure/__init__.py"

for infra in mongodb sqlserver redis qdrant repositories cache queue providers llm security config logging; do
    create_dir "app/infrastructure/$infra"
    create_file "app/infrastructure/$infra/__init__.py"
done

# 6.1 MongoDB Setup
log_info "Configuring MongoDB collections, mappers, and repositories..."
create_file "app/infrastructure/mongodb/client.py"
create_file "app/infrastructure/mongodb/collections.py"
create_file "app/infrastructure/mongodb/indexes.py"
create_file "app/infrastructure/mongodb/validators.py"

# MongoDB Subdirectories
create_dir "app/infrastructure/mongodb/documents"
create_file "app/infrastructure/mongodb/documents/__init__.py"

create_dir "app/infrastructure/mongodb/mappers"
create_file "app/infrastructure/mongodb/mappers/__init__.py"

create_dir "app/infrastructure/mongodb/repositories"
create_file "app/infrastructure/mongodb/repositories/__init__.py"

# MongoDB Documents
for doc in conversation message knowledge knowledge_chunk runtime_log prompt_history recommendation bundle campaign dashboard ticket; do
    create_file "app/infrastructure/mongodb/documents/${doc}_document.py"
done

# MongoDB Repositories
for repo in conversation knowledge recommendation analytics marketing ticket; do
    create_file "app/infrastructure/mongodb/repositories/${repo}_repository.py"
done

# MongoDB Mappers
for mapper in conversation knowledge recommendation; do
    create_file "app/infrastructure/mongodb/mappers/${mapper}_mapper.py"
done

# 6.2 LLM Providers Setup
log_info "Creating Multi-LLM provider components..."
for provider in base openai_provider azure_provider claude_provider gemini_provider deepseek_provider mistral_provider ollama_provider; do
    create_file "app/infrastructure/providers/${provider}.py"
done

# ==============================================================================
# 7. SHARED KERNEL & CQRS UTILITIES
# ==============================================================================
log_info "Creating Shared Kernel components..."
create_file "app/shared/__init__.py"

for sub in kernel cqrs mediator events responses pagination exceptions utils; do
    create_dir "app/shared/$sub"
    create_file "app/shared/$sub/__init__.py"
done

# Shared Kernel Domain Base Classes
create_file "app/shared/kernel/entity.py"
create_file "app/shared/kernel/aggregate_root.py"
create_file "app/shared/kernel/domain_event.py"

# Shared CQRS Core abstractions
create_file "app/shared/cqrs/command.py"
create_file "app/shared/cqrs/query.py"
create_file "app/shared/cqrs/command_handler.py"
create_file "app/shared/cqrs/query_handler.py"

# Shared Mediator Pattern
create_file "app/shared/mediator/mediator.py"

# ==============================================================================
# 8. RAG PIPELINE
# ==============================================================================
log_info "Creating RAG architectural components..."
create_file "app/rag/__init__.py"

for sub in loaders parsers chunking embeddings vectorstore retrievers rerankers prompts pipeline indexing; do
    create_dir "app/rag/$sub"
    create_file "app/rag/$sub/__init__.py"
done

# ==============================================================================
# 9. AI AGENTS (LANGCHAIN / CUSTOM AGENT SYSTEM)
# ==============================================================================
log_info "Creating AI Agents (stateful/node-based architecture)..."
create_file "app/agents/__init__.py"

for agent in coordinator sales support recommendation marketing analytics memory planner escalation; do
    create_dir "app/agents/$agent"
    create_file "app/agents/$agent/__init__.py"
    create_file "app/agents/$agent/agent.py"
    create_file "app/agents/$agent/state.py"
    create_file "app/agents/$agent/nodes.py"
    create_file "app/agents/$agent/prompts.py"
done

# ==============================================================================
# 10. LANGGRAPH WORKFLOWS
# ==============================================================================
log_info "Creating LangGraph orchestration workflows..."
create_file "app/workflows/__init__.py"

for flow in conversation sales support marketing analytics recommendation; do
    create_dir "app/workflows/$flow"
    create_file "app/workflows/$flow/__init__.py"
    create_file "app/workflows/$flow/graph.py"
    create_file "app/workflows/$flow/state.py"
done

# ==============================================================================
# 11. CELERY WORKERS
# ==============================================================================
log_info "Creating Celery background tasks & workers..."
create_file "app/workers/__init__.py"

for worker in embedding ingestion analytics summarization cleanup recommendation campaigns scheduler; do
    create_dir "app/workers/$worker"
    create_file "app/workers/$worker/__init__.py"
    create_file "app/workers/$worker/tasks.py"
done

# ==============================================================================
# 12. MIDDLEWARE, CORE, DB & UTILS
# ==============================================================================
log_info "Creating middleware, database connectivity, and utilities..."

# Middleware
create_dir "app/middleware"
create_file "app/middleware/__init__.py"
create_file "app/middleware/auth.py"
create_file "app/middleware/logging.py"
create_file "app/middleware/rate_limit.py"

# Core Settings & Config
create_dir "app/core"
create_file "app/core/__init__.py"
create_file "app/core/config.py"
create_file "app/core/security.py"
create_file "app/core/exceptions.py"
create_file "app/core/constants.py"
create_file "app/core/dependencies.py"

# Database Connections
create_dir "app/db"
create_file "app/db/__init__.py"
create_file "app/db/mongodb.py"
create_file "app/db/sqlserver.py"
create_file "app/db/redis.py"
create_file "app/db/qdrant.py"

# Utils
create_dir "app/utils"
create_file "app/utils/__init__.py"
create_file "app/utils/helpers.py"
create_file "app/utils/logger.py"

# ==============================================================================
# 13. SCRIPTS, TESTS, DOCUMENTATION & STORAGE
# ==============================================================================
log_info "Creating system administration scripts..."
create_file "scripts/load_documents.py"
create_file "scripts/create_embeddings.py"
create_file "scripts/reindex.py"
create_file "scripts/seed_prompts.py"

log_info "Creating testing suite structure..."
create_file "tests/__init__.py"
for suite in unit integration e2e fixtures factories; do
    create_dir "tests/$suite"
    create_file "tests/$suite/__init__.py"
done

# Mirror production structure in test suites
for folder in api application domain infrastructure agents workflows rag workers; do
    create_dir "tests/unit/$folder"
    create_file "tests/unit/$folder/__init__.py"
    create_dir "tests/integration/$folder"
    create_file "tests/integration/$folder/__init__.py"
done

log_info "Creating Markdown documentation..."
create_file "docs/architecture.md"
create_file "docs/api.md"
create_file "docs/rag.md"
create_file "docs/agents.md"
create_file "docs/deployment.md"
create_file "docs/security.md"
create_file "docs/database.md"

log_info "Configuring runtime directories..."
create_file "logs/.gitkeep"

create_dir "data/documents"
create_file "data/documents/.gitkeep"
create_dir "data/uploads"
create_file "data/uploads/.gitkeep"
create_dir "data/temp"
create_file "data/temp/.gitkeep"

create_file "models/.gitkeep"
create_file "qdrant_storage/.gitkeep"

# ==============================================================================
# EXECUTION SUMMARY
# ==============================================================================
echo ""
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}AI Commerce Project Created Successfully  ${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""

if command -v tree &> /dev/null; then
    tree .
else
    find .
fi