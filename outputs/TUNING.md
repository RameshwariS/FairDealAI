# Tuning results

Objective: `deal_rate * margin_kept - 2 * deadlock_rate` · buyers: cooperative, hard_bargainer, manipulator, persona · 300 negotiations × seeds [1, 2]

| Rank | Objective | boulware | end_x | open_single | reciprocity | firm_from_round | deal rate | margin kept |
|---|---|---|---|---|---|---|---|---|
| 1 | 0.4314 | 1.0 | 0.0 | 1.0 | 0.4 | 3 | 0.569 | 0.759 |
| 2 | 0.4311 | 1.0 | 0.0 | 1.0 | 0.2 | 3 | 0.569 | 0.758 |
| 3 | 0.4311 | 1.0 | 0.0 | 1.0 | 0.2 | 4 | 0.569 | 0.758 |
| 4 | 0.4311 | 1.0 | 0.0 | 1.0 | 0.4 | 4 | 0.569 | 0.758 |
| 5 | 0.4306 | 1.0 | 0.05 | 0.92 | 0.4 | 3 | 0.569 | 0.758 |
| 6 | 0.4306 | 1.0 | 0.05 | 0.92 | 0.4 | 4 | 0.569 | 0.758 |
| 7 | 0.4299 | 1.0 | 0.0 | 1.0 | 0.2 | 6 | 0.567 | 0.759 |
| 8 | 0.4299 | 1.0 | 0.0 | 1.0 | 0.4 | 6 | 0.567 | 0.759 |
| 9 | 0.4298 | 1.0 | 0.05 | 1.0 | 0.2 | 3 | 0.563 | 0.764 |
| 10 | 0.4298 | 1.0 | 0.05 | 1.0 | 0.2 | 4 | 0.563 | 0.764 |

Current defaults: boulware=1.6, end_x=0.05, open_single=1.0, reciprocity=0.3, firm_from_round=4