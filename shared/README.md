# shared/ — module certificates

One JSON file per module, written **before** the module. Each says what goes in,
what comes out, what the module promises, and what it must never do. Modules are
built to fit the certificate, not the other way round.

- `types.schema.json` — every record that crosses a boundary (`Profile`, `RawEvent`,
  `Event`, `Stream`, `OneOff`, `Ledger`, `Capacity`, `Candidate`, `Decision`,
  `VisionResult`, `Operation`, …). JSON Schema draft 2020-12. Defined once, referenced
  everywhere, so `Stream` means the same thing in `recurrence`, `amend`, `ledger` and
  `spending`.
- `<module>.certificate.json` — `module`, `stage`, `spec` (sections it implements),
  `signature`, `input`, `output`, `guarantees`, `forbidden`.

Data flow (arrows are the `output` of one certificate feeding the `input` of the next):

```
load ─► amounts ─► inclusion ─► links ─► recurrence ─► amend ─► ledger ─► plans ─► rank ─► format ─► write
          │                                              │                    │
      ports_vision                                   ports_ops            spending
          └──────────────── ports_cache ─────────────────┘
main.run() composes the chain and returns Decision[]; evaluation_score / evaluation_ablation call run().
```

Conventions fixed here:
- Dates are ISO strings in JSON, `datetime.date` in Python. Money is `float`, home currency
  unless a `currency` field is present.
- `Stream` is frozen. Anything that changes a stream returns a new one.
- Every `Decision` carries `diagnostics` (provenance + `capacity.min_balance`). `write.py`
  ignores it; `score.py` reads it for calibration.
- `RunConfig` flags (`links`, `vision`, `ops`, `spending_changes`) are what `ablation.py` toggles.
  MVP = all false.

`tests/test_shared_certificates.py` checks every `$ref` resolves and that the `OutputRow`
patterns accept all 25 sample rows. When a module lands, its tests should validate real
output against its certificate.
