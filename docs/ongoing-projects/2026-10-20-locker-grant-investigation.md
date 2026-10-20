# Qua / Zyx locker grant investigation

Issue: [#234 - Fix named locker entry rejecting valid account-locker grants](https://github.com/LuminariMUD/Duris/issues/234)

Work branch: [`branch/issue-234-locker-grant-entry`](https://github.com/LuminariMUD/Duris/tree/branch/issue-234-locker-grant-entry)

Status: Implemented and locally verified; PR review and production acceptance pending.

## Implementation decisions

Bare character names resolve through the active, unblocked account-character
mapping to the owner's account locker and racewar side. This takes precedence over
a coexisting legacy personal locker. Full `<character>.locker` names explicitly
select legacy lockers; canonical account and guild names accept the final suffix
with no duplicate `.locker`. Without an active mapping, a bare character name
retains the legacy personal target. No contents or grants are moved or rewritten.

Resolution runs on the existing persistence worker before normal locker entry,
so occupancy and pending saves use the resolved identity. Named owner entry keeps
account ownership; visitors still need the selected locker's grants and racewar
side. Authorization precedes every occupied/pending-save response.

Scope: locker entry, LOCKER/GRANT help, focused executable regressions, and a
disposable MariaDB mortal gameplay journey covering the acceptance checks below.
No schema change or production operation is needed. Historical findings below
describe the pre-fix checkout.

## Implementation and local validation (2026-10-20)

The real gameplay check also reproduced an existing occupancy defect: locker
characters stay in holding room 65201, while their `StorageLocker` wrappers live
in the private rooms. Looking for a wrapper in the character's holding room
classified an occupied locker as stale and loaded a second copy. Busy detection
and occupant lookup now search the bounded private locker rooms. Authorization
runs before every busy response, including in-flight entries and deferred saves,
and opposite-side grants fail before occupant disclosure.

Both maintained LOCKER/GRANT help sources explain the supported forms. The new
MariaDB journey is registered in `tests/run_db_tests.sh` and excluded from the
ordinary runner that has no disposable database.

Passed:

```sh
make -C src -j2
make -C src -j2 PERSISTENCE_BACKEND=flatfile \
  DMS_BINARY="$PWD/bin/server/dms_issue234_flatfile"
python3 tests/async/test_locker_named_entry_runtime.py
tests/async/with_disposable_mariadb.sh \
  python3 tests/async/test_mysql_locker_grant_journey.py
```

- The ASan/UBSan executable regression covers holding/private-room occupancy,
  pending saves and entries, delayed name resolution, legacy fallback,
  move-away/worker admission failure, owner/visitor grants and racewar verdicts.
- The full-world MariaDB journey uses three level-20 mortal characters with
  different character/account names. It proves grant -> leave -> mixed-case
  named entry, account-first precedence, separate legacy contents/grants,
  canonical targeting with/without the suffix, owner entry, character/account
  grants and revocation, unauthorized entry, occupancy privacy, a real inn
  logout/reconnect, and a clean server restart. Post-restart opposite-side checks
  use a neutral Ixarkon counter, so town admission cannot mask locker checks.
  All seven journey stages passed. All three stored item UIDs and both lockers'
  grants survived restart unchanged; account-grant revocation still denied entry.
- Journey evidence: `bin/analysis/issue-234/journey.json` (generated, untracked).
  Tested MariaDB binary SHA-256:
  `c2f438692df517d474c88d107430d0f3331722ca06d9388fddb9664480f2f66b`.
- The existing flat-file locker journey also passed using
  `bin/server/dms_issue234_flatfile` and a freshly built coin/death inspector.
  It preserved account contents through restart/retrieval and guild contents
  through re-entry. Re-run after building the flat-file executable above:

  ```sh
  python3 tests/async/test_flatfile_player_repository.py \
    --build-inspector bin/tests/coin-death-inspector
  PYTHONPATH=tests/async python3 -c 'from pathlib import Path; from test_flatfile_locker_journey import run; run(Path("bin/server/dms_issue234_flatfile").resolve())'
  ```

- Relevant existing locker result, ownership, boot-room, async pipeline,
  leave-during-save, saved-with-occupant, container-weight, terminal fallback,
  worker lifecycle, legacy repair and save-room regressions passed. The
  save-room fixture initially lacked the new short-affect capture link hooks
  from master; separate commit `125239fbf` restores its empty fixture hooks.
- Root-runner, help import/parser, flat-file help and 14 documentation checks
  passed. The help-import atomic suite passed its three local tests and skipped
  five optional database cases; the actual help import and rendered LOCKER/GRANT
  help were exercised by the disposable gameplay journey.

The full repository suite was not run. Review/merge, deployment and live Qua/Zyx
acceptance remain pending; this work performed no production operation.

## Original investigation (pre-fix)

Investigated on 2026-10-20 UTC against checkout
`fcb54a1d068015f7ab3887944ba8929208568c0d`, using read-only production SQL,
local logs, source inspection, and an isolated executable routing probe.
The running process started on October 19 at 17:30:50 UTC and reports
`ENVIRONMENT=production`, `PERSISTENCE_MODE=mariadb-primary`. The revision
identifies the inspected checkout; the process's exact build revision was
not independently established.

**Zyx's grant exists. The confirmed defect is that documented named entry
targets a different locker from the owner's default account locker.**
`enter locker qua` looks for `qua.locker`, which does not exist, while Qua's
default locker and Zyx's saved grant use `account.qua.1.locker`.

This is a strong explanation for the report, conditional on Zyx having used
the documented character-name command. The exact attempted command and
response were not supplied or recovered from the inspected logs. Successful
entry by Zyx was not exercised on the live server.

## Production evidence

Read-only snapshots at **12:30:45 and 12:33:06 UTC** established:

| Check | Observed result |
| --- | --- |
| Qua's account locker | `account.qua.1.locker` exists, racewar side `1` |
| Qua's legacy personal locker | No `qua.locker` row |
| Saved visitor grant | `(owner='account.qua.1.locker', visitor='zyx')` |
| Grant count on Qua's account locker | One |
| Runtime's direct grant predicate for Zyx on that account locker | Returns `1` |
| Qua and Zyx's persisted racewar sides | Both `1`, in both `player_data` and `account_characters` |
| Their account-character mappings | Active and unblocked |

The direct character grant is sufficient; Zyx does not need an additional
account-level grant. Capitalization is not the problem: the grant predicate
uses `LOWER(visitor)=LOWER(name)`.

`logs/log/debug`, lines 608–624 at inspection, also records Qua saving and
leaving `account.qua.1.locker` between **10:51:24 and 10:55:31 UTC** on
October 20. This corroborates which locker Qua was using. These entries
record queued saves, not the text or timestamp of a successful grant command.
The saved grant's presence is established by SQL.

No matching locker/grant events were returned from `log_entries` for Qua or
Zyx from October 18 onward, and no Zyx locker attempt appeared in the inspected
current locker logs. This does not establish that no attempt occurred.
Neither the schema's grant row nor these logs establishes when the grant was
added or whether it existed at the precise time of the reported failure.

## Confirmed code path

The relevant functions are in
[storage_lockers.c](../../src/item/storage_lockers.c):

1. **Default entry selects the account locker.**
   `storage_locker_room_hook()` uses the entrant's lowercased account name and
   racewar side when no owner argument is supplied, producing
   `account.<account>.<side>.locker`.
2. **Named entry does not resolve a character to their account.**
   For an ordinary explicit argument, the same function sets `bValidate=1`
   and appends `.locker` directly. Thus `enter locker qua` selects
   `qua.locker`; there is no fallback to Qua's account locker.
3. **Grants belong to the current locker's exact identity.**
   `locker_access_add()` inserts `GET_NAME(locker)` as `locker_access.owner`.
   A grant added inside Qua's default locker therefore belongs to
   `account.qua.1.locker`. `locker_access_show()` lists that same identity.
4. **Entry looks up that exact identity before consulting its grants.**
   `locker_enter()` submits a `locker_entry` with the selected name.
   `locker_entry_read()` searches `lockers.locker_name`; for a missing named
   locker it returns access false and does not create a replacement.
   `load_locker_char()` then sends
   `You don't have access to that locker!`.
5. **The account locker would pass this grant check.**
   For `account.qua.1.locker`, `locker_granted()` finds the persisted direct
   grant to Zyx. The separately enforced racewar check also matches the
   inspected persisted state. Other entry conditions, including occupancy,
   still apply.

The checked-in [LOCKER help](../../lib/information/help_index), around line
9552, tells visitors to use `enter locker char_name`. Its documented command
therefore leads directly into this mismatch for an account locker. The
in-locker grant help accepts character or account names, but that describes
the **visitor**, not how to address the locker on entry.

## Workaround and diagnostic distinction

For this saved grant, Zyx can address the correct locker explicitly:

```text
enter locker account.qua.1
```

Use this at a locker counter after Qua has left and its save has completed.
Do **not** append `.locker`: the command already appends it. This form keeps
normal grant and racewar validation enabled. It is supported by the routing
probe and live read-only access predicate, but has not been verified through
a live Zyx gameplay session.

Adding the same grant again, restarting, or changing capitalization does not
correct the named-entry target. The evidence does not justify rewriting
locker ownership or running the legacy personal-locker repair: that repair
requires an existing player-owned locker, whereas this report concerns an
account locker and an already-present visitor grant.

If explicit account entry still fails, retain the exact response:

- `You don't have access to that locker!` warrants rechecking the target
  identity and current grant.
- `... is currently using that locker. Please try later.` is an occupancy
  restriction, even for an authorized visitor.
- `Slow your roll...` indicates the deferred-save branch.
- `The locker could not be opened right now...` indicates an entry-read or
  materialization failure rather than the ordinary missing-grant verdict.

These are distinct code paths; the original report did not identify which
message Zyx saw.

## Verification and reproduction

An isolated C++ probe compiled the actual
`argument_interpreter()` and `storage_locker_room_hook()` bodies from this
checkout. World eligibility, account lookup, and the downstream entry service
were fixture stubs; the latter captured the target and validation flag.
All five assertions passed under ASan/UBSan:

| Input after `enter` | Selected identity | Access validation requested |
| --- | --- | --- |
| `locker` as Qua | `account.qua.1.locker` | No, default owner entry |
| `locker qua` as a visitor | `qua.locker` | Yes |
| `locker QuA` as a visitor | `qua.locker` | Yes |
| `locker account.qua.1` as a visitor | `account.qua.1.locker` | Yes |
| `locker account.qua.1.locker` as a visitor | `account.qua.1.locker.locker` | Yes |

The scratch driver is `/tmp/duris-locker-grant-routing-probe.py`; generated
source and executable are under
`bin/tests/locker-grant-investigation-20261020/`. Re-run from the repository:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=tests/async \
  python3 /tmp/duris-locker-grant-routing-probe.py
```

These scratch files are local investigation artifacts, not durable regression
coverage. The probe proves command routing, not a complete login, SQL writer,
or item-loading journey.

The existing source-contract checks also passed:

```sh
python3 tests/async/test_locker_result_failures.py
python3 tests/async/test_legacy_personal_locker_access_repair.py
```

They cover authorization/error-handling contracts and the separate legacy
repair's safeguards. They do not test successful visitor entry into an
account locker through a character name.

The central database finding can be rechecked with the configured client in
a read-only transaction:

```sql
START TRANSACTION READ ONLY;
SELECT UTC_TIMESTAMP();
SELECT locker_name, racewar
FROM lockers
WHERE locker_name IN ('qua.locker', 'account.qua.1.locker');
SELECT owner, visitor
FROM locker_access
WHERE owner IN ('qua.locker', 'account.qua.1.locker')
  AND LOWER(visitor) = LOWER('Zyx');
SELECT 1
FROM locker_access
WHERE owner = 'account.qua.1.locker'
  AND LOWER(visitor) = LOWER('Zyx')
LIMIT 1;
ROLLBACK;
```

Expected from the inspected snapshots: one account-locker row on side `1`,
one direct grant to `zyx`, and `1` from the runtime's direct grant predicate.
There is no personal-locker row.

## Original repair requirements

Resolve the documented character-name entry to the intended account locker
before the existing grant check. Define precedence when a legacy personal
locker also exists, preserving access to its separate contents and grants.
Keep explicit canonical targeting available, retain racewar and occupancy
checks, and update help to explain the supported forms.

Add a gameplay regression with two ordinary, same-side characters: the
owner enters their default locker, grants the visitor, leaves, and the
visitor enters by the owner's character name. Verify the intended locker
identity and contents, then repeat after reconnect/restart. Include mixed
case, an owner whose character name differs from their account name,
character and account visitor grants, revocation, an ungranted visitor,
opposite-side entry, occupancy privacy, and coexistence with a legacy
personal locker. Staff entry alone is insufficient because it bypasses grant
validation.

The initial investigation made no runtime fix, production data change, migration,
restart, or player login. The branch now implements the repair and records its
local validation above; production deployment and live acceptance remain separate.
