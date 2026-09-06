# PendulumFlow native V3 price-time source proof

This is a new, independent, depth-free acquisition project for Polymarket five-minute
Up/Down BTC, ETH, SOL, XRP, DOGE, BNB and HYPE. Development and control run on Windows;
market payload acquisition and decoding are restricted to standard GitHub-hosted Linux.

**Current status: no certified daily or rolling research authority exists.** The first
complete production projection is blocked because native observations reference
conditions that lack identity records in the pinned V3 generation. Earlier checkpoints
also preserved separate negative findings about historical venue membership and exact
price continuity; neither is being imposed as the current gate.

The frozen research-facing acquisition path permits only `new_market`, `best_bid_ask`
and `market_resolved` product ranges.
Full published product-range SHA-256 hashes are checked; a sparse local Parquet combines
those bytes with the footer, and row-group offsets and event types are cross-checked.
This is **not whole-file hash verification**. The reader projects an explicit allowlist;
no depth, quantity, raw payload or synthetic polling observations enter research records.
Equal-price events retain their distinct receipts and provenance. Null asks remain unknown.

The separately authorized [continuity experiment](docs/continuity-plan.md) permits
`book` and `price_change` only as transient integrity evidence on a bounded Actions
runner. Its fixed diagnostic export contains no depth and cannot promote research.
The [independent source review](docs/continuity-source-review.md) explains why matching
snapshots and collector-local sequences cannot exclude a missed, reverted excursion.
The original immutable `run-1-source-proof-blocked-v0.1.0` checkpoint is preserved.
The two-hour experiment is complete; exact continuity remains blocked. Its measured
results and continuation condition are in [continuity status](docs/continuity-status.json)
and the [Run 2 consumer handoff](docs/continuity-consumer-handoff.json).

An exact continuity diagnostic pin can be independently read with
`PYTHONPATH=src python tools/verify_continuity.py --tag <exact continuity-probe tag> --sha256 <report digest>`.
This verifier always returns `research_import_allowed=false`; no mutable current
reference is involved. See [implementation review](docs/continuity-implementation-review.md).

`python -m pflow.probe plan` discovers only paths from the published V3 ledger.
`python -m pflow.probe probe --hour YYYY-MM-DD/HH` runs only on Actions Linux and writes
an independently verified native immutable evidence Release. It is not daily authority.
Re-running the exact source/transform partition independently verifies and reuses its sealed
checkpoint without reacquiring market bytes. New source content binds a new identity.

Project-local validation: install `requirements.lock` in `.venv`, set `PYTHONPATH=src`,
then run `python -m unittest discover -s tests -v`, `ruff check .`, `ruff format --check .`,
`mypy`, `python tools/check_workflows.py`, and `git diff --check`.

Source: [PendulumFlow V3](https://archive.pendulumflow.com/formats/v3),
[data notes](https://archive.pendulumflow.com/data-notes),
[machine documentation](https://archive.pendulumflow.com/llms.txt),
[native coverage criteria](https://archive.pendulumflow.com/audit#per-hour-coverage-v3).
Native data is credited to PendulumFlow under CC BY 4.0. The free archive is supported by donations.
This project's projections and proof reports are transformations, not upstream certification.

The subsequent user policy authorizes the separate
[PENDULUMFLOW_V3_OBSERVED v1 profile](docs/observed-profile-v1.md), with source-time
qualification at recorded observations only. It does not require price continuity.
The historical v0.3 [observed-profile source review](docs/observed-source-review.md)
identified an expected-target catalog gate before the later source-inventory scope policy.
See that checkpoint's
[consumer handoff](docs/observed-consumer-handoff.json) for explicit profile and authority flags.

The final additive policy in [inventory scope v1](docs/inventory-scope-v1.md) accepts
the discovered native V3 lifecycle universe as the denominator for this temporary
profile only. The production workflow pins the complete paginated published index and
each manifest, projects only the three allowed products, publishes immutable day/window
generations, and fails closed on unresolved native identities. The first complete
projection found 170,369 condition IDs with no `new_market` classification record in
the same generation. All three assessed days were excluded, so no research window or
current reference exists and scheduled acquisition is disabled. See the
[inventory identity capability gap](docs/inventory-identity-capability-gap.md). This
does not revise the earlier negative continuity or historical venue-catalog findings.
