# AutoQA Agent

> **AI-powered repository analysis, code execution tracing, feature map extraction, cross-repository comparison, and interactive Q&A — all in one system.**

AutoQA Agent accepts any public GitHub repository URL, clones it locally, runs an 18-agent analysis pipeline, and produces a rich structured report covering tech stack, API inventory, dependency graphs, bug detection, execution flow traces, business feature maps, architecture drift, developer onboarding guides, tech debt rankings, and AI-generated architectural insights. A built-in RAG chat lets you ask questions about the code in plain English.

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
  - [Stage 11 — ChangeImpactAnalysisAgent (V2)](#stage-11--changeimpactanalysisagent-v2)
  - [Stage 12 — ArchitectureDriftAgent (V2)](#stage-12--architecturedriftagent-v2)
  - [Stage 13 — AIProjectOnboardingAgent (V2)](#stage-13--aiprojectonboardingagent-v2)
  - [Stage 14 — RepositoryHealthScoreAgent (V2)](#stage-14--repositoryhealthscoreagent-v2)
  - [Stage 15 — TechnicalDebtPrioritizationAgent (V2)](#stage-15--technicaldebtprioritizationagent-v2)
  - [Stage 16 — ExecutionFlowAgent (V3)](#stage-16--executionflowagent-v3)
  - [Stage 17 — FeatureExtractionAgent (V3)](#stage-17--featureextractionagent-v3)
  - [Stage 18 — CrossRepoDuplicateAgent (V3 Enhanced)](#stage-18--crossrepoduplicateagent-v3-enhanced)
  - [Stage 19 — QAChatAgent](#stage-19--qachatagent)
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
- [Running Tests](#running-tests)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER  (React Frontend)                            │
│           Submits GitHub URL  ·  Views report  ·  Compares Repos  ·  Chats  │
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
               ┌──────────────────┴──────────────────────┐
               │                                         │
               ▼                                         ▼
   [Stage 11–15: V2 Enterprise]              [Stage 16–18: V3 AI Agents]
   Impact Analysis · Arch Drift              Execution Flow Visualizer
   Onboarding · Health · Tech Debt           Feature Map · Clone Detection
                                  │
                                  ▼
                        [PostgreSQL Database]
                                  │
                      ┌───────────┘
                      ▼
                  [Stage 19]
                  QAChatAgent (RAG: Pinned → Semantic → Targeted)
                      │
                      ▼
                  Groq API (answer generation)
```

---

## Agent Pipeline — How It Works

The full pipeline executes in sequence across 18 specialized agents.

---

### Stage 1 — `RepositoryAnalysisAgent`
**File:** `backend/app/agents/repository_analysis_agent.py`
- Validates the submitted URL matches `https://github.com/owner/repo`.
- Shallow-clones the repository (`depth=1`) via GitPython into `WORKSPACE_DIR/`.
- Handles Windows file-lock permission errors during cleanups via `_remove_readonly`.
- Extracts repository metadata: branch, latest commit SHA, total file/directory counts, top-level structure, and config files.

---

### Stage 2 — `TechStackDetectionAgent`
**File:** `backend/app/agents/tech_stack_agent.py`
- Deterministic analysis (zero LLM calls).
- Inspects file extensions, parses `package.json`, `requirements.txt`, `pyproject.toml`, `pom.xml`, `build.gradle`.
- Detects frontend/backend frameworks, databases (PostgreSQL, MongoDB, MySQL), languages, and records source evidence.

---

### Stage 3 — `ApiDiscoveryAgent`
**File:** `backend/app/agents/api_discovery_agent.py`
- Deterministic regex scanning for REST endpoints across frameworks:
  - **FastAPI**: `@router.get(...)`, `@app.post(...)`
  - **Flask**: `@app.route(...)`, `@blueprint.get(...)`
  - **Django**: `path(...)`, `re_path(...)`
  - **Express.js**: `app.get(...)`, `router.post(...)`
  - **Spring Boot**: `@GetMapping`, `@PostMapping`
- Extracts HTTP method, path, file, line number, and framework.

---

### Stage 4 — `FilePrioritizationAgent`
**File:** `backend/app/agents/file_prioritization_agent.py`
- Ranks repository files by architectural importance (+50 entry points, +40 API route files, +30 services/models/controllers).
- Enforces token budget caps (`MAX_FILES_TO_ANALYZE` and `MAX_CODE_TOKEN_BUDGET`).

---

### Stage 5 — `CodeChunkingAgent`
**File:** `backend/app/agents/code_chunking_agent.py`
- Splits prioritized source files into semantic AST chunks (functions/classes) using **tree-sitter**.
- Fallback to line/character chunks for languages without tree-sitter grammars.

---

### Stage 6 — `PatternDetector`
**File:** `backend/app/agents/pattern_detector.py`
- Scans chunks for notable patterns: JWT auth, raw SQL queries, external HTTP calls, env secret access, hardcoded secrets, sub-processes, developer debt comments (`TODO`, `FIXME`).

---

### Stage 7 — `BugDetectionAgent`
**File:** `backend/app/agents/bug_detection_agent.py`
- Static code analysis smell detection: bare excepts, pass-only functions, deep nesting (>4 levels), debug print statements, duplicate function bodies.
- Integrates optional `Ruff` linter for Python repositories when installed on system `PATH`.

---

### Stage 8 — `DependencyGraphAgent`
**File:** `backend/app/agents/dependency_graph_agent.py`
- Parses import statements across the entire repository to build a directed graph (nodes, edges, in-degree centrality, circular dependency cycles).

---

### Stage 9 — `CodeAnalysisAgent` (Orchestrator)
**File:** `backend/app/agents/code_analysis_agent.py`
- Orchestrates Phases 0–2 (deterministic) and Phases A–B (Ollama LLM summarization).
- Concurrent chunk summarization via local code model (`qwen2.5-coder:7b`).
- Hierarchical reduce to produce per-file and per-module summaries via local text model (`llama3.1:8b`).
- Stores vector embeddings for semantic code search.

---

### Stage 10 — `ReportGenerationAgent`
**File:** `backend/app/agents/report_generation_agent.py`
- Assembles non-sensitive structured facts payload (< 32 KB) and queries Groq API for architectural reasoning.
- Produces overview, complexity level, workflows, key tech, confidence score, and persists report to PostgreSQL & JSON file.

---

### Stage 11 — `ChangeImpactAnalysisAgent` (V2)
**File:** `backend/app/agents/change_impact_agent.py`
- Performs blast-radius analysis when a file is modified.
- Calculates direct/transitive dependencies, affected API routes, and assigns risk levels (Low/Medium/High/Critical).

---

### Stage 12 — `ArchitectureDriftAgent` (V2)
**File:** `backend/app/agents/architecture_drift_agent.py`
- Audits repository structure against clean architecture guidelines.
- Detects circular dependencies, layer violations (e.g. DB calls in controllers), orphaned files, and monolithic file smells.

---

### Stage 13 — `AIProjectOnboardingAgent` (V2)
**File:** `backend/app/agents/project_onboarding_agent.py`
- Generates a step-by-step recommended reading path for new developers.
- Produces interactive comprehension quizzes based on repository architecture.

---

### Stage 14 — `RepositoryHealthScoreAgent` (V2)
**File:** `backend/app/agents/repository_health_agent.py`
- Computes an overall 0–100 health score with category breakdowns (Maintainability, Test Coverage, Architectural Hygiene, Documentation).

---

### Stage 15 — `TechnicalDebtPrioritizationAgent` (V2)
**File:** `backend/app/agents/technical_debt_agent.py`
- Generates an actionable, prioritized tech debt backlog ranked by business impact, estimated fix effort (hours), and risk.

---

### Stage 16 — `ExecutionFlowAgent` (V3 New)
**File:** `backend/app/agents/execution_flow_agent.py`
- **Purely deterministic static AST tracer** — visualizes execution call paths starting from API endpoints.
- Traces direct and transitive function calls, database operations (`session.query`, `execute`, `filter`), external HTTP calls (`requests`, `httpx`, `axios`), and handled exceptions.
- Computes confidence scores per node (0.0–1.0) and assigns depth meters.

---

### Stage 17 — `FeatureExtractionAgent` (V3 New)
**File:** `backend/app/agents/feature_extraction_agent.py`
- **Zero re-scanning agent** — discovers business feature domains from existing pipeline artifacts (API inventory, module summaries, code insights, `.env.example`).
- Classifies routes, controllers, services, models, DB tables, env vars, and config files into business feature cards (Authentication, Payment, User Management, Analytics, AI/ML, etc.).
- Computes weighted feature confidence scores and includes fallback micro-clustering for custom routes.

---

### Stage 18 — `CrossRepoDuplicateAgent` (V3 Enhanced)
**File:** `backend/app/agents/cross_repo_duplicate_agent.py`
- Performs multi-dimensional cross-repository comparison:
  - **API similarity** (35% weight)
  - **Code similarity** (30% weight)
  - **Architecture similarity** (15% weight)
  - **Module structure similarity** (10% weight)
  - **Feature similarity** (10% weight)
- **Clone Detection**: Identifies near-identical codebases at a 98% threshold and outputs informational warning banners (without legal/ownership claims).
- **Relationship Classification**: Classifies repository pairs as *Near-Identical Copy*, *Likely Cloned Repository*, *Shared Template*, *Fork*, *Shared Architecture*, or *Independent Repository*.

---

### Stage 19 — `QAChatAgent`
**File:** `backend/app/agents/qa_chat_agent.py`
- Three-tier RAG retrieval pipeline:
  1. **Pinned retrieval**: Direct `file:line` references (score = 1.0)
  2. **Semantic retrieval**: Cosine vector search over `chunk_embeddings`
  3. **Targeted retrieval**: Symbol substring matching if mentioned symbols are missing from context
- Generates grounded answers via Groq with exact file & line-range citations.

---

## LLM Architecture

The system uses a **three-tier LLM strategy**:

| Tier | Model | Provider | Purpose |
|---|---|---|---|
| **Code model** | `qwen2.5-coder:7b` | Ollama (local) | Chunk-level code semantics & function summaries |
| **Text model** | `llama3.1:8b` | Ollama (local) | README summarisation, module reduce, feature enrichment |
| **Cloud reasoning** | `llama-3.1-8b-instant` | Groq API | Project overview, high-level feature reasoning, RAG chat |
| **Embedding** | `nomic-embed-text` | Ollama (local) | Vector search embeddings for code chunks |

---

## Groq Safety Boundary

**Groq never receives raw source code during repository analysis.**

- Sent to Groq: Tech stack names, API endpoint paths, 1-sentence module summaries, pattern descriptions, issue count totals.
- Never sent to Groq: Raw chunk contents, full file source code, full bug issue lists.

*Exception*: Interactive Q&A chat sends user-requested, relevant code snippets to Groq to generate answers.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115 · Python 3.11+ · Pydantic V2 |
| Frontend | React 18 · Vite · Vanilla CSS |
| Database | PostgreSQL · SQLAlchemy 2.0 |
| Local LLM | Ollama (`qwen2.5-coder:7b`, `llama3.1:8b`, `nomic-embed-text`) |
| Cloud LLM | Groq API (`llama-3.1-8b-instant`) |
| AST & Static Analysis | tree-sitter · Python `ast` · Ruff |
| Visualisation | D3-force (Dependency Graph) · Custom SVG (Execution Flow) |
| Testing | Pytest (68 unit & integration tests) |

---

## Folder Structure

```text
AutoQA_Agent/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── api_discovery_agent.py         # Stage 3  — REST endpoint scanner
│   │   │   ├── architecture_drift_agent.py    # Stage 12 — Clean architecture audit
│   │   │   ├── bug_detection_agent.py         # Stage 7  — Ruff + static smell detection
│   │   │   ├── change_impact_agent.py         # Stage 11 — Blast radius analyzer
│   │   │   ├── code_analysis_agent.py         # Stage 9  — Async pipeline orchestrator
│   │   │   ├── code_chunking_agent.py         # Stage 5  — tree-sitter semantic chunking
│   │   │   ├── cross_repo_duplicate_agent.py  # Stage 18 — Clone detection & multi-dim compare
│   │   │   ├── dependency_graph_agent.py      # Stage 8  — Import graph & cycle detection
│   │   │   ├── execution_flow_agent.py        # Stage 16 — AST static call graph tracer
│   │   │   ├── feature_extraction_agent.py    # Stage 17 — Business feature discovery
│   │   │   ├── file_prioritization_agent.py   # Stage 4  — Scored file ranking
│   │   │   ├── pattern_detector.py            # Stage 6  — Regex pattern detector
│   │   │   ├── project_onboarding_agent.py    # Stage 13 — Developer reading path & quizzes
│   │   │   ├── qa_chat_agent.py               # Stage 19 — 3-tier RAG chat
│   │   │   ├── report_generation_agent.py     # Stage 10 — Report assembly & JSON save
│   │   │   ├── repository_analysis_agent.py   # Stage 1  — Clone & metadata extractor
│   │   │   ├── repository_health_agent.py     # Stage 14 — 0-100 health scoring
│   │   │   ├── technical_debt_agent.py        # Stage 15 — Prioritized tech debt backlog
│   │   │   └── tech_stack_agent.py            # Stage 2  — Stack detection
│   │   ├── api/
   │   │   └── routes.py                      # FastAPI routes (+ V3 endpoints)
│   │   ├── schemas/
│   │   │   ├── analysis.py                    # RepositoryAnalysisReport model
│   │   │   └── v2_schemas.py                 # V2 & V3 execution flow / feature map schemas
│   │   └── services/
│   │       ├── analysis_service.py            # Main pipeline orchestrator
│   │       └── pipeline_status_service.py     # Real-time status tracking service
│   ├── tests/
│   │   ├── test_cross_repo_clone_detection.py# Clone threshold & similarity tests
│   │   ├── test_execution_flow_agent.py       # AST tracer & DB/HTTP call tests
│   │   ├── test_feature_extraction_agent.py   # Feature domain & env var tests
│   │   ├── test_groq_boundary.py              # Safety boundary tests
│   │   └── test_qa_chat_agent.py              # RAG retrieval tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── CrossRepoCompareModal.jsx     # Enhanced clone detection compare modal
│   │   │   ├── ExecutionFlowTab.jsx          # Interactive call graph flow UI
│   │   │   ├── FeatureMapTab.jsx             # Business feature map & implementation cards
│   │   │   ├── ImpactAnalysisTab.jsx         # Blast radius UI
│   │   │   ├── ArchitectureDriftTab.jsx      # Architecture drift UI
│   │   │   ├── ProjectOnboardingTab.jsx      # Onboarding guide & quiz UI
│   │   │   ├── RepositoryHealthTab.jsx       # Health score gauge & metrics UI
│   │   │   └── TechnicalDebtTab.jsx          # Tech debt backlog UI
│   │   └── App.jsx                           # Main React app & tab navigation
│   └── package.json
└── README.md
```

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.11+ | Backend runtime |
| Node.js 18+ | Frontend dev server |
| PostgreSQL | Report and vector embedding storage |
| Git | Repository cloning |
| [Ollama](https://ollama.com) | Local LLM summarization and embeddings |
| [Groq API key](https://console.groq.com) | Cloud reasoning and RAG chat |

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

# Start the backend server
uvicorn app.main:app --reload
```

Backend runs at: `http://localhost:8000`  
Swagger API Docs: `http://localhost:8000/docs`

---

### Frontend

```bash
cd AutoQA_Agent/frontend
npm install
npm run dev
```

Frontend runs at: `http://localhost:5173`

---

## API Reference

### V3 Endpoints (New)

#### Get Execution Flow Graphs
```http
GET /analysis/{analysis_id}/execution-flow?entry_point=POST+/login
```
Returns AST-traced call graphs, DB operations, HTTP calls, depth, and handled exceptions for entry points.

#### Get Business Feature Map
```http
GET /analysis/{analysis_id}/feature-map
```
Returns detected business features with linked APIs, controllers, services, models, DB tables, and env vars.

#### Enhanced Cross-Repo Comparison
```http
POST /compare-repositories
Content-Type: application/json

{
  "analysis_id_a": "uuid-1",
  "analysis_id_b": "uuid-2"
}
```
Returns multi-dimensional similarity percentages (API, Code, Architecture, Module, Feature), clone detection flags (`clone_detected`), relationship classification, and banner messages.

---

### Existing Endpoints

- `POST /analyze-repository` — Trigger full pipeline
- `GET /analysis/{analysis_id}` — Retrieve full analysis report
- `GET /analysis/{analysis_id}/status` — Real-time stage progress
- `GET /analyses` — List all stored repository reports
- `POST /analysis/{analysis_id}/chat` — RAG Q&A chat
- `GET /analysis/{analysis_id}/pdf` — Download PDF report

---

## Frontend UI Panels

| Tab | Description |
|---|---|
| **Q&A Chat** | RAG-powered chat with citations and code snippet responses |
| **Dependency Graph** | Interactive D3 force-directed dependency graph with cycle detection |
| **Execution Flow** *(New)* | Interactive AST call graph visualizer with node type filtering |
| **Feature Map** *(New)* | Business feature discovery cards with full implementation mappings |
| **Impact Analysis** | Change impact blast-radius calculator |
| **Arch Drift** | Clean architecture audit & violation detector |
| **Onboarding** | Step-by-step developer reading path and interactive quizzes |
| **Health Score** | Overall 0–100 repository health gauge & category breakdown |
| **Tech Debt** | Prioritized debt backlog with estimated fix hours |
| **Bug Report** | Static code smells & linter warnings |
| **Architecture** | Automatic architectural layer classification |

---

## Running Tests

Run the unit test suite:

```bash
cd AutoQA_Agent/backend
python -m pytest tests/test_execution_flow_agent.py tests/test_feature_extraction_agent.py tests/test_cross_repo_clone_detection.py -v -p no:asyncio
```

Run all tests:
```bash
python -m pytest tests/ -v -p no:asyncio
```
