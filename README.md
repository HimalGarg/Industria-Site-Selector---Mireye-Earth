# Industria Site Selector - Mireye Earth

An advanced, AI-driven commercial real estate (CRE) site selection and due diligence platform. It combines an intelligent Chrome Extension scraper with a powerful Python backend and React frontend to automate property evaluation, compliance checking, and radius recommendations.

## Core Features

1. **Intelligent Web Scraper (Chrome Extension)**
   - Automatically scrapes real estate and business listings from Crexi and LoopNet.
   - Intelligently bypasses SPA (Single Page Application) routing maps to extract true listing links (`/properties/`, `/businesses/`, `/lease/`).
   - Uses OpenAI API batch-processing to convert messy URL slugs into perfect physical addresses for downstream geocoding.

2. **Rule-Based Recommendation Engine**
   - Discards generic radial searches in favor of a precise **True Geodesic Distance (Haversine)** calculation via OpenStreetMap/Google geocoders.
   - Evaluates comparable properties on a strict 100-point scale based on Geographic Proximity (50 points), Asset Type Match (30 points), and Financial Price Similarity (20 points).

3. **AI-Powered Compliance & Regulatory Engine**
   - Interrogates municipal Open Data portals (Chicago, NYC, SF) for building permits, occupancy certificates, fire codes, and zoning violations.
   - **LLM Regulatory Fallback**: If municipal data is unavailable, it automatically queries an OpenAI Regulatory Agent (`gpt-4o-mini`) to synthesize the exact zoning, fire, and commercial compliance baseline for that specific jurisdiction, rendering it seamlessly in the UI.

4. **Multi-Agent Evaluation Council**
   - Runs a concurrent council of AI agents (Energy, Transport, Environmental, Risk) to evaluate the feasibility of the site against specific industrial requirements.

---

## Complete Build & Execution Guide

### Prerequisites
- **Node.js** (v18+)
- **Python** (3.10+)
- **Chrome/Chromium Browser**

### 1. Setup the Backend (FastAPI)
The backend handles the AI agents, the local SQLite database, and the geocoding engines.

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Environment Variables:**
Create a `.env` file in the `backend/` directory:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

**Run the Server:**
```bash
uvicorn main:app --reload --port 8000
```
*(The backend runs on `http://localhost:8000`)*

### 2. Setup the Frontend (React + Vite)
The frontend is a modern React application that renders the property pipeline and compliance dashboards.

```bash
cd frontend
npm install
npm run build   # Optional: verifies TypeScript compilation
npm run dev
```
*(The frontend runs on `http://localhost:5173`)*

### 3. Install the Chrome Extension
The Chrome Extension acts as the bridge between commercial real estate websites (Crexi/LoopNet) and your local pipeline.

1. Open Chrome and navigate to `chrome://extensions/`.
2. Enable **"Developer mode"** in the top right corner.
3. Click **"Load unpacked"**.
4. Select the `extension/` folder located in this repository.
5. *Note: If you ever modify the extension files (like `background.js`), you MUST click the circular "Refresh" icon on the extension card in Chrome for the changes to take effect in memory!*

### Usage
1. Open a commercial listing on Crexi or LoopNet.
2. Click the Mireye extension icon in your Chrome toolbar.
3. The extension will parse the property and push it to your frontend Property Pipeline.
4. From the frontend, you can trigger Radius Recommendations, Compliance Audits, and Agent Evaluations.

---
*Built by the Mireye Earth Team.*
