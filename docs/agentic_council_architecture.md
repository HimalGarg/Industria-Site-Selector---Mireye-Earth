# Agentic Council Architecture & Evaluation Engine

## Executive Overview & Core Purpose

The **Agentic Council** is an autonomous multi-agent evaluation engine designed for high-stakes Commercial Real Estate (CRE) site selection, due diligence, and risk assessment. Developed as part of the **Industria Site Selector — Mireye Earth** platform, the Agentic Council replaces manual, multi-week physical site audits with an instant, concurrent, domain-specialized evaluation pipeline.

Instead of relying on a single generalist LLM prompt, the system deploys a **Council of 5 Specialized AI Agents** operating concurrently across five distinct engineering and environmental disciplines:
1. **Energy & Power Infrastructure**
2. **Water & Watershed**
3. **Surface & Environment**
4. **Transportation & Access**
5. **Risk & Compliance**

Each agent is grounded in real-world spatial intelligence retrieved from **Mireye Earth GIS APIs** (spanning 58 physical datasets) and cross-referenced against seller-provided listing metrics. A 6th meta-agent—the **Council Synthesizer**—aggregates discipline scores, resolves cross-agent tensions, surfaces contradictions between listing claims and physical data, and generates executive board-ready evaluation memos.

```
                                 ┌─────────────────────────────────────────┐
                                 │     Commercial Listing / Cart Item      │
                                 │      (Seller Disclosures & Facts)       │
                                 └────────────────────┬────────────────────┘
                                                      │
                                                      ▼
                                 ┌─────────────────────────────────────────┐
                                 │       FastAPI Evaluation Router         │
                                 │          `POST /evaluate-site`          │
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

## Technical Architecture & Core Components

The Agentic Council resides in the [`backend/evaluate`](file:///c:/Users/nayak/Desktop/chrome%20extension/backend/evaluate) module of the FastAPI server. It is structured into clean, decoupled layers:

### 1. Data Inventory & Mapping (`config.py`)
- **`AGENT_FIELD_MAP`**: Defines the precise mapping between domain agents and GIS field parameters from Mireye Earth.
- **`IDENTITY_FIELDS`**: Global spatial context parameters (e.g., County, State, Census Tract, Opportunity Zone status, Parcel ID) queried once per evaluation and shared across all agents.
- **`PROXIMITY_CURATED_SETS`**: Curated amenity/infrastructure categories (`@power_plants`, `@airports`, `@ports`, `@rail`) passed to Mireye's Drive-Time Proximity API.
- **`LLM_STRUCTURED_SLICES`**: Selected listing-side properties (e.g., claimed acreage, building age, property type, seller highlights) passed specifically to Surface and Risk agents for automated cross-referencing.

### 2. Spatial Data Fetcher & Caching (`mireye_fetcher.py`)
To ensure rapid execution and eliminate unnecessary third-party API costs, the evaluation pipeline employs a cache-first strategy:
- **Address Resolution & Normalization**: Resolves unstructured real estate addresses into precise latitude/longitude coordinates and normalized cache keys.
- **Additive SQLite Cache (`mireye_cache`)**: Caches individual field responses keyed by `normalized_address + field_name`. If a requested field exists in cache, it is loaded locally; missing fields are fetched in bulk from the Mireye Earth API (`POST /v1/fetch`) and cached immediately.
- **Drive-Time Distance Calculation**: Queries Mireye Proximity API (`POST /v1/proximity`) to determine true road network drive-time durations to power plants, airports, ports, and rail nodes, superseding simplistic Euclidean straight-line measurements.

### 3. Concurrent Multi-Agent Engine (`agents.py`)
The council consists of 5 domain-expert agents executing simultaneously via Python's `asyncio.gather()`:

```python
tasks = [
    run_agent("energy", all_mireye_fields, llm_structured, fields, proximity_results.get("energy")),
    run_agent("water", all_mireye_fields, llm_structured, fields, proximity_results.get("water")),
    run_agent("surface", all_mireye_fields, llm_structured, fields, proximity_results.get("surface")),
    run_agent("transport", all_mireye_fields, llm_structured, fields, proximity_results.get("transport")),
    run_agent("risk", all_mireye_fields, llm_structured, fields, proximity_results.get("risk")),
]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

Each agent makes a single structured LLM call (via JSON mode) instructed with strict discipline-specific evaluation criteria:

| Agent Discipline | Primary Datasets & Inputs | Key Evaluation Focus & Criteria |
| :--- | :--- | :--- |
| **Energy & Power Infrastructure** | Transmission lines (voltage kV, status), power plants (capacity MW, fuel type, distance), natural gas pipelines | Assesses power feasibility for commercial/industrial usage. Evaluates grid redundancy vs single-point-of-failure. Prefers drive-time power plant proximity. |
| **Water & Watershed** | Public water service area, PWSID, utility name, wastewater plant capacity & population served, wetlands count (100m/500m), HUC12 watershed | Evaluates utility hookups, spare treatment capacity, and hydrological development constraints. Penalizes non-serviced water areas heavily. |
| **Surface & Environment** | Elevation, slope degrees, soil drainage class, bedrock depth, karst terrain exposure, tree canopy %, NDVI 5-yr trend | Analyzes buildability, foundation risks, and land clearing costs. Cross-references listing claims (e.g., "flat parcel") against GIS slope/karst ground truth. |
| **Transportation & Access** | Major road distance, rail distance, airport drive-time, seaport distance, catalogued bridges | Evaluates logistics accessibility for freight, industrial, or commercial traffic based on land use type. Prioritizes road proximity (<200m). |
| **Risk & Compliance** | FEMA flood zones, UST (underground storage tank) leaks within 1km, orphaned wells, critical habitat status, conservation easements | Identifies fatal environmental liabilities, regulatory litigation risks, and title encumbrances. Cross-examines seller "clean site" disclosures against toxic records. |

#### Strict Grounding & Citation Engine
To prevent hallucination, every agent prompt enforces mandatory **Grounding Rules**:
1. Every factual assertion in an agent memo **must be tied to a structured citation** specifying `source` (`"mireye"` or `"listing"`), `field`, and `value`.
2. Missing or null GIS data must be explicitly reported as `"not available"`—agents are forbidden from guessing missing values.
3. Every agent returns a structured `AgentResult`:
   - `score`: `0 - 100` numeric rating.
   - `summary`: 1-2 sentence executive verdict.
   - `memo`: 3-6 paragraph detailed engineering assessment.
   - `citations`: Array of source-attributed data points.
   - `data_availability`: `"full"` | `"partial"` | `"unavailable"`.

---

## The Council Synthesizer (`synthesizer.py`)

Once all 5 agents complete their evaluations, their raw outputs are ingested by the **Council Synthesizer**. The Synthesizer performs meta-analysis across all agent reports to deliver a single cohesive verdict:

### Key Synthesizer Responsibilities:
1. **Weighted Overall Score (`0 - 100`)**: Computes a holistic site score that weights critical disciplines (e.g., Risk and Water) more heavily than amenity disciplines. Fatal environmental issues (e.g., severe flood zone or toxic leaks) trigger score caps regardless of high transport or energy scores.
2. **Conflict & Contradiction Flagger (`conflicts_flagged`)**: Automatically detects and surfaces two classes of friction:
   - **Cross-Agent Domain Tensions**: E.g., High Energy Score (85/100) paired with Severe Risk Score (20/100)—signaling a site with power access but uninsurable environmental risks.
   - **Listing Discrepancies**: E.g., Broker listing advertises "Fully Serviced Build-Ready Site", but Water Agent detects `in_public_water_service_area = false` or Risk Agent detects `ust_facilities_with_open_leak_count > 0`.
3. **Board-Readable Executive Summary (`narrative_summary`)**: Synthesizes a 2-4 paragraph decision memo suitable for investment committees and CRE decision-makers.

---

## Multi-Site Comparison & Chat Router Integration

The Agentic Council architecture extends beyond individual site evaluations to power portfolio-level workflows across the platform:

```
                                 ┌─────────────────────────────────────────┐
                                 │         Stored Site Evaluations         │
                                 │              (`evaluations`)            │
                                 └────────────────────┬────────────────────┘
                                                      │
                       ┌──────────────────────────────┴──────────────────────────────┐
                       │                                                             │
                       ▼                                                             ▼
         ┌───────────────────────────┐                                 ┌───────────────────────────┐
         │ Multi-Site Comparison     │                                 │ Context-Grounded Chat     │
         │ `POST /compare-sites`     │                                 │ `POST /chat`              │
         └─────────────┬─────────────┘                                 └─────────────┬─────────────┘
                       │                                                             │
                       ▼                                                             ▼
         ┌───────────────────────────┐                                 ┌───────────────────────────┐
         │ Side-by-Side Radar Matrix │                                 │ Grounded Q&A against      │
         │ & Trade-off Synthesizer   │                                 │ Council Memos & Citations │
         └───────────────────────────┘                                 └───────────────────────────┘
```

### Multi-Site Comparison Pipeline (`compare_router.py` & `compare_synthesizer.py`)
- Accepts between 2 to 4 evaluated site IDs (`POST /compare-sites`).
- Extracts and flattens agent scores into a normalized comparison matrix across Energy, Water, Surface, Transport, and Risk.
- Invokes the **Compare Synthesizer** to generate a comparative trade-off breakdown highlighting which site excels for specific industrial or commercial use cases.

### Context-Grounded Chat Router (`backend/chat/router.py`)
- When users converse with the platform assistant about a property (`POST /chat`), the chat router automatically pulls the site's primary Council Evaluation Report.
- Answers are strictly grounded in the Council's findings, citations, and flagged conflicts, enabling users to ask follow-up questions such as *"Why did the Water Agent score this site low?"* or *"What are the key environmental risks flagged by the council?"*.

---

## Asynchronous Execution & Database Persistence (`router.py`)

To deliver responsive user experiences, council evaluations are handled via non-blocking background jobs:

1. **Trigger (`POST /evaluate-site`)**: Accepts a `cart_item_id`, validates property existence, generates a unique `evaluation_id`, and initiates background execution in a dedicated daemon thread. Returns immediately with `status: "processing"`.
2. **Polling (`GET /evaluate-site/{evaluation_id}`)**: The frontend dashboard auto-polls the in-memory job store (`_job_store`).
3. **Database Persistence**: Upon completion, full evaluation results (overall score, recommendation, agent JSON results, citations, and flagged conflicts) are committed to the SQLite `evaluations` table:

```sql
CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id TEXT PRIMARY KEY,
    cart_item_id TEXT NOT NULL,
    overall_score INTEGER,
    recommendation TEXT,
    conflicts_flagged TEXT, -- JSON Array
    agent_results TEXT,      -- JSON Array of 5 AgentResult objects
    created_at TEXT NOT NULL,
    FOREIGN KEY (cart_item_id) REFERENCES cart_items (cart_item_id) ON DELETE CASCADE
);
```

---

## Summary of Design Principles & Benefits

| Architecture Feature | Strategic Advantage |
| :--- | :--- |
| **Concurrent Execution** | Runs 5 specialized LLM agents in parallel via `asyncio.gather()`, maintaining sub-10s analysis response times. |
| **Strict Citation Requirement** | Prevents AI hallucination by enforcing explicit data line-item tracing to Mireye GIS sources or listing disclosures. |
| **Listing vs. GIS Discrepancy Detection** | Automatically flags deceptive or inaccurate broker claims by auditing self-reported metadata against satellite & spatial ground truth. |
| **Cache-First Spatial Engine** | Reduces GIS API latency and token cost via additive SQLite caching at the individual field level. |
| **Downstream Synergy** | Council evaluation outputs serve as the single source of truth for dashboard UI drawers, multi-site comparison matrices, and grounded conversational AI. |
