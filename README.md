# Site Ranker Capture — Multi-Site Chrome Extension & LLM Normalization Engine

A Manifest V3 Chrome Extension (v0.2) and FastAPI Backend Server for multi-site commercial real estate listing capture (**Crexi**, **LoopNet**, and extensible for **Zillow**). Extracts raw listing facts, normalizes them into typed JSON for LLM processing, and persists them for location intelligence enrichment.

---

## Key Features

* 📍 **One-Click Listing Capture**: Injects a dark/neon "Add to Site Ranker" button directly onto Crexi and LoopNet property detail pages.
* 🏗 **Multi-Site Adapter Framework**: Extensible architecture separating website scraping, raw data preservation, common normalization, and LLM output formatting.
* 🤖 **LLM Normalization Engine**: Automatically cleans asking prices, square footage, cap rates, NOI, occupancy, and lease terms into a typed `schema_version: "1.0"` canonical payload (`llm_structured`).
* 🏷 **Visual Site Badges**: Identifies capture source (`Crexi` or `LoopNet`) in the extension popup with site-specific colors.
* 🔗 **Session Synchronization**: Auto-syncs session ID between web application `localStorage` and `chrome.storage.local`.

---

## Folder Structure

```text
chrome extension/
├── extension/          ← Load this folder in Chrome (Clean Extension Source)
│   ├── manifest.json   (v0.2 multi-site config & content script bindings)
│   ├── popup.html / popup.js
│   ├── content-crexi.js      (Crexi Adapter)
│   ├── content-loopnet.js    (LoopNet Adapter)
│   ├── content-session.js    (Website session sync)
│   ├── content.js            (Manual text highlight capture)
│   ├── background.js
│   ├── scrapers/             (Adapter Framework)
│   │   ├── base-adapter.js
│   │   ├── normalize.js
│   │   ├── llm-formatter.js
│   │   └── website-registry.js
│   └── icons/
├── backend/            ← FastAPI cart API & LLM normalizer
│   ├── main.py
│   ├── test_normalizer.py
│   └── requirements.txt
├── docs/               ← Multi-site scraping guides & selector docs
├── fixtures/           ← HTML test fixtures
└── scratch/            ← Database audit & comparison scripts
```

---

## Quick Start

### 1. Running the Backend Server

```bash
# Navigate to the backend directory:
cd backend

# Install dependencies:
pip install -r requirements.txt

# Start FastAPI server with live reload:
python -m uvicorn main:app --reload --port 8000
```

* Backend API Root: `http://localhost:8000/`
* Interactive API Documentation (Swagger UI): `http://localhost:8000/docs`
* Health Check: `http://localhost:8000/health`

### 2. Loading the Extension in Chrome

1. Open Chrome and navigate to `chrome://extensions`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked** and select the `extension/` folder in this repository
4. The **Site Ranker Capture** icon will appear in your Chrome toolbar

---

## Data Architecture

```text
Listing Page (Crexi / LoopNet)
            │
            ▼ (Adapter: CrexiAdapter / LoopNetAdapter)
 Raw Scraped Record (extractRaw())
            │
            ▼ (Normalization: normalize())
 Common Fields + Website-Specific Fields
            │
            ▼ (LLM Formatter: formatForLLM())
 POST /cart-items (FastAPI Backend)
 ┌──────────┴────────────────────────┐
 ▼                                   ▼
details column                      llm_structured column
(Raw key-values for provenance)     (Typed canonical schema v1.0)
 └──────────┬────────────────────────┘
            ▼
   SQLite Database (site_ranker.db)
```

---

## API Reference

### `POST /cart-items`
Accepts captured listing data from content scripts, builds the LLM normalization payload, and inserts the record into SQLite.

### `GET /cart-items?session_id=<UUID>`
Retrieves all captured listings for a given session, ordered newest first.

### `GET /`
API root dashboard with quick navigation to `/docs`, `/health`, and endpoints.

---

## Deployment Checklist

When deploying to production:

1. **`extension/manifest.json`**: Update `host_permissions` and `content_scripts.matches` with your production domain.
2. **`extension/popup.js`**: Update `WEBSITE_URL` (near top of file) to your production web app URL.
3. **`backend/main.py`**: Update `CORSMiddleware` `allow_origins` to restrict requests to your domain and extension ID.
