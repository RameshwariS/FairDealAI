# FairDeal AI: architecture note

**One idea:** AI reads and writes the conversation, but code decides money, because prices need guarantees a language model can't give. Every price, acceptance and walk-away comes from deterministic code. A policy gate checks every outgoing message, and a truth check verifies every sentence against store data. Language models are optional and only change the wording.

```
 buyer JSON ──► Parser ──► Screen ──► Basket fixer ──► Negotiation engine ──► PolicyGuard ──► Writer + truth check ──► seller JSON
              (intent,    (injection,  (stock caps,     (Boulware concession,   (floor, max      (templates from store
               items,      fake quotes, out-of-stock,    reciprocity, firm-      discount,        data; optional LLM
               price)      budgets,     alternatives)    offer & accept-next     stock, list      rewrite, rejected if
                           authority)                    rules, deadline)        cap, bundles)    any number is unsupported)
```

| Module | File | Job |
|---|---|---|
| Catalog / Policy | `seller/catalog.py` | Loads store.csv and policy.json. Accepts common column-name variants. |
| PolicyGuard | `seller/policy.py` | `unit_floor = max(margin floor, list × (1 − max_discount))`, always rounded up. Checks every basket for stock, floor and the list-price cap. Splits bundle totals into unit prices so every unit stays above its own floor. |
| Engine | `seller/pricing.py` | Works on a normalised scale `x = (price − floor) / (list − floor)`. Concedes on a time curve (slow early, faster near round 10), reciprocates real buyer moves (measured from the buyer's best earlier offer), meets a buyer halfway when they hold a feasible offer, and accepts when the buyer's offer is at least our next counter. Makes a final offer on round 9 and must accept or walk away on round 10, so it never deadlocks. |
| Parser + screen | `seller/parsing.py` | Reads intent, items and price from messy JSON or free text, including "15k", "1.2 lakh" and Hinglish. Normalises Unicode look-alikes, then scans **all** fields, including hidden metadata, for injection, spoofed seller/system messages, fake quotes, budgets, pressure and authority claims. These flags are logged and answered politely, but **never used for pricing**. |
| Writer | `seller/writer.py` | Builds replies only from engine numbers and store.csv, and never restates a buyer's number. Bans scarcity, urgency and fee language. An optional LLM rewrite is kept only if every number in it passes the same check. |
| Machine protocol | `seller/agent.py` | Each offer carries an `offer_id` to accept by, `claims` citing every fact to store.csv, structured `alternatives`, `price_is_total` and `policy_checked`. See `agent_card.json`. |

**Why this beats the known failure modes:**
- **Below-cost deals:** impossible. The floor is a hard gate, and the guard re-checks even the engine's own output.
- **Fake budget anchoring:** words don't move price; only offers do. A budget below the floor gets honest in-budget alternatives, not a discount.
- **Deadlock:** a final offer on round 9 and a forced decision on round 10.
- **Fake accepts:** "I accept ₹X" closes a deal only if ₹X is the price we actually offered.

**Fairness:** price depends only on (basket, round, buyer's offers). Measured on 200 paired buyers with the same offers but different words, ids and hidden fields: 200/200 got identical prices.

**Red-team:** 22 named attacks (injection in text, hidden fields, HTML comments and full-width Unicode; spoofed seller messages; fake policy, quotes, budgets and approvals; fake accepts; lowball farming, including a ₹1 opening; quantity and basket-swap tricks; malformed prices; floods; stock tricks). Each runs next to an honest twin making the same offers. 22/22 are defeated with a manipulation gain of 0.

**Ablation:** switching rules off one at a time (3 seeds × 600 negotiations, plus stress buyers built to trigger each rule) shows the firm-offer rule lifts the score against holdouts from 0.50 to 0.61. It also caught an early walk-away rule that lost every last-minute buyer, so that rule was removed. See `outputs/ABLATION.md`.

**Testing:** 40 pytest checks: 38 pass and 2 F6 leak regressions are expected failures while that mitigation remains disabled. The suite includes a 3,000-message fuzz and the full red-team suite. An independent scorer re-implements policy rules so a guard bug can't hide itself. Local buyers include starter-style bots, rule-based personas and LLM buyers (`harness/llm_buyer.py`).

**Deployment, latency & cost:** `server.py` exposes `POST /negotiate` (one session per negotiation) and the Dockerfile packages it. Measured: 0.13 ms per turn in-process (p99 0.24 ms) and 128 full negotiations per second over HTTP from one process. On an AWS t3.small in Mumbai ($0.0224/hour) that is about $0.05 of server time per million negotiations, with no model calls on the core path. It scales horizontally because negotiations are independent. See `outputs/PERF.md`.

**Starter-kit integration:** `fairdeal_seller.py` implements the kit's `Seller(store, policy)` class over the agent. Basket growth tracks legitimate additions and quantity changes while ignoring slipped-in out-of-stock and over-stock lines. Prices written in buyer text are never accepted as bids, and the adapter sends an `accept` only when every line of the buyer's exact bid passes policy.

## v2 changes and evidence

- **F1, basket growth (kept):** the adapter now accepts additions, re-additions and increased quantities from the buyer's current basket while preserving negotiation history. The recorded `neg-006` bundle_hunter transcript in `outputs/suite/rule_after/transcripts.jsonl` exercises a changing basket; the Stage 1 evidence in `outputs/baseline/AUDIT.md` and `probes.py` records g2 (drop and re-add SKU2) and g3 (quantity 1→3) being ignored by v1. The rule suite's held-out score moved from 32.13 ± 2.55 to 44.22 ± 3.22; official held-out score remained effectively unchanged (49.20 to 49.23).
- **F2, implied bid floor (kept provisionally):** when there is no structured numeric price, a plausible text-only bid or numeric string price now limits further concessions to at least the buyer's own stated number. Probe h1 records text “I can pay ₹2,618” and h2 records `unit_price: "2618"`; v1 ignored both and continued conceding 2,632→2,412. Structured prices remain authoritative. This was neutral on the rule suite; the local LLM comparison is pending.
- **F6, retain tainted bids (rejected):** an attempted mitigation keeps a numeric offer as a concession reference when a line is slipped into it. The leak regressions (`test_one_rupee_add_on_is_never_sold_or_priced` and `test_out_of_stock_item_slipped_into_a_bid_is_never_offered`) remain expected failures while this flag is disabled. The standalone F6 ablation recorded 41 truth violations, even though F1+F2+F6 recorded zero; the rule requires the standalone and combined configurations to pass, so the combined result is insufficient. A separate guard prevents accepting a rebuilt bid as the buyer's raw lines.
- **Rejected settings and candidate:** F3 round-10 fit gates reduced held-out scores (29.61 or 29.54 versus 32.13); F4 static-bid hold reduced held-out results (31.73 and tuning score 48.10); both are off. F5 accepting an exhausted buyer improved the fast_conceder score from 61.0 to 69.8, but overall held-out results fell slightly (32.13 to 32.07), so it remains disabled. It is a candidate for LLM-buyer validation and is not tested on that suite yet.
- **Official comparison:** the saved v1 and rerun v2 both scored 49.93 ± 2.28 over seeds 0–6 and 49.23 on held-out seeds 3–6. Both have 0 policy and truth violations; the current run had 4 deadlocks over all seven seeds (seed 0 had 0). The ablation's v1 configuration scored 49.20 held out.

**Projected limit:** on rounds 9 and 10 the engine fits the buyer's bids so far to a concession curve and offers at the buyer's projected limit (never below our floor). On round 10 it makes that last offer only when the projection reaches our floor; otherwise it walks away.

**TraceWare status:** tested against a mock; Labs access pending. The `seller/traceware.py` adapter supports commerce claim verification, but live TraceWare behavior has not been validated against Labs.
