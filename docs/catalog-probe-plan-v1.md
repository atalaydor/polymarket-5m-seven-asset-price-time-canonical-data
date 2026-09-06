# First-party catalog capability probe

This continuation permits first-party Polymarket catalog metadata for identity and
listing only. Historical price observations and official winning outcomes remain
PendulumFlow native V3 only. PENDULUMFLOW_V3_OBSERVED v1 is unchanged.

The initial Actions scout tests the documented Gamma market/event keyset routes,
their legacy offset alternatives and series discovery. It uses explicit closed=true
and closed=false, stable ID ordering, and the same bounded historical end-date query
around 2026-08-28 and its UTC boundary. This is an API capability slice, not a complete
market-start research day. At most two pages per market/event stream and ten per
series stream are allowed; reaching a cap is explicitly nonterminal. No production
promotion exists in this scout. API errors and unavailable cursors never mean absence.

Seven identity cross-checks come from the already pinned Aug28 quote samples, after
discarding their price/time-observation fields except market interval identity. The
slug constructed from each sample is only a lookup hypothesis; neither these samples
nor that hypothesis define expected membership. The old mapping_samples slice alone
contains only BNB and BTC and cannot stand for seven-asset discovery.

Every response is received only on a standard GitHub-hosted Linux runner. A strict
projection preserves catalog IDs, labels/token identities, listing flags, available
identity times and typed event/series relations. No prices, book data, quantities,
winning outcomes, rewards, arbitrary payload or unrecognized field is published.
Original response byte hashes and request times identify source observations; raw
mixed-purpose API bodies are discarded. Redirects are not followed. The scout is
bounded to 100 requests and less than 64 MB of responses, with each response below
8 MB. Documentation response digests are version observations, not source signatures.

The immutable report is evidence-only. A completed report is independently verified
and reused without new API reads; interrupted page streams are not yet durable
production pagination. Real expected-catalog authority would additionally require
terminal historical enumeration, all target-series reconciliation without date-only
blind spots, exact identity/boundary checks, handling of archived/ambiguous/duplicate
entries, and independent review. A short filtered stream does not by itself prove
that an absent theoretical interval was never listed.

Sources: official Polymarket [market keyset contract](https://docs.polymarket.com/api-reference/markets/list-markets-keyset-pagination),
[event keyset contract](https://docs.polymarket.com/api-reference/events/list-events-keyset-pagination),
[series contract](https://docs.polymarket.com/api-reference/series/list-series), and
[market metadata](https://docs.polymarket.com/market-data/market-details).
