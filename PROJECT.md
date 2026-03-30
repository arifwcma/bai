# UniChat — University Data Assistant

## Overview

Build "UniChat" — a university data assistant chatbot over the OULAD dataset in PostgreSQL, progressing through 5 phases to gain hands-on experience with text-to-SQL, RAG, vector databases, MCP, LoRA fine-tuning, and predictive ML integration. All local using Ollama + PostgreSQL + Python.

## Background

The developer has a PhD in machine learning, strong deep learning fundamentals (NumPy, PyTorch), but limited exposure to real-world AI application development. This project is designed as a structured hands-on learning experience covering the modern AI application stack: tool use, RAG, vector databases, MCP, LoRA, and predictive model integration.

## Dataset

**Open University Learning Analytics Dataset (OULAD)**

- Source: https://analyse.kmi.open.ac.uk/open_dataset
- ~32,000 students, ~22 courses, ~170 assessments, 10M+ VLE interaction records
- Tables: `studentInfo`, `courses`, `studentRegistration`, `assessments`, `studentAssessment`, `studentVle`, `vle`
- Format: CSV files to be loaded into PostgreSQL

## Tech Stack

- **LLM runtime:** Ollama (local, models like `llama3.1`, `deepseek-coder-v2`, `mistral`)
- **Embedding model:** Ollama (`nomic-embed-text` or similar)
- **Relational DB:** PostgreSQL (already installed)
- **Vector DB:** ChromaDB (pure Python, no admin needed) — fallback from pgvector
- **Language:** Python
- **LoRA tooling:** HuggingFace `peft` + `transformers` (Phase 4)
- **MCP:** Python `mcp` package

## Architecture Mental Model

```
LLM = reasoning/orchestration layer (Ollama)
SQL DB = structured truth (PostgreSQL + OULAD)
Vector DB = unstructured memory/retrieval (ChromaDB)
MCP/tools = standardized action interface
LoRA = optional weight adaptation
Predictive ML = separate model for risk scoring
```

The LLM does NOT memorize database contents. It uses tools (SQL, retrieval) at runtime.

## Phases

### Phase 1 — Text-to-SQL Chatbot (No Training)

**Goal:** Build a working chatbot that answers natural language questions by generating and executing SQL.

**Key concepts:** Tool use, prompt engineering, schema injection, "Level 1: no weight update"

**Steps:**

1. Download OULAD CSV files
2. Design and create PostgreSQL schema, load data
3. Pull a suitable Ollama model (`llama3.1` or similar with tool calling support)
4. Build Python app:
   - System prompt with schema description
   - LLM generates SQL from natural language
   - Execute SQL read-only against PostgreSQL
   - Feed results back to LLM for natural English explanation
5. Add query classification (SQL question vs. general question)
6. Add safety guardrails (read-only, query validation)
7. Test with questions like:
   - "How many students are registered in module AAA 2013J?"
   - "What is the average score for TMA assessments?"
   - "Which modules have the highest withdrawal rate?"
   - "List students who scored below 40 on their first assessment"

### Phase 2 — RAG + Vector Database

**Goal:** Add document-grounded answers for unstructured knowledge alongside SQL for structured data.

**Key concepts:** RAG pipeline, embeddings, vector search, query routing

**Steps:**

1. Gather/create unstructured documents (Open University module descriptions, assessment policies, grading rules, FAQ-style content)
2. Chunk documents, generate embeddings via Ollama (`nomic-embed-text`)
3. Store embeddings in ChromaDB
4. Build retrieval pipeline: query -> embed -> vector search -> top-k chunks -> LLM context
5. Add query router: SQL path vs. RAG path vs. hybrid
6. Test with questions like:
   - "What is the passing threshold for a module?"
   - "How does the credit weighting system work?"
   - "Can a student retake an exam?"

### Phase 3 — MCP Integration

**Goal:** Expose SQL and RAG tools as MCP servers, connect to MCP clients.

**Key concepts:** MCP protocol, tool exposure, standardized LLM-tool communication

**Steps:**

1. Build MCP server in Python wrapping: `run_sql(query)`, `get_schema()`, `search_documents(query)`
2. Connect to an MCP client (Cursor IDE or custom)
3. Test end-to-end through MCP protocol
4. Understand how MCP standardizes what was previously custom tool-calling code

### Phase 4 — LoRA Fine-Tuning

**Goal:** Adapt model weights to improve SQL generation accuracy for this specific schema.

**Key concepts:** LoRA, weight adaptation, training data creation, before/after evaluation

**Steps:**

1. Create dataset of ~200-500 examples: (natural language question, schema context, correct SQL)
2. Set up LoRA training using HuggingFace `peft` + `transformers`
3. Fine-tune a small model (e.g., `codellama-7b` or similar)
4. Evaluate: compare SQL accuracy before vs. after LoRA
5. Swap LoRA-adapted model into the chatbot
6. Understand at the weight level: which layers are adapted, rank, alpha, what changes

**Note:** This phase may require moving to another machine if Windows build tools are unavailable.

### Phase 5 — Predictive Model + LLM Explanation

**Goal:** Train a traditional ML model for student risk prediction and integrate it with the chatbot.

**Key concepts:** Full integration pattern — separate ML model + LLM orchestration/explanation

**Steps:**

1. Feature engineering from OULAD data (VLE clicks, assessment scores, registration timing, demographics)
2. Train XGBoost/random forest for dropout/failure risk prediction
3. Store predictions back in PostgreSQL
4. Extend chatbot to query and explain risk predictions
5. Test with: "Which students are most at risk of failing module BBB?"

## Project Structure

```
bai/
  PROJECT.md          — this file
  .gitignore          — git ignore rules
  requirements.txt    — Python dependencies
  data/               — OULAD CSV files (git-ignored)
  sql/                — schema creation and data loading scripts
  src/
    phase1/           — text-to-SQL chatbot
    phase2/           — RAG + vector DB additions
    phase3/           — MCP servers
    phase4/           — LoRA fine-tuning
    phase5/           — predictive model integration
  docs/               — synthesized university policy documents (for RAG)
```

## Key Design Decisions

- **ChromaDB over pgvector** — avoids admin access requirement for PostgreSQL extension installation
- **Python MCP servers over Node.js** — avoids Node.js dependency
- **HuggingFace peft over unsloth** — better Windows compatibility with pre-built wheels
- **Ollama over cloud APIs** — free, local, full control, no API keys needed
- **OULAD dataset** — real educational data, perfect match for university chatbot scenario, freely available

## Status Log

| Date | Status |
|------|--------|
| 2026-03-30 | Project initialized. Starting Phase 1. |
