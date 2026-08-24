# Site Ranker Capture & AI Evaluation System — Build Context

## 1. Executive Summary

This repository (`chrome extension`) contains the **Site Ranker Capture & Intelligence Platform** consisting of three core tiers:
1. **Manifest V3 Chrome Extension** (`extension/` v0.2): One-click multi-site listing capture for **Crexi** and **LoopNet** with an in-page dark neon capture button and toolbar popup.
2. **FastAPI Backend Server, 5-Agent Council Engine, Chat Router & Multi-Site Comparison** (`backend/` v0.3.5):
   - Cart items storage, raw provenance preservation (`details`), canonical LLM schema v1.0 normalization (`llm_structured`), duplicate listing prevention.
   - Additive Mireye GIS location intelligence cache (`mireye_cache`).
   - 5-agent council evaluation pipeline (`evaluations`).
   - Grounded Site Chat, LLM Field Router, Listing Memory & Session Context Engine (`backend/chat/`).
   - Multi-Site Side-by-Side Comparison & Synthesizer Engine (`backend/evaluate/compare_router.py`).
3. **React Web Application Dashboard** (`frontend/` v0.3.4): Built with React 18, Vite, and TailwindCSS adhering to the **Obsidian Intelligence** dark design system (#0B0F17 background, #151C28 glass surfaces, #4EDEA3 electric emerald). Features a Bento-grid property pipeline with 4s auto-polling, dual facts toggle (Clean LLM Facts vs Raw Provenance), property deletion, evaluation status badges, and a slide-over 5-Agent Council evaluation report drawer.

---

## 2. Directory & Repository Structure

```text
chrome extension/
├── extension/                        # Manifest V3 Chrome Extension Source
│   ├── manifest.json                 # Manifest V3 config & content script bindings
│   ├── popup.html / popup.js         # Toolbar popup UI (session sync, quick preview, instant capture)
│   ├── content-crexi.js              # CrexiAdapter for Crexi property detail pages
│   ├── content-loopnet.js            # LoopNetAdapter for LoopNet property detail pages
│   ├── content-session.js            # Syncs session_id between web app localStorage & extension
│   ├── background.js                 # Service worker handling storage & background sync
│   └── scrapers/                     # Pluggable Adapter Framework
│       ├── base-adapter.js           # BaseAdapter class (button injection, dark neon styling, click handler)
│       ├── normalize.js              # Pure normalization helper functions
│       ├── llm-formatter.js          # Shared LLM payload formatter
│       └── website-registry.js       # Hostname matching registry & capability matrix
│
├── backend/                          # FastAPI Server, Cart API, Chat, Memory & Comparison Engines
│   ├── evaluate/                     # 5-Agent Council Evaluation & Multi-Site Comparison Pipeline
│   │   ├── config.py                 # 58-field Mireye inventory mapping & agent settings
│   │   ├── mireye_fetcher.py         # Mireye API wrapper, geocode fallback handler & additive cache
│   │   ├── agents.py                 # 5 concurrent OpenAI LLM agents (Energy, Water, Surface, Transport, Risk)
│   │   ├── synthesizer.py            # Council synthesizer (score 0-100, verdict memo, conflict flagger)
│   │   ├── compare_synthesizer.py    # Multi-site comparison narrative & trade-offs synthesizer
│   │   ├── compare_router.py         # POST /compare-sites endpoint (2-4 site range, score flattening)
│   │   └── router.py                 # Async evaluation endpoints (/evaluate-site)
│   ├── chat/                         # Site Chat, Router & Memory Layer
│   │   ├── router_engine.py          # LLM router for Mireye field expansion (max 5 fields cap)
│   │   ├── answer_generator.py       # Grounded answer generation with source citations (mireye, listing, memory)
│   │   ├── memory_engine.py          # Background atomic listing memory extraction & session context summarizer
│   │   └── router.py                 # Chat endpoints (POST /chat, GET /chat, GET /listing-memory, GET /session-context)
│   ├── main.py                       # FastAPI application & SQLite migration handlers (v0.3.5)
│   ├── site_ranker.db                # SQLite database storing cart items, cache, evaluations & chat memory
│   ├── test_normalizer.py            # Unit test suite for LLM schema normalizer
│   ├── test_evaluation_pipeline.py    # Integration test suite for 5-agent council pipeline
│   ├── test_chat_pipeline.py          # Integration test suite for Chat, Router & Memory pipeline
│   ├── test_compare_pipeline.py       # Integration test suite for Multi-Site Comparison pipeline
│   ├── .env.example                  # Template for secrets (OPENAI_API_KEY, MIREYE_API_KEY)
│   └── requirements.txt              # Dependencies (fastapi, uvicorn, pydantic, openai)
│
├── frontend/                         # React 18 + Vite + TailwindCSS Web Application
│   ├── index.html                    # HTML entry point with Google Fonts (Outfit & Inter)
│   ├── package.json                  # Dependencies (react, vite, tailwindcss, lucide-react)
│   ├── tailwind.config.js            # Obsidian Intelligence theme tokens
│   ├── postcss.config.js             # PostCSS Tailwind config
│   ├── tsconfig.json                 # TypeScript compiler configuration
│   ├── vite.config.ts                # Vite dev server configuration
│   └── src/
│       ├── main.tsx                  # React DOM root entry
│       ├── index.css                 # Glassmorphic utilities, animations, scrollbars
│       ├── api.ts                    # Backend API client wrapper with type definitions
│       └── App.tsx                   # Main Dashboard UI & 5-Agent Evaluation Slide-Over Drawer
│
├── docs/                             # Architecture specifications & documentation
│   └── build_context.md              # [THIS FILE] System build context & technical specifications
└── README.md                         # Main repository setup & user operational guide
```

---

## 3. Data & Storage Architecture

### Database Tables (`site_ranker.db`)

#### `cart_items`
Stores raw scraped listing payloads alongside canonical LLM schema v1.0 objects. Prevents duplicates by updating existing records on matching `session_id` + `source_url` or `address`.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `cart_item_id` | `TEXT PRIMARY KEY` | UUID string identifying the cart item |
| `session_id` | `TEXT NOT NULL` | Session UUID linking items to a user session |
| `address` | `TEXT NOT NULL` | Property physical street address |
| `source_url` | `TEXT` | Original listing URL (Crexi, LoopNet, etc.) |
| `listing_title` | `TEXT` | Commercial listing headline |
| `image_url` | `TEXT` | Primary hero image URL |
| `details` | `TEXT (JSON)` | **100% Raw Scraped Data** (unaltered key-values for provenance & audit) |
| `llm_structured` | `TEXT (JSON)` | **Clean LLM Schema v1.0** (typed, deduplicated, canonical JSON) |
| `added_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp of creation |

#### `mireye_cache`
Additive field cache keyed by normalized address string. Merges newly fetched Mireye GIS fields without overwriting existing entries.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `cache_key` | `TEXT PRIMARY KEY` | Normalized address string from Mireye geocoder |
| `fields` | `TEXT NOT NULL (JSON)` | Additive JSON blob: `{field_name: {value, unit, source, ...}}` |
| `last_updated` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

#### `evaluations`
Stores 5-agent council evaluation reports and synthesizer verdicts.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `evaluation_id` | `TEXT PRIMARY KEY` | UUID string identifying the evaluation job |
| `cart_item_id` | `TEXT NOT NULL` | Foreign key to `cart_items` |
| `overall_score` | `INTEGER` | Synthesized 0-100 score |
| `recommendation` | `TEXT` | Executive board verdict (`Highly Recommended`, `Proceed with Caution`, `Not Recommended`) |
| `conflicts_flagged` | `TEXT (JSON)` | Array of cross-agent tensions & listing-vs-Mireye disagreements |
| `agent_results` | `TEXT NOT NULL (JSON)` | Array of 5 agent result objects with grounded citations |
| `created_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

#### `listing_memory`
Append-only store for atomic, listing-specific facts extracted from user chat turns.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `memory_id` | `TEXT PRIMARY KEY` | UUID string identifying the memory entry |
| `cart_item_id` | `TEXT NOT NULL` | Foreign key to `cart_items` |
| `session_id` | `TEXT NOT NULL` | Session UUID |
| `fact` | `TEXT NOT NULL` | Single atomic fact string |
| `created_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

#### `session_context`
Single-row snapshot per session storing re-summarized user intent and priorities across all sites.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `session_id` | `TEXT PRIMARY KEY` | Session UUID |
| `summary` | `TEXT NOT NULL` | Unified single-paragraph snapshot summary |
| `updated_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

#### `chat_messages`
Turn-by-turn chat conversation log for each listing.

| Column Name | SQL Type | Description |
| :--- | :--- | :--- |
| `message_id` | `TEXT PRIMARY KEY` | UUID string identifying the message |
| `cart_item_id` | `TEXT NOT NULL` | Foreign key to `cart_items` |
| `session_id` | `TEXT NOT NULL` | Session UUID |
| `role` | `TEXT NOT NULL` | `"user"` or `"assistant"` |
| `content` | `TEXT NOT NULL` | Message body text |
| `citations` | `TEXT (JSON)` | Array of citation objects: `[{"source": "mireye"\|"listing"\|"memory", ...}]` |
| `created_at` | `TEXT NOT NULL` | ISO 8601 UTC timestamp |

---

## 4. Endpoints & API Reference (`backend/main.py`)

Backend server runs with FastAPI on `http://localhost:8000`:

### Core Cart & Health Endpoints
* `GET /` — Service dashboard returning version info and API navigation paths.
* `GET /health` — Health check endpoint (`{"status": "ok", "service": "site-ranker-cart", "version": "0.3.5"}`).
* `GET /docs` — Interactive Swagger UI documentation.
* `POST /cart-items` — Accepts captured listing data from content script into SQLite database (prevents duplicate entries).
* `GET /cart-items?session_id=<optional>` — Returns all cart items (filtered by session_id if provided), ordered newest first.
* `DELETE /cart-items/{cart_item_id}` — Deletes listing and all associated evaluations, chat messages, and memory records.

### 5-Agent Council Evaluation Endpoints
* `POST /evaluate-site` — Triggers non-blocking 5-agent evaluation job (`{"cart_item_id": "..."}`).
* `GET /evaluate-site/{evaluation_id}` — Polls evaluation status & retrieves full 5-agent council report when `status` is `"done"`.
* `GET /evaluate-site?cart_item_id=<optional>` — Lists historical evaluations for a cart item.

### Multi-Site Comparison Endpoint
* `POST /compare-sites` — Compares 2 to 4 cart items side-by-side. Returns flattened `agent_scores`, `missing_evaluation` flags, executive `comparison_narrative`, and discipline `trade_offs`.

### Site Chat & Memory Endpoints
* `POST /chat` — Synchronous chat turn endpoint. Evaluates router for Mireye field expansion (max 5 fields cap), generates grounded answers with citations, and triggers background memory extraction & session context summarization.
* `GET /chat?cart_item_id=<id>` — Returns full chat message history for a listing.
* `GET /listing-memory?cart_item_id=<id>` — Returns all atomic memory facts for a listing.
* `GET /session-context?session_id=<id>` — Returns current session context summary snapshot.

---

## 5. Verification & Testing

* **Normalizer Unit Tests**: Run `python -m unittest test_normalizer.py` inside `backend/` (8/8 tests PASSED).
* **Evaluation Pipeline Integration Tests**: Run `python test_evaluation_pipeline.py -v` inside `backend/` (9/9 tests PASSED).
* **Chat, Router & Memory Pipeline Tests**: Run `python test_chat_pipeline.py -v` inside `backend/` (7/7 tests PASSED).
* **Multi-Site Comparison Pipeline Tests**: Run `python test_compare_pipeline.py -v` inside `backend/` (4/4 tests PASSED).
* **Frontend Production Build**: Run `npm run build` inside `frontend/` (0 errors, dist bundle generated cleanly).
