Feature: 90-day ledger and suffix minima (code/ledger.py, MVP M4)
  forecast(streams, oneoffs, start, opening) -> balance[0..90]; then suffix_min.
  Source: project_spec.md §3, §4.1.

  Background:
    Given day 0 is request_date and the window is days 0..90 inclusive (91 elements)
    And opening balance is the profile's current_available_balance
    And the floor is minimum_balance_to_keep

  Scenario: Recorded events win over prediction on the days they cover
    Given a rent stream with recorded occurrences on day 5 and day 35 (events dated after request_date)
    And cadence 30 and anchor on day 35
    When the ledger is built
    Then rent is placed on day 5 and day 35 from the recorded occurrences
    And predicted rent is placed only on day 65 (and later within the window)
    And no day carries both a recorded and a predicted occurrence of the same stream

  Scenario: Double placement is asserted, not tolerated
    Given a stream whose predicted occurrence would land on a day already covered by a recorded occurrence
    When the ledger is built
    Then an assertion fails
    And the run aborts rather than silently halving the user's balance

  Scenario: A past anchor rolls forward by whole cadences
    Given a stream anchored 10 days before request_date with cadence 30
    When the ledger is built
    Then occurrences land on days 20, 50 and 80
    And none is skipped

  Scenario: One-offs land on their settlement day only if inside the window
    Given a scheduled one-off settling 100 days after request_date
    Then it does not appear in balance[0..90]
    Given a scheduled one-off settling 10 days after request_date
    Then it appears on day 10

  Scenario: Suffix minima
    Given balance = [100, 80, 120, 60, 90]
    When suffix_minima runs
    Then suffix_min = [60, 60, 60, 60, 90]
    And suffix_min is monotonically non-decreasing

  Scenario: Capacity definitions
    Then amount_safe_to_pay = clamp(suffix_min[0] - floor, 0, requested_amount) computed before any spending change
    And earliest_date_for_full_payment = the first day d with suffix_min[d] - requested_amount >= floor, computed without spending changes and ignoring payment_methods_user_will_consider
    And it is empty when no such day exists in 0..90

  Scenario: Ledger is cached per (user_id, request_date)
    When the same (user_id, request_date) is requested twice
    Then the second call returns the cached arrays

  Scenario: Calibration against the sample answer key
    Given sample request_03 has amount_safe_to_pay 873000 and minimum_balance_to_keep 2668700
    Then the answer key implies min(balance[0..90]) = 3541700 for user_03 on 2019-09-03
    And score.py prints our computed minimum beside that value with the delta
