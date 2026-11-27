"""Store data + policy loading.

The loaders accept several common column / key spellings so the agent can be
pointed at the official starter-kit files without code changes. If the kit uses
names not listed here, add them to the alias tables below.
"""
from __future__ import annotations

import csv
import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path

COLUMN_ALIASES = {
    "sku": ["sku", "id", "product_id", "item_id", "code"],
    "name": ["name", "product", "product_name", "title"],
    "category": ["category", "cat", "type"],
    "price": ["price", "list_price", "mrp", "retail_price"],
    "cost": ["cost", "unit_cost", "cost_price"],
    "stock": ["stock", "qty", "quantity", "inventory", "in_stock"],
}


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str
    price: float  # list price
    cost: float
    stock: int


def _pick(row: dict, field: str):
    lowered = {k.strip().lower(): v for k, v in row.items() if k}
    for alias in COLUMN_ALIASES[field]:
        if alias in lowered and lowered[alias] not in (None, ""):
            return lowered[alias]
    return None


class Catalog:
    def __init__(self, products: list[Product]):
        self.products = {p.sku: p for p in products}
        self._by_name = {p.name.lower(): p for p in products}

    @classmethod
    def from_csv(cls, path: str | Path) -> "Catalog":
        with open(path, newline="", encoding="utf-8") as f:
            return cls.from_rows(list(csv.DictReader(f)))

    @classmethod
    def from_rows(cls, rows) -> "Catalog":
        """Rows as dicts (csv.DictReader rows, or the {sku: row} values the starter kit passes in)."""
        products = []
        if True:
            for i, row in enumerate(rows):
                sku = _pick(row, "sku") or f"ROW{i + 1}"
                products.append(Product(
                    sku=str(sku).strip(),
                    name=str(_pick(row, "name") or sku).strip(),
                    category=str(_pick(row, "category") or "default").strip().lower(),
                    price=float(_pick(row, "price")),
                    cost=float(_pick(row, "cost")),
                    stock=int(float(_pick(row, "stock") or 0)),
                ))
        return cls(products)

    def get(self, key: str | None) -> Product | None:
        if key is None:
            return None
        key = str(key).strip()
        if key in self.products:
            return self.products[key]
        upper = key.upper()
        if upper in self.products:
            return self.products[upper]
        return self._by_name.get(key.lower())

    def find_in_text(self, text: str) -> list[Product]:
        """Products whose SKU or full name appears in free text."""
        low = text.lower()
        hits = []
        for p in self.products.values():
            if p.sku.lower() in low.split() or p.sku.lower() in low or p.name.lower() in low:
                hits.append(p)
        return hits or self._fuzzy_find(low)

    def _fuzzy_find(self, low: str) -> list[Product]:
        """Fallback for typos / partial names ("zentrain puffer jacet", "puffer jacket").

        Names look like "Brand Model Type, Colour". A product qualifies when every
        model/type word appears (typos allowed); brand and colour only add score.
        Returns a product only when it is the single best match - an ambiguous ask
        ("rain jacket") returns nothing, so the seller asks instead of guessing.
        """
        words = set(re.findall(r"[a-z0-9]+", low))
        if not words:
            return []

        def seen(tok: str) -> bool:
            if tok in words:
                return True
            return len(tok) >= 4 and any(len(w) >= 3 and difflib.SequenceMatcher(None, tok, w).ratio() >= 0.8
                                         for w in words)

        scored = []
        for p in self.products.values():
            base, _, variant = p.name.lower().partition(",")
            btoks, vtoks = re.findall(r"[a-z0-9]+", base), re.findall(r"[a-z0-9]+", variant)
            core = btoks[1:]  # drop the brand
            if not core or not all(seen(t) for t in core):
                continue
            brand_hit = seen(btoks[0])
            if len(core) < 2 and not brand_hit:
                continue  # one generic word ("jacket") is never enough
            scored.append((len(core) + brand_hit + sum(seen(t) for t in vtoks), p))
        if not scored:
            return []
        scored.sort(key=lambda x: -x[0])
        if len(scored) > 1 and scored[1][0] == scored[0][0]:
            return []
        return [scored[0][1]]

    def suggest(self, text: str) -> list[Product]:
        """Products that fit every product word in a vague ask ("jacket", "zentrail jacket").

        Used to offer choices when find_in_text can't pick one product. Words that
        match no catalog word ("I", "want", "please") are ignored; typos are allowed.
        """
        vocab = {t for p in self.products.values() for t in re.findall(r"[a-z0-9]+", p.name.lower())}
        keys = set()
        for w in re.findall(r"[a-z0-9]+", text.lower()):
            if w in vocab:
                keys.add(w)
            elif len(w) >= 4:
                keys.update(difflib.get_close_matches(w, vocab, n=1, cutoff=0.8))
        if not keys:
            return []
        hits = [p for p in self.products.values() if keys <= set(re.findall(r"[a-z0-9]+", p.name.lower()))]
        return sorted(hits, key=lambda p: p.price)

    def alternatives(self, product: Product, max_total: float, floor_fn, k: int = 2) -> list[Product]:
        """In-stock products in the same category whose policy floor fits a budget."""
        options = [p for p in self.products.values()
                   if p.category == product.category and p.sku != product.sku
                   and p.stock > 0 and floor_fn(p) <= max_total]
        options.sort(key=lambda p: abs(p.price - product.price))  # closest to what they wanted first
        return options[:k]


@dataclass
class Policy:
    min_margin: dict  # category -> fraction
    max_discount: dict | float  # fraction, global or per category
    default_min_margin: float = 0.0
    # "price": margin = (price - cost) / price   (standard retail definition)
    # "cost":  margin = (price - cost) / cost    (markup)
    # "strict": satisfy both (safe default until the official definition is confirmed)
    margin_basis: str = "strict"

    @classmethod
    def from_json(cls, path: str | Path, margin_basis: str = "strict") -> "Policy":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f), margin_basis)

    @classmethod
    def from_dict(cls, raw: dict, margin_basis: str = "strict") -> "Policy":
        mm = raw.get("min_margin") or raw.get("minimum_margin") or raw.get("min_margin_per_category") or {}
        if isinstance(mm, (int, float)):
            mm = {"default": float(mm)}
        mm = {str(k).lower(): _frac(v) for k, v in mm.items()}
        md = raw.get("max_discount", raw.get("maximum_discount", 1.0))
        if isinstance(md, dict):
            md = {str(k).lower(): _frac(v) for k, v in md.items()}
        else:
            md = _frac(md)
        return cls(min_margin=mm, max_discount=md,
                   default_min_margin=mm.get("default", max(mm.values()) if mm else 0.0),
                   margin_basis=raw.get("margin_basis", margin_basis))

    def margin_for(self, category: str) -> float:
        return self.min_margin.get(category.lower(), self.default_min_margin)

    def discount_for(self, category: str) -> float:
        if isinstance(self.max_discount, dict):
            return self.max_discount.get(category.lower(), self.max_discount.get("default", 0.0))
        return self.max_discount


def _frac(v) -> float:
    """Accept 0.2, "20%", or 20 (percent) and return a fraction."""
    if isinstance(v, str):
        v = v.strip().rstrip("%")
        v = float(v)
        return v / 100 if v > 1 else v
    v = float(v)
    return v / 100 if v > 1 else v
