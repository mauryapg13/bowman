"""amend.py — V1-3. Apply validated message operations to copies of streams / one-offs.

Certificate: shared/amend.certificate.json. Spec §4.6 (FX at the occurrence's
settlement-date row, latest-on-or-before fallback), §4.7, §8 P2 P3.
Runs after recurrence and before the ledger. Never creates a stream or one-off.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta

from inclusion import Event
from load import Message, convert, fx_key, FxRateMissing
from ports.ops import Operation
from recurrence import Amendment, OneOff, Stream


def rate_on_or_before(amount: float, currency: str, home: str, on: date, fx: dict[str, float]) -> tuple[float, date | None]:
    if currency == home:
        return amount, None
    try:
        return convert(amount, currency, home, on, fx), on
    except FxRateMissing:
        pass
    d = on
    for _ in range(400):                                   # spec §4.6 fallback: latest row on or before
        d -= timedelta(days=1)
        k = fx_key(d, currency, home)
        if k in fx:
            return amount * fx[k], d
    raise FxRateMissing(f"no rate on or before {on} for {currency}->{home}")


def _first_predicted_after(s: Stream, after: date) -> date:
    from ledger import _nth_date
    k = 1
    while _nth_date(s, k) <= after:
        k += 1
    return _nth_date(s, k)


def apply(streams: tuple[Stream, ...], oneoffs: tuple[OneOff, ...], events: list[Event], messages: tuple[Message, ...],
          ops_port, fx: dict[str, float], home_currency: str, request_date: date) -> tuple[list[Stream], list[OneOff], list[Operation]]:
    if ops_port is None or not messages:
        return list(streams), list(oneoffs), []
    by_stream = {s.stream_id: s for s in streams}
    by_oneoff = {o.event_id: o for o in oneoffs}
    by_event = {e.event_id: e for e in events}
    applied: list[Operation] = []
    for m in messages:
        rel = None
        if m.related_event_id and m.related_event_id in by_event:
            e = by_event[m.related_event_id]
            rel = {"event_id": e.event_id, "description": e.description, "amount": e.amount, "date": str(e.settlement_date or e.event_date),
                   "status": e.status, "direction": e.direction, "included": e.included}
        stream_view = [{"stream_id": s.stream_id, "category": s.category, "description": s.description, "direction": s.direction,
                        "amount": round(s.amount, 2), "cadence_days": s.cadence_days} for s in by_stream.values()]
        for op in ops_port.operations(m.message_id, m.message_text, rel, stream_view):
            if op.op == "none":
                applied.append(op)
                continue
            if op.target_kind == "stream":
                s = by_stream[op.target_id]                                   # allow-list guarantees presence
                effective = op.effective_date or _first_predicted_after(s, request_date)      # spec §4.7
                if effective <= request_date and not op.ended:
                    effective = _first_predicted_after(s, request_date)
                new_amount, rate_date = (None, None)
                if op.new_amount is not None:
                    new_amount, rate_date = rate_on_or_before(op.new_amount, op.currency or home_currency, home_currency, effective, fx)
                am = Amendment(effective_date=effective, new_amount=new_amount, new_amount_original=op.new_amount,
                               currency=op.currency, rate_date_used=rate_date, ended=op.ended,
                               one_occurrence_only=op.one_occurrence_only, source_message_id=m.message_id, op=op.op)
                by_stream[op.target_id] = replace(s, amendments=s.amendments + (am,),
                                                  provenance=s.provenance + (f"amend:{op.op}:{m.message_id}",))
                applied.append(op)
            elif op.target_kind == "event" and op.target_id in by_oneoff:
                o = by_oneoff[op.target_id]
                if op.op == "cancel":
                    del by_oneoff[op.target_id]
                elif op.op == "delay" and op.effective_date:
                    by_oneoff[op.target_id] = replace(o, date=op.effective_date)
                elif op.op == "amend_amount" and op.new_amount is not None:
                    amt, _ = rate_on_or_before(op.new_amount, op.currency or home_currency, home_currency, o.date, fx)
                    by_oneoff[op.target_id] = replace(o, amount=amt)
                applied.append(op)
            else:
                applied.append(op)          # event target that is not a one-off (e.g. excluded or in a stream): no-op, recorded
    return list(by_stream.values()), sorted(by_oneoff.values(), key=lambda o: (o.date, o.event_id)), applied
