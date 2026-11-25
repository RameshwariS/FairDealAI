"""Starter-kit checks: the adapter must score with zero violations under the kit's own rules."""
import random
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent / "ps2-selling-to-machines"


def _kit():
    # the kit has its own harness.py; make sure it wins over our harness/ package
    sys.path.insert(0, str(KIT))
    for mod in ("harness", "buyers"):
        m = sys.modules.get(mod)
        if m is not None and not str(getattr(m, "__file__", "")).startswith(str(KIT)):
            del sys.modules[mod]
    import buyers
    import harness
    sys.path.remove(str(KIT))
    return harness, buyers


def test_floor_matches_kit_floating_point():
    harness, _ = _kit()
    sys.path.append(str(KIT.parent))
    from fairdeal_seller import Seller
    store, policy = harness.load_store(), harness.load_policy()
    s = Seller(store, policy)
    for sku, row in store.items():
        f = s.agent.guard.unit_floor(s.agent.catalog.get(sku))
        assert not harness.check_items([{"sku": sku, "qty": 1, "unit_price": f}], store, policy) or row["stock"] == 0


def test_kit_runs_with_zero_violations():
    harness, buyers = _kit()
    sys.path.append(str(KIT.parent))
    from fairdeal_seller import Seller
    store, policy = harness.load_store(), harness.load_policy()
    seller = Seller(store, policy)
    for sc in buyers.make_scenarios(store, policy, 90, 2):  # seed 2 once exposed both bugs below
        buyer = buyers.BUYERS[sc["buyer"]](sc, store, random.Random(sc["seed"]))
        r = harness.run_negotiation(seller, buyer, store, policy, sc["id"])
        assert not r["violations"], (sc["id"], r["violations"])
