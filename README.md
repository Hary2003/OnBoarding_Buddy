# 🚀 OnBoarding Buddy

[![CI Pipeline](https://github.com/Hary2003/OnBoarding_Buddy/actions/workflows/ci.yml/badge.svg)](https://github.com/Hary2003/OnBoarding_Buddy/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-2.0.0-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12-blue?style=flat&logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Production%20Ready-2496ED?style=flat&logo=docker)](https://docker.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AI-powered repository intelligence and agentic codebase exploration platform for developers.**

OnBoarding Buddy helps developers understand, navigate, and contribute to unfamiliar codebases.

Instead of manually reading hundreds of disconnected files, developers can ingest a GitHub repository or local project and use OnBoarding Buddy to analyze its architecture, dependencies, active development areas, security findings, contribution opportunities, and relevant code — all through grounded AI assistance.

---

## ✨ Why OnBoarding Buddy?

Understanding an unfamiliar codebase is one of the biggest sources of developer onboarding friction.

Developers often need to figure out:

* Where does the application start?
* How are modules connected?
* Where is a particular feature implemented?
* Which files are actively changing?
* What would be affected if I modify this module?
* Which tests should I update?
* Are there obvious security or architectural issues?
* Where could I contribute to an open-source project?

Traditional documentation can be incomplete or outdated, while generic LLMs lack repository-specific context.

**OnBoarding Buddy combines static code intelligence, dependency analysis, retrieval, and grounded LLM reasoning to solve this problem.**

---

# 🧠 Core Capabilities

### 📂 Repository Intelligence

Analyze GitHub repositories or local directories without executing the repository code.

* Repository ingestion
* Multi-language source analysis
* AST-based symbol extraction
* Function/class/method discovery
* Git activity analysis
* Recently modified file ranking
* Entry-point detection

### 🕸️ Dependency & Architecture Intelligence

Build a structured representation of how the repository is connected.

* Internal dependency resolution
* Directed dependency graph
* Import analysis
* In-degree / out-degree analysis
* Core module detection
* Leaf / utility module detection
* Entry-point identification
* Circular dependency detection
* Architecture summaries

Interactive dependency visualization makes it easier to understand large codebases.

### 🔍 Explainable Context Retrieval

Instead of sending an entire repository to an LLM, OnBoarding Buddy retrieves the most relevant code.

The retrieval engine combines:

* File/path matching
* Symbol matching
* Docstring matching
* Dependency relationships
* Source-code matching
* Module importance
* Git activity

Every retrieval result contains explainable relevance signals.

### 🤖 Grounded AI Assistant

Ask natural-language questions about the repository.

Examples:

> "Where is database initialization handled?"

> "How does authentication work?"

> "How does an API request flow through the application?"

> "Which files should I modify to add a new endpoint?"

The assistant uses retrieved repository context and provides source-attributed answers.

The system is explicitly designed to avoid presenting unsupported information as repository fact.

### 🎯 Contribution Intelligence

Turn issues and feature requests into evidence-backed contribution plans.

Example:

> "Add PostgreSQL connection pooling."

OnBoarding Buddy can identify:

* Relevant modules
* Relevant symbols
* Potentially affected files
* Dependency impact
* Configuration files
* Related tests
* Recommended implementation areas
* Confidence and supporting evidence

### 🔐 Repository Audit & Security Scanner

Perform static repository audits for potential issues including:

* Hardcoded secrets
* Unsafe `eval()` / `exec()` usage
* Shell execution risks
* Disabled SSL verification
* Unsafe deserialization patterns
* Circular dependencies
* High-centrality / large modules
* Missing test coverage for important modules

Findings are presented as **static-analysis findings/potential issues**, rather than automatically treating heuristic matches as confirmed vulnerabilities.

### 🧑‍💻 Agentic Repository Exploration

The M6 architecture adds an agent capable of autonomously investigating complex developer questions.

Instead of performing a single retrieval operation, the agent can:

```text
Developer Question
       ↓
Agent Planner
       ↓
Select Repository Tool
       ↓
Execute Tool
       ↓
Observe Result
       ↓
Re-plan
       ↓
Investigate Further
       ↓
Collect Evidence
       ↓
Grounded Answer
```

Available repository intelligence tools include:

* Repository search
* File inspection
* Symbol inspection
* Reference discovery
* Dependency analysis
* Dependant analysis
* Entry-point detection
* Test discovery
* Architecture inspection
* Git activity analysis

The agent is designed as a **read-only investigation system** and does not modify repositories or execute arbitrary repository code.

---

# 🏗️ Architecture

```text
                         Developer
                             │
                             ▼
                  ┌────────────────────┐
                  │   Web Dashboard    │
                  └─────────┬──────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │    FastAPI API     │
                  └─────────┬──────────┘
                            │
             ┌──────────────┼───────────────┐
             │              │               │
             ▼              ▼               ▼
       Repository       Retrieval      Contribution
       Intelligence      Engine         Intelligence
             │              │               │
             └──────────────┼───────────────┘
                            │
                            ▼
                  ┌────────────────────┐
                  │ Agentic Explorer   │
                  │      M6            │
                  └─────────┬──────────┘
                            │
                            ▼
                     ┌────────────┐
                     │ Groq / LLM │
                     └─────┬──────┘
                           │
                           ▼
                 Grounded AI Response
```

---

# 🧩 Milestone Architecture

## M1 — Repository Intelligence ✅

```text
Repository
   ↓
Ingestion
   ↓
Multi-language parsing
   ↓
AST / symbol extraction
   ↓
Git activity analysis
```

## M2 — Dependency & Architecture Intelligence ✅

```text
Imports
   ↓
Dependency resolution
   ↓
Directed graph
   ↓
Centrality
   ↓
Cycles
   ↓
Entry points
   ↓
Architecture analysis
```

## M3 — Context Retrieval Engine ✅

```text
Developer Query
      ↓
Query Analysis
      ↓
Candidate Retrieval
      ↓
Explainable Ranking
      ↓
Dependency Expansion
      ↓
Context Builder
```

## M4 — Grounded AI Assistant ✅

```text
Question
   ↓
M3 Retrieval
   ↓
Context
   ↓
Groq
   ↓
Grounded Answer
   ↓
Source Attribution
```

## M5 — Contribution & Vulnerability Intelligence ✅

```text
Issue / Feature Request
        ↓
Issue Analysis
        ↓
Code Retrieval
        ↓
Impact Analysis
        ↓
Test Detection
        ↓
Configuration Analysis
        ↓
Contribution Plan
```

Also includes static repository auditing for potential security, architecture, and test-coverage issues.

## M6 — Agentic Repository Exploration ✅

```text
Developer Question
        ↓
Agent Planner
        ↓
Repository Tools
        ↓
Observations
        ↓
Dynamic Re-planning
        ↓
Evidence Collection
        ↓
Grounded Response
```

## M7 — Pull Request Intelligence & Code Review Agent ✅

```text
Pull Request Diff / Unified Patch
        ↓
Git Diff Engine (Added/Removed lines, Hunks)
        ↓
Symbol Extraction & Change Classification
        ↓
Architecture Blast Radius (Layers, Entry Points, Couplings)
        ↓
Test Impact Intelligence (Missing Tests, Scenarios, Edge Cases)
        ↓
Diff-Level Security Scanner (Secrets, Eval, Shell, SQLi, XSS, SSRF)
        ↓
Review Comment Generator & PR Review Agent
        ↓
Approval Verdict (APPROVE / REQUEST_CHANGES) & Evidence-Backed Comments
```

---

# 🛠️ Technology Stack

### Backend

* Python
* FastAPI
* Pydantic
* Uvicorn

### AI

* Groq API
* LLM-powered grounded reasoning
* Structured context generation
* Agentic tool orchestration

### Code Intelligence

* Python `ast`
* Multi-language parsing / pattern extraction
* GitPython
* Dependency graph analysis
* Static analysis

### Frontend

* HTML5
* CSS
* JavaScript
* Prism.js
* vis-network

### Development

* Git
* GitHub
* Python `unittest`
* Environment-based configuration

---

# 🌍 Supported Languages

Current parsing and dependency analysis includes:

* Python
* JavaScript
* TypeScript
* Go
* Rust
* Java
* C
* C++

Python uses native AST analysis, while other languages use language-specific parsing and pattern-based extraction where applicable.

---

# 🚀 Getting Started

## 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd onboarding-buddy
```

## 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it.

### Windows

```bash
.venv\Scripts\activate
```

### Linux / macOS

```bash
source .venv/bin/activate
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Configure environment variables

### Local Development
Copy `.env.example` to `.env` and set your local keys:

```bash
cp .env.example .env
```

```env
ENVIRONMENT=development
DEBUG=true
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b
HOST=127.0.0.1
PORT=8000
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173,http://127.0.0.1:5173
```

> **Security Rule**: The `.env` file is strictly for local development and is ignored by `.gitignore`. **Never commit `.env` or API keys to Git.**

### Production Deployment & Secrets Management

In production (e.g. AWS, Render, Railway, Fly.io, Kubernetes, Docker):
1. **No `.env` file**: Do not mount or bundle a `.env` file. The application automatically falls back to process environment variables.
2. **Secrets as Deployment Secrets**: Store `GROQ_API_KEY` and `DATABASE_URL` securely in your platform's secret manager (e.g., Kubernetes Secret, AWS Secrets Manager, GitHub Deployment Secrets).
3. **Production Environment Variables**:
   - `ENVIRONMENT=production`
   - `DEBUG=false` (disables internal stack trace exposure and auto-reload)
   - `HOST=0.0.0.0`
   - `PORT=8000`
   - `DATABASE_URL=postgresql://user:pass@ep-xyz-pooler.neon.tech/neondb?sslmode=require`
   - `DB_POOL_SIZE=10`, `DB_MAX_OVERFLOW=20`, `DB_POOL_RECYCLE=300`
   - `CORS_ALLOWED_ORIGINS=https://app.yourdomain.com` (strictly restrict allowed origins; wildcard with credentials is blocked in production)
   - `ENABLE_DOCS=false` (hides Swagger/Redoc endpoints in production)
   - `LOG_LEVEL=INFO`
4. **Secure Error Responses**: All unhandled 5xx exceptions and system errors return sanitized JSON responses (`{"detail": "An internal server error occurred."}`) rather than leaking server filepaths or tracebacks.

---

# 🐘 PostgreSQL Persistence & Database Architecture

OnBoarding Buddy uses **Neon Serverless PostgreSQL** for persistent, scalable state across server restarts and horizontally scaled replicas:

### 1. Persistent Data Entities
- **`repositories`**: Stores parsed AST indices, language breakdowns, module centrality metrics, and architecture summaries.
- **`conversation_turns`**: Stores multi-turn chat sessions and evidence source attributions.
- **`pr_reviews`**: Stores static diff security audits, risks, and inline comments.
- **`audit_reports`**: Stores repository health and contribution intelligence opportunity audits.

### 2. Connection Pooling & Serverless Optimization
- `pool_pre_ping=True`: Proactively verifies connection liveness, gracefully handling Neon's automatic scale-to-zero compute wakeups.
- `pool_size=10`, `max_overflow=20`: Manages concurrent client requests through pgBouncer/pooler endpoints.
- `pool_recycle=300`: Periodically recycles stale serverless connections.

### 3. Proper Indexes
- B-tree indexes on `session_id`, `repo_name`, `created_at`, and `updated_at`.
- Composite index `(session_id, updated_at)` for high-throughput session lookups.

### 4. Database Migrations (Alembic)
Schema evolution is tracked and versioned using **Alembic**, ensuring seamless synchronization between SQLAlchemy ORM models and Neon PostgreSQL:
- **Automatic Execution on Startup**: When `server.py` or test suites initialize via `init_db()`, pending migrations are applied automatically and idempotently.
- **Manual Migration Command**:
  ```bash
  alembic upgrade head
  # or using the migration utility:
  python migrate.py
  ```
- **Key Entities & Fields**:
  - `pr_reviews`: Includes `verdict` (indexed), `risks_count`, `executive_summary`, `developer_summary`, and `full_analysis`.
  - `audit_reports`: Includes `total_opportunities`, `critical_count`, `high_count`, `medium_count`, `low_count`, `summary_narrative`, and `report_data`.

### 5. Backup & Disaster Recovery Strategy
- **Neon Point-in-Time Recovery (PITR)**: Provides continuous automated backup retention with recovery to any second.
- **Instant Branching**: Enables zero-copy database branches for staging, migrations, and pre-deployment testing.
- **Logical Backups**:
  ```bash
  pg_dump "$DATABASE_URL" -F c -b -v -f onboarding_buddy_backup.dump
  ```

---

## 5. Start the server

### Development Mode
```bash
python app.py
# or: uvicorn server:app --reload
```

### Production Mode
```bash
python app.py
# or: uvicorn server:app --host 0.0.0.0 --port 8000 --no-reload
```

Open:

```text
http://127.0.0.1:8000
```

---

# 🐳 Docker & Frontend Containerization

OnBoarding Buddy features a production-grade multi-container architecture orchestrated via Docker Compose:

```
┌─────────────────────────────────────────────────────────────┐
│                 Client Browser / Developer                  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                     Port 80   │
                               ▼
       ┌───────────────────────────────────────────────┐
       │   Frontend Container (Nginx 1.27 Alpine)      │
       │   - Serves HTML5 / CSS / JS UI Assets        │
       │   - Rewrites & caches /static/ bundles        │
       │   - Enforces Security Headers & Gzip          │
       │   - Healthcheck: /healthz                     │
       └───────────────────────┬───────────────────────┘
                               │
             Internal Network  │ proxy_pass /api/ -> backend:8000
             (onboarding-net)  │ proxy_pass /docs -> backend:8000
                               ▼
       ┌───────────────────────────────────────────────┐
       │   Backend Container (Python 3.12 FastAPI)     │
       │   - AST Intelligence & Dependency Parsing     │
       │   - Groq AI Reasoning & Agentic Tools         │
       │   - Alembic & Neon PostgreSQL Engine          │
       │   - Healthcheck: /api/health                  │
       └───────────────────────┬───────────────────────┘
                               │
                               ▼
       ┌───────────────────────────────────────────────┐
       │          Neon Serverless PostgreSQL           │
       └───────────────────────────────────────────────┘
```

### 1. Quickstart with Docker Compose

Build and launch the full stack (backend + frontend reverse proxy) with one command:

```bash
docker compose up --build
```

Access the application:
* **Frontend Web Application**: [http://localhost](http://localhost) (Port 80)
* **FastAPI Backend & Interactive Swagger UI**: [http://localhost/docs](http://localhost/docs) (proxied) or direct at [http://localhost:8000/docs](http://localhost:8000/docs)
* **Frontend Container Healthcheck**: [http://localhost/healthz](http://localhost/healthz)
* **Backend Health & Diagnostics**: [http://localhost/api/health](http://localhost/api/health)

To stop services:
```bash
docker compose down
```

### 2. Standalone Frontend Docker Container

Build the frontend Docker image directly:

```bash
docker build -t onboarding-buddy-frontend:latest ./frontend
```

Run the container:

```bash
docker run -d -p 3000:80 --name onboarding-frontend onboarding-buddy-frontend:latest
```

### 3. Local Development with Live Hot-Reloading

#### Option A: Docker Compose Dev Override
Mount local source directories for hot-reloading across backend and frontend containers:
```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

#### Option B: Vite Frontend Dev Server
Run Vite locally with instant Hot Module Replacement (HMR) and automatic `/api` proxying to FastAPI backend:
```bash
cd frontend
npm install
npm run dev
```

---

# 🧪 Testing

Run the complete test suite:

```bash
python -m unittest discover -s tests
```

The current implementation has **131 automated tests covering M1–M7** (including 36 dedicated M6 agentic exploration tests and 34 dedicated M7 PR intelligence tests), with the full suite passing.

The test suite covers:

* Repository ingestion
* AST analysis
* Dependency graphs
* Circular dependencies
* Retrieval
* Context generation
* Grounded AI responses
* Source attribution
* Multi-turn conversation
* Contribution intelligence
* Change impact analysis
* Test detection
* Configuration detection
* Static repository auditing
* Security/debt heuristics
* Agent architecture, planning, and memory
* Read-only repository tools (10 tools)
* Dynamic tool selection and re-planning
* Trace event generation and hard limits
* Grounded answer synthesis without hallucination
* Git diff parsing and unified hunk processing
* Change classification (feature, bugfix, refactor, config, test, doc)
* Architectural layer violations and god module alerts
* Test impact intelligence and scenario recommendations
* Diff-level security vulnerability scanning (secrets, eval, shell, injection, SSL, deserialization)
* PR Review Agent and evidence-backed inline review comments
* Agent PR investigation tools (`get_pr_diff`, `get_changed_files`, `get_changed_symbols`, etc.)
* FastAPI PR endpoints (`/api/pr/analyze`, `/api/pr/review`, `/api/pr/summary`)
* Enterprise Markdown & Report Export Engine (`/api/export/guide`, `/api/export/architecture`, `/api/export/audit`)
* Architectural blueprint exporter with dynamic Mermaid diagram rendering
* Automated CI/CD pipeline with multi-version testing, flake8 linting, security audits, and Docker verification

---

# 🔄 Example Workflow

### Analyze a repository

```text
GitHub URL / Local Directory
            ↓
      Repository Ingestion
            ↓
      Code Intelligence
            ↓
      Dependency Analysis
```

### Ask a question

```text
"Where is database initialization handled?"
            ↓
       Query Analyzer
            ↓
       Relevant Files
            ↓
    Dependency Expansion
            ↓
       Context Builder
            ↓
          Groq
            ↓
     Grounded Answer
```

### Analyze an issue

```text
"Add OAuth authentication"
            ↓
       Issue Analyzer
            ↓
      Relevant Code
            ↓
      Impact Analysis
            ↓
       Related Tests
            ↓
      Configuration
            ↓
   Contribution Plan
```

### Explore with the agent

```text
"How does authentication work?"
            ↓
       Agent Planner
            ↓
    Search Repository
            ↓
     Inspect Symbols
            ↓
    Find References
            ↓
   Trace Dependencies
            ↓
      Find Tests
            ↓
    Gather Evidence
            ↓
     Final Answer
```

---

# 🔒 Security & Design Principles

OnBoarding Buddy follows several important design principles:

### Grounded AI

LLM responses should be based on retrieved repository evidence rather than unsupported assumptions.

### Explainable Retrieval

Retrieval results expose the signals that contributed to their ranking.

### Evidence-Based Recommendations

Contribution recommendations are linked to repository files, symbols, dependencies, and tests where evidence exists.

### Read-Only Agent

The agentic exploration layer is designed for repository investigation and does not modify the codebase.

### No Repository Execution

Repository analysis does not require executing arbitrary target-repository code.

---

# 📈 Future Roadmap

* [x] Repository ingestion
* [x] Multi-language code analysis
* [x] Dependency graph
* [x] Architecture intelligence
* [x] Explainable retrieval
* [x] Grounded AI assistant
* [x] Contribution intelligence
* [x] Static repository auditing
* [x] Vulnerability/debt opportunity detection
* [x] Agentic repository exploration
* [x] Pull-request analysis & code review agent
* [x] Markdown & Mermaid architecture report export engine
* [x] Automated CI/CD pipeline with security and Docker validation
* [ ] Advanced semantic code retrieval
* [ ] GitHub issue integration
* [ ] Repository change tracking
* [ ] Cross-commit architectural analysis
* [ ] Advanced code-change impact prediction

---

# 💡 Project Philosophy

OnBoarding Buddy is built around a simple principle:

> **AI should reason over the codebase, not guess about it.**

The project combines deterministic software-engineering analysis with LLM reasoning:

```text
Static Analysis
      +
Repository Graph
      +
Explainable Retrieval
      +
LLM Reasoning
      +
Agentic Exploration
      =
Repository Intelligence
```

---

# 👨‍💻 Author

**Harisankar (Hary)**

AI Engineer | AI/ML | Agentic AI | Cloud

Built as a personal AI engineering project focused on repository intelligence, grounded AI systems, and developer tooling.
