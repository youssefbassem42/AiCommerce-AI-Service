# Agents

LangGraph-based autonomous agents that encapsulate domain-specific business logic.

## Architecture

Each agent follows a consistent structure:

```
agents/<agent_name>/
├── agent.py      # LangGraph StateGraph definition + entry point
├── nodes.py      # Individual graph node functions
├── prompts.py    # LLM system/user prompts
├── state.py      # TypedDict state schema
└── tools.py      # Tool functions callable by the LLM
```

## Implemented Agents

| Agent | Status | Purpose |
|-------|--------|---------|
| Bundle | ✅ | Product bundling recommendations |
| Integration | ✅ | E-commerce platform integration setup |
| Recommendation | ✅ | Product recommendation engine |
| Coordinator | ✅ | Intent classification + routing to sub-agents |
| Memory | ✅ | Cross-session context persistence (Mongo MemoryRepository, TTL) |
| Support | ✅ | Customer issue resolution (LangGraph: verify → categorize → facts → resolve → escalate) |
| Escalation | ✅ | Human handoff when AI can't resolve (explicit request, business rule, repeated failure, strong frustration, knowledge unavailable) |
| Sales | 📝 Phase 02 | Conversational sales funnel |
| Marketing | 📝 Phase 03 | Campaign creation and management |
| Analytics | 📝 Phase 03 | Natural-language business intelligence |
| Planner | 📝 Phase 06 | Multi-step task decomposition |

## Coordinator (Phase 01)

`app/agents/coordinator/` routes user messages to the right sub-agent:

- `extract_context` → loads recent history from the DDD conversation store and
  extracts structured context (topics, preferences, sentiment)
- `classify_intent` → LLM intent classification (sales, support, bundle,
  recommendation, marketing, analytics, escalation, integration, general)
- `route_to_agent` → selects the target sub-agent
- `execute_sub_agent` → runs the routed agent (`bundle`, `recommendation`)
- `handle_fallback` → graceful fallback: static integration guidance,
  "coming soon" for Phase 02+ intents, or a clarifying question

## Memory Agent (Phase 01)

`app/agents/memory/` persists and recalls context with TTL support:

- `store` / `recall` / `forget` / `summarize` actions
- Session-scoped memory in Redis (`session:{session_id}:memory` hash, TTL)
- User-scoped memory in Mongo (`user_memories` collection via `MemoryRepository`)
- Recall priority: current session → user profile → store defaults

## Conversation Workflow (Phase 01)

`app/workflows/conversation/` is the top-level loop used by `/api/v1/ai/chat`:

- `validate_input` → `route_to_agent` (coordinator) → `execute_agent` (sub-agent
  or general LLM chat) → `format_response` → `update_memory` → `check_continuation`
- Clarification loops continue across HTTP requests via the persisted conversation
- Wired through `OrchestrationService` in `app/application/services/orchestration_service.py`

## Adding a New Agent

1. Create `app/agents/<name>/` with the 5 files above
2. Implement `state.py` with the agent's TypedDict
3. Implement `nodes.py` with pure functions (each takes state, returns state updates)
4. Implement `prompts.py` with system prompt templates
5. Implement `tools.py` with any external tools the agent needs
6. Implement `agent.py` — build a `StateGraph`, compile it, export `async def run(state)`
7. Register the agent in the coordinator's routing table

## Conventions

- Nodes are pure functions — no side effects outside tool calls
- State is immutable — each node returns a dict of state updates
- Tools are async functions decorated with `@tool`
- Prompts use Jinja2 templating for dynamic content

## Guardrails

- Provider credentials are required: agents fail loudly at construction when
  an API key is missing or set to `mock-key` (`KeyManager.require_provider_api_key`).
- Retrieved knowledge is treated as untrusted data: directive-style content is
  redacted before prompting (`app/utils/content_guard.py`), prompt boundaries
  mark fact blocks as untrusted, and instructional docs are flagged at chunk time.
- All agent stores are tenant-scoped; store-tagged resources are never read or
  written across stores.
