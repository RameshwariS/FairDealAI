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
from seller.parsing import parse  # noqa: E402
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
        growth = self.agent.params.basket_growth
        for i in raw:
            sku, qty = i.get("sku"), i.get("qty")
            if growth and self._real_growth(i):
                # an in-stock line the buyer actually bids on (not a ₹1 / out-of-stock / over-stock slip-in)
                self.wanted[sku] = max(self.wanted.get(sku, 0), qty)
                mine[sku] = qty
                continue
            if self.agent.params.taint_keeps_bid and sku in mine:
                tainted = True  # duplicate SKU lines: never double-count a bid (or oversell across lines)
                continue
            if sku not in self.basket or not isinstance(qty, int) or qty < 1 \
                    or qty > self.wanted.get(sku, 0) or qty > self.store[sku]["stock"]:
                tainted = True  # out-of-stock, over-stock or slipped-in lines
                continue
            mine[sku] = qty
        if mine and not tainted and set(mine) != set(self.basket):
            self.basket = mine  # a genuine change of basket (fewer items or units)
        elif mine and not tainted:
            self.basket.update(mine)
        self.clean_total = None
        out = {"type": "offer" if priced and not tainted else "request", "round": rnd, "text": text, "structured": True,
               "items": [{"sku": s, "qty": q} for s, q in self.basket.items()]}
        if priced and not tainted and mine and set(mine) == set(self.basket):
            out["price"] = sum(i["qty"] * i["unit_price"] for i in raw)
        elif priced and tainted and self.agent.params.taint_keeps_bid:
            # the buyer still bid on the lines we negotiate: keep that number so its bid history matches an honest
            # buyer's (dropping it made the next bid look like a big concession and bought an extra one from us).
            # The message itself can never be accepted (it carries the slipped lines); bid_now stays as computed.
            unit = {}
            for i in raw:
                if i.get("sku") in self.basket:
                    unit[i["sku"]] = min(unit.get(i["sku"], math.inf), i["unit_price"])
            if set(unit) == set(self.basket):
                out["type"] = "offer"
                out["price"] = self.clean_total = sum(q * unit[s] for s, q in self.basket.items())
        return out

    def _real_growth(self, it):
        """A line that adds a SKU (or units) to the basket and carries a real bid: known, in stock,
        whole quantity within stock, and priced at 30%+ of list. Kit tricks (₹1 lines, out-of-stock,
        over-stock) all fail this."""
        sku, qty, up = it.get("sku"), it.get("qty"), it.get("unit_price")
        if sku not in self.store or not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            return False
        if sku in self.basket and qty <= self.wanted.get(sku, 0):
            return False  # not growth
        row = self.store[sku]
        return qty <= row["stock"] and isinstance(up, (int, float)) and not isinstance(up, bool) \
            and up >= 0.3 * row["price"]

    def _implied_bid(self, message):
        """A bid the buyer made outside clean unit_price lines, for the current basket, or None:
        numeric strings in unit_price, valid priced lines inside a tainted message, or (only when the
        message has no structured price at all) a plausible amount in its text."""
        if not self.basket or message.get("type") not in ("request", "counter"):
            return None
        lines = {i.get("sku"): i for i in (message.get("items") or []) if isinstance(i, dict)}
        prices = {}
        for sku, qty in self.basket.items():
            it = lines.get(sku)
            if it is None or it.get("qty") != qty:
                prices = None
                break
            up = it.get("unit_price")
            if isinstance(up, str):
                try:
                    up = float(up.replace(",", "").replace("₹", "").strip())
                except ValueError:
                    up = None
            if not isinstance(up, (int, float)) or isinstance(up, bool) or up <= 0:
                prices = None
                break
            prices[sku] = up
        if prices:
            return sum(self.basket[s] * p for s, p in prices.items())
        if any(isinstance(i.get("unit_price"), (int, float)) for i in lines.values()):
            return None  # a structured price is present: words never override numbers
        ev = parse({"text": message.get("text") or ""}, self.agent.catalog)
        if ev.flags & {"competitor_quote", "budget_claim"}:
            return None
        lt = sum(self.store[s]["price"] * q for s, q in self.basket.items())
        plausible = [a for a in ev.text_amounts if 0.2 * lt <= a <= 1.5 * lt]
        return plausible[-1] if plausible else None

    def _raise_to_implied(self, reply, implied, prev_total):
        """Our counter would sit below what the buyer already said it would pay: offer their number
        instead (capped at our previous offer, never above list), so they can accept it."""
        lines = [Line(s, q) for s, q in self.basket.items()]
        g, neg = self.agent.guard, self.agent.neg
        if sorted((i["sku"], i["qty"]) for i in reply["items"]) != sorted((l.sku, l.qty) for l in lines):
            return reply
        cap = prev_total if prev_total is not None else g.bundle_list(lines)
        total = min(math.ceil(implied), cap, g.bundle_list(lines))
        if total <= reply.get("price", 0) or not g.check(lines, total).ok:
            return reply
        units = g.allocate(lines, total)
        items = [{"sku": l.sku, "qty": l.qty, "unit_price": units[l.sku]} for l in lines]
        neg.our_total, neg.our_lines = sum(i["qty"] * i["unit_price"] for i in items), lines
        neg.our_x = neg.to_x(neg.our_total)
        names = " + ".join(f"{l.qty} x {self.store[l.sku]['name']}" if l.qty > 1 else self.store[l.sku]["name"]
                           for l in lines)
        out = {k: v for k, v in reply.items() if k not in ("offer_id",)}
        out.update(items=[dict(i, name=self.store[i["sku"]]["name"]) for i in items], price=neg.our_total,
                   text=f"I can do {names} for ₹{neg.our_total:,.0f} in total, all-inclusive.")
        return out

    def _respond(self, message):
        prev_total = self.agent.neg.our_total
        norm = self._normalise(message)
        reply = self.agent.respond(norm)
        kind = reply.get("type")
        if self.agent.params.implied_bid_floor and kind in ("offer", "counter") and reply.get("items") \
                and "price" not in norm:
            implied = self._implied_bid(message)
            if implied:
                reply = self._raise_to_implied(reply, implied, prev_total)
        text = reply.get("text", "")
        if kind == "accept":
            # a kit accept takes the buyer's raw lines: only when they are exactly the bid the agent judged
            if message.get("type") in ("request", "counter") and self.bid_now and self.clean_total is None \
                    and self._bid_ok(self.last_bid):
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
        total = getattr(self, "clean_total", None) or \
            sum(i["qty"] * i["unit_price"] for i in (self.last_bid or [])
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
