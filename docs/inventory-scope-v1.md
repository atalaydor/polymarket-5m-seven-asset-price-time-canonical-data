# Published-V3-inventory certification scope, version 1

This additive user policy resolves the v0.4 historical catalog blocker for
`PENDULUMFLOW_V3_OBSERVED` only. The v0.1 source, v0.2 continuity, v0.3 observed-catalog
and v0.4 historical-membership checkpoints remain truthful evidence for their original
claims. No claim is made that PendulumFlow captured every market Polymarket listed.

A source generation is the exact byte-bound union of two identical complete passes over
every page of the public `/v3/` index plus the raw manifest bytes for every indexed
receipt hour. Index page bytes, parsed hour membership, terminal pagination, manifest
bytes, object identity, product byte ranges, row-group bounds, row counts and product
hashes are retained. A changed page, manifest or product creates a different generation.

The finite generation is scanned in two phases. Every `new_market` row is classified as
in-scope, out-of-scope or ambiguous target-like evidence. The resulting mapping catalog
then filters every `best_bid_ask` and `market_resolved` row across every receipt hour.
Physical row locators and exact range hashes bind every retained row. Market research-day
membership follows the slug's aligned five-minute start, while dependencies may occur in
any receipt hour. Rows outside a market's `[start, expiry)` event-time interval are counted
as ineligible observations; malformed in-scope rows fail the affected day.

A day certifies only when every target mapping discovered in that source generation for
the market-start UTC day has both token identities, at least one non-null recorded ask
for each outcome, unambiguous native `market_resolved` evidence, exact clocks required by
the observation contract, verified product ranges and deterministic output. Missing
resolution is `PENDING`; malformed, contradictory or missing-side evidence is `EXCLUDED`.
No problematic in-scope market is removed to make the rest pass. Upstream audit findings
remain annotations unless they cause one of these explicit finite-inventory gates to fail.

Canonical mapping, observation and resolution schemas use explicit scalar allowlists.
They cannot carry quantity, levels, ladders, liquidity, imbalance, depth features or raw
payloads. Repeated same-price observations keep distinct timestamps and provenance. The
consumer verifies profile/scope values, hashes, mappings, both sides, outcomes and
resolutions across the exact immutable shard graph.

The replay predicate is evaluated with exact rational arithmetic only on recorded rows.
Its result is the earliest qualifying recorded source timestamp. Equal qualifying UP/DOWN
source times fail closed. No persistence, interpolation, missed-excursion exclusion,
actual first-crossing or sender execution claim exists. `OWN_RECORDER_EXACT` remains a
mechanically incompatible future profile.

The scheduled workflow reconciles content-addressed immutable staging before downloads,
publishes immutable day/window manifests, independently reads the complete generation,
then advances the serialized `observed-current` branch. A pending or failed newer day
does not replace an existing current reference. Release objects, rather than workflow
status or expiring artifacts, are the durable authority.
