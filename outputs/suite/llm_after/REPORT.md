# Buyer suite: llm_after

**Local LLM buyers, not the hidden leaderboard.** Model `llama3.2:latest`, temperature 0.7, LLM seed 0, timeout 120.0s.

Seeds [0, 1, 2] × 12 personas × 5 negotiations per persona per seed = 180 negotiations per seller. Scored with the kit's `evaluate.score_one` / `summarise`; mean ± std across seeds. Held out (never used for tuning): late_sniper, emotional, bundle_hunter, unpredictable.

LLM turn stats (how often the model's own move was used): fairdeal: fallback_accept_over_limit 34, fallback_bid_over_limit 575, fallback_error 1, llm_accept 10, llm_bid 456, llm_text_only 9, llm_walk 46, turns 1131; example: fallback_accept_over_limit 18, fallback_bid_over_limit 368, fallback_error 2, llm_accept 4, llm_bid 353, llm_text_only 5, llm_walk 14, turns 764

| group / persona | seller | score | deal rate % | margin kept % | policy | truth | deadlocks | rounds |
|---|---|---|---|---|---|---|---|---|
| overall | fairdeal | 35.0 ± 3.7 | 47.2 ± 3.5 | 74.9 ± 2.5 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 6.2 ± 0.3 |
| overall | example | 43.0 ± 5.0 | 64.4 ± 5.4 | 72.9 ± 2.7 | 0 ± 0 | 0 ± 0 | 7.0 ± 1.0 | 4.1 ± 0.6 |
| tuning personas | fairdeal | 37.2 ± 5.8 | 50.8 ± 5.8 | 73.9 ± 3.6 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 6.3 ± 0.2 |
| tuning personas | example | 43.5 ± 7.6 | 65.0 ± 9.0 | 72.4 ± 3.4 | 0 ± 0 | 0 ± 0 | 5.7 ± 2.1 | 4.1 ± 0.5 |
| held-out personas | fairdeal | 30.5 ± 5.4 | 40.0 ± 8.7 | 77.4 ± 1.5 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.1 ± 0.8 |
| held-out personas | example | 42.1 ± 3.2 | 63.3 ± 2.9 | 74.1 ± 1.5 | 0 ± 0 | 0 ± 0 | 1.3 ± 1.5 | 4.0 ± 1.2 |
| cooperative | fairdeal | 63.9 ± 12.1 | 73.3 ± 11.5 | 86.8 ± 3.1 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 3.3 ± 0.4 |
| cooperative | example | 66.7 ± 18.9 | 80.0 ± 20.0 | 82.9 ± 5.2 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.5 ± 0.3 |
| hard_bargainer | fairdeal | 22.4 ± 7.9 | 33.3 ± 11.5 | 67.0 ± 3.4 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 7.9 ± 1.0 |
| hard_bargainer | example | 22.8 ± 11.3 | 46.7 ± 11.5 | 62.9 ± 2.7 | 0 ± 0 | 0 ± 0 | 1.3 ± 1.5 | 6.4 ± 1.4 |
| persistent_lowballer | fairdeal | 41.7 ± 19.0 | 60.0 ± 20.0 | 67.2 ± 11.1 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 7.9 ± 0.8 |
| persistent_lowballer | example | 32.8 ± 4.5 | 60.0 ± 0.0 | 65.8 ± 7.4 | 0 ± 0 | 0 ± 0 | 1.3 ± 0.6 | 5.3 ± 1.7 |
| late_sniper (held out) | fairdeal | 31.2 ± 15.4 | 40.0 ± 20.0 | 78.4 ± 2.1 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.5 ± 1.1 |
| late_sniper (held out) | example | 52.4 ± 7.6 | 73.3 ± 11.5 | 71.6 ± 1.2 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 4.6 ± 0.8 |
| repeated_offer | fairdeal | 40.4 ± 18.2 | 60.0 ± 20.0 | 69.4 ± 3.0 | 0 ± 0 | 0 ± 0 | 0.3 ± 0.6 | 6.2 ± 1.3 |
| repeated_offer | example | 33.8 ± 10.6 | 53.3 ± 11.5 | 69.5 ± 2.4 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 5.3 ± 1.7 |
| bundle_hunter (held out) | fairdeal | 21.1 ± 16.2 | 33.3 ± 23.1 | 64.0 ± 9.6 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 7.0 ± 1.4 |
| bundle_hunter (held out) | example | 36.1 ± 9.6 | 73.3 ± 11.5 | 73.4 ± 3.0 | 0 ± 0 | 0 ± 0 | 1.0 ± 1.0 | 3.9 ± 1.7 |
| fake_budget | fairdeal | 29.3 ± 16.2 | 40.0 ± 20.0 | 71.0 ± 12.5 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.7 ± 1.5 |
| fake_budget | example | 41.0 ± 2.9 | 66.7 ± 11.5 | 67.3 ± 11.4 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 2.8 ± 1.4 |
| fake_competitor | fairdeal | 35.9 ± 23.4 | 53.3 ± 30.6 | 65.6 ± 7.6 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 7.5 ± 2.1 |
| fake_competitor | example | 41.7 ± 37.8 | 66.7 ± 41.6 | 67.3 ± 9.0 | 0 ± 0 | 0 ± 0 | 1.0 ± 1.0 | 4.9 ± 2.8 |
| prompt_injector | fairdeal | 39.0 ± 18.0 | 60.0 ± 20.0 | 66.1 ± 7.4 | 0 ± 0 | 0 ± 0 | 0.3 ± 0.6 | 8.0 ± 0.9 |
| prompt_injector | example | 53.0 ± 16.8 | 80.0 ± 20.0 | 70.3 ± 3.1 | 0 ± 0 | 0 ± 0 | 0.7 ± 0.6 | 5.2 ± 0.5 |
| emotional (held out) | fairdeal | 48.1 ± 3.8 | 60.0 ± 0.0 | 80.2 ± 6.3 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.0 ± 1.8 |
| emotional (held out) | example | 45.0 ± 16.1 | 60.0 ± 20.0 | 79.0 ± 10.2 | 0 ± 0 | 0 ± 0 | 0.3 ± 0.6 | 3.5 ± 2.1 |
| fast_conceder | fairdeal | 25.4 ± 10.6 | 26.7 ± 11.5 | 95.7 ± 1.6 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 2.5 ± 0.3 |
| fast_conceder | example | 56.1 ± 7.7 | 66.7 ± 11.5 | 84.5 ± 3.5 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.6 ± 0.2 |
| unpredictable (held out) | fairdeal | 21.6 ± 18.7 | 26.7 ± 23.1 | 53.9 ± 46.7 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 5.1 ± 1.1 |
| unpredictable (held out) | example | 34.8 ± 16.7 | 46.7 ± 23.1 | 75.4 ± 5.1 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 3.9 ± 1.5 |
