"""amounts.py — fill blank amounts from images. Pass-through in MVP (V1-2 adds the port).

Certificate: shared/amounts.certificate.json. Spec: project_spec.md §4.6, §4.7, §8.
"""
from __future__ import annotations

from load import ImageRef, RawEvent


def resolve_amounts(events: tuple[RawEvent, ...] | list[RawEvent], images_by_event: dict[str, ImageRef],
                    fx: dict[str, float], vision=None) -> list[RawEvent]:
    if vision is None:
        return list(events)
    raise NotImplementedError("V1-2")
