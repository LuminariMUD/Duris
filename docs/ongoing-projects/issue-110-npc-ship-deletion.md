# Issue #110: NPC ship deletion and heartbeat recovery

Tracking: https://github.com/LuminariMUD/Duris/issues/110

## Current handoff (2026-10-16)

Implementation and focused regression pass on `branch/issue-110-npc-ship-deletion`, based on
`b149b3ada6e8c9c1e041ad864772195173fef7c6` (`origin/master` at start).
The checkout was clean and `.env` reports `ENVIRONMENT=local`.
No production deployment or restart is authorized by this task. Leave #110 open
until its separately authorized live validation is recorded.

## Outcome, non-goals, files, and proof

Outcome: NPC sinking, staff hull purge, and normal unload remove the runtime ship
once without attempting persistence. Preserve the 30-tick delay while a player
is aboard, and allow later ships' timers, repairs and movement to resume on
subsequent heartbeats. Failed player persistence and ownerless non-NPC state
must preserve the ship and its references for investigation.

Non-goals: iterator/sweep redesign, malformed-state recovery policy, ship string
ownership cleanup, deployment, restart, merge, or a release tag. A source fix
does not establish which commit is currently deployed.

Files: `src/ships/ship_base.c`, one focused executable regression under
`tests/async/`, and this handoff. Add other files only for demonstrated needs.

Proof: execute the production deletion, sinking, heartbeat, purge and unload
paths with the real ship hash and runtime identities under ASan/UBSan, for both
SQL and `__NO_MYSQL__` branches; demonstrate failures against the starting source.
Run related ship regressions, `./scripts/format.sh --all --check`, and
`make -C src` for MariaDB and flat-file backends. Record exact results below.

## Findings and ablation decisions

- Confirmed both faulty callers and the persistence-failure reinsertion on the
  current base. Keep the early return after `finish_sinking()`; advancing its
  freed hash visitor would be unsafe.
- Infer NPC identity from `race == NPCSHIP` inside `delete_ship`, and explicitly
  identify the known sinking caller. Keep the ownerless-player guard before
  persistence and teardown.
- Existing callers use `npc=true` to release failed loads and runtime ships
  after an owning transaction deletes persistence. Preserve that explicit
  bypass contract rather than replacing the flag with a race-only decision.
- The shared deletion boundary fixes staff purge without a duplicate check in
  `actwiz.c`. No new runtime abstraction or sweep refactor is needed.

## Work and evidence

- [x] Read #110, all deletion call sites, hash iteration and existing tests.
- [x] Add executable regression; capture failing-before results.
- [x] Implement deletion guards and sinking correction.
- [x] Verify both backends, cleanup, player safeguards and heartbeat recovery.
- [x] Run formatting, full server builds and relevant existing regressions.
- [ ] Review the final diff, commit, push and open a focused review-ready PR.
- [ ] Record exact remote parity and final continuation instructions.
- [ ] Separately authorized production deployment and live acceptance (pending;
  not part of this source-change PR).

### Verified evidence so far

- `python3 tests/async/test_npc_ship_deletion.py`: passes both backend builds
  under ASan/UBSan. Runs unmodified production `ship_activity`, `finish_sinking`,
  `delete_ship`, `do_purge`, `try_unload_npc_ship`, `pc_is_aboard`, ship hash,
  runtime identity, room/reference/autopilot cleanup, and `list_hulls` functions.
  External persistence and unrelated world mechanics are controlled stubs.
- The baseline failed SQL sinking, passenger disembark destruction, purge and
  ownerless guard cases; flat-file failed purge with a stale positive NPC ID and
  the ownerless guard. Ordinary flat-file NPC sinking already passed because
  its `db_id == 0` skips removal. Do not claim the ordinary flat-file case
  reproduced the SQL stall.
- After the fix: no NPC persistence calls, one free per removed ship, stale
  runtime references invalidated, other ships' target locks cleared, hull/panel
  extracted and interior returned. A player aboard delays destruction 30 ticks;
  disembarking permits removal at the next expiry.
- Later ships resume maintenance countdown, undocking, sail repair, coordinate
  movement and weapon reload. The real shipyard listing changes from 2.0 to
  1.9 hours after five subsequent ticks (the passenger scenario also checks its
  corresponding countdown). The intentional single skipped tick is preserved.
- Player persistence failures preserve hash membership, runtime identity,
  target references and interior objects; successful retry frees them. Null
  owner guards are covered with both positive and zero durable IDs.
- `./scripts/format.sh --check`: passed.
- `./scripts/format.sh --all --check`: all 1061 tracked C/C++ files passed.
- `make -C src -j4`: passed, including the MariaDB server link.
- `make -C src -j4 PERSISTENCE_BACKEND=flatfile
  DMS_BINARY=/home/aiwithapex/projects/duris/bin/server/dms_issue110_flatfile`:
  passed, including the flat-file server link. Both used existing object caches
  with dependency tracking; these were not clean rebuilds.
- Local evidence is in ignored `bin/analysis/issue110/`; the committed test and
  commands above reproduce the checks without those logs.
- Existing regressions passed individually with `python3 tests/async/<name>.py`:
  `test_ship_owner_rename_failure`, `test_ship_save_guards`,
  `test_nevent_ship_volley_runtime`, `test_flatfile_ship_repository`,
  `test_ship_autopilot_group_safety`, `test_ship_boot_room_pool_full`,
  `test_ship_documented_bugs`, and `test_account_character_delete_runtime`.
  No pre-existing failure was found in these checks.

### Separate cleanup follow-up discovered during the audit

After publishing the core heartbeat correction, extend the regression to cover
occupied interiors during staff purge and NPC AI `escort`/`did_board` references
on other ships. `do_purge` does not clear contents before `delete_ship`, which
releases the rooms, while `clear_references_to_ship` currently clears only
`target`. Verify these gaps with executable failures and repair them as a
separate stacked PR. Preserve all runtime state on player persistence failure.

## Resume point

Commit/push/open the verified heartbeat correction, then reproduce and repair
the separate cleanup gaps above. The production live acceptance remains pending.
Read the current branch and working diff first; do not restart from `master` or
discard uncommitted work. Update this document at each verified checkpoint.
