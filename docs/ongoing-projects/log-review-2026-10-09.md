# Log review, 2026-10-09

Read:

- The 03:50-09:01 run's server logs: `logs/log/*`, `logs/player-log/*` and
  `logs/latency_trace.log`, then current and now archived.
- The nine runs archived before it in `logs/old-logs/<date>/`, and the stale `logs/boot.log`.
- The user journal for `duris-mud-production`, `duris-mariadb`, `duris-redis`, cloudflared and
  the DurisWeb units. MariaDB and Redis write their logs to that journal. Also read:
  `runtime/`, the `server_reboots` table, and the MariaDB and Redis status counters.
- The readable host logs: `dpkg`, `apt/history`, `sa-update`, `fontconfig`,
  `ubuntu-advantage`, `landscape`, and the empty `nginx`, `ufw` and `stunnel` logs. Also
  `wtmp`, `/proc`, `/etc/ssh` and the TLS certificate.
- The build and test logs: those in `/tmp`, those in earlier sessions' scratchpads, and the
  editor and agent tool logs under `~/.vscode-server`, `~/.copilot` and `~/.codex`.

The logs only root can read were not read; they, SSH, backups and the kernel are in
[staging-host-follow-ups.md](staging-host-follow-ups.md).

## Summary

| # | Finding | Severity | State |
|---|---|---|---|
| 1 | A 40 to 140 ms pulse every 75 s from `affect_update` on an idle server, and the event wheel defers work in most windows | Low | Open |
| 2 | `server_reboots` records one of ten restarts: a service stop kills the launcher before it writes | Low | Open |
| 3 | Plain HTTP requests to `ws.duris.sbs` reach the MUD's WebSocket port and get a tunnel error | Low | Open |
| 4 | `lib/etc/hosts` keeps every client's address and reverse-DNS name, and nothing prunes it | Low | Open (part of ADR 0003) |
| 5 | Nine shops ask for a buy rate the loader clamps at every boot | Low | Open, data |
| 6 | `logs/boot.log` is stale since 2026-10-04 and nothing writes it | Low | Open |
| 7 | `cmd.debug` never records a one-letter command, and records stale text for an empty line | Low | Open |
| 8 | Wizard broadcasts go into `status` raw, a lost peer's host is a color code, and zone-command lines print internal indices | Low | Open |
| 9 | `snoop` never tells its target, and nothing ages out players' addresses | Low | Decided (ADR 0003); code pending |
| 10 | Boot takes about 12 s, up from about 10 s, since the build booted 2026-10-08 10:01 | Info | Open |
| 11 | Any immortal can read a player's last 200 private messages with `recall` | Medium | Decided: disable; code pending |

## Findings

### 1. A slow pulse every 75 s on an idle server

The pulse is 250 ms (`OPT_USEC`); the event wheel's budget is 25 ms
(`DURIS_NEVENT_BUDGET_USEC`). At most three players were on in the 03:50-09:01 run. Even so,
198 of its 209 latency windows (`logs/latency_trace.log`, 300 pulses each) had a pulse over 50
ms. The worst pulse was 121 ms. The pattern is the same in every window:

- `affect_update` takes 40 to 115 ms on pulse 299, once per game tick. It is among the ten
  worst samples in 204 of the 207 windows that list them.
- `ne_events` spikes on pulses 0, 10 and 20 of the next tick.
- `event_balance_affects` runs one tick late in 172 of that run's 175 `NEVENT BUDGET WINDOW`
  lines. The boot's first window deferred 71,643 events, with a catch-up debt of 8,976.

Every archived run with more than two windows shows the same spikes. The longer runs:

| Run ended | Windows | Over 50 ms | Worst pulse (us) | Worst `affect_update` (us) |
|---|---|---|---|---|
| 2026-10-05 03:12 | 237 | 228 | 125,847 | 120,410 |
| 2026-10-07 08:17 | 2,497 | 2,489 | 144,832 | 137,315 |
| 2026-10-08 10:01 | 1,232 | 1,226 | 475,386 | 130,946 |
| 2026-10-09 03:50 | 749 | 738 | 144,826 | 137,944 |
| 2026-10-09 09:01 (read to 08:15) | 209 | 198 | 121,020 | 114,971 |

The 475 ms pulse on 2026-10-07 13:12:55 UTC was an immortal's `zreset` of Tharnadia
(`COMMAND OP SLOW ... operation=zreset duration_us=469879`), not the tick. No pulse went past
250 ms otherwise, so players see no lag. But this is the tick's cost with nobody on: it scales
with the world, not the player count. The 200-player gate (`scripts/session14_gate.py`) has
never measured it under load.

The deferrals follow from the tick. Each character whose affects change gets an
`event_balance_affects` queued with no delay (`balance_affects()`, `src/magic/affects.c`
L488-493). Thousands land at once after the tick's `affect_update()` and overrun the 25 ms
budget on the next pulses: the worst late event falls on pulse 1 or 2 of the window in 738 of
the 742 deferring windows of the 12:11-03:50 run. That run deferred 2.58 million
callbacks in 15.6 hours, about 3,400 per window after boot, and about 75% more per window than
the run of 10-07 to 10-08. The level was flat within the run. All the catch-up debt was repaid.
There was one `NEVENT SLOW`, on 2026-10-08 12:07:34: a single `event_mob_mundane` callback took
29.7 ms in a 54 ms pass. The logs do not say which mob.

**Next.** Profile one `affect_update` pass on a local copy of the world, and find what it
walks: every character, or every affect. Decide whether the balance events should be spread
over the tick instead of queued for the same pulse. Find the slow `event_mob_mundane` with
`DURIS_NEVENT_ANALYTICS=1` on a local server.

### 2. `server_reboots` records one restart in ten

The launcher writes the row after `dms` exits (`scripts/cycle_mud.sh` L419-464). A
`systemctl --user restart` or `stop` signals the whole control group
(`KillMode=control-group`), so the launcher dies with the server and never writes. The
journal has one `Logged reboot` line in nine boots: the in-game reboot at 03:50 on 10-09.
The table has the same one row. The rebuild's `systemctl --user stop` at 09:01 on 10-09 added
no row either: the table still has one. Separately, the insert interpolates the shutdown
reason into SQL between single quotes and sends errors to `/dev/null` (L455-463), so a
reason with an apostrophe drops its row without a word.

**Next.** `KillMode=mixed` alone is not the fix: it sends SIGTERM only to the unit's main
process, the launcher, which has no `trap`, so the launcher would die at once and `dms` would
run on until systemd kills it, unsaved. The launcher needs to run `dms` in the background,
`wait` on it, and `trap` SIGTERM to forward it to `dms` (L395 starts it in the foreground,
and `dms` already shuts down cleanly on SIGTERM, `src/core/signals.c` L121). After `dms`
exits, the launcher writes the row and exits without relaunching. Then `KillMode=mixed` in
`deploy/systemd/duris-mud-production.service.in` and the installed unit lets it do so. Pass
the reason as data (for example hex-encoded into `UNHEX()`), not inside the SQL.

### 3. Plain HTTP to `ws.duris.sbs` gets a tunnel error

cloudflared logged `Unable to reach the origin service ... EOF` for
`https://ws.duris.sbs/robots.txt` at 2026-10-09 05:28:35. It logged the same for `/` twice
at 2026-10-08 18:00:07. Each lines up with a `Losing descriptor without char
[host=127.0.0.1 ... connected=18]` in the MUD's debug log, and a `lib/etc/hosts/*.127.0.0.1`
file of the same minute. The WebSocket listener (4050) drops a request without an
upgrade, so crawlers get a Cloudflare error page.

**Next.** Answer a plain GET on the WebSocket port with a short HTTP response (and
`robots.txt` with `Disallow: /`), or route only upgrade requests to 4050 at the tunnel.

### 4. `lib/etc/hosts` keeps every client's address and name

`hostname_lookup_worker()` and `resolve_descriptor_hostname_async()` (`src/net/comm.c`
L3638-3725) write one file per descriptor number and address, `lib/etc/hosts/<desc>.<address>`,
holding the reverse-DNS name. It removes the file only before the same pair is looked up again;
nothing else does, in `src/`, `scripts/` or the launcher. The directory had 139 files from
2026-10-04 on, most of them scanners, and 140 at the recheck. Players' addresses stay there
indefinitely, against the 30-day limit of
[ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md).

**Next.** Clear the directory at boot, and remove a descriptor's file when it closes (a
lookup can finish after the close, so the boot clear is still needed).

### 5. Nine shops ask for a buy rate the loader clamps

At every boot the shop loader caps a buy rate above 0.8 and logs `Shop #N: Old buy/sell`
(`src/economy/shop.c` L2383-2424) for shops 31310, 47061, 47070, 47097, 47116, 59081 and
59097 (1.0 to 0.8), and 89091 and 89118 (0.9 to 0.8). The 09:01 boot logs the same nine.

**Next.** Set those rates to 0.8 in the shop files so that the boot log carries nothing.

### 6. `logs/boot.log` is stale

`logs/boot.log` is dated 2026-10-04 22:05. Nothing in `scripts/` or `src/` writes it, and the
boot's stderr goes to the journal. It shows 15 `Recalculating zone numbers` warnings ("Heaven
has invalid number: 1 (should be 0)" and others). Neither the 03:50 boot nor the 09:01 boot
prints them, so the file misleads anyone who reads it.

**Next.** Delete it, or have the launcher write the boot's stderr there.

### 7. `cmd.debug` misses one-letter commands

`cmdlog()` records a command only when `*(str + 1) != '\0'` (`src/core/debug.c` L121). A
one-letter command (`n`, `s`, `k`) is never recorded. An empty line reads the byte past the
terminator, which is stale buffer content, and records a blank or stale entry. The
12:11-03:50 run has 11 such blank lines (`[1042] Bogum in 591075: `). `cmd.debug` holds the last
500 commands for crash forensics (`src/core/signals.c` L77), so the moves before a crash are
the part it loses.

**Next.** Test `*str != '\0'`.

### 8. Three log-hygiene defects

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
  line. Log the vnums.

### 9. `snoop` never tells its target, and nothing ages out players' addresses

Decided on 2026-10-09 in [ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md),
whose logging rule is in the code. Two parts are not:

- `snoop` needs level 60, but `do_snoop()` (`src/cmd/actwiz.c`) tells the target only when
  the snooper is below 58 or 59, so no target is ever told. It audits a snoop only below
  level 61. The decision: tell the target on start and stop, allow a silent snoop only at
  level 62 with a stated reason, and audit every snoop.
- Addresses are kept with no limit: `player-log/new` records each new character's, the log
  archives hold them in `comm` and `debug`, `lib/etc/hosts` keeps them (finding 4), and so
  do `log_entries`, `account_ips`, `account_login_history`, `ip_info` and the `last_ip`
  columns. The launcher drops the oldest archive past `LOG_ARCHIVE_LIMIT_MB`
  (`scripts/cycle_mud.sh` L309-312), which caps the size, not the age. The decision: 30
  days, except the ban list.

**Next.** The code changes and regression tests in ADR 0003's Consequences. Until the
30-day limit holds, treat a copy of `logs/` as player data.

### 10. Boot is slower since 2026-10-08 10:01

Boot took 9.5 to 10.1 s before the build promoted at 2026-10-08 10:01, and 12.0 to 12.3 s from
it on (12.0 s at 03:50 on 2026-10-09, and 11.8 s at 09:01). The extra time is in the boot-time
reset of all zones, which grew from about 7 s to about 9 s. The cause was not found. The
commits between the two builds are the place to look.

### 11. Any immortal can read a player's last 200 private messages with `recall`

Each player keeps their last 200 private messages in memory (`PRIVATE_LOG_SIZE`,
`src/player/player_log.h`) for their own `recall` command. `do_recall()`
(`src/cmd/actinf.c` L10021) lets any immortal add a player's name (L10030,
`if (*argument && IS_TRUSTED(ch))`) and read that player's instead, while the player is
online. The player is not told and nothing audits it. Nothing reaches disk, so it is not
logging, but it is a silent look at tells, against the rule of
[ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md).

**Decision** (owner, 2026-10-09): `recall <n> <player>` returns at once with "Disabled by
Zusuk October 9 2026". A player's own `recall` is unchanged. ADR 0003 records it with the
snoop rules.

**Next.** The early return in that branch, with a regression test that an immortal's
`recall` on another player gets the message and reads nothing.

## Checked: expected or benign

- **Restarts.** The service never crashed. `NRestarts=0` on every unit, and no exit 139 or
  signal appears. Every archived run with logs ends in a normal termination or the one in-game
  reboot (the first archive, 2026-10-04 22:11, is empty). That includes the 03:50-09:01 run,
  stopped for the rebuild at 09:01:42. No archive has a backtrace, assert, abort or sanitizer
  report. There are no core files and no failed user units. MariaDB started once and its InnoDB
  start was clean. Redis's 137 background saves all succeeded.
- **Zone resets.** `M cmd not executed` (322 lines) and `F cmd not executed` in `mob` are a
  rare load's percentage roll failing (`src/world/db.c` L3544), and `O cmd: obj ...` in `obj`
  is the object side. They appear only at boot: a load under 100% is rolled only by the boot's
  forced reset (L3517-3523 for mobs, L3578-3580 for objects), as the "Rareload" help entry
  says, and the known-benign table in `RUNBOOK.md` now says so too. The line's numbers are
  finding 8.
- **Mob data.** These are the loader's FYI lines. Every boot logs 58 `_RIDICULOUS_
  damage` lines for the same 22 mobs (`db.c` L2690-2709). The cap applies only to a local
  value, so the mobs keep their dice, as the message says. `RUNBOOK.md` already lists the
  line as known area data. The largest, 100d100+63, is "Mary, tailor of time" (142401 in
  `Voluntown.mob`), and her description says she is not to be trifled with. 10 `extreme
  exp` lines name Tiamat and the five dragon wyrms (100,000,000 each), among others
  (`db.c` L2281).
- **Item ownership.** `Item ownership reap: records of items no player holds deleted=71` at
  the 03:50 boot (29 at 10-08 10:01; none at 09:01) is the boot reap ADR 0002 describes.
- **Corpses.** Three test characters' corpses are restored at each boot with their decay timer
  refreshed. That is the crash-recovery rule.
- **MariaDB.** `Aborted connection ... Got timeout reading communication packets` comes about
  8 h after each boot. These are idle pool connections closed at `wait_timeout` (28,800 s).
  The main connection sets its own `wait_timeout` (`src/sql/sql.c` L1446-1450), and the pool
  replaces a closed connection when it hands it out (`src/sql/sql_pool.c` L231-247). The
  MUD logged no database error.
- **TLS and sockets.** `Write to SSL socket error: The specified session has been invalidated`
  (7 in all runs) and `getpeername: Transport endpoint is not connected` (2) are clients
  hanging up. `gnutls_handshake failed` lines (0 to 68 a run: "unexpected TLS packet",
  "No supported cipher suites") are scanners on the TLS port. They are at debug level since
  `345812f19`.
- **Boot and config.** Each boot logs that telemetry is disabled and that account recovery by
  mail is off (`MAIL_ENABLED` is not `TRUE`), as `.env` sets them. `Loaded creation
  availability config` comes twice per boot, from a lazy load and then the boot's own; that
  is harmless.
- **Host health.** `/` is 33% full and inodes are 3% used. The load was about 0.6 on 8 CPUs
  at the review, and 2.1 to 2.4 just after the rebuild, with no memory pressure. 2.6 of 8 GiB
  of swap is in use, MariaDB's share 97 MiB and none of it the MUD's. Time is in sync.
  `duris.crt` (`mud.duris.sbs`) is valid to 2027-01-03, and certbot runs cleanly.
- **Runtime state.** `runtime/` has an empty critical-command journal (only an empty
  `.service-lock`) and an empty telemetry-outage ledger. `maintenance-scheduler.state` is
  valid (`DMSMNT3`, version 3, 12 jobs), all of them idle at the review.

## Outside this repository

These turned up in the same logs and belong to other projects or to the host's owner:

- **DurisWeb.**
  - It logs the in-game reboot as `[MUD] MUD process crashed (not running)`, and logs
    `ECONNREFUSED 127.0.0.1:4050` while the MUD is down. The 09:01 service stop logged only
    three `ECONNREFUSED` lines.
  - It warns `[MUD Auction] Ignoring pre-authentication message: system` once each time it
    connects to the MUD: 11 times from 2026-10-08 12:03 to 2026-10-09 09:02. The MUD sends a
    `system` message before the service authenticates.
  - A graceful stop took 25 s, against `TimeoutStopSec=30s`.
- **Other tenants.**
  - `krynn-live.service` has been failed since 2026-10-01 06:31 (`Result: resources`, a
    minute after an ImageMagick upgrade). Krynn runs outside systemd.
  - The `/tmp` build logs belong to krynn (36 `-Wformat-truncation` warnings) and swrpg (a
    `tmpnam` warning). None is from duris.
- **Tooling.**
  - Codex's app server cannot start its sandbox: bubblewrap needs user namespaces.
  - Copilot Chat falls back to an in-memory database every session.
- **Host packages.** 20 packages can be upgraded, none from the security pocket.
