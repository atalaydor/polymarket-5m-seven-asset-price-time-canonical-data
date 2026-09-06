# Target-first salvage remains blocked

The final target-first attempt reused the complete retained V3 projection without
requesting any PendulumFlow archive bytes. It proved a useful narrower fact: terminal
first-party series queries independently returned 6,048 distinct target contracts for
2026-08-25, 2026-08-27 and 2026-08-28, with exact interval, condition, market and
aligned UP/DOWN token identities. That returned cohort is independent of V3 quote
presence.

It did not prove the required exhaustive historical target denominator. The retained
first-party interface evidence has no historical deletion/tombstone contract, no
transactional as-of snapshot, and no closure for moved or null-dated membership. A
complete 288-slot returned grid is observed corroboration, not a rule excluding an
additional or relisted target. The retained V3 index still has 170,369 condition IDs
without identity records. None is proven to be a target, but none may be called
unrelated merely because it is absent from the current first-party query result.

The minimum additional authority is one of:

- first-party historical listing/tombstone or immutable as-of catalog evidence that
  closes these seven series for the proposed days, including moved, deleted and
  relisted entries; or
- positive first-party identity/exclusion evidence for the subset of the 170,369 V3
  conditions capable of belonging to those seven target series and days.

This is the same missing historical-membership fact preserved at v0.4.0, narrowed to
the target-first join. No further archive-wide classification or V3 acquisition is
justified.

## Rejected tentative outputs

Actions run `34047329275` used zero V3 source reacquisition and produced diagnostic
objects before independent review completed. They are immutable historical artifacts,
not certified authority:

- target catalog Release `383656295`, tag
  `target-catalog-v1-67a645e177e9efb19849c1d466fb53d4700197de57cdb48b6fb6cafaf9329cc8`;
- tentative day Release `383658043` for 2026-08-25;
- excluded day Release `383658096` for 2026-08-27;
- tentative day Release `383658310` for 2026-08-28;
- tentative window Release `383658420`, tag
  `target-window-v1-cab0a284a23a94113d85acacd2b9416993fe18586bff4bab83b10c44761282bd`.

The window's embedded `research_import_allowed=true` is rejected. Its independent
verification did not finish, no `observed-current` reference was created, and current
code fails closed for all target-day certification, window publication and window
verification. Independent review also found the tentative consumer failed to
reconstruct the full expected retained shard set and therefore could accept a
manifest-selected subset. This is a second sufficient reason the tentative window is
not authority.

`PENDULUMFLOW_V3_OBSERVED` v1 and all earlier continuity/catalog blockers remain
unchanged. No certified day or current window exists. `research_import_allowed=false`.
Future acquisition and scheduled accumulation remain stopped.
