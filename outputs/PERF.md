# Latency, throughput and cost

Measured on the development machine (one Python process, no model calls). A different CPU will give different absolute numbers; rerun `python -m harness.perf` on the target VM.

| Path | Turns timed | Mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|---|---|
| In-process (agent only) | 5,629 | 0.133 | 0.128 | 0.192 | 0.236 |
| Over HTTP, 8 concurrent clients | 2,239 | 9.126 | 6.663 | 9.574 | 11.637 |

Average turns per negotiation: 5.6.

HTTP throughput: **128 full negotiations per second** (714 turns per second) from one server process. The test clients ran in the same process and shared its CPU, so this is a conservative figure.

## Cost

| Item | Value |
|---|---|
| Server | AWS t3.small, Mumbai, on-demand at $0.0224/hour |
| Server time for 1 million negotiations | 130.6 minutes |
| Compute cost per 1 million negotiations | **$0.0488** |
| Server cost for a month, always on | $16.35 |
| LLM calls on the core path | 0 |

Optional LLM wording or parsing adds one small-model call per turn; with a local model (Ollama) that costs no API fees, only CPU/GPU time.

Source for the price: https://www.doit.com/compute/spot/ap-south-1/t3.small (checked Nov 2026).