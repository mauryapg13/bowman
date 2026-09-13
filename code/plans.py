"""plans.py — M5. Enumerate every candidate plan and score it (safe? cost? on time?).

Certificate: shared/plans.certificate.json. Spec: project_spec.md §5, §6.
Enumerate, then let rank.py filter and sort. Never an if/elif cascade.
Spending-change variants (V1-5) are generated only when config.spending_changes
is on and no change-free candidate is both safe and on time.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from itertools import combinations

import ledger as LG
from load import PaymentOption, Profile, Request
from recurrence import OneOff, Stream

METHOD_RANK_NONE = ""


@dataclass(frozen=True, slots=True)
class RunConfig:
    links: bool = False
    vision: bool = False
    ops: bool = False
    spending_changes: bool = False
    reapply_settled_past: bool = False      # ablation-only negative control
    variable_first_day: int | None = 5      # variable-spend phase: first occurrence this many days after the request; None = last + cadence
    horizon_days: int = 84                  # forecast/safety window; contract says 90, key behaves as <=86 (ledger.configure)


MVP = RunConfig()
FULL = RunConfig(links=True, vision=True, ops=True, spending_changes=True)   # flipped on as V1 tasks land


@dataclass(frozen=True, slots=True)
class SpendingChange:
    action: str                 # stop | reduce_to
    event_id: str               # = stream.latest_event_id
    stream_id: str
    new_amount: float | None    # minimum_allowed_amount for reduce_to; None for stop


@dataclass(frozen=True, slots=True)
class Payment:
    date: date
    day: int
    amount: float


@dataclass(frozen=True, slots=True)
class Candidate:
    method: str
    payments: tuple[Payment, ...]
    option_id: str | None
    spending_changes: tuple[SpendingChange, ...]
    safe: bool
    total_paid: float
    completes_by_deadline: bool
    first_payment_offset_days: int
    sort_key: tuple
    eligible: bool = True                       # set by rank.py
    rejection_reasons: tuple[str, ...] = ()     # set by rank.py

    @property
    def n_payments(self) -> int:
        return len(self.payments)


def _payments(dates_amounts: list[tuple[date, float]], start: date) -> tuple[Payment, ...]:
    return tuple(Payment(d, (d - start).days, a) for d, a in dates_amounts)


def _candidate(method: str, pays: tuple[Payment, ...], option_id: str | None, changes: tuple[SpendingChange, ...],
               total_paid: float, request: Request, led: LG.Ledger) -> Candidate:
    safe = LG.is_safe(led, [(p.day, p.amount) for p in pays])
    last = max(p.date for p in pays)
    on_time = last <= request.desired_completion_date
    first_offset = min(p.day for p in pays)
    key = (0 if on_time else 1, len(changes), round(total_paid, 2), first_offset, len(pays), option_id or METHOD_RANK_NONE)
    return Candidate(method, pays, option_id, changes, safe, total_paid, on_time, first_offset, key)


def _option_dates(o: PaymentOption) -> list[tuple[date, float]]:
    step = o.payment_frequency_days or 0
    return [(o.first_payment_date + timedelta(days=step * k), o.payment_amount) for k in range(o.number_of_payments)]


def base_candidates(request: Request, options: tuple[PaymentOption, ...], led: LG.Ledger,
                    cap: LG.Capacity, changes: tuple[SpendingChange, ...] = ()) -> list[Candidate]:
    start = request.request_date
    out: list[Candidate] = []
    for o in options:
        pays = _payments(_option_dates(o), start)
        out.append(_candidate(o.payment_method, pays, o.payment_option_id, changes, o.total_payable_amount, request, led))
    # partial_payment: capacity on day 0, remainder on earliest full date (I4/I5 checked in rank)
    if cap.earliest_full_date is not None and 0 < cap.amount_safe_to_pay < request.requested_amount:
        pays = _payments([(start, cap.amount_safe_to_pay),
                          (cap.earliest_full_date, request.requested_amount - cap.amount_safe_to_pay)], start)
        out.append(_candidate("partial_payment", pays, None, changes, request.requested_amount, request, led))
    # wait: full amount on the earliest safe day
    if cap.earliest_full_date is not None and cap.earliest_full_day is not None and cap.earliest_full_day > 0:
        pays = _payments([(cap.earliest_full_date, request.requested_amount)], start)
        out.append(_candidate("wait", pays, None, changes, request.requested_amount, request, led))
    return out


def candidates(request: Request, profile: Profile, options: tuple[PaymentOption, ...],
               led: LG.Ledger, cap: LG.Capacity, streams: tuple[Stream, ...], oneoffs: tuple[OneOff, ...],
               config: RunConfig = MVP) -> list[Candidate]:
    out = base_candidates(request, options, led, cap)
    if not config.spending_changes:
        return out
    if any(c.safe and c.completes_by_deadline for c in out):
        return out
    import spending                                            # V1-4; imported lazily so MVP has no dependency
    eligible = spending.eligible_changes(streams, profile)
    for size in (1, 2, 3):
        for subset in combinations(eligible, size):
            if len({c.stream_id for c in subset}) < size:      # stop and reduce on the same stream: skip
                continue
            new_streams = spending.apply(streams, subset, effective=request.request_date)
            led2 = LG.forecast(new_streams, oneoffs, led.start, led.opening, led.floor, led.user_id, variable_first_day=config.variable_first_day)
            out.extend(base_candidates(request, options, led2, cap, tuple(subset)))
    return out
