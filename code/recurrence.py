"""recurrence.py — M3. Derive recurring streams from history; the rest are one-offs.

Certificate: shared/recurrence.certificate.json. Spec: project_spec.md §4.2, N6.

Grouping unit is chosen by category (recon: groceries/transport/dining rotate
descriptions and only look regular at category level; everything else is
regular per description). A group is a stream when it has >= 3 included
occurrences and the median consecutive gap is within [5, 35] days.

Absorption (spec §4.2 addendum, measured on the shipped data): 47 users carry
a `scheduled` "Next confirmed salary" row that is the next occurrence of their
payroll stream under a different description (45/47 same amount). Without
absorbing it into the stream the ledger would count that salary twice on the
same day. So after detection, a `scheduled` event with the same (direction,
category) as exactly one stream, dated one cadence (+/-10 days) after that
stream's anchor, joins the stream as its latest *recorded* occurrence. This
never touches settled history and never invents anything: the row exists.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from statistics import median

from inclusion import Event

CATEGORY_LEVEL = frozenset({"groceries", "transport", "dining"})
MIN_OCCURRENCES = 3
GAP_MIN, GAP_MAX = 5, 35
ABSORB_TOLERANCE_DAYS = 10


@dataclass(frozen=True, slots=True)
class Occurrence:
    event_id: str
    date: date
    amount: float


@dataclass(frozen=True, slots=True)
class Amendment:
    """Mirror of shared/types Amendment; produced by amend.py (V1-3)."""
    effective_date: date
    new_amount: float | None
    new_amount_original: float | None
    currency: str | None
    rate_date_used: date | None
    ended: bool
    one_occurrence_only: bool
    source_message_id: str
    op: str


@dataclass(frozen=True, slots=True)
class Stream:
    """FROZEN. Anyone changing a stream returns a new one (spec §7)."""
    stream_id: str
    user_id: str
    direction: str
    category: str
    description: str | None          # None for category-level streams
    cadence_days: int
    amount: float                    # median of occurrences, home currency
    anchor: date                     # latest recorded occurrence
    occurrences: tuple[Occurrence, ...]
    flexibility: str
    minimum_allowed_amount: float | None
    latest_event_id: str
    amendments: tuple[Amendment, ...] = ()
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OneOff:
    event_id: str
    user_id: str
    direction: str
    amount: float
    date: date                       # settlement_date
    category: str
    status: str


@dataclass(frozen=True, slots=True)
class Detection:
    streams: tuple[Stream, ...]
    oneoffs: tuple[OneOff, ...]
    zero_income: bool


def _group_key(e: Event) -> tuple[str, str, str]:
    desc = "" if e.category in CATEGORY_LEVEL else e.description
    return (e.direction, e.category, desc)


def _median_gap(dates: list[date]) -> float:
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    return float(median(gaps))


def _make_stream(user_id: str, ordinal: int, key: tuple[str, str, str], evs: list[Event]) -> Stream | None:
    evs = sorted(evs, key=lambda e: (e.event_date, e.event_id))
    if len(evs) < MIN_OCCURRENCES:
        return None
    gap = _median_gap([e.event_date for e in evs])
    if not (GAP_MIN <= gap <= GAP_MAX):
        return None
    latest = evs[-1]
    return Stream(
        stream_id=f"stream_{user_id}_{ordinal}",
        user_id=user_id,
        direction=key[0],
        category=key[1],
        description=None if key[1] in CATEGORY_LEVEL else key[2],
        cadence_days=int(round(gap)),
        amount=float(median(e.amount for e in evs)),     # type: ignore[arg-type]  (amount is not None: included)
        anchor=latest.event_date,
        occurrences=tuple(Occurrence(e.event_id, e.event_date, e.amount) for e in evs),   # type: ignore[arg-type]
        flexibility=latest.flexibility,
        minimum_allowed_amount=latest.minimum_allowed_amount,
        latest_event_id=latest.event_id,
        provenance=(f"recurrence:{'category' if key[1] in CATEGORY_LEVEL else 'description'}-level n={len(evs)} median_gap={gap:g}",),
    )


def _absorb(streams: list[Stream], leftovers: list[Event]) -> tuple[list[Stream], list[Event]]:
    """Attach scheduled events that are the next occurrence of exactly one
    stream of the same (direction, category). See module docstring."""
    by_cat: dict[tuple[str, str], list[int]] = {}
    for i, s in enumerate(streams):
        by_cat.setdefault((s.direction, s.category), []).append(i)
    remaining: list[Event] = []
    for e in leftovers:
        idxs = by_cat.get((e.direction, e.category), [])
        if e.status != "scheduled" or len(idxs) != 1:
            remaining.append(e)
            continue
        s = streams[idxs[0]]
        delta = (e.event_date - s.anchor).days
        if not (s.cadence_days - ABSORB_TOLERANCE_DAYS <= delta <= s.cadence_days + ABSORB_TOLERANCE_DAYS):
            remaining.append(e)
            continue
        streams[idxs[0]] = replace(
            s,
            anchor=e.event_date,
            occurrences=s.occurrences + (Occurrence(e.event_id, e.event_date, e.amount),),   # type: ignore[arg-type]
            latest_event_id=e.event_id,
            provenance=s.provenance + (f"recurrence:absorbed scheduled {e.event_id} ({e.description!r}) at +{delta}d",),
        )
    return streams, remaining


def detect(events: list[Event] | tuple[Event, ...], user_id: str) -> Detection:
    included = [e for e in events if e.included and e.user_id == user_id]
    groups: dict[tuple[str, str, str], list[Event]] = {}
    for e in included:
        groups.setdefault(_group_key(e), []).append(e)

    streams: list[Stream] = []
    leftovers: list[Event] = []
    for ordinal, key in enumerate(sorted(groups), start=1):
        s = _make_stream(user_id, ordinal, key, groups[key])
        if s is None:
            leftovers.extend(groups[key])
        else:
            streams.append(s)

    streams, leftovers = _absorb(streams, leftovers)

    oneoffs = tuple(
        OneOff(e.event_id, e.user_id, e.direction, e.amount, e.settlement_date, e.category, e.status)   # type: ignore[arg-type]
        for e in sorted(leftovers, key=lambda e: (e.settlement_date, e.event_id))
    )
    zero_income = not any(s.direction == "credit" for s in streams) and \
                  not any(o.direction == "credit" and o.status == "scheduled" for o in oneoffs)
    return Detection(tuple(streams), oneoffs, zero_income)


if __name__ == "__main__":                                       # M3 "done when" printout
    from collections import Counter
    import load, inclusion
    ds = load.load()
    cad = Counter(); zero = 0; absorbed = 0; n_streams = 0; n_oneoffs = 0
    for u, evs in ds.events_by_user.items():
        d = detect(inclusion.gate(evs), u)
        n_streams += len(d.streams); n_oneoffs += len(d.oneoffs); zero += d.zero_income
        for s in d.streams:
            cad[(s.cadence_days // 5) * 5] += 1
            absorbed += any(p.startswith("recurrence:absorbed") for p in s.provenance)
    print(f"streams={n_streams} oneoffs={n_oneoffs} users_zero_income={zero} absorbed_scheduled={absorbed}")
    print("cadence buckets (5-day):", dict(sorted(cad.items())))
    for u in ("user_01", "user_11"):
        d = detect(inclusion.gate(ds.events_by_user[u]), u)
        print(f"\n{u}:")
        for s in d.streams:
            print(f"  {s.stream_id} {s.direction:6} {s.category:18} {str(s.description):32} cad={s.cadence_days:2} amt={s.amount:>12.2f} anchor={s.anchor} latest={s.latest_event_id} n={len(s.occurrences)}")
        print("  one-offs:", [(o.event_id, o.status, o.direction, o.amount) for o in d.oneoffs][-6:])
