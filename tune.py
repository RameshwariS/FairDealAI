"""Tune the negotiation settings against a chosen scoring rule and buyer set.

Use this once the official kit is in: copy its scoring formula into --objective
(or point --score-cmd at its evaluate.py), pick the buyers closest to the
hidden ones (LLM buyers), and let it search.

    # our scorer, mixed bots, default objective
    python tune.py

    # the official formula, once you have read it in evaluate.py (any metric names below)
    python tune.py --objective "deal_rate * margin_kept - 2 * deadlock_rate"

    # LLM buyers (slow: keep --n small), see harness/llm_buyer.py for setup
    python tune.py --buyers llm --n 20 --seeds 1

    # score each candidate with an external command; {log} is replaced by a JSONL log path,
    # and the LAST number it prints is used as the score
    python tune.py --score-cmd "python ../kit/evaluate.py --log {log}"

    python tune.py --apply      # also save the winner to data/params.json (SellerAgent loads it)

Metrics available to --objective: deal_rate, margin_kept, deal_rate_x_margin_kept,
profit_captured_of_max, deadlock_rate, policy_violations, truthfulness_errors,
deal_rate_when_deal_possible, avg_rounds_to_deal.
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from seller import Params, SellerAgent  # noqa: E402
from harness.evaluate import load, score  # noqa: E402
from harness.run import make_buyer, make_scenarios, negotiate  # noqa: E402

GRID = {
    "boulware": [1.0, 1.6, 2.4],
    "end_x": [0.0, 0.05, 0.15],
    "open_single": [0.92, 1.0],
    "reciprocity": [0.2, 0.4],
    "firm_from_round": [3, 4, 6],
}
SAFE = {"policy_violations", "truthfulness_errors"}


def logs_for(params, buyers, n, seed):
    agent = SellerAgent(params=params)
    rng = random.Random(seed + 1)
    out = []
    for sc in make_scenarios(agent.catalog, n, seed):
        kind = rng.choice(buyers)
        if kind == "llm":
            from harness.llm_buyer import PERSONAS, LLMBuyer
            buyer = LLMBuyer(list(sc["lines"]), sc["list_total"], sc["wtp"], rng.choice(list(PERSONAS)),
                             agent.catalog)
        else:
            buyer = make_buyer(kind, sc, agent.catalog)
        r = negotiate(agent, buyer)
        r.update({"scenario": sc["id"], "buyer_kind": kind, "lines": sc["lines"], "list_total": sc["list_total"]})
        out.append(r)
    return out


def objective_value(logs, expr, score_cmd, items, pol):
    m = score(logs, items, pol)
    if score_cmd:
        with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
            for r in logs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        res = subprocess.run(score_cmd.format(log=f.name), shell=True, capture_output=True, text=True)
        nums = re.findall(r"-?\d+(?:\.\d+)?", res.stdout)
        value = float(nums[-1]) if nums else float("-inf")
    else:
        names = {k: v for k, v in m.items() if isinstance(v, (int, float))}
        value = eval(expr, {"__builtins__": {}}, names)  # expression typed by you on the command line
    if any(m[k] for k in SAFE):
        value = float("-inf")  # never pick settings that break policy or truthfulness
    return value, m


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--objective", default="deal_rate_x_margin_kept")
    ap.add_argument("--score-cmd", default=None)
    ap.add_argument("--buyers", nargs="+", default=["cooperative", "hard_bargainer", "manipulator",
                                                    "persona", "persona", "persona"])
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2])
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    items, pol = load()

    if not a.score_cmd:
        # Catch placeholders such as "..." (which Python evaluates as Ellipsis)
        # before running the expensive candidate simulations.
        metric_names = {
            "deal_rate", "margin_kept", "deal_rate_x_margin_kept",
            "profit_captured_of_max", "deadlock_rate", "policy_violations",
            "truthfulness_errors", "deal_rate_when_deal_possible", "avg_rounds_to_deal",
        }
        try:
            probe = eval(a.objective, {"__builtins__": {}}, {name: 0 for name in metric_names})
        except Exception as e:
            ap.error(f"invalid --objective: {e}. Use a numeric expression over: {', '.join(sorted(metric_names))}")
        if isinstance(probe, bool) or not isinstance(probe, (int, float)):
            ap.error("--objective must evaluate to a number; replace placeholder expressions such as '...' with a formula")

    keys = list(GRID)
    results = []
    combos = list(itertools.product(*GRID.values()))
    for i, combo in enumerate(combos, 1):
        kw = dict(zip(keys, combo))
        vals, metrics = [], []
        for s in a.seeds:
            v, m = objective_value(logs_for(Params(**kw), a.buyers, a.n, s), a.objective, a.score_cmd, items, pol)
            vals.append(v)
            metrics.append(m)
        mean = sum(vals) / len(vals)
        results.append((mean, kw, metrics))
        print(f"[{i}/{len(combos)}] {mean:.4f} {kw}", flush=True)
    results.sort(key=lambda r: -r[0])
    default = Params()
    md = ["# Tuning results\n", f"Objective: `{a.score_cmd or a.objective}` · buyers: {', '.join(sorted(set(a.buyers)))} "
          f"· {a.n} negotiations × seeds {a.seeds}\n",
          "| Rank | Objective | " + " | ".join(keys) + " | deal rate | margin kept |",
          "|---|---|" + "---|" * len(keys) + "---|---|"]
    for rank, (v, kw, ms) in enumerate(results[:10], 1):
        dr = sum(m["deal_rate"] for m in ms) / len(ms)
        mk = sum(m["margin_kept"] for m in ms) / len(ms)
        md.append(f"| {rank} | {v:.4f} | " + " | ".join(str(kw[k]) for k in keys) + f" | {dr:.3f} | {mk:.3f} |")
    md.append("\nCurrent defaults: " + ", ".join(f"{k}={getattr(default, k)}" for k in keys))
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs/TUNING.md").write_text("\n".join(md))
    best = results[0][1]
    print("\n".join(md))
    if a.apply:
        (ROOT / "data/params.json").write_text(json.dumps(best, indent=2))
        print("saved data/params.json; SellerAgent will load it")


if __name__ == "__main__":
    main()
