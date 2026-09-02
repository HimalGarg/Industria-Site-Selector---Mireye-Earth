# 🏢 Industria Site Selector — Mireye Earth & 5-Agent Council

> **An autonomous, multi-agent evaluation platform that independently underwrites and audits commercial real estate using physical GIS data.**

Most real estate tools simply aggregate listings. **Industria Site Selector** is fundamentally different: it deploys a network of autonomous AI agents to fact-check seller claims against hard geospatial and regulatory data, automatically flagging risks, contradictions, and physical constraints before human review.

---

## 🧠 The Core Engine: Multi-Agent Site Underwriting

The heart of the platform is an asynchronous, multi-agent evaluation pipeline. When a property is captured, the system doesn't rely on a single AI prompt. Instead, it queries 58 distinct physical data layers from Mireye Earth (elevation, power grids, flood zones) and distributes that raw data to a council of 5 specialized agents.

These agents run concurrently, meaning they analyze the site entirely independently of one another, simulating a team of specialized civil and environmental engineers.

### 🏛️ The 5-Agent Council

- **⚡ Energy & Power Agent:** Cross-references the property’s coordinates against geospatial power infrastructure. It calculates the physical distance to high-voltage transmission lines and substations to determine if the site can support heavy industrial loads.
- **💧 Water Agent:** Evaluates public water service boundaries and watershed capacity. It flags if a property sits outside municipal utility zones, which would mandate expensive well and septic installations.
- **🏔️ Surface Agent:** Processes topographic arrays to determine terrain slope and soil drainage. It calculates the exact grading requirements (e.g., identifying a 15% slope that makes warehouse construction economically unviable).
- **🚛 Transport Agent:** Executes routing algorithms to determine actual drive-time logistical access to major interstate highways, freight rail nodes, and seaports, grading the site on supply-chain viability.
- **⚠️ Risk Agent:** Overlays the site bounds with FEMA flood maps and EPA hazardous data. It actively searches for localized encumbrances, such as underground storage tank (UST) leaks within a 1km radius or critical habitat restrictions.

---

## ⚖️ The Synthesis & Contradiction Engine

Because the 5 agents evaluate the site concurrently and independently, their outputs must be reconciled. This is handled by the **Master Synthesizer**.

The Synthesizer serves two primary functions:
1. **Cross-Domain Arbitration:** It resolves tensions between conflicting agent reports. For example, if the Transport Agent gives a site a 95/100 for highway access, but the Risk Agent flags that the site sits in a 100-year flood plain, the Synthesizer dynamically downgrades the final viability score.
2. **BS Detection (Seller vs. Ground Truth):** The Synthesizer reads the original seller listing notes (e.g., "Perfect flat land, ready to build") and mathematically cross-checks it against the physical GIS findings (e.g., the Surface Agent reports a severe 22% grade). It explicitly calls out these contradictions in the final executive summary.

```text
                            [ Site Captured via Extension ]
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │    Geospatial Data Aggregation Phase         │
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
┌────────────────┐ ┌──────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐
│  Energy Agent  │ │  Water Agent │ │ Surface Agent │ │Transport Agent│ │  Risk Agent  │
└────────┬───────┘ └───────┬──────┘ └───────┬───────┘ └───────┬───────┘ └───────┬──────┘
         │                 │                │                 │                 │
         └─────────────────┴────────────────┼─────────────────┴─────────────────┘
                                            │
                                            ▼
                     ┌──────────────────────────────────────────────┐
                     │   👑 Council Synthesizer & Conflict Engine   │
                     │ - Detects cross-domain contradictions        │
                     │ - Flags Seller Claims vs. GIS Ground Truth   │
                     │ - Generates Executive Board-Ready Summary    │
                     └──────────────────────┬───────────────────────┘
                                            │
                                            ▼
                                [ Executive Dashboard ]
```

---

## 🏛️ Government Compliance Scraper

To ground our risk assessments in reality, the system bypasses generalized AI knowledge and actively scrapes publicly available government data. 

When a site is evaluated, the Compliance Scraper reaches out to localized municipal databases, county zoning portals, and EPA public registries. It pulls active building permits, fire code violations, and current zoning ordinances directly from the source, ensuring the due diligence report reflects the exact, real-time legal status of the property.

---

## 🎯 Rule-Based Radius Matching

The platform does not use simple keyword matching to find alternatives. It utilizes a strict mathematical **Radius Engine**. 

When triggered, the engine executes a Haversine formula to draw a geodesic 2km boundary around the site. It then grades every neighboring property on a strict 100-point algorithm:
- **Proximity (50 Points):** Absolute geodesic distance from the target site.
- **Asset Type (30 Points):** Strict category alignment (e.g., Industrial vs. Retail).
- **Financial Variance (20 Points):** Price-per-square-foot deviation from the baseline.

---

## 💬 Continuous Context & Agent Memory

The agents are not static; they adapt to user directives. Through the embedded chat interface, users can provide specific development goals (e.g., *"I am building a 50MW data center, water access is critical"*).

This input doesn't just trigger a chatbot response—it is permanently written to the site's atomic memory state. The next time the 5-Agent Council evaluates the property, the agents read this memory state and completely alter their scoring criteria to aggressively penalize the site if it lacks heavy water utilities or sufficient power grid access.

---

## ⚙️ Quick Local Setup

*For development and testing purposes.*

**1. Boot the Backend (Python / FastAPI)**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
*(Requires `OPENAI_API_KEY` and `MIREYE_BASE_URL` in `backend/.env`)*

**2. Boot the Dashboard (React / Vite)**
```bash
cd frontend
npm install
npm run dev
```

**3. Load the Capture Tool**
Go to `chrome://extensions/` in Chrome, turn on Developer Mode, and click "Load unpacked" to load the `extension/` folder.
