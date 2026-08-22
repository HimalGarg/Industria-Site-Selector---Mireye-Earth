# Crexi DOM Inspection + Auto-Capture Build Guide

## Why this guide exists, and an important caveat

Crexi is a client-rendered React SPA — the real listing content (address,
title, price, sqft) does not exist in the initial HTML response, it's
injected by JavaScript after the page loads. This means:

- I cannot hand you accurate CSS selectors sight-unseen — any selectors
  given without actually opening DevTools on a live page would very likely
  be wrong or already stale.
- A plain `fetch()`/`curl` of a Crexi URL will return an empty shell, not
  the listing data. The extension's content script works fine because it
  runs *inside* the already-rendered page in the browser, but any offline
  inspection tooling needs to render JS first.

So this guide is a **process** for getting real selectors yourself (or
having the coding agent do it), not a pre-filled selector list. Do this
inspection step before writing `extractListingData()` — don't let the
agent guess at selectors either.

---

## Step 1 — Manually inspect a real Crexi listing page

1. Open a real property listing on Crexi in Chrome, e.g. search
   `crexi.com/properties` and click into any individual listing (URL
   pattern looks like `https://www.crexi.com/properties/<id>/<slug>`).
2. Open DevTools (`Cmd+Option+I` / `F12`) → Elements tab.
3. Use the element picker (top-left cursor icon in DevTools) and click
   directly on:
   - The property address text
   - The listing title/headline
   - The price (if for sale) or lease rate (if for lease)
   - The square footage figure
   - The property type/subtype label
4. For each one, note in the Elements panel:
   - The tag and any `class` names
   - Any `data-*` attributes (React apps often have more stable
     `data-testid` or `data-qa` attributes than class names — **prefer
     these over class names if present**, since utility-CSS class names
     like `sc-a1b2c3` or Tailwind-generated classes churn on every
     deploy, while test IDs tend to be intentionally stable)
   - Where it sits in the DOM relative to a stable parent (e.g. "inside a
     `<header>` near the top of the main content area")

Write these down in a small reference doc as you go — this becomes the
input to Step 2.

---

## Step 2 — Prefer resilient selector strategies over exact class names

Once you have real selectors from Step 1, rank your extraction strategy in
this order of preference (most to least stable):

1. **`data-testid` / `data-qa` / other `data-*` attributes**, if present.
   These are the most likely to survive a redesign since they're usually
   added intentionally for internal QA automation.
2. **Semantic structure** — e.g. "the `<h1>` inside the main listing
   header," or "the element right after the element containing the '$'
   sign" — more robust than a specific class name because it relies on
   layout logic that changes less often than utility classes.
3. **Text-pattern matching as a fallback** — scan visible text nodes near
   your anchor point for patterns that look like an address (contains a
   state abbreviation + zip-like digit pattern) or a price (leads with
   `$`), and treat the first match as the value. This is your safety net
   when structural selectors miss entirely.
4. **Exact utility class names** — last resort only, and expect to
   re-verify these periodically since they're the most likely to break.

Write `extractListingData()` to try strategy 1, fall back to 2, fall back
to 3, in that order — not just strategy 1 alone. This is what makes the
extraction survive Crexi's redesigns without needing a rebuild every time.

---

## Step 3 — Handle the SPA rendering timing problem

Because Crexi is client-rendered, the content script's target elements
won't exist yet at `document_start`/`document_end` injection time. Two
things to build:

1. Set `"run_at": "document_idle"` in the manifest's content script config
   (a small improvement over the default, though not sufficient alone).
2. Use a `MutationObserver` on `document.body` that watches for your
   target anchor element (e.g. the container holding the address) to
   appear, then injects the capture button and runs extraction — don't
   assume it's there immediately. Disconnect the observer once the
   element is found, to avoid running indefinitely.

```js
function waitForElement(selectorFn, callback, timeoutMs = 8000) {
  const found = selectorFn();
  if (found) { callback(found); return; }
  const observer = new MutationObserver(() => {
    const el = selectorFn();
    if (el) {
      observer.disconnect();
      callback(el);
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
  setTimeout(() => observer.disconnect(), timeoutMs); // safety cutoff
}
```

`selectorFn` should implement the tiered strategy from Step 2, not a
single hardcoded selector.

---

## Step 4 — Verify against multiple real listings, not just one

Selectors that work on one listing page can fail on another if Crexi uses
slightly different layouts for different property types (e.g. land vs.
office vs. multifamily) or for-sale vs. for-lease listings. Before
considering extraction "done":

- Test against at least 3-4 different real listings, spanning at least
  two different property types.
- Confirm the fallback strategy (Step 2, tier 3) actually kicks in and
  produces a reasonable result on any listing where the primary selector
  strategy fails, rather than returning nothing.

---

## Step 5 — What to do when Crexi changes their DOM (it will happen)

Since you can't lock this down permanently:
- Keep `extractListingData()` isolated in its own module (as already
  specified in the main extension build guide) so fixing Crexi doesn't
  touch the button-injection or popup logic.
- Log a console warning (visible in the content script's DevTools console)
  whenever the primary/secondary selectors fail and the text-pattern
  fallback had to be used — this gives you an early signal that Crexi's
  markup shifted, before users start reporting silently-wrong captures.
- Treat "auto-extraction quietly wrong" as worse than "auto-extraction
  visibly failing" — always show the user the extracted values in an
  editable field before saving (already specified in the main guide) so a
  bad selector produces a visible wrong value the user can fix, not a
  silent bad database entry.

---

## Handoff note for the coding agent

Do Step 1 (manual DevTools inspection on a real, current Crexi listing)
yourself before writing any extraction code. Do not invent selectors from
training knowledge or assumptions about typical React app structure —
Crexi's actual current markup must be observed directly, since it's a
live SPA that can differ from any prior knowledge of the site.
