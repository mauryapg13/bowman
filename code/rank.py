"""rank.py — M6. Filter candidates by eligibility and safety, sort, derive status.

Certificate: shared/rank.certificate.json. Spec: project_spec.md §5.
"""
from __future__ import annotations

from dataclasses import replace

import ledger as LG
from load import Profile, Request
from plans import Candidate

AFFORDABLE_NOW = "affordable_now"
AFFORDABLE_WITH_PLAN = "affordable_with_plan"
AFFORDABLE_LATER = "affordable_later"
NOT_AFFORDABLE = "not_affordable"


def _reasons(c: Candidate, profile: Profile, request: Request) -> tuple[str, ...]:
    accepted = set(profile.payment_methods_user_will_consider)
    r: list[str] = []
    if c.method == "wait":
        if "full_payment" not in accepted:
            r.append("wait_requires_full_payment")
    elif c.method not in accepted:
        r.append("method_not_accepted")
    if c.method == "installments":
        months = c.n_payments * ((c.payments[1].day - c.payments[0].day) if c.n_payments > 1 else 0) / 30
        if profile.max_installment_months is None or months > profile.max_installment_months + 1e-9:
            r.append("term_exceeds_max_installment_months")
    if c.method == "partial_payment":
        if not request.allows_partial_payment or not (c.payments[-1].date <= request.desired_completion_date):
            r.append("partial_rule_I5")
    if not c.safe:
        r.append("unsafe")
    return tuple(r)


def annotate(candidates: list[Candidate], profile: Profile, request: Request) -> list[Candidate]:
    out = []
    for c in candidates:
        reasons = _reasons(c, profile, request)
        out.append(replace(c, eligible=not reasons, rejection_reasons=reasons))
    return out


def status_of(chosen: Candidate | None) -> str:
    if chosen is None:
        return NOT_AFFORDABLE
    if chosen.method == "wait":
        return AFFORDABLE_LATER
    if chosen.method == "full_payment" and chosen.first_payment_offset_days == 0 and not chosen.spending_changes:
        return AFFORDABLE_NOW
    return AFFORDABLE_WITH_PLAN


def choose(candidates: list[Candidate], profile: Profile, request: Request,
           cap: LG.Capacity) -> tuple[list[Candidate], Candidate | None, str]:
    annotated = annotate(candidates, profile, request)
    survivors = sorted((c for c in annotated if c.eligible), key=lambda c: c.sort_key)
    chosen = survivors[0] if survivors else None
    return annotated, chosen, status_of(chosen)
