# Independent review: native V3 continuity with transient book replay

Reviewed: 2026-09-06T07:54:17Z. This extends [the earlier source review](independent-source-review.md) for the newly authorized experiment using native `book` and `price_change` transiently on standard GitHub Linux runners. The canonical published representation remains depth-free. The user's explicit authorization for this bounded experiment supersedes the older blanket ingestion restriction in `AGENTS.md`; this review changes neither the publication contract nor any other project.

Scope: current official native V3 documentation, schema, one indexed hour's metadata, and the officially linked collector's pinned semantic source. No historical data products were downloaded or decoded locally. No server was contacted. This document contains a source-identifiability analysis, not a claim about canary results or an approval of publication code.

## Decision

**Transient snapshots and deltas can strengthen observed-state validation and expose defects. They do not, by themselves, make an exact intervening best-ask history identifiable from the currently published native V3 evidence.** A missing price excursion that returns to the observed state can evade the documented integrity checks, aggregate coverage checks, and matching snapshot endpoints.

The limitation is in what the current export and its source capture can demonstrate. It is not a claim that every future product called V3 must have this limitation. Native publication could add independently checkable sequence, recovery and coverage evidence. Historical events that no surviving source ever recorded cannot be recovered merely by changing a transform or publishing stronger metadata.

## Source facts checked again

### Native merge, provenance and hashes

The [native V3 format contract](https://archive.pendulumflow.com/formats/v3#what-sequence-is-not) still identifies `sequence` as collector-local. It describes content-and-occurrence matching across witnesses, preserving repeated observations while selecting one witness's receipt time and sequence by registry position. Physical order is event type, market, token, source timestamp and sequence; it is not one subscriber's receive order.

The [boundary description](https://archive.pendulumflow.com/formats/v3#the-hour-boundary-where-latency-shows-up) uses prior-hour tail keys to remove cross-hour duplicates. That prevents a particular double-counting mechanism; it is not a proof of uninterrupted token observation. [Published range digests](https://archive.pendulumflow.com/formats/v3#what-a-checksum-here-does-and-does-not-prove) check the bytes that were published, not whether uncaptured events existed.

The [data notes](https://archive.pendulumflow.com/data-notes#what-this-data-cannot-tell-you) distinguish the selected witness from every witness that heard a row. Their receipt clocks must not be combined into an exact global clock. `witness_set` permits membership checks for retained observations; it does not restore each member's discarded receipt time and sequence. Filtering `source_witness=a` omits observations heard by a whose retained copy came from another witness. Filtering `witness_set` for a includes those observations but still lacks a's ordering metadata for them.

### Current published metadata has no token continuity chain

The [schema](https://archive.pendulumflow.com/v3/SCHEMA.json), still dated `2026-08-28T08:40:13Z`, includes book levels, level updates, top asks and witness fields. It exposes no venue sequence, per-token predecessor digest, per-witness sequence vector, connection epoch, subscription-status interval, or token-gap marker.

The [2026-09-06T03 index](https://archive.pendulumflow.com/v3/2026-09-06/03/) links the Parquet, manifest, witness-statistics sidecar and checksum ledger. Its [manifest](https://archive.pendulumflow.com/v3/2026-09-06/03/manifest.json) reports:

- `layout=union-event-sorted-v1`, `boundary_guard=cache`;
- `generated_by=tools/orderbook_ab/merge_ab.py`;
- `merger_git_sha=unknown: MERGER_GIT_SHA malformed (not 40-hex)`;
- product hashes, counts, ranges, sequence extrema and aggregate witness accounting.

The sequence note explicitly assigns the kept provenance to the last active domain with the row. No per-token hash chain, source sequence ledger, target subscription ledger or predecessor-hour content binding appeared in these inspected fields. This is a bounded observation of published surfaces, not a claim to have searched private staging or unlinked paths. The manifest's merger filename is not an audited public source-code version.

### Aggregate coverage and supersession are narrower than continuity

The [current hour audit](https://archive.pendulumflow.com/audit/hour/2026-09-06/03) reports 60/60 minutes, 6,607 boundary drops and a successful boundary guard. It defines product `FULL` through expected-machine contribution and says per-hour market census output is unpublished. It also says the hour manifest does not expose remerge attempt history or corpus-level supersession records. Do not use the broader [glossary supersession description](https://archive.pendulumflow.com/glossary#supersession) as proof that a particular hour supplies those records.

The [native audit criteria](https://archive.pendulumflow.com/audit#per-hour-coverage-v3) measure the union's minute presence and hour edges; they expressly allow missing rows within a complete hour. [Known losses and pending remerges](https://archive.pendulumflow.com/audit#known-losses-in-our-own-capture) distinguish irrecoverable lifecycle loss, unenumerated feed loss, and omitted but surviving witness contributions. A later remerge can repair the latter and change hashes. It does not retrospectively prove that every venue event was captured.

The [witness scorecard](https://archive.pendulumflow.com/witnesses) measures product/hour contributions and availability from merged manifests. It has observation floors and held measurements. Its redundancy evidence is useful but supplies no target-token no-gap guarantee.

### Collector sequence allocation and snapshot resets

The official data notes link [collector DATA_MODEL.md](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/DATA_MODEL.md). Its repository main still resolved to `815388e0c782fe3f026d4a59f5d9447c44e0d13b` during this review. This is semantic corroboration, not proof that the native merger deployed that exact source.

In [record.rs, lines 15-59](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/services/polymarket/collector/src/record.rs#L15), the high 16 bits encode publisher generation and the low 48 encode an atomic local counter. `record()` increments that counter when an accepted event receives a record. An event not admitted to the collector has no reserved missing venue number. A contiguous collector counter therefore cannot prove an uninterrupted venue feed. Conversely, sequence gaps within one token or product may simply be other recorded events.

In [connection.rs, lines 357-377](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/services/polymarket/collector/src/ws/connection.rs#L357), disconnects invalidate ready assets. [Lines 479-487](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/services/polymarket/collector/src/ws/connection.rs#L479) log connection gaps. [Lines 735-780](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/services/polymarket/collector/src/ws/connection.rs#L735) admit a book as initialization, reject price deltas before initialization, then allocate a record to accepted events. Rejected parents and discarded pre-snapshot deltas do not receive that counter value. BBA is not restricted by this particular fresh-book branch.

The [collector replay contract](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/DATA_MODEL.md#archive-and-replay) starts with a book, assigns each level update's resulting size, removes zero levels and treats BBA separately. Its [public-feed limit](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/DATA_MODEL.md#limits-of-the-public-feed) states that there is no source replay cursor/sequence to recover missed events. Connection logs are not archive rows. The public source `hash` is removed; the current native schema does not reintroduce an event hash chain.

The pinned [product-specific export contract](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/PARQUET_EXPORT.md#price_changeparquet) explicitly maps `BUY` to bid levels and `SELL` to ask levels for `price_change`. Its size is the new aggregate at that level, not an increment; zero deletes. Optional `best_ask` is a source observation after the change. [events.rs](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/services/polymarket/collector/src/events.rs) parses decimal strings and copies these fields unchanged during fan-out. The native overview's shared side description is less precise: the linked contract separately reserves taker-side terminology for trade events. Use the product-specific semantics for the diagnostic experiment and test them against real anchors; do not report deployed-code equivalence as established.

## What a transient replay can establish

The following are meaningful, testable improvements over reading only BBA:

1. Derive the best ask or an explicitly empty ask side at each accepted snapshot without publishing levels or quantities.
2. Replay accepted deltas from an anchor and compare the resulting state with later accepted snapshots and contemporaneous BBA observations.
3. Detect persistent mismatches, absent opening anchors, inconsistent updates, unsupported ordering, known gaps and missing source dependencies; retain exclusion reasons.
4. Verify exact source values, product hashes and deterministic transformation, then discard transient depth-bearing material before publication.

A successful comparison proves consistency of the observations compared. It is not an independent observation of the interval between them. A new snapshot provides a new anchor; it does not validate an unknown interval before its receipt. Snapshot source time and receipt time have distinct meanings, so neither automatically certifies state at a UTC boundary.

Mixed-witness replay also needs ordering discipline. The retained sequence is not comparable across witnesses. Source timestamps can tie, and receipt clocks differ. If different admissible orders alter a derived state, fail closed rather than using an arbitrary sort as evidence. Even an ordering that produces matching endpoints does not establish complete intervening observation.

## Identifiability counterexample

This is a logical counterexample, not an allegation that a particular canary hour contained it.

Consider two source histories for a token whose observed ask is 0.5000:

- History A contains no intervening best-ask excursion.
- History B contains an added ask at 0.4500 and its later removal, returning the entire book to A's state. Every witness misses those two source events before admission. There are no trades or lifecycle changes in the excursion.

After that interval, both histories contain the same retained non-touch level update and then the same next snapshot and BBA observations. The common final update also makes the snapshot's last-change timestamp identical; comparing only endpoint prices is not the argument. The two hidden events have no venue sequence exposed by this contract, and they never consumed collector counter values. All retained rows, times, selected witnesses, witness sets, local sequences, counts and resulting byte hashes can therefore be identical. Minute coverage and product contribution can also remain identical through other activity.

Yet the histories have different best asks during the hidden interval. The current export supplies no premise excluding a common upstream feed/subscription omission of this kind. A deterministic consumer of identical inputs must reach the same result for both histories; it cannot certify which intervening path occurred. This does not imply arbitrary loss inside a healthy TCP byte stream. The missing evidence is that every relevant source event reached at least one accepted capture, a condition the public-feed contract and aggregate audits do not establish.

Matching full snapshots can detect omitted changes that leave a persistent state difference. They cannot exclude a reverted excursion. More snapshot anchors, more witnesses and agreement among BBA/delta/book products improve empirical confidence and fault detection; they do not change this logical distinction when all products share the missing observations.

## Current gap versus possible future evidence

There are two separate limits:

- **Export sufficiency:** complete retained per-witness event/order information, token subscription/recovery intervals and content-bound seam evidence could make an admitted-observation replay much stronger. Those are absent from the inspected public surfaces, and may exist in upstream private records that this project is not authorized to contact or use.
- **Source completeness:** a collector-issued counter or hash chain proves continuity only after its own observation point. Excluding source events missed by every collector requires a stronger source-side continuity/replay contract or equivalent independent native evidence. Publishing a hash chain over today's incomplete observations alone does not supply that premise.

Future native V3 releases may add such evidence or incorporate surviving missing captures. Reevaluate the actual new contract and content when that occurs; do not declare V3 permanently incapable by name. Conversely, permanently destroyed historical observations cannot be reconstructed from matching later state alone.

Run 1 should measure the authorized transient replay and report observed anchors, comparisons, faults and remaining unknowns. A clean result may justify an accurately named checkpoint for validated observed signals. It must not automatically promote complete exact-continuity days while the missing native target coverage/order condition remains unresolved. Full sender equivalence and execution simulation are not part of this gate.

Source attribution: PendulumFlow native V3, [archive.pendulumflow.com](https://archive.pendulumflow.com/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The identifiability argument and acceptance conclusions are this project's independent analysis, not an upstream certification claim.
