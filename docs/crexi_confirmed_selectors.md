# Crexi Listing Detail Page — Confirmed Selectors

Extracted directly from a real rendered Crexi listing page
(`crexi.com/lease/properties/699886/...`). These are verified, not
guessed — pulled from actual `outerHTML` after JS rendering. Still worth
spot-checking against a second listing (different property type / for-sale
vs for-lease) before shipping, since Crexi may vary structure slightly by
listing type.

---

## Address

```
header[data-cy="pdpHeader"] h1
```
Contains the full address as plain text, followed by a trailing
`<span>` with the status label. Example raw content:

```html
<h1 class="ctw:text-heading-6 ...">
  1800 2nd Loop Rd, Florence, SC 29501
  <span class="ctw:font-normal ctw:text-text-secondary">For Lease</span>
</h1>
```

**Extraction approach:** grab `h1`'s text content, then strip the text of
the trailing `<span>` (its own text is available separately via
`h1.querySelector('span').textContent` — subtract that from the full
`h1.textContent`, or just take `h1.childNodes[0].textContent.trim()` since
the address is the first text node before the span).

**Fallback source for address:** the page's `<meta name="description">`
tag also contains the full address in a predictable sentence pattern
("...for lease at {address}. Visit Crexi.com..."), and the `<link
rel="canonical">` href's slug is a URL-safe version of the address/title.
Useful as a tier-3 fallback if the h1 selector ever breaks.

---

## Listing title (property/building name)

```
h2.ctw\:text-body.ctw\:m-0.ctw\:line-clamp-1
```
(inside the price section, e.g. `<h2 class="ctw:text-body ctw:m-0
ctw:line-clamp-1">Logan Plaza</h2>`)

A more complete version combining building name + description exists as
the `<h2>` inside `crx-smart-about-property` (id="about-property"), e.g.
"Logan Plaza | Multiple Office/Retail Suites" — prefer this one for a
richer title if present, since it's more descriptive than the short name
alone.

---

## Price / rate

```
[data-cy="auctionDetailsValue"]
```
or more generally, look inside `[data-cy="primary-price"]` — this
container holds the formatted rate (e.g. `$16/SF/YR`).

**Note:** exact `data-cy` value may differ for for-sale vs for-lease vs
auction listings (`auctionDetailsValue` suggests this one was an
auction-context page). Check `[data-cy="primary-price"] div` broadly as a
more robust fallback — the price text is reliably the first meaningful
text node inside that container regardless of the specific data-cy label
used for the value itself.

---

## Days on market / listing freshness

```
[data-cy="date-or-info-label"]
```
Text like "1065 days on market". Bonus field, not required for MVP.

---

## Building details / key facts (sqft, year built, parking, etc.)

```
[data-cy="property-detail-summary"] [data-cy="label"]
[data-cy="property-detail-summary"] [data-cy="value"]
```
These come in matched pairs — each row has one label span and one value
span, in document order. To extract as a dict:

```js
const rows = document.querySelectorAll('[data-cy="property-detail-summary"] > div > div');
// or more directly:
const labels = document.querySelectorAll('[data-cy="property-detail-summary"] [data-cy="label"]');
const values = document.querySelectorAll('[data-cy="property-detail-summary"] [data-cy="value"]');
// zip labels[i] with values[i]
```
This is the richest structured data on the page — total building sqft,
year built, parking spaces, property type/subtype, tenancy, all as clean
label/value pairs with `data-cy` markers. Prioritize this section for the
"bonus fields" (sqft, year built) mentioned in the extension guide.

---

## Description (building description + highlights)

```
crx-smart-about-property [data-cy] crx-safe-html-with-abs-links
```
More reliably: `crx-smart-about-property` has two
`crx-safe-html-with-abs-links` blocks in sequence — first is the building
description (prose), second is the highlights (bullet list). Grab
`.textContent` from each, or preserve the `<p>`/`<li>` structure if you
want formatted output.

---

## Images

```
img[data-cy="image"]
```
Multiple matches (carousel slides). Each has a `src` and often a
`srcset` with multiple resolutions — take the `src` of the first match
(the hero/cover image) for a single representative image, or collect all
matches' `src` values for a full gallery.

---

## Broker / listing contact

```
[data-cy="broker-name-link"]        → name (text) + href (profile link)
[data-cy="avatar"] img              → photo src
```
**Phone and email are NOT statically present** — they're behind
`[data-cy="phoneButton"]` / `[data-cy="emailButton"]` which reveal the
actual number/address only on click (likely a lead-gen gate). Do not
attempt to scrape these — respect the click-to-reveal gate. This is a
firm boundary: broker contact info stays behind Crexi's own gate, not
something to extract.

---

## Property type / subtype (also in the key-value table above, but a
## quick top-level version exists too)

Covered by the `property-detail-summary` label/value pairs above
("Property Type", "Sub Type", "Tenancy").

---

## Confirmed real class-name examples for future tier-2/3 fallback logic

If `data-cy` selectors ever fail, these `ctw:` utility classes were
observed on this page and can serve as a secondary structural signal
(though less stable than `data-cy`):

- Address h1: `ctw:text-heading-6 ctw:@720:text-heading-5 ctw:m-0
  ctw:font-branding ctw:line-clamp-2`
- Building name h2: `ctw:text-body ctw:m-0 ctw:line-clamp-1`

---

## Recommended field extraction priority for `extractListingData()`

1. **Address** — `header[data-cy="pdpHeader"] h1` (strip trailing status
   span)
2. **Title** — `crx-smart-about-property h2`, fallback to the short
   building-name `h2` in the price section
3. **Price** — `[data-cy="primary-price"]` container text
4. **Source URL** — `document.location.href` or the `<link
   rel="canonical">` href (canonical is cleaner, no tracking params)
5. **Bonus fields** (only if time permits) — sqft/year-built from
   `property-detail-summary` label/value pairs, first image from
   `img[data-cy="image"]`

Do not attempt to extract broker phone/email — respect the click-gate.

---

## Still needed before shipping

- Confirm these same selectors hold on a **for-sale** listing (this
  sample was for-lease) — the `pdpHeader`/`h1` structure is likely shared
  across the universal PDP template (`crx-universal-property-detail`
  wraps both), but verify on one real for-sale page before assuming.
- Confirm on a **different property type** (e.g. industrial or land vs.
  this office/retail example) since building-detail fields may vary.
