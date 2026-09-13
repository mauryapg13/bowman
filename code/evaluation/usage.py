"""usage.py — token/cost instrumentation for every port call (AGENTS.md §6.5).

Every real model call appends one JSON line to code/evaluation/usage.jsonl.
Cache hits are recorded too (calls=0, cache_hits=1) so the report can state
how much of the final run was served offline. report() renders usage_report.md.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent / "usage.jsonl"
REPORT = Path(__file__).resolve().parent / "usage_report.md"

# USD per 1M tokens (input, output) — Anthropic list prices, 2026-06.
PRICES = {
    "z-ai/glm-5.3-flash": (0.15, 0.50),            # OpenRouter list price, 2026-09-13
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (2.00, 10.00),
    "claude-haiku-4-5": (1.00, 5.00),
}


def record(port: str, provider: str, model: str, input_tokens: int, output_tokens: int,
           cache_hit: bool, request_id: str | None = None) -> None:
    pin, pout = PRICES.get(model, (0.0, 0.0))
    row = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "port": port, "provider": provider, "model": model,
        "calls": 0 if cache_hit else 1, "cache_hits": 1 if cache_hit else 0,
        "input_tokens": input_tokens, "output_tokens": output_tokens,
        "estimated_cost_usd": 0.0 if cache_hit else (input_tokens * pin + output_tokens * pout) / 1e6,
        "request_id": request_id,
    }
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def reset() -> None:
    if LOG.exists():
        LOG.unlink()


def summarise(n_requests: int = 250) -> dict:
    per: dict[tuple[str, str, str], dict] = defaultdict(lambda: {"calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0})
    if LOG.exists():
        for line in LOG.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            k = (r["port"], r["provider"], r["model"])
            for f in ("calls", "cache_hits", "input_tokens", "output_tokens", "estimated_cost_usd"):
                per[k][f] += r[f]
    total = {"calls": 0, "cache_hits": 0, "input_tokens": 0, "output_tokens": 0, "estimated_cost_usd": 0.0}
    for v in per.values():
        for f in total:
            total[f] += v[f]
    total["total_tokens"] = total["input_tokens"] + total["output_tokens"]
    total["avg_tokens_per_request"] = total["total_tokens"] / n_requests
    total["cost_per_request_usd"] = total["estimated_cost_usd"] / n_requests
    return {"per_model": {"/".join(k): v for k, v in per.items()}, "totals": total, "n_requests": n_requests}


def report(n_requests: int = 250) -> str:
    s = summarise(n_requests)
    t = s["totals"]
    lines = [
        "# Usage report — final full-dataset run",
        "",
        f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from `code/evaluation/usage.jsonl`, "
        f"which is appended by every port call during the run that produced `output.csv` ({n_requests} requests).",
        "",
        "Design note: the decision pipeline is deterministic code. Models are used only at the",
        "perception edges — reading one amount off each of the 16 images (`ports/vision.py`) and",
        "mapping each of the 215 messages to one closed-enum operation (`ports/ops.py`).",
        "`decision_explanation` is templated by code: **zero model calls** for that column.",
        "All port results are cached on sha256(payload)+prompt_version, so a re-run is offline.",
        "",
        "## Per model",
        "",
        "| port / provider / model | live calls | cache hits | input tokens | output tokens | est. cost (USD) |",
        "|---|---|---|---|---|---|",
    ]
    for k, v in sorted(s["per_model"].items()):
        lines.append(f"| {k} | {v['calls']} | {v['cache_hits']} | {v['input_tokens']:,} | {v['output_tokens']:,} | {v['estimated_cost_usd']:.4f} |")
    if not s["per_model"]:
        lines.append("| (no model calls — table/offline backends only) | 0 | 0 | 0 | 0 | 0.0000 |")
    lines += [
        "",
        "## Totals",
        "",
        f"- model calls: **{t['calls']}** (plus {t['cache_hits']} cache hits)",
        f"- input tokens: **{t['input_tokens']:,}**; output tokens: **{t['output_tokens']:,}**; total: **{t['total_tokens']:,}**",
        f"- average tokens per request: **{t['avg_tokens_per_request']:.1f}**",
        f"- estimated total cost: **${t['estimated_cost_usd']:.4f}**; per request: **${t['cost_per_request_usd']:.6f}**",
        "",
        "Prices used (USD per 1M tokens, input/output): " + ", ".join(f"{m} {p[0]}/{p[1]}" for m, p in PRICES.items()) + ".",
        "No API keys or credentials appear in this file or in the submission.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    REPORT.write_text(report(), encoding="utf-8")
    print(REPORT.read_text())
