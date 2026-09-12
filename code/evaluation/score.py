"""score.py — M9. Run the real pipeline over the 25 samples and report.

Certificate: shared/evaluation_score.certificate.json. Spec: project_spec.md §9.
Calls main.run(); never re-implements the pipeline. The calibration table
compares our 90-day minimum with the one the answer key implies:
    expected_min = amount_safe_to_pay + minimum_balance_to_keep   (when safe < requested)
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import load as L
import main as M
import plans as PL

SCORED = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method",
          "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed", "decision_explanation"]
CATEGORICAL = ["affordability_status", "recommended_payment_method", "payment_plan"]


@dataclass(frozen=True)
class CalRow:
    request_id: str
    expected_min: float | None
    our_min: float
    delta: float | None
    capped: bool
    safe_ours: float
    safe_key: float


@dataclass(frozen=True)
class ScoreReport:
    per_column: dict[str, float]
    exact_match_categorical: float
    safe_abs_err_mean: float
    safe_rel_err_mean: float
    safe_within_half_pct: int
    calibration: list[CalRow]
    calibration_mean_abs_delta: float | None
    mismatches: list[tuple[str, str, str, str]]
    n: int


def _num_eq(a: str, b: str, tol: float = 0.005) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol * max(1.0, abs(float(b)))
    except ValueError:
        return a == b


def _plan_eq(a: str, b: str) -> bool:
    if a == b:
        return True
    if a == "none" or b == "none":
        return False
    pa, pb = a.split("|"), b.split("|")
    if len(pa) != len(pb):
        return False
    return all(x.split(":")[0] == y.split(":")[0] and _num_eq(x.split(":")[1], y.split(":")[1], 0.001) for x, y in zip(pa, pb))


def _expl_eq(a: str, b: str) -> bool:
    """Template fidelity: same first word and same numbers in the same order."""
    import re
    nums = lambda s: re.findall(r"\d[\d,]*\.?\d*", s)
    return a.split(" ")[0] == b.split(" ")[0] and nums(a) == nums(b)


EQ = {"amount_safe_to_pay": _num_eq, "payment_plan": _plan_eq, "decision_explanation": _expl_eq}


def score(decisions: list[M.Decision], answers: tuple[L.SampleAnswer, ...]) -> ScoreReport:
    by_id = {a.request_id: a for a in answers}
    hits = {c: 0 for c in SCORED}
    cat_exact = 0
    abs_err, rel_err, within = [], [], 0
    cal: list[CalRow] = []
    mism: list[tuple[str, str, str, str]] = []
    for d in decisions:
        a = by_id[d.request_id]
        ours = dict(zip(L.COL["output"], d.row.as_list()))
        row_ok = True
        for c in SCORED:
            eq = EQ.get(c, lambda x, y: x == y)
            if eq(ours[c], a.row[c]):
                hits[c] += 1
            else:
                mism.append((d.request_id, c, a.row[c], ours[c]))
                if c in CATEGORICAL:
                    row_ok = False
        cat_exact += row_ok
        so, sk = float(ours["amount_safe_to_pay"]), float(a.row["amount_safe_to_pay"])
        abs_err.append(abs(so - sk)); rel_err.append(abs(so - sk) / max(sk, 1e-9)); within += abs(so - sk) <= 0.005 * sk
        capped = sk >= a.requested_amount - 1e-9
        exp = None if capped else sk + a.minimum_balance_to_keep
        our_min = d.diagnostics.capacity.min_balance
        cal.append(CalRow(d.request_id, exp, our_min, None if exp is None else our_min - exp, capped, so, sk))
    n = len(decisions)
    deltas = [abs(r.delta) for r in cal if r.delta is not None]
    return ScoreReport(
        per_column={c: hits[c] / n for c in SCORED},
        exact_match_categorical=cat_exact / n,
        safe_abs_err_mean=sum(abs_err) / n, safe_rel_err_mean=sum(rel_err) / n, safe_within_half_pct=within,
        calibration=cal, calibration_mean_abs_delta=(sum(deltas) / len(deltas)) if deltas else None,
        mismatches=mism, n=n,
    )


def render(rep: ScoreReport) -> str:
    out = ["PER-COLUMN ACCURACY (25 samples)"]
    for c, v in rep.per_column.items():
        out.append(f"  {c:32} {v:6.1%}")
    out.append(f"  {'all three categoricals exact':32} {rep.exact_match_categorical:6.1%}")
    out.append(f"  amount_safe_to_pay: mean abs err {rep.safe_abs_err_mean:,.2f}, mean rel err {rep.safe_rel_err_mean:.1%}, within 0.5%: {rep.safe_within_half_pct}/{rep.n}")
    out.append("\nCALIBRATION  (expected_min = key amount_safe_to_pay + minimum_balance_to_keep)")
    out.append(f"  {'request':11}{'expected_min':>16}{'our_min':>16}{'delta':>16}   safe ours / key")
    for r in rep.calibration:
        exp = "capped (lower bound)" if r.capped else f"{r.expected_min:,.2f}"
        dl = "" if r.delta is None else f"{r.delta:+,.2f}"
        out.append(f"  {r.request_id:11}{exp:>16}{r.our_min:>16,.2f}{dl:>16}   {r.safe_ours:,.2f} / {r.safe_key:,.2f}")
    out.append(f"  mean |delta| over uncapped rows: {rep.calibration_mean_abs_delta:,.2f}" if rep.calibration_mean_abs_delta is not None else "")
    out.append("\nMISMATCHES (request, column, expected -> actual)")
    for rid, c, e, a in rep.mismatches:
        out.append(f"  {rid:11} {c:30} {e!r} -> {a!r}")
    return "\n".join(out)


def to_json(rep: ScoreReport) -> dict:
    return {"per_column": rep.per_column, "exact_match_categorical": rep.exact_match_categorical,
            "safe_abs_err_mean": rep.safe_abs_err_mean, "safe_within_half_pct": rep.safe_within_half_pct,
            "calibration_mean_abs_delta": rep.calibration_mean_abs_delta,
            "calibration": [asdict(r) for r in rep.calibration]}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="write the report as JSON to this path")
    args = ap.parse_args(argv)
    ds = L.load(M.REPO_ROOT / "dataset")
    decisions = M.run(requests=ds.sample_requests, config=PL.MVP, ds=ds)
    rep = score(decisions, ds.sample_answers)
    print(render(rep))
    if args.json:
        Path(args.json).write_text(json.dumps(to_json(rep), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
