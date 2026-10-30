# Issue #490: complete private locker chest behavior

Status: **implementation in progress; capacity foundation qualified for review**. Updated 2026-10-30.
Issue: [Duris #490](https://github.com/LuminariMUD/Duris/issues/490).
Assignee: `moshehbenavraham`.
Branch: [branch/issue-490-private-chests](https://github.com/LuminariMUD/Duris/tree/branch/issue-490-private-chests).
Worktree: `/home/aiwithapex/projects/duris-issue-490`.
Source baseline: remote `master`, `0bec1dbaec2793f64bb8b6328dcd69447ef17494`.

The previous shared plan, including #420's completed implementation and later
integration records, is preserved byte-for-byte in
[plan-issue-420.md](plan-issue-420.md). Its SHA-256 is
`9306f27c4fad0663f588bb44f6b05fc8492d368d9bffb872c5c325570020f8e7`.
The owner authorized implementation, proportional local validation, commits, pushes
and focused review-ready PRs, stacked where dependent. The progress section below
is the current handoff; original source findings describe the planning baseline.

## Outcome

Make the advertised private-chest workflow coherent: explicit access policy,
effective open/close state, item movement history, capacity independent of ID,
truthful backend availability, and management/payment/save results that survive
asynchronous completion and restart without inventing success. Preserve existing
items, saved ownership identities, public sorting, password hardening, price and
five-chest limit. Prove the entire supported command journey in disposable state.

## Independently checked source findings

Paths and line numbers refer to the baseline above. These are source findings,
not a claim of unauthorized access against a running game.

1. `src/item/storage_lockers.c:567-607` authorizes personal/account owners,
   staff, and matching guild members for management. `locker_opencmd()` at
   4279-4366 exempts only the personal/account owner from passwords. The two
   policies differ. `StorageLocker` has an occupant, and normal entry excludes
   a second occupant at 3333-3415. Do not invent a multi-user session service.

2. `GetCurrentChestId()` is used only by `locker_closecmd()`; successful open
   sets a selection without connecting it to content inspection or movement.
   `PrivateChest` objects start with ordinary container flags at zero.
   `src/cmd/actobj.c:1095-1141`, `3473-3481`, and `7683-7767` supply container
   preflight/bulk/empty paths, while `src/cmd/actinf.c:2893-2937` and 3928-3929
   render contents, including examine's call back into look. The shared
   `item_command_policy.c` checks type/takeability, not chest authorization.

3. `PrivateChest::PrivateChest()` at `storage_lockers.c:1680-1707` puts the
   database ID into `value[0]`. Ordinary `put()` at `actobj.c:3966-3970` and
   `bulk_put_permitted()` at 3489-3523 interpret it as weight capacity. The
   existing sorting-chest constructor sets `value[0] = -1` at 1568. Separate
   `m_chestId` already exists. This confirms the field collision in source;
   this planning pass did not rerun the issue's removed temporary diagnostic.

4. A complete source call-site search finds no consumers of `CHEST_ACTION_PUT`
   or `CHEST_ACTION_GET`. The three gameplay calls to `sql_log_chest_activity()`
   record open, failed verification, and close with no item text.
   `sql_player.c:2114-2125` queues the insert; callers ignore its result.
   `locker_logcmd()` at 4386-4427 reads 50 records and checks permission only
   before its asynchronous read. Its name join loses the display name after
   deletion, but the log's numeric locker/chest identities remain stored.

5. Creation at `storage_lockers.c:4051-4148` commits the new row on the writer
   before its actor-bound callback charges money. `sql_async.c:265-281` drops
   that callback if the character no longer exists. Payment failure queues an
   unchecked compensating delete. The callback does not recheck management
   authorization before charging. Password removal/replacement and deletion at
   4191-4265 mutate memory and report success without inspecting durable results.
   Name lookup is case-insensitive, but input is not checked against the SQL
   `chest_name varchar(32)` before insertion; add only the validation this real
   representation and unambiguous command targeting require.

6. The currency facade is not a durable purchase receipt.
   `src/economy/currency_transaction.c:143-218` changes memory and calls its
   completion immediately; bank deltas queue separately. Its bank-payment
   calculation at 54-88 can return denomination change to the wallet. Preserve
   that detail and the existing whole-wallet-else-whole-bank choice; do not
   silently combine a short wallet and short bank. Existing durable command
   infrastructure supplies an inbox, operation IDs, transaction/replay handling,
   and completion publication (`critical_command_repository.c:727-772`,
   1136-1168). Divine trade demonstrates joint wallet/domain persistence and
   save reservations; its cargo-specific payload cannot simply be used for a chest.

7. Flat-file support is intentionally public-only in gameplay:
   `storage_lockers.c:2891-2958` explicitly says private chests are MariaDB's,
   and materialization at 3113-3136 expects SQL private-chest rows.
   `flatfile_locker_repository.h:27-55` nevertheless represents private chests
   and their saved contents. `flatfile_locker_prepare_public_save()` at
   `flatfile_locker_repository.c:683-755` updates only the public record in the
   loaded catalog. SQL reads refuse without a DB; no-MySQL save/log stubs return
   false. Backend availability needs a deliberate contract, not a claim that
   flat-file cannot serialize private data or has already deleted it.

8. Private content saves already use the one writer and owner
   `{locker, locker_id, chest_id}` (`sql_player.c:2127-2149`,
   `player_snapshot_repository.c:1337-1362`). However, their bool reports only
   admission; they lack the per-locker completion delivery used for public saves
   in `persistence/locker_async.c:263-298`. Private durability must participate
   in terminal cleanup. The constructor/sort/load path and metadata handling
   should be repaired without replacing the established ownership authority.

The room advertises the full command set at `storage_lockers.c:3225-3236`.
The maintained `CHEST / EQ CHEST / CHEST CREATE` help entry in
`lib/information/help_index` does not describe this implemented subcommand system.
The schema already accommodates bcrypt's 60-byte encoding; a password column
widening is unnecessary (`migrations/bootstrap_multithread_safe.sql:1324-1348`).

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

## Non-goals and ablation

No production operations, migration against a live database, deployment, wipe,
new authentication service, general container ACL framework, configurable chest
limits/prices/capacities, creator/rank permissions, flat-file gameplay parity,
or repository-wide cleanup. No unrelated locker entry, guild, cargo, currency,
privacy, or terminal-departure policy change belongs in this branch.

Ablation keeps the existing wrapper list, selection, password worker, item
movement bodies, ownership snapshots, writer, and durable command coordinator.
One small chest access predicate has real inspection/movement consumers; it is
not a new permissions layer. A new private-chest command payload is justified
by the existing create/payment split and durable activity/management outcomes;
reuse the current inbox/journal instead of adding a receipt service or table.
The wallet/bank reservation work below serves a real second payment consumer.
Do not broaden cargo-specific types merely to avoid writing a few chest fields.

Flat-file gameplay parity is dropped because the issue explicitly allows honest
unsupported-backend rejection and the owning loader already declares this
boundary. Data preservation and the unsupported-mode journey remain mandatory.
Capacity uses the existing unlimited sentinel instead of an invented limit.
Log rendering uses stable stored numeric IDs after deletion, avoiding a new
historical-name column. No password schema migration or rewrite is justified.
Do not add a migration unless implementation proves existing durable storage
cannot express a required invariant; any such change must be additive, guarded,
re-runnable, and update this plan and the repository's migration contracts.

## Files and implementation sequence

Only this plan and its preserved predecessor change during planning.
Expected implementation touch points are listed with their concrete purpose:

- `src/item/storage_lockers.c` and `.h`: policy, selection/invalidation,
  management publication, backend messages, activity handoff and room help.
- `src/cmd/actobj.c`, `src/cmd/actinf.c`: content gates and successful movement
  hooks at the real single/bulk/empty/coin boundaries.
- `src/sql/sql_player.c` and `.h`, `src/player/player_snapshot_repository.c`
  and `.h`, `src/persistence/locker_async.c` and `.h`: private save receipts,
  error propagation and cleanup fencing, reusing existing snapshot application.
- A focused `src/item/private_chest_command.c` and `.h`: the concrete immutable
  command codec/result and SQL executor for creation, metadata changes and
  activity records; keep runtime ownership in the locker code. Split this file
  only if the current build boundaries actually require it.
- Existing critical command validation/dispatch/completion files, `src/Makefile`,
  and currency/player save reservation code: register that command and prevent
  a pending purchase or later save from undoing/double-applying its payment.
  Touch the snapshot codec only if required for payment recovery, preserving
  older save compatibility. Do not reuse a cargo trade marker as a chest marker.
- Existing locker/password/container/flat-file tests, one native private-chest
  lifecycle regression and one SQL command journey; relevant regression-runner
  registration, `lib/information/help_index`, and this plan's completion record.

### 1. Establish focused failing behavior before changing production

Extend `test_locker_container_weight_lifecycle.py` to instantiate the production
private constructor at multiple IDs and exercise both `put()` capacity handling
and `bulk_put_permitted()`. Reuse its production-body extraction and ASan/UBSan
stubs; do not recreate container arithmetic in a test.

Add `tests/async/test_private_chest_lifecycle.py` using actual locker management,
open/close, content gate and movement bodies. Control password-worker, writer
and completion timing at their existing boundaries. Demonstrate missing session
gating, missing item history, premature metadata success, and stale completions
with disposable identities. Keep cryptographic behavior in the existing password
suite. Negative controls must fail for the intended observable behavior on the
baseline; source-token assertions alone do not prove authorization.

### 2. Connect selection to inspection and all item boundaries

Resolve a private chest through its actual `StorageLocker::FindChestForObject()`
wrapper, never through a name, prototype number, or `value[0]`. Apply one shared
access decision before content enumeration and before transfer preflight. Trace
ancestor containers where the lookup permits nested content; an inner object
cannot bypass its private root. Ordinary containers pass through unchanged.

Cover single/numeric/all/all-filtered get and put, coin paths, empty with both
source and destination, look-in/examine, and the existing public sort path.
Check again after traps or delayed work that can change actor/object/session
identity. Close cannot leave an earlier selection or queued verification usable.
Use a small authorization generation only for actual in-flight invalidation;
do not build a general session map. Never authorize by generic container flags
alone, including transparent containers. Change the private capacity constructor
without changing the ordinary container weight rules.

### 3. Give management and payment a durable result

Use one domain-specific private-chest command on the existing critical command
coordinator/writer. Include operation ID, stable locker/chest identity, actor PID,
account/side where needed, expected state, and owned strings/hashes; no pointers
or plaintext passwords cross the thread boundary. Reuse the existing completion
and replay mechanism rather than actor-bound callbacks for persistent effects.

For creation, capture the complete wallet-else-bank payment including change,
reserve the affected purse/account-side bank and relevant save publication, and
admit the immutable operation. Adapt the existing economic/save reservation
pattern narrowly for this real consumer; block conflicting account-bank mutations
on other online characters until resolution too. Do not equate the currency
facade's immediate callback with COMMIT.

In one SQL transaction, lock/validate the locker, name, count and payment
preconditions, write the exact payment and new chest, and retain the result in
the existing operation inbox. Duplicate operation delivery returns the same
result without charging/inserting again. Duplicate names, a full locker,
insufficient funds, rejected submission or failed transaction produce neither
charge nor chest. Ambiguous commit uses the existing durable result resolution;
never retry as a new operation or rely on an unchecked compensating delete.

Only committed results publish new balances, synchronize the shared bank,
materialize a chest in a still-matching visit, and announce success. Resolve an
offline payer by durable identity/recovery; disconnect must not discard the
payment outcome, resurrect a stale wallet snapshot, or charge a new session.
Release reservations on final rejection or reconciliation, not on a timeout that
leaves the database outcome unknown. The committed chest is found on next entry
if its original room no longer exists. Allocation failure in materialization
must leave the stored paid chest available for re-entry, not repeat the purchase.

For password replacement/removal and deletion, invalidate access when admitted,
serialize conflicting operations, check expected chest/password state, and
publish metadata/removal and final success only after the committed result.
Reject nonempty or unavailable deletion and wait for older chest snapshots
before removal. A failed write retains the prior hash/chest; re-opening is
required after invalidation. A legacy rehash uses compare-and-swap against the
verified credential and cannot replace a newer password. Re-resolve all live
objects by identity when publishing; a freed/reused room is not the old visit.

### 4. Record successful movement and wait for private saves

At the confirmed movement boundary, capture actual actor, locker/chest IDs,
action, item description plus UID/vnum, and actual moved amount for coins.
Reserve bounded event context before mutation; if that reservation fails, reject
the candidate before moving it. Submit reserved context only after an actual
success; a refused writer submission retains the event for retry. Reserve per root,
not one misleading entry for an entire attempted bulk command. Moving a bag
records that root and keeps its nested identity intact. Empty records source
GET and target PUT where applicable. Moves within the same private root are
internal rearrangements; crossing private roots produces the appropriate two
records. Automatic sort/load/save is not a player deposit/withdrawal.

Submit successful events through the same domain command's activity action so
its operation inbox prevents duplicate records on retry. Do not emit success
for authorization, capacity, cursed-item, trap or other rejected candidates.
Preserve earlier successful entries when a later bulk candidate fails. Handle
coin piles before extraction/merging destroys their description; record the
actual amount moved. Keep passwords and hashes out of all event payloads/output.
Keep the relevant locker busy until admitted events are acknowledged; retain
pending evidence through writer rejection/retry instead of silently dropping it.
Revalidate log-view permission and visit on asynchronous read completion. Order
latest-50 deterministically and show numeric IDs when the chest has been deleted.

Extend the existing private snapshot submission to report final writer results
into the locker lifecycle. All private saves, activity and management results
must settle before a terminal public-save acknowledgement can release the room
or allow a conflicting re-entry. Retryable/ambiguous results preserve the work;
terminal failures retain recoverable state and report the real failure. Reuse
public locker result handling; do not add a second save worker. Preserve owner
`{locker, locker_id, chest_id}`, nested UIDs, and sort isolation.

### 5. Match help and finish complete local qualification

Document supported backends, manager/guest/guild semantics, explicit open/close,
capacity, syntax, cost/funding/change, limit, passwords, logging, empty-only delete
and persistence outcomes in chest/locker help and room instructions. Retain the
distinction between `eq chest create` and a nonexistent standalone command.

Use `tests/async/test_mysql_private_chest_journey.py` (new) with the existing
`test_mysql_locker_grant_journey.py` fixture/bootstrap/socket patterns and
`with_disposable_mariadb.sh`. Extend `test_flatfile_locker_journey.py` for clear
unsupported-mode behavior and public-storage compatibility. Seed private flat
records through the existing repository fixture and prove they are unchanged
after public saves and a cold restart. Never use real player inventories.
Register expensive journeys in the existing resource-intensive test list.

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

Commands after implementation (new test filenames above are planned):

    python3 tests/async/test_private_chest_lifecycle.py
    python3 tests/async/test_private_chest_password_hardening.py
    python3 tests/async/test_locker_container_weight_lifecycle.py
    python3 tests/async/test_locker_ownership_cutover.py
    python3 tests/async/test_flatfile_locker_repository.py
    python3 tests/async/test_locker_named_entry_runtime.py
    python3 tests/async/test_locker_async_pipeline.py
    python3 tests/async/test_locker_result_failures.py
    python3 tests/async/test_locker_leave_during_save.py
    python3 tests/async/test_sql_async.py
    make -C src
    tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_private_chest_journey.py
    TEST_DB_IMAGE=mysql:8.0 tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_private_chest_journey.py
    tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_locker_grant_journey.py
    python3 tests/async/test_flatfile_locker_journey.py
    ./scripts/format.sh --check
    python3 tests/async/test_documentation_contract.py
    git diff --check

The flat-file journey already builds a no-MySQL server through existing helpers;
keep all build artifacts under `bin/`. Also run the focused command codec,
critical replay, currency/reservation and snapshot compatibility checks affected
by the implementation, using existing tests. Record exact commands at that step.
Inspect local/dev environment before booting; use synthetic run roots and the
disposable SQL wrapper, which never sources the checkout's `.env`. Do not require
hosted CI, full burn-in, production reproduction, or a deployment for completion.

## Estimate and tracking

Estimate for me: **12-18 hours of active implementation and qualification** for
this complete SQL-supported contract. Rough allocation: 2-3 hours for focused
regressions/access/capacity; 4-6 hours for durable creation/payment, management
and lifecycle integration; 2-3 hours for audit/save acknowledgements; 4-6 hours
for engine/backend journeys, help, required builds and final review. Allow up to
24 hours if payment reservation/recovery compatibility requires more work than
the existing durable domain patterns support. These are my working-time estimates,
not elapsed waiting time, another developer's estimate, or implementation already
performed. External review, changed product policy, full flat-file private-chest
parity, merge waiting and deployment are outside this estimate.

Issue #490 is the single work item. GitHub's Development association links this
branch to #490; the handling comment and final plan link provide the handoff.
Use a planning-only commit referencing #490 without a closing keyword. Do not
close the issue, open an implementation PR, merge or deploy at the planning stage.

## Planning validation and limits

On this isolated baseline, independently rerun and passed:

- `python3 tests/async/test_private_chest_password_hardening.py`: hashing worker,
  bounded/cancelled login jobs, legacy handling, stale hash and source contracts.
- `python3 tests/async/test_locker_container_weight_lifecycle.py`: all 22 existing
  cases under ASan/UBSan, covering sorting/loading/weights/movement predicates.
- `python3 tests/async/test_locker_ownership_cutover.py`: all six contract tests.
- `python3 tests/async/test_flatfile_locker_repository.py`: repository harness.

These do not prove the unimplemented access policy, full management journey,
activity logging or durable payment result. No maintained C/C++ code changed;
no full server build, new runtime reproduction, database migration, or production
operation is claimed. The original checkout's quest-documentation work and all
other worktrees are preserved. Additional planning checks passed:

- `python3 tests/async/test_documentation_contract.py`: all 14 tests.
- `git diff --check`: no whitespace errors.
- The archived #420 record exactly matches the baseline shared plan bytes and
  SHA-256 given above.
- GitHub assignment, handling comment, and the native Development branch link
  were verified. The final issue handoff records the published commit and plan;
  post-push checks must confirm matching local/remote heads and a clean worktree.


## Implementation progress, 2026-10-30

Integrated remote master `40a6a7bc0` (22 commits since the planning baseline)
without conflicts before implementation. The shared #490 plan and preserved #420
record remain intact. No local `.env` is present in this isolated worktree;
runtime qualification will use synthetic configuration and disposable state.

The first independent delivery is the capacity foundation on
`branch/issue-490-private-chests`, targeting master. It changes only the private
constructor's capacity to the existing unlimited locker sentinel and retains
`m_chestId` as the persistent identity. `USE_SPACE` is explicitly disabled in
`actobj.c`; no speculative space-policy code is added.

The extended existing native regression compiles the real private constructor,
ordinary `put()`, bulk predicate, and object/weight code. Its new single and bulk
cases both fail on the unmodified constructor at the actual admission assertions.
The fixture crosses IDs 10, 100 and 1000000 with sequential weights 20, 200 and
2000, verifies transfer/weight accounting, and retains finite ordinary-container
rejection controls. World/prototype/log/trap services remain controlled fixture
boundaries; this does not claim the full socket command journey.

Ablation for this chunk keeps one local constructor fix and extends the existing
harness. No capacity helper, header, migration or configuration is needed. The
access, backend, audit, management/payment, save-result and full journey work
remain required; passing this chunk does not complete #490. Capacity-foundation validation passed:

- `python3 tests/async/test_locker_container_weight_lifecycle.py`: all 24 cases
  under ASan/UBSan, including both new regressions and all 22 existing cases.
- `make -C src -j6`: complete MariaDB development build, warnings as errors.
- `bash scripts/format.sh --check`: passed.
- Staged clang-tidy uses the installed Clang-Tidy 22 via
  `CLANG_TIDY=/home/aiwithapex/.local/bin/clang-tidy`. The system default 18
  cannot parse the GCC 16 headers it selects; no hook is bypassed.
- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `git diff --check`: passed.

The two new cases were first observed failing against the unchanged constructor
and then passing after the fix. No socket/restart/backend-parity qualification is
claimed for this isolated capacity PR. The next chunk is access/session/backend
policy, followed by durable management/payment/audit/save integration and full
command qualification. Its dependent PR will be based on this foundation rather
than waiting to publish the entire issue at once. The first review-ready chunk is [PR #497](https://github.com/LuminariMUD/Duris/pull/497),
head `branch/issue-490-private-chests`, base `master`. Commit `e41c1b2e0` contains
the capacity fix. The PR is open, non-draft and mergeable; it references #490
without closing it. Later master commits only change unrelated population and
regression fixtures, so the capacity/build evidence remains applicable.
