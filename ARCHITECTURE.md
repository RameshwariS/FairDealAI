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

**Testing:** 23 pytest checks, run by CI on every push, including a 3,000-message fuzz with garbage and hostile input and the full red-team suite. An independent scorer re-implements the policy rules so a guard bug can't hide itself. Local buyers: the 3 starter-style bots, randomised agentic-style personas, and LLM buyers (`harness/llm_buyer.py`, any OpenAI-compatible endpoint, such as Ollama).

**Deployment, latency & cost:** `server.py` exposes `POST /negotiate` (one session per negotiation) and the Dockerfile packages it. Measured: 0.13 ms per turn in-process (p99 0.24 ms) and 128 full negotiations per second over HTTP from one process. On an AWS t3.small in Mumbai ($0.0224/hour) that is about $0.05 of server time per million negotiations, with no model calls on the core path. It scales horizontally because negotiations are independent. See `outputs/PERF.md`.

**Starter-kit integration:** `fairdeal_seller.py` implements the kit's `Seller(store, policy)` class over the agent. It locks the basket to the buyer's opening request, ignores slipped-in ₹1, out-of-stock and over-stock lines, never reads prices written in buyer text as bids, and sends an `accept` only when every line of the buyer's exact bid passes policy (otherwise it offers the same total split so every line clears its floor).

**Projected limit:** on rounds 9 and 10 the engine fits the buyer's bids so far to a concession curve and offers at the buyer's projected limit (never below our floor). On round 10 it makes that last offer only when the projection reaches our floor; otherwise it walks away.

**Rezolve Labs capability used: TraceWare commerce claim verification** (`seller/traceware.py`). For every offer and accept, the seller records one `add_to_basket` action per line (SKU, name, quantity, unit price) and verifies the reply text against them before sending. PASS or WARN replies go out as written; REGENERATE or BLOCK replies are replaced with a plain sentence built from the same actions. Enabled with `REZOLVE_API_KEY` and `REZOLVE_MERCHANT_ID`; it sits alongside the deterministic truth check, so a claim must satisfy two independent verifiers.
