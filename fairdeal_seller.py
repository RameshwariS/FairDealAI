"""FairDeal AI as a starter-kit seller.

    cd ps2-selling-to-machines
    python evaluate.py --seller ../fairdeal_seller.py
    python harness.py --seller ../fairdeal_seller.py --buyer manipulator --seed 3

This file only translates between the kit's message format and the agent in seller/.
All pricing, policy and truth checks happen in the agent; this adapter adds one more
gate the kit's rules need: an `accept` takes the buyer's exact last priced lines, so it
is only sent when every one of those lines is within policy.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))  # append: the kit has its own harness.py

from seller import SellerAgent  # noqa: E402
from seller import traceware  # noqa: E402
from seller.policy import Line  # noqa: E402


class Seller:
    def __init__(self, store, policy):
        self.store, self.kit_policy = store, policy
        # the kit defines margin on price: unit_price >= cost / (1 - min_margin)
        # bids arrive as structured unit_price lines, so prices written in the text are never read as offers
        self.agent = SellerAgent(store, policy, margin_basis="price", text_offers=False)
        self.max_rounds = int(policy.get("max_rounds", 10))

    # ---------------------------------------------------------------- kit interface
    def start(self, negotiation_id):
        self.negotiation_id = str(negotiation_id)
        self.agent.reset(max_rounds=self.max_rounds)
        self.basket = None    # {sku: qty} we are negotiating
        self.wanted = {}      # what the buyer first asked for
        self.last_bid = None  # buyer's last fully priced lines (what an accept would take)

    def respond(self, message):
        try:
            return self._verified(self._respond(message))
        except Exception:  # never crash a turn: say nothing binding instead
            return {"type": "message", "text": "Sorry, could you repeat that?"}

    # ---------------------------------------------------------------- Rezolve Labs TraceWare
    def _verified(self, reply):
        """Check the reply's claims against what we actually did (TraceWare); rewrite if it blocks."""
        kind = reply.get("type")
        items = reply.get("items") if kind == "offer" else (self.last_bid if kind == "accept" else None)
        if not items:
            return reply
        decision = traceware.verify(reply.get("text", ""), items, self.store, self.negotiation_id)
        reply.setdefault("verification", {"traceware": decision})  # None when the service is off
        if decision in ("REGENERATE", "BLOCK"):
            reply["text"] = self._plain_text(kind, items)
        return reply

    def _plain_text(self, kind, items):
        lines = ", ".join(f"{i['qty']} x {self.store[i['sku']]['name']} ({i['sku']}) at ₹{i['unit_price']:,.0f} each"
                          for i in items if i.get("sku") in self.store)
        return f"Deal: {lines}." if kind == "accept" else f"I can offer {lines}."

    # ---------------------------------------------------------------- translation
    def _floor(self, sku):
        row = self.store[sku]
        margin = self.kit_policy["min_margin"][row["category"]]
        return max(row["cost"] / (1 - margin), row["price"] * (1 - self.kit_policy["max_discount"]))

    def _line_ok(self, it):
        """Same rules as harness.check_items, for one line."""
        if not isinstance(it, dict) or it.get("sku") not in self.store:
            return False
        row, qty, price = self.store[it["sku"]], it.get("qty"), it.get("unit_price")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1 or qty > row["stock"]:
            return False
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            return False
        return self._floor(it["sku"]) <= price <= row["price"]

    def _bid_ok(self, bid):
        return isinstance(bid, list) and bool(bid) and all(self._line_ok(i) for i in bid)

    def _normalise(self, message):
        """Kit message -> the agent's message. Buyer-slipped lines never enter the basket."""
        t = message.get("type")
        rnd = message.get("round")
        text = message.get("text") or ""
        self.bid_now = False
        if t in ("accept", "walk_away"):
            return {"type": t, "round": rnd, "text": text, "structured": True}
        raw = [i for i in (message.get("items") or []) if isinstance(i, dict)]
        priced = bool(raw) and all(isinstance(i.get("unit_price"), (int, float)) for i in raw)
        self.bid_now = priced  # this message carries a fully priced bid (what an accept would take)
        if priced:
            self.last_bid = raw
        if self.basket is None:  # the opening request fixes what is being negotiated
            self.wanted = {i["sku"]: i["qty"] for i in raw
                           if i.get("sku") in self.store and isinstance(i.get("qty"), int) and i["qty"] >= 1}
            self.basket = dict(self.wanted)
        mine, tainted = {}, False
        for i in raw:
            sku, qty = i.get("sku"), i.get("qty")
            if sku not in self.basket or not isinstance(qty, int) or qty < 1 \
                    or qty > self.wanted.get(sku, 0) or qty > self.store[sku]["stock"]:
                tainted = True  # out-of-stock, over-stock or slipped-in lines
                continue
            mine[sku] = qty
        if mine and not tainted and set(mine) != set(self.basket):
            self.basket = mine  # a genuine change of basket (fewer items or units)
        elif mine and not tainted:
            self.basket.update(mine)
        out = {"type": "offer" if priced and not tainted else "request", "round": rnd, "text": text, "structured": True,
               "items": [{"sku": s, "qty": q} for s, q in self.basket.items()]}
        if priced and not tainted and mine and set(mine) == set(self.basket):
            out["price"] = sum(i["qty"] * i["unit_price"] for i in raw)
        return out

    def _respond(self, message):
        reply = self.agent.respond(self._normalise(message))
        kind = reply.get("type")
        text = reply.get("text", "")
        if kind == "accept":
            if message.get("type") in ("request", "counter") and self.bid_now and self._bid_ok(self.last_bid):
                return {"type": "accept", "text": text}
            return self._split_their_total(message, text)
        if kind in ("offer", "counter") and reply.get("items"):
            return {"type": "offer", "text": text, "items": self._kit_items(reply["items"]),
                    **{k: reply[k] for k in ("offer_id", "claims", "alternatives", "final") if k in reply}}
        if kind == "walk_away":
            return {"type": "walk_away", "text": text}
        return {"type": "message", "text": text}

    def _kit_items(self, items):
        out = []
        for i in items:
            up = i.get("unit_price")
            up = math.ceil(up * 100) / 100 if isinstance(up, float) else up
            out.append({"sku": i["sku"], "qty": int(i["qty"]), "unit_price": up})
        return out

    def _split_their_total(self, message, text):
        """The agent would take the buyer's total, but one of its lines breaks policy on its own.
        Offer the same total split so every line clears its floor; the buyer's own number, so it can say yes."""
        lines = [Line(s, q) for s, q in self.basket.items()]
        total = sum(i["qty"] * i["unit_price"] for i in (self.last_bid or [])
                    if isinstance(i, dict) and i.get("sku") in self.basket
                    and isinstance(i.get("unit_price"), (int, float)))
        g = self.agent.guard
        if not lines or not total or not g.check(lines, total).ok:
            total = self.agent.neg.our_total
            if total is None:
                return {"type": "message", "text": "Which product and how many would you like?"}
        units = g.allocate(lines, total)
        items = [{"sku": l.sku, "qty": l.qty, "unit_price": units[l.sku]} for l in lines]
        neg = self.agent.neg
        neg.closed, self.agent.done = False, False
        if not self.agent.persist_stock:
            self.agent.guard.sold = {}  # the agent booked the stock for a sale that didn't happen
        neg.our_total, neg.our_lines = sum(i["qty"] * i["unit_price"] for i in items), lines
        names = " + ".join(f"{l.qty} x {self.store[l.sku]['name']}" if l.qty > 1 else self.store[l.sku]["name"]
                           for l in lines)
        return {"type": "offer", "items": items,
                "text": f"I can do {names} for ₹{neg.our_total:,.0f} in total, all-inclusive."}
