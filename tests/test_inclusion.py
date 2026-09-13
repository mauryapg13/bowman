"""M2 acceptance — shared/inclusion.certificate.json, spec §4.3."""
from collections import Counter
from pathlib import Path

import pytest

import inclusion as I
import load as L

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def verdicts():
    ds = L.load(ROOT / "dataset")
    return I.gate(list(ds.events()))


@pytest.mark.parametrize("status,direction,amount,included,reason", [
    ("settled", "debit", 1.0, True, None),
    ("settled", "credit", 1.0, True, None),
    ("scheduled", "debit", 1.0, True, None),
    ("scheduled", "credit", 1.0, True, None),
    ("pending", "debit", 1.0, True, None),
    ("pending", "credit", 1.0, False, I.PENDING_CREDIT),
    ("cancelled", "debit", 1.0, False, I.CANCELLED),
    ("failed", "debit", 1.0, False, I.FAILED),
    ("unrealized", "non_cash", 1.0, False, I.NON_CASH_UNREALIZED),
    ("settled", "debit", None, False, I.AMOUNT_UNKNOWN),
    ("pending", "debit", None, False, I.AMOUNT_UNKNOWN),
])
def test_gate_table(status, direction, amount, included, reason):
    from datetime import date
    e = L.RawEvent("event_1", "user_1", "expense", "x", "dining", direction, amount, amount, "INR",
                   date(2024, 1, 1), date(2024, 1, 1), status, None, "fixed", None)
    v = I.gate([e])[0]
    assert (v.included, v.exclusion_reason) == (included, reason)
    assert v.provenance and v.provenance[0].startswith("inclusion:")


def test_dataset_counts(verdicts):
    c = Counter(v.exclusion_reason for v in verdicts if not v.included)
    assert c == {"cancelled": 22, "failed": 21, "pending_credit": 8, "non_cash_unrealized": 10, "amount_unknown": 16}
    assert len(verdicts) == 25342
    assert sum(v.included for v in verdicts) == 25342 - sum(c.values())


def test_pending_asymmetry(verdicts):
    pend = [v for v in verdicts if v.status == "pending"]
    assert all(not v.included for v in pend if v.direction == "credit")
    assert all(v.included for v in pend if v.direction == "debit" and v.amount is not None)


def test_investments_are_cash_except_valuations(verdicts):
    by_type = {}
    for v in verdicts:
        if v.event_type.startswith("investment"):
            by_type.setdefault(v.event_type, set()).add(v.included)
    assert by_type == {"investment_purchase": {True}, "investment_sale": {True}, "investment_valuation": {False}}


def test_exclude_returns_copy(verdicts):
    v = next(x for x in verdicts if x.included)
    w = v.exclude(I.DUPLICATE_CHARGE, "links:test")
    assert v.included and not w.included and w.exclusion_reason == I.DUPLICATE_CHARGE
    assert w.provenance[-1] == "links:test"
