# Issue #67: artifact identity, duplicate prevention, and feeding feedback

Tracking: [Duris #67](https://github.com/LuminariMUD/Duris/issues/67).
Implementation branch: `branch/issue-67-artifact-identity`.
Status: AR-01 executable acceptance cases and source boundary mapped; identity
implementation in progress; independent feeding feedback implemented on
`branch/issue-67-feeding-feedback`. No operational repair started.
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

8. **The requested wording remains outstanding.**
   `publish_messages()` still says “from your artifact(s)”; `artifact_feed_sql()`
   retains separate deep/light “from somewhere” messages. Treat “from above” as
   requested wording, not a verified historic quotation. Trace active direct
   callers and the flat-file path before changing them. Existing capped feeds
   can still produce feedback; a wording fix must not silently change that rule.

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
  Choose whether the canonical UID must be retained in recovery or a proven
  absent, non-durable predecessor may be replaced. A fresh reconstruction UID
  must never bypass an existing saved/canonical copy.

Exit: documented reachable paths, identity states, and executable failing cases;
an implementation-ready boot/admission design consistent with memory authority.

### AR-02 — Persist and hydrate canonical identity using existing stores

Dependencies: AR-01.

- [ ] Qualify `artifact_domain_state.item_uid` and its FK for the selected design.
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
- [ ] Add schema only when the existing nullable link cannot express a proven
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
- [ ] Update `publish_messages()` and every verified active positive direct-feed
  path to the requested “from above” text. Preserve colors, negative feedback,
  recipient eligibility and reward timing. No duplicate feedback for several
  artifacts, history retry/completion, replay, or restart. Test successful one-
  and several-artifact rewards, capped valid feed, no eligible reward, rejected
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

- [PR #132](https://github.com/LuminariMUD/Duris/pull/132),
  `branch/issue-67-artifact-identity` → `master`: acceptance repros and admission
  map, published at `21bcc2754`. No identity behavior is fixed in that PR.
- `branch/issue-67-feeding-feedback` → `branch/issue-67-artifact-identity`:
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
eligibility remain in AR-05. The two AR-01 expected failures remain unfixed.

The following pass for this chunk: reward runtime (baseline plus 2 expected
failures), flat-file artifact repository/bind/gameplay harnesses, transactional
cutover (3/3), combat/artifact persistence contracts, changed-line formatting,
clang-tidy and `make -C src`. This is no claim of full gameplay/restart, database
matrix, production qualification or complete AR-05 acceptance.

Next: qualify canonical identity storage/boot candidate publication for AR-02.
While tracing direct feedback, an additional timer defect was found: negative
feed is converted to an absolute value for logging then added to the timer, and
an above-cap positive clamp can therefore increase it further. Repair this as
its own focused chunk with direct executable timer assertions before resuming
the larger identity work. No production state has been inspected or changed.

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
