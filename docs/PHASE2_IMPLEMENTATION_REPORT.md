# Phase 2 Implementation Report — LLM Provider Structured-Output Contract Remediation

**Status: PASS**

**Date:** 2026-08-17

---

## 1. Summary

The `structured_output(request, response_schema)` contract was broken for the
default production provider. Bedrock (SBG gateway) is the default provider;
its `structured_output` raised `NotImplementedError` for **every** caller, and
the other providers only worked "by luck" for the most common schema shape.

The root cause is a schema-type mismatch at the provider boundary: agents pass
`dict[str, Any]` — a `types.GenericAlias`, not a dict — while every provider
branch (`isinstance(response_schema, dict)`, `response_format=response_schema`,
`GenerateContentConfig(response_schema=...)`, `str(response_schema)`) either
rejects it or degrades it to the literal string `"dict[str, typing.Any]"`.

Scope was strictly the provider/schema boundary (Domain 2). No agents, prompts,
LangGraph nodes, routing, integration sync, streaming, retries, default provider
or model were touched, and no dependency was added or upgraded.

## 2. Root Cause

Reproduced locally (no API keys needed):

```
type(dict[str, Any]) == GenericAlias | isinstance(dict[str, Any], dict) == False
BedrockProvider.structured_output(req, dict[str, Any])
  -> NotImplementedError("Bedrock gateway provider supports streaming only")
```

Per provider, `dict[str, Any]` previously behaved as:

| Provider | Old behavior |
|---|---|
| Bedrock (SBG gateway) | `NotImplementedError` — structured output unsupported entirely |
| OpenAI / Azure | `beta.chat.completions.parse(response_format=GenericAlias)` → SDK type error |
| Gemini | GenericAlias passed to `GenerateContentConfig(response_schema=...)` → SDK rejection |
| Claude | `not isinstance(schema_params, dict)` → `ValueError` |
| DeepSeek / Mistral / Ollama / OpenRouter | `str(GenericAlias)` → literal `"dict[str, typing.Any]"` injected into the prompt (degenerate but non-crashing) |
| Mock | passthrough (unaffected) |

Production impact with Bedrock as default: intent classification (coordinator),
support categorization and topic detection, sales extraction, bundle budget
extraction, shopping-state extraction, memory summarization, integration
feature analysis, recommendation intent and mapping analysis all raised
`NotImplementedError` or silently depended on a non-default provider.

## 3. Fixes

### 3.1 Schema normalization layer (new)

`app/infrastructure/providers/schema_utils.py` — the single canonical mapping
for the three caller shapes:

- Pydantic model class → `model_json_schema()` (unchanged behavior);
- JSON-schema dict → passed through as-is;
- `dict[str, Any]` GenericAlias (and any other typing construct) →
  permissive JSON object schema `{"type": "object", "additionalProperties": true}`.

Helpers: `extract_json_schema`, `schema_description` (JSON string for
prompt injection), `schema_name`, `is_pydantic_schema`, `is_generic_alias_schema`,
`is_full_response_format` (distinguishes a complete OpenAI-style
`response_format` from a bare JSON schema).

### 3.2 Bedrock — `structured_output` implemented

`app/infrastructure/providers/bedrock_provider.py`: `structured_output` now
performs the same single-shot gateway POST as `stream()` with the canonical
JSON schema injected into the user prompt, and returns a `ChatResponse` with
`output_text`, usage and latency. The gateway has no native structured mode,
so this matches the exact contract DeepSeek/OpenRouter already use: raw JSON
text returned for callers to parse. The `dict[str, Any]` repro now succeeds
(see §6).

Also added a **bedrock branch to `app/utils/ai_error_handler.py`** (401/403 →
`AuthenticationException`, 429 → `RateLimitException`, timeout/5xx/gateway →
`ProviderUnavailableException`) so gateway HTTP failures map like the other
HTTP-based providers and are retryable by the existing `execute_with_retry`.

### 3.3 OpenAI / Azure — GenericAlias and bare JSON schemas wrapped

`structured_output` now passes Pydantic models natively (unchanged) and wraps
everything else as the documented response format
`{"type": "json_schema", "json_schema": {"name", "schema", "strict": false}}`.
Pre-existing complete formats (`{"type": "json_object"}`) are untouched. This
also fixes the `/api/v1/ai/chat/structured` route contract
(`schema_definition: dict`) which previously sent a bare schema dict as
`response_format`.

### 3.4 Gemini — GenericAlias resolved before the config

`response_schema` is normalized through `extract_json_schema` so
`GenerateContentConfig` always receives a plain dict.

### 3.5 Claude — GenericAlias accepted

The `ValueError` for non-dict schemas is gone; the tool input schema is always
the canonical JSON-schema dict. Default tool name is now the canonical
`"structured_output"` (previously `"structured_output_schema"`); Pydantic
models keep their class name.

### 3.6 DeepSeek / Mistral / Ollama / OpenRouter — real schema instead of `str()`

The `str(response_schema)` fallback was replaced with
`schema_description(response_schema)`, so `dict[str, Any]` now injects
`{"type": "object", "additionalProperties": true}` into the prompt instead of
the literal `"dict[str, typing.Any]"`. Pydantic descriptions are unchanged.

## 4. Provider Compatibility Matrix (after)

| Provider | Pydantic model | JSON-schema dict | `dict[str, Any]` GenericAlias |
|---|---|---|---|
| Bedrock (SBG gateway) | ✅ prompt-schema + parse | ✅ prompt-schema + parse | ✅ permissive prompt-schema |
| OpenAI | ✅ native `parse(model)` | ✅ `json_schema` format | ✅ `json_schema` format |
| Azure OpenAI | ✅ native `parse(model)` | ✅ `json_schema` format | ✅ `json_schema` format |
| Gemini | ✅ `response_schema` | ✅ `response_schema` | ✅ permissive `response_schema` |
| Claude | ✅ tool input_schema | ✅ tool input_schema | ✅ permissive tool input_schema |
| DeepSeek | ✅ prompt-schema | ✅ prompt-schema | ✅ permissive prompt-schema |
| Mistral | ✅ prompt-schema | ✅ prompt-schema | ✅ permissive prompt-schema |
| Ollama | ✅ prompt-schema | ✅ prompt-schema | ✅ permissive prompt-schema |
| OpenRouter | ✅ prompt-schema | ✅ prompt-schema | ✅ permissive prompt-schema |
| Mock | ✅ passthrough | ✅ passthrough | ✅ passthrough |

Embeddings are unchanged: only Gemini provides them (Bedrock has none), per the
current `EMBEDDING_PROVIDER` configuration.

## 5. Files Changed

- `app/infrastructure/providers/schema_utils.py` — **new**, canonical schema normalization
- `app/infrastructure/providers/bedrock_provider.py` — `structured_output` implemented; docstrings
- `app/infrastructure/providers/openai_provider.py` — `response_format` normalization
- `app/infrastructure/providers/azure_provider.py` — `response_format` normalization
- `app/infrastructure/providers/gemini_provider.py` — `extract_json_schema` in config
- `app/infrastructure/providers/claude_provider.py` — GenericAlias accepted; canonical tool name
- `app/infrastructure/providers/deepseek_provider.py` — canonical `schema_description`
- `app/infrastructure/providers/mistral_provider.py` — canonical `schema_description`
- `app/infrastructure/providers/ollama_provider.py` — canonical `schema_description`
- `app/infrastructure/providers/openrouter_provider.py` — canonical `schema_description`
- `app/utils/ai_error_handler.py` — bedrock error mapping branch

No application-layer files were modified. No callers changed.

## 6. Verification

### 6.1 Test baselines

| Suite | Before | After | Delta |
|---|---|---|---|
| `tests/unit` | 1888 passed | 1907 passed | +19 (new tests) |
| `tests/integration` + `tests/e2e` | 145 passed | 145 passed | 0 |
| `ruff check .` | clean | clean | 0 |
| `ruff format --check` | clean | clean | 0 |

New tests (provider-level regression for the exact broken call):

- `tests/unit/modules/ai/test_schema_utils.py` — normalization matrix: Pydantic,
  plain dict, `dict[str, Any]`, `list[str]`, full-response-format detection.
- `tests/unit/modules/ai/test_bedrock_provider.py` — `structured_output` with a
  Pydantic model (schema injected, ChatResponse + usage/cost returned), with
  `dict[str, Any]` (permissive schema injected), non-200 → `ProviderUnavailableException`;
  guardrail test now covers only chat/embeddings/tool_call `NotImplementedError`.
- `tests/unit/modules/ai/test_openai_provider.py` — `dict[str, Any]` and bare
  JSON-schema dict wrapped as `json_schema` response format; `{"type":"json_object"}` untouched.
- `tests/unit/modules/ai/test_azure_provider.py` — `dict[str, Any]` wrapped as `json_schema` format.
- `tests/unit/modules/ai/test_gemini_provider.py` — `dict[str, Any]` → permissive `response_schema`.
- `tests/unit/modules/ai/test_claude_provider.py` — `dict[str, Any]` → permissive
  `input_schema` + canonical tool name/choice.
- `tests/unit/modules/ai/test_deepseek_provider.py` — `dict[str, Any]` → permissive
  schema injected in the prompt.

Reproduction script (pre-fix / post-fix):

```
pre-fix:  BedrockProvider.structured_output(req, dict[str, Any])
          -> NotImplementedError("Bedrock gateway provider supports streaming only")
post-fix: PROMPT includes permissive schema: True
          FIXED -> bedrock | {"intent": "buy", "confidence": 0.9} | tokens: 7
```

### 6.2 Caller verification

All existing callers run their unchanged tests and pass (185 agent tests, plus
application/service suites):

- coordinator `classify_intent` / `classify_internal` (`dict[str, Any]`)
- sales extraction (`dict[str, Any]`)
- bundle budget extraction (`dict[str, Any]`)
- support categorization / topic detection (`dict[str, Any]`)
- memory summarization (`dict[str, Any]`)
- integration feature analysis / mapping report (`FeatureAnalysis`, `IntegrationMappingReport` — Pydantic)
- recommendation intent (`RecommendationIntent` — Pydantic)
- `llm_mapper` (`LLMMappingResult` — Pydantic)
- API route `/api/v1/ai/chat/structured` (`schema_definition: dict` — plain dict)

### 6.3 Domain 1 sanity

No Domain 1 (integration sync) code touched. Atlas still holds the synced store's
data (`5f051250-4caa-4732-8b11-836de4f5a15e`): products 29, categories 11,
customers 51 — Domain 1 intact. (The Phase 1 widget store `3ad1b6e1…` is empty
by design: all its data was deleted at the user's request earlier this session.)

## 7. Architecture & Integration Safety Audit

- `BaseLLMProvider.structured_output` signature unchanged; callers untouched.
- Default provider/model (`DEFAULT_PROVIDER`, `DEFAULT_MODEL`) untouched.
- Embedding path untouched (Gemini remains the embedding provider).
- Streaming/retry machinery untouched (`execute_with_retry` semantics preserved;
  the new bedrock error branch makes gateway 5xx/429 retryable like other providers).
- No new dependencies; no dependency upgrades.
- Prompt-injection providers (DeepSeek/Bedrock/Mistral/Ollama/OpenRouter) still
  return raw text for callers to parse — same contract as before, no parsing
  behavior change, no error swallowing.
- ChatService and provider selection (quota provider_selector) untouched.

## 8. Known Limitations / Deferred Findings

- **Production env-var values are unverifiable from this session** (Railway OAuth
  returns names only). The reported prod default provider is Bedrock
  (per the project owner) with Gemini for embeddings; `DEFAULT_PROVIDER`/`DEFAULT_MODEL`
  values in production were not confirmed independently.
- **Live gateway behavior** (whether SBG models emit markdown-fenced JSON) could
  not be probed without spending SBG budget; the provider returns raw text like
  every other prompt-based provider, and callers own JSON parsing.
- B1/B2/B4/B5/B7/B9/B10/B11 findings from the diagnostics remain **open and
  untouched** (out of Domain 2 scope): retry redundancy, cost/usage consistency,
  provider selection, model availability drift, prompt stability, silent
  fallbacks, and instrumentation gaps.
- Plain-dict `response_format` on OpenAI/Azure was previously invalid at the API
  (`/chat/structured` with OpenAI would 400); now wrapped correctly — behavior
  change is limited to turning a broken call into a working one.
- Claude tool name for non-Pydantic schemas changed from `structured_output_schema`
  to `structured_output`; consumers match on the returned tool block name only
  inside the provider, so nothing external depends on it.

## 9. Verdict

**PASS** — the structured-output contract now holds for all providers for all
three schema shapes, the exact production-failing call
(`BedrockProvider.structured_output(request, dict[str, Any])`) is fixed and
covered by regression tests, the full test suite is green
(1907 unit + 145 integration/e2e), and Domain 1 remains intact.
