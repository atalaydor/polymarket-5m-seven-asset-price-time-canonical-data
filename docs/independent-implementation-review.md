# Independent implementation acceptance review

Reviewed 2026-09-06. Scope: this project's `AGENTS.md`, `src/pflow`, unit tests,
dependency pins, source-proof workflow and locally preserved public schema/manifest
metadata. No source payloads were acquired and no remote jobs or servers were contacted
by this reviewer. This is independent static review, not evidence of a successful canary.

## Initial verdict (superseded by the follow-up below)

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

## Follow-up: commit `58b8fa385c676b8ce454a02e0e8bc5bfc9dfb19a`

The reviewer independently reread the current implementation and all twelve test
definitions. The implementation author reports that twelve tests, lint, format, strict
types and structural workflow checks passed; this reviewer did not independently run
those checks or read the remote canary payloads.

| Initial finding | Follow-up result |
| --- | --- |
| 1. Draft report nondeterminism | Repaired for a fully uploaded report: `probe.run` reads and reuses its original bytes before reacquisition, preserving measured attempt telemetry. |
| 2. Checkpoint semantic binding | Repaired in code: exact single-report inventory, schema, partition, hour, transform, source-manifest set and non-authority status are checked before reuse. Quote samples are revalidated; sealed assets are independently verified against exact bytes. |
| 3. Pre-seal verification | Repaired: authenticated API asset bytes are independently size/hash checked before PATCH publication; sealed public bytes are checked afterward. The draft-resume fixture asserts this order and that no successful existing asset is uploaded again. |
| 4. Missing clocks and edges | Repaired: missing-clock counts precede time filtering; missing event times and outside-interval observations are separately counted; first/last observations are retained with an explicit no-continuity label. |
| 5. Resolution provenance | Repaired: samples now retain per-asset witness/sequence/skew, product digest, row ordinal and nullable exact times. Unknown transport remains explicit. |
| 6. Strict quote fields | Materially repaired: identities, scalar integer types, exact four-place prices, interval bounds, receipt provenance and availability consistency are checked. The output still cannot claim interval continuity. |
| 7. Exact source types | Time/price precision repaired: unsupported timestamp units and Decimal type are rejected before conversion. The binary identity-width component remains only partly implemented, as described below. |

The added fixtures exercise rejection of an HTTP 200 response without reading its body,
valid product-range verification, corrupted product bytes, footer/manifest row-count
disagreement, unsupported nanosecond/float schema, and byte verification before draft
sealing. These are useful acquisition/publication regression checks.

### Remaining bounded findings

- `check_schema` checks timestamp, receipt, sequence and ask types, but not binary market
  and token widths. `token()` validates 32-byte outcome identifiers and quote validation
  checks the resulting market hexadecimal width; mapping rows without quote samples and
  resolution winner bytes do not have equivalent complete checks. Add explicit native
  binary type/width validation and avoid describing the current source schema check as
  exhaustive.
- No fixture yet exercises `probe.run`'s report-reuse branch or rejection of a report with
  mismatched source/transform/partition semantics. The implementation looks correct for
  the examined branch, but its key recovery guarantee needs a regression fixture.
- Recovery from a fully uploaded draft report is implemented. A failed-upload placeholder
  (`state=starter`, missing digest or incomplete bytes) fails closed on reread and cannot
  currently be selectively retried. This preserves existing bytes, but is a remaining
  recovery limitation and must not be represented as proof of arbitrary runner-loss
  recovery. A fix may handle only demonstrably incomplete assets in an unsealed draft;
  completed or sealed content must remain protected.

**Follow-up verdict:** the main static safety findings are repaired for bounded source
proof, with the remaining implementation/test limits above. Daily/window certification,
native source sufficiency, remote canary results, real failed-shard recovery and autonomous
accumulation remain unapproved and unverified by this review. The source capability gate
must remain closed; no successful job or immutable canary report can substitute for it.

## Final local acceptance addendum

Independently reviewed the final working changes over
`58b8fa385c676b8ce454a02e0e8bc5bfc9dfb19a`: binary identity validation in `source.py`,
32-byte condition validation in `model.py`, resolution winner/token-set validation in
`probe.py`, the pinned `consumer.py`, and the acquisition/resume fixtures. These changes
were uncommitted when inspected; this addendum does not assign them the earlier commit's
identity.

**Independent execution passed:** all 14 unit tests in 0.109 seconds, Ruff lint, Ruff
format check (10 files), strict mypy (10 source files), both structural workflow checks,
and `git diff --check`. Tests used this project's `.venv` and
`work/test-temp`; the approved Windows fixture execution ran outside the sandbox to allow
temporary-directory ACL operations. No dependencies were installed, no market payloads
were acquired, and no server was contacted by the reviewer.

The new resume fixture enters the actual `probe.run` checkpoint branch, verifies no
product fetch occurs for an exact sealed checkpoint, and rejects a transform mismatch.
The consumer fixture rejects a wrong independently supplied hash and rejects research
import even when the evidence report verifies. Binary source types and per-row 32-byte
tokens/conditions are now checked for the target records, and resolution token sets must
agree with the mapped UP/DOWN identities. The previously outstanding bounded schema and
reuse-test findings are closed.

Incomplete draft-upload placeholders remain **preserved and fail closed, without
autonomous cleanup/retry**. This is an explicitly unfinished production-recovery feature,
not proof of arbitrary runner-loss recovery. It does not prevent preservation or
verification of a completed source-proof report. Because full accumulation is already
blocked by source capability, this limitation is not treated as a claim that the
production pipeline is complete.

### Local inspection of the first real report

The implementation author supplied an independently downloaded envelope at
`work/verified-2026-08-27.json`. This reviewer independently rehashed the canonical report
inside that local file, matched its supplied SHA-256 pin, and validated every quote
sample under the current strict contract. The reviewer did not make a second remote
download or independently reestablish current GitHub release metadata.

- Release ID: `383483454`; asset ID: `546813960`.
- Tag: `source-probe-e351a89837a1a06d7f1fcd300a163d1d7f75650e64ba003e9e8ac3c1153e4caa`.
- Report SHA-256: `f9ede8837faa8973f8f77261657515856efa7375e7d5bce8aeea21eec2519d6a`.
- Report transform: `58b8fa385c676b8ce454a02e0e8bc5bfc9dfb19a`.

For source hour `2026-08-27/12`, the report contains 84 mapped markets, both-side
observations for all 84, resolution observations for all 84, and 224,196 in-interval
target ask observations. Measured acquisition was 131,717,227 bytes, 48.934896118 seconds
of network time and 76.581052056 seconds of decoding. It also explicitly records 237,172
target observations with missing clock/witness evidence across the examined target rows.
Its envelope says `immutable=true`, while the report says `certified_days=[]` and the
consumer says `research_import_allowed=false`. These are source-hour observations,
not complete-day certification.

**Final review verdict:** bounded source-proof machinery passes the independent local
checks above; no remaining identified issue requires weakening or bypassing its
fail-closed source gate. No daily dataset, rolling window, complete production recovery,
autonomous accumulation or research authority is approved. Target census, token/side
continuity and opening-state evidence remain the substantive source blocker.
