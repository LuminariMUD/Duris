# Issue #490: complete private locker chest behavior

Status: **focused follow-up active; baseline implementation merged**.
Updated 2026-10-31. Implementation resumed by the owner after the plan review.
Issue: [Duris #490](https://github.com/LuminariMUD/Duris/issues/490).
Merged implementation: [PR #497](https://github.com/LuminariMUD/Duris/pull/497).
Inspected source: `master` at `b737db20210ff2d3e4eebccb212c9918b9b6f877`.
Plan checkout: `/home/aiwithapex/projects/duris-issue-490`,
`branch/issue-490-chest-durability` at `cc1ed03d72ff7f5b480ffe86e0c0976cfa90708b`.
That checkout predates the merged runtime code and retains the reviewed plan.
Active checkout: `/home/aiwithapex/projects/duris-issue-490-followup`,
`branch/issue-490-password-parsing`, stacked on `branch/issue-490-bank-load`
(PR #510, head `fb5cd3051`), then PR #509 and PR #507, based on master `b737db202`.
The maintained implementation handoff is `docs/ongoing-projects/plan-issue-490.md`
in that checkout; the shared master `plan.md` belongs to unrelated work.

## Outcome and current baseline

Keep the full private-chest workflow and acceptance criteria below, reuse the
merged implementation, and finish only the source-confirmed defects and missing
proof. The original plan, pause checkpoint and qualification history remain in
[the immutable reviewed snapshot](https://github.com/LuminariMUD/Duris/blob/cc1ed03d72ff7f5b480ffe86e0c0976cfa90708b/docs/ongoing-projects/plan.md).
The original behavior contract and acceptance coverage are retained below.

Live GitHub state checked on 2026-10-31:

- #497 merged on 2026-10-30 as `b737db202`; it includes access, payment,
  management, audit and private-save work, not just the initial capacity fix.
- #502 is merged; #503 is closed and its access work is incorporated into #497.
- #490 is closed as completed. Closure is not proof of every original test case.
- The old "durability implementation not started", open-stack handoff and
  **10-16 hours remaining** estimate are superseded. Do not restart that backlog.

The merged [implementation record](https://github.com/LuminariMUD/Duris/blob/b737db20210ff2d3e4eebccb212c9918b9b6f877/docs/ongoing-projects/plan-issue-490.md)
records prior builds, SQL engine qualification and broad regressions. Its
"ready for review"/"PR remains open" wording predates the merge. Preserve its
valid results as historical evidence, with the coverage limits identified here.
For any later implementation, start a narrow branch from refreshed master;
retain the paused branch and other worktrees as history. Do not replay or
reimplement the superseded stack.

## Non-goals and ablation decisions

The owner has authorized runtime fixes, focused proof and review-ready PRs for
this follow-up. Production operations and deployment remain separate work. Retain existing price, permissions,
capacity, backend support, saved identities and data. No general ACL service,
flat-file private gameplay, new writer, global bank cache, configurable limits,
repository-wide cleanup or full burn-in is needed by this review.

Use these existing mechanisms:

- `storage_lockers.c/.h`: one occupant/visit, one selected chest, shared access
  checks, password worker, wrapper registry and credential invalidation.
- `private_chest_purchase.c`: one immutable purchase on the existing SQL writer;
  chest creation, exact wallet/bank payment and `purchase_operation` receipt
  commit together. The same operation reconciles a lost reply. Currency
  reservation and wallet revisions already protect the affected balances/saves.
- `locker_change_chest()` and `locker_chest_changes_pulse()`: existing write
  receipt plus authoritative readback for metadata/deletion; existing guarded
  legacy rehash. Keep these result checks and the locker departure fence.
- `sql_log_chest_activity()` and its pulse: retained bounded audit work,
  deduplicated by `event_id`, with departure held until acknowledgement.
- `PrivateChest::SaveContents()/FlushContents()`: one immutable in-flight capture
  and one latest waiting capture, scheduled through the existing owner event.

Drop the proposed new `private_chest_command.c/.h`, multiplexed command codec,
critical-command dispatch registration and speculative snapshot-schema extension.
Those are suggested mechanisms, not required outcomes, and the merged paths
already supply the underlying transactions and receipts. Keep the existing
additive `0056_private_chest_receipts` migration (manifest sequence 57); do not
add a second receipt table, rewrite it, or migrate production during this work.

Reuse the existing native fixtures and SQL/socket journeys. Do not create another
journey framework or repeat the 898-test/98-database-leg qualification merely
because this plan changed. Extend proof where the original contract is not yet
covered; preserve the failure/restart checks that correctness actually needs.

## Proposed behavior contract

These are explicit implementation choices based on the existing code, not a
claim that the issue or current help has already established all these rules.

- Keep current management rights: matching personal/account owner, staff under
  the existing staff predicate, and members of the owning guild may list,
  create, delete-empty, change passwords, and read the log. Use the same manager
  verdict for password bypass on open. Guild private chests partition the shared
  locker; they are not secret from fellow guild members who can change passwords.
  Do not add creator ownership, guild ranks, or a second access list.
- A guest must already have valid locker entry access. A named chest with a
  password also requires successful verification; a password-free chest requires
  no secret. Guests cannot manage chests or view the activity log. Knowing a
  chest password never grants locker entry or bypasses racewar restrictions.
- Every private chest requires an explicit successful `open <name> [password]`
  before content inspection or movement, including for managers. One chest is
  selected at a time; opening another replaces it, and `close` revokes it.
  Bind authorization to the opener's runtime identity and current locker visit;
  another actor must never borrow the occupant's selection. Public sorting
  chests retain their existing behavior; `open public` clears private selection.
- Close, password changes/removal, deletion, departure, disconnect, and re-entry
  invalidate private authorization and pending open requests. Recheck current
  role, locker visit, chest identity and credential generation on asynchronous
  completion. A stale response cannot reopen a chest or alter a recreated one.
- Use unlimited locker-container weight (`value[0] = -1`), matching public
  sorting storage. Keep `m_chestId` for identity. Initialize the corresponding
  space sentinel if a supported `USE_SPACE` build needs it. Player carrying
  limits, item restrictions, and total locker accounting stay in force.
- Support private-chest gameplay on the SQL backend, including MariaDB and
  MySQL qualification. In flat-file mode, clearly reject private management,
  private-chest open, and activity-log operations before hashing, charges, selection, or
  mutations. Describe this availability in the room/help and retain public
  storage/sorting. Preserve all serialized private metadata, hashes, IDs and
  item graphs across public saves/restart. A temporary SQL outage is a service
  failure, not permission to switch backend or create a new empty catalog.
- Retain 500 platinum, five private chests plus public storage, one-token names,
  optional passwords up to 72 bytes, bcrypt and guarded legacy upgrades,
  empty-only deletion, no deletion refund, and latest-50 log viewing.

## Files and smallest remaining sequence

All source references here are to inspected master `b737db202`, not the old
plan checkout. The findings below distinguish visible source defects from
integration questions and missing test coverage.

### 1. Finish the small source-confirmed behavior gaps

- **Password-presence display:** `PrivateChest` constructs its room description
  from the initial hash (`storage_lockers.c`, constructor), while
  `SetPasswordHash()` in `storage_lockers.h` only replaces the string. Committed
  password set/removal therefore leaves the displayed "(locked)" marker stale
  until recreation. Update that owned description at the existing metadata
  publication boundary, using one rendering path. Extend the existing management
  regression for set/remove and failed write; verify both hash and room text.
- **Stable latest-50 history:** `locker_logcmd()` orders only by `logged_at`,
  whose stored timestamp has second precision. Add the existing unique log `id`
  as the tie-breaker (`logged_at DESC, id DESC`). No new column/index is required
  for deterministic ordering. In the existing SQL fixture, compare the actual
  latest 50 IDs with more than 50 events sharing a timestamp, including a replay.
- **Item identity survives truncation:** `locker_record_movement()` appends the
  UID after the full description; `sql_log_chest_activity()` then takes the first
  256 bytes. Item descriptions can be 512 characters in the existing schema, so
  the stable UID can be discarded. Keep the UID within the stored bound and
  truncate only display text, preserving valid text encoding. Extend the current
  audit fixture with a long description and assert the stored UID. No new audit
  schema or redundant item-identity service is needed.

Expected production files for those fixes: `src/item/storage_lockers.c/.h` and,
only if needed for the bounded audit text, `src/sql/sql_player.c`. Extend
`tests/async/private_chest_regressions.cpp` and existing SQL/command fixtures;
add no standalone framework. These are planned repairs, not fixes made by this
review.

### 2. Resolve two specific integration questions before adding machinery

- **Audit admission:** the movement hook ignores the bool returned by
  `sql_log_chest_activity()`. The shared access predicate checks queue capacity,
  but event-ID generation can also reject admission. Retrying an already-retained
  statement does not prove admission cannot lose a successful movement. Extend
  the existing native movement/audit fixture to control that failure boundary.
  If it confirms loss, prepare only the required one/two event records before
  the move, cancel on failed movement, and publish after success using the same
  queue. A new durable domain command is unnecessary.
- **Bank completion versus character load:** the purchase publishes to
  `CON_PLAYING` descriptors (`utility.c::publish_account_bank_balances_revision`),
  while `player_load_materialize.c` applies the read worker's bank snapshot.
  The configured load hold is PID-based and does not directly cover the chest
  reservation. Normal account login disconnects the prior account session;
  model that actual replacement/reconnect route, not invented simultaneous
  sessions. Use the existing load/account fixture to delay a bank snapshot across
  purchase completion and assert the admitted character sees the committed bank
  revision. This remains an integration question, not a reproduced loss. Add a
  targeted refresh/fence only if the real path fails; no global cache or global
  login barrier is justified in advance.

The relevant existing owners are `src/economy/currency_transaction.c`,
`src/item/private_chest_purchase.c`, `src/account/account.c` and
`src/player/player_load_materialize.c`. Touch them only if the focused case
establishes a defect. Preserve unrelated peer wallet credits and existing
auction/collector/shop interlocks.

### 3. Complete command and persistence proof in the existing journey

`test_mysql_locker_grant_journey.py` exercises real owner/guest/guild access and
bulk transfers, but explicitly empties the private chest before its restart.
Its surviving UIDs are public contents. `test_mysql_game_loop_queries_journey.py`
proves filled private re-entry and retained-save retry, but does not cold-restart
that filled private graph. The native SQL purchase fixture controls payment
preparation/publication; it does not replace real funding/management commands.

Extend `test_mysql_locker_grant_journey.py` once, reusing its actors, database,
server and existing cold restart:

- Exercise actual list/create/password set/change/remove/delete commands, bounded
  and reserved names, duplicates, fifth/sixth chest, empty-only deletion and no
  refund. Assert SQL plus user-visible results; run funding cases with whole
  wallet, whole bank and denomination change, and reject two insufficient
  individual sources even when their sum covers the fee.
- Leave a nested item graph in a private chest before that restart. Compare its
  locker/chest IDs, root/child UIDs and parent relationships after save, re-entry,
  cold restart and authorized retrieval, alongside public storage controls.
- Check exact movement audit rows (actor, chest, item UID or actual coin amount),
  partial/bulk/empty success and rejection, no sorting events, deleted identity,
  and password/log permissions. Aggregate nonzero row counts are insufficient.

Keep `run_private_chest_purchase_mysql.py` for deterministic rollback, refused
admission, lost COMMIT reply, offline completion, duplicate/limit/revision and
bank-change cases. Keep `test_mysql_game_loop_queries_journey.py` for private
write failure, departure veto and background retry. Extend an existing fixture
only for a missing outcome; do not repeat the same fault in every test layer.
Keep flat-file public-storage/restart and serialized-private-data preservation
proof; rerun them when a changed path affects those guarantees.

**Reachability clarification:** one private chest can be open at a time. Direct
private-A-to-private-B `empty` must be rejected; the supported transfer is GET
from A, select B, then PUT. `do_empty()` resolves room/inventory containers and
rejects identical source/target; it does not expose arbitrary nested-container
addressing. Cover nested bags as transferred roots and retained item graphs.
Do not add multi-open state or a new nested-targeting feature to manufacture a
successful test. The cross-chest acceptance below includes rejection of the
unsupported direct move and correct records for the supported two-step move.

### 4. Qualify the affected paths and stop

Run the extended real command journey on disposable MariaDB 10.11 and MySQL 8.0.
Run only the affected native/SQL failure tests while iterating; after C/C++ edits,
`make -C src`, changed-line formatting and the relevant documentation/runtime
contracts remain required. Reuse unchanged qualified builds and tests when their
source/behavior remains applicable; retain explicit limits when it does not.

Update the issue-specific handoff and maintained help only where final behavior
or its status changes. A focused follow-up can be reviewed separately from the
merged #497. No full-system rewrite, new stacked foundation PR or production
operation is required. Estimate the remaining work from these concrete checks
and any reproduced load/admission failure; the superseded 10-16-hour estimate
is not a current forecast or a basis for promising a shorter runtime completion.

## Proof and acceptance coverage

Completion requires all of the following; a green hash/helper suite is insufficient:

- Roles: personal owner, same-account same-side owner, matching guild member,
  staff using the current staff rule, granted guest, ungranted and opposite-side
  controls. Managers use explicit open; guests cannot manage/view logs; a guild
  member can manage shared chests and bypass their passwords as documented.
- Access: content inspection and all movement forms fail closed until permitted
  open; correct, missing, wrong, overlength and legacy credentials; password-free
  operation; selecting another chest; close; password replacement/removal;
  deletion/recreation; revoked role; leave/re-entry; disconnect; stale/out-of-order
  completion. Also verify ordinary bags, public sorting and unrelated door open/close.
- Capacity: chest IDs 10 and 100 with identical contents produce identical
  single/bulk eligibility; high IDs never grant extra capacity. Existing nested
  weight, ordinary finite container limits and carrying limits still hold.
- Audit: actual actor/IDs/item context, partial coins, nested bag roots,
  single/bulk/empty and cross-chest movement, latest-50 ordering, post-deletion
  identity, and log-view denial. No rejected or automatic move appears as success.
  Writer admission failure, transaction failure and replay cannot silently lose
  or duplicate accepted activity; no passwords/hashes enter logs.
- Management/payment: create/list, case-insensitive duplicates, name length and
  reserved/unresolvable names, public name protection, fifth/sixth chest,
  password set/change/remove, delete-empty/reject-nonempty/unavailable, no refund,
  full wallet, full bank, bank denomination change, insufficient individual
  sources despite a combined sufficient total, and no double charge on replay.
- Persistence/lifecycle: save/re-entry/cold restart preserve private/public item
  graphs, UIDs, ownership and sorting; private writer failure cannot be hidden
  by a successful public save. Exercise departure, idle rent, disconnect/extraction,
  actor disappearance between commit/publication, rejection before admission,
  pre-COMMIT failure, lost/ambiguous COMMIT acknowledgement and recovery. Verify
  balances and chest rows together using the disposable database, not just text.
- Backend matrix: real SQL command journeys on disposable MariaDB 10.11 and
  MySQL 8.0; no-MySQL/flat-file build plus unsupported-mode/public-storage journey
  and preserved pre-existing private records. A missing engine leg remains
  explicitly unqualified; it is not replaced by compilation or mocked SQL.

## Verification for this plan review

On inspected master `b737db202`, rerun successfully on 2026-10-31:

- `python3 tests/async/test_private_chest_lifecycle.py`: all 25 lifecycle cases.
- `python3 tests/async/test_private_chest_regressions.py`: registry, save receipts,
  immutable/coalesced retries, actor access, stale opens, management and history.
- `python3 tests/async/test_currency_in_memory.py`: currency calculations,
  reservations, shared-bank publication and independent peer wallet credits.
- `python3 tests/async/test_locker_container_weight_lifecycle.py`: all 24 cases.

These are executable native fixtures with controlled services, not new proof of
complete socket commands or SQL/cold-restart behavior. Prior MariaDB/MySQL and
flat-file runs are recorded in the merged handoff; this review inspected their
coverage and did not rerun them. No runtime code, server build, migration, production
state, branch history or external issue/PR was changed by this review.

Plan completion checks passed in the plan checkout (14 documentation tests and
no whitespace errors):

    python3 tests/async/test_documentation_contract.py
    git diff --check

The retained behavior-contract and acceptance sections were compared against
`cc1ed03d72ff7f5b480ffe86e0c0976cfa90708b` and match verbatim. Only this plan is
edited; the prior snapshot and the existing
`plan-issue-420.md` archive remain intact.

## Follow-up progress

2026-10-31: refreshed origin/master and confirmed the merged #497 baseline.
Created the isolated follow-up checkout above; preserved all prior branches and
worktrees. Outcome: finish every remaining behavior and proof requirement in this
plan. Non-goals and ablation decisions remain in force. First delivery: the three
source-confirmed display/history/identity fixes, extending existing native/SQL
fixtures and the required build. Audit admission, bank/load and complete command
journeys remain open until their own evidence proves the accepted outcomes.

### First follow-up delivery: metadata and history

Implemented the three source-confirmed fixes in section 1. `SetPasswordHash()`
now owns the one description-rendering path used by construction and committed
metadata readback; rejected/failed changes retain the previous marker. History
orders by timestamp then unique row ID. Item audit text starts with its UID and
SQL truncation preserves complete UTF-8 characters within 256 bytes. No schema,
new policy or new persistence service is required.

Proof on 2026-10-31:

- The expanded native regression first failed on the old implementation after
  acknowledged password removal left `(locked)` visible. The final production
  registry/receipt/metadata/audit fixture passes under ASan/UBSan, including
  failed writes, successful set/removal and long 2/3/4-byte UTF-8 item descriptions.
- `test_private_chest_lifecycle.py`: all 25 ASan/UBSan cases pass; the existing
  source extractor now includes the moved setter and its ordinary string service.
- `test_locker_container_weight_lifecycle.py`: all 24 ASan/UBSan cases pass;
  its existing source extractor also includes the setter.
- `make -C src -j6` passes, including a final incremental build after formatting.
- `with_disposable_mariadb.sh python3 tests/async/test_mysql_locker_grant_journey.py`
  passes all 14 groups. The added real `eq log` case compares the exact latest 50
  IDs from 60 equal-timestamp events, including a deduplicated replay; the original
  owner/guest/guild, idle-save and cold-restart cases remain intact.
- All 14 documentation tests and `git diff --check` pass. The commit hook runs
  changed-line formatting and Clang-Tidy 22.

Evidence stays in ignored `bin/qualification/issue490/`: `followup-build.log`,
`followup-build-final.log`, `followup-mariadb-journey.log` and `journey.json`.
The MariaDB journey binary SHA256 is `4bbe046fba84bc9d411afdf2f93b4e570a26c1d6dc1e9e4aa82983a0e20dd263`.
The MySQL leg and the expanded management/funding/filled-private-restart journey
remain due for the complete follow-up. Audit admission and bank/load behavior
are still integration questions, not fixed or disproved by this first delivery.

Published first delivery: [PR #507](https://github.com/LuminariMUD/Duris/pull/507),
`branch/issue-490-followup`, targeting master. The next dependent delivery will
resolve audit admission using the existing movement and SQL fixtures.

### Audit admission continuation (active)

Active branch is now `branch/issue-490-audit-admission` in the follow-up checkout,
stacked on PR #507 (`branch/issue-490-followup`, head `6a6182b0b`). The refreshed
fault test controls the production event-ID generator through a linker wrapper;
on the prior code it reproduced admission despite generation failure.

The repair uses the existing SQL audit queue: reserve one/two immutable records
before an item/coin/empty mutation; a small scoped `LockerMovementAudit` cancels
uncommitted attempts and marks records ready only after successful movement.
Prepared records count toward the same queue bound, cannot reach the writer, and
release on failure. The existing SQL retry, deduplication and departure fence stay
in force. Ordinary containers and flat-file public storage need no audit ticket.
No new writer, schema, global cache or domain-command service is introduced.

The production private-chest fixture passes controlled ID refusal, abandoned
reservation, failure of the second record in a private-to-public move and accepted
paired records, alongside its existing refusal/retry/metadata/save cases. The
server build passes. The affected command fixtures are being extended/run to
prove no item/coin mutation on refused admission (and wallet refund for coin-put
publication after debit). This is work in progress, not a completed delivery.
Bank/load and full command/funding/filled-private cold restart remain open.

Audit-admission qualification completed on 2026-10-31:

- Production private-chest ASan/UBSan regression passes event-ID failure, second-ID
  failure, abandonment without publication, accepted paired events and the full
  queue's last-slot case (no false first event or leaked reservation). Its existing
  refused-writer/failed-receipt/retry checks still pass.
- Actual put/get, whole/partial coin pickup, coin debit/publication/refund, empty
  and corpse-haul fixtures pass. Added controlled admission refusal proves no
  movement/credit/pile mutation; old-money PUT restores its prior wallet once.
- `test_private_chest_lifecycle.py`: all 25 cases; container/weight: all 24 cases.
- Disposable MySQL 8.0 locker command journey: all 14 groups pass, including exact
  history ordering, real private transfers, idle save and cold restart. Report:
  `bin/qualification/issue490/audit-admission-mysql-journey.json`; binary SHA256
  `26e80815fa214f8c1be9e3a698db3b64c3fcf0725c3df86815e13325388e9b85`.
- Fresh no-MySQL artifact build plus flat-file unsupported-private/public-storage
  and restart journey pass (`audit-admission-flatfile-journey.log`).
- Final `make -C src -j6` passes (`audit-admission-build-final.log`), as do four
  item-command pipeline contracts, item-in-memory/account-bound/password contracts,
  all 14 documentation contracts, changed-line formatting and Clang-Tidy 22.

The socket/flat-file journeys precede only final formatting and preservation of
`item_get_rejected` after a failed container delivery. The affected rejection
boundary was rerun under ASan/UBSan (get finalizers and corpse haul), with a final
successful server build; unchanged successful runtime paths reuse those journeys.
The earlier metadata MariaDB report is retained as
`bin/qualification/issue490/metadata-mariadb-journey.json` rather than overwritten
by the MySQL report. Bank/load and expanded command/funding/private-graph restart
proof remain outstanding; no complete-goal claim or production operation is made.

Published audit delivery: [PR #509](https://github.com/LuminariMUD/Duris/pull/509),
`branch/issue-490-audit-admission`, targeting PR #507. Next: investigate the actual
account replacement/new-character load path against purchase completion.

### Bank/load continuation (active)

Current branch: `branch/issue-490-bank-load`, stacked on PR #509 (parent head
`8a6af45c2`), same follow-up checkout. Focused fault cases reproduced three actual
boundaries before repair: (1) real `get_account_name_safe()` returns Unknown after
socket detachment, causing the purchase callback to discard a still-live purchaser;
(2) the real currency publisher skips a disconnected purchaser's bank fields;
(3) the actual duplicate-login block plus request builder admits a different
character's read before purchase completion, while bank publication skips its
loading descriptor. The held old snapshot then hydrates the old bank revision.

The purchase SQL fixture now compiles the production identity getter, shared-bank
publisher and chest balance publisher, retaining controlled payment preparation,
writer delivery and actor lifetimes. The load pipeline fixture compiles the actual
account replacement block, request builder, bank publisher and bank-hydration
statements, with a controlled database read delayed across completion. It models
one old socket replaced by one new socket, not simultaneous active account users.

Repair: retain the purchaser's stable PID/racewar when linkdead, still reject a
mismatched connected account/side; publish its acknowledged bank directly with a
revision guard. Fresh game loads for the pending purchase's account refuse until
the receipt resolves, then retry against committed data. Other accounts and
metadata-only deletion loads continue. No cache, new writer, schema extension,
global login barrier or snapshot replay service is needed. The existing bank/peer
wallet interlocks stay in force. Qualification and remaining full journey proof
are still in progress.

Bank/load qualification completed on 2026-10-31:

- The expanded load pipeline case first failed by admitting bank revision 1 / 1000
  platinum after revision 2 / 500 platinum committed. It now passes: this account's
  fresh game load refuses while the receipt is pending and reads revision 2 on
  retry. The real account replacement block has removed the prior descriptor;
  unrelated accounts and metadata-only deletion loads remain admitted.
- The real currency ASan/UBSan fixture first failed for a disconnected purchaser's
  bank. It now passes direct purchaser publication, older-result revision fencing,
  account-busy identity/release and all existing peer wallet-credit interlocks.
- The expanded SQL purchase fixture first failed with a retained linkdead buyer
  misclassified as absent. Final MariaDB 10.11 and MySQL 8.0 runs pass, compiling
  the actual identity getter, bank publisher and currency publisher. Tests include
  linkdead wallet completion, disconnected bank completion after a lost COMMIT
  response, extracted actors, changed connected account/side controls, rollback,
  writer refusal, duplicate/collation/limit conflicts and denomination change.
- `make -C src -j6` passes (`bank-load-build.log`); currency transaction contracts
  (9), racewar policy/runtime contracts, account-menu contracts, load pipeline,
  currency in-memory and all 14 documentation contracts pass. The commit hook
  runs formatting and Clang-Tidy 22.

Logs: `bin/qualification/issue490/bank-load-baseline-purchase.log`,
`bank-load-purchase-mariadb.log`, `bank-load-purchase-mysql.log` and the build log.
The load fixture controls the read worker and applies the production bank hydration
statements; it is focused integration proof, not a new whole-socket delayed-login
journey. Full management/funding, exact movement-row assertions and filled nested
private graph cold-restart/retrieval proof in the existing command journey remain
outstanding. The accepted behavior and completion criteria remain unchanged.

Published bank/load delivery: [PR #510](https://github.com/LuminariMUD/Duris/pull/510),
`branch/issue-490-bank-load`, targeting PR #509. Next delivery extends the existing
real locker command journey and completes the acceptance audit.

### Final qualification continuation checkpoint

The three implementation deliveries are published for review: #507 -> #509 ->
#510. They are not merged by this task. Current branch is
`branch/issue-490-command-qualification`; no command-journey extension has been
implemented yet on this branch. All prior build/test/tool sessions are terminal.
No production operation, tag, deployment or goal-completion claim was made.

Next work remains exactly section 3 plus the final acceptance audit:

1. Extend the existing `test_mysql_locker_grant_journey.py`, keeping its actors,
   database, idle journey and cold restart. Add SQL-plus-feedback assertions for
   management/name/password/limit/no-refund and actual wallet/bank funding. Use
   the existing disposable seed and normal in-game funding commands; never adjust
   live cached balances via SQL. A separate visitor wallet/bank seed of 300/300
   platinum can test combined-sufficient, individually-insufficient rejection
   during its already-existing own-locker visit. A staff-funded owner wallet can
   cover the first chest; a bank seed with small denominations plus enough whole
   platinum covers bank change and fifth/sixth chest checks.
2. Capture actual moved UIDs from the player inventory snapshots before/after
   movement, then compare exact SQL actor/chest/action/item records. Keep the
   existing equal-timestamp/replay case. Add real partial coin amounts, ordinary
   bag EMPTY to/from the selected private chest, rejected private-A-to-private-B
   EMPTY, and supported GET/select/PUT transfer. Deleted/recreated-name history
   must retain the old numeric chest identity. No new journey framework is needed.
3. Before the existing cold restart, leave one bag root with a child in the private
   chest. Compare locker/chest IDs, UIDs and parent UID relationships across leave,
   re-entry, restart and authorized retrieval. Keep public contents as controls.
   The existing `contents()` query includes private rows, so update its expected
   four-row baseline when adding the nested graph. Source-confirmed: the escort's
   `m_itemCount` is public carried roots only (`PFileToLocker`), so existing
   `enter(..., items=2)` controls do not count private roots/children.
4. The real `locker_equipcmd` and `locker_chestcmd` both call the same
   `locker_require_owner` predicate. Extend the existing native private fixture
   where needed for actual canonical same-account/same-side and staff predicate
   variants, and unavailable-chest deletion, rather than inventing simultaneous
   account sessions. The real guild/owner/guest/side controls already have socket
   proof. `OVERLORD` or `god_check` is the preserved staff rule.
5. Run the completed command journey on disposable MariaDB 10.11 and MySQL 8.0,
   and the final no-MySQL/public-storage journey where final sources affect it.
   Reuse unchanged native/fault/migration proof; add a missing outcome in its
   existing fixture only. Compare every acceptance item to actual test coverage,
   update the handoff/help if needed, publish the qualification delivery stacked
   on #510, verify all remote heads/PR state and keep the goal active until the
   full objective is proven.

Useful source details checked for this continuation: names are 1-32 ASCII-style
letters/digits/underscore/hyphen; `public`, `chest`, `private` are rejected. Both
create/password reject over 72 bytes. Management may report `A chest change is
still pending` or `That chest is still being secured`; a bounded retry should
handle these real asynchronous refusals instead of assuming admission is success.
The existing staff coin syntax is `give 500 platinum <name>`; bank syntax is
`deposit/withdraw <count> <denomination>`. Bag #96443 is the actual bottomless
illithid bag (`bag` keyword), capacity 500, and the native container suite already
uses its weight semantics. Do not relax item/carry restrictions to make a fixture
pass; choose a valid ordinary fixture if a particular prototype is unsuitable.

### Password parsing defect found by complete commands

The expanded MariaDB journey passed the new actual wallet/bank/change, combined
insufficiency, name, duplicate, fifth/sixth and no-refund cases, then reproduced
rejection of an actual 72-byte password. `one_argument()` leaves the separator
at the start of its remainder. The old handler counted/hashed that separator;
`password ... none` also compared the untrimmed remainder and hashed it instead
of removing the password. The native fixture had hidden this by trimming in its
parser stub. It now compiles the real argument/filler parsing code.

A literal parser handles the two management words (operation and chest name);
creation rejects the existing filler words so names/passwords cannot silently
shift position. Leading password separators are removed before create/set and
before interpreting the `none` sentinel or checking the payload length. OPEN
retains its raw remainder for existing credentials; the existing private password
worker checks the normalized candidate, then the legacy raw candidate, each
bounded to 72 bytes. It upgrades SHA-256 using the candidate actually verified.
Account password semantics and the C API stay unchanged. No credential rewrite,
migration, plaintext logging or game-thread bcrypt is introduced.

The real worker regression first failed on a separator plus a 72-byte credential;
it now passes current/prefixed bcrypt, both SHA-256 forms/upgrades, wrong input,
72/73-byte boundaries, prevention of legacy bcrypt prefix truncation and unchanged
account whitespace behavior. The native production registry/controller fixture
passes real parser/72-byte create/set, `none` removal, reserved filler names,
actual same-account/staff role checks and unavailable deletion. All 25 lifecycle
cases and `make -C src -j6` pass. Maintained chest help now states the real bounds,
reserved names and guild policy. Active source delivery branch is
`branch/issue-490-password-parsing`; the expanded command journey remains
uncommitted for its subsequent qualification delivery. Complete two-engine journey
and the final acceptance audit are still outstanding.

Parser ablation: ordinary OPEN/door word parsing stays on the original function;
only management needs literal words. The helper consumes management separators
once, so no duplicate trimming is required there. Existing separator-only stored
credentials remain verifiable through the raw worker fallback; account whitespace
semantics and the private 72-byte bound have executable controls. The latest
native suites, final MariaDB build, fresh no-MySQL locker journey and flat-file
private-data preservation fixture pass. The extended SQL journey has also passed
management/password/access/audit/idle groups. Its fixture was adjusted to collect
legitimate mortal coin spills and to fund exact copper while already in the room;
production carrying/coin rules are unchanged. Final SQL journey runs remain due.

Password source delivery qualification: the final worker suite, all 25 lifecycle
cases and the expanded production registry/controller ASan/UBSan fixture pass.
`password-parsing-build-final.log` records the final successful server build.
The real MariaDB journey has passed the corrected 72-byte set/change/removal,
password-free guest open, all reserved-name cases, exact history ordering, owner/
guest movements and idle save. Complete journey qualification is still separate
work; its pending test-file changes are intentionally not in this source commit.
The fresh no-MySQL build/public-storage restart journey and flat-file repository
private-record preservation checks pass; management-only token parsing does not
run for unsupported flat-file private commands. Help and documentation contracts
are current. No production state or stored credentials were rewritten.

### Command-log privacy continuation

The final acceptance audit reproduced chest credentials in the default-enabled
command ring and all three forced-command log sinks. The existing command-log
filter now withholds private OPEN/equipment commands, including abbreviations
and nested AT/FORCE/ORDER commands. FORCE logs use that same filter, while
execution retains its original input and unrelated staff diagnostics remain.
No additional logging service, setting or credential storage is added.

The expanded existing command-ring regression compiles the real parser/table
and FORCE handler, and passes persisted-ring, exit/crash, all three forced log
sinks, unchanged execution, and ordinary-command/conversation controls. The
chat-privacy policy regression and MariaDB server build pass. Complete locker
journeys already pass all 20 groups on both MariaDB 10.11 and MySQL 8.0, including
filled nested private cold restart; those pending qualification changes remain
in the qualification checkout. Real socket log-privacy and the final handoff
audit remain in progress. Delivery branch: branch/issue-490-command-privacy.
