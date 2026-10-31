# Issue #490: complete private locker chest behavior

Status: **complete and ready for review**.
Updated 2026-10-31. Work is prepared for review; follow-up PRs remain open.
Issue: [#490](https://github.com/LuminariMUD/Duris/issues/490).
Merged baseline: [#497](https://github.com/LuminariMUD/Duris/pull/497),
`b737db20210ff2d3e4eebccb212c9918b9b6f877`.

## Current checkout and delivery

Active checkout: `/home/aiwithapex/projects/duris-issue-490-followup`.
Delivery branch: `branch/issue-490-command-qualification`, targeting
`branch/issue-490-command-privacy` ([#524](https://github.com/LuminariMUD/Duris/pull/524)).
This file is the maintained implementation handoff. The original reviewed
`docs/ongoing-projects/plan.md` in `/home/aiwithapex/projects/duris-issue-490`
is mirrored only if unchanged since the last checkpoint. Master's shared
`docs/ongoing-projects/plan.md` belongs to other work.

Review order:

1. [#507](https://github.com/LuminariMUD/Duris/pull/507): room password marker,
   deterministic latest-50 ordering, UID-preserving UTF-8 audit text and audit
   admission before movement. The admission commits originally delivered as
   #509 were integrated into #507 by the separate review continuation.
2. [#509](https://github.com/LuminariMUD/Duris/pull/509): the review continuation's
   damaged-item scrapping fix reserves history for the destroyed item and spilled
   contents before mutation, and propagates refusal to single/bulk GET.
3. [#510](https://github.com/LuminariMUD/Duris/pull/510): linkdead payment completion,
   revision-guarded bank publication and the existing purchase reservation's
   account-load fence.
4. [#516](https://github.com/LuminariMUD/Duris/pull/516): literal management words,
   correct 72-byte password boundaries and `none` removal, compatible verification
   of old raw-remainder credentials, and maintained help.
5. [#524](https://github.com/LuminariMUD/Duris/pull/524): credentials withheld from
   debug-ring and FORCE log sinks, including nested command wrappers, while
   execution receives unchanged input.
6. The qualification branch above: expanded real management/payment/history/
   nested cold-restart journey, missing/overlength/stale OPEN cases, valid sorting,
   real EXAMINE access and persisted-log privacy proof, plus this handoff.

The published dependent branches were synchronized with the reviewed #509 commits
using ordinary merges, without rewriting history. Every runtime source in the
final qualification tree matches the synchronized #524 head. The qualification
PR adds tests and documentation only.

[#517](https://github.com/LuminariMUD/Duris/pull/517) independently corrected the
SQL journey's stale artifact-clear oracle and has already merged into master.
The same original fixture correction remains in this branch's ancestry. It
requires a protected physical stone to remain tracked, at its legitimate floor
or mobile location; disappearance is no longer accepted. No artifact runtime
source was changed for that fixture correction.

Published stack refs at this checkpoint:

- `branch/issue-490-followup`: `189227546437`.
- `branch/issue-490-audit-admission`: `54e19ed63ccc`.
- `branch/issue-490-bank-load`: `bd68742331e6`.
- `branch/issue-490-password-parsing`: `1659208660d4`.
- `branch/issue-490-command-privacy`: `26b3991d9c07`.

Original paused checkout `/home/aiwithapex/projects/duris-issue-490` remains on
`branch/issue-490-chest-durability` at `cc1ed03d72ff7f5b480ffe86e0c0976cfa90708b`.
Its [reviewed plan and original history](https://github.com/LuminariMUD/Duris/blob/cc1ed03d72ff7f5b480ffe86e0c0976cfa90708b/docs/ongoing-projects/plan.md)
and the archived #497 qualified checkout remain intact. Unrelated worktrees,
credentials, player data and production were preserved.

## Outcome, scope and implementation

Deliver the original behavior and acceptance criteria below through the existing
locker registry, purchase transaction, write receipts, password worker, bounded
audit queue and immutable private-item snapshot path. Keep the 500-platinum fee,
five-chest limit, guild policy, explicit open requirement and public storage.

Dropped the proposed `private_chest_command.c/.h`, multiplexed codec, new critical
command registration and speculative snapshot/schema extension: the existing
transaction/receipt paths already supply those responsibilities. There is no new
service, cache, backend fallback, multi-open state, nested-targeting feature or
production migration in this follow-up. Existing additive
`0056_private_chest_receipts` remains the required baseline (manifest sequence 57).

Current implementation owners:

- `src/item/storage_lockers.c/.h`: registry, manager/guest access, selection and
  lifecycle, committed metadata/room marker, deterministic history and the
  movement-audit reservation guard. `src/sql/sql_player.c`: bounded immutable
  activity admission, cancellation, deduplicated retry and acknowledgement.
- `src/cmd/actobj.c`: existing item/coin/empty handlers reserve before mutation
  and publish after success; refusals preserve contents/refund prepared coins.
  `src/world/condition.c` applies the same admission rule to damaged-item scraps.
- `src/item/private_chest_purchase.c`, `src/economy/currency_transaction.c`,
  `src/account/account.c`, `src/player/player_load_pipeline.c`: captured purchase
  identity, disconnected publication, bank revisions and pending-account load
  admission. Other account loads and metadata-only deletion remain available;
  independent peer wallet credits remain untouched.
- `src/account/password_hash.c`: private normalized/raw credential compatibility through
  the existing asynchronous worker. Account-password semantics and public C ABI
  remain unchanged; no credential rewrite is performed.
- `src/core/debug.c`, `src/core/prototypes.h`, `src/cmd/actwiz.c`: shared existing
  command-log filter for private credentials and the FORCE logging sinks.
- Existing native/SQL/socket fixtures are extended, not replaced by another
  framework. the locker entry in `lib/information/help_index` documents the actual bounds and guild policy.

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

## Qualification evidence and exact limits

Evidence lives under `bin/qualification/issue490/` in the active checkout;
compiled artifacts, runtime data and logs are untracked and must stay out of Git.
The commands below are run from that checkout. The SQL wrapper starts disposable
containers and never sources the local `.env`.

### Real commands, payments, audit and cold restart

`bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_locker_grant_journey.py`
and its `TEST_DB_IMAGE=mysql:8.0` counterpart passed **all 20 groups each**.
Reports: `complete-command-mariadb.json` and `complete-command-mysql.json`;
matching `.log` files retain the outputs. Both used binary SHA256
`402c869ac2db6bb146c32784164347e83eb78c93a628beb21a0c5d3bc8438138`, runtime source
at `28f194ae4` before the later logging-only repair and reviewed scrap repair.

Those real owner/guest/staff/guild journeys assert wallet-only and bank-only fees,
exact denomination change, individually insufficient sources despite sufficient
combined funds, names 32/33 bytes, duplicates/reserved/filler names, fifth/sixth
chests, nonempty refusal, no refund, 72/73-byte passwords, set/change/remove and
committed room markers. They cover existing entry/ownership/grant/racewar rules,
explicit open, denied guest management/history, ordinary door close, idle rent,
reconnect and cold restart.

Movement checks compare exact actors, numeric chest IDs, root item UIDs and coin
amounts; latest-50 checks compare actual IDs with tied timestamps and replay.
A nested bag and child retain chest ID, root/child UIDs, parent UID and vnum
across save, leave/re-entry, cold restart and actual owner/guest GET+PUT. Public
contents and grants are controls. Deleted-name reuse retains the old numeric
identity in history; rejected, automatic and sorting movements add no success.
MySQL's JSON also dumps exact movement rows; MariaDB passed the identical
assertions before that diagnostic-only dump was added.

Reachability: only one private chest is selected. Direct private-A-to-B EMPTY is
rejected; GET A, select B, PUT is the supported transfer and has exact history.
GET has no player amount/denomination syntax. Real partial PUT adds 1 copper to
an existing 3-copper pile and logs 1, followed by actual single/bulk GET of 4/2.
Internal selected-amount GET is covered by the existing native coin fixture.
No quantity-GET or nested-targeting feature was added to manufacture coverage.

### Final integrated source and failure/privacy journeys

`make -C src -j6` passed (`integrated-build.log`). Final runtime source includes
both reviewed #509 and #524. The complete 20-group journeys above are reused for
unchanged behavior; the final affected paths are qualified as follows.

`bash tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_game_loop_queries_journey.py`
and `TEST_DB_IMAGE=mysql:8.0` are the final socket checks. Their
`integrated-game-loop-{mariadb,mysql}.log/.json` record status and binary SHA256.
They use a real passworded chest, open/closed EXAMINE and LOOK controls, actual
valid `custom wield body` sorting, private INSERT rejection while public saves
continue, retained contents/departure veto, immutable background retry after
fault removal, re-entry and shutdown drain. Runtime logs must omit the supplied
password; game-loop query sites must remain zero. Both final integrated engine runs pass with zero game-loop SQL sites. Their
binary SHA256 is `25d9c108e2574bd685323e5803ce29c9cbe42a38b734b949c8a8470cb0e8dccd`.

`python3 tests/async/test_private_chest_regressions.py` passes the production
ASan/UBSan registry/controller fixture, real parser/role checks, unavailable
management, long UTF-8/UID text, metadata receipts, history and valid sorting.
Audit admission controls cover unavailable DB, event-ID failure (including the
second paired ID), full/last-slot queue, cancellation, paired publication,
writer failure/retry and reviewed damaged-item reservations/scrap creation.
The integration preserved both fixture allocation-failure controls.

`python3 tests/async/test_private_chest_lifecycle.py` passes **28 cases** under
ASan/UBSan, including newly explicit missing/overlength passwords and an older
pending OPEN arriving after a newer password-free selection. Earlier cases cover
wrong/legacy credentials, guarded upgrade failure/staleness, changed hash, close,
role/visit/actor changes, selection, deletion/recreation, disconnect, public
furniture, ordinary doors, backend denial and asynchronous history access.

`python3 tests/async/test_private_chest_password_hardening.py` passes the real
worker's full 72-byte normalized credential, bounded legacy raw candidates,
bcrypt/SHA-256 upgrades, separator-only legacy input, wrong/overlong rejection
and account-whitespace controls.

`python3 tests/async/test_command_log_ring.py` passes persisted ring/exit/crash
privacy using the real command table/parser and FORCE handler, abbreviations,
filler words, nested AT/FORCE/ORDER, all three forced-command log sinks and
single/all targets. Execution receives the exact original command; ordinary
commands/staff conversation logging retain their established behavior.
`python3 tests/async/test_chat_log_privacy.py` passes the existing policy contract.
The five latest native outputs are `integrated-*.log` named for each test.

### Controlled purchase and unchanged container proof

`python3 tests/async/test_currency_in_memory.py` and the existing
player-load fixture qualified actual account replacement, request building,
publication and hydration, including an old 1000-platinum/revision-1 read delayed
across a committed 500-platinum/revision-2 bank. Fresh loads for the pending
account wait; other accounts/deletion and peer wallet credits are controls.

`tests/async/run_private_chest_purchase_mysql.py` passed against disposable
MariaDB 10.11 and MySQL 8.0 using the actual purchaser identity/balance publisher:
linkdead wallet and bank completion, extracted actor, changed connected account/
side, refused submission, rollback, duplicate/limit/revision cases, denomination
change, and lost COMMIT reply/recovery without double charge. Evidence:
`bank-load-purchase-mariadb.log`, `bank-load-purchase-mysql.log`, plus the native
fixtures named in #510. These paths are unchanged by the later parser/logger fixes.

The existing 24-case locker/container weight lifecycle matrix qualified IDs 10
and 100/high IDs, single/bulk behavior, nested weight and ordinary finite/carrying
limits. Affected coin/item/empty/trap/corpse command fixtures passed after audit
admission; the reviewed scrap change also has single/bulk refusal proof in #509.
`USE_SPACE` is hardcoded 0 in maintained `actobj.c`; no supported enabled variant
requires a speculative new sentinel path.

### Flat-file, contracts and delivery limits

`python3 tests/async/test_flatfile_locker_journey.py` builds a fresh no-MySQL
server and exercises unsupported private operations before hashing/payment/
selection plus public sorting, guild/account storage and restart. Final output:
`integrated-flatfile-journey.log`. The final fresh build (86.107 seconds) and full journey pass.
`python3 tests/async/test_flatfile_locker_repository.py` previously passed
preservation of pre-existing private IDs, metadata, hashes and nested item graphs
across two public saves. The later logger and SQL scrap-admission changes do not
change that serialization path; do not rerun it just to repeat green evidence.

`python3 scripts/validate_runtime_compatibility.py` passes: 200 tables,
head `0056_private_chest_receipts`, maintained MariaDB/MySQL fingerprints.
`python3 tests/async/test_persistence_migration_contract.py` passes.
`python3 tests/async/test_documentation_contract.py`, changed-line formatting,
Clang-Tidy 22 and `git diff --check` are final delivery gates. Final gates pass; no generated artifacts are committed.

The baseline #497's broad 898-test/98-database-leg evidence is historical, not a
claim that those suites were rerun here. No full burn-in, hosted-CI wait,
production migration, deployment or live-player acceptance is part of this
review-ready objective. Original #490 is already closed; it was not reopened.
Master has advanced independently; its unrelated source changes are not claimed
as tested by this checkout. Any later merge/deployment must qualify its exact tree
and retain the existing production owner boundary.

## Handoff and remaining work

No required implementation or qualification work remains for this review-ready
objective. The final branch contains the synchronized source dependencies and
only the necessary qualification/documentation diff above #524.

Review the focused PRs in dependency order. Their required follow-up work is
implemented and covered above. Owner review/merging and separately authorized
production delivery remain subsequent actions. Do not restart the superseded
10-16-hour backlog, add the dropped command framework, or repeat broad green
qualification without a changed path or unresolved finding.
