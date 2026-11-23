"""Run the full local benchmark and write outputs/.

    python benchmark.py            # ~200 negotiations per seller (matches the official run size)

Writes:
  outputs/fairdeal_run.jsonl     every message of every negotiation (FairDeal AI)
  outputs/naive_run.jsonl     same scenarios, naive baseline seller
  outputs/results.json        scores for both
  outputs/RESULTS.md          readable summary
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from harness.evaluate import load, score  # noqa: E402
from harness.run import run  # noqa: E402

N, SEED = 200, 42  # seed 42 was NOT used for tuning (tuning used seed 1)


def table(rows):
    keys = ["deal_rate", "margin_kept", "deal_rate_x_margin_kept", "profit_captured_of_max",
            "policy_violations", "below_cost_deals", "deadlock_rate", "truthfulness_errors", "avg_rounds_to_deal"]
    out = "| metric | " + " | ".join(rows) + " |\n|---|" + "---|" * len(rows) + "\n"
    for k in keys:
        out += f"| {k} | " + " | ".join(str(rows[r][k]) for r in rows) + " |\n"
    return out


def main():
    items, pol = load()
    res = {}
    for seller in ("fairdeal", "naive"):
        logs = run(seller, N, SEED, ROOT / f"outputs/{seller}_run.jsonl", quiet=True)
        res[seller] = score(logs, items, pol)
    # per-buyer view on the three starter-kit style bots only
    per_bot = {}
    for bot in ("cooperative", "hard_bargainer", "manipulator", "persona"):
        logs = run("fairdeal", 100, SEED, None, buyers=[bot], quiet=True)
        s = score(logs, items, pol)
        per_bot[bot] = {k: s[k] for k in ("deal_rate", "margin_kept", "policy_violations",
                                          "deadlock_rate", "truthfulness_errors")}
    res["fairdeal_per_buyer"] = per_bot
    (ROOT / "outputs/results.json").write_text(json.dumps(
        {k: ({kk: vv for kk, vv in v.items() if kk != "examples"} if isinstance(v, dict) else v)
         for k, v in res.items()}, indent=2))
    md = f"# Local benchmark results\n\n{N} negotiations, seed {SEED} (held out from tuning), max 10 rounds.\n"
    md += "Buyers: cooperative, hard bargainer, manipulator (1:1:1) + randomised agentic-style personas (x3 weight).\n\n"
    md += table({"FairDeal AI": res["fairdeal"], "Naive baseline": res["naive"]})
    md += "\n## FairDeal AI by buyer type (100 negotiations each)\n\n| buyer | deal rate | margin kept | violations | deadlock | truth errors |\n|---|---|---|---|---|---|\n"
    for b, s in per_bot.items():
        md += f"| {b} | {s['deal_rate']} | {s['margin_kept']} | {s['policy_violations']} | {s['deadlock_rate']} | {s['truthfulness_errors']} |\n"
    md += ("\nmargin_kept = (price - cost) / (list - cost), averaged over deals. "
           "Some scenarios have no possible deal (buyer budget below the policy floor); walking away is correct there. "
           f"Deal rate when a deal was possible: {res['fairdeal']['deal_rate_when_deal_possible']}.\n")
    (ROOT / "outputs/RESULTS.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
