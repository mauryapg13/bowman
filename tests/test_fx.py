"""Currency handling end-to-end — AGENTS.md §6.1, spec §4.6."""
from datetime import date
from pathlib import Path

import pytest

import amend
import amounts
import load as L
import main as M
import plans as PL

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def ds():
    return L.load(ROOT / "dataset")


def test_recorded_foreign_rows_use_their_own_settlement_date_row(ds):
    e = next(x for x in ds.events_by_user["user_25"] if x.event_id == "event_2167")   # USD 1800, IDR user
    assert e.amount == pytest.approx(1800 * ds.fx[L.fx_key(e.settlement_date, "USD", "IDR")])


def test_image_amount_in_foreign_currency_is_converted_after_extraction(ds):
    ports = M.build_ports(PL.RunConfig(vision=True))
    evs = amounts.resolve_amounts(ds.events_by_user["user_78"], ds.images_by_event, ds.fx, "INR", vision=ports.vision)
    e = next(x for x in evs if x.event_id == "event_7307")
    assert (e.amount_original, e.currency) == (33.5, "USD")
    assert e.amount == pytest.approx(33.5 * 83.33)          # 2025-10-01 USD->INR row exists for exactly this event


def test_message_amounts_convert_on_the_occurrence_date_with_fallback(ds):
    assert amend.rate_on_or_before(1804, "EUR", "ZAR", date(2025, 8, 15), ds.fx) == (36080.0, date(2025, 8, 15))
    amt, used = amend.rate_on_or_before(1296, "USD", "INR", date(2026, 9, 20), ds.fx)   # no row on the 20th
    assert used == date(2026, 9, 15) and amt == pytest.approx(1296 * 83.33)
    assert amend.rate_on_or_before(100, "INR", "INR", date(2026, 9, 20), ds.fx) == (100, None)
    with pytest.raises(L.FxRateMissing):
        amend.rate_on_or_before(1, "ZAR", "USD", date(2026, 9, 20), ds.fx)              # pair never quoted


def test_output_amounts_are_home_currency_only(ds):
    for r in list(ds.requests)[:20]:
        for o in ds.options_by_request[r.request_id]:
            assert o.total_payable_amount >= r.requested_amount - 1e-6         # options quoted in the same currency as the request
