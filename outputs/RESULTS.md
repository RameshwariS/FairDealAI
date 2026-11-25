# Local benchmark results

200 negotiations, seed 42 (held out from tuning), max 10 rounds.
Buyers: cooperative, hard bargainer, manipulator (1:1:1) + randomised agentic-style personas (x3 weight).

| metric | FairDeal AI | Naive baseline |
|---|---|---|
| deal_rate | 0.5 | 1.0 |
| margin_kept | 0.765 | 0.287 |
| deal_rate_x_margin_kept | 0.383 | 0.287 |
| profit_captured_of_max | 0.382 | 0.341 |
| policy_violations | 0 | 314 |
| below_cost_deals | 0 | 36 |
| deadlock_rate | 0.025 | 0.0 |
| truthfulness_errors | 0 | 0 |
| avg_rounds_to_deal | 5.68 | 2.67 |

## FairDeal AI by buyer type (100 negotiations each)

| buyer | deal rate | margin kept | violations | deadlock | truth errors |
|---|---|---|---|---|---|
| cooperative | 0.62 | 0.79 | 0 | 0.02 | 0 |
| hard_bargainer | 0.62 | 0.704 | 0 | 0.11 | 0 |
| manipulator | 0.62 | 0.683 | 0 | 0.05 | 0 |
| persona | 0.39 | 0.835 | 0 | 0.01 | 0 |

margin_kept = (price - cost) / (list - cost), averaged over deals. Some scenarios have no possible deal (buyer budget below the policy floor); walking away is correct there. Deal rate when a deal was possible: 0.769.
