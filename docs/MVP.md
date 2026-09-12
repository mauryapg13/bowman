# MVP — Deterministic Core

**Human preamble.** Ship a valid 250-row `output.csv` with zero LLM calls,
zero image reads and zero message handling. Everything here is arithmetic over
`financial_events.csv`, `financial_profiles.csv` and
`request_payment_options.csv`. The point is not accuracy — it is a submittable
artefact plus a scorer, so every later change is measured rather than guessed.

Read `docs/project_spec.md` and `docs/dataset_notes.md` first. Column names
come from the `COL` block in `dataset_notes.md`.

**Deliberately out of scope:** images, messages, spending changes, lifecycle
links. Each is a V1 task.

---

## M1 — `code/load.py`

Parse into dataclasses using the verified `COL` block: `Profile`, `RawEvent`,
`Request`, `PaymentOption`.

- Dates → `datetime.date`. `allows_partial_payment` → bool from lowercase
  `true`/`false`.
- `|`-split every list column: `financial_priorities`,
  `expense_categories_to_protect`,
  `expense_categories_user_is_willing_to_reduce`,
  `expense_categories_user_is_willing_to_stop`,
  `payment_methods_user_will_consider`.
- `max_installment_months`: blank → `None`.
- `amount`: blank → `None`, never `0.0`.

FX per spec §4.6. A missing rate raises.

Indexes: `events_by_user`, `options_by_request`, `profile_by_user`.

Assert the snapshot fact (spec §3): no settled event is dated after its
user's `request_date`. Fail loudly if the hidden data breaks it.

`load.py` calls no port. `code/amounts.py` exists as a pass-through in MVP.

**Done when:** all nine files load; 25,342 events parsed; exactly 16 with
`amount is None`; 139 converted at load (the 140th foreign row, `event_7307`, is
blank and converts in `amounts.py`); zero FX failures; the snapshot assertion
passes.

## M2 — `code/inclusion.py`

Implement the spec §4.3 table. Record `exclusion_reason` on every exclusion.

**Done when:** printed counts show 10 `non_cash`, 22 `cancelled`, 21 `failed`,
10 `unrealized` and 16 `amount_unknown` excluded, and pending debits retained
while pending credits are dropped.

## M3 — `code/recurrence.py`

**The highest-value module in the MVP.** Implement spec §4.2 exactly:
category-level grouping for `groceries`/`transport`/`dining`, description-level
elsewhere, band `[5, 35]`. Print a histogram of streams per cadence bucket for
`docs/mvp_results.md`.

Emit a `Stream` per detected series: `cadence_days`, `amount`, `anchor`,
`category`, `flexibility`, `latest_event_id`, `occurrences` (the list of
recorded dates, needed by M4).

Everything unmatched becomes a one-off at its `settlement_date`.

Log how many users end with zero forecast income — spec N6 forbids inventing
it, and recon says 228 of 275 have no scheduled salary row.

**Done when:** `user_01` resolves to distinct streams for the monthly rent
transfer, the music subscription and the household utility payment, with
cadences near 30 and amounts matching the recorded history; and `user_11`
resolves to one dining stream with cadence 21 whose `latest_event_id` is
`event_989`.

## M4 — `code/ledger.py`

`forecast(streams, oneoffs, start, opening) -> balance[0..90]`.

**Implement the merge rule from spec §4.1, not a switch.** For each stream:

1. Place every **recorded** occurrence whose date falls in the window, from
   `stream.occurrences`.
2. Then place **predicted** occurrences at `anchor + k·cadence` only for days
   strictly after the stream's last recorded occurrence.

A predicted occurrence must never land on a day already covered by a recorded
one for the same stream. Assert this — it is the double-counting bug, and it
would otherwise silently halve those users' balances.

One-offs land at `(settlement_date - start).days` if in `0..90`.

Anchors before day 0 roll forward by whole cadences; never skipped.

Then `suffix_minima(balance)` by one reverse scan. Cache on
`(user_id, request_date)`.

**Done when:** `tests/test_ledger.py` covers a past anchor rolling forward, a
one-off outside the window being ignored, suffix minima being monotonically
non-decreasing, and — explicitly — a stream with recorded occurrences after
`request_date` producing no duplicate placements.

## M5 — `code/plans.py`

Build the four candidate families from spec §5 (no spending-change variants in
MVP). Per candidate compute `total_paid` (`total_payable_amount` for options),
`completes_by_deadline`, and `safe`.

**Done when:** across the samples, roughly 84% of installment candidates are
rejected on `completes_by_deadline`, matching recon's 434/515.

## M6 — `code/rank.py`

Filters and sort key from spec §5. Status derivation from the same section,
including the spending-change branch (unreachable in MVP — leave it wired).

Run the `max_installment_months` cross-tab described in spec §5 filter 2 and
record the result in `docs/mvp_results.md`.

## M7 — `code/format.py`

`decision_explanation` is **templated, not generated**.

Before writing this module, extract all 25 `decision_explanation` cells from
`sample_requests.csv` and derive the exact template per outcome. Recon quoted
three and inferred the rest; work from all 25.

Confirmed formatting rules: currency **code** prefix, comma-grouped thousands,
decimals only when non-zero (`ZAR 25,256` but `IDR 15,952,906.67`), dates
written as `8 August 2025`, and the second sentence citing
`minimum_balance_to_keep` verbatim rather than the computed minimum.

Grouping applies only inside this column. `payment_plan` and
`amount_safe_to_pay` use plain numbers.

## M8 — `code/write.py`

Assert I1–I13 from spec §2, then temp file → `fsync` → atomic replace to the
**repo-root** `output.csv`.

## M9 — `code/evaluation/score.py`

**Build this before starting V1.** Runs the pipeline over
`sample_requests.csv` and reports:

- per-column accuracy for all seven scored columns, separately
- exact-match rate on the three categorical columns
- `amount_safe_to_pay`: absolute and relative error, plus count within 0.5%
- **the calibration table from spec §9** — for every row where
  `amount_safe_to_pay < requested_amount`, print
  `expected_min = amount_safe_to_pay + minimum_balance_to_keep` beside our
  computed `min(balance)`, with the delta
- a per-row diff of expected vs actual for every mismatch, one line per row

`tests/test_calibration.py` wraps the calibration table as a CI test. The
pipeline is invoked through `main.run(...)`, never re-implemented.

The calibration column is the most valuable output here. A mismatch localises
the fault to the ledger; a match means the balance curve's floor is right and
any remaining error lives in ranking or formatting.

## Definition of done

- `python3 code/main.py` produces a root-level `output.csv` with 250 rows.
- All invariants pass; nothing was written that failed validation.
- `score.py` prints the per-column table and the calibration table.
- Two runs produce byte-identical output (`sha256`).
- Zero network calls, zero API keys required.
- `docs/mvp_results.md` records the baseline per-column score, the calibration
  deltas, the `max_installment_months` cross-tab, and the count of users with
  zero forecast income.

Do not start V1 until `mvp_results.md` exists.
