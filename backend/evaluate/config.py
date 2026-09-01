"""
backend/evaluate/config.py — Field inventory and agent configuration
=====================================================================

AGENT_FIELD_MAP  — Fixed set of Mireye fields each agent receives.
                   Field names here are confirmed against real /v1/fetch
                   responses (see mireye_test_logs/). Do NOT add fields
                   ad-hoc; use the chat-router task for per-evaluation extras.

IDENTITY_FIELDS  — Fetched once per evaluation (not per-agent). Provides
                   jurisdiction context used by the synthesizer's narrative
                   and by report headers.

AGENT_NAMES      — Display names keyed by agent_key.

NOTE on field naming:
  The names below are confirmed to be exact Mireye API wire-format keys,
  verified from sample /v1/fetch responses in the mireye_test_logs/ directory.
  Fields marked # CONFIRM mean they appear in mireye_questions.md but have not
  yet been confirmed from a live response — treat as best-guess until a real
  call returns them. The mireye_fetcher.py will log null fields explicitly so
  any mismatches surface immediately during testing.
"""

# ---------------------------------------------------------------------------
# Agent → field mapping
# ---------------------------------------------------------------------------

AGENT_FIELD_MAP: dict[str, list[str]] = {
    "energy": [
        "nearest_power_plant_name",
        "nearest_power_plant_distance_m",
        "nearest_power_plant_fuel_type",
        "nearest_power_plant_capacity_mw",
        "nearest_transmission_line_distance_m",
        "nearest_transmission_line_voltage_kv",
        "nearest_transmission_line_voltage_class",
        "nearest_transmission_line_status",      # in service / under construction / inactive
        "highest_voltage_line_within_2km",
        "transmission_lines_within_2km_count",
        "nearest_natural_gas_pipeline_distance_m",
    ],
    "water": [
        "in_public_water_service_area",
        "water_utility_name",
        "water_system_pwsid",
        "nearest_wastewater_plant_name",
        "nearest_wastewater_plant_distance_m",
        "nearest_wastewater_plant_population_served",
        "nearest_stream_or_river_name",
        "wetlands_within_100m_count",
        "wetlands_within_500m_count",
        "surface_water_pct_time_covered",
        "huc12_watershed",
    ],
    "surface": [
        "elevation",            # NOTE: Mireye returns this as "elevation" (unit=meters) — mapped in fetcher
        "slope_degrees",
        "aspect_direction",
        "soil_drainage_class",
        "soil_map_unit_name",
        "bedrock_depth_cm",
        "is_karst_terrain",
        "karst_exposure_class",
        "land_cover_class",
        "land_use_class",
        "tree_canopy_pct",
        "ndvi_current",
        "ndvi_5yr_trend",
        "federal_wetlands_flag",
        "wetland_type",
        "distance_to_coast_m",
    ],
    "transport": [
        "nearest_major_road_name",
        "nearest_major_road_distance_m",
        "nearest_railroad_distance_m",
        "nearest_airport_name",
        "nearest_airport_distance_m",
        "nearest_seaport_name",
        "nearest_seaport_distance_m",
        "nearest_catalogued_bridge_name",
    ],
    "risk": [
        "fema_flood_zone",
        "is_wetland_at_point",
        "ust_facilities_within_1km_count",
        "ust_facilities_with_open_leak_count",
        "nearest_hazardous_waste_facility_distance_m",
        "orphaned_wells_within_1km_count",
        "is_karst_terrain",          # shared with surface — fetched once, used by both agents
        "is_critical_habitat",
        "critical_habitat_status",   # final vs proposed
        "is_protected_area",
        "protected_area_gap_status",
        "has_conservation_easement",
        "conservation_easement_type",
    ],
}

# All unique fields across all agents (deduplicated — is_karst_terrain only fetched once)
ALL_AGENT_FIELDS: list[str] = list(dict.fromkeys(
    field
    for fields in AGENT_FIELD_MAP.values()
    for field in fields
))

# ---------------------------------------------------------------------------
# Identity fields — fetched once per evaluation, not per-agent
# ---------------------------------------------------------------------------

IDENTITY_FIELDS: list[str] = [
    # NOTE: resolved_address and coordinate_match_quality come from the geocode
    # block of ANY /v1/fetch response — we don't need to request them as fields.
    # The remaining fields below are proper Mireye field names.
    "state",
    "county",
    "city",
    "census_tract_geoid",
    "congressional_district",
    "cbsa_metro_area",
    "is_opportunity_zone",
    "parcel_id",
]

# ---------------------------------------------------------------------------
# Proximity curated sets (for /v1/proximity drive-time queries)
# Energy and Transport agents prefer drive-time over straight-line distance.
# ---------------------------------------------------------------------------

PROXIMITY_CURATED_SETS: dict[str, str] = {
    "energy":    "@power_plants",
    "transport": "@airports",        # primary transport proximity target
    "transport_ports": "@ports",
    "transport_rail":  "@rail",
}

# ---------------------------------------------------------------------------
# Agent display names (key → label used in agent_results JSON)
# ---------------------------------------------------------------------------

AGENT_NAMES: dict[str, str] = {
    "energy":    "Energy & Power Infrastructure Agent",
    "water":     "Water & Watershed Agent",
    "surface":   "Surface & Environment Agent",
    "transport": "Transportation & Access Agent",
    "risk":      "Risk & Compliance Agent",
}

# ---------------------------------------------------------------------------
# llm_structured slices passed to each agent for cross-referencing
# Only Risk and Surface agents need listing-side data (per the guide).
# ---------------------------------------------------------------------------

LLM_STRUCTURED_SLICES: dict[str, list[tuple[str, str]]] = {
    # Format: list of (section, field) tuples from the llm_structured schema
    "risk": [
        ("property", "property_type"),
        ("property", "year_built"),
        ("property", "lot_acres"),
        ("financials", "occupancy_percent"),
        ("narrative", "description"),
        ("narrative", "highlights"),
    ],
    "surface": [
        ("property", "property_type"),
        ("property", "lot_acres"),
        ("property", "building_sqft"),
        ("narrative", "description"),
        ("narrative", "highlights"),
    ],
}
