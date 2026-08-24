"""
backend/evaluate/compare_synthesizer.py — Multi-Site Comparison Narrative Synthesizer
====================================================================================

Generates a grounded 2-3 sentence comparison narrative and specific discipline trade-offs
comparing 2 to 4 evaluated commercial real estate sites.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


def run_compare_synthesizer(evaluated_sites: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Synthesizes a grounded comparison narrative and trade-offs array.
    
    Args:
        evaluated_sites: List of site dicts containing address, listing_title,
                         overall_score, recommendation, agent_results.
                         
    Returns:
        {
          "comparison_narrative": str,
          "trade_offs": list[str]
        }
    """
    if not evaluated_sites:
        return {
            "comparison_narrative": "No evaluated sites were provided for comparison.",
            "trade_offs": [],
        }

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[COMPARE SYNTHESIZER] OPENAI_API_KEY missing — returning fallback narrative")
        # Simple rule-based fallback if API key missing
        sorted_sites = sorted(evaluated_sites, key=lambda s: s.get("overall_score") or 0, reverse=True)
        top_site = sorted_sites[0]
        return {
            "comparison_narrative": f"Among the evaluated properties, {top_site['address']} leads with an overall score of {top_site.get('overall_score')}/100 ({top_site.get('recommendation')}).",
            "trade_offs": [
                f"{top_site['address']} has higher overall score compared to other sites in the evaluation pipeline."
            ],
        }

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are an expert commercial real estate investment board synthesizer.\n"
        "Your task is to compare 2 to 4 evaluated commercial sites side-by-side based STRICTLY on "
        "their provided 5-agent council evaluation reports (Energy, Water, Surface, Transport, Risk).\n\n"
        "GROUNDING DISCIPLINE (CRITICAL):\n"
        "1. Identify clear winners and contrast trade-offs directly based ONLY on the provided agent scores and memos.\n"
        "2. Do NOT invent outside facts or guess information not present in the input evaluation reports.\n"
        "3. Provide a concise 2-3 sentence executive comparison narrative.\n"
        "4. Provide 2-4 concrete trade-off statements contrasting specific site discipline strengths vs weaknesses "
        "(e.g., 'Site A offers superior power transmission infrastructure, but Site B presents lower FEMA flood risk').\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "comparison_narrative": "2-3 sentence overview text",\n'
        '  "trade_offs": [\n'
        '    "Trade-off statement 1",\n'
        '    "Trade-off statement 2"\n'
        '  ]\n'
        "}"
    )

    user_prompt = (
        f"Evaluated Sites for Side-by-Side Comparison ({len(evaluated_sites)} sites):\n"
        f"{json.dumps(evaluated_sites, indent=2)}\n"
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

        raw_content = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_content)

        comparison_narrative = parsed.get("comparison_narrative", "").strip()
        trade_offs = parsed.get("trade_offs", [])

        if not isinstance(trade_offs, list):
            trade_offs = []

        if not comparison_narrative:
            comparison_narrative = "Side-by-side comparison generated based on 5-agent council evaluation metrics."

        return {
            "comparison_narrative": comparison_narrative,
            "trade_offs": [str(t).strip() for t in trade_offs if str(t).strip()],
        }

    except Exception as e:
        logger.error("[COMPARE SYNTHESIZER ERROR] %s", e)
        return {
            "comparison_narrative": "Unable to generate comparison narrative due to an API processing error.",
            "trade_offs": [],
        }
