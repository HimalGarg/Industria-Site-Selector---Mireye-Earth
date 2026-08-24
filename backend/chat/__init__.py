"""
backend/chat/__init__.py — Site Chat, Router, and Memory Layer
================================================================

Subpackage components:
  - router_engine.py      — Decides if new Mireye GIS fields are needed & fetches them into cache
  - answer_generator.py   — Generates grounded answers with source citations (mireye, listing, memory)
  - memory_engine.py      — Fire-and-forget memory extraction & cross-site session context summarizer
  - router.py             — FastAPI endpoints (POST /chat, GET /chat, GET /listing-memory, GET /session-context)
"""
