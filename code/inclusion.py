"""inclusion.py — M2. Decide which raw events are cash movements that count.

Certificate: shared/inclusion.certificate.json. Spec: project_spec.md §4.3
(the gate table), §4.7 (amount_unknown). Reads nothing but the event itself:
links are links.py's job, messages are amend.py's.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from load import RawEvent

# Closed set — mirrors shared/types.schema.json ExclusionReason.
PENDING_CREDIT = "pending_credit"
CANCELLED = "cancelled"
FAILED = "failed"
NON_CASH_UNREALIZED = "non_cash_unrealized"
AMOUNT_UNKNOWN = "amount_unknown"
DUPLICATE_CHARGE = "duplicate_charge"           # set by links.py
SUPERSEDED_BY_LINK = "superseded_by_link"       # set by links.py
PRECEDENCE_RULE_4 = "precedence_rule_4"         # set by links.py


@dataclass(frozen=True, slots=True)
class Event:
    """RawEvent + the gate's verdict. Same fields as RawEvent so downstream
    code reads one shape; `raw` keeps the original for provenance."""
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: float | None
    amount_original: float | None
    currency: str
    event_date: date
    settlement_date: date | None
    status: str
    linked_event_id: str | None
    flexibility: str
    minimum_allowed_amount: float | None
    included: bool
    exclusion_reason: str | None
    provenance: tuple[str, ...] = field(default_factory=tuple)

    def exclude(self, reason: str, note: str) -> "Event":
        """Return a copy marked excluded. Used by links.py; never mutates."""
        return replace(self, included=False, exclusion_reason=reason,
                       provenance=self.provenance + (note,))


def _verdict(e: RawEvent) -> tuple[bool, str | None, str]:
    """The §4.3 table, row by row, first match wins."""
    if e.direction == "non_cash" or e.status == "unrealized":
        return False, NON_CASH_UNREALIZED, "inclusion:non_cash_or_unrealized"
    if e.status == "cancelled":
        return False, CANCELLED, "inclusion:cancelled"
    if e.status == "failed":
        return False, FAILED, "inclusion:failed"
    if e.status == "pending" and e.direction == "credit":
        return False, PENDING_CREDIT, "inclusion:pending_credit_ignored"
    if e.amount is None:
        return False, AMOUNT_UNKNOWN, "inclusion:amount_unknown"        # spec §4.7
    if e.status == "pending":                                             # debit
        return True, None, "inclusion:pending_debit_reserved"
    if e.status in ("settled", "scheduled"):
        return True, None, f"inclusion:{e.status}"
    raise ValueError(f"{e.event_id}: unknown status {e.status!r}")       # programmer error


def gate(events: list[RawEvent] | tuple[RawEvent, ...]) -> list[Event]:
    """One Event per RawEvent, order preserved."""
    out: list[Event] = []
    for e in events:
        included, reason, note = _verdict(e)
        out.append(Event(
            event_id=e.event_id, user_id=e.user_id, event_type=e.event_type,
            description=e.description, category=e.category, direction=e.direction,
            amount=e.amount, amount_original=e.amount_original, currency=e.currency,
            event_date=e.event_date, settlement_date=e.settlement_date, status=e.status,
            linked_event_id=e.linked_event_id, flexibility=e.flexibility,
            minimum_allowed_amount=e.minimum_allowed_amount,
            included=included, exclusion_reason=reason, provenance=(note,),
        ))
    return out


if __name__ == "__main__":                                       # M2 "done when" printout
    from collections import Counter
    import load
    ds = load.load()
    verdicts = gate(list(ds.events()))
    c = Counter(v.exclusion_reason for v in verdicts if not v.included)
    pend = Counter((v.direction, v.included) for v in verdicts if v.status == "pending")
    print("excluded:", dict(c))
    print("pending (direction, included):", dict(pend))
    print("included:", sum(v.included for v in verdicts), "of", len(verdicts))
