# Site Ranker — Commercial Real Estate Intelligence Platform

**Site Ranker** is an end-to-end commercial real estate site selection platform consisting of:
1. **Manifest V3 Chrome Extension** (`extension/`): One-click listing capture on **Crexi** and **LoopNet** with an in-page dark neon capture button and toolbar popup.
2. **FastAPI Backend & 5-Agent Council Evaluation Engine** (`backend/` v0.3.5):
   - SQLite persistence (`site_ranker.db`) with raw scraped data provenance preservation (`details`) and canonical LLM schema normalization (`llm_structured`).
   - 5-Agent Council Audit Engine (Energy, Water, Surface, Transport, Risk) querying 58 physical/regulatory GIS datasets via **Mireye Earth API**.
   - Grounded Site Intelligence Chat & LLM Field Expansion Router (`backend/chat/`).
   - Atomic Listing Memory Notes & Cross-Site Session Context Summarizer.
   - Multi-Site Side-by-Side Comparison & Trade-Offs Synthesis Engine (`POST /compare-sites`).
3. **React Web Application Dashboard** (`frontend/`): Built with React 18, Vite, and TailwindCSS adhering to the **Obsidian Intelligence** dark design system (#0B0F17 background, #151C28 glass surfaces, #4EDEA3 electric emerald). Features a Bento-grid property pipeline, client-side routing, tabbed audit reports, interactive site chat, memory notes, and multi-site comparison matrix.

---

## 🔑 Environment Configuration (`backend/.env`)

Create a `.env` file in the `backend/` directory. Do **NOT** commit your `.env` file to Git repository.

### Example `backend/.env` Configuration

```env
# ---------------------------------------------------------------------------
# OpenAI API Key (Required for 5-Agent Council, Chat, & Synthesis)
# ---------------------------------------------------------------------------
OPENAI_API_KEY=sk-proj-...your_openai_key_here
OPENAI_MODEL=gpt-4o
OPENAI_MODEL_LIGHT=gpt-4o-mini

# ---------------------------------------------------------------------------
# Mireye Earth API Key (Required for GIS Location Intelligence)
# ---------------------------------------------------------------------------
MIREYE_API_KEY=eyJhbGciOi...your_mireye_key_here
MIREYE_BASE_URL=https://api.mireye.earth
```

---

## 🚀 Quick Start Guide

### Step 1: Start the FastAPI Backend Server

```bash
# 1. Navigate to the backend folder
cd backend

# 2. Create and activate a virtual environment (optional but recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Create your .env file with your API keys (see Environment Configuration above)
# On Windows PowerShell:
# Copy-Item .env.example .env

# 5. Launch the FastAPI server
python -m uvicorn main:app --reload --port 8000
```

Backend will be running at:
* 🌐 **API Dashboard**: `http://localhost:8000/`
* 📖 **Interactive Swagger UI Docs**: `http://localhost:8000/docs`
* ❤️ **Health Check**: `http://localhost:8000/health`

---

### Step 2: Start the React Web Dashboard

Open a new terminal tab/window:

```bash
# 1. Navigate to the frontend folder
cd frontend

# 2. Install dependencies
npm install

# 3. Launch Vite development server
npm run dev
```

Dashboard will be running at:
* 🖥️ **Site Ranker Dashboard**: `http://localhost:5173/`

---

### Step 3: Install the Chrome Extension

1. Open Google Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (toggle switch in top-right corner).
3. Click **Load unpacked**.
4. Select the `extension/` directory from this repository.
5. Pin **Site Ranker Capture** to your Chrome toolbar.
6. Browse any property listing detail page on **Crexi** or **LoopNet** and click the injected **"Add to Site Ranker"** button to capture properties into your pipeline!

---

## 🧪 Running Automated Test Suites

The backend includes 4 test suites to verify functionality:

```bash
cd backend

# 1. LLM Schema Normalizer Unit Tests (8/8)
python -m unittest test_normalizer.py

# 2. 5-Agent Council Evaluation Engine Integration Tests (9/9)
python test_evaluation_pipeline.py -v

# 3. Site Intelligence Chat, Router & Memory Tests (7/7)
python test_chat_pipeline.py -v

# 4. Multi-Site Comparison Pipeline Tests (4/4)
python test_compare_pipeline.py -v
```

---

## 🔌 API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/cart-items` | Save/update listing captured from Chrome Extension |
| `GET` | `/cart-items` | Retrieve captured properties |
| `DELETE` | `/cart-items/{id}` | Delete listing and all associated reports/chats |
| `POST` | `/evaluate-site` | Trigger 5-agent council evaluation audit |
| `GET` | `/evaluate-site/{id}` | Poll evaluation audit status & retrieve 5-agent report |
| `POST` | `/chat` | Synchronous site intelligence chat turn (with router field expansion & citations) |
| `GET` | `/chat` | Retrieve full chat thread history for a property |
| `GET` | `/listing-memory` | Retrieve atomic listing takeaway notes |
| `POST` | `/compare-sites` | Side-by-side comparison of 2-4 sites with score matrix & trade-offs synthesis |
| `GET` | `/health` | Health check endpoint |

---

## 🛠 Tech Stack

- **Extension**: Chrome Manifest V3, Pluggable Scraping Adapter Pattern.
- **Backend**: Python 3.10+, FastAPI, Uvicorn, SQLite, OpenAI API (JSON Mode), Mireye Earth GIS API.
- **Frontend**: React 18, Vite, TypeScript, TailwindCSS, Lucide/Google Symbols Icons.
