Feature: Loading the nine dataset files (code/load.py, MVP M1)
  All CSVs are parsed into dataclasses using only the verified column names in
  docs/dataset_notes.md §1. Every amount is converted to the user's home currency at load.

  Scenario: Verified column names only
    Given the COL block in docs/dataset_notes.md
    Then every column accessed by load.py appears in that block
    And no column name is invented or guessed

  Scenario: Profiles parse
    When financial_profiles.csv is loaded
    Then 275 Profile records exist
    And financial_priorities, expense_categories_to_protect, expense_categories_user_is_willing_to_reduce, expense_categories_user_is_willing_to_stop and payment_methods_user_will_consider are split on "|"
    And a blank expense_categories_user_is_willing_to_stop becomes an empty list, not [""]
    And a blank max_installment_months becomes None
    And 119 profiles have max_installment_months None

  Scenario: Events parse without turning blank amounts into zero
    When financial_events.csv is loaded
    Then 25342 RawEvent records exist
    And exactly 16 records have amount None
    And no record has amount 0.0 as a result of a blank cell
    And settlement_date is None on exactly the 10 non_cash rows
    And event_date and settlement_date are datetime.date objects

  Scenario: Requests and options parse
    When requests.csv, sample_requests.csv and request_payment_options.csv are loaded
    Then 250 evaluation requests and 25 sample requests exist
    And allows_partial_payment is True only for the literal lowercase string "true"
    And 790 PaymentOption records exist
    And payment_frequency_days is None for the 275 full_payment options

  Scenario: Foreign-currency events convert at load using the settlement-date rate
    Given event_2167 is a USD 1800 income for user_25 whose home_currency is INR, settled 2023-10-15
    When it is loaded
    Then its amount is 1800 * 83.33 in INR
    And the rate row used was (2023-10-15, USD, INR)
    And 140 events are converted in total with zero FX failures

  Scenario: A missing rate is a hard error
    Given an event whose (settlement_date, currency, home_currency) has no row in exchange_rates.csv
    When it is loaded
    Then loading raises an error
    And no partial output is produced

  Scenario: Indexes exist
    Then events_by_user, options_by_request and profile_by_user are available
    And every request_id in requests.csv has between 2 and 4 options
