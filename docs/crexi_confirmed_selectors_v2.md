# Crexi Listing Detail Page — Confirmed Selectors (v2)

v2 changes from v1: confirmed selectors hold on **for-sale** listings (not
just for-lease), added the richer sale-specific detail fields observed
(Cap Rate, NOI, Occupancy, Year Built, etc.), added guidance on
sale-vs-lease price formatting, and added prioritized next steps now that
core extraction is verified working in the live extension.

---

## Status: core extraction confirmed working

The injected button and `extractListingData()` logic have been verified
against a real for-sale listing (`3578 Brodhead Rd, Monaca, PA 15061`) in
addition to the earlier for-lease example. Both listing types share the
same underlying PDP template structure — the selectors below are safe to
treat as stable across sale/lease, based on two confirmed real examples.

Still not tested: a for-sale/for-lease listing of a different property
type (e.g. industrial, land, multifamily) — building-detail fields likely
vary by type even if the template shell doesn't.

---

## Address

```
header[data-cy="pdpHeader"] h1
```
Unchanged from v1. Confirmed working on for-sale example: extracted
"3578 Brodhead Rd, Monaca, PA 15061" correctly (strip trailing status
span, same as before).

---

## Listing title

```
h2.ctw\:text-body.ctw\:m-0.ctw\:line-clamp-1
```
or the richer version inside `crx-smart-about-property`. Unchanged from
v1.

---

## Price — IMPORTANT: format differs by listing type

**For-lease** example: `$16/SF/YR` (rate per square foot per year)
**For-sale** example: `$2,300,000` (flat total price)

Same selector (`[data-cy="primary-price"]` container) works for both, but
**do not assume a numeric $/sqft/yr shape in your data model** — store
price as a raw formatted string (`price_display: string`) rather than
trying to parse it into a structured number at capture time. If you need
a normalized numeric price later (e.g. for sorting/filtering in
comparison view), parse it downstream in your backend with logic that
branches on whether the string matches a rate pattern (`/SF/YR`, `/SF/MO`)
vs. a flat price pattern (leading `$`, no rate suffix) — don't try to
guess this in the extension's extraction code, keep the extension dumb
and let the backend own interpretation.

---

## Sale-specific detail fields (new in v2)

The `property-detail-summary` label/value pairs (same selector pattern as
v1: `[data-cy="label"]` / `[data-cy="value"]`) include richer fields on
for-sale listings than were visible on the for-lease example:

- **Property Type** / **Sub Type** (shared with lease)
- **Square Footage** / **Net Rentable (SqFt)**
- **Cap Rate** (e.g. "8.72%") — sale-specific, high-value for investment
  evaluation
- **NOI** (Net Operating Income, e.g. "$200,526") — sale-specific
- **Occupancy** (e.g. "69%") — sale-specific, directly useful signal
- **Tenancy** (e.g. "Multi")
- **Lease Type** (e.g. "Modified")
- **Rent Bumps** (Yes/No)
- **Broker Co-Op** (Yes/No)
- **Year Built**
- **Buildings** / **Stories**
- **Parking Spaces** (e.g. "4 per 1,000 sq ft")
- **Investment Type** (e.g. "Value Add") — sale-specific, useful category
  for filtering/comparison later

Same extraction logic as v1 (zip labels with values in document order) —
no new selector needed, just a wider expected field set. Since these
fields are conditionally present depending on listing type, your
extraction function should build a flexible key-value object from
whatever pairs are actually present, not assume a fixed schema with
required Cap Rate/NOI/Occupancy fields (a for-lease listing won't have
them).

**Recommendation:** add Cap Rate, NOI, Occupancy, and Year Built to the
"bonus fields" tier from v1 — these are exactly the kind of investment
signal that pairs well with your Mireye council's infrastructure scoring,
and they're already sitting in a clean structured table on the page.

---

## Investment highlights (new field, sale listings)

Sale listings include a prose bullet-list section ("Investment
highlights") with narrative selling points — value-add potential, tenant
base quality, traffic counts, etc. This maps to roughly the same DOM
region/pattern as the "Building highlights" bullet list already covered
in v1 under `crx-smart-about-property`'s second
`crx-safe-html-with-abs-links` block. Treat as the same field, just
labeled differently depending on listing type — no separate selector
needed.

---

## Broker contact — unchanged from v1

Still gated behind click-to-reveal (`View phone number` / `View email`
buttons). Confirmed same pattern on this for-sale listing — two brokers
shown (Josh Cordray, Michael Moreno), same gated structure. **Do not
extract past the gate** — this boundary holds regardless of listing type.

---

## Extension button placement — feedback from live test

Current placement (top-left, floating, disconnected from listing content)
works functionally but doesn't visually associate with the listing it
applies to. Recommend repositioning the injected button nearer the
address/price block (inside or adjacent to `header[data-cy="pdpHeader"]`)
so it reads as "capture this listing" rather than a generic page overlay.
Not a blocker — cosmetic polish, do after functional correctness is fully
confirmed on more listing types.

---

## Recommended field extraction priority (v2, updated)

1. **Address** — `header[data-cy="pdpHeader"] h1` (strip trailing status
   span)
2. **Title** — `crx-smart-about-property h2`, fallback to short
   building-name `h2`
3. **Price** — `[data-cy="primary-price"]` container text, stored as raw
   string, not parsed
4. **Source URL** — canonical link href
5. **Bonus fields** — from `property-detail-summary` label/value pairs,
   captured as a flexible key-value object (not a fixed schema):
   square footage, year built, and, when present (sale listings): Cap
   Rate, NOI, Occupancy, Investment Type
6. **First image** — `img[data-cy="image"]` first match

Do not extract broker phone/email — respect the click-gate, confirmed
holding across both listing types.

---

## Next steps, prioritized (as of v2)

1. **Confirm on one more property type** (industrial, land, or
   multifamily — something structurally different from
   office/retail) before considering extraction "done" across the board.
2. **Bulk capture from search results pages** — now genuinely ready to
   build. You have confirmed selectors for both the search-grid cards
   (`data-cy="propertyTile"`, `cui-card-cover-link`, from the earlier
   Instant Data Scraper export) and single-listing detail extraction
   (this doc). This is the highest-leverage next feature since the hard
   selector research for both is done.
3. **Backend price-parsing logic** — implement the sale-vs-lease price
   format branching described above, in the backend, not the extension.
4. **Button placement polish** — reposition near the listing header once
   functional coverage is broader.
