Feature: Vision port for blank amounts (code/ports/vision.py, V1-2)
  16 events have a blank amount; each has exactly one image. The model reads a number; the code decides.
  Source: project_spec.md §8 P1, P4, P6, P7, P8; dataset_notes Q11, Q37, Q38.

  Background:
    Given the port receives image_id and the linked event's description
    And returns exactly {amount_raw, amount, currency, field_used, confidence}

  Scenario Outline: Description picks the field
    Given image "<image>" linked to event "<event>" described as "<description>"
    When the port runs
    Then field_used is "<field>" and amount is <amount>

    Examples:
      | image    | event       | description                | field       | amount   |
      | image_01 | event_253   | August 2019 net salary     | Net Pay     | 4365000  |
      | image_02 | event_1442  | Outstanding rent balance   | Balance Due | 100000   |
      | image_11 | event_6859  | Hospital bill payable      | Balance     | 3650     |
      | image_16 | event_10521 | EV charging wallet payment | Total       | 393.22   |

  Scenario: Printed total beats recomputed subtotals
    Given image_11's itemised subtotals sum to 3150 while the printed total is 3650
    Then amount is 3650
    And the port never recomputes a total from line items

  Scenario: Indian lakh grouping survives parsing
    Given amount_raw "1,00,000.00"
    Then amount is 100000.0

  Scenario: Foreign-currency image amount is converted after extraction
    Given event_7307 is a USD taxi fare for INR user_78 settled 2025-10-01
    And image_12 yields a USD amount
    Then the amount is converted with the (2025-10-01, USD, INR, 83.33) row
    And the event's currency field is USD before conversion

  Scenario: Two backends, one signature, one cache
    Given an API key is present in the environment
    Then the LLM extractor backend is used
    Given no API key is present
    Then the offline OCR backend is used
    And both return the same schema and share the same cache

  Scenario: Cache key
    Then every call is cached on sha256(payload) + prompt_version
    And bumping prompt_version is the only way to invalidate

  Scenario: No branch on event_id
    Then no code path selects an amount by matching a specific event_id, image_id, request_id or user_id
    And any reviewed transcription table lives in a data file with provenance and a regeneration script

  Scenario: Remaining images are inspected before trust
    Given image_03 to image_10 and image_12 to image_15 were not opened during recon
    Then each is inspected and its extraction verified against the calibration table for its user
