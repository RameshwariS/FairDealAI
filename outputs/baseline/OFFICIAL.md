# Official starter-kit results

`ps2-selling-to-machines/evaluate.py`, 210 negotiations per seed against the kit's buyer bots. Seeds 0-2 were used to tune FairDeal AI; seeds 3-6 were not. The leaderboard uses hidden LLM buyers instead.

## Default run (seed 0)

| | FairDeal AI | Kit example seller |
|---|---|---|
| score | **53** | 48.5 |
| deal rate possible | **0.988** | 0.981 |
| margin kept | **0.695** | 0.673 |
| value | **0.53** | 0.51 |
| policy violations | **0** | 0 |
| truth violations | **0** | 0 |
| deadlocks | **0** | 21 |

## Every seed (score)

| seed | FairDeal AI | example seller | used for tuning |
|---|---|---|---|
| 0 | 53 | 48.5 | yes |
| 1 | 52.2 | 48.3 | yes |
| 2 | 47.4 | 42.9 | yes |
| 3 | 48.6 | 44.4 | no |
| 4 | 48.3 | 43.3 | no |
| 5 | 51.7 | 45.8 | no |
| 6 | 48.3 | 44.7 | no |

Held-out seeds 3-6: FairDeal AI **49.2** vs 44.5. Across all 7 seeds (1,470 negotiations): 0 violations, 4 deadlocks.
