# Findings: log review after the 2026-10-08 pull, clean rebuild and restart of staging

Written 2026-10-08 against `master` at `ca92ef1c2`. That morning the staging checkout was
pulled from `a7e43bd0a` (70 commits, the clean-rebuild and fall fixes, Phases 3 to 5 and the
work-item plan), fully cleaned with `make clean-all`, rebuilt with the production profile,
and restarted at 10:01:55 UTC (boot in 12 316 ms). Every log the server and the host keep
was then read: `logs/log/*` of the new run, the systemd journal of
`duris-mud-production.service` since the restart, the archived logs of the run that ended at
10:01:55 (`logs/old-logs/2026.10.08-10.01.55/`), the MariaDB and Redis unit journals, the
user-level journal at warning and above, the unit and timer list, both latency traces, and
the item-ownership audit against `duris_staging`. File each row as a work item or dismiss
it, then delete the file. Line numbers are from `ca92ef1c2`.

## Findings

| # | Severity | Finding | Evidence | Suggested action |
|---|---|---|---|---|
| 1 | Medium, bug. **Fixed in the worktree, uncommitted.** | Two operator scripts ignore `DB_PORT`. `scripts/item_ownership_audit.sh:57` and `scripts/change_password.sh:20` call `mysql -h"$DB_HOST"` with no port, so on a host whose staging MariaDB is not on 3306 they reach another server. Here the system MariaDB listens on 127.0.0.1:3306 and the staging one on 127.0.0.1:3307, and both scripts failed with `ERROR 1045 Access denied for user 'duris_staging'@'localhost'`. `migrations/verify_runtime_compatibility.sh:18` already passes `-P "${DB_PORT:-3306}"`. | `ss -ltn` shows both listeners; the audit's first run printed the access-denied line and no counts. | Done: both calls now pass `-P"${DB_PORT:-3306}"`, after which the audit ran (finding 4). Commit the two one-line changes. The remaining scripts that call `mysql` go through the launcher's argument array or `--socket`, and were not changed. |
| 2 | Low, code and content | Six objects carry the `board` special procedure without a row in the board table, so `look`, `read`, `examine`, `write` or `remove` near one logs `degenerate board!  (what the hell...)` (`src/cmd/boards.c:199`, from `find_board()` at L121 returning -1). The assignments are `src/specs/specs.assign.c` L1764 (76), L1767 (86), L1768 (87), L1776 (42), L2102 (55026) and L2103 (55197); the table `board_info[]` (`boards.c:55-103`, `NUM_OF_BOARDS` 44 at L52) has none of them. The configured boards do not need those lines at all: `initialize_boards()` assigns the special to every table entry itself (`boards.c:162`). Of the six, two are zone-loaded: 42 is now "a dazzling pearl necklace" (`areas/obj/dalvik.obj`) placed by `areas/zon/heavens.zon:182` in room 1196 "The Ideas Room", whose zone comment still reads `* The board of IDEAS`; 55197 is "a discussion board" (`areas/obj/wh.obj`) placed by `areas/zon/wh.zon:559` in room 55612 "The Immortal Control Room of Winterhaven". The other four are not placed by any zone command and no `player_items` row holds one: 76 "a shard of rock" (`hostel.obj`), 86 "the devil prince's infernal wings" (`mavulsk.obj`), 87 "Forger's bulletin board" (`heavens.obj`), 55026 "the suggestion board" (`wh.obj`). | Six lines in the previous run's `logs/log/board`: 2026-10-07 14:56:54, 14:57:35, 14:58:14, 14:58:16, 14:59:01 and 2026-10-08 06:58:14 (six seconds after Zusuk's login; the command log does not record the room). | Delete the six `specs.assign.c` lines; the warning then needs a wizard to load one of the four unplaced objects. Decide separately whether 87, 55026 and 55197 are meant to be working boards (a `board_info` row each, with read/write/remove levels and a `lib/boards/` file) and whether room 1196 should load a real board again instead of the necklace. |
| 3 | Medium, latent bug | A special assigned to a vnum that no longer exists lands on index 0. `real_object0()`, `real_mobile0()` and `real_room0()` return 0 for a missing vnum (`src/world/db.c:4772`; the comment at L4531-4539 says this was done so `spec_ass.c` never indexes -1), and `specs.assign.c` assigns through them without a check. With comments and `#if 0` blocks excluded, 17 object, 86 mobile and 18 room assignments name vnums absent from `areas/world.obj`, `world.mob` and `world.wld`. The last one in file order wins: object 1 ("a silvery pendant in the shape of a skull", `areas/obj/Magetower.obj`) ends with `staff_of_blue_flames` (L1971), mobile 1 ("mob", a placeholder) with `world_quest` (L2214), and room 0 "The Void" with `inn` (L2462). Object 1 and mobile 1 are loaded by no zone command and no character holds object 1, so those two are dormant; room 0 is live. The full lists are in the appendix. | `python3` pass over the stripped source, lists in the appendix; `grep -c '^[OEGP] [0-9]* 1 ' areas/world.zon` and `'^M [0-9]* 1 '` both 0; `SELECT COUNT(*) FROM player_items WHERE vnum=1` is 0. | Give `specs.assign.c` one helper per kind that looks the vnum up with the `-1` variant, skips a missing one and logs it once at boot (`LOG_STATUS`, one line per vnum), and switch the assignments to it; then prune the 121 dead lines, which is content archaeology and can wait. A regression that boots the world and asserts `world[0].funct`, `mob_index[0].func.mob` and `obj_index[0].func.obj` are null unless vnum 0 or 1 is assigned on purpose. |
| 4 | Info, resolved by the pull | The previous run's debug log carried 666 `player_snapshot_capture: … outcome=unowned_object … recovery=audit_grant_path` lines and 6 `player_load_materialize: … outcome=missing_payload_rows` lines with `DURIS_PERSISTENCE_TRACE` unset. Commit `61fa52894` in the pull made both of them traces: the first now needs `persistence_trace_enabled()` (`src/player/player_snapshot_capture.c:347-351`). None since the restart, including a level-62 login and its saves. | The audit after finding 1: zero orphan payload rows, zero ownership rows without a payload row, zero characters over `PLAYER_LOAD_ITEM_SKIP_MAX`. | None. |
| 5 | Low, docs | `scripts/item_ownership_audit.sh:65` still prints `== Orphan payload rows (item loss: dropped at load, deleted at next save) ==`, while the header comment the pull rewrote (L10-14) says the load takes the item as the player's and nothing is lost. | The two texts in the same file. | Reword the echo to match the header. |
| 6 | Info | The new run is clean. `logs/log/status` holds zone resets, event-budget windows and one `telemetry_health … state=disabled` line; `debug` holds mine and node loads, shop ratio notes, `sql_restore_shopkeepers: loaded 544 shopkeepers` and connection probes; `comm` has one `Write to socket error: Connection reset by peer (errno=104)` (`src/net/mccp.c:378`, a client that dropped); `sys` shows Redis connected and every cache primed; `kingdom` loaded 0 realms; `mob` has 302 `M cmd not executed` lines against 312 in the previous run (area data, not engine defects, per `docs/operations/RUNBOOK.md:549`); `obj` has 90 zone loads. The journal has no warning-class line; the launcher verified schema compatibility, rebuilt nothing (the area tools were already built) and generated 17 680 mobs, 19 149 objects, 1 723 quests, 544 shops, 253 261 rooms and 350 zones. | First event-budget window `deferring_pulses=20 deferred=70212 peak_catchup_debt=8741 max_late_ticks=2`, then 1 to 2 deferring pulses a window, the same shape as the previous run (boot catch-up is #14's territory). Both latency traces: `dropped_section_samples=0 dropped_contended_samples=0 invalid_clock_samples=0`. | None. |
| 7 | Info | The previous run (2026-10-07 08:17 to 2026-10-08 10:01) ended cleanly: `Normal termination of game.` and `SQL connection pool shut down.` in its status log, `Launcher|signal from launcher` in `logs/shutdown_info.txt`, no core file. Its `comm` log holds pre-login probes from 35.205.33.66 (a cloud address) and one from this host; its `exp`, `file` and `cmd.debug` logs show ordinary play by six characters. | `logs/old-logs/2026.10.08-10.01.55/{exit,status,comm}`. | None. |
| 8 | Info, operations | Host state after the deploy. MariaDB (3307) and Redis (6381) logged nothing but a routine RDB save since 10:00; no failed user unit; `duris-certbot-renew.timer` ran at 00:56 and is due again at 12:41; disk at 32 %, `logs/old-logs` at 18 MB. The scheduler state was carried from `bin/server/` to `runtime/maintenance-scheduler.state` at the restart and is being rewritten there; the stale copy under `bin/server/` was removed. `TELEMETRY_OUTAGE_LEDGER_DIR=/home/staging/duris/runtime/telemetry-outages` (0700) was added to `.env` for when telemetry is turned on. The pull's `make_lookup` fix held: all five `lib/misc/lookup*` tables are 0600 after the boot. `bin/server/history/dms.2026.10.08-10.01.55` is the previous binary. | `systemctl --user list-units 'duris-*'`, `ls -l lib/misc/lookup*`, `stat runtime/maintenance-scheduler.state`. | None. |

## Follow-ups

- Finding 1 is two committed lines away from done; finding 5 is one more line in the same
  script.
- Finding 2 is a six-line deletion plus two content decisions for the owner (which of the
  three real boards should work, and what room 1196 should hold).
- Finding 3 is the one worth a work item: a small helper and a boot-time regression, then a
  pruning pass over `specs.assign.c` that can be split off.

## Appendix: special assignments whose vnum is not in the world

From `src/specs/specs.assign.c` at `ca92ef1c2`, comments and `#if 0` blocks excluded,
checked against the `#<vnum>` lines of `areas/world.obj`, `areas/world.mob` and
`areas/world.wld` generated at the 10:01:55 boot. Format: `vnum→special (line)`.

Objects (17), all landing on object 1:
35102→magic_pool (L1287); 35103→magic_pool (L1288); 32507→shard_frozen_styx_water (L1455);
70549→circlet_of_light (L1501); 70554→ljs_sword (L1502); 70556→wuss_sword (L1503);
70558→head_guard_sword (L1504); 70559→priest_rudder (L1505); 70565→alch_bag (L1506);
70568→alch_rod (L1507); 70571→ljs_armor (L1508); 70572→dragon_skull_helm (L1509);
65050→dragonslayer (L1552); 4801→magic_pool (L1827); 4802→magic_pool (L1828);
25080→ring_elemental_control (L1965); 25103→staff_of_blue_flames (L1971).

Mobiles (86), all landing on mobile 1:
8028→cityguard (L374); 8034→cityguard (L375); 8047→cityguard (L376); 1919→bridge_troll (L416);
65012→fooquest_mob (L478); 65013→fooquest_boss (L479); 4070→piercer (L569);
4120→guild_guard (L570); 210004→undeadcont_track (L587); 210005→undeadcont_track (L588);
4812→poison (L622); 4830→wanderer (L623); 150115 to 150140→outpost_captain (L687 to L712,
26 lines); 8003→world_quest (L772); 8309→world_quest (L779); 8004→money_changer (L904);
8019→guild_guard (L905); 8029→guild_guard (L906); 8037→guild_guard (L907);
8039→guild_guard (L908); 8040→guild_guard (L909); 8041→guild_guard (L910);
8042→guild_guard (L911); 8044→janitor (L912); 8050→guild_guard (L913);
8311→guild_guard (L914); 8312→guild_guard (L915); 8313→guild_guard (L916);
14202→bridge_troll (L987); 25000→guild_guard (L1051); 25101→guild_guard (L1054);
25104→guild_guard (L1055); 150100→patrol_leader (L1212); 150101→patrol_leader_road (L1213);
65015, 65016, 65018, 65019, 65022, 65024, 65026, 65028, 65029, 65030, 65032, 65033,
65034→newbie_quest (L1228 to L1240, 13 lines); 70535→long_john_silver_shout (L1514);
70542→undead_parrot (L1515); 70546→undead_dragon_east (L1516);
70552→pirate_cabinboy_talk (L1519); 70554→pirate_female_talk (L1520); 70502, 70503, 70539,
70540, 70541, 70549, 70551, 70561→pirate_talk (L1521 to L1528); 87891→world_quest (L2214).

Rooms (18), all landing on room 0:
29605→inn (L296); 19890→GithyankiCave (L2294); 3398→inn (L2318); 66355→undead_inn (L2337);
43341→patrol_shops (L2340); 140854→ship_shop_proc (L2388); 258421→ship_shop_proc (L2389
and L2392); 70501→ship_shop_proc (L2391); 8010→pet_shops (L2435); 8211→dump (L2436);
8323→pet_shops (L2437); 8003→inn (L2438); 8287→ship_shop_proc (L2439); 29502→inn (L2456);
30511→inn (L2457); 29903→inn (L2459); 30303→inn (L2462).
