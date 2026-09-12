Feature: Scoring, calibration, ablation, determinism and usage report (code/evaluation/*)
  Source: project_spec.md §9; MVP M9; V1-7.

  Scenario: score.py runs the real pipeline over the 25 samples
    When score.py runs
    Then it prints per-column accuracy for all seven scored columns separately
    And exact-match rate for affordability_status, recommended_payment_method and payment_plan
    And absolute and relative error for amount_safe_to_pay plus the count within 0.5%
    And a one-line diff per mismatching row

  Scenario: Calibration table
    Given every sample row with amount_safe_to_pay < requested_amount (about 20 of 25)
    Then score.py prints expected_min = amount_safe_to_pay + minimum_balance_to_keep beside our min(balance[0..90]) with the delta
    And rows with amount_safe_to_pay == requested_amount are shown as lower bounds only

  Scenario: Baseline is recorded before V1 starts
    Then docs/mvp_results.md records the per-column score, the calibration deltas, the max_installment_months cross-tab and the count of zero-income users
    And no V1 task starts before that file exists

  Scenario: Every V1 change is measured and reversible
    Given a change to any module
    When score.py is re-run
    Then the delta versus the baseline is logged in docs/v1_log.md
    And a change that does not improve the score is reverted and the negative result kept in the log

  Scenario: Ablation table
    When ablation.py runs
    Then it reports the per-column score for: MVP core only; + lifecycle links; + vision; + message operations; + spending changes; full system

  Scenario: Determinism proof
    When the pipeline is run twice over the same inputs and cache
    Then the sha256 of output.csv is identical both times

  Scenario: Usage report describes the final run
    Then code/evaluation/usage_report.md lists providers, model names, call counts, input/output tokens, totals, per-request averages, estimated total and per-request cost, per-model if more than one
    And token counting is instrumented from the first port call, not reconstructed
    And it states explicitly that decision_explanation used zero model calls
    And it contains no API keys or secrets
