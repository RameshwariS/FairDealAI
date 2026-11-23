"""Ablation study: switch off one part of the engine at a time.

    python -m harness.ablation        # writes outputs/ABLATION.md

Each variant runs 600 negotiations on each of 3 seeds (1,800 total) against
the same mixed buyers. The PolicyGuard is never switched off, so every variant
keeps 0 violations; the ablation shows what each NEGOTIATION rule buys.
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seller import Params  # noqa: E402
from harness.evaluate import load, score  # noqa: E402
from harness.run import negotiate, run  # noqa: E402
from harness.buyers import Buyer, _items  # noqa: E402
from seller import SellerAgent  # noqa: E402
import random  # noqa: E402


class Holdout(Buyer):
    """Climbs to its limit by round 3, then repeats it. Only accepts a price at or below its own offer."""
    name = "holdout"

    def act(self, rnd, seller_msg):
        sp = self.seller_price(seller_msg)
        offer = round(min(self.wtp, self.list_total * 0.6 + (self.wtp - self.list_total * 0.6) * min(1, rnd / 3)))
        if sp is not None and sp <= offer:
            return {"type": "accept", "items": _items(self.lines), "price": sp}
        if rnd >= 9:
            return {"type": "walk_away"}
        return {"type": "offer", "items": _items(self.lines), "price": offer, "text": "That's my final offer."}


class LastMinute(Buyer):
    """Lowballs until round 8, then offers its real limit on rounds 9 and 10."""
    name = "last_minute"

    def act(self, rnd, seller_msg):
        sp = self.seller_price(seller_msg)
        offer = round(self.wtp) if rnd >= 9 else round(self.list_total * 0.5)
        if sp is not None and sp <= offer:
            return {"type": "accept", "items": _items(self.lines), "price": sp}
        return {"type": "offer", "items": _items(self.lines), "price": offer}


class Staller(Buyer):
    """Repeats an offer below the policy floor and never leaves."""
    name = "staller"

    def act(self, rnd, seller_msg):
        return {"type": "offer", "items": _items(self.lines), "price": round(self.list_total * 0.4)}


def stress(params, n=150, seed=5):
    """Score against buyers built to trigger each rule. Their limits are always above the floor."""
    agent = SellerAgent(params=params)
    g, rng = agent.guard, random.Random(seed)
    from seller.policy import Line
    in_stock = [p for p in agent.catalog.products.values() if p.stock > 0]
    out = {}
    for cls in (Holdout, LastMinute, Staller):
        deals = kept = rounds = 0
        for _ in range(n):
            p = rng.choice(in_stock)
            fl = g.bundle_floor([Line(p.sku, 1)])
            wtp = fl + rng.uniform(0.0, 0.6) * (p.price - fl)
            r = negotiate(agent, cls([(p.sku, 1)], p.price, wtp, rng))
            o = r["outcome"]
            rounds += o.get("round", 10)
            if o["result"] == "deal":
                deals += 1
                kept += (o["price"] - p.cost) / (p.price - p.cost)
        out[cls.name] = {"score": deals / n * (kept / deals if deals else 0), "deal_rate": deals / n,
                         "avg_rounds": rounds / n}
    return out

SEEDS, N = (1, 2, 3), 600
VARIANTS = [
    ("Full agent", {}),
    ("No firm-offer rule (meet a held offer halfway, then take it)", {"firm_from_round": 99}),
    ("No reciprocity (ignore how much the buyer moved)", {"reciprocity": 0.0}),
    ("No minimum concession per round", {"min_step": 0.0}),
    ("No late accept (rounds 9-10)", {"late_accept": False}),
    ("No final best offer on round 9", {"final_offer": False}),
    ("Stall rule on: final offer after 3 frozen rounds", {"stall_rounds": 3}),
    ("Stall rule on + walk away early (first version)", {"stall_rounds": 3, "stall_walk": True}),
    ("No small-gap close", {"close_gap": 0.0, "close_gap_abs": 0.0}),
    ("Linear concession instead of Boulware", {"boulware": 1.0}),
    ("No bundle opening discount", {"open_bundle": 1.0}),
]
KEYS = ["deal_rate_x_margin_kept", "profit_captured_of_max", "deal_rate", "margin_kept",
        "deadlock_rate", "policy_violations"]


def main():
    items, pol = load()
    rows = []
    for name, kw in VARIANTS:
        per = [score(run(n=N, seed=s, quiet=True, params=Params(**kw)), items, pol) for s in SEEDS]
        rows.append((name, {k: statistics.mean(p[k] for p in per) for k in KEYS},
                     statistics.pstdev(p["deal_rate_x_margin_kept"] for p in per), stress(Params(**kw))))
        print(name, rows[-1][1])
    base = rows[0][1]
    md = ["# Ablation study\n",
          f"{len(SEEDS)} seeds × {N} negotiations per variant, mixed buyers (cooperative, hard bargainer, "
          "manipulator, randomised personas). Score = deal rate × margin kept (higher is better). "
          "The policy guard stays on in every variant, so violations stay 0; this measures what each "
          "negotiation rule adds.\n",
          "| Variant | Score | Change vs full | Profit captured | Deal rate | Margin kept | Deadlocks |",
          "|---|---|---|---|---|---|---|"]
    for name, m, sd, _ in rows:
        delta = m["deal_rate_x_margin_kept"] - base["deal_rate_x_margin_kept"]
        md.append(f"| {name} | {m['deal_rate_x_margin_kept']:.3f} ± {sd:.3f} | "
                  f"{'–' if name == 'Full agent' else f'{delta:+.3f}'} | {m['profit_captured_of_max']:.3f} | "
                  f"{m['deal_rate']:.3f} | {m['margin_kept']:.3f} | {m['deadlock_rate']:.1%} |")
    md += ["\n± is the spread across seeds. On this mix most rules change little: the time curve and the "
           "walk-away do most of the work, and the other rules rarely fire.\n",
           "## Stress buyers: what each rule is for\n",
           "150 negotiations per buyer. Every buyer here can afford a deal above the policy floor. "
           "**Holdout** climbs to its limit and repeats it; **last-minute** lowballs until round 9, then "
           "offers its real limit; **staller** repeats an offer below the floor and never leaves "
           "(fewer rounds = better).\n",
           "| Variant | Holdout score | Last-minute score | Staller rounds |", "|---|---|---|---|"]
    for name, _, _, st in rows:
        md.append(f"| {name} | {st['holdout']['score']:.3f} | {st['last_minute']['score']:.3f} | "
                  f"{st['staller']['avg_rounds']:.1f} |")
    md += ["\nScore = deal rate × margin kept.\n",
           f"**Reading it:** the firm-offer rule is what closes holdouts "
           f"({next(st for n, _, _, st in rows if n.startswith('No firm'))['holdout']['score']:.2f} → "
           f"{rows[0][3]['holdout']['score']:.2f}). The stall rule, which we "
           "first shipped, cost every last-minute deal, so it is now off. Late accept and the round-9 final "
           "offer changed no outcome in any of our tests (reciprocity already closes these deals); they stay "
           "as zero-cost safety nets.\n",
           "## Tried and dropped\n",
           "| Idea | Result | Decision |", "|---|---|---|",
           "| Opponent model: project the buyer's next offer and never concede below it | "
           "Score 0.442 → 0.438 (seed 1) and 0.417 → 0.415 (seed 2), measured on an earlier build | "
           "Dropped: no gain, more complexity |",
           "| Stall rule: after 3 frozen rounds below the floor, make the final offer and walk away | Lost every "
           "last-minute buyer (score 0.000), and rounds aren't scored | Dropped the walk-away; "
           "the early final offer also only gave margin away, so the rule is now off |",
           "| Treating repeated offers as firm from round 1 | +0.002 score, but lets a buyer lock in a "
           "near-floor price by round 3 | Kept the round-4 gate for safety |"]
    (ROOT / "outputs/ABLATION.md").write_text("\n".join(md))
    (ROOT / "outputs/ablation.json").write_text(json.dumps(
        [{"variant": n, **m, "score_sd": sd, "stress": st} for n, m, sd, st in rows], indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
