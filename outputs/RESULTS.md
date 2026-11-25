# Local benchmark results

200 negotiations, seed 42 (held out from tuning), max 10 rounds.
Buyers: cooperative, hard bargainer, manipulator (1:1:1) + randomised agentic-style personas (x3 weight).

| metric | FairDeal AI | Naive baseline |
|---|---|---|
| deal_rate | 0.485 | 1.0 |
| margin_kept | 0.775 | 0.287 |
| deal_rate_x_margin_kept | 0.376 | 0.287 |
| profit_captured_of_max | 0.379 | 0.341 |
| policy_violations | 0 | 314 |
| below_cost_deals | 0 | 36 |
| deadlock_rate | 0.0 | 0.0 |
| truthfulness_errors | 0 | 0 |
| avg_rounds_to_deal | 5.96 | 2.67 |

## FairDeal AI by buyer type (100 negotiations each)

| buyer | deal rate | margin kept | violations | deadlock | truth errors |
|---|---|---|---|---|---|
| cooperative | 0.62 | 0.8 | 0 | 0.0 | 0 |
| hard_bargainer | 0.62 | 0.716 | 0 | 0.0 | 0 |
| manipulator | 0.62 | 0.687 | 0 | 0.0 | 0 |
| persona | 0.35 | 0.861 | 0 | 0.0 | 0 |

margin_kept = (price - cost) / (list - cost), averaged over deals. Some scenarios have no possible deal (buyer budget below the policy floor); walking away is correct there. Deal rate when a deal was possible: 0.746.
