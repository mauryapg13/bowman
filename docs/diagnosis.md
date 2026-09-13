# Deep diagnosis — why our numbers and the key's numbers come out the way they do

Written 2026-09-13 after the phase-reset change. Method: for every sample, back out the key's
outflow before its trough (`opening − floor − key safe`), lay it beside our placements
(`score.py --trace`), and test hypotheses jointly across rows (never per row).

## What both sides agree on (18 of 25 rows exact on status / method / plan)

- The minimum of the 90-day curve is the trough just before the first payday (20/25 rows).
- Salary and fixed bills recur on the same day-of-month; cash moves on the settlement date.
- Scheduled "next salary" rows are the next payroll occurrence, not extra income.
- Messages change streams (raise, first salary, ended, one-off reduction); links remove
  duplicate charges; images fill the 16 blanks.
- Variable spend (groceries / transport / dining) is one clock per category with an exact
  per-user period (5/7/10/14/21 days) and the next occurrence lands a few days after the request.

## What the key does that we do not — the evidence

**1. The key's forecast amounts are whole units.** `opening − floor − key safe` is an exact
integer on 12 of 20 uncapped rows, including EUR/USD users whose bills carry cents
(157.00, 452.00, 624.00, 568.00, 487.00, 1,134.00, 140,430.00, 38,775.00, 13,996,350.00).
When we round varying streams to integers ourselves (constant streams left exact), our residuals
become integers too: 08 −1, 13 +3, 18 −2, 20 +27, 21 +46, 22 **0**. So the key builds its
curve from rounded estimates of each varying stream. Which statistic it rounds (mean vs
median, ceil vs round) is not identifiable: several choices give the same integer residuals.

**2. The remaining integer residuals are one placement in or out of the pre-payday window.**
They are the size of one purchase (21: +46; 20: +27) or one fixed bill, never a fraction. That
means the key's *schedule* still differs from ours by one item on those rows — a different
first-occurrence day for one category, or a bill the key places a day earlier/later relative to
payday. With one request per user there is no second observation to pin the day.

**3. Rows where the key knows something the data does not state.**
- request_14 / 15: the message confirms a first salary; the key's trough (1,134 / 487 below
  opening) includes expenses we place *after* its arrival. Our start_stream lands the salary on
  the confirmed date; the key evidently books the pre-salary expenses first. Same information,
  different ordering within the month.
- request_10: "next payout is still pending" — the key removes ≈469k of gig income; four gig
  streams exist and the message names none of them.
- request_05: "Final employer payroll" — we end the stream one occurrence earlier than the key.
- request_12: capacity 55,072 vs 65,164 (capped); the key's curve is 10k higher over the window;
  the user has no income stream and a terminated one — the key may keep one more occurrence.

## Row-by-row

| row | ours vs key | mechanism |
|---|---|---|
| 01, 09, 16 | identical | fixed-bill users; nothing to estimate |
| 17, 20 | within 0.1% | residual = rounding of one varying stream |
| 08, 18, 22, 23, 13 | within 1–2% on capacity; 08/13 miss `wait` | residual is one rounding step (−1 / −2 / 0 / +50.8 / +3); 08 and 13 lose the `wait` date because a rent/school-fee on **day 87** drags the 90-day minimum — the key does not count it (its horizon looks ≤ 86 days, unexplained) |
| 02, 03, 04, 25, 11 | 0.6–4% on capacity; categoricals right except 11 | IDR users: 2–3 weekly purchases of ~1–2M each before payday; ±15% amount noise × rounding; 11 additionally has a commission stream the key ends earlier |
| 06, 21 | key: pay today with stop/reduce; ours: wait / affordable_now | our trough is 58 / 46 off the key's — one rounding-sized item — and that decides whether a change-free plan is safe |
| 07 | key: installments; ours: not_affordable | −8,950 pessimistic on days 70–78 (three variable streams × rounding, accumulated over 2.5 months) |
| 19 | partial split | capacity 25,415 vs 28,820: one grocery placement inside vs outside the window |
| 14, 15 | capacity too high | first-salary ordering, see above |
| 05, 10, 12, 24 | capacity | stream termination / gig payout / one-occurrence differences |

## What would move the remaining rows

- **Integer rounding of varying streams**: evidence-based; on its own it does not add exact
  rows (5 → 5) because the schedule differences dominate. Adopt only with a schedule fix.
- **Horizon ≤ 86 days**: flips 08 and 13 to the key's `wait`; contradicts the 90-day contract
  and has no rationale. Not adopted.
- **Per-category first day** (e.g. groceries day 3, dining day 5): fits more rows on the samples
  and is unconstrained by any rule — classic overfit on 20 points. Not adopted.

## Verdict

The model reproduces the key's *structure* (18/25 categoricals, 13/20 minima within 2%, ten
rows within single units). The rest is (a) the key's integer rounding of noisy estimates and
(b) one-item schedule differences we cannot pin down with one request per user. Both are
recorded as V2 leads; neither is worth trading generality for on a 20-row jury.
