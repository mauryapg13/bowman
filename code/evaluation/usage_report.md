# Usage report — final full-dataset run

Generated 2026-09-13T02:22:23+00:00 from `code/evaluation/usage.jsonl`, which is appended by every port call during the run that produced `output.csv` (250 requests).

Design note: the decision pipeline is deterministic code. Models are used only at the
perception edges — reading one amount off each of the 16 images (`ports/vision.py`) and
mapping each of the 215 messages to one closed-enum operation (`ports/ops.py`).
`decision_explanation` is templated by code: **zero model calls** for that column.
All port results are cached on sha256(payload)+prompt_version, so a re-run is offline.
Vision ran on the reviewed-transcription backend (all 16 images opened and transcribed during
development, sha256 provenance in `code/ports/vision_table.json`): zero model tokens for images.

The run that wrote `output.csv` made **0 live model calls** and **209 cache hits** — it is fully reproducible offline. The tokens and cost below are the live calls that populated that cache (this is the compute the submission actually consumed; a handful of early calls under a superseded prompt version are included rather than hidden).

## Per model (live calls that built the cache)

| port / provider / model | live calls | cache hits | input tokens | output tokens | est. cost (USD) |
|---|---|---|---|---|---|
| ops/openrouter/z-ai/glm-5.3-flash | 318 | 0 | 343,485 | 116,505 | 0.1098 |

## Totals

- live model calls: **318**; final-run cache hits: **209**
- input tokens: **343,485**; output tokens: **116,505**; total: **459,990**
- average tokens per request: **1840.0**
- estimated total cost: **$0.1098**; per request: **$0.000439**

Prices used (USD per 1M tokens, input/output): z-ai/glm-5.3-flash 0.15/0.5, claude-opus-5 5.0/25.0, claude-sonnet-5 2.0/10.0, claude-haiku-4-5 1.0/5.0.
No API keys or credentials appear in this file or in the submission.
