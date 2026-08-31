# 🏢 Industria Site Selector — Mireye Earth & 5-Agent Council

> **Next-Generation Commercial Real Estate (CRE) Site Selection & Intelligence Platform**  
> Powered by Chrome Extension Auto-Capture, 58 Physical GIS Datasets via Mireye Earth, a 5-Agent Autonomous Evaluation Council, and a Dark-Mode React Executive Dashboard.

---

## 🌟 Key Features & Capabilities

- ⚡ **1-Click Property Capture (`extension/`)**: Chrome Manifest V3 extension featuring auto-scraping adapters for **Crexi** and **LoopNet**, extracting property metrics, financial disclosures, and seller facts straight into your site pipeline.
- 🏛️ **5-Agent Autonomous Evaluation Council (`backend/evaluate/`)**:
  - **Energy & Power Infrastructure Agent**: Grid capacity, high-voltage transmission lines, natural gas pipelines, and drive-time power proximity.
  - **Water & Watershed Agent**: Public water service areas, PWSID, wastewater plant capacity, wetlands counts, and watershed dynamics.
  - **Surface & Environment Agent**: Terrain slope, soil drainage, elevation, bedrock depth, tree canopy %, and karst sinkhole risks.
  - **Transportation & Access Agent**: Major road distance, freight rail access, airport drive-time, and seaport proximity.
  - **Risk & Compliance Agent**: FEMA flood zones, underground storage tank (UST) open leaks within 1km, orphaned wells, critical habitats, and conservation easements.
- ⚖️ **Council Synthesizer & Contradiction Engine**:
  - Computes weighted overall site feasibility scores (`0–100`).
  - Detects cross-agent domain tensions (e.g. High Energy 85 vs. Low Risk 20).
  - Automatically flags seller listing disclosures that contradict physical GIS ground truth (e.g., claimed "flat, fully serviced site" vs. non-serviced water area or steep terrain).
- 📊 **Multi-Site Side-by-Side Comparison (`POST /compare-sites`)**: Matrix comparison of 2–4 candidate properties with automated trade-off synthesis for investment committees.
- 💬 **Context-Grounded Site Chat & Memory Notes (`backend/chat/`)**: Grounded conversational AI assistant querying council evaluation memos, citations, and atomic listing memory notes.
- 💎 **Obsidian Intelligence Dashboard (`frontend/`)**: Modern, high-performance React 18 + Vite + TailwindCSS executive UI featuring dark glassmorphism styling, Bento-grid pipeline layout, and slide-over audit drawers.

---

## 🏗️ System Architecture

```
                                 ┌─────────────────────────────────────────┐
                                 │     Commercial Listing / Cart Item      │
                                 │  (Scraped via Crexi / LoopNet Extension) │
                                 └────────────────────┬────────────────────┘
                                                      │
                                                      ▼
                                 ┌─────────────────────────────────────────┐
                                 │          FastAPI Backend Server         │
                                 │        SQLite Database (`site_ranker`)  │
                                 └────────────────────┬────────────────────┘
                                                      │
                                                      ▼
                                 ┌─────────────────────────────────────────┐
                                 │  Address Geocoder & Mireye Cache Layer  │
                                 │ (Normalize Address & Identity Data)     │
                                 └────────────────────┬────────────────────┘
                                                      │
                       ┌──────────────────────────────┼──────────────────────────────┐
                       │                              │                              │
                       ▼                              ▼                              ▼
             ┌───────────────────┐          ┌───────────────────┐          ┌───────────────────┐
             │   Mireye Fetcher  │          │   Proximity API   │          │ Listing Normalizer│
             │(58 GIS Datasets)  │          │(Drive-Time Routing│          │ (llm_structured)  │
             └─────────┬─────────┘          └─────────┬─────────┘          └─────────┬─────────┘
                       │                              │                              │
                       └──────────────────────────────┼──────────────────────────────┘
                                                      │
                                                      ▼
                       ┌─────────────────────────────────────────────────────────────┐
                       │           Concurrent Agent Evaluation Pipeline              │
                       │                   `asyncio.gather()`                        │
                       └──────┬─────────────┬─────────────┬─────────────┬────────────┘
                              │             │             │             │
             ┌────────────────┴─┐  ┌────────┴─────────┐  ┌┴─────────────┴┐  ┌─────────┴───────┐
             ▼                  ▼  ▼                  ▼  ▼               ▼  ▼                 ▼
     ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
     │ Energy Agent  │  │  Water Agent  │  │ Surface Agent │  │Transport Agent│  │  Risk Agent   │
     │(Power Grid &  │  │(Utility & H2O │  │(Terrain, Slope│  │(Road, Rail,   │  │(Flood, Contam,│
     │ Natural Gas)  │  │  Capacity)    │  │ Soil & Karst) │  │ Airport, Port)│  │ Encumbrance)  │
     └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
             │                  │                  │                  │                  │
             └──────────────────┼──────────────────┼──────────────────┼──────────────────┘
                                │                  │                  │
                                └──────────────────┼──────────────────┘
                                                   │
                                                   ▼
                                ┌────────────────────────────────────┐
                                │        Council Synthesizer         │
                                │(Weighted Scoring & Discrepancies)  │
                                └──────────────────┬─────────────────┘
                                                   │
                                                   ▼
                                ┌────────────────────────────────────┐
                                │   SQLite Storage (`evaluations`)   │
                                │   & Front-End Dashboard Render     │
                                └────────────────────────────────────┘
```

---

## 📁 Repository Directory Structure

```
.
├── backend/                         # FastAPI Python Application Server
│   ├── chat/                        # Conversational AI & Memory Note Router
│   │   ├── answer_generator.py      # Citation-grounded LLM response engine
│   │   ├── memory_engine.py         # Atomic note generator & session context
│   │   └── router.py                # FastAPI endpoints for /chat and /listing-memory
│   ├── evaluate/                    # 5-Agent Council Evaluation Engine
│   │   ├── agents.py                # Concurrent domain agents (Energy, Water, Surface, Transport, Risk)
│   │   ├── compare_router.py        # Side-by-side site comparison endpoint
│   │   ├── compare_synthesizer.py    # Multi-site trade-off synthesis LLM prompt
│   │   ├── config.py                # Mireye GIS field inventory & agent mapping
│   │   ├── mireye_fetcher.py        # Mireye Earth client & additive SQLite cache
│   │   ├── router.py                # Async evaluation router & job runner
│   │   └── synthesizer.py           # Council meta-synthesizer & conflict flagger
│   ├── main.py                      # FastAPI application entrypoint & SQLite DB setup
│   ├── requirements.txt             # Python backend dependencies
│   └── test_*.py                    # Automated test suites (normalizer, evaluation, chat, comparison)
│
├── extension/                       # Manifest V3 Chrome Extension
│   ├── manifest.json                # Chrome extension permissions & content script match patterns
│   ├── background.js                # Service worker for API sync & message routing
│   ├── content.js                   # Primary DOM injector & capture button listener
│   ├── scrapers/                    # Pluggable site scraping adapters (Crexi, LoopNet)
│   └── popup.html / popup.js        # Extension toolbar popup interface
│
└── frontend/                        # React 18 + Vite Web Application
    ├── src/
    │   ├── api.ts                   # Backend REST API client methods
    │   ├── main.tsx                 # React DOM root entrypoint
    │   ├── App.tsx                  # Pipeline dashboard & routing structure
    │   └── pages/                   # Application views (SiteDetailPage, ComparePage)
    ├── package.json                 # Node dependencies
    ├── tailwind.config.js           # Obsidian Intelligence theme color tokens
    └── vite.config.ts               # Vite bundler configuration
```

---

## 🔑 Environment Configuration (`backend/.env`)

Create a `.env` file inside the `backend/` directory before running the server:

```env
# ---------------------------------------------------------------------------
# OpenAI API Key (Required for 5-Agent Council, Chat, & Synthesis)
# ---------------------------------------------------------------------------
OPENAI_API_KEY=sk-proj-...your_openai_key_here
OPENAI_MODEL=gpt-4o
OPENAI_MODEL_LIGHT=gpt-4o-mini

# ---------------------------------------------------------------------------
# Mireye Earth API Key (Required for 58 Spatial/GIS Datasets)
# ---------------------------------------------------------------------------
MIREYE_API_KEY=eyJhbGciOi...your_mireye_key_here
MIREYE_BASE_URL=https://api.mireye.earth
```

---

## 🚀 Quick Start & Setup Guide

> **Note:** For a comprehensive, step-by-step setup and build guide for production and development, please see [BUILD.md](BUILD.md).

### 1. Launch FastAPI Backend Server

```bash
# Navigate to the backend directory
cd backend

# (Optional) Create & activate Python virtual environment
python -m venv venv

# On Windows PowerShell:
.\venv\Scripts\activate
# On macOS / Linux:
# source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt

# Create .env file from template
copy .env.example .env   # (or cp .env.example .env on Linux/macOS)

# Start the development server
python -m uvicorn main:app --reload --port 8000
```

- 🌐 **Interactive Swagger Docs**: [`http://localhost:8000/docs`](http://localhost:8000/docs)
- ❤️ **Server Health Check**: [`http://localhost:8000/health`](http://localhost:8000/health)

---

### 2. Launch React Executive Dashboard

Open a separate terminal window:

```bash
# Navigate to the frontend directory
cd frontend

# Install Node dependencies
npm install

# Start Vite dev server
npm run dev
```

- 🖥️ **React Web Dashboard**: [`http://localhost:5173/`](http://localhost:5173/)

---

### 3. Install Chrome Extension

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** using the toggle in the top-right corner.
3. Click **Load unpacked**.
4. Select the `extension/` folder in this repository.
5. Open any property listing on **Crexi** or **LoopNet** and click **"Add to Site Ranker"** to instantly push listings into your intelligence pipeline!

---

## 🧪 Running Automated Test Suites

The backend includes 4 automated test suites verifying all core engine layers:

```bash
cd backend

# 1. LLM Schema Normalizer Unit Tests
python -m unittest test_normalizer.py

# 2. 5-Agent Council Evaluation Engine Tests
python test_evaluation_pipeline.py -v

# 3. Site Intelligence Chat & Memory Router Tests
python test_chat_pipeline.py -v

# 4. Multi-Site Side-by-Side Comparison Tests
python test_compare_pipeline.py -v
```

---

## 🔌 Core API Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/cart-items` | Save/update listing captured from Chrome Extension |
| `GET` | `/cart-items` | Retrieve captured properties in user pipeline |
| `DELETE` | `/cart-items/{id}` | Delete listing and all associated evaluation/chat data |
| `POST` | `/evaluate-site` | Kick off non-blocking 5-agent council evaluation audit |
| `GET` | `/evaluate-site/{id}` | Poll evaluation audit status & retrieve full 5-agent report |
| `POST` | `/chat` | Synchronous site intelligence chat turn (grounded in council findings) |
| `GET` | `/chat` | Retrieve full chat history for a property |
| `GET` | `/listing-memory` | Retrieve atomic key takeaway notes for a listing |
| `POST` | `/compare-sites` | Side-by-side comparison of 2–4 sites with matrix & trade-offs synthesis |
| `GET` | `/health` | Server health check endpoint |

---

## 🛠 Tech Stack

- **Extension**: Chrome Manifest V3, Pluggable DOM Adapters, Fetch API.
- **Backend**: Python 3.10+, FastAPI, Uvicorn, SQLite, OpenAI API (JSON Mode), Mireye Earth GIS API.
- **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Lucide / Google Symbols Icons.
