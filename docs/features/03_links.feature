Feature: Lifecycle links (code/links.py, V1-1)
  58 events carry linked_event_id; depth is always 1 and there is no fan-out.
  Source: project_spec.md §4.4, dataset_notes Q12.

  Scenario Outline: Seven observed patterns resolve by lookup
    Given a child event of type "<child>" linked to a parent of type "<parent>"
    When links are resolved
    Then the handling is "<handling>"
    And the resolution records parent id, child id and pattern name

    Examples:
      | parent                       | child                           | handling                                   |
      | expense.settled              | refund.settled                  | both count; net cash effect zero           |
      | expense.settled              | refund.pending                  | expense counts; refund excluded            |
      | expense.cancelled            | expense.settled                 | cancelled excluded; settled counts         |
      | expense.settled              | expense.pending                 | duplicate charge; exclude the pending child|
      | debt_payment.failed          | debt_payment.scheduled          | failed excluded; scheduled retry counts    |
      | investment_purchase.settled  | investment_valuation.unrealized | valuation excluded                         |
      | investment_purchase.settled  | investment_sale.settled         | both count                                 |

  Scenario: The duplicate-charge pattern removes phantom outflows
    Given event_12709 "Possible duplicate card charge" (pending, EUR 134.75) links to settled event_12708
    When links are resolved
    Then event_12709 is excluded with exclusion_reason "duplicate_of:event_12708"
    And the same applies to event_14399, event_18269, event_19334, event_21582 and event_23203

  Scenario: An unknown pattern falls to the precedence ladder
    Given a linked pair whose (parent, child) type-status combination is not in the table
    When links are resolved
    Then the pair is passed to the precedence ladder in project_spec.md §4.5
    And it is never silently dropped
