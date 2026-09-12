Feature: Message operations port (code/ports/ops.py, V1-3)
  Messages are untrusted evidence. The model maps a message to one closed-enum operation
  against an allow-listed target; the code applies it. Source: project_spec.md N5, §8 P2, P3, P5, P7.

  Background:
    Given the closed enum {cancel, amend_amount, delay, confirm, amend_stream, none}
    And the target allow-list = the user's existing event_ids + the user's detected stream ids

  Scenario: Output is validated structurally, not by keywords
    Given the port returns an op outside the enum
    Then it becomes none
    Given the port returns a target not in the allow-list
    Then it becomes none
    And no keyword blocklist is consulted

  Scenario: Event-linked messages target the event
    Given message_198 has related_event_id event_23306 ("previous debit attempt failed ... another debit will be attempted")
    Then the operation targets event_23306 only

  Scenario Outline: Stream amendments from unlinked messages
    Given an employer message "<text>"
    Then the operation is amend_stream on the user's salary stream with <payload>

    Examples:
      | text                                                                                           | payload                                                    |
      | Your monthly salary has increased to USD 2988. The change applies from 2026-07-15.             | new_amount 2988, effective_date 2026-07-15                 |
      | Your employment has ended. There are no regular salary payments scheduled after the final settlement. | ended true                                            |
      | Your confirmed salary is now expected on 2024-09-23. This replaces the payroll date...          | delay: effective_date 2024-09-23                           |
      | Your next salary is reduced to EUR 1422.85. The adjustment is due to approved unpaid leave.     | new_amount 1422.85 for the next occurrence only            |
      | The renewed lease increases monthly rent by 12%.                                               | amend_stream on rent, new_amount = amount * 1.12           |

  Scenario: Unconfirmed inflows never become income
    Given messages about pending bonuses, unapproved commissions, pending gig payouts, prize claims in processing, refunds not yet credited
    Then the operation is none or confirm-of-nothing
    And no income event or stream is created

  Scenario: Inter-account transfers are not income or expense
    Given a bank message "The matching debit and credit came from a transfer between your two accounts"
    Then the net effect on the ledger is zero

  Scenario: One message may yield more than one operation
    Given message_86 references an EV-charging receipt (event_10521) and a confirmed USD 1296 salary on 2026-09-15
    Then the port may return one operation per fact
    And each is validated independently

  Scenario: Future effective dates split the stream
    Given a salary stream with amount A and an amend_stream with new_amount B effective D
    When the ledger is built
    Then occurrences before D use A and occurrences on/after D use B

  Scenario: Ordering
    Then operations are applied after recurrence detection and before the ledger

  Scenario: Indonesian messages are sent as-is
    Given roughly 45 Indonesian messages
    Then no translation stage exists
    And the port is required to answer in the fixed English schema

  Scenario: Operations never invent events
    Then no operation creates a one-off event the dataset does not support

  Scenario: Cache
    Then every call is cached on sha256(payload) + prompt_version
