# Issue #537: combat-intent backup recovery plan

Updated 2026-11-01. Work item: [#537](https://github.com/LuminariMUD/Duris/issues/537).
Branch: [branch/issue-537-backup-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-537-backup-plan).
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
checkout, not current master. No production state was inspected for this plan;
the issue's October 31 inventory, ages, capacity and service status are historical
reports, not fresh measurements. PR #551 also explicitly leaves production
acceptance pending.

**Non-goals:** no storage migration, schema or policy changes, replacement backup
system, retry/backoff redesign, replication setup, enabling recurring restore
drills, retention changes, live evidence deletion, full burn-in or unrelated
combat behavior changes. Production operations require separate authorization;
this request covers planning, an isolated checkout and publishing the plan.

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

## Delivery steps and acceptance coverage

1. **Retain the delivered implementation.** The first five issue checkboxes have
   paths in current master: storage validation and transient handling in
   `persistence_backup.py`; ordering and replay in the capture/restore/native
   owners above; focused tests below; updated `BACKUPS.md`. Do not reimplement
   the old validator or cherry-pick #551 again. If later evidence exposes a gap
   in an acceptance criterion, make the smallest change in its existing owner
   and extend its existing regression before revising this plan's status.

2. **Verify with the existing fixtures and preserve evidence.** Fresh focused
   checks on this baseline passed:

   ```sh
   python3 tests/async/test_combat_intent_backup.py -v
   python3 tests/async/test_persistence_backup.py
   python3 tests/async/test_backup_review_remediations.py
   ```

   Results: **7 + 43 + 17 = 67 passed**. The first command builds the native
   writer/qualifier fixture and proves held boot-lock capture, pending/completed
   bytes, recognized temporary omission, invalid-entry rejection, failed rename
   cleanup/retry, schedule/health success, and representative backup/restore
   journeys. Native repository outcomes are `applied` when the commit missed
   the authority snapshot and `already_applied` when it preceded it; repeated
   replay is idempotent and source/generation inventories stay unchanged.

   Limits: that focused journey substitutes candidate service boot and the
   dedicated-filesystem guard. Its MariaDB ordering case uses synthetic dump
   bytes. It does not independently prove a real MariaDB import or game boot.
   PR #551 records both backend builds and these two real disposable integration
   tests passing for the unchanged implementation:

   ```sh
   DURIS_RUN_BACKUP_INTEGRATION=1 python3 tests/async/test_persistence_backup_integration.py \
     PersistenceRecoveryIntegration.test_combat_intents_backup_restore_and_isolated_service_replay \
     PersistenceRecoveryIntegration.test_mariadb_full_dump_schema_history_values_and_isolated_service_boot
   ```

   Reuse that reported integration evidence for this documentation-only change;
   it was not rerun here. If an implementation fix or relevant dependency change
   makes it stale, build both server backends and the native fixture, then rerun
   these selected cases on disposable Linux with mount/unshare privileges,
   private MariaDB daemons and bounded restore storage as documented in
   `test_persistence_backup_integration.py`. Never load a production environment
   for those tests. For any C/C++ change run `./scripts/format.sh --check` and
   `make -C src`, plus the affected native tests. No hosted CI wait is required.

3. **After explicit production authorization, establish the actual rollout state.**
   Read the effective backup/health units, their checkout and environment-file
   paths, current policy, journal metadata, newest generation/status receipt and
   `schedule.json.completed`. Check whether the effective backup scripts already
   include #551 and whether any changed native qualifier/server executable needs
   building or deployment. Follow the normal deployment procedure only for the
   changes still absent; a source merge does not prove deployment. Preserve
   private configuration and all live evidence. No database migration is required
   by #551. Do not delete/unlock `.service-lock` or manufacture combat events.

4. **Prove recovery through the scheduled path.** Let a due timer evaluation run,
   or invoke its existing `schedule` entry point only within the authorized
   operation. Record the before/after generation IDs, capture-start/completion
   times, manifest/readback verification and completion receipt, then establish:

   - A new complete generation publishes successfully with `result: ok`, and its
     combat evidence satisfies the supported storage contract.
   - `schedule.json.completed` advances for that successful due capture, and a
     subsequent evaluation follows the configured interval instead of retrying
     capture every minute.
   - Both the effective backup and health units finish successfully and their
     outputs report `ok`; the newest capture-start age is within the configured
     7,200-second RPO. Check actual results, not merely timer activation.
   - The game remains healthy. Retain known-good generations and apply only the
     already-approved retention policy. If the run fails, retain redacted error
     evidence and investigate the actual failing phase without relaxing validation.

5. **Close only with operational evidence.** Post the authorized rollout revision,
   new generation, schedule advancement, UTC check times and backup/health results
   to #537. Keep it open until these facts are recorded; do not use a closing
   keyword on the plan PR. A production restore drill, replication and any
   reconciliation are separate decisions; the isolated fixture supplies the
   requested representative backup/restore proof.

## Files and ablation decisions

This plan delivery changes `docs/ongoing-projects/plan.md` and preserves its prior
#498 handoff unchanged as [plan-issue-498.md](plan-issue-498.md). No runtime code,
configuration, credentials, player data or operational state changes are needed.
The original dirty checkout and existing #537 implementation worktree are left
untouched.

For any demonstrated remaining defect, edit only the existing capture/restore,
native reader/qualifier or focused test owner identified above; update
`BACKUPS.md` only if its contract changes. Keep both durable file types, private
metadata checks, pre-snapshot combat capture and native qualification: removing
any loses a traced acceptance requirement. Reuse the existing retry path, fixture
and reported integration results. Drop duplicate implementation, new validators,
new test infrastructure and scheduler redesign: current paths already satisfy
those needs. No acceptance criterion is dropped to reduce scope.

## Estimate for me to finish implementation

The code and documentation implementation is already merged; **no additional
coding is currently indicated**. Fresh focused verification is complete above.
Allow **30-60 minutes of my active work** for the remaining authorized production
state check, any script/qualifier update still needed, one due capture, health
checks and issue evidence, excluding approval and time waiting for the configured
schedule. If a fresh isolated full integration run is needed, allow another
**45-90 minutes**, including backend builds. If live evidence reveals a new defect,
re-estimate from that concrete failure. These are estimates, not evidence that
production is recovered.
