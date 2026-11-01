# Issue #537: combat-intent backup recovery plan

Updated 2026-11-01. Work item: [#537](https://github.com/LuminariMUD/Duris/issues/537).
Delivery: [PR #556](https://github.com/LuminariMUD/Duris/pull/556), merged as
[`fb01299a9`](https://github.com/LuminariMUD/Duris/commit/fb01299a9cacdb93b63055b8af39e0b48242cc9a).
Worktree: `/home/aiwithapex/projects/duris-issue-537-plan`.
Reviewed baseline: `0a972227636b66c4e0c98900b1120c25ac181353` (`origin/master`).

## Outcome

A normally booted supported game can publish and restore persistence generations
containing locker receipts and durable combat outcomes, with strict validation and
correct replay across the authority snapshot. Complete the issue only when an
authorized production check proves publication, schedule advancement, and backup
and health success inside the configured two-hour recovery-point objective (RPO).

**Current status:** the implementation is already on master through
[PR #551](https://github.com/LuminariMUD/Duris/pull/551), squash commit
`601fdf646ad65d6dc16fc9df9f1175b1250d2411`. Its relevant implementation,
documentation and test files are unchanged at this baseline. This plan therefore
retains that implementation and targets the remaining verification and operational
acceptance. The issue's receipt-only description describes its older incident
checkout, not current master. The fresh qualification and read-only production
inspection below supersede the planning-time reliance on #551's reported tests.
All six issue acceptance criteria now have evidence. No additional runtime fix
was needed; #551's implementation is retained.

**Non-goals:** no storage migration, schema or policy changes, replacement backup
system, retry/backoff redesign, replication setup, enabling recurring restore
drills, retention changes, live evidence deletion, full burn-in or unrelated
combat behavior changes. This delivery qualifies the existing implementation;
production inspection is read-only and invokes no backup, deployment, migration,
restart, restore, retention or configuration operation.

## Verified code paths and storage contract

- [Startup](../../src/net/comm.c) initializes locker identification and combat
  transactions with the same `CRITICAL_COMMAND_JOURNAL_DIR` (lines 1220-1223).
  [The native intent store](../../src/combat/combat_outcome_intent.c) creates
  `combat-intents/` with mode 0700 and holds its empty `.service-lock`. A normal
  boot therefore needs backup support even before any combat command exists.
- [The native atomic writer](../../src/flatfile/flatfile_store.c) publishes a
  command by writing `.<operation-id>.intent.tmp.<pid>.<sequence>` at mode 0600,
  syncing it, and renaming it to `<operation-id>.intent`. Completion renames that
  file to `<operation-id>.recorded` and syncs the directory. Pending commands
  replay on initialization; completed files remain reconciliation evidence.
- [Capture](../../scripts/persistence_backup.py) already recognizes the empty
  lock and both durable extensions with a nonzero lowercase 32-digit hexadecimal
  operation ID. It bounds durable files to the native 8 MiB payload + 128 KiB
  envelope + 32-byte SHA-256 limit and checks their appended checksum. Existing
  path checks enforce custodian ownership, private permissions, regular files,
  single links, and no symlinks; capacity and free-space limits remain active.
  The locker/retired-journal compatibility rules remain supported.
- Capture omits only recognized unpublished atomic-write names after checking
  their file metadata. It does not copy partial temporary bytes, remove live
  temporaries, skip arbitrary dotfiles, or omit durable combat evidence. Unknown
  files, nested directories, unsafe metadata, invalid IDs/sizes, nonempty locks
  and bad checksums reject the generation. A rename race can fail the attempt
  safely; staging is removed, the old generation survives, and the existing next
  schedule evaluation retries without an advanced completion timestamp.
- `backup()` freezes combat evidence **before** either the MariaDB dump or the
  flatfile authority copy. A captured `.recorded` marker then cannot suppress a
  commit missing from that later snapshot. A captured `.intent` remains pending
  even if the live game completes it during capture: restored repository replay
  applies a missing commit or recognizes its existing operation receipt.
  [Combat completion](../../src/combat/combat_outcome_transaction.c) only records
  completion after a committed result. Locker receipts retain their separate
  after-snapshot copy and existing payment-in-flight check.
- [Restore](../../scripts/persistence_restore.py) verifies generation hashes,
  copies journals into a fresh isolated candidate, and invokes
  [the native qualifier](../../scripts/qualify_flatfile_restore.cpp) with
  `--receipts` before either backend boots. The qualifier uses the shared
  `combat_outcome_intent_read()` for pending **and completed** files: checksum,
  bounded command/payload decoding, admission timestamp and filename identity
  must agree. It also rejects duplicate operation IDs, more than 128 pending
  intents, temporaries in a published generation, and unsafe entries. Preflight
  validates without replaying or renaming evidence; candidate service boot
  performs recovery. The [qualifier builder](../../scripts/build_restore_qualifier.py)
  includes the shared reader. Older generations with no combat directory remain
  supported.
- [BACKUPS.md](../operations/BACKUPS.md) already documents this storage contract,
  snapshot ordering, race/retry behavior, native qualification and isolated tests.
  `schedule()` advances `schedule.json.completed` only after an `ok` scheduled
  capture; a direct `backup` invocation alone does not advance that schedule.
  `status()` measures RPO age from the newest generation's capture-start time.

## Execution and proof (2026-11-01)

1. **Retained the completed implementation.** #551 already supplies the storage
   contract, transient handling, capture ordering, shared native qualifier and
   `BACKUPS.md` update. Code inspection and fresh tests found no additional
   implementation defect. Reapplying that fix or adding another validator would
   duplicate working code. The relevant production source hashes match this
   checkout's capture, restore, intent-reader and native qualifier sources.

2. **Built both server backends locally.** These commands passed with the normal
   warnings-as-errors profile and separate backend object directories:

   ```sh
   make -C src -j6
   make -C src -j6 PERSISTENCE_BACKEND=flatfile \
     DMS_BINARY=/home/aiwithapex/projects/duris-issue-537-plan/bin/server/dms_restore_flatfile
   ```

   All compiled artifacts remain ignored under `bin/`. The server hashes are
   `7defdd7dad77c20945e9ea65ee0f8d9fe420c723dc9da00eb861d05504ffe99a`
   (MariaDB) and
   `30993ef249c1f90a596a3957ff942870148bd43930e3650f6684af5c3d30c8a3`
   (flatfile).

3. **Passed all 72 focused checks.**

   ```sh
   python3 tests/async/test_combat_intent_backup.py -v
   python3 tests/async/test_persistence_backup.py
   python3 tests/async/test_backup_review_remediations.py
   python3 tests/async/test_backup_pfiles.py
   python3 tests/async/test_flatfile_backup_manifest.py
   ```

   Counts: 7 + 43 + 17 + 2 + 3. The native combat fixture proves held boot-lock
   capture, pending/completed evidence, exact temporary omission, unsafe-entry
   rejection, failed rename cleanup/retry and schedule/health success. Its
   backup/restore journey proves `applied` when the commit missed the authority
   snapshot and `already_applied` when it preceded it; repeated replay preserves
   authority values and leaves source/generation inventories unchanged.

4. **Passed both real disposable restore integration cases.** Run as local WSL
   root inside a private mount namespace, with newly built executables, private
   MariaDB daemons, bounded tmpfs restore storage and isolated service namespaces:

   ```sh
   unshare --mount --propagation private env DURIS_RUN_BACKUP_INTEGRATION=1 \
     python3 tests/async/test_persistence_backup_integration.py -v \
       PersistenceRecoveryIntegration.test_combat_intents_backup_restore_and_isolated_service_replay \
       PersistenceRecoveryIntegration.test_mariadb_full_dump_schema_history_values_and_isolated_service_boot
   ```

   Both passed in 153.522 seconds. This is fresh evidence, not a reuse of #551's
   results. Actual restored service boots replay pending combat into recorded
   evidence, retain completed evidence, and preserve source/generation bytes.
   The MariaDB case verifies dump/import, schema history and value reconciliation.
   No checkout environment or existing authority was used. The two compiled
   native fixture outputs were returned to the local checkout owner's ownership.

5. **Qualified gameplay on both backends.** The existing default combat journeys
   passed using the freshly built binaries and disposable accounts/characters:

   ```sh
   python3 tests/async/test_flatfile_player_repository.py \
     --build-inspector "$PWD/bin/tests/coin-death-inspector"
   python3 tests/async/test_flatfile_combat_journey.py \
     --variant default "$PWD/bin/server/dms_restore_flatfile"
   bash tests/async/with_disposable_mariadb.sh \
     python3 tests/async/test_mysql_combat_journey.py \
       --server "$PWD/bin/server/dms_new" --one
   ```

   They exercise account/character creation, real NPC combat, death, corpse loot,
   saves, reconnect and a server restart without duplicate consequences. The
   MariaDB journey put 12 items into the first player corpse and confirmed stable
   state after the second death/restart. The flatfile journey verified wallet,
   inventory, death count, experience and level across restart/re-entry.

   Real PvP qualification also passed on both backends after one `make world`
   preparation:

   ```sh
   python3 tests/async/test_frag_cap_journey.py --backend flatfile \
     --server "$PWD/bin/server/dms_restore_flatfile"
   bash tests/async/with_disposable_mariadb.sh \
     python3 tests/async/test_frag_cap_journey.py --backend mariadb \
       --server "$PWD/bin/server/dms_new"
   ```

   Both reached `PASS`: ordinary PvP produced the durable receipt, the maintenance
   clock consumed the result, shared caps/banked XP progressed correctly, and
   saved state survived restart. The existing quiet/circle result checks passed.
   This exercises the real combat caller alongside the native backup fixtures.

6. **Inspected production without changing it.** At 19:00:31 UTC the actual
   production checkout was `0a972227636b66c4e0c98900b1120c25ac181353`, running
   `mariadb-primary`. Effective user units use that checkout's `.env` and invoke
   the existing wrapper's `schedule` / `status --require-drill` entry points.
   Both backup and health last exited 0 with `Result=success` and JSON `ok`.
   The game unit remained active/running. Readback verified all inventory sizes,
   hashes, schema-manifest hash and dump structure for generation
   `01793556665833190526-61018f101094472e870be950f20de735`.
   Its captured combat tree contains the supported empty lock. The completion
   receipt is `ok`; its completion and `schedule.json.completed` both equal
   `1793556705`. Capture age was 2,966 seconds against the 7,200-second RPO.
   Policy remains hourly capture, no replica, and recurring restore drills off.

   At 19:08:20 UTC the game health endpoint returned HTTP 200 with
   `{"status":"healthy","persistence":"ready"}`. The production host has no
   `bin/tools/qualify_flatfile_restore` executable; a restore on that host must
   first run the existing documented `python3 scripts/build_restore_qualifier.py`
   step. This is a restore prerequisite, not evidence of a production restore
   test. The fresh real restore proof above used the locally built qualifier.
   No production build or restore was performed and disabled drill policy was
   preserved.

   **Observed scheduled recovery directly.** The existing timer published
   `01793560330608382493-e572569306ac47759ede58b927e88313`, captured
   19:12:10-19:12:50 UTC, with completion `ok`. Readback verified its complete
   inventory hashes/sizes, schema-manifest hash and dump structure; its combat
   tree contains the supported empty lock. `schedule.json.completed` advanced
   from `1793556705` to `1793560370`, matching the new completion receipt.
   Subsequent backup and health evaluations returned JSON `ok` (19:13:10 UTC),
   following the normal hourly capture cadence rather than recapturing every
   minute. At 19:14:07 UTC the new capture-start age was 117 seconds, inside the
   7,200-second RPO. Both units again exited 0 with `Result=success` at 19:14:08;
   the game health endpoint still returned healthy/persistence-ready at 19:14:36.
   Earlier generations remain present. No manual capture or operational script
   was invoked and no production state was changed by this work.

## Files, ablation and completion

This delivery changes `docs/ongoing-projects/plan.md` and preserves its previous
#498 handoff unchanged as [plan-issue-498.md](plan-issue-498.md). It adds no runtime
code, options, configuration or test infrastructure. Fresh executable evidence
replaces the planning-time assumption that existing reported proof was sufficient.
The original dirty checkout and existing #537 implementation worktree are untouched.

Keep both durable file types, private metadata checks, pre-snapshot combat capture
and native qualification: removing any loses a traced acceptance requirement.
Reuse existing fixtures and the scheduled retry path. Drop duplicate code,
validator layers and scheduler redesign because existing paths meet the outcome.
No acceptance criterion is dropped. Local build/qualification evidence is ignored
under `bin/qualification/issue537/`; synthetic game/database state is cleaned by
its owning tests. No full burn-in or hosted CI wait is part of this scoped work.

Implementation, focused tests, real isolated restores, both-backend gameplay and
production publication/schedule/health acceptance are complete. PR #556 merged
this record and completed #537. No deployment, production restore,
replica setup or recurring drill activation is included in this delivery.
