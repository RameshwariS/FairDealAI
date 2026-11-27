"""Ablation for the v2 fixes: each flag on/off, scored with the kit's evaluate.py functions.

    python run_ablation_v2.py                 # -> outputs/ABLATION_V2.md, outputs/ablation_v2.json

For every configuration:
  official   kit buyers, 210 negotiations x seeds 0-6 (mean, and held-out seeds 3-6 separately)
  suite      the 12 rule-based personas of buyer_suite.py, 30 per persona x seeds 0-2,
             split into tuning personas and the 4 held-out personas
Keep rule (all must hold vs v1): official 7-seed mean doesn't drop; held-out personas don't get worse;
0 policy and 0 truth violations. (Video lock + full pytest are checked separately on the final config.)
"""
from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

import run_suite as rs  # sets up the kit import path

ROOT = Path(__file__).resolve().parent
store, policy = rs.load_store(), rs.load_policy()

CONFIGS = [
    ("v1 (all fixes off)", {}),
    ("F1 basket_growth", {"basket_growth": True}),
    ("F2 implied_bid_floor", {"implied_bid_floor": True}),
    ("F3 r10_fit_gate=0.02", {"r10_fit_gate": 0.02}),
    ("F3 r10_fit_gate=0.05", {"r10_fit_gate": 0.05}),
    ("F4 hold_when_static", {"hold_when_static": True}),
]


def evaluate(params, cache={}):
    cls = rs.seller_class("fairdeal", params)
    off, held = [], []
    pol = tru = dead = 0
    for seed in range(7):
        scs = rs.kit_buyers.make_scenarios(store, policy, 210, seed)
        sm = rs.kit_eval.summarise(rs.kit_eval.run(cls, scs, rs.kit_buyers.BUYERS, store, policy)[0])
        off.append(sm["score"])
        pol, tru, dead = pol + sm["policy"], tru + sm["truth"], dead + sm["deadlocks"]
    tune_s, held_s, per = [], [], {}
    for seed in (0, 1, 2):
        scs = rs.scenarios_for(store, policy, rs.buyer_suite.BUYERS, 30, seed)
        res = rs.kit_eval.run(cls, scs, rs.buyer_suite.BUYERS, store, policy)[0]
        t = [r for r in res if r["buyer"] not in rs.buyer_suite.HELD_OUT]
        h = [r for r in res if r["buyer"] in rs.buyer_suite.HELD_OUT]
        tune_s.append(rs.kit_eval.summarise(t)["score"])
        held_s.append(rs.kit_eval.summarise(h)["score"])
        for name in rs.buyer_suite.BUYERS:
            per.setdefault(name, []).append(rs.kit_eval.summarise([r for r in res if r["buyer"] == name])["score"])
        s_all = rs.kit_eval.summarise(res)
        pol, tru, dead = pol + s_all["policy"], tru + s_all["truth"], dead + s_all["deadlocks"]
    m = statistics.mean
    return {"official_mean": m(off), "official_std": statistics.stdev(off), "official_heldout_3_6": m(off[3:]),
            "official_seeds": off, "suite_tuning": m(tune_s), "suite_heldout": m(held_s),
            "suite_heldout_std": statistics.stdev(held_s),
            "per_persona": {k: m(v) for k, v in per.items()}, "policy": pol, "truth": tru, "deadlocks": dead}


def verdict(r, base):
    ok = (r["official_mean"] >= base["official_mean"] - 1e-9 and r["suite_heldout"] >= base["suite_heldout"] - 1e-9
          and r["policy"] == 0 and r["truth"] == 0)
    return "keep" if ok else "reject"


def main(configs=CONFIGS, extra=()):
    results = []
    for name, params in list(configs) + list(extra):
        r = evaluate(params)
        results.append((name, params, r))
        print(f"{name:34} official {r['official_mean']:.2f} (3-6 {r['official_heldout_3_6']:.2f})  "
              f"suite tune {r['suite_tuning']:.2f} held-out {r['suite_heldout']:.2f}  "
              f"pol {r['policy']} truth {r['truth']} deadlocks {r['deadlocks']}", flush=True)
    base = results[0][2]
    md = ["# Ablation v2: each fix on/off\n",
          "Official = `ps2-selling-to-machines/evaluate.py` scoring, kit buyers, 210 negotiations × seeds 0-6. "
          "Suite = the 12 rule-based personas (`buyer_suite.py`), 30 each × seeds 0-2, scored with the kit's "
          "`score_one`/`summarise`. Held-out personas (late_sniper, emotional, bundle_hunter, unpredictable) were "
          "never used to choose settings. Violations and deadlocks are summed over all official and suite runs. "
          "Keep rule vs v1: official mean must not drop, held-out personas must not get worse, 0 violations.\n",
          "| config | official mean ± std (0-6) | official held-out seeds 3-6 | suite tuning personas | "
          "suite held-out personas | policy | truth | deadlocks | verdict |", "|---|---|---|---|---|---|---|---|---|"]
    for name, params, r in results:
        v = "baseline" if r is base else verdict(r, base)
        md.append(f"| {name} | {r['official_mean']:.2f} ± {r['official_std']:.2f} | {r['official_heldout_3_6']:.2f} | "
                  f"{r['suite_tuning']:.2f} | {r['suite_heldout']:.2f} ± {r['suite_heldout_std']:.2f} | {r['policy']} | "
                  f"{r['truth']} | {r['deadlocks']} | {v} |")
    names = list(base["per_persona"])
    md += ["\n## Per persona (suite score, mean of seeds 0-2)\n",
           "| config | " + " | ".join(n + (" (H)" if n in rs.buyer_suite.HELD_OUT else "") for n in names) + " |",
           "|---|" + "---|" * len(names)]
    for name, _, r in results:
        md.append(f"| {name} | " + " | ".join(f"{r['per_persona'][n]:.1f}" for n in names) + " |")
    (ROOT / "outputs/ABLATION_V2.md").write_text("\n".join(md) + "\n")
    (ROOT / "outputs/ablation_v2.json").write_text(json.dumps(
        [{"config": n, "params": p, **r} for n, p, r in results], indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    extra = [(a, json.loads(b)) for a, b in zip(sys.argv[1::2], sys.argv[2::2])]
    main(extra=extra)
