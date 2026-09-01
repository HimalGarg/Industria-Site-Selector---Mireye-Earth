"""
backend/evaluate/agents.py — The 5 concurrent site-analysis agents
===================================================================

Each agent is a function that takes:
  - mireye_fields: dict  — field name → full Mireye field object (or None)
  - llm_structured: dict — the cart item's llm_structured schema (full)
  - proximity_data: dict — optional drive-time data from /v1/proximity

And returns a typed AgentResult dict:
  {
    "agent_name": str,
    "score": 0-100,
    "summary": str,          # 1-2 sentence verdict
    "memo": str,             # full written reasoning
    "citations": [{ "source": "mireye"|"listing", "field": str, "value": str }],
    "data_availability": "full" | "partial" | "unavailable"
  }

Grounding rule (enforced in every system prompt):
  Every factual claim must be traceable to a citation entry.
  Null/missing fields must be stated as "not available" — never estimated.

Agent execution model:
  All 5 agents are run concurrently via asyncio.gather() in the router.
  Each agent makes ONE LLM call (JSON mode via Gemini).

Risk and Surface agents additionally receive a slice of the listing's own
llm_structured data and are instructed to flag disagreements explicitly.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from openai import OpenAI

from .config import AGENT_NAMES, LLM_STRUCTURED_SLICES

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini setup
# ---------------------------------------------------------------------------


def _get_openai_client() -> OpenAI:
    """Build and return an OpenAI client using OPENAI_API_KEY from env."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Add it to backend/.env: OPENAI_API_KEY=sk-..."
        )
    return OpenAI(api_key=api_key)


# ---------------------------------------------------------------------------
# Field value extractor helpers
# ---------------------------------------------------------------------------


def _field_value(field_obj: Any) -> Any:
    """
    Extract the scalar value from a Mireye field object.
    Returns None if the field is null, missing, or has no value key.
    """
    if field_obj is None:
        return None
    if isinstance(field_obj, dict):
        return field_obj.get("value")
    return field_obj  # already a scalar (should not happen with real Mireye data)


def _format_mireye_fields_for_prompt(
    fields: dict[str, Any],
    agent_keys: list[str],
) -> str:
    """
    Format the agent's Mireye field slice as a readable block for the prompt.
    Each field becomes one line: FIELD_NAME: value (unit) [source] — or "not available".
    """
    lines = []
    for key in agent_keys:
        field_obj = fields.get(key)
        if field_obj is None or (isinstance(field_obj, dict) and field_obj.get("value") is None):
            lines.append(f"  {key}: not available")
        else:
            val = field_obj.get("value") if isinstance(field_obj, dict) else field_obj
            unit = field_obj.get("unit", "") if isinstance(field_obj, dict) else ""
            source = field_obj.get("source", "") if isinstance(field_obj, dict) else ""
            unit_str = f" {unit}" if unit else ""
            source_str = f" [{source}]" if source else ""
            lines.append(f"  {key}: {val}{unit_str}{source_str}")
    return "\n".join(lines)


def _extract_llm_structured_slice(
    llm_structured: dict[str, Any],
    slice_spec: list[tuple[str, str]],
) -> dict[str, Any]:
    """Extract the specified (section, field) pairs from llm_structured into a flat dict."""
    result = {}
    for section, field in slice_spec:
        val = llm_structured.get(section, {}).get(field)
        result[f"{section}.{field}"] = val
    return result


def _format_listing_slice_for_prompt(slice_data: dict[str, Any]) -> str:
    """Format the listing's llm_structured slice as a prompt block."""
    lines = []
    for key, val in slice_data.items():
        if val is None:
            lines.append(f"  {key}: not available")
        else:
            lines.append(f"  {key}: {val}")
    return "\n".join(lines) if lines else "  (no listing data available for this agent)"


# ---------------------------------------------------------------------------
# Shared grounding rule (injected into every agent system prompt)
# ---------------------------------------------------------------------------

GROUNDING_RULE = """
CRITICAL GROUNDING RULES — follow these exactly:
1. Only make factual claims that are directly traceable to a field in the data provided.
2. For every number, fact, or comparison in your memo, there must be a corresponding entry in "citations".
3. If a field value is "not available", state it as "not available" in your memo. Never estimate, infer, or guess missing values.
4. Cite the source of each fact: use "mireye" for data from the Mireye block, "listing" for data from the Listing Data block.
5. Your "data_availability" field must reflect reality: "full" if most fields have values, "partial" if some are null, "unavailable" if almost none have values.
6. Your "score" (0-100) must be defensible from your citations alone.
"""

AGENT_OUTPUT_SCHEMA = """
Return ONLY valid JSON matching this schema exactly:
{
  "agent_name": "string — the agent's display name",
    "score": integer between 0 and 100,
    "summary": "string - 1 to 2 sentence verdict",
    "memo": "string - full written reasoning (use clear bullet points/itemized lists for maximum clarity)",
    "citations": [
    { "source": "mireye" or "listing", "field": "field_name", "value": "string representation of value" }
  ],
  "data_availability": "full" or "partial" or "unavailable"
}
"""

# ---------------------------------------------------------------------------
# Agent system prompts
# ---------------------------------------------------------------------------


def _energy_system_prompt(
    agent_name: str,
    mireye_block: str,
    proximity_block: str,
    user_req_block: str,
) -> str:
    return f"""You are the {agent_name} for a commercial real estate site evaluation council.
Your job: assess whether this site has adequate power and energy infrastructure to support commercial or industrial use.
{user_req_block}
{GROUNDING_RULE}

MIREYE DATA (primary source — cite as "mireye"):
{mireye_block}

DRIVE-TIME PROXIMITY DATA (from /v1/proximity — cite as "mireye"):
{proximity_block}

EVALUATION GUIDANCE:
- Lead with drive-time results over straight-line distance where both are available.
- Assess: proximity to power plant, transmission voltage available, pipeline access.
- Flag if the nearest power plant is very far, low-capacity, or uses an intermittent fuel type.
- Note if multiple high-voltage lines are nearby (redundancy) or if there's only one (single point of failure).
- Score 80+ only if grid connection is clearly viable for heavy commercial use.

{AGENT_OUTPUT_SCHEMA}"""


def _water_system_prompt(agent_name: str, mireye_block: str, user_req_block: str) -> str:
    return f"""You are the {agent_name} for a commercial real estate site evaluation council.
Your job: assess water availability, wastewater treatment capacity, and hydrological constraints at this site.
{user_req_block}
{GROUNDING_RULE}

MIREYE DATA (primary source — cite as "mireye"):
{mireye_block}

EVALUATION GUIDANCE:
- Is the site in a public water service area? If not, that's a major constraint — flag it.
- Assess wastewater plant proximity and population served (proxy for spare capacity).
- Wetlands count within 100m and 500m: more wetlands = more regulatory friction for development.
- Surface water time coverage affects flood risk and wetland delineation complexity.
- Score 70+ only if public water service is confirmed and wastewater is accessible.

{AGENT_OUTPUT_SCHEMA}"""


def _surface_system_prompt(
    agent_name: str,
    mireye_block: str,
    listing_block: str,
    user_req_block: str,
) -> str:
    return f"""You are the {agent_name} for a commercial real estate site evaluation council.
Your job: assess terrain buildability, soil conditions, ecological constraints, and land cover at this site.
{user_req_block}
{GROUNDING_RULE}

MIREYE DATA (primary source — cite as "mireye"):
{mireye_block}

LISTING DATA (self-reported by the seller — cite as "listing"):
{listing_block}

EVALUATION GUIDANCE:
- Slope: >5° starts to add cost; >15° is a significant challenge for most commercial uses.
- Soil drainage class affects foundation requirements and stormwater design.
- Karst terrain (sinkholes) is a serious buildability risk — flag explicitly if true.
- NDVI and land_cover_class tell you what's on the ground now; high canopy may signal clearing costs.
- CROSS-REFERENCE: If listing self-reports anything that conflicts with Mireye terrain data (e.g. listing says "flat site" but slope_degrees is significant), flag the disagreement explicitly in your memo and in citations (source: "listing" for the claim, source: "mireye" for the counter-evidence).
- Score 80+ only for flat, well-drained, non-karst, non-wetland terrain with developed land cover.

{AGENT_OUTPUT_SCHEMA}"""


def _transport_system_prompt(
    agent_name: str,
    mireye_block: str,
    proximity_block: str,
    user_req_block: str,
) -> str:
    return f"""You are the {agent_name} for a commercial real estate site evaluation council.
Your job: assess transportation and logistics access for this site — road, rail, air, and sea.
{user_req_block}
{GROUNDING_RULE}

MIREYE DATA (primary source — cite as "mireye"):
{mireye_block}

DRIVE-TIME PROXIMITY DATA (from /v1/proximity — cite as "mireye"):
{proximity_block}

EVALUATION GUIDANCE:
- Lead with drive-time results over straight-line distance.
- Assess: road access (distance to major road), rail (if any), airport drive time, seaport if relevant.
- Consider the use case implied by the listing type — a retail site needs road access; a distribution center needs highway + rail.
- A major road within 200m is strong; >2km is a concern for most commercial uses.
- Score 80+ only if road access is excellent AND at least one multi-modal option (rail, air, or port) is viable.

{AGENT_OUTPUT_SCHEMA}"""


def _risk_system_prompt(
    agent_name: str,
    mireye_block: str,
    listing_block: str,
    user_req_block: str,
) -> str:
    return f"""You are the {agent_name} for a commercial real estate site evaluation council.
Your job: assess environmental, regulatory, and contamination risks that could constrain, delay, or prevent development of this site.
{user_req_block}
{GROUNDING_RULE}

MIREYE DATA (primary source — cite as "mireye"):
{mireye_block}

LISTING DATA (self-reported by the seller — cite as "listing"):
{listing_block}

EVALUATION GUIDANCE:
- FEMA flood zone: A or AE = 100-year floodplain (major constraint), X = minimal flood risk.
- UST (underground storage tank) facilities with open leaks nearby = contamination liability — flag count explicitly.
- Orphaned wells within 1km = legacy contamination and methane risk.
- Critical habitat or protected area = potential ESA/NEPA litigation risk — flag status (final vs proposed).
- Conservation easement = title encumbrance that may severely limit use.
- Karst terrain = sinkhole risk affecting foundations and insurance.
- CROSS-REFERENCE: If the listing self-reports anything about the site's condition, history, or use that could conflict with Mireye's risk data (e.g. listing highlights "clean site" but UST leaks are present nearby), flag the disagreement explicitly.
- Score below 50 if the site is in a 100-year floodplain, has confirmed nearby contamination, OR is critical habitat.

{AGENT_OUTPUT_SCHEMA}"""


# ---------------------------------------------------------------------------
# Core agent runner
# ---------------------------------------------------------------------------


async def run_agent(
    agent_key: str,
    all_mireye_fields: dict[str, Any],
    llm_structured: dict[str, Any],
    agent_field_list: list[str],
    proximity_data: dict[str, Any] | None = None,
    user_requirements: str | None = None,
) -> dict[str, Any]:
    """
    Run one agent asynchronously.

    Args:
        agent_key:         One of "energy", "water", "surface", "transport", "risk"
        all_mireye_fields: Full combined field dict (cache + newly fetched)
        llm_structured:    The cart item's llm_structured schema
        agent_field_list:  The specific fields for this agent
        proximity_data:    Optional /v1/proximity result for energy/transport agents
        user_requirements: Optional string detailing user-specified constraints

    Returns an AgentResult dict matching the schema in Step 4 of the guide.
    """
    agent_name = AGENT_NAMES[agent_key]
    logger.info("[AGENT START] %s", agent_name)

    # Build the Mireye data block for this agent's fields
    mireye_block = _format_mireye_fields_for_prompt(all_mireye_fields, agent_field_list)

    # Build proximity block (if any)
    proximity_block = "Not available."
    if proximity_data:
        try:
            proximity_block = json.dumps(proximity_data, indent=2)[:3000]  # truncate if huge
        except Exception:
            proximity_block = str(proximity_data)[:3000]

    # Build llm_structured slice for risk/surface agents
    listing_block = "(not applicable for this agent)"
    slice_spec = LLM_STRUCTURED_SLICES.get(agent_key, [])
    if slice_spec:
        listing_slice = _extract_llm_structured_slice(llm_structured, slice_spec)
        listing_block = _format_listing_slice_for_prompt(listing_slice)

    user_req_block = ""
    if user_requirements:
        user_req_block = f"\n\nUSER REQUIREMENTS:\nThe user has specified these requirements/preferences for this site:\n\"{user_requirements}\"\nTake these strictly into account when assessing risk, scoring, and writing your memo.\n"

    # Select the system prompt for this agent
    if agent_key == "energy":
        prompt = _energy_system_prompt(agent_name, mireye_block, proximity_block, user_req_block)
    elif agent_key == "water":
        prompt = _water_system_prompt(agent_name, mireye_block, user_req_block)
    elif agent_key == "surface":
        prompt = _surface_system_prompt(agent_name, mireye_block, listing_block, user_req_block)
    elif agent_key == "transport":
        prompt = _transport_system_prompt(agent_name, mireye_block, proximity_block, user_req_block)
    elif agent_key == "risk":
        prompt = _risk_system_prompt(agent_name, mireye_block, listing_block, user_req_block)
    else:
        raise ValueError(f"Unknown agent_key: {agent_key!r}")

    # Run the LLM call in a thread pool (openai SDK is synchronous)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _call_openai, agent_key, prompt)

    logger.info("[AGENT DONE] %s | score=%s | citations=%d", agent_name, result.get("score"), len(result.get("citations", [])))
    return result


def _call_openai(agent_key: str, prompt: str) -> dict[str, Any]:
    """Synchronous OpenAI call (run inside executor)."""
    agent_name = AGENT_NAMES[agent_key]
    model_name = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    try:
        client = _get_openai_client()
        response = client.chat.completions.create(
            model=model_name,
            response_format={"type": "json_object"},
            temperature=0.2,
            max_tokens=2048,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": "Generate your evaluation report now."},
            ],
        )
        raw_text = response.choices[0].message.content.strip()

        # Parse the JSON response
        result = json.loads(raw_text)

        # Enforce required fields — fill in defaults if LLM omitted them
        result.setdefault("agent_name", agent_name)
        result.setdefault("score", 0)
        result.setdefault("summary", "No summary generated.")
        result.setdefault("memo", "No memo generated.")
        result.setdefault("citations", [])
        result.setdefault("data_availability", "partial")

        # Clamp score to 0-100
        result["score"] = max(0, min(100, int(result["score"])))

        return result

    except json.JSONDecodeError as e:
        logger.error("[AGENT %s] JSON parse error: %s", agent_key, e)
        return _error_result(agent_name, f"JSON parse error: {e}")
    except Exception as e:
        logger.error("[AGENT %s] Unexpected error: %s", agent_key, e)
        return _error_result(agent_name, str(e))


def _error_result(agent_name: str, error_msg: str) -> dict[str, Any]:
    """Return a safe fallback result when an agent fails."""
    return {
        "agent_name": agent_name,
        "score": 0,
        "summary": f"Agent failed: {error_msg}",
        "memo": f"This agent encountered an error and could not produce a report. Error: {error_msg}",
        "citations": [],
        "data_availability": "unavailable",
    }


# ---------------------------------------------------------------------------
# Run all 5 agents concurrently
# ---------------------------------------------------------------------------


async def run_all_agents(
    all_mireye_fields: dict[str, Any],
    llm_structured: dict[str, Any],
    agent_field_map: dict[str, list[str]],
    proximity_results: dict[str, dict[str, Any]] | None = None,
    user_requirements: str | None = None,
) -> list[dict[str, Any]]:
    """
    Run all 5 agents concurrently via asyncio.gather.

    Args:
        all_mireye_fields:  Combined field dict (all agent fields merged)
        llm_structured:     The listing's canonical schema
        agent_field_map:    AGENT_FIELD_MAP from config
        proximity_results:  Optional dict keyed by agent_key → proximity response
        user_requirements:  Optional string of user goals for this site.

    Returns list of 5 AgentResult dicts (one per agent, in config order).
    """
    proximity_results = proximity_results or {}

    tasks = [
        run_agent(
            agent_key=key,
            all_mireye_fields=all_mireye_fields,
            llm_structured=llm_structured,
            agent_field_list=fields,
            proximity_data=proximity_results.get(key),
            user_requirements=user_requirements,
        )
        for key, fields in agent_field_map.items()
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert any exceptions into error results
    agent_names = list(agent_field_map.keys())
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("[AGENT GATHER] Agent %s raised: %s", agent_names[i], result)
            final_results.append(_error_result(AGENT_NAMES[agent_names[i]], str(result)))
        else:
            final_results.append(result)

    return final_results
