"""SellerAgent: the public entry point.

    agent = SellerAgent("data/store.csv", "data/policy.json")
    agent.reset()                      # start of each negotiation
    reply = agent.respond(buyer_msg)   # dict in, dict out (JSON-serialisable)

Pipeline per turn:  parse -> screen -> fix basket against stock -> engine
decides -> PolicyGuard re-checks -> writer builds text -> truth check.
"""
from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

from .catalog import Catalog, Policy
from .parsing import parse
from .policy import Line, PolicyGuard
from .pricing import Negotiation, Params
from .writer import Writer

ROOT = Path(__file__).resolve().parent.parent
_NEGOTIATION_IDS = itertools.count(1)  # makes offer ids unique across negotiations and sessions

NOTE = {
    "injection": "I can only negotiate price, quantity and bundles for products in our store.",
    "competitor_quote": "I can't verify prices from other stores, so I price from our own costs and policy.",
    "authority": "Price changes can't be authorised over chat.",
    "spoofing": "This message came from the buyer side, so I can't treat it as a store message.",
    "malformed": "I can only use a positive price.",
}


class SellerAgent:
    def __init__(self, store=ROOT / "data/store.csv", policy=ROOT / "data/policy.json",
                 params: Params | None = None, llm=None, margin_basis: str = "strict",
                 persist_stock: bool = False, llm_parse=None, rich_protocol: bool = True,
                 text_offers: bool = True):
        # paths, or the in-memory objects the starter kit hands its Seller ({sku: row}, policy dict)
        self.catalog = Catalog.from_rows(store.values()) if isinstance(store, dict) else Catalog.from_csv(store)
        self.policy = (Policy.from_dict(policy, margin_basis) if isinstance(policy, dict)
                       else Policy.from_json(policy, margin_basis=margin_basis))
        self.guard = PolicyGuard(self.catalog, self.policy)
        tuned = ROOT / "data/params.json"  # written by `python tune.py --apply`
        if params is None and tuned.exists():
            params = Params(**json.loads(tuned.read_text()))
        self.params = params or Params()
        self.writer = Writer(self.catalog, llm=llm)
        self.persist_stock = persist_stock  # keep sold units across negotiations
        self.llm_parse = llm_parse          # optional: callable(text, catalog) -> dict, only fills gaps
        self.rich_protocol = rich_protocol  # add offer_id / claims / alternatives to every reply
        self.text_offers = text_offers      # read "can you do 15k?" in free text as an offer (off when bids are structured)
        self.reset()

    def fork(self) -> "SellerAgent":
        """A fresh negotiator sharing this agent's read-only catalog, policy and settings (used by server.py)."""
        twin = object.__new__(SellerAgent)
        for k in ("catalog", "policy", "params", "writer", "persist_stock", "llm_parse", "rich_protocol",
                  "text_offers"):
            setattr(twin, k, getattr(self, k))
        twin.guard = PolicyGuard(self.catalog, self.policy)
        twin.reset()
        return twin

    # ------------------------------------------------------------------
    def reset(self, max_rounds: int | None = None):
        if not self.persist_stock:
            self.guard.sold = {}
        p = Params(**{**self.params.__dict__, **({"max_rounds": max_rounds} if max_rounds else {})})
        self.neg = Negotiation(self.guard, p)
        self.turn = 0
        self.round_offset = None
        self.noted: set = set()
        self.log: list = []
        self.done = False
        self.unsellable = 0
        self.session = next(_NEGOTIATION_IDS)
        self.offer_ids: dict = {}

    # ------------------------------------------------------------------
    def respond(self, msg) -> dict:
        self.turn += 1
        ev = parse(msg, self.catalog)
        if self.llm_parse and ev.text and (ev.lines is None and not self.neg.lines
                                           or ev.offer_total is None and ev.intent in ("question", "request")):
            self._llm_fill(ev)
        raw = ev.raw
        if "max_rounds" in raw:
            try:
                self.neg.p.max_rounds = int(raw["max_rounds"])
            except (TypeError, ValueError):
                pass
        rnd = self._round(raw)
        notes, alts, stock_lines = [], [], []

        if self.done:
            return self._out("info", rnd, None, None, "This negotiation is already closed. Thank you!", ev)

        for flag in ("injection", "competitor_quote", "authority", "spoofing", "malformed"):
            if flag in ev.flags and flag not in self.noted:
                notes.append(NOTE[flag])
                self.noted.add(flag)
        if ev.unknown_skus:  # never echo the code back: it may contain a number we can't vouch for
            notes.append("One of those items isn't in our store.")

        # ---- basket vs stock (truthful quantity handling) ----
        offer_total = ev.offer_total
        dropped = False  # True when we deliberately ignore the price (basket changed under it)
        if ev.lines is not None:
            fixed = []
            for l in ev.lines:
                p = self.catalog.get(l.sku)
                avail = self.guard.available(p)
                q = max(1, l.qty)
                if avail == 0:
                    notes.append(f"Sorry, {p.name} is out of stock.")
                    alts += self.catalog.alternatives(p, float("inf"), lambda x: 0, k=1)
                    offer_total, dropped = None, True
                    continue
                if q > avail:
                    notes.append(f"We have {avail} of {p.name} in stock, so I've priced {avail}.")
                    q, offer_total, dropped = avail, None, True
                elif q != l.qty:
                    offer_total, dropped = None, True
                fixed.append(Line(p.sku, q))
            if fixed:
                self.neg.set_basket(fixed)
            elif not self.neg.lines:
                self.unsellable += 1
                if self.unsellable >= 2 or rnd >= self.neg.p.max_rounds:
                    # nothing we can sell them: close cleanly instead of looping to a deadlock
                    self.done = True
                    text = self._text("info", notes=[f"Sorry, I can't fill this order from current stock, "
                                                     f"so I'll close this negotiation."], alts=alts[:1])
                    return self._out("walk_away", rnd, None, None, text, ev, reason="unsellable basket")
                return self._out("info", rnd, None, None, self._text("info", notes=notes, alts=alts), ev,
                                 alts=alts)
        if not self.neg.lines:
            text = self._text("info", notes=notes + ["Which product and how many would you like?"])
            return self._out("info", rnd, None, None, text, ev)
        if ev.asked_stock:
            stock_lines = list(self.neg.lines)

        # an amount written only in text ("can you do 15k?") counts as an offer if it is plausible
        if self.text_offers and offer_total is None and not dropped and ev.text_amounts and ev.intent != "accept" \
                and not (ev.flags & {"competitor_quote", "budget_claim"}):
            lt = self.guard.bundle_list(self.neg.lines)
            plausible = [a for a in ev.text_amounts if 0.2 * lt <= a <= 1.5 * lt]
            if plausible:
                offer_total, ev.intent = plausible[-1], "offer"
                ev.offer_total = offer_total

        # machine buyers can accept by offer_id (we only ever issue policy-checked offers)
        oid = raw.get("offer_id")
        if oid is not None and ev.intent == "accept":
            if oid in self.offer_ids:
                d = self.neg.buyer_accepts(None, None)
                if d.action == "accept":
                    return self._finish(d, rnd, notes, ev)
            else:
                notes.append("I don't recognise that offer id.")

        # ---- intents ----
        if ev.intent == "walk_away":
            self.done = True
            text = self._text("info", notes=["Understood, thanks for your time."])
            return self._out("end", rnd, None, None, text, ev)

        if ev.intent == "accept":
            # "I accept your offer of 5000" with the number only in text: if it isn't our price, it's no accept
            if ev.offer_total is None and ev.text_amounts and self.neg.our_total is not None \
                    and all(abs(a - self.neg.our_total) > 0.005 * self.neg.our_total for a in ev.text_amounts):
                ev.offer_total = min(ev.text_amounts)
                offer_total = None if dropped else ev.offer_total
            d = self.neg.buyer_accepts(ev.lines, ev.offer_total)
            if d.action == "accept":
                return self._finish(d, rnd, notes, ev)
            if ev.offer_total is None and self.neg.our_total is not None:
                text = self._text("counter", lines=self.neg.our_lines, total=self.neg.our_total,
                                  notes=notes + ["To confirm, my current offer is below."])
                return self._out("counter", rnd, self.neg.our_lines, self.neg.our_total, text, ev)
            # "I accept at <a different price>" is treated as a counter-offer, not a deal
            if self.neg.our_total is not None:
                notes.append("Just to be clear, that isn't a price I offered.")
                ev.flags.add("fake_accept")

        # budget below what policy allows -> point to in-budget items (honest cross-sell)
        claimed = ev.claimed_amount if "budget_claim" in ev.flags else None
        if claimed and len(self.neg.lines) == 1 and claimed < self.guard.bundle_floor(self.neg.lines) \
                and "alts" not in self.noted:
            p = self.catalog.get(self.neg.lines[0].sku)
            alts += self.catalog.alternatives(p, claimed / self.neg.lines[0].qty, self.guard.unit_floor, k=2)
            self.noted.add("alts")

        d = self.neg.step(rnd, offer_total)
        if d.action == "accept":
            return self._finish(d, rnd, notes, ev)
        if d.action == "walk_away":
            self.done = True
            # only ever quote a price we actually offered, together with the items it was for
            last, last_lines = self.neg.our_total, (self.neg.our_lines or d.lines)
            text = self._text("walk_away", lines=last_lines, total=last, buyer_offer=offer_total,
                              notes=notes, alts=alts)
            return self._out("walk_away", rnd, last_lines if last is not None else None, last, text, ev,
                             reason=d.reason, alts=alts)
        if d.action == "info":
            text = self._text("info", notes=notes + [f"I can't price that right now ({d.reason})."], alts=alts)
            return self._out("info", rnd, None, None, text, ev, reason=d.reason)
        kind = "offer" if d.action == "offer" else "counter"
        serious = (offer_total is not None and offer_total >= 0.2 * self.guard.bundle_list(d.lines)
                   and "fake_accept" not in ev.flags)
        text = self._text(kind, lines=d.lines, total=d.total, buyer_offer=offer_total if serious else None, notes=notes,
                          alts=alts, stock_lines=stock_lines, final=d.final)
        return self._out(kind, rnd, d.lines, d.total, text, ev, final=d.final, reason=d.reason,
                         alts=alts, stock_lines=stock_lines)

    # ------------------------------------------------------------------
    def _round(self, raw) -> int:
        r = raw.get("round", raw.get("turn"))
        try:
            r = int(r)
        except (TypeError, ValueError):
            return self.turn
        if self.round_offset is None:
            self.round_offset = 1 if r == 0 else 0
        return r + self.round_offset

    def _finish(self, d, rnd, notes, ev):
        chk = self.guard.check(d.lines, d.total)
        if not chk.ok:  # defence in depth: should never happen
            text = self._text("counter", lines=self.neg.our_lines or d.lines,
                              total=self.neg.our_total, notes=notes)
            return self._out("counter", rnd, self.neg.our_lines, self.neg.our_total, text, ev,
                             reason="guard blocked accept: " + "; ".join(chk.reasons))
        self.guard.commit(d.lines)
        self.done = True
        text = self._text("accept", lines=d.lines, total=d.total, notes=notes)
        return self._out("accept", rnd, d.lines, d.total, text, ev, final=True, reason=d.reason)

    def _enrich(self, out, kind, lines, total, alts, stock_lines):
        """Machine-readable extras for buyer agents: an id to accept by, and every fact cited to its source."""
        if lines and total is not None and kind in ("offer", "counter"):
            key = f"{self.session}|{out['round']}|{sorted((l.sku, l.qty) for l in lines)}|{total:.2f}"
            oid = "of-" + hashlib.sha1(key.encode()).hexdigest()[:10]
            self.offer_ids[oid] = total
            out["offer_id"] = oid
            out["price_is_total"] = True  # no fees are ever added on top
        claims = []
        for l in lines or []:
            p = self.catalog.get(l.sku)
            claims.append({"sku": p.sku, "fact": "list_price", "value": p.price, "source": "store.csv"})
        for l in stock_lines:
            p = self.catalog.get(l.sku)
            claims.append({"sku": p.sku, "fact": "stock", "value": self.guard.available(p), "source": "store.csv"})
        for p in alts:
            claims.append({"sku": p.sku, "fact": "list_price", "value": p.price, "source": "store.csv"})
        if alts:
            out["alternatives"] = [{"sku": p.sku, "name": p.name, "price": p.price} for p in alts]
        if claims:
            out["claims"] = claims
        if total is not None:
            out["policy_checked"] = True

    def _llm_fill(self, ev):
        """Optional LLM extraction for free-text buyers. It can only FILL gaps, and every field is validated."""
        try:
            got = self.llm_parse(ev.text, self.catalog) or {}
        except Exception:
            return
        if ev.lines is None and isinstance(got.get("items"), list):
            lines = []
            for it in got["items"]:
                p = self.catalog.get(str(it.get("sku", ""))) if isinstance(it, dict) else None
                if p is not None:
                    try:
                        lines.append(Line(p.sku, max(1, int(it.get("qty", 1)))))
                    except (TypeError, ValueError):
                        lines.append(Line(p.sku, 1))
            ev.lines = lines or None
        if ev.offer_total is None and isinstance(got.get("price"), (int, float)) and got["price"] > 0 \
                and not (ev.flags & {"competitor_quote", "budget_claim"}):
            ev.offer_total = float(got["price"])
        if ev.intent in ("question", "request") and got.get("intent") in ("offer", "accept", "walk_away"):
            ev.intent = got["intent"]

    def _text(self, kind, **kw):
        text, problems = self.writer.compose(kind, **kw)
        if problems:
            self.log.append({"truth_check": problems, "text": text})
        return text

    def _out(self, kind, rnd, lines, total, text, ev, final=False, reason="", alts=None, stock_lines=None):
        out = {"type": kind, "round": rnd, "text": text}
        if lines:
            units = self.guard.allocate(lines, total) if total is not None else {}
            out["items"] = [{"sku": l.sku, "name": self.catalog.get(l.sku).name, "qty": l.qty,
                             "unit_price": units.get(l.sku)} for l in lines]
        if total is not None:
            out["price"] = round(total, 2)
            out["currency"] = "INR"
        if final:
            out["final"] = True
        if self.rich_protocol:
            self._enrich(out, kind, lines, total, alts or [], stock_lines or [])
        self.log.append({"round": rnd, "in_intent": ev.intent, "flags": sorted(ev.flags),
                         "buyer_offer": ev.offer_total, "out": kind, "price": total, "reason": reason})
        return out
