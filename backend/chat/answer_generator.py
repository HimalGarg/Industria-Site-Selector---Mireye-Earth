"""
backend/chat/answer_generator.py — Grounded Answer Generation Engine
=======================================================================

Generates grounded conversational answers tagged with source citations
(mireye, listing, memory). Enforces "not available" over estimation.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

logger = logging.getLogger(__name__)


def generate_chat_answer(
    user_message: str,
    llm_structured: dict[str, Any],
    mireye_data: dict[str, Any],
    latest_evaluation: dict[str, Any] | None,
    history_messages: list[dict[str, Any]],
    listing_memory_facts: list[str],
    session_summary: str | None,
) -> dict[str, Any]:
    """
    Generates a grounded, cited answer using OpenAI JSON mode.
    
    Returns:
        {
          "content": str,
          "citations": list[dict[str, Any]]
        }
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {
            "content": "API key unavailable for chat generation.",
            "citations": [],
        }

    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are an expert commercial real estate AI advisor answering follow-up questions about a site.\n\n"
        "GROUNDING DISCIPLINE (CRITICAL):\n"
        "1. Every factual statement in your response MUST be grounded in the provided context.\n"
        "2. Distinguish Mireye-derived GIS facts from listing-stated facts and listing-memory facts.\n"
        "3. Every citation must have a 'source' key set to exactly 'mireye', 'listing', or 'memory'.\n"
        "4. If data for a requested metric is missing or null, explicitly state that it is 'not available' "
        "rather than estimating or guessing.\n"
        "5. If a session summary is provided, use it to tailor tone and highlight user priorities, but NEVER let it override factual data.\n\n"
        "Return ONLY a JSON object with this exact schema:\n"
        "{\n"
        '  "content": "Detailed, professional answer text",\n'
        '  "citations": [\n'
        '    { "source": "mireye", "field": "fema_flood_zone", "value": "Zone X" },\n'
        '    { "source": "listing", "field": "asking_price", "value": "$12,500,000" },\n'
        '    { "source": "memory", "fact": "User is concerned about rail noise" }\n'
        "  ]\n"
        "}"
    )

    user_prompt = (
        f"User Question: {user_message!r}\n\n"
        f"=== Session Context Summary (User Priorities) ===\n"
        f"{session_summary or 'None set yet.'}\n\n"
        f"=== Listing Self-Reported Data (`llm_structured`) ===\n"
        f"{json.dumps(llm_structured, indent=2)}\n\n"
        f"=== Primary Council Evaluation Report ===\n"
        f"{json.dumps(latest_evaluation or {}, indent=2)}\n\n"
        f"=== Mireye GIS Cached Data ({len(mireye_data)} fields) ===\n"
        f"{json.dumps(mireye_data, indent=2)}\n\n"
        f"=== Listing Accumulated Memory Facts ({len(listing_memory_facts)}) ===\n"
        f"{json.dumps(listing_memory_facts, indent=2)}\n\n"
        f"=== Conversation History (Last {len(history_messages)} turns) ===\n"
        f"{json.dumps(history_messages, indent=2)}\n"
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

        content = parsed.get("content", "No response generated.")
        citations = parsed.get("citations", [])

        if not isinstance(citations, list):
            citations = []

        return {
            "content": content,
            "citations": citations,
        }

    except Exception as e:
        logger.error("[CHAT ANSWER ERROR] %s", e)
        return {
            "content": f"I encountered an issue generating the answer: {str(e)}",
            "citations": [],
        }
