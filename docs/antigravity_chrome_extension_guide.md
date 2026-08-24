# Build Task for Antigravity: Site Ranker Capture Extension

## How to use this doc
This is a self-contained task spec for an agentic coding session in
Antigravity. Give the agent this whole file as the task brief. It includes
context, scope boundaries, step-by-step build order, and a verification
checklist the agent should run through before declaring done. Treat each
"Step" as a natural checkpoint — the agent should produce working,
testable output at each step before moving to the next, not write
everything in one pass.

---

## Project context

We're building "Site Ranker" — a tool that evaluates industrial real
estate sites using federal infrastructure data (power, water, terrain,
transportation, environmental risk) via an API called Mireye. The full
system has three parts:
1. A website (already being built separately) — input a site, get a
   scored report from a "council" of domain agents, chat about it, compare
   sites.
2. **This task**: a Chrome extension that lets a user capture a site
   address while browsing commercial real estate listing sites, and adds
   it to a shared "cart" that shows up on the website.
3. A chatbot layer (separate, not part of this task).

This extension's job is narrow on purpose: **capture, not evaluate**. For
supported sites (starting with Crexi), it auto-extracts public, on-page
listing facts (address, title, and similarly visible top-line details)
via a one-click injected button, and sends them to our backend. For any
other site, it falls back to manual text-selection capture. Either way it
does not run any evaluation itself, and it never pulls gated/login-only
data (broker contact info, private documents, etc.) — only what's already
visible on the public listing page.

---

## Non-negotiable scope boundaries

Build exactly this, nothing more:
- Manifest V3 Chrome extension
- Auto-extraction via an injected button for explicitly supported sites
  (Crexi first), scoped to public on-page fields only (address, title,
  a few bonus fields like square footage/price if reliably present)
- Selection-based manual capture as a fallback for any unsupported site
  (user highlights text, extension reads the selection)
- A popup with an editable text field, "Add to cart" button, and a short
  list of recently-added items
- A lightweight session-sync mechanism so the extension and website agree
  on the same session ID, with no login/auth system
- Two small backend endpoints to support the above

Do NOT build: a full cart view inside the extension, evaluation logic,
price/contact scraping, support for more than 1-2 listing sites, or any
auth/login flow. If any of these seem necessary to solve a problem, stop
and flag it instead of building around the boundary.

---

## Session model — read this before writing any code

There is no login. The website generates a random `session_id`, stores it
in `localStorage`, and reflects it in its URL as `?session=<id>`. Every
piece of data (cart items, evaluations, chat memory) is tagged with this
ID in the database instead of a user ID.

The extension needs the same `session_id` the website is using, so a
captured item lands in the cart the user will actually see. Build it this
way:

1. **Primary path**: a content script scoped only to our own website's
   domain (not the listing sites) reads `session_id` from that page's
   `localStorage` when the user has the website open, and relays it into
   `chrome.storage.local` via a message to the background script.
2. **Fallback path**: if the extension has never seen a `session_id` yet
   (fresh install, website never opened), the popup shows a "Connect your
   session" button instead of the capture form. Clicking it opens the
   website in a new tab; the extension generates a fresh ID locally and
   passes it via query param (`?session=<id>`) so the website adopts the
   same ID on load rather than generating its own.

Store the resolved ID in `chrome.storage.local` so it survives browser
restarts without the website needing to be open.

---

## Step 1 — Scaffold the extension

Create the extension folder with:
- `manifest.json` (Manifest V3)
- `popup.html`, `popup.js`
- `content.js` (runs on listing sites — selection capture)
- `content-session.js` (runs on our own website domain — session sync)
- `background.js` (service worker — relays messages, holds shared state
  access)

Manifest permissions — keep minimal. Since the website is running on
localhost for now (e.g. `http://localhost:3000` or `http://127.0.0.1:5173`,
whatever the dev server's port is — confirm the exact port before hardcoding),
match on localhost explicitly:

```json
{
  "manifest_version": 3,
  "name": "Site Ranker Capture",
  "version": "0.1",
  "action": { "default_popup": "popup.html" },
  "permissions": ["storage"],
  "host_permissions": [
    "https://www.loopnet.com/*",
    "https://www.crexi.com/*",
    "http://localhost/*",
    "http://127.0.0.1/*"
  ],
  "content_scripts": [
    {
      "matches": ["https://www.loopnet.com/*", "https://www.crexi.com/*"],
      "js": ["content.js"]
    },
    {
      "matches": ["http://localhost/*", "http://127.0.0.1/*"],
      "js": ["content-session.js"]
    }
  ]
}
```

Notes on this:
- `http://localhost/*` and `http://127.0.0.1/*` match any port by default
  in Chrome's host permission syntax, so this covers whatever dev port the
  website ends up on without hardcoding a port number.
- The backend API calls from `popup.js` (Step 4/5) will also hit
  `http://localhost:<backend-port>` — Manifest V3 extensions are allowed
  to fetch localhost URLs without adding them to `host_permissions`
  **only if** using `fetch` from the popup/background context, but to be
  safe and avoid CORS/permission surprises, also add the backend's
  specific `http://localhost:<port>/*` to `host_permissions` once that
  port is known. Ask/check what port the backend runs on rather than
  guessing.
- **When you eventually deploy the website for real**, swap the localhost
  entries above for the real domain (and keep localhost too, so local dev
  still works) — this is the only part of the extension that needs to
  change at deploy time. Flag this as a TODO comment directly in
  `manifest.json` so it's not forgotten.
- Pick 1-2 real listing sites for the demo — do not add more.

Checkpoint: extension loads in `chrome://extensions` (developer mode,
load unpacked) with no manifest errors.

---

## Step 2 — Session sync

`content-session.js`: on page load, read `localStorage.getItem('session_id')`
from the website's own page context, and if present, send it to the
background script via `chrome.runtime.sendMessage`.

`background.js`: listen for that message, store the value in
`chrome.storage.local` under a fixed key (e.g. `siteRankerSessionId`).

Checkpoint: open the website (even a placeholder page that sets
`localStorage.session_id` manually for testing), confirm the extension's
`chrome.storage.local` picks it up. Verify via the extension's service
worker console.

Note: with everything on localhost, CORS is likely to bite you between
the extension's popup/background fetches and the local backend server if
the backend doesn't have permissive CORS headers set for local dev. If
`POST`/`GET` calls to the backend fail silently or with a CORS error in
the console, add `Access-Control-Allow-Origin: *` (or the specific
`chrome-extension://<id>` origin) on the backend for local development —
this is expected friction with localhost + extensions, not a sign
something's architecturally wrong.

---

## Step 3 — Auto-capture button injected per listing (Crexi first)

Scope change from pure selection-capture: for sites we explicitly support
(starting with Crexi), inject a small "Add to Site Ranker" button directly
onto each listing page. Clicking it auto-extracts the address and a few
key details from that page's DOM — no manual highlighting needed. This is
real per-site DOM parsing, so it's inherently more fragile than selection
capture and needs to be built site-by-site, one at a time, starting with
Crexi only.

Keep this scoped to public, on-page, user-visible fields only — address,
listing title, square footage, listing URL, and similar top-line facts
that are the whole point of a public listing page. Do not attempt to pull
data from anything gated (login-required detail panels, contact-broker
forms, etc.).

**3a — Injecting the button**

In `content.js` (scoped via manifest `matches` to Crexi listing detail
page URL patterns, e.g. `https://www.crexi.com/properties/*` — check
Crexi's actual URL structure and confirm before hardcoding), find a stable
anchor point in the page layout (e.g. near the listing title/header) and
inject a button element there via plain DOM manipulation
(`document.createElement`, `insertBefore`/`appendChild`). Style it
minimally inline so it doesn't depend on a stylesheet load order.

Use `MutationObserver` to handle the case where Crexi's page content loads
in dynamically after initial page load (common on modern listing sites) —
don't assume the DOM is fully populated at `content_scripts` injection
time. Wait for the target anchor element to appear before inserting the
button, rather than firing once on page load and giving up.

**3b — Extracting listing data**

Write a small `extractListingData()` function specific to Crexi's current
DOM structure. Since exact selectors will drift as Crexi updates their
site, structure this defensively:
- Try a primary selector (e.g. a specific class or data-attribute Crexi
  uses for the address).
- Fall back to a secondary strategy if the primary fails — e.g. scanning
  page `<h1>`/`<h2>` text near the injected button's anchor, or a broader
  attribute-based search — rather than throwing/breaking silently.
- If extraction fails entirely, still show the button, but on click open
  the popup with an empty/editable field and a note ("Couldn't
  auto-detect — enter manually") rather than blocking the user.

Extract, at minimum: `address`, `listing_title`, and the current page URL
(`source_url`). Add `square_footage` or `price` only if reliably present
site-wide — treat these as bonus fields, not required ones, since MVP only
strictly needs an address for Mireye lookups.

Store the extracted object in `chrome.storage.local` under a temporary key
(e.g. `lastCapture`) on button click, then open the popup (or a small
inline confirmation) pre-filled with this data, still editable — always
let the user correct auto-extracted data before it's saved, since DOM
scraping will occasionally get it wrong.

**3c — Keep the manual fallback**

Retain the original selection-based capture (`window.getSelection()`) as
a fallback path for any listing site that isn't in the supported/auto list
yet. This means `content.js` should support two capture triggers:
1. The injected auto-button (supported sites only, e.g. Crexi)
2. A manual popup-based flow using text selection (any site) — this is
   what covers "later on we'll do it for more websites" without needing
   new code per site in the meantime.

**3d — Adding more sites later**

Structure `extractListingData()` and the button-injection logic so each
supported site is its own small config/module (selectors + anchor point +
URL match pattern), not one big function with if/else branches per
domain. This is what makes "add LoopNet next" a matter of writing one new
config block rather than reworking shared logic.

Checkpoint: on a real Crexi listing page, confirm the button appears
(including on pages where content loads dynamically after initial load),
clicking it correctly pre-fills address + title + URL in the popup, and
edits made before submit are what actually gets saved.

---

## Step 4 — Popup UI and submit flow

`popup.html` / `popup.js`:
- If no `siteRankerSessionId` is stored yet: show the "Connect your
  session" state — a button that opens the website in a new tab with a
  freshly generated ID appended as `?session=<id>`.
- If a session ID exists: show the capture form — text input pre-filled
  from `lastSelection` (editable), "Add to cart" button, status line, and
  a list of the last 3-5 cart items for this session (fetched via `GET
  /cart-items`).
- On submit: `POST /cart-items` with
  `{ session_id, address, source_url, listing_title?, details? }` where
  `source_url` is the active tab's URL, and `listing_title`/`details`
  (square footage, price, etc.) are included when the item came from
  auto-extraction and omitted for manual selection captures. Show
  success/error inline. Clear the input and refresh the recent-items list
  on success.

Checkpoint: full flow works end to end on a real listing page — select
text, open popup, edit if needed, submit, see it appear in the recent
list.

---

## Step 5 — Backend endpoints

These are small additions to the shared backend (assume it already
exists with some framework — ask/check before assuming a stack; if none
exists yet, stub a minimal FastAPI or Express server just for these two
routes so this extension is independently testable):

```
POST /cart-items
  body: {
    session_id: string,
    address: string,
    source_url?: string,
    listing_title?: string,
    details?: object   // e.g. { square_footage, price } — free-form, optional
  }
  returns: { cart_item_id, address, status: "added" }

GET /cart-items?session_id=...
  returns: [ { cart_item_id, address, source_url, listing_title, details, added_at }, ... ]
```

No geocoding or Mireye calls happen here — just store the raw address
string (plus whatever optional metadata came along) tied to the session.
Evaluation happens later, from the website, not at capture time.

---

## Step 6 — Verification pass

Before declaring this done, actually test all of these, not just the
happy path:
- [ ] Fresh install, no session yet → popup shows "connect" state, not a
      broken form
- [ ] After connecting via the website, session ID persists across a
      browser restart
- [ ] Auto-capture button appears on Crexi listing pages, including ones
      where content loads in dynamically after initial page load
- [ ] Auto-extraction correctly pulls address/title/URL on a handful of
      different real Crexi listings, not just one tested page
- [ ] Extraction failure (selector miss) falls back to an editable empty
      field rather than breaking the button entirely
- [ ] Selection-based fallback still works on a non-Crexi page
- [ ] Editing pre-filled data (auto or manual) before submit actually
      saves the edited text, not the original extracted/selected values
- [ ] `GET /cart-items` for a given session returns exactly the items
      added under that session, not other sessions' items
- [ ] Submitting with no data captured doesn't silently fail — shows a
      clear inline error instead

---

## If something in this spec seems wrong

If a step conflicts with how the website's session system actually works,
or the backend already has a different endpoint convention in place,
stop and flag the mismatch rather than guessing — this extension only
works if its session ID and cart-item schema line up exactly with what
the website expects.

Since everything is local right now: confirm the actual dev server ports
for both the website and backend before hardcoding anything, and expect
to revisit `manifest.json`'s `host_permissions` once real domains exist.
