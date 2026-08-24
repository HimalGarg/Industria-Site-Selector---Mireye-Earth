"""
backend/evaluate/synthesizer.py — Council synthesizer (one LLM call)
=====================================================================

The synthesizer takes all 5 agent results as input and produces:
  {
    "overall_score": 0-100,
    "recommendation": str,        # short verdict (1 sentence)
    "conflicts_flagged": [str],   # cross-agent tensions AND listing-vs-Mireye disagreements
    "narrative_summary": str      # board-readable paragraph
  }

Key rules:
  - Does NOT hide or overwrite raw per-agent scores (those are stored separately).
  - conflicts_flagged must surface BOTH cross-agent tensions AND any listing-vs-Mireye
    disagreements flagged by individual agents in their memos/citations.
  - overall_score is a weighted synthesis, not a simple average.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

from .agents import _get_openai_client

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Synthesizer prompt
# ---------------------------------------------------------------------------

SYNTHESIZER_OUTPUT_SCHEMA = """
Return ONLY valid JSON matching this schema exactly:
{
  "overall_score": integer between 0 and 100,
  "recommendation": "string — one clear sentence verdict (e.g. 'Strong candidate', 'Proceed with caution', 'Not recommended')",
  "conflicts_flagged": [
    "string describing a tension or disagreement — be specific (which agents, which fields)"
  ],
  "narrative_summary": "string — 2-4 paragraph board-readable executive summary"
}
"""


def _build_synthesizer_prompt(agent_results: list[dict[str, Any]]) -> str:
    """Build the synthesizer prompt from the 5 agent results."""

    # Format each agent result as a concise summary block
    agent_blocks = []
    for r in agent_results:
        block = (
            f"=== {r.get('agent_name', 'Unknown Agent')} ===\n"
            f"Score: {r.get('score', 'N/A')}/100\n"
            f"Data availability: {r.get('data_availability', 'unknown')}\n"
            f"Summary: {r.get('summary', 'none')}\n"
            f"Memo:\n{r.get('memo', 'none')}\n"
        )

        # Include any listing-vs-Mireye citations so the synthesizer can flag them
        citations = r.get("citations", [])
        listing_citations = [c for c in citations if c.get("source") == "listing"]
        if listing_citations:
            block += "Listing-sourced data (potential cross-reference points):\n"
            for c in listing_citations:
                block += f"  - {c.get('field')}: {c.get('value')}\n"

        agent_blocks.append(block)

    agent_text = "\n\n".join(agent_blocks)

    return f"""You are the Council Synthesizer for a commercial real estate site evaluation.
You have received reports from 5 specialized agents. Your job is to produce a final, board-readable synthesis.

AGENT REPORTS:
{agent_text}

YOUR TASK:
1. Compute an overall_score (0-100) that weights the agent scores thoughtfully. Risk and Water scores should weigh more heavily than others — a site with fatal environmental risk shouldn't score 80 just because energy and transport are great.
2. Write a clear, one-sentence recommendation.
3. List ALL conflicts_flagged:
   - Cross-agent tensions: e.g., high Energy score (85) but high Risk score (20) — the site has power but environmental constraints.
   - Any listing-vs-Mireye disagreements flagged by individual agents — do NOT drop these. Surface them with specifics.
4. Write a narrative_summary (2-4 paragraphs) suitable for a board presentation. Lead with the verdict. Name specific data points. Be honest about uncertainties.

IMPORTANT: Do not make up data not present in the agent reports. Do not hide fatal risks in optimistic language.

{SYNTHESIZER_OUTPUT_SCHEMA}"""


# ---------------------------------------------------------------------------
# Synthesizer runner
# ---------------------------------------------------------------------------


def run_synthesizer(agent_results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Run the synthesizer LLM call synchronously (called from background thread).

    Args:
        agent_results: List of 5 AgentResult dicts from run_all_agents()

    Returns SynthesizerResult dict.
    """
    logger.info("[SYNTHESIZER] Starting synthesis of %d agent results", len(agent_results))

    prompt = _build_synthesizer_prompt(agent_results)

    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=model_name,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Generate the synthesis report now."},
            ],
        )
        raw_text = response.choices[0].message.content.strip()

        result = json.loads(raw_text)

        # Enforce required fields
        result.setdefault("overall_score", 0)
        result.setdefault("recommendation", "Evaluation incomplete.")
        result.setdefault("conflicts_flagged", [])
        result.setdefault("narrative_summary", "No narrative generated.")

        # Clamp score
        result["overall_score"] = max(0, min(100, int(result["overall_score"])))

        logger.info(
            "[SYNTHESIZER DONE] overall_score=%d | conflicts=%d",
            result["overall_score"],
            len(result["conflicts_flagged"]),
        )
        return result

    except json.JSONDecodeError as e:
        logger.error("[SYNTHESIZER] JSON parse error: %s", e)
        return {
            "overall_score": 0,
            "recommendation": "Synthesis failed — JSON parse error.",
            "conflicts_flagged": [],
            "narrative_summary": f"Synthesizer failed to produce valid JSON: {e}",
        }
    except Exception as e:
        logger.error("[SYNTHESIZER] Unexpected error: %s", e)
        return {
            "overall_score": 0,
            "recommendation": "Synthesis failed — unexpected error.",
            "conflicts_flagged": [],
            "narrative_summary": f"Synthesizer error: {e}",
        }
