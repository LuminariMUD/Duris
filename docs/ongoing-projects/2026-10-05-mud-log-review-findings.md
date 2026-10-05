# MUD log review findings — 2026-10-05

Status: open. This records what a full read of the server's logs turned up. No
server code was changed. One housekeeping fix (ignoring `logs/boot.log`) landed
alongside this document.

## Result

No crash, no failed save and no lost item in any of the four runs. Two bugs
need a code change, one gap needs a hardening decision, and the rest is small
defects, log noise, configuration and area data.

| #   | Issue                                                        | Kind      | Effect today                                                   |
| --- | ------------------------------------------------------------ | --------- | -------------------------------------------------------------- |
| 1   | SQL queued during boot is discarded                          | Bug       | `artifact list` is nearly empty; boot caches not warmed         |
| 2   | Item ownership rows are never retired                        | Bug       | A warning on every login of an affected character, growing     |
| 3   | Save audit flags every ordinary pickup as `unowned_object`   | Bug       | False alarms in `debug` on each save until the next login      |
| 4   | Unauthenticated connections have no per-host limit           | Hardening | None yet; a 51-minute burst showed the exposure                |
| 5   | Quest count shows `-1` before the history loads              | Defect    | Wrong number in `score` and the client quest panel, briefly    |
| 6   | Quit timestamp is UTC−4 labelled `EST`                       | Defect    | One hour off for the half of the year that really is EST       |
| 7   | Log noise (five sources)                                     | Noise     | Hides real lines; `status` is 23% event-budget records         |
| 8   | Configuration notes (mail, MariaDB)                          | Config    | Password reset by email is off                                 |
| 9   | Area-data notices                                            | Data      | None; standing notices repeated every boot                     |

Suggested order: 1, then 2 and 3 together (same subsystem), then 4.

## Scope and method

The install is `/home/staging/duris` on `plesk.luminarimud.com`, checkout
`dc8357143` on `master`, version `0.1.63`, run by the user unit
`duris-mud-production.service` (production role, ports 7777 and 7778). Its
database was created empty on 2026-10-04, which matters for issue 1. Times are
UTC.

| Run | Started          | Ended            | Logs                                   |
| --- | ---------------- | ---------------- | -------------------------------------- |
| 1   | Oct 4 22:11:17   | Oct 4 22:14:58   | `logs/old-logs/2026.10.04-22.14.58/`   |
| 2   | Oct 4 22:14:58   | Oct 5 03:12:09   | `logs/old-logs/2026.10.05-03.12.09/`   |
| 3   | Oct 5 03:12:09   | Oct 5 04:02:44   | `logs/old-logs/2026.10.05-04.03.02/`   |
| 4   | Oct 5 04:03:02   | still running    | `logs/log/` (read up to 04:24)         |

Read in full: every file under `logs/log/`, `logs/player-log/` and the three
archives, the four `latency_trace.log` files, `logs/shutdown_info.txt`, and the
journals of the MUD, MariaDB and Redis user units. Each recurring line was
traced to the source that writes it. Issues 1, 2 and 7 were confirmed with
read-only `SELECT`s against the instance's database; nothing was written.

Character names and the operator's client address are left out. Characters are
named by player id (pid).

## 1. SQL queued during boot is discarded

**Symptom.** Every boot writes 45 to 62 lines like this to `logs/log/file`:

```text
sql job not queued: guild/artifact.c:164 artifact_row_store
sql job not queued: guild/artifact.c:455 arti_redis_cache
sql job not queued: redis/redis_report_cache.c:498 redis_cache_fraglist
sql job not queued: world/outposts.c:270 save_outpost_record
```

| Run | `artifact_row_store` | `arti_redis_cache` | `redis_cache_fraglist` | `save_outpost_record` | Total |
| --- | -------------------: | -----------------: | ---------------------: | --------------------: | ----: |
| 1   | 42                   | 6                  | 1                      | 3                     | 52    |
| 2   | 35                   | 6                  | 1                      | 3                     | 45    |
| 3   | 39                   | 6                  | 1                      | 3                     | 49    |
| 4   | 52                   | 6                  | 1                      | 3                     | 62    |

**Cause.** `sql_queue()` and `sql_read()` hand their work to the persistence
writer thread (`submit()` in `src/sql/sql_async.c`). The writer is started by
`player_save_pipeline_init()` at `src/net/comm.c:990`, after `boot_db()` and
after "Entering game loop" is logged. Before that, `enqueue()` in
`src/player/player_save_worker.c` returns `unavailable` because
`health.running` is false, and `submit()` logs the line above and drops the
job. Nothing retries it. A dropped read never calls its completion callback.

The late start is deliberate: the comment at `src/net/comm.c:967` explains that
a joinable worker thread started before `boot_db()` turned a fatal world-data
error into `SIGABRT`. The queue was introduced on 2026-09-30 in `ddd52a342`
("Queue game-thread SQL on the writer, and count what still waits"), so this
dates from then; before it, these statements ran synchronously.

**What is lost.**

- **Artifact rows.** The boot zone reset loads artifacts onto mobs and into
  rooms. Each one reaches `arti_update_sql()`, finds no row, logs "Creating
  entry" to `logs/log/artifact`, and calls `artifact_row_store()`
  (`src/guild/artifact.c:161`). That updates the in-memory map and queues an
  `INSERT … ON DUPLICATE KEY UPDATE` plus the `artifact_domain_state` mirror.
  Both statements are dropped. The "Creating entry" count matches the dropped
  `artifact_row_store` count in all four runs.
- **Artifact list caches.** `arti_cache_init()` queues six reads to fill the
  Redis artifact lists. All six are dropped.
- **Frag list cache.** `redis_cache_fraglist()` at `src/net/comm.c:838` is
  dropped. `logs/log/sys` shows "cached named report" and "cached epic zones"
  on every boot and never "cached fraglist".
- **Outpost hit points.** `outpost_generate()` (`src/world/buildings.c:584`)
  calls `set_current_outpost_hitpoints()` for each of the three outposts.
  `save_outpost_record()` returns before updating its in-memory copy when the
  queue refuses, so neither memory nor the table changes.

**Effect.**

- The `artifacts` table holds 2 rows, although run 4 created 52 artifacts in
  memory. Both rows were written a few minutes after a boot (03:15:29 and
  04:07:04), when the writer was running. `artifact_domain_state` also holds 2.
- `artifact list` reads the `artifacts` and `artifacts_mortal` tables, not
  memory (`artifact_list_query()`, `src/guild/artifact.c:339`), so players and
  immortals see only artifacts that changed after boot. The Redis copy the
  website reads is built from the same query.
- The frag list cache is rebuilt on the first `fraglist` command, so that loss
  is one slow first view.
- The `outposts` table shows `hitpoints = 0` for all three outposts, and
  `show_outposts()` prints the stored value, so an undamaged outpost can be
  displayed at 0 hit points until something saves it at runtime.
- On a long-lived database the artifact rows already exist, so the dropped
  statement is usually a no-op update and the bug is mostly hidden. It shows
  fully here because this database started empty.

**Fix direction.** Two options, both in `src/sql/sql_async.c`:

1. Hold jobs submitted before the writer starts and submit them once
   `player_save_pipeline_init()` succeeds.
2. Run them synchronously on the boot connection while the game loop is not
   yet running, as the rest of boot already does with `qry()`.

Starting the writer earlier is ruled out by the comment cited above. A boot
test should assert that `logs/log/file` has no `sql job not queued` line and
that `artifacts` has one row per in-memory artifact.

## 2. Item ownership rows are never retired

**Symptom.** In run 3, each of pid 1's three logins wrote this to
`logs/log/debug`:

```text
player_load_materialize: component=items pid=1 outcome=missing_payload_rows count=1
```

**What happened.** Reconstructed from `cmd.debug`, `player-log/wizcmds`,
`debug` and the database, all on Oct 4 in run 2:

| Time     | Event                                                                                   |
| -------- | --------------------------------------------------------------------------------------- |
| 22:19:13 | pid 1 runs `drop all` in room 22800 (28 items)                                          |
| 22:19:16 | `get all` picks them up again, plus the room's own zone-loaded sign (vnum 22800)        |
| 22:19:16 | The save that follows inserts an `item_current_owner` row: item 1009112, owner pid 1    |
| 22:19:19 | pid 1 quits                                                                             |
| 22:19:32 | pid 1 returns and runs `drop sign`; saves at 22:19:35; quits at 22:19:36                |
| 03:12:09 | Shutdown. The sign, still on the floor, is extracted with the rest of the world         |

The row for item 1009112 was never touched again: `updated_at` is
22:19:16.262797 and `item_revision` is 1. It still names pid 1 as the active
owner of an item that no longer exists.

**Cause.** This is how item custody is designed, as
[DATABASE.md](../reference/DATABASE.md) describes: memory is the authority, and
each save *claims* what its owner holds (`claim_items()` in
`src/item/item_claim_repository.c`). A claim inserts or re-points rows for
items the owner holds. Nothing releases rows for items the owner no longer
holds:

- Dropping, giving and picking up are not ledgered. The reasons `player_get`,
  `player_drop`, `player_give`, `corpse_loot` and `mobile_claim` exist in
  `src/item/item_transfer_command.h` but no code uses them. The ledger on this
  instance holds 185 rows and every one is a creation grant.
- `extract_obj()` deliberately leaves the row in place; the comment at
  `src/world/handler.c:3151` says so and calls the result a "stale custody
  row".
- No statement anywhere in `src/` deletes from `item_current_owner`.
  Destruction is recorded only for shop sales and a few repository paths.

So a row goes stale whenever a player's item stops existing without passing to
another saved owner: dropped and then cleared by a zone reset or shutdown, and
by the same reading eaten, quaffed, junked or decayed. Only the
dropped-then-extracted case was observed.

**Effect.**

- Players lose nothing. The load path only counts the row
  (`src/player/player_load_repository.c:869`).
- The warning repeats on every login of the character, forever. There is no
  repair path; `scripts/item_ownership_audit.sh` reports these rows and is
  read-only.
- The count can only grow with play, so the line will stop meaning anything
  once real players are on, and `item_current_owner` grows without bound.
- The count is parsed with a cap of 4096; past that it silently reads as 0.

**Fix direction.** A design decision, not a one-line fix. Options:

1. Have the save's claim also release rows that name this owner but are absent
   from the snapshot, in the same transaction.
2. Reap rows whose item is in no payload table and not live in memory.
3. Accept the rows, document them as expected, and stop logging the count (or
   log it only above a threshold).

## 3. Save audit flags every ordinary pickup as `unowned_object`

**Symptom.** In run 2 the same sign produced three lines in `logs/log/debug`,
at 22:19:16, 22:19:18 and 22:19:19:

```text
player_snapshot_capture: component=items outcome=unowned_object uid=1009112 vnum=22800 recovery=audit_grant_path
```

**Cause.** `capture_item_tree()` in `src/player/player_snapshot_capture.c`
logs this when an item being saved has no entry in the in-memory ownership
table (`item_ownership_runtime_lookup()`). Its comment says the line exists to
find "grant paths" that hand out items without a transfer. Under the claim
model in issue 2 that is the normal state of any zone-loaded item a player
picks up: it has no row until the first save inserts one. The save's insert is
not published back to the in-memory table, which is filled only at login and
by ledgered transfers, so the line fires again on every later save in the
session. It stopped here only because the character logged out and back in.

**Effect.** With players looting, every picked-up item logs once per save
until the holder's next login. The line cannot separate its intended target (a
grant path that skipped the ledger) from ordinary play, so it will bury the
cases it was written to find.

**Fix direction.** Either publish a committed claim's inserted rows to the
in-memory table, or narrow the audit to the grant paths it is meant to watch.
Best decided together with issue 2.

## 4. Unauthenticated connections have no per-host limit

**What happened.** Between 02:31:48 and 03:22:40 on Oct 5, the address
`209.126.199.93` opened 753 plain-telnet connections: a median of 13 a minute,
at most 26 a minute, and 11 in the busiest second. None got past the account
name prompt (`CON_GET_ACCT_NAME`, state 60), about 21 were open at once, and
each was closed by the client within seconds. The burst carried across the
03:12 restart and has not returned. Reverse DNS for the address does not
resolve. Five other addresses made one to three connections each, which is
ordinary internet background.

The server was unaffected. Each connection left one "Losing descriptor without
char" line in `logs/log/comm`: 753 of the 782 such lines across the runs.

**Exposure.** The burst was harmless only because the client hung up quickly.
From `src/net/comm.c`:

- The descriptor cap is `MAX_CONNECTIONS` = 256, for all clients together.
  `new_descriptor()` closes any connection past it.
- There is no per-address limit on open connections or on connection rate. The
  only per-host control is the ban list (`bannedsite()`), which is empty here.
- A connection idle at the account name prompt is kept for 3600 pulses, which
  is 15 minutes (the `default` case of the idle switch near line 1810).

One client that opens about 240 connections and stays silent would therefore
hold every slot for 15 minutes at a time and keep players from logging in.

**Fix direction.** A hardening decision: a per-address cap on unauthenticated
connections, a much shorter idle timeout before an account name is entered, or
both. A ban entry for the one address is a stopgap and does not close the gap.

## 5. Quest count shows `-1` before the history loads

At 04:12:06 in run 4, when a new character entered the game, `debug` logged
`sql_world_quest_can_do_another: history not loaded yet`. The function
(`src/sql/sql.c:2779`) returns `-1` in that case, and two callers print the
value unchecked: `score` shows "Bartender Quests Remaining: -1"
(`src/cmd/actinf.c:6559`) and the quest JSON sent to clients carries
`"remaining": -1` (`src/core/json_utils.c:1141`). The history loads a moment
later and the next reading is right. Seen once; any character can hit it in
the first instant after entering.

## 6. Quit timestamp is UTC−4 labelled `EST`

`logs/log/comm` records quits as, for example,
`has quit in [15295] @ Mon Oct  5 00:03:36 2026 EST` at 04:03:36 UTC.
`src/cmd/actoth.c:310` subtracts a fixed four hours and appends the text
" EST". Four hours is Eastern Daylight Time; when the clocks change the stamp
will be an hour wrong and the label has been wrong all summer. The line
already carries a UTC prefix from the logger, so the second stamp can go.

## 7. Log noise

None of these is a fault. Each adds lines that make real problems harder to
see.

- **Disconnects logged as errors.** A client that closes its socket without a
  TLS close produces `process_input() CON_63 Read: -54 Error: Error in the pull
  function` or `Read: -110 … non-properly terminated`; a plain one produces
  `Read: -1 Error: 104` or "EOF encountered". Every scripted login in these
  runs ended this way. State 63 is the account menu, where a client sits after
  `quit`.
- **`get_mud_info(): requested mud_info 'lock', but doesn't exist!`** Logged
  eight times, once per new-character name entered. `mud_info` has no `lock`
  row and no migration seeds one; the row is an optional switch that blocks
  creation when set to `create` (`src/account/account.c:2402`). Absent is the
  normal state, so the lookup should not log.
- **Profile dump of zeros.** Every shutdown writes 39 `Profile info` lines to
  `logs/log/file`, all with zero calls: the build defines `DO_PROFILE`,
  profiling is off, and `PROFILES(SAVE)` at `src/net/comm.c:2631` runs anyway.
- **Event-budget records.** `NEVENT BUDGET` and `NEVENT CATCHUP` are written to
  `status` whenever the event pass defers work past its 25 ms budget. That is
  the design working: the worst lateness in any run was 3 pulses (0.75 s). In
  run 2 they were 1,069 of 4,624 `status` lines.
- **Shopkeeper saves after boot.** `sql_save_dirty_shopkeepers: saved 16
  shopkeepers` repeats 34 times about two minutes after each boot. A boot marks
  all 543 shops dirty and the save is batched on purpose
  (`src/sql/sql_player.c:3655`).

Housekeeping found on the way:

- **`logs/boot.log` was tracked in git.** It was committed once in `2a79fe583`
  and nothing writes it; its "has invalid number" zone lines are from that old
  capture and do not appear in a live boot. It is now ignored and untracked.
- **Archive names.** `scripts/cycle_mud.sh` names each `logs/old-logs/`
  directory for the moment of the restart, so a directory holds the run that
  *ended* then. The first start of a fresh install leaves an empty one
  (`2026.10.04-22.11.17`).

## 8. Configuration notes

- **Mail is not configured.** Each boot logs `Account recovery: MAIL_ENABLED is
  not TRUE; password reset by email disabled.` `.env` has no `MAIL_*` settings.
  Intended or not, players on this instance cannot reset a password by email.
- **MariaDB startup warnings.** `Could not increase number of max_open_files to
  more than 16384 (request: 32190)` and an ignored `proxies_priv` entry under
  `--skip-name-resolve`. Neither has caused an error. Redis logged nothing.

## 9. Area-data notices

`logs/log/mob` repeats the same notices at every boot. They describe world
files, not the running server.

- **`_RIDICULOUS_ damage`** (58 lines, 22 mobs). Average damage is over the
  200 or 400 cap in `src/world/db.c:2704`; the line says no change is made. The
  largest are 142401 (100d100+63, a tailor in Voluntown), 51401 (10d100+160)
  and 48001 (10d50+110).
- **`extreme exp`** (10 lines, 8 mobs) for experience above 10,000,000:
  the five dragon wyrms 19710 to 19750 at 100,000,000, and 19700, 32637 and
  77734.
- **`M cmd not executed` / `F cmd not executed`** (about 300 and 3 to 5 a
  boot). These are zone loads with a percentage chance that did not roll. They
  are expected and vary run to run.
- **Coins in room 19953.** Shortly after every boot `debug` logs, twice, that
  "a pitiful slave" picked up 1,500 platinum from the room. Two piles load
  there and a scavenging mob takes them; pickups over 1,000 platinum are
  logged by design.

## Checked and clean

- **Stops.** All three restarts were operator stop and start, each with
  "Normal termination of game". No core files, and no error line in the unit
  journal.
- **Saves.** No save failure, retry or persistence alert in any log.
- **Tick time.** The worst tick in any latency window was 126 ms against a
  250 ms pulse.
- **Persistence start.** MariaDB and Redis connected first try on every boot.
