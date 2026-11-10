# Issue #992: independently open private locker chests

Status: implementation in progress on `branch/issue-992-multiple-open-chests-plan`.
Date: 2026-11-10.
Issue: [#992](https://github.com/LuminariMUD/Duris/issues/992).
Source inspected: `master` at `46468abbec508fd26c358535502e62b5590552ab`.

## Outcome and scope

A visitor can keep all five created private chests open after individually
opening each one. Looking in, getting, putting, and emptying any authorized
chest continues to work after opening another. A failed open does not remove
existing access. `close <name>` closes one private chest; bare `close` closes
all open private chests for this visit.

Implement this in the existing locker access state and commands, extend the
existing executable tests and MariaDB journey, and update player help. Reuse
the shared container-access predicate so ordinary, bulk, nested-container,
and coin operations all receive the same rule.

Keep the five-chest limit, prices, capacity, names, stored chest IDs, item
custody, permissions, and persistence policy. No database migration, bulk-open
command, persistent open state, new authorization framework, parallel password
worker support, or unrelated locker cleanup is needed. Production deployment
is a separate task. MariaDB is the only supported persistence backend.

## Verified baseline and constraints

- [storage_lockers.h](../../src/item/storage_lockers.h) stores one current
  chest ID and one manager flag. `InvalidateChestAccess()` clears both and
  advances a generation used by delayed open and management callbacks.
- [storage_lockers.c](../../src/item/storage_lockers.c) uses that ID in
  `locker_container_access_allowed()`. `locker_opencmd()` invalidates access
  before verification and selects one ID after successful audit admission.
  `locker_closecmd()` operates on the selection. Opening `public` also clears
  it. The room instructions and [chest help](../../lib/information/help_index)
  explicitly describe the current single-chest behavior.
- Private access is tied to the active visitor's runtime identity, descriptor,
  room, and write-pending state. A manager-derived authorization also rechecks
  the existing owner/staff/guild predicate when used.
- [password_async.c](../../src/account/password_async.c) allows one pending
  password request per descriptor and checks session identity before invoking
  its callback. Multiple completed chest authorizations do not require multiple
  pending password requests.
- Metadata changes call `SetChestWritePending()` at submission and resolution;
  it currently revokes all chest access. Removal, departure, and disconnect
  also invalidate access. Retain these established boundaries in this change.
- `m_chestsOpenedThisVisit` is historical bookkeeping for `ReturnNorentItems()`.
  It intentionally survives closing a chest. It must not become the set of
  currently authorized chests or be cleared by ordinary close/invalidation.
- [test_private_chest_lifecycle.py](../../tests/async/test_private_chest_lifecycle.py)
  currently expects opening a second chest to deny access to the first.
  The investigation ran its 29 cases successfully under ASan/UBSan against
  exported master `6c3d9213da8b7a0fb856bf46ed78e5111b76969a`. That is baseline
  evidence, not validation of the future implementation or this newer revision.

## Behavior decisions

1. **Open independently.** A successful private open adds or refreshes only
   that chest's authorization after the existing credential/manager checks and
   OPEN audit admission succeed. Record whether this authorization came from
   manager privileges. Preserve other open chests. Wrong/missing/overlength
   passwords, an unavailable service, rejected submissions, or rejected audit
   admission leave established authorizations unchanged, including when the
   attempted chest was already open. Repeated successful opens retain the
   existing OPEN logging behavior.
2. **Public storage.** Explicit `open public` retains its existing response and
   audit behavior but does not close private chests or create a private grant.
   Ordinary public access keeps its existing policy.
3. **Named close.** Recognize an exact private name through the existing
   case-insensitive lookup. Remove only that grant and prevent an older
   pending open from restoring access. A recognized but closed private chest
   reports that it is already closed and emits no successful CLOSE event.
   Ordinary targets such as `close door`, and unrecognized names, fall through
   without changing private authorization or request state.
4. **Bare close.** Snapshot the open chest IDs, revoke every current grant,
   and invalidate pending opens, including when no chest has finished opening.
   Then record CLOSE once for each grant removed. Report when nothing was open.
   Keep the existing single-chest success wording where applicable; use clear
   plural wording when several were closed.
5. **Close failures.** Revoke access before attempting CLOSE logging. If any
   audit submission fails, all requested grants still remain revoked and the
   response explicitly says that some activity could not be recorded. Do not
   report a completely recorded close or restore access to retry a log write.
6. **Lifecycle and management.** Departure/disconnect/replacement of a visit
   revoke all grants. Keep the existing locker-wide revocation and write
   barrier for password changes/removal and chest deletion; these management
   operations require reopening chests afterward. A rejected management
   submission before the existing invalidation point preserves its current
   behavior. Manager privilege loss must deny each manager-derived grant;
   password-derived grants retain their existing rules. Returning or
   restarting begins with all private chests closed.
7. **Delayed requests.** Preserve the existing newest-request generation
   semantics. A recognized new open, recognized private close, bare close, or
   global invalidation makes older delayed completions stale. This may cancel
   an unfinished open for another chest, but must not revoke an already
   completed authorization except under the explicit close/global rules.
   The existing one-request-per-descriptor busy behavior remains in effect.

## Implementation sequence

### 1. Establish the failing behavior tests

Extend the existing lifecycle harness first. Exercise the production command
and access functions, rather than a copied implementation. Demonstrate that
opening A then B should allow both, failed opening B should preserve A, and
closing A should leave B usable. These positive expectations must fail against
this baseline. Keep ordinary-door, identity, manager-role, credential-change,
and stale-callback cases as controls.

### 2. Replace the single selection in the existing locker class

In `src/item/storage_lockers.h` and `src/item/storage_lockers.c`:

- Replace the current ID/manager fields with a small ID-to-manager-flag map
  containing only currently open private chests. At most five entries are
  needed; no heap-allocated session objects or global registry are needed.
- Separate advancing the existing request generation from revoking completed
  grants. Opening another chest advances the generation without clearing the
  map; global invalidation clears the map and advances the generation.
  Keep management callbacks using the existing generation checks.
- Adapt the shared container-access predicate to find the target grant and
  check its own manager flag. Preserve every surrounding access check and
  the traversal from nested containers to their owning chest.
- Update open and close handlers to the decisions above. Keep locker/chest
  identity, object UID, credential-hash, and generation checks on callbacks;
  verify an old visit or a deleted/recreated same-name chest cannot inherit
  a completion. Never capture a raw chest pointer across delayed work.
- Preserve successful-open insertion into `m_chestsOpenedThisVisit`. Current
  authorization and historical no-rent bookkeeping must have separate duties.
- Replace obsolete single-selection getters/setters and fixture expectations;
  do not keep a second authoritative selection to satisfy old tests. Search
  all consumers before deleting the old API.

The existing access predicate already serves `actobj.c` and `actinf.c`.
Prefer leaving those callers unchanged. The descriptor invalidation hook in
`src/net/comm.c` should continue to revoke every grant through its existing
entry point. Preserve save barriers and item movement/audit machinery.

### 3. Update messages, help, and focused tests

Update the room command list and the CHEST help entry together: multiple open
chests, named close, bare close-all, and the existing management/lifecycle
revocation rules. Avoid suggesting that opening a chest unlocks it for other
visitors. Retain password secrecy in command logs and history.

Primary files beyond the two locker sources:

- `tests/async/test_private_chest_lifecycle.py`: independent grants, commands,
  failures, manager provenance, request generations, and lifecycle cases.
- `tests/async/private_chest_regressions.cpp`: adapt API consumers and extend
  production-backed management/audit checks where the lifecycle fixture is
  insufficient. Its runner is `test_private_chest_regressions.py`.
- `tests/async/test_locker_result_failures.py`: replace obsolete setter-name
  expectations while retaining the fail-closed ordering contract. Behavioral
  coverage belongs in the executable fixtures above.
- `tests/async/test_mysql_locker_grant_journey.py`: real owner/guest/guild
  command coverage, transfers, logs, and save/re-entry/restart assertions.
- `lib/information/help_index`: player-facing contract.

Use `test_private_chest_password_hardening.py`, the no-rent journey, and shared
locker fixtures as regression checks. Change their fixtures only where the
new API or behavior requires it; keep unrelated cleanup separate.

### 4. Qualify the complete behavior

Required executable cases:

- Open all five chests and use each; reopen one; attempt a failed sixth-name
  lookup; ensure both unknown targets and failed recognized opens preserve
  existing grants. Include protected and password-free guest chests.
- Close one of several, close an already-closed chest, close all, and close
  while a password result is pending. Check ordinary doors and public storage.
- Verify owner/staff/guild authorization, guest access to only authenticated
  chests, manager role revocation, and a mixture of manager- and
  password-derived grants. Opening one chest must not copy its privileges to
  another.
- Delay completions across a later open, named/bare close, password change,
  deletion/recreation, disconnect, and visit/runtime replacement. Preserve
  valid legacy password rehash behavior. Inject password-service and audit
  admission failures without losing other completed grants.
- Confirm each real OPEN/CLOSE/GET/PUT event has the correct chest and actor;
  close-all with partial log refusal still revokes all grants. Passwords stay
  out of audit text.
- In the MariaDB journey, perform look/examine, ordinary and bulk get/put,
  nested-container access, coins, and direct private-to-private `empty` while
  both chests are open. Close the source or destination and verify rejection
  leaves items unchanged. Confirm exact item UIDs, parentage, and chest IDs
  after save, re-entry, and cold restart; new visits require reopening.
- Verify no-rent return for a chest opened and later closed, alongside another
  open chest and a never-opened private chest. Closing does not erase the
  historical bookkeeping or turn it into permission for item commands.

Run focused checks from the implementation worktree:

```sh
python3 tests/async/test_private_chest_lifecycle.py
python3 tests/async/test_private_chest_regressions.py
python3 tests/async/test_private_chest_password_hardening.py
python3 tests/async/test_locker_result_failures.py
python3 tests/async/test_locker_container_weight_lifecycle.py
python3 tests/async/test_help_layout.py
./scripts/format.sh --check
make -C src
make world
```

Then run the real locker journey with the newly built binary and the existing
disposable MariaDB wrapper:

```sh
tests/async/with_disposable_mariadb.sh python3 tests/async/test_mysql_locker_grant_journey.py --server bin/server/dms_new
```

Qualify historical-open behavior with the existing no-rent journey:

```sh
tests/async/with_disposable_mariadb.sh python3 tests/async/test_norent_key_rent_journey.py --backend mariadb --server bin/server/dms_new
```

Run affected departure, shutdown, or item-command fixtures if implementation
changes touch their contracts or fixture dependencies. Keep build outputs and diagnostic
evidence under ignored `bin/`; use no production database or player accounts.
Do not require hosted CI or an unrelated full burn-in to finish this change.

## Review and completion

Review the final diff against every behavior decision and remove obsolete
selection state and unnecessary new machinery. Verify that ordinary open/close
operations mutate only intended grants, while global revocation still clears
all of them and rejects delayed completions. Check both current grants and
historical no-rent bookkeeping explicitly.

A completed implementation needs passing focused runtime tests, a successful
server build, the real MariaDB multi-chest journey, accurate help, formatting,
`git diff --check`, and the normal commit hooks. Record the tested commit and
binary identity with any limitations. If a relevant check cannot run, state
that gap and do not claim that behavior qualified. Submit the implementation
for normal review linked to #992; keep the issue open until the implementation
lands. This plan commit itself changes documentation only and does not claim
any feature implementation, merge, or deployment.

## Implementation handoff

- 2026-11-10: clean worktree confirmed at plan commit `1ad221ed1`; no existing PR.
  Extending lifecycle behavior coverage before replacing the single selection.
- Ablation: retain one request-generation counter and the existing password
  service. Completed grants need only an ID-to-manager-flag map. Keep global
  management revocation and historical no-rent tracking separate. No migration
  or new item-command layer is needed.
- Remaining: production access/commands, expanded failure coverage, help, real
  MariaDB and no-rent journeys, build/hooks, self-review, push and labeled PR.

- Core implementation and 48 ASan/UBSan lifecycle cases now pass. The original
  positive regressions failed on the baseline (`missing`, `overlength`, failed
  audit admission, and `select-other`) before the access-state change.
- The normal MariaDB server build, private-chest production/audit fixture,
  password suite, result contracts, container-weight cases, help layout, and
  formatting pass. Real locker/no-rent journey extensions are in progress.
- First real locker launch exposed absent generated world files in this fresh
  worktree. Add `make world` before journeys; this is a build prerequisite,
  not an implementation defect or a reason to change the server.

- Implementation checkpoint: code, help and focused fixtures are ready for
  review; full MariaDB qualification is still pending. The built server SHA-256
  is `aaa19b1ed4b5a75df1d22babb5bbe59d8ef34b634c9242626715015c497df518`.
  Added two filled private chests to the restart journey and per-chest
  OPEN/CLOSE audit checks. The first running journey predates the final
  test-only fixes; complete the final journey before marking the PR ready.
