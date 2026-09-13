"""ablation.py — V1-7. Score the 25 samples with each layer switched on in turn.

Certificate: shared/evaluation_ablation.certificate.json. Every row is one
main.run() with a RunConfig; the negative control re-applies settled past
events to the opening balance and must score WORSE on calibration.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import load as L
import main as M
import plans as PL
import score as S

CONFIGS = [
    ("MVP core only", PL.RunConfig()),
    ("+ lifecycle links", PL.RunConfig(links=True)),
    ("+ vision", PL.RunConfig(links=True, vision=True)),
    ("+ message operations", PL.RunConfig(links=True, vision=True, ops=True)),
    ("+ spending changes, phase = last + cadence", PL.RunConfig(links=True, vision=True, ops=True, spending_changes=True, variable_first_day=None)),
    ("+ variable-spend phase reset (full system)", PL.RunConfig(links=True, vision=True, ops=True, spending_changes=True)),
    ("negative control: re-apply settled past", PL.RunConfig(links=True, vision=True, ops=True, spending_changes=True, reapply_settled_past=True)),
]


def run() -> list[tuple[str, PL.RunConfig, S.ScoreReport]]:
    ds = L.load(M.REPO_ROOT / "dataset")
    out = []
    for name, cfg in CONFIGS:
        rep = S.score(M.run(requests=ds.sample_requests, config=cfg, ds=ds), ds.sample_answers)
        out.append((name, cfg, rep))
    return out


def render(rows) -> str:
    cols = ["affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed", "decision_explanation"]
    head = "| configuration | " + " | ".join(c.replace("_", " ") for c in cols) + " | all 3 categoricals | mean \\|calibration Δ\\| |"
    sep = "|---|" + "---|" * (len(cols) + 2)
    lines = [head, sep]
    for name, cfg, rep in rows:
        lines.append(f"| {name} | " + " | ".join(f"{rep.per_column[c]:.0%}" for c in cols) +
                     f" | **{rep.exact_match_categorical:.0%}** | {rep.calibration_mean_abs_delta:,.0f} |")
    return "\n".join(lines)


if __name__ == "__main__":
    rows = run()
    print(render(rows))
    full = next(r for n, c, r in rows if n.startswith("+ variable-spend"))
    ctrl = next(r for n, c, r in rows if n.startswith("negative"))
    if ctrl.calibration_mean_abs_delta <= full.calibration_mean_abs_delta:
        raise SystemExit("negative control did not score worse — spec §3 guard 3 failed")
    print("\nnegative control scored worse on calibration: guard 3 holds")
