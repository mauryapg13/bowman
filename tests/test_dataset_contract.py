"""Contract tests over the shipped dataset — read-only, no pipeline code.

Every number here was measured in docs/dataset_notes.md. If one breaks, the
dataset changed under us and every downstream assumption must be re-checked.
"""
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "dataset"

REQUIRED_HEADER = [
    "request_id", "amount_safe_to_pay", "affordability_status",
    "recommended_payment_method", "payment_plan",
    "earliest_date_for_full_payment", "spending_changes_needed",
    "decision_explanation",
]


def rows(name):
    with open(DATA / name, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def header(name):
    with open(DATA / name, newline="", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def test_output_template_header_is_exact():
    assert header("output.csv") == REQUIRED_HEADER


def test_row_counts():
    assert len(rows("requests.csv")) == 250
    assert len(rows("sample_requests.csv")) == 25
    assert len(rows("financial_profiles.csv")) == 275
    assert len(rows("financial_events.csv")) == 25342
    assert len(rows("request_payment_options.csv")) == 790
    assert len(rows("images.csv")) == 16


def test_sixteen_blank_amounts_each_with_an_image_file():
    blank = {e["event_id"] for e in rows("financial_events.csv") if e["amount"] == ""}
    assert len(blank) == 16
    linked = {i["related_event_id"]: i["image_id"] for i in rows("images.csv")}
    assert set(linked) == blank
    for image_id in linked.values():
        assert (DATA / "media" / "images" / f"{image_id}.png").is_file()


def test_snapshot_fact_no_settled_event_after_request_date():
    """spec §3: current_available_balance already contains every settled event."""
    req = {r["user_id"]: r["request_date"]
           for r in rows("requests.csv") + rows("sample_requests.csv")}
    late = [e["event_id"] for e in rows("financial_events.csv")
            if e["status"] == "settled" and e["event_date"] > req[e["user_id"]]]
    assert late == []


def test_every_foreign_currency_event_has_an_exact_rate_row():
    home = {p["user_id"]: p["home_currency"] for p in rows("financial_profiles.csv")}
    rates = {(r["rate_date"], r["from_currency"], r["to_currency"])
             for r in rows("exchange_rates.csv")}
    missing = [e["event_id"] for e in rows("financial_events.csv")
               if e["currency"] != home[e["user_id"]]
               and (e["settlement_date"], e["currency"], home[e["user_id"]]) not in rates]
    assert missing == []


def test_blank_max_installment_months_means_no_installments():
    """spec §5 filter 2: verified by cross-tab, not assumed."""
    for p in rows("financial_profiles.csv"):
        lists = "installments" in p["payment_methods_user_will_consider"].split("|")
        assert lists == (p["max_installment_months"] != "")


def test_exchange_rates_are_constant_per_pair():
    """spec §4.6: the latest-on-or-before fallback for undated predicted
    occurrences is numerically neutral only while this holds."""
    seen = {}
    for r in rows("exchange_rates.csv"):
        pair = (r["from_currency"], r["to_currency"])
        seen.setdefault(pair, set()).add(r["rate"])
    assert all(len(v) == 1 for v in seen.values()), seen
    assert set(seen) == {("USD", "INR"), ("USD", "IDR"), ("USD", "EUR"), ("EUR", "USD"), ("EUR", "ZAR")}
