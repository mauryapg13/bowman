# V1 log — every change, its score delta, and what was reverted

Scores are on the 25 samples: "cat" = all three categoricals exact; "Δ" = mean |calibration delta|.
Baseline (MVP, docs/mvp_results.md): cat 64%, Δ 250,286.

| # | change | cat | Δ | kept? | evidence |
|---|---|---|---|---|---|
| 1 | V1-1 lifecycle links (7 patterns, 6 duplicate charges excluded) | 64% | 250,286 | yes | correct by construction; no sample user has a linked duplicate |
| 2 | V1-2 vision (16 images, reviewed-table backend) | 64% | 250,151 | yes | 12/16 settled → no curve change, as predicted; 4 pending/scheduled move request_16/19/20 slightly |
| 3 | V1-4/5 spending changes (two gates, copy-on-write variants) | 64% | 250,151 | yes | machinery correct; request_06/11/21 still masked by ledger deltas of −86/−389k/+185 |
| 4 | V1-3 ops-v1 (GLM 5.3 Flash via OpenRouter) | 68% | 250,151 | yes | request_02 raise applied → installments now chosen; users 14/15 still `none` (no stream to amend) |
| 5 | ops-v2: `start_stream` when the user has no income stream (allow-list gets `new:salary`) | 68% | 248,708 | yes | request_14 Δ −4,701 → +30; request_15 Δ −3,393 → −77 |
| 6 | confirmed scheduled salary with no stream → monthly stream (request_01) | 72% | 249,771 | yes | request_01 min 27,611 → 48,886 (key needs ≥ 43,256); request_09 also fixed |
| 7 | absorption picks the closest-amount stream when several qualify (user_13 double count) | — | — | yes | user_13 salary was placed twice on 15 Mar |
| 8 | stale-stream termination: expected next occurrence > 7 days before last settled event ⇒ ended | **76%** | 248,708 | yes | request_05 now `not_affordable` (Final employer payroll); request_13 second income ends |
| 9 | amount estimator variants for streams (mean / last-3 mean / last-3 median / max / latest) | 68–72% | 234k–274k | **reverted** | mean: +2 rows within 1% but same cat; last-3 mean: cat −4pts; max: cat 48%. Median kept |

| 10 | stream occurrences/anchors use `settlement_date` (cash date), numeric event-id sort | 72% | 248,414 | yes | contract (AGENTS §6.3) and key agree: request_07's salary settles on the 23rd and the key's earliest date is 10-23. Categoricals −4 pts from request_07 alone (−1,669 pessimistic near day 70–78) |
| 11 | grid search: variable-spend amount {median, mean, last, mean-last-4, median-last-6, max-last-4} × cadence {median gap, mean gap, last gap, 7, 14} — 30 combos | ≤2/20 exact | 374–1,285 on the six small rows | **no change** | no combination zeroes more than 2 rows; (mean, median gap) ≈ (median, median gap); the key's estimator is outside this family. Stopped chasing `amount_safe_to_pay` exactness here |
| 12 | monthly-total-as-monthly-stream, description-level grouping (3 bands), min-occurrences 2 | 0–1/20 | 287k–850k | **reverted** | all far worse |

## Open misses after #12 (see score.py output)

- request_05: ended payroll cut too early — our min 7,777 vs key 13,837 (key still counts one more occurrence or cuts later expenses).
- request_06 (−86), request_21 (+185), request_13 (+705), request_23 (−745): variable-spend estimation differences; no estimator variant fixed them without hurting others (#9).
- request_10: "payout still pending" message; key drops ~489k of gig income; our ops return `none`. Deliberately not chased — which of four gig streams the key dropped is not identifiable from the text.
- request_11: −389k pessimistic; dining stream every 21 days at median 1.37M IDR — the key's estimate is lower.
- request_07 / 12: earliest date off by days (12: we find no full-payment day; key has day 0 — capacity 58,772 vs 65,164).

## Ablation (code/evaluation/ablation.py)

| configuration | all 3 exact | mean \|Δ\| |
|---|---|---|
| deterministic core only | 68% | 249,223 |
| + links | 68% | 249,223 |
| + vision | 68% | 249,089 |
| + message operations | 72% | 248,708 |
| + spending changes (full) | **76%** | 248,708 |
| negative control: re-apply last 30 days of settled events to the balance | 56% | 1,975,610 |

The negative control is spec §3 guard 3: settled events are already inside the balance, and pretending otherwise wrecks calibration by 8×.

## Full-run numbers (250 requests)

status: affordable_now 55, affordable_with_plan 66, affordable_later 50, not_affordable 79;
method: full 67, installments 44, partial 10, wait 50, not_recommended 79;
`amount_safe_to_pay == 0` on 11 rows (was 30 at MVP). Two CLI runs: identical sha256.
Model usage: 318 live GLM calls total while building the cache (~$0.11); the final run made 0 live calls.
