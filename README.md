# 🚀 OnBoarding Buddy

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

## M6 — Agentic Repository Exploration 🚧

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

Create a `.env` file:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

**Never commit `.env` or API keys to GitHub.**

Use `.env.example` for public configuration documentation.

## 5. Start the server

```bash
uvicorn server:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

---

# 🧪 Testing

Run the complete test suite:

```bash
python -m unittest discover -s tests
```

The current implementation has **61 automated tests covering M1–M5**, with the full suite passing during M5 verification.

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
* FastAPI endpoints

M6 adds a separate agent test suite as agentic exploration is developed.

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
* [ ] Agentic repository exploration
* [ ] Advanced semantic code retrieval
* [ ] GitHub issue integration
* [ ] Pull-request analysis
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
