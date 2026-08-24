# Build Task: Multi-Site Comparison View

## Scope of this task, explicitly

Build: a backend endpoint that returns multiple stored evaluations
side-by-side plus a synthesized comparison narrative, and the minimal
data shape the frontend's comparison screen (already designed per the
Stitch prompt) needs to render.

Do NOT build in this task: any new Mireye calls (comparison is strictly
a read-over-existing-evaluations feature), any new agent logic, saved/
named comparison sets (out of scope — comparisons are ephemeral, built
from whatever's currently selected in the cart).

---

## Context you need

- Every site being compared must already have a row in `evaluations`
  (via the pipeline from the earlier evaluate-site build task). If a
  selected cart item has no evaluation yet, surface that clearly rather
  than silently excluding it or failing.
- `evaluations.agent_results` already contains all 5 agents' scores,
  summaries, and citations per site — this is 100% of what comparison
  needs. No new data source required.

---

## Step 1 — Endpoint

```
POST /compare-sites
  body: { cart_item_ids: string[] }   // 2-4 ids, enforce this range
  returns: {
    sites: [
      {
        cart_item_id,
        address,
        listing_title,
        overall_score,
        recommendation,
        agent_scores: {          // flattened for easy row-by-row rendering
          energy: number,
          water: number,
          surface: number,
          transport: number,
          risk: number
        },
        missing_evaluation: boolean   // true if no evaluations row exists
      },
      ...
    ],
    comparison_narrative: string,
    trade_offs: string[]
  }
```

Reject requests with fewer than 2 or more than 4 `cart_item_ids` with a
clear error message — comparison beyond 4 sites gets visually unwieldy
and isn't worth supporting for a hackathon scope.

---

## Step 2 — Handler logic

1. For each `cart_item_id`, look up its most recent `evaluations` row.
2. If missing, set `missing_evaluation: true` for that site and exclude
   it from the narrative generation in Step 3 — don't let one
   un-evaluated site block the whole comparison, but do surface it so
   the user knows to run an evaluation first.
3. Flatten `agent_results` into the `agent_scores` shape shown above —
   this is a pure data transform, no LLM call needed for this part.
4. Run Step 3 for the narrative.

---

## Step 3 — Comparison narrative (one LLM call)

Input: all evaluated sites' full `agent_results` (not just the flattened
scores — the LLM needs the actual memos/citations to write something
grounded, not just numbers).

Output:
```json
{
  "comparison_narrative": "2-3 sentence overview of how the sites stack up",
  "trade_offs": [
    "Site A has stronger power infrastructure but Site B has lower flood risk",
    "..."
  ]
}
```

Same grounding discipline as everywhere else: every trade-off claim
should be traceable to specific agent scores/citations from the input
data, not invented. Instruct the model explicitly: compare only using
the provided per-site evaluation data, do not introduce outside
knowledge about these addresses or property types.

---

## Step 4 — Testing

- Compare 2 sites where one clearly outscores the other — confirm the
  narrative correctly identifies the stronger site, not a hedge.
- Compare 3-4 sites with genuinely mixed trade-offs (no single winner
  across all categories) — confirm `trade_offs` reflects real tension,
  not a flattened "they're all fine" statement.
- Include one cart_item_id with no evaluation — confirm it's flagged via
  `missing_evaluation` and the narrative still generates sensibly for
  the remaining sites.
- Submit 1 or 5 `cart_item_ids` — confirm both are rejected with a clear
  error, not a silent partial response.
- Spot-check that `trade_offs` entries trace back to real agent
  scores/citations in the input, not fabricated comparisons.

---

## Handoff checklist

- [ ] `POST /compare-sites` enforces 2-4 site range
- [ ] Missing evaluations flagged per-site, don't block the rest
- [ ] `agent_scores` flattened cleanly for frontend row-by-row rendering
- [ ] Narrative + trade-offs generated from real evaluation data only,
      no new Mireye calls anywhere in this feature
- [ ] All Step 4 test scenarios pass, including the grounding spot-check
