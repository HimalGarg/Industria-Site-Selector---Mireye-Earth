# 🌐 Site Ranker: Obsidian Intelligence System

> **Advanced AI-driven commercial real estate (CRE) site selection, multi-agent evaluation, and automated regulatory due diligence.**

The **Site Ranker** is an end-to-end intelligence platform designed to automate the arduous process of industrial and commercial site selection. It bridges the gap between raw web listings and deep geospatial analysis by combining an intelligent browser extension, a Python-based Multi-Agent architecture, and a modern React frontend.

---

## 🏗️ System Architecture

The platform operates across three distinct layers. Rather than a monolithic backend, the system orchestrates data across specialized micro-engines for geospatial caching, AI routing, and compliance checking.

```text
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│       CAPTURE & INGESTION        │        │      OBSIDIAN UI DASHBOARD       │
│  (Chrome Manifest V3 Extension)  │        │   (React 18, Vite, Tailwind)     │
│ - Auto-scrapes Crexi / LoopNet   │        │ - Bento-Grid Property Pipeline   │
│ - Bypasses SPA routing maps      │        │ - Tabbed Agent Audit Drawers     │
└────────────────┬─────────────────┘        └────────────────┬─────────────────┘
                 │                                           │
                 ▼                                           ▼
┌────────────────┴───────────────────────────────────────────┴─────────────────┐
│                       FASTAPI CENTRAL ORCHESTRATOR                           │
│             (REST API, Job Queues, Chat Memory, SQLite DB)                   │
└────┬────────────────────────┬──────────────────────────┬─────────────────┬───┘
     │                        │                          │                 │
     ▼                        ▼                          ▼                 ▼
┌────────────┐         ┌────────────┐            ┌───────────────┐  ┌───────────────┐
│ Mireye GIS │         │ OpenAI API │            │ Open Data API │  │ Radius Engine │
│ (58 Data   │         │ (Agents &  │            │ (Municipal &  │  │ (Haversine    │
│  Layers)   │         │ Synthesis) │            │  EPA Regs)    │  │  Proximity)   │
└────────────┘         └────────────┘            └───────────────┘  └───────────────┘
```

---

## 🧠 Core Capabilities & Multi-Agent Focus

### 1. 🏛️ The 5-Agent Evaluation Council
When a site is submitted for evaluation, the system bypasses standard single-prompt constraints. Instead, it dispatches an `asyncio.gather()` pipeline to a concurrent council of specialized agents. Each agent is strictly focused on its specific discipline:

- **⚡ Energy & Power Agent:** Evaluates grid capacity, high-voltage transmission lines, and substation limits.
- **💧 Water Agent:** Analyzes public water service areas, wastewater plant capacity, and wetlands counts.
- **🏔️ Surface Agent:** Assesses elevation, terrain slope, soil drainage, and karst sinkhole risks.
- **🚛 Transport Agent:** Audits drive-time distance to major highways, freight rail access, and seaports.
- **⚠️ Risk Agent:** Flags fatal flaws such as FEMA flood zones, underground storage tank leaks, and orphaned wells.

### 2. ⚙️ Agent Operational Workflow

```text
                            [ User Triggers Site Evaluation ]
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │    Data Aggregation & Normalization Phase    │
                     │ (Mireye GIS: Elevation, Flood, Power, Water) │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │      Concurrent Agent Evaluation Pipeline    │
                     │              `asyncio.gather()`              │
                     └─┬─────────┬─────────┬──────────┬───────────┬─┘
                       │         │         │          │           │
         ┌─────────────┴┐ ┌──────┴───────┐ │ ┌────────┴───────┐ ┌─┴────────────┐
         ▼              ▼ ▼              ▼ ▼ ▼                ▼ ▼              ▼
┌────────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ ⚡ Energy Agent │ │ 💧 Water Agent │ │🏔️ Surface Agent│ │🚛Transport Agt│ │⚠️ Risk Agent  │
│ Analyzes power │ │ Checks public │ │ Grades terrain│ │ Measures road │ │ Flags FEMA    │
│ lines, capacity│ │ utilities and │ │ slope & karst │ │ & rail access │ │ flood & USTs  │
│ & drive-times. │ │ watershed vol.│ │ sinkholes.    │ │ logistics.    │ │ encumbrances. │
└────────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
         │                 │                 │                 │                 │
         └─────────────────┴─────────────────┼─────────────────┴─────────────────┘
                                             │
                                             ▼
                     ┌──────────────────────────────────────────────┐
                     │   👑 Council Synthesizer & Conflict Engine   │
                     │ - Detects cross-domain contradictions        │
                     │ - Scores overall feasibility (0-100 scale)   │
                     │ - Generates Executive Board-Ready Summary    │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                                [ Final Output to React UI ]
```

### 3. ⚖️ Automated Compliance & Regulatory Agent
- Interrogates municipal Open Data portals for building permits, certificates of occupancy, fire codes, and zoning violations.
- **AI Regulatory Fallback:** If a municipality lacks open data, the system automatically calls upon a dedicated LLM Regulatory Agent to synthesize a highly accurate zoning and compliance baseline for that specific jurisdiction.

### 4. 🎯 Rule-Based Radius Recommendations
- Scans a 2km geodesic radius around your target site to find comparables.
- Ranks recommendations on a strict mathematical scale: **Proximity** (50 points) + **Asset Type Match** (30 points) + **Price Similarity** (20 points).

---

## 🚀 Installation & Build Guide

### Prerequisites
- **Node.js** (v18+)
- **Python** (3.10+)
- **Google Chrome**

### 1. Backend Setup (FastAPI)

```bash
cd backend
python -m venv venv

# Activate the virtual environment
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file inside the `backend/` directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
MIREYE_BASE_URL=https://api.mireye.com
```

**Run the Backend:**
```bash
python -m uvicorn main:app --reload --port 8000
```

### 2. Frontend Setup (React)

```bash
cd frontend
npm install
npm run dev
```

### 3. Chrome Extension Setup
1. Open Chrome and navigate to `chrome://extensions/`.
2. Toggle **"Developer mode"** ON (top right corner).
3. Click **"Load unpacked"** and select the `extension/` folder from this repository.

---

## 🗺️ How to Use the System

1. **Capture:** Browse Crexi or LoopNet. Open a property listing and click the Mireye extension icon to add it to your cart.
2. **Pipeline:** Open the Frontend (`http://localhost:5173`) to view your Property Pipeline.
3. **Audit:** Click into a property and press **Evaluate Site**. The 5-Agent Council will run a deep geospatial analysis.
4. **Chat & Refine:** Open the Site Intelligence Chat. Tell the system your exact requirements (e.g., *"I need this site for a data center"*). The requirements are saved to memory and factored into the agents' logic.
5. **Expand:** Check the **Recommendations** tab to view rule-based comparables within a 2km radius. 

---
*Developed by the Mireye Earth Team.*
