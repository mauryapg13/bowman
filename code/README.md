# BOWman — Buy or Wait?

Deterministic financial-decision pipeline for the HackerRank Orchestrate "Buy or Wait?"
challenge. For each of the 250 requests it reconstructs the user's 90-day balance curve,
enumerates every payment plan, keeps only the safe ones the user would accept, and writes
the best by the challenge's ranking rule.

## Run

```bash
python3 --version          # 3.11+ ; standard library only for the core
python3 code/main.py       # -> ./output.csv (250 rows), validated before writing
python3 code/evaluation/score.py     # per-column accuracy + calibration table on the 25 samples
python3 code/evaluation/ablation.py  # layer-by-layer table + negative control
python3 -m pytest -q tests           # 75 tests
sh code/determinism.sh               # runs twice, compares sha256
```

Model access is optional. `code/cache/` ships every port result, so the run above is
**offline and byte-identical**. To re-query the models copy `.env.example` to `.env` and
set `OPENROUTER_API_KEY` (default model `z-ai/glm-5.3-flash`) or `ANTHROPIC_API_KEY`;
bump `PROMPT_VERSION` in a port to invalidate its cache.

## Architecture

```
dataset/*.csv ─► load ─► amounts ─► inclusion ─► links ─► recurrence ─► amend ─► ledger ─► plans ─► rank ─► format ─► write ─► output.csv
                          │                                              │                    │
                     ports/vision                                    ports/ops            spending
                          └──────────────── ports/cache (sha256) ────────┘
```

| module | job |
|---|---|
| `load.py` | typed records, FX at load (settlement-date rate row), snapshot assertion |
| `amounts.py` | 16 blank amounts filled from images via `ports/vision.py`, converted on settlement date |
| `inclusion.py` | which rows are cash: pending debits reserved, pending credits ignored, cancelled/failed/unrealized out |
| `links.py` | 7 lifecycle patterns over `linked_event_id` (refunds, duplicate charges, retries, valuations) |
| `recurrence.py` | streams from history: per-description for fixed bills, per-category for groceries/transport/dining; scheduled "next salary" rows join their stream; stale streams end |
| `amend.py` + `ports/ops.py` | each message → one closed-enum operation against an allow-list (raise, ended, first salary, rent +12%, delay, cancel, none) |
| `ledger.py` | `balance[0..90]`, suffix minima, `amount_safe_to_pay`, earliest full-payment day, plan safety |
| `plans.py` / `spending.py` / `rank.py` | full / installments / partial / wait (+ stop/reduce variants) → filters → 6-key sort → status |
| `format.py` | templated explanations (derived from all 25 samples) — no model |
| `write.py` | invariants I1–I13, atomic write |

**Key design decision — the model describes, the code decides.** Language models appear in
exactly two places, both before any arithmetic: reading *which printed number* an image
contains, and classifying a message into an operation the code then validates and applies.
No model output reaches a scored column directly; `decision_explanation` is a template.
Untrusted text (messages, images, request_text) is defended structurally — closed enums and
identifier allow-lists — never by keyword filtering.

## How we know it works

**Calibration.** For every sample where `amount_safe_to_pay < requested_amount`, the answer key
implies the exact 90-day minimum: `amount_safe_to_pay + minimum_balance_to_keep`. `score.py`
prints ours beside it; the sign of the delta says whether we are optimistic (missed an outflow)
or pessimistic (missed an income). Rows within a few units mean the curve is right in shape.

**Ablation (25 samples):**

| configuration | affordability | method | plan | earliest date | all 3 exact | mean \|calibration Δ\| |
|---|---|---|---|---|---|---|
| deterministic core only | 68% | 72% | 68% | 76% | 64% | 120k |
| + lifecycle links | 68% | 72% | 68% | 76% | 64% | 120k |
| + vision (16 images) | 68% | 72% | 68% | 76% | 64% | 120k |
| + message operations | 72% | 76% | 72% | 76% | 68% | 88k |
| + spending changes, variable spend phased from last purchase | **76%** | **80%** | **76%** | **76%** | **72%** | 248k |
| + variable-spend phase reset (full system) | **76%** | **80%** | **76%** | **76%** | **72%** | **88k** |
| negative control (re-apply settled past) | 64% | 72% | 68% | 40% | 56% | 1.83M |

Links and vision are correct but nearly invisible on the samples (no sample user has a
duplicate charge; 12 of the 16 images are settled history already inside the balance).
Message operations are the largest single gain, exactly as the data predicted: 228 of 275
users have no scheduled salary row, and for many the message is the only forward signal.

**Determinism.** `code/determinism.sh` runs the CLI twice and diffs the sha256.

## Known limitations

- Variable spend (groceries/transport/dining) is a fixed-period clock per user (gaps of exactly
  5/7/10/14/21 days across all 275 users) with ±15% amount noise. We forecast each category on
  its own cadence at the median amount, restarting the clock 3 days after the request — the
  phase the answer key uses (found by plotting all 25 sample curves; `docs/v1_log.md` #13). The
  remaining `amount_safe_to_pay` residuals (1–4% on a few large users) are the amount noise on
  the one to three purchases before payday, which no history-only forecast can know.
- Income that ends is detected from a missing expected occurrence, not from wording; a payroll
  that stops exactly at the request date with no gap is not caught.
- Gig-income messages ("payout still pending") are classified `none`; the key appears to drop
  part of that income (sample request_10) and we do not.
- `image_04` is cropped below "Item Bill"; the order total is not visible (recorded at low confidence).
- Rates are constant per pair in the shipped data; a moving-rate dataset would need per-occurrence
  conversion in the ledger (currently converted once at the effective date, documented in spec §4.6).

Full rules: `docs/project_spec.md`; every empirical finding: `docs/learnings.md`; results:
`docs/mvp_results.md`, `docs/v1_log.md`.
