"""
backend/evaluate/router.py — FastAPI routes for the evaluation pipeline
========================================================================

Endpoints:
  POST /evaluate-site
    Body: { "cart_item_id": str }
    Returns: { "evaluation_id": str, "status": "processing" }

  GET /evaluate-site/{evaluation_id}
    Returns: { "status": "processing" | "done" | "error", ...full eval fields if done }

Async job pattern:
  - POST starts a background thread running the full pipeline
  - In-memory job store (dict) tracks status per evaluation_id
  - GET polls the store and returns full results when done
  - This is intentionally simple for hackathon use; swap for a proper queue later

Pipeline steps (per build guide):
  1. Look up cart item (address + llm_structured)
  2. Resolve address via Mireye geocoder → get normalized_address (cache_key)
  3. Fetch IDENTITY_FIELDS (once, not per-agent)
  4. Check mireye_cache for all agent fields; fetch misses from Mireye
  5. Run /v1/proximity for energy and transport agents (drive-time)
  6. Run 5 agents concurrently via asyncio.gather
  7. Run synthesizer
  8. Persist to evaluations table; mark job done
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .agents import run_all_agents
from .config import (
    AGENT_FIELD_MAP,
    ALL_AGENT_FIELDS,
    IDENTITY_FIELDS,
    PROXIMITY_CURATED_SETS,
)
from .mireye_fetcher import (
    fetch_fields_with_cache,
    fetch_identity_fields,
    fetch_proximity_drive_time,
    resolve_address,
)
from .synthesizer import run_synthesizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["evaluation"])

# ---------------------------------------------------------------------------
# In-memory job store
# { evaluation_id: { "status": str, "result": dict|None, "error": str|None } }
# ---------------------------------------------------------------------------

_job_store: dict[str, dict[str, Any]] = {}
_job_store_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class EvaluateSiteRequest(BaseModel):
    cart_item_id: str
    user_requirements: Optional[str] = None


class EvaluateSiteStarted(BaseModel):
    evaluation_id: str
    status: str = "processing"


# ---------------------------------------------------------------------------
# POST /evaluate-site
# ---------------------------------------------------------------------------


@router.post("/evaluate-site", response_model=EvaluateSiteStarted, status_code=202)
def start_evaluation(body: EvaluateSiteRequest, conn_factory=None) -> EvaluateSiteStarted:
    """
    Kick off an async evaluation for a cart item.
    Returns immediately with evaluation_id and status="processing".
    Poll GET /evaluate-site/{evaluation_id} for results.
    """
    cart_item_id = body.cart_item_id.strip()
    user_requirements = body.user_requirements

    if not cart_item_id:
        raise HTTPException(status_code=400, detail="cart_item_id is required")

    # Look up the cart item immediately (fail fast before starting background job)
    from main import get_db  # import here to avoid circular at module level
    with get_db() as conn:
        row = conn.execute(
            "SELECT cart_item_id, address, llm_structured FROM cart_items WHERE cart_item_id = ?",
            (cart_item_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"cart_item_id {cart_item_id!r} not found")

    address = row["address"]
    llm_structured_raw = row["llm_structured"]
    llm_structured = {}
    if llm_structured_raw:
        try:
            llm_structured = json.loads(llm_structured_raw)
        except json.JSONDecodeError:
            llm_structured = {}

    evaluation_id = str(uuid.uuid4())

    with _job_store_lock:
        _job_store[evaluation_id] = {"status": "processing", "result": None, "error": None, "cart_item_id": cart_item_id}

    # Start the pipeline in a background thread
    thread = threading.Thread(
        target=_run_pipeline_sync,
        args=(evaluation_id, cart_item_id, address, llm_structured, user_requirements),
        daemon=True,
    )
    thread.start()

    logger.info("[PIPELINE START] evaluation_id=%s cart_item_id=%s address=%r user_reqs=%r", evaluation_id, cart_item_id, address, bool(user_requirements))
    return EvaluateSiteStarted(evaluation_id=evaluation_id)


# ---------------------------------------------------------------------------
# GET /evaluate-site/{evaluation_id}
# ---------------------------------------------------------------------------


@router.get("/evaluate-site/{evaluation_id}")
def get_evaluation(evaluation_id: str) -> dict[str, Any]:
    """
    Poll for evaluation results. Returns:
      { status: "processing" }   — still running
      { status: "done", ...all evaluation fields... }   — complete
      { status: "error", "error": str }   — pipeline failed
    """
    with _job_store_lock:
        job = _job_store.get(evaluation_id)

    if job is None:
        # Not in memory — check the DB (survives server restart)
        from main import get_db
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM evaluations WHERE evaluation_id = ?",
                (evaluation_id,),
            ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail=f"evaluation_id {evaluation_id!r} not found")

        return _format_db_row(row)

    if job["status"] == "processing":
        return {"status": "processing", "evaluation_id": evaluation_id}

    if job["status"] == "error":
        return {"status": "error", "evaluation_id": evaluation_id, "error": job.get("error", "Unknown error")}

    # Done — return the full result (already formatted as a clean dict)
    return {"status": "done", "evaluation_id": evaluation_id, **job["result"]}


# ---------------------------------------------------------------------------
# GET /evaluate-site (list all for a cart item)
# ---------------------------------------------------------------------------


@router.get("/evaluate-site")
def list_evaluations(cart_item_id: Optional[str] = None) -> list[dict[str, Any]]:
    """
    List all evaluations, optionally filtered by cart_item_id.
    Useful for checking existing evaluations before triggering a new one.
    """
    from main import get_db
    with get_db() as conn:
        if cart_item_id:
            rows = conn.execute(
                "SELECT * FROM evaluations WHERE cart_item_id = ? ORDER BY created_at DESC",
                (cart_item_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM evaluations ORDER BY created_at DESC LIMIT 50"
            ).fetchall()

    return [_format_db_row(row) for row in rows]


# ---------------------------------------------------------------------------
# Background pipeline (runs in a thread)
# ---------------------------------------------------------------------------


def _run_pipeline_sync(
    evaluation_id: str,
    cart_item_id: str,
    address: str,
    llm_structured: dict[str, Any],
    user_requirements: Optional[str] = None,
) -> None:
    """
    Full synchronous evaluation pipeline. Runs in a background daemon thread.
    Writes results to DB and updates the in-memory job store when done.
    """
    try:
        # Run the async pipeline on a fresh event loop for this thread
        result = asyncio.run(_run_pipeline_async(evaluation_id, cart_item_id, address, llm_structured, user_requirements))

        with _job_store_lock:
            _job_store[evaluation_id] = {"status": "done", "result": result, "error": None}

        logger.info("[PIPELINE DONE] evaluation_id=%s overall_score=%s", evaluation_id, result.get("overall_score"))

    except Exception as e:
        logger.exception("[PIPELINE ERROR] evaluation_id=%s: %s", evaluation_id, e)
        with _job_store_lock:
            _job_store[evaluation_id] = {"status": "error", "result": None, "error": str(e)}

        # Persist error row to DB
        _persist_error(evaluation_id, cart_item_id, str(e))


async def _run_pipeline_async(
    evaluation_id: str,
    cart_item_id: str,
    address: str,
    llm_structured: dict[str, Any],
    user_requirements: Optional[str] = None,
) -> dict[str, Any]:
    """
    The full async evaluation pipeline:
      1. Geocode via Mireye
      2. Fetch identity fields (once)
      3. Check cache + fetch all agent fields
      4. Fetch proximity data for energy + transport
      5. Run 5 agents concurrently
      6. Run synthesizer
      7. Persist to DB
      8. Return result dict
    """
    from main import get_db

    # ── Step 1: Address resolution ─────────────────────────────────────
    logger.info("[STEP 1] Resolving address: %r", address)
    loop = asyncio.get_event_loop()
    geo = await loop.run_in_executor(None, resolve_address, address)

    lat = geo["lat"]
    lng = geo["lng"]
    cache_key = geo["normalized_address"]
    coordinate_match_quality = geo["coordinate_match_quality"]

    logger.info(
        "[STEP 1 DONE] cache_key=%r | quality=%s | lat=%.5f | lng=%.5f",
        cache_key, coordinate_match_quality, lat, lng,
    )

    # ── Step 2: Identity fields (once, not per-agent) ──────────────────
    logger.info("[STEP 2] Fetching identity fields")
    identity_data = await loop.run_in_executor(
        None, fetch_identity_fields, cache_key, IDENTITY_FIELDS
    )
    logger.info("[STEP 2 DONE] identity fields fetched: %d", len(identity_data))

    # ── Step 3: Cache check + fetch all agent fields ───────────────────
    logger.info("[STEP 3] Fetching all agent fields (cache-first) for %d unique fields", len(ALL_AGENT_FIELDS))
    all_mireye_fields = await loop.run_in_executor(
        None, fetch_fields_with_cache, cache_key, ALL_AGENT_FIELDS
    )
    logger.info("[STEP 3 DONE] field fetch complete. Total fields in store: %d", len(all_mireye_fields))

    # ── Step 4: Proximity (energy + transport) ────────────────────────
    logger.info("[STEP 4] Fetching drive-time proximity data")
    proximity_results: dict[str, Any] = {}

    energy_proximity = await loop.run_in_executor(
        None, fetch_proximity_drive_time, lat, lng, PROXIMITY_CURATED_SETS["energy"]
    )
    if energy_proximity:
        proximity_results["energy"] = energy_proximity

    airport_proximity = await loop.run_in_executor(
        None, fetch_proximity_drive_time, lat, lng, PROXIMITY_CURATED_SETS["transport"]
    )
    ports_proximity = await loop.run_in_executor(
        None, fetch_proximity_drive_time, lat, lng, PROXIMITY_CURATED_SETS["transport_ports"]
    )
    if airport_proximity or ports_proximity:
        proximity_results["transport"] = {
            "airports": airport_proximity,
            "ports": ports_proximity,
        }

    logger.info("[STEP 4 DONE] proximity fetched for: %s", list(proximity_results.keys()))

    # ── Step 5: Run all 5 agents concurrently ─────────────────────────
    logger.info("[STEP 5] Running 5 agents concurrently")
    agent_results = await run_all_agents(
        all_mireye_fields=all_mireye_fields,
        llm_structured=llm_structured,
        agent_field_map=AGENT_FIELD_MAP,
        proximity_results=proximity_results,
        user_requirements=user_requirements,
    )
    logger.info("[STEP 5 DONE] agent scores: %s", [r.get("score") for r in agent_results])

    # ── Step 6: Synthesizer ────────────────────────────────────────────
    logger.info("[STEP 6] Running synthesizer")
    synth = await loop.run_in_executor(None, run_synthesizer, agent_results, user_requirements)
    logger.info("[STEP 6 DONE] overall_score=%d conflicts=%d", synth["overall_score"], len(synth["conflicts_flagged"]))

    # ── Step 7: Persist to DB ─────────────────────────────────────────
    logger.info("[STEP 7] Persisting evaluation to DB")
    created_at = datetime.now(timezone.utc).isoformat()

    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO evaluations
                (evaluation_id, cart_item_id, overall_score, recommendation,
                 conflicts_flagged, agent_results, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_id,
                cart_item_id,
                synth["overall_score"],
                synth["recommendation"],
                json.dumps(synth["conflicts_flagged"]),
                json.dumps(agent_results),
                created_at,
            ),
        )
        conn.commit()
    logger.info("[STEP 7 DONE] evaluation_id=%s persisted", evaluation_id)

    # Return the full evaluation result dict
    return {
        "evaluation_id": evaluation_id,
        "cart_item_id": cart_item_id,
        "overall_score": synth["overall_score"],
        "recommendation": synth["recommendation"],
        "conflicts_flagged": synth["conflicts_flagged"],
        "narrative_summary": synth.get("narrative_summary", ""),
        "agent_results": agent_results,
        "geocode": {
            "cache_key": cache_key,
            "coordinate_match_quality": coordinate_match_quality,
            "lat": lat,
            "lng": lng,
        },
        "identity_data": identity_data,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# DB persistence helpers
# ---------------------------------------------------------------------------


def _persist_error(evaluation_id: str, cart_item_id: str, error_msg: str) -> None:
    """Write a failed evaluation row to DB so errors are queryable."""
    from main import get_db
    try:
        with get_db() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO evaluations
                    (evaluation_id, cart_item_id, overall_score, recommendation,
                     conflicts_flagged, agent_results, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation_id,
                    cart_item_id,
                    None,
                    f"ERROR: {error_msg}",
                    json.dumps([]),
                    json.dumps([]),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
    except Exception as e:
        logger.error("[PERSIST ERROR] Could not write error row: %s", e)


def _format_db_row(row) -> dict[str, Any]:
    """Convert a DB row from the evaluations table into a clean dict."""
    result = dict(row)
    # Parse JSON fields back into Python objects
    for field in ("conflicts_flagged", "agent_results"):
        raw = result.get(field)
        if raw:
            try:
                result[field] = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                result[field] = []
        else:
            result[field] = []

    result["status"] = "done"
    return result
