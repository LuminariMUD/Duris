# October 30 core: locker callbacks outlive the visit

The immediate crash was already prevented by the room guard in `b737db202`
(#497). This investigation additionally fixes delayed work acting on a different
locker visit. The implementation is in the worktree; no production operation
was performed.

## Artifact identity

- Core: `core.2026.10.30-18.50.39`, 2,311,249,920 bytes, modification time
  October 30 at 18:50:28 UTC. The cycle script's filename is the later archival
  time, not the exact fault time.
- Command: `bin/server/dms 7777`; faulting LWP: 647555; signal: SIGSEGV;
  fault address: `0xba`.
- Matching executable:
  `/home/staging/deploy-recovery/20261031-95179c4a8/dms.previous`.
- GNU build ID: `47170539adabaac293c289eadb0cb8b99d2aa560`, read from both
  the core's embedded executable note and the backup executable.
- Executable SHA-256:
  `14c919aaffe4962e57a8b8b761853727b31c0c03f6360ddbba813b97caddf239`.
  The October 30 deployment receipt associates this hash with release
  `b9de5047732df100ae4892df55be4f58b6fe4fc3`.

The current `bin/server/dms` and `dms_new` have different build IDs. All core
symbolization used the matching backup. GDB still warns about the current file
at the core's original executable path; the supplied symbol file matches.
Source line numbers in the dump refer to the older build, not the current file.

## Direct evidence and cause

The main thread is in:

```text
StorageLocker::event_resortLocker  item/storage_lockers.c:2296
ne_events                         world/new_events.c:1677
run_event_phase / game_loop        net/comm.c
```

The failing instruction loads `pLocker->m_itemCount` through `rbp == 0xba`.
The player is in room index 76821, VNUM 132508, **Tharnadian Bank**. That room
does not have `ROOM_LOCKER`. Its second extra-description keyword is
`"bar bars cell"`. `GetChestList()` reads that field using `sscanf("%p")`;
the initial hexadecimal characters `ba` parse successfully as pointer `0xba`.
The old `locker_current()` checked only whether the character was null.

This is a stale room-context lookup. Both characters are still live: the event's
owner and victim runtime IDs match the locker holder (76104) and player (76102).
The event has no payload, due tick 51693, sequence 58419622, and no deferrals.
The player's last-room field is locker VNUM 65202; the temporary locker holder
remains in holding room index 40531. The locker slot is terminal, `LCHK_DIRTY`,
generation 21, ready to capture the departed visit. The crash happens before
that capture, while an earlier nonterminal save's refresh is dispatched.

The archived debug log records a nonterminal save at 18:50:27, followed by
departure and terminal generation 21 in the same second. The last command in
`cmd.debug` belongs to another player issuing `list`; it is incidental to the
event-phase failure. The twelve other threads are waiting in ordinary logging,
password, persistence, Redis, maintenance, collector and telemetry worker loops.
Their stacks reveal no additional initiating fault. The core does not establish
whether the last visit's items required any durable data recovery.

## Existing fix and remaining defects

`b737db202` rejects invalid room indexes and rooms without `ROOM_LOCKER` before
calling `GetChestList()`. That prevents the observed bank crash in current code.

The remaining callbacks still selected a locker using only the player's current
room:

1. A refresh queued for locker A could sort locker B after the player changed
   visits. It did not verify its `chLocker` argument or the authenticated occupant.
2. An old terminal snapshot could call `LockerToPFile()` on locker B before
   capturing holder A. Because terminal captures do not restore the visible
   chests, this could leave B's items hidden on its holder until another rebuild.
3. Snapshot restoration similarly lacked the expected holder identity, and
   worker completion could queue a refresh after departure.

The existing callback helpers now receive/check the expected holder and use
`LockerUserMatches()` for the occupant's pointer and runtime identity. Sorting
checks again at dispatch, since a player can move after scheduling. Stale work
returns silently. A departed visit's snapshot preparation succeeds without
touching another room: departure already put its items on its own holder, and
its terminal capture must still finish.

## Verification

`python3 tests/async/test_locker_callback_visit.py` compiles the production
callbacks, constructor and guarded room lookup with the real locker writer state
machine under ASan/UBSan. Controlled event dispatch, inventory
movement and persistence boundaries exercise the bank keyword, invalid rooms,
null players, delayed dispatch/completion, a different holder, a guest, reused
player identity, normal automatic/explicit sorting, failed preparation, and
terminal capture after entry into another locker. Assertions check both saved
item identities and unchanged contents in the second room.

Three local negative controls fail as expected: restoring the original room
lookup reaches pointer `0xba`; removing the sort visit check or preparation
visit check fails the stale-work assertions. The existing idle lifecycle,
leave-during-save, async pipeline, occupant-save and terminal-fallback
regressions pass.

`make -C src -j2`, the repository formatting check, and whitespace validation
pass. `python3 tests/async/test_flatfile_locker_journey.py` also passes against a
real local server: account-locker contents survive restart, an item taken back
stays with the player across another restart, and a guild-locker item survives
leave/re-entry after the async save lands.

Unrelated validation constraints remain. A disposable MariaDB journey could
not boot its fresh fixture because shared frag-cap authority was unavailable,
before any locker path ran. The documentation contract reports the same 13
links to absent `docs/records` files with or without this report. LeakSanitizer
also cannot run under the current ptraced sandbox; the callback harness keeps
ASan/UBSan enabled with leak scanning disabled, and the existing room-departure
test passes under the same setting.

Local GDB captures, negative-control output and build evidence are under ignored
`bin/analysis/core-2026-10-30/`. The core and archived logs remain untouched.
