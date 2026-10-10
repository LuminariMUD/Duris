# Plan: the 2026-10-09 log review's fixes, seven test-quality additions, MariaDB 11.8 and the slow tick and boot

Written 2026-10-09 against `master` at `24e7d3fba`. It holds the open work of two working
notes it replaces: the 2026-10-09 log review (Part 1, items 1 to 9) and the test-quality
proposals (Part 2, items 10 to 16). Both notes were deleted when their work was written here;
their last versions are at `24e7d3fba`, where
`docs/ongoing-projects/log-review-2026-10-09.md` also records what the review read and what
it found expected or benign. Part 3 (item 17) was added the same day: the staging host's
upgrade to MariaDB 11.8, found during the tick and boot investigation, stops a new database
from being built. Part 4 (items 18 and 19) was added the same day from a third working note,
the investigations of the review's two performance findings, deleted when their fixes were
written here; its last version is at `dd1c33842`. Each item holds the problem, the evidence,
the change and when it is done. The order and the decisions were proposed; on 2026-10-09 the
owner had the whole plan built at once as stacked pull requests, so the decisions were taken
as written and the order is the stack's (below). This file is a working note: delete it when
the last item lands.

Kept apart, in its own working note:
[staging-host-follow-ups.md](staging-host-follow-ups.md), the host owner's work left from the
review and the host's 26.04 upgrade (SSH, a GitHub token, backups).

[ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md) is the decision record for
items 3, 8 and 9.

## Stack

Built from 2026-10-09 (night) in the worktree `/home/aiwithapex/projects/duris-plan`, one
branch per pull request, each based on the one below it, so each pull request's diff is its
own items. The first targets `master`; when one lands, the next is retargeted to `master`
before its base branch is deleted (`gh pr edit <n> --base master`). Each head that goes up
for review is tagged `issue-14/<subject>-review-0` (lightweight); a review round's fixed head
gets `-review-1`, and so on. A fix to a lower branch after the ones above it exist goes on
that branch as a new commit, and the branches above take it by merge, never by rebase once
pushed. Every branch also carries this file: its Status table and Stack table say what is
built at that branch's head.

| PR | Branch | Items | State |
|---|---|---|---|
| 1 | `fix/14-privacy` | 9, 8, 3 (ADR 0003's code) | Built |
| 2 | `fix/14-log-fixes` | 6, 1, 2, 7, 4, 5 | Built |
| 3 | `fix/14-mariadb-11.8` | 17 | Built |
| 4 | `fix/14-boot-scan` | 19 | Built |
| 5 | `fix/14-tick-spikes` | 18 | Built |
| 6 | `fix/14-test-tools` | 10, 14, 16 | Built |
| 7 | `fix/14-test-stability` | 11 | Built |
| 8 | `fix/14-clang-tidy` | 13 | Built |
| 9 | `fix/14-fuzz` | 12 | Not started |
| 10 | `fix/14-mutation` | 15 | Not started |

Parts 3 and 4 sit below Part 2 because they matter more and change less: Part 3 has to land
before a database is next built on MariaDB 11.8. Part 2 keeps its own order: 10 and 14 (and
16, which is independent) first, then 11, then 13, then 12, which uses 11's shared stubs, and
15.

How each pull request is checked: the focused tests of its items, `./scripts/format.sh
--check`, a flat-file build, then `make test-all` and `make test-db` on its head in a
throwaway worktree (`git worktree add --detach ../duris-plan-gate <sha>`, removed after),
so the checkout can move on while the gate runs.

## Status

Part 1, the log review's fixes:

| # | Item | Severity | State |
|---|---|---|---|
| 1 | `server_reboots` records one of ten restarts: a service stop kills the launcher before it writes | Low | Built (PR 2) |
| 2 | Plain HTTP requests to `ws.duris.sbs` reach the MUD's WebSocket port and get a tunnel error | Low | Built (PR 2) |
| 3 | `lib/etc/hosts` keeps every client's address and reverse-DNS name, and nothing prunes it | Low | Built (PR 1) |
| 4 | Nine shops ask for a buy rate the loader clamps at every boot | Low | Built (PR 2) |
| 5 | `logs/boot.log` is stale since 2026-10-04 and nothing writes it | Low | Done (staging, 2026-10-10) |
| 6 | `cmd.debug` never records a one-letter command, and records stale text for an empty line | Low | Built (PR 2) |
| 7 | Wizard broadcasts go into `status` raw, a lost peer's host is a color code, and zone-command lines print internal indices | Low | Built (PR 2) |
| 8 | `snoop` never tells its target, and nothing ages out players' addresses | Low | Built (PR 1) |
| 9 | Any immortal can read a player's last 200 private messages with `recall` | Medium | Built (PR 1) |

Part 2, test quality:

| # | Item | Gate time | State |
|---|---|---|---|
| 10 | Prove a regression test fails without its fix | none | Built (PR 6) |
| 11 | Make tests break only when behaviour breaks | same or less | Built (PR 7) |
| 12 | Fuzz the code that reads outside input | one replay test | Proposed |
| 13 | `clang-tidy` on changed lines | none (commit hook) | Built (PR 8) |
| 14 | Keep a history of test runs | none | Built (PR 6) |
| 15 | Mutation testing, by hand | none | Proposed |
| 16 | Line coverage, on demand | none (by hand) | Built (PR 6) |

Part 3, database engine support:

| # | Item | Severity | State |
|---|---|---|---|
| 17 | A new database cannot be built on MariaDB 11.8: migrations 0031 and 0032 know only MariaDB 10.11 and MySQL 8.0 | Medium | Built (PR 3); staging upgraded |

Part 4, the slow tick and the slower boot:

| # | Item | Severity | State |
|---|---|---|---|
| 18 | Every tick, `affect_update` walks all ~56,000 mobs (40 to 140 ms on staging), and the events it queues land on pulses 0, 10 and 20, where the event pass goes over its budget | Low | Built (PR 5) |
| 19 | Most of every boot is one shopkeeper scan in the zone resets (7.4 billion comparisons, about 8 s of staging's 12 s); its loop's placement across a cache line made it 2 s slower on 2026-10-08 | Low | Built (PR 4) |

## Order (proposed)

The parts touch different files and can go side by side, except where noted below.

- **Part 1:** 9 first, the one Medium item, decided and small; then 8 with 3, the rest of
  ADR 0003's code; then 6, which loses the moves before a crash; then 1, 2, 7, 4 and 5.
- **Part 2:** 10, 11 and 14 first, because they are cheap and address the breakages already
  seen; then 13; then 12 and 15, which look for bugs nobody has reported. 16 depends on
  nothing and can land at any point. 12 uses 11's shared stubs, so 11 comes first.
- **Part 3:** 17 touches only the migration runner, the manifest, two new verifier files and
  a test leg, so it can go beside either part. It has to land before a database is next built
  on staging, and before production moves to Ubuntu 26.04.
- **Part 4:** 18's changes 1 to 3 and 19's change 1 first, because they are small and change
  nothing a player sees; then 19's change 2; then 18's change 4, the largest. 19 changes
  `reset_zone()` in `src/world/db.c`, where item 7 changes the `cmd not executed` lines, so
  whichever lands second rebases onto the other.

## Decisions

Items 8 and 9 were decided by the owner on 2026-10-09 in ADR 0003. The rest are proposed:

| # | Decision | Item |
|---|---|---|
| 1 | A plain GET is answered by the MUD's WebSocket listener, not routed away at the tunnel: the tunnel's configuration lives on the host, outside this repository. | 2 |
| 2 | The stale `logs/boot.log` is deleted rather than written: the journal already holds the boot's stderr. | 5 |
| 3 | Item 10 reports; it does not block a landing. | 10 |
| 4 | Item 13's hook refuses a commit with a new finding on a changed line, as the format hook does. | 13 |
| 5 | Item 12's long runs are by hand; no scheduled workflow. | 12 |
| 6 | Item 16 runs only when a developer asks for it, and its percentage is never a target. | 16 |
| 7 | MariaDB 11.8 becomes a supported engine beside MariaDB 10.11 and MySQL 8.0, and the sealed files of 0031 and 0032 stay as they are, so no existing history changes. | 17 |

---

## Part 1: the log review's fixes

The review read the staging host's logs from its first boot (2026-10-04 22:11 UTC) to the
rebuild at 09:01 on 2026-10-09: the server logs and their archives in `logs/old-logs/`, the
user journal of the MUD, MariaDB, Redis, cloudflared and DurisWeb units, `runtime/`, the
`server_reboots` table, and the MariaDB and Redis status counters. Times are UTC. The service
never crashed in that time.

### 1. `server_reboots` records one restart in ten

**Problem.** The launcher writes the row after `dms` exits (`scripts/cycle_mud.sh` L419-464). A
`systemctl --user restart` or `stop` signals the whole control group
(`KillMode=control-group`), so the launcher dies with the server and never writes. The
journal has one `Logged reboot` line in nine boots: the in-game reboot at 03:50 on 10-09.
The table has the same one row. The rebuild's `systemctl --user stop` at 09:01 on 10-09 added
no row either. Separately, the insert interpolates the shutdown reason into SQL between single
quotes and sends errors to `/dev/null` (L455-463), so a reason with an apostrophe drops its row
without a word.

**The change.** `KillMode=mixed` alone is not the fix: it sends SIGTERM only to the unit's main
process, the launcher, which has no `trap`, so the launcher would die at once and `dms` would
run on until systemd kills it, unsaved. The launcher needs to run `dms` in the background,
`wait` on it, and `trap` SIGTERM to forward it to `dms` (L395 starts it in the foreground,
and `dms` already shuts down cleanly on SIGTERM, `src/core/signals.c` L121). After `dms`
exits, the launcher writes the row and exits without relaunching. Then `KillMode=mixed` in
`deploy/systemd/duris-mud-production.service.in` and the installed unit lets it do so. Pass
the reason as data (for example hex-encoded into `UNHEX()`), not inside the SQL.

**Done when** a service stop and a restart each shut `dms` down cleanly and leave one row, a
reason with an apostrophe is recorded, and a regression test covers both.

**Built** (PR 2). `scripts/cycle_mud.sh` runs the server in the background, traps TERM, INT
and HUP to pass them on, and waits until the server has exited (`wait` returns early when a
trapped signal arrives). After a stop it writes the row and leaves the loop at once, with no
ten-second pause, so the post-loop steps (a pwipe's wipe, the email) still run. The issuer
and reason go in as `CONVERT(UNHEX(...) USING utf8mb4)`, and a failed insert prints an error
instead of the old unconditional "Logged reboot". The unit template has `KillMode=mixed`.
`tests/async/run_launcher_stop_journey.py` (in `make test-db`) runs the real launcher with a
stand-in server on MariaDB and sends SIGTERM to the launcher alone, twice.

Left for the deploy: staging's unit is written by hand
(`~/.config/systemd/user/duris-mud-production.service`, `KillMode=control-group`). Set
`KillMode=mixed` there and run `systemctl --user daemon-reload` in the same step that
deploys this launcher, never before: the old launcher has no trap, so with `mixed` it would
die at once and leave the server running until `TimeoutStopSec` kills it unsaved.

**Review round 1** (2026-10-10, #16's adversarial review): a stop that landed after the
server's fork and before `SERVER_PID=$!` ran the trap with the last run's PID, so the new
server was never told and systemd killed it unsaved. `SERVER_PID` is cleared before the
trap, the trap signals only a known PID, and the flag is checked once the PID is set
(`39dc1e0e3`); `test_flatfile_launcher.py` runs the launch block with the launcher
signalling itself in that window.

### 2. Plain HTTP to `ws.duris.sbs` gets a tunnel error

**Problem.** cloudflared logged `Unable to reach the origin service ... EOF` for
`https://ws.duris.sbs/robots.txt` at 2026-10-09 05:28:35. It logged the same for `/` twice
at 2026-10-08 18:00:07. Each lines up with a `Losing descriptor without char
[host=127.0.0.1 ... connected=18]` in the MUD's debug log, and a `lib/etc/hosts/*.127.0.0.1`
file of the same minute. The WebSocket listener (4050) drops a request without an
upgrade, so crawlers get a Cloudflare error page.

**The change.** Answer a plain GET on the WebSocket port with a short HTTP response, and
`robots.txt` with `Disallow: /` (decision 1). The other way, routing only upgrade requests to
4050 at the tunnel, is a change to the host's tunnel configuration.

**Done when** a plain GET and a GET of `/robots.txt` get their responses, an upgrade still
connects, and a regression test sends all three.

**Built** (PR 2). A GET with neither the upgrade nor the WebSocket header gets `426 Upgrade
Required` (with `Upgrade: websocket`), and `GET /robots.txt` gets `200` with `User-agent: *`
and `Disallow: /`; the connection closes after either, as after `/health`. A banned address
still gets its `403` first. The three HTTP answers share one function. Tested in
`tests/async/websocket_runtime_harness.cpp`, whose first case is a real upgrade.

### 3. `lib/etc/hosts` keeps every client's address and name

**Problem.** `hostname_lookup_worker()` and `resolve_descriptor_hostname_async()`
(`src/net/comm.c` L3638-3725) write one file per descriptor number and address,
`lib/etc/hosts/<desc>.<address>`, holding the reverse-DNS name. It removes the file only before
the same pair is looked up again; nothing else does, in `src/`, `scripts/` or the launcher.
The directory had 139 files from 2026-10-04 on, most of them scanners, and 140 at the recheck.
Players' addresses stay there indefinitely, against the 30-day limit of ADR 0003.

**The change.** Clear the directory at boot, and remove a descriptor's file when it closes (a
lookup can finish after the close, so the boot clear is still needed).

**Done when** both are in the code and a regression test shows the boot clear and the removal
on close.

**Built** (PR 1). `remove_hostname_files()` in `src/net/comm.c` runs at a cold boot (not a
copyover, whose descriptors stay open) and in `close_socket()`, where it removes every
`<descriptor>.*` file: a WebSocket connection is looked up twice, under the proxy's address
and then the client's. The unlink before each lookup is gone; the close made it redundant.
`tests/async/test_hostname_files_journey.py` boots a flat-file server over stale files,
connects and disconnects.

### 4. Nine shops ask for a buy rate the loader clamps

**Problem.** At every boot the shop loader caps a buy rate above 0.8 and logs `Shop #N: Old
buy/sell` (`src/economy/shop.c` L2383-2424) for shops 31310, 47061, 47070, 47097, 47116, 59081
and 59097 (1.0 to 0.8), and 89091 and 89118 (0.9 to 0.8). The 09:01 boot logs the same nine.

**The change.** Set those rates to 0.8 in the shop files under `areas/shp/`, so that the boot
log carries nothing.

**Done when** a boot logs no `Old buy/sell` line.

**Built** (PR 2). The nine buy rates in `areas/shp/{dream,vehicles,ravenloft2,newhope}.shp`
are `0.80`; each shop's sell rate stays above it, so the loader changes nothing.
`tests/async/test_flatfile_full_world_boot.py` fails on any `Old buy/sell` line in its debug
log.

### 5. `logs/boot.log` is stale

**Problem.** `logs/boot.log` is dated 2026-10-04 22:05. Nothing in `scripts/` or `src/` writes
it, and the boot's stderr goes to the journal. It shows 15 `Recalculating zone numbers`
warnings ("Heaven has invalid number: 1 (should be 0)" and others). Neither the 03:50 boot
nor the 09:01 boot prints them, so the file misleads anyone who reads it.

**The change.** Delete it (decision 2), or have the launcher write the boot's stderr there.

**Done when** no `logs/boot.log` older than the last boot is left on the host.

**Done** (2026-10-10). Deleted on staging (`~/duris/logs/boot.log`, 2,940 bytes, dated
2026-10-04 22:05; the service had last started at 13:04 on 2026-10-09). Nothing in
`scripts/` or `src/` writes the file; `.gitignore` still lists it. Also seen there:
`logs/shutdown_info.txt` of the 12:33 stop during the OS upgrade, which item 1's defect left
unread. The next stop's server overwrites it, so it was left.

### 6. `cmd.debug` misses one-letter commands

**Problem.** `cmdlog()` records a command only when `*(str + 1) != '\0'` (`src/core/debug.c`
L163). A one-letter command (`n`, `s`, `k`) is never recorded. An empty line reads the byte
past the terminator, which is stale buffer content, and records a blank or stale entry. The
12:11-03:50 run has 11 such blank lines (`[1042] Bogum in 591075: `). `cmd.debug` holds the
last 500 commands for crash forensics (`src/core/signals.c` L77), so the moves before a crash
are the part it loses.

**The change.** Test `*str != '\0'`.

**Done when** `tests/async/test_command_log_ring.py`, which runs the real `cmdlog()`, records a
one-letter command and nothing for an empty line.

**Built** (PR 2), as written; the test also checks a two-word command after them.

### 7. Three log-hygiene defects

- Each timed shutdown, reboot or copyover writes its broadcast to `status` as players see it,
  with `\r\n` and color codes (`src/cmd/actwiz.c` L4430, L4440, L4451). The `status` of
  the 12:11-03:50 run ends with an empty `::` line, then `Zusuk shreds the world
  around you.` on a line of its own. Log the issuer and the kind instead.
- When `getpeername()` fails in `new_descriptor()`, the host is set to `&+RUNTRACEABLE&n`
  (`src/net/comm.c` L3843-3846), and the color code goes into every log line about that
  descriptor. This happened twice, on 2026-10-08 at 18:43:23 and 18:46:15, both with a
  `Connection reset by peer`. Use a plain `unknown`.
- `M cmd not executed`, `F cmd not executed` and `R cmd not executed` (`src/world/db.c`
  L3544, L3904, L3954) print the zone command's arguments after the boot has turned them into
  internal indices, so the mob and room numbers match no vnum and a builder cannot use the
  line. Log the vnums. The lines themselves are expected: a load under 100% is rolled only by
  the boot's forced reset, and `RUNBOOK.md`'s known-benign table says so.

**Done when** all three are fixed, each with a regression test.
`tests/async/test_boot_log_hygiene.py` pins `src/net/comm.c` in places; read its contracts
before moving anything there.

**Built** (PR 2).

- `timedShutdown()` logs `<kind> by <issuer>: <reason>` to the status log through
  `log_shutdown()` (kinds: Shutdown, Reboot, Copyover, Auto-reboot, Auto-reboot with
  copyover); the players' broadcast is unchanged. Codex, on the round's push: its wiz row
  was never written, because the countdown and a signal run it with no character (as
  before). The issuer's wiz row is written when the shutdown is scheduled, and launcher
  stops are in `server_reboots`, so the dead call is gone and these notes say "status log".
- A failed `getpeername()` gives the host `unknown`; the `strip_ansi()` around the lookup's
  address went with the color code.
- `M`, `F` and `R cmd not executed` print `mob <vnum> in room <vnum>, limit <n>, chance
  <n>%`.

One journey covers all three, `tests/async/test_log_hygiene_journey.py`: a flat-file server
with zero-chance `M`, `F` and `R` commands, a connection reset before the server accepts it
(Linux hands it over, and `getpeername()` then fails, as on staging), and a SIGTERM stop.
`test_boot_log_hygiene.py`'s pins on `comm.c` still hold.

**Review round 1** (2026-10-10, #16's adversarial review): an old bug in the block this item
edits. An `R` that missed its roll after an `M` that loaded its rider kept `last_mob` and
went on with a NULL mount, a crash in the zone pass; none of the shipped `R` lines is below
100%. The guard now also needs the mount (`1a8731b80`), and the journey's zone has that
case.

### 8. `snoop` never tells its target, and nothing ages out players' addresses

**Problem.** Decided on 2026-10-09 in ADR 0003, whose logging rule is in the code. Two parts
are not:

- `snoop` needs level 60, but `do_snoop()` (`src/cmd/actwiz.c`) tells the target only when
  the snooper is below 58 or 59, so no target is ever told. It audits a snoop only below
  level 61. The decision: tell the target on start and stop, allow a silent snoop
  (`snoop <name> silent <reason>`) only at level 62 with a stated reason, and audit every
  snoop at every level: who, whom, start, stop, whether it was silent, and the reason.
- Addresses are kept with no limit: `player-log/new` records each new character's, the log
  archives hold them in `comm` and `debug`, `lib/etc/hosts` keeps them (item 3), and so
  do `log_entries`, `account_ips`, `account_login_history`, `ip_info` and the `last_ip`
  columns of `player_data` and `account_characters`. The launcher drops the oldest archive
  past `LOG_ARCHIVE_LIMIT_MB` (`scripts/cycle_mud.sh` L309-312), which caps the size, not the
  age. The decision: 30 days, except an address on the ban list, kept while its ban stands;
  nothing is kept past the 30 days to recognize a returning player, not even a hashed or
  truncated address.

**The change**, as ADR 0003's Consequences list it:

- Rework `do_snoop()` as decided, with the target's notice and the audit row.
- Cap the log archives at 30 days of age in `scripts/cycle_mud.sh`, on top of the size cap.
  That also limits the petition and newbie-channel logs to 30 days; keeping them longer means
  storing them apart from the logs that hold addresses.
- Clear `lib/etc/hosts` (item 3).
- Add a daily database prune that deletes address rows older than 30 days and blanks older
  `last_ip` values, leaving the ban list alone.
- Update with the code: the in-game `snoop` help entry and the privacy lines of the
  `COMMUNICATIONS UTILITIES CHANNELS` entry in `lib/information/help_index`; the personal
  data inventory in `docs/records/SECURITY-COMPLIANCE.md`; the `log_entries`, `account_ips`,
  `account_login_history` and `ip_info` entries in `migrations/data_lifecycle_manifest.json`;
  and ADR 0003's status line.

Until the 30-day limit holds, treat a copy of `logs/` as player data. The same 30-day rule
applies to the addresses in DurisWeb's tables; that work belongs to the DurisWeb repository.

**Done when** the changes are in, with regression tests that a snoop at each level notifies
and audits as decided and that the prune removes exactly the expired rows.

**Built** (PR 1); ADR 0003's Consequences list what is in the code. Where it differs from the
change above:

- Every way a snoop ends goes through two functions in `src/cmd/actwiz.c`:
  `stop_snooping()` (the snooper stops, moves to another target, quits, loses its link or
  leaves the game) and `end_snoops_on()` (the target leaves, switches or unmorphs). They
  replace five copies of the list handling, and fix one defect on the way:
  `extract_char()` removed an immortal snooper's entry from its target's list only below
  level 58, because a commented-out statement left the removal as the `if`'s body.
- `snoop_data` gained `by_command` and `silent`: the channel spell's shared sight uses the
  same lists, and is neither told nor audited.
- The prune is a maintenance job, `address_retention`, hourly rather than daily: the
  scheduler's offsets are per boot, so a daily slot could miss a server that restarts every
  day. Its state file went to version 4 (13 jobs); versions 2 and 3 still load.
- The account address list was rewritten with the save's time at every login, so an
  account that logs in monthly would never age out an address. Each address now keeps its
  last use, written to `account_ips.updated_at`, and a login drops one past 30 days.
- `finger` shows an address only from a login in the last 30 days, since the server's copy
  of `ip_info` is read at boot.
- `account_login_history` is a website table the migrations do not create; the prune
  clears it when it exists. It has no manifest entry, so three entries, not four, carry the
  ADR's reference. The `last_ip` columns are in the `player_data` and `account_characters`
  entries, whose other data stays pending.
- The flat-file backend's account address lists and IP activity files are not pruned; no
  deployment runs it.
- Tests: `tests/async/test_snoop_and_recall.py` (the real `do_snoop()` and `do_recall()`
  under ASan and UBSan), `run_address_retention_journey.py` (in `make test-db`: a MariaDB
  login, then the job with and without the website table and with a row budget of one),
  `test_log_retention.py` (the log files), `test_hostname_lookup_cancel.py` (a lookup that
  outlives its connection) and `test_maintenance_scheduler.py` (state files of versions 2
  and 3).

**Review round 1** (2026-10-10, #15's adversarial review and Codex's), one commit each:

- A god switched into a mob snoops as itself (`interp.c` runs its Imm commands as
  `desc->original`), but `stop_snooping()` removed the mob from the target's list. The
  snoop went on while its target was told it had ended, the entry outlived the god (a
  use-after-free once the god quit), and the stop's audit row went to the mob, which
  `sql_log()` skips. Both now use the body the snoop is registered under (`beec88c58`).
- `who <name>` showed a silent snooper to its target when that target was a level 61; it
  now shows one only to level 62 (`ce0dbc837`). `users` already did.
- A reverse-DNS lookup that answered after its connection closed wrote its file back. The
  close now cancels the descriptor's lookups under their mutex and also removes a temporary
  file a copyover cut short (`d07a75095`).
- The launcher's 30-day step ran only between launcher passes, and by the archive's age: a
  server kept up by copyovers never archived or pruned its logs, a 40-day run's first lines
  lived 70 days, and `core.*` dumps were never removed. The hourly `address_retention` job
  now moves the live logs into `logs/old-logs/<date>/` once they are a day old and removes
  each archived file and core dump 28 days after its last write (Codex, on the round's
  push: 30 days after the last line kept a day-long file's first lines 31 days). A live set
  without its marker, as after a copyover onto this code, may hold lines of any age, so it
  moves at the next run, and the launcher marks each new set (Codex's next review); the
  launcher keeps only
  its archive at each start and the size cap (`eb496c0b0`).
- Codex, on the round's push: a snooped player who came back from a shapechange was told
  the start but never the stop, and the row named the shapechanged body. `un_morph()` now
  ends the snoops after the link is the player's again, retargeted to the player, and tells
  the target; `do_switch()` tells it too (`end_snoops_on()` gained the flag).
- Not changed: `player_data.last_ip` clears 30 days after the last save, not the login. The
  address is in use for the whole session and every save writes it back from memory, so a
  clear during the session would not hold; a mortal idle 15 minutes is voided anyway.

### 9. Any immortal can read a player's last 200 private messages with `recall`

**Problem.** Each player keeps their last 200 private messages in memory (`PRIVATE_LOG_SIZE`,
`src/player/player_log.h`) for their own `recall` command. `do_recall()`
(`src/cmd/actinf.c` L10021) lets any immortal add a player's name (L10030,
`if (*argument && IS_TRUSTED(ch))`) and read that player's instead, while the player is
online. The player is not told and nothing audits it. Nothing reaches disk, so it is not
logging, but it is a silent look at tells, against the rule of ADR 0003.

**Decision** (owner, 2026-10-09): `recall <n> <player>` returns at once with "Disabled by
Zusuk October 9 2026". A player's own `recall` is unchanged. ADR 0003 records it with the
snoop rules.

**The change.** The early return in that branch.

**Done when** it is in, with a regression test that an immortal's `recall` on another player
gets the message and reads nothing.

**Built** (PR 1). The branch that read another player's log is gone, so `do_recall()` reads
only the caller's; a mortal's extra word is still ignored. `help recall` says the gods
cannot read them. Tested in `tests/async/test_snoop_and_recall.py`.

### Found in the same logs, for other projects

Not this repository's work; listed so that it is handed on:

- **DurisWeb.**
  - It logs the in-game reboot as `[MUD] MUD process crashed (not running)`, and logs
    `ECONNREFUSED 127.0.0.1:4050` while the MUD is down. The 09:01 service stop logged only
    three `ECONNREFUSED` lines.
  - It warns `[MUD Auction] Ignoring pre-authentication message: system` once each time it
    connects to the MUD: 11 times from 2026-10-08 12:03 to 2026-10-09 09:02. The MUD sends a
    `system` message before the service authenticates.
  - A graceful stop took 25 s, against `TimeoutStopSec=30s`.
- **The host's owner.**
  - `krynn-live.service` has been failed since 2026-10-01 06:31 (`Result: resources`, a
    minute after an ImageMagick upgrade). Krynn runs outside systemd.
  - 20 packages can be upgraded, none from the security pocket.
  - Codex's app server cannot start its sandbox: bubblewrap needs user namespaces.
    Copilot Chat falls back to an in-memory database every session.

---

## Part 2: test quality, seven additions that keep the gate's time

Proposed 2026-10-09 against `master` at `d6fe4c210`; the numbers below were counted on that
commit. The additions raise what the tests prove without making `make test-all` or
`make test-db` slower: anything slow runs outside the gate.

### Where the suite stands

- `tests/async/` holds 690 Python tests, 118 `.cpp` and 23 `.cc` harness sources. 72 tests
  boot a real server, about 300 compile server sources into a native harness, and 77 more
  use a database.
- 437 tests read the C sources as text; 193 of them do nothing else: no build, no boot, no
  database. 129 tests pin an exact count or hash.
- 128 test files build with `-fsanitize`, almost all with `address,undefined`. The server
  builds with `-Wall -Wextra -Wpedantic -Werror`, and CodeQL (`c-cpp`) runs in
  `.github/workflows/security.yml`.
- There is no fuzz target, no `clang-tidy` or `cppcheck` run, no coverage build and no
  record of past test runs. `clang` 18, `clang-tidy`, `clang-tidy-diff`, `ccache`,
  `valgrind`, `gcov` and `gcovr` 8.6 are installed locally.
- Since 2026-09-01, 158 of 1,319 non-merge commits changed only tests; since 2026-10-01, 39
  of 437. Most of them fixed a test, not the server: a pinned count (`426bb5557`), a missing
  harness stub (`119dda91e`, `ad529fd16`), or a journey wait (`9cd0ef332`, `2bc212690`,
  `69dbf4886`, `105dc9092`).

### 10. Prove a regression test fails without its fix

**Problem.** Nothing checks that a new regression test fails on the code before its fix. A
test that passes on the broken code proves nothing, and in the gate it looks the same as one
that works. Today this is checked only by hand, with a variant build under `bin/analysis/`.

**The change.** `scripts/check_tests_catch.sh BASE HEAD`. For each `tests/async/test_*.py`
the range adds or changes, when the range also changes `src/`, it:

1. creates a detached worktree of `BASE` under `bin/analysis/catch-<sha>/`;
2. copies in `HEAD`'s version of every file the range changed under `tests/` (the test and
   any helper or harness it uses);
3. runs each test there and reports it: a failure means the test catches the bug, a pass
   means it does not;
4. removes the worktree.

Tests find `src/` from their own location (`_paths.ROOT`), so a test copied into the `BASE`
worktree tests `BASE`'s sources. A journey in the range builds a server in the worktree,
about three minutes, outside the gate.

It reports and does not block (decision 3): a test reshaped by a refactor passes on `BASE` and
is still right. The reviewer reads the report; the landing commit message records it.

**Steps.** Write the script. Check it on a fix, such as `932421560` (a board file kept whole
across a failed save), whose `test_boards.py` must fail on the parent, and on a refactor
commit, whose test passes. Add a paragraph to "Before a merge" in `docs/guides/TESTING.md`.

**Done when** the script exists, it reports both checks correctly, and `TESTING.md` says
when to run it.

**Built** (PR 6). `scripts/check_tests_catch.sh BASE [HEAD]` as described; it checks out
`HEAD`'s version of every file the range changed under `tests/`, runs each test the range
adds or changes on `BASE`'s sources, and says "catches" or "does not catch".

- On `932421560` (a board file kept whole across a failed save) `test_boards.py` catches:
  it fails on the parent.
- On `28a19a882` (the board of IDEAS given back its `board_info[]` row) it does not catch:
  the test checked that every row names a board, which cannot notice a row the fix restored.
  That was a gap, not a refactor, so `test_boards.py` now asks for row 42 as well
  (`940c53998`).
- `TESTING.md`'s "Before a merge" says to run it on a fix's range and record the report in
  the landing commit.

**Review round 1** (2026-10-10, #20's adversarial review and Codex's): the script said
"catches" for any failure on `BASE`, in a bare worktree with none of what the checkout
generates, so a comment-only range whose test reads `areas/world.*` reported a catch; and it
copied only the test files the range added or changed, so a deleted or renamed helper stayed
in `BASE`'s tree. Each test now runs first in a `HEAD` worktree, the control ("cannot judge"
when it fails there), both trees run `make world`, and `BASE`'s gets `HEAD`'s whole `tests/`
(`f399d96db`). `932421560` still catches. `test_check_tests_catch.py` runs the script in a
scratch repository.

### 11. Make tests break only when behaviour breaks

**Problem.** Three habits make tests fail when the server is fine. They are what usually
turns `master` red after a merge.

- **Text checks.** 193 tests only read sources as text. They fail on a harmless rename or a
  reshaped block, and they pass when the behaviour is wrong but the text still matches. The
  most changed since 2026-09-01: `test_account_erasure.py` (19 commits),
  `test_personal_data_export.py` (18), `test_character_persistence_gap.py` (13),
  `test_chaos_infinite_starting_grants.py` (12), `test_flatfile_corpse_live_routing.py` (10)
  and `test_chaos_new_character_kit.py` (10).
- **Exact counts.** 129 tests pin a count or a hash. `426bb5557` changed 220 to 221 in three
  places when the lifecycle policy gained one entry; nothing was wrong.
- **Copied stubs.** Each native harness defines its own stubs for the server functions it
  does not link. `logit` alone is stubbed in 30 `.cpp`/`.cc` harnesses and in 56 Python
  tests that embed harness source. Since 2026-09-01, 17 commits added a missing stub to a
  harness after the server started calling something new. Shared stub files already exist
  for three subsystems: `chat_presentation_stubs.inc`, `combat_prompt_stubs.inc` and
  `world_output_stubs.inc`.

**The change.**

- A rule in `docs/guides/TESTING.md`: a new test is behavioural when a harness or a journey
  can reach the code. A text check stays only for what text alone can show, such as a call
  site that must not come back or an order that must hold.
- Convert or delete the most-changed text-only tests above. Each becomes a harness test of
  the same behaviour, preferably as more assertions in an existing harness for the same
  source, so it adds no compile. If breaking the code makes another test fail, the text
  check is redundant and is deleted.
- Replace an exact count with the property it stood for (every entry has an owner and a
  retention, no duplicates), unless the count itself is the contract. Hashes stay where
  they guard a generated file against hand edits, such as the epic-zone seed.
- Put the stubs that repeat (`logit`, `send_to_char`, `persistence_mode_flatfile_root` and
  the like) in one `tests/async/harness_stubs.inc`. A harness keeps a local stub only where
  it must behave differently.

**Done when** `TESTING.md` has the rule, the six tests above are converted or deleted, no
test pins a count that grows with content, and the repeated stubs come from one file.

**Built** (PR 7).

- **The rule.** `TESTING.md`'s "Test styles" says a new test is behavioural whenever a
  harness or a journey can reach the code, and keeps a text check only for what text alone
  shows (a call site that must not come back, an order that must hold), after breaking the
  code shows no other test notices. It also covers counts, harness stubs and database tests.
- **Counts.** Twenty assertions pinned a number that grows with content (schema tables,
  lifecycle entries, Redis surfaces, migrations, the quest catalog, epic zones, classes,
  races, dials, the session 14 gate, kit arrays, telemetry fixtures). Each now checks the
  property it stood for. The counts that are the contract stay: the shops' 540 durable ids,
  the 170-table sealed baseline, the 100-row weather table, the sealed migrations' first ids.
- **Stubs.** `tests/async/harness_stubs.cpp` defines the twenty server functions harnesses
  most often stubbed, as weak symbols (`_paths.HARNESS_STUBS`). A harness's own definition,
  or the real source, replaces one at link time. 283 copies are gone from 117 harnesses. The
  22 harnesses built on their own types, without the server's headers, keep their 39: there
  the stub is also the only declaration. (A `.cpp` linked in, not the planned `.inc`
  included: only a separate file lets a harness keep its own version of one stub.)
- **The six tests.** Each check was broken on its own, with the behavioural tests that
  could notice run against it: 52 mutations, each built once into the flat-file server and
  shared through the journeys' build cache.
  - `test_account_erasure.py` and `test_personal_data_export.py` were behavioural already.
    Their churn was the 220 → 221 kind of count, now the manifest's own.
  - `test_flatfile_corpse_live_routing.py` is gone. Three of its six behaviours failed no
    test when broken; `test_corpse_save_routing.py` runs the three production functions
    and catches all six.
  - `test_chaos_new_character_kit.py` keeps its checks of the generated kit data. Its text
    checks of the kit loader are gone (`test_chaos_kit_runtime.py` and the CHAOS journey
    run that code), except the build-before-grant order and two "must not come back"
    checks.
  - `test_character_persistence_gap.py`: 36 checks on eleven files became six. Caught
    elsewhere: a death that saves nothing, a NULL account menu argument, an edited sealed
    migration. Now asserted in the MariaDB load harness: duplicate descriptions and the
    stage a refused load names. Noticed by nothing: the flat-file first save's
    `NO_DB_BASELINE` flag, the gate on it and the writer's re-arm of it. Even all three
    together go unnoticed, because a new flat-file character's first save lands without
    them. Also unnoticed: the baseline save's owner-revision reload, the post-entry save,
    the delete before re-inserting a saved item's descriptions, and the log lines.
  - `test_chaos_infinite_starting_grants.py`: 122 checks on 36 files became an order file
    and a "must not come back" file. `test_epic_skill_grant.py` and
    `test_guild_chaos_epic_skills.py` now run the epic skill rules and the guild's CHAOS
    fill.
- **What stays as text without a behavioural test.** Pouch crafting, enhancing,
  salvaging and encrusting, and the shipyard's frigate discount, keep their text checks:
  breaking each fails no test, and no journey crafts with the pouch or buys a hull with
  the tattoo. A CHAOS journey step for each would let those checks go.
- **Found on the way and fixed.**
  - Twenty MariaDB tests ran in no gate since `make test-db` took its list on 2026-09-29.
    Ten read the checkout's `.env` and wrote to whatever database it named; they now take
    a disposable one through `tests/async/disposable_schema.sh`. The telemetry reports
    runner wanted a client container; it now starts its own. All twenty are in
    `tests/run_db_tests.sh` and pass.
  - `test_pet_restart_journey.py` and `test_mob_gold_dial_runtime.py` were manual. They
    now build their own server and are in `make test-all`; the gold journey promotes its
    character with the combat journey's `make_overlord()`.

### 12. Fuzz the code that reads outside input

**Problem.** No fuzz target exists. Code that parses input from clients or files is tested
only with the inputs someone thought of. The sanitizer builds already exist, and they are
what turn a fuzzed input into a reported bug instead of silent corruption.

**Targets**, in order:

1. WebSocket handshake and frames: `websocket_parse_handshake` and `websocket_parse_frame`
   (`src/net/websocket.h`). Any client reaches them before logging in.
2. GMCP input: `gmcp_handle_input` (`src/net/gmcp.h`). Client-controlled.
3. Player save decoding: `player_snapshot_decode` and `player_item_snapshot_list_decode`
   (`src/player/player_snapshot_codec.h`), plus a round-trip check: what is encoded decodes
   to the same snapshot.
4. Flat-file records behind `flatfile_read` (`src/flatfile/flatfile_store.h`).
5. Telnet input in `process_input` (`src/net/comm.c`), once a harness can give it a
   descriptor.

**The change.** One `tests/fuzz/<target>.cpp` per target, each with
`LLVMFuzzerTestOneInput` and the shared stubs from item 11. `make fuzz FUZZ_TARGET=<name>
FUZZ_SECONDS=<n>` builds it with `clang -fsanitize=fuzzer,address,undefined` under
`bin/fuzz/` and runs it. Useful inputs and every crash go into
`tests/fuzz/corpus/<target>/` as small committed files. The gate gets one test,
`tests/async/test_fuzz_corpus.py`, which builds each target with `g++`, the sanitizers and a
small `main` that feeds every corpus file once: no fuzzing engine, and seconds of run time
after the compile. Long runs are by hand (decision 5).

**Done when** the first three targets exist, each has run for an hour, every finding is
fixed in its own commit with its input in the corpus, and the replay test runs in
`make test`.

### 13. `clang-tidy` on changed lines

**Problem.** The warnings are strict and CodeQL runs in CI, but nothing checks for bug
patterns compilers do not warn on: use after `std::move`, `sizeof` of a pointer, a
suspicious string compare, an ignored failure return, a narrowing comparison.

**The change.** A root `.clang-tidy` with `bugprone-*` and a few `cert-*` and
`performance-*` checks. `scripts/tidy.sh` works like `scripts/format.sh`: it checks changed
lines only (through `clang-tidy-diff`), and `--check` only verifies. The `.c` files are
C++20, so the script passes `-x c++ -std=c++20` and the include paths from `src/Makefile`;
no compile database exists, so the script writes one from those flags. The hook in
`scripts/git-hooks/` runs it after the format check, and refuses a commit with a new finding
on a changed line (decision 4).

**Steps.** Run it once over all of `src/` first. Fix each real bug it finds in its own
commit, and turn off each noisy check in `.clang-tidy` with the reason beside it. Then add
it to the hook.

**Done when** `.clang-tidy` and `scripts/tidy.sh` exist, the first full run's real findings
are fixed, and the hook runs it.

**Built** (PR 8).

- `.clang-tidy` turns on `bugprone-*`, `cert-flp30-c` and three `performance-*` checks, with
  `WarningsAsErrors: '*'`; each check that is off has its reason and its first-run count in
  the file. It is added past `.gitignore`'s `.c*`, as `.clang-format` is.
- `scripts/tidy.sh` checks the lines changed against `HEAD` (or `--staged`, or `--rev REV`)
  through `clang-tidy-diff`, or every line with `--all` and a count by check. It writes
  `bin/tidy/compile_commands.json` from `src/Makefile`'s `-D`, `-I` and `-std` flags (the
  MariaDB build: code only under `__NO_MYSQL__` is not analysed), and returns at once when
  no `src/` line changed.
- The pre-commit hook runs `tidy.sh --staged` after formatting and refuses a commit with a
  finding; a missing `clang-tidy` lets the commit through, as a missing `clang-format`
  does. `test_tidy_tooling.py` drives it in a fixture repository (a finding on a staged
  line fails, the fixed line passes, the same finding on an unchanged line does not count),
  and the hook test checks the hook runs it. `formatting.md` describes it.
- The first full run (clang-tidy 22, 469 files, 7.5 minutes) found 11,308. Three were bugs,
  each fixed in its own commit with a test: the kick messages one race short, the last
  reading past the array (`bugprone-suspicious-missing-comma`; a `static_assert` holds the
  nine arrays at 20); the line editor freeing every second line and never its line array
  (`bugprone-macro-repeated-side-effects`; `test_editor_free.py` under LeakSanitizer); and a
  missing `<climits>` in `flatfile_store.c`. The rest were reviewed: the noisy checks are
  off, and the second full run finds 560, 508 of them parentheses missing from legacy
  header macros, the others deliberate (empty catches of `bad_alloc`, `system()` calls,
  binary `memcpy`) or guarded. Five are `std::sort` without `<algorithm>`, which `master`
  fixed in `af2ea8e0d` after this stack branched.

**Review round 1** (2026-10-10, #22's adversarial review and Codex's): `--staged` analysed
the working-tree file at the staged lines, so an unstaged fix let a staged finding into the
commit, and the reverse refused a clean one; and the diff it fed `clang-tidy-diff` followed
the user's git config: `color.diff=always` let every finding through, `diff.noprefix=true`
refused every commit touching `src/`. The staged check now reads `src/` and `.clang-tidy`
as staged, written to `bin/tidy/staged/` (0.2 s), and both diffs pin `--no-color
--no-ext-diff` and the `a/`/`b/` prefixes; `test_tidy_tooling.py` covers all four cases.
The review also noted that no command reaches the line editor whose leak this item fixed;
REGRESSIONS.md and `formatting.md` now say so, and what wiring it back in would need.
Codex, on the round's push: `--all` with no finding at all exited 1 at its summary's empty
`grep` under `set -e`; the summary tolerates that now (`5413f3914`), and the test runs
`--all` on a clean file. Codex's next review: the staged check took its flags from the
working tree's Makefile, and `--all` called a tree clean when clang-tidy could not run.
The flags now come from the staged `src/Makefile`, and an `xargs` status above 123 (the
analyzer missing or killed; a finding is 123) fails the run.

### 14. Keep a history of test runs

**Problem.** The runner prints each test's result and time, then forgets them. A journey
that fails now and then is found one red run at a time (the four journey fixes listed under
"Where the suite stands", all since 2026-10-01), and a test that slowly gets slower is noticed
only when the gate runs late.

**The change.** `tests/run_regression_tests.py` already has each test's status and elapsed
time. At the end of a run it writes `bin/test-history/<UTC time>-<short sha>.json` with the
commit, whether the tree was dirty, and each test's path, status and seconds.
`scripts/test_history.py` reads those files and reports:

- tests that both passed and failed on the same commit (flaky);
- tests whose time rose more than half over their median of the last ten runs;
- the twenty slowest tests.

`bin/` is ignored, so the history stays local.

**Done when** runs write the file, the report works on a week of runs, and `TESTING.md` says
where the files are.

**Built** (PR 6). `tests/run_regression_tests.py` writes
`bin/test-history/<UTC time>-<short sha>.json` after every run (the commit, whether tracked
files were dirty, the `--match` filter, and each test's path, status and seconds), and
`scripts/test_history.py [--history DIR]` reports as described; a slowdown counts only for
tests whose median is a second or more, because the ratio of tenths of a second is noise.

- A week of runs does not exist yet: the history is local and new. The report was run on
  the 67 `make test-all` runs GitHub Actions kept from 2026-10-08 (when the repository moved
  there) to 2026-10-10, each log turned into a history file: no flaky test (no clean commit
  ran twice), one slower test (`test_studioproc_duplicate_record.py`, 617 s against a
  median of 340 s), and the twenty slowest, led by the three flat-file journeys that pass
  the 900 s timeout on those runners.
- That last finding was a bug: every journey hashed `/usr/local/lib` for its build key, and
  GitHub's runner image keeps gigabytes there. `46ac05997` on `master` stops it.
- `TESTING.md` says where the files are and what the report lists.

**Review round 1** (2026-10-10, #20's adversarial review and Codex's): two runs starting in
the same second on one commit overwrote each other's file; a run with an untracked test or
source counted as clean, so a test fixed while untracked read as flaky; and a test's time
in a full parallel run was set against focused runs made alone. The file name ends in the
runner's pid and is created exclusively, an untracked file makes a run dirty, and each run
records its workers beside `--match`, so a slowdown is judged only against runs made like
the last (`f58f6e67c`; `test_test_history.py`). Codex, on the round's push: the untracked
check covered only `src/`, `tests/`, `areas/` and `scripts/`, but tests read `migrations/`
and `docs/` too; any untracked file counts now. Codex's next review: when the last run failed
a test or did not run it, the slowdown check compared an older pass; it now takes only the
tests the last run passed, against their passes in earlier runs made like it. The review
after that: runs that started in the same second sorted by commit and pid, so the "last"
could be the earlier one; each run records when it finished, and that breaks the tie.
`make coverage` also checks for `gcovr` before its `test-all` instead of failing after it.

### 15. Mutation testing, by hand

**Problem.** Nothing measures whether the tests catch bugs. A coverage number (item 16) says
a line ran, not that a test would notice if the line were wrong.

**The change.** `scripts/mutate.py <src file>`. It finds mutation sites outside comments and
strings (reusing `_source_contract.strip_comments`): it flips a relational operator, swaps
`==` and `!=` or `&&` and `||`, drops a `!`, and replaces a returned constant. For each
mutant it edits the file in a worktree under `bin/analysis/mutate/`, runs the tests that
name the file, and records whether they caught it, missed it, or timed out. `ccache` keeps
each rebuild to the one changed file. The report gives a score per file and lists the
mutants that survived, with their lines; each one is either a missing test or dead code.

It never runs in the gate, and it works in its own worktree, so the checkout and any running
gate are untouched. The score counts only the tests that name the file; journeys cover
most files without naming them, so it shows where the focused tests are weak, not the whole
suite's strength.

**First files**, those named by the most tests: `src/player/player_snapshot_codec.c` (17),
`src/persistence/critical_command.c` (13) and `src/economy/collector_policy.c` (12).

**Done when** the script runs on those three files, each surviving mutant has a new test or
its dead code removed, and the commit that does so records the before and after scores.

### 16. Line coverage, on demand

**Problem.** Nothing shows which code no test reaches. Item 15 scores only the tests that
name a file, and journeys reach most of the server without naming anything, so a function
that no harness and no journey ever runs looks the same as one that both run.

**The change.** `make coverage` runs `scripts/coverage.sh`, and nothing else runs it: it is
never part of `test-all`, `test-db` or the commit hook (decision 6). One command does the
whole run:

1. it creates a detached worktree of `HEAD` (or a commit given as an argument) under
   `bin/analysis/coverage-<sha>/`, so the checkout, its objects and any running gate are
   untouched;
2. it puts a `g++` wrapper from `scripts/coverage/` first on `PATH`. The wrapper adds
   `--coverage -fprofile-abs-path -fprofile-update=atomic` and a new `-dumpdir` under
   `bin/coverage/<sha>/data/` to every compile, then runs the real `g++`. The server
   `Makefile` (`CC = g++`), the journeys' own flat-file builds and the harness tests all
   call `g++` by name, so one wrapper instruments all three, and the notes and counts of a
   harness built in a temporary directory outlive that directory. It keeps the build's
   `-Og`: `_FORTIFY_SOURCE=3` without optimisation is a warning, and `-Werror` makes it
   fatal;
3. it runs `make -k test-all` in the worktree, and `make test-db` as well when given
   `--db`, and lists the tests that failed. A test that breaks only under instrumentation
   loses its own counts, not the report;
4. it writes `bin/coverage/<sha>/index.html` and a per-directory summary with `gcovr`,
   reporting only files under `src/`, replaces any earlier report for the same commit, and
   removes the worktree.

**What it cannot see.** A process stopped with `SIGKILL` writes no counts. `SIGTERM` shuts
the server down in order (`hupsig` sets `signal_shutdown_pending`), so most journeys count,
but the crash probes do not. A test that patches a copy of a server source and compiles the
copy is left out, because only `src/` is reported. The few tests that call `c++` or
`clang++` bypass the wrapper.

**Steps.** Write the wrapper, the script and the target. Run it once on `master`. Check
that `src/economy/collector_policy.c`, which `collector_policy_harness.cpp` compiles, shows
counts, and so does a command handler that only journeys reach. Add a "Coverage" paragraph
to `docs/guides/TESTING.md`: the command, where the report lands, and what it cannot see.

**Done when** `make coverage` on a clean checkout produces the report with no other step,
both checks show counts, and `TESTING.md` says how to run it.

**Built** (PR 6). `make coverage` and `scripts/coverage.sh [--db] [COMMIT]` as described,
with `scripts/coverage/g++`. Three things the first runs on `master` showed are fixed in the
wrapper and the script:

- **ccache.** Where ccache's `g++` links come first on `PATH` (as on this workstation), the
  wrapper took ccache for the real compiler. ccache found the wrapper again on `PATH`, and
  each round added the flags once more, until "Argument list too long". The wrapper now skips
  ccache's directories.
- **Warnings.** At `-O2` (the production profile `make test-all` builds), `--coverage`
  provokes false array-bounds and null-dereference warnings in libstdc++, and `-Werror`
  stopped the build before any test ran. The wrapper appends `-Wno-error`.
- **gcovr.** It stopped on counts whose harness source was a deleted temporary file, on hot
  loops past its "suspicious" count, and on a function at two lines when a source is built
  both with and without `__NO_MYSQL__`. The script now ignores the first two and keeps such
  functions apart (`--merge-mode-functions=separate`).

The run on `master` (`46ac05997`, without `--db`, 14 minutes on this workstation):

- 688 tests ran under instrumentation. One failed only under coverage:
  `test_spell_schedule_failure_runtime.py`, whose harness linked only because the optimiser
  dropped a call to `GET_CLASS()`, which it never defined, and `--coverage` kept it. The
  harness now defines it.
- 33% of `src/` lines ran (94,731 of 285,816). By directory: `telemetry` 68%, `flatfile` 65%,
  `redis` and `account` 54%, `world` 49%, `item` 48%, `player` 45%, `net` 45%,
  `persistence` 42%; then `economy` 33%, `mob` 28%, `classes` 25%, `combat` 22%, `specs`
  19%, `cmd` 17%, `ships` 15%, `kingdom` 13%, `magic` 12%, `guild` 11%. `sql` is 9% because
  only `--db` runs the MariaDB tests.
- Both checks show counts. `src/economy/collector_policy.c`, which
  `collector_policy_harness.cpp` compiles, is at 79%. `do_score()`, which only journeys
  reach (they send `score`), has counts on all but 11 of its first 60 lines.
- `kick.c` is at 0%: no test kicks.

---

## Part 3: database engine support

### 17. A new database cannot be built on MariaDB 11.8

**Problem.** The staging host moved to Ubuntu 26.04 on 2026-10-09, and its MariaDB went from
10.11 to 11.8.6. Migrations 0031 (`economy_accounting`) and 0032 (`economic_baseline`) verify
by hashing their tables' metadata (columns, indexes, foreign keys, checks) against one
fingerprint per engine. They know only MariaDB 10.11 and MySQL 8.0, and on any other version
they stop with `unsupported database engine for accounting schema` (or `... for baseline
retention schema`) (`migrations/immutable/0031_economy_accounting.sh` L26-34, and the same
lines of `0032_economic_baseline.sh`). A database built from scratch on staging on
2026-10-09 got through 0001 to 0030 and failed at 0031. Migrations 0033 to 0036 have not run
on 11.8 yet. No other verifier checks the version.

Existing databases are not affected. The runner runs a migration's verifier only when it
applies that migration (`run_pending()`, `scripts/migration_runner.py` L273-282). Staging's
live database was migrated under 10.11, and on 11.8 it boots and passes the server's schema
checks (the boot of 13:04 that day). What breaks is building a database: rebuilding staging's,
a new development database on a current Ubuntu, or production after the same OS upgrade. The
gate does not see it, because its containers and `compose.yaml` pin `mariadb:10.11`
(`tests/async/with_disposable_mariadb.sh`), and the documentation names MySQL 8.0 and MariaDB
10.11 as the supported engines (`docs/reference/DATABASE.md` L145-146,
`docs/persistence/IMMUTABLE_MIGRATIONS.md`, `docs/guides/TESTING.md`).

**Why the verifiers cannot simply be edited.** They are sealed. `mud_schema_history` keeps
each applied migration's verifier checksum. The runner refuses a database whose history
differs from the manifest (`validate_applied_prefix()`, L247: "applied migration history was
edited or reordered"), and the server compares the history checksum at every boot
(`src/sql/sql.c` L1618-1636, `COMPAT-E002`). Adding an 11.8 branch to `0031_*.sh` or
`0032_*.sh` would change their checksums and lock out every existing database. The manifest
version and the runner version (both 1) are recorded in existing databases too, so neither
can change either.

**Also on staging.** Staging's MariaDB runs as a private instance with its own data
directory, and that directory still records `10.11.14-MariaDB` in `mysql_upgrade_info`:
`mariadb-upgrade` has not run against it. Ubuntu's package upgrades only the system
instance. The unit failed to start from 12:35 to 13:03 during the upgrade (`Fatal error in
defaults handling`, then a start timeout) and has run since 13:03:57.

**The change.**

1. Support MariaDB 11.8 (decision 7).
2. Give 0031 and 0032 an 11.8 check without touching their sealed files. Add one verifier
   per migration (for example `immutable/0031_economy_accounting.mariadb-11.8.sh`) with the
   same metadata query and an 11.8 fingerprint, list it in the manifest with its own
   checksum, and have the runner run it in place of the sealed verifier only when the server
   reports MariaDB 11.8. The history row keeps the sealed verifier's checksum, so a history
   is the same on every engine. Measure the fingerprints on a `mariadb:11.8` container from a
   fresh bootstrap.
3. Run all 36 migrations on 11.8, and fix any later verifier that fails the same way.
4. Add an 11.8 leg: `RUNTIME_DB_IMAGE=mariadb:11.8 tests/async/run_runtime_compatibility_mysql.sh`,
   which takes the image as a variable, plus a regression test that a fresh bootstrap through
   the runner reaches the head on 11.8, and that the runner still refuses an edited history.
5. Update the support statements in `DATABASE.md`, `IMMUTABLE_MIGRATIONS.md` and
   `TESTING.md`.
6. On staging, back up the database, then run `mariadb-upgrade` against the private instance
   (its socket and `~/.config/duris-mariadb/my.cnf`), and check that `mysql_upgrade_info`
   reads 11.8.

**Done when** a fresh database reaches the head through `scripts/migration_runner.py` on
MariaDB 11.8, MariaDB 10.11 and MySQL 8.0 with the same history checksum; staging's existing
database still passes the runner and boots; the 11.8 leg and the regression test run; the
documents name the three engines; and staging's `mysql_upgrade_info` reads 11.8.

**Built** (PR 3), and the staging step done.

- Running all 36 migrations on a fresh `mariadb:11.8` (11.8.9) failed only at 0031's and
  0032's verifiers, on the version gate: their metadata fingerprints on 11.8 are 10.11's.
- `migrations/immutable/0031_economy_accounting_mariadb_11_8.sh` and
  `0032_economic_baseline_mariadb_11_8.sh` are the sealed files with the version gate
  for `11.8.*MariaDB*` and 10.11's fingerprints. The manifest lists them in a new optional
  top-level `engine_verifiers` list (migration, engine, path, checksum); the runner checks
  them like any sealed file. `MysqlExecutor.verify()` asks `SELECT VERSION()` once and runs
  `Migration.verifier(engine)`; the history row keeps the sealed checksum. The manifest and
  runner versions stay 1.
- `run_runtime_compatibility_mysql.sh` runs each step's verifier as the runner chooses it,
  and links `mysql` to `mariadb` inside a MariaDB 11 container, whose image has only the
  new name. `verify_runtime_compatibility.sh` needed nothing: its one MariaDB fingerprint
  holds on 11.8.
- New legs in `make test-db`: `runtime_compatibility_mariadb_11_8` and
  `migration_runner_engines` (`tests/async/run_migration_runner_engines.py`: the runner on
  all three engines, one history checksum, an edited history refused). The runner's unit
  test covers the new manifest list.
- Docs: `IMMUTABLE_MIGRATIONS.md` (a "Supported engines" section), `DATABASE.md`,
  `RUNTIME_COMPATIBILITY.md`, `TESTING.md`.
- Staging, 2026-10-10 00:27 local: `duris_staging` dumped to
  `~/backups/duris/2026-10-10-pre-mariadb-upgrade/duris_staging.sql.gz` (6.9 MB), then
  `mariadb-upgrade --defaults-file=~/.config/duris-mariadb/my.cnf --user="$(id -un)"` (the
  tool defaults to `root`, which the instance refuses). The data directory's upgrade file
  is `mariadb_upgrade_info` on 11.x, and it reads `11.8.6-MariaDB`; the old
  `mysql_upgrade_info` (10.11.14) is gone. The game and MariaDB stayed up. The server
  reports `11.8.6-MariaDB-5ubuntu0.1 from Ubuntu`, which `engine_of()` and the verifiers'
  `11.8.*MariaDB*` both match.
- Staging's existing database, restored from that dump into a local `mariadb:11.8`, passes
  the new runner (`run`: nothing pending, history intact) and
  `verify_runtime_compatibility.sh`. The copy was deleted afterwards.

**Review round 1** (2026-10-10, #17's adversarial review): the review found that MariaDB
11.8's own client has no `mysql` or `mysqldump` command, so the runner, every verifier and
the backup would stop at `command not found`, and that the engine leg drives the 11.8
server with this machine's 10.11 client. Not changed in code. MariaDB's container image
lacks the names (they are in its `mariadb-client-compat`), but Ubuntu 26.04's
`mariadb-client` (11.8.6) ships `/usr/bin/mysql` and `mysqldump` in
`mariadb-client-core`, and the dependency manifest installs `default-mysql-client |
mariadb-client`. Forty scripts and the boot's compatibility check call the names too, so a
shim in the runner alone would not make such a host work. Checked once with that client:
in an `ubuntu:26.04` container with `mariadb-client` and `python3`, sharing a
`mariadb:11.8` server's network, bootstrap, `adopt` and `run` reached all 36 migrations
with the manifest's history checksum. The README now says which package gives the names
on a host with MariaDB's own packages. The check stays out of `make test-db`: it installs
packages from the network.

Codex, on the round's push: no database records which verifier approved 0031 and 0032 on
11.8, so an engine verifier changed together with its manifest checksum would approve new
databases while existing histories still pass. Not changed. Anchoring it means recording
the engine verifier in every database, a history or schema change that decision 7 ruled out
so that one history holds on every engine. A sealed verifier has the same exposure on a
fresh database, which has no history to compare; histories catch an edit only for databases
built before it. The engine verifiers are sealed by checksum under `immutable/` like the
others, and an edit to one is a reviewed diff there.

---

## Part 4: the slow tick and the slower boot

The log review's two performance findings, investigated and concluded on 2026-10-09 in a
working note of their own. It was deleted when its work was written here; its last version,
with every measurement, is at `dd1c33842` (`docs/ongoing-projects/tick-and-boot-performance.md`).
Players feel neither: no pulse of the tick comes near 250 ms, and the boot's cost is paid once
per start. Everything was measured on `24e7d3fba`, and nothing under `src/` has changed since.

### How to measure

- **A full world without a database:** the run-directory layout of
  `tests/async/run_cast_timing_probe.py` (flat-file, `REDIS=FALSE`) with `CHAOS_MUD=FALSE`,
  which is staging's configuration. It boots in about 4.5 s here and runs idle for as many
  ticks as wanted. `logs/latency_trace.log` and `DURIS_NEVENT_ANALYTICS=1` work there as on
  staging.
- **Timers in a scratch build:** extract a tree with `git archive <sha> src Makefile` into
  `bin/analysis/`, add `clock_gettime()` sums logged once per tick or per boot step, and build it
  with `make -C <tree>/src BUILD_PROFILE=production OBJDIR=... DMS_BINARY=...
  EXTRA_CFLAGS=-Wno-error`. Never in the worktree.
- **Staging's speed, locally:** the loops that do not depend on the world (`activities`,
  `connections` in the latency trace) take about 1.9 times as long on staging as on this
  workstation, so `DURIS_NEVENT_BUDGET_USEC=13000` here stands in for staging's 25 ms budget.
- **MariaDB boots:** `tests/async/with_disposable_mariadb.sh` with the commit's own migrations
  (`migrations/bootstrap_multithread_safe.sql`, then `scripts/migration_runner.py adopt
  --kind fresh_bootstrap` and `run`).
- **Profiling on staging:** valgrind cannot load the server (its `.bss` is 1.76 GB, which
  valgrind 3.22 fails to map), and `perf` needs root there (`perf_event_paranoid` is 4). gdb
  works with the server as its child (`ptrace_scope` is 1): start the server under
  `gdb -batch`, stop it with `SIGINT` every 0.2 s, and record `thread 1` plus `bt` each time.
- **A scratch boot on staging beside the live game:** the live binary, copied to a scratch
  directory, boots on loopback in the production role with `DURIS_PRODUCTION_PORT` set to its
  own port and `REDIS=FALSE`, against a copy of the database made inside staging's own MariaDB
  (`mariadb-dump duris_staging | mariadb <copy>`). Drop the copy, its user and the directory
  afterwards. Until item 17 lands, a fresh database cannot be built there, but a copy of the
  live one can.
- **`Boot completed in: N milliseconds` is CPU time**, not wall time: `clock()` sums every
  thread's CPU since `run_the_game()` started (`src/net/comm.c` L846-L1010). The boot is single
  threaded, so on staging it tracks the wall-clock boot to within a second.

### 18. A slow pulse every tick on an idle server

**Problem.** Once per tick (300 pulses, 75 s), on pulse 299, `affect_update()`
(`src/magic/affects.c` L3821) walks every character, and on an idle server that is about
56,000 mobs. It costs 40 to 140 ms on staging. It also queues two waves of events that land
on pulses 0, 10 and 20 of the next tick, where the event pass goes over its 25 ms budget
(`DURIS_NEVENT_BUDGET_USEC`) and runs its tail one pulse late. The cost grows with the age of
the world.

**Evidence on staging.** Every run with more than two latency windows since 2026-10-04:

| Run ended | Windows | Over 50 ms | Worst pulse (us) | Worst `affect_update` (us) |
|---|---|---|---|---|
| 2026-10-05 03:12 | 237 | 228 | 125,847 | 120,410 |
| 2026-10-07 08:17 | 2,497 | 2,489 | 144,832 | 137,315 |
| 2026-10-08 10:01 | 1,232 | 1,226 | 475,386 | 130,946 |
| 2026-10-09 03:50 | 749 | 738 | 144,826 | 137,944 |
| 2026-10-09 09:01 (read to 08:15) | 209 | 198 | 121,020 | 114,971 |
| 2026-10-09 10:44 | 81 | 73 | 114,674 | 108,646 |

The 475 ms pulse was an immortal's `zreset` of Tharnadia on 2026-10-07 at 13:12:55
(`COMMAND OP SLOW ... operation=zreset`), not the tick. In every run of more than 20 windows,
the median of each window's worst `affect_update` is 58 to 71 ms, the cheapest pulse's event
pass 3.0 to 3.6 ms and the average pass 5.3 to 5.6 ms. `event_balance_affects` is
the latest callback in 172 of the 175 `NEVENT BUDGET WINDOW` lines of the run that ended at
09:01 on 2026-10-09, one pulse late (`max_late_ticks` counts pulses). The run of 2026-10-08
12:11 to 2026-10-09 03:50 deferred 2.58 million callbacks in 15.6 hours, and repaid all its
catch-up debt; the worst late event fell on pulse 1 or 2 in 738 of its 742 deferring windows.

**What one pass does**, measured locally with timers inside `affect_update()`, on a full idle
world in staging's configuration with no player online:

| Tick after boot | Pass | Regeneration check | Affect countdown and expiry | of which `affect_remove()` | Falling check | Mobs walked | Mob affects | Affects expired |
|---|---|---|---|---|---|---|---|---|
| 1 | 19.7 ms | 9.3 ms | 3.7 ms | 0 | 3.6 ms | 55,031 | 31,912 | 0 |
| 4 | 29.8 ms | 10.2 ms | 13.1 ms | 2.8 ms | 3.7 ms | 55,766 | 84,419 | 882 |
| 8 | 52.9 ms | 12.3 ms | 31.9 ms | 11.1 ms | 5.7 ms | 55,961 | 106,772 | 2,516 |
| 16 | 59.9 ms | 11.7 ms | 40.6 ms | 19.4 ms | 4.5 ms | 56,201 | 122,676 | 5,337 |
| 24 | 49.7 ms | 10.3 ms | 29.9 ms | 11.3 ms | 6.8 ms | 56,504 | 128,784 | 3,507 |

The rest of the pass (the walk itself, disguises and the timers' own cost) is about 3 ms. The
affects that expire are the mobs' own spells and songs (shadow shield, soulshield, minor globe,
armor, fireshield, coldshield, stone skin, war cry, infuriate). The mobs cast them again, so
their count climbs toward a plateau of about 130,000 after 30 minutes. A Chaos-mode run gives
the same picture. Staging's CPU is about 1.9 times slower on the same loops, hence 40 to
140 ms there. The players are not the cost: staging's at most three are 0.005% of the
characters walked.

- The regeneration check finds 11,700 to 12,100 mobs below their maximum vitality every tick,
  against 1 to 3 below their maximum hit points and a few hundred below their maximum mana.
  93 to 96% of the vitality ones are wanderers (no `ACT_SENTINEL`), short by 1 or 2 points
  that they spent moving. `StartRegen()` (`src/world/events.c` L256) gives each one an
  `event_move_regen` 10 pulses later (`MOB_MOVE_REGEN_DELAY`): 10,900 to 11,800 per pass.
- `balance_affects()` (`src/magic/affects.c` L487) queues up to 3,200 `event_balance_affects`
  per pass, with no delay and at most one per mob whose buff expired.

**Where the queued work lands**, per pulse of the tick, in a local Chaos-mode run with
per-pulse logging (which adds about 1 ms to every pulse):

| Pulse of the tick | Event pass, mean (max) | Callbacks run | What runs |
|---|---|---|---|
| 0 | 14.5 ms (23.9 ms) | 2,500 | 1,200 to 3,300 `event_balance_affects` (about 3 us each), one `generic_char_event` (4.8 to 5.4 ms), a wave of `event_mob_mundane` |
| 10 | 12.5 ms (20.5 ms) | 12,400 | about 11,000 `event_move_regen` restoring 1 or 2 points |
| 20 | 16.8 ms (21.4 ms) | 12,400 | the same `event_move_regen` again, now finding the mob full and stopping, and `generic_char_event` |
| any other | 3 to 4 ms | about 1,000 | |

- `event_move_regen()` (`src/world/events.c` L178) applies the gain and then always
  reschedules itself (L206). The next run finds the mob at its maximum and returns, so half of
  the 24,000 regeneration callbacks of every tick do nothing else.
- `generic_char_event()` (`src/world/handler.c` L298) is registered in `ne_init_events()`
  (`src/world/new_events.c` L2069) with an initial delay of 80 pulses and an interval of 20.
  Each run walks all 56,000 characters, though it does a character's work only once in four
  runs, and it took over 5 ms 273 to 306 times in 30 minutes locally. Twenty divides 300, so
  it runs on pulses 0 and 20, two of the tick's busy pulses.
- The pass checks its budget after each callback and moves the rest of the bucket to the next
  pulse (`nevent_defer_suffix()`, `src/world/new_events.c`). The balance events are queued
  after everything else due on pulse 0, so they are the tail that runs late. With the budget
  scaled to staging's speed (13 ms), the local world defers 300 to 14,000 callbacks per
  window, all one pulse late: 23% `event_move_regen`, 20% `event_spellcast`, 18%
  `event_mob_mundane`, 17% `event_balance_affects`, 8% `event_mana_regen` and 7% `event_wait`
  (Chaos mode, whose mobs cast more).

The 29.7 ms `event_mob_mundane` on staging at 2026-10-08 12:07:34 is not part of this: slow
`event_mob_mundane` runs locally are one-offs from different mobs, never repeated.

**The change.**

1. In `event_move_regen()`, and in `event_hit_regen()`, `event_mana_regen()` and
   `event_ward_regen()`, which have the same shape, stop rescheduling once the gain has
   brought the character to its maximum. This removes the pulse-20 wave of about 12,000
   callbacks. The same points are restored at the same moments.
2. In `StartRegen()`, give an NPC's first event a per-mob offset within
   `MOB_MOVE_REGEN_DELAY` instead of +10 for all. This flattens the pulse-10 wave. The event
   counts elapsed pulses (`regen_elapsed_ticks()`), so the points restored stay the same.
3. Give `generic_char_event`'s registration an initial delay that puts it on a pulse the tick
   does not use, such as 5, so it stops stacking on pulses 0 and 20.
4. Sweep the NPCs in `affect_update()` in slices across the tick, as `generic_char_event`
   slices its per-character work, and keep players on the tick boundary. This removes the
   40 to 140 ms pass and spreads the balance events. An NPC's buff then wears off at its
   slice's pulse within the same tick instead of at the boundary.

Changes 1 to 3 are small, change nothing a player sees, and remove the event-pass spikes;
change 4 removes the spike of the pass itself.

**Done when** an idle full world shows fewer pulses over 50 ms in `logs/latency_trace.log`
than today (locally, after 12 minutes, 6 to 11 of every 14 windows in the timed build, whose
timers add a few ms to the pass); `NEVENT BUDGET WINDOW` lines become rare on staging; and
regression tests show that a regeneration event stops at the maximum while restoring the same
points, and that a sliced NPC's affects still count down once per tick.

**Built** (PR 5), all four changes.

- Changes 1 and 2 (`src/world/events.c`): each of the four regeneration events returns
  without rescheduling once its gain leaves the character at its maximum, and `StartRegen()`
  gives an NPC's first event `1 + idnum % delay` pulses instead of the full delay.
- Change 3 (`src/world/new_events.c`): the generic character sweep starts at
  `20 * WAIT_SEC + 5` pulses, so it runs on pulses 5, 25, 45 and so on.
- Change 4: `affect_update(pulse)` runs every pulse and returns unless the pulse is a
  multiple of 15. Pulse 0 walks the players, as before, and each 15th pulse walks one of 20
  NPC slices (`char_slice()`, which `char_sweep_slice()` now wraps). `point_update()` stays
  on pulse 0.
- Effects a player could notice: an NPC's buff wears off at its slice's pulse, anywhere in
  the tick, instead of at the tick's start. A character whose points drop by a path that
  does not call `StartRegen()` starts regenerating at the next regeneration check of its
  slice, at most one tick later; before, its event kept running at the maximum and found
  the loss within 10 pulses.
- `tests/async/test_tick_work_spread.py` runs the production regeneration events and
  `affect_update()` in harnesses: an event at the maximum does not reschedule and one below
  restores the same points, an NPC's first run comes at its own offset, and over the 300
  pulses of a tick every NPC counts down exactly once, in 20 pulses, and players on pulse 0.
- Local, full world, staging's configuration, no player, event budget scaled to staging
  (13 ms), two runs of 12 and 8 minutes, before against after: windows with a pulse over
  50 ms 0 and 0 against 0 and 0 (this machine is faster); worst pulse 45 and 34 ms against
  27 and 28 ms; worst `affect_update` 30.5 and 23.9 ms against 16.1 and 8.6 ms. Budget
  windows were as many (8 and 6 each). In the second run the first two deferred 131,000 to
  353,000 callbacks either way while the world settled; the later four deferred 213 to
  9,496 per window before against 793 to 2,538 after.
- Staging, 2026-10-10 01:30 to 02:05 IDT, production profile, two scratch servers beside
  the live game against their own copies of `duris_staging` (loopback ports, Redis off),
  30 minutes idle: the live binary had a pulse over 50 ms in 16 of 23 latency windows (worst
  89 ms), its worst `affect_update` rising from 13 to 83 ms, and 14 `NEVENT BUDGET WINDOW`
  lines; this branch had none over 50 ms (worst 36 ms, in the first window), its worst
  `affect_update` 2 to 7 ms throughout, and 2 budget lines, both in the first 600 ticks.
  The copies, their users and the scratch directory were removed afterwards. The live
  service is measured after deploy.

**Review round 1** (2026-10-10): the adversarial review found no defect. Codex, on the
round's push: a player's shapechanged body is an NPC, so its affects (the shapechange's own
`SPELL_CALL_OF_THE_WILD`, a channel) counted down in a hashed slice, up to a tick off the
players' pulse 0. A shapechanged body (`IS_MORPH()`) now counts down with the players, and
`test_tick_work_spread.py` has one.

### 19. Most of every boot is one shopkeeper scan

**Problem.** When a boot's zone reset loads the keeper of a fixed (not replicated) shop
(command `M`, `src/world/db.c` L3505), it asks `live_shopkeeper_for_identity()` (L3244)
whether that shop already has a live keeper. That walks `character_list` until
`singleton_shop_id()` says so, and at boot none exists yet, so it walks the whole list.
`singleton_shop_id()` (`src/world/world_singletons.c` L89) answers at once for a bound keeper;
for every other mob it loops over all 544 `shop_index` entries, comparing each shop's keeper
with the mob's prototype. One local boot counted 519 walks, 13,774,490 characters visited,
13,639,309 full shop-table scans and 7,419,784,096 comparisons: 2.40 s of the 2.92 s
zone-reset phase, in a 4.1 s boot. On staging it is about 8 s of a 12 s boot: gdb stopped
the live binary's boot every 0.2 s, and 42 of the 49 samples were in this scan. It came in
with `4cb743b6a` ("Prevent duplicate fixed shopkeepers after recovery", 2026-09-22), before
staging's first boot.

**The 2 s step of 2026-10-08.** Staging's boot CPU went from 8.9 to 10.1 s, with 6 or 7 s of
zone resets, to 11.8 to 13.5 s, with 9 or 10 s, from the first boot of `ca92ef1c2`
(2026-10-08 10:01), and stayed there through the host's reboot and OS upgrade. The cause is
where the build placed the scan's loop, not a change in the code:

- The scan is a 24-byte loop of eight instructions at offset `0xfb` in `singleton_shop_id()`.
  Where it falls in a 64-byte cache line moves whenever code linked before the function
  changes size. In `a7e43bd0a` it fits in one line (byte 27). In `ca92ef1c2`, and in every
  staging build kept since, it crosses two (byte 43, once 59). A build here of a commit puts
  these functions at the same addresses as staging's build of it.
- Staging's AMD Zen 3 CPU runs the loop at 0.44 to 0.51 ns per comparison when it fits in one
  line and at 0.74 to 0.85 ns when it crosses: about 3.5 s against 6.3 s for 7.4 billion
  comparisons, which is the step. This workstation (Intel) runs every placement at about
  0.2 ns, which is why the step never showed here.
- Ruled out: the code in `a7e43bd0a..ca92ef1c2` (built here at the production profile, the two
  boot equally fast with flat files and with MariaDB, in the local and production roles);
  staging's data (the resets take as long against a copy of the database with its accumulated
  state deleted); the host's memory and CPU (the first boot after the reboot was as slow, with
  no direct reclaim, and a CPU-only step after the resets did not move); the world files,
  Chaos mode and the WebSocket listener.

Any later build can land either way. The cost underneath is the scan, and making it cheap
recovers about 8 s of every staging boot whatever the alignment.

**Other costs in every boot.**

- `restore_shopkeepers()`: `sql_restore_shopkeeper_catalog()` (`src/sql/sql_player.c` L3062)
  walks the whole `character_list` twice for each restored keeper (L3579 counts the incumbent,
  L3588 extracts it): 544 keepers × 2 × 54,500 characters, 59 million visits. That is 1.87 to
  1.91 s of the step's 2 s locally, and the step takes 0.76 to 0.86 s on staging. It takes
  0.3 ms when the database has no saved shops, so a local second boot is about 2 s slower
  than the first boot on a new database.
- `remember_boot_shopkeepers()` (`src/world/world_singletons.c` L142) calls
  `singleton_shop_id()` once for every character: about 10 ms locally.
- At runtime, a zone reset whose fixed keeper is missing pays one full scan, about
  56,000 × 544 comparisons: 15 to 26 ms on staging at the two loop speeds, consistent with
  local `event_reset_zone` callbacks of 6 to 15 ms.

**The change.**

1. Make `singleton_shop_id()` answer at once for a mob whose prototype keeps no shop: build a
   per-prototype flag once after the shops are booted, and return -1 when it is not set. The
   13.6 million full scans become flag reads, and only the list walk is left, about 0.45 s
   locally at the restore's measured 32 ns per visit.
2. Keep, per shop, its live keepers, updated where a keeper is bound (`bind_shopkeeper()`) and
   where it is extracted. `live_shopkeeper_for_identity()` and the restore's incumbent search
   then look it up instead of walking the list. `singleton_shop_id()` also recognizes an
   unbound keeper by its room or birthplace, so either every keeper is bound when it loads or
   the index covers those too.

Change 1 alone takes the 7.4 billion comparisons out of every boot and every runtime reset.
Together the two should cut staging's boot by about 8 s, the scan's share of the resets plus
the restore's 0.8 s, and a local boot from 4.1 s to under 2 s.

**Done when** the scan no longer shows in a sampled boot; staging's `Boot completed` falls by
several seconds and stays there across rebuilds; and a regression test shows that
`singleton_shop_id()` gives the same answers as before for a bound keeper, an unbound keeper
in its shop's room, a roaming keeper and a mob that keeps no shop.

**Built** (PR 4), both changes.

- Change 1: `index_shopkeeper_prototypes()` (`src/world/world_singletons.c`), run once after
  `assign_the_shopkeepers()`, marks the prototypes that keep a shop, and
  `singleton_shop_id()` returns -1 for any other mob before it looks at the shop table.
- Change 2: a set of the live NPCs of those prototypes. `read_mobile()` reports each NPC it
  creates and `extract_char()` each it removes, the only places an NPC enters or leaves the
  character list. `live_shopkeepers(shop)` returns the members `singleton_shop_id()` names,
  bound or not, so every answer is the same. `live_shopkeeper_for_identity()` and the SQL
  and flat-file restores' incumbent searches use it; the restores keep their other filters.
  Binding at load was not needed. `read_mobile()` reports a mob before it marks it an NPC,
  which `GET_RNUM()` refuses, so the report reads `R_num` itself: a first build crashed at
  boot on exactly that, and the harness's stand-in now reports in the same order.
- Local, development profile, MariaDB, full world, same load, `Boot completed` (CPU):

  | Build | First boot | Second boot (544 shops restored) | 519 reset checks | Restore |
  |---|---|---|---|---|
  | Before | 6.8 s | 10.5 s | 4.8 s | 3.5 s |
  | Change 1 | 2.8 s | 6.2 s | 0.84 s | 3.2 s |
  | Change 2 | 1.7 s | 1.9 s | 0.01 s | 0.30 s |

- Staging, 2026-10-09 21:54 UTC, production profile, scratch boots beside the live game
  against a copy of `duris_staging` (loopback ports, Redis off), each binary twice:
  the live binary (master, built 11:06) 12.2 and 13.0 s, this branch 3.7 and 3.7 s. A
  gdb-sampled boot of each (SIGINT every 0.2 s until the game loop): the live binary had
  41 of 72 samples in the reset scan and 5 in the restore; this branch had none in
  either and 1 of 28 in `remember_boot_shopkeepers()`'s single walk. The copy, its user
  and the scratch directory were removed afterwards.
- "Stays there across rebuilds": the loop whose placement cost 2 s is the shop-table scan,
  which no longer runs for any mob but a keeper, so where a build puts it no longer moves
  the boot by seconds. The live service is not measured until this is deployed.
- The staging build needed `fix/gcc-15-build` on master: master itself no longer built with
  staging's gcc 15.2 (two missing `<algorithm>` includes and a `-Wnull-dereference` report
  in `flatfile_ship_establish()`).
- Tests: `tests/async/world_singletons_harness.cpp` asks `singleton_shop_id()` about an
  unbound keeper in its shop's room and a mob whose prototype keeps no shop (it already
  asked about bound, roaming and controlled ones), and checks that `live_shopkeepers()`
  names exactly what a walk names, for every shop. Two source pins
  (`test_flatfile_shopkeeper_restore.py`, `test_issue_552_local_shop_contract.py`) name the
  new call.
