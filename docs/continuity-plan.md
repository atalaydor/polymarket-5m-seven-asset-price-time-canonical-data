# Run 1 continuity capability experiment

This continuation starts at `7c313b1e31f73cbba20465d0ed05d12b52a19bce`, immutable tag `run-1-source-proof-blocked-v0.1.0`. The earlier canaries, recovery proof, acceptance gates and canonical schema remain valid within their stated limits. They are not rerun or replaced by this experiment.

## Bounded native evidence

Two indexed, ledger-bound hours, `2026-08-28/11` and `/12`, are pinned by their manifest bytes. The cohort is the 14 exact previously verified UP/DOWN quote samples from the August 28 source canary: seven markets, one per asset. Their market intervals vary within hour 12; DOGE starts at the 12:00 boundary. This is a representative capability test, not a complete market census or a full-day assessment.

Only standard GitHub-hosted `ubuntu-24.04` runners may read source payloads. The cap is 2.1 billion bytes and 45 minutes. The probe obtains the complete published `book`, `price_change` and `best_bid_ask` product ranges in 32 MB pieces and verifies each aggregate product SHA-256. Other products are skipped. It verifies every referenced column chunk lies in its hashed product, product footer labels and row counts. It does **not** claim whole-file verification or an independently authenticated footer: the footer hash is an observed hash and structure check.

Full product bytes are necessary because the published integrity units are product ranges, not target-token/column hashes. Decode projects only the columns needed for the experiment, excludes book bids, prunes row groups using market bounds, and filters target-token IDs in Arrow before Python conversion. Book asks and change sizes exist only in a temporary sparse file and in memory. Windows receives source metadata and fixed report counters only.

## Exact diagnostic and its limits

1. Reverify the pinned immutable earlier report and all 14 frozen quote samples. Do not reacquire lifecycle mapping or resolution products.
2. Decode source timestamps as integer milliseconds multiplied by 1,000 and receipt times as integer microseconds. Decode prices and transient sizes as exact Decimal. Missing clocks or witness fields remain counted exclusions.
3. Within each target and **selected** witness, sort retained observations by receipt and local sequence. This is a diagnostic ordering hypothesis, not a reconstructed venue stream. Count equal keys, sequence non-successors/regressions and source-time regressions. Never join sequences into a global counter or infer loss from filtered counter gaps.
4. A book replaces the transient ask state. A SELL level change assigns the resulting size; zero removes that level. BUY does not alter asks. Compare reconstructed best ask with the delta's reported best ask and BBA, and compare state before a new anchor with its snapshot. Count boundary crossings with a carried state, without certifying those crossings. Snapshots can reset observed state but cannot establish what occurred before them.
5. Separately compare BBA with delta best asks in the same source-millisecond/selected-witness bucket. Skip and count buckets with multiple candidate asks. Equal source timestamps are not total ordering evidence. Retain unchanged-ask/later-receipt counts; do not synthesize polling or executable events.

Unknown side/invalid exact values, source mutation, incomplete range response, hash mismatch, footer escape, wrong identity/schema, exceeded budget or unexpected output fields abort publication. Successful diagnostic execution still has `continuity_proven=false` and no research authority. Replay disagreements alone are not claimed to prove venue loss: selected-copy merging, cross-product order and source semantics can also cause them.

The product-specific SELL/size interpretation is corroborated by the [officially linked, pinned export documentation](https://github.com/antoninkriz/polymarket-collector/blob/815388e0c782fe3f026d4a59f5d9447c44e0d13b/docs/PARQUET_EXPORT.md#price_changeparquet). It does not establish an exact deployed native merger revision. The [independent source review](continuity-source-review.md) distinguishes this corroboration from current native evidence.

## Acceptance question and counterexample

The unchanged daily gate requires target-token continuity/reset evidence; no number of matching replay checks substitutes for it. Current native V3 exports collector counters, selected-copy witness provenance, duplicate suppression metadata and aggregate audits. They do not export a venue-contiguous sequence/recovery ledger, token-specific gap/connection/subscription epochs or the discarded per-witness receipt/sequence vectors.

The corruption fixtures distinguish a persistent missing update (detected by a later BBA/snapshot disagreement) from an unrecorded, reverted excursion. In the latter, both the add and remove are missed before collector admission by every witness. A common later non-touch update makes subsequent snapshot state **and last-change timestamp** identical. Local counters, all retained rows, range hashes and aggregate audits can therefore be identical despite different intervening asks. This is an identifiability failure of the current evidence, not a claim that a particular real excursion occurred.

## Publication boundary

Only fixed nonnegative integer diagnostic counters, bounded numeric telemetry, explicit product integrity metadata, fixed explanatory enums and the hash-pinned earlier depth-free quote cohort may enter the diagnostic report. No Event, State, source level, quantity, raw payload, arbitrary nested field or new free-text source content is serialized. No canonical row is emitted. Canonical source/product allowlists, quote validator, receipt semantics and certification gates remain byte-for-byte unchanged.

Report publication stages and independently reads every asset, seals a native immutable Release, then independently verifies all sealed bytes. These are blocker evidence releases, never certified days or windows. Production remains disabled unless native evidence resolves the identifiability failure and the remaining original completeness gates independently pass.

Attribution: PendulumFlow native V3, CC BY 4.0. See [current format](https://archive.pendulumflow.com/formats/v3), [data notes](https://archive.pendulumflow.com/data-notes), [LLM reference](https://archive.pendulumflow.com/llms.txt), and [audit](https://archive.pendulumflow.com/audit). Exact document/manifest observations are recorded in `continuity-source-observations.json`.
