# Dataset Notes — Buy or Wait? (Task 0 recon)

Generated 2026-09-13 by read-only inspection of `dataset/` (scripts in `scratch/`, not committed).
Every column name below was copied from a real CSV header. Nothing under `dataset/` or `code/` was modified.

`docs/project_spec.md` does **not exist** at the time of this recon, and neither does
`evaluation_criteria.md`. There is therefore nothing to contradict yet; the "shipped docs win"
rule is recorded in §5 so the spec, when written, is checked against this file.

---

## 1. `COL` block

```python
# Verified column names — copied byte-for-byte from dataset/*.csv headers (2026-09-13).
COL = {
    # financial_profiles.csv
    "profiles": {
        "user_id": "user_id",
        "home_currency": "home_currency",
        "balance": "current_available_balance",
        "min_balance": "minimum_balance_to_keep",
        "priorities": "financial_priorities",                         # '|'-delimited
        "protect_categories": "expense_categories_to_protect",         # '|'-delimited
        "reduce_categories": "expense_categories_user_is_willing_to_reduce",  # '|'-delimited, may be blank
        "stop_categories": "expense_categories_user_is_willing_to_stop",      # '|'-delimited, may be blank
        "accepted_methods": "payment_methods_user_will_consider",      # '|'-delimited
        "max_installment_months": "max_installment_months",           # blank = no installments
    },
    # financial_events.csv
    "events": {
        "event_id": "event_id",
        "user_id": "user_id",
        "event_type": "event_type",          # expense|subscription|income|debt_payment|investment_purchase|refund|investment_valuation|investment_sale
        "description": "description",
        "category": "category",
        "direction": "direction",            # debit|credit|non_cash
        "amount": "amount",                  # blank on 16 rows -> read from image
        "currency": "currency",
        "event_date": "event_date",
        "settlement_date": "settlement_date",  # blank on the 10 non_cash rows
        "status": "status",                  # settled|pending|scheduled|cancelled|failed|unrealized
        "linked_event_id": "linked_event_id",
        "flexibility": "flexibility",        # fixed|reducible|stoppable|reducible_or_stoppable
        "min_allowed_amount": "minimum_allowed_amount",  # populated only for reducible / reducible_or_stoppable
    },
    # exchange_rates.csv
    "fx": {
        "rate_date": "rate_date",
        "from_currency": "from_currency",
        "to_currency": "to_currency",
        "rate": "rate",
    },
    # requests.csv / sample_requests.csv (input columns)
    "requests": {
        "request_id": "request_id",
        "user_id": "user_id",
        "request_date": "request_date",
        "request_type": "request_type",
        "requested_amount": "requested_amount",
        "deadline": "desired_completion_date",
        "allows_partial": "allows_partial_payment",   # literal 'true' / 'false'
        "request_text": "request_text",
    },
    # sample_requests.csv extra columns == output.csv columns
    "output": [
        "request_id",
        "amount_safe_to_pay",
        "affordability_status",
        "recommended_payment_method",
        "payment_plan",
        "earliest_date_for_full_payment",
        "spending_changes_needed",
        "decision_explanation",
    ],
    # request_payment_options.csv
    "options": {
        "option_id": "payment_option_id",
        "request_id": "request_id",
        "method": "payment_method",              # full_payment|installments
        "per_payment_amount": "payment_amount",
        "n_payments": "number_of_payments",
        "first_payment_date": "first_payment_date",
        "frequency_days": "payment_frequency_days",  # blank for full_payment; 28|30|31
        "fee": "financing_fee",
        "total_payable": "total_payable_amount",
    },
    # messages.csv
    "messages": {
        "message_id": "message_id",
        "user_id": "user_id",
        "request_id": "request_id",
        "related_event_id": "related_event_id",
        "sent_at": "sent_at",                # ISO-8601 with 'Z'
        "source_type": "source_type",        # employer|service_provider|financial_service|bank|merchant
        "text": "message_text",
    },
    # images.csv
    "images": {
        "image_id": "image_id",
        "user_id": "user_id",
        "request_id": "request_id",
        "related_event_id": "related_event_id",
    },
}
```

---

## 2. Data dictionary

### financial_profiles.csv (275 rows)

| column | type | nullable | notes |
|---|---|---|---|
| `user_id` | str | no | `user_01`…`user_275`; PK; one row per user |
| `home_currency` | enum | no | INR 67, EUR 62, IDR 55, ZAR 51, USD 40 |
| `current_available_balance` | float | no | 683.69 … 136,691,818.94 |
| `minimum_balance_to_keep` | float | no | 400 … 41,430,800 |
| `financial_priorities` | `\|`-list | no | 9 distinct combos, e.g. `education\|debt_repayment` |
| `expense_categories_to_protect` | `\|`-list | no | 8 distinct combos, always includes `rent` or `housing` |
| `expense_categories_user_is_willing_to_reduce` | `\|`-list | **yes** (blank possible) | values ⊂ {dining, entertainment, streaming, shopping, gym} |
| `expense_categories_user_is_willing_to_stop` | `\|`-list | **yes** (62 blank) | values ⊂ {cloud_storage, streaming, music_subscription, delivery_membership, gym} |
| `payment_methods_user_will_consider` | `\|`-list | no | 7 distinct combos of full_payment / partial_payment / installments |
| `max_installment_months` | int | **yes** (119 blank) | 2 … 12 |

### financial_events.csv (25,342 rows)

| column | type | nullable | notes |
|---|---|---|---|
| `event_id` | str | no | `event_01`…`event_25342`; PK |
| `user_id` | str | no | FK → profiles; ~92 events/user |
| `event_type` | enum | no | expense 20525, subscription 2488, income 1696, debt_payment 567, investment_purchase 29, refund 22, investment_valuation 10, investment_sale 5 |
| `description` | str | no | free text, templated (e.g. `Apartment rent transfer`) |
| `category` | enum | no | 22 values (groceries, transport, dining, salary, utilities, rent, cloud_storage, …) |
| `direction` | enum | no | debit 23609, credit 1723, non_cash 10 |
| `amount` | float | **yes** (16 blank) | 2 … 48,830,000; blank ⇒ image lookup |
| `currency` | enum | no | INR/EUR/IDR/ZAR/USD; 140 rows differ from user's home currency |
| `event_date` | date | no | 2019-03-09 … 2026-09-03 |
| `settlement_date` | date | **yes** (10 blank) | blank only on `non_cash` valuation rows; ≠ event_date on 178 rows |
| `status` | enum | no | settled 25148, pending 71, scheduled 70, cancelled 22, failed 21, unrealized 10 |
| `linked_event_id` | str | **yes** (58 non-blank) | FK → earlier event; no chains deeper than 1 |
| `flexibility` | enum | no | fixed 21138, reducible 2682, stoppable 1297, reducible_or_stoppable 225 |
| `minimum_allowed_amount` | float | **yes** (22,435 blank) | present iff flexibility ∈ {reducible, reducible_or_stoppable} |

### exchange_rates.csv (134 rows)

| column | type | nullable | notes |
|---|---|---|---|
| `rate_date` | date | no | 2023-10-15 … 2026-11-15; 133 rows on the 15th, one on 2025-10-01 |
| `from_currency` | enum | no | USD 88, EUR 46 |
| `to_currency` | enum | no | INR 33, IDR 30, EUR 25, USD 24, ZAR 22 |
| `rate` | float | no | constant per pair: USD→INR 83.33, USD→IDR 15833.33, USD→EUR 0.92, EUR→USD 1.09, EUR→ZAR 20 |

### requests.csv (250 rows) / sample_requests.csv (25 rows, same 8 input columns + 7 output columns)

| column | type | nullable | notes |
|---|---|---|---|
| `request_id` | str | no | `request_26`…`request_275` (eval) / `request_01`…`request_25` (sample); PK |
| `user_id` | str | no | numeric suffix always equals request's suffix (one request per user) |
| `request_date` | date | no | eval 2023-01-20 … 2026-09-04 (61 distinct); sample 2019-09-03 … 2026-07-07 |
| `request_type` | enum | no | 9 values, ~28 each |
| `requested_amount` | float | no | 199.89 … 83,923,000 |
| `desired_completion_date` | date | no | eval 2023-02-13 … 2026-10-19 |
| `allows_partial_payment` | bool-str | no | literal lowercase `true` / `false` (eval 80/170) |
| `request_text` | str | no | quoted, free text, contains the amount and deadline in prose |

### request_payment_options.csv (790 rows)

| column | type | nullable | notes |
|---|---|---|---|
| `payment_option_id` | str | no | `payment_option_01`…; PK; monotonically increasing within a request |
| `request_id` | str | no | every request (sample+eval) has 2–4 options; exactly one `full_payment` option each |
| `payment_method` | enum | no | installments 515, full_payment 275 |
| `payment_amount` | float | no | per-payment amount; × `number_of_payments` == `total_payable_amount` (0 mismatches > 0.05) |
| `number_of_payments` | int | no | 1 (full), 2, 3, 4, 6, 15, 18, 21, 24 |
| `first_payment_date` | date | no | full_payment: always == request_date; installments: request_date + {0,1,3,5,6,7,14} days |
| `payment_frequency_days` | int | **yes** (blank for full_payment) | 28 / 30 / 31 |
| `financing_fee` | float | no | 0 for full_payment; installments total == requested_amount + fee (515/515) |
| `total_payable_amount` | float | no | full_payment == requested_amount (275/275) |

### messages.csv (215 rows)

| column | type | nullable | notes |
|---|---|---|---|
| `message_id` | str | no | PK |
| `user_id` | str | no | 215 distinct users — at most one message per user |
| `request_id` | str | **yes** (128 non-blank) | FK → requests/sample |
| `related_event_id` | str | **yes** (39 non-blank) | FK → events; 28 rows have both request_id and related_event_id; 76 rows have neither |
| `sent_at` | ISO datetime | no | 2019-08-31T09:30:00Z … 2026-09-03T01:00:00Z |
| `source_type` | enum | no | employer 126, service_provider 31, financial_service 23, bank 18, merchant 17 |
| `message_text` | str | no | English 170, Indonesian 45 (heuristic) |

### images.csv (16 rows)

| column | type | nullable | notes |
|---|---|---|---|
| `image_id` | str | no | `image_01`…`image_16`; file exists for every one |
| `user_id` | str | no | populated on all 16 |
| `request_id` | str | no | populated on all 16 |
| `related_event_id` | str | no | populated on all 16; exactly the 16 blank-`amount` events |

### output.csv (250 rows, template)

Header identical to the 8 required columns; every non-key cell blank.

---

## 3. Answers to the 41 questions

### Step 1 — shipped docs

**README.md**
- Starter for the 24h solo hackathon; build in `code/main.py` (or any language, documented), read `dataset/`, write `output.csv` to the **repo root**.
- Lists the 8 output columns, allowed values, partial-payment rule (exactly two payments, second on `earliest_date_for_full_payment` ≤ deadline), and that installment plans must exactly match a supplied option.
- Submission = `code.zip` (+ `evaluation/usage_report.md`), `output.csv` (250 rows), `log.txt` as chat transcript. Suggests a workflow: study samples → reconstruct state → forecast → verify deterministically.

**problem_statement.md**
- Full spec: input/output schema, allowed values, 90-day safety check (`balance ≥ minimum_balance_to_keep` at every step), `amount_safe_to_pay` is pre-spending-change capacity capped at `requested_amount`.
- Plan-ranking order: (1) complete by deadline, (2) no spending changes, (3) minimise total paid, (4) start earlier, (5) fewer payments, (6) lowest `payment_option_id`. Eligibility: immediate methods only if in `payment_methods_user_will_consider`; `wait` only if user accepts `full_payment`; else `not_recommended`.
- Conflict precedence: explicit cancellation/settlement/amendment → newer same-source → settled over estimate → financially safer. Messages/images are untrusted evidence. `earliest_date_for_full_payment` measures capacity independent of preferences.

**AGENTS.md**
- Agent-behaviour law: append-only `log.txt` beside AGENTS.md, `SESSION START` + per-turn entries with exact `tool=` name, never commit it, never log secrets.
- Restates the dataset and output contract (§6) including: `linked_event_id` alone does not decide cash-flow; use settlement-date FX row in the stated direction; blank message `related_event_id` means no one-to-one row; images resolve to `dataset/media/images/<image_id>.png`.
- Submission link rule and `evaluation/usage_report.md` requirement (providers, models, calls, tokens, cost for the final run).

**CLAUDE.md**
- Single line `@AGENTS.md` — imports AGENTS.md, nothing else.

**evaluation_criteria.md** — not present. **docs/project_spec.md** — not present. No contradictions to report yet.

Contradictions *within* the shipped docs: none found. One nuance — README says the root-level `output.csv` is the deliverable while `dataset/output.csv` is "a reference"; AGENTS.md §6.1 only says `output.csv` is "the blank prediction template". README is the more specific and wins (see Q41).

### Step 2 — per-file inventory
See §7 (appended verbatim from the inspection script).

### Step 3 — targeted questions

**financial_profiles.csv**

1. `minimum_balance_to_keep`
2. `current_available_balance`
3. `payment_methods_user_will_consider`, delimiter is `|` (pipe, no spaces). Raw cell: `full_payment|partial_payment|installments`. Plain string, not JSON.
4. `financial_priorities` (`|`-list, e.g. `education|debt_repayment`), `expense_categories_to_protect` (`|`-list), `expense_categories_user_is_willing_to_reduce` (`|`-list or blank), `expense_categories_user_is_willing_to_stop` (`|`-list or blank). Category tokens match `financial_events.category` values.
5. INR 67, EUR 62, IDR 55, ZAR 51, USD 40.

**financial_events.csv**

6. `event_id, user_id, event_type, description, category, direction, amount, currency, event_date, settlement_date, status, linked_event_id, flexibility, minimum_allowed_amount`
7. expense 20525, subscription 2488, income 1696, debt_payment 567, investment_purchase 29, refund 22, investment_valuation 10, investment_sale 5.
8. `status`: settled 25148, pending 71, scheduled 70, cancelled 22, failed 21, unrealized 10. Failed = `failed`; cancelled = `cancelled`; pending = `pending`; settled = `settled`. `scheduled` = confirmed future (salary, school fee, insurance, utility debit, retry); `unrealized` = non-cash valuation.
9. **There is no cadence/interval/frequency column.** Recurrence is only inferable from repeated `(category, description)` rows at ~monthly spacing with identical or similar amounts. Raw recurring rows:
   ```
   event_05,user_01,subscription,Music service subscription,music_subscription,debit,235.4,ZAR,2023-10-11,2023-10-11,settled,,fixed,
   event_11,user_01,subscription,Music service subscription,music_subscription,debit,235.4,ZAR,2023-11-11,2023-11-11,settled,,fixed,
   ```
   Also `Apartment rent transfer` appears 6× for user_01 on the 2nd of each month; groceries/transport/dining are variable-amount recurring under several rotating descriptions.
10. Yes: `flexibility` ∈ {`fixed`, `reducible`, `stoppable`, `reducible_or_stoppable`}, plus `minimum_allowed_amount` (populated on all 2,907 reducible / reducible_or_stoppable rows, blank otherwise). So `spending_changes_needed` is computable. Flexibility is set per-row, so the same subscription is flexible on every occurrence.
11. **16** rows: `event_253, event_1442, event_1545, event_1700, event_1786, event_3051, event_3231, event_4535, event_5170, event_6033, event_6859, event_7307, event_7941, event_9421, event_9806, event_10521`.
12. 58 rows have `linked_event_id`. Longest chain = 1 (child → parent, never deeper). **No parent has ≥2 children.** No dangling links. The row carrying `linked_event_id` is always the *later* row; parent (earlier) → child (later) pairs:
    - expense.settled → refund.settled ×14 (card-charge reversals, employer expense reimbursements)
    - investment_purchase.settled → investment_valuation.unrealized ×10
    - expense.cancelled (card authorization) → expense.settled (the real purchase) ×8
    - expense.settled → refund.pending ×8 (refund not yet credited)
    - debt_payment.failed → debt_payment.scheduled ×7 (retry of a failed bill debit)
    - expense.settled → expense.pending ×6 (`Possible duplicate card charge`)
    - investment_purchase.settled → investment_sale.settled ×5
    Raw example: child `event_99,user_01,refund,Settled card charge reversal,shopping,credit,583,ZAR,2024-01-28,2024-01-29,settled,event_98,fixed,` → parent `event_98,user_01,expense,Card charge later reversed,shopping,debit,583,ZAR,2024-01-25,2024-01-26,settled,,fixed,`.
13. **140** rows: USD→INR-user 54, USD→IDR-user 28, USD→EUR-user 22, EUR→ZAR-user 20, EUR→USD-user 16. Breakdown: income.settled 131, income.scheduled 8, expense.settled 1 (`event_7307`, the blank-amount USD taxi fare for INR user_78). 27 users affected.
14. **Event row only.** 47 users have exactly one `income` row with `status=scheduled` and `description=Next confirmed salary`. No profile column. The other 228 users have no scheduled salary row — their future salary must be inferred from settled history (and messages).
15. `direction=non_cash` + `event_type=investment_valuation` + `status=unrealized` + blank `settlement_date`, always linked to an `investment_purchase`. 10 rows. `investment_purchase` (debit, settled) and `investment_sale` (credit, settled) are real cash.

**requests.csv / sample_requests.csv**

16. Confirmed: 250 and 25.
17. Lowercase literal `true` / `false`.
18. Eval: min `2023-01-20`, max `2026-09-04`, **61 distinct dates — not the same date**. 211 of 275 requests are dated after the user's last event; 64 are on/before it.
19. Sample distribution:
    - `affordability_status`: affordable_with_plan 9, not_affordable 7, affordable_later 6, affordable_now 3.
    - `recommended_payment_method`: not_recommended 7, full_payment 6, wait 6, installments 5, partial_payment 1.
    - `spending_changes_needed` ≠ none: **3** — `stop:event_476` (request_06), `reduce_to:event_989:665950` (request_11), `stop:event_1815|reduce_to:event_1816:23.50` (request_21).
    - `earliest_date_for_full_payment` empty: 7 (request_05, 10, 14, 15, 20, 24, 25 — all `not_affordable`).
    - `payment_plan` = none: the same 7.
    - Status×method pairs: (not_affordable, not_recommended) 7; (affordable_later, wait) 6; (affordable_with_plan, installments) 5; (affordable_now, full_payment) 3; (affordable_with_plan, full_payment) 3 [with spending changes]; (affordable_with_plan, partial_payment) 1.
20. Verbatim:
    - `Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available over the next 90 days.`
    - `Use 3 installments of IDR 15,952,906.67, starting 8 August 2025. This leaves at least IDR 29,158,400 available.`
    - `Do not proceed with the EUR 5,414.20 request. Although EUR 597.74 is available today, the full amount cannot be completed safely within 90 days.`
    Length 16–25 words (median 20). Always two sentences, always cite currency code + thousands-grouped amount, dates written as `8 August 2025`, and the minimum balance figure. Templates per outcome: "Pay X today…", "Use N installments of X, starting D…", "Pay X in full on D. Paying earlier would take the balance below the Y minimum.", "Wait until D, then pay X in full…", "Do not make this payment by D. None of the available options keeps the Y minimum protected.", "Stop/Reduce the <desc>, then pay X today…", "Pay X today and the remaining Y on D. This completes the full request and keeps the Z minimum protected."
21. Yes — all 13 `wait`/`not_recommended` rows have non-zero `amount_safe_to_pay`; no sample has `amount_safe_to_pay = 0`. E.g. `request_03,…,873000,affordable_later,wait,2019-11-15:5491000,2019-11-15,none` and `request_05,…,737,not_affordable,not_recommended,none,,none`. Also `request_12`: `amount_safe_to_pay == requested_amount == 65164` yet status is `affordable_with_plan`/`installments` because the user accepts only `partial_payment|installments` — capacity and recommendation are independent.

**request_payment_options.csv**

22. `payment_option_id, request_id, payment_method, payment_amount, number_of_payments, first_payment_date, payment_frequency_days, financing_fee, total_payable_amount`
23. first-payment date = `first_payment_date`; days between = `payment_frequency_days`; count = `number_of_payments`; fee = `financing_fee`; total = `total_payable_amount`.
24. 4 (30 requests); 3 (180); 2 (65). Every request has options.
25. Per-payment amount **is given** (`payment_amount`) and equals `total_payable_amount / number_of_payments` (0 mismatches > 0.05). Raw: `payment_option_02,request_01,installments,1852.11,15,2024-03-06,30,2525.65,27781.65`.
26. Yes. All 275 `full_payment` options start on `request_date`. Of 515 installment options, 409 start after `request_date` (offsets: +3d 156, +14d 144, +7d 104, +1/5/6d 5) and 106 start on it. **434/515 installment options finish after `desired_completion_date`** — only 81 complete by deadline (all 5 sample installment picks are among those 81, and every one is the 3-payment option).

**exchange_rates.csv**

27. `rate_date, from_currency, to_currency, rate`. **Directional** (`from_currency`, `to_currency`). Only 5 directed pairs exist: USD→INR, USD→IDR, USD→EUR, EUR→USD, EUR→ZAR. Rates are constant over time per pair.
28. **Yes, complete.** All 140 foreign-currency event rows have an exact `(settlement_date, from=currency, to=home_currency)` row. No missing combinations. (The single non-15th row, `2025-10-01,USD,INR,83.33`, exists precisely for `event_7307`.) No reverse-direction lookup is needed.

**messages.csv**

29. `message_id, user_id, request_id, related_event_id, sent_at, source_type, message_text`
30. with `related_event_id`: 39; with `request_id`: 128; with only `user_id` (neither): 76; both: 28. Every user has ≤1 message (215 distinct users). No dangling FK.
31. English ≈170, Indonesian (Bahasa) ≈45 (keyword heuristic; no other scripts/languages detected).
32. Amend / cancel / delay examples:
    - `message_05` (delay): "BrightPath Media has updated your payroll record. Your confirmed salary is now expected on 2024-09-23. This replaces the payroll date shown in the earlier update. …"
    - `message_30` (income ended): "… One household employment record has ended. The remaining confirmed monthly salary is INR 148000. Any income that has ended should be removed from future estimates. …"
    - `message_51` (amend expense): "… The renewed lease increases monthly rent by 12%. The new amount applies from the next rent payment. …"
    Semantic families found (approx. counts): first salary at new job 27, income ended 17, invoice approved (freelance) 15, salary increase 13, refund pending 13, prize/lottery 12 (some pending, some settled), temporary reduced pay 10, unpaid-leave reduction 10, one-time arrears 9, gig payout pending 9, bonus unconfirmed 8, salary resumes + new childcare 8, rent increase 7, foreign-salary FX note 7, salary date moved 6, card dispute open 6, failed debit will retry 4, foreign charge FX 2, commission pending 8, inter-account transfer (not income/expense) 7, two card minimums due 2, investment sale settled 3, expense reimbursement (not salary) 3, investment value fallen 3, receipt confirmations for image events 3.
33. See §4. **No overt injection found**: no "ignore", "system:", role markers, JSON, or instructions addressed to the model. Only soft imperatives phrased as business advice.

**images.csv**

34. `image_id, user_id, request_id, related_event_id`
35. All 16 rows populate all three of `related_event_id`, `request_id`, `user_id`.
36. All 16 files exist at `dataset/media/images/image_NN.png`; no extras, none missing.
37. Every one of the 16 blank-amount events has exactly one linked image and vice-versa. **No blank amount without an image** — precedence rule 4 fallback is not needed for amounts. 15 of the 16 image-linked users are INR home-currency; `image_01` is IDR. `event_7307` (image_12) is a **USD** expense for an INR user → amount from image must then be converted with `2025-10-01,USD,INR,83.33`.
38. Opened four:
    - `image_01.png` (1628×1366) — Indonesian HR payslip "PAY SLIP Aug-2019", clean printed render, English labels, `IDR` currency code printed on every line, Western grouping `4,365,000`. Contains **many** amounts (salary 4,500,000; subtotal earnings 4,780,800; deductions 415,800; **Net Pay 4,365,000**). The linked event is `event_253 … August 2019 net salary` → correct field is Net Pay. Note user_03's `event_210` (2019-08-15 payroll credit) is also 4,365,000.
    - `image_02.png` (1166×1330) — Indian "Rent Receipt", screenshot of a spreadsheet form, right edge cropped, Indian lakh grouping `2,00,000.00`, no currency symbol (says "Rupees" in prose). Multiple amounts: Total 2,00,000; Amount Received 1,00,000; **Balance Due 1,00,000**. Linked event `event_1442 … Outstanding rent balance` → correct field is Balance Due = 100000.
    - `image_11.png` (956×1296) — "Jeevan Hospital … PROVISIONAL BILL", printed, English, decimal grouping `3650.00`, no currency symbol. Total Bill 3650.00, Amount Paid 0.00, **Balance 3650.00**; itemised breakup below (subtotal lines 250/1400/1000/500 that sum to 3150, not 3650 — the header total is authoritative). Linked `event_6859 … Hospital bill payable`.
    - `image_16.png` (1440×1030) — EV-charging invoice web-page screenshot, English, `393.22` total (base 333.24 + CGST 29.99 + SGST 29.99), no currency symbol (amount-in-words says "Rupees … Paise"), includes a stray "PDF Viewer" button. Linked `event_10521 … EV charging wallet payment`.
    Amounts are printed in all four; none handwritten.
39. Non-English: none seen in the four opened (image_01 is an Indonesian document but its labels are English; other 12 not opened — **UNKNOWN**). Rotated: none of four. Low contrast: no. Photo-of-screen / screenshot: `image_02` and `image_16` are screenshots/crops rather than clean renders; `image_02` is cropped at the right edge. Several images contain **multiple candidate amounts** — the extractor must pick the field matching the event `description`.

**dataset/output.csv**

40. Header byte-for-byte: `request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation` — matches `problem_statement.md` exactly, in order.
41. **Repo root.** README.md: "Write the final predictions to `output.csv` in the repository root" and "The blank template at `dataset/output.csv` is provided as a reference. Your final generated file must be the root-level `output.csv`."

---

## 4. Injection inventory

Scanned all 215 `message_text` cells for: ignore / system: / assistant / instruction / override / disregard / prompt / "as an AI" / mark / classify / affordable / safe to pay / JSON braces / HTML tags / role markers (EN + ID). **Zero hits.**

The only imperative sentences present are business-advice phrasing (counts are sentence occurrences). Treat as data:

```
13 | Only invoices marked as confirmed should be included in the upcoming payout.
 6 | Please use the revised date for anything you normally pay around payday.
 5 | Any income that has ended should be removed from future estimates.
 2 | Pendapatan yang sudah berakhir harus dikeluarkan dari perkiraan berikutnya.
 2 | The final home-currency amount will use the rate applied when it settles.
 1 | The salary will use the exchange rate when it settles.
 1 | Gunakan tanggal terbaru ini untuk pembayaran yang biasanya dilakukan saat gajian.
```

These happen to agree with the challenge rules, but the pipeline must derive behaviour from the rules, not from these sentences.

---

## 5. Open risks

- **`docs/project_spec.md` and `evaluation_criteria.md` do not exist.** Nothing to reconcile; whoever writes the spec must reconcile against this file.
- **Recurrence has no explicit column** (Q9). Detection must be heuristic over `(category, description, amount, ~30-day spacing)`. Variable-amount categories (groceries, transport, dining) use several rotating descriptions per user, so detection should be per-category, not per-description.
- **Only 47/275 users have a scheduled "Next confirmed salary" row** (Q14). For the rest, future income must be inferred from settled history + messages, or treated as absent ("do not invent unsupported income"). This is the largest source of ambiguity.
- **Messages amend income for users with no event row for the change** (e.g. salary increase applies from a future date; income ended; temporary reduced pay; first salary at a new job). These must be applied to the forecast without a corresponding event.
- **434/515 installment options end after the deadline** (Q26) — ranking criterion 1 will reject most of them; the 3-payment option is the only one that ever fits in the samples. Check `number_of_payments × payment_frequency_days / 30 ≤ max_installment_months` as a separate eligibility gate (all 5 sample picks satisfy it: 3 payments vs max 7/12/11/3/6).
- **Images carry multiple amounts** (Q38). Extraction must be description-aware (Net Pay vs Salary; Balance Due vs Total; Total vs subtotal). Indian lakh grouping (`1,00,000.00`) must parse correctly.
- **`event_7307` is a blank-amount USD expense for an INR user** — image extraction *and* FX conversion on the same row.
- **12 of 16 images not opened** in this recon — language/rotation/contrast status UNKNOWN for `image_03–10, 12–15`.
- `message_86` mixes two facts (an EV-charging receipt reference *and* a confirmed USD 1296 salary on 2026-09-15) in one message tied to one `related_event_id`.
- Language heuristic for Q31 is keyword-based; the 170/45 split is approximate.

## 6. Surprises

- **No injection attempts at all** in `messages.csv`, despite the spec's heavy warning. Expect them in the hidden/organizer data or treat the warning as defensive only.
- **Exchange rates are constant per pair over time** (USD→INR always 83.33, etc.). The "use the settlement-date row" rule is a lookup-discipline test, not a numerical one — except the lone `2025-10-01` row that exists for a single event.
- **`amount_safe_to_pay` is never 0 in the samples**, and `request_12` has `amount_safe_to_pay == requested_amount` yet is `affordable_with_plan` / `installments` — user preference alone changed the status.
- **Every request has exactly one `full_payment` option** with `payment_amount == requested_amount` on `request_date`; the option table is redundant for full payment but authoritative for installments.
- **Each user has at most one message and one request**; `request_NN` ↔ `user_NN` numbering is 1:1. Messages tied to a `request_id` are therefore also per-user.
- **`linked_event_id` never chains** (depth 1, no fan-out), and duplicate charges are represented as a `pending` row with `description=Possible duplicate card charge` linking to the original — not as two identical rows (zero exact duplicates by (user, amount, date, description)).
- **Installment first payments are offset from request_date** by 0/3/7/14 days — so "start earlier" (ranking rule 4) can differentiate installment options from each other, and from full payment (always day 0).
- The hospital bill image's itemised subtotals (3150) do not sum to its printed total (3650) — a trap for extractors that recompute instead of reading the total.

---

## 7. Step-2 inventory (verbatim script output)

# STEP 2 — PER-FILE INVENTORY


## financial_profiles.csv

- header (exact): `['user_id', 'home_currency', 'current_available_balance', 'minimum_balance_to_keep', 'financial_priorities', 'expense_categories_to_protect', 'expense_categories_user_is_willing_to_reduce', 'expense_categories_user_is_willing_to_stop', 'payment_methods_user_will_consider', 'max_installment_months']`
- raw header bytes: `b'user_id,home_currency,current_available_balance,minimum_balance_to_keep,financial_priorities,expense_categories_to_protect,expense_categories_user_is_willing_to_reduce,expense_categories_user_is_willing_to_stop,payment_methods_user_will_consider,max_installment_months'`
- row count (excluding header): **275**
- representative rows (verbatim):
```
user_01,ZAR,58481.1,18000,education|debt_repayment,rent|education|groceries|debt_repayment,dining,delivery_membership,full_payment,
user_02,IDR,60383889.2,29158400,education|family_support,housing|utilities|education,entertainment,cloud_storage,partial_payment|installments,7
```
- `home_currency` distinct (5): `INR`=67, `EUR`=62, `IDR`=55, `ZAR`=51, `USD`=40
- `current_available_balance` NUMERIC min=683.69 max=136691818.94 blank=0
- `minimum_balance_to_keep` NUMERIC min=400.0 max=41430800.0 blank=0
- `financial_priorities` distinct (9): `emergency_savings|travel`=46, `retirement_investment|emergency_savings`=42, `education|debt_repayment`=36, `education|emergency_savings`=34, `emergency_savings|housing`=29, `healthcare|family_support`=25, `education|family_support`=24, `debt_repayment|emergency_savings`=20, `healthcare|retirement_investment`=19
- `expense_categories_to_protect` distinct (8): `rent|groceries|transport`=63, `rent|insurance|transport`=46, `rent|utilities|groceries`=42, `rent|education|groceries|debt_repayment`=36, `rent|healthcare|family_support|groceries`=25, `housing|utilities|education`=24, `rent|utilities|debt_repayment`=20, `housing|healthcare|utilities`=19
- `expense_categories_user_is_willing_to_stop` distinct (11): `<blank>`=62, `cloud_storage`=57, `streaming|cloud_storage`=52, `streaming`=32, `music_subscription`=26, `music_subscription|delivery_membership`=24, `delivery_membership`=10, `gym|music_subscription`=4, `gym|music_subscription|delivery_membership`=4, `gym|delivery_membership`=3, `gym`=1
- `payment_methods_user_will_consider` distinct (7): `full_payment`=60, `partial_payment|installments`=52, `installments`=41, `full_payment|partial_payment`=40, `full_payment|installments`=35, `full_payment|partial_payment|installments`=28, `partial_payment`=19
- `max_installment_months` distinct (12): `<blank>`=119, `3`=18, `4`=17, `12`=16, `11`=16, `5`=16, `2`=15, `7`=14, `6`=13, `10`=12, `8`=10, `9`=9
- `max_installment_months` NUMERIC min=2.0 max=12.0 blank=119

## financial_events.csv

- header (exact): `['event_id', 'user_id', 'event_type', 'description', 'category', 'direction', 'amount', 'currency', 'event_date', 'settlement_date', 'status', 'linked_event_id', 'flexibility', 'minimum_allowed_amount']`
- raw header bytes: `b'event_id,user_id,event_type,description,category,direction,amount,currency,event_date,settlement_date,status,linked_event_id,flexibility,minimum_allowed_amount'`
- row count (excluding header): **25342**
- representative rows (verbatim):
```
event_01,user_01,expense,Apartment rent transfer,rent,debit,5148,ZAR,2023-10-02,2023-10-02,settled,,fixed,
event_02,user_01,expense,Household utility payment,utilities,debit,1475.46,ZAR,2023-10-06,2023-10-06,settled,,fixed,
```
- `event_type` distinct (8): `expense`=20525, `subscription`=2488, `income`=1696, `debt_payment`=567, `investment_purchase`=29, `refund`=22, `investment_valuation`=10, `investment_sale`=5
- `direction` distinct (3): `debit`=23609, `credit`=1723, `non_cash`=10
- `amount` NUMERIC min=2.0 max=48830000.0 blank=16
- `currency` distinct (5): `INR`=6457, `EUR`=5585, `IDR`=4992, `ZAR`=4489, `USD`=3819
- `event_date` DATE min=`2019-03-09` max=`2026-09-03` blank=0
- `settlement_date` DATE min=`2019-03-09` max=`2026-09-03` blank=10
- `status` distinct (6): `settled`=25148, `pending`=71, `scheduled`=70, `cancelled`=22, `failed`=21, `unrealized`=10
- `flexibility` distinct (4): `fixed`=21138, `reducible`=2682, `stoppable`=1297, `reducible_or_stoppable`=225
- `minimum_allowed_amount` NUMERIC min=8.0 max=810350.0 blank=22435

## exchange_rates.csv

- header (exact): `['rate_date', 'from_currency', 'to_currency', 'rate']`
- raw header bytes: `b'rate_date,from_currency,to_currency,rate'`
- row count (excluding header): **134**
- representative rows (verbatim):
```
2023-10-15,EUR,ZAR,20
2023-10-15,USD,EUR,0.92
```
- `rate_date` DATE min=`2023-10-15` max=`2026-11-15` blank=0
- `from_currency` distinct (2): `USD`=88, `EUR`=46
- `to_currency` distinct (5): `INR`=33, `IDR`=30, `EUR`=25, `USD`=24, `ZAR`=22
- `rate` distinct (5): `83.33`=33, `15833.33`=30, `0.92`=25, `1.09`=24, `20`=22
- `rate` NUMERIC min=0.92 max=15833.33 blank=0

## requests.csv

- header (exact): `['request_id', 'user_id', 'request_date', 'request_type', 'requested_amount', 'desired_completion_date', 'allows_partial_payment', 'request_text']`
- raw header bytes: `b'request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text'`
- row count (excluding header): **250**
- representative rows (verbatim):
```
request_26,user_26,2025-08-03,family_transfer,15656000,2025-10-07,false,"I've been asked to transfer IDR 15,656,000 to my family. I need to complete it by 7 October 2025. Should I send the full amount, send part of it, or wait?"
request_27,user_27,2026-07-05,purchase,6670,2026-08-21,true,"Can I make this purchase without dipping into the balance I want to keep? I need to decide by 21 August 2026. The laptop costs ZAR 6,670."
```
- `request_date` DATE min=`2023-01-20` max=`2026-09-04` blank=0
- `request_type` distinct (9): `family_transfer`=28, `purchase`=28, `investment`=28, `debt_repayment`=28, `travel`=28, `housing`=28, `education`=28, `emergency_expense`=27, `other`=27
- `requested_amount` NUMERIC min=199.89 max=83923000.0 blank=0
- `desired_completion_date` DATE min=`2023-02-13` max=`2026-10-19` blank=0
- `allows_partial_payment` distinct (2): `false`=170, `true`=80

## sample_requests.csv

- header (exact): `['request_id', 'user_id', 'request_date', 'request_type', 'requested_amount', 'desired_completion_date', 'allows_partial_payment', 'request_text', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method', 'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed', 'decision_explanation']`
- raw header bytes: `b'request_id,user_id,request_date,request_type,requested_amount,desired_completion_date,allows_partial_payment,request_text,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation'`
- row count (excluding header): **25**
- representative rows (verbatim):
```
request_01,user_01,2024-03-03,purchase,25256,2024-03-20,true,"Would paying for the laptop today leave enough for my regular expenses? The laptop I'm looking at is ZAR 25,256.",25256,affordable_now,full_payment,2024-03-03:25256,2024-03-03,none,"Pay ZAR 25,256 today. This leaves at least ZAR 18,000 available over the next 90 days."
request_02,user_02,2025-08-05,travel,46018000,2025-10-10,false,"The current quote for the trip is IDR 46,018,000. I need to complete it by 10 October 2025. Can I afford the full trip without putting upcoming bills at risk?",17229139.2,affordable_with_plan,installments,2025-08-08:15952906.67|2025-09-07:15952906.67|2025-10-07:15952906.67,2025-09-15,none,"Use 3 installments of IDR 15,952,906.67, starting 8 August 2025. This leaves at least IDR 29,158,400 available."
```
- `request_date` DATE min=`2019-09-03` max=`2026-07-07` blank=0
- `request_type` distinct (9): `purchase`=3, `travel`=3, `education`=3, `family_transfer`=3, `debt_repayment`=3, `investment`=3, `housing`=3, `emergency_expense`=2, `other`=2
- `requested_amount` NUMERIC min=166.61 max=60496000.0 blank=0
- `desired_completion_date` DATE min=`2019-11-15` max=`2026-09-15` blank=0
- `allows_partial_payment` distinct (2): `false`=13, `true`=12
- `amount_safe_to_pay` NUMERIC min=83.05 max=17229139.2 blank=0
- `affordability_status` distinct (4): `affordable_with_plan`=9, `not_affordable`=7, `affordable_later`=6, `affordable_now`=3
- `recommended_payment_method` distinct (5): `not_recommended`=7, `full_payment`=6, `wait`=6, `installments`=5, `partial_payment`=1
- `earliest_date_for_full_payment` DATE min=`2019-11-15` max=`2026-09-15` blank=7
- `spending_changes_needed` distinct (4): `none`=22, `stop:event_476`=1, `reduce_to:event_989:665950`=1, `stop:event_1815|reduce_to:event_1816:23.50`=1

## request_payment_options.csv

- header (exact): `['payment_option_id', 'request_id', 'payment_method', 'payment_amount', 'number_of_payments', 'first_payment_date', 'payment_frequency_days', 'financing_fee', 'total_payable_amount']`
- raw header bytes: `b'payment_option_id,request_id,payment_method,payment_amount,number_of_payments,first_payment_date,payment_frequency_days,financing_fee,total_payable_amount'`
- row count (excluding header): **790**
- representative rows (verbatim):
```
payment_option_01,request_01,full_payment,25256,1,2024-03-03,,0,25256
payment_option_02,request_01,installments,1852.11,15,2024-03-06,30,2525.65,27781.65
```
- `payment_method` distinct (2): `installments`=515, `full_payment`=275
- `payment_amount` NUMERIC min=7.29 max=83923000.0 blank=0
- `number_of_payments` distinct (9): `1`=275, `24`=96, `15`=89, `21`=88, `18`=87, `3`=80, `6`=65, `2`=7, `4`=3
- `number_of_payments` NUMERIC min=1.0 max=24.0 blank=0
- `first_payment_date` DATE min=`2019-09-03` max=`2026-09-04` blank=0
- `payment_frequency_days` distinct (4): `<blank>`=275, `28`=180, `31`=169, `30`=166
- `payment_frequency_days` NUMERIC min=28.0 max=31.0 blank=275
- `financing_fee` NUMERIC min=0.0 max=18463059.92 blank=0
- `total_payable_amount` NUMERIC min=166.61 max=102386059.92 blank=0

## messages.csv

- header (exact): `['message_id', 'user_id', 'request_id', 'related_event_id', 'sent_at', 'source_type', 'message_text']`
- raw header bytes: `b'message_id,user_id,request_id,related_event_id,sent_at,source_type,message_text'`
- row count (excluding header): **215**
- representative rows (verbatim):
```
message_01,user_02,,,2025-07-29T09:30:00Z,employer,Rincian penggajian Anda di Cobalt Systems telah berubah. Gaji bulanan Anda naik menjadi IDR 42750000. Perubahan ini berlaku mulai 2025-08-15. Jumlah yang diperbarui akan terlihat pada slip gaji berikutnya. Ref payroll EMP-0001.
message_02,user_03,request_03,,2019-08-31T09:30:00Z,employer,Tim payroll BrightPath Media telah mengirim pembaruan. Gaji rutin untuk penggajian berikutnya sudah dikonfirmasi. Slip gaji berikutnya akan menampilkan gaji rutin dan penyesuaian satu kali secara terpisah. Ref payroll EMP-0002.
```
- `sent_at` DATE min=`2019-08-31T09:30:00Z` max=`2026-09-03T01:00:00Z` blank=0
- `source_type` distinct (5): `employer`=126, `service_provider`=31, `financial_service`=23, `bank`=18, `merchant`=17

## images.csv

- header (exact): `['image_id', 'user_id', 'request_id', 'related_event_id']`
- raw header bytes: `b'image_id,user_id,request_id,related_event_id'`
- row count (excluding header): **16**
- representative rows (verbatim):
```
image_01,user_03,request_03,event_253
image_02,user_16,request_16,event_1442
```

## output.csv

- header (exact): `['request_id', 'amount_safe_to_pay', 'affordability_status', 'recommended_payment_method', 'payment_plan', 'earliest_date_for_full_payment', 'spending_changes_needed', 'decision_explanation']`
- raw header bytes: `b'request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation'`
- row count (excluding header): **250**
- representative rows (verbatim):
```
request_26,,,,,,,
request_27,,,,,,,
```
- `amount_safe_to_pay` distinct (1): `<blank>`=250
- `affordability_status` distinct (1): `<blank>`=250
- `recommended_payment_method` distinct (1): `<blank>`=250
- `payment_plan` distinct (1): `<blank>`=250
- `earliest_date_for_full_payment` distinct (1): `<blank>`=250
- `spending_changes_needed` distinct (1): `<blank>`=250
- `decision_explanation` distinct (1): `<blank>`=250