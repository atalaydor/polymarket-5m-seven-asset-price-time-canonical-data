# PENDULUMFLOW_V3_OBSERVED_BOUNDED_V1

This temporary profile admits only positively identified seven-asset Polymarket
five-minute Up/Down markets from a content-pinned PendulumFlow V3 generation. Each
admitted market has an exact condition/market mapping, authoritative UP/DOWN token
orientation, recorded best-ask evidence for both tokens, one non-contradictory native
V3 resolution, authenticated provenance and valid canonical rows.

Unidentified retained V3 conditions are `UNRESOLVED_NOT_ADMITTED`. They are represented
by count and content digest and are never called out of scope. Positively identified
targets that fail an individual evidence gate are `REJECTED_TARGET_EVIDENCE` with
per-market reasons. A certified bounded day may therefore contain admitted and rejected
markets without claiming that its admitted population exhausts target markets in V3 or
historical Polymarket listings.

Research evaluates the strict affine predicate only at recorded observations using
integer microseconds and exact decimal/rational arithmetic. First means the earliest
lawfully ordered qualifying recorded observation. Equal or result-changing ambiguous
ordering fails closed. The profile never infers persistence, continuity, cadence or a
crossing between observations.

The immutable day manifest defines a virtual canonical projection: consumers load only
rows whose market is in the content-addressed admitted-market mapping. Referenced source
shards already use the strict depth-free `PENDULUMFLOW_V3_OBSERVED` row schemas. The
bounded window is the authority layer that fixes the evidence population. The verifier
rejects requests for `PENDULUMFLOW_V3_OBSERVED` exhaustive authority or
`OWN_RECORDER_EXACT`.

`OBSERVED_LOSS_COUNT`, `SIGNAL_MARKET_COUNT` and
`MEAN_GROSS_PROFIT_PER_SIGNAL` refer only to the admitted population in the exact pinned
window generation. A later `PROVEN_OPTIMAL` result can mean optimal only for that exact
dataset generation, admitted evidence population, affine strategy space and objective.
