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

Making it faster (LLM buyers are slow -- every candidate is n x ~10 model calls):

    python tune.py --buyers llm persona --n 20 --seeds 1 --quick          # 8 combos, not 108
    python tune.py ... --max-combos 20                                    # random sample of the grid
    python tune.py ... --grid '{"end_x": [0.05, 0.15], "firm_from_round": [3, 4]}'  # override some axes
    python tune.py ... --workers 4    # run candidates in parallel (needs OLLAMA_NUM_PARALLEL>=4 to help)

Every finished candidate is appended to outputs/tune_progress.jsonl. Ctrl+C still writes
TUNING.md from what finished, and --resume skips candidates already in that file
(same objective / buyers / n / seeds).

Metrics available to --objective: deal_rate, margin_kept, deal_rate_x_margin_kept,
profit_captured_of_max, deadlock_rate, policy_violations, truthfulness_errors,
deal_rate_when_deal_possible, avg_rounds_to_deal.
"""
from __future__ import annotations

import argparse
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
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
# --quick: the two axes that moved the score most in early runs, the rest pinned
QUICK_GRID = {
    "boulware": [1.0],
    "end_x": [0.05, 0.15],
    "open_single": [0.92],
    "reciprocity": [0.2, 0.4],
    "firm_from_round": [3, 4],
}
SAFE = {"policy_violations", "truthfulness_errors"}
PROGRESS = ROOT / "outputs/tune_progress.jsonl"


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
    ap.add_argument("--quick", action="store_true", help="small 8-candidate grid")
    ap.add_argument("--grid", default=None, help='JSON overriding grid axes, e.g. {"end_x": [0.05, 0.15]}')
    ap.add_argument("--max-combos", type=int, default=0, help="randomly sample at most this many candidates")
    ap.add_argument("--workers", type=int, default=1, help="candidates evaluated in parallel")
    ap.add_argument("--resume", action="store_true", help="skip candidates already in outputs/tune_progress.jsonl")
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

    grid = dict(QUICK_GRID if a.quick else GRID)
    if a.grid:
        extra = json.loads(a.grid)
        unknown = set(extra) - set(GRID)
        if unknown:
            ap.error(f"--grid has unknown keys {sorted(unknown)}; allowed: {list(GRID)}")
        grid.update(extra)
    keys = list(grid)
    combos = [dict(zip(keys, c)) for c in itertools.product(*grid.values())]
    if a.max_combos and a.max_combos < len(combos):
        combos = random.Random(0).sample(combos, a.max_combos)

    run_id = {"objective": a.score_cmd or a.objective, "buyers": sorted(a.buyers), "n": a.n, "seeds": a.seeds}
    key_of = lambda kw: json.dumps(kw, sort_keys=True)
    done = {}
    if a.resume and PROGRESS.exists():
        for line in PROGRESS.read_text().splitlines():
            rec = json.loads(line)
            if rec.get("run") == run_id:
                done[key_of(rec["params"])] = rec
    wanted = {key_of(c) for c in combos}
    results = [(r["value"], r["params"], r["metrics"]) for k, r in done.items() if k in wanted]
    todo = [c for c in combos if key_of(c) not in done]
    print(f"{len(combos)} candidates, {len(combos) - len(todo)} already done, {len(todo)} to run", flush=True)

    def evaluate(kw):
        vals, metrics = [], []
        for s in a.seeds:
            v, m = objective_value(logs_for(Params(**kw), a.buyers, a.n, s), a.objective, a.score_cmd, items, pol)
            vals.append(v)
            metrics.append(m)
        return sum(vals) / len(vals), kw, metrics

    PROGRESS.parent.mkdir(exist_ok=True)
    pool = ThreadPoolExecutor(max_workers=max(1, a.workers))
    try:
        futures = [pool.submit(evaluate, kw) for kw in todo]
        for i, fut in enumerate(as_completed(futures), 1):
            mean, kw, metrics = fut.result()
            results.append((mean, kw, metrics))
            with PROGRESS.open("a") as f:
                f.write(json.dumps({"run": run_id, "params": kw, "value": mean, "metrics": metrics}) + "\n")
            print(f"[{i}/{len(todo)}] {mean:.4f} {kw}", flush=True)
    except KeyboardInterrupt:
        print(f"\ninterrupted: writing results for {len(results)} finished candidates "
              "(rerun with --resume to continue)", flush=True)
        pool.shutdown(wait=False, cancel_futures=True)
    else:
        pool.shutdown()
    if not results:
        return
    results.sort(key=lambda r: -r[0])
    default = Params()
    md = ["# Tuning results\n", f"Objective: `{a.score_cmd or a.objective}` · buyers: {', '.join(sorted(set(a.buyers)))} "
          f"· {a.n} negotiations × seeds {a.seeds}\n",
          "| Rank | Objective | " + " | ".join(keys) + " | deal rate | margin kept |",
          "|---|---|" + "---|" * len(keys) + "---|---|"]
    for rank, (v, kw, ms) in enumerate(results[:10], 1):
        ms = [m for m in ms or [] if m]
        dr = f"{sum(m['deal_rate'] for m in ms) / len(ms):.3f}" if ms else "-"
        mk = f"{sum(m['margin_kept'] for m in ms) / len(ms):.3f}" if ms else "-"
        md.append(f"| {rank} | {v:.4f} | " + " | ".join(str(kw.get(k, "")) for k in keys) + f" | {dr} | {mk} |")
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
