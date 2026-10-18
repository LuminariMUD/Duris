# Issue #109: restore Marduk and Enlil Nexus stones

Status: implementation in progress. NS-01/NS-02 are implemented and locally validated;
NS-03 through NS-06 remain open. No production changes have been made.
Prepared 2026-10-18 from `origin/master` at
`89253179ab1f89249634eeef9116653381e3d807` and
[issue #109](https://github.com/LuminariMUD/Duris/issues/109), updated
2026-10-18T11:12:55Z. Delivery branch:
`branch/issue-109-nexus-stones`. Refresh master and the issue before implementation;
line references below describe this inspected revision, not a moving checkout.

The previous artifact plan is preserved unchanged in
[plan-issue-67.md](plan-issue-67.md). Its instructions concern that work only.

## Implementation record

### 2026-10-18 — NS-01: sage safety and neutral guardians

- Added a no-training response before dereferencing unsupported stats in both real
  sage handlers; preserved supported-stat purchases and their existing callback.
- Recognize neutral guardian 74 in the shared guardian predicate, retaining existing
  lookup/reset/reload/expiry behavior and per-stone tag matching.
- Added `tests/async/test_nexus_runtime.py` and its native harness. It links the real
  Nexus implementation and flat-file repository plus the extracted real `char_stat`.
  The unmodified source failed the neutral guardian lookup assertion. The fixed
  source passes with ASan/UBSan: two-stone repeated reset/reload, all alignments,
  repeated expiry, peer preservation, invalid sage stats 0/-1/255 with no spend or
  stat gain, and supported training/cap/insufficient-funds controls.
- Passed `make -C src -j8` (MariaDB server), the new runtime test, existing
  `test_nexus_stones_empty_table.py`, and `test_flatfile_nexus_repository.py`.
  The flat-file full server build and full-world gameplay proof remain outstanding.
- Publication snapshot: `branch/issue-109-nexus-sage-guardians`, based on master.
  [PR #190](https://github.com/LuminariMUD/Duris/pull/190), head `87a264acc`.
  The delivery branch carries this commit and subsequent chunks.

### 2026-10-18 — NS-02: load failures and diagnostics

- Guard callback prototype indexing; report missing ship/room/object/guardian,
  invalid SQL rows and query/result failures. A failed guardian load removes the
  newly created stone, and placement success is logged only after required entities
  are created. Preserve valid loaded prefixes and explicitly report incomplete loads.
- Empty catalogues still succeed. Initialization requests one warning; ordinary
  reload/reset loading stays quiet about intentional empty configuration. Existing
  flat-file authority failure still follows its fatal boot path.
- Staff reset/reload failures now report failure; request logs no longer claim that
  placement succeeded before attempting it.
- Replaced the old empty-table source assertion with ASan/UBSan executable tests of
  extracted real init/SQL+flat loaders/placement. The fixture controls database and
  world dependencies; it is not a live database/ship journey. Covers empty boot,
  missing callback prototypes, valid two-stone load, dynamic ship override, missing
  ship/room/object/guardian, invalid/missing SQL fields, query/result failures,
  retained valid prefix, cleanup on failure, and existing flat-file fatal policy.
- Passed both Nexus native suites, the existing flat-file repository regression,
  formatting, `make -C src -j8`, and the separate flat-file server build under
  `bin/issue109-flat`. No database seed or full-world journey has run yet.
- Publication snapshot: `branch/issue-109-nexus-loading`, based on
  `branch/issue-109-nexus-sage-guardians` for a focused dependent PR.

## Outcome and boundaries

Restore the two selected stones through persistent catalogue data, with working
placement, guardians, capture, existing rewards, expiration, and restart persistence.
Provide a repeatable migration, safe no-stat interaction, useful failure diagnostics,
and executable evidence before the separately authorized production rollout.

These are accepted design decisions, not recovered historical facts:

- Marduk: ID **1**, name `Marduk`, stored/active room **130199**, bonus **1** (epics).
- Enlil: ID **3**, name `Enlil`, stored room **130399**, bonus **3** (cargo). Keep
  `nexus_to_cyrics_revenge=true`; actual placement is Cyric's Revenge interior
  **slot 7**, resolved on each boot. Missing ship means load failure, never fallback
  placement in 130399.
- New rows start with `align=0`, `last_touched_at=NULL`, `stat_affect=0`
  (`APPLY_NONE`), and `affect_amount=0`. Zero is an explicit value, not a nullable
  field or the schema's legacy -1 default. Existing ownership/timestamps survive
  every retry and replay.
- Retain checked-in 11% epic/cargo rates, 12-day expiry, 300-second touch cooldown,
  and 3,600-second turn cooldown. Preserve minimum/rounding rules, ordinary turn
  payouts, Enlil's capture multiplier, and epic-task/boon completion. No sage/stat
  benefit is enabled for these rows.

Antu/Ningishzida, balance changes, hot catalogue refresh, a new persistence system,
historical mapping recovery, persistent cooldown redesign, and general ship changes
are excluded. Shared code must continue to support the flat-file backend. Production
SQL, migrations, restarts, and gameplay checks require explicit deployment authority.

## What the code actually establishes

The issue is a requirement source, not proof of the following behavior.

1. **Missing data explains the reported symptom, but current production is unverified.**
   The [dated investigation](../records/nexus-stones-109-investigation.md) records an October 16
   read-only zero-row query and two empty backup sections. This planning pass did not
   reconnect to that database or match it to the running process. The MySQL staff
   message describes the empty in-memory vector, not an independent SQL diagnosis.
   The [loader](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/economy/nexus_stones.c#L200-L257) reads/caches rows at
   boot; reset/reload at lines 1496-1588 do not requery SQL. A controlled restart is
   the existing activation mechanism.

2. **The selected data is supported, not already provisioned.**
   [Constants](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/economy/nexus_stones.h#L38-L68) define IDs 1/3, bonus types,
   object 394, guardians 65/66/74, and mace 395. Rooms are present in
   [nexus_ic.wld](../../areas/wld/nexus_ic.wld#L2760) and
   [nexus_island.wld](../../areas/wld/nexus_island.wld#L2405); their existence does
   not prove the historical mapping. The modern
   [bootstrap](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/migrations/bootstrap_multithread_safe.sql#L773-L784) creates
   **InnoDB** with NOT NULL integer stat fields and no rows. The legacy bootstrap
   used MyISAM. Do not assume that the target is MyISAM or claim a transaction can
   undo writes to an unverified target engine. This repair adds data, not an engine
   conversion or a schema-default change.

3. **No-stat needs a real guard despite disabled automatic sages.**
   [Ask/train](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/economy/nexus_stones.c#L1074-L1211) dereference
   `char_stat()` before checking it; [char_stat](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/core/utility.c#L5991-L6036)
   returns NULL for 0, -1, and unsupported apply codes. The training callback already
   checks the pointer. `affect_amount` is transported as data but does not disable
   training, which uses `nexusStones.sage.statAdd`. Automatic `load_sage` calls are
   commented out; do not reactivate them. A synthetic/manual sage can still reach
   the command handlers, so test those handlers directly.

4. **Neutral guardian cleanup is broken; neutral combat is not part of this repair.**
   `IS_NEXUS_GUARDIAN` excludes 74. Lookup, reset, reload and expiration use it;
   `load_guardian()` does create 74 at neutral alignment. Repeated neutral reloads
   therefore leave a previous guardian while adding another. Touch's room scan
   already blocks on 65/66/74. Preserve the existing combat procedures instead of
   assigning a new neutral combat special as a side effect of fixing recognition.
   Partial alignments -2/-1/+1/+2 intentionally load **no guardian**; an acceptance
   check requiring a guardian for every row would be wrong.

5. **Load logs currently overstate success.**
   [init/load](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/economy/nexus_stones.c#L178-L257) assigns prototype callbacks
   without guarding failed `real_mobile`/`real_object` lookups. The stone loader logs
   success before guardian creation, ignores its return value, and returns true.
   `load_guardian()` also logs before it has created a mob. Missing required templates
   must be covered at initialization and placement, not just by counting SQL rows.
   SQL stops at its first bad row and may retain a valid loaded prefix. Do not
   describe that as complete recovery or add unrelated all-or-nothing catalogue
   machinery to hide it.

6. **Ship ordering exists; ship availability is not guaranteed.**
   `boot_db()` calls [initialize_ships](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/ships/ship_base.c#L552-L584) before
   `init_nexus_stones()` in [comm.c](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/net/comm.c#L894). Enlil's
   [override](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/economy/nexus_stones.c#L1301-L1309) and
   [slot resolver](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/ships/ship_npc.c#L2042-L2045) are already implemented.
   `load_cyrics_revenge()` can fail its bounded ocean search, ship setup, creation,
   or room loading. The plan adds diagnosis and tests, not another ship spawner.

7. **Existing consumers already select catalogue-backed rewards/objectives.**
   [check_nexus_bonus](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/economy/nexus_stones.c#L281-L355) requires full
   control and matching racewar, then uses the property rate with integer truncation
   and its minimum. [gain_epic/PvP calculation](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/world/epic.c#L580-L608)
   and [normal/contraband cargo sales](https://github.com/LuminariMUD/Duris/blob/89253179ab1f89249634eeef9116653381e3d807/src/ships/ship_shop.c#L1084-L1088)
   already call it; epic bottles remain excluded. `get_random_enemy_nexus()` selects
   configured IDs and resolves a live object; `boon.c` validates the configured ID.
   No new hard-coded two-ID task selector is needed. Keep existing task probabilities
   and faction rules. Check the live reward paths, not just the bonus helper.

8. **Migration integration has requirements missing from the issue's sketch.**
   [run_pending](../../scripts/migration_runner.py#L331-L349) applies SQL, runs the
   verifier, then records success. A post-apply verifier is too late to provide
   the promised no-write conflict preflight. The apply SQL itself must check both
   target rows before either insert. The
   [0010 procedure/SIGNAL pattern](../../migrations/immutable/0010_coin_custody_payload.sql)
   already supplies a portable way to reject incompatible data before writes.
   A new head also requires the runtime manifest, compiled header and checksums;
   changing only the migration manifest makes the database and binary disagree.

9. **Default migration locking is not durable for the operation.**
   [acquire_lock/sql](../../scripts/migration_runner.py#L444-L479) holds a persistent
   client only for the special online modes. The normal path invokes one-shot
   `mysql -e GET_LOCK`, whose session exits before apply/verify/record. Its own code
   comment identifies that lifetime problem. Existing tests cover the online client,
   not exclusion between two normal runners. The issue's “serialize through the
   existing workflow” therefore needs a small runner repair, not an assumption.

## Implementation sequence

Keep these work items on the issue branch. Each needs its focused proof before
claiming completion; do not count publication of this plan as implementation.

### NS-01 — Safe no-stat handling and neutral lifecycle (locally complete)

Files: [nexus_stones.c](../../src/economy/nexus_stones.c),
[nexus_stones.h](../../src/economy/nexus_stones.h), and focused native regression
coverage under `tests/async/`.

- In ask/train, resolve the stat pointer once and return a handled, clear
  no-training response if NULL, before reading the stat, indexing names, displaying
  a purchase offer or submitting an epic transaction. Do not use `affect_amount`
  as a new training switch. Preserve valid legacy stat training/callback behavior.
- Include neutral guardian 74 in the existing guardian predicate. Retain per-stone
  tag matching in lookup/reload/expiry and global reset semantics. Do not change
  guardian stats, equipment, specials, or touch/capture balance.
- Compile the actual handlers and lifecycle paths with the real header, using the
  existing harness stubs. Test 0, -1, unsupported positive apply, and supported-stat
  controls. Assert unchanged stats/epics and zero transaction submissions on refusal.
- Exercise two stone IDs together: lookup, repeated neutral reload/reset, expiry
  and non-target guardian retention. Cover 0/+3/-3 guardian states and guardian-free
  partial states. ASan/UBSan must detect an unsafe dereference/lifetime regression.

Exit: no-stat commands are safe, supported training remains functional, and each
operation leaves only the intended stone and guardians without affecting its peer.

### NS-02 — Honest loading and diagnostics (locally complete)

Files: `src/economy/nexus_stones.c` and the same focused Nexus runtime harness.

- Guard prototype lookups before assigning callbacks. Missing stone or required
  guardian templates must produce a named failure instead of invalid indexing.
  Keep optional sage spawning disabled; guarding its existing callback assignment
  must not add a dependency on spawning sages.
- Resolve Enlil's ship slot before creating its stone. Report stone ID and missing
  ship/invalid resolved room explicitly. Never use 130399 as a missing-ship fallback.
- For states needing a guardian, make placement fail if it cannot be created;
  remove the just-created stone on that failure. Move successful placement messages
  after successful creation. Partial alignments still succeed without a guardian.
  Preserve existing mace behavior; missing mace is already an error and fails the
  rollout's template/equipment verification, not a reason to invent new equipment.
- Preserve valid prefix behavior on a later load failure, but report which row
  failed and that the catalogue is incomplete. Missing/null row fields, invalid ID,
  empty name, out-of-range alignment/bonus, SQL query/result failure, invalid room,
  and object/guardian failures need distinguishable messages. Respect the SQL
  integer schema and existing flat-file validation; no general parsing framework.
- On normal initialization, a successful zero-row load emits one warning explaining
  that Nexus gameplay is unavailable and pointing to the provisioning/runbook.
  Keep its successful return in SQL and flat-file worlds; do not make empty worlds
  fatal. Do not add recurring warning spam to periodic events or resets.
- Propagate/report failed reset/reload placement instead of announcing success.
  Do not make these commands refresh the SQL catalogue or add automatic retries.

Exit: a successful placement means the required world entities actually exist;
empty configuration and failed loading remain different, observable states.

### NS-03 — Serialized, insert-only migration and compatible runtime head

Files: [migration_runner.py](../../scripts/migration_runner.py), its existing tests,
one new `migrations/immutable/NNNN_nexus_phase1.sql` and executable `.sh` verifier,
[migration_manifest.json](../../migrations/migration_manifest.json),
[runtime_compatibility_manifest.json](../../migrations/runtime_compatibility_manifest.json),
[runtime_compatibility_contract.h](../../src/core/runtime_compatibility_contract.h),
and the two persistence contract documents. `NNNN` means the next free sequence at
implementation time; 0044 is the inspected head, not a reservation of 0045.

1. Reuse the runner's existing persistent lock-client path for ordinary runs as
   well as reviewed online modes. Hold it through baseline/prefix validation,
   apply, verification and history recording; fail if it dies. Record that exact
   connection ID and exclude only it and the probing connection from the ordinary
   production quiescence check. Other connections must still block the normal
   production path. Retain target confirmation, allow-list, backup, TLS and all
   existing online-mode restrictions. Do not add a Nexus online mode or lock service.
2. Add SQL preflight for both selected IDs, before either insert, using the existing
   short procedure/SIGNAL approach. Compare exact name, stored room, stat fields,
   and bonus, including a reserved stone name assigned to another ID. Reject a
   conflicting row with an identifiable ID/field; do not turn
   a missing counterpart into a partial write on a known conflict. Validate existing
   alignment is within -3..3; preserve valid alignment/touch state, including NULL.
3. Insert only the missing rows with the selected values. Preserve all unrelated
   IDs. Existing matching rows are no-ops even after play; a retry after an interrupted
   first insert adds only the missing row. No REPLACE, broad UPDATE, schema/default
   rewrite, or duplicate-ignoring statement that conceals a conflict. Clean up the
   migration-owned temporary routine on success and make its failed-run retry safe.
4. The verifier checks both canonical rows and valid state, without demanding
   neutral alignment/NULL timestamps or a global count of two on an unrelated
   populated database. An actual Phase 1 rollout separately requires exactly 1/3.
   It reports incompatibility without rewriting data. Replay of an already recorded
   migration does not run its verifier: run it explicitly in drift tests and rollout.
5. Seal apply/verify hashes and update the runtime head/history checksum in both
   contract files. Reuse
   [telemetry_rollup_schema_mysql.py](../../tests/async/telemetry_rollup_schema_mysql.py)
   with its private disposable-engine `--credentials` and `--update-contract`
   workflow; do not hand-copy metadata from production. Data-only seeding should
   leave table inventory/metadata fingerprints unchanged; investigate any drift.
   Do not edit existing immutable payloads or their hashes.

Exit: fresh and upgraded databases reach the same new head, concurrent runners
cannot overlap the operation, conflicts produce no catalogue write/history advance,
and a successful replay preserves player-influenced state.

### NS-04 — Automated qualification and test registration

Extend existing fixtures where they exercise the actual behavior. The current
flat-file harness proves storage/selected reward helpers; it does not boot the world
or exercise sages/guardian cleanup. The empty-table test is a source contract, not
an executable SQL loader test. Add a focused real-source Nexus harness for the missing
paths instead of counting those existing tests as proof. Keep generated binaries and
reports under `bin/`; never consume the checkout's `.env` in isolated tests.

Required executable cases:

- SQL and flat-file loader success with IDs 1/3; successful empty load with a warning;
  SQL query/result failures; malformed rows; each placement failure; missing ship;
  a good first row followed by failure. A failed row creates no stranded stone.
- NS-01 stat controls and complete guardian lifecycle, with assertions on side
  effects and object/guardian counts, not copies of the implementation's predicates.
- Migration on **MySQL 8.0, MariaDB 10.11 and MariaDB 11.8**: empty table, each
  row alone, both rows, changed alignment/time, partial prior apply, each static
  conflict, and unrelated rows. Check preserved bytes/values and failed/successful
  ledger state. Run the real apply twice as well as runner replay; those are
  different paths. Test verifier drift directly and incompatible preflight before
  any insert. The supported bootstrap is InnoDB; any claimed legacy MyISAM support
  also needs an explicit fixture and no rollback assumptions.
- Two real normal runners competing for the advisory lock; release and lock-client
  loss; ordinary production quiescence excluding only its own lock connection;
  existing reviewed online-mode guards. Extend
  [test_immutable_migration_runner.py](../../tests/async/test_immutable_migration_runner.py)
  and the disposable engine runner, rather than relying only on mocked call order.
- Full-control bonus calculations for good and evil, negative cases for the other
  side/neutral/partial control, integer/minimum cases, and zero stat effects.
  Exercise epic-award and both normal/contraband cargo-sale call paths; preserve
  the epic-bottle exclusion. Test only-configured Nexus task selection and boon IDs.

Register new database/journey legs in [run_db_tests.sh](../../tests/run_db_tests.sh);
keep argument-requiring journeys out of argument-free regression discovery. Reuse
the [disposable MariaDB wrapper](../../tests/async/with_disposable_mariadb.sh) and
existing journey client/runtime helpers. Label new test filenames as proposed until
implemented, and record their final commands here.

Run after relevant edits:

```sh
python3 tests/async/test_nexus_stones_empty_table.py
python3 tests/async/test_flatfile_nexus_repository.py
python3 tests/async/test_immutable_migration_runner.py
python3 tests/async/run_migration_runner_engines.py
tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:11.8 tests/async/run_runtime_compatibility_mysql.sh
./scripts/format.sh --check
make -C src
make -C src PERSISTENCE_BACKEND=flatfile BIN_ROOT="$PWD/bin/issue109-flat"
git diff --check
```

Also run the new native/migration cases and NS-05 journey at the final reviewed
source tree. Follow [TESTING.md](../guides/TESTING.md) for fixture integration. Use
the smallest relevant check while iterating; do not claim `make test-all` or
`make test-db` passed from individual legs. Hosted CI is reported separately and
does not replace local proof or require waiting to finish this work.

### NS-05 — Full-world staging and persistence journey

Use an isolated SQL database and full world, with independent accounts/characters,
ports and generated outputs. Reuse the setup/client conventions of
[world capture](../../tests/async/test_mysql_world_capture_journey.py) and
[epic training](../../tests/async/test_mysql_epic_training_journey.py), not their
current passing results as proof of Nexus gameplay. Create one focused Nexus journey
if these fixtures cannot directly host the scenario; register it as above.

1. Verify backend, new migration head, schema, selected catalogue, actual properties,
   rooms, prototypes 394/395 and 65/66/74, and Cyric's Revenge setup. Start normally;
   capture both successful load logs. Staff `nexus` must list only Marduk/Enlil.
   Inspect Marduk at 130199 and Enlil at the logged dynamic ship VNUM, with no
   Enlil object at the stored placeholder.
2. Use non-staff level-51+ good/evil characters. Prove guardian presence blocks
   touch, defeat allows progression, and full capture produces the correct guardian,
   rewards and +3/-3 ownership. Include low-level/neutral/same-side rejection.
   Staff may arrange fixture state but must not be the actor proving cooldowns.
   Use a controlled clock in native tests for exact 300/3,600-second boundaries;
   the journey proves real command wiring with recorded fixture timing settings.
3. Measure ordinary eligible epic gain and normal/contraband cargo sale deltas on
   the owning and opposing sides, before/after full control. Isolate other reward
   modifiers. Verify no bonus from neutral/partial states, existing turn payouts
   (including Enlil's multiplier), appropriate task completion and boon completion,
   and no stat gains/sage spawning.
4. Set controlled persisted touch timestamps while the isolated server is stopped,
   then boot: verify nonzero alignments expire only beyond the configured threshold,
   return to neutral with cleared touch time, lose their passive bonus and have
   one neutral guardian. NULL/zero touch timestamps do not expire a new row.
5. Capture partial and full alignments, wait for durable SQL writer completion,
   record SQL values, perform a clean stop/cold start, and compare them. Re-resolve
   the ship room; its VNUM need not remain constant. Verify no duplicate objects or
   guardians, including normal configured world-recovery startup if enabled.
   Restart resets transient stone timers/hum state today; preserve that behavior.
   Do not claim abrupt-crash durability from a clean restart or enqueue success.
6. Rehearse the missing-ship and failed-placement cases in the isolated fixture and
   repeat neutral resets/reloads. Diagnose the failure without fallback placement
   or a false complete-success report. Do not add ship respawn/lifecycle redesign.

Exit: both stones meet the gameplay and persistence checks on the same tested
revision. Record exact commands, engine/backend, effective settings, row snapshots,
logs and observed reward deltas in the handoff; keep credentials/player data private.

### NS-06 — Handoff, deployment and issue closeout

Update [the investigation](../records/nexus-stones-109-investigation.md) with a dated resolution
section linking this plan/results; retain its historical query and backup limits.
Update the migration/runtime contract docs for the new head. Before publication,
refresh master and resolve relevant drift, run affected checks, and publish a focused
implementation PR linked to #109. Do not merge or deploy merely because this plan
branch exists. Keep #109 open through production acceptance.

Before an authorized rollout, match the actual process, executable revision, backend
and database; query current schema/rows and effective tuning. Unexpected entries or
conflicting values require explicit reconciliation, never deletion to satisfy a count.
Retain a verified restorable backup plus before/after Nexus snapshots and the exact
set of newly inserted IDs. Build and prepare while service remains available.

The ordinary migration runner currently requires other database connections to be
stopped; special online allow-lists do not cover this new seed. Plan a controlled
maintenance/restart window for this existing path, after preparation and explicit
owner approval. Do not bypass quiescence or reuse an unrelated online flag. Apply,
verify the seed and runtime contract, then boot the matching binary. Record the
deployed revision, migration receipt, SQL rows, both load logs, staff listing and
authorized gameplay/restart smoke results. Close #109 only after both stones pass.

Rollback must account for the immutable ledger and cached rows:

- Before success is recorded, preserve the failure evidence and retry the guarded
  seed or restore only its newly inserted rows from the recorded snapshot with
  writers stopped. Do not overwrite pre-existing legitimate state.
- After the new head is recorded, **an old binary is not automatically compatible**:
  boot checks the exact migration head/checksums. Prefer a forward correction using
  the compatible binary/ledger. Never delete or forge history to make an old binary
  boot. A full downgrade needs a separately reviewed matching database/ledger backup
  restore and accounting for all intervening writes; it is not a two-row undo.
- Any authorized targeted data rollback first saves current Nexus state, stops
  writers, preserves unrelated rows, and restarts to clear the cache. Verify actual
  catalogue/world agreement afterward and record the intentionally disabled or
  restored state. Rollback is not successful Phase 1 acceptance.

## Completion map and current evidence

- [ ] Issue requirement 1, safe durable provisioning: NS-03 and NS-04.
- [ ] Issue requirement 2, no-stat sages: NS-01 and NS-04.
- [ ] Issue requirement 3, neutral guardian lifecycle: NS-01, NS-04 and NS-05.
- [ ] Issue requirement 4, empty/error/ship diagnostics: NS-02 and NS-04/NS-05.
- [ ] Issue requirement 5, tests and maintained handoff: NS-04 through NS-06.
- [ ] Staging catalogue/placement: NS-05.1; capture/rewards: NS-05.2-3;
  expiration/restart: NS-05.4-6.
- [ ] Target verification, backup, deployment approval, production proof and closure:
  NS-06. All remain required after local implementation.

Planning baseline checks run on the inspected revision (2026-10-18):

- `python3 tests/async/test_nexus_stones_empty_table.py`: passed its source contract.
- `TMPDIR="$PWD/bin/tests/issue109-plan" python3 tests/async/test_flatfile_nexus_repository.py`:
  passed the compiled repository/runtime-helper harness and preprocessing checks.
- `python3 tests/async/test_immutable_migration_runner.py`: 19 tests passed; this
  includes the existing online-lock test, not proof of normal-runner exclusion.

No full server build, disposable database integration, new runtime regression,
gameplay journey, production query or operational change was run for the original plan.
The source-derived failure paths above require executable reproduction during the
listed work items. These baseline passes do not prove the proposed fixes.
