# Gherkin understanding of BOWman

Behaviour-level specification of the whole project, written **before any pipeline code**,
derived from `docs/project_spec.md`, `docs/MVP.md`, `docs/V1.md`, `docs/V2.md`,
`docs/dataset_notes.md` and the shipped `problem_statement.md` / `README.md` / `AGENTS.md`.

Each feature file maps to one module or one concern. Scenarios use real dataset values
(event ids, sample request ids, counts) so they can become executable tests in `tests/`
without rewriting.

| File | Module / concern | Stage |
|---|---|---|
| `00_output_contract.feature` | root `output.csv` shape, allowed values, formats | MVP |
| `01_load.feature` | `code/load.py` — parsing, FX at load, indexes | MVP M1 |
| `02_inclusion.feature` | `code/inclusion.py` — status/direction gate | MVP M2 |
| `03_links.feature` | `code/links.py` — seven lifecycle patterns | V1-1 |
| `04_recurrence.feature` | `code/recurrence.py` — stream detection, category fallback | MVP M3 |
| `05_ledger.feature` | `code/ledger.py` — 91-day balance, merge rule, suffix minima, capacity | MVP M4 |
| `06_plans_and_ranking.feature` | `code/plans.py` + `code/rank.py` — candidates, filters, sort, status | MVP M5–M6 |
| `07_spending_changes.feature` | `code/spending.py` + variants — two gates, event_id convention | V1-4, V1-5 |
| `08_format.feature` | `code/format.py` — templated explanations | MVP M7 |
| `09_write_and_validate.feature` | `code/write.py` — invariants I1–I13, atomic write | MVP M8 |
| `10_port_vision.feature` | `code/ports/vision.py` — 16 image amounts | V1-2 |
| `11_port_ops.feature` | `code/ports/ops.py` — closed-enum message operations | V1-3 |
| `12_evaluation.feature` | `score.py`, calibration, `ablation.py`, determinism, usage report | MVP M9, V1-7 |
| `13_process_and_stage_gates.feature` | non-negotiables, definitions of done, prohibitions, doc precedence | all |

## Findings surfaced while writing these (not yet in the spec)

1. **`user_11` dining cadence is 21 days**, yet sample `request_11` reduces `event_989` — the
   spec's `[25, 35]` gap band will miss this stream. `04_recurrence.feature` records it as a known
   spec risk; the band (or a per-category band) must widen before request_11 is reproducible.
2. **`max_installment_months` cross-tab verified**: all 119 blank profiles omit `installments`,
   all 156 that list `installments` have a number. "Blank = unavailable" is safe.
3. **`event_id` convention verified** on all three spending-change samples: it is the latest
   recorded occurrence of the stream on/before `request_date`.
4. **Two wait-explanation variants** exist in the samples (request_03 vs request_04);
   `format.py` needs a deterministic choice.
5. **Doc conflict**: `V1.md` V1-7 says `log.txt` is at `$HOME/hackerrank_orchestrate/log.txt`;
   `AGENTS.md` §2 says repo root. AGENTS.md wins.
