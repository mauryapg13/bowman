"""Every module certificate under shared/ must be well-formed and every $ref
must resolve to a definition in shared/types.schema.json. Standard library only."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED = ROOT / "shared"
TYPES = json.loads((SHARED / "types.schema.json").read_text(encoding="utf-8"))
DEFS = TYPES["$defs"]

REQUIRED_KEYS = {"module", "stage", "spec", "signature", "input", "output", "guarantees", "forbidden"}


def refs(node):
    if isinstance(node, dict):
        if "$ref" in node:
            yield node["$ref"]
        for v in node.values():
            yield from refs(v)
    elif isinstance(node, list):
        for v in node:
            yield from refs(v)


def certificates():
    return sorted(SHARED.glob("*.certificate.json"))


def test_there_is_one_certificate_per_planned_module():
    names = {p.name.replace(".certificate.json", "") for p in certificates()}
    assert names == {
        "load", "amounts", "inclusion", "links", "recurrence", "amend", "ledger",
        "spending", "plans", "rank", "format", "write", "main",
        "ports_vision", "ports_ops", "ports_cache",
        "evaluation_score", "evaluation_ablation", "evaluation_usage",
    }


def test_certificates_have_required_sections():
    for path in certificates():
        doc = json.loads(path.read_text(encoding="utf-8"))
        missing = REQUIRED_KEYS - doc.keys()
        assert not missing, f"{path.name} missing {missing}"
        assert doc["guarantees"] and doc["forbidden"], path.name


def test_every_ref_resolves_to_a_shared_type():
    for path in certificates():
        doc = json.loads(path.read_text(encoding="utf-8"))
        for r in refs(doc):
            assert r.startswith("types.schema.json#/$defs/"), f"{path.name}: {r}"
            assert r.rsplit("/", 1)[1] in DEFS, f"{path.name}: unknown type {r}"


def test_internal_refs_in_types_resolve():
    for r in refs(TYPES):
        assert r.startswith("#/$defs/") and r.rsplit("/", 1)[1] in DEFS, r


def test_output_row_pattern_accepts_all_sample_rows():
    import csv, re
    props = DEFS["OutputRow"]["properties"]
    with open(ROOT / "dataset" / "sample_requests.csv", newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            for col in ("amount_safe_to_pay", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"):
                assert re.fullmatch(props[col]["pattern"], row[col]), (row["request_id"], col, row[col])
            assert row["affordability_status"] in DEFS["AffordabilityStatus"]["enum"]
            assert row["recommended_payment_method"] in DEFS["PaymentMethod"]["enum"]
