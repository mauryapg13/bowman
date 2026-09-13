"""spec §9: the calibration table is a CI test. No regression against the
recorded baseline (code/evaluation/baseline_mvp.json); the baseline is only
ever moved forward by a commit that also updates docs/*_results.md."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code" / "evaluation"))

import load as L
import main as M
import plans as PL
import score as S


@pytest.fixture(scope="module")
def report():
    ds = L.load(ROOT / "dataset")
    return S.score(M.run(requests=ds.sample_requests, config=PL.FULL, ds=ds), ds.sample_answers)


@pytest.fixture(scope="module")
def baseline():
    return json.loads((ROOT / "code" / "evaluation" / "baseline_mvp.json").read_text())


def test_calibration_table_covers_every_uncapped_sample(report):
    assert len(report.calibration) == 25
    assert sum(r.delta is not None for r in report.calibration) >= 20


def test_no_regression_on_categorical_accuracy(report, baseline):
    for col in ("affordability_status", "recommended_payment_method", "payment_plan"):
        assert report.per_column[col] >= baseline["per_column"][col] - 1e-9, col


def test_no_regression_on_calibration(report, baseline):
    assert report.calibration_mean_abs_delta <= baseline["calibration_mean_abs_delta"] * 1.001
