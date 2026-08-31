# Industria Site Selector — Build Guide

This document outlines the step-by-step instructions for setting up, building, and running the Industria Site Selector locally for development and production.

## 🛠️ Prerequisites

Before getting started, ensure you have the following installed on your machine:
- **Node.js** (v18 or higher) - For building the React frontend
- **Python** (3.10 or higher) - For running the FastAPI backend
- **Google Chrome** - For installing and testing the Manifest V3 extension
- **Git** - For cloning the repository

## 📦 1. Clone the Repository

```bash
git clone https://github.com/HimalGarg/Industria-Site-Selector---Mireye-Earth.git
cd Industria-Site-Selector---Mireye-Earth
```

## 🔐 2. Environment Configuration

You will need API keys for OpenAI and Mireye Earth. Create a `.env` file in the `backend/` directory:

```bash
cd backend
cp .env.example .env
```

Edit the `.env` file to include your credentials:
```env
# OpenAI API Keys
OPENAI_API_KEY="sk-proj-..."
OPENAI_MODEL="gpt-4o"
OPENAI_MODEL_LIGHT="gpt-4o-mini"

# Mireye Earth API
MIREYE_API_KEY="your_mireye_key_here"
MIREYE_BASE_URL="https://api.mireye.earth"
```

## ⚙️ 3. Backend Setup (FastAPI)

The backend handles the 5-Agent Council evaluation, SQLite database, and API endpoints.

```bash
cd backend

# Create a Python virtual environment
python -m venv venv

# Activate the virtual environment
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Start the development server
python -m uvicorn main:app --reload --port 8000
```
- The backend API will be available at `http://localhost:8000`
- Interactive Swagger documentation is at `http://localhost:8000/docs`

## 🖥️ 4. Frontend Setup (React + Vite)

The frontend is a React application styled with TailwindCSS.

```bash
# From the root directory, navigate to the frontend
cd frontend

# Install Node modules
npm install

# Start the Vite development server
npm run dev
```
- The React frontend will be available at `http://localhost:5173`

### Building Frontend for Production
To build the frontend for production deployment:
```bash
npm run build
```
The compiled assets will be placed in the `frontend/dist/` directory.

## 🧩 5. Chrome Extension Setup

The Chrome extension acts as the bridge for capturing commercial listings.

1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Enable **Developer mode** using the toggle switch in the top right corner.
3. Click on the **Load unpacked** button.
4. Select the `extension/` directory from the cloned repository folder.
5. The extension should now be installed and visible in your browser toolbar.

To test the extension:
- Navigate to a property listing on [Crexi](https://www.crexi.com) or [LoopNet](https://www.loopnet.com).
- Open the extension and click the **Add to Site Ranker** button to extract the property data.

## 🧪 6. Running Tests

The backend includes comprehensive test suites for various modules. To run them, make sure your virtual environment is active in the `backend/` directory:

```bash
cd backend

# Run LLM Schema Normalizer tests
python -m unittest test_normalizer.py

# Run Agent Council Pipeline tests
python test_evaluation_pipeline.py -v

# Run Chat & Memory tests
python test_chat_pipeline.py -v

# Run Multi-Site Comparison tests
python test_compare_pipeline.py -v
```

## 🚀 Deployment Considerations

- **Backend**: Can be containerized via Docker and deployed to a service like AWS ECS, Heroku, or Render. Make sure to persist the SQLite database or migrate to PostgreSQL.
- **Frontend**: The `dist/` folder can be hosted on static hosting services like Vercel, Netlify, or AWS S3. Ensure `.env` files are updated with the production backend URL.
- **Extension**: Can be zipped and uploaded to the Chrome Web Store for public distribution.

## ❓ Troubleshooting

- **Backend connection refused**: Ensure the backend is running on port 8000.
- **Frontend API errors**: Ensure that the backend server is reachable from the frontend and there are no CORS issues.
- **Extension not extracting data**: Crexi or LoopNet DOM structures might have changed. You may need to inspect the elements and update the selectors in `extension/content.js`.
