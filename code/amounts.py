"""amounts.py — V1-2. Fill blank amounts from images, then convert to home currency.

Certificate: shared/amounts.certificate.json. Spec §4.6, §4.7, §8. Pass-through when
`vision` is None (MVP). Returns new RawEvent instances; never mutates.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from load import ImageRef, RawEvent, convert, FxRateMissing

REPO_ROOT = Path(__file__).resolve().parents[1]


def resolve_amounts(events: tuple[RawEvent, ...] | list[RawEvent], images_by_event: dict[str, ImageRef],
                    fx: dict[str, float], home_currency: str, vision=None) -> list[RawEvent]:
    if vision is None:
        return list(events)
    out: list[RawEvent] = []
    for e in events:
        img = images_by_event.get(e.event_id) if e.amount is None else None
        if img is None:
            out.append(e)
            continue
        try:
            r = vision.extract(REPO_ROOT / img.path, img.image_id, e.event_id, e.description, e.category, e.event_type)
            on = e.settlement_date or e.event_date
            amount = convert(r.amount, r.currency, home_currency, on, fx)
        except (FxRateMissing, Exception) as exc:                 # spec §4.7: stays None -> amount_unknown
            out.append(e)
            continue
        out.append(replace(e, amount=amount, amount_original=r.amount, currency=r.currency))
    return out
