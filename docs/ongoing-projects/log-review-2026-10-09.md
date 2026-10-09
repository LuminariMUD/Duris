# Log review, 2026-10-09

Written 2026-10-09 on the staging host, against `master` at `639f6fd55`. It covers every log
this account can read, from the first staging boot (2026-10-04 22:11 UTC) to about 08:15 UTC
on 2026-10-09. Each finding gives the evidence, the cause where it was found, and a next step.
Findings already tracked in the 2026-10-08 plan are listed only to say whether they still show;
that plan finished on 2026-10-09, and its file was deleted in `ef891cc54`.
This file is a working note: when a finding is fixed, moved into a plan, or dropped, mark it
here. Delete the file when every row is settled.

Read:

- The current run's server logs: `logs/log/*`, `logs/player-log/*` and
  `logs/latency_trace.log`, from the boot at 03:50:37 UTC.
- The nine archived runs in `logs/old-logs/<date>/`, and the stale `logs/boot.log`.
- The user journal for `duris-mud-production`, `duris-mariadb`, `duris-redis`, cloudflared and
  the DurisWeb units. MariaDB and Redis write their logs to that journal. Also read:
  `runtime/`, the `server_reboots` table, and the MariaDB and Redis status counters.
- The readable host logs: `dpkg`, `apt/history`, `sa-update`, `fontconfig`,
  `ubuntu-advantage`, `landscape`, and the empty `nginx`, `ufw` and `stunnel` logs. Also
  `wtmp`, `/proc`, `/etc/ssh` and the TLS certificate.
- The build and test logs: those in `/tmp`, those in earlier sessions' scratchpads, and the
  editor and agent tool logs under `~/.vscode-server`, `~/.copilot` and `~/.codex`.

Not read, because `staging` cannot read them without root:

- `syslog`, `kern.log`, `auth.log`, `mail.err`, `php8.3-fpm.log`, `cloud-init`, `apt/term.log`
  and `btmp`.
- The system journal, `dmesg`, the Plesk and Apache logs, and
  `/etc/ssh/sshd_config.d/50-cloud-init.conf`.

So kernel segfault or OOM lines cannot be ruled out from the logs. No unit shows an OOM event,
the host's `oom_kill` count is 0 since boot, and `/var/crash` is empty. `kern.log` grew from
12.8 KB (2026-09-27 to 10-03) to 356 KB since 10-04, and someone with root should read it
(finding 4).

## Summary

| # | Finding | Severity | State |
|---|---|---|---|
| 1 | Staging runs a binary built before the 2026-10-09 merges: 18 source commits behind, with four crash and memory fixes not live | Medium | Open |
| 2 | SSH offers passwords, permits root, and nothing limits attempts | Medium (host) | Open, owner |
| 3 | Nothing backs up the MUD's persistence on staging except DurisWeb's hourly dump | Low-medium | Open, decision |
| 4 | Root-only logs are unread while they grow | Low | Open, owner |
| 5 | A 40 to 140 ms pulse every 75 s from `affect_update` on an idle server, and the event wheel defers work in most windows | Low | Open |
| 6 | `server_reboots` records one of nine restarts: a service stop kills the launcher before it writes | Low | Open |
| 7 | Staging Redis and the MUD run replaced binaries (Redis with two CVE fixes waiting), and a new kernel is not booted | Low | Open, restart |
| 8 | Plain HTTP requests to `ws.duris.sbs` reach the MUD's WebSocket port and get a tunnel error | Low | Open |
| 9 | `lib/etc/hosts` keeps every client's address and reverse-DNS name, and nothing prunes it | Low | Open |
| 10 | Nine shops ask for a buy rate the loader clamps at every boot | Low | Open, data |
| 11 | `logs/boot.log` is stale since 2026-10-04 and nothing writes it | Low | Open |
| 12 | Every boot, a slave in the Vault of Avernus picks up the vault's two 1500p piles | Info | Open, builder |
| 13 | A mob whose zone load chance is under 100% is rolled only at boot | Info | Open, decision |
| 14 | `cmd.debug` never records a one-letter command, and records stale text for an empty line | Low | Open |
| 15 | Wizard broadcasts go into `status` raw, and a lost peer's host is a color code | Low | Open |
| 16 | The logs hold players' private tells and addresses | Info | Open, decision |
| 17 | Boot takes about 12 s, up from about 10 s, since the build booted 2026-10-08 10:01 | Info | Open |

## Findings

### 1. Staging runs a build from before the 2026-10-09 merges

`bin/server/dms` was built 2026-10-08 12:09:08 UTC (stamp `mariadb/production`) and promoted
by the service restart at 12:11:02. The restart at 03:50 on 10-09 was an in-game
`shutdown reboot`; it relaunched the same binary. No `dms_new` is staged, so the next restart
would also relaunch it. `master` has 18 source commits that the live server does not
(`git log --no-merges 278a7069f..master -- src`). They include all of Phases 2 and 3:

- `b20612298`: a telnet connection from a banned address crashed the server. Staging has no
  `lib/misc/ban_sites` today, so the first ban an immortal adds makes this reachable.
- `7a16e9c13`: the snoop copy of an output block could run past its 64 KB buffer ("stack
  smashing detected" on a production build). An immortal reaches it by snooping a player who
  lists a large shop.
- `c4a9eb681` and `4c4557d76`: the shop listing's stack overflow.
- `3bc4fa8bb`: the TLS session leaked for each connection a full server refuses.
- `dad3822f6`, `90cb04769`, `2843a9a0c`: the per-address cap on connections that have not
  logged in, and the 120 s login timeout. Staging takes scanner connections every hour:
  21 of the 23 `Losing descriptor without char` lines in this run are at the account name
  prompt (`connected=60`).
- `7c21ef491`, `b4e6fb0b0`, `3fb6883e6`, `546605f93`: the trusted-proxy and `X-Forwarded-For`
  fixes. This one bites here: `.env` sets `DURIS_TRUSTED_PROXY_IP=127.0.0.1`, which the live
  binary never matches on its IPv6 listeners. So every website player comes from
  127.0.0.1, and a completed WebSocket handshake closes any other website login still in
  progress, as a stale connection from the same address. The close goes to immortals in game
  (`statuslog`), not to a file, so the logs only show its side: `host=127.0.0.1
  connected=60` drops in `debug`.

**Next.** Build the production server (`make -C src PERSISTENCE_BACKEND=mariadb
BUILD_PROFILE=production -j4`) and restart `duris-mud-production`. The restart also picks up
the new `libxml2` (finding 7).

### 2. SSH accepts passwords, permits root, and nothing limits attempts

`/etc/ssh/sshd_config` L132 is `PermitRootLogin yes`. The readable drop-in
`60-cloudimg-settings.conf` says `PasswordAuthentication no`, but a probe of sshd, on
127.0.0.1 and on the public address, answers `Permission denied (publickey,password)`, so
passwords are offered. sshd takes the first value it reads, and `50-cloud-init.conf` (root-only,
27 bytes) is read before the 60 file; it is probably `PasswordAuthentication yes`. fail2ban is
not installed. ufw is off (`ENABLED=no`); the Plesk firewall is the active one, and its rules
could not be read. `auth.log` grows about 11 MB a day. Root can read it to tell brute force
from PAM and cron noise; `staging` cannot. `wtmp` shows 15 interactive sessions from 7
addresses in 14 days, and no root login since 2025-09. One session (`swrpg`, 2026-09-26) came
from a hosting-type range, and the owner should confirm it.

**Next** (owner, root). Read `50-cloud-init.conf`. Set `PasswordAuthentication no` and
`PermitRootLogin prohibit-password` (or `no`) where they take effect, and check them with
`sshd -T`. Add fail2ban or a Plesk equivalent. This host serves other tenants (krynn, swrpg,
aod), so agree the change with them.

### 3. Nothing backs up the MUD's persistence on staging except DurisWeb's dump

`.env` sets neither `BACKUP_POLICY_FILE` nor `PREBOOT_BACKUP`. The user manager has no backup
timer and `staging` has no crontab, so `scripts/persistence_backup.py` never runs here, and
`cycle_mud.sh` skips the pre-boot backup (L318-323). The one database copy is DurisWeb's
hourly dump in `/home/staging/durisweb-backups`: 20 of 20 succeeded from 2026-10-08 13:00 to
2026-10-09 08:00, and the latest holds `database/duris_staging.sql` (61 MB). That dump is
not the verified, drilled backup `docs/operations/BACKUPS.md` describes, and its restore has
not been tried. `/home/staging/backups/duris/2026-10-07-prebuild` is a one-off copy of a binary
and the scheduler state.

**Next** (decision). Staging may not need more than this. If it does, install the policy and
the sample units in `deploy/systemd/duris-backup-*` as `BACKUPS.md` says, or set
`PREBOOT_BACKUP=1`.

### 4. Root-only logs are unread while they grow

These logs could not be read (see the top of this file). Some are growing:

- `kern.log`: about 28 times its rate of the week before.
- `mail.err`: 172 KB, last written 2026-10-08 05:48.
- `php8.3-fpm.log`: about 1.7 MB a week.
- `auth.log`: see finding 2.

`/var/log/sa-update.log` is readable. It is a 41 MB debug-level log (426,000 lines since
2026-07-31), it is not rotated, and SpamAssassin runs without Mail::SPF, Razor2 and
Mail::DMARC. That is Plesk mail, not the MUD.

**Next** (owner, root):

```bash
sudo grep -E 'segfault|traps:|oom-kill|I/O error|EXT4-fs error' /var/log/kern.log*
sudo tail -50 /var/log/mail.err
```

Also summarize failed SSH logins with `lastb` or `auth.log`.

### 5. A slow pulse every 75 s on an idle server

The pulse is 250 ms (`OPT_USEC`); the event wheel's budget is 25 ms
(`DURIS_NEVENT_BUDGET_USEC`). At most three players were on in this run. Even so, 198 of its
209 latency windows (`logs/latency_trace.log`, 300 pulses each) had a pulse over 50 ms. The
worst pulse was 121 ms. The pattern is the same in every window:

- `affect_update` takes 40 to 115 ms on pulse 299, once per game tick. It is among the ten
  worst samples in 204 of the 207 windows that list them.
- `ne_events` spikes on pulses 0, 10 and 20 of the next tick.
- `event_balance_affects` runs one tick late in 172 of this run's 175 `NEVENT BUDGET WINDOW`
  lines. The boot's first window deferred 71,643 events, with a catch-up debt of 8,976.

Every archived run with more than two windows shows the same spikes. The longer runs:

| Run ended | Windows | Over 50 ms | Worst pulse (us) | Worst `affect_update` (us) |
|---|---|---|---|---|
| 2026-10-05 03:12 | 237 | 228 | 125,847 | 120,410 |
| 2026-10-07 08:17 | 2,497 | 2,489 | 144,832 | 137,315 |
| 2026-10-08 10:01 | 1,232 | 1,226 | 475,386 | 130,946 |
| 2026-10-09 03:50 | 749 | 738 | 144,826 | 137,944 |
| current | 209 | 198 | 121,020 | 114,971 |

The 475 ms pulse on 2026-10-07 13:12:55 UTC was an immortal's `zreset` of Tharnadia
(`COMMAND OP SLOW ... operation=zreset duration_us=469879`), not the tick. No pulse went past
250 ms otherwise, so players see no lag. But this is the tick's cost with nobody on: it scales
with the world, not the player count. The 200-player gate (`scripts/session14_gate.py`) has
never measured it under load.

The deferrals follow from the tick. Each character whose affects change gets an
`event_balance_affects` queued with no delay (`balance_affects()`, `src/magic/affects.c`
L488-493). Thousands land at once after the tick's `affect_update()` and overrun the 25 ms
budget on the next pulses: the worst late event falls on pulse 1 or 2 of the window in 738
of the last archived run's 742 deferring windows. That run deferred 2.58 million callbacks
in 15.6 hours, about 3,400 per window after boot, and about 75% more per window than the
run of 10-07 to 10-08. The level was flat within the run. All the catch-up debt was repaid.
There was one `NEVENT SLOW`, on 2026-10-08 12:07:34: a single `event_mob_mundane` callback took
29.7 ms in a 54 ms pass. The logs do not say which mob.

**Next.** Profile one `affect_update` pass on a local copy of the world, and find what it
walks: every character, or every affect. Decide whether the balance events should be spread
over the tick instead of queued for the same pulse. Find the slow `event_mob_mundane` with
`DURIS_NEVENT_ANALYTICS=1` on a local server.

### 6. `server_reboots` records one restart in nine

The launcher writes the row after `dms` exits (`scripts/cycle_mud.sh` L418-461). A
`systemctl --user restart` or `stop` signals the whole control group
(`KillMode=control-group`), so the launcher dies with the server and never writes. The
journal has one `Logged reboot` line in nine boots: the in-game reboot at 03:50 on 10-09.
The table has the same one row. Separately, the insert interpolates the shutdown reason into
SQL between single quotes and sends errors to `/dev/null` (L452-460), so a reason with an
apostrophe drops its row without a word.

**Next.** Write the row from the server at shutdown, or give the unit `KillMode=mixed` so
that only `dms` gets the first signal. Pass the reason as data, not inside the SQL.

### 7. Replaced binaries still running, and a new kernel not booted

- The staging Redis (6381, running since 2026-10-04) still runs the binary that the 2026-10-08
  06:36 upgrade replaced: `/proc/<pid>/exe` is `/usr/bin/redis-check-rdb (deleted)`. The update
  fixes CVE-2026-81934 (a TLS use-after-free) and CVE-2026-92925 (cluster-bus PING).
  Redis listens only on 127.0.0.1 without TLS or cluster mode, so the exposure is small.
- The MUD has `libxml2.so.2.9.14 (deleted)` mapped. The 2026-10-09 06:49 upgrade fixes three
  CVEs, and the restart in finding 1 picks it up.
- `linux-image-6.8.0-146` was installed by unattended-upgrades at 06:49 on 10-09. The host
  runs 6.8.0-142 and has been up since 2026-09-25, and `/run/reboot-required` is not set.

**Next.** Restart `duris-redis` with the MUD's next restart. The kernel is the owner's call
for the whole host.

### 8. Plain HTTP to `ws.duris.sbs` gets a tunnel error

cloudflared logged `Unable to reach the origin service ... EOF` for
`https://ws.duris.sbs/robots.txt` at 2026-10-09 05:28:35. It logged the same for `/` twice
at 2026-10-08 18:00:07. Each lines up with a `Losing descriptor without char
[host=127.0.0.1 ... connected=18]` in the MUD's debug log, and a `lib/etc/hosts/*.127.0.0.1`
file of the same minute. The WebSocket listener (4050) drops a request without an
upgrade, so crawlers get a Cloudflare error page.

**Next.** Answer a plain GET on the WebSocket port with a short HTTP response (and
`robots.txt` with `Disallow: /`), or route only upgrade requests to 4050 at the tunnel.

### 9. `lib/etc/hosts` keeps every client's address and name

`resolve_descriptor_hostname_async()` (`src/net/comm.c` L3637-3712) writes one file per
descriptor number and address, `lib/etc/hosts/<desc>.<address>`, holding the reverse-DNS name.
It removes the file only before the same pair is looked up again; nothing else does, in
`src/`, `scripts/` or the launcher. The directory has 139 files from 2026-10-04 on, most of
them scanners. Players' addresses stay there indefinitely, beside the retention questions
in finding P00-S08 of `docs/records/SECURITY-COMPLIANCE.md`.

**Next.** Remove a descriptor's file when the descriptor closes, or clear the directory at
boot.

### 10. Nine shops ask for a buy rate the loader clamps

At every boot the shop loader caps a buy rate above 0.8 and logs `Shop #N: Old buy/sell`
(`src/economy/shop.c` L2398-2424) for shops 31310, 47061, 47070, 47097, 47116, 59081 and
59097 (1.0 to 0.8), and 89091 and 89118 (0.9 to 0.8).

**Next.** Set those rates to 0.8 in the shop files so that the boot log carries nothing.

### 11. `logs/boot.log` is stale

`logs/boot.log` is dated 2026-10-04 22:05. Nothing in `scripts/` or `src/` writes it, and the
boot's stderr goes to the journal. It shows 15 `Recalculating zone numbers` warnings ("Heaven
has invalid number: 1 (should be 0)" and others). The current boot does not print them, so
the file misleads anyone who reads it.

**Next.** Delete it, or have the launcher write the boot's stderr there.

### 12. The Vault of Avernus loses its coins at boot

Every run (all eight archived runs with a debug log, and the current one) logs two lines
like `a pitiful slave (19953) got 1500p from room.` within a minute of boot
(`src/cmd/actobj.c` L610). Room 19953 is the Vault of Avernus in `astral_tiamat`. The zone
loads the coin piles there, and a slave in the room picks them up before any player can
arrive. Killing the slave gets them back, so this is a builder's question: is that intended?

### 13. A mob whose load chance is under 100% is rolled only at boot

`reset_zone()` skips an `M` command whose chance (`arg4`) is not 100 unless
`force_item_repop` is set (`src/world/db.c` L3505-3527). Only the boot's reset sets it. In
this run, 2,438 zone resets ran with `force_item_repop: 0`, and the 351 boot resets with 2.
All 322 `M cmd not executed` lines in `mob` fall inside the boot's reset (03:50:26 to
03:50:35), and they name 194 distinct mobs, most at 25%, 50% or 33%. The last archive is the
same: 326 lines, all at boot. So a chance mob that misses its roll at boot is absent until
the next reboot. One that loads and is killed does not come back
either. `docs/content/area_writing.txt` (about L3341) tells builders that percentage loads
make a quest "slightly different each time the PCs try to complete it", which is not what
happens between reboots. The line itself logs internal mob and room indices, not vnums, so
a builder cannot read it.

**Next** (decision). Either roll chance mobs at each reset, within the limit, or document
that they are boot-only. Either way, log vnums.

### 14. `cmd.debug` misses one-letter commands

`cmdlog()` records a command only when `*(str + 1) != '\0'` (`src/core/debug.c` L121). A
one-letter command (`n`, `s`, `k`) is never recorded. An empty line reads the byte past the
terminator, which is stale buffer content, and records a blank or stale entry. The latest
archive has 11 such blank lines (`[1042] Bogum in 591075: `). `cmd.debug` holds the last 500
commands for crash forensics (`src/core/signals.c` L77), so the moves before a crash are
the part it loses.

**Next.** Test `*str != '\0'`.

### 15. Two log-hygiene defects

- Each timed shutdown, reboot or copyover writes its broadcast to `status` as players see it,
  with `\r\n` and color codes (`src/cmd/actwiz.c` L4430, L4440, L4451). The last archive's
  `status` ends with an empty `::` line, then `Zusuk shreds the world around you.` on a line
  of its own. Log the issuer and the kind instead.
- When `getpeername()` fails in `new_descriptor()`, the host is set to `&+RUNTRACEABLE&n`
  (`src/net/comm.c` L3842-3845), and the color code goes into every log line about that
  descriptor. This happened twice, on 2026-10-08 at 18:43:23 and 18:46:15, both with a
  `Connection reset by peer`. Use a plain `unknown`.

### 16. The logs hold private tells and addresses

The `chat` log (new in the last archive, 66 lines) records tells between players.
`player-log/new` records each new character's address. `lib/etc/hosts` keeps addresses
too (finding 9). The files are `0600`, and the launcher drops the oldest archive past
`LOG_ARCHIVE_LIMIT_MB` (`scripts/cycle_mud.sh` L309-312), which caps the size, not the age.
This belongs with the retention decision in finding P00-S08 of
`docs/records/SECURITY-COMPLIANCE.md`. Until then, treat a copy of `logs/` as player data.

### 17. Boot is slower since 2026-10-08 10:01

Boot took 9.5 to 10.1 s before the build promoted at 2026-10-08 10:01, and 12.0 to 12.3 s
from it on (12.0 s on 2026-10-09). The extra time is in the boot-time reset of all zones,
which grew from about 7 s to about 9 s. The cause was not found. The commits between the
two builds are the place to look.

## Fixed since the first runs

These patterns stopped with a commit and have not come back:

| Pattern | Last run that shows it | Fix |
|---|---|---|
| `sql job not queued` from `artifact_row_store`, `arti_redis_cache`, `save_outpost_record` and `redis_cache_fraglist` (35 to 62 a run); the boot's Redis caches were not primed | ended 2026-10-07 08:17 | `92fce27db`, `ee927e1a7` |
| `player_snapshot_capture: ... outcome=unowned_object` (up to 834 a run) and `player_load_materialize: ... missing_payload_rows` (up to 6) | ended 2026-10-08 10:01 | `61fa52894` (now trace-only) |
| `get_mud_info(): requested mud_info 'lock', but doesn't exist!` | ended 2026-10-07 08:17 | `53b51de63` |
| `sql_world_quest_can_do_another: history not loaded yet` | ended 2026-10-07 08:17 | `87cca01d2` |
| `process_input() ... Error: 104` and TLS pull errors (72 and more) | ended 2026-10-07 08:17 | `9f027d69d` |
| The 15 `has invalid number` zone warnings at boot | `logs/boot.log`, 2026-10-04 | not traced; the current boot prints none |

## Already tracked in the 2026-10-08 plan

- **Phase 2** (landed on `master`, not live here; finding 1): `Losing descriptor without
  char` from scanners at the account name prompt. There were 2, 595, 181, 937, 130, 14, 11
  and 79 lines in the archived runs, and 21 so far in the current one. Two floods: one
  address opened 583 connections in 41 minutes on 2026-10-05, and another 757 in 49 minutes
  the same day.
- **Phase 5** (landed on `master` in `2584ad609` after this review, not live here):
  `STUDIOPROC: no areas/world.trg, proc engine idle.` at every boot.
- **Phase 8** (landed on `master` in `eb34cf799` after this review, not live here): the
  specials assigned to vnums not in the world. An earlier session's `stale_specs.out`
  counts the same 17 object, 86 mobile and 18 room assignments, and the cited lines were
  still in `src/specs/specs.assign.c` at `639f6fd55`.
- **Phase 9** (landed on `master` in `115fba006` after this review, not live here):
  `degenerate board!  (what the hell...)` in `board`. It shows 6 times in the run that ended
  2026-10-08 10:01, and once in the last archive (2026-10-08 21:24:35). It has not shown yet
  in the current run.

## Checked: expected or benign

- **Restarts.** The service never crashed. `NRestarts=0` on every unit, and no exit 139 or
  signal appears. Every archived run with logs ends in a normal termination or the one
  in-game reboot (the first archive, 2026-10-04 22:11, is empty). No archive has a
  backtrace, assert, abort or sanitizer report. There are no core files and no failed user
  units. MariaDB started once and its InnoDB start was clean. Redis started once, with 137
  background saves, all ok.
- **Zone resets.** `M cmd not executed` (322 lines) and `F cmd not executed` in `mob` are a
  zone command's percentage roll failing (`src/world/db.c` L3544). `RUNBOOK.md` L554 calls
  them area data; finding 13 is what they show about the engine. `O cmd: obj ...` in `obj`
  is the object side.
- **Mob data.** These are the loader's FYI lines. Every boot logs 58 `_RIDICULOUS_
  damage` lines for the same 22 mobs (`db.c` L2690-2709). The cap applies only to a local
  value, so the mobs keep their dice, as the message says. `RUNBOOK.md` already lists the
  line as known area data. The largest, 100d100+63, is "Mary, tailor of time" (142401 in
  `Voluntown.mob`), and her description says she is not to be trifled with. 10 `extreme
  exp` lines name Tiamat and the five dragon wyrms (100,000,000 each), among others
  (`db.c` L2281).
- **Item ownership.** `Item ownership reap: records of items no player holds deleted=71` at
  this boot (29 at 10-08 10:01) is the boot reap ADR 0002 describes.
- **Corpses.** Three test characters' corpses are restored at each boot with their decay timer
  refreshed. That is the crash-recovery rule.
- **MariaDB.** `Aborted connection ... Got timeout reading communication packets` comes about
  8 h after each boot. These are idle pool connections closed at `wait_timeout` (28,800 s).
  The main connection sets its own `wait_timeout` (`src/sql/sql.c` L1446-1450), and the pool
  replaces a closed connection when it hands it out (`src/sql/sql_pool.c` L231-247). The
  MUD logged no database error.
- **MariaDB access.** All 51 `Access denied` events are explained:
  - 49 are `durisweb_test` on 2026-10-08 12:22-12:27: a DurisWeb test against a user this
    server does not have.
  - 1 is `root@localhost`.
  - 1 is a session that read `$DB_PASSWORD` instead of `DB_PASSWD`.

  The 13 `error reading communication packets` lines fall in the 10-08 deploys.
  `max_open_files` is capped at 16,384 by the unit's `LimitNOFILE`, against 32,190 asked
  for. That is harmless at `Max_used_connections=12`.
- **Redis.** It counts 58 `ERR`, 23 `NOPERM` and 1 `NOAUTH` errors, and 20 rejected `eval`
  calls. The ACL log's three entries are DurisWeb users on 2026-10-08 about 11:45, the
  minute before `users.acl` was edited.
- **TLS and sockets.** `Write to SSL socket error: The specified session has been invalidated`
  (7 in all runs) and `getpeername: Transport endpoint is not connected` (2) are clients
  hanging up. `gnutls_handshake failed` lines (0 to 68 a run: "unexpected TLS packet",
  "No supported cipher suites") are scanners on the TLS port. They are at debug level since
  `345812f19`.
- **Boot and config.** Each boot logs that telemetry is disabled and that account recovery by
  mail is off (`MAIL_ENABLED` is not `TRUE`), as `.env` sets them. `Loaded creation
  availability config` comes twice per boot, from a lazy load and then the boot's own; that
  is harmless.
- **Host health.** `/` is 33% full and inodes are 3% used. The load is about 0.6 on 8 CPUs,
  with no memory pressure. 2.6 of 8 GiB of swap is in use, MariaDB's share 97 MiB and none of
  it the MUD's. Time is in sync. `duris.crt` (`mud.duris.sbs`) is valid to 2027-01-03, and
  certbot runs cleanly.
- **Builds and tests.** The duris build and test logs in earlier sessions' scratchpads are
  clean: 0 warnings under `-Werror`, and 671 passed, 0 failed on 2026-10-07.
- **Runtime state.** `runtime/` has an empty critical-command journal and an empty
  telemetry-outage ledger. `maintenance-scheduler.state` holds 12 jobs, all idle.

## Outside this repository

These turned up in the same logs and belong to other projects or to the host's owner:

- **DurisWeb.**
  - It logs the in-game reboot as `[MUD] MUD process crashed (not running)`, and logs
    `ECONNREFUSED 127.0.0.1:4050` while the MUD is down.
  - 344 CORS rejections fell on 2026-10-08 before a deploy, and none since.
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
