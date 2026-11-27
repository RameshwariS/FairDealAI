# Stage 1 audit + Stage 2 baseline (before any code change)

Commit audited: `0c1844a`. All numbers below come from runs in this folder:
`official_results.json` (docs/official_results.py, unchanged, output redirected here),
`audit_kit.py` (seeds 0-6 replayed in-process with full transcripts -> `audit_transcripts.jsonl`),
`probes.py` (scripted buyers through `fairdeal_seller.Seller`), `pytest.txt`, `video_lock_demo.txt`.

## Baseline (official evaluate.py, 210 negotiations per seed)

| | FairDeal AI | Kit example seller |
|---|---|---|
| Mean score, seeds 0-6 | **49.93 ± 2.28** | 45.41 ± 2.25 |
| Mean score, held-out seeds 3-6 | **49.23 ± 1.66** | 44.55 ± 1.03 |
| Seed 0 (default run) | 53.0 | 48.5 |
| Policy + truth violations, 7 seeds | 0 | 0 |
| Deadlocks, 7 seeds | **4** (seeds 1, 3, 5, 6) | 164 |

Per seed (FairDeal / example): 53.0/48.5, 52.2/48.3, 47.4/42.9, 48.6/44.4, 48.3/43.3, 51.7/45.8, 48.3/44.7.
pytest: 25 passed. Video lock: demo dialogue reproduces ₹5,070 / 4,989 / 4,885 / 4,729 / 4,573 / accept ₹4,500
with flags injection / competitor_quote / fake_accept; `python -m harness.redteam` regenerates REDTEAM.md
with no diff (22/22, gain 0).

## Findings, by priority

| # | Issue | Real? | Evidence | Expected impact | Fix risk |
|---|---|---|---|---|---|
| 1 | (a) Projection is fitted to the kit bots' own formula | **Yes** | `projected_limit()` fits `a+(L-a)(r/T)^e` with T=10, an `r-1` shift and e in {0.5,0.7,1.0,1.5,2.0,2.5,3.0}. The kit bots generate bids with exactly `anchor+(res-anchor)(r/deadline)^exp`, exp in {0.7, 2.5, 2.0}, deadline 10, and answer round r-1. 358 of the 1,470 deals (55% of hard-bargainer and manipulator deals) close when the buyer accepts our round-10 projected-limit offer. | High: most of the margin from tough buyers depends on a model that LLM buyers won't follow. | High: the kit score is very sensitive to this |
| 2 | (e) Round-10 offer → counter = deadlock | **Yes** | 363 round-10 offers → 358 deals, **all 4 deadlocks**, 1 buyer walk. A countered round-10 offer scores −0.25, a walk-away scores 0. Break-even acceptance ≈ 0.25/(0.25+value) ≈ 35-40%. Kit bots accept 98.6% of them; LLM acceptance is unknown. | High for LLM buyers (each counter costs 0.25) | Medium |
| 3 | (h) Natural-language / malformed bids lost | **Yes** | Probe h1: buyer writes "I can pay ₹2,618" (97% of list, above our offers); seller ignores it and keeps conceding 2,632→2,412. h2: `unit_price: "2618"` (string) is ignored the same way. | Medium-high for LLM buyers; 0 on kit bots | Low if the number only sets a lower bound on our counter (never accepted as-is) |
| 4 | (g) Adapter basket tracking | **Yes (bug)** | `_normalise` taints any SKU not in the *current* basket. Probe g2: buyer drops SKU2, re-adds it at r5 bidding ₹3,373 for both; every later bid is ignored and we keep conceding on one item (₹2,344). g3: qty 1→3 (within stock) bidding ₹7,287 is ignored. Concession progress is correctly *not* reset (no exploit); buyer history *is* reset, so a late change leaves <3 points for the projection. | Medium for LLM bundle hunters; 0 on kit bots (they never re-add) | Low-medium (must still reject over-stock / slipped lines) |
| 5 | (d) Concession while buyer doesn't move | **Yes** | Probes c2/d2: identical bid 9 rounds in a row; seller goes 2,632 → 2,025 (floor) anyway: the time curve, not buyer moves, drives concession. Late sniper (flat, then jumps at r8) gets its r8 bid accepted at x≈0.2. Round-9 "final offer = end_x": deals closed by the buyer accepting it leave the buyer 75-87% of its (floor→limit) zone (`audit_kit` breakdown). | Medium (margin) | Medium-high: tuned behaviour, hurts deal rate if overdone |
| 6 | (c) <3 bids / identical bids | **Partly** | <3 bids → no projection → round 9 at end_x, round 10 walk. Probe c1: buyer bids ₹1,985 at r9 then ₹2,020 at r10 against a ₹2,025 floor and still gets a walk-away. Identical bids → projection = that price → round-9 offer drops to floor (c2). No crash, no deadlock. | Low-medium | Low |
| 7 | Offer below the buyer's own earlier line bid | Yes, rare | When a bid has a slipped/out-of-stock line, its valid lines are discarded. 4/1,470 kit negotiations (₹152 total), e.g. seed 0 neg-001: buyer bid ₹9,200 for 4 pants, we offered ₹9,117. Same in the old LLM log. | Very low (merge with #3) | Low |
| 8 | (b) LLM buyers only mocked | **Not as stated** | No mock exists. `outputs/llm_run.jsonl` is a real llama3.2 run, but n=5, and `kit_llm_buyers.py` falls back to the rule bot whenever the LLM's reply is unusable or over its limit: only ~5 of 26 buyer turns were LLM-written. `harness/llm_buyer.py` uses our own protocol, not the kit's. | The real gap is coverage, not mocking | n/a |
| 9 | (f) Bundle allocation by headroom | **No** | Profit = Σq·p − Σq·cost depends only on the total; the kit scores profit and the kit buyers judge totals. Allocation changes nothing (except sub-paisa flooring). | ~0 | Reject |

## Doc inaccuracies found (no code impact)
- README says "Deadlocks, default run 0" (true for seed 0); seeds 0-6 have 4. README/STEPS say 23 tests; there are 25.
- README curl example uses SKU `P002`, which isn't in `data/store.csv` (it returns a bare `info`). With a real SKU (S001)
  the reply carries `offer_id`, `claims`, `price_is_total`, `policy_checked` as documented.
- `outputs/llm_eval.txt` starts with a stray `git checkout master` line; `outputs/TUNING.md` lists stale "current defaults".
