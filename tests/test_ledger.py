"""M4 acceptance — shared/ledger.certificate.json, spec §3 and §4.1."""
from datetime import date, timedelta

import pytest

import ledger as LG
from recurrence import Amendment, Occurrence, OneOff, Stream

START = date(2024, 3, 1)


def stream(anchor, cadence=30, amount=100.0, occurrences=None, direction="debit", amendments=(), sid="stream_user_9_1"):
    occs = occurrences or (Occurrence("event_1", anchor, amount),)
    return Stream(sid, "user_9", direction, "rent", "Rent", cadence, amount, anchor, tuple(occs),
                  "fixed", None, occs[-1].event_id, tuple(amendments))


def days_of(led, kind=None, source=None):
    return [p.day for p in led.placements if (kind is None or p.kind == kind) and (source is None or p.source_id == source)]


def test_past_anchor_rolls_forward_never_skipped():
    led = LG.forecast([stream(START - timedelta(days=10), cadence=20)], [], START, 1000, 0)
    assert days_of(led, "predicted") == [10, 30, 50, 70, 90]
    assert days_of(led, "recorded") == []          # anchor is before day 0


def test_anchor_on_day_zero_is_recorded_not_predicted():
    led = LG.forecast([stream(START, cadence=20)], [], START, 1000, 0)
    assert days_of(led, "recorded") == [0] and days_of(led, "predicted") == [20, 40, 60, 80]


def test_monthly_streams_keep_the_day_of_month():
    # anchor 15 Feb, cadence 31 -> 15 Mar, 15 Apr, 15 May (not 17 Mar / 17 Apr)
    led = LG.forecast([stream(date(2024, 2, 15), cadence=31)], [], START, 1000, 0)
    got = [START + timedelta(days=d) for d in days_of(led, "predicted")]
    assert got == [date(2024, 3, 15), date(2024, 4, 15), date(2024, 5, 15)]
    # 31 Jan anchor clamps to month ends
    led = LG.forecast([stream(date(2024, 1, 31), cadence=30)], [], date(2024, 2, 1), 1000, 0)
    got = [date(2024, 2, 1) + timedelta(days=d) for d in days_of(led, "predicted")]
    assert got == [date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30)]


def test_recorded_occurrences_after_request_date_are_not_duplicated():
    occs = (Occurrence("event_1", START - timedelta(days=25), 100.0),
            Occurrence("event_2", START + timedelta(days=5), 100.0),
            Occurrence("event_3", START + timedelta(days=35), 100.0))
    s = stream(START + timedelta(days=35), cadence=20, occurrences=occs)
    led = LG.forecast([s], [], START, 1000, 0)
    assert days_of(led, "recorded") == [5, 35]
    assert days_of(led, "predicted") == [55, 75]
    assert len([p for p in led.placements if p.day == 35]) == 1


def test_stale_anchor_cannot_double_place():
    """Even with an anchor older than the last recorded occurrence (a
    programmer error), prediction starts strictly after the last recorded
    day, so the same stream can never land twice on one day."""
    occs = (Occurrence("event_1", START, 100.0), Occurrence("event_2", START + timedelta(days=30), 100.0))
    s = stream(START, cadence=20, occurrences=occs)   # stale anchor at day 0
    led = LG.forecast([s], [], START, 1000, 0)
    assert days_of(led, "recorded") == [0, 30]
    assert days_of(led, "predicted") == [40, 60, 80]
    per_day = {}
    for p in led.placements:
        per_day[p.day] = per_day.get(p.day, 0) + 1
    assert max(per_day.values()) == 1


def test_oneoffs_only_inside_window():
    o_in = OneOff("event_5", "user_9", "debit", 50.0, START + timedelta(days=10), "x", "scheduled")
    o_out = OneOff("event_6", "user_9", "debit", 50.0, START + timedelta(days=100), "x", "scheduled")
    o_past = OneOff("event_7", "user_9", "debit", 50.0, START - timedelta(days=1), "x", "settled")
    led = LG.forecast([], [o_in, o_out, o_past], START, 1000, 0)
    assert days_of(led, "oneoff") == [10]
    assert led.balance[9] == 1000 and led.balance[10] == 950 and led.balance[90] == 950


def test_suffix_minima_definition_and_monotonicity():
    assert LG.suffix_minima([100, 80, 120, 60, 90]) == (60, 60, 60, 60, 90)
    led = LG.forecast([stream(START - timedelta(days=3), cadence=7, amount=10),
                       stream(START - timedelta(days=1), cadence=30, amount=300, direction="credit", sid="stream_user_9_2")],
                      [], START, 500, 0)
    sm = led.suffix_min
    assert all(sm[i] <= sm[i + 1] for i in range(len(sm) - 1))
    assert all(sm[d] == min(led.balance[d:]) for d in range(0, 91, 10))


def test_capacity_math():
    bal = [300, 250, 180, 400, 350] + [350] * 86
    led = LG.Ledger("user_9", START, 300, 100, tuple(bal), LG.suffix_minima(bal), ())
    cap = LG.capacity(led, 200)
    assert cap.amount_safe_to_pay == 80 and cap.min_balance == 180
    assert cap.earliest_full_day == 3 and cap.earliest_full_date == START + timedelta(days=3)
    assert LG.capacity(led, 60).amount_safe_to_pay == 60                  # capped at requested
    assert LG.capacity(led, 10_000).earliest_full_day is None            # never within window
    assert LG.capacity(led, 10_000).amount_safe_to_pay == 80


def test_amount_safe_never_negative():
    bal = [50] * 91
    led = LG.Ledger("user_9", START, 50, 100, tuple(bal), LG.suffix_minima(bal), ())
    assert LG.capacity(led, 10).amount_safe_to_pay == 0


def test_plan_safety():
    bal = [300, 250, 180, 400, 350] + [350] * 86
    led = LG.Ledger("user_9", START, 300, 100, tuple(bal), LG.suffix_minima(bal), ())
    assert LG.is_safe(led, [(0, 80)])
    assert not LG.is_safe(led, [(0, 81)])
    assert not LG.is_safe(led, [(0, 100), (3, 100)])    # day 2 dips to 80
    assert LG.is_safe(led, [(3, 250)])
    assert LG.is_safe(led, [(95, 1_000_000)])           # outside window: not checked


def test_amendments_raise_end_and_one_off_reduction():
    anchor = START - timedelta(days=15)
    raise_ = Amendment(START + timedelta(days=20), 150.0, 150.0, "INR", None, False, False, "message_1", "amend_stream")
    s = stream(anchor, cadence=30, amount=100, direction="credit", amendments=(raise_,))
    led = LG.forecast([s], [], START, 0, 0)
    got = {p.day: p.amount for p in led.placements}
    assert got == {14: 100.0, 45: 150.0, 75: 150.0}

    ended = Amendment(START + timedelta(days=40), None, None, None, None, True, False, "message_2", "amend_stream")
    led = LG.forecast([stream(anchor, 30, 100, direction="credit", amendments=(ended,))], [], START, 0, 0)
    assert sorted(p.day for p in led.placements) == [14]

    once = Amendment(START + timedelta(days=1), 60.0, 60.0, "INR", None, False, True, "message_3", "amend_stream")
    led = LG.forecast([stream(anchor, 30, 100, direction="credit", amendments=(once,))], [], START, 0, 0)
    assert {p.day: p.amount for p in led.placements} == {14: 60.0, 45: 100.0, 75: 100.0}


def test_determinism():
    s = stream(START - timedelta(days=3), cadence=7, amount=10)
    a = LG.forecast([s], [], START, 500, 0)
    b = LG.forecast([s], [], START, 500, 0)
    assert a == b
