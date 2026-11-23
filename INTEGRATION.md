# Plugging into the official starter kit

The local `data/store.csv` and `data/policy.json` are **synthetic stand-ins** built to the shape the problem statement describes. Before you submit:

1. Copy the kit's `store.csv` and `policy.json` into `data/`. The loaders accept common column names (`sku/id/product_id`, `price/list_price/mrp`, `cost/unit_cost`, `stock/qty/inventory`). If the kit uses other names, add them to `COLUMN_ALIASES` in `seller/catalog.py`.
2. Check how the kit defines margin:
   - `(price − cost) / price` → `SellerAgent(margin_basis="price")`
   - `(price − cost) / cost` → `margin_basis="cost"`
   - The default `"strict"` satisfies both, so it is always safe but slightly conservative.
3. Wrap the agent in whatever interface `harness.py` expects. Usually that's a class with a reset method and a respond/act method:

```python
from seller import SellerAgent

class Seller:                      # rename the methods to match harness.py
    def __init__(self):
        self.agent = SellerAgent("data/store.csv", "data/policy.json")
    def reset(self):
        self.agent.reset(max_rounds=10)
    def respond(self, buyer_message: dict) -> dict:
        return self.agent.respond(buyer_message)
```

4. If the kit's JSON keys differ (for example `offer_price` instead of `price`), the parser already accepts most variants (see `PRICE_KEYS`, `ITEM_KEYS` and `INTENT_KEYS` in `seller/parsing.py`). On the output side, rename keys in `SellerAgent._out`.
5. If the kit's harness rejects unknown keys, turn off the extra protocol fields with `SellerAgent(rich_protocol=False)` (`offer_id`, `claims`, `alternatives`, `price_is_total`, `policy_checked`).
6. Run the kit's `evaluate.py`, then `pytest tests/`, and save both outputs in `outputs/`.
