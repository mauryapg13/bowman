# Learnings — read this before touching the pipeline

Durable, non-obvious facts learned while building BOWman. Each entry says how it
was learned so it can be re-verified. Rules live in `docs/project_spec.md`; this
file is the *why* and the *gotchas*. Append, never rewrite history; date each entry.

## Data facts (verified 2026-09-13 by scripts in scratch/ and tests/)

- **Balance snapshot = request_date.** Zero settled events post-date any user's
  request; last settled event is 1–7 days before it. Sample `request_03` proves the
  IDR 4,365,000 payslip credit is already inside `current_available_balance`.
  → settled history never moves the forward curve. Guard: `load._assert_snapshot`.
- **One request per user, one message max per user**; `request_NN` ↔ `user_NN`.
- **Only 47/275 users have a scheduled "Next confirmed salary" row.** It is the next
  occurrence of their payroll stream (45/47 same amount). Left as a one-off it is
  counted twice on the same day. → `recurrence._absorb`.
- **No recurrence column.** Fixed bills recur per description at ~30d. Groceries /
  transport / dining rotate descriptions and only look regular at category level
  (5–24d). Salary can be weekly/fortnightly gig income under one description
  (`Weekly app earnings`) or rotating freelance descriptions (user_09) → category
  fallback needed beyond the fixed three.
- **user_11 dining recurs every 21 days** and the key reduces it (`event_989`), so
  the cadence band is [5, 35], not [25, 35].
- **Monthly streams land on the same day-of-month.** The key puts salary on the 15th
  every month; anchor+30k drifts (13 Nov vs 15 Nov). Cadence 28–31 ⇒ monthly.
- **Exchange rates are constant per pair** (USD→INR 83.33, USD→IDR 15833.33,
  USD→EUR 0.92, EUR→USD 1.09, EUR→ZAR 20), rows on the 15th of each month
  2023-10-15…2026-11-15, plus one row `2025-10-01,USD,INR` that exists only for
  `event_7307`. All 140 recorded foreign rows match exactly. Test pins constancy.
- **16 blank amounts ↔ 16 images, 1:1.** All are the user's last event, 1–3 days
  before the request, unique descriptions (never stream members). 12 settled (only
  affect category medians), 4 pending/scheduled (`event_1442`, `1786`, `6033`,
  `6859`) actually move the curve. `event_7307` is USD for an INR user.
- **Images carry several amounts.** Payslip: read Net Pay (4,365,000), not Salary.
  Rent receipt: Balance Due (1,00,000 — lakh grouping), not Total. Hospital bill:
  printed total 3650 while line items sum to 3150 — printed total wins.
- **`linked_event_id` never chains** (depth 1, no fan-out). 7 patterns only. The
  child (later row) carries the link. Duplicate charges are a `pending` child titled
  "Possible duplicate card charge" — zero exact-duplicate rows exist.
- **434/515 installment options end after the deadline.** Every sample installment
  pick is the 3-payment option. Installment first payments are request_date +
  {0,1,3,5,6,7,14} days; full_payment always day 0 with amount == requested.
- **`max_installment_months` blank ⇔ user omits `installments`** (119 vs 156, no
  crossovers).
- **Spending-change `event_id` = latest recorded occurrence of the stream** on/before
  request_date (verified on event_476, 989, 1815, 1816). `minimum_allowed_amount`
  is constant across a stream's rows.
- **Messages: zero injection attempts.** 168 template families; ~45 Indonesian.
  Soft imperatives only ("income that has ended should be removed…"). Intent
  families: first salary at new job (27), income ended (17), invoice approved (15),
  raise (13), refund pending (13), prize pending/settled (12), temporary reduced pay
  (10), unpaid-leave reduction (10), one-time arrears (9), gig payout pending (9),
  bonus unconfirmed (8), salary resumes + childcare (8), rent +12% (7), foreign
  salary FX note (7), payday moved (6), dispute open (6), failed debit retry (4),
  inter-account transfer (7), commission pending (8), reimbursement ≠ salary (3),
  investment sale settled (3), investment value fallen (3).
- **Some income endings are only in event text**: user_05's last payroll row is
  titled "Final employer payroll" with no message. No deterministic rule catches it
  yet (open).
- **Sample explanations are two-sentence templates**, 16–25 words. Two `wait`
  variants (5:1 → use "Pay X in full on D. Paying earlier would take the balance
  below the Y minimum."); two `affordable_now` variants (2:1 → "leaves at least");
  `not_affordable` uses "Do not proceed with… Although X is available today…" only
  when the user accepts *only* partial_payment and the request allows partial.
- **Number formats differ by column**: `amount_safe_to_pay` shortest repr (603.3);
  `payment_plan` and `reduce_to` amounts 2 dp when fractional (620.40, 23.50);
  explanation amounts comma-grouped with 2 dp when fractional; dates "8 August 2025".
- **`request_12`**: capacity == requested yet `affordable_with_plan/installments`
  because the user rejects full payment — capacity and recommendation are independent.

## Learned in V1 (2026-09-13, from the calibration table)

- **A scheduled salary that matches no stream must still become income** (user_01: one
  prorated salary + "Next confirmed salary"; the key is `affordable_now`, impossible without
  income after 15 Mar). Promote it to a monthly stream anchored on itself.
- **Absorption must pick the closest-amount stream** when a user has two salary streams
  (user_13) — otherwise the scheduled row is a one-off *and* a predicted occurrence: double count.
- **Streams end when they skip a beat**: expected next occurrence > 7 days before the user's
  last settled event ⇒ ended (user_05 "Final employer payroll", user_13 second income). This
  catches terminations without reading wording.
- **Messages can create income only when no income stream exists** (`start_stream`, allow-list
  target `new:salary`): users 14/15 have zero history and the key counts the confirmed salary.
- **GLM 5.3 Flash handles the Indonesian messages and the closed enum well** at temperature 0;
  ~1,400 input / ~370 output tokens per message; whole cache ≈ $0.11.
- **Determinism test = full CLI run twice**; with a live provider and a cold cache that is
  ~200 calls × ~5 s. Warm the cache first (run `main.py` once) or the suite looks hung.
- **Stream amount estimator**: median vs mean vs last-3 made no consistent difference on
  categoricals; residual deltas of a few percent remain on 4–5 users and are not the estimator.
- The `Weekly app earnings`-style gig income + "payout still pending" message (request_10):
  the key drops ~one stream's worth; not identifiable from the text — left as a known miss.

- **Cash moves on `settlement_date`** — recurrence anchors, cadence and placements must use
  it (request_07: salary event 15th, settled 23rd; key's earliest date is the 23rd).
- **Plot the curves before fitting.** All 25 minima sit on the pre-payday trough, so only
  the first ~10 days of forecast matter for `amount_safe_to_pay`. That reframed the search
  from "which statistic" to "which phase": the key restarts variable-spend streams at the
  request (first occurrence ~day 3), not at last-occurrence + cadence. Mean error 248k → 88k,
  categoricals unchanged. (`docs/v1_log.md` #13)
- **The key's variable-spend estimator is not median/mean/last/last-N × median-gap/mean-gap/7/14**
  (30-combo grid, ≤2 of 20 rows exact). Residuals of a few percent on ~6 users remain; exactness
  on `amount_safe_to_pay` is not reachable by tuning this family. Don't spend more time there.
- **Variable-spend amounts are i.i.d. noise** (800 streams: lag-1 autocorrelation −0.08, no trend,
  every predictor at the ~15% floor, mean/median best). Figures: `docs/why_variable_spend_is_noise.png`,
  `docs/sample_curves.png`. No "prediction factor" can help; don't build one.
- **A cadence of 0 days loops the ledger forever** — guard `cadence_days >= 1` (hit during the grid
  with a last-gap rule on same-day occurrences).
- **Ops cache keys must not depend on the forecast estimator**: the model's stream view uses the
  median of occurrences and the median gap, so experiments don't trigger live calls.

## Engineering gotchas

- The starter shipped an **empty `code/evaluation/main.py`**; with `code/evaluation`
  on `sys.path` it shadows `code/main.py`. Deleted.
- `sorted()` on `RawEvent` by `(event_date, id number)` — ids are strings, sort by
  the integer suffix.
- Frozen slots dataclasses: use `dataclasses.replace`, never `__dict__`.
- `score.py` must call `main.run()`; `tests/test_calibration.py` is a no-regression
  gate against `code/evaluation/baseline_mvp.json` — move the baseline forward only
  in the same commit that updates `docs/*_results.md`.
- Branch protection on `main`: PR + `test` check required; `log.txt` and
  `scratch/` are gitignored; CI fails on any diff under `dataset/`.

## Calibration signal (spec §9) — how to read it

`expected_min = key amount_safe_to_pay + minimum_balance_to_keep` when the key's
safe amount is below the request. Positive delta = we are optimistic (missed an
outflow / kept an ended income); negative = pessimistic (missed an income). Rows
within a few units (request_08, 17, 22) mean the curve shape is right. MVP baseline
mean |delta| ≈ 200k; the big rows each have a named cause in `docs/mvp_results.md`.

## Process

- Spec wins over stage docs; shipped docs (README/AGENTS/problem_statement) win over
  spec — every correction goes in spec §14.
- Any absence not in spec §4.7's table is a new case: add the row before the code.
- Every turn is logged to repo-root `log.txt` with `tool=Claude Code`.
