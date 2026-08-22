# Site Ranker Capture — Multi-Site Chrome Extension & LLM Normalization Engine - Build Context

## 1. Executive Summary

This repository (`chrome extension`) contains the **Site Ranker Capture Chrome Extension** (Manifest V3 v0.2) and its companion **FastAPI Backend Server & LLM Normalization Engine**. 

Its purpose is to capture commercial real estate listings across multiple sites (**Crexi** and **LoopNet**, with extensible architecture for **Zillow** and future platforms), extract raw property specifications and financial data, normalize them into a typed, canonical JSON representation (`llm_structured`), and persist them in an SQLite database (`site_ranker.db`) for downstream processing (such as location intelligence enrichment via the **Mireye Earth API**).

---

## 2. Directory & Repository Structure

```text
chrome extension/
├── extension/                        # Load this folder in Chrome (Clean Extension Source)
│   ├── manifest.json                 # Manifest V3 (v0.2 multi-site config & content script bindings)
│   ├── popup.html / popup.js         # Extension toolbar UI (multi-site badges, cart preview, session sync)
│   ├── content-crexi.js              # CrexiAdapter (extends BaseAdapter for Crexi PDP pages)
│   ├── content-loopnet.js            # LoopNetAdapter (extends BaseAdapter for LoopNet detail pages)
│   ├── content-session.js            # Reads session_id from web application localStorage & syncs to background
│   ├── content.js                    # Manual text selection capture script
│   ├── background.js                 # Service worker handling storage, tab events & session state
│   ├── scrapers/                     # Pluggable Adapter Framework
│   │   ├── base-adapter.js           # BaseAdapter class (button injection, click handler, SPA nav, logging)
│   │   ├── normalize.js              # Shared pure normalization functions (price, address, sqft parsing)
│   │   ├── llm-formatter.js          # Shared LLM payload formatter
│   │   └── website-registry.js       # Hostname matching registry & capability matrix
│   └── icons/                        # Extension toolbar icons (16, 48, 128px)
│
├── backend/                          # FastAPI Cart API, LLM Normalizer & Evaluation Pipeline
│   ├── evaluate/                     # 5-Agent Site Evaluation Pipeline
│   │   ├── config.py                 # 58-field Mireye inventory mapping & agent settings
│   │   ├── mireye_fetcher.py         # Mireye API wrapper with additive SQLite cache
│   │   ├── agents.py                 # 5 concurrent OpenAI agents (Energy, Water, Surface, Transport, Risk)
│   │   ├── synthesizer.py            # Council synthesizer (overall score, recommendation, conflicts)
│   │   └── router.py                 # FastAPI async job endpoints (/evaluate-site)
│   ├── main.py                       # FastAPI routes, DB schema, migration handler (v0.3.3)
│   ├── site_ranker.db                # SQLite database storing cart items, cache & evaluations
│   ├── test_normalizer.py            # Unit test suite verifying raw preservation & llm_structured schema
│   ├── test_evaluation_pipeline.py    # Integration test suite for 5-agent evaluation pipeline
│   ├── .env                          # Local secrets (OPENAI_API_KEY, MIREYE_API_KEY)
│   └── requirements.txt              # Backend dependencies (fastapi, uvicorn, pydantic, openai)
│
├── docs/                             # Documentation, specifications & build guides
│   ├── build_context.md              # [THIS FILE] Complete build context for system understanding
│   ├── Chrome Extension Multi-Site Scraping Build Guide.md # Multi-site build specification
│   ├── llm_structured_normalization_guide.md # Pipeline spec separating raw data from LLM inference schema
│   ├── crexi_confirmed_selectors_v2.md       # Tested DOM selectors for Crexi PDP pages
│   ├── crexi_confirmed_selectors.md          # Initial DOM selector analysis for Crexi
│   ├── crexi_dom_inspection_guide.md         # Guide for inspecting Crexi DOM structures
│   └── antigravity_chrome_extension_guide.md # Core design guide for extension architecture
│
├── fixtures/                         # Saved HTML fixtures for offline testing
│   └── 667 Madison Ave, New York, NY 10065 - Office for Lease _ LoopNet.html
│
├── scratch/                          # Audit & database comparison scripts
│   ├── compare_db_items.py
│   ├── compare_crexi.py
│   ├── compare_recent.py
│   └── crexi_diff.py
│
└── README.md                         # Setup, installation, project structure, and deployment instructions
```

---

## 3. Data Pipeline & Architecture

The extension implements a **two-layer data model** separating raw scraped data, common normalized fields, website-specific fields, and LLM-optimized payloads:

```text
Crexi / LoopNet / Zillow Listing Page
                 │
                 ▼
     Website Adapter (CrexiAdapter / LoopNetAdapter)
                 │
                 ├─────────────► Raw Scraped Record (extractRaw())
                 │
                 ▼
       Normalization Layer (normalize())
                 │
                 ├─────────────► Common Fields (title, address, price, status, etc.)
                 ├─────────────► Website-Specific Fields (loopnet.available_spaces, crexi.cap_rate, etc.)
                 │
                 ▼
       LLM Output Layer (formatForLLM())
                 │
                 ▼ (HTTP POST /cart-items)
        FastAPI Backend (backend/main.py)
         ┌───────┴────────────────────────┐
         ▼                                ▼
  RAW PROVENANCE                   LLM NORMALIZATION
  details column                   llm_structured column
  (100% unaltered dict)            (Typed, canonical schema v1.0)
         │                                │
         └───────────────┬────────────────┘
                         ▼
             SQLite Database (site_ranker.db)
                         │
                         ▼ (Address string extraction)
             Mireye Earth API Integration
```

---

## 4. Multi-Site Adapter Architecture (v0.2)

All website adapters extend `BaseAdapter` ([`extension/scrapers/base-adapter.js`](file:///c:/Users/nayak/Desktop/chrome%20extension/extension/scrapers/base-adapter.js)):

### Standard Adapter Contract
* `siteName` — Short identifier (`"crexi"`, `"loopnet"`, `"zillow"`)
* `hostnames` — List of supported hostnames
* `isListingPage()` — Page URL pattern matcher
* `getAnchorElement()` — Target element for button injection
* `extractRaw()` — Multi-source raw extraction
* `normalize(raw)` — Maps raw data to `{ source, common, website_specific }`
* `formatForLLM(normalized)` — Produces compact LLM payload
* `scrape()` — Executes pipeline + attaches diagnostics metadata

### Supported Platforms & Data Sources

| Platform | Class | Primary Extraction Sources | Unique Capabilities |
| :--- | :--- | :--- | :--- |
| **Crexi** | `CrexiAdapter` | `data-cy` attributes, `header h1`, `crx-smart-about-property`, og meta tags | Cap Rate, NOI, Occupancy, NNN lease terms, Tenant Credit |
| **LoopNet** | `LoopNetAdapter` | `data-listing-*` attributes, `og:title`/image/desc, `.profile-hero`, `#property-facts`, `data-fields` JSON | Building Class, Building Height, Space/Suite breakdowns (`available_spaces`), PDF Brochure link, Broker cards |
| **Zillow** | `ZillowAdapter` *(stub)* | Reserved in registry for future residential integration | Zestimate, HOA, Bedrooms/Bathrooms *(future)* |

---

## 5. Database Architecture (`site_ranker.db`)

**Location**: `backend/site_ranker.db`  
**Primary Table**: `cart_items`

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `cart_item_id` | `TEXT PRIMARY KEY` | UUID string identifying the cart item |
| `session_id` | `TEXT NOT NULL` | Session UUID linking items to a user session |
| `address` | `TEXT NOT NULL` | Property physical street address |
| `source_url` | `TEXT` | Original listing URL (Crexi, LoopNet, etc.) |
| `listing_title` | `TEXT` | Commercial listing headline |
| `image_url` | `TEXT` | Primary hero image URL |
| `details` | `TEXT (JSON)` | **100% Raw Scraped Data** (unaltered key-values for provenance & audit) |
| `llm_structured` | `TEXT (JSON)` | **Clean LLM Schema v1.0** (typed, deduplicated, normalized for LLM inference) |
| `added_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp of creation |

### Additional Tables

#### `mireye_cache`
Additive field cache keyed by normalized address. Merges newly fetched Mireye fields without overwriting existing entries.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `cache_key` | `TEXT PRIMARY KEY` | Normalized address string from Mireye geocoder |
| `fields` | `TEXT NOT NULL (JSON)` | Additive JSON blob: `{field_name: {value, unit, source, ...}}` |
| `last_updated` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

#### `evaluations`
Stores 5-agent council evaluation reports and synthesizer verdicts.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `evaluation_id` | `TEXT PRIMARY KEY` | UUID string identifying the evaluation |
| `cart_item_id` | `TEXT NOT NULL` | Foreign key to `cart_items` |
| `overall_score` | `INTEGER` | Synthesized 0-100 score |
| `recommendation` | `TEXT` | One-sentence executive verdict |
| `conflicts_flagged` | `TEXT (JSON)` | Array of cross-agent tensions & listing-vs-Mireye disagreements |
| `agent_results` | `TEXT NOT NULL (JSON)` | Array of 5 agent result objects with citations |
| `created_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

---

## 6. LLM Structured Schema Specification (`schema_version: "1.0"`)

The `build_llm_structured_data()` function in `backend/main.py` converts raw scrape key-value pairs into a clean, non-redundant schema specifically designed for LLM prompts:

```json
{
  "schema_version": "1.0",
  "identity": {
    "address": "667 Madison Ave, New York, NY 10065",
    "listing_title": "667 Madison Ave, New York, NY 10065 - Office for Lease",
    "source_url": "https://www.loopnet.com/Listing/667-Madison-Ave-New-York-NY/20044350/",
    "image_url": "https://images1.loopnet.com/i2/..."
  },
  "property": {
    "property_type": "Office",
    "sub_type": null,
    "building_sqft": 257210,
    "lot_acres": null,
    "year_built": 1985,
    "building_class": "A",
    "stories": 25,
    "units": null,
    "buildings": null
  },
  "financials": {
    "asking_price_display": "Upon Request",
    "asking_price": null,
    "cap_rate_percent": null,
    "noi_annual": null,
    "occupancy_percent": null,
    "price_per_sqft": null
  },
  "lease": {
    "tenant": null,
    "tenancy": null,
    "lease_type": null,
    "lease_term_years": null,
    "lease_commencement": null,
    "lease_expiration": null,
    "rent_bumps": null,
    "lease_options": null
  },
  "investment": {
    "investment_type": null,
    "tenant_credit": null,
    "ownership": null,
    "ground_lease": null,
    "broker_co_op": null
  },
  "listing_freshness": {
    "days_on_market": null,
    "days_since_update": null
  },
  "narrative": {
    "description": "Rising 25 stories above Midtown Manhattan...",
    "highlights": []
  }
}
```

---

## 7. Endpoints & API Reference (`backend/main.py`)

Backend server runs with FastAPI on `http://localhost:8000`:

* `GET /` — API root dashboard returning service info, documentation links, and endpoint paths.
* `GET /health` — Health check endpoint (`{"status": "ok", "version": "0.3.2"}`).
* `GET /docs` — Interactive Swagger UI documentation.
* `POST /cart-items` — Accepts raw listing data from extension content scripts, generates `llm_structured` schema, and inserts into `site_ranker.db`.
* `GET /cart-items?session_id=<UUID>` — Retrieves all cart items for a given session, ordered newest first.

---

## 8. Integration with Mireye Earth API

Address strings stored in `site_ranker.db` are processed by the companion `mireye` service (`C:\Users\nayak\Desktop\mireye`):

1. `fetch_from_db_sample.py` queries `cart_items` in `site_ranker.db` to extract address strings.
2. `MireyeClient` invokes `https://api.mireye.com/v1/fetch` with the address string.
3. Retrieves environmental, terrain, infrastructure, and risk datasets:
   - `elevation` & `slope_degrees` (USGS 3DEP)
   - `tree_canopy_pct` & `land_use_class` (USFS NLCD / LCMS)
   - `nearest_major_road_distance_m` (Overture Transportation)
   - `ndvi_current` & `coast_distance_m`

---

## 9. Verification & Quality Status

* **Unit Tests**: Executed `python -m unittest test_normalizer.py` inside `backend/`.
  * **Result**: `8/8 tests PASSED` (0.001s).
  * Validates sale price numeric extraction, lease rate display parsing, date ISO conversion, boolean parsing, and field fallback handling.
* **Crexi Extraction Parity**: Verified that refactoring Crexi into `CrexiAdapter` maintains **100% extraction parity** with previous captures (23+ details fields preserved identically).
* **LoopNet Multi-Source Pipeline**: 12 extraction sources verified against real listing HTML fixtures.
