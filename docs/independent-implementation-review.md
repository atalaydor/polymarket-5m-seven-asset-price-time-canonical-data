# Independent implementation acceptance review

Reviewed 2026-09-06. Scope: this project's `AGENTS.md`, `src/pflow`, unit tests,
dependency pins, source-proof workflow and locally preserved public schema/manifest
metadata. No source payloads were acquired and no remote jobs or servers were contacted
by this reviewer. This is independent static review, not evidence of a successful canary.

## Initial verdict

**Changes required before accepting durable source-proof publication. No daily or window
authority is approved.** The separate [source review](independent-source-review.md)
identifies unresolved target census and continuity evidence. Keeping acquisition bounded
and promotion disabled is appropriate; an upstream audit label cannot close those gaps.

The implementation confines acquired products to `new_market`, `best_bid_ask` and
`market_resolved`, checks exact HTTP range responses and published product-range hashes,
and projects an explicit depth-free field list. Decimal prices and integer microseconds
avoid floating-point conversion. Null asks remain unknown and archive receipts are
explicitly distinguished from sender HTTP receipts. Standard Linux runners, bounded
parallelism, pinned Actions and workflow concurrency match the requested execution scope.

## Findings supplied to the implementation author

1. **Draft restart is not idempotent.** `probe.run` binds the partition tag to source
   manifests and transform, while the report includes run ID and measured timings.
   Recreating a report after a failed upload changes its content-addressed asset name;
   `release.publish` rejects the old draft inventory. Resume and verify the original
   staged report for its exact partition, or separate deterministic identity from attempt
   telemetry. Never overwrite an existing staged object to conceal the mismatch.
2. **Checkpoint reuse lacks semantic binding.** The early reuse branch verifies sealed
   asset bytes and content-addressed names, but does not validate report schema,
   partition identity, source set, transform commit or expected inventory. A
   self-consistent unrelated report must not satisfy the requested partition.
3. **Pre-seal verification is metadata-only.** Draft upload checks use GitHub asset size
   and digest metadata; independent byte retrieval occurs only after publication.
   Independently retrieve and hash every draft asset through the authenticated asset
   endpoint before sealing, then independently verify the immutable published result.
4. **Missing-clock reporting can undercount.** Rows with absent source-event timestamps
   are filtered before the missing-clock counter. Count missing/malformed clocks before
   time-window filtering and report out-of-window observations separately. Computed
   first/last event boundaries are discarded and should be retained as observed evidence,
   explicitly without continuity authority.
5. **Resolution evidence loses ordering provenance.** Retain sequence, witness identity,
   witness set, arrival skew, product digest and product row ordinal with resolution
   samples. Bound samples across assets and preserve contradictory/missing evidence.
6. **The advertised strict quote validator is incomplete.** The initial validator checks
   field names and excludes nested values/floats, but accepts invalid scalar prices,
   timestamps, digests, tokens and availability combinations. Validate scalar types and
   invariants if this function is to define the published contract.
7. **Exact physical/logical source types need validation.** Cross-check the Arrow schema
   against native Decimal(9,4), timestamp units and binary identity widths before Python
   conversion. In particular, unsupported nanosecond precision must not be silently
   truncated by the microsecond conversion. Footer offset checks are structural checks;
   its observed hash is distinct from the verified published product-range hashes.

Regression evidence should cover range rejection, product hash failure, strict schema
rejection, draft restart, partial publication and semantic checkpoint mismatch. Existing
unit tests demonstrate basic contract gates and sealed-release rejection, but initially
did not exercise these acquisition and recovery paths.

## Acceptance limits

No tests, remote runs, immutable payload reads, real certified days, rolling windows,
failed-shard recovery or autonomous backlog continuation were independently verified by
this static review. The code intentionally exposes no certification/promotion path.
Successful canary reports may certify only their stated source observations and hashes;
they cannot be relabeled daily research authority. A follow-up review is required after
the actionable implementation findings are repaired.
