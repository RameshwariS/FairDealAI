# Ablation v2: each fix on/off

Official = `ps2-selling-to-machines/evaluate.py` scoring, kit buyers, 210 negotiations × seeds 0-6. Suite = the 12 rule-based personas (`buyer_suite.py`), 30 each × seeds 0-2, scored with the kit's `score_one`/`summarise`. Held-out personas (late_sniper, emotional, bundle_hunter, unpredictable) were never used to choose settings. Violations and deadlocks are summed over all official and suite runs. Keep rule vs v1: official mean must not drop, held-out personas must not get worse, 0 violations. F5 improves fast_conceder but slightly lowers the aggregate held-out score, so it remains a candidate and is disabled by default pending broader validation.

| config | official mean ± std (0-6) | official held-out seeds 3-6 | suite tuning personas | suite held-out personas | policy | truth | deadlocks | verdict |
|---|---|---|---|---|---|---|---|---|
| v1 (all fixes off) | 49.92 ± 2.28 | 49.20 | 49.22 | 32.13 ± 2.55 | 0 | 0 | 31 | baseline |
| F1 basket_growth | 49.92 ± 2.28 | 49.20 | 49.22 | 44.22 ± 3.22 | 0 | 0 | 8 | keep |
| F2 implied_bid_floor | 49.92 ± 2.28 | 49.20 | 49.22 | 32.13 ± 2.55 | 0 | 0 | 31 | keep |
| F3 r10_fit_gate=0.02 | 47.63 ± 1.65 | 47.09 | 46.92 | 29.61 ± 1.00 | 0 | 0 | 24 | reject |
| F3 r10_fit_gate=0.05 | 49.92 ± 2.28 | 49.20 | 48.37 | 29.54 ± 1.12 | 0 | 0 | 27 | reject |
| F4 hold_when_static | 49.93 ± 2.28 | 49.21 | 48.10 | 31.73 ± 2.62 | 0 | 0 | 31 | reject |
| F5 accept_exhausted | 49.92 ± 2.28 | 49.20 | 50.31 | 32.07 ± 2.49 | 0 | 0 | 31 | candidate |
| F6 taint_keeps_bid | 49.93 ± 2.31 | 49.28 | 49.22 | 38.99 ± 2.72 | 0 | 41 | 7 | reject |
| F1+F2 (kept so far) | 49.92 ± 2.28 | 49.20 | 49.22 | 44.22 ± 3.22 | 0 | 0 | 8 | keep |
| F1+F2+F6 | 49.93 ± 2.31 | 49.28 | 49.22 | 44.22 ± 3.22 | 0 | 0 | 7 | keep |
| F1+F2+F5 | 49.92 ± 2.28 | 49.20 | 50.31 | 44.17 ± 3.16 | 0 | 0 | 8 | candidate |
| F1+F2+F5+F6 | 49.93 ± 2.31 | 49.28 | 50.31 | 44.17 ± 3.16 | 0 | 0 | 7 | candidate |

## Per persona (suite score, mean of seeds 0-2)

| config | cooperative | hard_bargainer | persistent_lowballer | late_sniper (H) | repeated_offer | bundle_hunter (H) | fake_budget | fake_competitor | prompt_injector | emotional (H) | fast_conceder | unpredictable (H) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1 (all fixes off) | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | -1.4 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 36.7 |
| F1 basket_growth | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | 46.9 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 36.7 |
| F2 implied_bid_floor | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | -1.4 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 36.7 |
| F3 r10_fit_gate=0.02 | 73.3 | 34.3 | 38.9 | 29.9 | 49.9 | -1.2 | 48.8 | 45.6 | 23.4 | 52.5 | 61.0 | 37.3 |
| F3 r10_fit_gate=0.05 | 73.3 | 36.7 | 38.9 | 29.9 | 49.9 | -1.4 | 48.8 | 45.6 | 32.6 | 52.5 | 61.0 | 37.3 |
| F4 hold_when_static | 73.4 | 36.7 | 38.9 | 40.9 | 40.9 | -1.4 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 35.0 |
| F5 accept_exhausted | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | -1.4 | 48.8 | 45.6 | 39.4 | 52.5 | 69.8 | 36.5 |
| F6 taint_keeps_bid | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | 26.0 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 36.7 |
| F1+F2 (kept so far) | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | 46.9 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 36.7 |
| F1+F2+F6 | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | 46.9 | 48.8 | 45.6 | 39.4 | 52.5 | 61.0 | 36.7 |
| F1+F2+F5 | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | 46.9 | 48.8 | 45.6 | 39.4 | 52.5 | 69.8 | 36.5 |
| F1+F2+F5+F6 | 73.3 | 36.7 | 38.9 | 40.8 | 49.9 | 46.9 | 48.8 | 45.6 | 39.4 | 52.5 | 69.8 | 36.5 |
