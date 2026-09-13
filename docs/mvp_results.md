# MVP results — baseline (2026-09-13)

Zero LLM calls, zero image reads, zero message handling, no lifecycle links,
no spending changes. Everything below is the number V1 must beat.
Regenerate with `python3 code/evaluation/score.py`.

## Per-column accuracy on the 25 samples

| column | accuracy |
|---|---|
| `amount_safe_to_pay` | 16% |
| `affordability_status` | 68% |
| `recommended_payment_method` | 72% |
| `payment_plan` | 68% |
| `earliest_date_for_full_payment` | 68% |
| `spending_changes_needed` | 88% |
| `decision_explanation` | 52% |
| all three categoricals exact | 64% |

`amount_safe_to_pay`: mean abs error 200,646.35; within 0.5% on 4/25.
Mean |calibration delta| over uncapped rows: **250,285.66**.

## Calibration table

```
CALIBRATION  (expected_min = key amount_safe_to_pay + minimum_balance_to_keep)
  request        expected_min         our_min           delta   safe ours / key
  request_01 capped (lower bound)       27,610.80                   9,610.80 / 25,256.00
  request_02    46,387,539.20   47,359,323.11     +971,783.91   18,200,923.11 / 17,229,139.20
  request_03     3,541,700.00    3,641,281.91      +99,581.91   972,581.91 / 873,000.00
  request_04    39,088,400.00   41,228,918.03   +2,140,518.03   10,542,318.03 / 8,401,800.00
  request_05        13,837.00       41,568.30      +27,731.30   15,488.00 / 737.00
  request_06         1,403.30        1,317.36          -85.94   517.36 / 603.30
  request_07       180,170.56      187,960.66       +7,790.10   94,960.66 / 87,170.56
  request_08         1,084.57        1,091.12           +6.56   291.12 / 284.57
  request_09 capped (lower bound)        2,069.95                   166.61 / 166.61
  request_10       238,100.00      726,840.81     +488,740.81   266,700.00 / 12,700.00
  request_11    46,651,245.00   46,262,175.11     -389,069.89   12,121,575.11 / 12,510,645.00
  request_12 capped (lower bound)      184,006.15                   65,164.00 / 65,164.00
  request_13         1,733.40        2,438.63         +705.23   941.60 / 433.40
  request_14         2,797.74       -1,902.87       -4,700.61   0.00 / 597.74
  request_15         1,283.05       -2,110.16       -3,393.21   0.00 / 83.05
  request_16 capped (lower bound)      362,370.00                   122,500.00 / 122,500.00
  request_17       409,949.58      409,854.81          -94.77   243,754.81 / 243,849.58
  request_18         1,862.00        1,951.03          +89.03   551.03 / 462.00
  request_19       121,620.00      118,209.46       -3,410.54   25,409.46 / 28,820.00
  request_20        69,900.00       74,067.32       +4,167.32   9,567.32 / 5,400.00
  request_21         3,343.35        3,528.58         +185.23   1,574.40 / 1,543.35
  request_22           975.46          965.27          -10.19   465.27 / 475.46
  request_23        36,152.00       35,406.78         -745.22   8,406.78 / 9,152.00
  request_24        64,420.00       67,101.53       +2,681.53   16,101.53 / 13,420.00
  request_25    24,804,100.00   23,693,592.35   -1,110,507.65   314,492.35 / 1,425,000.00
  mean |delta| over uncapped rows: 250,285.66
```

Reading it: a positive delta means our 90-day minimum is *higher* than the
answer key's (we are optimistic). Rows within a few units (request_08 +6.56,
request_17 −94.77, request_22 −10.19) say the balance model is right in shape;
the large ones each have a known cause:

| rows | cause | fix stage |
|---|---|---|
| request_02 (+971k), 14, 15 (negative balance) | salary changes / first salary exist **only in messages** — user_14 and user_15 have no income history at all | V1-3 |
| request_05 (+27.7k) | income ended: last payroll row is titled "Final employer payroll"; nothing else signals it | open — no message, description text only |
| request_10 (+489k) | gig payouts; message says the next payout is pending — key drops it | V1-3 |
| request_06, 11, 21 | need spending changes to be `affordable_with_plan`; we call them `affordable_now`/`wait` | V1-4/5 |
| request_01, 09, 12 (capped, we are low) | user_01: one prorated salary + one scheduled row, no stream (N6 keeps income at zero after 15 Mar) | investigate in V1-6 |
| request_25 (−1.1M), 19 (−3.4k), 23 | small/medium pessimism; likely variable-spend medians vs the key's estimate | V1-6 |

## Decisions taken while building the MVP (all in spec §14)

- **Monthly streams recur on the anchor's day-of-month**, not anchor+30·k
  (fixed request_03/04/18/23 dates: 13 Nov → 15 Nov etc.). Cadence 28–31 = monthly.
- **Scheduled occurrences are absorbed** into their stream (47 "Next confirmed
  salary" rows) — otherwise salary is counted twice on the same day.
- **Category-level fallback** for any category whose descriptions rotate
  (user_09's fortnightly freelance income), on top of the fixed
  groceries/transport/dining set.

## Other numbers the stage asked for

- `max_installment_months` cross-tab: {('blank', 'no'): 119, ('set', 'lists_installments'): 156} — blank ⇔ user omits installments; the "blank = unavailable" reading is safe.
- Users with **zero forecast income** after detection: **28** of 275 (N6: nothing invented).
- Streams per cadence bucket (5-day bins): {5: 316, 10: 363, 15: 5, 20: 156, 25: 4, 30: 1889}
- Full run over 250 requests: status {'affordable_now': 62, 'affordable_later': 55, 'affordable_with_plan': 52, 'not_affordable': 81}; method {'full_payment': 62, 'wait': 55, 'installments': 43, 'not_recommended': 81, 'partial_payment': 9}; `amount_safe_to_pay == 0` on **25** rows (smell test — mostly zero-income users, see V1-3).
- Determinism: two CLI runs produce identical sha256 (`tests/test_plans_rank_format_write.py::test_pipeline_is_deterministic`).
- Test suite: 70 passing.
