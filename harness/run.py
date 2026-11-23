"""Turn-based negotiation harness (max 10 rounds) -- local stand-in for the kit's harness.py.

    python -m harness.run --n 200 --out outputs/run.jsonl
    python -m harness.run --seller naive          # baseline for comparison

Each round: buyer sends a JSON message, seller replies. A deal happens only
when the seller sends type="accept". Every message is logged.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seller import SellerAgent  # noqa: E402
from harness.buyers import CooperativeBuyer, HardBargainer, Manipulator, PersonaBuyer  # noqa: E402
from harness.naive_seller import NaiveSeller  # noqa: E402

MAX_ROUNDS = 10


def make_scenarios(catalog, n, seed=42):
    rng = random.Random(seed)
    in_stock = [p for p in catalog.products.values() if p.stock > 0]
    every = list(catalog.products.values())
    out = []
    for i in range(n):
        r = rng.random()
        if r < 0.65:
            p = rng.choice(in_stock)
            lines = [(p.sku, 1)]
        elif r < 0.80:
            p = rng.choice([x for x in in_stock if x.stock >= 2])
            lines = [(p.sku, rng.randint(2, min(3, p.stock)))]
        elif r < 0.95:
            a, b = rng.sample(in_stock, 2)
            lines = [(a.sku, 1), (b.sku, 1)]
        else:
            p = rng.choice(every)  # may be out of stock / over stock
            lines = [(p.sku, rng.randint(1, 4))]
        list_total = sum(catalog.get(s).price * q for s, q in lines)
        wtp = list_total * rng.uniform(0.65, 1.05)
        out.append({"id": i, "lines": lines, "list_total": list_total, "wtp": round(wtp, 2),
                    "seed": rng.randint(0, 10**9)})
    return out


def make_buyer(kind, sc, catalog):
    rng = random.Random(sc["seed"])
    args = (list(sc["lines"]), sc["list_total"], sc["wtp"])
    if kind == "cooperative":
        return CooperativeBuyer(*args, rng)
    if kind == "hard_bargainer":
        return HardBargainer(*args, rng)
    if kind == "manipulator":
        return Manipulator(*args, rng)
    return PersonaBuyer(*args, rng, catalog=catalog)


def negotiate(seller, buyer, max_rounds=MAX_ROUNDS):
    seller.reset(max_rounds=max_rounds) if hasattr(seller, "reset") else None
    transcript, outcome, last = [], {"result": "deadlock"}, None
    for rnd in range(1, max_rounds + 1):
        b = buyer.act(rnd, last)
        b = {**b, "round": rnd, "max_rounds": max_rounds}
        transcript.append({"from": "buyer", **b})
        if b.get("type") == "walk_away":
            outcome = {"result": "buyer_walked", "round": rnd}
            break
        s = seller.respond(json.loads(json.dumps(b)))  # seller only ever sees plain JSON
        transcript.append({"from": "seller", **s})
        last = s
        if s.get("type") == "accept":
            outcome = {"result": "deal", "round": rnd, "price": s.get("price"), "items": s.get("items")}
            break
        if s.get("type") in ("walk_away", "end"):
            outcome = {"result": "seller_walked", "round": rnd}
            break
    res = {"buyer": buyer.name, "wtp": buyer.wtp, "outcome": outcome, "transcript": transcript}
    if hasattr(seller, "log"):  # what the seller detected and why it decided, per turn
        res["seller_log"] = [e for e in seller.log if "round" in e]
    return res


def run(seller_kind="fairdeal", n=200, seed=42, out=None, buyers=None, quiet=False, params=None):
    agent = SellerAgent(params=params) if seller_kind == "fairdeal" else NaiveSeller()
    catalog = agent.catalog
    scenarios = make_scenarios(catalog, n, seed)
    buyers = buyers or ["cooperative", "hard_bargainer", "manipulator", "persona"]
    weights = {"cooperative": 1, "hard_bargainer": 1, "manipulator": 1, "persona": 3}
    rng = random.Random(seed + 1)
    logs = []
    for sc in scenarios:
        kind = rng.choices(buyers, weights=[weights.get(b, 1) for b in buyers])[0]
        res = negotiate(agent, make_buyer(kind, sc, catalog))
        res.update({"scenario": sc["id"], "buyer_kind": kind, "lines": sc["lines"],
                    "list_total": sc["list_total"]})
        logs.append(res)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            for r in logs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        if not quiet:
            print(f"wrote {len(logs)} negotiations to {out}")
    return logs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seller", default="fairdeal", choices=["fairdeal", "naive"])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--buyers", nargs="*")
    ap.add_argument("--out", default="outputs/run.jsonl")
    a = ap.parse_args()
    run(a.seller, a.n, a.seed, a.out, a.buyers)
