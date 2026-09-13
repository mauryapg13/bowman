"""main.py — compose the pipeline. `run()` is the only entry point; the CLI wraps it.

Certificate: shared/main.certificate.json. Spec: project_spec.md §7, §10.
Business rules live in the modules, never here.
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import amend as AD
import amounts as AM
import format as FM
import inclusion as IN
import ledger as LG
import links as LK
import load as L
import plans as PL
import rank as RK
import recurrence as RC
import write as WR

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path = REPO_ROOT / ".env") -> None:
    """Minimal .env reader: KEY=VALUE lines, no expansion, never overrides a set variable."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_dotenv()


@dataclass(frozen=True, slots=True)
class Diagnostics:
    capacity: LG.Capacity
    streams: tuple[RC.Stream, ...]
    oneoffs: tuple[RC.OneOff, ...]
    exclusions: tuple[tuple[str, str], ...]
    candidates: tuple[PL.Candidate, ...]
    winning_sort_key: tuple | None
    config: PL.RunConfig
    zero_income: bool
    link_resolutions: tuple = ()
    operations: tuple = ()


@dataclass(frozen=True, slots=True)
class Decision:
    request_id: str
    row: FM.OutputRow
    chosen: PL.Candidate | None
    diagnostics: Diagnostics


@dataclass(frozen=True, slots=True)
class Ports:
    vision: object | None = None
    ops: object | None = None


def build_ports(config: PL.RunConfig) -> Ports:
    """The only place that reads the environment for model access."""
    vision = ops = None
    if config.vision:
        from ports.vision import VisionPort
        vision = VisionPort()
    if config.ops:
        from ports import llm as LLM
        if LLM.provider():
            from ports.ops import OpsPort
            ops = OpsPort()
    return Ports(vision=vision, ops=ops)


def decide(ds: L.Dataset, req: L.Request, config: PL.RunConfig, ports: Ports = Ports()) -> Decision:
    profile = ds.profiles[req.user_id]
    raw = AM.resolve_amounts(ds.events_by_user[req.user_id], ds.images_by_event, ds.fx,
                             profile.home_currency, vision=ports.vision if config.vision else None)
    events = IN.gate(raw)
    link_resolutions: tuple[LK.LinkResolution, ...] = ()
    if config.links:
        events, res = LK.resolve_links(events)
        link_resolutions = tuple(res)
    det = RC.detect(events, req.user_id)
    streams, oneoffs, operations = AD.apply(det.streams, det.oneoffs, events, ds.messages_by_user.get(req.user_id, ()),
                                            ports.ops if config.ops else None, ds.fx, profile.home_currency, req.request_date)
    streams, oneoffs = tuple(streams), tuple(oneoffs)
    led = LG.forecast(streams, oneoffs, req.request_date,
                      profile.current_available_balance, profile.minimum_balance_to_keep, req.user_id)
    cap = LG.capacity(led, req.requested_amount)
    cands = PL.candidates(req, profile, ds.options_by_request[req.request_id], led, cap, streams, oneoffs, config)
    annotated, chosen, status = RK.choose(cands, profile, req, cap)
    streams_by_id = {s.stream_id: s for s in streams}
    row = FM.render(req, profile, chosen, status, cap, streams_by_id)
    diag = Diagnostics(
        capacity=cap, streams=streams, oneoffs=oneoffs, operations=tuple(operations),
        exclusions=tuple((e.event_id, e.exclusion_reason or "") for e in events if not e.included),
        candidates=tuple(annotated), winning_sort_key=chosen.sort_key if chosen else None,
        config=config, zero_income=det.zero_income, link_resolutions=link_resolutions,
    )
    return Decision(req.request_id, row, chosen, diag)


def run(dataset_dir: Path | str = REPO_ROOT / "dataset", requests: tuple[L.Request, ...] | None = None,
        config: PL.RunConfig = PL.MVP, ds: L.Dataset | None = None) -> list[Decision]:
    ds = ds or L.load(dataset_dir)
    reqs = ds.requests if requests is None else requests
    ports = build_ports(config)
    return [decide(ds, r, config, ports) for r in reqs]


def flexibility_index(ds: L.Dataset) -> dict[str, tuple[str, str]]:
    return {e.event_id: (e.flexibility, e.category) for e in ds.events()}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Buy or Wait? — deterministic pipeline")
    ap.add_argument("--dataset", default=str(REPO_ROOT / "dataset"))
    ap.add_argument("--out", default=str(REPO_ROOT / "output.csv"))
    args = ap.parse_args(argv)

    ds = L.load(args.dataset)
    decisions = run(args.dataset, config=PL.FULL, ds=ds)
    zeros = WR.write([d.row for d in decisions], ds.requests, ds.profiles, ds.options_by_request,
                     flexibility_index(ds), args.out)
    from collections import Counter
    print(f"wrote {args.out}: {len(decisions)} rows; amount_safe_to_pay==0 on {zeros} rows (smell test)")
    print("status:", dict(Counter(d.row.affordability_status for d in decisions)))
    print("method:", dict(Counter(d.row.recommended_payment_method for d in decisions)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
