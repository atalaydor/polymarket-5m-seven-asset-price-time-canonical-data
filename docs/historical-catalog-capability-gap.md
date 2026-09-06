# Historical expected-listing authority remains unestablished

The additive first-party metadata investigation did not establish the historical
expected-membership gate. `PENDULUMFLOW_V3_OBSERVED` version 1 is unchanged. This is
not the rejected price-continuity requirement. Earlier v0.1.0, v0.2.0 and v0.3.0
checkpoints and successful native acquisition/recovery proofs remain preserved.

## Positive evidence

Gamma metadata access works. Two independently pinned, oppositely ordered complete
series enumerations returned 2,414 identities with the same stable membership digest:
`6d90a622f24813e94f4b9551691094dc27fbe0f3b59904d943f2747bed7e8688`.
Releases 383545434 and 383545482 preserve the projected rows and request ledgers.
The observed effective series page limit is 50; the original 100-request/50-return
short-page termination inference was invalidated, not overwritten. Corrected scans
advance by actual returned count and reach an explicit empty page.

Seven series were discovered independently of V3 quotes: BTC 10684, ETH 10683,
SOL 10686, XRP 10685, DOGE 11325, BNB 11326 and HYPE 11327. The last three have
`recurrence=daily` despite their 5m titles. Recurrence and series creation dates
therefore do not establish a five-minute listing schedule or first listed interval.

On 2026-08-25, 2026-08-27 and 2026-08-28, each target-series closed query returned
290 entries in three terminal keyset pages: 288 entries assigned to the requested
market-start day and two boundary neighbors. All 21 corresponding open-state
queries terminated empty. The 6,048 named-day entries have positive first-party
identity and interval evidence; these counts alone are not a proof of historical
exhaustiveness. Independent full-object review proves 6,048 distinct named-day
interval/market/condition/event identities, oriented token pairs and 14/14 prior V3
sample mappings. The subsequent metadata-only review identified the extra five-minute
series 12517 as `zec-up-or-down-5m`, titled `ZEC Up or Down 5m`, outside the seven-asset
universe. Both review generations are preserved; no new source bytes were acquired.

The target probes acquired 42,532,081 first-party response bytes in a summed
28.215456621 seconds of network time. These are metadata diagnostics, not production
V3 throughput or a backfill ETA. No native price payload was reacquired.

## Routes and limits

- Gamma series enumeration: complete returned series scope, stable in both orders.
  It supplies current first-party series records, without historical deletion or
  membership-transition authority.
- Gamma market/event keyset and legacy listings: documented historical date filters
  and explicit closed states were tested. Broad closed-market slices were capped at
  5,000 rows, not declared complete; broad closed-event responses exceeded the
  configured runner response-byte bound. Independent target-series slices subsequently completed. Null/moved-date
  candidates outside those slices remain outside their positive scope.
- Date-free target-series first/last ID queries: positive historical and current
  records, with nonterminal cursors. ID order is not a normative chronological or
  continuous listing schedule.
- `GET /series/{id}`: despite an official SDK description suggesting all series
  markets, each of seven real calls returned only 20 recent September 6/7 events,
  without the nested market/series identity evidence needed by the diagnostic.
  It did not return the representative August catalog. The v1 diagnostic's
  `network_ns` includes decode/projection time and is not a pure transfer measurement;
  its body-length inference lacked recorded Content-Length. Later v2 code repairs
  both limitations; successful route probes are retained and were not repeated.
- CLOB full and simplified listings: both returned 1,000 matching first-page
  identities and nonterminal cursors, including 941 closed and 57 archived records.
  Seven clean token lookups matched the V3 condition and unordered token pairs.
  Primary-token order is not UP/DOWN orientation. No historical absence/retention
  contract was found in the inspected first-party interfaces.
- First-party web/robots/sitemap and identity lookups can recover positive records.
  They are not documented historical listing/exception ledgers. Remaining payload
  pages are not falsely described as exhaustively downloaded.
- Official contract/SDK source explains condition preparation and market identity.
  Preparation alone is not off-chain listing. No inspected first-party route exposes
  a historical listing snapshot, deletion/tombstone history, or normative finite
  listing rule with its exceptions. A bounded chain-ID transport probe failed; no
  chain log, payout, price or research-observation data was imported.
- The pinned native V3 index exhaustively enumerates its served objects, not the
  independent venue-expected target listing set. Lifecycle rows cannot define their
  own expected denominator.

Full date-free enumeration can resolve currently retained null/moved-date records.
It cannot by itself supply the missing historical-retention semantics. More current
CLOB or sitemap pages could identify omitted positives, but a terminal negative
result still cannot lawfully establish historical `NOT_EXPECTED` under the inspected
contracts. The missing capability is authority, not a page budget or access denial.

## Why the distinction matters

Two finite past listing histories remain compatible with the inspected evidence.
An additional prepared target condition could have never been listed, or could have
been briefly listed then removed before the present catalog captures. Current
catalog responses and identical condition-preparation records need not distinguish
those histories. Their required historical expected sets differ. No such removal
was observed or asserted: this is the precise information absent from the published
contract, rather than a claim that the positive returned rows are wrong.

Even a fully populated observed 288-slot grid does not prove a normative one-market
per asset/interval listing rule, exclude historical relistings, or authorize labeling
other conditions/intervals as never expected. Promoting the returned set would change
the denominator to a current-catalog-relative product, which this continuation did
not authorize.

## Continuation condition

Provide an authoritative first-party finite historical expected-membership basis for
the claimed UTC days: a retained complete listing/exception inventory, applicable
historical listing snapshots, or a normative listing/identity rule plus explicit
exceptions and delisting/relisting semantics. It must distinguish historically never
listed from removed/omitted membership and be pinnable independently of V3 quote
presence. An equivalent exhaustive native published expected catalog also qualifies.

No unchanged-price continuity proof, new price source, recorder, sender or factory
change is required to address this blocker. No certified day/window exists; import
remains false and production/scheduled accumulation is not launched.

See [source review](catalog-authority-review.md),
[implementation review](catalog-implementation-review.md), and
[immutable evidence inventory](catalog-evidence-inventory.json) for exact source,
workflow, release, asset, byte-size and digest pointers.
