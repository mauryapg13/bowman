"""write.py — M8. Assert invariants I1–I13, then write output.csv atomically.

Certificate: shared/write.certificate.json. Spec: project_spec.md §2.
A single violation aborts the write; the previous file survives.
"""
from __future__ import annotations

import csv
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from load import COL, PaymentOption, Profile, Request
from format import OutputRow, two_dp

HEADER = COL["output"]
STATUSES = {"affordable_now", "affordable_with_plan", "affordable_later", "not_affordable"}
METHODS = {"full_payment", "partial_payment", "installments", "wait", "not_recommended"}
PLAN_RE = re.compile(r"^(none|\d{4}-\d{2}-\d{2}:\d+(\.\d+)?(\|\d{4}-\d{2}-\d{2}:\d+(\.\d+)?)*)$")
CHANGE_RE = re.compile(r"^(stop:event_\d+|reduce_to:event_\d+:\d+(\.\d+)?)$")


class InvariantViolation(Exception):
    def __init__(self, violations: list["Violation"]):
        super().__init__(f"{len(violations)} invariant violation(s): " + "; ".join(str(v) for v in violations[:5]))
        self.violations = violations


@dataclass(frozen=True, slots=True)
class Violation:
    request_id: str
    invariant: str
    detail: str

    def __str__(self) -> str:
        return f"{self.request_id} {self.invariant}: {self.detail}"


def _plan_items(plan: str) -> list[tuple[str, float]]:
    if plan == "none":
        return []
    return [(p.split(":")[0], float(p.split(":")[1])) for p in plan.split("|")]


def validate_row(row: OutputRow, req: Request, profile: Profile, options: tuple[PaymentOption, ...],
                 flexibility_by_event: dict[str, tuple[str, str]]) -> list[Violation]:
    v: list[Violation] = []
    rid = row.request_id
    def bad(inv: str, detail: str) -> None:
        v.append(Violation(rid, inv, detail))

    safe = float(row.amount_safe_to_pay)
    if not (0 <= safe <= req.requested_amount + 1e-9):
        bad("I1", f"amount_safe_to_pay={safe} requested={req.requested_amount}")
    if row.affordability_status not in STATUSES or row.recommended_payment_method not in METHODS:
        bad("I12", "value outside allowed set")
    if not PLAN_RE.match(row.payment_plan):
        bad("I7", f"plan format {row.payment_plan!r}")
    plan = _plan_items(row.payment_plan) if PLAN_RE.match(row.payment_plan) else []
    dates = [d for d, _ in plan]
    if dates != sorted(dates):
        bad("I7", "plan dates not non-decreasing")
    if row.affordability_status == "affordable_now" and row.earliest_date_for_full_payment != req.request_date.isoformat():
        bad("I2", f"earliest={row.earliest_date_for_full_payment!r}")
    m = row.recommended_payment_method
    if m == "partial_payment":
        if row.affordability_status != "affordable_with_plan":
            bad("I3", row.affordability_status)
        if len(plan) != 2 or abs(plan[0][1] + plan[1][1] - req.requested_amount) > 0.011:
            bad("I4", f"plan={row.payment_plan}")
        elif abs(plan[0][1] - safe) > 0.011 or plan[0][0] != req.request_date.isoformat() or plan[1][0] != row.earliest_date_for_full_payment:
            bad("I4", "first payment must be amount_safe_to_pay on request_date, second on earliest date")
        if not req.allows_partial_payment or not (0 < safe < req.requested_amount) or \
           not row.earliest_date_for_full_payment or row.earliest_date_for_full_payment > req.desired_completion_date.isoformat():
            bad("I5", "partial preconditions")
    if m == "installments":
        ok = False
        for o in options:
            if o.payment_method != "installments":
                continue
            from datetime import timedelta
            exp = [((o.first_payment_date + timedelta(days=(o.payment_frequency_days or 0) * k)).isoformat(), o.payment_amount)
                   for k in range(o.number_of_payments)]
            if len(exp) == len(plan) and all(d == e[0] and abs(a - e[1]) < 0.011 for (d, a), e in zip(plan, exp)):
                ok = True
        if not ok:
            bad("I6", "plan matches no installment option")
    if m != "not_recommended" and m not in profile.payment_methods_user_will_consider and \
       not (m == "wait" and "full_payment" in profile.payment_methods_user_will_consider):
        bad("I8", f"{m} not in {profile.payment_methods_user_will_consider}")
    changes = [] if row.spending_changes_needed == "none" else row.spending_changes_needed.split("|")
    if len(changes) > 3:
        bad("I11", str(len(changes)))
    ids: dict[str, set[str]] = {}
    for c in changes:
        if not CHANGE_RE.match(c):
            bad("I9", f"format {c!r}")
            continue
        action, eid = c.split(":")[0], c.split(":")[1]
        ids.setdefault(eid, set()).add(action)
        flex_cat = flexibility_by_event.get(eid)
        if flex_cat is None:
            bad("I9", f"unknown event {eid}")
            continue
        flex, cat = flex_cat
        if action == "stop" and not (flex in ("stoppable", "reducible_or_stoppable") and cat in profile.expense_categories_user_is_willing_to_stop):
            bad("I9", f"stop not permitted for {eid}")
        if action == "reduce_to" and not (flex in ("reducible", "reducible_or_stoppable") and cat in profile.expense_categories_user_is_willing_to_reduce):
            bad("I9", f"reduce not permitted for {eid}")
        if cat in profile.expense_categories_to_protect:
            bad("I9", f"{eid} is in a protected category")
    if any(len(a) > 1 for a in ids.values()):
        bad("I10", "same event stopped and reduced")
    if row.affordability_status == "not_affordable" and (row.payment_plan != "none" or row.earliest_date_for_full_payment != ""):
        bad("I13", "not_affordable must have plan none and empty date")
    if m == "not_recommended" and row.affordability_status != "not_affordable":
        bad("I13", "not_recommended implies not_affordable")
    return v


def write(rows: list[OutputRow], requests: tuple[Request, ...], profiles: dict[str, Profile],
          options_by_request: dict[str, tuple[PaymentOption, ...]], flexibility_by_event: dict[str, tuple[str, str]],
          path: Path | str = "output.csv") -> int:
    """Validate every row, then temp file -> fsync -> atomic replace. Returns
    the count of rows with amount_safe_to_pay == 0 (smell test)."""
    if [r.request_id for r in rows] != [q.request_id for q in requests]:
        raise InvariantViolation([Violation("*", "I12", "row order/count differs from requests.csv")])
    by_id = {q.request_id: q for q in requests}
    violations: list[Violation] = []
    for r in rows:
        q = by_id[r.request_id]
        violations += validate_row(r, q, profiles[q.user_id], options_by_request[q.request_id], flexibility_by_event)
    if violations:
        raise InvariantViolation(violations)

    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix=".output-", suffix=".csv", dir=path.parent or ".")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, lineterminator="\n")
            w.writerow(HEADER)
            for r in rows:
                w.writerow(r.as_list())
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return sum(1 for r in rows if float(r.amount_safe_to_pay) == 0)
