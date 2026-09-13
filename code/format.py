"""format.py — M7. Render the eight output cells from fixed templates. No model.

Certificate: shared/format.certificate.json. Spec: project_spec.md §2 formats,
N1; templates derived from all 25 rows of sample_requests.csv (see TEMPLATES).

Number formats observed in the samples:
  amount_safe_to_pay        shortest plain repr      17229139.2 / 25256 / 603.3
  payment_plan amounts      2 dp when fractional     2026-01-03:620.40 / 2024-03-03:25256
  reduce_to amounts         2 dp when fractional     reduce_to:event_1816:23.50 / :665950
  explanation amounts       code + thousands, 2 dp when fractional   ZAR 25,256 / EUR 620.40 / IDR 15,952,906.67
  explanation dates         8 August 2025 (no leading zero)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import ledger as LG
from load import Profile, Request
from plans import Candidate, SpendingChange
from recurrence import Stream


@dataclass(frozen=True, slots=True)
class OutputRow:
    request_id: str
    amount_safe_to_pay: str
    affordability_status: str
    recommended_payment_method: str
    payment_plan: str
    earliest_date_for_full_payment: str
    spending_changes_needed: str
    decision_explanation: str

    def as_list(self) -> list[str]:
        return [self.request_id, self.amount_safe_to_pay, self.affordability_status,
                self.recommended_payment_method, self.payment_plan, self.earliest_date_for_full_payment,
                self.spending_changes_needed, self.decision_explanation]


# --- number / date formatting ------------------------------------------------
def plain(x: float) -> str:
    """Shortest plain representation: 25256 -> '25256', 603.3 -> '603.3'."""
    x = round(x, 2)
    if x == int(x):
        return str(int(x))
    return f"{x:.2f}".rstrip("0").rstrip(".")


def two_dp(x: float) -> str:
    """Two decimals when fractional: 620.4 -> '620.40', 25256 -> '25256'."""
    x = round(x, 2)
    return str(int(x)) if x == int(x) else f"{x:.2f}"


def money(x: float, cur: str) -> str:
    x = round(x, 2)
    body = f"{int(x):,}" if x == int(x) else f"{x:,.2f}"
    return f"{cur} {body}"


def long_date(d: date) -> str:
    return f"{d.day} {d.strftime('%B')} {d.year}"


# --- templates (one per outcome, majority variant where the samples differ) --
TEMPLATES = {
    "affordable_now":   "Pay {amt} today. This leaves at least {min} available over the next 90 days.",
    "installments":     "Use {n} installments of {per}, starting {first}. This leaves at least {min} available.",
    "wait":             "Pay {amt} in full on {date}. Paying earlier would take the balance below the {min} minimum.",
    "partial_payment":  "Pay {a} today and the remaining {b} on {date}. This completes the full request and keeps the {min} minimum protected.",
    "full_with_changes": "{changes}, then pay {amt} today. This leaves at least {min} available.",
    "not_affordable":   "Do not make this payment by {deadline}. None of the available options keeps the {min} minimum protected.",
    "not_affordable_partial_only": "Do not proceed with the {amt} request. Although {safe} is available today, the full amount cannot be completed safely within 90 days.",
}


def _changes_phrase(changes: tuple[SpendingChange, ...], streams_by_id: dict[str, Stream], cur: str) -> str:
    parts = []
    for c in changes:
        s = streams_by_id[c.stream_id]
        name = (s.description or s.category.replace("_", " ")).lower()
        if c.action == "stop":
            parts.append(f"stop the {name}")
        else:
            parts.append(f"reduce the {name} to {money(c.new_amount or 0.0, cur)}")
    text = " and ".join(parts)
    return text[0].upper() + text[1:]


def explanation(request: Request, profile: Profile, chosen: Candidate | None, status: str,
                cap: LG.Capacity, streams_by_id: dict[str, Stream]) -> str:
    cur = profile.home_currency
    mn = money(profile.minimum_balance_to_keep, cur)
    if chosen is None:
        accepted = set(profile.payment_methods_user_will_consider)
        if accepted == {"partial_payment"} and request.allows_partial_payment:
            return TEMPLATES["not_affordable_partial_only"].format(
                amt=money(request.requested_amount, cur), safe=money(cap.amount_safe_to_pay, cur))
        return TEMPLATES["not_affordable"].format(deadline=long_date(request.desired_completion_date), min=mn)
    if chosen.method == "installments":
        return TEMPLATES["installments"].format(n=chosen.n_payments, per=money(chosen.payments[0].amount, cur),
                                                first=long_date(chosen.payments[0].date), min=mn)
    if chosen.method == "wait":
        return TEMPLATES["wait"].format(amt=money(request.requested_amount, cur), date=long_date(chosen.payments[0].date), min=mn)
    if chosen.method == "partial_payment":
        a, b = chosen.payments
        return TEMPLATES["partial_payment"].format(a=money(a.amount, cur), b=money(b.amount, cur), date=long_date(b.date), min=mn)
    if chosen.spending_changes:
        return TEMPLATES["full_with_changes"].format(changes=_changes_phrase(chosen.spending_changes, streams_by_id, cur),
                                                     amt=money(request.requested_amount, cur), min=mn)
    return TEMPLATES["affordable_now"].format(amt=money(request.requested_amount, cur), min=mn)


def render(request: Request, profile: Profile, chosen: Candidate | None, status: str,
           cap: LG.Capacity, streams_by_id: dict[str, Stream]) -> OutputRow:
    if chosen is None:
        plan, method, changes = "none", "not_recommended", "none"
        earliest = ""
    else:
        plan = "|".join(f"{p.date.isoformat()}:{two_dp(p.amount)}" for p in chosen.payments)
        method = chosen.method
        changes = "|".join(f"stop:{c.event_id}" if c.action == "stop" else f"reduce_to:{c.event_id}:{two_dp(c.new_amount or 0.0)}"
                           for c in chosen.spending_changes) or "none"
        earliest = cap.earliest_full_date.isoformat() if cap.earliest_full_date else ""
    return OutputRow(
        request_id=request.request_id,
        amount_safe_to_pay=plain(cap.amount_safe_to_pay),
        affordability_status=status,
        recommended_payment_method=method,
        payment_plan=plan,
        earliest_date_for_full_payment=earliest,
        spending_changes_needed=changes,
        decision_explanation=explanation(request, profile, chosen, status, cap, streams_by_id),
    )
