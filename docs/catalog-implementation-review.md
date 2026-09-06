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

## Provisional review of the remaining route-access probe

The reviewer inspected new `src/pflow/catalog_access.py`,
`tests/test_catalog_access.py`, `.github/workflows/catalog-access.yml` and the
route-access plan after the initial Gamma artifact was preserved. The reviewed access
changes were uncommitted at inspection. **No remaining pre-dispatch blocker was
identified for this bounded, evidence-only access experiment.** This does not approve
an expected catalog or research day.

The fixed plan contains fourteen ordinary requests: one minimal Gamma series request,
initial full/simplified CLOB catalog pages, seven prior-token identity lookups, the
official geographic diagnostic, robots metadata, one event-page lookup hypothesis and
a Polygon transport identity request. It uses an honest project User-Agent, follows no
redirect, and uses no cookie handling, geographic rotation, proxy change, impersonation
or authentication-challenge workaround. The previous successful scout is not rerun.

The Polygon endpoint is an officially referenced public transport, not a
Polymarket-owned catalog. Its sole fixed POST body is `eth_chainId` with no parameters.
The request-body digest and POST method are checked; successful projection must be the
Polygon chain ID `0x89` with JSON-RPC version `2.0` and request ID `1`. No chain log,
market result, payout, price or trade request is present. This tests transport identity
only and cannot establish listing history.

### Access-review findings resolved before clearance

- **Raw denial text:** the initial short alphabetic-body projection could retain
  forbidden statements such as a winning-outcome string. It was removed. Only fixed
  `ACCESS_DENIED` or `UNCLASSIFIED_HTTP_ERROR` classifications may now survive; the
  original body is represented solely by its hash/count and is discarded.
- **Untyped existing fields:** an offline reproduction initially injected forbidden
  nested values into commit, workflow ID, method, request hash and observation time.
  These fields now enforce the commit/run formats, UTC timestamp, request kind,
  HTTPS origin, expected method and exact fixed RPC body hash (or null for GET).
  Mutation fixtures reject these payloads and arbitrary denial classifications.
- **Exhausted byte budget:** `request` rejects a nonpositive remaining budget before
  any network operation. The route loop stops at its 64 MB total cap and records when
  the route plan is truncated. A capped or failed response has a null catalog result;
  it never establishes an empty page or an absent expected market.

The CLOB projection retains only bounded identity strings, listing booleans and token
ID/outcome-label pairs, removing token prices, winner flags, rewards, depth and volume.
The public-page parser traverses embedded data transiently and exports only the same
strict Gamma identity projection. Robots output retains advertised first-party sitemap
URLs only. The geographic diagnostic drops its IP field and retains only the defined
blocked/country/region metadata; that diagnostic must not automatically be treated as
the explanation for catalog denial.

The report has explicit top-level and nested structures and fixed false research-import
and catalog-certification flags. Transport errors, HTTP errors, byte caps and
unsupported metadata shapes remain distinguishable null-result evidence. A successful
initial cursor page would support a further measured enumeration step, not terminal
closure by itself. Prior-token/page lookups remain corroborative and do not define
expected membership.

Four focused tests independently passed in 0.021 seconds. They cover HTTP 403 retaining
a null result, forbidden denial/provenance payload rejection, zero-budget rejection,
CLOB price/winner/depth removal, clean token lookup, public-page projection and removal
of geographic IP data. Changed-file Ruff lint/format and strict mypy passed; all five
workflow structural checks and `git diff --check` passed. No real route request was
made by this reviewer during this pre-dispatch review.

The actual route statuses, projected data compatibility and exact immutable access
report still require independent verification after execution. None of the cleared
code turns Gamma 403 into an absence claim, assumes CLOB/website/chain catalog closure,
or promotes the existing native samples into OBSERVED-profile research authority.

## Independent verification of the successful route-access artifact

The reviewer inspected and executed the new exact-pin `tools/verify_catalog.py` against
the public Release. It checks the small-report size bound, independent digest pin,
native immutable single-asset release, report/tag/schema/generation agreement and the
Git tag's exact transform commit. Those checks passed. The helper's own Ruff lint,
format and strict mypy checks also passed independently.

| Evidence | Exact identity |
| --- | --- |
| Immutable Release | `383539333` |
| Asset | `547039472`, 1,187,518 bytes |
| Tag | `catalog-access-bfb585a2b40c98ae7c1d195bbbbda7962c85d72e6d2cf65a071c1b75641edc93` |
| Report SHA-256 | `550c7e1c87fb2690dc5b24b5e280f3d1bc625c5129d45237ae8c80d28792442c` |
| Acquisition transform | `f9207e78a7a23218fe5aa262bd1336fd0f5792d5` |
| Recorded workflow run | `34026602233` |

Fresh public report bytes were independently retrieved and validated. The local
`work/verified-catalog-access.json` envelope was additionally decoded from bytes as
UTF-8 JSON and rehashed to the same exact pin. An initial reviewer-only locale-decoding
check was corrected; neither the local file nor the immutable artifact was corrupted
or changed. Metadata text must always be decoded explicitly as UTF-8 or from JSON bytes.

The report records fourteen completed access attempts, **2,959,391 response bytes**
and **37.694187883 seconds** of network time, without exhausting its budget:

- The minimal Gamma series request returned HTTP 200 and one projected series row.
  This is positive measured access with the stated request parameters/headers; it does
  not establish the precise cause of the earlier differently shaped 403 requests.
- CLOB full and simplified initial catalog pages each returned HTTP 200, 1,000 projected
  rows and continuation cursor `aWQ6MjQ5Mzk2`. They are successful nonterminal pages,
  not closed catalogs.
- All seven token-to-market identity requests returned HTTP 200. The reviewer derived
  expected identities from the independently pinned native Aug28 report and compared
  fresh access-report bytes: each asset's condition and both complementary token IDs
  agree for BTC, ETH, SOL, XRP, DOGE, BNB and HYPE.
- The geographic diagnostic returned HTTP 200 with `blocked=true`, country `US` and
  region `IL`, with no IP retained. This describes that diagnostic's semantics and is
  not proof of the reason any catalog route was denied.
- Robots metadata returned HTTP 200 and one advertised sitemap. The event-page request
  returned HTTP 200 but contained no supported `__NEXT_DATA__` block or projected
  embedded catalog row. That parser result is not an absence-of-listing judgment.
- The fixed Polygon `eth_chainId` request returned HTTP 401 and a null projected
  result. No chain identity or historical log-access capability was established; no
  log, trade, payout or result request was made.

The exact report passed the complete access-report/result validators, including CLOB
recursive projection and fixed non-authority flags. Actual CLOB metadata compatibility
and seven cross-source identity correspondences are now positive evidence. Foreign
prices, winner flags, depth, quantity, raw denial bodies and geographic IP fields are
absent from the published projections. Native historical prices and official outcomes
remain separate from these first-party catalog observations.

**Accepted as independently verified immutable access and identity evidence.** The
measured Gamma/CLOB routes support further bounded enumeration and reconciliation.
Neither the first pages nor the seven corroborative lookups certify expected membership,
close a research day, or permit research import. Both
`expected_catalog_certified=false` and `research_import_allowed=false` remain explicit.
The reviewer contacted only GitHub to read projected published evidence; no new native
or first-party market source payload was acquired during this verification.

## Independent review of bounded catalog enumeration

The reviewer inspected `src/pflow/catalog_enumerate.py`, its three focused tests,
the expanded exact-pin verifier, and `catalog-enumerate.yml`. This continuation is
cleared for a bounded evidence-only run, subject to the routine verifier formatting
check recorded below. It does not approve a complete expected catalog or a research day.

The fourteen preregistered streams comprise two unfiltered series traversals in
opposite ID order and market/event keyset traversals with explicit `closed=true` and
`closed=false` for each of the three prior native canary dates. Each stream is capped
at fifty pages of at most one hundred rows, with the inherited 64 MB request-byte
budget. The workflow uses standard Ubuntu runners, at most two concurrent streams,
thirty-minute jobs and `fail-fast: false`. No native payload is reacquired. The older
native report pin is provenance context, not a row-presence filter defining this
independent first-party discovery.

Full response bodies remain transient. Retained rows pass the existing strict Gamma
identity/listing/token metadata projection; no foreign prices, winner values, books,
quantities or raw-body escape field is introduced. The stable identity summary
deliberately omits changing listing flags and `updatedAt`; its hash establishes
equality only for that defined identity projection. The complete projected stream
retains the permitted listing flags and each HTTP response's timing, size and digest.
An HTTP-body digest is transport provenance, not an upstream signed catalog snapshot.

The pagination validator now independently reconstructs each request URL and cursor
or offset chain, requires exact agreement between the request ledger and page ledger,
accounts for all projected rows and duplicate IDs, and rejects pages after a terminal
or failed response. Terminal evidence, an explicit HTTP error and exhaustion of the
fifty-page bound remain distinct. A missing next cursor is accepted as the documented
keyset terminal signal; offset pagination requires a short final page. These checks
validate the observed traversal, not a simultaneous immutable view of a mutable API.

Two additional review findings were repaired in implementation: the expanded consumer
again recognizes the existing `--access-report.json` asset suffix, and enumeration
validation regenerates the preregistered specification by name rather than accepting
a report's self-consistent but arbitrary query specification. The reviewer exercised
both scout and access verifier paths offline with the previously pinned local report
bytes and mocked GitHub transport; both passed. A self-consistent mutation that changed
the query page budget and recomputed its generation was rejected as unregistered.
These are offline regression checks, not a fresh remote re-verification claim.

Each completed stream stages its content-addressed projected report and deterministic
summary, verifies both assets, and seals a native immutable release. Reuse validates
the exact stream specification, transform and report before accepting the checkpoint;
the consumer independently binds the report pin and recomputed summary to the exact
two-asset inventory and transform tag. Completed sibling streams survive failure.
This is stream-level durability: an interruption before report upload has no per-page
checkpoint, and a sealed HTTP-error report is preserved and reused as evidence rather
than automatically retried under the same generation. Partial starter-upload cleanup
and autonomous catalog retry scheduling are not implemented by this diagnostic.

The three enumeration unit tests independently passed in 0.009 seconds; strict mypy
passed for all three changed Python files, and all six workflow structural checks
passed. The final suffix repair initially needed Ruff formatting for one long line;
that mechanical check must pass before dispatch. The implementer reported a passing
32-test full suite; this reviewer independently reran the focused enumeration suite
and the additional offline regressions rather than claiming a second full-suite run.

Remaining interpretation limits are explicit. Unfiltered series requests do not by
themselves prove undocumented server defaults for closed or archived membership.
The date-filtered probes select the API's `end_date` range, including a five-minute
upper margin; they are not certified market-start-day membership sets. Candidate word
matches and seven-asset slug counts are discovery diagnostics, not the expected
denominator. Opposite-order agreement, if observed, would be corroboration rather
than independent proof against consistent omissions. Date-free histories and
reconciliation under documented listing rules still require separate evidence.

Both `expected_catalog_certified=false` and `research_import_allowed=false` remain
fixed. Actual reports, terminal behavior and pinned immutable stream/summary objects
require independent post-run verification on Linux for bulky streams. This review
does not change old native artifacts, source assumptions, OBSERVED-profile schema
status, daily gates or the absence of certified research authority.

## Page-clamp correction review and invalidated terminal inference

The refinement reviewed here is commit
`8659c75117a2b2acf080cea49ee0143d54ef25ae`, dispatched as workflow run
`34027804994`. The preceding enumeration ran under transform
`65b474aad96b6adde2901ba4d5b2944dd9353ce5` in run `34027566646`.
The earlier review's assumption that a short offset page establishes terminal closure
is **invalidated by actual API behavior**. A request for one hundred series returned
fifty, and the two opposite-order first-page identity projections differed. Existing
immutable reports retain their original `terminal_observed=true` claims as historical
diagnostics; those claims must not be interpreted as proved terminal catalog closure.

The reviewer read the saved small summaries independently. Both contain fifty rows
and one page; their stable identity digests are respectively
`1b362c2e1ceebc08a7158fb34aae7abdcbc0c70fbfb527d1018dd563ac6663f8`
and `405b43ef2540f4c31dc3da8730635c5ab0d9d549e2d9702a5c9a40fc944d59ff`.
The local inspection record `work/catalog-query-inspection.json` has canonical digest
`dc5371a9139e691dd6d6f1b137f2312e1db46f002af81d3a71b49fa9b6c0728e`;
it explicitly marks `series_short_page_terminal_claim_invalidated=true` and retains
false research-import and catalog-certification flags. These are local evidence reads,
not a claim that this reviewer freshly downloaded and independently verified every
old full stream.

The repaired scanner increments offsets by the actual number of returned rows and
continues until an explicit empty page or its budget/error boundary. This prevents
skipping records when the server clamps a requested page size. New
`series-complete-ascending` and `series-complete-descending` specifications request
fifty rows and their validators require the explicit empty terminal response.
The new refinement workflow makes only these two fresh first-party traversals. Its
separate Linux inspection job reads already published projected streams, preserving
successful keyset work without repeating that source acquisition. Each job remains
bounded to twenty minutes on standard Ubuntu; the two series streams use at most two
concurrent runners. No metadata projection or source-price/depth permission expands.

The saved inspection distinguishes three closed-market streams that exhausted their
fifty-page limits at five thousand rows from six observed terminal open-market/event
streams. The three closed-event streams have no sealed report. The implementer
reported oversized event responses hitting the response cap; the inspection's
`NO_SEALED_STREAM` alone does not independently establish the cause of that failure.
Neither a missing artifact nor a cap-limited traversal is an empty catalog.

Thirteen focused catalog tests independently passed in 0.045 seconds, including the
new fifty-row clamp, actual offsets 50 and 51, and explicit empty terminal fixture.
Changed-file Ruff lint/format and strict mypy passed; all seven workflow structural
checks passed. This also resolves the earlier mechanical verifier-formatting item.

Two actionable follow-ups were sent to the implementer during this review:

- Legacy short-page validation is selected by the stream name in the reviewed
  commit. Current acquisition always uses the empty-page rule. The reviewer reproduced
  a current `series-ascending` traversal containing a nonempty short page followed by
  an empty page that its own validator rejects as `pages after terminal/error`.
  The new `series-complete` execution is unaffected, but the existing enumeration
  workflow's original names must use current semantics for new transforms. Historical
  compatibility should be bound to the exact old acquisition commit.
- `catalog_inspect` checks immutable content-addressed release assets and validates
  the stream report, but the reviewed version does not enforce its expected two-asset
  inventory, recompute/compare the summary or verify the tag's exact transform commit.
  Those checks should match the exact-pin consumer before the inspection is described
  as complete independent verification of the old stream/summary pair. The existing
  native hashes and projected metadata remain preserved; this finding does not require
  fresh first-party source acquisition.

The new offset traversal is accepted as bounded diagnostic machinery. Complete
expected membership, historical listing-rule coverage and certified OBSERVED research
days remain unapproved. An explicit empty response repairs this observed pagination
fault; it does not establish atomic catalog snapshots, undocumented default inclusion
rules, or freedom from consistent upstream omissions.

## Refinement follow-up and target-series diagnostic review

Both refinement findings above are resolved in the next local implementation.
Legacy short-page semantics are now limited to the exact old transform
`65b474aad96b6adde2901ba4d5b2944dd9353ce5`; an independently rerun fixture confirms
that a current original-name series traversal with a short nonempty page followed by
an empty page now validates. The inspector now recomputes the deterministic summary,
requires the exact two-asset inventory and checks the tag object type and exact
transform commit. These repairs strengthen future inspection and do not rewrite the
earlier immutable reports or relabel their invalidated terminal claims.

The new target diagnostic selects seven series IDs from the independently pinned
projected series report, verifies its immutable report/summary inventory and transform,
and requires each selected series ID to occur once with the expected series slug.
The seed report SHA-256 is
`f4dbb82576c1001d25d82cb91163b51250da20cdc3c48bbe89e78ce3658e3c05`, from transform
`8659c75117a2b2acf080cea49ee0143d54ef25ae`. Selection is based on independently
discovered first-party series metadata, not absence or presence of native price rows.
It does not by itself prove that those series constitute all possible target listings.

Each asset has ten fixed event-keyset queries: four date-free first/last ID sentinels
cover both closed states and ordering directions, and six day-filtered traversals
cover both closed states for the three prior canary days. Sentinels request one page
of one row; daily probes request at most ten pages of one hundred rows. The inherited
request/byte caps remain in force. The workflow has seven bounded standard Ubuntu
jobs, at most two concurrent workers, no sibling cancellation, and no native-source
payload acquisition. ID extrema are not assumed to be chronological listing extrema.

Source bodies continue through the strict event/market/series metadata projection.
The summary exports only interval, market, condition, token and listing diagnostics,
with fixed false catalog-certification and research-import flags. Up/Down labels are
token identity labels; no winning outcome, external price or depth value is retained.
Date-filtered results are counted by their independently parsed event start times;
the five-minute end-date margin does not extend a certified research window because
this diagnostic certifies none.

Pre-dispatch review identified three target-specific corrections still requiring
verification at this point: reuse validation must bind the complete cursor/request
ledger, exact per-query page limits, row totals and terminal/error/duplicate accounting;
two outcome token IDs must be distinct numeric identities to avoid an error-free
diagnostic for duplicate tokens; and timestamp conversion must reject unsupported
sub-microsecond precision instead of silently truncating it. The reviewer reproduced
duplicate-token acceptance and sub-microsecond truncation with offline fixtures.
An exact-pin consumer path for the new report/summary pair is also required before
post-run independent artifact acceptance. No foreign-field projection leak was found.

The target corrections were subsequently inspected and independently checked. Target
reuse now invokes the shared strict page validator with the fixed one-page or ten-page
budget for each query, then requires the flattened ledger to equal the complete
request ledger. A synthetic ten-query report passed; independent mutations of the
page budget, terminal claim, duplicate IDs, error claim, request URL and row total were
all rejected. Token identities must now be two distinct positive decimal strings,
with either explicitly paired Up/Down label order permitted. The small summary also
retains the corresponding outcome labels alongside the token list, preserving that
orientation. Timestamp parsing accepts only an explicit timezone and zero to six
fractional digits; unsupported finer precision fails closed without truncation.

Fifteen focused catalog tests independently passed in 0.031 seconds. Ruff lint and
strict mypy passed for the four changed implementation/test files; their format checks,
all eight workflow structural checks and `git diff --check` passed. The independently
observed synthetic-report mutation checks were additional offline checks. No new
source payload was acquired during this review.

**Cleared for the bounded metadata-only target diagnostic.** Its independently pinned
published report/summary pair, measured route behavior and exact-pin consumer path
still require post-run acceptance. No catalog closure, source completeness, native
official outcome, certified day or research-import authority is granted by this code
review or by an error-free interval diagnostic.

## Actual target summaries and independent remote review implementation

The reviewer read all seven small target summaries and their saved immutable release
metadata from run `34028303954`, transform
`c4df60f9bfaa2ae1ea4f5d8838c33f73d6025e0b`. Each closed-state day query reports 290
returned events, including 288 starts within its intended UTC day and two boundary
neighbors; the corresponding open-state day queries report zero rows. These measured
queries have terminal cursor evidence and zero interval errors. Their combined source
request measurements are 42,532,081 bytes and 28,215,456,621 nanoseconds. These local
summary checks alone do not independently prove unique full identities, reconcile
every series candidate, or establish a historical expected denominator.

At the user's independent-review request, this reviewer implemented
`tools/review_catalog_remote.py`; no acquisition implementation module was changed by
the reviewer. The script freezes exact release IDs, report asset IDs, transform commits
and report SHA-256 pins for the two complete series reports, seven target reports and
prior native Aug28 source report. It requires Actions Linux before any report read.
Its only reads are existing GitHub Release objects and tag metadata; it does not call
any first-party market endpoint or acquire a native source payload.

The remote review independently verifies native release immutability, exact inventory,
report hashes, strict report projections, query ledgers, recomputed summaries and tag
transforms. It compares all 2,414 stable series identities between opposite-order
traversals, scans every preserved row for null metadata and fixed five-minute candidate
patterns, and records unknown/ambiguous candidates rather than hiding them. This
classification is explicitly a heuristic over preserved metadata; it does not claim
complete historical alias coverage or prove that an unmarked row cannot be a target.

For targets it independently derives event/market interval agreement and oriented
Up/Down token identities, requires unique positive listings within each observed
asset-day, and checks 6,048 globally distinct condition, market and event identities
across the 21 asset-days. The 288-start grid is labeled a positive query diagnostic,
with `expected_membership_inferred=false`. All fourteen prior native quote-side
identities are compared by condition, interval and oriented token. The native asks
themselves do not enter the review output.

The script publishes only a fixed allowlist of small metadata counters, diagnostic
hashes, bounded candidate ID samples and exact evidence pointers, with a 64 KB output
bound and explicit false research/certification flags. Its offline self-tests cover
orientation, duplicate tokens, unsupported timestamp precision, missing/duplicate
day rows and null/unknown candidate classification. Self-tests, Ruff lint/format and
strict mypy passed locally. The root-provided standard Linux review workflow passed
the structural check. Actual independent remote verification and the sealed review
report are pending execution; no result is inferred from the implementation alone.

## Series-detail probe review and retained measurement limits

The bounded detail probe makes one documented series-by-ID request per discovered
asset on standard Linux, with a 128 MB response cap and no redirects. It projects
explicit series/event/market identity and listing metadata, dropping foreign prices,
winner values, statistics, books and quantities. Null event relations remain null.
The cap stores only a prefix hash claim and null projected metadata when a full body
was not acquired; it does not publish raw or partial payloads as catalog evidence.

The reviewer identified two measurement/integrity limits in executed detail v1:
its `network_ns` includes JSON decoding/projection, and completion was inferred from
being below the cap without comparing declared response length. They are preserved
limitations of transform `f858dc3b16675148617749a16b122b755f69318b`, not retroactively
repaired claims. Future v2 code records `declared_bytes`, classifies an early EOF
against a larger declaration as prefix-only, and stops the network timer immediately
after reading the response. The reviewer inspected those repairs and independently
ran the new truncation fixture. Seventeen focused catalog tests passed in 0.031
seconds. V1 acquisition must not be repeated merely to replace these measurements.

The seven saved v1 detail summaries each report HTTP 200 and twenty returned recent
events, with twenty interval diagnostic errors. The inspected BTC/DOGE examples mark
missing or nonunique market evidence and absent back-relations; these are
unsupported nested identity shapes for that checker, not proof that the listed markets
do not exist. The route's successful response does not establish the SDK description's
suggested full historical membership. Full-history or native outcome authority remains
unapproved, and all earlier immutable target and detail evidence is preserved.

## Independently verified remote review result and remaining candidate

The Linux review completed in run `34029087406` under transform
`ee9398287209aee3cbea25e0a6c1cafd415ff67c`. This reviewer then freshly read its small
public GitHub report and independently verified the exact SHA-256, immutable release
inventory and transform tag:

| Evidence | Exact identifier |
| --- | --- |
| Release / asset | `383552489` / `547086233` |
| Tag | `catalog-independent-review-892c12abc44d17e54188bb2707d40dc91e6dbb6e3a896d4fc79f0f99e0bac04b` |
| Report SHA-256 | `892c12abc44d17e54188bb2707d40dc91e6dbb6e3a896d4fc79f0f99e0bac04b` |
| Report bytes | `12862` |

The sealed result establishes agreement between the two full pinned series identity
sets, positive observed listings for 6,048 globally unique conditions, market IDs and
event IDs across the 21 asset-days, and agreement for all fourteen native oriented
quote-side identities. This is independently verified positive catalog/mapping
evidence, not merely a count of returned entries or a green workflow. The report binds
the exact ten input generations and makes no new first-party or native payload
request. It retains false catalog-certification and research-import flags.

The all-row classification scanned 2,414 series. No row had a null slug, title or
ticker; two had null recurrence. It found eight five-minute candidates: the seven
known target series and additional series ID `12517`, whose asset could not be resolved
from v1's deliberately small candidate output. This candidate remains pending. It
must not be silently excluded or converted into an absence/complete-denominator claim.

Reviewer v2 adds only the already acquired series slug, title and recurrence to the
candidate output, with explicit nullable string types, 2,048-character field bounds
and the existing strict candidate allowlist. All input pins remain unchanged; the
follow-up rereads existing immutable GitHub evidence on Linux and makes no new source
query. V1 stays immutable. Offline self-tests, Ruff lint/format and strict mypy passed;
extra raw-body, nested-title and oversized-title mutations were rejected. The pending
candidate must be identified from the v2 evidence before the catalog checkpoint is
finalized. Historical denominator proof and certified research days remain unapproved
regardless of the positive identity checks already accepted.

## Final independent acceptance of positive evidence and candidate disposition

The reviewer freshly read and verified the v2 public report from run `34029408059`,
including its strict output allowlist, independent SHA-256 pin, exact single-asset
native immutable release and exact transform tag:

| Evidence | Exact identifier |
| --- | --- |
| Release / asset | `383554272` / `547092907` |
| Transform commit | `e723ebab3537d65f576520ecc75b47729ca1d633` |
| Tag | `catalog-independent-review-663f13177d380429a01000b9c5241e1e0640257f54b82dba67e42ef0a7b9723b` |
| Report SHA-256 | `663f13177d380429a01000b9c5241e1e0640257f54b82dba67e42ef0a7b9723b` |
| Report bytes | `13459` |

Series `12517` is explicitly named **ZEC Up or Down 5m**, with slug
`zec-up-or-down-5m` and recurrence `5m`. Its pending identity is therefore resolved:
it is outside the frozen BTC/ETH/SOL/XRP/DOGE/BNB/HYPE universe. It is retained in the
immutable evidence and is not silently dropped. The report's heuristic count of one
candidate outside its seven known target IDs remains an accurate historical output;
this reviewed disposition explains that candidate using the newly exposed first-party
identity text. No further unresolved candidate remains among these eight returned
five-minute candidates. That statement does not claim complete historical alias or
removed-listing coverage beyond the pinned returned catalog.

**Accepted as independently verified positive metadata evidence:** both full pinned
series identity sets agree; the three named UTC days contain 6,048 globally unique
returned condition/market/event identities across the seven assets; and all fourteen
native oriented token/interval identity comparisons agree. The v2 review required no
new first-party query or native payload acquisition. It grants no historical expected
denominator, official native outcome, certified day/window or research import.

The reviewer also inspected `tools/publish_catalog_checkpoint.py`. It requires a clean
committed worktree, the intended repository identity, remote main at the selected
commit, enabled release immutability, preserved old checkpoint tags/releases and a
successful push-triggered CI run for that exact main commit. It packages exact Git
blob bytes, verifies frozen policy hashes and rejects nonempty certified-day/window
or running-accumulation claims. Publication uses the previously reviewed draft-stage,
byte-verification and native immutable-release helper. Ruff lint/format and strict
mypy passed independently for the publisher.

No fatal publication or authority issue was found for the reviewed blocker-only
payloads. One pre-seal consistency item was sent to the implementer: the status file
still referenced v1 while the bundled independent result was v2. Its pointer must be
updated, and comparing the status digest with the exact bundled Git bytes prevents
that mismatch recurring. This is a metadata consistency correction, not permission
to promote research data. Final checkpoint publication and its exact resulting tag,
manifest and asset identities remain the root orchestrator's verification step.

The pre-seal consistency item is resolved. The reviewer re-read both status and
consumer handoff pointers and confirmed that their v2 digest equals the exact bundled
13,459-byte review payload. The publisher now rejects either stale digest, independently
reads and verifies the referenced immutable single-asset review release against those
Git bytes, and requires its tag to match the handoff locator. Changed-publisher Ruff
lint/format and strict mypy passed again. The implementer reports a passing 37-test
full suite; the independent checks and their narrower scopes are recorded above.

**Final review ready:** no unresolved implementation-review finding blocks sealing
this accurately named evidence/blocker checkpoint after its own exact-commit CI gates
pass. Accepted authority remains positive catalog and native identity evidence only.
Expected historical membership, certified research days/windows and autonomous
production accumulation remain explicitly unproven or unimplemented; this checkpoint
must not be consumed as a research dataset.
