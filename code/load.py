"""load.py — M1. Parse the nine dataset CSVs into typed records.

Certificate: shared/load.certificate.json. Spec: project_spec.md §3 (snapshot
fact), §4.6 (FX at load), §4.7 (missing information), §7.

Column names are copied from docs/dataset_notes.md §1 and nowhere else.
This module calls no port, needs no API key, no OCR and no network.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

# --------------------------------------------------------------------------- #
# Verified column names (docs/dataset_notes.md §1). Never invent one.
# --------------------------------------------------------------------------- #
COL = {
    "profiles": {
        "user_id": "user_id",
        "home_currency": "home_currency",
        "balance": "current_available_balance",
        "min_balance": "minimum_balance_to_keep",
        "priorities": "financial_priorities",
        "protect_categories": "expense_categories_to_protect",
        "reduce_categories": "expense_categories_user_is_willing_to_reduce",
        "stop_categories": "expense_categories_user_is_willing_to_stop",
        "accepted_methods": "payment_methods_user_will_consider",
        "max_installment_months": "max_installment_months",
    },
    "events": {
        "event_id": "event_id", "user_id": "user_id", "event_type": "event_type",
        "description": "description", "category": "category", "direction": "direction",
        "amount": "amount", "currency": "currency", "event_date": "event_date",
        "settlement_date": "settlement_date", "status": "status",
        "linked_event_id": "linked_event_id", "flexibility": "flexibility",
        "min_allowed_amount": "minimum_allowed_amount",
    },
    "fx": {"rate_date": "rate_date", "from_currency": "from_currency",
           "to_currency": "to_currency", "rate": "rate"},
    "requests": {
        "request_id": "request_id", "user_id": "user_id", "request_date": "request_date",
        "request_type": "request_type", "requested_amount": "requested_amount",
        "deadline": "desired_completion_date", "allows_partial": "allows_partial_payment",
        "request_text": "request_text",
    },
    "output": [
        "request_id", "amount_safe_to_pay", "affordability_status",
        "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment",
        "spending_changes_needed", "decision_explanation",
    ],
    "options": {
        "option_id": "payment_option_id", "request_id": "request_id",
        "method": "payment_method", "per_payment_amount": "payment_amount",
        "n_payments": "number_of_payments", "first_payment_date": "first_payment_date",
        "frequency_days": "payment_frequency_days", "fee": "financing_fee",
        "total_payable": "total_payable_amount",
    },
    "messages": {
        "message_id": "message_id", "user_id": "user_id", "request_id": "request_id",
        "related_event_id": "related_event_id", "sent_at": "sent_at",
        "source_type": "source_type", "text": "message_text",
    },
    "images": {"image_id": "image_id", "user_id": "user_id",
               "request_id": "request_id", "related_event_id": "related_event_id"},
}

FILES = (
    "financial_profiles.csv", "financial_events.csv", "exchange_rates.csv",
    "requests.csv", "sample_requests.csv", "request_payment_options.csv",
    "messages.csv", "images.csv", "output.csv",
)


class LoadError(Exception):
    """Base class: the dataset does not fit its contract."""


class FxRateMissing(LoadError):
    """No exchange_rates.csv row for (settlement_date, from, to). Spec §4.6/§4.7."""


class SnapshotViolation(LoadError):
    """A settled event is dated after its user's request_date. Spec §3."""


# --------------------------------------------------------------------------- #
# Records — shapes mirror shared/types.schema.json. Frozen: downstream copies.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Profile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: tuple[str, ...]
    expense_categories_to_protect: tuple[str, ...]
    expense_categories_user_is_willing_to_reduce: tuple[str, ...]
    expense_categories_user_is_willing_to_stop: tuple[str, ...]
    payment_methods_user_will_consider: tuple[str, ...]
    max_installment_months: int | None


@dataclass(frozen=True, slots=True)
class RawEvent:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: float | None            # home currency; None iff the CSV cell is blank
    amount_original: float | None   # as written, in `currency`
    currency: str
    event_date: date
    settlement_date: date | None
    status: str
    linked_event_id: str | None
    flexibility: str
    minimum_allowed_amount: float | None


@dataclass(frozen=True, slots=True)
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: float
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str               # untrusted; never parsed for instructions


@dataclass(frozen=True, slots=True)
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: float
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: int | None
    financing_fee: float
    total_payable_amount: float


@dataclass(frozen=True, slots=True)
class Message:
    message_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    sent_at: str
    source_type: str
    message_text: str               # untrusted


@dataclass(frozen=True, slots=True)
class ImageRef:
    image_id: str
    user_id: str
    request_id: str
    related_event_id: str
    path: str


@dataclass(frozen=True, slots=True)
class SampleAnswer:
    """Answer columns of sample_requests.csv. Exposed to evaluation only —
    never handed to a pipeline module (certificate: forbidden)."""
    request_id: str
    row: dict[str, str]
    requested_amount: float
    minimum_balance_to_keep: float


@dataclass(frozen=True, slots=True)
class Dataset:
    profiles: dict[str, Profile]
    events_by_user: dict[str, tuple[RawEvent, ...]]
    requests: tuple[Request, ...]
    sample_requests: tuple[Request, ...]
    sample_answers: tuple[SampleAnswer, ...]
    options_by_request: dict[str, tuple[PaymentOption, ...]]
    messages_by_user: dict[str, tuple[Message, ...]]
    images_by_event: dict[str, ImageRef]
    fx: dict[str, float]            # "YYYY-MM-DD|FROM|TO" -> rate

    def events(self) -> Iterator[RawEvent]:
        for user_events in self.events_by_user.values():
            yield from user_events


# --------------------------------------------------------------------------- #
# Cell parsers. Blank means None — never 0.0, never "".
# --------------------------------------------------------------------------- #
def _num(cell: str) -> float | None:
    return float(cell) if cell != "" else None


def _int(cell: str) -> int | None:
    return int(cell) if cell != "" else None


def _date(cell: str) -> date | None:
    return date.fromisoformat(cell) if cell != "" else None


def _list(cell: str) -> tuple[str, ...]:
    return tuple(cell.split("|")) if cell != "" else ()


def _opt(cell: str) -> str | None:
    return cell if cell != "" else None


def _bool(cell: str) -> bool:
    if cell == "true":
        return True
    if cell == "false":
        return False
    raise LoadError(f"allows_partial_payment must be 'true'/'false', got {cell!r}")


def _id_num(identifier: str) -> int:
    return int(identifier.rsplit("_", 1)[1])


def _rows(path: Path) -> list[dict[str, str]]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# --------------------------------------------------------------------------- #
# FX — spec §4.6. One function for the whole codebase.
# --------------------------------------------------------------------------- #
def fx_key(rate_date: date, from_currency: str, to_currency: str) -> str:
    return f"{rate_date.isoformat()}|{from_currency}|{to_currency}"


def convert(amount: float, currency: str, home_currency: str,
            on: date, fx: dict[str, float]) -> float:
    """Convert `amount` from `currency` to `home_currency` using the rate row
    dated `on`. Exact match only — spec §4.7 says a recorded event without a
    row is a hard error. (The latest-on-or-before fallback for *predicted*
    dates lives in amend/ledger, not here.)"""
    if currency == home_currency:
        return amount
    key = fx_key(on, currency, home_currency)
    if key not in fx:
        raise FxRateMissing(f"no rate for {key}")
    return amount * fx[key]


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def _load_profiles(path: Path) -> dict[str, Profile]:
    c = COL["profiles"]
    out: dict[str, Profile] = {}
    for r in _rows(path):
        p = Profile(
            user_id=r[c["user_id"]],
            home_currency=r[c["home_currency"]],
            current_available_balance=float(r[c["balance"]]),
            minimum_balance_to_keep=float(r[c["min_balance"]]),
            financial_priorities=_list(r[c["priorities"]]),
            expense_categories_to_protect=_list(r[c["protect_categories"]]),
            expense_categories_user_is_willing_to_reduce=_list(r[c["reduce_categories"]]),
            expense_categories_user_is_willing_to_stop=_list(r[c["stop_categories"]]),
            payment_methods_user_will_consider=_list(r[c["accepted_methods"]]),
            max_installment_months=_int(r[c["max_installment_months"]]),
        )
        out[p.user_id] = p
    return out


def _load_fx(path: Path) -> dict[str, float]:
    c = COL["fx"]
    return {
        fx_key(date.fromisoformat(r[c["rate_date"]]), r[c["from_currency"]], r[c["to_currency"]]): float(r[c["rate"]])
        for r in _rows(path)
    }


def _load_events(path: Path, profiles: dict[str, Profile],
                 fx: dict[str, float]) -> dict[str, tuple[RawEvent, ...]]:
    c = COL["events"]
    by_user: dict[str, list[RawEvent]] = {}
    for r in _rows(path):
        user_id = r[c["user_id"]]
        home = profiles[user_id].home_currency
        currency = r[c["currency"]]
        original = _num(r[c["amount"]])
        settlement = _date(r[c["settlement_date"]])
        if original is None:
            amount = None                       # spec §4.7: blank ≠ 0; amounts.py may fill
        elif currency == home:
            amount = original
        else:
            # AGENTS.md §6.1: the row for the settlement date. Non-cash rows have no settlement
            # date (they are excluded later anyway); use the event date so loading never depends
            # on a row that carries no cash.
            amount = convert(original, currency, home, settlement or date.fromisoformat(r[c["event_date"]]), fx)
        ev = RawEvent(
            event_id=r[c["event_id"]],
            user_id=user_id,
            event_type=r[c["event_type"]],
            description=r[c["description"]],
            category=r[c["category"]],
            direction=r[c["direction"]],
            amount=amount,
            amount_original=original,
            currency=currency,
            event_date=date.fromisoformat(r[c["event_date"]]),
            settlement_date=settlement,
            status=r[c["status"]],
            linked_event_id=_opt(r[c["linked_event_id"]]),
            flexibility=r[c["flexibility"]],
            minimum_allowed_amount=_num(r[c["min_allowed_amount"]]),
        )
        by_user.setdefault(user_id, []).append(ev)
    return {
        u: tuple(sorted(evs, key=lambda e: (e.event_date, _id_num(e.event_id))))
        for u, evs in by_user.items()
    }


def _request(r: dict[str, str]) -> Request:
    c = COL["requests"]
    return Request(
        request_id=r[c["request_id"]],
        user_id=r[c["user_id"]],
        request_date=date.fromisoformat(r[c["request_date"]]),
        request_type=r[c["request_type"]],
        requested_amount=float(r[c["requested_amount"]]),
        desired_completion_date=date.fromisoformat(r[c["deadline"]]),
        allows_partial_payment=_bool(r[c["allows_partial"]]),
        request_text=r[c["request_text"]],
    )


def _load_samples(path: Path, profiles: dict[str, Profile]) -> tuple[tuple[Request, ...], tuple[SampleAnswer, ...]]:
    reqs, answers = [], []
    for r in _rows(path):
        req = _request(r)
        reqs.append(req)
        answers.append(SampleAnswer(
            request_id=req.request_id,
            row={k: r[k] for k in COL["output"]},
            requested_amount=req.requested_amount,
            minimum_balance_to_keep=profiles[req.user_id].minimum_balance_to_keep,
        ))
    return tuple(reqs), tuple(answers)


def _load_options(path: Path) -> dict[str, tuple[PaymentOption, ...]]:
    c = COL["options"]
    by_req: dict[str, list[PaymentOption]] = {}
    for r in _rows(path):
        o = PaymentOption(
            payment_option_id=r[c["option_id"]],
            request_id=r[c["request_id"]],
            payment_method=r[c["method"]],
            payment_amount=float(r[c["per_payment_amount"]]),
            number_of_payments=int(r[c["n_payments"]]),
            first_payment_date=date.fromisoformat(r[c["first_payment_date"]]),
            payment_frequency_days=_int(r[c["frequency_days"]]),
            financing_fee=float(r[c["fee"]]),
            total_payable_amount=float(r[c["total_payable"]]),
        )
        by_req.setdefault(o.request_id, []).append(o)
    return {k: tuple(sorted(v, key=lambda o: _id_num(o.payment_option_id))) for k, v in by_req.items()}


def _load_messages(path: Path) -> dict[str, tuple[Message, ...]]:
    c = COL["messages"]
    by_user: dict[str, list[Message]] = {}
    for r in _rows(path):
        m = Message(
            message_id=r[c["message_id"]],
            user_id=r[c["user_id"]],
            request_id=_opt(r[c["request_id"]]),
            related_event_id=_opt(r[c["related_event_id"]]),
            sent_at=r[c["sent_at"]],
            source_type=r[c["source_type"]],
            message_text=r[c["text"]],
        )
        by_user.setdefault(m.user_id, []).append(m)
    return {k: tuple(sorted(v, key=lambda m: _id_num(m.message_id))) for k, v in by_user.items()}


def _load_images(path: Path, dataset_dir: Path) -> dict[str, ImageRef]:
    c = COL["images"]
    out: dict[str, ImageRef] = {}
    for r in _rows(path):
        img = ImageRef(
            image_id=r[c["image_id"]],
            user_id=r[c["user_id"]],
            request_id=r[c["request_id"]],
            related_event_id=r[c["related_event_id"]],
            path=str(Path("dataset") / "media" / "images" / f"{r[c['image_id']]}.png"),
        )
        out[img.related_event_id] = img
    return out


def _assert_snapshot(events_by_user: dict[str, tuple[RawEvent, ...]],
                     requests: tuple[Request, ...]) -> None:
    """Spec §3 guard 1: current_available_balance already contains every
    settled event, which is only coherent if no settled event post-dates the
    request. Users without a request are not checked."""
    request_date = {r.user_id: r.request_date for r in requests}
    late = [
        e.event_id
        for u, evs in events_by_user.items() if u in request_date
        for e in evs
        if e.status == "settled" and e.event_date > request_date[u]
    ]
    if late:
        raise SnapshotViolation(f"settled events after request_date: {late[:10]}{'...' if len(late) > 10 else ''}")


def load(dataset_dir: Path | str = "dataset") -> Dataset:
    """Load all nine files. Raises LoadError (FxRateMissing, SnapshotViolation)
    rather than returning a partial Dataset."""
    d = Path(dataset_dir)
    for name in FILES:
        if not (d / name).is_file():
            raise LoadError(f"missing {d / name}")

    profiles = _load_profiles(d / "financial_profiles.csv")
    fx = _load_fx(d / "exchange_rates.csv")
    events_by_user = _load_events(d / "financial_events.csv", profiles, fx)
    requests = tuple(_request(r) for r in _rows(d / "requests.csv"))
    sample_requests, sample_answers = _load_samples(d / "sample_requests.csv", profiles)
    options_by_request = _load_options(d / "request_payment_options.csv")
    messages_by_user = _load_messages(d / "messages.csv")
    images_by_event = _load_images(d / "images.csv", d)

    for req in requests + sample_requests:
        if req.request_id not in options_by_request:
            raise LoadError(f"{req.request_id} has no payment options")   # spec §4.7
    _assert_snapshot(events_by_user, requests + sample_requests)

    return Dataset(
        profiles=profiles,
        events_by_user=events_by_user,
        requests=requests,
        sample_requests=sample_requests,
        sample_answers=sample_answers,
        options_by_request=options_by_request,
        messages_by_user=messages_by_user,
        images_by_event=images_by_event,
        fx=fx,
    )


if __name__ == "__main__":                                       # M1 "done when" printout
    ds = load()
    evs = list(ds.events())
    print(f"profiles={len(ds.profiles)} events={len(evs)} "
          f"blank_amount={sum(e.amount is None for e in evs)} "
          f"converted={sum(e.amount is not None and e.currency != ds.profiles[e.user_id].home_currency for e in evs)} "
          f"requests={len(ds.requests)} samples={len(ds.sample_requests)} "
          f"options={sum(len(v) for v in ds.options_by_request.values())} "
          f"messages={sum(len(v) for v in ds.messages_by_user.values())} images={len(ds.images_by_event)}")
