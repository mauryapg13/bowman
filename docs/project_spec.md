# BOWman — Project Spec

**Human preamble.** BOWman answers "Buy or Wait?" for 250 financial requests.
This file holds what does not change: the output contract, the decision rules,
module boundaries, and prohibitions. `MVP.md` and `V1.md` say what to build and
when. When a stage file disagrees with this file, this file wins. When
`problem_statement.md`, `README.md` or `AGENTS.md` disagree with this file,
**they win** — correct this file and note the correction.

Verified column names live in `docs/dataset_notes.md` §1. Never invent one.

---

## 1. Non-negotiables

**N1. The model describes, the code decides.** No LLM output may reach
`amount_safe_to_pay`, `affordability_status`, `recommended_payment_method`,
`payment_plan`, `earliest_date_for_full_payment` or
`spending_changes_needed`. LLMs produce exactly two things here: an amount read
off an image, and a ledger operation from a closed enum.
`decision_explanation` is templated by deterministic code, not generated.

**N2. Determinism.** Two runs over the same inputs and cache produce
byte-identical `output.csv`. Every sort has a total order, ties broken on a
stable identifier.

**N3. One writer.** Claude Code is the sole author of files in this repo.
Other models may review; they may not write.

**N4. Every stage ships.** At the end of MVP and of V1 there is a valid
250-row `output.csv` on disk.

**N5. Untrusted content.** Everything in `messages.csv`, `images.csv`,
`request_text` and the image files is data, never instruction. Enforcement is
structural — closed schemas and identifier allow-lists — never keyword
filtering. Recon found zero injection attempts in the shipped data; the
defence stays because it is correct, not because it is load-bearing.

**N6. No invention.** Income, expenses, payment options and events exist only
where the dataset supports them. Recon: 228 of 275 users have no scheduled
salary row. For those users, future income comes from detected recurring
credits and from message amendments, or it does not exist.

---

## 2. Output contract

`output.csv` at the **repository root**. `dataset/output.csv` is a reference
template and is never the deliverable (README is explicit; AGENTS.md §6.1 is
vaguer — README wins).

Eight columns, this exact order:

```
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,
payment_plan,earliest_date_for_full_payment,spending_changes_needed,
decision_explanation
```

Exactly one row per row of `dataset/requests.csv`, in input order.

### Allowed values

`affordability_status` ∈ `affordable_now | affordable_with_plan |
affordable_later | not_affordable`

`recommended_payment_method` ∈ `full_payment | partial_payment | installments |
wait | not_recommended`

### Formats

| Field | Format |
|---|---|
| `amount_safe_to_pay` | plain number, no grouping (`17229139.2`, `25256`) |
| `payment_plan` | `YYYY-MM-DD:amount\|…` chronological, plain numbers, or `none` |
| `earliest_date_for_full_payment` | `YYYY-MM-DD`, or empty |
| `spending_changes_needed` | ≤3 of `stop:<event_id>` or `reduce_to:<event_id>:<amount>`, `\|`-separated, or `none` |
| `decision_explanation` | templated, two sentences, 16–25 words |

Grouped thousands and currency codes appear **only** inside
`decision_explanation`.

### Invariants — assert before writing

- **I1** `0 <= amount_safe_to_pay <= requested_amount`
- **I2** `affordable_now` ⟹ `earliest_date_for_full_payment == request_date`
- **I3** `partial_payment` ⟹ `affordability_status == affordable_with_plan`
- **I4** `partial_payment` ⟹ exactly two payments summing to
  `requested_amount`: `amount_safe_to_pay` on `request_date`, remainder on
  `earliest_date_for_full_payment`
- **I5** `partial_payment` ⟹ `allows_partial_payment`,
  `0 < amount_safe_to_pay < requested_amount`,
  `earliest_date_for_full_payment <= desired_completion_date`
- **I6** `installments` ⟹ dates and amounts match one supplied
  `payment_option_id` exactly
- **I7** plan dates strictly non-decreasing
- **I8** chosen method ∈ `payment_methods_user_will_consider`, except
  `not_recommended`
- **I9** every `event_id` in `spending_changes_needed` has `flexibility`
  permitting that change, and its `category` is in the user's willing-to-stop
  or willing-to-reduce list
- **I10** no `event_id` appears in both a `stop:` and a `reduce_to:`
- **I11** ≤3 spending changes
- **I12** header and column order match byte-for-byte
- **I13** `not_affordable` ⟹ `payment_plan == none` and
  `earliest_date_for_full_payment` empty

A failed assertion aborts the write; the previous `output.csv` survives.

**Smell test, not a rule:** no sample has `amount_safe_to_pay == 0`. Many
zeros in your output means something upstream is broken.

---

## 3. Definitions

**Forecast window.** Days 0–90 inclusive, day 0 = `request_date`. 91 elements.

**Snapshot fact (verified, not assumed).** `current_available_balance` already
contains every settled event. Evidence: across all 275 users, zero settled
events are dated after `request_date` (the only later rows are 47 scheduled
salaries); every user's last settled event is 1–7 days before `request_date`;
and sample `request_03` — whose IDR 4,365,000 payslip credit settled 3 days
before the request — keys `amount_safe_to_pay = 873000`, which is impossible
if that credit were still to be added. Therefore settled events **never** move
the forward curve; they feed recurrence detection only. Guarded three ways:
`load.py` asserts no settled event post-dates its user's request;
`tests/test_calibration.py` checks the ~20 implied minima; an ablation that
re-applies settled-past events must score worse.

**Floor.** `minimum_balance_to_keep`. A hard lower bound, not zero.

**`balance[d]`.** Closing balance on day `d`, from
`current_available_balance` plus all included cash movements up to and
including day `d`.

**`suffix_min[d]`.** `min(balance[d:])`. The binding constraint for a payment
made on day `d`, since such a payment reduces days `d..90` only.

**Safe.** A plan is safe iff after subtracting its payments,
`balance[d] >= floor` for every `d` in 0..90.

**`amount_safe_to_pay`.** `clamp(suffix_min[0] - floor, 0, requested_amount)`,
computed **before** optional spending changes.

**`earliest_date_for_full_payment`.** First day `d` with
`suffix_min[d] - requested_amount >= floor`. Empty if none exists in the
window. Computed **without** spending changes and **independently of**
`payment_methods_user_will_consider` — it measures capacity, not preference.
Sample `request_12` confirms: capacity equalled the full amount, yet the
recommendation was installments because the user rejects full payment.

---

## 4. Building the ledger

### 4.1 Actuals and prediction must not double-count

64 requests have recorded events dated after `request_date`. These are real
records, not forecasts. The merge rule:

> **For each recurring stream, recorded events take precedence on the days
> they cover. Prediction fills only the days after that stream's last recorded
> occurrence.**

Never place a predicted occurrence on a day already covered by a recorded
event of the same stream. Doing so subtracts the same rent twice.

One-off recorded events after `request_date` are included as confirmed
movements, still subject to the inclusion gate.

### 4.2 Recurrence detection

There is no cadence column. Derive it. Two grouping units, chosen by
category — **not** a fallback, because the data shows which unit is real:

- **Variable-spend categories `groceries`, `transport`, `dining`** group by
  `(direction, category)`. Recon: at description level their median gaps are
  scattered 5–85 days (descriptions rotate); at category level they are tight
  at 5–24 days. Sample `request_11` reduces `event_989`, the latest of user_11's
  dining events, which recur every **21** days under six different
  descriptions — only category-level grouping reproduces it.
- **Every other category** groups by `(direction, category, description)`.
  Recon: all of these have median gaps in the 30-day bin; `salary` also shows
  weekly/fortnightly gig payouts (5–15 days) under a stable description.

A group of ≥3 occurrences whose median consecutive gap falls in **`[5, 35]`**
days is a recurring stream with `cadence_days = round(median gap)`,
`amount = median amount`, `anchor = latest occurrence`, carrying
`flexibility`, `category`, `minimum_allowed_amount` and the latest
`event_id`. The band was `[25, 35]`; it was widened after recon showed weekly
income and 21-day dining are real streams the samples expect.

`docs/mvp_results.md` records the count of streams per cadence bucket so a
future band change is measured, not argued.

**Absorption of scheduled occurrences.** 47 users carry a `scheduled` "Next
confirmed salary" row (and a few carry scheduled school-fee / insurance /
utility rows) that is the *next occurrence* of an already-detected stream
under a different description — 45 of 47 even repeat the amount. Left as a
one-off, the ledger would count that salary twice on the same day (once
predicted, once recorded). So after detection: a `scheduled` event with the
same `(direction, category)` as **exactly one** stream, dated one cadence
(±10 days) after that stream's anchor, joins the stream as its latest
*recorded* occurrence (new anchor, new `latest_event_id`). Settled history is
never absorbed; nothing is invented — the row exists. Measured: 48
absorptions on the shipped data. When no stream exists (e.g. `user_01`, one
prorated salary), the scheduled row stays a one-off and income after it is
not forecast — the conservative reading N6 demands.

Recurring expansion places occurrences at `anchor + k·cadence_days` for every
`k` landing in 0..90, subject to §4.1. Anchors before day 0 roll forward by
whole cadences; they are never skipped.

### 4.3 Inclusion gate

| Condition | Treatment |
|---|---|
| `status = settled` | include |
| `status = scheduled` | include — confirmed future |
| `status = pending`, `direction = debit` | include — unconfirmed outflow reserved |
| `status = pending`, `direction = credit` | **exclude** — unconfirmed inflow ignored |
| `status ∈ {cancelled, failed}` | exclude |
| `status = unrealized` or `direction = non_cash` | exclude — not cash |
| `amount is None` (blank cell, image not yet read) | exclude with `amount_unknown` — MVP only; `amounts.py` fills it in V1-2 and the row then re-enters the gate |

The asymmetry in rows 3 and 4 is deliberate. Do not symmetrise it.
`investment_purchase` (debit) and `investment_sale` (credit) are real cash;
only `investment_valuation` is not.

Every excluded event carries an `exclusion_reason`.

### 4.4 Lifecycle links

58 events carry `linked_event_id`. Recon confirms depth is always 1, no
fan-out, no dangling links — so no graph traversal is needed. A lookup table
over the seven observed patterns suffices:

| Parent → child | Handling |
|---|---|
| `expense.settled` → `refund.settled` (14) | both real cash; net effect zero |
| `expense.settled` → `refund.pending` (8) | expense counts, refund excluded |
| `expense.cancelled` → `expense.settled` (8) | cancelled excluded, settled counts |
| `expense.settled` → `expense.pending` (6) | duplicate charge — exclude the pending child |
| `debt_payment.failed` → `debt_payment.scheduled` (7) | failed excluded, scheduled counts |
| `investment_purchase.settled` → `investment_valuation.unrealized` (10) | valuation excluded |
| `investment_purchase.settled` → `investment_sale.settled` (5) | both real cash |

Any pattern not in this table falls to the precedence ladder.

### 4.5 Precedence ladder

When records conflict, apply in order, stopping at the first that fires:

1. Explicit cancellation, settlement or amendment. Only this rule rewrites or
   zeroes an amount.
2. Newer record from the same source.
3. Settled event over an estimate or forecast, regardless of date.
4. The financially safer interpretation — the reading that leaves **less**
   money available. Assume an ambiguous outflow is real; assume an ambiguous
   inflow is not.

Rule 4 also handles unresolved gaps. Never silently drop one; a dropped
outflow inflates every balance downstream.

### 4.6 Currency

Conversion happens in `load.py` for every row that has an amount, and in
`amounts.py` for the 16 rows whose amount comes from an image — same rule,
same function. It uses the `exchange_rates.csv` row matching
`(settlement_date, from_currency = record currency, to_currency =
home_currency)`. Recon confirms all 140 foreign rows have an exact match and
no reverse lookup is needed. A missing rate raises. Image-extracted amounts
carry their own currency and convert on the same rule — `event_7307` is a
blank-amount USD expense for an INR user and needs both. `load.py` never
calls a port: it must parse the CSVs with no API key and no OCR installed.

**Message-quoted amounts.** AGENTS.md §6.1 gives one FX rule and it applies
here too: *use the row for the event's settlement date, in the stated
`from_currency → to_currency` direction.* Seven messages confirm a salary in a
non-home currency ("Your salary of EUR 1804 is confirmed for 2025-08-15 … the
receiving bank will convert it using the rate applied on the settlement
date"). So `ports/ops` returns the amount **as quoted, with its currency**;
`amend.py` converts it with the rate row for the occurrence's settlement date
— the `effective_date` for a confirmed one-off, the occurrence date for a
stream. The model never converts.

**Dates with no rate row.** Recorded events always have an exact row (recon:
140/140). Predicted or amended occurrences may fall on a date with no row
(rows exist on the 15th of each month, 2023-10-15 … 2026-11-15). For those,
use the latest row on or before the date and record `rate_date_used` in
provenance. Recon shows every pair's rate is constant across all dates
(USD→INR 83.33, USD→IDR 15833.33, USD→EUR 0.92, EUR→USD 1.09, EUR→ZAR 20), so
this fallback is numerically neutral on this dataset; `tests/` asserts that
constancy so a future dataset with moving rates fails loudly instead of
silently using a stale row.

### 4.7 Missing information — the single lookup table

When something is absent, the answer is here, not in a judgement call. Each
row names the module that owns the rule and what the diagnostics must show.

| Missing thing | Rule | Owner | Trace |
|---|---|---|---|
| Blank `amount`, linked image exists (all 16 in the shipped data) | `amounts.py` fills it from the vision port. If the port fails or returns a non-conforming result, `amount` stays `None`. | `amounts` | `VisionResult` or the port error |
| Blank `amount`, no image, or port failed | Excluded, `exclusion_reason = amount_unknown`. An unknown outflow cannot be reserved as a number; it must never be treated as 0. | `inclusion` | exclusion entry |
| No scheduled salary row (228 users) | Use detected recurring credit streams. None ⇒ **zero forecast income**. Never synthesise (N6). | `recurrence` | `zero_income = true` |
| No exchange-rate row for a **recorded** event | Hard error; the run stops. | `load` | exception |
| No rate row on a **predicted/amended** date | Latest row on or before that date; `rate_date_used` recorded. | `amend`, `ledger` | `Amendment.rate_date_used` |
| Message changes an amount but gives no `effective_date` | Applies from the first occurrence **after** `request_date`. Occurrences on or before the request are history and cannot change. | `amend` | `Amendment.effective_date` set by code |
| Message quotes no currency | Home currency assumed; `Amendment.currency = null`. | `amend` | `Amendment` |
| Message target not in the allow-list, or op outside the enum | Operation becomes `none`; nothing changes. | `ports/ops` | `Operation` with `op = none` |
| `linked_event_id` pattern not in the §4.4 table | Precedence ladder §4.5; rule 4 = the reading that leaves less money. Never dropped silently. | `links` | `LinkResolution.pattern = unknown` |
| Ambiguous outflow / inflow | Outflow assumed real; inflow assumed absent (rule 4). | any | provenance string |
| `max_installment_months` blank | Installments unavailable (verified: all 119 such users omit `installments`). | `rank` | `rejection_reasons` |
| No safe eligible plan | `not_recommended`, `not_affordable`, plan `none`, date empty. | `rank`, `format` | `chosen = null` |
| `earliest_date_for_full_payment` not inside days 0..90 | Empty string. `wait` is not a candidate. | `ledger`, `plans` | `Capacity.earliest_full_day = null` |
| Payment option missing for a request | Cannot happen (every request has 2–4); if it does, `load` raises. | `load` | exception |

Anything not in this table is a new case: add the row **before** writing the
code that handles it.

---

## 5. Candidate plans and ranking

Enumerate, filter, sort. **Never a cascade** — an `if/elif` ladder encodes our
preferences; the sort encodes the spec's.

### Candidates

- `full_payment` — from the request's single `full_payment` option row
- `installments` — one per installment option, using `payment_amount`,
  `number_of_payments`, `first_payment_date`, `payment_frequency_days` exactly
- `partial_payment` — `amount_safe_to_pay` on day 0, remainder on
  `earliest_date_for_full_payment`, only where I5 holds
- `wait` — `requested_amount` on `earliest_date_for_full_payment`
- spending-change variants — see §6

### Filters, in order

1. **Method eligibility.** Method ∈ `payment_methods_user_will_consider`.
   `wait` requires `full_payment` accepted. `not_recommended` always eligible.
2. **Installment term gate.** `number_of_payments × payment_frequency_days /
   30 <= max_installment_months`. Blank `max_installment_months` reads as
   "installments unavailable" — **verify by cross-tab**; if any profile has a
   blank value while listing `installments`, this reading is wrong.
3. **Safety.** Per §3.

### Sort key — lower is better throughout

```python
(
  0 if completes_by_desired_completion_date else 1,
  len(spending_changes),
  total_paid,
  (first_payment_date - request_date).days,
  len(payments),
  option_id or "",
)
```

`sorted(survivors, key=sort_key)[0]`. No survivors → `not_recommended`, plan
`none`.

Two consequences worth internalising. Key 2 above key 3 means a **more
expensive** plan needing no spending changes beats a cheaper one that needs
them. Key 3 means a cheaper `wait` beats a fee-bearing installment plan even
when the user accepts installments.

Recon: 434 of 515 installment options finish after their deadline and die on
key 1. All five sample installment picks are the 3-payment option.

### Status derivation

| Condition | Status |
|---|---|
| pays in full on day 0, no spending changes | `affordable_now` |
| completes in full via installments, partial, or spending changes | `affordable_with_plan` |
| full amount safe later and the plan is `wait` | `affordable_later` |
| no safe eligible plan completes the request in the window | `not_affordable` |

Note row 2: full payment on day 0 that **requires spending changes** is
`affordable_with_plan`, not `affordable_now`. Three samples confirm this.

---

## 6. Spending changes

Not a search. A lookup with two gates.

**Eligible to stop:** `flexibility ∈ {stoppable, reducible_or_stoppable}`
**and** `category ∈ expense_categories_user_is_willing_to_stop`.

**Eligible to reduce:** `flexibility ∈ {reducible, reducible_or_stoppable}`
**and** `category ∈ expense_categories_user_is_willing_to_reduce`. The new
amount is that event's `minimum_allowed_amount`, populated on all 2,907
reducible rows.

**Never eligible:** any category in `expense_categories_to_protect`.

Generate spending-change candidates only when no candidate without them is
both safe and completes by `desired_completion_date` — key 2 of the sort
guarantees such a candidate would win anyway. Try subsets in increasing size,
ordered by `event_id`, maximum three.

The `event_id` written to output identifies the recurring stream. Use the
stream's latest occurrence `event_id`, and verify against the three samples
(`stop:event_476`, `reduce_to:event_989:665950`,
`stop:event_1815|reduce_to:event_1816:23.50`) before trusting the rule.

---

## 7. Modules

| Module | In | Out |
|---|---|---|
| `load.py` | nine CSVs | typed records, indexes; amounts in home currency where present, `None` where blank; asserts the snapshot fact |
| `amounts.py` | events with `amount is None`, `ports/vision` | the same events with amount filled and converted (V1-2); a no-op in MVP |
| `inclusion.py` | raw events | included flag + `exclusion_reason` |
| `links.py` | linked pairs | §4.4 resolutions |
| `recurrence.py` | included events | streams with cadence, amount, anchor, flexibility |
| `ledger.py` | streams, one-offs, start, opening | `balance[0..90]`, `suffix_min[0..90]` |
| `spending.py` | streams, profile | eligible stop/reduce actions; returns **new** stream lists, never mutates (V1-4) |
| `plans.py` | request, arrays, profile, options | candidates with `safe`, `total_paid`, `completes_by_deadline`; re-runs `ledger.forecast` for spending variants |
| `rank.py` | candidates, profile | chosen plan, derived status |
| `format.py` | chosen plan, profile, request | the seven output cells, templated |
| `write.py` | 250 `Decision`s | validated `output.csv`, atomically; ignores `diagnostics` |
| `main.py` | paths | `run(requests) -> list[Decision]`; the CLI is a thin wrapper. `score.py` and `ablation.py` call `run`, never copy it |
| `ports/vision.py` | `image_id` + event description | `{amount_raw, amount, currency, field_used, confidence}` |
| `ports/ops.py` | message + target allow-list | closed-enum operation |
| `ports/cache.py` | key | cached JSON or miss |

**Record types.** `Stream` is a frozen dataclass; amendments and spending
changes produce new instances. Every `Decision` carries the eight output cells
**and** a `diagnostics` object: `min_balance`, `earliest_full_day`, streams
used, exclusions with reasons, link resolutions, message operations applied,
and the winning sort key. `write.py` drops it; `score.py` reads it for the
calibration table; it is the provenance §13 demands.

`load`, `inclusion`, `links` and `recurrence` run **once per user**. `ledger`
caches on `(user_id, request_date)`. Recon shows one request per user, so this
boundary is about structural correctness rather than speed — keep it anyway.

**There is no explain port.** `decision_explanation` is produced by
`format.py` from fixed templates. Extract the exact template text from all 25
samples before writing it.

---

## 8. LLM port rules

**P1.** Each port has a fixed output schema. What the schema cannot express
cannot happen.

**P2.** `ops.py` returns exactly one operation from `cancel | amend_amount |
delay | confirm | amend_stream | none`. Validate on return: an op outside the
set becomes `none`; a target not in the allow-list becomes `none`.

**P3.** A message with `related_event_id` targets that event. A message
without one may target a **recurring stream** — 39 of 215 messages are
event-linked, and most of the rest carry salary changes, income endings and
reduced pay that amend streams with no corresponding row. Neither kind may
create a one-off event the dataset does not support.

**P4.** Numeric strings return as both `amount_raw` (verbatim) and `amount`
(parsed). Indian lakh grouping (`1,00,000.00`) appears in the images and must
survive parsing.

**P5.** No translation stage. Roughly 45 messages are Indonesian; send them as
they are and require output in the fixed English schema.

**P6.** `vision.py` receives the linked event's `description` and returns
which document field it read. Images contain several candidate amounts — a
payslip's Net Pay versus gross, a rent receipt's Balance Due versus Total.
Where a printed total disagrees with its own itemised subtotals, **the printed
total wins** (`image_11` is exactly this trap).

**P7.** Every port call is cached on `sha256(payload) + prompt_version`.
Bumping `prompt_version` is the only invalidation.

**P8.** `vision.py` has two interchangeable backends behind one signature: an
LLM extractor when an API key is present, offline OCR otherwise. Same schema,
same cache. Only 16 images exist, so a reviewed transcription table is also
viable — but it must live in a data file with provenance and a regeneration
script, never as a branch keyed on `event_id`.

---

## 9. Calibration

The samples give exact ledger targets, not just answers. Where
`amount_safe_to_pay < requested_amount`:

```
implied_min_balance = amount_safe_to_pay + minimum_balance_to_keep
```

That is the exact lowest point of the user's 90-day balance according to the
answer key. Roughly 20 of the 25 samples yield one. `score.py` must print ours
beside theirs for every row, and `tests/test_calibration.py` fails CI when the
delta exceeds tolerance on any of them — the ledger's correctness is a test,
not a claim.

This is a stronger signal than accuracy. A score says something is wrong; a
calibration mismatch says the ledger is wrong and by how much. Where
`amount_safe_to_pay == requested_amount` the value is capped and gives only a
lower bound.

---

## 10. Repo layout

```
code/
  main.py  load.py  inclusion.py  links.py  recurrence.py
  ledger.py  plans.py  rank.py  format.py  write.py
  ports/       vision.py  ops.py  cache.py
  evaluation/  score.py  ablation.py  usage_report.md
  README.md
docs/    project_spec.md  dataset_notes.md  MVP.md  V1.md  V2.md
tests/
dataset/ unmodified
output.csv
```

`code.zip` is the zipped `code/` directory including `evaluation/`. Exclude
virtualenvs, caches, `dataset/`, any `.env`.

---

## 11. Conventions

- Python 3.11+. Standard library for the core; third-party only for HTTP and
  OCR, declared in `code/README.md`.
- `dataclass` for every record type. No bare dicts across boundaries.
- Type hints on public functions. Dates are `datetime.date` except at CSV
  edges. Money is `float`, rounded once at write time.
- Secrets from environment variables only. Ship `.env.example`. Never commit a
  key.
- Fail loudly in the core, gracefully in the ports.

---

## 12. Prohibited

- **No hardcoded sample answers.** No branch may key on a specific
  `request_id` or `user_id`. `sample_requests.csv` is a regression diagnostic
  for policy, never a lookup table.
- No arithmetic by LLM (N1).
- No keyword-based injection filtering — schemas, not blocklists.
- No writes to `dataset/`.
- No second writing agent (N3).
- No output written before validation passes.
- No invented income for the 228 users without a scheduled salary row.

---

## 13. Why traceability matters

Every stream and fact carries provenance: which sources produced it, which
rule fired. Three reasons, in order: it is how a wrong sample row gets
diagnosed, it is what the calibration check reads, and it is what makes the
architecture defensible under questioning.

Submissions are judged on four signals — the code, the agent's output, the
chat transcript, and a 30-minute interview. Only one of the four is
`output.csv`.

---

## 14. Corrections log

Shipped docs and verified data win over this file. Every change is listed.

| Date | Section | Change | Evidence |
|---|---|---|---|
| 2026-09-13 | §3 | Added the snapshot fact + three guards | 0 settled events after any request_date; sample request_03 |
| 2026-09-13 | §4.2 | Grouping unit by category (variable-spend → category level); band `[25,35]` → `[5,35]` | median-gap histogram in recon; user_11 dining every 21 days; sample request_11 |
| 2026-09-13 | §4.3 | `amount is None` row: excluded as `amount_unknown` until `amounts.py` fills it | 16 blank amounts, all one-offs 1–3 days before request |
| 2026-09-13 | §4.6, §7 | Vision moved out of `load.py` into `amounts.py`; `load` is port-free | load must run with no key/OCR |
| 2026-09-13 | §7 | `spending.py` returns new stream lists; `Stream` frozen; `main.run()`; `Decision.diagnostics` | decoupling review |
| 2026-09-13 | §9 | Calibration is a CI test, not only a printout | — |
| 2026-09-13 | §4.2 | Monthly streams (cadence 28–31) recur on the anchor's day-of-month, clamped to month end; shorter cadences use day arithmetic | samples key salary on the 15th; 30-day steps drift (13 Nov vs 15 Nov) |
| 2026-09-13 | §4.2 | Category-level fallback for any category whose description pass finds nothing (not only groceries/transport/dining) | user_09 fortnightly freelance income |
| 2026-09-13 | §4.2 | Absorption of scheduled occurrences into their stream (prevents same-day double count) | 47 scheduled salaries, 45 same amount as last payroll |
| 2026-09-13 | §4.7 | New: single missing-information table; adds the no-effective-date and no-currency rules | user question 2026-09-13 |
| 2026-09-13 | §4.6 | Message-quoted foreign amounts convert in `amend.py` at the occurrence's settlement-date row (AGENTS.md §6.1); latest-on-or-before fallback for dates with no row | 7 foreign-salary messages; rates constant per pair |
