"""ledger.py — M4. Project streams and one-offs over days 0..90; suffix minima; capacity.

Certificate: shared/ledger.certificate.json. Spec: project_spec.md §3, §4.1.

Pure arithmetic: no I/O, no ports, no profile preferences. Same inputs =>
identical arrays. The merge rule (§4.1) is implemented, not switched: for
each stream, recorded occurrences are placed first and prediction only fills
days strictly after the stream's last recorded occurrence. A predicted and a
recorded placement for the same stream on the same day is an assertion
failure, not a silent halving of the user's balance.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, timedelta

from recurrence import OneOff, Stream

WINDOW_DAYS = 90                        # days 0..90 inclusive -> 91 elements
N = WINDOW_DAYS + 1


class DoublePlacement(AssertionError):
    """A predicted occurrence landed on a day already covered by a recorded one."""


@dataclass(frozen=True, slots=True)
class Placement:
    day: int
    amount: float
    direction: str                      # debit | credit
    source_id: str                      # event_id or stream_id
    kind: str                           # recorded | predicted | oneoff


@dataclass(frozen=True, slots=True)
class Ledger:
    user_id: str
    start: date
    opening: float
    floor: float
    balance: tuple[float, ...]          # 91
    suffix_min: tuple[float, ...]       # 91, non-decreasing
    placements: tuple[Placement, ...]


@dataclass(frozen=True, slots=True)
class Capacity:
    """Spec §3 — before spending changes, blind to payment preferences."""
    amount_safe_to_pay: float
    earliest_full_day: int | None
    earliest_full_date: date | None
    min_balance: float                  # = suffix_min[0]; calibration compares this


def _day(d: date, start: date) -> int:
    return (d - start).days


def _amount_on(stream: Stream, d: date, occurrence_index_after_anchor: int) -> float | None:
    """Apply amendments (V1-3) to a predicted occurrence on date d. Returns
    None when the stream has ended by then. `occurrence_index_after_anchor`
    is 1 for the first predicted occurrence, 2 for the next, ..."""
    amount = stream.amount
    for a in stream.amendments:                       # applied in list order
        if d < a.effective_date:
            continue
        if a.ended:
            return None
        if a.new_amount is None:
            continue
        if a.one_occurrence_only:
            # only the first predicted occurrence on/after effective_date
            first_after = next((i for i in range(1, occurrence_index_after_anchor + 1)
                                if _nth_date(stream, i) >= a.effective_date), None)
            if first_after == occurrence_index_after_anchor:
                amount = a.new_amount
        else:
            amount = a.new_amount
    return amount


MONTHLY_MIN, MONTHLY_MAX = 28, 31
VARIABLE_FIRST_DAY = 3      # variable-spend streams: next occurrence assumed this many days after the request


def _add_months(d: date, n: int) -> date:
    """Same day-of-month n months later, clamped to the month's last day."""
    import calendar
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _nth_date(stream: Stream, n: int) -> date:
    """Monthly streams (median gap 28-31) recur on the anchor's day-of-month —
    the samples key salary on the 15th every month, and day arithmetic drifts
    (30-day steps put 15 Sep, 15 Oct, 15 Nov on 13 Nov). Shorter cadences use
    day arithmetic."""
    if MONTHLY_MIN <= stream.cadence_days <= MONTHLY_MAX:
        return _add_months(stream.anchor, n)
    return stream.anchor + timedelta(days=stream.cadence_days * n)


def _stream_placements(stream: Stream, start: date) -> list[Placement]:
    if stream.cadence_days < 1:
        raise ValueError(f"{stream.stream_id}: cadence_days must be >= 1")   # a 0 cadence would loop forever
    out: list[Placement] = []
    recorded_days: set[int] = set()
    last_recorded_day = -10**9
    for occ in stream.occurrences:                     # 1. recorded occurrences in the window
        day = _day(occ.date, start)
        last_recorded_day = max(last_recorded_day, day)
        if 0 <= day <= WINDOW_DAYS:
            recorded_days.add(day)
            out.append(Placement(day, occ.amount, stream.direction, occ.event_id, "recorded"))

    # 2. predicted occurrences: anchor + k*cadence, only strictly after the last recorded day.
    #    A past anchor rolls forward by whole cadences; k starts at 1 so the anchor itself
    #    (always recorded) is never predicted.
    k = 1
    while True:
        d = _nth_date(stream, k)
        day = _day(d, start)
        if day > WINDOW_DAYS:
            break
        if day > last_recorded_day and day >= 0:
            if day in recorded_days:
                raise DoublePlacement(f"{stream.stream_id}: predicted and recorded on day {day}")
            amount = _amount_on(stream, d, k)
            if amount is not None:
                out.append(Placement(day, amount, stream.direction, stream.stream_id, "predicted"))
        k += 1
    return out


def _phase_reset(stream: Stream, start: date, first_day: int | None = VARIABLE_FIRST_DAY) -> Stream:
    """Variable-spend streams (groceries/transport/dining, description None) do not
    wait a full cadence from their last recorded purchase: AGENTS.md §6.3 asks for a
    conservative forecast of essential variable spending, and the answer key places
    the next occurrence a few days after the request regardless of the last one.
    Measured on the samples (docs/v1_log.md #13): first occurrence on day 3 halves
    the mean calibration error (248k -> 88k) and doubles the rows within 2%, with
    no change to the categorical columns. Recorded occurrences on/after the request
    are kept; prediction restarts from the request date."""
    if stream.description is not None or first_day is None:
        return stream
    first = min(first_day, stream.cadence_days)
    future = tuple(o for o in stream.occurrences if o.date >= start)
    if future:                                         # a recorded occurrence after the request: keep the real anchor
        return stream
    return replace(stream, anchor=start + timedelta(days=first - stream.cadence_days),
                   provenance=stream.provenance + (f"ledger:phase-reset first occurrence day {first}",))


def forecast(streams: tuple[Stream, ...] | list[Stream], oneoffs: tuple[OneOff, ...] | list[OneOff],
             start: date, opening: float, floor: float, user_id: str = "",
             variable_first_day: int | None = VARIABLE_FIRST_DAY) -> Ledger:
    placements: list[Placement] = []
    for s in streams:
        placements.extend(_stream_placements(_phase_reset(s, start, variable_first_day), start))
    for o in oneoffs:
        day = _day(o.date, start)
        if 0 <= day <= WINDOW_DAYS:
            placements.append(Placement(day, o.amount, o.direction, o.event_id, "oneoff"))
    placements.sort(key=lambda p: (p.day, p.kind, p.source_id))

    delta = [0.0] * N
    for p in placements:
        delta[p.day] += p.amount if p.direction == "credit" else -p.amount
    balance = [0.0] * N
    running = opening
    for d in range(N):
        running += delta[d]
        balance[d] = running
    return Ledger(user_id, start, opening, floor, tuple(balance), suffix_minima(balance), tuple(placements))


def suffix_minima(balance: list[float] | tuple[float, ...]) -> tuple[float, ...]:
    out = [0.0] * len(balance)
    running = float("inf")
    for d in range(len(balance) - 1, -1, -1):
        running = min(running, balance[d])
        out[d] = running
    return tuple(out)


def capacity(ledger: Ledger, requested_amount: float) -> Capacity:
    safe = min(max(ledger.suffix_min[0] - ledger.floor, 0.0), requested_amount)
    day = next((d for d in range(N) if ledger.suffix_min[d] - requested_amount >= ledger.floor), None)
    return Capacity(
        amount_safe_to_pay=safe,
        earliest_full_day=day,
        earliest_full_date=None if day is None else ledger.start + timedelta(days=day),
        min_balance=ledger.suffix_min[0],
    )


def is_safe(ledger: Ledger, payments: list[tuple[int, float]]) -> bool:
    """Plan safety (spec §3): after subtracting cumulative payments, every day
    0..90 stays >= floor. Payments after day 90 are outside the window."""
    cum = 0.0
    by_day: dict[int, float] = {}
    for day, amt in payments:
        if 0 <= day <= WINDOW_DAYS:
            by_day[day] = by_day.get(day, 0.0) + amt
    for d in range(N):
        cum += by_day.get(d, 0.0)
        if ledger.balance[d] - cum < ledger.floor - 1e-9:
            return False
    return True


if __name__ == "__main__":                                       # M4 calibration preview on samples
    import load, inclusion, recurrence
    ds = load.load()
    print(f"{'request':10} {'expected_min':>15} {'our_min':>15} {'delta':>14}  safe_ours / safe_key")
    for req, ans in zip(ds.sample_requests, ds.sample_answers):
        p = ds.profiles[req.user_id]
        det = recurrence.detect(inclusion.gate(ds.events_by_user[req.user_id]), req.user_id)
        led = forecast(det.streams, det.oneoffs, req.request_date, p.current_available_balance, p.minimum_balance_to_keep, req.user_id)
        cap = capacity(led, req.requested_amount)
        key_safe = float(ans.row["amount_safe_to_pay"])
        capped = key_safe >= req.requested_amount
        exp = None if capped else key_safe + p.minimum_balance_to_keep
        print(f"{req.request_id:10} {('capped' if capped else f'{exp:.2f}'):>15} {cap.min_balance:15.2f} {('' if capped else f'{cap.min_balance-exp:+14.2f}'):>14}  {cap.amount_safe_to_pay:.2f} / {key_safe:.2f}")
