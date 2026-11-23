"""Latency, throughput and cost measurement -> outputs/PERF.md

    python -m harness.perf

1. In-process: time every SellerAgent.respond call over many negotiations.
2. Over HTTP: start server.py's handler in a thread and drive it with
   concurrent clients, each running full negotiations.
Cost per 1M negotiations is derived from measured HTTP throughput and an
AWS on-demand price (constant below, with its source).
"""
from __future__ import annotations

import json
import random
import statistics
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from seller import SellerAgent  # noqa: E402
from harness.run import make_buyer, make_scenarios  # noqa: E402

# AWS EC2 t3.small (2 vCPU, 2 GiB), Asia Pacific (Mumbai) on-demand, Nov 2026:
# $0.0224/hour -- https://www.doit.com/compute/spot/ap-south-1/t3.small
VM_NAME, VM_USD_PER_HOUR = "AWS t3.small, Mumbai, on-demand", 0.0224


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


def in_process(n=1000, seed=9):
    agent = SellerAgent()
    times, turns = [], 0
    for sc in make_scenarios(agent.catalog, n, seed):
        buyer = make_buyer("persona", sc, agent.catalog)
        agent.reset()
        last = None
        for rnd in range(1, 11):
            b = {**buyer.act(rnd, last), "round": rnd, "max_rounds": 10}
            if b.get("type") == "walk_away":
                break
            t0 = time.perf_counter()
            last = agent.respond(b)
            times.append((time.perf_counter() - t0) * 1000)
            turns += 1
            if last["type"] in ("accept", "walk_away", "end"):
                break
    return times, turns / n


def over_http(n=400, workers=8, seed=11):
    import server
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    cat = SellerAgent().catalog
    scenarios = make_scenarios(cat, n, seed)
    lat, lock = [], threading.Lock()

    def post(path, body):
        req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())

    def one(sc):
        sid = f"s{sc['id']}"
        buyer, last, mine = make_buyer("persona", sc, cat), None, []
        for rnd in range(1, 11):
            b = {**buyer.act(rnd, last), "round": rnd, "max_rounds": 10}
            if b.get("type") == "walk_away":
                break
            t0 = time.perf_counter()
            last = post("/negotiate", {"session_id": sid, "message": b})
            mine.append((time.perf_counter() - t0) * 1000)
            if last["type"] in ("accept", "walk_away", "end"):
                break
        post("/reset", {"session_id": sid})
        with lock:
            lat.extend(mine)

    t0 = time.perf_counter()
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, scenarios))
    wall = time.perf_counter() - t0
    httpd.shutdown()
    return lat, wall, n


def main():
    random.seed(0)
    t_in, turns_per = in_process()
    t_http, wall, n = over_http()
    neg_per_s = n / wall
    hours_per_million = 1e6 / neg_per_s / 3600
    usd_per_million = hours_per_million * VM_USD_PER_HOUR
    rows = [("In-process (agent only)", t_in), ("Over HTTP, 8 concurrent clients", t_http)]
    md = ["# Latency, throughput and cost\n",
          "Measured on the development machine (one Python process, no model calls). "
          "A different CPU will give different absolute numbers; rerun `python -m harness.perf` on the target VM.\n",
          "| Path | Turns timed | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) |", "|---|---|---|---|---|---|"]
    for name, xs in rows:
        md.append(f"| {name} | {len(xs):,} | {statistics.mean(xs):.3f} | {pct(xs, 50):.3f} | "
                  f"{pct(xs, 95):.3f} | {pct(xs, 99):.3f} |")
    md += [f"\nAverage turns per negotiation: {turns_per:.1f}.",
           f"\nHTTP throughput: **{neg_per_s:,.0f} full negotiations per second** "
           f"({len(t_http) / wall:,.0f} turns per second) from one server process. The test clients ran in the "
           "same process and shared its CPU, so this is a conservative figure.\n",
           "## Cost\n",
           f"| Item | Value |\n|---|---|\n| Server | {VM_NAME} at ${VM_USD_PER_HOUR}/hour |",
           f"| Server time for 1 million negotiations | {hours_per_million * 60:.1f} minutes |",
           f"| Compute cost per 1 million negotiations | **${usd_per_million:.4f}** |",
           f"| Server cost for a month, always on | ${VM_USD_PER_HOUR * 730:.2f} |",
           "| LLM calls on the core path | 0 |\n",
           "Optional LLM wording or parsing adds one small-model call per turn; with a local model (Ollama) "
           "that costs no API fees, only CPU/GPU time.\n",
           "Source for the price: https://www.doit.com/compute/spot/ap-south-1/t3.small (checked Nov 2026)."]
    (ROOT / "outputs/PERF.md").write_text("\n".join(md))
    json.dump({"in_process_ms": {"mean": statistics.mean(t_in), "p50": pct(t_in, 50), "p95": pct(t_in, 95),
                                 "p99": pct(t_in, 99)},
               "http_ms": {"mean": statistics.mean(t_http), "p50": pct(t_http, 50), "p95": pct(t_http, 95),
                           "p99": pct(t_http, 99)},
               "negotiations_per_second_http": neg_per_s, "usd_per_million_negotiations": usd_per_million},
              open(ROOT / "outputs/perf.json", "w"), indent=2)
    print("\n".join(md))


if __name__ == "__main__":
    main()
