# Findings: clean rebuild and restart of staging, 2026-10-07

Written 2026-10-07 against `master` at `a7e43bd0a`, right after the pull from `baba13d99`
(36 commits: Phases 1 and 2 of the plan for #10, #11, #13, #14 and #17, whose last phase
landed on 2026-10-07 in `338092a78`, plus the documentation consolidation).
This is a working note. File each row of the findings table as a work item or dismiss it,
then delete the file.

## What was done

All times UTC. The host is the staging box; the MUD runs as the systemd user service
`duris-mud-production.service` (`cycle_mud.sh --production`, `ENVIRONMENT=production`).

| Time | Step | Result |
|---|---|---|
| before | Migration check | Nothing under `migrations/` changed in the pull, no DDL added under `src/`, no new `.env` keys. Ledger `applied_count=36` matches the manifest's 36 migrations; `verify_runtime_compatibility.sh` passed. Nothing to run. |
| 08:11 | Backup of what `make clean-all` deletes | `bin/server/dms` (sha256 `cdd61b5f…`), `.dms-backend`, `maintenance-scheduler.state` copied to `/home/staging/backups/duris/2026-10-07-prebuild/`. |
| 08:12 | `make clean-all` | 0.5 s. Removed all of `bin/`, `areas/world.*`, `lib/misc/lookup.*`. Worktree stayed clean. See finding 1. |
| 08:13 | `make build-editor world` | 32 s, no warnings. |
| 08:12–08:16 | `make -C src -j4 PERSISTENCE_BACKEND=mariadb BUILD_PROFILE=production` | 3 m 32 s, 466 translation units, 0 warnings under `-Werror`. Staged `bin/server/dms_new` sha256 `f292cacd…`, stamp `mariadb/production`. |
| 08:17:05 | `systemctl --user restart duris-mud-production.service` | Old process exited with "Normal termination of game." within a second (`shutdown_info.txt`: `Launcher|signal from launcher`). The launcher promoted `dms_new` to `dms`, the runtime schema gate passed, areas regenerated, "Boot completed in: 10059 milliseconds". Listeners on 74.208.126.44:7777 and :7778. `/proc/<pid>/exe` hashes to the build. |
| 08:19–08:20 | Scripted login with the `.env` test account | Account menu, character selection, `time`, `who`, `score`, `quit` to the menu. All rendered. |
| 08:22 | `make test TEST_JOBS=3` | Against a production-profile relink of `dms_new` (finding 2 says why). Results in finding 12. |

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

## Findings

| # | Severity | Finding | Evidence | Suggested action |
|---|---|---|---|---|
| 1 | Medium, operations | `make clean-all` deletes live runtime state. `.env` sets `MAINTENANCE_STATE_FILE=bin/server/maintenance-scheduler.state` and the code default is the same path (`src/net/comm.c:1036`). `clean-all` removes all of `bin/`, so the file and its directory vanished under the running server. `persist_state()` (`src/persistence/maintenance_scheduler.c:137`) writes `<path>.tmp` then `rename()`, which cannot succeed while the directory is missing, and nothing is logged. | Directory recreated by hand at 08:12:32 and the backup copied back; the server rewrote the file at 08:13:48. `RUNBOOK.md` already warns about this boundary. | Default and configure the state file outside `bin/` (`runtime/` already holds `CRITICAL_COMMAND_JOURNAL_DIR`), or exclude it from `clean-all`. Log a failed persist. |
| 2 | Medium, operations | A staged binary with the wrong stamp takes the service down. `scripts/cycle_mud.sh:240-247` exits 1 when `.dms_new-backend` is not `mariadb/production`, before promotion; with `Restart=always` the unit retries every 10 s and the valid runtime binary is never started. The regression suite hardcodes `bin/server/dms_new`, and `make` / `make build-server` default to the development profile, so running tests on this host stages exactly such a binary. | Not triggered today. The development profile only adds `-Og -DTEST_MUD`, and `TEST_MUD` gates one block in `src/cmd/actwiz.c:439`, so the suite was run against a production relink (3.6 s from cached objects, identical hash to the running binary). | Have the launcher skip and log a mismatched staged binary instead of exiting. Let the tests take the binary path from an environment variable. Document the production relink for test runs on this host. |
| 3 | Low, bug | `ssl_read_cert()` reports with `printf` to stdout (`src/net/ssl.c:82`); every other boot message uses stderr or `logit`. Under systemd stdout is a pipe and fully buffered, so the line surfaces only when the process exits. | The journal shows the 2026-10-05 boot-time read (`old_mtime=0.0`) stamped 08:17:06 at shutdown, attributed to the old pid. Misleading when checking a reload after `duris-certbot-renew`. | `logit(LOG_STATUS, …)` or `fprintf(stderr, …)`. |
| 4 | Low, logging | The stderr stream carries a stray carriage return just before the exit line, so journald stores "Normal termination of game." as `[54B blob data]`. `logit()` builds the line as `asctime::message\n` (`src/core/utility.c:871-877`) and copies `LOG_EXIT` lines to stderr (`:757`), so the `\r` comes from an earlier stderr write; the boot messages in `src/net/comm.c` end in `\r\n`. | Journal entry for pid 3538006 at 08:17:06, raw bytes `\rWed Oct  7 08:17:06 2026::Normal termination of game.` | End stderr writes with `\n` only, and strip leading `\r` from the console copy. |
| 5 | Low, content | A launcher-initiated shutdown writes "Launcher grabs Duris by the balls and rips them off." into `logs/log/status` (`src/cmd/actwiz.c:4424`). | Old run's status log, last lines. | Owner's call on the wording in an operator log. |
| 6 | Low, noise | The comm log still writes one `Losing descriptor without char […]` per connection that closes before login, plus `gnutls_handshake failed` lines from scanners. The pull removed the read-side EOF line; this close-side line remains. | 798 such lines on 2026-10-05 alone in the previous run; one more at 08:20:24 today when the test client closed at the account menu. | Rate-limit or demote to the debug log. |
| 7 | Low, world data | The mob log at every boot: 313 `M cmd not executed`, 4 `F cmd not executed`, 58 `FYI - no changes made to MOB: N has _RIDICULOUS_ damage`, and `extreme exp` for tiamat, aramus dreameater and aan huge dragon. | `logs/log/mob` after this boot; the same volume in the previous run. | Builders' backlog, not a server defect. |
| 8 | Low, permissions | `areas/make_lookup` writes `lib/misc/lookup.*` by shell redirection, so the files keep the mode of whoever created them. After the developer-shell `make world` they are 0644, and the launcher's regeneration under `UMask=0077` truncates in place without changing the mode. `areas/world.*` are 0600. | `ls -l lib/misc/lookup.mob` after the 08:17 boot: `-rw-r--r--`. | `umask 077` in `make_lookup`, or write through `install -m 600`. |
| 9 | Info, tracked as #14 | First event-budget window after boot: `deferring_pulses=20 deferred=92957 peak_catchup_debt=14974 max_late_ticks=3 max_late_name=event_memorize`. Second: `deferring_pulses=1 deferred=2566 max_late_ticks=1 max_late_name=event_move_regen`. Then silence (`src/world/new_events.c:1499` writes the line only when something deferred). | `logs/log/status` 08:18:34 and 08:19:49. | Boot catch-up is expected. Steady-state deferrals belong to work item #14 (Phase 4). |
| 10 | Info | Staging configuration lines at boot, all expected: `MAIL_ENABLED` not TRUE (account recovery by email disabled), `TELEMETRY_ENABLED` unset (`telemetry_health … state=disabled`), `DURIS_WEBSOCKET=FALSE` (no `/health` listener, so `scripts/healthcheck.sh` fails here by design), `REDIS_WORLD_STATE=FALSE` (no recovery line expected), no `areas/world.trg` (STUDIOPROC idle). | `logs/log/status` 08:17:10–08:17:19. | None. |
| 11 | Info | Promotion archived no previous binary into `bin/server/history/` because `clean-all` had already removed `bin/server/dms`. The pre-clean executable, stamp and scheduler state are in `/home/staging/backups/duris/2026-10-07-prebuild/`. | `bin/server/history/` empty after the restart. | Keep the backup until the next successful restart, then delete it. |
| 12 | Verified | `make test TEST_JOBS=3`: 671 passed, 0 failed in 1202 s (20 m 03 s wall, 52 m CPU), then `run_signal_handlers.sh` passed; exit 0. `test_compiler_warning_profile.py` passed against this build. Slowest: `test_flatfile_newbie_regrant_journey.py` 309 s, `test_game_loop_session_journey.py` 248 s. | Log in the session scratchpad; `bin/tests/` holds the artifacts. The binary under test was the production relink (same hash as the running server), see finding 2. | None. |
| 13 | Info, operations | Running the regression suite on the same host perturbs the live game loop. With three test workers the load average rose above 6 on 8 cores and the server logged deferral windows that were absent while the host was quiet. | No `NEVENT BUDGET WINDOW` between 08:20 and 08:27. During the suite: 08:27:20 `deferring_pulses=8 deferred=9753`, 08:28:35 `deferring_pulses=6 deferred=4259`, 08:38:36 `deferring_pulses=4 deferred=2687`, and six single-pulse windows of 168–917 deferred callbacks, all `max_late_ticks=1`. Server CPU itself stayed at 3–8%; the previous binary showed `catchup_debt` of 1,300–2,400 every window with an idle host, so a few hundred deferrals a window is also the normal baseline (work item #14). | Run the suite on a build host, or keep `TEST_JOBS` low here and expect one-tick late events while it runs. |

## Follow-ups

- Findings 1 and 2 are the ones worth a decision: each is a one-line configuration or
  launcher change plus a sentence in `RUNBOOK.md`.
- Findings 3, 4 and 8 fit one small log-and-permissions hygiene branch.
- Findings 6 and 7 are backlog.
