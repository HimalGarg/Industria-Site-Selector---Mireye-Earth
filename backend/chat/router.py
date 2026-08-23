"""
backend/chat/router.py — FastAPI Router for Chat, Router & Memory Layer
========================================================================

Endpoints:
  POST /chat                 — Synchronous conversational chat turn
  GET  /chat                 — Retrieves chat message history for a cart_item_id
  GET  /listing-memory       — Retrieves atomic listing memory facts for a cart_item_id
  GET  /session-context      — Retrieves cross-site session context summary for a session_id
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .answer_generator import generate_chat_answer
from .memory_engine import (
    maybe_update_session_context,
    trigger_memory_extraction_background,
)
from .router_engine import route_chat_query

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# Pydantic Request & Response Models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    cart_item_id: str
    session_id: str
    message: str


class ChatResponse(BaseModel):
    message_id: str
    content: str
    citations: list[dict[str, Any]]
    status: str = "done"


# ---------------------------------------------------------------------------
# 1. POST /chat
# ---------------------------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
def post_chat_message(body: ChatRequest) -> ChatResponse:
    """
    Synchronous chat turn handler:
    1. Loads most recent evaluation for cart_item_id.
    2. Loads listing details (llm_structured) and chat history.
    3. Runs router engine to decide if new Mireye fields are needed.
    4. Generates grounded answer with citations.
    5. Stores user & assistant messages in DB.
    6. Triggers background memory extraction & session context updates.
    """
    from main import get_db

    cart_item_id = body.cart_item_id.strip()
    session_id = body.session_id.strip()
    user_message = body.message.strip()

    if not cart_item_id:
        raise HTTPException(status_code=400, detail="cart_item_id is required")
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    if not user_message:
        raise HTTPException(status_code=400, detail="message is required")

    with get_db() as conn:
        # Step 1: Load cart item
        cart_row = conn.execute(
            "SELECT address, llm_structured FROM cart_items WHERE cart_item_id = ?",
            (cart_item_id,),
        ).fetchone()

        if not cart_row:
            raise HTTPException(status_code=404, detail=f"cart_item_id {cart_item_id!r} not found")

        address = cart_row["address"]
        llm_structured = json.loads(cart_row["llm_structured"]) if cart_row["llm_structured"] else {}

        # Step 2: Check for existing evaluation report
        eval_row = conn.execute(
            "SELECT overall_score, recommendation, conflicts_flagged, agent_results FROM evaluations WHERE cart_item_id = ? ORDER BY created_at DESC LIMIT 1",
            (cart_item_id,),
        ).fetchone()

        if not eval_row:
            # User hasn't run an evaluation report yet
            prompt_content = (
                "This site has not been evaluated by the 5-Agent Council yet. "
                "Please run an **Evaluate Site** audit first so I can ground our conversation in physical GIS data and council analyses!"
            )
            assistant_msg_id = str(uuid.uuid4())
            user_msg_id = str(uuid.uuid4())
            now_iso = datetime.now(timezone.utc).isoformat()

            conn.execute(
                "INSERT INTO chat_messages (message_id, cart_item_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_msg_id, cart_item_id, session_id, "user", user_message, now_iso),
            )
            conn.execute(
                "INSERT INTO chat_messages (message_id, cart_item_id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (assistant_msg_id, cart_item_id, session_id, "assistant", prompt_content, now_iso),
            )
            conn.commit()

            return ChatResponse(message_id=assistant_msg_id, content=prompt_content, citations=[])

        latest_evaluation = {
            "overall_score": eval_row["overall_score"],
            "recommendation": eval_row["recommendation"],
            "conflicts_flagged": json.loads(eval_row["conflicts_flagged"]) if eval_row["conflicts_flagged"] else [],
            "agent_results": json.loads(eval_row["agent_results"]) if eval_row["agent_results"] else [],
        }

        # Step 3: Load Mireye cached fields for this normalized address
        cache_key = address
        cache_row = conn.execute(
            "SELECT fields FROM mireye_cache WHERE cache_key = ?",
            (cache_key,),
        ).fetchone()

        mireye_cached_data = json.loads(cache_row["fields"]) if cache_row and cache_row["fields"] else {}

        # Step 4: Load conversation history (last 10 turns)
        msg_rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE cart_item_id = ? ORDER BY created_at DESC LIMIT 10",
            (cart_item_id,),
        ).fetchall()
        history_messages = [dict(r) for r in reversed(msg_rows)]

        # Step 5: Load listing memory facts
        mem_rows = conn.execute(
            "SELECT fact FROM listing_memory WHERE cart_item_id = ? ORDER BY created_at ASC",
            (cart_item_id,),
        ).fetchall()
        listing_memory_facts = [r["fact"] for r in mem_rows]

        # Step 6: Load session context summary
        sess_row = conn.execute(
            "SELECT summary FROM session_context WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        session_summary = sess_row["summary"] if sess_row else None

    # Step 7: Run LLM Router to check if missing Mireye fields should be fetched
    action, newly_fetched = route_chat_query(
        user_message=user_message,
        cached_fields=mireye_cached_data,
        cache_key=cache_key,
    )

    if newly_fetched:
        # Reload updated cache from DB
        with get_db() as conn:
            c_row = conn.execute(
                "SELECT fields FROM mireye_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if c_row and c_row["fields"]:
                mireye_cached_data = json.loads(c_row["fields"])

    # Step 8: Generate grounded answer with citations
    answer_res = generate_chat_answer(
        user_message=user_message,
        llm_structured=llm_structured,
        mireye_data=mireye_cached_data,
        latest_evaluation=latest_evaluation,
        history_messages=history_messages,
        listing_memory_facts=listing_memory_facts,
        session_summary=session_summary,
    )

    content = answer_res["content"]
    citations = answer_res["citations"]

    user_msg_id = str(uuid.uuid4())
    assistant_msg_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # Step 9: Store user and assistant messages in chat_messages table
    with get_db() as conn:
        conn.execute(
            "INSERT INTO chat_messages (message_id, cart_item_id, session_id, role, content, citations, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_msg_id, cart_item_id, session_id, "user", user_message, None, now_iso),
        )
        conn.execute(
            "INSERT INTO chat_messages (message_id, cart_item_id, session_id, role, content, citations, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (assistant_msg_id, cart_item_id, session_id, "assistant", content, json.dumps(citations), now_iso),
        )
        conn.commit()

    # Step 10: Trigger background memory extraction & session context re-summarizer
    trigger_memory_extraction_background(
        cart_item_id=cart_item_id,
        session_id=session_id,
        user_message=user_message,
        assistant_content=content,
    )

    maybe_update_session_context(session_id=session_id)

    return ChatResponse(
        message_id=assistant_msg_id,
        content=content,
        citations=citations,
        status="done",
    )


# ---------------------------------------------------------------------------
# 2. GET /chat (Read Chat History)
# ---------------------------------------------------------------------------


@router.get("/chat")
def get_chat_history(
    cart_item_id: str = Query(..., description="Cart item ID to fetch chat history for")
) -> list[dict[str, Any]]:
    """Retrieves full chat message history for a listing, ordered by created_at."""
    from main import get_db
    cart_item_id = cart_item_id.strip()

    with get_db() as conn:
        rows = conn.execute(
            "SELECT message_id, cart_item_id, session_id, role, content, citations, created_at FROM chat_messages WHERE cart_item_id = ? ORDER BY created_at ASC",
            (cart_item_id,),
        ).fetchall()

    result = []
    for r in rows:
        item = dict(r)
        if item.get("citations"):
            try:
                item["citations"] = json.loads(item["citations"])
            except (json.JSONDecodeError, TypeError):
                item["citations"] = []
        else:
            item["citations"] = []
        result.append(item)

    return result


# ---------------------------------------------------------------------------
# 3. GET /listing-memory (Read Listing Memory Facts)
# ---------------------------------------------------------------------------


@router.get("/listing-memory")
def get_listing_memory(
    cart_item_id: str = Query(..., description="Cart item ID to fetch listing memory for")
) -> list[dict[str, Any]]:
    """Retrieves all atomic listing memory rows for a given listing."""
    from main import get_db
    cart_item_id = cart_item_id.strip()

    with get_db() as conn:
        rows = conn.execute(
            "SELECT memory_id, cart_item_id, session_id, fact, created_at FROM listing_memory WHERE cart_item_id = ? ORDER BY created_at ASC",
            (cart_item_id,),
        ).fetchall()

    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 4. GET /session-context (Read Session Context Summary)
# ---------------------------------------------------------------------------


@router.get("/session-context")
def get_session_context(
    session_id: str = Query(..., description="Session ID to fetch context summary for")
) -> dict[str, Any]:
    """Retrieves the current re-summarized session_context.summary snapshot for a session."""
    from main import get_db
    session_id = session_id.strip()

    with get_db() as conn:
        row = conn.execute(
            "SELECT session_id, summary, updated_at FROM session_context WHERE session_id = ?",
            (session_id,),
        ).fetchone()

    if not row:
        return {"session_id": session_id, "summary": None, "updated_at": None}

    return dict(row)
