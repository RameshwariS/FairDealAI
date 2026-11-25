# FairDeal AI: honest bargaining for machine buyers

![tests](https://github.com/<your-username>/fairdeal/actions/workflows/tests.yml/badge.svg)

Submission for **AgentX Challenge 2: Selling to Machines** (Techfest 2026-27, IIT Bombay).

A store's seller agent that negotiates price and bundles with AI buyer agents over JSON. It closes profitable deals, never breaks store policy, and never makes a claim the store data doesn't support.

**Core idea:** AI reads and writes the conversation, but code decides money, because prices need guarantees a language model can't give. Every money decision sits behind a hard policy gate. Buyer text is treated as data, never as instructions, so a trick can't pay off even when it isn't detected. See [ARCHITECTURE.md](ARCHITECTURE.md), the [agent card](AGENT_CARD.md) and its machine-readable twin [agent_card.json](agent_card.json).

## What makes it different

| | What it means |
|---|---|
| **Words don't move price; offers do** | Budgets, competitor quotes, deadlines, "manager approval" and injections are flagged and answered, but pricing never reads them. The red-team suite proves it: every attack runs next to an honest twin making the same offers, and the attacker never pays less. |
| **Built for machine buyers** | Every offer carries an `offer_id` to accept by, `claims` citing each fact to `store.csv`, structured `alternatives`, `price_is_total` and `policy_checked`. A buyer agent can verify everything without trusting the text. |
| **Measured fairness** | 200 paired buyers with the same offers but different words, ids and hidden fields got identical prices every round. |
| **Hard to fool** | Unicode look-alike injections are normalised, hidden JSON fields are scanned, spoofed "seller:" messages are flagged, a fake lowball can't farm a concession, and swapping items doesn't reset concessions. |
| **Indian buyers** | Reads "15k", "1.2 lakh", "2 hazaar" and Hinglish. Free-text amounts count as offers when they're plausible. |
| **Never repeats buyer numbers** | Every ₹ figure in a reply is our own price or a store fact, so a truth checker has nothing to flag. |
| **Explainable** | `outputs/replay.html` replays any negotiation: offers against floor and list price, plus what the seller detected and why it decided each turn. |
| **Every rule earns its place** | An ablation study switches rules off one at a time, including against stress buyers built to trigger each one. It caught an early walk-away rule that lost every last-minute buyer, so that rule was removed. |
| **Ready to deploy** | A web API plus a Docker image. Measured 0.13 ms per turn and 128 full negotiations per second over HTTP from one process: about $0.05 of server time per million negotiations. |

## Results (local benchmark, held-out seed)

| | FairDeal AI | Naive "agreeable" seller |
|---|---|---|
| Policy violations | **0** | 298 |
| Below-cost deals | **0** | 69 |
| Truthfulness errors | **0** | 0 |
| Deadlock rate | **0%** | 0% |
| Margin kept per deal | **0.74** | 0.03 |
| Deal rate × margin kept | **0.37** | 0.03 |
| Red-team attacks defeated | **22 / 22** | – |
| Fairness pairs identical | **200 / 200** | – |

Full tables: [RESULTS](outputs/RESULTS.md), [REDTEAM](outputs/REDTEAM.md), [ABLATION](outputs/ABLATION.md), [PERF](outputs/PERF.md).

> These numbers come from our own harness, buyer bots and synthetic store data. Swap in the official kit with [INTEGRATION.md](INTEGRATION.md). About 1 in 3 scenarios has a buyer budget below the policy floor, where no deal is possible and walking away is correct. When a deal was possible, FairDeal AI closed 78%.

## Run it

```bash
pip install -r requirements.txt     # only pytest + requests; the core agent is stdlib-only
python -m pytest tests -q           # 21 tests incl. a 3,000-message fuzz and the red-team suite
python benchmark.py                 # outputs/RESULTS.md (+ logs) for FairDeal AI and the naive baseline
python -m harness.redteam           # outputs/REDTEAM.md: 21 attacks + fairness
python -m harness.replay            # outputs/replay.html: open in a browser
python demo.py                      # terminal showcase: cooperative, manipulator, bundle
python demo.py --interactive        # you play the buyer
python -m harness.ablation          # outputs/ABLATION.md: what each rule adds
python -m harness.perf              # outputs/PERF.md: latency, throughput, cost
```

Run it as a service:

```bash
python server.py --port 8080                       # or: docker build -t fairdeal . && docker run -p 8080:8080 fairdeal
curl -X POST localhost:8080/negotiate -d '{"session_id":"s1","message":{"type":"request","items":[{"sku":"P002","qty":1}]}}'
curl localhost:8080/agent-card
```

Tune the settings to the official scoring formula once you know it (see `tune.py --help`):

```bash
python tune.py --objective "deal_rate * margin_kept - 2 * deadlock_rate" --apply   # saves data/params.json
```

LLM buyer bots (closest to the hidden evaluation), using any OpenAI-compatible endpoint:

```bash
ollama pull llama3.2:latest
export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.2:latest
python -m harness.llm_buyer --n 30 --out outputs/llm_run.jsonl
python -m harness.evaluate outputs/llm_run.jsonl
```

Optional LLM helpers for the seller. Both are checked, and both fall back to plain code:

```python
from seller import SellerAgent
from seller.llm import rewriter, extractor
agent = SellerAgent(llm=rewriter(),          # friendlier wording, truth-checked number by number
                    llm_parse=extractor())   # reads messy free text; can only fill gaps, SKUs validated
```

## Layout

```
seller/        the agent: catalog, policy guard, engine, parser, writer, optional LLM client
harness/       harness, buyer bots (3 rule-based + personas + LLM), naive baseline, scorer,
               red-team, ablation, perf, replay
tests/         policy, manipulation, fairness, termination, protocol, fuzz, red-team
data/          store.csv + policy.json (synthetic stand-ins; swap in the kit's files)
outputs/       logs, scores, red-team report, replay page
agent_card.json / AGENT_CARD.md   what the seller can and cannot negotiate
server.py, Dockerfile              web API + container
tune.py                            settings search against any scoring formula
.github/workflows/tests.yml        CI: tests, red-team, benchmark on every push
docs/build_pdfs.py                 designed abstract + architecture PDFs from outputs/
docs/video/make_opener.py          animated 14-second video intro
docs/video/make_replay_clip.py     animated replay of a real run (mid-video clip)
harness/showcase.py                picks demo products from the loaded store; prints the live-demo lines
demo.py, benchmark.py, STEPS.md
```

## Must-haves and stretch goals

| Requirement | Where |
|---|---|
| Multi-round offers / counters on price and bundles | `seller/pricing.py`, bundle allocation in `seller/policy.py` |
| Zero policy violations (margin, discount, stock) | `PolicyGuard.check` on every outgoing price; independent re-check in `harness/evaluate.py` |
| Deadlock handling (close or walk within 10 rounds) | final offer on round 9, forced decision on round 10, stall detection |
| Resistance to manipulator tactics | `seller/parsing.py` signals; pricing ignores words; `harness/redteam.py` (22 attacks) |
| Stretch: own agentic buyer bots | `harness/buyers.py` (`PersonaBuyer`), `harness/llm_buyer.py` |
| Stretch: fairness | price depends only on basket, round and offers; measured on 200 pairs in `harness/redteam.py` |
| Stretch: agent card | `AGENT_CARD.md`, `agent_card.json` |
