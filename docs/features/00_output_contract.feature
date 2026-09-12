Feature: Output contract for output.csv
  The deliverable is a root-level output.csv with eight columns in a fixed order,
  one row per row of dataset/requests.csv, in input order.
  Source: project_spec.md §2, problem_statement.md "Required output", README "Submission".

  Background:
    Given dataset/requests.csv has 250 rows with request_id request_26 .. request_275
    And the required header is
      """
      request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
      """

  Scenario: The file lands at the repository root, not in dataset/
    When the pipeline finishes
    Then a file named output.csv exists in the repository root
    And dataset/output.csv is byte-identical to its shipped template

  Scenario: Header and row count
    Then the first line of output.csv equals the required header byte-for-byte
    And output.csv has exactly 250 data rows
    And the request_id column equals dataset/requests.csv's request_id column in the same order

  Scenario Outline: Allowed categorical values
    Then every <column> value is one of <allowed>

    Examples:
      | column                     | allowed                                                                  |
      | affordability_status       | affordable_now, affordable_with_plan, affordable_later, not_affordable   |
      | recommended_payment_method | full_payment, partial_payment, installments, wait, not_recommended       |

  Scenario: Plain numbers outside the explanation
    Then amount_safe_to_pay is a plain number with no thousands grouping and no currency code
    And every amount inside payment_plan is a plain number
    And thousands grouping and currency codes appear only inside decision_explanation

  Scenario: payment_plan format
    Then payment_plan is either the literal "none"
    Or a "|"-separated list of "YYYY-MM-DD:amount" entries whose dates are non-decreasing

  Scenario: spending_changes_needed format
    Then spending_changes_needed is either the literal "none"
    Or a "|"-separated list of at most three entries each matching "stop:<event_id>" or "reduce_to:<event_id>:<amount>"
