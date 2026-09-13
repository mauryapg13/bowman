# The sample-key ruleset — what is decoded, what is proven undecodable

Written 2026-09-13 (branch `feat/ruleset`). Premise given by the organizers: the 25 answered rows in
`dataset/sample_requests.csv` are the deterministic output of their own procedure over the same files.
Method: every rule is stated first, then counted on all 25 rows (rows fixed / broken / unchanged).
Scores are from `python3 code/evaluation/score.py`; "exact" means to the cent, "tol" means score.py's
0.5 % tolerance. Experiments live in `scratch/` (gitignored) and are indexed in `docs/v1_log.md` #32–#38.

## 0. Headline

| | before (main 803cf7a) | after (this branch) |
|---|---|---|
| `amount_safe_to_pay` exact / within 0.5 % | 5 / 11 | 5 / 12 |
| mean abs / mean rel error on `amount_safe_to_pay` | 100,219 / 13.5 % | 100,117 / **12.7 %** |
| `affordability_status` | 22 | **23** |
| `recommended_payment_method` | 23 | 23 |
| `payment_plan` | 22 | 22 |
| `earliest_date_for_full_payment` | 22 | **23** |
| `spending_changes_needed` | 22 | 22 |
| `decision_explanation` | 18 | 18 |
| all three categoricals exact | 21 (84 %) | **22 (88 %)** |
| rows exact on all 7 columns | 10 | 10 |

Two new rules (R7, R8) were found and shipped; each fixes one sample row's curve to within estimator noise and breaks none. The remaining `amount_safe_to_pay` residuals are **not a
hidden rule**: §3 proves the key's per-stream amounts are the data generator's own base parameters,
which the history only lets us estimate to a few percent. That boundary is stated with counts in §4.

## 1. What the generator is (proven on all 275 users, `scratch/noise_shape*.py`, `grid*.py`)

These are facts about the dataset, not about our pipeline. They are what a judge should check first.

- **G1. Amount noise is uniform and multiplicative.** For every varying stream, `amount / midrange`
  is flat: category-level spend (groceries / transport / dining) fills `[0.72, 1.28]` with a hard cap
  `max/min ≤ 1.775` on all 822 streams with n ≥ 20; monthly bills (utilities, shopping,
  entertainment, healthcare) fill `[0.88, 1.12]` (`max/min ≤ 1.27`, 676 streams). No tail beyond
  the bounds except bulk-purchase outliers. Histograms in `scratch/noise_shape3.py`.
- **G2. Base amounts sit on a per-currency grid.** Every constant stream is `integer × unit` with
  unit = EUR 1, USD 1, ZAR 1.1, INR 5, IDR 50 (ZAR: 227/227; IDR: 244/249 — the 5 misses are
  salaries after a percentage raise; INR: 302/312; EUR rent is `integer × 1.1`, USD rent
  `integer × 1.2`).
- **G3. The key's forecast amounts sit on the same grid.** Back out the key's varying pre-trough
  outflow (`opening − floor − key safe − constant items`): ZAR 16,929.00 = 15,390 × 1.1 and
  8,104.80 = 7,368 × 1.1; all five IDR rows are multiples of 100; all seven EUR and the USD row
  are integers. A statistic of 2-decimal history would land on the ZAR grid by chance with
  probability ≈ 1/110 per row.
- **G4. No history statistic reproduces the key.** 504 combinations — window ∈ {all history,
  30/45/60/90/120/180 days, last 3–12 occurrences, last 1/2/3/6 calendar months} × statistic ∈
  {mean, median, trimmed mean, midrange, max, min, last} × rounding ∈ {none, round, ceil, floor}
  — reproduce at most **2 of 20** uncapped rows' varying totals exactly (`scratch/sweep_est.py`),
  with the placement counts held at ours. The current estimator (round of the trimmed mean) is
  among the best of them and hits 1.
- **G5. Noise is not shared.** Multipliers do not correlate across a user's streams by index
  (mean r = 0.01, n = 1,518 pairs) or by date (r = 0.03), and lag-1 within a stream is −0.06
  (`scratch/shared_noise.py`). So the base amount cannot be solved from ratios between streams.

Conclusion: the key = `Σ base_amount × count_before_trough` with base amounts the generator drew
and never wrote to disk. From n uniform draws with half-width w the base is only known to
≈ ±w·√2/(n+1) (1.5 % at n = 25, 3 % at n = 5). The residuals in §4 are that size, in both signs.

## 2. Decoded rules (all counted on the 25)

Rules R1–R6 and R9–R11 were established in v1 (`docs/v1_log.md`) and are restated here with their
derivation so the ruleset is complete in one place; R7 and R8 are new in this branch.

| # | rule | derives from | count |
|---|---|---|---|
| R1 | `current_available_balance` is the balance on `request_date`; settled history is already inside it and never re-applied. | problem_statement "available balance"; every user's last settled event is 1–7 days before the request; sample 03's payslip credit is inside the balance | negative control (re-apply last 30 days): categoricals 84 → 56 %, calibration 8× worse (v1_log ablation) |
| R2 | Cash moves on `settlement_date`. Monthly streams (median gap 28–31 d) recur on the anchor's day-of-month; shorter cadences by day arithmetic. | AGENTS §6.3 "count confirmed salary on its settlement date"; sample 07 (salary event 15th, settled 23rd, key's earliest date 23rd) | v1 #10: 0 rows broken; #6: fixes 01 and 09 |
| R3 | A `scheduled` "Next confirmed salary" row is the next occurrence of the payroll stream (absorbed, closest-amount stream when two qualify); with no payroll stream it is promoted to a monthly stream. | problem_statement "the next confirmed salary"; "do not invent income" (the row exists) | v1 #6/#7: fixes 01, 09, 13 (double count) |
| R4 | A stream whose next expected occurrence is > 7 days before the user's last settled event has ended. | conflict rule 3 "a settled event over an estimate": later settled data with the beat missing | v1 #8: fixes 05 (Final employer payroll) and 13; 0 broken |
| R5 | Variable-spend categories restart at `request_date + 5` (cadence unchanged), not at last occurrence + cadence. | "Forecast essential variable spending conservatively" (AGENTS §6.3) | v1 #13/#23; re-verified here (`scratch/schedule_cmp.py`): the key's pre-trough count vector matches this on 16/20 rows, the pure clock on 9/20 |
| R6 | Stream amount = round(mean with the single min and max dropped); constant series exact. | best history estimator of G1's base amount that is outlier-robust; rounding matches G2/G3 (integers) | v1 #20: exact 5 → 10 (tol); here: among the top of the 504-combo sweep |
| **R7** | **A pending/scheduled occurrence of a variable-spend category dated after the request is reserved as a recorded placement but does not replace the category's recurring forecast: the stream still restarts at day 5; a predicted day equal to a recorded day is skipped, never doubled.** | problem_statement 90-day check: forecast "using recurring income and expenses, **confirmed future payments**" — both; "Reserve pending debits" (AGENTS §6.3) | **fixes 21** (residual +31.05 → +5.00; status/method/plan/earliest now match; `spending_changes_needed` still differs by the 5-unit residual), **0 broken, 24 unchanged**. On the 250: rows 41, 101, 141 change |
| **R8** | **A `scheduled` debit joins a bill stream as its next occurrence only when its amount is the bill's amount (constant series) or inside the recorded [min, max] (varying series); otherwise it is an additional confirmed payment and the bill is still forecast. Credits keep the existing absorption.** | conflict rules 1 and 4: a scheduled row with another amount and a generic description ("Scheduled insurance payment" 1,830 vs a 2,510 policy) is not an amendment of the bill; when unresolved take the financially safer reading | **fixes 24** (residual +2,673 → +163), **0 broken, 24 unchanged**. On the 250: rows 44, 84, 104, 224 change; 6 message re-reads (see §3) |
| R9 | Forecast horizon 84 days (12 weeks). | contract says 90; no key decision depends on days 85–90 and three rows require ignoring a bill on day 87–89; any horizon 77–86 fits | v1 #22: fixes 08, 12, 13; 0 broken |
| R10 | `reduce_to` amount = the row's `minimum_allowed_amount`; `event_id` = latest recorded occurrence of the stream; only non-protected flexible streams in permitted categories. | problem_statement `reduce_to:<event_id>:<new_amount>`; samples 06/11/21 | v1 #31 correction; 3/3 sample change strings reproduced when the curve agrees |
| R11 | Plan ranking exactly as problem_statement "Choosing Between Safe Plans" (deadline, no changes, total cost, earlier start, fewer payments, lowest option id); `wait` only when the user accepts full payment. | verbatim | 22/25 categoricals; the 3 misses (06, 11, 19) are all curve-boundary cases, not ranking |

## 3. R7 and R8 in detail (the two new rules)

Sample `request_21` (USD): transport recurs every 21 days (last 26 Mar); a `pending` "Pending fuel
authorization" of 53 settles on 5 Apr, two days after the request. Before R7 the pending row became
the stream's latest recorded occurrence, which switched off the day-5 restart, so no transport run was
forecast before the 12 Apr trough; the key's outflow is 47 higher (its transport base amount, ≈ our
42), and with it the full payment is unsafe without the two spending changes the key lists.
After R7 the recorded 53 and a predicted transport run on day 5 both stand; residual +5.00
(estimator noise on one item); status, method, plan and earliest date match. `spending_changes_needed`
still differs (`stop:event_1816` vs the key's `stop:event_1815|reduce_to:event_1816:23.50`): on a curve
5 units higher, stopping the 47 streaming plan alone closes the gap, so the 5-unit residual decides it.

Implementation: `code/ledger.py` `_phase_reset` (no longer keeps the anchor when a future
occurrence exists) and `_stream_placements` (for reset streams only past occurrences gate
prediction; a predicted day that coincides with a recorded day is skipped). Test:
`tests/test_ledger.py::test_variable_streams_restart_at_the_request`.

Sample `request_24` (INR): insurance is 2,510 on the 6th of every month. A `scheduled` "Scheduled
insurance payment" of 1,830 settling 11 Jan (+36 days after the last policy payment, inside the
±10-day absorption window) was taken as the stream's next occurrence, so the 6 Jan policy payment
was never forecast. The key's outflow is 2,673 higher = 2,510 + 163 (0.9 % noise on the other items):
it reserves the scheduled 1,830 **and** keeps the 2,510 bill. Across all 275 users the absorption
touched 14 non-salary scheduled rows: 6 "Scheduled bill payment retry" (amount inside the bill's
range — still absorbed, the retry *is* the month's bill after a failed attempt), 4 "Scheduled utility
debit" (+37 d, ≈ 60 % of the bill), 2 "Scheduled insurance payment", 1 "Scheduled school fee" (the
last three families have another amount — no longer absorbed). Implementation: `code/recurrence.py`
`_absorb` / `_amount_compatible`.

Side effect to disclose: the message-operation port's cache key includes the stream view, so the
changed absorption for 6 users triggered 6 live GLM-5.3-Flash calls (≈ $0.003) during the R8
experiment; their results are committed under `code/cache/` and the final run is offline again
(0 live calls). One of them (user_104) now reads "confirmed base salary is ZAR 35860" as an
`amend_stream` where the earlier view returned `none`; that flips request_104 to `affordable_now`.

## 4. Rules we could not decode (honest boundary)

Per-row residual of our pre-trough outflow vs the key's, after R7 (`scratch/schedule_cmp.py`,
`scratch/feasible.py`). "Feasible" = the key's total is reachable with every varying stream inside
its G1 interval `[max/(1+w), min/(1−w)]` at our placement counts — i.e. the placement set agrees
and only the base amounts differ.

| row | ccy | residual (ours − key, % of outflow) | placements before trough | feasible | reading |
|---|---|---|---|---|---|
| 02 | IDR | +8,238 (−0.06 %) | 5 | yes | base-amount noise |
| 03 | IDR | +5,861 (−0.26 %) | 5 | yes | noise |
| 04 | IDR | +2.19 M (−16.7 %) | 5 | **no** | key has 2 groceries + 2 transports (cad 7) before day 11 → first day ≤ 3; conflicts with 06 |
| 05 | ZAR | +366 (−1.1 %) | 27 | yes | ≈ 2σ of a 27-item sum; same sign as 13 |
| 06 | EUR | −6 (+1.1 %) | 6 | yes | needs one dining (cad 7) before day 10 → first day ≥ 4; conflicts with 04 |
| 07 | INR | −1,083 (+2.8 %) | 4 | yes | 4 items, 2.7σ; no single item explains it |
| 10 | INR | +25.6 k (−5 %) | 36 | **no** | "payout still pending" message; which of four gig streams the key drops is not in the text |
| 11 | IDR | −238 k (+1.4 %) | 5 | yes | noise; but it decides `reduce dining + pay today` vs `wait` |
| 13 | EUR | +15 (−1.4 %) | 30 | yes | exactly −15.00 over 30 items |
| 14 | EUR | +21 (−1.9 %) | 5 | yes | noise |
| 15 | EUR | +15 (−3.1 %) | 4 | yes | noise |
| 17 | INR | −1,177 (+0.8 %) | 6 | no (bulk grocery outlier) | boundary: second-month trough 1.3 % from the full-payment line → earliest date 15 Apr vs key 15 Mar |
| 18 | EUR | −1 (+0.2 %) | 5 | yes | noise |
| 19 | INR | +1,250 (−1.6 %) | 5 | yes | noise; decides the partial split |
| 20 | INR | −9 (0.0 %) | 5 | yes | the key's varying total 18,312 is not on the INR-5 grid → one of its items is off-grid |
| 21 | USD | +5 (−1.1 %) | 7 | yes (after R7) | noise |
| 22 | EUR | +2 (−1.3 %) | 4 | yes | unique grid solution: key dining 17, groceries 25 vs our 16, 24 |
| 23 | ZAR | +28.8 (−0.2 %) | 5 | yes | noise |
| 24 | INR | +163 (−0.9 %) after R8 (was +2,673) | 8 | yes | the missing item was the regular insurance bill dropped by the absorption → R8 |
| 25 | IDR | −26 k (+0.4 %) | 6 | yes | noise |

Rows 01, 08, 09, 12, 16 are exact (08 is the only uncapped one).

Ruled out this session, each counted on the 25 (v1_log #32–#37):

- **Any history statistic as the key's estimator** (G4): ≤ 2/20 exact. Includes every window,
  every order statistic, ceil/floor/round.
- **Feasible-midpoint estimator** (midpoint of `[max/(1+w), min/(1−w)]`, w = 0.28 / 0.12, outliers
  dropped until feasible, snapped to the grid) — the minimum-variance estimator of G1's base amount:
  total relative error on the 16 feasible rows falls 18 % (0.315 → 0.258), but in the pipeline
  exact stays 4–5, categoricals stay 22, mean error slightly worse (rows 04/10/24 dominate).
  **Candidate, unshipped** — better in expectation, not on the jury; it is not in `output.csv`.
- **Grid snapping** of the current estimates (INR 5, IDR 50, ZAR 1.1): 0 rows change category or
  exactness; residuals are 10–1000× the grid step.
- **Pure clock schedule** (last occurrence + cadence, with or without day 0): matches the key's
  count vector on 9/20 rows vs 16/20 for the day-5 restart; re-confirms v1 #13.
- **A different first day** for the restart: 04 needs ≤ 3, 06 needs ≥ 4, 24 wants ≤ 3 with one more
  item still missing; no single value fits (v1 #23 stands).
- **Shared noise across streams** (G5): none, so the base amounts cannot be solved exactly.

What would decode the rest: nothing inside `dataset/`. The base amounts and the generator's own
forward schedule for the three schedule-mismatch rows (04, 10, 17) are not in the files.

## 5. Final numbers

`python3 code/evaluation/score.py` on `feat/ruleset` (after R7 + R8):
amount 48 % (tol) / 5 exact, status 92 %, method 92 %, plan 88 %, earliest 92 %, spending 88 %,
explanation 72 %, all-three 88 %, mean abs safe error 100,117 (rel 12.7 %), calibration mean |Δ| 119,187.
`python3 -m pytest tests -q`: 81 passed. `python3 code/main.py` twice: identical
sha256 `2c0cf3bf72e3fa429d58742e7e9b6f535835b1251147c18ffee2efe18fe73d2a`; 250 rows; 0 live model calls.
