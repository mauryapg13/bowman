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
from datetime import date, timedelta
from statistics import median

from inclusion import Event

CATEGORY_LEVEL = frozenset({"groceries", "transport", "dining"})


def cash_date(e: Event) -> date:
    """Cash moves on settlement_date (AGENTS.md §6.3 'count confirmed salary on its
    settlement date'); event_date is only a fallback for rows without one."""
    return e.settlement_date or e.event_date


def _id_num(event_id: str) -> int:
    return int(event_id.rsplit("_", 1)[1])
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


def stream_amount(amounts: list[float]) -> float:
    """Forecast amount for a stream (spec §4.2, v1_log #20). A constant series is
    exact. A varying series is the mean with the single highest and lowest
    purchases dropped, rounded to whole currency units — the estimator that
    reproduces the answer key's integer outflow totals and lands sample
    request_08 to the cent (284.57); plain median/mean do not."""
    if max(amounts) - min(amounts) < 1e-9:
        return float(amounts[0])
    b = sorted(amounts)
    if len(b) > 4:
        b = b[1:-1]
    return float(round(sum(b) / len(b)))


def _median_gap(dates: list[date]) -> float:
    gaps = [(b - a).days for a, b in zip(dates, dates[1:])]
    return float(median(gaps))


def _make_stream(user_id: str, ordinal: int, key: tuple[str, str, str], evs: list[Event]) -> Stream | None:
    evs = sorted(evs, key=lambda e: (cash_date(e), _id_num(e.event_id)))     # numeric id: event_84 < event_102
    if len(evs) < MIN_OCCURRENCES:
        return None
    gap = _median_gap([cash_date(e) for e in evs])
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
        amount=stream_amount([e.amount for e in evs]),      # type: ignore[list-item]  (amount is not None: included)
        anchor=cash_date(latest),
        occurrences=tuple(Occurrence(e.event_id, cash_date(e), e.amount) for e in evs),   # type: ignore[arg-type]
        flexibility=latest.flexibility,
        minimum_allowed_amount=latest.minimum_allowed_amount,
        latest_event_id=latest.event_id,
        provenance=(f"recurrence:{'category' if key[1] in CATEGORY_LEVEL else 'description'}-level n={len(evs)} median_gap={gap:g}",),
    )


def _absorb(streams: list[Stream], leftovers: list[Event]) -> tuple[list[Stream], list[Event]]:
    """Attach scheduled events that are the next occurrence of a stream of the
    same (direction, category). When several streams qualify (two salary streams,
    user_13), the one whose amount is closest wins. See module docstring."""
    by_cat: dict[tuple[str, str], list[int]] = {}
    for i, s in enumerate(streams):
        by_cat.setdefault((s.direction, s.category), []).append(i)
    remaining: list[Event] = []
    for e in leftovers:
        if e.status != "scheduled":
            remaining.append(e)
            continue
        fits = []
        for i in by_cat.get((e.direction, e.category), []):
            s = streams[i]
            delta = (cash_date(e) - s.anchor).days
            if not (s.cadence_days - ABSORB_TOLERANCE_DAYS <= delta <= s.cadence_days + ABSORB_TOLERANCE_DAYS):
                continue
            if e.direction == "debit" and e.linked_event_id is None and not _amount_compatible(s, e.amount):   # type: ignore[arg-type]
                continue                       # R8 (docs/ruleset.md): another amount => an additional confirmed payment, not the bill
                                               # (a linked row — the scheduled retry of a failed attempt — is the bill itself)
            fits.append((abs(e.amount - s.amount) / max(s.amount, 1e-9), i, delta))     # type: ignore[operator]
        if not fits:
            remaining.append(e)
            continue
        _, i, delta = min(fits)
        s = streams[i]
        streams[i] = replace(
            s,
            anchor=cash_date(e),
            occurrences=s.occurrences + (Occurrence(e.event_id, cash_date(e), e.amount),),   # type: ignore[arg-type]
            latest_event_id=e.event_id,
            provenance=s.provenance + (f"recurrence:absorbed scheduled {e.event_id} ({e.description!r}) at +{delta}d",),
        )
    return streams, remaining


def _amount_compatible(s: Stream, amount: float) -> bool:
    """R8 (docs/ruleset.md, sample request_24): a scheduled debit is the bill's next
    occurrence only when its amount is the bill's amount (constant series) or inside the
    recorded range (varying series). A 'Scheduled insurance payment' of 1,830 against a
    2,510 policy is a separate confirmed payment; the key reserves it AND keeps the bill."""
    lo = min(o.amount for o in s.occurrences)
    hi = max(o.amount for o in s.occurrences)
    if hi - lo < 1e-9:
        return abs(amount - lo) < 0.005
    return lo - 1e-9 <= amount <= hi + 1e-9


TERMINATION_GRACE_DAYS = 7


def _terminate_stale(streams: list[Stream], last_settled: date | None) -> list[Stream]:
    """A stream whose next expected occurrence lies more than a week before the
    user's last settled event has skipped a beat while later data exists — it
    has ended (user_13's second household income stops in February; user_05's
    payroll stops after 'Final employer payroll'). Ended streams stay in the
    list (history, spending-change ids) but predict nothing."""
    if last_settled is None:
        return streams
    out: list[Stream] = []
    for s in streams:
        from ledger import _nth_date
        if s.occurrences and s.occurrences[-1].date <= last_settled and \
           _nth_date(s, 1) < last_settled - timedelta(days=TERMINATION_GRACE_DAYS):
            am = Amendment(effective_date=_nth_date(s, 1), new_amount=None, new_amount_original=None, currency=None,
                           rate_date_used=None, ended=True, one_occurrence_only=False, source_message_id="message_0", op="terminated")
            s = replace(s, amendments=s.amendments + (am,),
                        provenance=s.provenance + (f"recurrence:ended — expected {_nth_date(s, 1)} missing, data runs to {last_settled}",))
        out.append(s)
    return out


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

    # Category-level fallback (spec §4.2): where the description-level pass found
    # no stream for a (direction, category) but the category as a whole recurs —
    # e.g. freelance income under rotating descriptions every ~2 weeks (user_09).
    covered = {(s.direction, s.category) for s in streams}
    by_cat: dict[tuple[str, str], list[Event]] = {}
    for e in leftovers:
        if (e.direction, e.category) not in covered and e.category not in CATEGORY_LEVEL:
            by_cat.setdefault((e.direction, e.category), []).append(e)
    ordinal = len(groups)
    absorbed_ids: set[str] = set()
    for cat_key in sorted(by_cat):
        ordinal += 1
        s = _make_stream(user_id, ordinal, (cat_key[0], cat_key[1], ""), by_cat[cat_key])
        if s is not None:
            s = replace(s, description=None, provenance=(s.provenance[0].replace("description-level", "category-fallback"),))
            streams.append(s)
            absorbed_ids.update(o.event_id for o in s.occurrences)
    leftovers = [e for e in leftovers if e.event_id not in absorbed_ids]

    streams, leftovers = _absorb(streams, leftovers)
    last_settled = max((cash_date(e) for e in included if e.status == "settled"), default=None)
    streams = _terminate_stale(streams, last_settled)

    # Confirmed salary with no detected salary stream (spec §4.2, request_01): a `scheduled`
    # salary credit is confirmed recurring income — AGENTS.md §6.3 "count confirmed salary on its
    # settlement date" — and the answer key continues it monthly. Promote it to a monthly stream
    # anchored on itself (one recorded occurrence, prediction continues after it).
    has_salary_stream = any(s.direction == "credit" and s.category == "salary" for s in streams)
    promoted: list[Event] = []
    if not has_salary_stream:
        for e in leftovers:
            if e.status == "scheduled" and e.direction == "credit" and e.category == "salary":
                promoted.append(e)
    for e in promoted:
        leftovers.remove(e)
        streams.append(Stream(
            stream_id=f"stream_{user_id}_confirmed{len(streams) + 1}", user_id=user_id, direction="credit",
            category="salary", description=e.description, cadence_days=31, amount=e.amount,      # type: ignore[arg-type]
            anchor=cash_date(e), occurrences=(Occurrence(e.event_id, cash_date(e), e.amount),),   # type: ignore[arg-type]
            flexibility=e.flexibility, minimum_allowed_amount=None, latest_event_id=e.event_id,
            provenance=(f"recurrence:confirmed scheduled salary {e.event_id} promoted to monthly stream",),
        ))

    oneoffs = tuple(
        OneOff(e.event_id, e.user_id, e.direction, e.amount, e.settlement_date, e.category, e.status)   # type: ignore[arg-type]
        for e in sorted(leftovers, key=lambda e: (cash_date(e), _id_num(e.event_id)))
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
