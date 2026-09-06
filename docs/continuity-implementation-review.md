# Independent implementation review: transient continuity diagnostic

Reviewed 2026-09-06. Scope: the explicit continuation exception in `AGENTS.md`, new
`src/pflow/integrity.py`, `src/pflow/continuity_probe.py`, both integrity test files, and
`.github/workflows/continuity-proof.yml`. This reviewer made no network request for
source payloads, acquired no real depth locally, and contacted no server.

## Pre-dispatch verdict

**The bounded diagnostic is acceptable to run; no pre-dispatch depth-leak or runtime
blocker was identified. This is not approval of research authority or venue continuity.**
The new work was uncommitted when inspected. A Git comparison confirms that `model.py`,
`source.py`, `consumer.py`, `probe.py` and `release.py` match frozen checkpoint
`7c313b1e31f73cbba20465d0ed05d12b52a19bce`. The canonical product allowlist and daily
certification gates remain unchanged.

The `AGENTS.md` exception authorizes only this bounded, transient use of native `book`
and `price_change` on standard GitHub Linux runners. The new entry point checks Linux
and `GITHUB_ACTIONS=true`; the frozen range reader independently imposes the same
restriction on real byte-range reads. The workflow uses `ubuntu-24.04`, pinned Actions,
one 45-minute job, no paid runner, and no automatic dispatch chain.

## Acquisition and interpretation

The probe binds exactly `2026-08-28/11` and `2026-08-28/12`, their two manifest digests,
the previous report pin and current transform commit. The reviewer independently
hashed the locally preserved public manifests and previous depth-free cohort. Their
pins agree with the constants in the new code:

- Manifests: `e0eaf9f38222ebe4ba78df9ba525cd56b89b273d577f8bec8af058457ef52c5b` and
  `b7d00beb5e0590d88482824580493f793ad379024cce94a28e20f6a21ad0145b`.
- Prior report: `61347d5fdd408676adff2d40a5224934e5b646175a59d2c562a6b042ec355173`.
- Exact 14-outcome cohort: `ccc37ac860ec9cce50a9ee501b6375435f85893d32204373046559760e479fe1`.

The three complete product ranges across both hours total **1,891,887,040 bytes** from
observed metadata. Footer and inventory overhead must also fit the **2,100,000,000-byte**
reader budget. Product bodies stream in at most 32,000,000-byte requests, with exact
range-response checks inherited from the frozen reader and a SHA-256 over each complete
product range. Whole-file verification remains explicitly false. Footer hashes are
observed evidence; offset, event-label and row-count checks are structural bindings to
the hashed product regions.

The synthetic acquisition test exercises the union Parquet layout, projected decoding,
target selection and corrupted-range rejection. Timestamp schema checks precede Arrow
integer conversion: source milliseconds are multiplied by 1,000 and receipt microseconds
remain unchanged. This preserves exact values and avoids a platform timezone-database
dependency. Decimal level prices and sizes remain exact during the transient computation.

State is maintained separately for each target and selected witness. Snapshot replacement,
SELL size assignment and zero-size removal match the reviewed product semantics. BBA
remains a separate observation. Equal local keys, ambiguous source-time comparisons,
non-successor local sequences, missing clocks/witnesses, and state disagreements become
diagnostic counts. Per-token sequence gaps may represent other recorded events; the
code and source review do not relabel them venue losses.

Sorting retained rows by a selected witness's receipt/sequence is only an explicit
diagnostic hypothesis. It cannot restore that witness's discarded copies or resolve
all equal-key orders. Even an entirely agreeing replay supplies no source-side premise
excluding a missed and subsequently reverted price excursion. The counterexample test
demonstrates identical admitted observations with different unobserved paths.

## No-depth publication boundary

Real depth-bearing Parquet files live only in a temporary directory. Event objects and
state maps are transient; neither is passed to the serializer or release publisher.
The files are closed/unlinked before report publication, and event collections are
cleared. The new report publishes only:

- fixed diagnostic integer counters and bounded scan/network telemetry;
- typed source-content provenance;
- the exact previously published, hash-bound, depth-free cohort;
- fixed non-authority declarations and attribution.

`validate_report` checks the complete top-level and nested field sets. The cohort hash
prevents replacing the original best-ask samples with depth-derived rows. Every cohort
row also passes the frozen strict quote validator. Source proofs have exact typed fields;
counters and scans cannot carry lists, payloads or arbitrary field names. The report
requires `research_authority=false`, `continuity_proven=false`, `certified_days=[]` and
`canonical_rows_emitted=0`. Full product hashes are provenance, not a published depth
state or an executable signal.

The reviewer constructed a synthetic valid report using only locally preserved public
metadata and the prior cohort. Seven mutations were independently rejected: raw payload
at the top level, raw proof content, product-level asks, cohort quantity, an extra depth
counter, raw scan content, and a continuity-promotion flag. No source payload was needed
for these checks.

Existing draft/published checkpoint handling validates the diagnostic schema and exact
identity before reuse. Publication reuses the frozen independent pre-seal asset reads
and immutable-release verification. Incomplete draft uploads remain preserved and fail
closed without autonomous cleanup; this remains an explicit production-recovery limit.

## Independently executed checks

- **20 tests passed** in 0.098 seconds, including actual synthetic three-product
  acquisition/decode/hash rejection and the identifiability counterexample.
- Ruff lint and format passed for 14 files; strict mypy passed for 14 source files.
- All three structural workflow checks and `git diff --check` passed.
- Local cohort/manifest hashing and seven nested report-mutation checks passed.

Checks used this project's pinned `.venv` and project-local temporary storage. The
offline fixture suite used approved Windows sandbox escalation solely for temporary-file
ACL operations. No dependencies were installed.

## Remaining acceptance boundary

Actual runner byte counts, runtime, decoding outcomes, a sealed diagnostic asset and its
independently read bytes are still required before calling the remote experiment verified.
The real report must be checked again with the strict validator and exact content pin.
No new canonical rows, certified days or rolling generation may be inferred from that
success. The source limitations described in
[the independent continuity source review](continuity-source-review.md) remain active.

## Final review of the real immutable diagnostic

The reviewer independently requested the exact public Release metadata and small
diagnostic asset using the inspected `tools/verify_continuity.py`. Native immutability,
non-draft/non-prerelease status, exact single-asset inventory, GitHub digest, independently
supplied SHA-256, complete report allowlists, prior cohort identity, and recomputed
source/transform generation identity all passed. No native market-data product was
downloaded during this review.

| Evidence | Exact identifier |
| --- | --- |
| Immutable Release | `383511393` |
| Diagnostic asset | `546922721` |
| Tag | `continuity-probe-c387591627194c3c5a6f668cbea707da7085c658ba94b3c054b41ce30c6a3b51` |
| Report SHA-256 | `b107e4a5033ba09e1ace47439e37e2e5c529be94e7a91561884070f49c71c619` |
| Acquisition transform | `529e6b5e2b18d46834815e90ad2f1b0ff45c599c` |
| Workflow / run | `351422157` / `34021182240`, attempt `1` |

An independent GitHub run-metadata read confirmed `completed`, `success` and the exact
transform commit above. The artifact verification, rather than that job status, is the
publication evidence. The verifier has no mutable-current lookup and always returns
`research_import_allowed=false`. Its own Ruff lint/format and strict mypy checks passed
independently. The local report envelope was also rehashed against the independently
verified remote pin and all diagnostic totals were recomputed from its per-target counts.

### Measured observations

The two-hour report records **1,894,050,290 downloaded bytes**, including metadata,
**1,893,960,850 requested range bytes**, **121.526821495 network seconds**, and
**10.975252367 decode/diagnostic seconds**. These are measurements of this bounded
experiment, not a certified-backfill estimate.

The projected cohort contains **351,524 target rows**: 6,160 book observations,
328,528 price changes, and 16,836 BBA observations. All 14 pinned outcomes have observations.
Selected-witness counts differ by asset: BNB/HYPE have one per outcome, ETH/SOL/XRP have
two, and BTC/DOGE have three. Summing that field gives 28; it must not be interpreted as
two witnesses for every outcome or as 28 independent collectors.

The report contains 201 disagreements in 6,134 snapshot-state comparisons; 12,327 in
324,062 delta/ask comparisons; 5,992 in 16,634 BBA/state comparisons; and 24 in 14,624
unambiguous same-source-time BBA/delta comparisons. It reports 10 boundary-carried
diagnostic states, 4,466 unanchored delta observations, and zero missing-clock or
missing-witness rows under this diagnostic's checks. These counts are conditional on
its retained-witness/order and snapshot interpretation. They are neither a count of
proven venue losses nor proof of a complete capture when they agree.

### Snapshot-null limitation and subsequent hardening

The acquired transform `529e6b5e2b18d46834815e90ad2f1b0ff45c599c` normalized a null book
ask list to the same transient empty tuple as an explicit empty list. The report has no
counter distinguishing those cases, so it cannot establish whether null snapshots
occurred or use an empty anchor as independently established absence. Its anchor/state
diagnostic counts retain that interpretation limit. No published canonical row was
created by this normalization, and it does not change the independently established
source-continuity insufficiency.

The reviewer inspected the subsequent, then-uncommitted two-line guard rejecting a book
ask side that is not an explicit list. The affected synthetic acquisition test now
includes null-snapshot rejection and passed independently in 0.079 seconds. This closes
the issue for future execution; it does not retroactively change the sealed report or
claim that the hardened working tree acquired real source bytes. The old artifact is
preserved with its precise transform and stated limitation. No source payload was
reacquired merely to restate the unchanged blocked verdict.

### Final no-depth and authority verdict

The exact published bytes pass the full nested report validator and the original cohort
hash. They contain fixed counters, typed provenance/telemetry and the previously
published depth-free samples; no newly derived price rows, levels, quantities or raw
payload are present. The verified report explicitly has `research_authority=false`,
`continuity_proven=false`, `canonical_rows_emitted=0`, and `certified_days=[]`.

**Accepted as a verified immutable, bounded diagnostic with the snapshot-null limitation
above. No daily/window or exact-continuity authority is approved.** Frozen canonical
files still match `7c313b1e31f73cbba20465d0ed05d12b52a19bce`. The target-coverage,
source-side continuity, retained-witness ordering and opening-state capability gaps
remain substantive blockers. More agreeing anchors or a green diagnostic job cannot
remove those missing premises.
