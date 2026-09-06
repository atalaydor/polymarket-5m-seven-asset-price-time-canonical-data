# Independent implementation review: inventory-scoped OBSERVED production

## Authorization and baseline

This review applies to the user's newly authorized `PENDULUMFLOW_V3_OBSERVED`
inventory scope. A certified UTC day is a complete deterministic projection of the
seven-asset five-minute Up/Down markets present in its pinned published native V3
inventory/source generation, with lawful mapping, observation integrity and native
official resolution. It does not assert exhaustive historical venue listing,
continuity between observations, absence of missed observations, mathematical
time-only execution, or hypothetical sender receipts. The old historical-catalog
blocker is not imposed as a production gate for this separately identified scope.

Initial inspected baseline: `2b51b798c9cd7d689b94957ba2c775e00f95e8d3`.
The existing source, model, probe, release, consumer and workflow files implement
bounded diagnostics and safe immutable evidence publication. They do not yet implement
production day/window certification, a persistent production backlog, scheduled
accumulation or a research consumer. Earlier independent checks and immutable
diagnostics remain valid within their original scopes; they are not relabeled here.

The reviewer owns only this document for this implementation phase. No production
implementation, source acquisition, workflow dispatch or server connection is performed
by this review. Findings below are concrete implementation requirements, not a new
source-capability refusal. They will be updated against the actual production code.

## Findings requiring resolution in production

| Priority | Observed baseline / risk | Required implementation evidence |
| --- | --- | --- |
| High | `Reader.inventory()` silently skips unparsed ledger lines and overwrites duplicate paths. A partial parser must not become a complete inventory claim. | Freeze the raw source ledger and a strict, deterministic parsed inventory. Reject conflicting duplicate entries and unexplained malformed or unsupported in-scope entries. Explicitly identify any documented out-of-scope entries. Bind every selected manifest and product digest. |
| High | `probe.run()` uses fixed history/after limits and acquires best asks only for the center hour. | Define the research day and finite inventory dependency closure precisely. Enumerate every relevant observation, mapping and resolution partition within that pinned scope, including required off-day mapping/resolution evidence. A fixed lookback cannot stand in for exhaustive declared scope. |
| High | The old model's certification function requires continuity and an independent venue universe, while its consumer rejects every research import. | Add a separately versioned inventory-scoped schema and acceptance function. Preserve the old gates, immutable reports and old consumer behavior; new consumer approval must require an actual verified inventory-scoped window. |
| High | Existing canary partition IDs include the full current Git commit and context manifests. This repeats unrelated successful work after unrelated changes. | Separate acquisition product identities from mapping/certification identities. Source-content changes invalidate only dependent partitions. Bind the relevant transform and pinned dependencies; do not use unrelated documentation edits or a growing root inventory as reasons to reacquire unchanged products. |
| High | Immutable release publication verifies complete asset sets, but does not implement a rolling reference or concurrent backlog coordinator. | Shards publish immutable outputs only. A reconciler reads durable state, verifies all referenced content and updates current under a serialized or compare-and-swap protocol with an explicit freshness rule. Late workers must not replace newer day revisions, newer source plans or a newer window. |
| High | Existing workflows are manual source/catalog probes. No scheduled production planner or durable cursor exists. | Scheduled discovery/catch-up must independently reread durable backlog state on every tick, select bounded missing/failed work, and continue past workflow/matrix limits. Do not depend on a token-authored push triggering another workflow. Preserve successful siblings and prove selective retry with real durable outputs. |
| Medium | `fetch_products()` proves product-range hashes and footer consistency, not a complete Parquet-file hash. | Retain the exact distinction in canonical provenance: published product bytes verified, footer bytes observed/pinned, whole-file verification false unless every byte is actually verified. Streaming larger products must finish the full published product digest before accepting decoded output. |
| Medium | `release.publish()` safely fails closed on unexpected partial staging, but its caller must supply a reproducible complete payload set. | Define restart behavior for unfinished drafts and pre-upload runner loss. Reuse verified durable payloads and regenerate deterministic metadata. Do not confuse sealed failed-diagnostic reuse with an autonomous production retry mechanism. |

The day definition needs particular care. The earlier OBSERVED policy used a market's
start UTC day, while native objects are organized by archive receipt hour. If that
market-start definition is retained, the inventory plan must bind which other receipt
hours can contribute recorded observations or dependencies. If a receipt-hour day is
chosen instead, that is a distinct explicit data scope and cannot silently inherit
the previous market-start-day description. A source cutoff is part of the scope, not
a promise that future inventory additions cannot contain delayed evidence.

## Deterministic projection and strict no-depth contract

The native products remain `new_market`, `best_bid_ask` and `market_resolved`. Other
products, first-party catalog prices/winners, historic depth diagnostics and external
datasets cannot supply canonical observations or official resolution. A complete
projection must account for all in-scope rows and every excluded or uninterpretable
identity. A broad parse exception followed by `continue` is insufficient if it can
discard an ambiguous target market from a certified day.

Mapping conflicts must be evaluated on actual identity: condition, asset, interval,
complementary token identities and their aligned labels. Repeated lifecycle records
with different receipt provenance must not be lost; changes in descriptive question
text alone should not manufacture a token-identity contradiction. Ambiguous native
target identities must fail closed, with reasons available for inspection.

The canonical research schema must have an explicit field allowlist, exact scalar
types and no raw-payload extension. Quantity, size, ladders, liquidity, imbalance and
depth-derived features remain prohibited. Prices must retain their native decimal
values without float conversion; native millisecond event timestamps and microsecond
receipt timestamps must retain their actual precision and clock roles. Original
source object/product identity and product-row position must survive transformation.

Preserve every required ordering/provenance observation even when the best ask is
unchanged. Sorting rows deterministically by source/object/row coordinates is a byte
serialization choice, not proof of cross-witness chronological authority. Witness-local
sequence values cannot become a global clock. Identical price/clock fields at distinct
source row positions must not be deduplicated merely because they look redundant.

A source-null ask, no recorded observation for one side in the pinned inventory,
an explicit known unavailable state, and evidence missing because a required shard
failed are different conditions. The inventory scope permits an honest declaration
of the first two without inferring a venue state; it does not permit failed work or
unresolved target identity to be relabeled as a complete empty projection. The two
token identities and separately identifiable native resolution evidence remain bound
to every included market. Missing or contradictory native resolution is pending or
excluded according to the explicit acceptance policy, never filled from Gamma.

Any optional replay consumer must apply the frozen recorded-observation semantics:
exact `0 < remaining < T` and `price > m * remaining + b`, with finite decimal
parameters and exact arithmetic. It must preserve same-price later receipts as distinct
observations, reject ties or result-changing ordering ambiguity appropriately, and
never invent persistence, polling, intervening threshold crossings or executable fills.

## Daily authority, windows and durable recovery

Each daily certificate must bind a source inventory generation, transform/schema
identity, exact target membership projection, all required successful partitions,
observation accounting, identity checks, resolution evidence and explicit coverage
limitations. The market count or a 288-slot grid is a diagnostic of the returned
inventory, not a replacement denominator or venue-completeness gate.

Daily objects and their certificates must be immutable and content-addressed. A later
source revision or new dependency evidence creates a new generation; it does not
overwrite a historical artifact. A pending/failed day cannot advance current. Its
reason must remain durable and a later eligible source generation must be able to
revisit it without repeating unrelated successful acquisition.

A window must contain all selected complete certified UTC days while fewer than
thirty exist, and thereafter the latest thirty by day, not by job completion time.
Partial current days are ineligible. Window publication must verify every referenced
day generation and every data object before exposing the immutable window manifest
and updating current. Concurrent stale workers must re-evaluate current authoritative
selection at the update boundary; merely disabling cancellation is not a monotonic
selection protocol.

The mutable reference is a discovery aid. A consumer given an exact window tag and
digest must independently verify the pinned manifest, profile/scope, its immutable
inventory and all referenced day/object hashes without consulting current for data
selection. It must reject old diagnostic artifacts, cross-profile substitution,
unsealed drafts, missing assets and contradictory authority flags. Release caches
and expiring Actions artifacts cannot be the only resume or canonical store.

## Acceptance evidence still required

Meaningful implementation checks should exercise malformed/conflicting source
inventory, source mutation between discovery and acquisition, exact range/hash
failure, unexpected depth fields, exact clock/price preservation, same-ask provenance
changes, ambiguous mapping, absent observations, delayed/conflicting resolutions,
day-boundary dependencies and deterministic replay. Publication checks must cover
partial staging, loss before and after sealing, idempotent reuse, failed siblings,
late successful workers and concurrent window updates. Fixtures must prove the
30-to-31-day selection rule and that failure of a new day preserves prior current.

Required real acceptance is several complete seven-asset days independently read from
their published immutable objects, a consumer verification of a real exact window,
failed-shard recovery without reacquiring successful work, and durable scheduled
backlog continuation. Job color alone is insufficient. Previously verified positive
catalog identities and native source canaries are useful reference evidence but do
not themselves certify the new production generations.

Initial verdict: **production acceptance pending implementation and real proof**.
There is no new venue-census or quote-continuity requirement in this review. The
user-authorized inventory scope is the denominator for the new acceptance contract.

## Implemented working-tree review, 2026-09-06

The reviewer inspected the new `inventory.py`, `observed_v1.py`, `production.py`,
`production_consumer.py`, production workflow and focused tests while the author was
repairing the uncommitted implementation above the baseline commit. This is a
point-in-time review, not acceptance of subsequent edits or a claim that production
has acquired or certified real days. No native payload was acquired by the reviewer.

The new contract correctly separates inventory-scoped observed evidence from venue
history, continuity and sender execution. Acquisition projects only the three
authorized native products. Canonical rows use a fixed field set, exact decimal
strings and integer clock values; repeated recorded observations are retained.
Immutable daily certificates refer to verified compressed observation shards and
separate mapping bytes. The old diagnostic artifacts and consumer are preserved.

During this review the author repaired the initial inventory generation collision,
raw source page/manifest binding, mismatch between day shard publication and consumer
layout, iteration over release asset dictionaries, and update of current before
consumer verification. Chunk callers now match the exact planned hours and source
proofs; catalog reconciliation no longer rejects reusable mapping shards solely
because the root inventory grew. A per-product encountered-condition index limits
mapping dependency invalidation for data reuse. Strict row validation now rejects the
initial wrong asset/token/outcome, out-of-range price, Boolean profile version,
unsupported scope version, and malformed receipt/ordinal examples. These are useful
repairs; the remaining findings below require separate evidence.

| Finding | Concrete inspected behavior | Acceptance requirement |
| --- | --- | --- |
| Blocking: consumer authority rejection | An offline mock of immutable GitHub reads passed real payload SHA checks and returned `verified: true`, `research_import_allowed: true` for an empty 20-byte mapping gzip, future day `2999-01-01`, zero markets, scope version `999`, a day manifest without schema/day, and an all-zero window generation unrelated to its content. The consumer did not read source inventory, catalog or data-index closure. | Validate exact versioned day/window manifest contracts, recompute generation bindings, reject future/empty/inconsistent days, and independently bind expected target membership and the complete referenced partition set to the pinned inventory/catalog/index. Counts alone cannot prove omitted markets or shards were absent. |
| Blocking: same-horizon revisions | `window()` orders assessments by `inventory_last_hour` and raises when two different generations share that horizon. A legitimate source correction or new implementation commit can create this condition without adding an hour. | Bind an explicit deterministic revision ordering or approved replacement relation. Source-content or transform changes must create usable new generations while preserving historical authority. Do not make one such revision permanently prevent all later windows. |
| Blocking: rolling history | Choosing the latest assessment before filtering certified status suppresses an older certified day when its newer assessment is excluded. `_update_current()` compares tuples when the old window has thirty days; a single newer day compares greater and can shrink the window to one day. | Retain eligible previously certified day generations under an explicit revision policy, select the latest thirty from the full eligible set, and enforce monotonicity of both selected days and generation revisions at current update. A failed new day leaves current unchanged. |
| Blocking: interrupted staging | `_existing_partition()` can now independently read and seal a complete draft with a report, avoiding reacquisition after pre-seal loss. A failed starter upload with incorrect size/digest, or a report declaring an asset absent from the draft, still fails repeatedly without automatic recovery. | Recover bounded missing/failed staging uploads while preserving verified successful payloads. Mismatched completed bytes must remain fail closed. Prove runner loss before report upload, during upload, after all uploads and after sealing. |
| Blocking until proven: bounded autonomous backlog | The initial workflow emitted every eight-hour partition and every day directly into matrices. The author was adding bounded worker batches during review. A matrix-size cap alone does not establish progress within a runner timeout or preserve a source generation across scheduled discovery. | Prove a tick selects bounded missing work, persists its plan/checkpoints, continues after timeout/sibling failure, and advances through more than one matrix/runner budget without requiring another session. Reconciliation must not silently certify a partial plan. |
| High: remaining row domains | At the inspected revision, non-null asks allowed arbitrary `availability`, resolution rows allowed arbitrary `evidence_kind`, and observation interval/remaining values lacked exact integer type checks. Mapping text and source-hour formats were not sufficient to prove native slug/interval correspondence or calendar validity. | Enforce the finite semantic enums and exact scalar domains, and join each observation/resolution to its mapping. Add negative fixtures for the specific field mutations; arbitrary strings must not become a payload escape in semantic fields. |
| High: transform and stable partition identity | Acquisition identities use a manually maintained transform string. Groups are sliced by position in the full sorted inventory; insertion of an earlier newly served hour changes unrelated later groups. | Bind relevant transform implementation explicitly, and use stable source partition identities so unrelated source additions or documentation changes do not invalidate successful work. |

The reviewed consumer reproduction used only locally constructed fixture bytes and
mocked release reads. It did not publish a malformed artifact, bypass actual GitHub
immutability, or assert that current source data has these defects. It demonstrates
that the consumer's claimed mechanical rejection was incomplete even when all supplied
content hashes agreed.

Independent focused check: project-local Python ran
`python -B -m unittest discover -s tests -p test_observed_production.py -v`; all four
tests passed after the author's raw-inventory fixture repair. These tests cover basic
page parsing, no-depth extra fields, exact affine boundaries/ties, and the simple
30-to-31 selection helper. They do not yet exercise the production orchestrator,
interrupted drafts, consumer authority mutations, concurrent current updates, or
scheduled backlog continuation. Passing these four tests is not production acceptance.

Disposition at this inspection: **production approval withheld for repairable
implementation defects and missing real acceptance evidence**. The inventory-scoped
source policy is accepted; neither a venue historical census nor quote continuity is
being reintroduced as a blocker. Later repairs and their checks should be recorded
explicitly below before any final acceptance verdict.

## Repair re-review before production evidence acquisition

The subsequent working-tree re-review resolves the original consumer reproduction.
The consumer now enforces exact day/window field sets and profile/scope versions,
recomputes content-derived generations, rejects future and empty certified days,
and follows each day's independently pinned inventory, catalog and data index. It
reconstructs the complete expected mapping/data partition sets from the inventory,
verifies product proof bindings and decoded counts, reconciles mapping identities,
requires exact day membership and shard selection, and reads every referenced
canonical object. Mapping, observation and resolution source locators are checked
against their actual partition, manifest/product digest and row bounds. Data error
ledgers and retained-row counts must agree with their immutable reports. The earlier
hash-consistent empty/future-day acceptance is no longer an accepted code path.

Source index validation now requires the exact page-one start, subsequent URL/page
chain and a terminal page, as well as the raw-byte hashes and normalized hour set.
This closes the separately reported valid-first-page-but-missing-page-two fixture.
Canonical row validators now constrain availability, resolution evidence kind,
integer clocks/intervals and source-hour/receipt correspondence. Display question
changes are retained in mapping evidence without becoming token-identity conflicts;
the catalog builder and independent consumer use the same identity core.

Window reconciliation keeps the latest certified generation independently of the
latest failed/pending assessment. It ranks source revisions using the pinned
inventory release identity and retains old certified authority when a newer
assessment fails. Same-horizon revisions no longer raise an unconditional conflict.
Current updates verify the proposed window first, use a non-forced Git ref update,
and compare the selected days to the latest thirty of their union. Offline review
confirmed both the valid 29-to-31 transition and rejection of thirty days shrinking
to one newer day. A failed newer day leaves an existing current reference unchanged.
A concurrent non-fast-forward update fails closed; later scheduled reconciliation
is the continuation mechanism, rather than an automatic workflow-trigger chain.

Zero-byte upload starters are now retried only when they contain no completed bytes.
The production partition entry point separately handles an interrupted report
starter before trying to decode it. Fully uploaded drafts are independently read
before sealing; sealed successful partitions are reusable without source downloads.
An incomplete upload may require reacquiring that unfinished partition to regenerate
its report, while already sealed sibling partitions remain durable. Completed
assets with mismatched bytes, unexpected assets, or a completed report declaring
missing data still fail closed. The normal publisher uploads the report last, so
the latter state is not produced by interruption of its sequential upload protocol.

Production and consumer partition planning now use fixed four-hour data and
eight-hour mapping UTC buckets rather than positions in the growing inventory.
An independent offline insertion check added a missing historical hour and verified
that five unrelated data buckets and two unrelated mapping buckets retained their
identities; the consumer's independently calculated IDs agreed. Within a changed
bucket, source and manifest changes create a new partition; encountered-condition
dependencies prevent unrelated catalog additions from invalidating data projections.

The workflow emits at most 128 worker batches and preserves every planned item;
workers checkpoint individual partitions. A six-hour schedule independently
rediscovers/reconciles work and does not depend on a token-authored push. This fixes
the immediate oversized-matrix design defect. The batched work list itself is not
a measured runtime bound: verification of continuation across runner timeout and a
real backlog remains required, including evidence that successful siblings were
reused with zero new source bytes. No real accumulation claim is made by this review.

Independent offline checks in this re-review:

- Nine production-focused tests passed, including exact profile/day rejection,
  page-chain truncation, report-starter handling, batch completeness and rolling
  no-regression fixtures.
- Five acquisition/publication tests passed, including full-response rejection,
  product hashes/footer binding, draft pre-seal reads and zero-byte starter retry.
  The Windows sandbox initially denied temporary fixture file access; rerunning
  these same offline tests with narrow permission for this project's existing
  temporary directory passed. No source or GitHub network calls occurred.
- Additional reviewer-only inline fixtures confirmed fixed-bucket insertion
  stability, agreement with consumer partition identities, and the actual mocked
  current-update path for a 29-to-31 transition.

One final binding hardening was sent to the author during this re-review: the
window/day inventory release ID, tag, digest and last-hour fields must equal the
verified catalog/inventory, in addition to matching generation IDs. These fields
influence current-reference revision ranking and must not be treated as independent
claims. Its final disposition will be recorded after inspecting the repair.

Re-review disposition: the major prior implementation blockers have been repaired.
Subject to that final redundant-pointer binding and the normal required checks,
the reviewed design is suitable to obtain real production acceptance evidence.
This is **not** acceptance of certified days, a real pinned window, failed-shard
recovery, remote throughput estimates or autonomous accumulation: those require
independently read published objects and the requested real workflow evidence.
Transform version `pendulumflow-v3-observed-inventory-projection.v1` is a frozen
implementation contract; any behavior-changing transform revision must use an
explicit new transform identity while preserving these generations.

## Final pre-launch check

The window/day inventory release ID, tag, digest and last-hour cross-pointer check
is now present and was independently inspected. Catalog bounds also match the
verified inventory's first/last hours. This resolves the last pointer-binding
condition in the preceding review. The final focused rerun passed ten production
tests and the five acquisition/publication tests with no network acquisition.

A new automatic implementation digest was added to partition, catalog, index, day
and window identities. Its first revision hashed only `production.py`; this was
reported before launch because actual canonical transformation also depends on
`observed_v1.py`, `model.py`, `source.py` and `probe.py`. Reusing an unchanged
partition digest after changing one of those transformation modules would be
incorrect. The final disposition of the implementation-bundle repair is recorded
below after inspection.

The implementation-bundle repair is now inspected: the deterministic digest binds
`production.py`, `observed_v1.py`, `model.py`, `source.py`, `probe.py` and
`requirements.lock`. Partition and catalog/index/day/window identities bind that
digest. Documentation changes do not enter it, and a fixture proves changing a
bound transformation input changes the digest. This resolves the automatic
transform-invalidation defect. Source changes remain isolated to fixed UTC buckets;
the independent consumer computes partition identities using the recorded transform
digest, allowing exact historical generations to remain verifiable.

Final code verdict: **approved to launch the authorized production acquisition and
obtain real acceptance evidence**. No remaining launch-blocking correctness or
no-depth defect was identified in the reviewed paths. This approval does not waive
the project's required checks. The final eleven-test focused rerun found one stale
classifier expectation: an unparseable/null slug with a seven-asset Up/Down question
now fails closed as potentially in scope even without a readable five-minute marker;
the fixture still expected it to be out of scope. Ten other focused tests passed.
The author was notified to align that fixture with the accepted conservative rule
and rerun it before launch. The five acquisition/publication tests passed after the
source redirect guard change.

Research acceptance remains pending real certified day/window bytes, independent
consumer verification, measured acquisition and selective recovery, and observed
scheduled continuation. No day, window, throughput estimate or durable backlog
progress is certified by this offline review.

## Final condition-disposition and reconciliation review

The additional condition-disposition changes were independently inspected before
launch. Mapping staging publishes only condition identity, one fixed disposition,
source hour and product-row ordinal for this new evidence stream. It has no price,
quantity, order-book data or opaque payload field. The catalog reconstructs the
complete published disposition list from the pinned mapping partitions, rejects
contradictory dispositions and requires its in-scope condition set to equal the
actual target mapping set. Canonical observed row schemas and profile limitations
remain unchanged.

The data path now accounts separately for retained target rows, target errors,
out-of-interval recorded events, known out-of-scope conditions, unresolved condition
identities, ambiguous conditions and rows without a condition identity. Encountered
identity counts and conditionless counts are durable source-partition evidence.
The index recomputes unresolved membership against the current pinned catalog;
unclassified identities are not silently treated as out of scope. The independent
consumer repeats that reconciliation, checks its counts against the data reports,
and rejects a window whose required index remains unresolved. A physically missing
condition identity is not repaired by guessing which target market it belonged to.

This preserves selective reuse. Newly available evidence that classifies a formerly
unknown condition as out of scope can be reconciled through a new catalog/index
without reacquiring unchanged source products. If a newly mapped target condition
was encountered in an earlier product, its relevant target-mapping dependency changes
and the affected product bucket must be projected again. Old shard report counters
remain observations made against their original pinned catalog; they are not
overwritten to claim that later metadata was available during their acquisition.

Certification now requires both `complete_expected_partition_set is True` and
`target_membership_reconciled is True`; missing, string or integer substitutes do
not pass by truthiness. It records explicit exclusion reasons and does not publish
certified mapping payloads for an excluded assessment. An additional reviewer-only
offline probe supplied valid UP/DOWN/native-resolution fixture rows with mocked
upstream metadata and publication: unresolved membership alone produced `EXCLUDED`
and `research_import_allowed: false`; resolved membership followed the normal
certificate branch. This was a control-flow fixture, not certification of a real
source day or proof of an entire mocked dependency chain. No real release was written.

All eleven production-focused tests passed in the final rerun after the strict
Boolean gates were inspected. The formerly stale null-slug classifier expectation
is repaired and passes. Earlier independently passing range/hash, no-depth,
publication and recovery fixtures remain applicable; no acquisition or publication
implementation was changed by this reviewer.

**Final implementation disposition: approved for the authorized production launch
and collection of real acceptance evidence.** No unresolved launch-blocking defect
was identified in the reviewed condition reconciliation, manifest/consumer closure,
profile separation, no-depth representation or resume/publication paths. This
supersedes the provisional implementation findings above, whose repair history is
retained for reviewability.

**Final research acceptance: pending.** This document approves machinery for launch;
it does not assert any real day/window is certified, that native inventory membership
actually reconciles, or that scheduled backlog/recovery has been proven. The required
independent published-byte verification, measured acquisition, several real complete
days, selective failed-shard recovery and autonomous continuation evidence still
determine the final Run-1 verdict.
