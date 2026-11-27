"""Run the 12-persona buyer suite against FairDeal AI and the kit's example seller; score with the kit's evaluate.py.

    python run_suite.py --mode rule --seeds 0 1 2 --n-per 30                     # rule-based personas
    python run_suite.py --mode llm --model llama3.2:latest --seeds 0 1 2 --n-per 3 --workers 4
    python run_suite.py --mode rule --personas heldout                           # only the 4 held-out personas
    python run_suite.py --mode rule --params '{"project_limit": false}' --label no_projection --sellers fairdeal

Scoring uses ps2-selling-to-machines/evaluate.py's own score_one() and summarise() (not a home-made metric).
Writes to outputs/suite/<label>/: transcripts.jsonl (every negotiation, both sellers), summary.json, REPORT.md.
LLM settings: --model/--base-url/--temperature/--timeout/--llm-seed, or LLM_MODEL, LLM_BASE_URL, LLM_TEMPERATURE,
LLM_TIMEOUT, LLM_SEED. API keys only ever come from the environment (LLM_API_KEY).
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
KIT = ROOT / "ps2-selling-to-machines"
sys.path.insert(0, str(KIT))  # the kit's harness.py / buyers.py / evaluate.py must win over our harness/ package
for _m in ("harness", "buyers"):
    if _m in sys.modules and not str(getattr(sys.modules[_m], "__file__", "")).startswith(str(KIT)):
        del sys.modules[_m]

import evaluate as kit_eval  # noqa: E402
import buyers as kit_buyers  # noqa: E402
from harness import load_class, load_policy, load_store  # noqa: E402

sys.path.append(str(ROOT))
import buyer_suite  # noqa: E402

METRICS = ("score", "deal_rate", "feasible_deal_rate", "margin_kept", "value", "policy", "truth", "deadlocks", "rounds")


def scenarios_for(store, policy, classes, n_per, seed):
    scs = kit_buyers.make_scenarios(store, policy, n_per * len(classes), seed, classes)
    for sc in scs:  # bundle hunters need a basket they can change: single-line baskets become 2-3 units
        cls = classes[sc["buyer"]]
        if getattr(cls, "multi_unit", False) and len(sc["items"]) == 1 and sc["items"][0]["qty"] == 1:
            stock = store[sc["items"][0]["sku"]]["stock"]
            if stock >= 2:
                sc["items"][0]["qty"] = min(3, stock)  # one SKU: the floor share of list (so feasibility) is unchanged
    return scs


def seller_class(name, params):
    if name == "example":
        return load_class(str(KIT / "example_seller.py"), "Seller")
    base = load_class(str(ROOT / "fairdeal_seller.py"), "Seller")
    if not params:
        return base
    from seller.pricing import Params

    class Tuned(base):
        def __init__(self, store, policy):
            super().__init__(store, policy)
            self.agent.params = Params(**{**self.agent.params.__dict__, **params})
    return Tuned


def agg(per_seed):
    """per_seed: list of summarise() dicts -> {metric: (mean, std)}"""
    out = {}
    for k in METRICS:
        xs = [s[k] for s in per_seed]
        out[k] = (statistics.mean(xs), statistics.stdev(xs) if len(xs) > 1 else 0.0)
    out["n"] = sum(s["n"] for s in per_seed)
    return out


def fmt(m, k, d=1):
    mean, std = m[k]
    scale = 100 if k in ("deal_rate", "feasible_deal_rate", "margin_kept", "value") else 1
    return f"{mean * scale:.{d}f} ± {std * scale:.{d}f}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=("rule", "llm"), default="rule")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--n-per", type=int, default=30, help="negotiations per persona per seed (sample count)")
    ap.add_argument("--personas", nargs="+", default=["all"], help="names, or all / tune / heldout")
    ap.add_argument("--sellers", nargs="+", default=["fairdeal", "example"])
    ap.add_argument("--params", default="", help="JSON overrides for FairDeal's Params (ablation)")
    ap.add_argument("--label", default="")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--model"), ap.add_argument("--base-url"), ap.add_argument("--temperature", type=float)
    ap.add_argument("--timeout", type=float), ap.add_argument("--llm-seed", type=int)
    a = ap.parse_args()

    pool = buyer_suite.LLM_BUYERS if a.mode == "llm" else buyer_suite.BUYERS
    sel = set(a.personas)
    names = [n for n in buyer_suite.BUYERS
             if "all" in sel or n in sel or ("heldout" in sel and n in buyer_suite.HELD_OUT)
             or ("tune" in sel and n not in buyer_suite.HELD_OUT)]
    classes = {n: pool[n] for n in names}
    for k, v in (("model", a.model), ("base_url", a.base_url), ("temperature", a.temperature),
                 ("timeout", a.timeout), ("seed", a.llm_seed)):
        if v is not None:
            buyer_suite.LLM_CONFIG[k] = v
    params = json.loads(a.params) if a.params else {}
    label = a.label or (a.mode if a.mode == "rule" else f"llm_{buyer_suite.LLM_CONFIG['model'].replace(':', '_')}")
    out_dir = ROOT / "outputs/suite" / label
    out_dir.mkdir(parents=True, exist_ok=True)

    store, policy = load_store(), load_policy()
    rows = {s: {} for s in a.sellers}  # seller -> seed -> list of score rows
    llm_totals = {}
    t0 = time.time()
    with open(out_dir / "transcripts.jsonl", "w", encoding="utf-8") as fh:
        for seed in a.seeds:
            scs = scenarios_for(store, policy, classes, a.n_per, seed)
            for s in a.sellers:
                buyer_suite.LLM_STATS.clear()
                results, transcripts, _ = kit_eval.run(seller_class(s, params if s == "fairdeal" else {}), scs,
                                                       classes, store, policy, a.workers)
                rows[s][seed] = results
                for r, t, sc in zip(results, transcripts, scs):
                    st = buyer_suite.LLM_STATS.get(sc["id"], {})
                    for k, v in st.items():
                        llm_totals.setdefault(s, {}).setdefault(k, 0)
                        llm_totals[s][k] += v
                    fh.write(json.dumps({"seller": s, "seed": seed, "mode": a.mode, **r, "scenario": sc,
                                         "llm_turn_stats": st, "transcript": t["transcript"]},
                                        ensure_ascii=False) + "\n")
                sm = kit_eval.summarise(results)
                print(f"seed {seed} {s:9} score {sm['score']:.1f}  deals {sm['deal_rate']:.2f}  "
                      f"policy {sm['policy']} truth {sm['truth']} deadlocks {sm['deadlocks']}  "
                      f"({time.time() - t0:.0f}s)", flush=True)

    groups = {"overall": names, "tuning personas": [n for n in names if n not in buyer_suite.HELD_OUT],
              "held-out personas": [n for n in names if n in buyer_suite.HELD_OUT]}
    summary = {"mode": a.mode, "seeds": a.seeds, "n_per_persona_per_seed": a.n_per, "personas": names,
               "params": params, "llm": dict(buyer_suite.LLM_CONFIG, api_key="(env)") if a.mode == "llm" else None,
               "llm_turn_stats": llm_totals, "results": {}}
    for s in a.sellers:
        res = {}
        for g, members in list(groups.items()) + [(n, [n]) for n in names]:
            if not members:
                continue
            per_seed = [kit_eval.summarise([r for r in rows[s][sd] if r["buyer"] in members]) for sd in a.seeds]
            res[g] = agg(per_seed)
        summary["results"][s] = res
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    hdr = f"# Buyer suite: {label}\n\n"
    if a.mode == "llm":
        c = buyer_suite.LLM_CONFIG
        hdr += (f"**Local LLM buyers, not the hidden leaderboard.** Model `{c['model']}`, temperature {c['temperature']}, "
                f"LLM seed {c['seed']}, timeout {c['timeout']}s.\n\n")
    else:
        hdr += "Rule-based personas (no model).\n\n"
    hdr += (f"Seeds {a.seeds} × {len(names)} personas × {a.n_per} negotiations per persona per seed "
            f"= {len(a.seeds) * len(names) * a.n_per} negotiations per seller. Scored with the kit's "
            f"`evaluate.score_one` / `summarise`; mean ± std across seeds. Held out (never used for tuning): "
            f"{', '.join(buyer_suite.HELD_OUT)}.\n" + (f"\nFairDeal Params overrides: `{params}`\n" if params else ""))
    md = [hdr]
    if llm_totals:
        md.append("LLM turn stats (how often the model's own move was used): " +
                  "; ".join(f"{s}: " + ", ".join(f"{k} {v}" for k, v in sorted(t.items())) for s, t in llm_totals.items()) + "\n")
    md += ["| group / persona | seller | score | deal rate % | margin kept % | policy | truth | deadlocks | rounds |",
           "|---|---|---|---|---|---|---|---|---|"]
    for g in summary["results"][a.sellers[0]]:
        for s in a.sellers:
            m = summary["results"][s][g]
            md.append(f"| {g}{' (held out)' if g in buyer_suite.HELD_OUT else ''} | {s} | {fmt(m, 'score')} | "
                      f"{fmt(m, 'deal_rate')} | {fmt(m, 'margin_kept')} | {fmt(m, 'policy', 0)} | {fmt(m, 'truth', 0)} | "
                      f"{fmt(m, 'deadlocks', 1)} | {fmt(m, 'rounds')} |")
    (out_dir / "REPORT.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nwrote {out_dir}")


if __name__ == "__main__":
    main()
