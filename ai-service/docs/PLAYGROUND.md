# RAG Playground — Usage Guide

## Overview

The RAG Playground (`scripts/rag_playground.py`) validates the complete tenant-aware knowledge pipeline end-to-end. It demonstrates tenant isolation, knowledge sync, context building, prompt assembly, and chat completion.

## Prerequisites

- MongoDB running on `localhost:27017`
- Qdrant running on `localhost:6333` (optional — steps without it are skipped)
- Gemini API key configured in environment (or `.env`)
- PDF documents in per-store directories

## Store-Specific Documents

Place documents in store-specific directories:

```
resources/stores/
├── electronics/
│   └── salla_file.pdf            # Salla e-commerce terms
├── fashion/
│   └── amazon-business-faq.pdf   # Amazon Business FAQ
└── pharmacy/                     # (add your own files)
```

## Running

```bash
# Activate virtual environment
source .venv/bin/activate

# Run for electronics store (Salla document)
python scripts/rag_playground.py --store electronics

# Run for fashion store (Amazon Business document)
python scripts/rag_playground.py --store fashion

# Run for pharmacy store (custom document)
python scripts/rag_playground.py --store pharmacy

# Run with default env-based store
python scripts/rag_playground.py
```

## Pipeline Steps

| Step | Name | Description |
|---|---|---|
| — | Tenant Resolution | Resolves `--store` to TenantContext |
| STEP 0 | Knowledge Sync Coordinator | Detects changes, bumps version if needed |
| STEP 1 | Load PDFs | Finds PDFs in store-specific directory |
| STEP 2 | Document Processing | Extracts text, metadata, page count |
| STEP 3 | Chunking | Splits documents into chunks |
| STEP 4 | Embedding Generation | Creates vector embeddings |
| STEP 5 | Vector Store Insertion | Upserts to Qdrant collection |
| STEP 6 | Business Summary | Generates structured business context |
| STEP 7 | Semantic Search | Tests retrieval queries |
| STEP 8 | RAG Prompt Construction | Builds prompt from context |
| STEP 9 | Chat Completion | Calls LLM and displays response |
| STEP 11 | Tenant Resolution Display | Shows resolved tenant details |
| STEP 12 | Active Knowledge Version | Shows current version info |
| STEP 13 | Context Builder | Loads summary + chunks + version |
| STEP 14 | Prompt Builder | Assembles and displays full prompt |
| STEP 15 | Chat Completion with Display | Full response with metrics |

## Tenant Isolation Verification

Run both stores with the same question and observe different answers:

```bash
python scripts/rag_playground.py --store electronics
# → Answers about Salla e-commerce platform

python scripts/rag_playground.py --store fashion
# → Answers about Amazon Business
```

Each store:
- Has its own MongoDB documents (`store_id` scoped)
- Has its own Qdrant collection (`kb_{slug}`)
- Has its own knowledge version history
- Has its own business summary
- Never sees another store's data

## Screenshots

Recorded terminal outputs are saved in `resources/testing/screenshots/`:

| File | Content |
|---|---|
| `electronics_run.txt` | Full output for `--store electronics` |
| `fashion_run.txt` | Full output for `--store fashion` |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `RAG_PLAYGROUND_DEBUG` | `false` | Enable verbose object dumps |
| `RAG_STORE_ID` | `playground-store` | Default store ID |
| `RAG_ORG_ID` | `playground-org` | Default organization ID |
| `RAG_LLM_PROVIDER` | `gemini` | LLM provider name |
| `RAG_LLM_MODEL` | `gemini-2.5-flash` | Model for chat completion |
