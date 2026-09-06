# Exact continuity remains a source capability gate

The capability under review is exact target-token best-ask state between observations,
including reset and UTC-boundary dependencies. It is stronger than verifying that the
published observations can be replayed consistently. The frozen canonical contract is
best-ask signal evidence, not configured-size execution or a simulated sender HTTP feed.

## Irreducible gap in currently published evidence

The current native V3 contract has no venue-contiguous token event cursor, source-side
gap/recovery proof, or equivalent evidence that every relevant emitted event reached
at least one accepted capture. Its sequence is assigned locally after admission.
Selected-witness metadata discards the other witnesses' receipt/sequence values, and
the public products lack token subscription/connection epochs and explicit gap resets.
Hour tail duplicate suppression and aggregate product/witness/minute audits establish
narrower properties; they do not certify target continuity or a target-market census.

Transient book anchors and exact level replacement can expose persistent divergence.
They cannot prove that there was no intervening excursion that every witness missed
and that returned to the observed state. A common later non-touch update makes the
next snapshot state and last-change timestamp identical with and without the excursion.
All retained collector counters, witness memberships, hashes and aggregate counts can
also be identical. This counterexample is executable in `tests/test_integrity.py`.
It is not an assertion that a particular real canary interval suffered such a loss.

The [independent source review](continuity-source-review.md) supplies exact native
documentation and pinned collector-code references. The code is corroborating semantics,
not proof of an exact deployed native merger revision. Current native metadata reports
an unknown merger revision; it must remain unknown.

## Failure conditions and continuation

The [daily acceptance contract](daily-acceptance-v1.md) remains unchanged. Missing or
ambiguous target continuity, missing opening anchors, unresolved boundaries, incomplete
target census, unknown clocks, contradictory outcomes, source incidents and failed
integrity all exclude authority. A successful diagnostic job or matching anchor is
insufficient to clear any unsupported condition.

Continue only when FREE native V3 publishes new, content-bound evidence that resolves
the source-side target continuity premise and supplies unambiguous reset/order/seam
semantics. Examples would require an actual venue continuity/recovery contract or
equivalent independently checkable evidence; a new collector-only hash chain over the
same retained rows is insufficient. Then independently review the new evidence and
rerun only source/transform partitions it invalidates. The remaining original market
completeness and complete-day certification gates must also pass before production.

This is a limitation of the currently exported evidence and documented source feed,
not a permanent theorem about every future format bearing the name V3. Surviving
omitted capture may be republished; historical observations lost by every source
cannot be recovered by replaying matching later snapshots. No alternate historical
source, live reconstruction or recorder is authorized as a remedy.

No production acquisition, daily authority, rolling window, mutable current pointer
or scheduled accumulation is enabled by this experiment. The diagnostic's durable
immutable objects are blocker evidence only.
