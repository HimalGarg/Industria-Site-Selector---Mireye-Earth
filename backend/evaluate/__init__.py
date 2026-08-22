"""
backend/evaluate — Site Evaluation Pipeline
============================================

Produces a full council evaluation report for a given cart_item_id:

  1. Fetches location intelligence from Mireye API (with additive SQLite cache)
  2. Runs 5 specialized site-analysis agents concurrently via Gemini
  3. Synthesizes a board-readable report with scores, citations, and conflicts
  4. Persists the result to the `evaluations` table

Modules:
  config.py         — AGENT_FIELD_MAP, IDENTITY_FIELDS constants
  mireye_fetcher.py — Mireye client wrapper + cache read/write logic
  agents.py         — The 5 concurrent LLM agents
  synthesizer.py    — Synthesizer LLM call (overall score + conflicts)
  router.py         — FastAPI router exposing /evaluate-site endpoints
"""
