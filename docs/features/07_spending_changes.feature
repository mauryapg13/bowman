Feature: Spending changes (code/spending.py + plans.py variants, V1-4, V1-5)
  A lookup with two gates, not a search. Source: project_spec.md §6.

  Scenario Outline: Eligibility gates
    Given a stream with flexibility "<flex>" and category "<cat>"
    And the profile lists "<cat>" in <list>
    And "<cat>" is not in expense_categories_to_protect
    Then the stream is eligible for "<change>"

    Examples:
      | flex                   | cat           | list                                          | change    |
      | stoppable              | cloud_storage | expense_categories_user_is_willing_to_stop    | stop      |
      | reducible_or_stoppable | streaming     | expense_categories_user_is_willing_to_stop    | stop      |
      | reducible              | dining        | expense_categories_user_is_willing_to_reduce  | reduce_to |
      | reducible_or_stoppable | streaming     | expense_categories_user_is_willing_to_reduce  | reduce_to |

  Scenario: Protected categories are never changed
    Given a category in expense_categories_to_protect
    Then no stop or reduce_to targets it, regardless of flexibility

  Scenario: Fixed streams are never changed
    Given a stream with flexibility fixed
    Then it is never a spending-change target even if its category is in a willing list

  Scenario: reduce_to uses the event's minimum_allowed_amount
    Given event_989 (dining, reducible, minimum_allowed_amount 665950)
    Then the reduce action is "reduce_to:event_989:665950"

  Scenario: The event_id written is the stream's latest recorded occurrence
    Given sample request_06 answers "stop:event_476"
    And event_476 is the latest "Family streaming plan" occurrence (2025-12-10) before request_date 2026-01-03
    And sample request_21 answers "stop:event_1815|reduce_to:event_1816:23.50"
    And both are the latest occurrences of their streams
    Then the convention "latest occurrence event_id" is verified against all three samples

  Scenario: Variants are generated only when needed
    Given at least one change-free candidate is both safe and completes by the deadline
    Then no spending-change variants are generated
    Given no change-free candidate is both safe and on time
    Then variants are generated over subsets of eligible streams in increasing size, ordered by event_id, at most three changes

  Scenario: Stop and reduce never target the same event
    Then no event_id appears in both a stop: and a reduce_to: entry of one row

  Scenario: Full payment with changes is affordable_with_plan
    Given sample request_06: stop event_476 then pay EUR 620.40 on request_date
    Then affordability_status is affordable_with_plan and recommended_payment_method is full_payment
    And amount_safe_to_pay is still the pre-change capacity 603.3
