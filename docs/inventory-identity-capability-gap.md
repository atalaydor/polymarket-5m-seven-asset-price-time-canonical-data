# Pinned V3 inventory identity closure is blocked

The first full `PENDULUMFLOW_V3_OBSERVED` v1 production projection reached its strict
identity-closure gate. The pinned inventory and every planned mapping/data partition were
successfully acquired, content-addressed, sealed and reconciled. The data products then
referenced 170,369 distinct condition IDs for which no classifying `new_market` row exists
anywhere in that same pinned source generation.

This is a new and narrower native evidence gap. These condition IDs are present in the
authorized source denominator through `best_bid_ask` and/or `market_resolved`, but those
products do not supply the asset, five-minute interval and two-token orientation needed to
decide whether a condition belongs to the seven-asset target projection. Treating every
unmapped condition as out of scope would make the successfully mapped target set define
its own completeness and would violate the frozen source-inventory claim.

The gap is not proof that an unresolved condition is a target, and it is not a claim that
future V3 generations can never supply the missing evidence. It does not require an
exhaustive historical Polymarket listing universe, continuous price state, missed-event
exclusion, mathematical first crossing or sender reconstruction. The v0.1 through v0.4
checkpoints remain truthful for their original claims.

## Real closure evidence

Production run `34036701676` at commit
`bc18255ce620507a4eda4ffa0b3ae73c7baf4225` pinned inventory generation
`ead9a909a8c4fa5ad638a111040087609f6e7ac88c95b3f4596786810586bcc0`,
catalog generation `305b1e9b81cea2a844f9d9aa48c4a1b70cc7d9dc0d53a7bee369c3423c79a9de`
and data-index generation
`24254f9fc394e161f916285cd8ddbac6644cdb7de1f7524d2f9c323b0d38070f`.
It completed all 116 planned data partitions and published a 405,302,696-byte immutable
index. Accepted partition reports bind 40,488,664,657 source bytes across 460 published
receipt hours. Those report sums include durable partitions reused by the resumed run;
they do not claim that run `34036701676` freshly transferred all 40.49 GB. Its 8,370
seconds from planning through index publication is an inventory-equivalent completion
rate of 4.84 MB/s, while summed shard wall time shows decoding/projection as the bottleneck.

Deep-verification run `34044977198`, job `101518323111`, at commit
`9fc8aab3712fcf69a8131c4608423369d7ae8d73` independently reverified the complete source
inventory, every mapping partition, the exact expected data-partition identities/order,
and every immutable encountered-condition artifact. It recomputed 170,369 unique
unresolved IDs across 116/116 partitions, 5,876,014 summed per-partition references and
zero conditionless BBA/resolution rows. The sorted unresolved-set digest is
`11c7ae4f3732a232dbb07c183b73a7b7fa655a7e52af211231514020bfea3984`.

The compact immutable evidence is Release
`inventory-identity-gap-v1-20e03c76f4b665f0d4966dcaa5c572fa1adcb073c3e595bb00d8a95f1c275f21`
(ID `383646042`), asset ID `547403584`, SHA-256
`20e03c76f4b665f0d4966dcaa5c572fa1adcb073c3e595bb00d8a95f1c275f21`,
3,304 bytes. A prior diagnostic Release with incomplete reporting remains immutable
historical evidence and is not the accepted pin.

## Certification outcome

The green per-day jobs published assessments, not authority:

| UTC day | Status | Markets | Observations | Reasons |
| --- | --- | ---: | ---: | --- |
| 2026-09-03 | EXCLUDED | 2,009 | 5,968,996 | unresolved source membership; missing ask-side evidence; five missing native resolutions |
| 2026-09-04 | EXCLUDED | 2,015 | 6,624,910 | unresolved source membership |
| 2026-09-05 | EXCLUDED | 2,016 | 4,505,198 | unresolved source membership |

No certified day, immutable window Release, or `observed-current` ref exists. The window
job failed closed with `no certified day exists; current research authority unchanged`.
The production cron was removed after the blocker was confirmed; manual dispatch remains
available only for a later evidence-backed continuation.

The sealed September 3 manifest lists those same five missing markets under both
`missing_resolutions` and `contradictory_resolutions`, and reports 2,009 rather than 2,004
markets with resolution evidence. Independent review traced this to a `defaultdict`
read-side mutation in the certification accounting. The code now treats only two or more
distinct winners as contradictory and counts nonempty winner sets. The immutable manifest
is preserved as the historical assessment; its contradiction label and resolution count
are not accepted as source facts. The identity-closure exclusion remains independently
sufficient and unchanged.

The gate can reopen when a content-bound native V3 identity/lifecycle mapping exists for
every unresolved condition ID, or native evidence supplies a supported exclusion or day
bound for each relevant unresolved ID. Newly published evidence requires a new pinned
inventory generation and new content-addressed catalog/day assessments. No threshold or
profile relaxation is authorized.
