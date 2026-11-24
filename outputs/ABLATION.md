# Ablation study

3 seeds × 600 negotiations per variant, mixed buyers (cooperative, hard bargainer, manipulator, randomised personas). Score = deal rate × margin kept (higher is better). The policy guard stays on in every variant, so violations stay 0; this measures what each negotiation rule adds.

| Variant | Score | Change vs full | Profit captured | Deal rate | Margin kept | Deadlocks |
|---|---|---|---|---|---|---|
| Full agent | 0.416 ± 0.004 | – | 0.438 | 0.531 | 0.784 | 0.0% |
| No firm-offer rule (meet a held offer halfway, then take it) | 0.411 ± 0.005 | -0.005 | 0.433 | 0.522 | 0.786 | 0.0% |
| No reciprocity (ignore how much the buyer moved) | 0.414 ± 0.004 | -0.002 | 0.437 | 0.528 | 0.784 | 0.0% |
| No minimum concession per round | 0.416 ± 0.004 | +0.000 | 0.438 | 0.531 | 0.784 | 0.0% |
| No late accept (rounds 9-10) | 0.416 ± 0.004 | +0.000 | 0.438 | 0.531 | 0.784 | 0.0% |
| No final best offer on round 9 | 0.416 ± 0.004 | +0.000 | 0.438 | 0.531 | 0.784 | 0.0% |
| Stall rule on: final offer after 3 frozen rounds | 0.416 ± 0.004 | +0.000 | 0.438 | 0.531 | 0.784 | 0.0% |
| Stall rule on + walk away early (first version) | 0.416 ± 0.004 | +0.000 | 0.438 | 0.531 | 0.784 | 0.0% |
| No small-gap close | 0.416 ± 0.004 | -0.000 | 0.438 | 0.530 | 0.784 | 0.0% |
| Linear concession instead of Boulware | 0.423 ± 0.004 | +0.007 | 0.445 | 0.551 | 0.768 | 0.0% |
| No bundle opening discount | 0.415 ± 0.005 | -0.001 | 0.441 | 0.524 | 0.793 | 0.0% |

± is the spread across seeds. On this mix most rules change little: the time curve and the walk-away do most of the work, and the other rules rarely fire.

## Stress buyers: what each rule is for

150 negotiations per buyer. Every buyer here can afford a deal above the policy floor. **Holdout** climbs to its limit and repeats it; **last-minute** lowballs until round 9, then offers its real limit; **staller** repeats an offer below the floor and never leaves (fewer rounds = better).

| Variant | Holdout score | Last-minute score | Staller rounds |
|---|---|---|---|
| Full agent | 0.697 | 0.642 | 10.0 |
| No firm-offer rule (meet a held offer halfway, then take it) | 0.566 | 0.642 | 10.0 |
| No reciprocity (ignore how much the buyer moved) | 0.697 | 0.642 | 10.0 |
| No minimum concession per round | 0.697 | 0.642 | 10.0 |
| No late accept (rounds 9-10) | 0.697 | 0.642 | 10.0 |
| No final best offer on round 9 | 0.697 | 0.642 | 10.0 |
| Stall rule on: final offer after 3 frozen rounds | 0.697 | 0.587 | 10.0 |
| Stall rule on + walk away early (first version) | 0.697 | 0.000 | 5.0 |
| No small-gap close | 0.697 | 0.642 | 10.0 |
| Linear concession instead of Boulware | 0.697 | 0.626 | 10.0 |
| No bundle opening discount | 0.697 | 0.642 | 10.0 |

Score = deal rate × margin kept.

**Reading it:** the firm-offer rule is what closes holdouts (0.57 → 0.70). The stall rule, which we first shipped, cost every last-minute deal, so it is now off. Late accept and the round-9 final offer changed no outcome in any of our tests (reciprocity already closes these deals); they stay as zero-cost safety nets.

## Tried and dropped

| Idea | Result | Decision |
|---|---|---|
| Opponent model: project the buyer's next offer and never concede below it | Score 0.442 → 0.438 (seed 1) and 0.417 → 0.415 (seed 2), measured on an earlier build | Dropped: no gain, more complexity |
| Stall rule: after 3 frozen rounds below the floor, make the final offer and walk away | Lost every last-minute buyer (score 0.000), and rounds aren't scored | Dropped the walk-away; the early final offer also only gave margin away, so the rule is now off |
| Treating repeated offers as firm from round 1 | +0.002 score, but lets a buyer lock in a near-floor price by round 3 | Kept the round-4 gate for safety |