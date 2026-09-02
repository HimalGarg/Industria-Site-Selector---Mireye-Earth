# 🏢 Industria Site Selector — Mireye Earth & 5-Agent Council

> **Next-Generation Commercial Real Estate (CRE) Site Selection & Intelligence Platform**

The **Industria Site Selector** is an automated platform that speeds up industrial and commercial site selection. It connects raw property listings (like those from Crexi and LoopNet) directly to geospatial data and regulatory records, using a multi-agent backend to evaluate a site's true feasibility.

---

## 🏗️ System Architecture

The platform runs on a modern stack, separating the data capture from the heavy lifting of the agents and the user dashboard.

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
│                           FASTAPI BACKEND SERVER                             │
│             (REST API, Job Queues, Chat Memory, SQLite DB)                   │
└────┬────────────────────────┬──────────────────────────┬─────────────────┬───┘
     │                        │                          │                 │
     ▼                        ▼                          ▼                 ▼
┌────────────┐         ┌────────────┐            ┌───────────────┐  ┌───────────────┐
│ Mireye GIS │         │ OpenAI API │            │  Govt Scraper │  │ Radius Engine │
│ (58 Data   │         │ (Agents &  │            │ (Zoning &     │  │ (Haversine    │
│  Layers)   │         │ Synthesis) │            │  Compliance)  │  │  Proximity)   │
└────────────┘         └────────────┘            └───────────────┘  └───────────────┘
```

---

## 🧠 Core Features & The 5-Agent Council

### 1. 🏛️ The 5-Agent Evaluation Council
When you evaluate a site, the backend doesn't just run one massive prompt. Instead, it uses `asyncio.gather()` to run five specialized AI agents concurrently. Each agent evaluates physical ground-truth data fetched from the Mireye Earth API:

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

### 3. ⚖️ Government Compliance Data Scraper
We do not rely on standard AI models for regulatory truth. Instead, our compliance engine directly scrapes publicly available online government and municipal data sources. It pulls active building permits, local zoning codes, and environmental records from city databases and EPA public registries so that compliance audits are grounded in real, documented civic data.

### 4. 🎯 Rule-Based Radius Recommendations
- Scans a 2km geodesic radius (Haversine distance) around your target site to find comparables.
- Ranks recommendations on a strict mathematical scale: Proximity (50 points) + Asset Type Match (30 points) + Price Similarity (20 points).

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
