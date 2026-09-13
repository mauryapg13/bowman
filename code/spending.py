"""spending.py — V1-4. Eligible stop / reduce_to actions; apply returns new streams.

Certificate: shared/spending.certificate.json. Spec §6 — a lookup with two gates.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from load import Profile
from plans import SpendingChange
from recurrence import Amendment, Stream

STOPPABLE = {"stoppable", "reducible_or_stoppable"}
REDUCIBLE = {"reducible", "reducible_or_stoppable"}


def eligible_changes(streams: tuple[Stream, ...] | list[Stream], profile: Profile) -> list[SpendingChange]:
    out: list[SpendingChange] = []
    protect = set(profile.expense_categories_to_protect)
    for s in streams:
        if s.direction != "debit" or s.category in protect:
            continue
        if s.flexibility in STOPPABLE and s.category in profile.expense_categories_user_is_willing_to_stop:
            out.append(SpendingChange("stop", s.latest_event_id, s.stream_id, None))
        if s.flexibility in REDUCIBLE and s.category in profile.expense_categories_user_is_willing_to_reduce \
           and s.minimum_allowed_amount is not None and s.minimum_allowed_amount < s.amount:
            out.append(SpendingChange("reduce_to", s.latest_event_id, s.stream_id, s.minimum_allowed_amount))
    out.sort(key=lambda c: (int(c.event_id.rsplit("_", 1)[1]), c.action))
    return out


def apply(streams: tuple[Stream, ...] | list[Stream], changes: tuple[SpendingChange, ...] | list[SpendingChange],
          effective: date = date.min) -> list[Stream]:
    """Copy-on-write: a stop ends the stream from `effective`; a reduce_to sets its amount.
    Recorded occurrences are history and untouched; only predicted occurrences change."""
    by_stream = {c.stream_id: c for c in changes}
    out: list[Stream] = []
    for s in streams:
        c = by_stream.get(s.stream_id)
        if c is None:
            out.append(s)
            continue
        am = Amendment(effective_date=effective, new_amount=None if c.action == "stop" else c.new_amount,
                       new_amount_original=None, currency=None, rate_date_used=None,
                       ended=c.action == "stop", one_occurrence_only=False,
                       source_message_id="message_0", op="spending_change")
        out.append(replace(s, amendments=s.amendments + (am,),
                           provenance=s.provenance + (f"spending:{c.action}:{c.event_id}",)))
    return out
