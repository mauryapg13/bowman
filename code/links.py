"""links.py — V1-1. Resolve the 58 linked pairs by the seven-pattern lookup.

Certificate: shared/links.certificate.json. Spec: project_spec.md §4.4, §4.5.
Depth is always 1 and there is no fan-out (recon), so each pair is resolved
directly. The row carrying `linked_event_id` is the child (later) row.
"""
from __future__ import annotations

from dataclasses import dataclass

import inclusion as IN
from inclusion import Event

# (parent event_type.status, child event_type.status) -> (pattern, effect)
PATTERNS: dict[tuple[str, str], tuple[str, str]] = {
    ("expense.settled", "refund.settled"): ("refund_settled", "both_count"),
    ("expense.settled", "refund.pending"): ("refund_pending", "exclude_child"),        # already pending_credit
    ("expense.cancelled", "expense.settled"): ("authorization_then_purchase", "exclude_parent"),  # already cancelled
    ("expense.settled", "expense.pending"): ("duplicate_charge", "exclude_child"),
    ("debt_payment.failed", "debt_payment.scheduled"): ("failed_then_retry", "exclude_parent"),   # already failed
    ("investment_purchase.settled", "investment_valuation.unrealized"): ("valuation", "exclude_child"),
    ("investment_purchase.settled", "investment_sale.settled"): ("investment_sale", "both_count"),
}


@dataclass(frozen=True, slots=True)
class LinkResolution:
    parent_id: str
    child_id: str
    pattern: str
    effect: str


def resolve_links(events: list[Event]) -> tuple[list[Event], list[LinkResolution]]:
    by_id = {e.event_id: e for e in events}
    out = {e.event_id: e for e in events}
    resolutions: list[LinkResolution] = []
    for child in events:
        if child.linked_event_id is None:
            continue
        parent = by_id.get(child.linked_event_id)
        if parent is None:                       # cannot happen on shipped data; never drop silently
            resolutions.append(LinkResolution(child.linked_event_id, child.event_id, "unknown", "precedence_ladder"))
            continue
        key = (f"{parent.event_type}.{parent.status}", f"{child.event_type}.{child.status}")
        pattern, effect = PATTERNS.get(key, ("unknown", "precedence_ladder"))
        note = f"links:{pattern}({parent.event_id}->{child.event_id})"
        if effect == "exclude_child" and out[child.event_id].included:
            reason = IN.DUPLICATE_CHARGE if pattern == "duplicate_charge" else IN.SUPERSEDED_BY_LINK
            out[child.event_id] = out[child.event_id].exclude(reason, note)
        elif effect == "exclude_parent" and out[parent.event_id].included:
            out[parent.event_id] = out[parent.event_id].exclude(IN.SUPERSEDED_BY_LINK, note)
        elif effect == "precedence_ladder":
            # §4.5 rule 4: an ambiguous outflow is real, an ambiguous inflow is not.
            if child.direction == "credit" and out[child.event_id].included:
                out[child.event_id] = out[child.event_id].exclude(IN.PRECEDENCE_RULE_4, note)
        # annotate both rows so provenance shows the link even when nothing changed
        for eid in (parent.event_id, child.event_id):
            if note not in out[eid].provenance:
                out[eid] = IN.Event(**{**_fields(out[eid]), "provenance": out[eid].provenance + (note,)})
        resolutions.append(LinkResolution(parent.event_id, child.event_id, pattern, effect))
    return [out[e.event_id] for e in events], resolutions


def _fields(e: Event) -> dict:
    return {f: getattr(e, f) for f in Event.__slots__}   # type: ignore[attr-defined]
