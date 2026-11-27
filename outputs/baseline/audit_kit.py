"""Stage-1 audit: replay the official kit (seeds 0-6) in-process and measure suspected failure modes."""
import json, random, sys, collections
from pathlib import Path
ROOT = Path("/media/shruti/3E2AA2792AA22E39/web_dev/fairdeal")
KIT = ROOT / "ps2-selling-to-machines"
sys.path.insert(0, str(KIT))
import buyers as kb, evaluate as ev
from harness import load_store, load_policy, floor_price, run_negotiation
sys.path.append(str(ROOT))
from fairdeal_seller import Seller

st, po = load_store(), load_policy()
C = collections.Counter
agg = C(); per = collections.defaultdict(C)
examples = collections.defaultdict(list)
out = open(ROOT / "outputs/baseline/audit_transcripts.jsonl", "w")

for seed in range(7):
    scs = kb.make_scenarios(st, po, 210, seed)
    seller = Seller(st, po)
    for sc in scs:
        b = kb.BUYERS[sc["buyer"]](sc, st, random.Random(sc["seed"]))
        res = run_negotiation(seller, b, st, po, sc["id"])
        row = ev.score_one(res, sc, st, po)
        out.write(json.dumps({"seed": seed, **row, "scenario": sc, "transcript": res["transcript"]}) + "\n")
        T = res["transcript"]; who = sc["buyer"]
        sl = [(st[i["sku"]], min(i["qty"], st[i["sku"]]["stock"])) for i in sc["items"]]
        top = sum(r["price"] * q for r, q in sl)
        res_total = sc["reservation"] * top
        sells = [m for m in T if m["from"] == "seller"]
        bids = [m for m in T if m["from"] == "buyer" and m["type"] in ("request", "counter")]
        tag = lambda k: (agg.update([k]), per[who].update([k]))
        tag("n")
        if row["feasible"]: tag("feasible")
        if res["ended"] == "deadlock":
            tag("deadlock"); examples["deadlock"].append((seed, sc["id"], who))
        last = sells[-1] if sells else None
        # (e) seller offer on round 10 -> outcome
        if last and last["round"] == 10 and last["type"] == "offer":
            tag("r10_offer"); tag("r10_offer_" + res["ended"])
        # (c) round-10 walk-aways in feasible scenarios (lost deals)
        if res["ended"] == "seller_walked" and row["feasible"]:
            tag("walk_feasible"); examples["walk_feasible"].append((seed, sc["id"], who, last["round"]))
            # how many clean numeric bids did the buyer make?
        # (d) money left on table: deal price vs buyer's limit for the dealt lines
        if row["deal"]:
            tot = sum(i["qty"] * i["unit_price"] for i in row["deal"])
            lim = sc["reservation"] * sum(st[i["sku"]]["price"] * i["qty"] for i in row["deal"])
            flo = sum(floor_price(st[i["sku"]], po) * i["qty"] for i in row["deal"])
            if lim > flo:
                per[who]["surplus_share_x1000"] += int(1000 * max(0, lim - tot) / (lim - flo))
                per[who]["deals_scored"] += 1
            if tot <= flo * 1.005: tag("deal_at_floor")
        # neg-001 pattern: we offered a total BELOW a buyer's earlier per-line bid on the same lines
        for k, m in enumerate(T):
            if m["from"] != "seller" or m["type"] != "offer": continue
            prev_b = [x for x in T[:k] if x["from"] == "buyer" and x.get("items")]
            if not prev_b: continue
            our = {i["sku"]: (i["qty"], i["unit_price"]) for i in m["items"]}
            best = 0
            for pb in prev_b:
                lines = {i.get("sku"): i for i in pb["items"] if isinstance(i, dict)}
                if all(s in lines and isinstance(lines[s].get("unit_price"), (int, float)) for s in our):
                    best = max(best, sum(our[s][0] * lines[s]["unit_price"] for s in our))
            ours = sum(q * p for q, p in our.values())
            if best > ours + 0.5:
                tag("offer_below_buyer_bid"); per[who]["rupees_below_bid"] += int(best - ours)
                examples["offer_below_buyer_bid"].append((seed, sc["id"], who, m["round"], round(best), round(ours)))
                break
        # tainted bids (slipped lines) – their numbers never reach the engine
        for m in bids[1:]:
            skus = {i.get("sku") for i in m.get("items") or []}
            if any(s not in {i["sku"] for i in sc["items"]} or
                   any(i.get("qty", 0) > st.get(i.get("sku"), {"stock": 0})["stock"] for i in m["items"]) for s in skus):
                tag("tainted_bid_msgs")

print("ALL SEEDS:", dict(agg))
for w, c in per.items():
    d = dict(c)
    if c["deals_scored"]:
        d["avg_buyer_surplus_left_share"] = round(c["surplus_share_x1000"] / c["deals_scored"] / 1000, 3)
    print(w, d)
for k, v in examples.items():
    print(k, len(v), v[:8])
