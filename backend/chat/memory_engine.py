"""
backend/chat/memory_engine.py — Memory Extraction & Session Context Summarizer
================================================================================

Handles:
  1. Fire-and-forget background extraction of atomic facts into listing_memory.
  2. Cross-site session context re-summarization into session_context.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Background Memory Extraction (Fire-and-forget)
# ---------------------------------------------------------------------------


def trigger_memory_extraction_background(
    cart_item_id: str,
    session_id: str,
    user_message: str,
    assistant_content: str,
) -> None:
    """Spawns a daemon thread to extract durable atomic facts into listing_memory."""
    thread = threading.Thread(
        target=_extract_memory_sync,
        args=(cart_item_id, session_id, user_message, assistant_content),
        daemon=True,
    )
    thread.start()


def _extract_memory_sync(
    cart_item_id: str,
    session_id: str,
    user_message: str,
    assistant_content: str,
) -> None:
    """Analyzes a turn for durable atomic facts and inserts a row into listing_memory if found."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return

    model = os.environ.get("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a site intelligence memory agent for commercial real estate site selection.\n"
        "Analyze the conversation turn below and extract site-specific key findings, listing facts, "
        "and user requirement alignment for THIS property.\n\n"
        "Formulate atomic, concrete takeaway notes about the property itself, connecting user questions/requirements "
        "to the actual site capabilities revealed in the response.\n\n"
        "EXAMPLES:\n"
        "- Vague: 'User needs low flood danger.'\n"
        "  Site Takeaway: 'Site confirmed in FEMA Flood Zone X (minimal flood risk, outside 100-yr floodplain).'\n"
        "- Vague: 'User needs a good electric supply.'\n"
        "  Site Takeaway: 'Site has robust 256.7 MW power plant capacity & active 100-161 kV transmission line within 580m.'\n"
        "- Vague: 'User asked about cell towers.'\n"
        "  Site Takeaway: 'Site has 4 cell towers within 1.2km radius.'\n\n"
        "If the turn reveals any site facts, evaluation findings, or requirement alignment for this property, "
        "set has_fact = true and write a concise, professional site intelligence takeaway note.\n\n"
        "Return ONLY a JSON object with this schema:\n"
        "{\n"
        '  "has_fact": boolean,\n'
        '  "fact": "Concise, professional site intelligence note string"\n'
        "}"
    )

    user_prompt = (
        f"User Message: {user_message!r}\n"
        f"Assistant Response: {assistant_content!r}\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.0,
        )

        parsed = json.loads(response.choices[0].message.content or "{}")
        if parsed.get("has_fact") and parsed.get("fact"):
            fact_str = str(parsed["fact"]).strip()
            if fact_str:
                _insert_listing_memory(cart_item_id, session_id, fact_str)
                logger.info("[MEMORY EXTRACTED] cart_item_id=%s fact=%r", cart_item_id, fact_str)

    except Exception as e:
        logger.error("[MEMORY EXTRACT ERROR] %s", e)


def _insert_listing_memory(cart_item_id: str, session_id: str, fact: str) -> None:
    """Inserts a new listing memory row into SQLite database."""
    from main import get_db
    memory_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO listing_memory (memory_id, cart_item_id, session_id, fact, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory_id, cart_item_id, session_id, fact, created_at),
            )
            conn.commit()
    except Exception as e:
        logger.error("[MEMORY DB INSERT ERROR] %s", e)


# ---------------------------------------------------------------------------
# 2. Session Context Re-Summarization
# ---------------------------------------------------------------------------


def maybe_update_session_context(session_id: str, force_update: bool = False) -> None:
    """Triggers background re-summarization of cross-site session context."""
    thread = threading.Thread(
        target=_resummarize_session_context_sync,
        args=(session_id, force_update),
        daemon=True,
    )
    thread.start()


def _resummarize_session_context_sync(session_id: str, force_update: bool = False) -> None:
    """
    Pulls recent ~20 chat messages across ALL listings for this session_id,
    and updates session_context with a fresh 1-paragraph summary.
    """
    from main import get_db

    # Pull recent messages across all listings for session
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (session_id,),
        ).fetchall()

        current_row = conn.execute(
            "SELECT summary FROM session_context WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    if not rows:
        return

    # Trigger re-summarization every 4 messages or if forced
    if not force_update and len(rows) % 4 != 0 and current_row:
        return

    recent_messages = [dict(r) for r in reversed(rows)]
    existing_summary = current_row["summary"] if current_row else None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return

    model = os.environ.get("OPENAI_MODEL_LIGHT", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are a session context summarizer for an industrial real estate platform.\n"
        "Given recent user conversation turns across multiple sites in a session, produce a single, "
        "coherent 1-paragraph summary of what the user is looking for (e.g. key requirements, budget, "
        "must-have infrastructure, preferred regions, dealbreakers).\n\n"
        "IMPORTANT: Re-summarize into a fresh, unified paragraph. Do NOT append or concatenate bullet points.\n\n"
        "Return ONLY a JSON object:\n"
        "{\n"
        '  "summary": "Unified one-paragraph summary string"\n'
        "}"
    )

    user_prompt = (
        f"Existing Session Summary: {existing_summary or 'None'}\n\n"
        f"Recent Messages Across All Sites:\n"
        f"{json.dumps(recent_messages, indent=2)}\n"
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )

        parsed = json.loads(response.choices[0].message.content or "{}")
        new_summary = str(parsed.get("summary", "")).strip()

        if new_summary:
            updated_at = datetime.now(timezone.utc).isoformat()
            with get_db() as conn:
                conn.execute(
                    """
                    INSERT INTO session_context (session_id, summary, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET summary=excluded.summary, updated_at=excluded.updated_at
                    """,
                    (session_id, new_summary, updated_at),
                )
                conn.commit()
            logger.info("[SESSION CONTEXT UPDATED] session_id=%s summary=%r", session_id, new_summary)

    except Exception as e:
        logger.error("[SESSION CONTEXT ERROR] %s", e)
