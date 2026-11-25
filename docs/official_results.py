"""Run the starter kit's evaluate.py for FairDeal AI and the kit's example seller, and save the results.

    python docs/official_results.py

Writes:
  outputs/official_eval.txt     evaluate.py's report for FairDeal AI on the default run (seed 0)
  outputs/official_run.jsonl    every negotiation of that run (evaluate.py --log), as the rules ask
  outputs/official_results.json scores for both sellers on seeds 0-6
  outputs/OFFICIAL.md           the same, readable
Seeds 0-2 were used to tune FairDeal AI's settings; seeds 3-6 were not.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "ps2-selling-to-machines"
OUT = ROOT / "outputs"
SEEDS = range(7)
FIELDS = {"score": r"SCORE\s+([\d.-]+)", "deal_rate": r"deal rate\s+([\d.]+)",
          "deal_rate_possible": r"where possible ([\d.]+)", "margin_kept": r"margin kept\s+([\d.]+)",
          "value": r"value\s+([\d.]+)", "policy_violations": r"policy violations\s+(\d+)",
          "truth_violations": r"truth violations\s+(\d+)", "deadlocks": r"deadlocks\s+(\d+)",
          "latency_ms": r"latency\s+([\d.]+) ms"}


def run(seller, seed, log=None):
    cmd = [sys.executable, "evaluate.py", "--seed", str(seed)]
    if seller:
        cmd += ["--seller", seller]
    if log:
        cmd += ["--log", str(log)]
    out = subprocess.run(cmd, cwd=KIT, capture_output=True, text=True, check=True).stdout
    return out, {k: float(re.search(rx, out).group(1)) for k, rx in FIELDS.items() if re.search(rx, out)}


def main():
    OUT.mkdir(exist_ok=True)
    text, _ = run("../fairdeal_seller.py", 0, OUT / "official_run.jsonl")
    (OUT / "official_eval.txt").write_text(text)
    res = {"fairdeal": {}, "baseline": {}}
    for s in SEEDS:
        res["fairdeal"][s] = run("../fairdeal_seller.py", s)[1]
        res["baseline"][s] = run(None, s)[1]
    mean = lambda who, seeds, k: sum(res[who][s][k] for s in seeds) / len(seeds)
    held = [s for s in SEEDS if s >= 3]
    res["summary"] = {
        "default_run": {"fairdeal": res["fairdeal"][0], "baseline": res["baseline"][0]},
        "held_out_mean_score": {"fairdeal": round(mean("fairdeal", held, "score"), 1),
                                "baseline": round(mean("baseline", held, "score"), 1)},
        "all_seeds_mean_score": {"fairdeal": round(mean("fairdeal", SEEDS, "score"), 1),
                                 "baseline": round(mean("baseline", SEEDS, "score"), 1)},
        "violations_all_seeds": int(sum(res["fairdeal"][s]["policy_violations"] + res["fairdeal"][s]["truth_violations"]
                                        for s in SEEDS)),
        "deadlocks_all_seeds": int(sum(res["fairdeal"][s]["deadlocks"] for s in SEEDS)),
    }
    (OUT / "official_results.json").write_text(json.dumps(res, indent=2))
    d, b = res["fairdeal"][0], res["baseline"][0]
    md = ["# Official starter-kit results\n",
          "`ps2-selling-to-machines/evaluate.py`, 210 negotiations per seed against the kit's buyer bots. "
          "Seeds 0-2 were used to tune FairDeal AI; seeds 3-6 were not. The leaderboard uses hidden LLM buyers instead.\n",
          "## Default run (seed 0)\n", "| | FairDeal AI | Kit example seller |", "|---|---|---|"]
    for k in ("score", "deal_rate_possible", "margin_kept", "value", "policy_violations", "truth_violations", "deadlocks"):
        md.append(f"| {k.replace('_', ' ')} | **{d[k]:g}** | {b[k]:g} |")
    md += ["\n## Every seed (score)\n", "| seed | FairDeal AI | example seller | used for tuning |", "|---|---|---|---|"]
    for s in SEEDS:
        md.append(f"| {s} | {res['fairdeal'][s]['score']:g} | {res['baseline'][s]['score']:g} | {'yes' if s < 3 else 'no'} |")
    sm = res["summary"]
    md.append(f"\nHeld-out seeds 3-6: FairDeal AI **{sm['held_out_mean_score']['fairdeal']}** vs "
              f"{sm['held_out_mean_score']['baseline']}. Across all 7 seeds (1,470 negotiations): "
              f"{sm['violations_all_seeds']} violations, {sm['deadlocks_all_seeds']} deadlocks.\n")
    (OUT / "OFFICIAL.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    main()
