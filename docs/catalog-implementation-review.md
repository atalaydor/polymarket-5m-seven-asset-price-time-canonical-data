# Independent implementation review: first-party catalog scout

Reviewed 2026-09-06. Scope: the additive authorization in `AGENTS.md`,
`src/pflow/catalog_probe.py`, `tests/test_catalog.py`, the catalog workflow and probe
plan. This reviewer read public first-party API documentation and ran offline checks.
No live catalog market response or native source payload was acquired by the reviewer,
and no workflow was dispatched or server contacted.

## Provisional verdict

**Acceptable to dispatch as a bounded, evidence-only capability scout. No expected
catalog or OBSERVED research day is approved.** The initial safety/runtime findings
below were repaired before this disposition. The reviewed new files were uncommitted
when inspected; this review does not assign them an older checkpoint's code identity.

The current authorization permits first-party metadata for identity, interval/token
mapping and listing/existence only. Outcome labels are identity metadata; winning
outcomes remain forbidden from this source. Native V3 remains the sole source for
historical prices and official resolution evidence.

## Findings and repairs

| Initial finding | Reviewed disposition |
| --- | --- |
| Report validator accepted arbitrary top-level raw payload and did not constrain several nested sections. | Repaired: root, request, scan, page, lookup and prior-identity field sets are explicit; projected rows are checked again recursively; profile/source pins, non-authority flags and ledger totals are validated. Mutation fixtures reject forbidden payload additions. |
| The old 14-row mapping sample covered only BNB/BTC. | Repaired: `prior_identities` requires both pinned quote samples for each of all seven assets, checks common market/interval identity, and exports only identity fields. Native sample asks and receipt observations do not enter the new catalog report. |
| Automatic redirects could contact an unapproved origin. | Repaired: a custom handler follows no redirect. Redirect responses become unavailable evidence, never a successful catalog response. |
| An 8 MB response could overshoot the 64 MB total. | Repaired: each read is bounded by the remaining total budget; equality with the bound fails closed. The stated limits are strictly below 8 MB per accepted response and 64 MB overall. |
| Nullable nested relations caused an unhandled projection failure. | Repaired: nullable relations remain explicitly null; non-null relations require bounded lists of dictionaries before recursive projection. |
| Full terminal pages were rejected solely because a cursor was omitted. | Repaired: keyset cursor omission is recorded as terminal under the documented API contract, including a full terminal page. A returned cursor still requires valid continuation and loop detection; a page cap remains nonterminal. |

The official [market keyset contract](https://docs.polymarket.com/api-reference/markets/list-markets-keyset-pagination)
specifies cursor pagination and a maximum limit of 100. It describes cursor omission
at termination; a short-page requirement must not be added as an independent source
rule. [Series listing](https://docs.polymarket.com/api-reference/series/list-series)
documents the legacy limit/offset, closed-state and `exclude_events` parameters used
here. The current implementation disposition supersedes the earlier redirect/code-hash
observation in the first draft of `catalog-authority-review.md`.

## Publication and source boundaries

Only fixed identity text, bounded outcome-label/token arrays, listing booleans and
typed event/series relationships survive `project`. Foreign asks/bids, outcome prices,
winner flags, books, quantities, volume, liquidity, rewards and arbitrary source fields
are discarded at every projected relationship. Original mixed-purpose response bodies
are not persisted as release assets; their hashes, byte counts and request times identify
the observed source response. These response digests are provenance, not a route to
import foreign prices or results.

The publisher receives one projected catalog report. Its strict validator requires
`research_import_allowed=false`, `expected_catalog_certified=false` and
`foreign_price_outcome_depth_fields_retained=false`, with the observed profile and
version fixed. Existing immutable-report publication still performs independent draft
asset reads before sealing and verifies published immutable bytes. Exact uploaded
reports can be reused without new catalog reads.

The seven prior-canary lookups are explicitly corroborative. Their slug construction
is a lookup hypothesis derived from already identified sample intervals, not the
expected-universe definition. Neither success for those seven lookups nor agreement
with the old canary can establish independent catalog completeness. Broader market,
event and series routes provide a separate discovery experiment.

## Limits that remain deliberate

The job is manual, uses pinned Actions on `ubuntu-24.04`, and has a 30-minute timeout.
The reader permits only the Gamma and documentation hosts and caps the scout at 100
requests. It reads no new native product ranges.

Market/event streams have at most two pages each, separately for `closed=false` and
`closed=true`; series streams have at most ten pages each. Terminal flags describe
the actual stream response, not whole-universe authority. The historical end-date
filter is an API slice, not the market-start-day membership definition. Nullable dates,
archived/deleted listings, changed membership, additional target series, duplicated or
ambiguous identities and interval exceptions need further measured reconciliation
before catalog promotion. An HTTP error is unavailable evidence, never absence.

Successful complete reports are durable checkpoints. Individual pages/streams are
not yet durable checkpoints if the runner fails before report publication, and partial
starter uploads still fail closed without automatic cleanup. No arbitrary pagination
restart or complete-production recovery claim is approved by this review.

The general report validator is a bounded metadata publication boundary, not a complete
catalog certificate. Real catalog closure would require stronger consistency checks
between page counts, terminal evidence, every expected stream, repeated membership
observations, independently classified target series and exact mapping/boundary data.
Those are intentionally not inferred from this scout's fixed non-authority flags.

## Independently executed checks

Five focused catalog tests passed in 0.003 seconds. They cover recursive removal of
foreign fields, nullable relations, all-seven-asset identity seeds without prices,
terminal/capped keyset behavior, nested payload rejection and promotion-flag rejection.
Changed-file Ruff lint/format and strict mypy passed; structural checks passed for all
four workflows. The reviewer also reproduced the original raw-payload/null-relation
failures before repair, so the findings are based on observed behavior rather than
speculation. No implementation file was edited by this reviewer.

Actual standard-runner status codes, page behavior, measured bytes, projected catalog
contents and an independently read exact immutable report remain pending. The next
acceptance step is to review that real evidence and choose a measured enumeration/
reconciliation path. The present verdict does not reinstate the waived quote-continuity
gate or declare first-party catalog capability exhausted before its real scout.

## Independent review of the real scout artifact

The reviewer independently read the small public Release metadata and asset, rather
than relying only on the implementation author's local copy. Native immutability,
non-draft/non-prerelease status, exact single-asset inventory, asset content address,
GitHub digest, independently supplied SHA-256 and complete report validation passed.
The local envelope at `work/verified-catalog-scout.json` was separately rehashed and
its measurements were recomputed; it agrees with the independently verified remote pin.

| Evidence | Exact identity |
| --- | --- |
| Immutable Release | `383534763` |
| Asset | `547023882`, 21,475 bytes |
| Tag | `catalog-probe-94843dedb39d4ed3549c45636c0cde9fa58e14209c835d4d8a8086333ae67231` |
| Report SHA-256 | `5e6e658e15bcc1e58b8bfe830af6c807afb1358ecc7793c98ff12dee5d19835f` |
| Transform commit | `e345d02e03c450a604f7ddf5af6391a933b22dc0` |
| Workflow run recorded in report | `34025801897` |

The report records 24 requests: **all 17 Gamma requests returned HTTP 403**, while
all seven documentation requests returned HTTP 200. Each Gamma response was 17 bytes.
Total measured response bytes were **195,750**, with **2.496530274 seconds** of network
time. The ten planned scan streams returned zero catalog rows and have no terminal
closure flags. All seven prior-identity lookups retain unavailable results, not
successful listing evidence.

These observations prove that the attempted Gamma requests were denied from that
runner during this attempt. They do not establish why, that the relevant markets are
absent, that Gamma's catalog is empty, or that first-party catalog capability is
fundamentally unavailable. HTTP 403 is not a terminal catalog page. The request ledger
retains the distinction, and no result was reclassified as "never listed."

The exact published report passes its nested metadata allowlists and generation/pin
checks. It explicitly retains `research_import_allowed=false`,
`expected_catalog_certified=false`, and
`foreign_price_outcome_depth_fields_retained=false`. No foreign price, winning result,
book or native price payload was published. Because no successful Gamma market response
was returned, real-data compatibility of the Gamma projection remains untested; the
existing offline projection tests are its current positive evidence.

**Accepted as immutable evidence of a bounded access/capability attempt, not as an
expected catalog or research-day certificate.** Independent verification required only
the small GitHub report and metadata; no new market payload or server connection was
made by this reviewer. Documented alternative first-party metadata routes remain
eligible for an ordinary bounded investigation under the same projection and
non-authority rules. This result does not justify bypassing access restrictions or
declaring those untested routes exhausted.
