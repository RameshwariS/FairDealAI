"""Reply writer + truth checker.

Every outgoing sentence is built from store data and engine numbers. If an
optional LLM is used to make the wording friendlier, its text must pass the
same truth check (every number it mentions must be a number we are allowed to
state); otherwise the template text is sent instead.
"""
from __future__ import annotations

import re

from .catalog import Catalog
from .policy import Line

NUM = re.compile(r"(?<![A-Za-z])[0-9][0-9,]*(?:\.[0-9]+)?")
BANNED = re.compile(
    r"only \d+ left|selling fast|last (few|one|unit|chance)|limited (time|stock)|hurry|"
    r"before it'?s gone|price (goes|will go) up|offer expires|today only|other buyers|"
    r"high demand|shipping fee|handling fee|convenience fee|service charge|plus tax|\+ ?tax",
    re.I)


def rs(x: float) -> str:
    return f"₹{x:,.0f}" if abs(x - round(x)) < 0.005 else f"₹{x:,.2f}"


class Writer:
    def __init__(self, catalog: Catalog, llm=None):
        self.c = catalog
        self.llm = llm  # optional callable(prompt:str)->str

    # ---------- descriptions ----------
    def desc(self, lines: list[Line]) -> str:
        parts = []
        for l in lines:
            p = self.c.get(l.sku)
            parts.append(f"{l.qty} x {p.name}" if l.qty > 1 else p.name)
        return " + ".join(parts)

    # ---------- truth check ----------
    def allowed_numbers(self, lines, extra) -> set:
        allowed = set()
        for l in lines or []:
            p = self.c.get(l.sku)
            if p:
                allowed |= {p.price, float(l.qty), float(p.stock), p.price * l.qty}
                allowed |= {float(d) for d in re.findall(r"\d+", p.name + " " + p.sku)}
        allowed |= {float(x) for x in extra if x is not None}
        return allowed

    def verify(self, text: str, allowed: set) -> list[str]:
        problems = []
        for m in NUM.findall(text):
            v = float(m.replace(",", ""))
            if not any(abs(v - a) < 0.01 for a in allowed):
                problems.append(f"unsupported number {m}")
        if BANNED.search(text):
            problems.append("pressure/scarcity/fee language")
        return problems

    # ---------- composing ----------
    def compose(self, kind: str, lines=None, total=None, buyer_offer=None, notes=None,
                alts=None, stock_lines=None, final=False) -> tuple[str, list]:
        lines = lines or []
        notes = notes or []
        s = []
        d = self.desc(lines) if lines else ""
        list_total = sum(self.c.get(l.sku).price * l.qty for l in lines) if lines else None

        for n in notes:  # honest, short responses to tactics / problems
            s.append(n)
        if kind == "offer":
            if total is not None and list_total and total < list_total - 0.005:
                is_bundle = len(lines) > 1 or sum(l.qty for l in lines) > 1
                lead = "As a bundle I can offer it for" if is_bundle else "I can offer it for"
                s.append(f"{d} lists at {rs(list_total)}. {lead} {rs(total)}.")
            else:
                s.append(f"{d} is {rs(total)}.")
            s.append("That is the total price, with no extra fees.")
        elif kind == "counter":
            if buyer_offer is not None:
                s.append("Thanks for your offer.")  # we never restate buyer numbers: every price we write is ours
            if final:
                s.append(f"My best and final price for {d} is {rs(total)}.")
            else:
                s.append(f"I can do {rs(total)} for {d}.")
        elif kind == "accept":
            s.append(f"Deal: {d} for {rs(total)}, all-inclusive. Thank you!")
        elif kind == "walk_away":
            if buyer_offer is not None:
                s.append(f"I can't go that low for {d}, so I'll have to pass this time.")
            else:
                s.append("I don't think we can agree on this one, so I'll close the negotiation here.")
            if total is not None:
                s.append(f"My best price stays {rs(total)} if you change your mind.")
        elif kind == "info":
            pass
        if alts:
            # names only: a price for a product not in this negotiation would be an unsupported claim
            opts = " and ".join(f"{p.name} ({p.sku})" for p in alts)
            s.append(f"If it helps, {opts} {'are' if len(alts) > 1 else 'is'} in stock.")
        for l in stock_lines or []:
            p = self.c.get(l.sku)
            s.append(f"{p.name}: {p.stock} in stock." if p.stock else f"{p.name} is out of stock.")
        text = " ".join(s).strip() or "How can I help? Tell me which product and quantity you need."

        extra = [total, list_total]
        extra += [self.c.get(l.sku).stock for l in stock_lines or []]
        allowed = self.allowed_numbers(lines + list(stock_lines or []), extra)
        problems = self.verify(text, allowed)
        if self.llm and not problems:
            try:
                rewritten = self.llm(
                    "Rewrite this store assistant message to sound warm and natural. Keep every number, "
                    "product name and fact exactly as written. Do not add any new numbers, discounts, "
                    "scarcity, urgency or fees. Reply with the message only.\n\n" + text).strip()
                if rewritten and not self.verify(rewritten, allowed):
                    text = rewritten
            except Exception:
                pass  # LLM is optional; template text stands
        return text, problems
