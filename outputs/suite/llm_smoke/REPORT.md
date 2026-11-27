# Buyer suite: llm_smoke

**Local LLM buyers, not the hidden leaderboard.** Model `llama3.2:latest`, temperature 0.7, LLM seed 0, timeout 120.0s.

Seeds [0] × 12 personas × 1 negotiations per persona per seed = 12 negotiations per seller. Scored with the kit's `evaluate.score_one` / `summarise`; mean ± std across seeds. Held out (never used for tuning): late_sniper, emotional, bundle_hunter, unpredictable.

LLM turn stats (how often the model's own move was used): fairdeal: clamped_to_limit 18, fallback_accept_over_limit 3, fallback_unparsed 1, llm_bid 60, llm_walk 3, turns 67; example: clamped_to_limit 6, fallback_unparsed 1, llm_bid 46, llm_walk 1, turns 48

| group / persona | seller | score | deal rate % | margin kept % | policy | truth | deadlocks | rounds |
|---|---|---|---|---|---|---|---|---|
| overall | fairdeal | 39.5 ± 0.0 | 50.0 ± 0.0 | 79.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 5.6 ± 0.0 |
| overall | example | 46.0 ± 0.0 | 66.7 ± 0.0 | 78.4 ± 0.0 | 0 ± 0 | 0 ± 0 | 3.0 ± 0.0 | 3.8 ± 0.0 |
| tuning personas | fairdeal | 39.4 ± 0.0 | 50.0 ± 0.0 | 78.7 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 5.2 ± 0.0 |
| tuning personas | example | 51.5 ± 0.0 | 75.0 ± 0.0 | 77.1 ± 0.0 | 0 ± 0 | 0 ± 0 | 2.0 ± 0.0 | 3.5 ± 0.0 |
| held-out personas | fairdeal | 39.8 ± 0.0 | 50.0 ± 0.0 | 79.5 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.2 ± 0.0 |
| held-out personas | example | 34.9 ± 0.0 | 50.0 ± 0.0 | 82.3 ± 0.0 | 0 ± 0 | 0 ± 0 | 1.0 ± 0.0 | 4.2 ± 0.0 |
| cooperative | fairdeal | 91.2 ± 0.0 | 100.0 ± 0.0 | 91.2 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 2.0 ± 0.0 |
| cooperative | example | 97.6 ± 0.0 | 100.0 ± 0.0 | 97.6 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 2.0 ± 0.0 |
| hard_bargainer | fairdeal | 72.6 ± 0.0 | 100.0 ± 0.0 | 72.6 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 4.0 ± 0.0 |
| hard_bargainer | example | 67.9 ± 0.0 | 100.0 ± 0.0 | 67.9 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.0 ± 0.0 |
| persistent_lowballer | fairdeal | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 10.0 ± 0.0 |
| persistent_lowballer | example | -25.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 1.0 ± 0.0 | 10.0 ± 0.0 |
| late_sniper (held out) | fairdeal | 73.2 ± 0.0 | 100.0 ± 0.0 | 73.2 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.0 ± 0.0 |
| late_sniper (held out) | example | 76.6 ± 0.0 | 100.0 ± 0.0 | 76.6 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.0 ± 0.0 |
| repeated_offer | fairdeal | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 10.0 ± 0.0 |
| repeated_offer | example | -25.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 1.0 ± 0.0 | 10.0 ± 0.0 |
| bundle_hunter (held out) | fairdeal | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 10.0 ± 0.0 |
| bundle_hunter (held out) | example | -25.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 1.0 ± 0.0 | 10.0 ± 0.0 |
| fake_budget | fairdeal | 63.1 ± 0.0 | 100.0 ± 0.0 | 63.1 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 4.0 ± 0.0 |
| fake_budget | example | 63.1 ± 0.0 | 100.0 ± 0.0 | 63.1 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.0 ± 0.0 |
| fake_competitor | fairdeal | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 6.0 ± 0.0 |
| fake_competitor | example | 66.6 ± 0.0 | 100.0 ± 0.0 | 66.6 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.0 ± 0.0 |
| prompt_injector | fairdeal | 87.9 ± 0.0 | 100.0 ± 0.0 | 87.9 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 3.0 ± 0.0 |
| prompt_injector | example | 87.9 ± 0.0 | 100.0 ± 0.0 | 87.9 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 2.0 ± 0.0 |
| emotional (held out) | fairdeal | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 5.0 ± 0.0 |
| emotional (held out) | example | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 5.0 ± 0.0 |
| fast_conceder | fairdeal | 0.0 ± 0.0 | 0.0 ± 0.0 | 0.0 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 3.0 ± 0.0 |
| fast_conceder | example | 79.3 ± 0.0 | 100.0 ± 0.0 | 79.3 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.0 ± 0.0 |
| unpredictable (held out) | fairdeal | 85.8 ± 0.0 | 100.0 ± 0.0 | 85.8 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 4.0 ± 0.0 |
| unpredictable (held out) | example | 87.9 ± 0.0 | 100.0 ± 0.0 | 87.9 ± 0.0 | 0 ± 0 | 0 ± 0 | 0.0 ± 0.0 | 1.0 ± 0.0 |
