# Build Task: Separate Raw Scraped Data from LLM Inference Data

## Purpose

Refactor the current listing-data pipeline so that:

1. The scraper's raw output is preserved unchanged for provenance, debugging, and future re-processing.
2. A separate `llm_structured` object is generated from the raw listing data.
3. `llm_structured` is the only representation sent to the LLM.
4. `llm_structured` is normalized, deduplicated, typed, and designed for inference rather than being a second copy of the raw scraper output.
5. Do not change the scraper's public extraction scope or add gated/private data.

The existing Crexi scraper/extension already extracts public, on-page listing information. The selector research confirms that Crexi's `property-detail-summary` exposes flexible label/value pairs and that sale and lease listings share the main PDP structure, while price formatting differs between sale and lease listings. Use those existing extraction capabilities rather than redesigning the scraper.

---

## Current Architecture

The desired pipeline is:

```text
Crexi / other supported listing site
        |
        v
RAW SCRAPED RECORD
        |
        |  preserve exactly
        v
NORMALIZER
        |
        v
LLM_STRUCTURED
        |
        v
LLM inference
```

There should be no `raw_attributes` copy inside `llm_structured`.

The raw record should remain available in storage, but it should NOT be included in the payload sent to the LLM.

---

# Step 1 — Inspect the Existing Implementation

Before changing code:

1. Locate the current scraper/capture implementation.
2. Locate the backend model/storage for cart/listing items.
3. Locate the code that currently constructs `llm_structured`.
4. Locate the code that sends listing data to the LLM.
5. Identify all existing tests around listing extraction, normalization, and LLM payload construction.
6. Do not change the scraper selectors unless required by an existing bug.

Document the actual files/functions involved before editing.

Important:
- Preserve the current raw scraper fields.
- Do not silently rename or delete raw fields.
- Do not move normalization logic into the browser extension unless that is already the established architecture.
- The extension should remain focused on capture.

---

# Step 2 — Preserve Raw Scraper Data

The raw scraped representation is an audit/provenance layer.

For each captured listing, preserve the original scraper output, including fields such as:

```json
{
  "cart_item_id": "...",
  "address": "...",
  "source_url": "...",
  "listing_title": "...",
  "image_url": "...",
  "details": {
    "...": "..."
  },
  "added_at": "..."
}
```

Do not require the raw representation to be pretty, normalized, or optimized for the LLM.

The raw record should be treated as the source of truth for what the scraper observed.

If the current system stores the raw record already, keep that behavior.

If the system currently overwrites raw data with normalized values, change it so the original scraped values remain recoverable.

---

# Step 3 — Remove Duplication from `llm_structured`

The current structure contains:

```text
llm_structured
├── site_identity
├── financials
├── physical_specifications
├── lease_investment_profile
├── narrative
└── raw_attributes
```

Remove:

```text
llm_structured.raw_attributes
```

`raw_attributes` is redundant because it duplicates the scraper's `details`/raw representation.

Do NOT remove the raw attributes from the stored raw record.

The distinction is:

```text
Stored raw record:
    raw details = KEEP

LLM payload:
    raw_attributes = REMOVE
```

---

# Step 4 — Build a Canonical LLM Schema

Replace the current `llm_structured` representation with a clean, inference-oriented schema.

Recommended structure:

```json
{
  "identity": {
    "address": "100 North Progress Avenue, Harrisburg, PA 17109",
    "source_url": "https://www.crexi.com/properties/2601532/pennsylvania-wendys",
    "listing_title": "Retail | 7.00% CAP | 2,629 SqFt"
  },

  "property": {
    "property_type": "Retail",
    "sub_type": "Restaurant, QSR/Fast Food",
    "building_sqft": 2629,
    "lot_acres": 0.9,
    "year_built": 1976
  },

  "financials": {
    "asking_price_display": "$2,037,286",
    "asking_price": 2037286,
    "cap_rate_percent": 7.0,
    "noi_annual": 142610,
    "occupancy_percent": null
  },

  "lease": {
    "tenant": "Wendy's",
    "tenancy": "Single",
    "lease_type": "NNN",
    "lease_term_years": 20,
    "lease_commencement": "2017-04-19",
    "lease_expiration": "2037-04-30",
    "rent_bumps": "10% every 5 years",
    "lease_options": "2x5"
  },

  "investment": {
    "investment_type": "Net Lease",
    "tenant_credit": "Franchisee",
    "ownership": "Fee Simple",
    "ground_lease": false
  },

  "market_context": {
    "population_5mi": 203000,
    "avg_household_income_1mi": 93100,
    "nearby_retail_center": "Union Square",
    "nearby_retail_center_sqft": 318000,
    "state_capitol_employment": 15000,
    "nearby_hospital_beds": 567,
    "nearby_student_population": 21420
  },

  "narrative": {
    "description": "...",
    "highlights": [
      "..."
    ]
  }
}
```

This is a recommended canonical organization, not a requirement that every field always exist.

Fields that are unavailable should be `null` or omitted according to the project's existing JSON conventions. Do not invent values.

---

# Step 5 — Normalize Types

The LLM schema should use typed values whenever the meaning is unambiguous.

Examples:

```text
"2,629"       -> 2629
"0.900"       -> 0.9
"7.00%"       -> 7.0
"$142,610"    -> 142610
"1976"        -> 1976
"Yes"         -> true
"No"          -> false
```

Dates should use ISO format where normalization is safe:

```text
04/19/2017 -> 2017-04-19
04/30/2037 -> 2037-04-30
```

Do not normalize values where interpretation is ambiguous.

---

# Step 6 — Fix Price Handling

There is an existing data-quality issue in the current example:

```json
"price_raw": "$2,037,286  |  56 days on market  |  Updated 20 days ago",
"price_numeric": 20372865620
```

Do not reproduce this behavior.

The numeric value should be:

```text
2037286
```

However, sale and lease listings have different price formats.

Examples:

```text
For sale:
"$2,300,000"

For lease:
"$16/SF/YR"
```

Therefore preserve the display representation separately:

```json
"financials": {
  "asking_price_display": "$2,300,000",
  "asking_price": 2300000
}
```

For a lease-rate listing:

```json
"financials": {
  "asking_price_display": "$16/SF/YR",
  "asking_price": null
}
```

Do NOT force lease rates into `asking_price`.

If the current scraper already captures a formatted price string, preserve that raw/display value and normalize it downstream.

Do not make the browser extension responsible for financial interpretation.

---

# Step 7 — Separate Listing Freshness Fields

The current raw price string can contain unrelated information:

```text
"$2,037,286 | 56 days on market | Updated 20 days ago"
```

The normalized LLM representation should separate these concepts.

Use fields such as:

```json
{
  "financials": {
    "asking_price_display": "$2,037,286"
  },
  "listing": {
    "days_on_market": 56,
    "days_since_update": 20
  }
}
```

If these values are not reliably available, use `null` or omit them.

Do not parse them from prose unless the parser can distinguish the components reliably.

---

# Step 8 — Flexible Property Detail Extraction

The existing Crexi extraction uses:

```text
[data-cy="property-detail-summary"] [data-cy="label"]
[data-cy="property-detail-summary"] [data-cy="value"]
```

These are matched label/value pairs.

Do not create a rigid scraper schema that assumes every listing contains:

- Cap Rate
- NOI
- Occupancy
- Lease Type
- Investment Type
- etc.

Different listing types expose different fields.

Instead:

1. Keep the raw label/value pairs in the raw scraper record.
2. Normalize known fields into canonical LLM fields when present.
3. Ignore irrelevant fields for the LLM schema unless they become useful to the inference task.
4. Never invent missing fields.

Example:

```text
Raw:
"Square Footage": "2,629"
"Cap Rate": "7.00%"
"NOI": "$142,610"
"Year Built": "1976"
"Tenancy": "Single"
```

Becomes:

```json
{
  "property": {
    "building_sqft": 2629,
    "year_built": 1976
  },
  "financials": {
    "cap_rate_percent": 7.0,
    "noi_annual": 142610
  },
  "lease": {
    "tenancy": "Single"
  }
}
```

---

# Step 9 — Narrative Normalization

Keep useful qualitative information because the LLM may need it for reasoning.

Recommended:

```json
"narrative": {
  "description": "...",
  "highlights": [
    "...",
    "...",
    "..."
  ]
}
```

Do not duplicate the same narrative under multiple keys.

If the scraper provides one large `highlights` string containing separators, normalize it into an array only when the separators are reliable.

Do not rewrite the broker's claims into factual assertions.

The narrative is listing-provided context, not independently verified truth.

---

# Step 10 — Tenant / Investment Information

Where the raw data contains fields such as:

```text
Brand/Tenant
Tenant Credit
Investment Type
Tenancy
Lease Type
Ownership
Ground Lease
```

map them to canonical fields:

```json
{
  "lease": {
    "tenant": "Wendy's",
    "tenancy": "Single",
    "lease_type": "NNN"
  },
  "investment": {
    "investment_type": "Net Lease",
    "tenant_credit": "Franchisee",
    "ownership": "Fee Simple",
    "ground_lease": false
  }
}
```

Do not duplicate `tenant` under both:

```text
lease.tenant
investment.tenant
```

unless there is a genuine semantic difference.

---

# Step 11 — Market Context

If market/context information is already available in the listing's narrative/highlights, it can be extracted into structured fields for inference.

For example:

```json
{
  "market_context": {
    "population_5mi": 203000,
    "avg_household_income_1mi": 93100,
    "nearby_retail_center": "Union Square",
    "nearby_retail_center_sqft": 318000,
    "state_capitol_employment": 15000,
    "nearby_hospital_beds": 567,
    "nearby_student_population": 21420
  }
}
```

Important:

These values are listing-provided claims unless independently verified elsewhere.

Do not silently treat them as authoritative external facts.

If the current implementation does not have reliable extraction for these values, do not build a fragile parser solely to produce this example schema. Keep the narrative instead.

---

# Step 12 — Derived Values

Only create derived fields when they can be calculated deterministically.

Examples that are reasonable:

```text
asking_price = parsed asking price
cap_rate_percent = parsed percentage
noi_annual = parsed NOI
building_sqft = parsed square footage
lease_term_years = parsed lease term
```

Do NOT have the normalizer make investment judgments.

Do not add fields such as:

```text
investment_score
deal_quality
tenant_risk
location_quality
good_deal
bad_deal
```

Those belong to the LLM inference layer.

The normalizer should prepare facts; the LLM should reason over them.

---

# Step 13 — Provenance

The LLM schema should retain enough provenance to identify the source listing.

At minimum:

```json
"identity": {
  "address": "...",
  "source_url": "...",
  "listing_title": "..."
}
```

If the project already has a listing/cart ID, keep it available at the application level.

Do not expose unnecessary scraper internals to the LLM.

The raw stored record remains the authoritative audit trail.

---

# Step 14 — LLM Payload Boundary

Find the exact function that creates the LLM request.

Change it so the LLM receives:

```text
llm_structured
```

and NOT:

```text
raw
details
raw_attributes
scraper metadata
duplicate normalized fields
```

Conceptually:

```js
const llmPayload = buildLLMStructured(rawListing);

await callLLM({
  listing: llmPayload
});
```

Do not do:

```js
await callLLM({
  raw: rawListing,
  structured: llmPayload
});
```

unless a future inference explicitly requires raw source material.

For this task, it should receive only the structured representation.

---

# Step 15 — Preserve Raw Data for Future Reprocessing

Do not delete raw data after normalization.

The purpose of retaining raw data is that the canonical schema may evolve.

For example:

```text
v1 raw
   ↓
v1 normalizer
   ↓
LLM schema v1
```

Later:

```text
same raw
   ↓
v2 normalizer
   ↓
LLM schema v2
```

This allows you to improve the inference schema without having to rescrape Crexi.

This is an important architectural requirement.

---

# Step 16 — Schema Version

Add a schema version to the LLM representation.

For example:

```json
{
  "schema_version": "1.0",
  "identity": {},
  "property": {},
  "financials": {}
}
```

If the project already has a versioning convention, use that instead.

Increment the version when the meaning or structure of the LLM schema changes materially.

Do not add a version field to the raw scraper payload unless the existing architecture already does so.

---

# Step 17 — Backward Compatibility

Before changing the schema:

1. Find existing consumers of `llm_structured`.
2. Identify code that references:
   - `site_identity`
   - `physical_specifications`
   - `lease_investment_profile`
   - `raw_attributes`
   - `financials`
3. Update those consumers to the new schema.
4. Do not leave code silently expecting the old shape.

If existing stored records use the old format, support them during migration if the application needs to process historical records.

Do not modify historical raw records.

---

# Step 18 — Tests

Add tests for normalization.

At minimum test:

### Test 1 — Sale listing

Input:

```text
Price: $2,037,286
Cap Rate: 7.00%
NOI: $142,610
Square Footage: 2,629
Year Built: 1976
```

Expected:

```json
{
  "financials": {
    "asking_price": 2037286,
    "cap_rate_percent": 7.0,
    "noi_annual": 142610
  },
  "property": {
    "building_sqft": 2629,
    "year_built": 1976
  }
}
```

### Test 2 — Lease rate

Input:

```text
Price: $16/SF/YR
```

Expected:

```json
{
  "financials": {
    "asking_price_display": "$16/SF/YR",
    "asking_price": null
  }
}
```

### Test 3 — Missing sale fields

A lease listing without Cap Rate/NOI should not fail normalization.

Expected:

```json
{
  "financials": {
    "cap_rate_percent": null,
    "noi_annual": null
  }
}
```

or the project's established convention of omission.

### Test 4 — Boolean normalization

```text
Rent Bumps: Yes
Ground Lease: No
```

Expected:

```json
{
  "rent_bumps": true,
  "ground_lease": false
}
```

If `rent_bumps` contains a schedule rather than only Yes/No, preserve the schedule separately instead of reducing it to a boolean.

### Test 5 — No raw duplication

Assert:

```text
llm_structured.raw_attributes
```

does not exist.

### Test 6 — Raw preservation

Given an input raw listing, verify that normalization does not mutate the original raw object.

### Test 7 — LLM boundary

Mock the LLM call and assert that its listing payload contains only the normalized LLM representation.

---

# Step 19 — Validate the Existing Example

After implementation, normalize the provided Wendy's example.

The resulting LLM payload should approximately contain:

```json
{
  "schema_version": "1.0",

  "identity": {
    "address": "100 North Progress Avenue, Harrisburg, PA 17109",
    "listing_title": "Retail | 7.00% CAP | 2,629 SqFt",
    "source_url": "https://www.crexi.com/properties/2601532/pennsylvania-wendys"
  },

  "property": {
    "property_type": "Retail",
    "sub_type": "Restaurant, QSR/Fast Food",
    "building_sqft": 2629,
    "lot_acres": 0.9,
    "year_built": 1976
  },

  "financials": {
    "asking_price_display": "$2,037,286",
    "asking_price": 2037286,
    "cap_rate_percent": 7.0,
    "noi_annual": 142610
  },

  "lease": {
    "tenant": "Wendy's",
    "tenancy": "Single",
    "lease_type": "NNN",
    "lease_term_years": 20,
    "lease_commencement": "2017-04-19",
    "lease_expiration": "2037-04-30",
    "lease_options": "2x5"
  },

  "investment": {
    "investment_type": "Net Lease",
    "tenant_credit": "Franchisee",
    "ownership": "Fee Simple",
    "ground_lease": false
  },

  "narrative": {
    "description": "...",
    "highlights": []
  }
}
```

Do not invent fields that cannot be reliably derived from the raw input.

Also correct the known bad numeric price from the current example.

---

# Step 20 — Do Not Expand Scraper Scope

This task is a normalization/schema task.

Do NOT:

- scrape broker phone numbers
- scrape broker email
- bypass Crexi click-to-reveal gates
- scrape login-only information
- add new listing websites
- redesign the capture extension
- add evaluation logic to the scraper
- make Mireye calls from the scraper
- add LLM reasoning to the scraper

The existing Crexi selector research explicitly confirms that broker phone/email are gated and should not be extracted. Keep that boundary intact.

---

# Step 21 — Final Verification Checklist

Before declaring the task complete:

- [ ] Raw scraper data is still preserved.
- [ ] Raw data is not sent to the LLM.
- [ ] `llm_structured.raw_attributes` has been removed.
- [ ] LLM schema is canonical and deduplicated.
- [ ] Numeric values are correctly typed.
- [ ] Dates use the project's canonical format.
- [ ] Sale price is correctly parsed.
- [ ] Lease-rate strings such as `$16/SF/YR` are not treated as sale prices.
- [ ] Listing freshness fields are separated from price.
- [ ] Optional Crexi detail fields remain optional.
- [ ] Missing Cap Rate/NOI/Occupancy does not break normalization.
- [ ] Narrative information is not duplicated.
- [ ] No investment judgment is performed during normalization.
- [ ] Existing LLM consumers use the new schema.
- [ ] Schema version is present.
- [ ] Raw records remain usable for future re-normalization.
- [ ] Unit tests cover sale, lease, missing fields, typing, duplication, and payload boundaries.
- [ ] Existing extension capture behavior still works.
- [ ] No gated/private data extraction was introduced.

---

## Definition of Done

The implementation is complete when the system has a clean separation:

```text
                 ┌─────────────────────────┐
                 │     RAW SCRAPED DATA    │
                 │                         │
                 │ exact scraper output    │
                 │ preserved for audit     │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │       NORMALIZER        │
                 │                         │
                 │ parse / type / map /   │
                 │ deduplicate             │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │      LLM_STRUCTURED     │
                 │                         │
                 │ canonical facts only    │
                 │ inference-oriented      │
                 │ no raw_attributes       │
                 └────────────┬────────────┘
                              │
                              ▼
                 ┌─────────────────────────┐
                 │           LLM           │
                 │                         │
                 │ inference / reasoning   │
                 └─────────────────────────┘
```

The core principle is:

**Raw data is for preservation. `llm_structured` is for reasoning. Do not make the LLM reconcile two copies of the same listing.**
