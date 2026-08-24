# Build Task: Frontend — Site Detail Page, Chat, Memory & Comparison

## Scope of this task, explicitly

This is a **frontend-only** task. All backend endpoints referenced below
already exist and are tested (`backend/chat/`, `backend/evaluate/
compare_router.py`, per `build_context.md`). Do not modify backend code
in this task — if something doesn't work as described, that's a bug to
flag, not a reason to change the API contract.

Build:
1. Convert the current slide-over evaluation drawer into a full page
   (its own route), since a listing's full report + chat + memory is too
   much content for a drawer.
2. Add a chat panel to that page, wired to `POST /chat` and `GET /chat`.
3. Add a memory/notes panel to that page, wired to `GET /listing-memory`.
4. Add a new "Compare" page: a site-picker (multi-select from the cart)
   that triggers `POST /compare-sites` and renders the result.

Do NOT build: any new backend logic, session-context UI (there's no
endpoint consumer for `session-context` specified here — skip it this
task, it can be a small addition later), saved/named comparisons.

---

## Context you need

- Current state: `frontend/src/App.tsx` has a Bento-grid cart view and a
  slide-over drawer that calls `/evaluate-site` and shows only the 5
  agent cards. This task changes that drawer into a routed page and adds
  the missing panels — it does not change the Bento-grid cart view
  itself.
- Design system to maintain: **Obsidian Intelligence** — `#0B0F17`
  background, `#151C28` glass surfaces, `#4EDEA3` electric emerald
  accent. Match this on all new UI, don't introduce a different palette.
- You'll need client-side routing if it isn't already present (check
  `App.tsx` for existing router setup before adding a new dependency).

---

## Step 1 — Add routing, convert drawer to a page

Route structure:
```
/                          → existing Bento-grid cart view
/site/:cartItemId          → NEW full-page site detail (was the drawer)
/compare                   → NEW comparison page
```

Move the current drawer's evaluation-fetching logic
(`POST /evaluate-site`, `GET /evaluate-site/{id}` polling) into the new
`/site/:cartItemId` page component. Keep the same 4s polling pattern
already in use elsewhere in the app for consistency.

Clicking a card in the Bento grid should navigate to `/site/:cartItemId`
instead of opening the drawer. Remove the drawer component once this is
working — don't leave dead code.

---

## Step 2 — Page layout for `/site/:cartItemId`

Three-region layout (per the original Stitch design intent — center
report, side panels):

```
┌─────────────────────────────────────────────────┐
│  Header: address, listing title, source badge,   │
│  link to original listing, overall score          │
├───────────────────────┬───────────────────────────┤
│                       │  Right rail (stacked):     │
│  CENTER:              │  - Listing facts (llm_     │
│  5 Agent Council       │    structured, dual toggle │
│  cards (existing        │    already built — reuse) │
│  behavior, keep as-is)  │  - Memory/Notes panel      │
│                       │    (NEW, Step 4)            │
│  Below agents:         │  - Chat panel (NEW, Step 3)│
│  Conflicts/flags        │                            │
│  section (if any)       │                            │
└───────────────────────┴───────────────────────────┘
```

On mobile/narrow viewports, stack top-to-bottom: header → agent cards →
chat → memory → listing facts. Chat should be reachable without
excessive scrolling on mobile — consider making it a sticky bottom
sheet on small screens if time allows, otherwise plain stacking is fine
for now.

---

## Step 3 — Chat panel

On page load for `/site/:cartItemId`:
1. Call `GET /chat?cart_item_id={id}` to load existing message history.
   Render as a scrollable thread — user messages right-aligned or
   visually distinct from assistant messages, standard chat UI pattern.
2. Render each assistant message's citations below its text — small,
   muted, monospace, tagged by source (`mireye` / `listing` / `memory`)
   with a tiny colored dot or label per source type, consistent with the
   distinction already established in the agent citation displays.

Input:
- Text input + send button, pinned to the bottom of the panel.
- On send: `POST /chat` with `{ cart_item_id, session_id, message }`.
  Get `session_id` the same way the rest of the app already does (check
  `api.ts` / existing session handling — don't invent a new session
  mechanism).
- This endpoint is synchronous (not polled) — show a lightweight loading
  state on the input/send button while waiting, then append the
  response to the thread.
- If the site has no evaluation yet (chat backend handles this case per
  the earlier build guide, returning an explanatory message rather than
  an answer), just render that response normally — no special frontend
  handling needed, the backend already produces user-facing text for
  this case.

Include 2-3 starter suggestion chips above the input on first load (no
messages yet) — e.g. "What's the flood risk here?", "How's the power
infrastructure?" — clicking one fills the input, doesn't auto-send
(let the user confirm/edit first).

---

## Step 4 — Memory/Notes panel

Call `GET /listing-memory?cart_item_id={id}` on page load. Render as a
simple bullet list — small text, muted background box, clearly visually
secondary to the chat panel (this is supporting context, not the main
interaction surface). Each fact is one line/bullet, no interaction
needed (read-only display).

If empty, show a plain one-line placeholder ("Notes from your
conversation will appear here") rather than an empty box.

**Refresh behavior:** after a chat response comes back (Step 3), refetch
`GET /listing-memory` in case that turn produced a new memory entry —
don't require a full page reload for the notes panel to update.

---

## Step 5 — Comparison page (`/compare`)

Two-part page:

**Part A — Site picker (shown first):**
- Reuse the cart's listing data (fetch `GET /cart-items?session_id=`)
  and render as a checkbox-selectable list/grid — simpler visual
  treatment than the full Bento cards, this is a picker, not a browse
  view.
- Enforce 2-4 selection (per the backend's enforced range) — disable
  the "Compare" button outside that range, with a small inline hint
  ("Select 2-4 sites to compare").
- "Compare" button triggers `POST /compare-sites` with the selected
  `cart_item_ids`.

**Part B — Results (shown after comparing, same page, replaces or
appears below the picker — your call on whether to keep the picker
visible for easy re-selection):**
- Column-per-site layout: each column header shows address + score.
- Row-per-agent grid below: Energy, Water, Surface, Transport, Risk —
  each cell shows that site's score for that category, so a user can
  scan a row left-to-right and compare directly. Use the flattened
  `agent_scores` object from the response directly — no client-side
  recomputation needed.
- If any selected site has `missing_evaluation: true`, show that column
  with a clear "Not yet evaluated" state instead of scores, and exclude
  it from visual comparison emphasis (e.g. slightly muted) — the
  backend already excludes it from the narrative, so the frontend
  should visually reflect the same exclusion.
- Below the grid: render `comparison_narrative` (short paragraph) and
  `trade_offs` (as a bullet list) — this is the synthesized takeaway,
  should have visual prominence, not buried below the grid.

---

## Step 6 — Testing

- Navigate from the cart grid into a site's full page — confirm the
  agent cards still work exactly as before (this is a refactor, not a
  behavior change for that part).
- Send a chat message on a site with no evaluation yet — confirm the
  graceful "run an evaluation first" response renders correctly, not as
  an error state.
- Send a chat message that should trigger a memory entry (e.g. state a
  clear preference) — confirm the memory panel updates without a full
  page reload.
- Load a site's page a second time after chatting — confirm
  `GET /chat` correctly restores the full prior conversation.
- Run a comparison with exactly 2 sites, then with 4 — confirm both
  work and the UI doesn't break at either boundary.
- Run a comparison including one un-evaluated site — confirm it's
  visually flagged, not silently dropped or shown as an error.
- Check mobile/narrow viewport for both new pages — confirm nothing is
  unreachable or overlapping.

---

## Handoff checklist

- [ ] Routing added: `/site/:cartItemId`, `/compare`, existing `/`
      unchanged
- [ ] Slide-over drawer removed, replaced by full-page site detail,
      same evaluation-fetching behavior preserved
- [ ] Chat panel: history load, send, citations rendered with source
      tags, starter chips, synchronous send with loading state
- [ ] Memory panel: loads and refreshes after each chat turn, visually
      secondary to chat
- [ ] Comparison page: site picker enforces 2-4 range, results render
      as column/row grid using `agent_scores` directly, narrative +
      trade-offs shown prominently, missing evaluations visually flagged
- [ ] Design system consistency maintained (Obsidian Intelligence
      palette) across all new UI
- [ ] All Step 6 test scenarios pass, including mobile check
