# UniChat — GitHub Activity Assistant

## Overview

Build a GitHub activity assistant chatbot that can answer natural language questions about GitHub events by generating SQL, retrieve information from documentation via RAG, expose tools via MCP, and optionally improve with LoRA fine-tuning. Start with a static snapshot of GH Archive data; later connect to the live GitHub API.

All local using Ollama + PostgreSQL + Python.

## Purpose

**Primary:** Learn real-world AI application development hands-on — tool use, RAG, vector databases, MCP, LoRA, and predictive ML integration.

**Secondary:** Build a useful GitHub analytics assistant.

## Dataset

**GH Archive** — https://www.gharchive.org/

- Records the entire public GitHub timeline as hourly JSON archives
- 15+ event types: PushEvent, PullRequestEvent, IssuesEvent, WatchEvent (stars), ForkEvent, CreateEvent, IssueCommentEvent, ReleaseEvent, etc.
- Each event contains: actor (user), repo, org, timestamp, and a type-specific payload
- Available from 2011 to present, updated hourly
- We start with a snapshot (a few hours/days), later connect to live GitHub API

## Tech Stack

- **LLM runtime:** Ollama (local, models like `llama3.1`, `deepseek-coder-v2`, `mistral`)
- **Embedding model:** Ollama (`nomic-embed-text` or similar)
- **Relational DB:** PostgreSQL (already installed)
- **Vector DB:** ChromaDB (pure Python, no admin needed)
- **Language:** Python
- **LoRA tooling:** HuggingFace `peft` + `transformers` (Phase 4)
- **MCP:** Python `mcp` package
- **Live API (later):** GitHub REST API via personal access token

## Architecture Mental Model

```
LLM = reasoning/orchestration layer (Ollama)
SQL DB = structured truth (PostgreSQL + GH Archive snapshot)
Vector DB = unstructured memory/retrieval (ChromaDB)
MCP/tools = standardized action interface
LoRA = optional weight adaptation
Predictive ML = separate model for predictions
Live API = real-time GitHub data (future)
```

The LLM does NOT memorize database contents. It uses tools (SQL, retrieval) at runtime.

## Database Schema

Normalized from raw GH Archive JSON events into relational tables:

```
actors          — GitHub users (id, login, avatar_url)
repos           — repositories (id, name)
orgs            — organizations (id, login)
events          — main event table (id, type, actor_id, repo_id, org_id, created_at)
push_events     — commits pushed (ref, size, distinct_size)
pull_request_events — PR opened/closed/merged (action, title, state, merged, additions, deletions)
issue_events    — issues opened/closed (action, title, state, labels)
issue_comment_events — comments on issues/PRs (action, body)
watch_events    — stars (action = "started")
fork_events     — forks (fork_id, fork_full_name)
create_events   — branches/tags/repos created (ref_type, ref)
release_events  — releases published (action, tag_name, release_name)
```

## Phases

### Phase 1 — Text-to-SQL Chatbot (No Training)

**Goal:** Build a working chatbot that answers natural language questions about GitHub activity by generating and executing SQL.

**Key concepts:** Tool use, prompt engineering, schema injection, "Level 1: no weight update"

**Steps:**

1. Download GH Archive hourly JSON files (start with ~3 hours, ~500K-1M events)
2. Create PostgreSQL database `ghchat` with normalized schema
3. Parse JSON and load into PostgreSQL tables
4. Pull a suitable Ollama model (`llama3.1` or similar with tool calling)
5. Build Python chatbot:
   - System prompt with schema description
   - LLM generates SQL from natural language
   - Execute SQL read-only against PostgreSQL
   - Feed results back to LLM for natural English explanation
6. Add safety guardrails (read-only, query validation)
7. Test with questions like:
   - "Which repos got the most stars today?"
   - "Top 10 users by number of push events"
   - "How many PRs were merged vs closed without merging?"
   - "Which programming-related repos had the most forks?"
   - "What's the average number of commits per push?"
   - "Show me the most active organizations"

### Phase 2 — RAG + Vector Database

**Goal:** Add document-grounded answers for unstructured knowledge alongside SQL for structured data.

**Key concepts:** RAG pipeline, embeddings, vector search, query routing

**Steps:**

1. Gather/create unstructured documents (GitHub Docs: how PRs work, what forks mean, open source licensing, contribution guidelines, GitHub Actions docs, etc.)
2. Chunk documents, generate embeddings via Ollama (`nomic-embed-text`)
3. Store embeddings in ChromaDB
4. Build retrieval pipeline: query -> embed -> vector search -> top-k chunks -> LLM context
5. Add query router: SQL path vs. RAG path vs. hybrid
6. Test with questions like:
   - "What's the difference between a fork and a clone?"
   - "How do GitHub Actions workflows work?"
   - "What license should I use for my open source project?"

### Phase 3 — MCP Integration

**Goal:** Expose SQL and RAG tools as MCP servers, connect to MCP clients.

**Key concepts:** MCP protocol, tool exposure, standardized LLM-tool communication

**Steps:**

1. Build MCP server in Python wrapping: `run_sql(query)`, `get_schema()`, `search_documents(query)`
2. Add live GitHub API tools: `get_repo(owner, name)`, `search_repos(query)`, `get_user(login)`
3. Connect to an MCP client (Cursor IDE or custom)
4. Test end-to-end through MCP protocol — combining static DB data with live API calls

### Phase 4 — LoRA Fine-Tuning

**Goal:** Adapt model weights to improve SQL generation accuracy for this specific schema.

**Key concepts:** LoRA, weight adaptation, training data creation, before/after evaluation

**Steps:**

1. Create dataset of ~200-500 examples: (natural language question, schema context, correct SQL)
2. Set up LoRA training using HuggingFace `peft` + `transformers`
3. Fine-tune a small model (e.g., `codellama-7b` or similar)
4. Evaluate: compare SQL accuracy before vs. after LoRA
5. Swap LoRA-adapted model into the chatbot

**Note:** This phase may require moving to another machine if Windows build tools are unavailable.

### Phase 5 — Predictive Model + LLM Explanation

**Goal:** Train a traditional ML model for predictions and integrate it with the chatbot.

**Key concepts:** Full integration pattern — separate ML model + LLM orchestration/explanation

**Steps:**

1. Feature engineering from GH Archive data (event patterns, timing, repo characteristics)
2. Train model for predictions like: will a PR get merged? repo star growth? issue resolution time?
3. Store predictions back in PostgreSQL
4. Extend chatbot to query and explain predictions
5. Test with: "Which open PRs in repo X are most likely to be merged?"

### Phase 6 (Bonus) — Live Data Connection

**Goal:** Connect the static snapshot system to live GitHub data.

**Steps:**

1. Add scheduled GH Archive ingestion (download latest hours, parse, load)
2. Connect GitHub REST API for real-time queries via MCP
3. Compare live API results with historical DB analysis

## Project Structure

```
bai/
  PROJECT.md          — this file (project plan, progress, decisions)
  .gitignore          — git ignore rules
  requirements.txt    — Python dependencies
  data/               — GH Archive JSON files (git-ignored)
  sql/                — schema creation and data loading scripts
  src/
    phase1/           — text-to-SQL chatbot
    phase2/           — RAG + vector DB additions
    phase3/           — MCP servers
    phase4/           — LoRA fine-tuning
    phase5/           — predictive model integration
  docs/               — GitHub documentation for RAG (Phase 2)
```

## Key Design Decisions

- **GH Archive over other datasets** — continuously updated, globally interesting, rich relational structure, live API available for later phases
- **ChromaDB over pgvector** — avoids admin access requirement for PostgreSQL extension installation
- **Python MCP servers over Node.js** — avoids Node.js dependency
- **HuggingFace peft over unsloth** — better Windows compatibility with pre-built wheels
- **Ollama over cloud APIs** — free, local, full control, no API keys needed
- **Start with snapshot, go live later** — learn with static data first, add real-time as a final phase

## Status Log

| Date | Status |
|------|--------|
| 2026-03-30 | Project initialized. Chose GitHub/GH Archive as dataset. Starting Phase 1 Step 1: data download and schema setup. |
