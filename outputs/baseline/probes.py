"""Stage-1 probes: scripted buyer messages through fairdeal_seller.Seller (the kit adapter)."""
import sys
from pathlib import Path
ROOT = Path("/media/shruti/3E2AA2792AA22E39/web_dev/fairdeal")
sys.path.insert(0, str(ROOT / "ps2-selling-to-machines"))
from harness import load_store, load_policy, floor_price
sys.path.append(str(ROOT))
from fairdeal_seller import Seller

st, po = load_store(), load_policy()
SKU = next(s for s, r in sorted(st.items()) if r["stock"] >= 5 and r["price"] > 2000)
SKU2 = next(s for s, r in sorted(st.items()) if r["stock"] >= 5 and r["price"] > 1000 and s != SKU)
L, F = st[SKU]["price"], floor_price(st[SKU], po)
print(f"probe sku {SKU}: list {L} floor {F}; sku2 {SKU2}: list {st[SKU2]['price']} floor {floor_price(st[SKU2], po)}\n")


def play(name, script):
    """script: list of buyer messages (round added automatically). Stops on seller accept/walk."""
    s = Seller(st, po); s.start(name)
    print(f"--- {name}")
    for r, m in enumerate(script, 1):
        out = s.respond(dict(m, round=r))
        its = [(i["sku"], i["qty"], i["unit_price"]) for i in out.get("items", [])]
        tot = sum(q * p for _, q, p in its)
        bid = sum(i["qty"] * i["unit_price"] for i in m.get("items", []) if isinstance(i.get("unit_price"), (int, float)))
        print(f"  r{r:<2} buyer {m['type']:8} bid {bid or '-':>8} | seller {out['type']:9} total {round(tot) or '-':>7} "
              f"{'(final)' if out.get('final') else ''} {s.agent.log[-1]['reason'] if s.agent.log else ''}")
        if out["type"] in ("accept", "walk_away"):
            return out
    return out


one = lambda p, q=1, sku=None: {"sku": sku or SKU, "qty": q, "unit_price": p}
req = {"type": "request", "items": [{"sku": SKU, "qty": 1}], "text": "hi"}
x = lambda frac: int(F + frac * (L - F))           # price at a headroom fraction

# (c) fewer than 3 numeric bids: buyer only bids in rounds 9 and 10, above floor-ish
play("c1: only 2 numeric bids (r9, r10), r10 bid just below floor",
     [req] + [{"type": "request", "items": [{"sku": SKU, "qty": 1}], "text": "what's your best?"}] * 7
     + [{"type": "counter", "items": [one(F - 40)]}, {"type": "counter", "items": [one(F - 5)]}])
play("c2: identical repeated price below floor every round",
     [{"type": "request", "items": [one(int(0.6 * L))]}] + [{"type": "counter", "items": [one(int(0.6 * L))]}] * 9)
# (d) repeated feasible offer (buyer never moves)
play("d1: repeats a feasible bid (x=0.3) every round",
     [{"type": "request", "items": [one(x(0.3))]}] + [{"type": "counter", "items": [one(x(0.3))]}] * 9)
play("d2: repeats a bid just under floor; does the seller keep conceding?",
     [{"type": "request", "items": [one(F - 20)]}] + [{"type": "counter", "items": [one(F - 20)]}] * 9)
# late sniper: flat low, jumps on 8-10
play("late sniper: flat at 0.55*list, then jumps at r8-10 to x=0.5",
     [{"type": "request", "items": [one(int(0.55 * L))]}] + [{"type": "counter", "items": [one(int(0.55 * L))]}] * 6
     + [{"type": "counter", "items": [one(x(0.2))]}, {"type": "counter", "items": [one(x(0.4))]},
        {"type": "counter", "items": [one(x(0.5))]}])
# (g) quantity change mid-negotiation
play("g1: 3 units, drops to 2 at r7 (late basket change)",
     [{"type": "request", "items": [one(int(0.6 * L), 3)]}]
     + [{"type": "counter", "items": [one(int((0.6 + 0.02 * k) * L), 3)]} for k in range(1, 6)]
     + [{"type": "counter", "items": [one(int((0.72 + 0.01 * k) * L), 2)]} for k in range(4)])
play("g2: drops SKU2 at r3, then asks for it back at r5",
     [{"type": "request", "items": [one(int(0.7 * L)), one(int(0.7 * st[SKU2]['price']), 1, SKU2)]},
      {"type": "counter", "items": [one(int(0.72 * L)), one(int(0.72 * st[SKU2]['price']), 1, SKU2)]},
      {"type": "counter", "items": [one(int(0.75 * L))]},
      {"type": "counter", "items": [one(int(0.77 * L))]},
      {"type": "counter", "items": [one(int(0.85 * L)), one(int(0.85 * st[SKU2]['price']), 1, SKU2)]},
      {"type": "counter", "items": [one(int(0.9 * L)), one(int(0.9 * st[SKU2]['price']), 1, SKU2)]}])
play("g3: honest bundle hunter asks for MORE units (1 -> 3) at r3",
     [{"type": "request", "items": [one(int(0.7 * L))]}, {"type": "counter", "items": [one(int(0.75 * L))]},
      {"type": "counter", "items": [one(int(0.85 * L), 3)]}, {"type": "counter", "items": [one(int(0.9 * L), 3)]}])
# (h) natural-language-only bids (text_offers=False)
play("h1: bids only in text (items without unit_price), generous amount",
     [req] + [{"type": "counter", "items": [{"sku": SKU, "qty": 1}], "text": f"I can pay ₹{int(0.97 * L)} for it."}] * 4)
play("h2: unit_price as a string",
     [req] + [{"type": "counter", "items": [{"sku": SKU, "qty": 1, "unit_price": str(int(0.97 * L))}]}] * 3)
# (e) buyer counters our round-10 offer
play("e1: buyer moving slowly; what does seller send in r10?",
     [{"type": "request", "items": [one(int(0.55 * L))]}]
     + [{"type": "counter", "items": [one(int((0.55 + 0.02 * k) * L))]} for k in range(1, 10)])
