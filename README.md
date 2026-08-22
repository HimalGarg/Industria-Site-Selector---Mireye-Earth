# Site Ranker Capture & AI Evaluation Platform

A Manifest V3 Chrome Extension and FastAPI Backend Platform for commercial real estate (**Crexi** & **LoopNet**). Instantly capture listings from your browser, clean and normalize property data with LLMs, and run a **5-Agent Council Site Evaluation** grounded in **Mireye Earth** physical and regulatory location intelligence.

---

## 🌟 What Is Built

### 1. Browser Extension (`extension/`)
* 📍 **One-Click Listing Capture**: Injects a dark/neon **"Add to Site Ranker"** button directly onto Crexi and LoopNet property detail pages.
* 🏷 **Visual Badges**: Distinguishes capture source (`Crexi` or `LoopNet`) in the popup UI.
* 🔗 **Session Sync**: Auto-syncs session ID between web app `localStorage` and `chrome.storage.local`.

### 2. FastAPI Backend (`backend/main.py`)
* 📦 **Dual Data Architecture**: Preserves 100% raw scraped key-values (`details`) for audit provenance while generating clean, typed JSON (`llm_structured` v1.0 schema).
* 💾 **SQLite Persistence**: Stores listings, location intelligence caches, and evaluation reports in `site_ranker.db`.

### 3. 5-Agent Council Evaluation Engine (`backend/evaluate/`)
Runs 5 specialized AI agents concurrently to evaluate any captured property:
1. ⚡ **Energy & Power Infrastructure Agent**: High-voltage lines, substations, gas pipelines, power plant proximity.
2. 💧 **Water & Watershed Agent**: Water/wastewater service areas, wetlands, flood risk, watershed boundaries.
3. 🏔 **Surface & Environment Agent**: Soil type, elevation, slope, karst risk, land cover, NDVI vegetation index.
4. 🚗 **Transportation & Access Agent**: Nearest highways, rail access, airport drive-times, port proximity.
5. ⚠️ **Risk & Compliance Agent**: FEMA flood zones, underground storage tanks (UST), orphaned oil wells, critical species habitats.

### 4. Location Intelligence & Additive Cache (`mireye_fetcher.py`)
* 🌍 **Mireye Earth API Integration**: Queries 58 physical/regulatory GIS datasets per property address.
* ⚡ **Additive `mireye_cache`**: Caches GIS fields per normalized address so repeat evaluations reuse existing data instantly without duplicate API calls.

### 5. Council Synthesizer (`synthesizer.py`)
* 📊 **Overall Site Score**: Calculates a 0-100 weighted score.
* 🎯 **Executive Verdict**: Generates a one-sentence board-ready recommendation (`Highly recommended`, `Proceed with caution`, `Not recommended`).
* ⚡ **Conflict Flagger**: Cross-references listing claims against Mireye physical facts (e.g. listing claims "all utilities on site" but Mireye flags "no public water service").

---

## 🚀 How to Access & Use

### Step 1: Environment Setup

1. Copy the environment template in the `backend/` folder:
   ```bash
   cd backend
   cp .env.example .env
   ```

2. Open `backend/.env` and fill in your API keys:
   ```env
   # OpenAI API key (required for AI agents + synthesizer)
   OPENAI_API_KEY=sk-proj-...your_key_here
   OPENAI_MODEL=gpt-4o-mini

   # Mireye Earth API key (required for GIS location intelligence)
   MIREYE_API_KEY=eyJhbGciOi...your_key_here
   ```

---

### Step 2: Start the Backend Server

```bash
# Navigate to the backend directory
cd backend

# Install dependencies
pip install -r requirements.txt

# Launch FastAPI server
python -m uvicorn main:app --reload --port 8000
```

Once started, access the backend at:
* 🌐 **API Dashboard**: `http://localhost:8000/`
* 📖 **Interactive Swagger UI Docs**: `http://localhost:8000/docs`
* ❤️ **Health Check**: `http://localhost:8000/health`

---

### Step 3: Install the Chrome Extension

1. Open Google Chrome and go to `chrome://extensions`
2. Turn on **Developer mode** (toggle switch in the top-right corner)
3. Click **Load unpacked**
4. Select the `extension/` directory from this repository
5. Pin **Site Ranker Capture** to your Chrome toolbar

---

### Step 4: Capture Property Listings

1. Navigate to any property detail page on **Crexi** or **LoopNet** (e.g., a commercial listing page).
2. Click the neon **"Add to Site Ranker"** button injected on the page (or click the extension icon in your toolbar).
3. The listing is instantly parsed, normalized into canonical JSON, and saved to your backend database!

---

### Step 5: Trigger a 5-Agent Site Evaluation

You can run evaluations directly via the interactive Swagger UI or curl:

#### Option A: Via Swagger UI (`http://localhost:8000/docs`)
1. Open `http://localhost:8000/docs` in your browser.
2. Under `evaluate`, click **`POST /evaluate-site`** -> **Try it out**.
3. Pass a captured `cart_item_id` (from `GET /cart-items`):
   ```json
   {
     "cart_item_id": "eea9a61c-694a-4034-a2c5-558460211507"
   }
   ```
4. Click **Execute**. The API returns `{ "evaluation_id": "...", "status": "processing" }`.
5. Copy the returned `evaluation_id` and open **`GET /evaluate-site/{evaluation_id}`** to poll for the complete 5-agent report!

#### Option B: Via Python Test Script
You can also run the automated evaluation suite against real cart items:
```bash
python test_evaluation_pipeline.py -v
```

---

## 📁 Repository Structure

```text
chrome extension/
├── extension/                      ← Load this folder in chrome://extensions
│   ├── manifest.json               (v0.2 Manifest V3 config & match rules)
│   ├── popup.html / popup.js       (Cart preview, source badges, session sync UI)
│   ├── content-crexi.js            (Crexi DOM scraper adapter)
│   ├── content-loopnet.js          (LoopNet DOM scraper adapter)
│   ├── content-session.js          (Web app session synchronization)
│   ├── background.js               (Service worker storage & background sync)
│   └── scrapers/                   (Pluggable Scraping & Normalization Framework)
│
├── backend/                        ← FastAPI Server & Evaluation Engine
│   ├── evaluate/                   ← 5-Agent Council Pipeline
│   │   ├── config.py               (58-field Mireye dataset inventory mapping)
│   │   ├── mireye_fetcher.py       (Mireye API client & additive SQLite cache)
│   │   ├── agents.py               (5 concurrent OpenAI agents)
│   │   ├── synthesizer.py          (Overall score, conflict flagger & verdict)
│   │   └── router.py               (Async non-blocking FastAPI endpoints)
│   ├── main.py                     (FastAPI app v0.3.3 & migration handlers)
│   ├── site_ranker.db              (SQLite storage for cart items, cache & evaluations)
│   ├── test_normalizer.py          (Unit tests for LLM data normalizer)
│   ├── test_evaluation_pipeline.py (Integration test suite for evaluation engine)
│   ├── .env.example                (Template for environment variables)
│   └── requirements.txt            (Dependencies: fastapi, uvicorn, openai)
│
└── docs/                           # Architecture guides & documentation
    └── build_context.md            # Technical specifications & database schemas
```

---

## 🔌 API Reference Quick Table

| Method | Path | Description |
| :--- | :--- | :--- |
| `POST` | `/evaluate-site` | Trigger async 5-agent site evaluation (`{ cart_item_id }`) |
| `GET` | `/evaluate-site/{evaluation_id}` | Poll evaluation status & retrieve full 5-agent council report |
| `GET` | `/evaluate-site?cart_item_id=...` | List all historical evaluations for a cart item |
| `POST` | `/cart-items` | Capture listing from content script into SQLite database |
| `GET` | `/cart-items?session_id=...` | Retrieve all captured listings for a user session |
| `GET` | `/health` | Health check endpoint (`{ "status": "ok", "version": "0.3.3" }`) |
