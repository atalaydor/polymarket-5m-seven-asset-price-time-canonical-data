# PendulumFlow native V3 price-time source proof

This is a new, independent, depth-free acquisition project for Polymarket five-minute
Up/Down BTC, ETH, SOL, XRP, DOGE, BNB and HYPE. Development and control run on Windows;
market payload acquisition and decoding are restricted to standard GitHub-hosted Linux.

**No certified daily or rolling research authority exists.** Source sufficiency is a hard
gate before scaling. Current native V3 coverage documentation does not establish a
target-market census or target-token continuity. The bounded canary measures what is
actually available without turning upstream audit labels into certification.

Only `new_market`, `best_bid_ask` and `market_resolved` product ranges may be acquired.
Full published product-range SHA-256 hashes are checked; a sparse local Parquet combines
those bytes with the footer, and row-group offsets and event types are cross-checked.
This is **not whole-file hash verification**. The reader projects an explicit allowlist;
no depth, quantity, raw payload or synthetic polling observations enter research records.
Equal-price events retain their distinct receipts and provenance. Null asks remain unknown.

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
