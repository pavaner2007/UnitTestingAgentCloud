# AutoQA Agent

> **AI-powered repository analysis, code intelligence, and interactive Q&A — all in one system.**

AutoQA Agent accepts any public GitHub repository URL, clones it locally, runs an 11-agent analysis pipeline, and produces a rich structured report covering tech stack, API inventory, dependency graphs, bug detection, module summaries, and AI-generated architectural insights. A built-in RAG chat lets you ask questions about the code in plain English.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Agent Pipeline — How It Works](#agent-pipeline--how-it-works)
  - [Stage 1 — RepositoryAnalysisAgent](#stage-1--repositoryanalysisagent)
  - [Stage 2 — TechStackDetectionAgent](#stage-2--techstackdetectionagent)
  - [Stage 3 — ApiDiscoveryAgent](#stage-3--apidiscoveryagent)
  - [Stage 4 — FilePrioritizationAgent](#stage-4--fileprioritizationagent)
  - [Stage 5 — CodeChunkingAgent](#stage-5--codechunkingagent)
  - [Stage 6 — PatternDetector](#stage-6--patterndetector)
  - [Stage 7 — BugDetectionAgent](#stage-7--bugdetectionagent)
  - [Stage 8 — DependencyGraphAgent](#stage-8--dependencygraphagent)
  - [Stage 9 — CodeAnalysisAgent (Orchestrator)](#stage-9--codeanalysisagent-orchestrator)
  - [Stage 10 — ReportGenerationAgent](#stage-10--reportgenerationagent)
  - [Stage 11 — QAChatAgent](#stage-11--qachatagent)
- [LLM Architecture](#llm-architecture)
- [Groq Safety Boundary](#groq-safety-boundary)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [Prerequisites](#prerequisites)
- [Setup Guide](#setup-guide)
  - [Backend](#backend)
  - [Frontend](#frontend)
  - [PostgreSQL](#postgresql)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [Frontend UI Panels](#frontend-ui-panels)
- [Example Report](#example-report)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER  (React Frontend)                            │
│                 Submits GitHub URL  ·  Views report  ·  Chats               │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              │ POST /analyze-repository
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    FastAPI  ·  routes.py  ·  analysis_service.py            │
│                         (Pipeline Orchestrator)                             │
└──┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬───────┘
   │          │          │          │          │          │          │
   ▼          ▼          ▼          ▼          ▼          ▼          ▼
[Stage 1]  [Stage 2]  [Stage 3]  [Stage 9]  [Stage 10] [Ollama]  [Groq API]
 Repo       Tech       API        Code       Report      llama3   llama-3.1
 Clone      Stack      Disc.      Analysis   Gen.       qwen2.5  8b-instant
 Agent      Agent      Agent      Agent      Agent
                                  │
               ┌──────────────────┼──────────────────────┐
               ▼                  ▼                       ▼
           [Stage 4]          [Stage 5]              [Stage 6+7+8]
           File               Code                   Pattern +
           Prioritize         Chunk                  Bug +
           Agent              Agent                  Dep Graph
                                                     Agents
                                  │
                                  ▼
                        [PostgreSQL  +  chunk_embeddings]
                                  │
                      ┌───────────┘
                      ▼
                  [Stage 11]
                  QAChatAgent
                  (RAG: Pinned → Semantic → Targeted)
                      │
                      ▼
                  Groq  (answer)
```

---

## Agent Pipeline — How It Works

The full pipeline executes in the order below. Stages 4–8 all run **inside** the `CodeAnalysisAgent` (Stage 9 orchestrates them). Stages 1–3 and 10 are independent.

---

### Stage 1 — `RepositoryAnalysisAgent`

**File:** `backend/app/agents/repository_analysis_agent.py`

**What it does:**
- Validates that the submitted URL matches `https://github.com/owner/repo`.
- Shallow-clones the repository (`depth=1`) via GitPython into `WORKSPACE_DIR/`.
- If the folder already exists from a prior run, it is wiped and re-cloned.
- Extracts metadata: default branch, latest commit SHA, total file/directory count, top-level items, and important config files (`requirements.txt`, `package.json`, `Dockerfile`, etc.).

**Output:** `RepositoryMetadata` dataclass — passed to every downstream stage.

---

### Stage 2 — `TechStackDetectionAgent`

**File:** `backend/app/agents/tech_stack_agent.py`

**What it does:**
- Fully deterministic — **zero LLM calls**.
- Inspects file extensions (`.py`, `.js`, `.java`, …) to detect languages.
- Parses `package.json` (JS dependencies) to identify React, Next.js, Angular, Vue, Express.js, and database clients.
- Parses `requirements.txt`, `pyproject.toml`, `Pipfile` to identify FastAPI, Django, Flask, SQLAlchemy, and database drivers.
- Inspects `pom.xml` / `build.gradle` for Spring Boot.
- Text-searches source files for database mentions: PostgreSQL, MongoDB, MySQL.
- Records **evidence** (which file triggered each detection) for UI display.

**Output:** `TechStackResponse` — `{frontend, backend, languages, databases, frameworks, package_managers, raw_evidence}`

---

### Stage 3 — `ApiDiscoveryAgent`

**File:** `backend/app/agents/api_discovery_agent.py`

**What it does:**
- Fully deterministic — **zero LLM calls**.
- Scans source files using regex patterns tuned for each web framework:
  - **FastAPI**: `@router.get(...)`, `@app.post(...)`, etc.
  - **Flask**: `@app.route(...)`, `@blueprint.get(...)`
  - **Django**: `path(...)`, `re_path(...)` in `urls.py`
  - **Express.js**: `app.get(...)`, `router.post(...)`, `app.use(...)`
  - **Spring Boot**: `@GetMapping`, `@PostMapping`, `@RequestMapping`
- Extracts method, path, framework, file, and line number for each endpoint.

**Output:** `list[ApiEndpoint]` — the full API inventory shown in the UI.

---

### Stage 4 — `FilePrioritizationAgent`

**File:** `backend/app/agents/file_prioritization_agent.py`

**What it does:**
- Fully deterministic — **zero LLM calls**.
- Ranks every repository file by architectural importance using a scoring model:

  | Score | Criterion |
  |---|---|
  | +50 | Known entry-point filename (`main.py`, `app.py`, `server.js`, `index.ts`, …) |
  | +40 | File is in a directory that contains API routes (from Stage 3) |
  | +30 | Architecturally significant directory (`models/`, `services/`, `db/`, `controllers/`, …) |
  | +15 | Test file (`test_*.py`, `*.spec.ts`) |
  | +5  | Config file (`.yaml`, `.toml`, `Makefile`) |
  | 0   | Everything else |
  | Excluded | `node_modules/`, `.git/`, `vendor/`, `dist/`, lockfiles, binaries, files > 1 MB |

- Applies two hard budget caps from `.env`: `MAX_FILES_TO_ANALYZE` (default 50) and `MAX_CODE_TOKEN_BUDGET` (default 40,000 characters). Files exceeding the budget are tagged `excluded_token_budget` and skipped, so their skip reason still appears in the report.
- Provides route-file hints from the API inventory for the +40 boost.

**Output:** `PrioritizationResult` — selected files + per-file skip reason codes.

---

### Stage 5 — `CodeChunkingAgent`

**File:** `backend/app/agents/code_chunking_agent.py`

**What it does:**
- Splits each prioritized source file into **semantic chunks** (functions and classes), not fixed-size token windows.
- Uses **tree-sitter** grammars (via `tree-sitter-languages`) for precise AST-based boundary detection.

  | Language | Grammar |
  |---|---|
  | Python | `function_definition`, `class_definition` |
  | JavaScript / TypeScript / TSX | `function_declaration`, `arrow_function`, `class_declaration`, `method_definition` |
  | Go | `function_declaration`, `method_declaration` |
  | Java | `method_declaration`, `class_declaration`, `constructor_declaration` |
  | C / C++ | `function_definition`, `class_specifier` |
  | Ruby | `method`, `class` |
  | Rust | `function_item`, `impl_item` |

- **Fallback**: If tree-sitter has no grammar for a language, the file is split into character-count chunks (max `CODE_CHUNK_MAX_CHARS` chars, default 3,000). Trivial chunks (< 5 lines, pure imports) are skipped.

**Output:** `list[CodeChunk]` — each chunk carries `file_path`, `chunk_type`, `name`, `content`, `start_line`, `end_line`.

---

### Stage 6 — `PatternDetector`

**File:** `backend/app/agents/pattern_detector.py`

**What it does:**
- Fully deterministic, regex-based — **zero LLM calls**.
- Scans all chunks for architecturally notable patterns:

  | Pattern | What It Detects |
  |---|---|
  | **JWT auth** | `jwt`, `decode_token`, `verify_token`, `@login_required` |
  | **Raw SQL** | `cursor.execute(...)`, f-string SQL queries |
  | **External API calls** | `requests.get/post`, `httpx`, `fetch(`, `axios` |
  | **Env / secrets** | `os.environ`, `process.env`, `dotenv` |
  | **Subprocess / exec** | `subprocess.`, `os.system`, `exec()`, `eval()` |
  | **File I/O** | `open(`, `fs.readFile`, `fs.writeFile` |
  | **Hardcoded secrets** | API-key-shaped string literals assigned to variables (HIGH severity) |
  | **TODO / FIXME** | `# TODO`, `# FIXME`, `# HACK` developer comments |

- Output is a `list[str]` of human-readable descriptions with file context, e.g. `"JWT auth in backend/app/api/routes.py"`.
- These `notable_patterns` are one of only two fields forwarded to Groq (the other being `module_summaries`).

**Output:** `list[str]` — `notable_patterns` field of `CodeInsights`.

---

### Stage 7 — `BugDetectionAgent`

**File:** `backend/app/agents/bug_detection_agent.py`

**What it does:**
- Fully deterministic static analysis — **zero LLM calls**.
- Two detection tiers:

  **Tier 1 — Ruff (Python only, optional)**
  - Checks if `ruff` is on `PATH`; gracefully skips if absent.
  - Runs `ruff check --output-format=json` over the entire repo root in one subprocess call.
  - Generates fix suggestions from ruff rule codes and message text.
  - Capped at 5 issues per file (highest severity first).

  **Tier 2 — Deterministic smell detection (all languages)**
  | Smell | What It Catches |
  |---|---|
  | Bare except | `except:` or `except Exception:` with no specific type |
  | Pass-only function | Function/method body that is only `pass` |
  | Deep nesting | > 4 levels of `if`/`else`/`for`/`while` indentation |
  | Debug prints | `print()` or `console.log()` in non-test files |
  | TODO/FIXME | `# TODO` / `# FIXME` / `# HACK` developer debt comments |
  | Duplicate functions | Near-identical function bodies in the same file (Jaccard ≥ 0.85) |

- Results are cached in PostgreSQL (keyed by file content hash) to avoid re-scanning unchanged files.
- The full `issues` list is **only used by the frontend** Bug Report panel — it is never forwarded to Groq.

**Output:** `list[CodeIssue]` — `{file, line, severity, source, rule, message, suggestion}`.

---

### Stage 8 — `DependencyGraphAgent`

**File:** `backend/app/agents/dependency_graph_agent.py`

**What it does:**
- Fully deterministic — **zero LLM calls**.
- Walks **the entire repository** (not just the LLM budget subset), because import parsing is cheap and a complete graph is more accurate.
- Parses import statements:
  - **Python**: `import x`, `from x import y`, `from . import z` (relative imports resolved to repo-relative paths).
  - **JS/TS**: `import ... from '...'`, `require('...')`.
- Builds a directed graph (file → file) and computes:
  - **Nodes**: each file + its in-degree (how many other files import it).
  - **Edges**: directed import relationships.
  - **Cycles**: DFS-detected circular dependency paths.
  - **Most depended-on**: file with the highest in-degree.

**Output:** `DependencyGraph` — `{nodes, edges, cycles, most_depended_on}` — rendered as an interactive D3 force-directed graph in the UI.

---

### Stage 9 — `CodeAnalysisAgent` (Orchestrator)

**File:** `backend/app/agents/code_analysis_agent.py`

**What it does:**
- Orchestrates Stages 4–8 and the Ollama LLM summarisation phases into a single async pipeline.
- Calls stages in this exact order:

```
Phase 0 → FilePrioritizationAgent       (deterministic)
Phase 1 → CodeChunkingAgent             (deterministic, tree-sitter)
Phase 2 → PatternDetector               (deterministic, regex)
         → BugDetectionAgent            (deterministic, static)
         → DependencyGraphAgent         (deterministic, AST/regex)

Phase A → Ollama code-model (qwen2.5-coder:7b)
           Concurrent chunk summarisation
           · Each chunk → one-sentence summary via code model
           · Capped at MAX_CHUNKS_TO_SUMMARIZE (default 60) LLM calls
           · Cached by SHA-256(content) + model name in PostgreSQL
           · Uncached chunks beyond the cap get a heuristic fallback summary

Phase B → Ollama text-model (llama3.1:8b)
           Reduce: chunk summaries → file summaries
           · ≤3 summaries: deterministic bullet-join (no LLM)
           · >3 summaries: LLM reduce call → one sentence per file
           Reduce: file summaries → module summaries
           · Group files by top-level directory
           · One-sentence module summary per directory
```

**Model batching**: All Phase A calls complete before Phase B begins (`OLLAMA_BATCH_BY_MODEL=True` by default). This prevents Ollama from swapping two loaded models on constrained hardware.

**Embedding for Q&A**: After all summaries are produced, each chunk is embedded via `EmbeddingService` (using `nomic-embed-text` or `llama3.1:8b` as fallback) and stored in the `chunk_embeddings` table — enabling the RAG chat pipeline.

**Output:** `CodeInsights` — `{analyzed_files, file_summaries, module_summaries, notable_patterns, issues, dependency_graph, cache_hit_rate}`

---

### Stage 10 — `ReportGenerationAgent`

**File:** `backend/app/agents/report_generation_agent.py`

**What it does:**
- Builds the structured facts payload to send to Groq (never raw source code):
  - Tech stack, API count, API paths, module summaries, notable patterns, issues summary counts (never the full list).
  - Enforces the `_GROQ_PAYLOAD_MAX_BYTES` cap (32 KB) as a regression guard.
- Calls `GroqAnalysisService.generate_report(facts)` → receives:
  - `project_overview`, `use_case`, `complexity_level`
  - `workflow` (step-by-step how the project operates)
  - `detected_features` (with evidence)
  - `key_technologies`, `architecture_notes`
  - `confidence_score` (0–100)
- Assembles the final `RepositoryAnalysisReport` from all pipeline outputs.
- Persists the report to PostgreSQL (`analysis_reports` table) and writes a JSON file to `REPORTS_DIR/`.

**Output:** `RepositoryAnalysisReport` — the complete report returned to the frontend and stored in the DB.

---

### Stage 11 — `QAChatAgent`

**File:** `backend/app/agents/qa_chat_agent.py`

**What it does:**
- Provides interactive Q&A about the analysed codebase using a **three-tier RAG retrieval** strategy — invoked on demand when the user types a question in the chat panel.

**Three-Tier Retrieval Pipeline:**

```
User Question
      │
      ├─── Parse: file:line refs?  ──────────────────────────── YES ──▶ PINNED retrieval
      │          (e.g. "app/main.py:321 fix this")                      DB query by file suffix
      │                                                                  + line range (±25 lines)
      │                                                                  Score = 1.0 (guaranteed)
      │
      ├─── Embed question (Ollama nomic-embed-text)
      │
      ├─── SECONDARY retrieval (cosine similarity)
      │    top-(5 − pinned_count) chunks from chunk_embeddings
      │
      ├─── Parse: code symbols? ──── symbols not in context? ──▶ TARGETED retrieval
      │          (call_llm_json, MyClass, …)                     substring search on chunk_content
      │                                                           Score = 0.8 (targeted match)
      │
      └─── Assemble context: [PINNED] + [SECONDARY] + [TARGETED]
                │
                ▼
           Build intent-aware prompt
           · Fix/debug question? → Groq instructed: concrete answer + corrected code block
           · General question?   → Focus on [DIRECTLY REFERENCED] chunks
                │
                ▼
             Groq API
           (llama-3.1-8b-instant)
                │
                ▼
           Answer + citations {file, start_line, end_line}
```

**Key behaviours:**
- Every message — including the first — goes through the full retrieval pipeline. There is no silent skip path.
- If a `file:line` reference is found, that exact file's chunk is **guaranteed** to appear in the context regardless of its similarity score.
- If a code symbol (e.g. `call_llm_json`) mentioned in the question is absent from the initial context, a targeted follow-up DB search fires before Groq is called.
- Fix/debug intent is detected via regex (`fix`, `rewrite`, `debug`, `explain this error`, etc.). When triggered, Groq is explicitly instructed **not** to hedge — it must provide a concrete explanation and corrected code block.
- Embedding model is resolved once per process start (module-level cache) — no repeated `GET /api/tags` on every chat message.

**Output:** `{answer: str, citations: list[{file, start_line, end_line}]}`

---

## LLM Architecture

The system uses a **three-tier LLM strategy**:

| Tier | Model | Where | Purpose |
|---|---|---|---|
| **Code model** | `qwen2.5-coder:7b` | Ollama (local) | Chunk-level summaries — understands code semantics deeply |
| **Text model** | `llama3.1:8b` | Ollama (local) | README summarisation, file/module reduce — runs offline |
| **Cloud reasoning** | `llama-3.1-8b-instant` | Groq API | High-level project overview, feature detection, architecture notes — fast cloud inference |
| **Embedding** | `nomic-embed-text` | Ollama (local) | Query and chunk embeddings for RAG chat — fallback to `llama3.1:8b` |

All four LLM providers degrade gracefully:
- Ollama offline → summaries skipped, code_insights = null, Q&A unavailable.
- Groq unavailable → deterministic fallback analysis returned.
- `nomic-embed-text` not pulled → embedding falls back to `llama3.1:8b`.

---

## Groq Safety Boundary

**Groq never receives raw source code.** The boundary is enforced in `analysis_service.py` and verified by `test_groq_boundary.py`.

What Groq **receives**:
- Tech stack lists (strings only)
- API endpoint paths and methods (strings only)
- `module_summaries` (one sentence per directory — produced by Ollama, not raw code)
- `notable_patterns` (human-readable descriptions, not code)
- Issues count summary (e.g. `{high: 2, medium: 5, low: 12}` — no code)

What Groq **never receives**:
- `file_summaries` (too verbose)
- `issues` full list (contains code snippets)
- Raw chunk content
- File contents of any kind

The Q&A chat is the **only** explicit exception — it passes retrieved code chunks to Groq to answer user questions. This is opt-in by the user, intentional, and clearly annotated in `groq_service.py`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115 · Python 3.11+ |
| Frontend | React 18 · Vite · Vanilla CSS |
| Database | PostgreSQL · SQLAlchemy 2.0 |
| Code LLM (local) | Ollama · `qwen2.5-coder:7b` |
| Text LLM (local) | Ollama · `llama3.1:8b` |
| Embedding (local) | Ollama · `nomic-embed-text` |
| Cloud LLM | Groq API · `llama-3.1-8b-instant` |
| AST parsing | tree-sitter · tree-sitter-languages |
| Static analysis | Ruff (Python linter, optional) |
| Visualisation | D3-force (dependency graph) |
| PDF export | ReportLab |
| Repo cloning | GitPython |

---

## Folder Structure

```text
AutoQA_Agent/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── api_discovery_agent.py        # Stage 3  — REST endpoint scanner
│   │   │   ├── bug_detection_agent.py        # Stage 7  — ruff + static smell detection
│   │   │   ├── code_analysis_agent.py        # Stage 9  — async pipeline orchestrator
│   │   │   ├── code_chunking_agent.py        # Stage 5  — tree-sitter semantic chunking
│   │   │   ├── dependency_graph_agent.py     # Stage 8  — import graph + cycle detection
│   │   │   ├── file_prioritization_agent.py  # Stage 4  — scored file ranking + budget
│   │   │   ├── pattern_detector.py           # Stage 6  — regex pattern detection
│   │   │   ├── qa_chat_agent.py              # Stage 11 — RAG chat (pinned/semantic/targeted)
│   │   │   ├── report_generation_agent.py    # Stage 10 — report assembly + persistence
│   │   │   ├── repository_analysis_agent.py  # Stage 1  — clone + metadata extraction
│   │   │   └── tech_stack_agent.py           # Stage 2  — deterministic stack detection
│   │   ├── api/
│   │   │   └── routes.py                     # FastAPI route definitions
│   │   ├── core/
│   │   │   ├── config.py                     # Pydantic settings (reads .env)
│   │   │   ├── exceptions.py                 # Custom exception types
│   │   │   └── logging_config.py             # Structured logging setup
│   │   ├── db/
│   │   │   ├── models.py                     # SQLAlchemy ORM: analysis_reports,
│   │   │   │                                 #   summary_cache, chunk_embeddings
│   │   │   └── session.py                    # DB session factory + get_db()
│   │   ├── repositories/
│   │   │   └── analysis_repository.py        # DB read/write layer
│   │   ├── schemas/
│   │   │   └── analysis.py                   # Pydantic request/response models
│   │   ├── services/
│   │   │   ├── analysis_service.py           # Top-level pipeline orchestrator
│   │   │   ├── cache_service.py              # SHA-256 content-addressed summary cache
│   │   │   ├── embedding_service.py          # Ollama embedding API wrapper
│   │   │   ├── groq_service.py               # Groq API integration + singleton
│   │   │   ├── llm_service.py                # Groq SDK wrapper (GroqClient)
│   │   │   ├── ollama_service.py             # Ollama HTTP integration
│   │   │   ├── pdf_service.py                # PDF report generation (ReportLab)
│   │   │   ├── vector_search_service.py      # Cosine similarity search over embeddings
│   │   │   └── worker_pool.py                # Async concurrency pool for Ollama calls
│   │   └── main.py                           # FastAPI app + CORS + startup
│   ├── tests/
│   │   ├── test_groq_boundary.py             # Verifies Groq never receives raw code
│   │   └── test_qa_chat_agent.py             # QAChatAgent + retrieval unit tests
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js                     # Fetch wrappers for all API endpoints
│   │   ├── components/
│   │   │   ├── AnalysisTimeline.jsx          # Step-by-step analysis progress
│   │   │   ├── ApiTable.jsx                  # API inventory table with search/filter
│   │   │   ├── ArchitectureFlow.jsx          # Architecture flow diagram
│   │   │   ├── ArchitectureTab.jsx           # Architecture layer view (UI/API/DB/…)
│   │   │   ├── BugReportPanel.jsx            # Bug & code issue browser
│   │   │   ├── CodeInsightsPanel.jsx         # File/module summaries + patterns
│   │   │   ├── DependencyGraphPanel.jsx      # Interactive D3 dependency graph
│   │   │   ├── EvidenceAccordion.jsx         # Collapsible evidence for features
│   │   │   ├── HeroSection.jsx               # Landing hero + URL input
│   │   │   ├── InsightsPanel.jsx             # Groq AI insights panel
│   │   │   ├── MetricCards.jsx               # Summary metric cards
│   │   │   ├── QAChatPanel.jsx               # RAG chat interface
│   │   │   ├── Sidebar.jsx                   # Navigation sidebar
│   │   │   └── TechStackPanel.jsx            # Tech stack display
│   │   └── App.jsx                           # Root app, tabs, lifted chat state
│   ├── package.json
│   └── vite.config.js
├── repositories/                             # Cloned repos (auto-created, git-ignored)
├── reports/                                  # JSON reports (auto-created)
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Backend runtime |
| Node.js 18+ | Frontend dev server |
| PostgreSQL | Report + embedding storage |
| Git | Required for GitPython repo cloning |
| [Ollama](https://ollama.com) | Local LLM — summaries and embeddings |
| [Groq API key](https://console.groq.com) | Cloud reasoning — free tier available |

**Pull the required Ollama models:**
```bash
ollama pull llama3.1:8b          # text model — README/module summaries
ollama pull qwen2.5-coder:7b     # code model — chunk summaries
ollama pull nomic-embed-text     # embedding model — RAG chat
```

> **Graceful degradation**: If Ollama is offline, `code_insights` is omitted from the report and Q&A chat is unavailable. If Groq is unavailable, a deterministic fallback analysis is returned. The pipeline never crashes due to a missing AI provider.

---

## Setup Guide

### Backend

```bash
cd AutoQA_Agent/backend

# Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — see Environment Variables table below

# Start the backend (with hot-reload, watching app/ only)
uvicorn app.main:app --reload --reload-dir app
```

Backend runs at: `http://localhost:8000`  
Interactive API docs: `http://localhost:8000/docs`

---

### Frontend

```bash
cd AutoQA_Agent/frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

### PostgreSQL

```sql
CREATE DATABASE autoqa_agent;
```

Tables are created automatically by SQLAlchemy on first backend startup — no manual migrations required.

Set the connection string in `backend/.env`:
```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/autoqa_agent
```

---

## Environment Variables

All variables are read from `backend/.env` (copy from `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://...` | PostgreSQL connection string |
| `WORKSPACE_DIR` | `../repositories` | Where repos are cloned |
| `REPORTS_DIR` | `../reports` | Where JSON reports are saved |
| `GROQ_API_KEY` | *(required)* | Groq API key for cloud reasoning |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama server URL |
| `OLLAMA_TEXT_MODEL` | `llama3.1:8b` | Ollama model for text tasks |
| `OLLAMA_CODE_MODEL` | `qwen2.5-coder:7b` | Ollama model for code chunk summaries |
| `OLLAMA_MAX_CONCURRENCY` | `2` | Max concurrent Ollama requests |
| `OLLAMA_CHUNK_TIMEOUT_SECONDS` | `90` | Per-chunk LLM timeout |
| `OLLAMA_BATCH_BY_MODEL` | `True` | Complete Phase A before Phase B (recommended) |
| `MAX_FILES_TO_ANALYZE` | `50` | Hard cap on files sent to code analysis |
| `MAX_CHUNKS_TO_SUMMARIZE` | `60` | Hard cap on LLM chunk summary calls |
| `MAX_CODE_TOKEN_BUDGET` | `40000` | Total character budget for selected files |
| `CODE_CHUNK_MAX_CHARS` | `3000` | Max characters per fallback chunk |
| `LOG_LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`) |

---

## API Reference

### Health Check
```http
GET /health
```
```json
{ "status": "healthy", "service": "AutoQA Agent" }
```

---

### Analyze Repository
```http
POST /analyze-repository
Content-Type: application/json

{ "github_url": "https://github.com/owner/repo" }
```
Triggers the full 11-agent pipeline. Returns `RepositoryAnalysisReport`.

---

### Get Analysis by ID
```http
GET /analysis/{analysis_id}
```
Returns the stored report JSON for a previously analysed repository.

---

### List All Analyses
```http
GET /analyses?limit=50
```
Returns a lightweight summary list (newest first) with confidence scores and tech stack.

---

### Download PDF Report
```http
GET /analysis/{analysis_id}/pdf
```
Streams a generated PDF report as a file download.

---

### Q&A Chat
```http
POST /analysis/{analysis_id}/chat
Content-Type: application/json

{ "question": "app/main.py:321 explain this error" }
```
Returns `{ "answer": "...", "citations": [{"file": "...", "start_line": 321, "end_line": 345}] }`.

Supports natural language, direct file:line references, and symbol lookups.

---

## Frontend UI Panels

| Tab / Panel | What It Shows |
|---|---|
| **Q&A Chat** | RAG-powered chat — ask anything about the codebase. Chat history persists across tab switches. |
| **Dependency Graph** | Interactive D3 force-directed graph. Pan + scroll zoom. Click a node to see its dependents. Circular imports highlighted in red. |
| **Bug Report** | All detected code issues from ruff + static smell detection, grouped by severity (High / Medium / Low). |
| **Architecture** | Files automatically classified into layers (Frontend / API / Services / Models / DB / Config / Tests). |
| **Code Insights** | File-level and module-level Ollama summaries, notable patterns, and analysis cache stats. |
| **Tech Stack** | Detected languages, frameworks, databases, and package managers with evidence. |
| **API Inventory** | Full searchable/filterable table of all discovered endpoints with method, path, framework, and file. |
| **AI Insights** | Groq-generated project overview, detected features, architecture notes, workflow steps, and confidence score. |
| **PDF Export** | Download a formatted PDF report of the full analysis. |

---

## Example Report

```json
{
  "analysis_id": "a1b2c3d4-...",
  "repository_name": "sample-api",
  "repository_url": "https://github.com/user/sample-api",
  "metadata": {
    "default_branch": "main",
    "latest_commit": "abc123ef",
    "local_path": "repositories/sample-api"
  },
  "technology_stack": {
    "frontend": ["React"],
    "backend": ["FastAPI"],
    "languages": ["Python", "JavaScript/TypeScript"],
    "databases": ["PostgreSQL"],
    "frameworks": ["FastAPI", "Vite"],
    "package_managers": ["pip/poetry/pipenv", "npm/yarn/pnpm"]
  },
  "number_of_files": 82,
  "number_of_apis_discovered": 6,
  "api_inventory": [
    { "method": "GET",  "path": "/health",             "framework": "FastAPI", "file": "routes.py", "line_number": 24 },
    { "method": "POST", "path": "/analyze-repository", "framework": "FastAPI", "file": "routes.py", "line_number": 31 }
  ],
  "code_insights": {
    "analyzed_files": ["app/main.py", "app/api/routes.py", "..."],
    "module_summaries": {
      "app":      "FastAPI application providing repository analysis and Q&A endpoints.",
      "frontend": "React UI for submitting GitHub URLs and exploring analysis results."
    },
    "notable_patterns": [
      "JWT auth in app/api/routes.py",
      "External API calls (httpx) in app/services/groq_service.py"
    ],
    "cache_hit_rate": 0.73
  },
  "dependency_graph": {
    "nodes": [{ "file": "app/main.py", "dependency_count": 3 }],
    "edges": [{ "from": "app/api/routes.py", "to": "app/agents/qa_chat_agent.py" }],
    "cycles": [],
    "most_depended_on": "app/services/analysis_service.py"
  },
  "ai_explanation": {
    "project_overview": "A FastAPI-based repository analysis system...",
    "use_case": "Automated code review and architecture documentation.",
    "complexity_level": "Intermediate",
    "workflow": ["Clone repo", "Detect stack", "Analyse code", "Generate report"],
    "architecture_notes": "Clean layered architecture with agents, services, and DB repositories."
  },
  "confidence_score": 88.0
}
```

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

Tests cover:
- Cosine similarity utility
- Vector store + retrieval round-trip
- QAChatAgent pinned retrieval (file:line)
- QAChatAgent targeted symbol lookup
- `_parse_file_line_refs` and `_parse_symbol_refs` helpers
- Groq boundary enforcement (14 assertions verifying no raw code leaks to Groq)
