# Issue #490: private locker chests

Status: implemented; local qualification complete; ready for review. Updated 2026-10-30.
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
One in-flight capture and one latest waiting capture are retained per chest.
A later ordinary save replaces the waiting capture, never the acknowledged one.
An existing owner-bound nevent flushes it after completion, including writer
refusal/failure; it uses immutable data rather than recapturing unsaved changes.
Timer admission failure is reported as non-acceptance. Public storage continues
through the existing locker writer.

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
Chest-name comparison uses the SQL column collation, so legacy accented names
produce a completed rejection without charges or a stuck reservation. Purchases
interlock with pending auction, collector and shop operations in both directions.
The shared bank is fenced; other account characters' independent wallet credits
continue to publish and survive the purchaser's final balance publication.
Names fit the SQL column and command targeting. Flat-file private commands reject
before hashing or payment; public storage and serialized private records remain.
The maintained chest help now documents the actual command/session contract.

The shared `plan.md` is restored from master; this issue's handoff is independent
of unrelated work. Original planning and capacity qualification remain in Git.
The published access stack (#502 -> #503, head `574b090e4`) is integrated into
#497, using its one occupant/credential-generation implementation and additional
furniture, role-revocation, ordinary-door and backend checks. Its original tests
are carried forward, with legacy-upgrade receipts and departure retry coverage.
Published ancestry is retained so the clean durability continuation can advance
without rewriting or dropping the existing stack.

Files: `storage_lockers.c/.h` own registry, sessions and receipts; `actobj.c`,
`actinf.c` and `item_command_policy.c` enforce inspection/movement; the purchase
module and currency module commit/publish payment. The movement visibility pass
now respects a vetoed departure. The dispatcher, migration/contracts, maintained
help and focused tests supply the integration and proof.

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
  reconciliation, audit retry and deleted identity; ASan/UBSan. It also verifies
  A/B/C coalescing without another save, immutable capture versus later unsaved
  changes, refused writer admission, failed predecessors and exception receipts.
- `python3 tests/async/test_locker_container_weight_lifecycle.py`: 24 native
  container, capacity, loading and weight cases; ASan/UBSan.
- `python3 tests/async/test_currency_in_memory.py`: the production currency
  calculations, synchronous ordinary facade and account/side reservation.
- `tests/async/with_disposable_mariadb.sh python3 tests/async/run_private_chest_purchase_mysql.py`:
  production atomic purchase/controller with rollback, queue refusal, lost reply,
  offline completion, duplicate/limit/stale controls and bank change. Also run with
  `TEST_DB_IMAGE=mysql:8.0`.
- `test_mysql_game_loop_queries_journey.py` passes on disposable MariaDB 10.11
  and MySQL 8.0: actual access, custom sorting, history and re-entry, plus a private
  INSERT trigger that forces a terminal save failure. The live actor/contents
  remain usable; removing the trigger permits a durable retry and re-entry. After removing the failure, SQL must contain the retained
  generation before any further save or departure. It reports zero game-loop SQL sites and no duplicate room insertion.
- `test_private_chest_lifecycle.py`: all 25 ASan/UBSan cases pass, including the
  carried access/role/visit/furniture/backend cases and acknowledged, failed and
  superseded legacy rehash completions.
- `test_mysql_locker_grant_journey.py`: all 13 real owner/guest/guild groups pass,
  including ordinary doors, idle disconnect, cold restart and stable item UIDs.

Final local results:

- Development and production MariaDB builds pass; the client-free artifact build
  and flat-file locker/public restart journey pass for the integrated sources.
- Root `make test-all -j8 TEST_JOBS=8` executed 898 tests: 897 passed initially;
  the timing-bound PostHog test passed an isolated rerun without relaxing its
  250ms assertion. Following access integration, all 35 affected regression files
  pass, including the 25 session cases and the flat-file locker journey.
- `make test-db -j4 TEST_DB_JOBS=8` executed 98 database legs: 97 passed initially.
  Its game-loop journey exposed the movement visibility pass ignoring a veto;
  the fix is verified by the strengthened MariaDB and MySQL reruns above. The
  other database results are retained; this was not a production operation.
- `make test-native`, all 14 documentation contracts, runtime/migration contract
  validation, changed-line formatting, Clang-Tidy 22 and whitespace checks pass.

Hosted CI completion is not a gate. The issue and #497 remain open for owner
review/merge. No release tag or deployment is part of this change.

Merge preflight qualification also passes all 39 financial/private regression files
and both native SQL purchase suites. Regressions cover the real auction pending
predicate and chest reservation before payout, reverse admission refusal before
any auction command, peer wallet credits while the bank is reserved, and legacy
`café`/`cafe` collisions with immediate reservation release and a succeeding later
purchase. The schema's collation remains authoritative; unknown COMMIT outcomes
still reconcile by operation ID before name checks.
