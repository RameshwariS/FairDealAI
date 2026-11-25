"""Deterministic negotiation engine.

All money decisions are made here, in plain code. Prices are expressed in a
normalised "headroom" scale so one strategy works for a Rs 99 book and a
Rs 25,000 speaker:

    x = (price - floor) / (list - floor)      x = 1 -> list price, x = 0 -> policy floor

Strategy = time-based (Boulware) concession + reciprocity + an "accept-next"
rule, with a hard walk-away on the final turn. Nothing a buyer *says* (budget,
competitor quote, deadline, "I'm the manager") moves the price; only what a
buyer *offers* does. That is what makes the agent manipulation-proof and fair:
two buyers who make the same offers get the same answers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .policy import Line, PolicyGuard, ceil2


@dataclass
class Params:
    # defaults tuned against the starter kit's evaluate.py on seeds 0-2; checked on held-out seeds 3-6
    open_single: float = 0.90      # open 10% of the headroom under list for a single unit
    open_bundle: float = 0.80      # bundles / multi-unit open with a real discount
    end_x: float = 0.15            # where the time curve ends (keep 15% of headroom; the projection does the rest)
    boulware: float = 1.2          # >1 = concede slowly early, faster near the deadline
    reciprocity: float = 0.6       # share of the buyer's concession we mirror
    close_gap: float = 0.06        # accept if the buyer is this close (in x units)
    close_gap_abs: float = 0.015   # ... or within 1.5% of list total
    stall_rounds: int = 99         # off: an early 'final offer' to a staller only gave margin away (see ABLATION.md)
    stall_walk: bool = False       # walk away early from a staller (off: rounds aren't scored, late deals are)
    max_rounds: int = 10
    project_limit: bool = True     # round-9 offer = the buyer's projected limit (see projected_limit)
    project_margin: float = 0.02   # aim this far (x units) under the projection so the buyer can say yes
    firm_from_round: int = 4       # only treat repeated offers as 'firm' from this round on
    late_accept: bool = True       # on rounds 9-10, take any offer that clears the policy floor
    final_offer: bool = True       # round 9 offer = our real best (end_x)
    lowball_clip: float = -1.5     # offers below this (in x units) count as this when measuring buyer moves
    max_recip_step: float = 0.12   # most we concede in one round because the buyer moved
    min_step: float = 0.03         # smallest per-round concession (x units) above end_x
    price_step: float = 1.0        # quote whole rupees (always rounded UP)


@dataclass
class Decision:
    action: str                    # "offer" | "counter" | "accept" | "walk_away" | "info"
    lines: list = field(default_factory=list)
    total: float | None = None
    final: bool = False            # True when this is our last offer
    reason: str = ""


class Negotiation:
    def __init__(self, guard: PolicyGuard, params: Params | None = None):
        self.g = guard
        self.p = params or Params()
        self.lines: list[Line] = []
        self.our_x: float | None = None          # our last offer, in x units
        self.our_total: float | None = None
        self.our_lines: list[Line] = []
        self.buyer_x: list[float] = []           # buyer offers on the current basket
        self.buyer_rounds: list[int] = []        # the round each of those offers came in
        self.closed = False

    # ---------- helpers ----------
    def _bounds(self):
        f, l = self.g.bundle_floor(self.lines), self.g.bundle_list(self.lines)
        return f, max(l, f + 0.01)

    def to_x(self, total: float) -> float:
        f, l = self._bounds()
        return (total - f) / (l - f)

    def to_total(self, x: float) -> float:
        f, l = self._bounds()
        x = min(1.0, max(0.0, x))
        raw = f + x * (l - f)
        step = self.p.price_step
        stepped = math.ceil(round(raw / step, 6)) * step  # ceil -> never below floor
        return round(min(l, stepped), 2) if stepped <= l else ceil2(raw)

    def is_bundle(self) -> bool:
        return len(self.lines) > 1 or any(l.qty > 1 for l in self.lines)

    def set_basket(self, lines: list[Line]):
        key = sorted((l.sku, l.qty) for l in lines)
        if key != sorted((l.sku, l.qty) for l in self.lines):
            self.lines = lines
            self.buyer_x = []  # buyer history is basket-specific
            self.buyer_rounds = []
            # keep our concession progress (x) so changing the basket is not a reset trick

    def _time_x(self, rnd: int) -> float:
        t = min(1.0, max(0.0, (rnd - 1) / max(1, self.p.max_rounds - 2)))
        start = self.p.open_bundle if self.is_bundle() else self.p.open_single
        return start - (start - self.p.end_x) * (t ** self.p.boulware)

    def projected_limit(self):
        """Where the buyer's offers are heading by the last round, in x units.

        Fits offers to  x(r) = a + (L - a) * (r / T) ** e  for a few curve shapes e (a buyer that
        concedes evenly, early or late) and returns L from the best fit. Needs 3+ offers on this
        basket. Only ever used to LOWER our round-9 offer toward a price the buyer can reach."""
        pts = list(zip(self.buyer_rounds, self.buyer_x))
        if len(pts) < 3:
            return None
        T = float(self.p.max_rounds)
        best = None
        for e in (0.5, 0.7, 1.0, 1.5, 2.0, 2.5, 3.0):
            # an offer that arrives in round r answers our round r-1 message, so it shows the buyer at time r-1
            xs = [min(1.0, max(0, r - 1) / T) ** e for r, _ in pts]
            ys = [y for _, y in pts]
            # least squares for y = a (1 - x) + L x
            s11 = sum((1 - x) ** 2 for x in xs)
            s12 = sum((1 - x) * x for x in xs)
            s22 = sum(x * x for x in xs)
            b1 = sum((1 - x) * y for x, y in zip(xs, ys))
            b2 = sum(x * y for x, y in zip(xs, ys))
            det = s11 * s22 - s12 * s12
            if abs(det) < 1e-12:
                continue
            a = (b1 * s22 - b2 * s12) / det
            L = (s11 * b2 - s12 * b1) / det
            err = sum((a * (1 - x) + L * x - y) ** 2 for x, y in zip(xs, ys))
            if best is None or err < best[0]:
                best = (err, L)
        if best is None:
            return None
        return max(best[1], max(self.buyer_x))  # never predict a limit below what they already offered

    def _firm_repeats(self) -> int:
        """How many times in a row the buyer has repeated (within 0.5%) the same offer."""
        n = 0
        for a, b in zip(reversed(self.buyer_x[:-1]), reversed(self.buyer_x[1:])):
            if abs(a - b) <= 0.005 * self._scale():
                n += 1
            else:
                break
        return n

    def _scale(self) -> float:
        f, l = self._bounds()
        return l / (l - f)  # 0.5% of list price, expressed in x units

    def _stalling(self) -> bool:
        k = self.p.stall_rounds
        if len(self.buyer_x) < k + 1:
            return False
        recent = self.buyer_x[-(k + 1):]
        return max(recent) - min(recent) < 0.01 and recent[-1] < 0

    # ---------- main step ----------
    def step(self, rnd: int, offer_total: float | None) -> Decision:
        if not self.lines:
            return Decision("info", reason="no basket yet")
        chk = self.g.check(self.lines, self.g.bundle_floor(self.lines))
        if not chk.ok:  # out of stock / unknown sku: nothing can be sold
            return Decision("info", reason="; ".join(chk.reasons))

        last_turn = rnd >= self.p.max_rounds
        penultimate = rnd == self.p.max_rounds - 1

        if offer_total is not None:
            self.buyer_x.append(self.to_x(offer_total))
            self.buyer_rounds.append(rnd)
        bx = self.buyer_x[-1] if offer_total is not None else None  # this turn's offer only

        # what we would say next if we countered
        target = self._time_x(rnd)
        if self.our_x is not None and len(self.buyer_x) >= 2:
            # measured against their best earlier offer, so a fake lowball can't manufacture a "concession"
            # absurd lowballs (e.g. ₹1) are clipped, so "₹1 then a real offer" can't fake a giant concession
            prev = max(max(self.buyer_x[:-1]), self.p.lowball_clip)
            buyer_move = max(0.0, self.buyer_x[-1] - prev)
            target = min(target, self.our_x - min(self.p.max_recip_step, self.p.reciprocity * buyer_move))
        if self.our_x is not None:
            target = min(target, self.our_x)       # never go back up
            if self.our_x > self.p.end_x:          # always visibly move while we still have room
                target = min(target, max(self.p.end_x, self.our_x - self.p.min_step))
        target = max(target, 0.0)
        firm = self._firm_repeats() if rnd >= self.p.firm_from_round else 0
        if firm >= 1 and bx is not None and bx >= 0 and self.our_x is not None:
            # buyer is holding a feasible offer: meet them halfway (their offers, not their words, move us)
            target = min(target, max(bx, (self.our_x + bx) / 2))
        if penultimate and self.p.final_offer:
            target = max(0.0, min(target, self.p.end_x))  # final offer: our real best
            # meet the buyer where its own concessions say it will be at the deadline (never below floor)
            limit = self.projected_limit() if self.p.project_limit else None
            if limit is not None:
                target = max(0.0, min(target, limit - self.p.project_margin))
        next_total = self.to_total(target)

        # ---- accept? (only ever accept an offer that passes the guard) ----
        if bx is not None and self.g.check(self.lines, offer_total).ok:
            our_last = self.our_x if self.our_x is not None else 1.0
            list_total = self._bounds()[1]
            if (offer_total >= next_total
                    or (firm >= 2 and bx >= 0)          # held a feasible offer 3 times: take it
                    or our_last - bx <= self.p.close_gap
                    or (self.our_total is not None and self.our_total - offer_total <= self.p.close_gap_abs * list_total)
                    or next_total - offer_total <= self.p.close_gap_abs * list_total  # our counter would be ~their offer
                    or (self.p.late_accept and (last_turn or (penultimate and bx >= 0)))):
                return self._close("accept", offer_total, "buyer offer acceptable")

        # ---- final turn: we must not leave it open (deadlock = lost points) ----
        if last_turn:
            limit = self.projected_limit() if self.p.project_limit else None
            if limit is not None and limit >= 0:
                # their own concessions say they can reach a price we may sell at: one last offer
                x = max(0.0, min(self.our_x if self.our_x is not None else 1.0, limit - self.p.project_margin))
                return self._offer(x, self.to_total(x), final=True, reason="last offer at projected limit")
            return Decision("walk_away", self.lines, self.to_total(0.0), reason="final round, buyer below floor")

        # ---- stalling far below floor: give a final offer once, then walk ----
        if self._stalling():
            if self.p.stall_walk and self.our_x is not None and self.our_x <= self.p.end_x + 1e-9:
                return Decision("walk_away", self.lines, self.our_total, reason="buyer stalled below floor")
            # hold our best price instead of leaving: a lowballer may still come up on rounds 9-10
            target = min(target, self.p.end_x)
            next_total = self.to_total(target)
            return self._offer(target, next_total, final=True, reason="stalled: final offer")

        return self._offer(target, next_total, final=penultimate,
                           reason="opening" if self.our_x is None else "counter")

    def _offer(self, x, total, final=False, reason=""):
        assert self.g.check(self.lines, total).ok, "engine produced an out-of-policy offer"
        self.our_x, self.our_total = x, total
        self.our_lines = [Line(l.sku, l.qty) for l in self.lines]
        return Decision("counter" if reason != "opening" else "offer", self.lines, total, final, reason)

    def _close(self, action, total, reason):
        self.closed = True
        return Decision(action, self.lines, total, True, reason)

    def buyer_accepts(self, lines: list[Line] | None, price: float | None) -> Decision:
        """Buyer says 'accept'. Only our own last offer, unchanged, can be accepted."""
        if self.our_total is None:
            return Decision("info", reason="nothing to accept yet")
        same_basket = lines is None or sorted((l.sku, l.qty) for l in lines) == \
            sorted((l.sku, l.qty) for l in self.our_lines)
        same_price = price is None or abs(price - self.our_total) < 0.01 or price > self.our_total
        if same_basket and same_price and self.g.check(self.our_lines, self.our_total).ok:
            self.lines = self.our_lines
            return self._close("accept", self.our_total, "buyer accepted our offer")
        return Decision("info", reason="accept did not match our last offer")
