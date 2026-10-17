# Issue #67: artifact identity, duplicate prevention, and feeding feedback

## Latest review checkpoint: new findings on #147–#149

Fresh inventory after #150: 41 findings total (including the original extra review
body finding), 24 resolved and 17 outstanding. #150 repair `d429a3736` is published
and all three threads are resolved. #151 carry-forward `bbea4f9f6` is published;
offline cleanup, lifecycle tests and native build pass. Its test now links the
existing shared lifecycle stubs. #152 and later have not received these repairs.

The scan added three findings on #147, two on #148 and one on #149. Active work
returns to #147 (`branch/issue-67-copyover-evidence`) in
`/home/aiwithapex/projects/duris-issue67-writer-backpressure`:
- Route failed native recovery to the existing graceful shutdown, avoiding exit
  while worker threads are joinable.
- Recheck the recovery-claim name immediately after publication and before any
  socket mutation/exec. On conflict, keep the live process and both evidence files.
- Mark embedded native owner revisions present, backporting the already tested
  #149 integration; this also addresses #148's duplicate flag finding once carried.
Outcome/files/proof: existing comm startup and copyover publication paths, native
projection reader and existing failure/custody/evidence harnesses; no new locking
service or format. Actual startup-branch and late-claim regressions fail before
repair; post-fix startup/thread-join, late-claim save/exec refusal, normal copyover
custody, projection/format evidence, native build and tidy pass. Evidence:
`bin/analysis/pr147-shutdown-*`, `pr147-claim-*`, `pr147-revision-after.log`,
`pr147-followup-*`. Publication is next.

Next: finish/publish these #147 repairs, carry to #148 and fix its foreign-vnum
canonical-release finding, then fix #149's native NPC completeness finding.
Carry through #150/#151, then #152/#153 and resume #154, #155, #156, #157, #162.
The full latest inventory is `bin/analysis/review-refresh-after-150.json`.

## Additional #141 review: saved-room source keys

A subsequent review identified cross-key parents inside the same room. The reader
now compares `saved_items.item_key` as well as room ownership, matching the real
saved-item loader's source boundary. A disposable SQL regression reproduces the
old accepted cross-key link and retains a valid same-key control. The disposable
SQL fixture, maintained-schema queries, native build and format/tidy pass. Evidence:
`bin/analysis/pr141-room-key-*.log`. This is an additional finding beyond the initial
32; fixed in `c3fae0f61`, pushed, and its thread is resolved.
Carry this repair through the dependent branches, then resume the #145–#147 checks.
The #145 transaction contract also needs its stale inline-ownership assertion
updated to follow the shared overlap planner.

## Oldest-first code-review follow-up — 2026-10-17

The current goal is to address every existing review finding, in PR creation order.
The initial inventory contained 31 unresolved inline threads across 14 PRs plus one
additional finding in #139's review body. #132/#133 repairs are already published
and resolved; #134–#137 have no outstanding findings. No merge is part of this pass.

Current work: carry-forward through #145–#147 in
`/home/aiwithapex/projects/duris-issue67-writer-backpressure`.
Published repairs: #138 `ba2f3f79f`, #139 `5df732237`, #141 `1bf1d5986` plus
`c3fae0f61`, #142 `e29ab3926`, #143 `d0845890f`, #144 `136b65c0f`.
Their review threads are resolved, and #139's additional review-body finding is
addressed. The newer saved-room fix has passed inherited SQL-reader/build checks
through #144. Fourteen findings have been addressed, including the later #141 one.

#145's native pipeline checks pass. Its transaction source contract still expected
inline parent validation after the overlap refactor moved that validation to
`world_recovery_read_object_record`; the assertion now follows that real call and
checks parent validation in the shared codec. Validate it, publish the carry-forward,
then continue through #146/#147 to #148. These three PRs had no open review findings
in the initial scan. Preserve all existing source-boundary regressions.

**Carry-forward requirement:** populate `custody_owner_revision_found` from actual
revision authority in later readers and have the #148 classifier reject missing
revision authority. Preserve legitimate flat recovery by obtaining its real owner
revision evidence before enforcing this check. Do not drop the flag when later
PRs move the shared projection type.

Remaining review sequence (initial inventory, oldest first):
- #139: all 3 findings addressed and published.
- #141: all 3 owner/revision evidence findings addressed and published.
- #142: root-compatible unreadable-store regression addressed and published.
- #143: both blob-reader findings addressed and published.
- #144: all 3 Redis retry/state/test-contract findings addressed and published.
- #148: 4 identity marker, vnum, repeated-UID and tombstone findings.
- #149: 1 recovered-NPC evidence completeness finding.
- #150: 3 legacy hydration/retirement/partial-NPC rollback findings.
- #154: 1 fatal-boot diagnostic retention finding.
- #155: 2 retained-row/pet overlap findings.
- #156: 3 source-ID, foreign-vnum and foreign-owner qualification findings.
- #157: 4 audit completeness/noise/quantity/revision findings.
- #162: 1 pending-action preservation finding.

Full fetched review/thread bodies and pagination evidence are retained privately in
`duris-issue67-delivery/bin/analysis/open-review-details.json`. Every fetched page
was complete. Refresh live reviews before final closeout. The implementation
checkpoint below is historical context for this PR, not the current review status.

Tracking: [Duris #67](https://github.com/LuminariMUD/Duris/issues/67).
Implementation branch: `branch/issue-67-artifact-identity`.
Status: AR-01 executable acceptance cases and source boundary mapped; identity
implementation in progress; independent feeding feedback implemented on
`branch/issue-67-feeding-feedback`, with direct timer arithmetic repaired on
`branch/issue-67-direct-feed-timers` and conservative reward conflict isolation on
`branch/issue-67-reward-conflicts`. AR-02 storage is implemented on
`branch/issue-67-canonical-storage`. Canonical snapshot/hydration is implemented
in PR #137 on `branch/issue-67-identity-snapshots`; writer backpressure is ready
in PR #138, and the common flat artifact authority is ready in PR #139 on
`branch/issue-67-flat-artifact-cache`. Numeric/flat/SQL blob readers and the SQL snapshot
aggregate are ready in PRs #141–#143. Redis generation/floor pinning is ready in
[PR #144](https://github.com/LuminariMUD/Duris/pull/144) on
`branch/issue-67-pinned-recovery-evidence`. Pinned Redis item/NPC projections are ready in PR #146; native copyover pinning
and projections are ready in [PR #147](https://github.com/LuminariMUD/Duris/pull/147).
Combined source assembly/custody correlation, NPC reconstruction qualification,
canonical classification and admission remain open.
No operational repair started.

Current copyover evidence checkpoint:
[PR #147](https://github.com/LuminariMUD/Duris/pull/147),
`branch/issue-67-copyover-evidence`, based on PR #146 and ready for review. Outcome: pin and frame-validate the bounded native copyover image before
boot, restore exactly that image, preserve failed/uncertain images and newer
published files, project ground UID trees and label NPC vnum hints as fresh
reconstruction. Non-goals: fabricate a physical UID for historical NPC hints,
introduce another NPC format/writer, choose a conflict winner or operate production.
Files: existing copyover reader and pure native-tree handoff inspector, boot caller,
population projection, focused fixtures and this plan. Proof: real save/exec/recover,
framing/truncation/version failures, unchanged pinned input after replacement,
complete NPC vectors and field/custody preservation, backend builds and checks.

Ablation decision: retain the plan's explicit proven-absent non-durable NPC
predecessor route. Vnum-only NPC images are reconstruction requests, not stable
physical UID payloads. Fresh admission must still wait for complete evidence and
must never bypass another saved/canonical UID. A new NPC item format would also
need to replace separately restored shop stock; it is unnecessary to enforce
that admitted-creation contract. Do not add a parallel ownerless item loader or
invent database/NPC custody merely to deserialize these hints. This does not
waive any admission, availability, rollback or recovery acceptance requirement.

Focused repair ready for review in [PR #145](https://github.com/LuminariMUD/Duris/pull/145):
`branch/issue-67-recovery-floor-overlap`, based on PR #144. Implementation commit:
`b988dc7b5e794f5033cdbf41197f850926032291`. Outcome: retain floor trees with unseen child UIDs instead of
consuming them as duplicates; validate even fully repeated trees before skipping.
Non-goals: picking a newer tree or changing canonical identity. Files: recovery
codec/planner, existing native fixture and this plan. Proof: the new actual
planner regression fails before the repair and passes under ASan/UBSan after it;
existing codec controls and the native build pass. The pure native-tree validator
is shared with the source-reader work below so inspection and materialization use
the same semantic boundary, without live template/custody calls in inspection.

Finding while mapping recovery: the actual planner considered a whole floor tree
redundant when any UID overlapped the generation. A generation with root 500 plus
a journaled `{500, child 501}` restored successfully while discarding child 501.
The new native pipeline case reproduces that failure before repair (assertion in
`recovery-population-overlap-before.log`). Repair: validate the complete floor
tree and skip it only if every UID is already held; partial overlap then refuses
before custody reconciliation or any materialization, retaining the original
Redis generation/floor for disposition. This repair is separate from adding the
source projection API. Fully repeated valid trees retain existing behavior.

Current recovery population checkpoint:
[PR #146](https://github.com/LuminariMUD/Duris/pull/146),
`branch/issue-67-recovery-population`, based on PR #145 and ready for review. Outcome: project the pinned
Redis ground graphs and retained NPC reconstruction evidence without constructing
objects. Reuse the same pure object-tree validator as the real recovery planner.
Keep generation/floor provenance, repeated-UID history, partial-overlap conflicts
and the distinction between unqueried versus missing custody. Non-goals: treating
NPC reconstruction records as stable item identities, choosing a conflict winner,
copyover completeness or production operations. Files: population model/reader,
its native fixture, minimal custody-evidence annotations in existing readers,
build registration and this plan. Combined classification and early boot
publication still require copyover/NPC qualification afterward. Details below.

Current recovery checkpoint: [PR #144](https://github.com/LuminariMUD/Duris/pull/144),
`branch/issue-67-pinned-recovery-evidence`, based on PR #143 and ready for review.
Outcome: prepare and retain one coherent generation/floor cut before boot, expose
ready/absent/disabled/failed evidence explicitly, restore exactly those bytes and
consume only matching generation/floor data. Non-goals: canonical choice, NPC item
identity changes, copyover admission or production operations. Files: existing
Redis runtime/store, boot caller, focused live Redis/runtime fixtures and this
plan. Proof: real publication and same-count mutation/head-change cases, immutable
restoration input, atomic consume refusal/preservation, failure vs absence, normal
recovery controls and required builds. Redis WATCH seals the existing paged
read and compare retained bytes during atomic consume; add no new key/version,
lock service, retry queue or recovery format.

Current SQL source checkpoint: [PR #143](https://github.com/LuminariMUD/Duris/pull/143),
`branch/issue-67-sql-population-blobs`, based on PR #142 and ready for review. Outcome: bounded SQL
auction, legacy pickup, collector and embedded-history pages, plus an atomic
aggregate under one read-only repeatable-read snapshot. Preserve unknown
identities, history roles and explicit quarantine; inspect bytes without
materializing objects. Non-goals: canonical choice, recovery completeness, boot
admission or production operations. Files: existing population reader/header,
focused database fixture and this plan. Reuse the existing page interface and
payload codecs; no delivery store is added because SQL delivery transactions
already write `player_items`. Proof and continuation details follow below.

Preceding flat source checkpoint: [PR #142](https://github.com/LuminariMUD/Duris/pull/142),
`branch/issue-67-flat-population-sources`, based on PR #141 and ready for review.
Outcome: stage flat-file
payload projections, including offline player
and pet files, private/account locker chests, corpses, legacy saved trees, current
rooms and shop stock, retained auction/collector and delivery payloads, and
embedded legacy coin history. Reuse existing bounded codecs
and readers. Keep conflicting custody separate, retain ordinary ancestors and
unknown UIDs, and publish no prefix after any failed read. Non-goals for this
source chunk: canonical selection or new gameplay permission. Files: population
reader, required real store readers, focused native fixture and this plan. Proof:
seed actual flat stores, verify all projections and failures, and build both modes.
Recovery evidence and the aggregate boot consumer remain required afterward.

Population implementation in progress: `branch/issue-67-population-evidence`,
based on PR #140, in `/home/aiwithapex/projects/duris-issue67-plan`. Build one staged
population reader for the artifact service, using the real payload stores and
custody evidence before population. Start with bounded SQL pages across all
eight numeric payload stores (player, pet, locker, legacy account locker, corpse,
room, shopkeeper and siege), retaining effective flags, unknown UIDs, parentage
and custody disagreements. Then cover auction/collector/delivery blobs, flat
equivalents and recovery evidence before classifying canonical/absent/unresolved
records or wiring admission. A numeric-table page is partial source evidence,
never a completeness or absence claim.

Outcome for this work: complete staged physical-candidate evidence for boot and
audit; no first-traversal winner, destructive cleanup, production read or new
writer. Files: artifact population reader/service and actual storage readers,
their focused executable fixtures, boot order and this plan. Proof must include
real disposable-database pages/failures, all supported flat/recovery domains,
atomic publication on complete success, and boot-before-population integration.
Do not describe a source-reader prerequisite as completed population/admission
work. The bounded numeric SQL page contract below is ready as a focused dependent
review chunk in [PR #141](https://github.com/LuminariMUD/Duris/pull/141); its
aggregate consumer and remaining domain readers are still open.

Current checkpoint: [PR #140](https://github.com/LuminariMUD/Duris/pull/140),
`branch/issue-67-recovery-numeric-evidence`, based on PR #139 and ready for review.
**Outcome:** Redis boot-head and floor UID reads accept complete positive unsigned
decimal values only; a genuine missing head is the only successful zero result.
Malformed, negative, overflow, trailing or embedded-NUL input remains failed
evidence. **Non-goals:** complete population classification, recovery-generation
pinning or a recovery format change. PR #144 now implements pinning; complete
classification still remains required. **Files:** the existing
Redis runtime, a native reader fixture in the existing live Redis driver, and
this plan. **Proof:** exercise the
actual readers on an isolated Redis server, including a negative floor field that
previously matched unsigned-maximum UID bytes; retain the existing world-store
and recovery controls, run the required builds and changed-line checks.

Completed prerequisite: [PR #138](https://github.com/LuminariMUD/Duris/pull/138),
`branch/issue-67-writer-backpressure`, based on PR #137 and ready for review.
**Outcome (implemented):** bound the existing persistence writer during a storage outage before
adding flat artifact captures. **Non-goals:** new queues, fallback writers,
configuration, or production operation. **Files:** worker implementation/header,
its existing executable test, pipeline contract, and this plan. **Proof:** hold
the real writer, exhaust byte/job capacity, reject without changing admitted
captures, allow fitting tail replacement, consume completions to release slots;
run the focused test and required native build. Fixed limits reuse the existing
`unavailable` result, so no new retry mechanism or state is needed.

The writer now admits at most 4,096 jobs including undrained completions, and
128 MiB of declared queued/in-flight payload. It rejects capacity with `ENOSPC`
without evicting admitted captures; a fitting tail replacement remains allowed.
Verification passed: `python3 tests/async/test_player_save_worker.py` (held-writer
byte/job boundaries, old-capture preservation, tail replacement and completion
slot release), `python3 tests/async/test_critical_command_coordinator.py` (existing
ordering/refusal/fence controls), `make -C src -j2`, `scripts/format.sh`,
`scripts/tidy.sh`, and `git diff --check`. Build/tidy/control output is retained
under ignored `bin/analysis/issue67/writer-backpressure-*` in
`/home/aiwithapex/projects/duris-issue67-writer-backpressure`.
This qualifies admission behavior, not production outage throughput.

Combined lifecycle review found that the artifact/guild drain did not consume
generic writer completions while retrying dirty captures. With bounded admission,
a completed backlog could keep every slot occupied until the drain timed out.
The existing drain now calls the game-thread completion consumer before retry.
The new existing-runtime-fixture case `drain-capacity` fails at the drain assertion
before this repair and passes afterward; the native writer fixture separately
proves the actual completion-slot accounting. No new drain or queue is introduced.

Current checkpoint: [PR #139](https://github.com/LuminariMUD/Duris/pull/139),
`branch/issue-67-flat-artifact-cache`, builds on PR #138 and is ready for review in
`duris-issue67-plan`. The earlier unpublished `branch/issue-67-flat-artifact-memory` and
`branch/issue-67-flat-artifact-authority` retain local checkpoints `5dd8be6cb` and
`713c00c82`; their changes are carried forward here on the updated prerequisite.
PR #139 replaces the flat-file hot getters/direct writes with the existing
artifact/soul memory maps and immutable captures on the same persistence writer.
The previous flat backend bypassed those maps; a separate identity-only map
would have created two competing authorities and retained partial legacy writes.

Outcome (implemented): complete flat artifact snapshots, current-state reads during storage
failure, receipt-safe retry and boot hydration; no new worker or automatic
fallback. Non-goals for this prerequisite chunk: canonical population selection
and new object admission. Files: artifact service, flat snapshot repository,
writer job label/boot phase, flat SQL-compatible bind wrappers and focused
fixtures. Proof must hold the writer, show memory changes before storage, keep
live state through corrupt/unavailable storage, exercise retry/late ACK, and run
the maintained flat build/journey plus SQL regression controls. Population and
admission remain required after this common authority exists.

Ablation removed the replaced file-backed gameplay repository APIs and their
obsolete helper tests after a tracked caller audit found no remaining server or
tool callers. The shared artifact service supplies those behaviors; fixtures now
seed through complete captures. Boot catalog loading, player-deletion atomic
release, persisted reports and room-transfer guards remain required consumers.
The flat `syncdb` command explicitly refuses incomplete reconciliation pending
the full population audit.
Prepared: 2026-10-16, against freshly fetched `origin/master`
`9b4d7384825aa9a19a990e68f939fb6e6c04c011`.

This plan belongs to the **Duris server** repository. DurisWeb is a separate
repository and needs no change for this issue. Publication of this document does
not authorize production inspection, cleanup, migration, restart, or deployment.

## Outcome and implementation boundaries

One allowed gameplay copy of an artifact vnum must remain identifiable through
creation, ownership changes, saves, offline storage, and recovery. An extra copy
must neither change that artifact's timer/soul/location nor suppress legitimate
guild or other artifact rewards. Resolve actual version conflicts from evidence,
and use the requested positive feedback:

> You feel a sense of satisfaction from above.

Follow [AGENTS.md](../../AGENTS.md), [conventions](../guides/CONVENTIONS.md),
[ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md), and the
[current reward contract](../persistence/CRITICAL_COMMAND_PIPELINE.md#artifact-and-guild-rewards-live-in-memory).
Mutable state stays on the game thread; the existing writer saves immutable
captures in order. No SQL/Redis lookup in object movement, feeding, or reset hot
paths, no second writer, and no synchronous persistence fallback.

Start on this issue branch with small dependent commits and publish focused PRs
as chunks are ready; use dependent branches/PR bases for subsequent chunks. The work items below
belong to #67; their IDs identify checkpoints, not additional uncreated issues.
[#58](https://github.com/LuminariMUD/Duris/issues/58) is a **closed, merged
dependency**, not outstanding work to reimplement or reopen. The merged
[#96](https://github.com/LuminariMUD/Duris/pull/96) changes artifact rewards and
callbacks; retain that current content when evaluating old versions.

## Current code findings and corrections to the issue

The issue's October 13 probes used `7a2a63447`. The following observations are
from the current base above. Earlier production population claims and historical
incident details have not been independently verified.

1. **Physical identity and artifact state still use different keys.**
   [Object construction](../../src/world/db.c) in
   `instantiate_object_template()` assigns a fresh UID and links the object into
   `object_list`. Staff `do_load()` and `clone_obj()` in
   [actwiz.c](../../src/cmd/actwiz.c) can create separate physical copies.
   [artifact.c](../../src/guild/artifact.c) still keys `artifact_rows` and
   `artifact_binds` by vnum. `artifact_update_sql()` excludes trusted holders;
   `artifact_update_location_sql()` and `remove_owned_artifact_sql()` do not
   compare the object's UID with a canonical UID. Removal can reset the shared
   binding. These source paths still support the reported interference; this
   planning pass has not executed their real SQL or production journey.

2. **There is already a nullable physical identity link.**
   [artifact_domain_state](../../migrations/artifact_guild_outcome.sql) has
   `item_uid`, `item_revision`, an item UID index, and a foreign key into
   `item_current_owner`. The current artifact snapshot/mirror does not populate
   or validate that link. Reuse and qualify it before inventing another durable
   registry. An index/FK alone does not prove canonical selection or uniqueness.
   [item_ownership_runtime](../../src/item/item_ownership_runtime.h) is UID keyed
   and hydrated for active domains; it is not a complete inventory of every
   offline artifact. A stale custody row without a payload is not proof that a
   physical artifact still exists; see [database custody rules](../reference/DATABASE.md).

3. **The reset guard still means owned, not present.**
   `get_artifact_data_sql()` returns `owned`, even when an unowned row exists.
   `reset_zone()` O/P/G/E branches and
   [recovered NPC equipment loading](../../src/world/world_recovery_npc_items.c)
   use that distinction. The current tracked `artifact.respawn` is **1**;
   ordinary artifact respawns therefore differ from boot/forced mode. The
   current [Shabo reset](../../areas/zon/shabo.zon) still contains
   `P 1 51005 3 32870 100 0 0 0`. Inspection confirms the population-limit bypass
   and owned-only guard; the older three-copy reset probe was not rerun here.
   Do not describe default ordinary resets as already reproducing three copies.

4. **Duplicate equipment still rejects rewards, but at a different boundary.**
   [Capture](../../src/guild/artifact_guild_state.c) appends equipped artifacts
   and now calls `artifact_guild_payload_valid()` before returning `ready`.
   The [codec](../../src/guild/artifact_guild_command.c) rejects duplicate vnums.
   A fresh UBSan executable probe using the current capture, transaction, codec,
   and existing reward fixture confirmed that two distinct-UID copies plus an
   unrelated artifact and eligible guild produce `invalid` capture. Submission
   returns false before **any** feed or guild application. Removing the second
   copy admits both feeds and guild prestige. Thus the old claim that rejection
   first occurs during command construction is outdated, but reward loss remains.

5. **Preserve the merged memory-authority repair.**
   [Submission](../../src/guild/artifact_guild_transaction.c) applies valid
   captured rewards and sends feedback immediately, before history admission.
   History completions do not grant rewards or send feedback again. Capture
   still calls `artifact_feed_state(vnum, ...)` without checking physical UID or
   custody; the fresh probe admits actor 42's feed with fixture owner 43.
   This proves the capture boundary, not real cross-player SQL persistence.

6. **Same name is not a duplicate definition.**
   The current source-inventory test regenerates the tracked inventory exactly:
   169 artifact templates, 29 golden-token placeholders, 80 literal bindings,
   69 callbacks. The source parser rejects repeated artifact vnum definitions
   in AREA-listed object files. Current assignments still bind `stalker_cloak`
   to 67281 and `artifact_stone` to 67280; their direct zone loads remain.
   [Player restoration](../../src/player/player_load_items.c) overwrites the
   constructor's temporary UID with the saved UID and reapplies saved instance
   fields. UID-level load validation is not vnum uniqueness. Old saved overrides,
   intentional distinct-vnum variants, and proc assignments require separate
   classification; no production instances were inspected for this plan.

7. **Existing repair commands still need identity protection.**
   `arti_sync_sql()` traverses live objects; MariaDB `arti_syncdb_sql()` joins
   active player saves by vnum and clears bindings. Its newer asynchronous
   generation check protects current memory against obsolete callbacks, but
   does not choose a canonical copy. Flat-file reconciliation rejects repeated
   vnums. `clear`, `purge`, and `eat ... update` have distinct tracking semantics;
   none is an approved automatic duplicate repair.

8. **The requested wording is implemented in PR #133.**
   `publish_messages()` and the active monolith direct-feed path through
   `artifact_feed_sql()` now say “You feel a sense of satisfaction from above.”
   The obsolete deep/light positive wording split is removed. Valid capped feeds
   retain positive feedback; negative text and live/history publication timing
   are unchanged. The direct path checks its existing tracked-owner restriction
   before publishing feedback. Treat “from above” as requested wording, not a
   verified historic quotation. Canonical UID eligibility and command-wide
   monolith message coalescing remain outstanding in AR-05.

## Decisions that guide the implementation

- Enforce one gameplay copy **per artifact vnum**, not per display name. Preserve
  distinct-vnum templates until a reviewed disposition establishes a conflict.
  Keep placeholder tokens in the inventory without inventing abilities or loads.
- Prefer the existing artifact record plus its canonical UID and a small bounded
  game-thread lookup. Hydrate all required durable identity evidence before zone
  population/recovery admission. Maintain current live reservations immediately;
  reserve unresolved vnums rather than treating unknown state as absence.
- Separate **new gameplay admission**, **hydration of an existing UID**, and
  **temporary inspection**. `read_object()` alone cannot decide: it runs before
  saved UID/flag overrides and is also used for inspections. Do not put a blanket
  rejection there or count every object in `object_list` as a gameplay copy.
- Proposed staff policy: `load` and `clone` that place items in the world obey
  the same uniqueness rule as other creation. Inspection objects remain temporary
  and cannot claim, release, feed, save, or enter circulation. Do not preserve an
  unlimited transferable staff-copy exception. If staff specimens are required
  later, obtain a specific policy and prove their isolation before adding them.
- Match the canonical physical UID before changing shared artifact state. For a
  valid UID, use current memory custody, not an asynchronously stale SQL owner.
  Missing/ambiguous identity excludes that artifact's contribution and diagnoses
  the conflict; it must not reject unrelated guild or artifact contributions.
- Preserve the codec's one-entry-per-vnum rule and #58's source identity, cap,
  soul rules, immediate application, snapshot retries, and history-only replay.
  Do not solve reward rejection by allowing duplicate entries in the codec.
- Production inventory, intended-version decisions, and destructive disposition
  are evidence gates in later work. No automatic oldest/newest/first-traversed
  winner, wholesale saved-stat normalization, compensation, or UID regeneration.

## Sequenced work items

### AR-01 — Establish the creation, identity, and custody boundary

Dependencies: none. Complete before choosing schema changes.

- [x] Extend the current probe into the existing reward harness as a permanent
  failing regression: duplicate worn vnums, unrelated artifact, eligible guild,
  and cross-player copy. Keep a valid single-copy control and cap control.
- [ ] Inventory every `read_object`, `instantiate_object_template`, and `clone_obj`
  caller. Classify new creation, template/inspection, saved-UID hydration, and
  reconstruction. Include reset O/P/G/E, indirect object tables, Studio/procs,
  scripted rewards, staff clone of containers/mobs, and saved flags that turn a
  currently non-artifact prototype into an artifact. Record reachable seams in
  this document; do not edit unrelated creation mechanics.
- [ ] Map identity evidence across online/offline players and pets, nested item
  trees, NPCs, rooms, corpses, lockers, shops/auctions/collector or delivery state
  where supported, and recovery payloads. Correlate UID, payload, custody owner,
  root/parent, vnum, and active/quarantined/deleted state. Treat two projections
  of one UID separately from two physical UIDs of one artifact.
- [ ] Specify the boot order: classify persistent candidates, establish reserved
  or canonical vnums, reconcile recovery, then admit new population. Identify
  authoritative absence for each domain; missing data or partial scans cannot
  release a reservation. Bound scans and retain continuation/error outcomes.
- [ ] Explicitly account for recovered NPC equipment: current recovery omits
  authoritative NPC item identity and reconstructs items from reset templates.
  Selected route: preserve reconstruction as a fresh-admission request only after
  complete evidence proves that a non-durable predecessor is not recoverable
  elsewhere. This source request does not itself prove absence or justify a UID.
  A known saved/canonical copy must block it. Enforcement and executable NPC
  availability/rollback qualification remain required before checking this item.

Exit: documented reachable paths, identity states, and executable failing cases;
an implementation-ready boot/admission design consistent with memory authority.

### AR-02 — Persist and hydrate canonical identity using existing stores

Dependencies: AR-01.

- [x] Qualify `artifact_domain_state.item_uid` and its FK for the selected design.
  Distinguish an identified canonical UID from absent, unresolved legacy, retired,
  and temporarily unavailable evidence. Handle unclaimed NPC/ground artifacts
  whose UID has not yet acquired a persistent custody row; do not write dangling
  FKs or create fake player ownership to fill the link.
- [ ] Integrate identity with artifact snapshots/mirroring and the existing
  one-writer lifecycle, boot hydration, player/item saves, and owner deletion.
  Prevent a mirror upsert, sync, or late callback from erasing/reassigning the
  canonical UID. Keep live reservations current before asynchronous persistence.
- [ ] Preserve legitimate hydration of the same UID, including an offline owner,
  and atomic rollback of failed staged loads. A rejected/temporary object must
  not clear the real artifact while its constructor UID is replaced or discarded.
- [ ] On legacy ambiguity, reserve the vnum and retain evidence. Keep unrelated
  inventory loadable; do not reject a whole player's valid inventory or destroy
  conflict payloads as a shortcut. Use existing quarantine/disposition patterns.
- [ ] Support the flat-file backend's equivalent identity/lifecycle contract and
  schema/version compatibility; its current vnum conflict check is insufficient
  for canonical-UID lifecycle protection.
- [x] Add schema only when the existing nullable link cannot express a proven
  requirement. Never edit sealed/applied migrations. Any new migration must
  include verification, manifest checksums, bootstrap/legacy convergence and
  runtime compatibility metadata/documentation under the current
  [immutable migration contract](../persistence/IMMUTABLE_MIGRATIONS.md).
  Validate interruption/replay and preserve uncertain legacy rows.

Exit: a canonical UID survives save/reload/restart in both persistence modes;
unknown/conflicting evidence cannot turn into permission to spawn another copy.

### AR-03 — Prevent duplicate admission across creation and recovery

Dependencies: AR-02.

- [ ] Apply a shared, narrow admission decision at the verified gameplay seams,
  before placement or dependent effects. Reserve an admitted UID on the game
  thread so two creations in one pulse cannot both succeed. Roll back only that
  tentative reservation if placement fails. Preserve normal non-artifact loads.
- [ ] Cover O/P/G/E and indirect/scripted creation, staff `load`/`clone`, nested
  clones, and recovered-NPC load paths. Check actual item flags after overrides.
  Forced reset and ordinary population limits cannot bypass artifact uniqueness.
- [ ] Exercise `artifact.respawn` 0/1/2 with boot, ordinary reset and forced reset,
  including the 51005 P-command limit of three. Preserve configured availability
  when no copy exists; merely reducing that one area's limit does not fix scope.
- [ ] Preserve owned offline/corpse protection, legacy ground restore, copyover,
  valid Redis recovery, disabled Redis, failed/partial recovery and forced-reset
  fallback. One canonical artifact must restore exactly once. Failed multi-item
  recovery must restore prior reservations with the rest of its rollback.
- [ ] Keep temporary inspection and replacement of a saved object's constructor
  UID harmless. Provide bounded staff feedback naming the vnum, reason and
  diagnostic reference when gameplay creation is rejected.

Exit: a second gameplay UID cannot enter any mapped domain while an allowed copy
exists, including before an offline owner logs in. Same-UID restoration succeeds.

### AR-04 — Protect shared state during movement and destruction

Dependencies: AR-02; coordinate admission tests with AR-03.

- [ ] Guard location/timer/soul updates and removal by canonical UID. Cover
  nested moves, wear/unwear, mortal/staff/NPC transfers, trading/storage paths,
  death/corpse loot/raise/decay, poof/expiration, deletion, purge, and
  `eat ... update`. Distinguish physical retirement from logout/unloading or
  temporary inspection cleanup; never release a claim for mere dematerialization.
- [ ] A rejected or noncanonical copy cannot change ownership, start/reset/feed a
  timer, bind a soul, clear another copy's binding, or enable a later reset load.
  Retain state for missing/offline owners that could not be loaded.
- [ ] For canonical destruction, define when new creation becomes eligible in
  memory and how ordered snapshots retire old payload/custody and retain removal
  tombstones. Test crash windows and failed saves: stale payloads and old
  acknowledgements cannot revive two canonical UIDs or release a new claim.
- [ ] Replace unsafe vnum-only `sync`/`syncdb` decisions with identity-aware
  validation or explicit conflict refusal. Preserve asynchronous generation checks
  and current-state retries. `clear` must not grant permission to duplicate a
  still-existing item. Do not turn these commands into silent destructive cleanup.
- [ ] Verify per-UID artifact mana stays isolated, and noncanonical extraction
  cannot remove the surviving UID's mana or persistence state.

Exit: survivor UID, timer, soul, custody and mana are unchanged by another copy's
movement/removal; canonical transfers and genuine retirement still work.

### AR-05 — Preserve valid rewards and restore the RP feedback

Dependencies: AR-02/AR-04 identity semantics; can be tested alongside AR-03.

- [ ] At capture, validate each equipped artifact's canonical UID and current
  game-thread custody. Deduplicate contributions by allowed vnum after identity
  validation; skip/quarantine detected copies with a bounded diagnostic. If
  neither copy has a justified canonical identity, feed neither. Preserve other
  valid artifact contributions and independently eligible guild benefits.
- [ ] Keep one delta per allowed artifact. Test canonical plus rejected copy in
  both equipment orders, cross-player copies, unrelated valid artifacts, guild
  construction thresholds and a guild-only result when every artifact conflicts.
  Retain normal PvP soul checks, no-effect, arithmetic failure and cap behavior.
- [x] Restore the requested “from above” text in `publish_messages()` and the
  verified active monolith direct-feed path in PR #133. Preserve colors,
  negative feedback, valid capped feedback and live/history publication timing.
  Existing native reward and direct-feed fixtures cover the wording and the
  direct tracked-owner rejection before feedback.
- [ ] Complete command-wide monolith message coalescing and canonical recipient
  eligibility. Verify no duplicate feedback for several artifacts, history
  retry/completion, replay, or restart. Retain successful one- and
  several-artifact rewards, capped valid feed, no eligible reward, rejected
  artifact-only reward, and guild-only rewards after artifact exclusion.
- [ ] Keep live benefit/message publication immediate after valid apply; a later
  history failure must neither undo a reward nor publish another. Reuse the
  existing diagnostics with controlled reason, vnum/opaque reference and bounded
  repetition; expose an actionable staff notice plus searchable server detail,
  without player/account data, raw SQL, credentials or IP addresses.

Exit: no double-feed and no loss of unrelated rewards; requested wording appears
once at the current valid live reward boundary, never for a rejected/no-effect feed.

### AR-06 — Audit variants and rehearse recoverable reconciliation

Dependencies: AR-01 inventory; run mutation rehearsal after AR-02–AR-05.

- [ ] Extend existing inventory/topology tooling with an artifact-focused dry-run
  report rather than inventing another item authority. Reuse
  [classify_item_topology.py](../../scripts/classify_item_topology.py) where its
  payload/custody checks apply, adding missing world/recovery/domain coverage.
  Report aggregate counts publicly; store exact UIDs, owners, payloads and
  provenance only in owner-controlled private evidence outside Git.
- [ ] Use synthetic fixtures and an isolated development clone first. Classify
  repeated materializations of one UID, distinct-UID same-vnum conflicts,
  stale/inactive/quarantined projections, and intentional template variants.
  The issue's local 430/139004 findings are leads, not current production proof.
- [ ] Compare 32827/67281, 67280/98904, 902/914 and 923–926 using actual object
  definitions, flags/affects/values, reset sites, saved overrides/enchantments,
  effective compiled callbacks, dynamic procs and intended design. Obtain an
  explicit disposition for each confirmed conflict; retain intentional variants
  and all unrelated valid saved enhancements. Source inventory alone is not a
  full 169-artifact behavioral qualification.
- [ ] For each repair candidate, prepare an exact canonical UID/template and
  conflict disposition with preserved source bytes, custody, timer, soul and mana.
  Never pick by traversal order or display name. If a template mapping is truly
  needed, update source/reset/binding/inventory and saved-instance conversion
  together, with proc/stat regressions and reversible, narrowly scoped changes.
- [ ] Rehearse cleanup as dry-run first, then explicit apply to the clone using a
  protected inventory digest, exact preconditions, bounded atomic units and audit
  identities. Unchanged evidence may be applied once; repeat is a no-op, changed
  evidence refuses. Prove restart cannot restore rejected copies from another
  payload/recovery source. Preserve rollback evidence and unaffected-row hashes.

Exit: every actual conflict is resolved or explicitly left blocked on evidence or
owner design; ambiguous cases never trigger broad deletion or normalization.

### AR-07 — Complete executable and gameplay qualification

Dependencies: AR-03–AR-06 implementation and rehearsal.

- [ ] Extend existing harnesses rather than duplicating reward/custody logic.
  Register any new focused regression/database leg in the established runner.
  Prove the new regressions fail when the relevant admission, identity, lifecycle
  or reward guard is removed, not just when source text changes.
- [ ] Run the focused commands below as affected, changed-line formatting and
  clang-tidy, plus `make -C src`. Run ASan/UBSan for identity/lifetime harnesses,
  including nested-container extraction and failed materialization rollback.
- [ ] Exercise real repositories on disposable MariaDB/MySQL for identity
  persistence, FK/null/unowned states, migration compatibility if changed,
  snapshots, failed/ambiguous writes, identity conflicts and idempotent repair.
  Cover the maintained flat-file build/journey, not only SQL source assertions.
- [ ] Run an isolated gameplay journey with disposable characters and configured
  test ports: create one artifact, attempt duplicates by each mapped path,
  transfer/equip/feed with guild rewards, save, logout/login, nest/store/drop,
  die/loot/raise, expire/destroy, copyover and clean/unclean restart. Repeat Redis
  success, disabled and failure/fallback. Verify actual UID population and stored
  timer/soul/custody/feedback after reload, not only in-memory fixture outputs.
- [ ] Include a genuine legacy-conflict fixture: audit, choose canonical UID,
  repair, save/restart, rerun cleanup, then prove both no recreation and no loss
  of unrelated items or valid saved enhancements. Finish with `make test-all`
  and applicable isolated `make test-db`; report partial runs accurately.

Focused entry points (from repository root; only existing files are listed):

```sh
python3 tests/async/test_artifact_source_inventory.py
python3 tests/async/test_artifact_guild_rewards_runtime.py
python3 tests/async/test_artifact_guild_transactional_cutover.py
python3 tests/async/test_artifact_guild_snapshots.py
python3 tests/async/test_mysql_artifact_guild_reward_journey.py
python3 tests/async/test_artifact_offline_owner_loads.py
python3 tests/async/test_combat_artifact_persistence.py
python3 tests/async/test_artifact_cache_codec.py
python3 tests/async/test_artifact_mana_game.py
python3 tests/async/test_artifact_mana_restore.py
python3 tests/async/test_native_artifact_runtime.py
python3 tests/async/test_item_ownership_runtime.py
python3 tests/async/test_player_load_items.py
python3 tests/async/test_item_transfer_creation_batch.py
python3 tests/async/test_world_recovery_npc_items.py
python3 tests/async/test_world_recovery_pipeline.py
python3 tests/async/test_world_recovery_transaction.py
python3 tests/async/test_flatfile_artifact_repository.py
python3 tests/async/run_world_recovery_journey.py
tests/async/run_artifact_guild_schema_mysql.sh
tests/async/run_item_transfer_schema_mysql.sh
./scripts/format.sh --check
./scripts/tidy.sh --rev origin/master
make -C src
git diff --check
```

Read each journey/wrapper's fixture/target requirements before execution; several
need a disposable database/server. Use the current [testing guide](../guides/TESTING.md)
for `make test-all`, `make test-db`, and the supported-engine migration matrix.
These are **future implementation checks**, not claims of completion below.

### AR-08 — Document, review, and separately authorize production closeout

Dependencies: AR-07; production repair also requires actual private evidence and
explicit approval of the concrete procedure.

- [ ] Update architecture/database/reward/recovery and staff-operation guidance
  with the implemented identity boundary, staff policy, conflict behavior,
  audit/apply/rollback steps, and known crash/durability limits. Keep evidence
  private. Add game release news through the Duris repository's established
  release process when an actual release is prepared.
- [ ] Refresh master/head and inspect the final source and evidence before PR
  publication/integration. Reference #67 and the completed #58 dependency; use
  closing language only when the applicable acceptance work is actually complete.
  Respect the repository's linear-history rules and other review requirements;
  hosted CI is not a substitute for local executable evidence or a required wait.
- [ ] Prepare a concrete production runbook: read-only population inventory,
  reviewed variant/canonical decisions, backups and restore proof, writer
  quiescence for consistent cleanup, exact migration/repair commands where
  needed, expected counts/hashes, rollback trigger and service recovery. Obtain
  owner authorization before production audit or any operational action.
- [ ] After authorized rollout, verify actual instances across every supported
  domain, duplicate admission, timer/soul/mana survival, requested feedback and
  save/relogin/restart. Keep #67 open for unmet production/version criteria;
  merging code or publishing this plan does not establish live reconciliation.

Exit: all #67 acceptance criteria have dated implementation and acceptance
evidence, or an explicit outstanding owner/evidence gate. Never mark a draft,
local fixture, or historical investigation as production completion.

## Issue acceptance coverage

- Actual-instance classification: AR-01, AR-06 and authorized AR-08 audit.
- Universal existence/offline/nested protection and staff policy: AR-02–AR-03.
- O/P/G/E, indirect creation, 51005, respawn modes and recovery matrix: AR-03/AR-07.
- Legitimate UID restoration and temporary inspection: AR-01–AR-03/AR-07.
- Transfer, feed, binding, expiration, destruction and noncanonical isolation: AR-04–AR-05.
- Duplicate/cross-player rewards without double-feed or unrelated loss: AR-05,
  preserving merged #58 behavior, and AR-07.
- Confirmed version dispositions, stats/procs and valid enhancements: AR-06.
- Auditable, repeatable, recoverable cleanup with separate production approval:
  AR-06/AR-08.
- “From above” wording and successful/rejected/no-effect message timing: AR-05.
- Permanent regressions and save/relogin/restart journey: AR-07; live AR-08 limits
  remain visible until actually satisfied.

## Planning verification and handoff

### Review stack and current resume point

The current continuation branch is `branch/issue-67-flat-population-sources` in
`/home/aiwithapex/projects/duris-issue67-plan`, based on PR #141. Earlier sections
record evidence at their own checkpoints; the current checkpoints below
supersede their old next-step statements and flat repository APIs.

- [PR #132](https://github.com/LuminariMUD/Duris/pull/132),
  `branch/issue-67-artifact-identity` → `master`: acceptance repros and admission
  map, published at `21bcc2754`. No identity behavior is fixed in that PR.
- [PR #133](https://github.com/LuminariMUD/Duris/pull/133),
  `branch/issue-67-feeding-feedback` → `branch/issue-67-artifact-identity`:
  independent AR-05 wording/feedback chunk. It uses the requested sentence for
  live awards and the active monolith direct feeder, removes the obsolete
  light/deep positive wording branch, and moves the direct path's existing
  tracked-owner rejection before its positive/negative feedback. Negative text,
  valid capped feedback and live/history publication timing are preserved.

Ablation: wording and truthful direct rejection feedback do not require a schema
or canonical selection, so publish this independent portion before the identity
work. No shared message abstraction or new configuration is needed. Files:
`artifact.c`, `artifact_guild_transaction.c`, existing native reward/flat-file
fixtures and this plan/current reward contract. Proof: runtime tests cover one
and several artifacts, valid capped feed, guild-only/no-effect/rejected awards,
duplicate completion, direct light/deep feeds, trusted/soul/cross-owner refusal,
and the original negative text. The direct test links actual `artifact.c`,
flat-file repository and bind lookup, with fixture placement and messaging.
Monolith still feeds per artifact; command-wide coalescing and canonical UID
eligibility remain in AR-05. The two AR-01 expected failures are resolved by
the conservative conflict-isolation checkpoint below.

The following pass for this chunk: reward runtime (baseline plus 2 expected
failures), flat-file artifact repository/bind/gameplay harnesses, transactional
cutover (3/3), combat/artifact persistence contracts, changed-line formatting,
clang-tidy and `make -C src`. This is no claim of full gameplay/restart, database
matrix, production qualification or complete AR-05 acceptance.

While tracing direct feedback, an additional timer defect was found: negative
feed is converted to an absolute value for logging then added to the timer, and
an above-cap positive clamp can therefore increase it further. Repair this as
its own focused chunk, [PR #134](https://github.com/LuminariMUD/Duris/pull/134),
`branch/issue-67-direct-feed-timers` →
`branch/issue-67-feeding-feedback`: compute a signed target once, clamp before
positive addition to avoid overflow, retain an expired nonzero timer instead of
restarting it, and calculate a separate magnitude only for the existing log.
No helper, backend or new state is needed. The direct flat-file harness first
failed with `negative direct feed increased the timer instead of reducing it`;
it now passes negative, above-cap, `INT_MIN` and `INT_MAX` assertions with UBSan
configured to terminate on a violation. Build, formatting, whitespace and
changed-line clang-tidy pass. This fixes shared direct-feed arithmetic for both
backends; it does not prove SQL storage through the flat-file fixture.

The next AR-02 checkpoint below qualifies canonical identity storage; boot
candidate publication remains required after that storage foundation.
No production state has been inspected or changed. No release tag is appropriate
for these unmerged review chunks.

### Flat payload evidence — AR-01/AR-02 prerequisite, 2026-10-17

[PR #142](https://github.com/LuminariMUD/Duris/pull/142),
`branch/issue-67-flat-population-sources` → `branch/issue-67-population-evidence`
adds `artifact_population_read_flat_payloads()` for boot/offline use while no
writers mutate the selected store. It stages all offline player/pet snapshots,
private/public/account locker chests, corpses, retained saved-item graphs,
current room graphs, shop stock, all retained auction/collector payloads,
inbound/outbound materialization receipts including raised pets, and legacy
embedded coin history. Ordinary ancestors, missing UIDs and conflicting custody
remain visible. A metadata-only custody row never synthesizes a payload.

Source roles distinguish stored data, deliveries and history; they do not decide
current existence. Claimed auction blobs, terminal collector payloads, outbound
receipts and legacy coin bytes remain evidence for later correlation. In
particular, an active custody row does not make old coin compatibility bytes a
pending delivery. Their independent payload holder remains unknown. Delivery
operation IDs and catalog order are retained. Pet-receive receipts that never
encoded a pet UID keep their player delivery-pool context without inventing a
specific pet from custody. Legacy pets with no UID use player custody in both
flat and SQL projections, matching actual load behavior.

Existing bounded store codecs/readers remain the source of truth. Small bulk
views expose retained auction claims, collector blobs and materialization
envelopes without replaying rewards or creating objects. One custody inventory
view supplies both embedded-history discovery and correlation, replacing a
second UID lookup/temporary query list. Raw flat owner revisions remain unknown
(zero), so these projections are not runtime custody hydration records.

Auction metadata inspection uses a bounded `write_one_object()` frame reader
instead of `read_one_object()` materialization. It preserves inherited versus
explicit-zero flags and optional saved UID, consumes variable strings, effects,
extra descriptions and native spellbook bitmaps, and validates the exact end.
Its wire contract is the existing native-width/native-endian legacy format;
there is no new serialized format or automatic conversion. No template lookup,
UID assignment, object placement/extraction, timer or soul change occurs.

The aggregate is sealed only after every selected read succeeds. Corruption,
unavailability, noncanonical snapshot names, malformed opaque auction frames,
allocation failure or the shared one-million-record limit cannot publish a
prefix. Directory enumeration is bounded too. Ordinary store readers retain
their existing committed-journal recovery behavior: a non-mutating offline
audit must use a retained store copy. This API is not a live concurrent audit,
world-recovery scan, canonical selector or admission decision. No boot caller is
wired yet; the aggregate service must combine SQL/blob and pinned recovery
evidence before granting any gameplay permission.

Passed:

```sh
python3 tests/async/test_flatfile_artifact_population.py
python3 tests/async/test_legacy_object_identity.py
python3 tests/async/test_flatfile_auction_repository.py
python3 tests/async/test_flatfile_collector_repository.py
python3 tests/async/test_flatfile_shop_trade_repository.py
tests/async/with_disposable_mariadb.sh python3 tests/async/test_artifact_population_repository.py
python3 bin/analysis/issue67/run_mysql8_artifact_population.py
make -C src -j2
```

The client-free flat build also passes with the dedicated `flat-memory-build`
outputs recorded above. The payload fixture uses real stores and transaction
APIs, covers 23 raw projections including stored/history/delivery roles,
conflicting/destroyed custody, UID-less legacy pets, ordinary ancestors, closed
auction claims, collector collection/expiry and player/pet delivery envelopes.
It rejects corruption in every selected catalog, a valid catalog containing a
malformed legacy blob, unavailable storage and bad snapshot names without
replacing prior output. The shared projection bound is exercised directly at
the sealing helper. It runs with terminating UBSan.

The legacy inspector fixture compiles the actual serializer bodies and checks
stock/custom/explicit-zero flags, full-width UID, compatible v35 frames,
ordinary and stock spellbooks, every truncation, trailing garbage and invalid
single-object framing. ASan/UBSan pass, and template-read/extraction counters
prove inspection itself performs no materialization. These are source-reader
and format checks, not a gameplay uniqueness or complete restoration proof.
When updating hydration, qualify the existing legacy materializer's stock-book
bitmap path independently; serialized bitmap data without other unique fields
must not be assumed preserved solely because metadata inspection passed.

SQL compatibility controls pass on MariaDB 10.11 and MySQL 8.0, including the
actual current schema after all 44 immutable migrations. Formatting, changed-line
clang-tidy and whitespace checks pass. Ignored evidence uses
`population-flat-payloads.log`, `population-legacy-identity.log`,
`population-flat-{maria-build,build,tidy,sql-control,mysql8-control}.log` and
`population-{auction,collector,shop}-control.log` under `bin/analysis/issue67/`.

SQL blob/history pages and their SQL aggregate are now implemented in the next
checkpoint below. PR #144 now pins the Redis generation/floor cut. Next: project
and qualify complete recovery candidates, publish combined evidence before early
cleanup/population and implement
canonical admission/materialization/retirement. Source snapshots are not full
store backups; retain originals before any operational disposition or routine
cleanup can remove historical evidence. All unchecked AR-01–AR-07 acceptance
work remains required. No production read, migration, cleanup, deployment or
release tag occurred.

### SQL blob sources and snapshot aggregate — AR-01/AR-02 prerequisite

Ready for review in [PR #143](https://github.com/LuminariMUD/Duris/pull/143) on
`branch/issue-67-sql-population-blobs`, based on PR #142. Implementation commit:
`12091c2c485bce9d43b36e042778a85f00a142ac`. The existing
population repository now reads five more source domains: per-slot auction
custody, retained auction listing templates, legacy auction item pickups,
collector item bodies and legacy `item_current_owner.coin_payload` history.
Every page buffers at most 256 source rows plus one lookahead; binary lengths
and bounded blob projections prevent unbounded body buffering. The aggregate
limits all inspected source rows, including metadata-only collector records,
to the existing 1,048,576-record bound. Packed auction cursors retain the full
32-bit auction/16-bit slot key while queries seek/order by the real key columns.

Per-slot auction binding UIDs override serialized template UIDs, matching the
actual claim path. Claimed slots are history, and listing templates with bound
slots are history rather than extra physical copies. Uncovered open legacy
listings and unretrieved pickup bodies retain their quantity and optional UID;
no identity is generated. Missing/mismatched listing coverage and open auction
quarantine remain explicit. Collector metadata is decoded with the real codec
and its identity/state/death-operation projections checked before reading a
singleton body; metadata without bytes is not a physical candidate. Coin bytes
are history regardless of custody state, with their payload holder unknown.

All numeric and blob projections now retain open item quarantine independently
of current custody, including quarantine for an item with no custody row. Missing
custody and conflicting owner/vnum/state remain visible. Modern bodies preserve
explicit zero flags, and legacy bodies preserve whether flags were encoded.
SQL delivery transactions already persist their captured item bodies directly
into `player_items` (`materialize_direct_player_items` and collector buyback's
`insert_player_item`); their inbox/result history is not another physical copy.
Auction claims retain their bound blob until player materialization/save and are
therefore retained as history for the later existence classifier to correlate.

`artifact_population_read_sql_payloads` requires a dedicated idle autocommit
connection, starts its own read-only repeatable-read snapshot, reads all eight
numeric and five blob domains, and publishes the staged vector only after a
successful commit. A failed page, malformed body, allocation/size failure or
commit cannot replace prior output; failed reads roll back. An already active
transaction or disabled autocommit returns `EBUSY` without taking ownership of
that transaction. This is a complete SQL-source cut, not combined recovery
completeness, a canonical selection, a boot caller or gameplay admission.

Passed with terminating UBSan through the existing native fixture/driver:

```sh
tests/async/with_disposable_mariadb.sh python3 tests/async/test_artifact_population_repository.py
python3 bin/analysis/issue67/run_mysql8_artifact_population.py
make -C src -j2
```

Both database legs run against the maintained 198-table schema after all 44
immutable migrations, alongside the existing permissive numeric contradiction
fixture. The populated current-schema leg retains 13 mixed room/blob projections,
ordinary parentage, shared UID evidence, unknown UID and quantity, unsigned-maximum
binding UID, claimed/retrieved and collector terminal history, explicit-zero and
missing flags, active/destroyed custody, foreign custody and orphan quarantine.
It tests a 257-row continuation, five malformed/oversized/mismatched-body failures,
a missing-table query failure, prior-output pointer preservation, metadata-only
record accounting and existing-transaction/autocommit refusal. A real table lock
blocks the aggregate at a later source while a second connection inserts a new
pickup: even with session isolation initially READ COMMITTED, the concurrent row
appears only in the next aggregate. No production/test hook is introduced.

The client-free flat build with the existing dedicated `flat-memory-build`
outputs, changed-line formatting, clang-tidy and whitespace checks also pass.
The native pre-commit environment's default Clang 18 selected incompatible GCC
16 headers; use the retained ignored `bin/analysis/issue67/clang-tidy-gcc13`
wrapper (`clang-tidy-18 --extra-arg=--gcc-install-dir=/usr/lib/gcc/x86_64-linux-gnu/13`)
as `CLANG_TIDY` for the staged hook. No check is bypassed.
Evidence is retained under ignored `bin/analysis/issue67/population-sql-blobs-*`
logs in `/home/aiwithapex/projects/duris-issue67-plan`. These are actual source-reader
and snapshot checks; this chunk adds no boot consumer and claims no fresh gameplay
uniqueness/restart qualification. PR #144 now supplies a pinned Redis cut. Next
required work is recovery candidate projection, combined classification before
early reap/forced population, canonical admission
and materialization/retirement, then the remaining AR-01–AR-07 runtime matrix.
All existing unchecked acceptance items remain open. No production read,
operational repair, migration, deployment, merge or release tag occurred.

### Pinned Redis boot evidence and guarded consume — AR-01/AR-02 prerequisite

Ready for review in [PR #144](https://github.com/LuminariMUD/Duris/pull/144) on
`branch/issue-67-pinned-recovery-evidence`, based on PR #143. Implementation commit:
`f14dbae85215c9b24087cad480b77f985a2e8127`. The boot caller now prepares recovery
once before `boot_db`.
Preparation distinguishes disabled configuration, a sealed missing head with an
empty floor, a ready snapshot, and failed evidence. Requested recovery that cannot
start its worker/authentication fails instead of appearing disabled. A failed
read stays failed for that boot; fixing storage later cannot silently change the
cut already classified by a consumer.

The existing authenticated/chunked generation reader and bounded 64-row floor
reader are reused. WATCH covers the head, selected manifest, floor hash and index
while the complete staged read is sealed with EXEC. A same-count value replacement
or head rotation aborts the cut. A lost connection retries the entire read after
reconnecting, never continues an old WATCH on a fresh connection. Every failure
cleans up transaction state or closes an unusable connection. Only a complete
successful seal publishes immutable bytes. Limits remain 256 MiB for generation
plus encoded floor values, at most 16 MiB/32,768 floor records, including their
wire prefix. Orphan floor evidence with no generation is failed/unresolved.

`redis_world_boot_evidence` exposes the retained const snapshot until boot clear.
It is source evidence, not a world-semantic plan, a cross-store exclusive cut or a
canonical decision. The normal recovery loader uses exactly its generation and
floor bytes with the existing semantic/materialization pipeline. It never rereads
Redis, retries a successful materialization, or clears a key. The later consume
requires a successful materialization, checks the current authenticated manifest
against the retained generation digest, and atomically compares the head,
manifest, complete floor count/index membership and every floor value before any
delete. Duplicate expected roots are refused. Any mismatch leaves the generation
and floor intact; chunk cleanup follows only the successful atomic consume.
The obsolete blind floor/pickup clears are removed. Retired pickup cleanup remains
owned by existing maintenance, not recovery.

Passed (logs under ignored `bin/analysis/issue67/pinned-recovery-*`):

```sh
python3 tests/async/test_redis_world_store_live.py
python3 tests/async/test_world_recovery_pipeline.py
python3 tests/async/test_world_recovery_codec.py
python3 tests/async/test_redis_floor_world_gate.py
python3 tests/async/test_redis_failure_containment.py
python3 tests/async/test_redis_admin_nonblocking.py
python3 tests/async/test_redis_key_registry.py
tests/async/with_disposable_mariadb.sh python3 tests/async/run_world_restart_journey.py bin/server/dms_new restart
tests/async/with_disposable_mariadb.sh python3 tests/async/run_world_restart_journey.py bin/server/dms_new slowread
make -C src -j2
```

The live fixture compiles the actual runtime, authenticated store/codec and
production framing validator with terminating UBSan. It uses real publication,
head advancement, same-count floor replacement after the real HMGET reply,
connection kill and Redis ACL rejection of EXEC. It verifies no prefix or
materialization on failed preparation, stable retained inputs after head/floor
changes, one successful load, failed-materialization refusal, digest/root-duplicate
consume refusal and exact-match deletion. Its materializer records input bytes;
that boundary check does not claim gameplay materialization by itself. The real
server journeys separately pass clean shutdown/player save/restart/restoration
and a delayed Redis read/reconnect. The delayed-read boot now reads the head twice
(one timeout and one successful pinned cut), with no restore/consume reread. The
client-free flat build with existing dedicated outputs, formatting, compatible
staged clang-tidy and whitespace checks also pass. Final build SHA-256 values are
`de5f31754391359602e9b0361f6c55c52fc95e98c5754eb95cde781f4ffce8c6`
(SQL) and `c17d9d64b03fab3e250a7d9bdd4aafe99031440300ad38145e52f5dfefaaa462`
(flat); these identify retained build outputs, not a production deployment.

Next: project actual ground item graphs from this pinned generation/floor cut and
qualify copyover/NPC identity evidence, then combine all durable/recovery sources
before early reap and forced population. Early startup custody reap has not been
moved by this change. A ready framing snapshot does not settle NPC equipment
identity or prove physical absence across stores. Canonical admission, selective
hydration rollback, lifecycle/reward eligibility and the full AR-01–AR-07 matrix
remain open. No production read, operational repair, migration, deployment, merge
or release tag occurred.

### Pinned recovery population projections — AR-01/AR-02 prerequisite

Ready for review in [PR #146](https://github.com/LuminariMUD/Duris/pull/146) on
`branch/issue-67-recovery-population`, based on PR #145. Implementation commit:
`a54995c84e259ebb60a3048a4e895095adccfefe`.
`artifact_population_read_recovery` consumes the immutable
snapshot exposed by PR #144. It validates framing and decodes the actual codec,
then uses PR #145's pure native-tree validator. It never reads templates, creates
or extracts an object, assigns an identity, looks up runtime custody, or writes.
Its successful output is raw source evidence, not permission to spawn or hydrate.

Ground rows retain sequence/domain/ordinal provenance, room and expected owner,
full-width UID, root/parent and parent-row IDs, effective vnum and explicit flags,
quantity, and the authority-required bit. Ordinary ancestors and explicit zero
flag overrides survive. The decoder retains every valid graph: fully repeated
floor trees are history, matching actual recovery; partial floor overlaps and
repeated generation UIDs remain visible with `restore_conflict` and quarantine on
the conflicting incoming tree. No different UID is chosen or erased. A consumer
must honor that conflict flag instead of treating success as a qualified world
restore or absence result.

NPC projections retain prototype, instance ID, room, birthplace and exact shop
identity for later reset/NPC mapping. The maintained Redis wire codec explicitly
rejects positive equipment vnums and carried items; these records therefore do
not encode equipment UID identity. No placeholder item or UID is invented for
them. Their G/E reconstruction remains an explicit open qualification step.
Copyover's independent native file format is not covered by this reader.

Recovery custody is deliberately **unqueried**. The shared model now distinguishes
`custody_examined=false` from an examined-but-missing row. Existing SQL numeric/blob
and flat catalog readers mark successful custody examination even when no row
matches; recovery leaves it false. This prevents raw ground rows from being
misreported as proved-unclaimed items. The combined boot consumer must fetch
independent custody for recovery UIDs under the same durable-store cut, including
UIDs represented only in recovery or metadata. A custody row alone still cannot
become a physical payload candidate. Non-recovery sources leave the newly added
payload-root field zero until their graph root has been qualified.

The existing byte/record/tree limits bound decoding: generation plus floor bytes
at most 256 MiB, encoded floor values at most 16 MiB/32,768 records, and at most 512
items per graph. A malformed header/checksum/record/tree or exceeded bound leaves
the previous output untouched. Inspection does not re-age an already sealed cut;
the actual materializer retains its existing freshness check. No extra registry,
recovery format, identity cache or configuration surface is introduced.

Verification:

```sh
python3 tests/async/test_artifact_recovery_population.py
python3 tests/run_regression_tests.py --match artifact_recovery_population
python3 tests/async/test_world_recovery_pipeline.py
python3 tests/async/test_world_recovery_codec.py
python3 tests/async/test_flatfile_artifact_population.py
tests/async/with_disposable_mariadb.sh python3 tests/async/test_artifact_population_repository.py
tests/async/with_disposable_mariadb.sh python3 tests/async/run_world_restart_journey.py bin/server/dms_new midcapture
make -C src -j2
```

The new fixture passes ASan/terminating UBSan in the client-free mode and is
automatically discovered by the established runner (one matched test passes).
It exercises actual encoded nested graphs, unsigned-maximum UID/sequence,
explicit-zero flags, ordinary ancestors, required/unqueried custody, repeated
and partially overlapping floor trees, duplicate generation projections, NPC/shop
provenance and atomic refusal of malformed or oversized evidence. Counters prove
no template read, extraction or custody lookup. The actual planner regression
in PR #145 remains red-before/green-after for unseen-child preservation. The
real `midcapture` server journey passes: a generation with the banana in its
basket restores it once and leaves the fully repeated journaled drop out.
The native SQL and client-free flat builds, changed-line formatting/tidy and
whitespace checks also pass. SQL and flat custody-examination controls pass;
SQL queries/schema are unchanged, and this fresh database leg uses disposable
MariaDB 10.11 through the maintained schema. Evidence is retained under ignored
`bin/analysis/issue67/recovery-population-*` logs in `duris-issue67-plan`.

Continuation: capture durable sources before `reap_unheld_player_items_at_boot`
(currently near the main startup's `redis_init`, before `run_the_game`); do not
move/permit cleanup on incomplete evidence. Pin and qualify copyover before its
later file reader and preserve uncertain file/payload evidence. Complete NPC
reconstruction identity rather than treating missing serialized equipment as
absence. Combine raw sources and independent custody, resolve flags against
loaded templates, then publish canonical/reserved vnums before `ne_init_events`
forces population. Keep legacy ambiguity reserved without rejecting unrelated
inventory or reducing the required availability of proved-absent artifacts.
Canonical admission, hydration rollback, retirement/reward guards and the full
AR-01–AR-07 acceptance matrix remain open. No production read, migration,
cleanup, repair, deployment, merge or release tag occurred.

### Native copyover pinning and evidence — AR-01/AR-02 prerequisite

Ready for review in [PR #147](https://github.com/LuminariMUD/Duris/pull/147) on
`branch/issue-67-copyover-evidence`, based on PR #146. Implementation commit:
`325971977d3924c03225b3d49067aa1827c7c774`. `copyover_prepare_boot` now runs before the existing early custody reap.
It distinguishes unprepared/absent/ready/failed state, validates the complete
selected native file read-only, then claims a valid regular file by an atomic
no-replace rename to `<COPYOVER_STATE_FILE>.recovering`. Invalid originals and
non-file paths remain in place. Existing claims are never replaced or selected
against another publication. After claiming, the reader seals the actual claimed
bytes and their inode/size/mtime/ctime identity. Only that ready cut is published.
A failed/absent result stays fixed for the boot; it cannot silently become a
newer source later. Source-file readiness helpers use the same prepared state.

The versioned decoder is shared by preflight, source projection and the actual
restorer. It retains complete NPC affect/inventory vectors, replacing the old
silent 64-affect/256-item truncation. Its allocations follow the bounded input
bytes. It preserves the established version-12 pre-transport and version-13–15
pre-shop-identity NPC widths and reads version 16 unchanged. The producer updates
short affects **before** recording their count, and explicitly zeroes the entire
legacy carried-item wire entry. Older file writers left its UID bytes
uninitialized; those bytes are never promoted to physical identity evidence.
No native file-format version or NPC item format is added.

Ground tree/custody inspection is extracted from the actual copyover materializer
into `world_recovery_read_copyover_object_record`. The same pure native numeric,
string, parent/UID and live-custody checks now serve both inspection and real
restoration. Captured logical corpse/storage custody may differ from physical
room/tree roots; it is preserved without synthetic owners or SQL reconciliation.
`artifact_population_read_copyover` emits physical ground UID projections plus
separate `reconstruction` rows for NPC vnum hints. It retains full ground flags,
parent/root, source inode/ordinal and captured live custody, and NPC prototype,
instance, room, birthplace and shop provenance. The NPC hint rows have no
trustworthy item UID or saved flag override and do not count as physical presence
or as proof of absence. Independent storage evidence still must be correlated.

Inspection reads at most 256 MiB, opens nonblocking and rejects non-regular data,
checks complete header/descriptor/telemetry/NPC/ground/door framing and exact EOF,
and refuses repeated physical ground UIDs. Read failure leaves the previous
snapshot intact; absent is reported only for a missing file in an available
parent. Item projection uses the existing one-million-record bound, including
reconstruction requests. Neither inspector queries templates, constructs an
object, touches sockets, nor reads/mutates runtime custody.

The actual restorer reads the retained memory image, never reopens the publication
path, and cannot replay a successful load. A failed requested copyover stops boot
before any partial world reaches the game loop. Failed claimed images remain for
owner disposition; an invalid original is not moved. Success consumes only the
unchanged claim and leaves a newer publication or changed claim untouched.
`copyover_clear_boot` releases the retained bytes only after the boot consumers.
The generic source acquisition/classification for SQL, flat and Redis still must
move ahead of cleanup and forced population; this chunk does not make cleanup
safe on incomplete evidence.

Publication uses a private `mkstemp` staging file, validates it before promotion,
and uses no-replace rename before any client disconnect/FD mutation. Both an
existing publication and a retained claim refuse a new copyover before terminal
saves. This includes a prior failed exec: its published source is not overwritten
without review. There is no automatic deletion or first-image winner. The default
publication/claim/staging names are ignored by Git. The real-journey client wrapper
also now accepts the shared reconnect helper's `source_host` argument; its former
signature failed the fixture before copyover was exercised.

Passed:

```sh
python3 tests/run_regression_tests.py --match copyover_evidence
python3 tests/async/test_copyover_custody.py
python3 tests/async/test_shopkeeper_copyover_compat.py
python3 tests/async/test_copyover_save_guards.py
python3 tests/async/test_copyover_failure_runtime.py
python3 tests/async/test_telemetry_copyover_format.py
python3 tests/async/test_world_singletons.py
python3 tests/async/test_world_recovery_pipeline.py
python3 tests/async/run_copyover_runtime_journey.py /home/aiwithapex/projects/duris-issue67-plan/bin/analysis/issue67/flat-memory-build/server/dms_new
make -C src -j2
```

The new automatically discovered native fixture uses ASan/terminating UBSan and
actual producers/decoders. It exercises known native version gates/record widths
12–16, short-affect expiration/count consistency, complete 300-item NPC vectors,
zeroed wire bytes, physical UID/custody versus reconstruction provenance,
truncation/count/trailing/oversize errors, missing/unavailable parents, FIFO and
non-file refusal, retained output, fixed failed/absent state and competing images.
The process replacement fixture uses actual save/exec/recover for normal, newer
publication and changed-claim cases, verifies physical tree/custody preservation
and refuses replay. Its competing-publication injection proves no-replace refusal
before exec with the live objects/custody intact. Removing only that publication
flag makes the case fail at the expected before-exec assertion. The early claim prototype's nonregular-input case reproduced a directory move;
the final validation path keeps both directories and symlinks in place before any
claim. These development/ablation logs are retained separately.

The real flat server journey passes ordinary Telnet and MCCP: failed open,
pending publication/claim refusal, non-preservable-session refusal, subsequent
look/save, real exec, original-connection recovery, acknowledged save and account
menu. Native SQL/client-free builds, formatting, compatible staged clang-tidy and
whitespace checks pass. All fixture state paths are explicit/private and do not
inherit a user's configured copyover target. Evidence is under ignored
`bin/analysis/issue67/copyover-evidence-*`. No hardware-power-loss or arbitrary
historical native-platform ABI qualification is inferred from these results.

Next: assemble the consistent durable and pinned recovery sources **before**
`reap_unheld_player_items_at_boot`, including a read-only check of both publication
and retained-claim paths on ordinary cold boots. Never ignore a retained image or
choose the newest/first file. Fetch independent custody for recovery-only UIDs;
keep captured warm-handoff memory authority distinct from stale SQL. Resolve
prototype/effective flags and stage canonical or unresolved vnums in the existing
artifact authority before `ne_init_events`. Preserve source/owner qualification
for same-UID hydration so a stale vnum fallback cannot materialize an offline
owner's UID at the wrong location. Prove the selected NPC reconstruction absence
rule; missing UID or vnum hints alone never grant admission. Then complete shared
creation/hydration/inspection and retirement/reward guards and the remaining
AR-01–AR-07 matrix. No production read, migration, cleanup, repair, deployment,
merge or release tag occurred.

### Numeric SQL population source pages — AR-01/AR-02 prerequisite

[PR #141](https://github.com/LuminariMUD/Duris/pull/141),
`branch/issue-67-population-evidence` →
`branch/issue-67-recovery-numeric-evidence` implements one read-only page contract
for all eight numeric payload stores: `player_items`, `player_pet_items`,
`locker_items`, retained `account_locker_items`, `corpse_items`, `saved_items`,
`shopkeeper_items` and retained `siege_items`. It reads every payload row,
including ordinary ancestors and zero/missing UIDs, rather than treating custody
as physical existence or filtering out legacy uncertainty.

Each projection retains its source row and owner reference, serialized parent,
parent UID/missing/owner disagreement, vnum, quantity, flags and flag-presence
bit, plus the independent full custody record and owner revision. A NULL flag
remains distinguishable from an explicit zero override for later effective-flag
classification. Pet metadata maps pet UID and player PID; corpse metadata maps
player PID/save ID; lockers resolve the public chest; shops use the established
shop-number-plus-one owner identity. Missing metadata leaves the source row
present with an unknown owner. Retained account-locker/siege rows deliberately
keep unknown normalized owners until their legacy disposition is qualified.

Pages use a fixed 256-row bound plus one lookahead, stable source-ID continuation,
and the caller's consistent snapshot. A terminal page applies only to that table.
Failed SQL/parsing/allocation never replaces the caller's previous page. Joined
metadata that repeats a source ID is refused, including a duplicate exactly in
the lookahead row; no arbitrary metadata winner can disappear across the cursor.
There is no aggregate completeness flag, canonical decision, boot invocation,
new migration, hot-path query or operational inspection in this prerequisite.

Validation passed with terminating UBSan on disposable MariaDB 10.11 and MySQL
8.0. The executable fixture covers all eight sources, full-width UID, missing UID,
NULL flags, broken/cross-owner/cross-chest parents, orphaned owner metadata,
quarantined conflicting custody, absence of custody-only synthetic payloads,
page-boundary continuation, a concurrent insert outside the caller's consistent
snapshot, duplicate metadata at the lookahead boundary and failed-read atomicity.
It also bootstraps the maintained schema through all 44 immutable migrations and
runs every page query against that actual layout. Commands:

```sh
tests/async/with_disposable_mariadb.sh python3 tests/async/test_artifact_population_repository.py
python3 bin/analysis/issue67/run_mysql8_artifact_population.py
make -C src -j2
```

The existing client-free flat build also passes (the SQL page API is excluded).
Formatting, changed-line clang-tidy and whitespace checks pass. Ignored evidence
is `population-sql-pages.log`, `population-sql-pages-mysql8.log`,
`population-build.log`, `population-flat-build.log` and `population-tidy.log`
under `bin/analysis/issue67/`. The MySQL helper uses its own loopback container
and invokes the same permanent fixture; neither test reads the checkout `.env`.

Next: assemble these pages under one consistent read, add auction/collector/
delivery payloads and their effective flags, implement equivalent flat reads,
then combine pinned recovery evidence before publication to the artifact service.
No numeric-source-only result may authorize creation or absence. The complete
population reader and all unchecked admission/lifecycle acceptance remain required.

### Strict recovery numeric evidence — AR-01/AR-02 prerequisite

[PR #140](https://github.com/LuminariMUD/Duris/pull/140),
`branch/issue-67-recovery-numeric-evidence` →
`branch/issue-67-flat-artifact-cache` repairs the actual Redis boot-head and floor
readers. Previously `strtoull` admitted numeric prefixes, signed input and
embedded-NUL suffixes; it accepted `-1` as the unsigned-maximum floor UID, while
boot treated some malformed values as a successful zero sequence. One bounded,
allocation-free `from_chars` parser now validates the complete Redis byte length
and positive unsigned range. The writer's current-sequence floor uses that same
parser. Only a genuinely missing boot-head key succeeds with sequence zero;
failed reads clear the output and remain failed evidence.

The existing isolated live Redis test now compiles the actual runtime reader
fixture as well as its established world-store fixture. Valid sequence 1 and
unsigned maximum pass. Empty/zero, signed, whitespace, trailing, overflow,
embedded-NUL and wrong-key-type heads fail. An actual encoded maximum-UID floor
record accepts its decimal field and refuses signed/trailing/NUL variants, so
refusal cannot be explained by a different embedded root UID. The native head
regression fails on the parent at the intended invalid-head assertion and passes
with the repair. Evidence is retained in ignored
`bin/analysis/issue67/recovery-sequence-before.log` and
`recovery-sequence-after.log`.

Passed: `python3 tests/async/test_redis_world_store_live.py`,
`test_world_recovery_transaction.py`, `test_redis_floor_world_gate.py`,
`test_redis_failure_containment.py`, `test_world_recovery_pipeline.py`, native
`make -C src -j2`, the maintained client-free flat build, changed-line formatting,
clang-tidy and whitespace checks. The recovery pipeline fixture runs with
ASan/UBSan; its obsolete SQL artifact seam was repaired separately in PR #139.
Build/tidy/control logs use `recovery-sequence-*` under the same ignored directory.
This supplies strict reader values; it does not make `redis_has_world_state()`'s
boolean an absence proof, pin the generation/floor handoff, inventory every
payload domain, or implement canonical selection/admission. Those required
steps remain open next.

### Common flat artifact authority — AR-02 prerequisite

[PR #139](https://github.com/LuminariMUD/Duris/pull/139),
`branch/issue-67-flat-artifact-cache` →
`branch/issue-67-writer-backpressure` carries the existing artifact/soul memory
authority into flat-file mode. Boot hydrates complete records before world
population; hot reads, direct feeds, location changes and maintenance use the
same maps as SQL. Captures seal current UID/state, timer and soul and are applied
by the existing writer. The catalog merges a batch atomically, assigns revisions,
rejects whole-result UID conflicts, and treats exact replay as unchanged.
The legacy v1 catalog remains readable as unresolved identity.

Receipt identity protects newer state from older acknowledgements, including a
shared all-souls reset followed by a binding change. Stopped/full writer admission
retains dirty live state; retryable storage errors retain the original queued
capture, while terminal corruption preserves the file and lets later pulses
capture fresh state after repair. There is no runtime synchronous fallback.
Persisted reports can lag memory. Flat player-only `syncdb` is refused until the
complete population audit, and the replaced direct file-backed gameplay APIs
have been removed after a tracked caller audit. Player deletion's atomic release
and room-transfer guard remain in the repository.

Validation passed on the combined writer-bound/cache branch:

```sh
python3 tests/async/test_player_save_worker.py
python3 tests/async/test_combat_artifact_persistence.py
python3 tests/async/test_artifact_guild_snapshots.py
python3 tests/async/test_flatfile_artifact_repository.py
python3 tests/async/test_artifact_guild_rewards_runtime.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_flatfile_player_repository.py --build-inspector bin/tests/coin-death-inspector
make -C src -j2
```

The maintained flat build passed with `PERSISTENCE_BACKEND=flatfile` and dedicated
`BIN_ROOT`, `OBJDIR`, `SERVER_BIN_DIR` and `DMS_BINARY` below
`bin/analysis/issue67/flat-memory-build`; it links without the SQL/Redis clients.
Native fixture proof covers held writer, stopped/full admission, storage
unavailability/corruption, late ACK/current-state retry, atomic multi-record
capture, UID conflict refusal, shared-reset receipts and the actual clear handler's
unresolved/present/retired refusal plus repeated proven-absent clear/reload. The direct-feed runtime
fixture and SQL snapshot controls use terminating UBSan. The ordinary flat
combat/death/save/reconnect/restart journey is the boot/lifecycle control, not
full artifact admission or the AR-07 matrix. The final combined lifecycle-drain
build passed:

```sh
python3 tests/async/test_flatfile_combat_journey.py --variant default /home/aiwithapex/projects/duris-issue67-plan/bin/analysis/issue67/flat-memory-build/server/dms_new
```

Tested flat binary SHA-256:
`a8de48d38e0b68dd2a423c30126d5d62f3cbd7fee16efc0070fbe45a134bed42`.

Ignored evidence in `bin/analysis/issue67/`: `flat-memory-combined-flat.log`,
`flat-memory-combined-snapshots.log`, `flat-memory-maria-build.log`,
`flat-memory-flat-build.log`, `flat-memory-combat-journey.log` and
`flat-memory-regression-proof.log`. The last probe restores synchronous runtime
writing or a storage-backed getter in source copies; both make the permanent
runtime regression fail at the intended behavioral boundary. Changed-line
formatting/clang-tidy and whitespace checks pass. No production operation,
canonical population selection, universal new-object admission, or new flat
reward-history capability is claimed.

Next after this prerequisite: publish complete durable/recovery candidate
evidence before any population, classify canonical versus unresolved state
without first-traversal selection, then integrate creation/materialization and
physical retirement. The unchecked AR-01–AR-07 acceptance work remains required.

Subsequent recovery control found an obsolete fixture seam:
`test_world_recovery_pipeline.py` still supplied SQL result stubs to the extracted
ground-artifact loader, which now reads the shared memory map. Replace that seam
with one tracked memory row and count loader calls at entry; retain all existing
successful-recovery, rollback, forced-reset and single-fallback assertions. The
full native recovery fixture passes with ASan/UBSan. Output is retained as
`bin/analysis/issue67/flat-cache-recovery-control.log` in
`/home/aiwithapex/projects/duris-issue67-writer-backpressure` (temporarily switched
to this PR's branch for the repair). This is fixture compatibility, not new
canonical admission coverage.

### Canonical identity snapshots and hydration — AR-02 in progress

[PR #137](https://github.com/LuminariMUD/Duris/pull/137),
`branch/issue-67-identity-snapshots` → `branch/issue-67-canonical-storage` carries
the stored identity into the existing artifact record and its immutable SQL
captures. Outcome: existing canonical UID/state survives normal legacy row
replacement, bindings, late acknowledgements, owner-deletion publication and
boot/administrative refresh. Files: `artifact.c`, the shared identity contract,
flat-file erase validation and the existing native snapshot/flat-file fixtures.
Non-goals: choosing a legacy canonical copy, complete payload candidate inventory,
new object admission or gameplay-wide lifecycle enforcement. Those remain open.

Boot now stages legacy rows, souls and domain identity before swapping current
memory, including canonical/retired domain rows with no legacy artifact row.
UID/state parsing is strict and full-width. The existing flat-file one-million
record ceiling is shared with these reads; queries request one extra row so
overflow refuses publication instead of accepting a silent prefix. Query,
mirror, allocation and malformed-identity failures preserve current memory.

Artifact, soul and reset snapshots for a known artifact capture canonical
UID/state, legacy timer/location and current soul in one owned job on the existing
writer. The primary soul and domain record
are written in the same transaction as the artifact row, preventing a newly
captured UID from inheriting an old durable soul after a partial save. Legacy
soul-only and all-row mirrors preserve identity. A refresh whose staged
identity differs from current memory is refused and current snapshots are
requeued; no canonical UID is chosen by a live sync. Ordinary row replacement
now changes only the legacy gameplay fields and retains identity by construction.

`artifact clear` and flat-file erase require explicit proven absence. They refuse
unresolved, present and retired identities, protecting canonical copies and
retirement tombstones. Domain-only retired and absent records remain in memory
after save polling. Clear retains domain absence evidence while removing legacy
display/tracking rows, with the existing dirty retry
and current-capture acknowledgement rules. This closes the concrete record-loss
path exposed by adding real hydration, while other sync/lifecycle policy remains
in AR-04.

Fault injection exposed an additional boundary: after a UID-changing snapshot
failed, a subsequent partial soul write could still change the old durable UID's
soul. The permanent SQL fixture reproduced this against `7ef7ed036`. The final
implementation uses one complete snapshot builder for artifact, soul and shared
all-souls-reset writes. All three refuse atomically under the injected UID write
failure, retaining the old durable UID/timer/soul; fresh retries then save the
current identity coherently. Legacy soul-only records without any artifact row
retain their compatible binding path. Future live identity transitions must
change both game-thread identity and binding before queueing a capture.

Ablation: keep one record and the existing writer/receipt protocol. Reuse a small
UID/state validator because both actual backends and the SQL reader require the
same invariant. Temporary staged maps are necessary for atomic publication; no
second registry, worker, hot-path query or synchronous persistence fallback is
introduced. The shared bound replaces the existing flat-file literal.

Current proof:

```sh
python3 tests/async/test_artifact_guild_snapshots.py
python3 tests/async/test_flatfile_artifact_repository.py
tests/async/run_artifact_guild_schema_mysql.sh
```

The native and disposable MariaDB/MySQL SQL cases pass immutable full-width UID
captures, late ACKs, binding/owner preservation, all three clear refusals,
malformed UID/state parsing, atomic sync conflict/malformed-result refusal, and
same-identity refresh. The SQL leg invokes actual `artifacts_load`: success,
each of its three failed reads, failed mirror, allocation failure during staged
row construction, malformed stored UID, and domain-only retired/absent records,
including retry and reload without recreating legacy tracking. It also checks
UID/timer/soul agreement at the first individual capture, before later captures
can hide a partial snapshot. Native snapshot tests run with terminating UBSan.
The flat-file fixture proves the equivalent clear refusal and idempotent clear
of a proven-absent row. Capacity has not been stress-qualified by these fixtures.

Final checks pass for code checkpoint `c09a7615e`: native terminating UBSan,
the existing SQL leg on disposable MariaDB and MySQL 8.0, flat-file fixtures,
combat/artifact contracts, `make -C src`, formatting, clang-tidy and whitespace.
The real standard gameplay journey also passes on that binary: three immediate
feeds and cumulative guild rewards while persistence is blocked, then stored
timer/guild/history agreement, copyover after drain, save/logout and clean
restart without re-award. This validates the normal reward workflow, not all
identity admission/recovery cases. Tested binary SHA-256:
`394572ede3429666d866eb72843aee7bdb21f83e6ffea05fbb62913f9dd6c28b`.

Useful ignored evidence: `identity-snapshot-fault-before.log` (the reproduced
failure), `identity-snapshot-fault-after.log` (MariaDB repair proof),
`identity-snapshots-mysql8.log`, `identity-snapshots-gameplay.log` and
`identity-snapshot-guard-proof.log`, all under `bin/analysis/issue67/`.
The MySQL helper and guard-removal probes are retained there; they compile/run
the existing permanent fixtures. Removing identity capture, clear proof or
refresh identity checks fails the intended behavioral assertion. The latest
gameplay receipt is `bin/analysis/artifact-estale/gameplay-journey.json`.

The stack was rebased during this chunk. At this branch, comparing original
`7ef7ed036` with published `47d0c7fc5` changes only the plan; source, tests and
migrations are identical. Keep the plan corrections from that rebase. Older
checkpoint hashes below are historical evidence; resume from the current branch
tip. PR #137 is ready for review after this verified repair. Next after this
chunk: complete durable/recovery candidate evidence before population, choose
canonical versus unresolved state without first-traversal selection, and wire
creation/materialization/retirement. Stored metadata hydration is not a complete
population inventory or proof of universal duplicate prevention.

### Canonical identity storage — AR-02

[PR #136](https://github.com/LuminariMUD/Duris/pull/136),
`branch/issue-67-canonical-storage` → `branch/issue-67-reward-conflicts` adds the
durable representation, without selecting copies or enabling an admission rule.
The published implementation checkpoint is `787b07cc7`, with the same source,
tests and migrations as the original tested `caca91293`.
The existing nullable `artifact_domain_state.item_uid` remains a custody FK.
Disposable engine tests prove it rejects a positive UID with no custody row
(error 1452), while unclaimed NPC/ground artifacts must be identifiable before
such a row exists. Add `canonical_item_uid` and `identity_state` to the **same
record**, retain the original FK, and do not create fake ownership or another
registry/table. A unique canonical UID key prevents one UID naming two vnums.

State values are sealed in `src/guild/artifact_identity.h`: 0 unresolved,
1 present, 2 retired, 3 proven absent. Present/retired carry a positive UID;
unresolved/absent carry SQL NULL (zero in the flat-file record). A retired UID is
retained so old payloads remain identifiable. All legacy rows stay unresolved;
the migration never infers absence from `owned` or selects a winner from order.
Read availability is separate from durable identity: a failed/partial evidence
scan must preserve the last stored UID/state and reserve the vnum until it can
be classified. It must not erase a known UID by storing unresolved/NULL.

Files/outcome: immutable migration 0044 and its verifier, fresh bootstrap,
migration/runtime manifests and compiled contract, shared state enum, existing
flat-file record/codec, their established engine/native tests and the database
contracts. Independent guards replay interrupted column/index DDL. The verifier
refuses incompatible shapes, inconsistent UID/state or a missing original FK;
no existing timer/soul/custody evidence is rewritten. Applied older immutable
files are unchanged. Runtime table count remains 198.

The flat-file artifact catalog writes v2, reads v1 as unresolved, rejects invalid
UID/state pairs and a shared nonzero UID across vnums, and preserves identity
through ordinary gameplay/bind updates. The existing fixture covers all four
states, round-trip/reload, invalid data, duplicate UID, a real v1 byte layout,
and v1→v2 rewrite without inventing identity. Older binaries refuse v2; this
chunk has not upgraded any operational store.

Ablation: reuse the existing artifact stores, nullable custody projection,
transaction/file codec and test runners. The additional two fields are needed
because custody cannot represent an unclaimed identity and a UID alone cannot
distinguish unresolved, absence and retirement. No new worker, store, service,
configuration, canonical selection or runtime UID map is introduced here.

Validation passed:

```sh
python3 tests/async/test_flatfile_artifact_repository.py
python3 tests/async/run_migration_runner_engines.py mariadb:10.11
python3 tests/async/run_migration_runner_engines.py mysql:8.0 mariadb:11.8
RUNTIME_DB_IMAGE=mysql:8.0 tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:11.8 tests/async/run_runtime_compatibility_mysql.sh
LEGACY_DB_IMAGE=mysql:8.0 tests/async/run_legacy_migration_mysql.sh
LEGACY_DB_IMAGE=mariadb:10.11 tests/async/run_legacy_migration_mysql.sh
python3 tests/async/run_news_migration.py --image mariadb:10.11
python3 tests/async/test_immutable_migration_runner.py
python3 tests/async/test_migration_runner_cli_safety.py
python3 tests/async/test_migration_mysql_invocation.py
python3 tests/async/test_persistence_migration_contract.py
python3 scripts/validate_runtime_compatibility.py
./scripts/format.sh --check
./scripts/tidy.sh --rev origin/branch/issue-67-reward-conflicts
make -C src
git diff --check
```

The engine tests prove nullable FK refusal versus unclaimed canonical identity,
full-width unsigned UIDs, present/retired/absent/unresolved storage, duplicate UID
refusal, preservation of an existing non-null custody UID/revision, partial DDL,
verifier refusal without ledger advancement, exact replay,
index/state drift refusal and preservation of original timers/souls. Fresh and
actual legacy upgrades converge on MySQL 8.0/MariaDB 10.11; MariaDB 11.8 passes
the full runner and runtime compatibility leg. Historical news/online tests are
pinned to their reviewed 0042/0043 prefix; the production runner itself is
unchanged and still refuses the online player-update option at head 0044.

Runtime metadata was measured on clean disposable schemas with the existing
measurement/update helpers, not copied from a configured game. MySQL:
`51ffa6558483c80cb3dbcd169092a06bd17267c597760cd14e31926ffae810ab`;
MariaDB: `37613651c2177a539bbced1f6dc6db307a179b9f14eff1f9084e6c5d64a942e8`.
Ignored command logs are `bin/analysis/issue67/identity-*.log`.
An executable ablation probe compiles the same permanent flat-file fixture with
each production UID/state or UID-uniqueness guard removed in an ignored source
copy. Both variants fail at the intended assertion (not compilation), while the
unchanged production implementation passes. See `identity-guard-proof.log`;
the probe and generated binaries remain under ignored `bin/analysis/issue67/`.

Still required next: hydrate/capture these fields in the existing artifact
game-thread record and ordered writer; read complete durable/recovery candidate
evidence before `ne_init_events` forces population; preserve same-UID staged-load
rollback and retirement tombstones; then wire creation/lifecycle/reward admission.
SQL snapshots and live gameplay do **not yet populate or enforce these fields**.
The full AR-02 exit and later work items remain open; storage tests do not prove
universal offline/admission/restart behavior. No production operation occurred.

### Conservative reward conflict isolation

[PR #135](https://github.com/LuminariMUD/Duris/pull/135),
`branch/issue-67-reward-conflicts` → `branch/issue-67-direct-feed-timers` fixes the
AR-01 reward-loss contracts without waiting for durable canonical identity. A
bounded scan of equipment rejects every contribution from a repeated worn vnum,
in either slot order, instead of selecting the first copy. A single contribution
must have a physical UID, be actually worn by the actor, and match the current
in-memory artifact record's owned/player/location fields. Conflicting or unknown
copies contribute no delta; unrelated artifacts and independently eligible guild
prestige/construction still apply. The strict codec and live/history boundary
are unchanged. Existing rate-limited persistence alerts report controlled reason,
vnum and an opaque source reference; there is no new limiter or identity registry.

Outcome/proof: the existing native capture/submission harness now passes all
seven conflict scenarios as normal tests, with **no expected failures**: duplicate
distinct UIDs, reversed equipment order, repeated same UID, guild-only after all
artifacts conflict, cross-player tracked owner, wrong live wearer and missing
UID. Each proves unchanged conflicting timer, correct unrelated timer/guild
totals, exactly eligible feedback, diagnostic detail, and silent late completion.
The single-copy/cap/PvP/history/source/stone controls remain passing. Transactional
cutover (3/3), difficulty dial contracts, build and changed-line clang-tidy pass.

The disposable standard full-server journey also passes:

```sh
make world
tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_artifact_guild_reward_journey.py --case standard
```

It uses synthetic accounts on a new loopback MariaDB container, never the checkout
`.env` or shared game. Actual Summon Ghasts kills grant three immediate artifact
feeds and cumulative guild rewards while snapshots/history are blocked; after
writer recovery, stored timers, guild totals and history agree. Copyover after
drain and save/logout/clean restart preserve equipment and persisted rewards;
history does not grant again. This qualifies the valid reward path, not all
duplicate creation/recovery cases or the full AR-07 matrix. The first attempt
failed before gameplay because generated `world.mob` was absent; `make world`
fixed that prerequisite and the rerun passed.

Tested binary SHA-256:
`8e868a6e534bae467aad265f53f31db4386bf9cdf0da1c6dbd616cde96da5574`.
Ignored evidence: `bin/analysis/issue67/conflicts-gameplay.log` and
`bin/analysis/issue67/reward-conflicts-gameplay-journey.json` (preserved before
the shared journey output is reused by later checkpoints). The code checkpoint is
`00503a0eb`; later documentation-only commits reuse this evidence. The regression
comparison passes here and fails on parent `7a6e5c5da` (all seven conflict cases).

Ablation: this independently useful guard needs only the already mapped reward
boundary and existing memory getters, so it can precede AR-02. No hot-path SQL,
new persistence or relaxed duplicate codec is introduced. This is deliberately
conservative: without a canonical UID, two same-vnum worn copies are both
excluded. It does **not** identify a noncanonical single copy whose shared legacy
record already names that actor, protect shared lifecycle writes, or prevent
creation. Full canonical validation and the boot/offline/recovery work remain
required; AR-02–AR-04 and the full AR-05 checkbox are still open.

Current review order is #132 → #133 → #134 → #135 → #136 → #137 → #138 → #139 → #140 → #141 → #142.
All published chunks are open for review,
with the displayed dependent PR bases; none has been merged or deployed. Resume
from the tip of `branch/issue-67-flat-population-sources` in
`/home/aiwithapex/projects/duris-issue67-plan`, keeping that stack intact and
creating a dependent branch for the next storage/admission chunk. Fresh master
remains `9b4d7384825aa9a19a990e68f939fb6e6c04c011`. Re-fetch before publication.

### Implementation checkpoint — 2026-10-16, AR-01

Outcome: permanent executable acceptance cases expose duplicate and cross-player
reward interference, while retaining the existing single-copy, cap, soul, source,
history and guild controls. Non-goals for this chunk: gameplay behavior, schema,
canonical selection and any data mutation. Files: this plan and the existing
`artifact_guild_rewards_runtime.cpp`/Python driver. Proof:
`python3 tests/async/test_artifact_guild_rewards_runtime.py` runs the existing
passing journey plus **two explicitly expected failures**, not two repaired
behaviors. Compilation happens outside the expected-failure tests, so a compiler
failure remains a real error. Remove each marker when its contract is repaired;
unexpected success deliberately fails the suite.

The duplicate fixture equips distinct UIDs 101/102 at vnum 42001 plus unrelated
UID 103/vnum 42002 with a three-member eligible guild at prestige 95. Capture
rejects the whole submission: both timers stay unchanged and prestige stays 95.
The cross-player fixture equips only one 42001 copy whose stored location owner
is another player: both timers incorrectly gain 3600 seconds. In both contracts
the required result is no feed of the unresolved/conflicting artifact, one feed
of 42002, and prestige 105/construction 1. These are synthetic storage/owner
boundaries with production capture/application/codec/transaction code, not a SQL
or full-player-load proof. No production population conclusion follows.

Ablation: reuse the existing reward fixture and runner; no second reward
implementation or new test framework. Keep conflict cases visible until the
canonical identity work can make them ordinary passing regressions.

### Creation and restoration map for AR-02/AR-03

Repository-wide search of `read_object`, `instantiate_object_template` and
`clone_obj` identifies these boundaries. The two template constructors are in
[db.c](../../src/world/db.c); the only direct constructor caller outside
`read_object` is the starter-kit adapter in [nanny.c](../../src/account/nanny.c).
Declarations, the pfile test stub, comments and the commented-out house flag are
not gameplay creation seams.

- **Fresh gameplay:** `reset_zone` O/P/G/E plus the M/F/R equipment paths use
  prototypes and indirect object tables. [world_recovery_npc_items.c](../../src/world/world_recovery_npc_items.c)
  reconstructs NPC equipment from those reset commands, allocating fresh UIDs.
  Staff `do_load`, `clone_obj`, recursive `clone_container_obj`, and mob cloning
  in [actwiz.c](../../src/cmd/actwiz.c) create transferable objects; cloning
  copies instance flags after construction and currently dereferences an unchecked
  constructor result. Studio `load obj` actions in
  [studioproc.c](../../src/mob/studioproc.c), scripted callbacks under `src/specs/`,
  random-zone tables, `mob/encounters.c`, quest/achievement and world singleton
  producers also create objects. All must use the same fresh-admission decision;
  changing only the four ordinary reset branches leaves reachable bypasses.
- **Other fresh producers:** account/newbie rewards, crafting/tradeskill/mining,
  shop-produced stock, salvage/enhancement/relic rewards, spell/class/forage
  products, combat corpses/blood, guildhall fittings, kingdoms, ships/transports,
  mail and staff/test commands all call the constructor. Most current literal
  vnums are non-artifacts, but dynamic vnums and copied flags cannot be exempted
  by assuming their caller family never creates an artifact. Preserve ordinary
  non-artifact availability and each caller's null-result behavior.
- **Stable-UID hydration:** [player_load_items.c](../../src/player/player_load_items.c)
  materializes player and pet snapshots, replaces the constructor UID, then
  reapplies saved flags/fields before placement. [sql_player.c](../../src/sql/sql_player.c)
  does likewise for lockers/account chests, corpse contents, saved rooms and
  shop stock. [world_recovery_pipeline.c](../../src/world/world_recovery_pipeline.c)
  stages ground graphs and overwrites UIDs/flags; its whole-graph rollback and
  custody publication must include artifact reservations. Distinguish saved
  shop stock from missing produced equipment loaded afresh during keeper restore.
- **Legacy reconstruction:** [copyover.c](../../src/persistence/copyover.c)
  reconstructs legacy NPC equipment by vnum; legacy `readObjectlist` and
  `read_one_object` in [files.c](../../src/core/files.c) parse saved instance
  fields after construction. `addOnGroundArtis_sql`, `addOnMobArtis_sql`,
  `arti_files_give`, `arti_player_sql`, swap and fixit in
  [artifact.c](../../src/guild/artifact.c) have vnum-only restoration paths.
  These cannot manufacture a new physical identity over an existing durable
  candidate. A legacy record without a justified UID is unresolved, not absent.
- **Temporary templates:** `writeObjectlist`/`write_one_object` in `files.c`,
  `sql_item_diff_strings` in `sql_player.c`, artifact list/JSON/admin inspection,
  `item/enhance.c` prototype-stat comparisons and staff inspection enumerate
  prototypes with `read_object` then extract them. They must not reserve, feed,
  clear, persist or release a canonical copy. Inspect administrative commands
  individually: some begin with a template and intentionally mutate tracking.
- **Post-construction changes:** clone overrides, saved flags and hydration can
  turn a currently ordinary prototype into an artifact. Validate effective
  flags after overrides, before circulation. Merely guarding the prototype
  constructor misses this case. `obj_to_char`, `equip_char`, `obj_to_room` and
  their end-placement variants in [handler.c](../../src/world/handler.c) call
  location updates; nested `obj_to_obj` movement must be traced through the root.
  These placement functions return void and cannot silently reject an object
  after a caller has already consumed a reward or source material.

### Identity evidence and boot design

This is the retained AR-01 source map. PR #136 subsequently added the independent
canonical UID/state fields, and PR #137 hydrates/captures them. The current flat
authority checkpoint above supersedes this map's old no-UID description. The
complete candidate reader, recovery proof and population ordering remain open.

Continuation inspection after PR #139 confirmed two reader boundaries to retain:

- The old `redis_has_world_state()` boolean conflated disabled/absent/failed
  evidence and the loader reread another head after `boot_db`. The pinned recovery
  checkpoint above replaces that path with explicit results and retained bytes.
  Candidate classification must still consume its actual ground graphs and
  unresolved/disabled status before granting physical absence across stores.
- `world_recovery_validate()` and the wire codec already validate bounded
  generation envelopes. Ground records contain full stable-UID item snapshots;
  `write_mob_record()` explicitly clears equipment vnums and carrying count, and
  the recovered-NPC helper reconstructs G/E equipment from reset templates.
  Preserve/qualify authoritative NPC artifact identity or keep it unresolved;
  that reconstruction is fresh creation, not same-UID hydration. Reuse existing
  codec/store readers and stage evidence before `ne_init_events`, rather than
  creating another registry or treating successful later ground restore as proof
  that earlier forced population was safe.

The numeric, flat and SQL blob source readers above now implement the durable
source prerequisites. Recovery candidate projection, the combined classifier and its early boot
consumer remain open; no new recovery format has been implemented.

The supported custody types in [item_transfer_command.h](../../src/item/item_transfer_command.h)
are player, container, room, corpse, locker, auction, system, destruction,
shopkeeper, collector and pet. State is absent/active/destroyed/quarantined.
For every artifact candidate retain UID, effective vnum/flags, root/parent,
payload owner and custody owner/context/state; compare payload and custody before
classifying existence. Two payload projections of one UID are not two physical
UIDs, and a stale custody row alone proves neither presence nor absence.

- The SQL topology classifier already joins player, corpse, locker, account
  locker and saved-room trees. It **does not cover** `player_pet_items`, shop
  inventory, auction/collector payloads, recovery generations or effective
  artifact flags. Extend those actual stores, rather than treating the existing
  classifier or runtime UID map as a complete population inventory.
- [player_load_repository.c](../../src/player/player_load_repository.c) separately
  joins player/pet payloads to custody. Offline owners remain candidates before
  login. Locker/corpse/room/shop loaders in `sql_player.c` restore domains
  separately; preserve their source rows and quarantine evidence on conflict.
  Auction/collector and pending delivery ownership must be included through
  their repositories, not through a live-object scan.
- Flat-file [artifact records](../../src/flatfile/flatfile_artifact_repository.h)
  contain vnum/state/timer/soul/revision but no UID. The item repository can load
  UID records and list active player custody, but that list is not every payload
  domain. Its boot reap already inspects player, pet, locker/corpse/room and
  pending delivery payloads. Reuse those store readers when qualifying a full
  artifact population, and retain the same missing/ambiguous-data semantics.
- Redis/copyover ground graphs carry stable UIDs and effective flags. Redis NPC
  equipment is rebuilt from resets and does **not** carry that stable item
  identity. A canonical saved/custody/recovery candidate must block such fresh
  reconstruction; a non-durable NPC predecessor may be replaced only after
  proving it absent from every durable/recoverable domain. If that cannot be
  proven, reserve the vnum until operator disposition instead of guessing.

Boot ordering is material: `comm.c` reaps unheld custody before `boot_db`;
`sql.c` hydrates artifact rows before world creation; `boot_db` calls
`ne_init_events` **before** restoring corpses/rooms/shops and legacy artifacts.
`ne_init_events` immediately calls forced `reset_zone` on a normal cold boot.
Redis/copyover suppress that population, then `comm.c` restores recovery and may
fall back to forced normal resets on failure. Thus installing an identity scan
after the domain loaders is too late. Required order: read consistent durable
candidate evidence and validated recovery metadata, publish reserved/canonical
vnums on the game thread, then allow forced population and domain materialization.
Any incomplete read/continuation leaves its affected vnums reserved; no hot-path
SQL or Redis lookup is permitted. Enforce existing payload/tree limits, bounded
query pages and an explicit terminal/partial result rather than a silent prefix.

Runtime identity states needed by AR-02 are absent (complete evidence only),
canonical UID, unresolved legacy/conflict/unavailable evidence, and retired
identity. A pending fresh claim takes effect before placement, is released only
on that failed admission, and cannot be released by inspection or logout.
Same-UID hydration must not create a second live materialization. Physical
retirement is separate from unloading; preserve the current single-writer order
and do not let old completions release a newer identity.

AR-02 must still qualify the existing nullable FK link against unclaimed
NPC/ground objects that have no custody row. No schema choice has been made and
no migration is justified merely by this map. The remaining AR-01 mapping
checkboxes stay open until the complete boot candidate reader and the exact
reconstruction/absence rule have executable coverage. Next implementation step:
qualify those stores and identity publication, then remove the known-failure
markers as their acceptance contracts become true.

AR-01 checkpoint validation: the reward runtime baseline passes with two known
expected failures; transactional cutover passes 3/3; source inventory matches all
169 templates. `./scripts/format.sh --check`, `git diff --check` and
`make -C src` pass. `./scripts/tidy.sh --rev origin/master` reports no changed
production C/C++ lines (only the native test harness changed). No full suite,
database matrix or gameplay/restart journey is claimed for this diagnostic chunk.

### Original planning baseline (before implementation)

The planning pass inspected current source, schema, callers, configuration,
maintained architecture/persistence/testing contracts, issue #67 and its timeline,
and the closed #58 delivery. It used a separate worktree based on the pinned
master above and did not inspect production or query a configured game database.

Passed during planning:

```sh
python3 tests/async/test_artifact_guild_rewards_runtime.py
python3 tests/async/test_artifact_source_inventory.py
python3 tests/async/test_artifact_cache_codec.py
python3 tests/async/test_artifact_offline_owner_loads.py
python3 tests/async/test_world_recovery_npc_items.py
python3 tests/async/test_flatfile_artifact_repository.py
python3 bin/analysis/issue67/verify_current.py
```

The last command is an ignored scratch probe derived from
`artifact_guild_rewards_runtime.cpp`; it compiles production capture/transaction/
codec with UBSan and fixture storage/writer/messaging boundaries. It confirms the
duplicate combined-reward rejection, single-copy control and missing physical
identity check described above. It is not a permanent regression, real wear
command, SQL integration test, or full-server/player journey. Generated sources
and binaries stay under ignored `bin/analysis/issue67/`.

The existing recovered-NPC baseline harness also runs with ASan/UBSan; that is
baseline recovery coverage, not qualification of the proposed identity changes.
Document validation passed for 19 local links/anchors, 27 listed existing test
paths, all eight work items, and the pinned base/publication branch.

The original planning publication changed no C/C++ implementation, schema,
world content or configuration. A full
build, full regression/database suites, real gameplay/restart journeys,
production operations and release news are not required for this plan-only
publication and were not run during planning. The implementation checkpoints
above supersede the old handoff; unchecked acceptance work remains outstanding.
