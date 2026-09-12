"""M5–M8 acceptance — plans, rank, format, write certificates; spec §2, §5."""
import csv
import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

import format as FM
import load as L
import main as M
import plans as PL
import rank as RK
import write as WR

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ds():
    return L.load(ROOT / "dataset")


@pytest.fixture(scope="module")
def sample_decisions(ds):
    return M.run(requests=ds.sample_requests, ds=ds)


def test_candidate_families_and_deadline_rejection(ds, sample_decisions):
    n_inst = n_late = 0
    for d in sample_decisions:
        for c in d.diagnostics.candidates:
            if c.method == "installments":
                n_inst += 1; n_late += not c.completes_by_deadline
        methods = {c.method for c in d.diagnostics.candidates}
        assert "full_payment" in methods
    assert n_late / n_inst > 0.7          # recon: 434/515 finish after the deadline


def test_sort_key_is_total_order_and_lower_is_better(ds, sample_decisions):
    for d in sample_decisions:
        if d.chosen is None:
            continue
        survivors = [c for c in d.diagnostics.candidates if c.eligible]
        assert d.chosen.sort_key == min(c.sort_key for c in survivors)
        keys = [c.sort_key for c in survivors]
        assert len(keys) == len(set(keys))   # option_id / method makes keys distinct


def test_status_derivation():
    p = PL.Payment(date(2024, 1, 1), 0, 10.0)
    full0 = PL.Candidate("full_payment", (p,), "payment_option_01", (), True, 10, True, 0, ())
    assert RK.status_of(full0) == RK.AFFORDABLE_NOW
    sc = PL.SpendingChange("stop", "event_1", "stream_user_1_1", None)
    assert RK.status_of(PL.Candidate("full_payment", (p,), "x", (sc,), True, 10, True, 0, ())) == RK.AFFORDABLE_WITH_PLAN
    assert RK.status_of(PL.Candidate("installments", (p,), "x", (), True, 10, True, 0, ())) == RK.AFFORDABLE_WITH_PLAN
    assert RK.status_of(PL.Candidate("wait", (p,), None, (), True, 10, True, 5, ())) == RK.AFFORDABLE_LATER
    assert RK.status_of(None) == RK.NOT_AFFORDABLE


def test_method_and_term_filters(ds, sample_decisions):
    for d in sample_decisions:
        prof = ds.profiles[next(r.user_id for r in ds.sample_requests if r.request_id == d.request_id)]
        for c in d.diagnostics.candidates:
            if c.method == "installments" and prof.max_installment_months is None:
                assert "term_exceeds_max_installment_months" in c.rejection_reasons
            if c.method not in prof.payment_methods_user_will_consider and c.method != "wait":
                assert "method_not_accepted" in c.rejection_reasons
            if c.method == "wait" and "full_payment" not in prof.payment_methods_user_will_consider:
                assert "wait_requires_full_payment" in c.rejection_reasons


def test_number_formats():
    assert FM.plain(25256) == "25256" and FM.plain(603.3) == "603.3" and FM.plain(17229139.2) == "17229139.2"
    assert FM.two_dp(620.4) == "620.40" and FM.two_dp(25256) == "25256" and FM.two_dp(23.5) == "23.50"
    assert FM.money(25256, "ZAR") == "ZAR 25,256" and FM.money(620.4, "EUR") == "EUR 620.40"
    assert FM.money(15952906.67, "IDR") == "IDR 15,952,906.67"
    assert FM.long_date(date(2025, 8, 8)) == "8 August 2025"


def test_templates_reproduce_sample_wording(ds):
    a = {s.request_id: s.row["decision_explanation"] for s in ds.sample_answers}
    assert FM.TEMPLATES["affordable_now"].format(amt="ZAR 25,256", min="ZAR 18,000") == a["request_01"]
    assert FM.TEMPLATES["installments"].format(n=3, per="IDR 15,952,906.67", first="8 August 2025", min="IDR 29,158,400") == a["request_02"]
    assert FM.TEMPLATES["wait"].format(amt="IDR 5,491,000", date="15 November 2019", min="IDR 2,668,700") == a["request_03"]
    assert FM.TEMPLATES["not_affordable"].format(deadline="12 January 2026", min="ZAR 13,100") == a["request_05"]
    assert FM.TEMPLATES["partial_payment"].format(a="INR 28,820", b="INR 10,840", date="15 September 2024", min="INR 92,800") == a["request_19"]
    assert FM.TEMPLATES["full_with_changes"].format(changes="Stop the family streaming plan", amt="EUR 620.40", min="EUR 800") == a["request_06"]


def test_output_contract_on_the_real_file(ds):
    out = ROOT / "output.csv"
    assert out.is_file()
    with open(out, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0] == L.COL["output"]
    assert len(rows) == 251
    assert [r[0] for r in rows[1:]] == [q.request_id for q in ds.requests]
    ids = M.flexibility_index(ds)
    for r in rows[1:]:
        row = FM.OutputRow(*r)
        q = next(x for x in ds.requests if x.request_id == row.request_id)
        assert WR.validate_row(row, q, ds.profiles[q.user_id], ds.options_by_request[q.request_id], ids) == []


def test_write_refuses_invalid_rows_and_keeps_previous_file(ds, tmp_path):
    target = tmp_path / "output.csv"
    target.write_text("previous\n")
    reqs = ds.sample_requests[:1]
    good = M.run(requests=reqs, ds=ds)[0].row
    bad = FM.OutputRow(good.request_id, "-1", good.affordability_status, good.recommended_payment_method,
                       good.payment_plan, good.earliest_date_for_full_payment, good.spending_changes_needed, good.decision_explanation)
    with pytest.raises(WR.InvariantViolation) as ex:
        WR.write([bad], reqs, ds.profiles, ds.options_by_request, M.flexibility_index(ds), target)
    assert any(v.invariant == "I1" for v in ex.value.violations)
    assert target.read_text() == "previous\n"
    WR.write([good], reqs, ds.profiles, ds.options_by_request, M.flexibility_index(ds), target)
    assert target.read_text().splitlines()[0] == ",".join(L.COL["output"])


def test_pipeline_is_deterministic(tmp_path):
    outs = []
    for i in range(2):
        p = tmp_path / f"o{i}.csv"
        subprocess.run([sys.executable, str(ROOT / "code" / "main.py"), "--out", str(p)], check=True, capture_output=True)
        outs.append(hashlib.sha256(p.read_bytes()).hexdigest())
    assert outs[0] == outs[1]
