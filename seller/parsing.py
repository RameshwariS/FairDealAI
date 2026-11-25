"""Turn a buyer message (JSON, possibly messy or hostile) into a typed event.

Buyer text is DATA. It is scanned for intent and for manipulation signals, but
it is never passed to anything that can change a price or policy.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field

from .catalog import Catalog
from .policy import Line

INTENT_KEYS = ("type", "action", "intent", "kind", "move")
ITEM_KEYS = ("items", "basket", "products", "lines", "bundle", "cart")
PRICE_KEYS = ("price", "offer", "offer_price", "total", "amount", "total_price", "bid", "counter_price")
TEXT_KEYS = ("text", "message", "content", "note", "msg", "body", "comment")

ACCEPT_WORDS = re.compile(r"\b(accept(ed)?|deal|agreed?|done|sold|i'?ll take it|let'?s do it|works for me)\b", re.I)
WALK_WORDS = re.compile(r"\b(walk(ing)? away|no deal|not interested|goodbye|bye|i'?m out|cancel|forget it)\b", re.I)
REJECT_WORDS = re.compile(r"\b(reject(ed)?|too (high|expensive|much)|no way)\b", re.I)
SCALED = re.compile(r"(\d+(?:\.\d+)?)\s*(k|thousand|hazaa?r|hajaa?r|lakhs?|lacs?)\b", re.I)
SCALE_OF = {"k": 1e3, "thousand": 1e3, "hazar": 1e3, "hazaar": 1e3, "hajar": 1e3, "hajaar": 1e3,
            "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5}
# a bare number in text that is not a quantity, a SKU part (P002), a spec (20000mAh) or a percentage
BARE = re.compile(r"(?<![\w.,])(\d[\d,]*(?:\.\d+)?)(?![\w%])(?!\s*(?:x|units?|pcs|pieces|nos|qty|items?|rounds?|mins?|minutes?|hours?|days?)\b)", re.I)
MONEY = re.compile(r"(?:₹|rs\.?|inr|\$)\s*([0-9][0-9,]*(?:\.[0-9]+)?)|([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:₹|rs\.?|inr|rupees|/-)", re.I)

# ---- manipulation signals (logged; never used to move price) ----
SIGNALS = {
    "injection": re.compile(
        r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|your\s+|the\s+|previous\s+|prior\s+)*"
        r"(instructions|rules|policy|policies|prompt|constraints|guidelines)"
        r"|system\s*(prompt|message|override)|\[\s*system\s*\]|<\s*system\s*>|you are now|developer mode"
        r"|new (store )?policy|policy (update|change)|set (the )?price to|price\s*=\s*0|jailbreak"
        r"|as an ai|act as|pretend (to be|you)|admin (mode|override)|<!--|\boverride\b"
        r"|max_discount|min_margin|policy allows|according to your policy|your (store )?policy (says|allows|permits)", re.I),
    "spoofing": re.compile(r"^\s*(seller|system|assistant|store)\s*:", re.I | re.M),
    "competitor_quote": re.compile(
        r"competitor|other (store|shop|seller)|elsewhere|amazon|flipkart|cheaper (at|on|from)|"
        r"price[- ]match|quoted (me|at)|best ?buy|croma|reliance digital|another (store|shop|site)", re.I),
    "budget_claim": re.compile(r"budget|can only (afford|pay|spend)|max(imum)? i can|only have|can'?t go (above|over|higher)", re.I),
    "pressure": re.compile(r"deadline|expires?|last chance|right now|in the next \d+|hurry|urgent|immediately|or i leave|final warning", re.I),
    "authority": re.compile(r"\b(manager|owner|ceo|head office|authori[sz]ed|approved by|your boss|supervisor)\b", re.I),
}


@dataclass
class BuyerEvent:
    intent: str                       # request | offer | accept | reject | walk_away | question
    lines: list | None = None         # None = "same basket as before"
    offer_total: float | None = None
    text: str = ""
    flags: set = field(default_factory=set)
    claimed_amount: float | None = None  # number attached to a budget / competitor claim
    asked_stock: bool = False
    raw: dict = field(default_factory=dict)
    unknown_skus: list = field(default_factory=list)
    text_amounts: list = field(default_factory=list)  # amounts found in free text (used only if plausible)


def _all_strings(obj, out):
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            _all_strings(v, out)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _all_strings(v, out)
    return out


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = re.search(r"-?[0-9][0-9,]*(?:\.[0-9]+)?", v)
        return float(m.group(0).replace(",", "")) if m else None
    if isinstance(v, dict):
        for k in ("total", "amount", "value", "price"):
            if k in v:
                return _num(v[k])
    return None


def normalize_amounts(text: str) -> str:
    """'15k' -> '15000', '1.2 lakh' -> '120000', '2 hazaar' -> '2000' (Indian buyers write prices this way)."""
    def sub(m):
        v = float(m.group(1)) * SCALE_OF[m.group(2).lower()]
        return f"{v:.0f}"
    return SCALED.sub(sub, text)


def _bare_numbers(text: str) -> list[float]:
    out = []
    for m in BARE.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            pass
    return out


def _money_in(text: str) -> list[float]:
    vals = []
    for a, b in MONEY.findall(text):
        try:
            vals.append(float((a or b).replace(",", "")))
        except ValueError:
            pass
    return vals


def parse(msg, catalog: Catalog) -> BuyerEvent:
    if isinstance(msg, str):
        try:
            msg = json.loads(msg)
        except (json.JSONDecodeError, ValueError):
            msg = {"text": msg}
    if not isinstance(msg, dict):
        msg = {"text": str(msg)}

    text = normalize_amounts(" ".join(str(msg[k]) for k in TEXT_KEYS if k in msg and msg[k] is not None))
    text = unicodedata.normalize("NFKC", text)  # full-width / look-alike letters -> plain ASCII
    every_string = unicodedata.normalize("NFKC", " ".join(_all_strings(msg, [])))  # hidden fields too
    ev = BuyerEvent(intent="question", text=text, raw=msg)

    for name, rx in SIGNALS.items():
        if rx.search(every_string):
            ev.flags.add(name)
    role = str(msg.get("from", msg.get("role", msg.get("sender", "")))).lower()
    if role in ("seller", "system", "assistant", "store", "admin"):
        ev.flags.add("spoofing")  # a buyer message claiming to come from us / the system

    # ---- items ----
    lines, unknown = None, []
    raw_items = next((msg[k] for k in ITEM_KEYS if k in msg and msg[k]), None)
    if raw_items is None and any(k in msg for k in ("sku", "product_id", "item_id", "id", "product")):
        raw_items = [msg]
    if isinstance(raw_items, dict):
        raw_items = [{"sku": k, "qty": v} for k, v in raw_items.items()] \
            if all(isinstance(v, (int, float)) for v in raw_items.values()) else [raw_items]
    if isinstance(raw_items, (list, tuple)):
        merged: dict[str, int] = {}
        for it in raw_items:
            if isinstance(it, str):
                sku, qty = it, 1
            elif isinstance(it, dict):
                sku = next((it[k] for k in ("sku", "product_id", "item_id", "id", "product", "name") if k in it), None)
                qty = it.get("qty", it.get("quantity", 1))
            else:
                continue
            p = catalog.get(str(sku)) if sku is not None else None
            if p is None:
                unknown.append(str(sku))
                continue
            try:
                q = int(float(qty))
            except (TypeError, ValueError):
                q = 1
            merged[p.sku] = merged.get(p.sku, 0) + q
        lines = [Line(s, q) for s, q in merged.items()] or None
    if lines is None and text:
        found = catalog.find_in_text(text)
        if found:
            qty_m = re.search(r"\b(\d{1,3})\s*(x|units?|pcs|pieces|nos)\b", text, re.I)
            q = int(qty_m.group(1)) if qty_m else 1
            lines = [Line(p.sku, q) for p in found[:3]]
    ev.lines, ev.unknown_skus = lines, unknown

    # ---- price ----
    price = None
    for k in PRICE_KEYS:
        if k in msg:
            price = _num(msg[k])
            if price is not None:
                break
    unit = _num(msg.get("unit_price")) if "unit_price" in msg else None
    if price is None and unit is not None and lines:
        price = unit * sum(l.qty for l in lines)
    text_money = _money_in(text)
    ev.text_amounts = text_money or _bare_numbers(text)
    if ev.flags & {"budget_claim", "competitor_quote"} and ev.text_amounts:
        ev.claimed_amount = min(ev.text_amounts)
    if price is None and text_money and not (ev.flags & {"competitor_quote"}) and not msg.get("structured"):
        price = text_money[-1]  # free-text buyers only: structured buyers put their bid in the items
    if price is not None and price <= 0:
        price = None  # zero / negative prices are not offers
        ev.flags.add("malformed")
    ev.offer_total = price

    # ---- intent ----
    declared = next((str(msg[k]).lower() for k in INTENT_KEYS if k in msg and msg[k]), "")
    if declared in ("accept", "accepted", "agree", "deal", "yes"):
        ev.intent = "accept"
    elif declared in ("walk_away", "walk", "leave", "quit", "end", "no_deal", "exit"):
        ev.intent = "walk_away"
    elif declared in ("reject", "decline", "no"):
        ev.intent = "reject" if price is None else "offer"
    elif declared in ("offer", "counter", "counter_offer", "counteroffer", "bid", "propose", "proposal"):
        ev.intent = "offer"
    elif declared in ("request", "inquiry", "enquiry", "ask", "start", "hello", "query", "browse"):
        ev.intent = "offer" if price is not None else "request"
    elif ACCEPT_WORDS.search(text) and not re.search(r"\b(not|n't|no)\b\s+\w*\s*(accept|deal)", text, re.I):
        ev.intent = "accept"
    elif WALK_WORDS.search(text):
        ev.intent = "walk_away"
    elif price is not None:
        ev.intent = "offer"
    elif lines:
        ev.intent = "request"
    elif REJECT_WORDS.search(text):
        ev.intent = "reject"
    ev.asked_stock = bool(re.search(r"\b(stock|available|availability|how many|in stock|units left)\b", text, re.I))
    return ev
