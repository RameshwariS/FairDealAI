# Buyer suite: rule_baseline

Rule-based personas (no model).

Seeds [0, 1, 2] × 12 personas × 30 negotiations per persona per seed = 1080 negotiations per seller. Scored with the kit's `evaluate.score_one` / `summarise`; mean ± std across seeds. Held out (never used for tuning): late_sniper, emotional, bundle_hunter, unpredictable.

| group / persona | seller | score | deal rate % | margin kept % | policy | truth | deadlocks | rounds |
|---|---|---|---|---|---|---|---|---|
| overall | fairdeal | 43.5 ± 2.0 | 64.7 ± 3.1 | 68.3 ± 0.7 | 0 ± 0 | 0 ± 0 | 9.0 ± 1.0 | 7.5 ± 0.1 |
| overall | example | 42.4 ± 2.3 | 68.9 ± 3.1 | 64.7 ± 0.3 | 0 ± 0 | 0 ± 0 | 25.0 ± 5.3 | 6.8 ± 0.1 |
| tuning personas | fairdeal | 49.2 ± 1.9 | 71.0 ± 3.2 | 69.5 ± 0.6 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 7.3 ± 0.2 |
| tuning personas | example | 46.8 ± 1.7 | 73.8 ± 2.2 | 66.0 ± 0.3 | 0 ± 0 | 0 ± 0 | 17.7 ± 4.0 | 6.5 ± 0.2 |
| held-out personas | fairdeal | 32.1 ± 2.5 | 52.2 ± 3.4 | 65.1 ± 1.1 | 0 ± 0 | 0 ± 0 | 8.3 ± 0.6 | 8.0 ± 0.3 |
| held-out personas | example | 33.5 ± 3.7 | 59.2 ± 5.2 | 61.3 ± 0.9 | 0 ± 0 | 0 ± 0 | 7.3 ± 2.9 | 7.3 ± 0.2 |
| cooperative | fairdeal | 73.3 ± 3.6 | 85.6 ± 5.1 | 85.8 ± 1.2 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 3.7 ± 0.2 |
| cooperative | example | 67.4 ± 4.4 | 85.6 ± 5.1 | 78.8 ± 0.8 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.6 ± 0.3 |
| hard_bargainer | fairdeal | 36.7 ± 7.0 | 62.2 ± 10.2 | 58.8 ± 2.6 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 8.7 ± 0.5 |
| hard_bargainer | example | 38.1 ± 6.1 | 66.7 ± 6.7 | 60.9 ± 1.7 | 0 ± 0 | 0 ± 0 | 3.0 ± 1.7 | 8.4 ± 0.6 |
| persistent_lowballer | fairdeal | 38.9 ± 0.4 | 61.1 ± 1.9 | 63.7 ± 2.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 8.7 ± 0.3 |
| persistent_lowballer | example | 32.8 ± 2.4 | 61.1 ± 1.9 | 62.0 ± 2.3 | 0 ± 0 | 0 ± 0 | 6.0 ± 2.0 | 8.5 ± 0.4 |
| late_sniper (held out) | fairdeal | 40.8 ± 3.2 | 71.1 ± 5.1 | 57.3 ± 1.5 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 9.0 ± 0.3 |
| late_sniper (held out) | example | 42.1 ± 3.4 | 71.1 ± 5.1 | 59.2 ± 1.4 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 8.9 ± 0.3 |
| repeated_offer | fairdeal | 49.9 ± 2.5 | 70.0 ± 5.8 | 71.4 ± 2.5 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 7.5 ± 0.4 |
| repeated_offer | example | 49.8 ± 3.7 | 70.0 ± 5.8 | 72.4 ± 2.1 | 0 ± 0 | 0 ± 0 | 1.0 ± 1.0 | 6.1 ± 0.5 |
| bundle_hunter (held out) | fairdeal | -1.4 ± 3.0 | 8.9 ± 3.8 | 62.4 ± 5.9 | 0 ± 0 | 0 ± 0 | 7.7 ± 0.6 | 9.3 ± 0.4 |
| bundle_hunter (held out) | example | 5.9 ± 4.6 | 30.0 ± 6.7 | 54.8 ± 2.2 | 0 ± 0 | 0 ± 0 | 6.7 ± 2.3 | 8.1 ± 0.4 |
| fake_budget | fairdeal | 48.8 ± 6.0 | 74.4 ± 8.4 | 65.6 ± 0.7 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 8.2 ± 0.3 |
| fake_budget | example | 45.4 ± 6.6 | 74.4 ± 8.4 | 61.6 ± 1.2 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 7.8 ± 0.5 |
| fake_competitor | fairdeal | 45.6 ± 1.9 | 73.3 ± 3.3 | 62.2 ± 0.5 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 8.4 ± 0.5 |
| fake_competitor | example | 41.7 ± 1.8 | 73.3 ± 3.3 | 59.5 ± 0.9 | 0 ± 0 | 0 ± 0 | 2.3 ± 1.2 | 7.9 ± 0.6 |
| prompt_injector | fairdeal | 39.4 ± 1.2 | 67.8 ± 1.9 | 59.0 ± 3.5 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 9.1 ± 0.1 |
| prompt_injector | example | 38.0 ± 3.0 | 70.0 ± 0.0 | 59.9 ± 4.2 | 0 ± 0 | 0 ± 0 | 4.7 ± 1.2 | 9.0 ± 0.2 |
| emotional (held out) | fairdeal | 52.5 ± 4.7 | 76.7 ± 6.7 | 68.4 ± 1.1 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.8 ± 0.5 |
| emotional (held out) | example | 48.6 ± 3.0 | 77.8 ± 5.1 | 62.4 ± 0.6 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.1 ± 0.4 |
| fast_conceder | fairdeal | 61.0 ± 4.9 | 73.3 ± 6.7 | 83.3 ± 0.9 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 4.1 ± 0.1 |
| fast_conceder | example | 61.5 ± 2.6 | 88.9 ± 3.8 | 69.2 ± 0.6 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 2.8 ± 0.0 |
| unpredictable (held out) | fairdeal | 36.7 ± 5.8 | 52.2 ± 7.7 | 71.4 ± 0.4 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 7.1 ± 0.3 |
| unpredictable (held out) | example | 37.5 ± 7.4 | 57.8 ± 10.2 | 65.8 ± 0.7 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 6.2 ± 0.2 |
