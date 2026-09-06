# Independent source review for PENDULUMFLOW_V3_OBSERVED

Reviewed: 2026-09-06T09:13:46Z against checkout `2c0062d90f6839516859368542ba3167cc41eadc` and current official native V3 public documentation/index metadata. No new market-data payload, probe, server connection or other dataset was used. This document reviews source sufficiency; it is not an implementation or daily-data approval.

## Effect of the accepted policy

The user now accepts an observed-signal product and the earliest lawfully ordered **recorded** qualifying observation. Exact intervening best-ask continuity, proof that no venue update was missed, and sender-equivalent replay are no longer required. The previous continuity non-identifiability argument therefore does **not** block this new profile. It must not be relabelled as an observation-completeness requirement.

The task nevertheless retains complete target-market discovery/mapping across the seven-asset 5-minute universe under documented source/catalog rules, both token identities, native official outcome evidence per market, source integrity, and a truthful complete OBSERVED UTC-day claim. Removing continuity does not by itself replace that expected-market denominator with whichever markets happen to be identified by an acquisition subset.

## Positive source support: a finite published-inventory claim

The official [llms.txt](https://archive.pendulumflow.com/llms.txt), section “The published namespace is the whole namespace,” states that the index inventories every served object. Internal working prefixes are not served. The same document names receipt time as the V3 partition key. This supports a finite, versioned scope: every qualifying recorded row in an explicitly enumerated, content-pinned published inventory at a stated discovery time, filtered by actual archive receipt timestamp to `[day_start, next_day_start)`.

The [V3 index](https://archive.pendulumflow.com/v3/) currently reports 453 hours and 1,272 objects, with witness sidecars through `2026-09-06T04`. Its corpus checksum ledger trails publication, ending at `2026-09-04T16`; newly served hours require their own manifest digests. A ledger subset is therefore not automatically the complete current published inventory.

A source generation can be frozen without waiting forever for future publications. Later source additions or supersessions can create new immutable generations. That is compatible with the accepted policy. It cannot be called a timeless claim about all past/future archive publications. Receipt-day selection must use the actual recorded receipt field, not merely filename or venue event time. Event-time or market-interval grouping would require a separately specified dependency-discovery horizon; it cannot inherit receipt-partition closure silently.

## What the current source does and does not catalog

The [native V3 schema](https://archive.pendulumflow.com/v3/SCHEMA.json) still has `generated_utc=2026-08-28T08:40:13Z`. [Format documentation](https://archive.pendulumflow.com/formats/v3) defines `new_market` as lifecycle observations with market ID, question, slug, aligned outcomes/token lists and times. `market_resolved` carries the winner token/label. Those are usable mapping/outcome inputs where present and consistent. They do not include explicit 5-minute interval-bound fields or a published expected-market schedule.

No rule in the inspected official native format, schema, machine guide, index or audit surfaces declares:

- exactly one eligible market for each asset in every five-minute UTC slot;
- `7 * 288` as an exhaustive daily expected-market count;
- `new_market` as a closed and exhaustive expected-target catalog, including a rule for omissions or exceptions;
- a published completed-catalog-scan watermark or final membership manifest for the target day.

Domain-restricted searches for `5m`, `updown`, `288`, `catalog` and `catalogue` returned no additional official source rule. Negative search results alone are not proof of absence; the conclusion is bounded to the actual schema, index and documented lifecycle contract inspected here. No hidden catalog path was guessed.

The [latest inspected hour audit](https://archive.pendulumflow.com/audit/hour/2026-09-06/04) explicitly states that its per-hour market census output is not published. It identifies product `FULL` through capture-machine contribution. Neither property closes the expected target-market set.

The published [COVERAGE.json](https://archive.pendulumflow.com/v3/COVERAGE.json) is generated at `2026-09-06T08:57:36+00:00`, identifies instrument `tools/coverage/hour_coverage.py, retro over the shipped parquet` and SHA-256 `5bf30658bb552b75d20eea7e19f73f9879c37283239e9d50a2a46d9bae697b3a`, and reports 456 attested hours: 444 complete, 9 partial and 3 refused. The attestation and publication counts differ; attested does not mean served. This metadata describes hour coverage, not a target catalog.

## Lifecycle history and finite dependency handling

The official data notes link the [collector discovery contract, pinned at `815388e0c782fe3f026d4a59f5d9447c44e0d13b`](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/DATA_MODEL.md#market-discovery-and-subscriptions). It documents full active-market scans every 30 minutes, incremental creation scans every 10 seconds and resolution scans every 30 seconds. These are operating cadences, not guaranteed maximum archive publication lateness. Recovered lifecycle rows require usable source creation/closure timestamps. Recovery receipt time records when the HTTP response was obtained.

The contract describes cache watermarks, but the current native published schema/manifest surfaces do not export a completed target-catalog scan with its membership. The linked collector's source is corroboration of semantics, not a claim that the native merger deployed that exact version.

Scanning **all** lifecycle products in a complete pinned inventory is a lawful finite alternative to guessing a fixed 24-hour lookback. Missing outcomes for an identified market can remain pending and be selectively revisited when new native evidence appears. This review does not require a permanent source finality promise before any immutable observed generation can exist. What remains missing is authority for the expected target membership, not a proof that no future observation will arrive.

## Strongest viable source-relative alternative considered

Suppose acquisition exhaustively reads `new_market` across the full pinned native inventory, independently of which markets have quotes, and finds `7 * 288` unique, mutually consistent target slots for one day. Suppose every entry has two valid tokens, its native official outcome, and all relevant published observations are acquired and hashed.

That would be substantially stronger than selecting markets from quotes or treating a sampled hour as a day. It would prove the discovered lifecycle catalog's internal cardinality and observed-row extraction completeness relative to the pinned objects. It would also support a clearly labelled artifact such as “all recorded observations for all target markets discovered in this exact published lifecycle inventory.”

It would **not**, without another source/catalog rule, establish that the empirical grid is the complete expected market universe retained by the task. A count cannot supply its own denominator: the regular cadence might be an observed pattern, while an omitted, differently named, duplicate or exceptional market remains outside the inferred rule. The absence of a mapping cannot itself classify an unknown quoted token as non-target. Such unresolved evidence cannot be silently discarded to preserve the grid.

This is a membership/mapping issue, not the waived question of unseen price excursions. Defining the target catalog to be exactly the discovered lifecycle rows would make the narrower source-relative statement true by construction, but adopting it as the retained **expected-universe** acceptance rule would be an additional policy change. The user's acceptance of OBSERVED alone did not authorize that substitution. This review therefore does not approve it as daily research authority.

## Narrow verdict and continuation condition

**Source status: EXPECTED_TARGET_CATALOG_UNESTABLISHED.** The accepted observed representation and finite published-inventory receipt-day scope are viable. Exact-continuity and venue-row completeness are not required. Current reviewed public native evidence still does not close the unchanged expected target-market discovery/mapping gate, so complete-day authority has not been established under the full remaining task.

The precise missing condition is an applicable native source/catalog membership rule or published target-market enumeration that makes the expected seven-asset 5-minute set checkable, including exceptions and closure at the chosen inventory generation. An expressly approved redefinition to a discovered-lifecycle-only universe would also change the policy question, but it must not be inferred by the implementation. New data probes cannot manufacture a missing normative catalog rule; they can only measure the observed grid and dependencies once an acceptance definition is valid.

No new payload acquisition or certification is approved by this review. Existing checkpoints and historical reviews remain intact, with the old continuity blocker inapplicable to the new OBSERVED policy. The continuation is a source/catalog evidence or explicit scope-definition change, followed by independent review and the necessary affected acquisition checks. It is not another attempt to prove uninterrupted quotes.

Attribution: PendulumFlow native V3, [archive.pendulumflow.com](https://archive.pendulumflow.com/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Acceptance interpretations above are this project's independent review, not upstream certification claims.
