Feature: Candidate plans, filters, sort and status (code/plans.py + code/rank.py, MVP M5-M6)
  Enumerate, filter, sort. Never an if/elif cascade. Source: project_spec.md §5.

  Background:
    Given the ledger arrays balance[0..90] and suffix_min[0..90] for the request's user
    And the request's payment options from request_payment_options.csv

  Scenario: Candidate families
    When candidates are enumerated
    Then there is one full_payment candidate from the request's single full_payment option
    And one installments candidate per installment option using payment_amount, number_of_payments, first_payment_date and payment_frequency_days exactly
    And one partial_payment candidate (amount_safe_to_pay on day 0, remainder on earliest_date_for_full_payment) only when invariant I5 holds
    And one wait candidate (requested_amount on earliest_date_for_full_payment) when that date exists
    And spending-change variants only per 07_spending_changes.feature

  Scenario: Each candidate carries safe, total_paid and completes_by_deadline
    Given candidate payments (day, amount)...
    Then safe is true iff balance[d] - cumulative payments up to d >= floor for every d in 0..90
    And total_paid is total_payable_amount for option-backed candidates and requested_amount otherwise
    And completes_by_deadline is true iff the last payment date <= desired_completion_date

  Scenario: Most installment options die on the deadline
    When candidates are built for all 275 requests
    Then roughly 434 of the 515 installment candidates have completes_by_deadline false

  Scenario Outline: Filter 1 - method eligibility
    Given payment_methods_user_will_consider is "<accepted>"
    Then candidate method "<method>" is <eligible>

    Examples:
      | accepted                     | method          | eligible     |
      | full_payment                 | full_payment    | eligible     |
      | full_payment                 | wait            | eligible     |
      | full_payment                 | installments    | not eligible |
      | partial_payment\|installments| wait            | not eligible |
      | partial_payment\|installments| partial_payment | eligible     |
      | installments                 | full_payment    | not eligible |
      | anything                     | not_recommended | eligible     |

  Scenario: Filter 2 - installment term gate
    Given max_installment_months is 3
    And an installment option with 3 payments every 30 days (3.0 months)
    Then the option passes the term gate
    Given an installment option with 18 payments every 31 days (18.6 months)
    Then the option fails the term gate

  Scenario: Blank max_installment_months means installments unavailable (verified)
    Given the cross-tab of financial_profiles.csv
    Then all 119 profiles with blank max_installment_months do not list installments
    And all 156 profiles listing installments have a numeric max_installment_months
    And the reading "blank = unavailable" is therefore consistent with the data

  Scenario: Filter 3 - safety
    Then every surviving candidate has safe == true

  Scenario: Sort key is a total order, lower is better
    Then survivors are sorted by
      | 1 | 0 if completes_by_deadline else 1                 |
      | 2 | number of spending changes                        |
      | 3 | total_paid                                        |
      | 4 | (first_payment_date - request_date).days          |
      | 5 | number of payments                                |
      | 6 | payment_option_id or ""                           |
    And the first survivor is chosen
    And no survivors yields not_recommended with payment_plan none

  Scenario: A change-free but pricier plan beats a cheaper plan needing changes
    Given a safe installment plan with fee and zero spending changes
    And a safe full payment requiring one spending change
    Then the installment plan ranks first

  Scenario: A cheaper wait beats a fee-bearing installment plan
    Given the user accepts full_payment and installments
    And wait completes by the deadline with total_paid = requested_amount
    And installments completes by the deadline with total_paid > requested_amount
    Then wait ranks first

  Scenario Outline: Status derivation
    Given the chosen plan is "<plan>"
    Then affordability_status is "<status>"

    Examples:
      | plan                                                     | status               |
      | full_payment on day 0 with no spending changes          | affordable_now       |
      | full_payment on day 0 with one or more spending changes | affordable_with_plan |
      | installments completing the request                     | affordable_with_plan |
      | partial_payment                                         | affordable_with_plan |
      | wait                                                    | affordable_later     |
      | not_recommended                                         | not_affordable       |

  Scenario: Capacity and recommendation are independent (sample request_12)
    Given user_12 accepts only partial_payment|installments
    And amount_safe_to_pay equals requested_amount 65164
    Then earliest_date_for_full_payment is request_date 2026-04-05
    And the recommendation is installments (payment_option_33) with status affordable_with_plan
    And not affordable_now

  Scenario: Sample reproduction targets
    Then the ranker reproduces, for the 25 sample rows:
      | request_01 | affordable_now       | full_payment    | 2024-03-03:25256                                                          |
      | request_02 | affordable_with_plan | installments    | 2025-08-08:15952906.67\|2025-09-07:15952906.67\|2025-10-07:15952906.67    |
      | request_03 | affordable_later     | wait            | 2019-11-15:5491000                                                        |
      | request_05 | not_affordable       | not_recommended | none                                                                      |
      | request_19 | affordable_with_plan | partial_payment | 2024-09-04:28820\|2024-09-15:10840                                        |
