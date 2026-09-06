# PENDULUMFLOW_V3_OBSERVED policy contract, version 1

Authority: the user's explicit observed-bootstrap policy decision following immutable
checkpoint `run-1-continuity-blocked-v0.2.0`, commit
`2c0062d90f6839516859368542ba3167cc41eadc`. This is additive policy authority.
The old negative continuity evidence remains truthful and unchanged.

This policy is frozen as version 1. A production row schema, encoder, certification
pipeline and window consumer are **not implemented or approved** by this document.
The source review stopped production at the still-required expected-target catalog
gate. This is not a completed observed-bootstrap data release.

## Semantic identity and clocks

Every future canonical record, day, window and consumer handoff must carry literal
`profile=PENDULUMFLOW_V3_OBSERVED`, `profile_version=1`, and its schema/transform
identity. Old `pendulumflow-observed-ask.v1` canary samples have no such authority;
their similar name must not be used as an implicit profile discriminator.

`OWN_RECORDER_EXACT` is a separate, unimplemented future profile. It is never an alias
for this profile, and no version or data authority for that recorder is created here.

Observation qualification uses the venue-reported source-event timestamp, represented
as exact integer microseconds after validating native millisecond precision. It orders
reported observation times, not hypothetical sender receipts or venue causal events
inside a timestamp tie. For an observation with market expiry E and source time t:

`remaining_us = E_us - t_us`

`remaining_seconds = Decimal(remaining_us) / Decimal(1000000)`

Archive collector receipt time, selected witness, witness membership, arrival skew
and collector-local sequence remain separate provenance. Missing values stay explicit.
Sequence never provides a global tie-break; receipt clocks from different witnesses
are never combined into a synthetic global clock. No archive timestamp is relabeled
as sender HTTP receipt, latency, freshness or executable evidence.

## Minimum strict data boundary

Only native V3 `new_market`, `best_bid_ask` and `market_resolved` are permitted.
The minimum representation has distinct typed mapping, observation and resolution
records, with source references into an explicit integrity manifest:

- Mapping: asset, condition/venue market identity, both complementary token IDs,
  ordered UP/DOWN labels and exact UTC five-minute interval bounds with mapping provenance.
- Observation: mapped market and token/outcome, exact source timestamp and remaining
  microseconds, Decimal ask or explicit source-null/unknown reason, exact collector
  receipt/provenance where present, source object/product/hash and physical row identity.
- Resolution: separately identifiable official archived lifecycle evidence with winner
  side/token, exact available timestamps, witness/sequence and source integrity references.

UP and DOWN observations remain independent. An observation of one outcome supplies
no current ask for the opposite outcome; that side is unobserved in that record. A
null ask is not known empty unless native evidence establishes that meaning. A missing
mapping, clock or resolution is an explicit unresolved dependency, never fabricated.

All schemas must have explicit fields and reject additional properties. No quantity,
levels, ladder, cumulative liquidity, imbalance, depth-derived feature, raw payload,
arbitrary extension map or opaque escape hatch is permitted. Source hashes identify
published byte ranges, not hidden depth states. A full book or price-change payload
is not part of the observed canonical representation.

Repeated unchanged-price rows remain distinct when lawful time/provenance differs.
No cadence, interpolation, forward fill, price-state duration or polling observation
is synthesized. Every interval between recorded observations remains continuity-UNKNOWN.

## Recorded-observation affine evaluation

For exact Decimal parameters T, m and b, evaluate only at evidenced observations:

`0 < remaining_seconds < T AND price > m * remaining_seconds + b`

Both inequalities are strict, with no float intermediates. A timer passing a computed
threshold between rows does not create qualification. Missing required evidence makes
the affected decision INDETERMINATE where it could alter the first side/result.

Parameters must be finite base-10 values, with T positive. Mathematical exactness
requires integer-scaled or rational evaluation (or demonstrably sufficient exact
Decimal precision), not implicit Decimal-context rounding of multiplication/addition.
Strict-boundary comparisons must not change because a default precision was exceeded.

For each market/outcome, select the earliest qualifying recorded observation under
the certified source-time ordering. For one market signal, the earlier lawful side
wins; at most one signal exists. Equal qualifying source times across sides fail
closed, with no witness-sequence or receipt-time tie-break. Authority ambiguity or
unresolved ordering capable of changing the winner yields INDETERMINATE. Conflicting
same-time observations remain visible; deterministic file order is not order authority.

“First” means first qualifying recorded observation in the certified, pinned evidence
scope. It never means earliest actual market crossing, proof of no missed excursion,
or hypothetical Stockholm receipt/execution. Both profile identity and this meaning
must be visible to factory qualifications. No factory, sender or recorder is built here.

## What completeness may mean, and the remaining gate

The documented native index is a complete inventory of **served objects**. Reading
all required products in a pinned inventory can therefore establish completeness of
that extraction relative to those exact published bytes. A receipt-day partition can
be explicitly bounded; a later source publication/supersession produces a new generation.
Neither infinite waiting nor venue-emission continuity is required for that finite claim.

The intended certified research day is a **market-start UTC day**, not a receipt day:
eligible markets start within that UTC day, and qualification observations have source
times within each market's `[start, expiry)` interval. Pre-opening history supports
mapping and later history supports resolution; neither extends the research interval.
All required observations/dependencies must be reconciled against the complete pinned
published inventory, including receipt-hour files outside the named market day. No
fixed lookback or event-time/filename equivalence is assumed. The finite receipt-day
extraction described above is a useful component property, not certification of this
market-start-day product. Later additions yield new source generations, not a claim
that the older pinned inventory included future publications.

This does not establish the **expected target-market membership** required by the user.
Native `new_market` rows are lifecycle observations. The inspected official contract
does not declare them an exhaustive expected-target catalog, publish a seven-asset
schedule, or provide a daily expected membership enumeration. Reading every lifecycle
row would give the complete discovered set in that inventory, independent of successful
quote rows. Declaring that set to be the complete expected universe would be an
additional scope change, not a consequence of removing price continuity.

An empirical 7 x 288 grid remains useful diagnostics; it is not a documented catalog
rule. The expected-target gate must be supported before mapping/resolution checks can
be applied to the whole required denominator rather than just its discovered subset.

The narrow blocker is `EXPECTED_TARGET_CATALOG_UNESTABLISHED`. It can be resolved by
native published expected-day membership or an explicit exhaustive catalog/schedule
rule from which seven-asset five-minute membership and exceptions can be verified.
It does not require proof of unchanged asks between observations. The original
continuity blocker must not be used to reject this newly authorized profile.

## Downstream authority remains conditional

Once this source gate and the remaining observed-profile identity, outcome, ordering,
integrity, deterministic-transform and no-depth gates pass, the authorized design uses
all complete certified days below 30 and the latest 30 thereafter. Failed new days
leave the current generation unchanged. Generations must bind the profile, schema,
transform, exact source set and referenced hashes; sealed generations are never changed.

That machinery, production canary, rolling fixtures and autonomous accumulation remain
unimplemented in this checkpoint. Existing immutable source/range/recovery proofs
remain reusable. No successful acquisition was repeated to create this policy record.

See [independent source review](observed-source-review.md) and
[observed source metadata](observed-source-observations.json). Native source attribution:
PendulumFlow V3, CC BY 4.0. This policy is the project's claim, not upstream certification.
