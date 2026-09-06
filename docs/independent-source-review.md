# Independent native V3 source acceptance review

Reviewed: 2026-09-06T05:57:44Z. Scope: public official documentation, published schema, current index, one hourly manifest and audit metadata. This review was performed independently of pipeline implementation. No market-data product bytes, production datasets or canary output were downloaded or decoded by this reviewer. It is a source-assumption review, not an implementation or daily-certification approval.

## Verdict

**Product-range acquisition is documented. Certification of complete seven-asset daily price histories remains unproven and must stay gated pending actual evidence.** The intended three products support a depth-free representation of observed quote, mapping and resolution evidence. Their existence, checksums and upstream audit labels alone do not establish target-market completeness or uninterrupted both-side observation history.

This conclusion does not require sender-equivalent replay, matching-engine order or fill simulation. Those are outside Run 1. It concerns the narrower requirement to distinguish reconstructible best-ask states from missing observations and unsupported continuity.

## Verified documentation and metadata

### Product and schema contract

The [native V3 format page](https://archive.pendulumflow.com/formats/v3) describes event-grouped Parquet with separately hashed product byte ranges. `best_bid_ask` is change-driven; `new_market` supplies question, slug and aligned outcomes/token lists; `market_resolved` supplies winner token and label. Documented prices are decimal(9,4), source time milliseconds and archive receipt time microseconds. Use actual footer types when decoding; do not introduce float conversions.

The same page says file partitions follow receipt time, merge sequence is collector-local, and the retained witness is chosen by registry position. Some old hours cannot acquire witness fields, and presence is not contiguous by date. The merge can preserve repeated observations; downstream ask compression must not discard changes in receipt time or provenance.

The [published schema](https://archive.pendulumflow.com/v3/SCHEMA.json) declares `generated_utc=2026-08-28T08:40:13Z`. Its intended products contain no explicit interval-bound fields, per-token subscription status, gap/reset event, or empty-book reason. Therefore interval identity needs validation against real lifecycle rows; null asks and absent rows need explicit unknown treatment unless further native evidence establishes another meaning.

### Current indexed object and integrity support

The [V3 index](https://archive.pendulumflow.com/v3/) observed in this review lists 449 hours through `2026-09-06T00`. The corpus checksum ledger trails the newest published objects; an absent ledger entry is not an absent object. The [explicitly indexed hour page](https://archive.pendulumflow.com/v3/2026-09-06/00/) links the following [manifest](https://archive.pendulumflow.com/v3/2026-09-06/00/manifest.json):

| Product | Half-open byte range | Rows | Published SHA-256 |
| --- | --- | ---: | --- |
| best_bid_ask | [4, 133552403) | 12,403,947 | `fcd6df009401980e88f6269eca4aa51000f6c27c816c58d1b5cf60a49aab1724` |
| market_resolved | [221250256, 221645051) | 3,850 | `7752862ca96a68ff7ad0a10b45652e82b002499217dfb99536684286334ae44d` |
| new_market | [221645051, 221758675) | 1,202 | `c46f2e748f232988be5d312db2635301038246a48feb8145bfb72bc333bf79d3` |

Its layout is `union-event-sorted-v1`; `merger_git_sha` contains `unknown: MERGER_GIT_SHA malformed (not 40-hex)`, not a source commit. Record that unavailability faithfully and bind the observed manifest and transform separately.

These numbers are upstream metadata, not this project's canary measurements. Hash each complete acquired product range, use inclusive HTTP endpoints ending one byte earlier, and validate footer row-group/product correspondence. Partial-range verification must never be reported as whole-file verification. Preserve observed metadata hashes because the upstream archive does not externally sign or anchor historical manifests.

### Coverage limits and known losses

The [hour audit](https://archive.pendulumflow.com/audit/hour/2026-09-06/00) says its target-independent market census is not published. Product `FULL` describes participation by expected capture machines, not continuity for each token. The reported status-feed observation ends at `2026-09-04T14:14Z`; later hours are unobserved by that incident check, not cleared by it. Audit values are stored measurements, not fresh verification of served objects.

The [native coverage criteria](https://archive.pendulumflow.com/audit#per-hour-coverage-v3) require events in every minute across the union of seven products and edges within five seconds. The page explicitly distinguishes this from row completeness. Its [known-loss register](https://archive.pendulumflow.com/audit#known-losses-in-our-own-capture) identifies:

- `2026-08-24T12`: 428 lost lifecycle rows, a historical count that upstream can no longer reproduce.
- `2026-08-24T16:38` to `17:00`: permanently lost lifecycle observations of unknown count.
- `2026-08-26T06:56` to `07:57`: unenumerated genuine feed loss within a longer incident.

The [pending-remerge section](https://archive.pendulumflow.com/audit#short) also identifies 14 hours within `2026-08-23T12` to `2026-08-24T04` that omit a surviving fourth witness; future content changes are expected. These findings apply to required lifecycle dependencies as well as the research day. Their exact effects on the seven-asset universe remain unmeasured here; do not silently dismiss them or fabricate repairs.

The [native corpus audit](https://archive.pendulumflow.com/audit/v3) measures traded-market presence over six preregistered hours. That supplies useful breadth evidence, not a daily target census or a measure of complete quote histories within those markets.

### Corroborating collector contract, with a version limitation

The official [data notes](https://archive.pendulumflow.com/data-notes) link the collector [DATA_MODEL.md, pinned to observed main commit `815388e0c782fe3f026d4a59f5d9447c44e0d13b`](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/DATA_MODEL.md). This contract puts connection/recovery information in logs and uses a fresh book snapshot to start a reconstructible segment. Best-bid/ask notifications are independently observed. Lifecycle observations can also be recovered through Gamma HTTP responses.

This is corroboration from an officially linked collector, not proof that the current native merger deployed that exact commit. Consequently this review does not assign an unrecorded transport type to a lifecycle row. Preserve archive receipt provenance with transport unknown where the native export cannot distinguish it.

## Evidence still required before daily promotion

The Linux canary must independently establish actual range responses, byte counts, throughput, hashes, footer interpretation, exact decoding, seven-asset 5m identity, both token sides, opening-state dependencies and winner evidence. No result in this review substitutes for that work.

For each proposed day, certification additionally needs a target-specific census and evidence sufficient to distinguish known absence from missing observations across each market interval. A pre-opening best-ask observation establishes a prior observed state. It does not, together with aggregate `FULL` or `Audit Pass`, establish that the state remained valid through an unobserved gap.

The precise unresolved source condition is **native V3 target-market/side coverage and boundary evidence sufficient to justify state continuity or delimit unknown segments**. No such published target-level coverage/reset contract was located in the reviewed schema and audit surfaces. If actual native rows and additional published native evidence cannot supply it, transformation code cannot repair that absence. Retain observed events and exclusion reasons, but do not promote a day by silently interpreting silence as unchanged price or an empty ask.

Mapping and resolution dependencies may precede or follow the research day without extending the research interval. Delayed or changed evidence requires selective reassessment and new content identities. Existing certifications from other projects are irrelevant.

## Attribution

Source: PendulumFlow native V3, [archive.pendulumflow.com](https://archive.pendulumflow.com/), offered under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) as stated on its official format and data-notes pages. Review conclusions and downstream transforms belong to this project; they are not upstream certification claims.
