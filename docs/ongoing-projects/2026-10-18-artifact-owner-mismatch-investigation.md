# Artifact owner mismatch after the October 18 reboot

Investigated on 2026-10-18 UTC against production source
`9017ce1ca940cbe74a6162fca3d4d8c113eeb8b6`. The server process started at
12:54:42 UTC. This investigation used read-only production queries and logs,
source inspection, and isolated executable probes. It did not change player
data, artifact records, configuration, or the running server.

**The alerts identify stale artifact ownership/location tracking after valid
item restoration. The affected artifact's feeding reward is skipped.** They
do not establish that the player has a duplicate or an illegitimate item.
The reported mindstone ring was affected too; its tracker subsequently
reconciled. The crown of Aramus remained inconsistent at inspection.

Repair and production verification are tracked in
[issue #197](https://github.com/LuminariMUD/Duris/issues/197).

## Report and observed scope

The supplied staff notice was:

```text
PERSISTENCE: domain=artifact_reward/capture action=owner_mismatch outcome=alert detail=vnum=32621 reference=19c8ee13523b2a70 (suppressed=1 age=30s)
```

Its reference matches `logs/log/file` at 13:44:17 UTC. The player also reported
equipping “a wispy astral-twined mindstone ring.” The production object catalog
and checked-in area definitions identify that ring as vnum **424**, whereas
**32621 is the crown of Aramus**.

The log snapshot inspected at approximately 13:48 UTC contains:

| Artifact | Recorded owner-mismatch alerts | First / last alert, UTC | Tracking observed afterward |
| --- | ---: | --- | --- |
| 424 — wispy astral-twined mindstone ring | 7 | 12:59:26 / 13:09:14 | Player-owned, matching canonical item custody |
| 32621 — crown of Aramus | 150 | 12:59:26 / 13:44:54 | Ground location despite matching player custody and saved payload |

Both artifacts initially generated alerts for the same source-award references.
The ring's later correction is consistent with ordinary remove/wear or other
placement activity. The exact action and correction time were not recorded;
the supplied wear message alone does not prove which action corrected it.

At 12:54:46 the artifact boot log reported retained identities without a
qualified restored ground body for 424, 922, and 32621. Read-only joins after
boot found the canonical UID for each in `player_items`, matching the active
player custody row in `item_current_owner`. Retaining the identity instead of
spawning a second ground object was appropriate.

A broader read-only scan at approximately 13:50 UTC found four canonical
artifacts whose active player custody and saved player payload agree but whose
artifact-domain owner/location does not:

| Vnum | Artifact | Artifact-domain state |
| --- | --- | --- |
| 922 | mirrored ioun stone | Owned, ground |
| 19730 | Avernus the life stealer | Unowned, NPC |
| 32621 | crown of Aramus | Owned, ground |
| 67244 | band of emerald flames | Unowned, not in game |

These additional rows are reconciliation candidates, not proof of an online
wearer or a current feeding failure. No alert for 922, 19730, or 67244 appeared
in the inspected log. The scan is bounded to canonical identities with active
player custody; it is not a full audit of pets, lockers, corpses, shops, or
every possible payload source. Private player identifiers and item UIDs are
omitted from this report.

## Confirmed failure path

1. `artifact_guild_state_capture()` in
   [artifact_guild_state.c](../../src/guild/artifact_guild_state.c) first checks
   canonical identity and the actual worn-object pointer. Only then does it
   report `owner_mismatch` if `get_artifact_data_sql()` returns false, the
   tracking location is not `ARTIFACT_ON_PC`, or its player ID differs.
   Consequently this exact alert means the identity and live wear checks
   already passed. A row with `owned=false` also fails this check even when
   its physical identity is valid.
2. Despite its name, `get_artifact_data_sql()` reads the game-thread
   `artifact_rows` map, not a fresh SQL query. The corresponding database
   mismatch corroborates the alert; changing SQL alone would not repair the
   live cache and could be overwritten by a later save.
3. `attach_loaded_inventory()` in
   [player_load_items.c](../../src/player/player_load_items.c) directly links
   saved equipment/inventory to the character, then calls
   `artifact_object_placed()`. The source-qualified recovery path in
   [artifact.c](../../src/guild/artifact.c) registers the canonical live body
   and clears the pending state, but its recovery branch deliberately returns
   without changing `owned`, `locType`, or `location`. The attachment path does
   not call `artifact_update_location_sql()`. Thus an admitted, correctly worn
   canonical artifact can retain a ground, NPC, or unowned tracking row.
4. Ordinary placement/equipment hooks in
   [handler.c](../../src/world/handler.c) do call
   `artifact_update_location_sql()`. This computes the current owner from the
   physical object and can reconcile the tracker. That explains why the ring
   can stop alerting while another restored artifact remains affected.

### How shutdown can produce the stale ground location

The orderly shutdown path in [comm.c](../../src/net/comm.c) queues terminal
player snapshots and drains them, then directly calls `extract_char()`.
`persistence_save_all_characters_terminal()` in
[actoth.c](../../src/cmd/actoth.c) does not set
`CHAR_RFLAG_TERMINAL_ITEMS_SAVED`. That flag is set by the separate
`extract_char_after_terminal_save()` helper, which this shutdown loop does
not call. Without the flag, equipment/inventory cleanup can put the saved
items into the room; `obj_to_room()` updates artifact tracking to ground.

The predeployment backup has crown 32621 tracked on a player, while startup
and subsequent SQL snapshots show it tracked on the ground. This transition
and the shutdown code support shutdown cleanup as the immediate source of the
crown's mismatch. The shutdown transition itself was not replayed against
production or instrumented in the old process. Not every stale row began with
this reboot: the predeployment backup already has 922 on the ground and 424
on an NPC. Both preventing teardown drift and reconciling qualified restored
ownership are needed.

## Impact and interpretation

- The capture loop logs the conflict and continues. It omits feeding for
  that artifact; valid other artifacts and eligible guild rewards can still
  proceed. The parent epic award is separate and is not rejected by this
  check. This is not evidence of lost epic points.
- Rejected feeding is not queued for later automatic replay. Correcting the
  tracker permits future awards but does not reconstruct skipped feed
  deltas. Actual lost timer extension was not calculated: source amounts,
  modifiers, and the ten-day cap must be considered before any compensation.
- This path does not delete the artifact or clear its canonical identity or
  soul. No item loss or duplicate creation was established by this alert.
- `suppressed=1 age=30s` describes staff-notice throttling. The reporter in
  [utility.c](../../src/core/utility.c) groups by domain and action with a
  30-second interval; different affected artifacts share that group. It logs
  each occurrence separately. The suffix is not a count of duplicates or a
  database retry age.
- PR #188 changes Paladin/Anti-Paladin balance. It does not touch the restore
  or artifact tracking paths and will not resolve these alerts.

## Isolated verification

An extension of `tests/async/test_artifact_creation_admission.py` ran the real
artifact service, source-qualified constructor, and extracted
`attach_loaded_inventory()` with a synthetic saved player artifact. It used
the existing fixture writer and ASan/UBSan, without a database or server.

The probe demonstrated both of these assertions:

1. A qualified saved UID becomes canonical and worn by the correct player,
   while its tracking row remains ground. The timer and soul remain intact.
2. Calling the ordinary location updater changes that same row to player
   ownership without resetting its timer or soul.

The probe and surrounding admission scenarios passed. The existing
`test_artifact_guild_rewards_runtime.py` also passed all four unittest groups,
including isolation of conflicting artifacts from unrelated rewards.
The isolated worktree combined deployed master with PR #188; all artifact,
player-load, and shutdown source files used here are unchanged from the pinned
production source. This proves the restore/tracking gap and normal update
behavior, not an end-to-end production restart or a repaired implementation.

Scratch reproduction:
`/tmp/duris-pr188-20261018/bin/tests/reproduce_artifact_restore_owner_mismatch.py`.
Run from that worktree with `PYTHONPATH=tests/async python3` followed by the
scratch path. Results: `/tmp/duris-artifact-restore-repro.log` and
`/tmp/duris-artifact-rewards-check.log`. These temporary files are not durable
regression coverage.

## Recommended repair and acceptance checks

Use the existing qualified recovery and terminal-extraction boundaries.
After successful player attachment, reconcile artifact owner/location only
for the source-qualified canonical body and validated custody. Preserve the
canonical UID, soul, timer, and rollback behavior; account explicitly for an
unowned tracking row that already has valid player custody. Prevent orderly
shutdown teardown from publishing a room transfer after a successful terminal
player snapshot. Do not weaken the reward ownership check to hide the alert.

Before deploying a repair, add permanent regression coverage for:

- Worn, carried, and nested qualified player artifacts restored from stale
  ground/NPC/unowned tracking, with unrelated inventory preserved.
- First eligible reward after restore: exactly one feed, no owner mismatch,
  unchanged independent rewards, and no duplicate/rejected-copy authority.
- Failed attachment and failed terminal-save admission: no premature owner
  publication, no lost payload, and no accidental artifact retirement.
- Orderly shutdown, fresh process boot, login, reward, save, and another
  restart, preserving canonical identity, timer, soul, and custody on both
  maintained persistence backends.

For an immediate operational repair, first review the specific canonical
bodies and custody records, then use a narrowly scoped game-thread location
reconciliation and verify the next eligible award. A blanket `syncdb`, direct
SQL rewrite, artifact recreation, or item deletion is not justified by this
evidence. No live repair or compensation was attempted in this investigation.
