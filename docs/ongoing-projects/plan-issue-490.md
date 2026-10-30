# Issue #490: private locker chests

Status: implemented; final local qualification in progress. Updated 2026-10-30.
Issue: [#490](https://github.com/LuminariMUD/Duris/issues/490).
PR: [#497](https://github.com/LuminariMUD/Duris/pull/497).
Branch: `branch/issue-490-private-chests`, based on current `master`.
Worktree: `/home/aiwithapex/projects/duris-review-497`.

## Outcome

The PR now addresses all seven verified review findings alongside the original
capacity fix. Private wrappers remain in the outer locker registry across custom
sorting. Their names own their storage; database identity does not set capacity.

A private chest requires an explicit successful open before inspection or item,
bulk, coin or empty movements. The session belongs to the actor and current visit.
Close, disconnect, credential management and departure invalidate access. Delayed
verification checks visit, identity and credential epoch before publishing access.
Existing locker managers (owner, staff and matching guild members) bypass the
password; guests still require locker admission and the private password.

Private snapshots retain immutable data and completion receipts. Departure keeps
the live room and contents until the current private captures are acknowledged.
A refused or failed snapshot can be retried with those contents still present.
Public storage continues through the existing locker writer.

A purchase commits the chest and exact wallet/bank payment together. The nullable
unique operation ID on the chest is its receipt while completion is unresolved;
reconciliation after a lost COMMIT reply cannot charge again. Currency reservations
cover the actor/account/side and the existing direct-wallet entry points. Player
snapshot wallet revisions keep older captures from overwriting the durable debit.
Completion resolves the purchaser by persistent PID and publishes only committed
balances. Actor extraction cannot turn a committed purchase into a free chest.

Deletion and password changes retain the old live state until the write resolves.
An authoritative read reconciles failed or unknown results before changing memory
or announcing success. Pending changes close access and hold the locker room.

Successful item and coin transfers record actor, locker/chest ID and actual item
UID or coin amount. Bulk and empty use the same movement boundaries. Rejected
candidates and automatic sorting create no movement event. Retained audit events
retry with a stable unique event ID; departure waits for that locker's audit ACKs.
Deleted-chest history displays the stored numeric ID, including after name reuse.

## Scope and ablation

Reuse one occupant, one selected chest and the existing writer, SQL receipts,
currency preparation/publication, snapshots and ownership repositories. No general
ACL framework, extra receipt table, new service, configurable limits, flat-file
private gameplay, production operation, release or deployment is included.

Keep 500 platinum, five private chests, whole-wallet-else-whole-bank selection,
denomination change, bcrypt/guarded upgrades, empty-only deletion and no refund.
Names fit the SQL column and command targeting. Flat-file private commands reject
before hashing or payment; public storage and serialized private records remain.
The maintained chest help now documents the actual command/session contract.

The shared `plan.md` is restored from master; this issue's handoff is independent
of unrelated work. Original planning and capacity qualification remain in Git.

## Migration and proof

New additive immutable migration `0056_private_chest_receipts` (sequence 57) adds
nullable unique purchase/audit IDs. Existing chests and events are retained.
Its verifier uses the established connection trust boundary. Replay and schema
metadata fingerprints are measured on disposable MariaDB 10.11 and MySQL 8.0.
Apply it through the migration runner before booting the updated SQL server.
No production database was changed.

Focused executable proof:

- `python3 tests/async/test_private_chest_regressions.py`: production sorting,
  registry, session and stale verification, save refusal/failure/ACK, management
  reconciliation, audit retry and deleted identity; ASan/UBSan.
- `python3 tests/async/test_locker_container_weight_lifecycle.py`: 24 native
  container, capacity, loading and weight cases; ASan/UBSan.
- `python3 tests/async/test_currency_in_memory.py`: the production currency
  calculations, synchronous ordinary facade and account/side reservation.
- `tests/async/with_disposable_mariadb.sh python3 tests/async/run_private_chest_purchase_mysql.py`:
  production atomic purchase/controller with rollback, queue refusal, lost reply,
  offline completion, duplicate/limit/stale controls and bank change. Also run with
  `TEST_DB_IMAGE=mysql:8.0`.
- Existing `test_mysql_game_loop_queries_journey.py`: real server commands,
  private access, custom sorting, item history, leave and re-entry, with no SQL
  queries on the game loop.

Final build, regression, database journey, documentation, formatting and static
analysis results will be recorded after the current local runs finish. Hosted CI
completion is not a gate. The issue remains open until final qualification is
recorded; the PR remains open for merge, with no production operation authorized.
