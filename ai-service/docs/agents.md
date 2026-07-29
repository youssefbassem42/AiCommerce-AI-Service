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
| Coordinator | 📝 Phase 01 | Intent classification + routing |
| Memory | 📝 Phase 01 | Cross-session context persistence |
| Sales | 📝 Phase 02 | Conversational sales funnel |
| Support | 📝 Phase 02 | Customer issue resolution |
| Escalation | 📝 Phase 02 | Human handoff when AI can't resolve |
| Marketing | 📝 Phase 03 | Campaign creation and management |
| Analytics | 📝 Phase 03 | Natural-language business intelligence |
| Planner | 📝 Phase 06 | Multi-step task decomposition |

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
