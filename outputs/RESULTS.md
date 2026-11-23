# Local benchmark results

200 negotiations, seed 42 (held out from tuning), max 10 rounds.
Buyers: cooperative, hard bargainer, manipulator (1:1:1) + randomised agentic-style personas (x3 weight).

| metric | FairDeal AI | Naive baseline |
|---|---|---|
| deal_rate | 0.5 | 1.0 |
| margin_kept | 0.745 | 0.031 |
| deal_rate_x_margin_kept | 0.372 | 0.031 |
| profit_captured_of_max | 0.325 | 0.074 |
| policy_violations | 0 | 298 |
| below_cost_deals | 0 | 69 |
| deadlock_rate | 0.0 | 0.0 |
| truthfulness_errors | 0 | 0 |
| avg_rounds_to_deal | 5.6 | 2.67 |

## FairDeal AI by buyer type (100 negotiations each)

| buyer | deal rate | margin kept | violations | deadlock | truth errors |
|---|---|---|---|---|---|
| cooperative | 0.54 | 0.769 | 0 | 0.0 | 0 |
| hard_bargainer | 0.54 | 0.668 | 0 | 0.0 | 0 |
| manipulator | 0.54 | 0.636 | 0 | 0.0 | 0 |
| persona | 0.38 | 0.811 | 0 | 0.0 | 0 |

margin_kept = (price - cost) / (list - cost), averaged over deals. Some scenarios have no possible deal (buyer budget below the policy floor); walking away is correct there. Deal rate when a deal was possible: 0.781.
