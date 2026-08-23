"""
backend/evaluate/compare_router.py — FastAPI Router for Multi-Site Comparison View
====================================================================================

Endpoint:
  POST /compare-sites
    Body: { "cart_item_ids": ["id1", "id2", ...] }
    Enforces: 2 to 4 cart item IDs
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .compare_synthesizer import run_compare_synthesizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["comparison"])


class CompareSitesRequest(BaseModel):
    cart_item_ids: list[str]


class AgentScores(BaseModel):
    energy: Optional[int] = None
    water: Optional[int] = None
    surface: Optional[int] = None
    transport: Optional[int] = None
    risk: Optional[int] = None


class ComparedSiteOut(BaseModel):
    cart_item_id: str
    address: str
    listing_title: Optional[str] = None
    image_url: Optional[str] = None
    overall_score: Optional[int] = None
    recommendation: Optional[str] = None
    agent_scores: Optional[AgentScores] = None
    missing_evaluation: bool = False


class CompareSitesResponse(BaseModel):
    sites: list[ComparedSiteOut]
    comparison_narrative: str
    trade_offs: list[str]


def _flatten_agent_scores(agent_results: list[dict[str, Any]]) -> AgentScores:
    """Helper to convert array of 5 agent result dicts into flattened AgentScores model."""
    scores: dict[str, Optional[int]] = {
        "energy": None,
        "water": None,
        "surface": None,
        "transport": None,
        "risk": None,
    }

    name_mapping = {
        "energy agent": "energy",
        "water agent": "water",
        "surface agent": "surface",
        "surface & environment agent": "surface",
        "transport agent": "transport",
        "transportation agent": "transport",
        "risk agent": "risk",
        "risk & regulatory agent": "risk",
    }

    for ag in agent_results:
        raw_name = str(ag.get("agent_name", "")).lower().strip()
        score = ag.get("score")
        
        # Match mapped discipline
        for key_pattern, score_key in name_mapping.items():
            if key_pattern in raw_name:
                scores[score_key] = score
                break

    return AgentScores(**scores)


@router.post("/compare-sites", response_model=CompareSitesResponse)
def compare_sites(body: CompareSitesRequest) -> CompareSitesResponse:
    """
    Compares 2 to 4 commercial listing sites side-by-side.
    Returns flattened agent scores per site and a synthesized comparison narrative.
    """
    from main import get_db

    cart_ids = [cid.strip() for cid in body.cart_item_ids if cid.strip()]

    if len(cart_ids) < 2 or len(cart_ids) > 4:
        raise HTTPException(
            status_code=400,
            detail=f"Comparison requires between 2 and 4 cart_item_ids. Provided: {len(cart_ids)}",
        )

    sites_out: list[ComparedSiteOut] = []
    evaluated_sites_for_llm: list[dict[str, Any]] = []

    with get_db() as conn:
        for cid in cart_ids:
            # 1. Fetch cart item
            cart_row = conn.execute(
                "SELECT cart_item_id, address, listing_title, image_url FROM cart_items WHERE cart_item_id = ?",
                (cid,),
            ).fetchone()

            if not cart_row:
                raise HTTPException(status_code=404, detail=f"cart_item_id {cid!r} not found")

            address = cart_row["address"]
            listing_title = cart_row["listing_title"]
            image_url = cart_row["image_url"]

            # 2. Fetch latest evaluation row
            eval_row = conn.execute(
                "SELECT overall_score, recommendation, agent_results FROM evaluations WHERE cart_item_id = ? ORDER BY created_at DESC LIMIT 1",
                (cid,),
            ).fetchone()

            if not eval_row or eval_row["overall_score"] is None:
                # Flag as missing evaluation
                sites_out.append(
                    ComparedSiteOut(
                        cart_item_id=cid,
                        address=address,
                        listing_title=listing_title,
                        image_url=image_url,
                        overall_score=None,
                        recommendation="Evaluation Required",
                        agent_scores=None,
                        missing_evaluation=True,
                    )
                )
            else:
                agent_results = json.loads(eval_row["agent_results"]) if eval_row["agent_results"] else []
                flattened_scores = _flatten_agent_scores(agent_results)

                sites_out.append(
                    ComparedSiteOut(
                        cart_item_id=cid,
                        address=address,
                        listing_title=listing_title,
                        image_url=image_url,
                        overall_score=eval_row["overall_score"],
                        recommendation=eval_row["recommendation"],
                        agent_scores=flattened_scores,
                        missing_evaluation=False,
                    )
                )

                evaluated_sites_for_llm.append({
                    "cart_item_id": cid,
                    "address": address,
                    "listing_title": listing_title,
                    "overall_score": eval_row["overall_score"],
                    "recommendation": eval_row["recommendation"],
                    "agent_results": agent_results,
                })

    # 3. Synthesize comparison narrative for evaluated sites
    synth_res = run_compare_synthesizer(evaluated_sites_for_llm)

    return CompareSitesResponse(
        sites=sites_out,
        comparison_narrative=synth_res["comparison_narrative"],
        trade_offs=synth_res["trade_offs"],
    )
