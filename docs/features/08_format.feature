Feature: Templated decision_explanation (code/format.py, MVP M7)
  The explanation is produced by fixed templates, never by a model.
  Source: project_spec.md N1, §7; MVP M7; all 25 sample explanations.

  Scenario: Templates are derived from all 25 samples before coding
    Given the 25 decision_explanation cells in sample_requests.csv
    Then one template per outcome is extracted and documented in code/format.py

  Scenario Outline: Outcome templates
    Given the chosen outcome "<outcome>"
    Then the explanation follows "<template>"

    Examples:
      | outcome                          | template                                                                                                            |
      | affordable_now                   | Pay {CUR} {amt} today. This leaves at least {CUR} {min} available over the next 90 days.                             |
      | installments                     | Use {n} installments of {CUR} {per}, starting {d}. This leaves at least {CUR} {min} available.                       |
      | wait                             | Pay {CUR} {amt} in full on {d}. Paying earlier would take the balance below the {CUR} {min} minimum.                 |
      | partial_payment                  | Pay {CUR} {a} today and the remaining {CUR} {b} on {d}. This completes the full request and keeps the {CUR} {min} minimum protected. |
      | full_payment + stop              | Stop the {desc}, then pay {CUR} {amt} today. This leaves at least {CUR} {min} available.                             |
      | full_payment + reduce            | Reduce the {desc} to {CUR} {new}, then pay {CUR} {amt} today. This leaves at least {CUR} {min} available.            |
      | not_affordable (options exist)   | Do not make this payment by {deadline}. None of the available options keeps the {CUR} {min} minimum protected.       |
      | not_affordable (partial capacity)| Do not proceed with the {CUR} {amt} request. Although {CUR} {safe} is available today, the full amount cannot be completed safely within 90 days. |

  Scenario: Two observed wait variants must be reconciled from the samples
    Given request_03 says "Pay IDR 5,491,000 in full on 15 November 2019. Paying earlier would take the balance below the IDR 2,668,700 minimum."
    And request_04 says "Wait until 15 June 2024, then pay IDR 12,693,000 in full. Paying sooner would put the IDR 30,686,600 minimum at risk."
    Then format.py picks one deterministic rule for choosing between them (e.g. the majority variant across all wait samples)
    And the choice is documented in code/format.py

  Scenario: Number formatting inside the explanation only
    Then amounts use the currency code prefix and comma-grouped thousands
    And decimals appear only when non-zero ("ZAR 25,256" but "IDR 15,952,906.67")
    And dates are written as "8 August 2025" with no leading zero
    And the second sentence cites minimum_balance_to_keep verbatim, not the computed minimum

  Scenario: Length
    Then every explanation is two sentences of roughly 16 to 25 words
