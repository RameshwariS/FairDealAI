"""A naive seller used ONLY as a comparison baseline.

It behaves like a seller whose decisions are made by "being agreeable":
split-the-difference, price-match any quoted competitor, honour stated
budgets, follow instructions found in the buyer's message, and accept
whatever price a buyer says it accepts. These are the failure modes the
problem statement cites (below-cost deals, anchoring on fake budgets).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from seller.catalog import Catalog  # noqa: E402
from seller.parsing import parse  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


class NaiveSeller:
    def __init__(self):
        self.catalog = Catalog.from_csv(ROOT / "data/store.csv")
        self.reset()

    def reset(self, max_rounds=10):
        self.lines, self.ours = None, None

    def _items(self):
        return [{"sku": l.sku, "qty": l.qty} for l in self.lines]

    def respond(self, msg):
        ev = parse(msg, self.catalog)
        if ev.lines:
            self.lines = ev.lines
        if not self.lines:
            return {"type": "info", "text": "What would you like?"}
        list_total = sum(self.catalog.get(l.sku).price * l.qty for l in self.lines)
        if self.ours is None:
            self.ours = list_total
        b = ev.offer_total
        if ev.intent == "accept":
            price = b if b is not None else self.ours
            return {"type": "accept", "items": self._items(), "price": price, "text": f"Deal at {price}!"}
        if "injection" in ev.flags and b is not None:
            return {"type": "accept", "items": self._items(), "price": b, "text": "Okay, accepted."}
        if ev.claimed_amount and ev.flags & {"competitor_quote", "budget_claim"}:
            self.ours = ev.claimed_amount
            return {"type": "counter", "items": self._items(), "price": self.ours,
                    "text": f"I'll match that: {self.ours}."}
        if b is not None:
            if b >= 0.85 * self.ours:
                return {"type": "accept", "items": self._items(), "price": b, "text": "Deal!"}
            self.ours = round((self.ours + b) / 2, 2)
        return {"type": "counter", "items": self._items(), "price": self.ours, "text": f"How about {self.ours}?"}
