Feature: Recurrence detection (code/recurrence.py, MVP M3)
  There is no cadence column; streams are derived from history.
  Source: project_spec.md §4.2, dataset_notes Q9, N6.

  Background:
    Given only included events are considered
    And events are grouped per user by (direction, category, description)

  Scenario: A monthly subscription becomes a stream
    Given user_01 has "Music service subscription" on 2023-10-11, 2023-11-11, 2023-12-11, ... (5 occurrences, amount 235.4)
    When recurrence runs
    Then a Stream exists with cadence_days 30 or 31, amount 235.4, anchor = the latest occurrence
    And it carries category music_subscription, flexibility fixed and latest_event_id
    And its occurrences list holds every recorded date

  Scenario: user_01 resolves to the expected streams
    When recurrence runs for user_01
    Then distinct streams exist for "Apartment rent transfer" (rent), "Household utility payment" (utilities) and "Music service subscription"
    And each has a cadence in [25, 35] and an amount matching recorded history

  Scenario: Detection threshold
    Given a (direction, category, description) group with fewer than 3 occurrences
    Then it does not become a stream by the description-level pass

  Scenario: Category-level fallback for rotating descriptions
    Given user_11's dining events use descriptions "Bakery and snacks", "Neighbourhood restaurant", "Weekend food delivery", "Coffee shop", "Quick-service meal", "Lunch with colleagues"
    And no single description has 3 occurrences
    When the description-level pass finds nothing for category dining
    Then the fallback groups by (direction, category) alone
    And a single dining stream is produced whose latest_event_id is event_989

  Scenario: Known spec risk - user_11's dining cadence is 21 days
    Given user_11's dining occurrences are 2024-11-06, 2024-11-27, 2024-12-18, 2025-01-08, ... (every 21 days)
    And the sample answer for request_11 reduces event_989, so this stream must be detected
    When the gap band is [25, 35] days
    Then the stream is NOT detected
    And therefore the accepted gap band must be widened (or made per-category) before request_11 can be reproduced
    And this finding is recorded in docs/mvp_results.md or docs/v1_log.md

  Scenario: Everything unmatched is a one-off
    Given an included event that belongs to no stream
    Then it is emitted as a one-off at its settlement_date

  Scenario: No invented income
    Given a user with no scheduled "Next confirmed salary" row and no detected recurring credit stream
    When recurrence runs
    Then the user has zero forecast income
    And the count of such users is logged
    And no salary is synthesised from any other source
