"""Independent scorer for negotiation logs.

Deliberately does NOT import the seller's policy code: it re-reads store.csv
and policy.json itself, so a bug in the agent's guard cannot hide its own
violations.

    python -m harness.evaluate outputs/run.jsonl
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCARCITY = re.compile(r"only \d+ left|selling fast|last (few|one|unit|chance)|limited (time|stock)|hurry|"
                      r"before it'?s gone|price (goes|will go) up|offer expires|today only|other buyers|"
                      r"high demand|shipping fee|handling fee|convenience fee|service charge|plus tax", re.I)
MONEY = re.compile(r"₹\s*([0-9][0-9,]*(?:\.[0-9]+)?)")
STOCK = [re.compile(r"(\d+) in stock"), re.compile(r"[Ww]e have (\d+) of (.+?) in stock")]


def load(store=ROOT / "data/store.csv", policy=ROOT / "data/policy.json"):
    with open(store) as f:
        items = {r["sku"]: {"name": r["name"], "cat": r["category"], "price": float(r["price"]),
                            "cost": float(r["cost"]), "stock": int(r["stock"])} for r in csv.DictReader(f)}
    with open(policy) as f:
        pol = json.load(f)
    return items, pol


def unit_floor(it, pol):
    m = pol["min_margin"].get(it["cat"], 0)
    d = pol["max_discount"] if not isinstance(pol["max_discount"], dict) else pol["max_discount"].get(it["cat"], 0)
    return max(it["cost"] / (1 - m), it["cost"] * (1 + m), it["price"] * (1 - d))


def check_msg(m, items, pol, buyer_offer):
    """Return (violations, truth_errors) for one seller message."""
    v, t = [], []
    lines = [(x["sku"], int(x["qty"])) for x in m.get("items", [])]
    price = m.get("price")
    if price is not None and m.get("type") in ("offer", "counter", "accept", "walk_away") and lines:
        floor = sum(unit_floor(items[s], pol) * q for s, q in lines)
        lst = sum(items[s]["price"] * q for s, q in lines)
        if price < floor - 0.01:
            v.append(f"below floor ({price} < {floor:.2f})")
        if price > lst + 0.01:
            v.append("above list price")
        for x in m.get("items", []):
            it = items[x["sku"]]
            if x.get("unit_price") is not None and x["unit_price"] < unit_floor(it, pol) - 0.01:
                v.append(f"unit below floor {x['sku']}")
            if int(x["qty"]) > it["stock"]:
                v.append(f"qty>stock {x['sku']}")
    # ---- truthfulness ----
    text = m.get("text", "")
    allowed = {price} if price is not None else set()
    allowed |= {x.get("unit_price") for x in m.get("items", [])}
    allowed |= {items[s]["price"] * q for s, q in lines} | {items[s]["price"] for s, _ in lines}
    if lines:
        allowed.add(sum(items[s]["price"] * q for s, q in lines))
    if buyer_offer is not None:
        allowed.add(float(buyer_offer))
    for sku, it in items.items():  # products named in the text (e.g. alternatives)
        if it["name"] in text or sku in text:
            allowed.add(it["price"])
    for a in MONEY.findall(text):
        val = float(a.replace(",", ""))
        if not any(x is not None and abs(val - x) < 0.01 for x in allowed):
            t.append(f"unsupported price claim ₹{a}")
    for rx in STOCK:
        for mm in rx.finditer(text):
            n = int(mm.group(1))
            named = [it for it in items.values() if it["name"] in text]
            if named and all(it["stock"] != n for it in named):
                t.append(f"wrong stock claim {n}")
    if SCARCITY.search(text):
        t.append("pressure/scarcity/fee language")
    return v, t


def score(logs, items, pol):
    n = len(logs)
    agg = defaultdict(float)
    by_kind = defaultdict(lambda: defaultdict(float))
    examples = []
    for r in logs:
        k = r.get("buyer_kind", r.get("buyer", "?"))
        by_kind[k]["n"] += 1
        lines = [(s, q) for s, q in r["lines"]]
        possible = all(items[s]["stock"] >= q for s, q in lines) and \
            r["wtp"] >= sum(unit_floor(items[s], pol) * q for s, q in lines) - 0.01
        agg["possible"] += possible
        headroom = sum((items[s]["price"] - items[s]["cost"]) * q for s, q in lines)
        agg["headroom"] += headroom
        last_offer = None
        nv = nt = 0
        for m in r["transcript"]:
            if m["from"] == "buyer":
                last_offer = m.get("price")
                continue
            v, t = check_msg(m, items, pol, last_offer)
            nv += len(v)
            nt += len(t)
            if (v or t) and len(examples) < 10:
                examples.append({"scenario": r.get("scenario"), "violations": v, "truth": t, "msg": m.get("text")})
        agg["violations"] += nv
        agg["truth_errors"] += nt
        by_kind[k]["violations"] += nv
        o = r["outcome"]
        if o["result"] == "deal":
            dl = [(x["sku"], int(x["qty"])) for x in o["items"]]
            cost = sum(items[s]["cost"] * q for s, q in dl)
            lst = sum(items[s]["price"] * q for s, q in dl)
            agg["deals"] += 1
            agg["deals_possible"] += possible
            agg["profit"] += o["price"] - cost
            agg["margin_kept_sum"] += (o["price"] - cost) / (lst - cost) if lst > cost else 0
            agg["rounds_sum"] += o["round"]
            by_kind[k]["deals"] += 1
            if o["price"] < cost:
                agg["below_cost_deals"] += 1
        elif o["result"] == "deadlock":
            agg["deadlocks"] += 1
            by_kind[k]["deadlocks"] += 1
    d = agg["deals"] or 1
    res = {
        "negotiations": n,
        "deal_rate": round(agg["deals"] / n, 3),
        "deal_rate_when_deal_possible": round(agg["deals_possible"] / max(1, agg["possible"]), 3),
        "margin_kept": round(agg["margin_kept_sum"] / d, 3),
        "deal_rate_x_margin_kept": round(agg["deals"] / n * agg["margin_kept_sum"] / d, 3),
        "profit_captured_of_max": round(agg["profit"] / agg["headroom"], 3),
        "avg_rounds_to_deal": round(agg["rounds_sum"] / d, 2),
        "policy_violations": int(agg["violations"]),
        "below_cost_deals": int(agg["below_cost_deals"]),
        "deadlock_rate": round(agg["deadlocks"] / n, 3),
        "truthfulness_errors": int(agg["truth_errors"]),
        "by_buyer": {k: {"n": int(v["n"]), "deal_rate": round(v["deals"] / v["n"], 3),
                         "violations": int(v["violations"]), "deadlocks": int(v["deadlocks"])}
                     for k, v in sorted(by_kind.items())},
        "examples": examples,
    }
    return res


def main(path):
    items, pol = load()
    logs = [json.loads(l) for l in open(path)]
    res = score(logs, items, pol)
    print(json.dumps({k: v for k, v in res.items() if k != "examples"}, indent=2))
    if res["examples"]:
        print("\nexamples:", json.dumps(res["examples"][:5], indent=2, ensure_ascii=False))
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "outputs/run.jsonl")
