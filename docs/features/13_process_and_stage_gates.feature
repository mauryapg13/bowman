Feature: Process, stage gates and prohibitions
  Source: project_spec.md N1-N6, §10-§13; MVP/V1/V2 definitions of done; AGENTS.md.

  Scenario: The model describes, the code decides (N1)
    Then no LLM output reaches amount_safe_to_pay, affordability_status, recommended_payment_method, payment_plan, earliest_date_for_full_payment or spending_changes_needed
    And LLMs produce only an image amount (vision port) and a closed-enum operation (ops port)

  Scenario: One writer (N3)
    Then Claude Code is the sole author of repository files
    And other models may review but never write

  Scenario: Every stage ships (N4)
    Then a valid 250-row output.csv exists at the end of MVP and at the end of V1

  Scenario: MVP definition of done
    Then python3 code/main.py produces a root-level output.csv with 250 rows
    And all invariants pass
    And score.py prints the per-column table and the calibration table
    And two runs are byte-identical
    And zero network calls and zero API keys are required
    And docs/mvp_results.md exists

  Scenario: V1 order of work
    Then tasks run in order: links, vision, ops, spending changes, variants, iterate, deliverables
    And each ends with a re-scored, still-valid output.csv

  Scenario: V1 definition of done
    Then output.csv, code.zip (with evaluation/usage_report.md, ablation.py, README.md), and a determinism script exist
    And docs/v1_log.md records every attempt, its score delta and any revert
    And code.zip excludes virtualenvs, caches, dataset/ and .env
    And the zip is grepped for keys before upload

  Scenario: V2 hard gate
    Given docs/v1_log.md shows a populated ablation table
    And code.zip has been built once successfully
    And at least three hours remain
    Then and only then may a V2 task begin
    And every V2 task ends with a valid output.csv and a logged score

  Scenario: Prohibitions
    Then no branch keys on a specific request_id or user_id
    And no arithmetic is done by an LLM
    And no keyword-based injection filtering exists
    And nothing under dataset/ is written
    And no output is written before validation passes
    And no income is invented for users without a supported income source

  Scenario: Conventions
    Then Python 3.11+, standard library core, third-party only for HTTP and OCR declared in code/README.md
    And dataclasses for every record type, type hints on public functions, dates as datetime.date
    And secrets from environment variables only with a shipped .env.example

  Scenario: Doc precedence
    Given a conflict between a stage file and project_spec.md
    Then project_spec.md wins
    Given a conflict between project_spec.md and problem_statement.md, README.md or AGENTS.md
    Then the shipped doc wins and project_spec.md is corrected with a note

  Scenario: Known doc conflict - log.txt location
    Given V1-7 says log.txt lives at $HOME/hackerrank_orchestrate/log.txt
    And AGENTS.md §2 says log.txt lives beside AGENTS.md at the repository root
    Then AGENTS.md wins and V1-7 must be corrected to the repo-root path

  Scenario: Transcript logging
    Then every user turn is appended to <repo root>/log.txt with tool=Claude Code
    And log.txt is never committed
