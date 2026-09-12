"""M1 acceptance — shared/load.certificate.json + MVP.md M1 'done when'."""
from datetime import date
from pathlib import Path

import pytest

import load as L

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ds():
    return L.load(ROOT / "dataset")


def test_all_nine_files_load(ds):
    assert len(ds.profiles) == 275
    assert sum(len(v) for v in ds.events_by_user.values()) == 25342
    assert len(ds.requests) == 250 and len(ds.sample_requests) == 25
    assert sum(len(v) for v in ds.options_by_request.values()) == 790
    assert sum(len(v) for v in ds.messages_by_user.values()) == 215
    assert len(ds.images_by_event) == 16
    assert len(ds.fx) == 134


def test_blank_amount_is_none_never_zero(ds):
    evs = list(ds.events())
    blank = [e for e in evs if e.amount is None]
    assert len(blank) == 16
    assert all(e.amount_original is None for e in blank)
    assert not any(e.amount == 0.0 and e.amount_original is None for e in evs)


def test_foreign_amounts_converted_with_settlement_date_rate(ds):
    evs = list(ds.events())
    foreign = [e for e in evs if e.currency != ds.profiles[e.user_id].home_currency]
    assert len(foreign) == 140
    converted = [e for e in foreign if e.amount is not None]
    assert len(converted) == 139            # event_7307 is blank until amounts.py fills it
    e = next(e for e in evs if e.event_id == "event_2167")   # USD 1800 for an IDR user, 2023-10-15
    assert e.amount_original == 1800 and e.currency == "USD"
    assert ds.profiles[e.user_id].home_currency == "IDR"
    assert e.amount == pytest.approx(1800 * 15833.33)


def test_missing_rate_raises():
    with pytest.raises(L.FxRateMissing):
        L.convert(1.0, "USD", "INR", date(2000, 1, 1), {})


def test_same_currency_is_identity_without_lookup():
    assert L.convert(5.5, "INR", "INR", date(2000, 1, 1), {}) == 5.5


def test_profile_lists_and_blanks(ds):
    assert sum(p.max_installment_months is None for p in ds.profiles.values()) == 119
    p = ds.profiles["user_02"]
    assert p.payment_methods_user_will_consider == ("partial_payment", "installments")
    assert p.max_installment_months == 7
    blank_stop = [p for p in ds.profiles.values() if p.expense_categories_user_is_willing_to_stop == ()]
    assert len(blank_stop) == 62
    assert not any("" in p.expense_categories_user_is_willing_to_stop for p in ds.profiles.values())


def test_requests_parse(ds):
    r = ds.requests[0]
    assert r.request_id == "request_26" and r.allows_partial_payment is False
    assert r.request_date == date(2025, 8, 3) and r.requested_amount == 15656000
    assert sum(r.allows_partial_payment for r in ds.requests) == 80
    assert [r.request_id for r in ds.requests][:2] == ["request_26", "request_27"]  # file order kept


def test_options_sorted_and_frequency_none_for_full(ds):
    opts = ds.options_by_request["request_01"]
    assert [o.payment_option_id for o in opts] == [f"payment_option_0{i}" for i in range(1, len(opts) + 1)]
    assert 2 <= len(opts) <= 4
    assert opts[0].payment_method == "full_payment" and opts[0].payment_frequency_days is None
    assert opts[1].payment_frequency_days == 30


def test_events_sorted_by_date_then_id(ds):
    for evs in ds.events_by_user.values():
        keys = [(e.event_date, int(e.event_id.split("_")[1])) for e in evs]
        assert keys == sorted(keys)


def test_settlement_date_none_only_on_non_cash(ds):
    evs = list(ds.events())
    assert all((e.settlement_date is None) == (e.direction == "non_cash") for e in evs)


def test_sample_answers_are_separate_from_requests(ds):
    a = {s.request_id: s for s in ds.sample_answers}
    assert a["request_01"].row["affordability_status"] == "affordable_now"
    assert a["request_03"].minimum_balance_to_keep == 2668700
    assert set(a["request_01"].row) == set(L.COL["output"])


def test_snapshot_assertion_fires_on_violation(ds):
    bad = list(ds.events_by_user["user_01"])
    late = L.RawEvent(**{**bad[0].__dict__, "event_id": "event_999999", "status": "settled",
                         "event_date": date(2099, 1, 1)}) if hasattr(bad[0], "__dict__") else None
    if late is None:  # slots dataclass: rebuild explicitly
        import dataclasses
        late = dataclasses.replace(bad[0], event_id="event_999999", status="settled", event_date=date(2099, 1, 1))
    with pytest.raises(L.SnapshotViolation):
        L._assert_snapshot({"user_01": tuple(bad + [late])}, ds.sample_requests)


def test_image_paths_resolve(ds):
    for img in ds.images_by_event.values():
        assert (ROOT / img.path).is_file()
    assert ds.images_by_event["event_253"].image_id == "image_01"
