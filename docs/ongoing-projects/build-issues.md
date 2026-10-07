# Record: clean rebuild and restart of staging, 2026-10-07

Written 2026-10-07 against `master` at `a7e43bd0a`, right after the pull from `baba13d99`
(36 commits: Phases 1 and 2 of the plan for #10, #11, #13, #14 and #17, whose last phase
landed on 2026-10-07 in `338092a78`, plus the documentation consolidation).
This is a working note: what the rebuild did and what the restart verified. Its findings
are in [build-findings.md](build-findings.md), the mob-log finding in
[world-data.md](world-data.md). Delete the file with them.

## What was done

All times UTC. The host is the staging box; the MUD runs as the systemd user service
`duris-mud-production.service` (`cycle_mud.sh --production`, `ENVIRONMENT=production`).

| Time | Step | Result |
|---|---|---|
| before | Migration check | Nothing under `migrations/` changed in the pull, no DDL added under `src/`, no new `.env` keys. Ledger `applied_count=36` matches the manifest's 36 migrations; `verify_runtime_compatibility.sh` passed. Nothing to run. |
| 08:11 | Backup of what `make clean-all` deletes | `bin/server/dms` (sha256 `cdd61b5f…`), `.dms-backend`, `maintenance-scheduler.state` copied to `/home/staging/backups/duris/2026-10-07-prebuild/`. |
| 08:12 | `make clean-all` | 0.5 s. Removed all of `bin/`, `areas/world.*`, `lib/misc/lookup.*`. Worktree stayed clean. See [finding 1](build-findings.md). |
| 08:13 | `make build-editor world` | 32 s, no warnings. |
| 08:12–08:16 | `make -C src -j4 PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production` | 3 m 32 s, 466 translation units, 0 warnings under `-Werror`. Staged `bin/server/dms_new` sha256 `f292cacd…`, stamp `mariadb/production`. |
| 08:17:05 | `systemctl --user restart duris-mud-production.service` | Old process exited with "Normal termination of game." within a second (`shutdown_info.txt`: `Launcher|signal from launcher`). The launcher promoted `dms_new` to `dms`, the runtime schema gate passed, areas regenerated, "Boot completed in: 10059 milliseconds". Listeners on 74.208.126.44:7777 and :7778. `/proc/<pid>/exe` hashes to the build. |
| 08:19–08:20 | Scripted login with the `.env` test account | Account menu, character selection, `time`, `who`, `score`, `quit` to the menu. All rendered. |
| 08:22 | `make test TEST_JOBS=3` | Against a production-profile relink of `dms_new` ([finding 2](build-findings.md) says why). Results in [finding 12](build-findings.md). |

## Verified at runtime

- The pull's log fixes hold: `get_mud_info(): requested mud_info 'lock'` (5 in the previous
  run) and `sql_world_quest_can_do_another: history not loaded yet` (4) have not reappeared;
  the `sql_save_dirty_shopkeepers: saved N` line (34) is gone.
- `time` prints `Current time is: Wed Oct  7 08:20:18 2026 (UTC)`. The quit line is
  `Veridian has quit in [22800].` with no `EST` stamp.
- `score` showed `Bartender Quests Remaining: 2` immediately after entering.
- The `NEVENT BUDGET` + two `NEVENT CATCHUP` lines every 75 s (144 an hour) are replaced by
  one `NEVENT BUDGET WINDOW` line, written only when something deferred.
- Status log volume: about 1,500 lines an hour before the restart; about one line a minute
  (zone resets) after boot.
- Boot 10.1 s (9.5 s before). RSS 387 MB (415 MB before). 13,458 callback names loaded with
  594 duplicate addresses, the same duplicate count as the previous binary.

