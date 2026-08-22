# Build Task: Evaluation Pipeline (Cart Item → Mireye → Council Report)

## Scope of this task, explicitly

Build ONLY this: given a `cart_item_id` already in `site_ranker.db`, produce
and store a full council evaluation (5 agents + synthesizer) grounded in
Mireye data and the listing's own `llm_structured` data.

Do NOT build in this task: chat/router mode, comparison view, session-level
intent notes, per-listing chat memory. Those are separate follow-up tasks
that depend on this one existing first. If you find yourself building any
of those, stop — you've gone out of scope.

---

## Context you need

- `backend/main.py` already has `POST /cart-items` and `GET /cart-items`,
  a SQLite `cart_items` table, and a `build_llm_structured_data()`
  function producing the schema described in `docs/build_context.md`
  section 6. Read that schema before writing anything — every agent
  prompt in this task pulls from it.
- Mireye API integration should already exist from an earlier phase
  (`mireye` client). If it doesn't, or if you can't find it, stop and
  flag this rather than reimplementing it from scratch.
- This task adds new tables and endpoints to the same backend — it does
  not create a new service.

---

## Step 1 — New tables

Add two tables to `site_ranker.db` (same DB, same file, new tables via
migration in `main.py`'s existing migration handler pattern):

```sql
CREATE TABLE IF NOT EXISTS mireye_cache (
  cache_key TEXT PRIMARY KEY,        -- normalized address or "lat,lng"
  fields TEXT NOT NULL,               -- JSON blob, additive: {field_name: value, ...}
  last_updated TEXT NOT NULL          -- ISO 8601 UTC
);

CREATE TABLE IF NOT EXISTS evaluations (
  evaluation_id TEXT PRIMARY KEY,     -- UUID
  cart_item_id TEXT NOT NULL,         -- FK to cart_items
  overall_score INTEGER,
  recommendation TEXT,
  conflicts_flagged TEXT,             -- JSON array of strings
  agent_results TEXT NOT NULL,        -- JSON array, see Step 4 shape
  created_at TEXT NOT NULL            -- ISO 8601 UTC
);
```

`mireye_cache` is additive-only: when you fetch new fields for a
cache_key that already has some fields cached, merge (don't overwrite)
the JSON blob, and bump `last_updated`. This is what makes future
chat-router calls (a later task) cheap — they check this table before
ever calling Mireye again.

---

## Step 2 — Mireye field inventory (fixed set for default evaluation)

This is updated against the real Mireye capability list
(`docs/mireye_questions.md` — every question there maps to an actual API
field). No cost constraint on the Mireye key, so this set is deliberately
richer than a bare-minimum MVP would use — more citations per agent
means a more defensible report, which is the actual product pitch.

Define this as a config object/file, not inline in the endpoint handler:

```js
const AGENT_FIELD_MAP = {
  energy: [
    'nearest_power_plant_name',
    'nearest_power_plant_distance_m',
    'nearest_power_plant_fuel_type',
    'nearest_power_plant_capacity_mw',
    'nearest_transmission_line_distance_m',
    'nearest_transmission_line_voltage_kv',
    'nearest_transmission_line_voltage_class',
    'nearest_transmission_line_status',       // in service / under construction / inactive
    'highest_voltage_line_within_2km',
    'transmission_lines_within_2km_count',
    'nearest_natural_gas_pipeline_distance_m',
  ],
  water: [
    'in_public_water_service_area',
    'water_utility_name',
    'water_system_pwsid',
    'nearest_wastewater_plant_name',
    'nearest_wastewater_plant_distance_m',
    'nearest_wastewater_plant_population_served',
    'nearest_stream_or_river_name',
    'wetlands_within_100m_count',
    'wetlands_within_500m_count',
    'surface_water_pct_time_covered',
    'huc12_watershed',
  ],
  surface: [
    'elevation_m',
    'slope_degrees',
    'aspect_direction',                       // which way the hillside faces
    'soil_drainage_class',
    'soil_map_unit_name',
    'bedrock_depth_cm',
    'is_karst_terrain',
    'karst_exposure_class',
    'land_cover_class',
    'land_use_class',
    'tree_canopy_pct',
    'ndvi_current',
    'ndvi_5yr_trend',
    'federal_wetlands_flag',
    'wetland_type',
    'distance_to_coast_m',
  ],
  transport: [
    'nearest_major_road_name',
    'nearest_major_road_distance_m',
    'nearest_railroad_distance_m',
    'nearest_airport_name',
    'nearest_airport_distance_m',
    'nearest_seaport_name',
    'nearest_seaport_distance_m',
    'nearest_catalogued_bridge_name',
  ],
  risk: [
    'fema_flood_zone',
    'is_wetland_at_point',
    'ust_facilities_within_1km_count',
    'ust_facilities_with_open_leak_count',
    'nearest_hazardous_waste_facility_distance_m',
    'orphaned_wells_within_1km_count',
    'is_karst_terrain',                       // shared with surface, cheap dup from same cache entry
    'is_critical_habitat',
    'critical_habitat_status',                // final vs proposed
    'is_protected_area',
    'protected_area_gap_status',
    'has_conservation_easement',
    'conservation_easement_type',
  ],
};
```

This is the fixed set the default evaluation calls. Notes:

- **Field names above are our own working identifiers**, written to
  match the natural-language capability list in
  `docs/mireye_questions.md`. When wiring the actual Mireye client,
  confirm the literal JSON response key names from a real `/v1/fetch`
  (or equivalent) call and adjust the mapping — the capability doc
  describes *what's available*, not the exact wire-format keys. Do this
  confirmation once, early, rather than guessing key names throughout
  the agent code.
- `is_karst_terrain` appears in both `surface` and `risk` on purpose —
  it's genuinely relevant to both agents' framing (buildability vs.
  environmental risk) but should only be fetched/cached once per
  coordinate. The cache in Step 1 already handles this correctly since
  it's keyed by field name, not by agent.
- Do not expand this list ad hoc later — if a specific evaluation needs
  more, that's what the chat-router task (separate, future) is for. This
  list stays the default, predictable set every evaluation gets.

### Jurisdiction/identity fields — fetch once, use everywhere

Also fetch these once per cart item (not per-agent, just once, stored
alongside the evaluation or on the cart item itself) since they're cheap
context useful in the synthesizer's narrative and in report headers:

```js
const IDENTITY_FIELDS = [
  'resolved_address',           // canonical, from address resolution
  'coordinate_match_quality',   // rooftop vs interpolated — worth surfacing, affects confidence
  'state', 'county', 'city',
  'census_tract_geoid',
  'congressional_district',
  'cbsa_metro_area',
  'is_opportunity_zone',
  'parcel_id',
];
```

`coordinate_match_quality` in particular is worth surfacing in the UI
later — a report built on an interpolated (not rooftop) address match is
meaningfully less trustworthy than one on a confirmed rooftop match, and
your citation/grounding discipline should extend to flagging this.

### Optional: use `/v1/proximity` for "nearest by drive time" instead of straight-line

The field list above (e.g. `nearest_power_plant_distance_m`,
`nearest_airport_distance_m`) is likely straight-line/geodesic distance
from a single-point fetch. Mireye also exposes a proximity/matrix engine
(`/v1/proximity`) with curated sets (`@airports`, `@substations`,
`@power_plants`, `@rail`, `@ports`) that can return **drive-time** and
**driving-distance** nearest-N results, which is more meaningful for a
site-selection use case than straight-line distance (a power plant 2
miles away across a river is not "2 miles away" in any useful sense).

Since there's no cost constraint on the key: prefer proximity/drive-time
results over straight-line distance wherever both are available, for the
Energy and Transportation agents specifically. Store both if convenient
(straight-line as a fallback citation, drive-time as the primary one),
but lead every citation and every agent memo with the drive-time number
when you have it.

### Workforce/Proximity Agent (6th agent, optional per listing)

This was already scoped in the original site plan (worker's-day
narrative → labor shed) but hadn't been given a real field list. Now
that we have one: use `/v1/proximity`'s labor shed capability directly —
"How many people live within a 30/45/60-minute drive of this location?"
and the civilian labor force figure. This agent only runs when the user
supplies a worker's-day description (same trigger condition as the
original build guide) — keep it optional, not part of the fixed default
5-agent set above.

---

## Step 3 — `POST /evaluate-site` endpoint

```
POST /evaluate-site
  body: { cart_item_id: string }
  returns: { evaluation_id, status: "processing" }

GET /evaluate-site/{evaluation_id}
  returns: { status: "processing" | "done" | "error", ...evaluation fields if done }
```

Use an async job pattern (same as specified in the earlier website build
guide) — don't block the request for the full evaluation duration.
In-memory or simple polling-friendly job store is fine for a hackathon.

Handler logic:
1. Look up the cart item by `cart_item_id`, get its `address` and
   `llm_structured` JSON.
2. Resolve/geocode the address via Mireye's own address resolution
   (this is a real capability per `mireye_questions.md` — it also tells
   you `coordinate_match_quality`, which is worth capturing). Don't use
   a separate third-party geocoder if Mireye's own resolution works,
   since you want the same canonical coordinate Mireye itself will use
   for every other field lookup.
3. Build the `cache_key` (normalized address string or `"lat,lng"` — pick
   one and be consistent).
4. Fetch `IDENTITY_FIELDS` once (not per-agent) — cache these under the
   same cache_key, same additive-merge rule as everything else.
5. Check `mireye_cache` for this key. For each field in
   `AGENT_FIELD_MAP` (flattened across all 5 agents), if it's already
   cached, use the cached value. If not, call Mireye for it — preferring
   `/v1/proximity` drive-time results over straight-line distance for
   Energy and Transportation fields, per the note above.
6. Merge any newly-fetched fields into `mireye_cache` (additive update).
7. Proceed to Step 4 with the full field set now available (mix of
   cached + freshly fetched, doesn't matter which).

---

## Step 4 — Run the 5 agents concurrently

Each agent is an async function, all run with `Promise.all` /
`asyncio.gather` — not sequentially. Each agent gets:
- Its slice of Mireye fields (from `AGENT_FIELD_MAP`)
- The relevant slice of the listing's own `llm_structured` data, if any
  agent overlaps with it (see Step 5 — this is new, not in the earlier
  generic guide)

Enforce this output shape per agent (JSON mode / tool use):

```json
{
  "agent_name": "Energy & Power Infra Agent",
  "score": 0-100,
  "summary": "1-2 sentence verdict",
  "memo": "full written reasoning",
  "citations": [
    { "source": "mireye", "field": "nearest_power_plant_capacity_mw", "value": "..." }
  ],
  "data_availability": "full | partial | unavailable"
}
```

**Grounding rule, non-negotiable:** the system prompt for every agent
must instruct it to only make claims traceable to a citation, and to
explicitly say "not available" for any null/missing field rather than
estimating. If an agent's memo contains a claim with no matching
citation entry, that's a bug — this should be checkable in testing by
scanning agent output for numbers/facts not present in the citations
list.

---

## Step 5 — Cross-referencing listing claims against Mireye (new)

For the **Risk & Compliance Agent** and **Surface & Environment Agent**
specifically, also pass in any overlapping fields from the listing's own
`llm_structured` data (e.g. `property.year_built`,
`financials.occupancy_percent` if relevant to risk framing). Instruct
these two agents to flag explicit disagreement if the listing's
self-reported data conflicts with Mireye's independent data — e.g.
listing claims "high traffic corridor" but Mireye's
`distance_to_highway` suggests otherwise.

**Label sources separately in the prompt and in citations** — never
merge listing-stated facts and Mireye-derived facts into one
undifferentiated claim. Citations should carry a `source` field
(`"mireye"` vs `"listing"`) as shown in the Step 4 JSON shape, exactly
so this distinction survives into the stored evaluation and can be
displayed separately later.

---

## Step 6 — Synthesizer

One more LLM call, taking all 5 agent outputs as input:

```json
{
  "overall_score": 0-100,
  "recommendation": "short verdict",
  "conflicts_flagged": [
    "string describing a cross-agent tension or a listing-vs-Mireye disagreement"
  ],
  "narrative_summary": "board-readable paragraph"
}
```

Populate `conflicts_flagged` from two sources: cross-agent tensions
(e.g. strong power score but high risk score) AND any
listing-vs-Mireye disagreements flagged by individual agents in Step 5 —
don't let the synthesizer drop those on the floor, surface them
explicitly since they're a meaningful differentiator for this product.

Do not let the synthesizer hide or overwrite the raw per-agent scores —
store both.

---

## Step 7 — Persist and return

Write one row to `evaluations`: `overall_score`, `recommendation`,
`conflicts_flagged` (JSON array), `agent_results` (JSON array of all 5
agent output objects from Step 4), timestamp. Mark the job `done`.

`GET /evaluate-site/{evaluation_id}` returns the full stored row,
parsed back into JSON (not raw strings) for the frontend to consume
directly.

---

## Step 8 — Testing

- Run against at least 2 real cart items already in `site_ranker.db`
  (one Crexi, one LoopNet, per the existing multi-site capture) to
  confirm the pipeline works regardless of source adapter.
- Confirm the cache actually prevents duplicate Mireye calls: run
  evaluation twice on the same cart item (or two cart items at the same
  address) and confirm the second run hits `mireye_cache` instead of
  calling Mireye again — log this explicitly so it's visible during
  testing, not just assumed.
- Confirm a listing with sparse `llm_structured` data (lots of nulls,
  common on LoopNet per the schema example in build_context.md) still
  produces a coherent evaluation — agents should say "not available"
  gracefully, not error out.
- Manually inspect at least one agent's citations against its memo text
  to confirm every claim traces back to a real cited field — this is
  the grounding check from Step 4, do it by hand at least once.

---

## Handoff checklist

- [x] `mireye_cache` and `evaluations` tables created via migration
- [x] `AGENT_FIELD_MAP` and `IDENTITY_FIELDS` defined as reusable
      config, not inline; field key names confirmed against a real
      Mireye response, not just assumed from the capability doc
- [x] Address resolution goes through Mireye's own resolution (not a
      separate geocoder), `coordinate_match_quality` captured
- [x] `POST /evaluate-site` + `GET /evaluate-site/{id}` working,
      async job pattern, not blocking
- [x] Cache checked before every Mireye call; additive merge on new
      fields; confirmed via repeat-run test
- [x] Energy/Transportation agents prefer `/v1/proximity` drive-time
      results over straight-line distance where both are available
- [x] All 5 agents run concurrently, enforced output shape with
      per-field citations tagged by source (`mireye` vs `listing`)
- [x] Risk & Surface agents cross-reference listing data where
      overlapping, flag disagreements explicitly
- [x] Synthesizer produces overall score + narrative + conflicts,
      without hiding raw agent scores
- [x] Tested against 2+ real cart items from different source adapters
- [x] Sparse-data listing (many nulls) handled gracefully, not an error

---

## Explicitly out of scope for this task (do not build)

- Chat-triggered ad-hoc Mireye field lookups (router logic)
- Comparison view across multiple evaluations
- Session-level "what the user is looking for" note
- Per-listing chat memory / notes panel
- Frontend rendering of any of this — this task is backend-only
