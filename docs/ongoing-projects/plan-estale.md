# Artifact and guild rewards: memory authority and ESTALE repair

Tracking issue: [#58 — Batched epic awards fail with ESTALE](https://github.com/LuminariMUD/Duris/issues/58).

Status: implementation and local qualification complete on 2026-10-14; ready for
review on `fix/58-artifact-guild-memory`, based on `origin/master` at `0e27ef1e8`.
No #58 merge, production rollout or compensation has occurred. LR-01 statistics
was already squash-merged through [PR #66](https://github.com/LuminariMUD/Duris/pull/66)
as `8c3f7384a`; LR-02–LR-20 remain in [plan-log_review.md](plan-log_review.md).

## Qualification update (2026-10-14)

Live eligible feeds and guild prestige/construction apply once on the game thread.
The existing ordered writer saves current entity snapshots; type-9 v2 commands
record immutable history and never apply rewards on completion/replay. Failed
snapshot admission or terminal writes retain dirty state and retry fresh captures.
History retention is bounded at 256 entries with at most eight unqueued retries
per second. Old committed v1 receipts/outbox remain readable; an uncommitted v1
command is refused explicitly. No schema migration is required for this cutover.

The payment repair keeps `payment_pending` until the matching guild receipt
confirms COMMIT. Later guild saves and member-deletion transactions carry the
current pending realm in the same transaction. Failed writes retry without
another debit. The realm owns retry state; the duplicate pending-ID list is gone.
Flat-file payments retain their existing shared recovery journal.

| #58 acceptance criterion | Local evidence |
| --- | --- |
| Actual clustered gameplay awards | The full-server journey casts Summon Ghasts, records cast/feedback/history timing, kills three boon targets, and observes three live rewards while the writer is held. The original repository probe isolates expected-timer/guild-revision vetoes; the native real-capture test fails before immediate publication. The exact historical cast remains unproven. |
| Every eligible feed and guild increment; state ordering | Native real reward capture covers same-character and same/different-guild bursts, cumulative construction and mixed rewards. Real artifact stores, timer command, wars callback and corpse/removal APIs run through held snapshots, then actual MariaDB transactions and the boot-row decoder verify final state and mirror agreement. |
| Capped feed and genuine eligibility | Native capture and SQL history cover below/at/above cap, same-second awards, zero-effect capped success, unworn/missing artifacts, trusted actors, group eligibility and wrong/right/free PvP souls. No blanket ESTALE retry was added. |
| Stable identity and no repeated benefit | Parent/actor-derived IDs, immutable history replay, actual boon/combat/stone producers, offline return/reconnect, and eviction beyond the real 256-entry completion cache all pass. Full-server crash/restart and PvP cases pass. |
| Useful bounded diagnostics | Actual reporters retain full opaque IDs plus stage/reason, entity and error metadata. Reconciliation detects mirror/missing-row/identity/history defects without equating history totals to current gameplay state. New history has no old SQL gameplay veto to report. Suppression age remains distinct from operation age. |
| Regressions, gameplay and historical assessment | The gates and fault cases below pass after documented fixture corrections. The bounded historical disposition below establishes no compensable amount from the reported capped bursts. |

The deterministic native direct-award control covers capped and uncapped bursts;
the full-server legs exercise actual spell/boon and PvP publication. The state-ordering
SQL leg controls writer scheduling and receipts, then runs real SQL and reloads
through the production row decoder. It covers feeds around transfer, soul changes,
staff extension, war burn, corpse moves, expiry/removal and recreation. It does
not simulate the full physical inventory/room engine. Those boundaries retain
existing gameplay checks and have the separate full-server reward/restart legs.

| Full-server boundary | Persisted artifact increment | Guild prestige / construction | Reward histories |
| --- | ---: | --- | ---: |
| Crash before the first artifact save | 0 | 85 / 0 | 0 |
| Crash after the first artifact save, before guild save | 3,600 seconds | 85 / 0 | 0 |
| Crash after first history COMMIT, before notification | 3,600 seconds | 95 / 0 | 1 |
| Boon burst drained, copied over, then restarted | 10,800 seconds | 115 / 1 | 3 |
| Blocked bounded shutdown, then restart | 0 | 85 / 0 | 0 |
| PvP reward drained and restarted | 720,000 seconds | 105 / 1 | 1 |

All six variants passed together on the final production source in the database
gate. A test-only interposer holds the real history COMMIT before notification.
Blocked shutdown names unsaved artifact/guild state and every unresolved history
pair; copyover cancels while the writer is blocked and succeeds after recovery.
`bin/analysis/artifact-estale/gameplay*.json` retains the private fixture evidence.

Validation and corrections:

- `make test-all -j16 TEST_JOBS=16`: **731/731 passed**, 695.94 seconds.
  An earlier run had five stale source/documentation/fixture checks; all were
  corrected before this passing run. The epic seed manifest changed only the
  `epic.h` source hash, not payout data.
- `make test-db`: **76 distinct legs**. Its full run passed 68 and exposed eight
  linker failures for the new metadata-log callback. A shared weak fixture adapter
  fixes those; all eight reran successfully under disposable MariaDB, plus the
  expanded artifact/guild SQL leg. The aggregate is 76/76; the original make
  invocation exited nonzero, and the entire already-passing set was not repeated.
- Server/development/production builds, `make -C src pfile`, maintained migration
  tools (`all affects pfile_converter`), and full-tree formatting pass.
- `npm ci --prefix site && npm test --prefix site`: **15/15 passed**.
- Writer/coordinator allocation regressions, guild-member capture restoration and
  copyover lifetime regression each pass after and fail before their repair.
  `scripts/check_tests_catch.sh` reports 1/1 for each corresponding isolated range.

Qualification also repaired three concrete persistence/lifetime defects: stale
staff artifact-sync publication, temporary guild-member removal surviving a
capture exception, and copyover running room-entry effects on restored characters.
The last was observed as an intermittent full-server crash and reproduced as an
ASan heap-use-after-free in the actual buffer restorer. Recovery now uses the
existing placement mode that skips movement hazards/procs. Old acknowledgements
cannot settle a newer snapshot or a recreated realm. No extra persistence queue
or generic retry framework was introduced.

The published working checkpoint is preserved on `fix/58-56-estale-log-review`.
The review branch replays only the #58 code/qualification commits onto current
master; it does not replay the squash-merged statistics commits. Its complete
`src/` tree equals the tested checkpoint (`5959df9992b3a0e8f6ca6af2f5d9dbcc191f5597`).
Only upstream migration/docs/help/news changes accompany the new base. Integration
checks pass: 18 migration-runner tests, 12 documentation tests, the pipeline contract,
full-tree formatting and all 15 site tests. No published branch was
rewritten. The earlier continuation/pause records below are historical and are
superseded by this section.

Historical compensation assessment: the reported three capped bursts contain
seven committed parent epic awards, three successful artifact-only children and
four rejected children. Successful feeds added 8, 123 and 55 seconds, each reaching
the ten-day cap; this evidence establishes no additional compensable timer value
or missing guild amount. Rejected transactions leave no child inbox/payload, so
alert counts and parent awards cannot reconstruct each rejected benefit. Below-cap
and guild-only loss is reproduced synthetically but is not an attributable recovery
amount for these historical failures. No compensation is proposed or applied.
Any later adjustment requires recoverable parent/actor/state/cap evidence and
specific owner authorization.

Local logs: `/tmp/duris-es-final-test-all.log`, `/tmp/duris-es-final-test-db.log`,
`/tmp/duris-es-db-fixed-*.log`, `/tmp/duris-es-copyover-placement-catches.log`,
`/tmp/duris-es-guild-capture-catches.log`, and `/tmp/duris-es-state-ordering*.log`.
All gameplay/database tests used isolated worlds and disposable schemas. The
shared dev game and production were not used for this implementation/qualification.

## Continuation evidence (2026-10-13)

The reward cutover builds with `make -C src -j16`, and the updated disposable
MariaDB artifact/guild fixture passes, including the corrected outbox stub.
`world persistence` now shows live applications, capture failures, dirty
artifact/soul and guild snapshots, committed/rejected/lost/pending history,
admission failures, malformed completions, and oldest pending-history age.
`test_persistence_status_contract.py` verifies that metadata boundary.

The writer allocation regression now injects failure at every admission allocation.
It proves that a refused submission leaves neither a queued job nor an owner-index
entry, and that replacing the tail needs no allocation. It passes on the worktree;
`0ccec836e` compiles but fails because a refused job remains queued. Evidence:
`bin/analysis/artifact-estale/writer-allocation-before.log`. This exposes a concrete
shared-writer defect required by snapshot admission recovery, not only an errno change.
It is committed in `dfecafbda`; `scripts/check_tests_catch.sh c8655bfbd dfecafbda`
confirms 1/1 changed tests pass after and fail before.

The snapshot fixture additionally passes bulk soul-reset receipt ownership,
later binding changes, and reset admission/allocation failure recovery. The reward
fixture adds a positive different-guild control and links the real stone publisher
to the actual artifact reward path: online publication, offline return, derived
parent identity, duplicate completion/reconnect after child completion, and a
recovered claim all pass. Its coordinator has no completed-ID cache, so the stone
source guards supply deduplication. Full real-coordinator cache-eviction and PvP
producer evidence remain open.

Allocation probing then reproduced a reservation leak between coordinator
reservation and writer submission: constructing the owned callback could throw,
leaving a fenced operation with no writer job. `532fe0653` releases that reservation
on dispatch failure, distinguishes admission errors, and counts acceptance only
once the writer accepts. The native fault test warms the hash buckets before
walking allocations (otherwise a failed rehash can shift a later failure point).
It fails before the fix with retained inflight/fence state and passes after it.
Local evidence is `/tmp/duris-es-coordinator-allocation-before.log` and
`/tmp/duris-es-coordinator-allocation.log`.
`scripts/check_tests_catch.sh dfecafbda 532fe0653` confirms 1/1 tests catch the
pre-fix behavior. The server was rebuilt successfully after this fix.

No new completed-result API is needed after that cleanup: admitted history remains
queued, retries submit only unadmitted commands, and source guards own new live
publication. Actual coordinator-cache eviction and the PvP producer still need
end-to-end proof; do not replace them with the finite cache as a deduplication store.

`test_mysql_artifact_guild_reward_journey.py` now passes against a disposable full
server/world and is registered in `tests/run_db_tests.sh`. The actual mortal
necromancer casts Summon Ghasts, its delayed event kills three targets, and the
real boon publisher grants three 4-epic awards. An SQL row lock holds the writer:
`world persistence` reports three live applications, one dirty artifact and guild,
and three pending histories while SQL still holds the old timer and 85/0 totals.
Copyover fails boundedly and leaves the server live. After release, the timer gains
exactly 10,800 seconds and guild totals become 115/1; the three history rows retain
successive timer values and 95/0, 105/1, 115/1 guild outcomes. Copyover then succeeds,
and a clean restart preserves state without granting history again.

Evidence is `bin/analysis/artifact-estale/gameplay-journey.json` (binary hash,
cast/event/award/history timestamps, held-writer health, SQL values and synthetic
transcript) and `/tmp/duris-es-gameplay.log`. This run used the server before the
later coordinator allocation fix; the complete final-source database gate still
must rerun it. The current journey does not yet cover crash stages, PvP, all
transfers/removals/spending, or real coordinator-cache eviction.

`make -C src -j16 pfile` and `make -C migrations/tools -j16 all affects pfile_converter`
pass. The migration build exposed one obsolete `Guild::add_points_from_epics` stub,
now removed. Full-tree formatting passed for tracked C/C++ before the subsequent
coordinator fix; the two untracked C++ fixtures have also been formatted.

Additional source-audit findings to reproduce and fix before final qualification:
`arti_syncdb_sql()` clears and hydrates artifact memory in an asynchronous callback,
which can overwrite changes made after the staff command was queued. The kingdom
payment pair still reports queue admission as durability and lacks terminal-failure
receipt tracking. Preserve paired guild/realm semantics while investigating it;
keep any independent pre-existing repair separate from the reward cutover.

## Pause handoff

This checkpoint was saved before resumption. The implementation and qualification
are active again; subsequent evidence is recorded below as it completes.

The worktree is `/home/aiwithapex/projects/duris-estale-log-review`; its common
Git directory is `/home/aiwithapex/projects/duris/.git`. Preserve the source,
reconciliation script, and maintained-test changes shown by `git status`, including
the four new runtime/snapshot fixture files. They are local work in progress,
not part of PR #66. This handoff updates documentation only.

The last pending snapshot/shutdown/severity test sequence completed successfully.
No task build, test, or disposable database process remains running. The shared
local/dev game and database remain running and may be used by another worktree.
Keep future journeys isolated; check current runtime ownership before operating
any shared instance. No #58 production operation, deployment, or compensation
has occurred.

### Implementation present in the worktree

- `artifact_guild_command.*`, `artifact_guild_state.*`, and
  `artifact_guild_transaction.*` implement v2 captured before/after facts,
  immediate game-thread rewards and feedback, immutable bounded pending history,
  and completion handling that does not apply rewards. Guild thresholds accumulate
  from current memory. The MySQL capability gate remains explicit; unused duplicate
  feeding formulas and the SQL approval/hydration cache are removed.
- `artifact_guild_repository.*` writes history only. It preserves committed v1
  receipt and outbox replay, refuses uncommitted v1 commands, and reports named
  malformed/identity/missing-parent failures. History revisions come from ledger
  metadata. No schema migration was added.
- `sql_async.*` adds preallocated commit receipts; `artifact.c`, `assocs.*`, and
  `sql_player.c` retain dirty current state after snapshot failure, acknowledge only
  the corresponding capture, and retry fresh snapshots in bounded batches. Guild
  upserts include both reward totals. Artifact removal retains a deletion tombstone
  until its write completes. The player writer preserves admission atomicity on
  allocation failure; coordinator admission distinguishes capacity, allocation,
  and quiescence errors.
- `comm.c` and `copyover.c` add domain pulse/drain accounting and unresolved-write
  reporting. The most recent copyover change adds a final domain drain after final
  saves; it still needs executable lifecycle qualification.
- `reconcile_artifact_guild_outcomes.sh` now takes explicit database credentials,
  checks persisted mirrors/references and internal history consistency in a read-only
  snapshot, and permits legitimate divergence between reward history and current
  gameplay totals. Cache generation invalidation also covers a successful retry
  after earlier snapshot admission failed.

### Verified evidence and limits

| Check | Result at pause |
| --- | --- |
| `test_artifact_guild_rewards_runtime.py` | Passes real capture/application tests for bursts, cumulative guild thresholds, caps, eligibility, invalid arithmetic, pending duplicates, delayed completions, and history refusal/retry/capacity. Against `0ccec836e`, fails at the first pre-completion timer assertion. |
| `test_artifact_guild_snapshots.py` | Passes real artifact row/soul and guild capture, exact-capture acknowledgement, terminal/admission/allocation failure, current-state retry, removal/recreation, bounded round-robin retries, and cache generation cases. The cache read after failed admission case failed before retry invalidation was added and now passes. SQL completion is controlled by the fixture; this is not a full database/restart journey. |
| `run_artifact_guild_schema_mysql.sh` under `with_disposable_mariadb.sh` | Passed captured history/replay, newer snapshot preservation, reconciliation mismatch/missing-row detection, cap no-op, malformed/identity/missing-parent failures, committed v1 receipt/outbox, and history after removal. A subsequent fixture-only return-type/header correction still needs a rerun. |
| Codec and existing focused tests | Passed `test_artifact_guild_transactional_cutover.py`, `test_combat_artifact_persistence.py`, `test_artifact_cache_codec.py`, `test_sql_async.py`, `test_player_save_worker.py`, `test_critical_command_coordinator.py`, `test_epic_in_memory.py`, `test_epic_stone_runtime.py`, `test_kingdom_contract.py`, `test_flatfile_artifact_repository.py`, and `test_flatfile_association_repository.py`. The stone fixture's artifact stub does not prove the full producer. |
| Latest completed sequence | Snapshot tests, `test_shutdown_writer_bound.py`, and `test_persistence_severity.py` pass. The shutdown test is a source contract, not the required live shutdown/copyover journey. |
| Server build | `make -C src -j16` passed during implementation, before the latest cache/copyover/diagnostic edits. A build of the final source is still required. |
| Complete qualification | Not run for #58. LR-01's 727 regression / 75 database / 15 site successes apply to its earlier source only. |

Before-fix evidence is retained under the ignored
`bin/analysis/artifact-estale/`: `probe.py`, `result.txt`, `runtime_before.cpp`,
and `runtime-regression-before.log`. The original SQL probe reproduced burst/cap
rejection, mirror disagreement, and successful receipt replay. The old native
fixture captured three identical +3,600-second feeds while memory advanced zero,
and three same-guild awards left memory at 85 prestige / 0 construction instead
of 115 / 1. Run old-source fixtures only in a detached checkout of `0ccec836e`,
with separate build outputs; their old APIs do not describe the new worktree.
The maintained runtime fixture's before-fix failure was a behavior assertion,
not a compile error.

Additional local logs are temporary files: `/tmp/duris-es-runtime.log`,
`/tmp/duris-es-sql-async.log`, `/tmp/duris-es-codec.log`,
`/tmp/duris-es-mysql.log`, `/tmp/duris-es-snapshots.log`,
`/tmp/duris-es-snapshot-retry-before.log`, and `/tmp/duris-es-build.log`.
Preserve needed evidence before cleanup; `make clean-all` removes ignored `bin/`
evidence, and `/tmp` is not durable storage.

### Resume checklist

1. Review the existing diff and the continuation evidence above. Diagnostics and
   shared admission repairs are implemented; preserve their separation of live
   application, unsaved state, and history success/loss.
2. Prove real boon/PvP/stone publication guards, including reconnect and completion
   cache eviction. The dispatch-allocation reservation leak is now fixed; retain that
   fault regression while checking source publication guards. Do not
   use that finite cache as permanent live-award deduplication.
3. Audit every artifact tombstone/removal loop, bulk soul-reset acknowledgement,
   and the kingdom-payment/member-removal shared SQL builders. Prove kingdom
   payment interleaving beyond source contracts. Writer enqueue allocation, bulk
   soul reset and the different-guild positive control now have executable coverage.
4. Extend the registered `test_mysql_artifact_guild_reward_journey.py` from its
   passing Summon Ghasts / blocked writer / copyover / clean restart cases to the
   remaining crash stages and gameplay interleavings. Qualify shutdown reporting
   and the final copyover drain after late saves. The full matrix below remains required.
5. Rerun the changed MariaDB fixture, build the final server and maintained tools
   affected by shared headers, format, run all local gates below, and retain genuine
   before/after evidence. References and regression notes now describe the branch
   implementation with its qualification limits; reconcile them with the final code.
6. Commit/push coherent qualified changes and open a separate #58 PR, leaving it
   unmerged. Then continue LR-02–LR-20 in [plan-log_review.md](plan-log_review.md).
   `skeer` stays skipped by owner decision.

Prepared on 2026-10-13 against `master` at `79541e206`, the current issue and its
two reproduction/trigger comments. Production observations below are the issue's
reported evidence, not a new inspection of the production database or logs.

Related work: [#56](https://github.com/LuminariMUD/Duris/issues/56) and
[plan-log_review.md](plan-log_review.md#preserve-memory-authority). That plan
correctly separates statistics output identity and epic-skill refresh from this
artifact/guild reward defect. #58 owns this work and its closure evidence.

## Decision, outcome, and boundaries

**Make artifact feeding and guild prestige/construction authoritative in memory.**
Apply each eligible reward on the game thread before processing the next award.
Persist the resulting state through the existing artifact and guild snapshot
writes on the single writer. Retain the derived type-9 command as idempotent
reward history; it must neither decide the reward nor mutate its live state on
completion. This follows the existing epic-point design and gives the live award
one authority.

The required outcome is that a burst of eligible awards produces all its timer,
prestige, and construction effects immediately, in gameplay order, with the
existing eligibility, feeding cap, and soul rules. Transfers, spending, expiry,
and removal must see those updated values. Ordered saves must preserve that
sequence; retries, completion delivery, and history replay must add no rewards.

[ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md) and the
pipeline reference now record the branch's narrowed economy exception for
epic-derived artifact/guild rewards, now locally qualified for review. Other
economy transactions retain their current authority and durability contracts.

**Crash contract:** this is asynchronous persistence, not a new durable gameplay
journal. A crash may lose state not yet saved, as the ADR permits. Committed
history is not an instruction to award again at boot. Exactly-once means one
live application per new source award, idempotent state snapshots, and one
history outcome per parent/actor through repository retries and replay. It does
not promise recovery of every unsaved reward or atomic durability of the epic
balance, all artifact snapshots, guild snapshot, and history as one transaction.
Do not claim the player's 30-second checkpoint covers artifact/guild state:
those currently have their own immediate queued writes, without that checkpoint.

**Non-goals:** spell balance, changing reward amounts or level gates, completing
the other #56 findings, a general persistence rewrite, new writer/journal/lock
infrastructure, new flat-file reward support, or automatic historical compensation.
Production repair, migration, restart, deployment, and historical compensation
require their specific authorization; none has been performed for this repair.

**Files and proof:** the source owners and existing tests are listed below.
Implementation needs executable tests of the actual capture/application path,
disposable database tests of snapshots/history, and a gameplay/restart journey.
The original planning document was published before implementation began.
Implementation delivery is through reviewed PRs, with documentation and
qualification evidence updated alongside the code.

## Original evidence and implementation consequences

The table records the pre-cutover behavior at `0ccec836e`; the pause handoff above
describes what is now implemented. The work sequence below remains the acceptance
contract, not a claim that every listed change or test is still unstarted.

| Original path | Finding and consequence |
| --- | --- |
| [epic_transaction.c](../../src/world/epic_transaction.c), `epic_transaction_submit_identified()` | Changes the balance and calls completion before returning. The writer records history; player saves persist the balance. Preserve this model. |
| [epic.c](../../src/world/epic.c), `gain_epic()`; [boon.c](../../src/economy/boon.c), `boon_publish_transaction_result()` | Each completed epic boon can submit a child before any preceding child's completion is handled. Ordinary awards are a real burst producer. |
| [artifact_guild_state.c](../../src/guild/artifact_guild_state.c) | Captures artifact timer/soul and cached guild revision; computes construction from current guild prestige. Reward-driven updates arrive only in `artifact_guild_state_publish()`. Successive captures can therefore reuse both a timer and a threshold calculation. |
| [artifact_guild_repository.c](../../src/guild/artifact_guild_repository.c) | Rejects mirror disagreement, expected timer/soul disagreement, or an old guild revision with `ESTALE`. An artifact revision change alone is already allowed. It currently mutates state as well as history. |
| [artifact_guild_transaction.c](../../src/guild/artifact_guild_transaction.c) | Publishes state/messages only after success and erases rejected pending work. `pending.emplace()` and coordinator attachment are not, by themselves, a guarantee of one live application after changing this design. |
| [artifact.c](../../src/guild/artifact.c) | `artifact_row_store()` and the soul stores already change memory and enqueue snapshots, including the domain mirror. `artifact_feed_published()` compensates for an intervening move storing the old timer by queueing another row. Remove the need for that delayed repair. |
| [assocs.h](../../src/guild/assocs.h), [assocs.c](../../src/guild/assocs.c), [sql_player.c](../../src/sql/sql_player.c) | Guild totals live on `Guild`, but `sql_save_guild_statements()` deliberately uses `prestige=prestige, construction=construction` on update. Memory authority requires saving both captured totals. Apply both before one save; do not reuse `add_points_from_epics()` unchanged, which saves prestige before adding construction. |
| [fight.c](../../src/combat/fight.c), `submit_pvp_outcome()`; [zone_touch_transaction.c](../../src/world/zone_touch_transaction.c), `publish()` | These are the other child producers. PvP derives children from a combat parent plus actor; stones use each participant's derived epic award ID and publish an offline participant on return. Preserve those identities and source timing. |
| [critical_command_coordinator.c](../../src/persistence/critical_command_coordinator.c), [player_save_worker.c](../../src/player/player_save_worker.c) | Commands and SQL jobs share one writer. Retried commands remain ahead of later jobs; completions return separately. Serial execution does not repair an already-stale captured command. The coordinator's 256-entry completion cache is not a permanent deduplication store. |
| [artifact_guild_outcome.sql](../../migrations/artifact_guild_outcome.sql) | Existing inbox/outcome keys, parent foreign key, and unique parent/actor pair protect history identity. Keep them. A failed parent-history insertion can also prevent child history; it must not undo or gate live benefits. |

The issue reproduces three captures yielding one applied child and two `ESTALE`
failures, separately for artifacts and guilds. It also reproduces rejection when
the first feed already reached the same capped target. The actual production
bursts' successful feeds reached ten days, so those alerts do not establish lost
additional time or guild benefits for that incident. Below-cap and guild-only
losses are demonstrated by the repository probe.

Summon Ghasts is the player's tentative corrected trigger. Its delayed area
attack can reach ordinary kill/boon awards; it is not a persistent-pet operation.
The exact production cast and rejected comparison remain unverified.

## Work sequence

### ES-01 — Establish executable evidence through gameplay capture

- [x] Add failing-before tests for the real reward path and identify each old rejection.

Extend [test_artifact_guild_transactional_cutover.py](../../tests/async/test_artifact_guild_transactional_cutover.py)
with a native runtime fixture, or a focused `test_artifact_guild_rewards_runtime.py`
if separation improves clarity. Link the real capture/submit/application code;
stub unrelated engine services and control writer/completion delivery, not reward
arithmetic. Hold completions while issuing three awards from the same character
and awards from multiple characters in one eligible guild. Include a prestige
threshold crossed only by the accumulated awards, mixed artifact/guild rewards,
and a timer already at the cap. Assert intermediate and final values, not only
an absence of `ESTALE`.

Extend the existing [MariaDB harness](../../tests/async/artifact_guild_mysql_harness.cpp)
with the issue's repository probe cases. Label that probe as repository evidence,
separate from the new real-capture fixture. During characterization, distinguish
`mirror`, `expected_timer`, `expected_soul`, `expected_bind_timer`, and
`guild_revision`; one numeric error cannot identify them. Preserve an executable
before-fix case even when the final implementation removes these checks.

### ES-02 — Apply rewards once in memory and save the actual state

- [x] Make live application synchronous and remove completion-driven state changes.

1. Keep one calculation path in `artifact_guild_state.c`, using the existing
   artifact memory and `Guild` objects. Preserve epic-source modifiers, difficulty
   scaling, recent-frag bonus, worn-artifact selection, trusted-character rules,
   group eligibility, nexus prestige bonus, and PvP soul eligibility. Capture
   time once per award and preserve the current cap calculation. Check arithmetic
   and result bounds before changing any part of a combined reward.
2. Calculate each timer from the current memory timer. Calculate construction as
   `(prestige_after / notch) - (prestige_before / notch)` using the newly updated
   prestige from preceding awards. Apply both guild totals before capturing one
   guild save. When the timer already equals this award's cap, the eligible feed
   has zero added time and is a successful no-op. Preserve the existing clamp
   behavior for a timer above the cap; do not introduce a new balance rule.
3. Reuse `artifact_row_store()` for timer persistence and its domain mirror;
   introduce only the small timer-update entry point needed across these files.
   A feed changes no location, ownership, or soul. Reuse `Guild::save()` and
   change its SQL upsert to write captured prestige/construction totals. Preserve
   other guild fields and the shared statements used by kingdom payment writes.
4. Queue snapshots at the point of live mutation. They capture owned values,
   never game pointers for the writer to read later. Later transfers, soul
   changes, timer extensions/wars, expiry/removal, guild spending, and staff
   settings must capture the resulting newer state. Do not append an old reward
   snapshot again when a completion arrives or a history retry is requested.
5. Publish reward feedback once with live application. Completion processing
   updates persistence health only. Remove `artifact_feed_published()`'s delayed
   repair and the guild revision cache/hydration dependency once their callers
   are replaced. Keep boot loading of actual artifact/guild state.
6. Integrate ordinary awards, PvP, and stone publication. Keep the stone's durable
   claim boundary and offline-recipient behavior. Inspect each source's existing
   publication guard; no callback, reconnect, or duplicate completion may invoke
   the live reward a second time. A history replay is a separate operation from
   a new gameplay award and must never enter live application.

Do not revive the unused `epic_feed_artifacts()`/`Guild::add_points_from_epics()`
formula copies as a second path. Keep backend capability checks explicit:
The old `artifact_guild_state_hydrate()` returned false without MySQL, and the
flat-file critical dispatcher has no type-9 implementation. Removing hydration
must not accidentally enable an unsupported backend or change its reward rules.

### ES-03 — Make type-9 history idempotent and independent of live state

- [x] Convert the existing command/repository to record captured reward facts only.

Use [artifact_guild_command.h](../../src/guild/artifact_guild_command.h) and
[artifact_guild_command.c](../../src/guild/artifact_guild_command.c) for a versioned
payload containing the parent/actor identity, calculated deltas, actual timer
before/after values, and guild totals before/after live application. Keep the
15-artifact bound. Before-values describe history; they are not SQL approval
conditions. The existing result shape can remain if it still represents these
captured values unambiguously.

In `artifact_guild_repository.c`, remove gameplay timer/soul/guild comparisons
and writes to those gameplay fields. Record outcome and delta rows with the
captured facts in the existing inbox/outbox transaction. Allocate database ledger
revisions on the writer from durable ledger metadata; they order history only
and are not hydrated into a gameplay approval cache. Keep identity/hash checks,
parent linkage, unique parent/actor identity, bounds checks, and the existing
transactional replay result. History must never recompute a reward from current
SQL totals or overwrite memory or persisted snapshots.

Submit state snapshots before their history command on the game thread. A
terminal snapshot failure can still be followed by a successful history write;
the receipt alone therefore does not certify saved state. Keep those statuses
distinct and verify the actual state after recovery/drain.

Handle the following explicitly in `artifact_guild_transaction.c` and its three
producers:

- Derive the child from the same parent, domain constant, and actor. Distinguish
  a new source award from attaching/retrying its existing history before any live
  mutation. Do not treat `accepted` and `attached` as two new grants or recapture
  changed state under an existing identity. Reuse the original immutable command.
- Writer retry, duplicate completion, and repository replay perform history work
  only. Parent publication guards own live once-only application; prove them at
  the real producers. Do not rely on the coordinator's short completion cache,
  add an unbounded set of every award ever seen, or allow a replay API to call
  `gain_epic()` with a newly minted parent.
- Preserve a prepared history command when its local submission is retryable,
  within the existing pending-work bounds. A later history retry cannot reorder
  gameplay snapshots because it writes no gameplay fields. Queue refusal,
  unavailable history, malformed data, or a missing parent receipt must be
  reported separately from live reward success; none reverses an earned reward.
- Check snapshot admission errors too: the old `artifact_row_store()` ignored
  the SQL queue result. Surface the failure and retain a dirty indication on the
  affected current artifact/guild state for a bounded later save attempt. Retry
  a freshly captured current snapshot, not the old reward's values. Keep this
  domain-local: one dirty indication per existing entity, serviced from the game
  thread, without a second queue of historical snapshots. Use the same writer,
  include unsaved dirty entities in shutdown drain accounting,
  and acknowledge it only for the captured state that actually succeeded. No
  false durable-success report or endless invisible dirty state is acceptable.
- Distinguish queue capacity from memory allocation failure and shutdown
  quiescence. Keep the live state authoritative and report anything that could
  not be retained/saved. Do not invent crash recovery for work never persisted.
  Test the exhaustion policy and pending-state bounds explicitly.

Retain decoding of committed old commands/results needed for receipt replay and
pending outbox delivery. Produce only the new payload for new awards. Old-format
replay must resolve an existing receipt without applying gameplay; unsupported
uncommitted old payloads must receive an identifiable disposition, not a new
identity. Drain before upgrading and qualify an old pending outbox fixture.
Do not add a second long-lived gameplay implementation for compatibility.

The existing tables already contain the required history and uniqueness fields;
no schema migration is planned. If the executable design reveals an actual
missing field, use an additive, guarded migration and update bootstrap/verifiers
and compatibility contracts together. Preserve existing history and baselines.

### ES-04 — Keep diagnostics and reconciliation truthful

- [x] Separate live application, saved state, history results, and genuine integrity failures.

Use bounded fields in existing persistence diagnostics: stage, reason, opaque
operation/parent IDs, entity kind, counts, relevant non-sensitive values, and
capture/queue/completion timing. Exclude player names, credentials, and raw
payloads. Give each retained rejection a named reason, including identity
conflict, malformed payload, missing parent, missing state, and storage failure.
The old expected-timer/soul/guild-revision vetoes are removed from the new history
path, not renamed into a retry loop. Mirror disagreement remains diagnosable as
a persistence problem. Preserve full logging before wizlog suppression and
document that suppression age is not operation age. Preserve artifact cache
generation invalidation at mutation and durable outbox invalidation, and test
that an earlier in-flight Redis read cannot become current after the change.

Update [reconcile_artifact_guild_outcomes.sh](../../migrations/reconcile_artifact_guild_outcomes.sh):
its baseline-plus-feed-ledger and latest-guild-ledger-equals-current-state checks
cannot prove current state after timer wars, staff adjustments, or guild spending.
Check artifact mirror agreement including missing rows, outcome/ledger internal
agreement, identity uniqueness, and referential integrity separately. Do not
silence a real mismatch by rewriting baselines or replaying rewards. Prove state
equality after an observed writer drain in disposable tests; distinguish pending
writes from settled divergence. The old script read `.env`; the branch version
requires explicit credentials. Keep its tests on disposable storage rather than
the configured game database.

Keep `artifact_domain_state` and its item ownership reference; removing that
table or the one-item/one-owner protections is unnecessary. Document the new
meaning of reward ledgers in
[CRITICAL_COMMAND_PIPELINE.md](../persistence/CRITICAL_COMMAND_PIPELINE.md), the
ADR, and the existing database reference where affected.

### ES-05 — Prove gameplay, persistence, replay, and restart

- [x] Pass the matrix below, a real Summon Ghasts journey, and the required local gates.

| Case | Required evidence |
| --- | --- |
| Same character: three uncapped feeds with writer/completions held | Three increments visible before completion; persisted timer agrees after drain; one history outcome per award. |
| Guild-only and mixed rewards from several same-guild participants | Every prestige increment survives; construction crosses each threshold correctly; artifact/guild eligibility remains independent. Include different guilds as a control. |
| At/below/above cap boundary and successive awards in one clock second | Existing cap formula is preserved; repeated capped awards succeed with zero added time; no duplicate messages on completion. |
| Missing/unworn artifact, trusted actor, insufficient group, PvP wrong/right/free soul | Current eligibility rules hold; no newly eligible reward due to removing SQL checks; malformed combined payloads cannot partly change memory. |
| Feed before and after transfer, soul change, extension/wars, death/corpse move, expiry, removal/recreation | Memory follows game-thread order immediately; drained and reloaded state retains the final owner/soul/timer; delayed history or completion resurrects nothing. |
| Guild reward interleaved with spending, construction changes, staff settings, and kingdom payment save | Captured saves preserve both totals in order; an old completion/history replay cannot undo a spend or overwrite a later setting. |
| Retry, duplicate completion, receipt replay, reconnect, and completed-cache eviction | One live source publication and one outcome per parent/actor; unchanged command identity/bytes; no reapplication after receipt replay or after boot hydration. Exercise PvP and stone producers, not only `gain_epic()`. |
| SQL outage, rollback, lost commit acknowledgement, local queue refusal, and missing parent receipt | Gameplay remains usable; snapshots recover or report their actual unresolved state; history retries add no reward; dirty/pending state is bounded; no false claim of atomic state/history durability. |
| Hard crash before saves, between entity saves/history, and after history commit but before completion | Restart loads only persisted state, with any permitted unsaved loss documented; history/outbox replay never re-awards. No timer/guild increment is applied twice. |
| Clean restart and copyover with outstanding writes | Correct state after successful drain; unresolved writes named on bounded shutdown; copyover follows the existing drain-failure policy. |
| Mirror missing/mismatched row, bad payload, identity conflict, old result/outbox | Named diagnostic and correct recovery/refusal disposition; no blind state overwrite; old notification delivery remains compatible. |

Extend the existing artifact/guild MariaDB wrapper and register a new gameplay
journey, `test_mysql_artifact_guild_reward_journey.py`, in
[tests/run_db_tests.sh](../../tests/run_db_tests.sh). Use the maintained disposable
MariaDB setup. Run the full game with isolated staff/players, controlled worn
artifacts and guild membership, and several eligible epic boons/targets. Cast
Summon Ghasts and record cast, delayed attack, kills, boon publications, live
reward values, snapshot writes, and history completion. Allow for its random
one-round deferral or control randomness in the test fixture; do not substitute
a direct SQL payload for the gameplay leg. Include a deterministic direct-award
burst as the control and test both capped and uncapped conditions.

Reuse these focused checks, extending behavioral coverage where needed:

- `python3 tests/async/test_artifact_guild_transactional_cutover.py`
- `python3 tests/async/test_combat_artifact_persistence.py`
- `python3 tests/async/test_artifact_cache_codec.py`
- `python3 tests/async/test_epic_in_memory.py`
- `python3 tests/async/test_epic_stone_runtime.py` (its current artifact stub is
  not proof of actual feeding; the new runtime/journey coverage must supply it)
- `python3 tests/async/test_critical_command_coordinator.py`
- `python3 tests/async/test_persistence_severity.py`
- `python3 tests/async/test_kingdom_contract.py`
- `tests/async/with_disposable_mariadb.sh tests/async/run_artifact_guild_schema_mysql.sh`

Replace source assertions that require delayed publication, hydrated approval
revisions, or protected guild totals with assertions for the new contract; keep
codec bounds, identity, mirror, and transaction coverage. Run the existing
flat-file artifact/association tests to prove unchanged backend behavior.

For implementation, follow [TESTING.md](../guides/TESTING.md) and
[AGENTS.md](../../AGENTS.md): `make -C src`, changed-line formatting while working,
then `./scripts/format.sh --all --check`, `make test-all -j16 TEST_JOBS=16`, and
`make test-db`. Run `scripts/check_tests_catch.sh BASE HEAD` for changed defect
regressions and inspect that failures demonstrate behavior rather than a missing
renamed symbol. Add before/after evidence to
[REGRESSIONS.md](../testing/REGRESSIONS.md). Run
`npm ci --prefix site && npm test --prefix site` for documentation. Do not wait
for CI in place of local verification.

## Rollout, historical impact, and closure

- [x] Record code/test evidence for all six #58 acceptance criteria before closure.

The first criterion maps to ES-01 and the Summon Ghasts journey; reward/cap/state
ordering maps to ES-02 and the matrix; identity/retry/restart maps to ES-03 and
the fault/restart legs; diagnostic specificity maps to ES-04; regression and
historical-impact evidence maps to ES-05 and this section. None is complete
merely because this plan is published.

For a later authorized release, use the existing runbook and stop/drain the old
writer before booting the new behavior. Verify the actual loaded binary and
observe an uncapped award burst plus settled artifact/guild saves. Qualify
rollback against retained payload/result versions; an older binary must not be
assumed to understand new pending records. No live two-version writer operation.

Historical recovery requires attributable parent/actor/reward evidence and the
state/cap applicable at that time. Failed type-9 transactions leave no inbox row;
successful parent epics and a count of alerts do not establish compensable loss.
Produce a bounded, redacted assessment on #58, including unresolvable cases.
Obtain specific authorization for any production adjustment. Never grant all
rejected capped feeds as additional time or compensate under a fresh identity
without establishing what was actually lost.

## Ablation decisions

Keep the existing memory stores, writer, command identity, inbox/outbox, and
history tables. Remove the SQL gameplay vetoes, delayed memory publication,
guild approval-revision cache, and compensating feed write. A per-artifact or
per-guild completion queue, SQL-side rebasing, or a generic retry framework would
retain competing state owners and leave transfers/spending dependent on delayed
publication. They are not needed once calculations use current memory.

Simply deleting `ESTALE` is insufficient: captured artifact targets would still
collapse several increments, and guild construction would still use old totals.
Simply advancing memory early is also insufficient: the old repository would
apply deltas again, ordinary guild saves would omit the totals, and completion
could overwrite newer state. The changes above form one coherent cutover.
