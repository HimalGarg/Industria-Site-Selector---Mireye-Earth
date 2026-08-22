# Chrome Extension Multi-Site Scraping — Further Build Guide

## 1. Objective

Extend the existing Chrome extension from supporting one website to supporting multiple real-estate websites, starting with:

- Crexi — existing implementation
- LoopNet — new integration
- Zillow — new integration
- Future websites — architecture should make adding another site straightforward

The extension should **not assume that every website exposes the same fields or structures its data the same way**.

The architecture should therefore separate:

1. Website-specific scraping
2. Raw scraped data
3. Normalized/common data
4. LLM-ready data
5. Website-specific metadata
6. Extension UI/state management

---

# 2. Core Architectural Principle

Do **not** create one rigid universal schema that forces every website into the same fields.

Instead, use a **two-layer data model**:

```text
Website
   ↓
Website Adapter / Scraper
   ↓
Raw Website Data
   ↓
Normalization Layer
   ↓
Common Fields + Website-Specific Fields
   ↓
LLM Format
```

The raw data must always be preserved.

The normalized/LLM representation should be derived from the raw representation rather than replacing it.

---

# 3. Recommended Data Model

Every scraped property/listing should have a structure conceptually similar to:

```json
{
  "source": {
    "website": "crexi",
    "url": "...",
    "listing_id": "...",
    "scraped_at": "..."
  },

  "common": {
    "title": "...",
    "property_type": "...",
    "address": "...",
    "city": "...",
    "state": "...",
    "zip_code": "...",
    "price": null,
    "price_text": "...",
    "status": "...",
    "description": "..."
  },

  "website_specific": {},

  "raw": {},

  "llm": {}
}
```

The exact implementation can differ, but the conceptual separation should remain.

---

# 4. Raw Data Must Be Preserved

The scraper should capture the data as close as possible to how the website exposes it.

For example:

```json
{
  "raw": {
    "listing_title": "...",
    "asking_price": "...",
    "property_details": {},
    "agent_information": {},
    "amenities": [],
    "financial_information": {},
    "page_metadata": {},
    "dom_data": {},
    "structured_data": {}
  }
}
```

Do **not** immediately discard information simply because it does not fit the current normalized schema.

This is important because:

- Different websites expose different information.
- A field that does not exist on Crexi may exist on LoopNet.
- Zillow may expose information that is useful later.
- The LLM may eventually need fields that are not currently part of the schema.
- Website-specific data can be used to improve future normalization.

---

# 5. Common vs Website-Specific Fields

## Common Fields

Only put a field in `common` when it is genuinely shared across websites.

Examples:

```text
title
address
city
state
zip_code
property_type
price
description
listing_url
listing_id
status
images
```

## Website-Specific Fields

Anything that is unique or inconsistently represented should remain under:

```text
website_specific
```

Example:

```json
{
  "website_specific": {
    "crexi": {
      "cap_rate": "...",
      "noi": "...",
      "broker": "..."
    }
  }
}
```

or:

```json
{
  "website_specific": {
    "zillow": {
      "zestimate": "...",
      "days_on_zillow": "...",
      "hoa": "...",
      "monthly_payment": "..."
    }
  }
}
```

The exact naming convention should be consistent across the project.

---

# 6. Website Adapter Architecture

Create a separate adapter for every supported website.

Recommended structure:

```text
src/
├── scrapers/
│   ├── base/
│   │   ├── scraper.js
│   │   └── types.js
│   │
│   ├── crexi/
│   │   ├── scraper.js
│   │   ├── selectors.js
│   │   ├── parser.js
│   │   └── mapper.js
│   │
│   ├── loopnet/
│   │   ├── scraper.js
│   │   ├── selectors.js
│   │   ├── parser.js
│   │   └── mapper.js
│   │
│   └── zillow/
│       ├── scraper.js
│       ├── selectors.js
│       ├── parser.js
│       └── mapper.js
│
├── normalization/
│   ├── normalize.js
│   └── common-fields.js
│
├── llm/
│   └── formatter.js
│
└── registry/
    └── website-registry.js
```

The exact directory structure may be adapted to the existing codebase.

---

# 7. Website Detection

The extension should detect the current website and select the appropriate adapter.

Conceptually:

```javascript
const adapter = websiteRegistry.getAdapter(window.location.hostname);

if (!adapter) {
  // Unsupported website
  return;
}

const result = await adapter.scrape();
```

Avoid large blocks such as:

```javascript
if (hostname.includes("crexi")) {
   ...
} else if (hostname.includes("loopnet")) {
   ...
} else if (hostname.includes("zillow")) {
   ...
}
```

inside the main scraper.

Website-specific logic belongs inside the adapter.

---

# 8. Website Registry

Create a central registry:

```javascript
const websiteRegistry = {
  crexi: CrexiScraper,
  loopnet: LoopNetScraper,
  zillow: ZillowScraper
};
```

The registry should also contain hostname matching.

Example:

```javascript
{
  name: "crexi",
  hostnames: ["crexi.com"],
  scraper: CrexiScraper
}
```

This makes adding another website straightforward.

---

# 9. Base Scraper Interface

All website adapters should expose the same high-level interface.

For example:

```javascript
class BaseScraper {
  canHandle() {}
  scrape() {}
  extractRaw() {}
  normalize() {}
  formatForLLM() {}
}
```

Not every website needs identical internal implementation.

Only the external contract should be consistent.

---

# 10. Scraping Strategy

Use a layered extraction strategy.

Priority should generally be:

```text
1. Structured data / JSON
2. Embedded page state
3. Stable DOM selectors
4. Visible text
5. Fallback heuristics
```

Do not depend exclusively on CSS selectors when structured data is available.

Websites frequently change their frontend classes.

---

# 11. Selector Management

Selectors must remain website-specific.

Do not create one universal selector file.

Example:

```text
crexi/selectors.js
loopnet/selectors.js
zillow/selectors.js
```

Selectors should be organized by field:

```javascript
export const selectors = {
  title: [...],
  price: [...],
  address: [...],
  description: [...],
  propertyType: [...]
};
```

Use multiple fallback selectors where appropriate.

---

# 12. Selector Documentation

For every website, document:

- Selector
- What it extracts
- Source type
- Reliability
- Fallback
- Example value
- Last verified date

Example:

```text
Field: price
Primary selector: ...
Fallback selector: ...
Source: DOM
Reliability: medium
Example: "$2,500,000"
Last verified: 2026-08-21
```

The existing Crexi selector documentation should be retained and updated rather than discarded.

Use the existing:

- `antigravity_chrome_extension_guide.md`
- `crexi_confirmed_selectors.md`
- `crexi_confirmed_selectors_v2.md`
- `crexi_dom_inspection_guide.md`

as reference material for the new integrations.

---

# 13. LoopNet Integration

Create a dedicated LoopNet adapter.

The agent should first inspect LoopNet's current DOM and page structure before writing selectors.

Do not assume that Crexi selectors or extraction logic will work on LoopNet.

The LoopNet implementation should identify:

- Listing ID
- Listing URL
- Property title
- Address
- Property type
- Asking price
- Lease information
- Property size
- Lot size
- Building information
- Description
- Broker/contact information
- Images
- Financial information
- Any additional listing-specific fields

Anything that is not common should remain website-specific.

---

# 14. Zillow Integration

Create a dedicated Zillow adapter.

The agent should inspect Zillow's current page structure before implementing extraction.

Potential fields include:

- Property ID
- Listing URL
- Address
- Price
- Zestimate
- Property type
- Bedrooms
- Bathrooms
- Square footage
- Lot size
- Year built
- HOA
- Property tax
- Description
- Listing status
- Days on Zillow
- Agent information
- Images
- Additional Zillow-specific information

Do not assume every Zillow listing contains every field.

Missing values should be represented consistently as `null`, an empty array, or another agreed convention.

---

# 15. Data Quality

Each extracted field should ideally carry metadata.

Example:

```json
{
  "price": {
    "value": 2500000,
    "raw": "$2.5M",
    "source": "dom",
    "confidence": 0.95
  }
}
```

If this level of metadata is too invasive for the current implementation, at minimum preserve the raw value somewhere.

Do not silently transform values without retaining the original representation.

---

# 16. Raw vs Normalized vs LLM

Maintain three distinct representations.

## Raw

Closest representation to the website.

```text
raw
```

## Normalized

Common fields mapped into predictable names.

```text
common
website_specific
```

## LLM

A compact representation specifically optimized for sending to the LLM.

```text
llm
```

The LLM format should not be the source of truth.

The raw data should remain the source of truth.

---

# 17. LLM Formatter

Create a dedicated formatter:

```javascript
formatForLLM(normalizedListing)
```

The formatter should:

- Include useful common fields.
- Include relevant website-specific fields.
- Avoid unnecessary DOM noise.
- Preserve important raw values where normalization could lose meaning.
- Handle missing fields.
- Remain deterministic.

Example:

```json
{
  "property": {
    "address": "...",
    "property_type": "...",
    "price": "...",
    "size": "..."
  },
  "financials": {},
  "website_specific": {}
}
```

Do not build the LLM payload directly inside the scraper.

---

# 18. Error Handling

A single missing field must never cause the entire scraper to fail.

Bad:

```javascript
const price = document.querySelector(selector).textContent;
```

Better:

```javascript
const element = document.querySelector(selector);
const price = element ? element.textContent.trim() : null;
```

Each field should fail independently.

The scraper should return partial data whenever possible.

---

# 19. Scraping Diagnostics

Add diagnostic information to every scrape.

Example:

```json
{
  "meta": {
    "website": "loopnet",
    "success": true,
    "fields_found": 18,
    "fields_missing": 4,
    "scraped_at": "...",
    "parser_version": "1.0.0"
  }
}
```

This makes debugging website changes much easier.

---

# 20. Logging

Use structured logs.

Example:

```text
[SCRAPER]
Website: Zillow
Field: Zestimate
Status: FOUND
Source: embedded JSON
```

and:

```text
[SCRAPER]
Website: Zillow
Field: HOA
Status: NOT_FOUND
```

Avoid excessive console noise in production.

Provide a debug mode for development.

---

# 21. Website Capability Matrix

Create a capability matrix.

Example:

| Field | Crexi | LoopNet | Zillow |
|---|---|---|---|
| Title | ✓ | ✓ | ✓ |
| Address | ✓ | ✓ | ✓ |
| Price | ✓ | ✓ | ✓ |
| Cap Rate | ✓ | ? | — |
| Zestimate | — | — | ✓ |
| HOA | — | ? | ✓ |
| Broker | ✓ | ✓ | ✓ |

This should be maintained as integrations evolve.

---

# 22. Testing

Each website should have its own test fixtures.

Example:

```text
tests/
├── crexi/
├── loopnet/
└── zillow/
```

Tests should verify:

- Website detection
- Listing ID extraction
- URL extraction
- Common fields
- Website-specific fields
- Missing-field behavior
- Raw data preservation
- Normalization
- LLM formatting

---

# 23. DOM Fixture Testing

Whenever possible, save representative HTML or extracted JSON fixtures.

Then run parsers against fixtures rather than requiring a live website for every test.

Example:

```text
fixtures/
├── crexi_listing.html
├── loopnet_listing.html
└── zillow_listing.html
```

This allows selector changes to be detected quickly.

---

# 24. Do Not Over-Normalize

Avoid this:

```json
{
  "price": 2500000,
  "size": 5000
}
```

if the website actually provides:

```text
"$2.5M"
"5,000 SF"
"From $2.5M"
"$500/SF"
```

Store both normalized and raw representations when the distinction matters.

For example:

```json
{
  "price": 2500000,
  "price_text": "$2.5M"
}
```

---

# 25. Images

Preserve image URLs separately from the LLM payload where appropriate.

Example:

```json
{
  "images": [
    {
      "url": "...",
      "source": "listing"
    }
  ]
}
```

Do not allow image extraction failures to break the listing scrape.

---

# 26. Pagination / Multiple Listings

The architecture should support both:

```text
Single listing page
```

and:

```text
Search/results page
```

without duplicating the entire scraper.

Consider separating:

```text
Listing parser
Search-result parser
```

for each website.

---

# 27. Future Website Integration

Adding a new website should require approximately:

```text
1. Create website adapter
2. Add hostname
3. Inspect DOM / structured data
4. Define selectors
5. Implement raw extraction
6. Implement normalization mapping
7. Define website-specific fields
8. Add LLM formatter mapping
9. Add fixtures
10. Add tests
11. Add capability matrix entry
```

It should **not** require modifying unrelated website scrapers.

---

# 28. Recommended Development Order

## Phase 1 — Refactor Existing Crexi

Before adding LoopNet/Zillow:

- Extract Crexi logic into an adapter.
- Separate raw extraction from normalization.
- Separate LLM formatting.
- Add website registry.
- Preserve current behavior.

Do not break the existing working scraper.

## Phase 2 — LoopNet

- Inspect LoopNet.
- Build raw extraction.
- Build normalization.
- Add website-specific fields.
- Add tests.
- Verify against real listings.

## Phase 3 — Zillow

- Inspect Zillow.
- Build raw extraction.
- Build normalization.
- Add website-specific fields.
- Add tests.
- Verify against real listings.

## Phase 4 — Hardening

- Error handling
- Logging
- Diagnostics
- Selector fallbacks
- Fixtures
- Versioning
- Capability matrix
- Performance improvements

---

# 29. Important Rule for the Agent

**Do not redesign the entire extension unnecessarily.**

First inspect the existing codebase and determine:

- Current scraper architecture
- Current message passing
- Current storage
- Current popup/UI
- Current LLM payload
- Current content-script architecture
- Current background/service-worker architecture

Then make the smallest architectural changes required to introduce the adapter system.

Preserve working behavior.

---

# 30. Definition of Done

The implementation is complete when:

- [ ] Existing Crexi functionality still works.
- [ ] Website detection automatically identifies supported websites.
- [ ] Crexi has its own adapter.
- [ ] LoopNet has its own adapter.
- [ ] Zillow has its own adapter.
- [ ] Raw scraped data is preserved.
- [ ] Common fields are normalized.
- [ ] Website-specific fields are preserved.
- [ ] LLM data is generated separately.
- [ ] Missing fields do not crash scraping.
- [ ] Selector fallbacks exist where necessary.
- [ ] Debug logging exists.
- [ ] Each website has test fixtures.
- [ ] Each website has parser tests.
- [ ] Capability matrix is documented.
- [ ] Adding another website does not require rewriting existing adapters.
- [ ] Existing extension UI/message flow remains functional.
- [ ] No information is discarded merely because it does not fit the common schema.

# 31. Final Design Principle

The extension should be designed around:

```text
SCRAPE EVERYTHING RELEVANT
        ↓
PRESERVE RAW DATA
        ↓
NORMALIZE WHAT IS COMMON
        ↓
PRESERVE WHAT IS UNIQUE
        ↓
GENERATE LLM-SPECIFIC OUTPUT
```

The **raw representation is the source of truth**.

The normalized schema is an interoperability layer.

The LLM representation is a consumption layer.

This structure allows Crexi, LoopNet, Zillow, and future real-estate websites to coexist without forcing every website into the same rigid data model.