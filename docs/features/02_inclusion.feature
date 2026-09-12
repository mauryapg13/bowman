Feature: Inclusion gate (code/inclusion.py, MVP M2)
  Decide which raw events are cash movements that count. Source: project_spec.md §4.3.

  Scenario Outline: Status and direction decide inclusion
    Given an event with status "<status>" and direction "<direction>"
    When the inclusion gate runs
    Then the event is <result>
    And if excluded it carries exclusion_reason "<reason>"

    Examples:
      | status     | direction | result   | reason              |
      | settled    | debit     | included |                     |
      | settled    | credit    | included |                     |
      | scheduled  | debit     | included |                     |
      | scheduled  | credit    | included |                     |
      | pending    | debit     | included |                     |
      | pending    | credit    | excluded | pending_credit      |
      | cancelled  | debit     | excluded | cancelled           |
      | failed     | debit     | excluded | failed              |
      | unrealized | non_cash  | excluded | non_cash_unrealized |

  Scenario: The pending asymmetry is deliberate
    Given the 71 pending events in the dataset
    Then the 63 pending debits are included as reserved outflows
    And the 8 pending credits (all "Pending merchant refund") are excluded

  Scenario: Dataset-level counts after the gate
    When the gate runs over all 25342 events
    Then 10 events are excluded as non_cash
    And 22 events are excluded as cancelled
    And 21 events are excluded as failed
    And 10 events are excluded as unrealized (the same 10 as non_cash)

  Scenario: Investments are cash except valuations
    Then all 29 investment_purchase events are included as debits
    And all 5 investment_sale events are included as credits
    And all 10 investment_valuation events are excluded
