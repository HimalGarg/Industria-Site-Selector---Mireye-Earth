"""
backend/chat/router_engine.py — LLM Router for Mireye field expansion
========================================================================

Decides whether a user chat query can be answered from existing evaluation context,
or if specific extra fields from the 58-field Mireye inventory need to be fetched.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from openai import OpenAI

from evaluate.config import AGENT_FIELD_MAP, IDENTITY_FIELDS
from evaluate.mireye_fetcher import fetch_fields_with_cache

logger = logging.getLogger(__name__)

# Complete list of 58 Mireye fields from config
FULL_MIREYE_INVENTORY: list[dict[str, str]] = [
    # Energy
    {"field": "nearest_power_plant_name", "description": "Name of nearest power generation plant"},
    {"field": "nearest_power_plant_distance_m", "description": "Distance in meters to nearest power plant"},
    {"field": "nearest_power_plant_fuel_type", "description": "Fuel type of nearest power plant (solar, gas, coal, etc.)"},
    {"field": "nearest_power_plant_capacity_mw", "description": "Generation capacity in MW"},
    {"field": "nearest_transmission_line_distance_m", "description": "Distance in meters to nearest high-voltage transmission line"},
    {"field": "nearest_transmission_line_voltage_kv", "description": "Voltage rating in kV of nearest transmission line"},
    {"field": "nearest_transmission_line_voltage_class", "description": "Voltage classification rating"},
    {"field": "nearest_transmission_line_status", "description": "Status of transmission line (IN SERVICE, inactive)"},
    {"field": "highest_voltage_line_within_2km", "description": "Highest voltage line in kV within 2km radius"},
    {"field": "transmission_lines_within_2km_count", "description": "Number of transmission lines within 2km radius"},
    {"field": "nearest_natural_gas_pipeline_distance_m", "description": "Distance to nearest natural gas pipeline"},

    # Water
    {"field": "in_public_water_service_area", "description": "Boolean whether property is inside public water service boundary"},
    {"field": "water_utility_name", "description": "Name of public water utility provider"},
    {"field": "water_system_pwsid", "description": "Public water system ID (PWSID)"},
    {"field": "nearest_wastewater_plant_name", "description": "Name of nearest wastewater treatment plant"},
    {"field": "nearest_wastewater_plant_distance_m", "description": "Distance to nearest wastewater treatment facility"},
    {"field": "nearest_wastewater_plant_population_served", "description": "Population served by wastewater facility"},
    {"field": "nearest_stream_or_river_name", "description": "Name of nearest stream, river, or water body"},
    {"field": "wetlands_within_100m_count", "description": "Count of USFWS NWI mapped wetlands within 100m"},
    {"field": "wetlands_within_500m_count", "description": "Count of USFWS NWI mapped wetlands within 500m"},
    {"field": "surface_water_pct_time_covered", "description": "Percentage of time surface water covers land"},
    {"field": "huc12_watershed", "description": "HUC-12 watershed identifier name"},

    # Surface & Environment
    {"field": "elevation_m", "description": "Elevation in meters above sea level (USGS 3DEP)"},
    {"field": "slope_degrees", "description": "Terrain slope in degrees"},
    {"field": "aspect_direction", "description": "Compass aspect direction of slope"},
    {"field": "soil_drainage_class", "description": "NRCS soil drainage classification (well drained, poorly drained, etc.)"},
    {"field": "soil_hydrologic_group", "description": "NRCS hydrologic soil group (A, B, C, D)"},
    {"field": "soil_map_unit_name", "description": "NRCS gNATSGO soil unit taxonomy name"},
    {"field": "bedrock_depth_cm", "description": "Depth in centimeters to bedrock"},
    {"field": "flooding_frequency", "description": "NRCS soil flooding frequency rating"},
    {"field": "ponding_frequency", "description": "NRCS soil ponding frequency rating"},
    {"field": "karst_susceptibility", "description": "USGS Karst topography susceptibility rating"},
    {"field": "land_use_class", "description": "USFS LCMS land cover class (developed, forest, agriculture)"},
    {"field": "tree_canopy_pct", "description": "USFS NLCD tree canopy coverage percentage"},
    {"field": "impervious_surface_pct", "description": "Impervious surface percentage"},
    {"field": "ndvi_current", "description": "Current Copernicus Sentinel-2 NDVI vegetation index"},
    {"field": "coast_distance_m", "description": "Distance in meters to nearest coastline"},

    # Transport
    {"field": "nearest_major_road_name", "description": "Name of nearest highway or major thoroughfare"},
    {"field": "nearest_major_road_distance_m", "description": "Distance in meters to nearest major road"},
    {"field": "nearest_rail_line_distance_m", "description": "Distance to active freight rail line"},
    {"field": "nearest_rail_line_operator", "description": "Rail road operator name (Class I / regional)"},
    {"field": "nearest_airport_name", "description": "Name of nearest FAA commercial or cargo airport"},
    {"field": "nearest_airport_distance_m", "description": "Distance in meters to nearest airport"},
    {"field": "nearest_deepwater_port_name", "description": "Name of nearest commercial deepwater port"},
    {"field": "nearest_deepwater_port_distance_m", "description": "Distance to nearest commercial port"},

    # Risk & Regulatory
    {"field": "fema_flood_zone", "description": "FEMA Flood Insurance Rate Map Zone (X, A, AE, VE, 500-yr)"},
    {"field": "fema_floodway_status", "description": "Inside regulatory floodway boolean"},
    {"field": "ust_facilities_within_1km_count", "description": "EPA underground storage tank (UST) facilities count within 1km"},
    {"field": "ust_tanks_within_1km_count", "description": "Total registered UST tanks within 1km"},
    {"field": "active_ust_tanks_within_1km_count", "description": "Active registered UST tanks within 1km"},
    {"field": "orphaned_wells_within-[#km_count", "description": "Orphaned oil/gas wells within 1km"},
    {"field": "critical_habitat_within_1km", "description": "USFWS critical endangered species habitat flag"},
    {"field": "opportunity_zone_status", "description": "Federal Tax Opportunity Zone designation status"},
    {"field": "brownfield_site_within_500m", "description": "EPA Superfund / Brownfield site flag within 500m"},
    {"field": "cell_towers_within_1km_count", "description": "FCC registered cellular antenna towers count within 1km"},
]


def route_chat_query(
    user_message: str,
    cached_fields: dict[str, Any],
    cache_key: str,
) -> tuple[str, list[str]]:
    """
    Decides whether to answer from existing context or fetch additional Mireye fields.
    
    Returns:
        (action, field_list) where action is "answer_from_existing_context" or "fetch_fields"
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[ROUTER] OPENAI_API_KEY missing — defaulting to answer_from_existing_context")
        return ("answer_from_existing_context", [])

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    already_cached_keys = list(cached_fields.keys())

    system_prompt = (
        "You are an intelligent data router for commercial real estate site selection.\n"
        "Your task is to analyze a user's question about a site and decide whether the question can be "
        "answered from existing cached data, or if specific additional fields from the 58-field Mireye "
        "location intelligence inventory need to be fetched.\n\n"
        "Rule 1: If the question is about flood zones, wetlands, slope, elevation, power plants, wastewater, "
        "airports, major roads, or anything ALREADY in the cached field list, return action='answer_from_existing_context'.\n"
        "Rule 2: If the user asks about an explicit un-cached dataset (e.g. opportunity zone status, karst susceptibility, "
        "cell towers, brownfield sites, gas pipelines, rail lines, soil drainage), return action='fetch_fields' with "
        "the requested field names in 'fields'.\n"
        "Rule 3: Maximum 5 fields per turn. If the question is very broad, pick at most 5 most relevant fields.\n\n"
        "Return ONLY a JSON object with this structure:\n"
        "{\n"
        '  "action": "answer_from_existing_context" | "fetch_fields",\n'
        '  "fields": ["field_name_1", "field_name_2"]\n'
        "}"
    )

    user_prompt = (
        f"User Message: {user_message!r}\n\n"
        f"Already Cached Fields ({len(already_cached_keys)}): {already_cached_keys}\n\n"
        f"Available Mireye Field Inventory:\n"
        f"{json.dumps(FULL_MIREYE_INVENTORY, indent=2)}\n"
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

        raw_content = response.choices[0].message.content or "{}"
        parsed = json.loads(raw_content)

        action = parsed.get("action", "answer_from_existing_context")
        fields = parsed.get("fields", [])

        if not isinstance(fields, list):
            fields = []

        # Enforce max 5 fields cap per turn
        fields = [f for f in fields if isinstance(f, str)][:5]

        # Filter out fields that are already cached
        fields = [f for f in fields if f not in cached_fields]

        if fields and action == "fetch_fields":
            logger.info("[ROUTER] Fetching %d new fields for %r: %s", len(fields), cache_key, fields)
            # Re-use existing mireye_fetcher to fetch & merge into cache
            fetch_fields_with_cache(cache_key, fields)
            return ("fetch_fields", fields)

        return ("answer_from_existing_context", [])

    except Exception as e:
        logger.error("[ROUTER ERROR] %s — falling back to existing context", e)
        return ("answer_from_existing_context", [])
