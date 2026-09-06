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
