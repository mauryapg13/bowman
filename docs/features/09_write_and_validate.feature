Feature: Validation and atomic write (code/write.py, MVP M8)
  Assert invariants I1-I13, then write atomically. Source: project_spec.md §2.

  Scenario Outline: Invariants
    Given a candidate output row
    Then invariant <id> holds: <rule>

    Examples:
      | id  | rule                                                                                              |
      | I1  | 0 <= amount_safe_to_pay <= requested_amount                                                       |
      | I2  | affordable_now implies earliest_date_for_full_payment == request_date                            |
      | I3  | partial_payment implies affordability_status == affordable_with_plan                             |
      | I4  | partial_payment implies exactly two payments summing to requested_amount on request_date and earliest_date_for_full_payment |
      | I5  | partial_payment implies allows_partial_payment, 0 < amount_safe_to_pay < requested_amount, earliest_date <= desired_completion_date |
      | I6  | installments implies dates and amounts match one supplied payment_option_id exactly              |
      | I7  | plan dates are non-decreasing                                                                     |
      | I8  | chosen method is in payment_methods_user_will_consider unless not_recommended                    |
      | I9  | every spending-change event_id has permitting flexibility and a category in the user's willing list |
      | I10 | no event_id appears in both stop: and reduce_to:                                                  |
      | I11 | at most three spending changes                                                                    |
      | I12 | header and column order match byte-for-byte                                                       |
      | I13 | not_affordable implies payment_plan == none and earliest_date_for_full_payment empty              |

  Scenario: A failed assertion protects the previous output
    Given an existing valid output.csv
    And one row that violates any invariant
    When write runs
    Then the write is aborted
    And the previous output.csv is unchanged

  Scenario: Atomic write
    When all invariants pass
    Then rows are written to a temp file, fsync'd, then atomically replaced onto the repo-root output.csv

  Scenario: Smell test
    When output.csv is written
    Then the count of rows with amount_safe_to_pay == 0 is printed
    And a large count is treated as a signal of upstream breakage (no sample has a zero)
