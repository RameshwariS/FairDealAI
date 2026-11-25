"""PolicyGuard: the single gate every outgoing price and every acceptance passes.

Nothing else in the agent is trusted to respect policy. The pricing engine,
the reply writer and (optionally) an LLM can propose anything; the guard
decides whether it may leave the store.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .catalog import Catalog, Policy, Product


def ceil2(x: float) -> float:
    """Round UP to 2 decimals so rounding can never push a price below a floor."""
    return math.ceil(round(x * 100, 6)) / 100


@dataclass
class Line:
    sku: str
    qty: int


@dataclass
class Check:
    ok: bool
    reasons: list = field(default_factory=list)


class PolicyGuard:
    def __init__(self, catalog: Catalog, policy: Policy, safety: float = 0.0):
        self.catalog = catalog
        self.policy = policy
        self.safety = safety  # extra fraction above the floor (0 = exact policy floor)
        self.sold: dict[str, int] = {}  # units committed in earlier deals (if the harness keeps state)

    # ---------- per-unit limits ----------
    def unit_floor(self, p: Product) -> float:
        m = self.policy.margin_for(p.category)
        basis = self.policy.margin_basis
        on_price = p.cost / (1 - m) if m < 1 else math.inf
        on_cost = p.cost * (1 + m)
        margin_floor = {"price": on_price, "cost": on_cost}.get(basis, max(on_price, on_cost))
        discount_floor = p.price * (1 - self.policy.discount_for(p.category))
        exact = max(margin_floor, discount_floor) * (1 + self.safety)
        f = ceil2(exact)
        while f < exact:  # e.g. 637 / 0.7 = 910.0000000000001 in floating point: ₹910.00 would be below it
            f = round(f + 0.01, 2)
        return f

    def available(self, p: Product) -> int:
        return max(0, p.stock - self.sold.get(p.sku, 0))

    # ---------- bundles ----------
    def bundle_floor(self, lines: list[Line]) -> float:
        return round(sum(self.unit_floor(self.catalog.get(l.sku)) * l.qty for l in lines), 2)

    def bundle_list(self, lines: list[Line]) -> float:
        return round(sum(self.catalog.get(l.sku).price * l.qty for l in lines), 2)

    def bundle_cost(self, lines: list[Line]) -> float:
        return round(sum(self.catalog.get(l.sku).cost * l.qty for l in lines), 2)

    def allocate(self, lines: list[Line], total: float) -> dict[str, float]:
        """Split a bundle total into unit prices so EVERY unit is within policy.

        Each unit starts at its floor; the surplus is shared in proportion to
        each unit's headroom (list - floor). If total >= sum(floors) every unit
        lands in [floor, list].
        """
        floors = {l.sku: self.unit_floor(self.catalog.get(l.sku)) for l in lines}
        heads = {l.sku: self.catalog.get(l.sku).price - floors[l.sku] for l in lines}
        surplus = total - sum(floors[l.sku] * l.qty for l in lines)
        head_total = sum(heads[l.sku] * l.qty for l in lines) or 1.0
        units = {}
        for l in lines:
            share = surplus * (heads[l.sku] * l.qty / head_total) / l.qty
            units[l.sku] = math.floor((floors[l.sku] + share) * 100) / 100
            units[l.sku] = max(units[l.sku], floors[l.sku])
        return units

    # ---------- the gate ----------
    def check(self, lines: list[Line], total: float) -> Check:
        reasons = []
        if not lines:
            return Check(False, ["empty basket"])
        for l in lines:
            p = self.catalog.get(l.sku)
            if p is None:
                reasons.append(f"unknown sku {l.sku}")
                continue
            if l.qty <= 0:
                reasons.append(f"bad qty {l.qty} for {l.sku}")
            if l.qty > self.available(p):
                reasons.append(f"{l.sku}: qty {l.qty} > stock {self.available(p)}")
        if reasons:
            return Check(False, reasons)
        if total + 1e-9 < self.bundle_floor(lines):
            reasons.append(f"total {total} below policy floor {self.bundle_floor(lines)}")
        if total - 1e-9 > self.bundle_list(lines):
            reasons.append("total above list price")  # never overcharge / no hidden fees
        if not reasons:
            units = self.allocate(lines, total)
            for l in lines:
                if units[l.sku] + 1e-9 < self.unit_floor(self.catalog.get(l.sku)):
                    reasons.append(f"{l.sku} unit {units[l.sku]} below floor")
        return Check(not reasons, reasons)

    def commit(self, lines: list[Line]):
        for l in lines:
            self.sold[l.sku] = self.sold.get(l.sku, 0) + l.qty
