# Build Task: Site Chat, Router, and Memory Layer

## Scope of this task, explicitly

Build: a chat endpoint that lets the user ask follow-up questions about a
specific cart item, a router that decides which (if any) additional
Mireye fields are needed to answer, reuse of the existing `mireye_cache`
to avoid duplicate calls, a per-listing memory table that accumulates
facts from the conversation, and a session-level "what the user is
looking for" note that updates as the user chats across sites.

Do NOT build in this task: comparison view, frontend chat UI beyond a
minimal test harness, any new Mireye field categories beyond the
58-field inventory already defined in `backend/evaluate/config.py`. This
task is backend-first — a later task wires the frontend's chat panel
(already scaffolded per the Stitch design) to these endpoints.

---

## Context you need

- `backend/evaluate/config.py` already has the 58-field Mireye inventory
  and `AGENT_FIELD_MAP`. This task reuses that inventory — do not
  redefine it, import it.
- `backend/evaluate/mireye_fetcher.py` already wraps Mireye calls with
  the additive `mireye_cache` table. Reuse this fetcher directly for any
  new field lookups triggered by chat — do not write a second Mireye
  client.
- `evaluations` table already stores the full 5-agent report per
  cart_item_id. Chat should treat the most recent evaluation for a given
  cart item as primary context — the user is almost always asking about
  a site they've already gotten a report on.
- `cart_items.llm_structured` has the listing's own self-reported data.
  Same grounding discipline as the evaluation pipeline applies here:
  every chat answer must distinguish Mireye-derived facts from
  listing-stated facts, and must not state anything not traceable to a
  citation.

---

## Step 1 — New tables

```sql
CREATE TABLE IF NOT EXISTS listing_memory (
  memory_id TEXT PRIMARY KEY,       -- UUID
  cart_item_id TEXT NOT NULL,       -- FK to cart_items
  session_id TEXT NOT NULL,
  fact TEXT NOT NULL,               -- one atomic, short fact
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session_context (
  session_id TEXT PRIMARY KEY,
  summary TEXT NOT NULL,            -- one evolving paragraph, re-summarized not appended
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
  message_id TEXT PRIMARY KEY,      -- UUID
  cart_item_id TEXT NOT NULL,       -- FK to cart_items
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,               -- "user" | "assistant"
  content TEXT NOT NULL,
  citations TEXT,                   -- JSON array, same shape as agent citations, null for user messages
  created_at TEXT NOT NULL
);
```

`listing_memory` is append-only, one row per atomic fact — do not
overwrite or merge rows. `session_context` is a single row per session,
overwritten in place each time it's re-summarized (not appended to —
this is a snapshot, not a log). `chat_messages` is your conversation
history, one row per turn, needed both for display and for feeding
context back into subsequent turns.

---

## Step 2 — `POST /chat` endpoint

```
POST /chat
  body: { cart_item_id: string, session_id: string, message: string }
  returns: { message_id, content, citations, status: "done" }
```

Keep this synchronous (not async-job like `/evaluate-site`) — chat
responses should feel conversational, and most turns will hit cache
rather than triggering new Mireye calls, so latency should be
low enough not to need polling. If a turn does require several new
Mireye fields and gets slow, that's a signal to look at Step 3's routing
logic, not to make this endpoint async.

Handler logic, in order:
1. Load the most recent `evaluations` row for `cart_item_id` (if none
   exists, the user hasn't evaluated this site yet — respond by saying
   so and prompting them to run an evaluation first, don't try to answer
   from nothing).
2. Load `cart_items.llm_structured` for the listing's own data.
3. Load the last ~10 rows from `chat_messages` for this cart_item_id, in
   order, as conversation history.
4. Load `listing_memory` for this cart_item_id — dump all of it into
   context (per the earlier design decision: dump-all is fine at this
   scale, don't build retrieval/filtering).
5. Load `session_context.summary` for this session_id, if it exists.
6. Run Step 3 (router) to determine if new Mireye data is needed.
7. Generate the answer (Step 4).
8. Store the user message and the assistant response as two new
   `chat_messages` rows.
9. Run Step 5 (memory extraction) as a fire-and-forget step — don't
   block the response on this.
10. Periodically (see Step 6) update `session_context`.

---

## Step 3 — Router: does this question need new Mireye data?

One LLM call, before generating the actual answer. Give it:
- The user's message
- The full list of already-cached field names for this listing (from
  `mireye_cache` — you already have the cache_key from the evaluation
  step, reuse it, don't re-geocode)
- The 58-field Mireye inventory (field names + one-line descriptions,
  from `config.py`) as the menu of what's fetchable

Ask it to return one of:
```json
{ "action": "answer_from_existing_context" }
```
or
```json
{ "action": "fetch_fields", "fields": ["field_name_1", "field_name_2"] }
```

Cap this at a small number of fields per turn (e.g. max 5) — if the
router wants more than that, it's a sign the question is too broad; have
it pick the most relevant subset rather than fetching everything. This
keeps chat turns fast and keeps Mireye call volume bounded.

If `fetch_fields` is returned: call `mireye_fetcher` (the existing
wrapper) for exactly those fields, merge results into `mireye_cache`
(same additive pattern as the evaluation pipeline — you're calling the
same fetcher, so this is automatic if you reuse it correctly), and add
them to context for Step 4.

**Important:** the router should almost always return
`answer_from_existing_context`, because the default evaluation already
pulled the 58-field... no — pulled the `AGENT_FIELD_MAP` subset per
agent. If the user asks about something genuinely outside that set
(e.g. karst terrain, opportunity zone status, telecom towers — fields
in the full inventory but not in the default 5-agent map), that's
exactly when `fetch_fields` should trigger. This is the whole point of
having a 58-field inventory but a smaller default set: the default
report stays cheap, and chat is where the long tail of fields actually
gets used.

---

## Step 4 — Answer generation

One more LLM call. System prompt must enforce the same grounding rules
as the evaluation agents:
- Every factual claim traceable to a citation
- Citations tagged by source: `mireye`, `listing`, or `memory` (a fact
  from `listing_memory` — e.g. something the user told you earlier in
  conversation, not derived from Mireye or the listing itself)
- Explicitly say "not available" rather than estimate, for any field
  that's null/missing even after the router step
- If `session_context.summary` exists, use it to shape tone/framing
  (e.g. weight answers toward the user's stated priorities) but don't
  let it override factual grounding — it's context, not evidence

Return shape:
```json
{
  "content": "the answer text",
  "citations": [
    { "source": "mireye", "field": "fema_flood_zone", "value": "..." },
    { "source": "memory", "fact": "..." }
  ]
}
```

---

## Step 5 — Memory extraction (fire-and-forget, after responding)

A lightweight LLM call: given the just-completed turn (user message +
assistant response), decide if there's a durable, atomic fact worth
remembering about this listing — not a full summary, just "is there
something here worth keeping." Examples: "User is concerned about rail
noise," "User confirmed this site is a backup option, not primary."

If yes, insert one row into `listing_memory`. If the turn was purely
informational (user asked a factual question, got a factual answer, no
new preference/concern/decision surfaced), insert nothing — don't force
a memory entry every turn, only when something genuinely worth keeping
came up.

Keep this call cheap (small model, short prompt) since it runs on every
turn — this is a background enrichment step, not part of the critical
response path.

---

## Step 6 — Session context re-summarization

Trigger this **not every turn** — every N turns (e.g. every 3-5 messages
across any site in the session) or when a new cart_item_id is chatted
with for the first time in a session. Logic:
1. Pull the last ~15-20 messages across ALL cart_items for this
   session_id (not just one listing — this is session-level, meant to
   capture cross-site intent like "generally looking for industrial
   sites near Atlanta, budget-conscious").
2. One LLM call: given the existing `session_context.summary` (if any)
   plus these recent messages, produce an updated one-paragraph summary.
   Explicitly instruct it to re-summarize, not append — the output
   should be a fresh, coherent paragraph, not the old summary plus new
   sentences tacked on.
3. Overwrite the single `session_context` row for this session_id.

This keeps the summary a stable, current snapshot rather than a
growing, staling log.

---

## Step 7 — Supporting read endpoints

```
GET /chat?cart_item_id=<id>
  returns: full chat_messages history for that listing, ordered by
  created_at, for the frontend to render on load

GET /listing-memory?cart_item_id=<id>
  returns: all listing_memory rows for that listing

GET /session-context?session_id=<id>
  returns: the current session_context.summary, or null if none exists
  yet
```

All three are simple reads, no new logic beyond querying and returning
JSON.

---

## Step 8 — Testing

- Ask a question fully answerable from the existing evaluation report
  (e.g. "what's the flood risk?" when `fema_flood_zone` was already in
  the default Risk agent's fields) — confirm the router returns
  `answer_from_existing_context` and no new Mireye call happens.
- Ask a question that requires a field outside the default 5-agent set
  (e.g. "is this near any FCC antenna towers?" or "is this in an
  opportunity zone?") — confirm the router correctly identifies and
  fetches exactly those fields, and confirm they get cached (repeat the
  same question in a new turn, confirm no second Mireye call).
- Ask a vague/broad question ("tell me everything about this site") —
  confirm the router caps the field request rather than requesting the
  entire 58-field inventory at once.
- Have a short conversation that includes a clear preference statement
  ("I really don't want anything near a flood zone") — confirm a
  `listing_memory` row gets created capturing this.
- Have a conversation spanning 2 different cart items in the same
  session — confirm `session_context` reflects both, not just the most
  recent one.
- Confirm every assistant response's citations actually trace to real
  field values or real memory rows — spot check by hand, same as the
  evaluation pipeline's grounding check.

---

## Handoff checklist

- [ ] `listing_memory`, `session_context`, `chat_messages` tables
      created via migration
- [ ] `POST /chat` reuses existing `evaluations`, `cart_items`,
      `mireye_cache`, and `mireye_fetcher` — no duplicate Mireye client
      or field inventory
- [ ] Router correctly distinguishes "answerable from existing context"
      vs "needs new fields," capped at a small max per turn
- [ ] New Mireye fetches from chat merge into the same additive
      `mireye_cache` used by the evaluation pipeline — confirmed via
      repeat-question test showing no duplicate calls
- [ ] Answer generation enforces citation-per-claim, source-tagged
      (mireye / listing / memory), "not available" over estimation
- [ ] Memory extraction runs fire-and-forget, only creates entries for
      genuinely durable facts, not every turn
- [ ] Session context re-summarizes (not appends) periodically, spans
      all cart_items in the session, not just the current one
- [ ] `GET /chat`, `GET /listing-memory`, `GET /session-context` read
      endpoints working
- [ ] All Step 8 test scenarios pass, including the grounding spot-check
