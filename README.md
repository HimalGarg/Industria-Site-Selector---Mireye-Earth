# 🏢 Industria Site Selector — Mireye Earth & 5-Agent Council

> **An enterprise-grade geospatial intelligence and multi-agent due diligence platform for industrial site selection.**

The **Industria Site Selector** is a heavily orchestrated, distributed intelligence platform designed to automate the deeply technical process of commercial real estate (CRE) due diligence. By unifying custom DOM-parsing browser extensions, a highly concurrent Python-based Multi-Agent architecture, and rigorous geospatial data pipelines, the system processes raw web listings into board-ready engineering and risk assessments.

---

## 🏗️ System Topology & Distributed Architecture

The platform operates across three decoupled layers, utilizing asynchronous event loops to pipe unformatted web data through a series of specialized micro-engines, geospatial caches, and autonomous decision nodes.

```text
┌──────────────────────────────────────────┐      ┌──────────────────────────────────────────┐
│          INGESTION & CAPTURE             │      │       OBSIDIAN EXECUTIVE DASHBOARD       │
│      (Chrome Manifest V3 Extension)      │      │       (React 18, Vite, TailwindCSS)      │
│ - Pluggable DOM Scrapers (Crexi/LoopNet) │      │ - Real-time WebSocket / REST Polling     │
│ - Bypasses SPA routing & obfuscation     │      │ - Tabbed Agent Audit UI & Memory States  │
└────────────────────┬─────────────────────┘      └────────────────────┬─────────────────────┘
                     │                                                 │
                     ▼                                                 ▼
┌────────────────────┴─────────────────────────────────────────────────┴─────────────────────┐
│                            FASTAPI ORCHESTRATION KERNEL                                    │
│       (Asynchronous REST API, State Machine, Semantic Router, SQLite Persistence)          │
└────┬────────────────────────┬───────────────────────────┬──────────────────────┬───────────┘
     │                        │                           │                      │
     ▼                        ▼                           ▼                      ▼
┌──────────────┐       ┌──────────────┐         ┌───────────────────┐    ┌───────────────┐
│  Mireye GIS  │       │ Cognitive    │         │ Regulatory Engine │    │ Radius Engine │
│  (58 Spatial │       │ Engine       │         │ (Municipal APIs & │    │ (Haversine    │
│   Layers)    │       │ (LLM Routing)│         │  Heuristic Logic) │    │  Vectors)     │
└──────────────┘       └──────────────┘         └───────────────────┘    └───────────────┘
```

---

## 🧠 Core Systems & Engineering Capabilities

### 1. 🏛️ The 5-Agent Autonomous Council
When a site enters the evaluation pipeline, the orchestration kernel dispatches an `asyncio.gather()` routine to a concurrent council of specialized micro-agents. Each agent computes localized feasibility metrics using physical ground-truth data from Mireye Earth GIS:

```text
                        [ Trigger: Distributed Evaluation Subroutine ]
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │    Data Aggregation & Spatial Normalization  │
                       │ (Mireye GIS: Elevation, Flood, Power, Water) │
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                       ┌──────────────────────────────────────────────┐
                       │     Concurrent Multi-Agent Worker Pool       │
                       │              `asyncio.gather()`              │
                       └─┬─────────┬─────────┬──────────┬───────────┬─┘
                         │         │         │          │           │
           ┌─────────────┴┐ ┌──────┴───────┐ │ ┌────────┴───────┐ ┌─┴────────────┐
           ▼              ▼ ▼              ▼ ▼ ▼                ▼ ▼              ▼
  ┌────────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
  │ ⚡ Energy Agent │ │ 💧 Water Agent │ │🏔️ Surface Agent│ │🚛Transport Agt│ │⚠️ Risk Agent  │
  │ Calculates grid│ │ Computes PWSID│ │ Computes slope│ │ Computes drive│ │ Cross-checks  │
  │ capacity, line │ │ bounds, runoff│ │ vectors & soil│ │ time matrices │ │ FEMA, USTs, & │
  │ distances & kV.│ │ & sewer limits│ │ drainage rates│ │ & port access.│ │ hazard zones. │
  └────────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
           │                 │                 │                 │                 │
           └─────────────────┴─────────────────┼─────────────────┴─────────────────┘
                                               │
                                               ▼
                       ┌──────────────────────────────────────────────┐
                       │   👑 Master Synthesizer & Contradiction Node │
                       │ - Executes deterministic cross-domain diffing│
                       │ - Normalizes outputs to a 0-100 scalar score │
                       │ - Flags seller listing vs. GIS contradictions│
                       └──────────────────────┬───────────────────────┘
                                              │
                                              ▼
                                 [ Pipeline Output to UI State ]
```

### 2. ⚖️ Autonomous Regulatory & Compliance Engine
Instead of relying on generalized AI models, the compliance engine programmatically interrogates real-world civic data structures:
- **Dynamic Municipal Interrogation:** Hooks into open-data endpoints (e.g., Socrata API) to query active building permits, certificates of occupancy, and open code violations.
- **Heuristic Regulatory Parsing:** In fragmented jurisdictions lacking structured APIs, the system deploys a semantic parsing engine to scrape, structure, and interpret localized zoning ordinances, fire codes, and commercial baselines, ensuring the data is strictly anchored to municipal reality rather than generated assumptions.

### 3. 🎯 Geodesic Radius Recommendation Engine (Haversine)
- Executes a strict `Haversine` geodesic algorithm to isolate properties within a 2km target radius.
- Computes multidimensional vector scoring based on three fixed heuristic rules: **Proximity** (50% weight), **Asset Class Alignment** (30% weight), and **Financial Variance** (20% weight), filtering out statistical noise and presenting highly correlated investment alternatives.

### 4. 💬 Context-Grounded Semantic Chat
- An embedded RAG (Retrieval-Augmented Generation) pipeline allows users to interrogate the 5-Agent Council's internal memory state. 
- Automatically injects user constraints (e.g., *"Filter for load capacities exceeding 50MW"*) into the system's global state memory, which dynamically overrides baseline assumptions in future council runs.

---

## 🚀 Deployment & Build Guide

### Prerequisites
- **Node.js** (v18+)
- **Python** (3.10+)
- **Google Chrome** (For DOM injection)

### 1. Core API & Database Initialization (FastAPI)

```bash
cd backend
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# Resolve dependencies
pip install -r requirements.txt
```

Initialize your `.env` configuration inside `backend/`:
```env
OPENAI_API_KEY=your_cognitive_engine_key_here
MIREYE_BASE_URL=https://api.mireye.com
```

**Boot the Orchestration Kernel:**
```bash
python -m uvicorn main:app --reload --port 8000
```

### 2. UI Dashboard Compilation (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

### 3. Capture Extension Injection
1. Navigate to `chrome://extensions/` in Google Chrome.
2. Enable **"Developer mode"** to bypass store verification.
3. Click **"Load unpacked"** and select the `extension/` directory.

---

## 🗺️ Operational Protocol

1. **Ingest Data:** Navigate to a commercial asset on Crexi or LoopNet. Initialize the Chrome extension to extract raw DOM parameters and push them to the FastAPI pipeline.
2. **Monitor State:** Open the Dashboard (`http://localhost:5173`) to observe the asset propagating through your Property Pipeline.
3. **Execute Audit:** Initialize the **Evaluate Site** sequence. The 5-Agent Council will run its concurrent `asyncio.gather()` sequence and compile the geospatial intelligence matrix.
4. **Interrogate:** Engage the Semantic Chat interface to query specific structural constraints or zoning anomalies detected by the council.

---
*Architected by the Mireye Earth Team.*
