# AutoQA Agent — AI Repository Intelligence & Code Analysis System

> **An enterprise-grade, multi-agent AI system for automated GitHub repository analysis, execution flow tracing, functional feature mapping, architectural audit, cross-repository comparison, and interactive RAG Q&A.**

AutoQA Agent accepts any public GitHub repository URL, clones it locally, executes a 19-agent analysis pipeline, and produces a comprehensive structured report. It features local Ollama models for code summarization/embeddings, cloud-based Groq reasoning for high-level insights, deterministic AST analysis for zero-hallucination metrics, and a React frontend.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Complete 19-Agent System Reference](#complete-19-agent-system-reference)
  - [Phase 1: Repository Discovery & Ingestion](#phase-1-repository-discovery--ingestion)
    - [1. RepositoryAnalysisAgent](#1-repositoryanalysisagent)
    - [2. TechStackDetectionAgent](#2-techstackdetectionagent)
    - [3. ApiDiscoveryAgent](#3-apidiscoveryagent)
  - [Phase 2: Codebase Parsing & Structural Analysis](#phase-2-codebase-parsing--structural-analysis)
    - [4. FilePrioritizationAgent](#4-fileprioritizationagent)
    - [5. CodeChunkingAgent](#5-codechunkingagent)
    - [6. PatternDetector](#6-patterndetector)
    - [7. BugDetectionAgent](#7-bugdetectionagent)
    - [8. DependencyGraphAgent](#8-dependencygraphagent)
    - [9. CodeAnalysisAgent (Orchestrator)](#9-codeanalysisagent-orchestrator)
  - [Phase 3: High-Level Reasoning & Report Generation](#phase-3-high-level-reasoning--report-generation)
    - [10. ReportGenerationAgent](#10-reportgenerationagent)
  - [Phase 4: Enterprise Intelligence & Quality Audits (V2)](#phase-4-enterprise-intelligence--quality-audits-v2)
    - [11. ChangeImpactAnalysisAgent](#11-changeimpactanalysisagent)
    - [12. ArchitectureDriftAgent](#12-architecturedriftagent)
    - [13. AIProjectOnboardingAgent](#13-aiprojectonboardingagent)
    - [14. RepositoryHealthScoreAgent](#14-repositoryhealthscoreagent)
    - [15. TechnicalDebtPrioritizationAgent](#15-technicaldebtprioritizationagent)
  - [Phase 5: AI Call Tracing & Feature Extraction (V3)](#phase-5-ai-call-tracing--feature-extraction-v3)
    - [16. ExecutionFlowAgent](#16-executionflowagent)
    - [17. FeatureExtractionAgent](#17-featureextractionagent)
    - [18. CrossRepoDuplicateAgent](#18-crossrepoduplicateagent)
  - [Phase 6: Interactive Q&A Engine](#phase-6-interactive-qa-engine)
    - [19. QAChatAgent](#19-qachatagent)
- [LLM Architecture & Model Delegation](#llm-architecture--model-delegation)
- [Groq Safety Boundary (Zero Code Leakage)](#groq-safety-boundary-zero-code-leakage)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [Prerequisites & Ollama Setup](#prerequisites--ollama-setup)
- [Setup & Quickstart Guide](#setup--quickstart-guide)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [PostgreSQL Database](#postgresql-database)
- [Environment Variables](#environment-variables)
- [API Endpoints Reference](#api-endpoints-reference)
- [Frontend UI Panels & Navigation](#frontend-ui-panels--navigation)
- [Running Unit & Integration Tests](#running-unit--integration-tests)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER  (React Frontend)                            │
│           Submits GitHub URL  ·  Views Report  ·  Compares Repos  ·  Chats  │
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
 Repo       Tech       API        Code       Report      llama3   gpt-oss
 Clone      Stack      Disc.      Analysis   Gen.       qwen2.5  120b/20b
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
                  QAChatAgent (3-Tier RAG Retrieval)
                      │
                      ▼
                  Groq API (Grounded Answer Generation)
```

---

## Complete 19-Agent System Reference

The system is composed of **19 decoupled agent modules**, each operating with strict responsibilities:

---

### Phase 1: Repository Discovery & Ingestion

#### 1. `RepositoryAnalysisAgent`
- **Class:** `RepositoryAnalysisAgent`
- **File:** `backend/app/agents/repository_analysis_agent.py`
- **Mode:** Deterministic
- **Role:** Validates GitHub URLs, shallow-clones (`depth=1`) repositories into `WORKSPACE_DIR/`, handles Windows file-lock permission errors (`_remove_readonly`), and extracts repository metadata (branch, commit SHA, total files/directories, config file inventory).

#### 2. `TechStackDetectionAgent`
- **Class:** `TechStackDetectionAgent`
- **File:** `backend/app/agents/tech_stack_agent.py`
- **Mode:** Deterministic (Zero LLM calls)
- **Role:** Inspects file extensions and parses project configuration files (`package.json`, `requirements.txt`, `pyproject.toml`, `pom.xml`, `build.gradle`) to identify languages, frontend/backend frameworks, databases (PostgreSQL, MongoDB, MySQL), and package managers with file-level evidence.

#### 3. `ApiDiscoveryAgent`
- **Class:** `ApiDiscoveryAgent`
- **File:** `backend/app/agents/api_discovery_agent.py`
- **Mode:** Deterministic (Regex AST match)
- **Role:** Scans source code for REST API endpoints across FastAPI, Flask, Django, Express.js, and Spring Boot. Extracts HTTP methods, URL paths, source files, line numbers, and framework tags.

---

### Phase 2: Codebase Parsing & Structural Analysis

#### 4. `FilePrioritizationAgent`
- **Class:** `FilePrioritizationAgent`
- **File:** `backend/app/agents/file_prioritization_agent.py`
- **Mode:** Scored Ranking Algorithm
- **Role:** Ranks repository files by architectural importance (+50 entry points, +40 API route files, +30 services/models/controllers). Enforces file count caps (`MAX_FILES_TO_ANALYZE`) and character token budgets (`MAX_CODE_TOKEN_BUDGET`).

#### 5. `CodeChunkingAgent`
- **Class:** `CodeChunkingAgent`
- **File:** `backend/app/agents/code_chunking_agent.py`
- **Mode:** Tree-Sitter AST Parsing
- **Role:** Splits prioritized source files into semantic AST chunks (functions, classes, methods) using `tree-sitter` grammars across Python, JavaScript, TypeScript, Go, Java, C/C++, Ruby, and Rust. Includes fallback character-window chunking.

#### 6. `PatternDetector`
- **Class:** `PatternDetector`
- **File:** `backend/app/agents/pattern_detector.py`
- **Mode:** Deterministic Regex Scanner
- **Role:** Identifies architecturally significant code patterns: JWT authentication, raw SQL queries, external HTTP client calls (`requests`, `httpx`, `axios`), environment secret access, hardcoded API keys, subprocess executions, and developer debt comments (`TODO`, `FIXME`).

#### 7. `BugDetectionAgent`
- **Class:** `BugDetectionAgent`
- **File:** `backend/app/agents/bug_detection_agent.py`
- **Mode:** Static Analysis + Ruff Linter
- **Role:** Detects code smells (bare excepts, pass-only function bodies, deep nesting >4 levels, debug print statements, duplicate function logic). Integrates system `Ruff` linter for Python when installed.

#### 8. `DependencyGraphAgent`
- **Class:** `DependencyGraphAgent`
- **File:** `backend/app/agents/dependency_graph_agent.py`
- **Mode:** AST & Import Parser
- **Role:** Parses import statements across the entire repository to construct a directed dependency graph (`nodes`, `edges`, `in-degree centrality`, `circular dependency cycles`).

#### 9. `CodeAnalysisAgent` (Orchestrator)
- **Class:** `CodeAnalysisAgent`
- **File:** `backend/app/agents/code_analysis_agent.py`
- **Mode:** Hybrid Async Orchestrator
- **Role:** Orchestrates file prioritization, tree-sitter chunking, pattern/bug/dependency detection, and manages batching of local Ollama calls: Phase A (`qwen2.5-coder:7b` chunk summaries) and Phase B (`llama3.1:8b` hierarchical file/module reduces). Generates vector embeddings.

---

### Phase 3: High-Level Reasoning & Report Generation

#### 10. `ReportGenerationAgent`
- **Class:** `ReportGenerationAgent`
- **File:** `backend/app/agents/report_generation_agent.py`
- **Mode:** Schema Aggregator & Groq Interface
- **Role:** Constructs a strict, privacy-safe facts payload (<32 KB, zero raw code), submits it to Groq (`openai/gpt-oss-20b`), receives architectural reasoning (overview, complexity, workflows, key tech, confidence score), and persists the report to PostgreSQL and disk.

---

### Phase 4: Enterprise Intelligence & Quality Audits (V2)

#### 11. `ChangeImpactAnalysisAgent`
- **Class:** `ChangeImpactAnalysisAgent`
- **File:** `backend/app/agents/change_impact_agent.py`
- **Mode:** Graph Traversal Blast-Radius Calculator
- **Role:** Simulates modifying a specific file, computing direct/transitive dependent files, impacted REST APIs, and assigning a risk level (`Low`, `Medium`, `High`, `Critical`).

#### 12. `ArchitectureDriftAgent`
- **Class:** `ArchitectureDriftAgent`
- **File:** `backend/app/agents/architecture_drift_agent.py`
- **Mode:** Clean Architecture Auditor
- **Role:** Audits codebase against clean architecture rules, flagging layer violations (e.g. database calls in controllers), circular import cycles, orphaned files, and monolithic file smells.

#### 13. `AIProjectOnboardingAgent`
- **Class:** `AIProjectOnboardingAgent`
- **File:** `backend/app/agents/project_onboarding_agent.py`
- **Mode:** Onboarding Generator
- **Role:** Generates an ordered developer reading path (key entry files to inspect first) and interactive comprehension quizzes based on the repository's real architecture.

#### 14. `RepositoryHealthScoreAgent`
- **Class:** `RepositoryHealthScoreAgent`
- **File:** `backend/app/agents/repository_health_agent.py`
- **Mode:** Weighted Multi-Metric Scorer
- **Role:** Calculates an overall 0–100 repository health score with category breakdowns: Maintainability, Test Coverage, Architectural Hygiene, and Documentation.

#### 15. `TechnicalDebtPrioritizationAgent`
- **Class:** `TechnicalDebtPrioritizationAgent`
- **File:** `backend/app/agents/technical_debt_agent.py`
- **Mode:** Debt Backlog Ranker
- **Role:** Builds a prioritized technical debt backlog ranked by business impact, estimated fix effort in hours, and risk level.

---

### Phase 5: AI Call Tracing & Feature Extraction (V3)

#### 16. `ExecutionFlowAgent`
- **Class:** `ExecutionFlowAgent`
- **File:** `backend/app/agents/execution_flow_agent.py`
- **Mode:** Deterministic AST Call Graph Visualizer
- **Role:** Visualizes request/function execution paths starting from API endpoints down to database queries (`session.query`, `execute`, `filter`), external HTTP calls (`requests`, `httpx`, `axios`), and handled exceptions without executing any code.

#### 17. `FeatureExtractionAgent`
- **Class:** `FeatureExtractionAgent`
- **File:** `backend/app/agents/feature_extraction_agent.py`
- **Mode:** Zero-Rescanning Feature Discoverer
- **Role:** Discovers business feature domains (Authentication, Payment, User Management, Analytics, AI/ML, etc.) by grouping existing API inventory, controllers, services, models, DB tables, and environment variables from `.env.example`.

#### 18. `CrossRepoDuplicateAgent`
- **Class:** `CrossRepoDuplicateAgent`
- **File:** `backend/app/agents/cross_repo_duplicate_agent.py`
- **Mode:** Multi-Dimensional Jaccard Scorer
- **Role:** Compares two analyzed repositories across 5 dimensions (API, Code, Architecture, Module, Feature). Detects near-identical clones at a 98% threshold, issues informational banners (non-legal), and classifies relationships (*Near-Identical Copy*, *Likely Cloned Repository*, *Shared Template*, *Fork*, *Shared Architecture*, or *Independent Repository*).

---

### Phase 6: Interactive Q&A Engine

#### 19. `QAChatAgent`
- **Class:** `QAChatAgent`
- **File:** `backend/app/agents/qa_chat_agent.py`
- **Mode:** 3-Tier RAG Retrieval Engine
- **Role:** Powers plain-English Q&A over the codebase using a three-tier retrieval hierarchy:
  1. **Pinned Retrieval:** Exact `file:line` references (score = 1.0)
  2. **Semantic Retrieval:** Cosine vector search over chunk embeddings
  3. **Targeted Symbol Retrieval:** Exact AST symbol substring fallback
  Generates grounded answers via Groq with exact file and line-range citations.

---

## LLM Architecture & Model Delegation

AutoQA Agent employs a **hybrid local + cloud LLM model delegation**:

| Tier | Model | Location | Responsibility |
|---|---|---|---|
| **Code Summary Model** | `qwen2.5-coder:7b` | Ollama (Local) | AST chunk-level code semantics and function summarisation |
| **Text & Reduce Model** | `llama3.1:8b` | Ollama (Local) | README summarisation, file/module reduce, feature enrichment |
| **Cloud Text Engine** | `openai/gpt-oss-120b` | Groq API (Cloud) | High-level architecture reasoning & text analysis |
| **Cloud Code Engine** | `qwen/qwen3.6-27b` | Groq API (Cloud) | Code-specialized cloud inference |
| **Cloud Report/Chat Engine** | `openai/gpt-oss-20b` | Groq API (Cloud) | Report generation, RAG chat & rate-limit fallback |
| **Embedding Engine** | `nomic-embed-text` | Ollama (Local) | Vector embeddings for code chunk semantic search |

> **Graceful Degradation:** If Ollama is offline, local code insights degrade gracefully while Groq generates high-level analysis from deterministic facts. If Groq is offline, deterministic fallback analysis reports are returned.

---

## Groq Safety Boundary (Zero Code Leakage)

**Groq never receives raw source code during repository analysis.**

- **Sent to Groq:** Tech stack lists, API endpoint paths/methods, 1-sentence module summaries, pattern descriptions, issue count totals.
- **Never sent to Groq:** Raw code chunks, source file contents, full linter issue lists.

*Note:* Interactive Q&A chat sends user-requested, relevant code snippets to Groq to answer specific questions.

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | FastAPI 0.115 · Python 3.11+ · Pydantic V2 · Uvicorn |
| **Frontend** | React 18 · Vite · Vanilla CSS · Lucide Icons |
| **Database** | PostgreSQL · SQLAlchemy 2.0 ORM |
| **Local LLM** | Ollama (`qwen2.5-coder:7b`, `llama3.1:8b`, `nomic-embed-text`) |
| **Cloud LLM** | Groq API (`openai/gpt-oss-120b`, `qwen/qwen3.6-27b`, `openai/gpt-oss-20b`) |
| **AST Parsing** | `tree-sitter` · Python `ast` module |
| **Static Analysis** | Ruff (Python linter) |
| **Visualisation** | D3-force (Dependency Graph) · Custom SVG/CSS (Execution Flow) |
| **PDF Export** | ReportLab |
| **Testing** | Pytest (68 unit & integration tests) |

---

## Folder Structure

```text
AutoQA_Agent/
├── backend/
│   ├── app/
│   │   ├── agents/                           # All 19 Decoupled Agents
│   │   │   ├── api_discovery_agent.py        # Agent 3  — REST endpoint scanner
│   │   │   ├── architecture_drift_agent.py   # Agent 12 — Clean architecture auditor
│   │   │   ├── bug_detection_agent.py        # Agent 7  — Static smell & Ruff detector
│   │   │   ├── change_impact_agent.py        # Agent 11 — Blast-radius calculator
│   │   │   ├── code_analysis_agent.py        # Agent 9  — Async pipeline orchestrator
│   │   │   ├── code_chunking_agent.py        # Agent 5  — tree-sitter AST chunker
│   │   │   ├── cross_repo_duplicate_agent.py # Agent 18 — Clone & multi-dim compare
│   │   │   ├── dependency_graph_agent.py    # Agent 8  — Import graph & cycle finder
│   │   │   ├── execution_flow_agent.py       # Agent 16 — AST static call graph tracer
│   │   │   ├── feature_extraction_agent.py   # Agent 17 — Business feature discoverer
│   │   │   ├── file_prioritization_agent.py # Agent 4  — Scored file ranker & budget
│   │   │   ├── pattern_detector.py           # Agent 6  — Regex pattern scanner
│   │   │   ├── project_onboarding_agent.py   # Agent 13 — Reading path & quiz generator
│   │   │   ├── qa_chat_agent.py              # Agent 19 — 3-Tier RAG chat engine
│   │   │   ├── report_generation_agent.py   # Agent 10 — Report builder & JSON saver
│   │   │   ├── repository_analysis_agent.py # Agent 1  — Git clone & metadata extractor
│   │   │   ├── repository_health_agent.py    # Agent 14 — 0-100 health scoring model
│   │   │   ├── technical_debt_agent.py       # Agent 15 — Tech debt backlog ranker
│   │   │   └── tech_stack_agent.py           # Agent 2  — Deterministic stack detector
│   │   ├── api/
│   │   │   └── routes.py                     # FastAPI REST Endpoints
│   │   ├── core/
│   │   │   ├── config.py                     # Pydantic Settings (.env reader)
│   │   │   └── logging_config.py             # Structured Logger
│   │   ├── db/
│   │   │   ├── models.py                     # SQLAlchemy ORM Models
│   │   │   └── session.py                    # DB Session Factory
│   │   ├── repositories/
│   │   │   └── analysis_repository.py        # DB CRUD Layer
│   │   ├── schemas/
│   │   │   ├── analysis.py                   # RepositoryAnalysisReport model
│   │   │   └── v2_schemas.py                 # V2 & V3 Data Schemas
│   │   └── services/
│   │       ├── analysis_service.py           # Top-level Orchestrator
│   │       ├── embedding_service.py         # Ollama Embedding Wrapper
│   │       ├── groq_service.py              # Groq API Client Singleton
│   │       ├── pipeline_status_service.py    # Real-time Stage Status Tracker
│   │       └── vector_search_service.py     # Cosine Vector Search Engine
│   ├── tests/                                # Pytest Test Suite
│   │   ├── test_cross_repo_clone_detection.py# Clone threshold & relationship tests
│   │   ├── test_execution_flow_agent.py      # Call tracer & AST extraction tests
│   │   ├── test_feature_extraction_agent.py  # Feature domain & env matching tests
│   │   ├── test_groq_boundary.py             # Privacy safety boundary tests
│   │   └── test_qa_chat_agent.py             # RAG retrieval & citations tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.js                     # API Client Fetch Wrappers
│   │   ├── components/
│   │   │   ├── CrossRepoCompareModal.jsx     # Clone Detection & Comparison Modal
│   │   │   ├── ExecutionFlowTab.jsx          # Execution Call Graph Visualizer
│   │   │   ├── FeatureMapTab.jsx             # Business Feature Map Cards
│   │   │   ├── ImpactAnalysisTab.jsx         # Blast Radius Calculator
│   │   │   ├── ArchitectureDriftTab.jsx      # Clean Architecture Violations
│   │   │   ├── ProjectOnboardingTab.jsx      # Developer Onboarding & Quizzes
│   │   │   ├── RepositoryHealthTab.jsx       # Health Gauge & Category Breakdown
│   │   │   ├── TechnicalDebtTab.jsx          # Prioritized Debt Backlog
│   │   │   ├── QAChatPanel.jsx               # RAG Chat Panel
│   │   │   ├── DependencyGraphPanel.jsx      # Interactive D3 Graph
│   │   │   ├── BugReportPanel.jsx            # Bug & Smell Browser
│   │   │   └── ArchitectureTab.jsx           # Architectural Layer Breakdown
│   │   └── App.jsx                           # Main React App & Tab Bar
│   └── package.json
└── README.md
```

---

## Prerequisites & Ollama Setup

1. **Python 3.11+** and **Node.js 18+**
2. **PostgreSQL** running locally or remotely
3. **Git** installed on PATH
4. **Ollama** running locally with required models:

```bash
# Pull required local LLM models
ollama pull llama3.1:8b          # Text model — README & module reduces
ollama pull qwen2.5-coder:7b     # Code model — Chunk summarization
ollama pull nomic-embed-text     # Embedding model — Vector RAG search
```

---

## Setup & Quickstart Guide

### Backend Setup

```bash
cd AutoQA_Agent/backend

# Create & activate virtual environment
python -m venv venv
source venv/bin/activate        # Linux / macOS
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Set GROQ_API_KEY and DATABASE_URL in .env

# Start FastAPI server
uvicorn app.main:app --reload
```

Backend: `http://localhost:8000` | Swagger Docs: `http://localhost:8000/docs`

---

### Frontend Setup

```bash
cd AutoQA_Agent/frontend
npm install
npm run dev
```

Frontend: `http://localhost:5173`

---

### PostgreSQL Database

```sql
CREATE DATABASE autoqa_agent;
```

SQLAlchemy automatically creates all required tables (`analysis_reports`, `summary_cache`, `chunk_embeddings`) on backend startup.

---

## Environment Variables

Read from `backend/.env`:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://...` | PostgreSQL connection string |
| `GROQ_API_KEY` | *(required)* | Groq API key for cloud reasoning |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_TEXT_MODEL` | `llama3.1:8b` | Model for text summarisation |
| `OLLAMA_CODE_MODEL` | `qwen2.5-coder:7b` | Model for code chunk summarisation |
| `MAX_FILES_TO_ANALYZE` | `50` | Maximum files analyzed per repo |
| `MAX_CODE_TOKEN_BUDGET` | `40000` | Token character budget cap |

---

## API Endpoints Reference

### Pipeline & Analysis
- `POST /analyze-repository` — Submit GitHub URL & execute 19-agent pipeline
- `GET /analysis/{analysis_id}` — Retrieve full report JSON
- `GET /analysis/{analysis_id}/status` — Poll real-time 19-stage progress
- `GET /analyses` — List all stored reports

### V3 Specialized Endpoints
- `GET /analysis/{analysis_id}/execution-flow` — Retrieve AST call graph flows
- `GET /analysis/{analysis_id}/feature-map` — Retrieve business feature map
- `POST /compare-repositories` — Multi-dimensional comparison & clone detection

### Enterprise V2 Endpoints
- `GET /analysis/{analysis_id}/impact` — Change impact blast-radius calculator
- `GET /analysis/{analysis_id}/drift` — Clean architecture drift audit
- `GET /analysis/{analysis_id}/onboarding` — Developer onboarding guide & quizzes
- `GET /analysis/{analysis_id}/health` — Repository health scores
- `GET /analysis/{analysis_id}/technical-debt` — Prioritized technical debt backlog

### Interactive Tools
- `POST /analysis/{analysis_id}/chat` — Execute 3-Tier RAG code Q&A
- `GET /analysis/{analysis_id}/pdf` — Export formatted PDF report

---

## Frontend UI Panels & Navigation

| Tab | Icon | Key Features |
|---|---|---|
| **Q&A Chat** | `MessageSquare` | 3-tier RAG chat with file:line citations and code block answers |
| **Dependency Graph** | `Network` | Interactive D3 force graph with circular import highlights |
| **Bug Report** | `Bug` | Static smell detector & Ruff linter issue browser |
| **Architecture** | `GitBranch` | Layer-by-layer architectural file breakdown |
| **Impact Analysis** | `Layers` | File modification blast-radius and risk analyzer |
| **Arch Drift** | `ShieldAlert` | Architecture rule violation auditor |
| **Onboarding** | `BookOpen` | Step-by-step reading path & interactive quizzes |
| **Health Score** | `Activity` | 0–100 health gauge & category breakdown |
| **Tech Debt** | `Wrench` | Prioritized technical debt backlog with fix hours |
| **Execution Flow** *(V3)* | `GitGraph` | Interactive AST call graph visualizer with node type filtering |
| **Feature Map** *(V3)* | `Map` | Business feature cards with APIs, DB tables, and env vars |
| **Cross-Repo Compare** | `GitCompare` | Multi-dimensional comparison modal & clone alert banner |

---

## Running Unit & Integration Tests

The test suite contains **68 unit and integration tests** covering all agent logic:

```bash
cd AutoQA_Agent/backend

# Run V3 agent tests (Execution Flow, Feature Map, Clone Detection)
python -m pytest tests/test_execution_flow_agent.py tests/test_feature_extraction_agent.py tests/test_cross_repo_clone_detection.py -v -p no:asyncio

# Run full backend test suite
python -m pytest tests/ -v -p no:asyncio
```
