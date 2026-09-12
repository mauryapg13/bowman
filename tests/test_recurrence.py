"""M3 acceptance — shared/recurrence.certificate.json, spec §4.2."""
from datetime import date, timedelta
from pathlib import Path

import pytest

import inclusion as I
import load as L
import recurrence as R

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ds():
    return L.load(ROOT / "dataset")


def detect(ds, user):
    return R.detect(I.gate(ds.events_by_user[user]), user)


def _event(i, d, amount, category="rent", description="Rent", status="settled", direction="debit"):
    return L.RawEvent(f"event_{i}", "user_9", "expense", description, category, direction, amount, amount,
                      "INR", d, d, status, None, "fixed", None)


def test_user_01_expected_streams(ds):
    d = detect(ds, "user_01")
    by = {(s.category, s.description): s for s in d.streams}
    for key in [("rent", "Apartment rent transfer"), ("utilities", "Household utility payment"),
                ("music_subscription", "Music service subscription")]:
        s = by[key]
        assert 25 <= s.cadence_days <= 35
        amounts = [o.amount for o in s.occurrences]
        assert min(amounts) <= s.amount <= max(amounts)          # median of history (spec §4.2)
    assert by[("music_subscription", "Music service subscription")].amount == 235.4


def test_user_11_dining_is_one_category_stream_with_cadence_21(ds):
    d = detect(ds, "user_11")
    dining = [s for s in d.streams if s.category == "dining"]
    assert len(dining) == 1
    assert dining[0].cadence_days == 21
    assert dining[0].latest_event_id == "event_989"
    assert dining[0].description is None
    assert dining[0].minimum_allowed_amount == 665950


def test_sample_spending_change_ids_are_latest_event_ids(ds):
    expected = {"user_06": "event_476", "user_21": {"event_1815", "event_1816"}}
    ids6 = {s.latest_event_id for s in detect(ds, "user_06").streams}
    assert "event_476" in ids6
    ids21 = {s.latest_event_id for s in detect(ds, "user_21").streams}
    assert expected["user_21"] <= ids21


def test_threshold_and_band():
    base = date(2024, 1, 1)
    two = [_event(i, base + timedelta(days=30 * i), 100) for i in range(2)]
    assert detect_synth(two).streams == ()
    three_monthly = [_event(i, base + timedelta(days=30 * i), 100) for i in range(3)]
    assert len(detect_synth(three_monthly).streams) == 1
    three_yearly = [_event(i, base + timedelta(days=365 * i), 100) for i in range(3)]
    assert detect_synth(three_yearly).streams == ()
    weekly = [_event(i, base + timedelta(days=7 * i), 100) for i in range(4)]
    assert detect_synth(weekly).streams[0].cadence_days == 7


def detect_synth(raw):
    return R.detect(I.gate(raw), "user_9")


def test_every_included_event_is_in_exactly_one_place(ds):
    for user in ("user_01", "user_11", "user_03", "user_200"):
        evs = I.gate(ds.events_by_user[user])
        d = detect(ds, user)
        in_streams = [o.event_id for s in d.streams for o in s.occurrences]
        in_oneoffs = [o.event_id for o in d.oneoffs]
        assert len(in_streams) == len(set(in_streams))
        assert set(in_streams).isdisjoint(in_oneoffs)
        assert set(in_streams) | set(in_oneoffs) == {e.event_id for e in evs if e.included}


def test_scheduled_salary_is_absorbed_not_double_counted(ds):
    d = detect(ds, "user_17")   # Payroll credit x5 + scheduled Next confirmed salary
    salary = [s for s in d.streams if s.category == "salary"]
    assert len(salary) == 1
    assert salary[0].occurrences[-1].event_id.startswith("event_") and salary[0].anchor == date(2026, 3, 15)
    assert not any(o.category == "salary" and o.status == "scheduled" for o in d.oneoffs)
    assert any(p.startswith("recurrence:absorbed") for p in salary[0].provenance)


def test_no_stream_means_scheduled_salary_stays_a_oneoff(ds):
    d = detect(ds, "user_01")   # only 1 settled salary + 1 scheduled
    assert not any(s.category == "salary" for s in d.streams)
    assert any(o.event_id == "event_103" and o.status == "scheduled" for o in d.oneoffs)
    assert d.zero_income is False


def test_zero_income_flag_and_no_invention(ds):
    zero = [u for u in ds.events_by_user if detect(ds, u).zero_income]
    assert len(zero) == 50
    for u in zero[:5]:
        d = detect(ds, u)
        assert not any(s.direction == "credit" for s in d.streams)


def test_stream_is_frozen(ds):
    s = detect(ds, "user_01").streams[0]
    with pytest.raises(Exception):
        s.amount = 1  # type: ignore[misc]
