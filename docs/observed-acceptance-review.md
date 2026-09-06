# Independent acceptance challenge: PENDULUMFLOW_V3_OBSERVED v1

Reviewed 2026-09-06 against baseline
`2c0062d90f6839516859368542ba3167cc41eadc` and the additive observed-profile policy
working files. This review inspected the user's exact retained acceptance wording,
`AGENTS.md`, both profile documents, the independent source review, original daily
gate 1, and the preserved native documentation snapshots. All six source-document
bodies were independently rehashed against `observed-source-observations.json`.
No source payload was acquired, workflow dispatched, dependency installed, or server
contacted by this reviewer.

## Verdict

**The OBSERVED policy is a valid narrower semantic contract. Its source gate remains
`EXPECTED_TARGET_CATALOG_UNESTABLISHED`; no observed production data is approved.**
This conclusion does not reuse the old price-continuity blocker. The new policy removes
the need to prove unchanged state between observations, capture of every venue update,
actual first crossing, or hypothetical sender-equivalent execution.

The remaining gate follows the user's retained requirement for complete discovery and
mapping of markets "expected under the documented source/catalog rules." It is not an
independent requirement invented from the older stricter price-state profile. The
meaning of the expected target membership still needs an applicable native rule or
enumeration; it cannot silently become whichever successfully mapped rows were found.

## Strongest alternative considered

An exhaustive, content-pinned scan of every served native `new_market` product is a
substantial improvement over discovering markets from successful quote rows. If that
scan found one unique, consistently mapped entry in every seven-asset five-minute slot
for a UTC day, and all included observations and official outcomes verified, it would
establish complete extraction of that discovered catalog relative to those exact bytes.
The count would be 2,016 target slots if the hypothesized 7 × 288 grid held.

The reviewer specifically challenged whether this is already enough for the accepted
OBSERVED product. The native [machine guide](https://archive.pendulumflow.com/llms.txt)
supports closure of the **served object inventory**, and the
[format contract](https://archive.pendulumflow.com/formats/v3) describes `new_market`
lifecycle identities and complementary token mappings. Those are positive support for
finite extraction and mapping. They do not, in the inspected material, declare that
the lifecycle rows are the exhaustive expected-target catalog or establish exactly one
eligible venue market per asset per five-minute slot, including membership exceptions.
The inspected [hour audit](https://archive.pendulumflow.com/audit/hour/2026-09-06/04)
does not publish its market census as an alternative denominator.

Accordingly, the empirical grid is evidence about the discovered set, not its own
exhaustive membership rule. Reading every served object proves that no object in that
pinned inventory was skipped; it does not classify an unresolved identity as non-target
or establish that differently named/exceptional target membership is forbidden by the
catalog contract. Silently defining the target set to be exactly the discovered
lifecycle entries would make a useful source-relative artifact possible, but would
change the retained expected-universe rule beyond the user's continuity relaxation.

This is a bounded conclusion from the inspected source surfaces, not a proof that no
future native publication could supply the missing rule. It does **not** require a
permanent publication-finality guarantee, a separate non-native venue API, or proof
that every venue price event reached a collector. A native catalog snapshot with
checkable membership/closure, or an applicable documented exhaustive schedule/catalog
rule reconciled to pinned objects, could resolve it. The frozen old gate's statement
that the grid is diagnostic remains consistent with the new user's explicit wording.

## Scope and semantics reviewed

The initial distinction between receipt-day extraction and a market-start research day
was material. The updated profile now resolves it: research-day membership uses market
start in the UTC day; eligible observation source times are within `[market_start,
expiry)`; and required observations, mapping history and resolutions are reconciled
against the complete finite served inventory at a stated cutoff, including receipt-hour
files outside the named market day. A fixed lookback or filename/event-time equivalence
is not assumed. Later publications can create new immutable generations without making
the old finite inventory claim dishonest.

The chosen qualification clock is the venue-reported source-event timestamp, with its
documented precision converted to integer microseconds. Collector receipts, selected
witness, witness membership and collector-local sequence remain separate provenance.
This is an explicit observed-profile choice, not a claim that source times are sender
HTTP receipts or that equal venue timestamps establish causal ordering.

The policy preserves the strict predicate
`0 < remaining_seconds < T AND price > m * remaining_seconds + b`, evaluated only at
recorded observations. Per-side earliest lawful qualifying observations are compared;
cross-side equal qualifying times fail closed, and result-changing authority/order
ambiguity is INDETERMINATE. At most one signal is permitted per market. Unchanged-price
records with distinct lawful timing/provenance remain available; neither opposite-side
carry nor synthetic timer crossings are authorized.

The arithmetic precision finding was resolved in the policy: parameters must be finite
base-10 values, T must be positive, and scaled-integer/rational arithmetic or demonstrably
sufficient Decimal precision must preserve strict comparisons without default-context
rounding. The policy JSON carries corresponding arithmetic and parameter requirements.
No observed-profile evaluator exists here, so this review verifies the stated requirement
rather than claiming numerical execution has been tested. Counterexamples concerning unobserved
price excursions remain historical evidence for the old profile and must not reject
this newly authorized recorded-observation interpretation.

## Separation, no-depth boundary and actual implementation status

The literal profile/version pair is `PENDULUMFLOW_V3_OBSERVED`, version `1`.
`OWN_RECORDER_EXACT` is a separate unimplemented future profile. Old canary samples named
`pendulumflow-observed-ask.v1` are not implicitly promoted into either profile. The policy
requires future rows, days, windows and consumer handoffs to carry explicit profile and
schema/transform identities.

The new policy permits only `new_market`, `best_bid_ask` and `market_resolved` for
canonical acquisition. Typed mapping, independent outcome observations and official
resolution evidence are required. Null asks remain unknown unless supported otherwise;
no levels, quantities, liquidity/depth feature, payload extension or carry-forward
state is allowed. Earlier transient depth diagnostics create no exception for this
canonical profile.

Git comparison against baseline `2c0062d90f6839516859368542ba3167cc41eadc` found no
changes to source modules, tools, tests, workflows or the original daily acceptance
document. The old pinned consumer still rejects research imports; no new consumer,
production row schema, encoder, daily/window pipeline, rolling authority or autonomous
accumulation was implemented by the additive policy. The policy JSON parses and its
inactive status, profile separation, restricted products and no-authority flags passed
independent checks. `git diff --check` passed. Unchanged implementation tests were not
repeated for this documentation-only review.

## Disposition of the five acceptance challenges

| Challenge | Disposition |
| --- | --- |
| Does exhaustive lifecycle extraction plus a complete empirical 7 × 288 grid close the expected catalog? | It closes the discovered set relative to pinned objects, but the retained documented expected-membership rule is still missing. The narrower blocker stands. |
| Is the old venue-continuity blocker being imposed again? | No. Unrecorded excursions, unchanged state between rows and actual first crossing are explicitly outside this profile. They cannot be used as replacement rejection grounds. |
| Are finite inventory closure, receipt partitions and the research day being conflated? | The policy was clarified: market-start UTC-day membership and source-time eligibility are reconciled across the complete finite published inventory; receipt-hour placement alone is not research-day closure. |
| Are clock roles, strict affine boundaries and first-recorded ordering precise? | Source-event qualification, separate receipt provenance, fail-closed cross-side ties, result-changing ambiguity, no timer/carry synthesis and exact non-rounding finite arithmetic are now explicit policy requirements. No executable evaluator or replay equivalence is claimed. |
| Is profile/no-depth separation truthful about existing authority and implementation? | Yes. Old evidence stays separate and unchanged; current consumers reject research import. New schema/encoder/evaluator, daily/window authority and accumulation are unimplemented. |

**Accepted as a truthful additive policy and narrower blocked checkpoint, not completed
OBSERVED bootstrapping.** Resolving the documented expected-target membership condition
is the next source/policy prerequisite. Implementation and independent daily-object,
recovery, rolling-window and autonomous-progress acceptance remain outstanding after
that prerequisite is met. No new research authority or current-window reference exists.
