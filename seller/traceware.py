"""Rezolve Labs TraceWare claim verification for outgoing seller replies.

Every offer or accept is recorded as tool actions (one `add_to_basket` span per line: SKU, name,
quantity, unit price) and the reply text is verified against them before it is sent. PASS / WARN
go out as written; REGENERATE / BLOCK make the seller send a minimal reply built from the same
items instead. This sits on top of the agent's own deterministic truth check, as a second,
independent verifier.

Turned on by environment variables (off by default, so tests and the kit's evaluator run offline):

    export REZOLVE_API_KEY=...            # your Rezolve Labs key
    export REZOLVE_MERCHANT_ID=...        # shown under "Your account" in the TraceWare docs
    export TRACEWARE_LOG=outputs/traceware_log.jsonl   # optional: one line per check

If the service can't be reached the reply is sent as the agent wrote it (its own truth check
already passed); the failure is logged.
"""
from __future__ import annotations

import json
import os
import time
import uuid

API = os.getenv("REZOLVE_BASE_URL", "https://api.rezolvelabs.com/api/v1")


def enabled() -> bool:
    return bool(os.getenv("REZOLVE_API_KEY") and os.getenv("REZOLVE_MERCHANT_ID"))


def observations(turn_id: str, items: list, store: dict) -> list:
    out = []
    for k, it in enumerate(items):
        row = store.get(it["sku"], {})
        out.append({"id": f"{turn_id}-{k}", "type": "SPAN", "name": "add_to_basket",
                    "metadata": {"attributes": {
                        "func.arg.product_id": it["sku"], "func.arg.name": row.get("name", it["sku"]),
                        "func.arg.quantity": str(it["qty"]), "func.arg.price": str(float(it["unit_price"])),
                        "func.result": json.dumps({"success": True})}}})
    return out


def verify(text: str, items: list, store: dict, session_id: str, post=None) -> str | None:
    """Returns PASS / WARN / REGENERATE / BLOCK, or None when disabled or unreachable."""
    if not enabled() or not text or not items:
        return None
    turn_id = f"{session_id}-{uuid.uuid4().hex[:10]}"  # fresh id every call: a repeated id returns the old decision
    body = {"id": turn_id, "sessionId": session_id, "userId": f"buyer-{session_id}",
            "metadata": {"merchant_id": os.environ["REZOLVE_MERCHANT_ID"]},
            "output": text, "observations": observations(turn_id, items, store)}
    t0 = time.perf_counter()
    decision, error = None, None
    try:
        if post is None:
            import requests
            r = requests.post(f"{API}/traceware/verify", json=body, timeout=4,
                              headers={"X-API-KEY": os.environ["REZOLVE_API_KEY"]})
            r.raise_for_status()
            data = r.json()
        else:  # injected for tests
            data = post(body)
        decision = (data.get("result") or {}).get("decision") or data.get("decision")
    except Exception as e:  # the agent's own truth check already passed; don't drop the turn
        error = f"{type(e).__name__}: {e}"
    log = os.getenv("TRACEWARE_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": turn_id, "decision": decision, "error": error, "text": text,
                                "ms": round(1000 * (time.perf_counter() - t0), 1)}, ensure_ascii=False) + "\n")
    return decision
