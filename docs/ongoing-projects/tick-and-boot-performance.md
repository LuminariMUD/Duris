# Investigations: the slow tick and the slower boot

Two performance findings of the 2026-10-09 log review, moved here on 2026-10-09 so that each
gets a proper investigation. The review's other open findings are in [plan.md](plan.md); its
own file was deleted then, and its last version is at `24e7d3fba`. Both investigations were
concluded on 2026-10-09: each section says what the issue is, then the measurements that show
it, what was ruled out and the proposed fix. This file is a working note: delete an
investigation when its fix has landed or been declined, and the file when none is left.

| # | Investigation | Severity | State |
|---|---|---|---|
| 1 | Every tick, `affect_update` walks all ~56,000 mobs (40 to 140 ms on staging), and the work it queues lands on pulses 0, 10 and 20, where the event pass runs over its budget | Low | Concluded; fix proposed, not started |
| 2 | Most of every boot is one shopkeeper-identity scan in the zone resets (7.4 billion comparisons); the 2 s step of 2026-10-08 is that scan's loop landing across a cache line, which staging's CPU runs 1.6 to 1.8 times slower | Low | Concluded; fix proposed, not started |

## In short

1. **The tick.** It is the idle world, not the players. Once per tick (300 pulses, 75 s)
   `affect_update()` walks every character, and on an idle server that is about 56,000 mobs.
   Locally, on a full idle world in staging's configuration, the pass costs 20 ms right after
   boot and 44 to 60 ms after 20 to 30 minutes, because the mobs keep casting buffs on
   themselves: their affects grow from 32,000 to 129,000, and 2,500 to 5,300 expire every
   tick. Staging's CPU is about 1.9 times slower on the same loops, hence 40 to 140 ms there.
   The pass queues two waves of events. Up to 3,200 `event_balance_affects` (one per mob whose
   buff expired) go to pulse 0, and about 12,000 `event_move_regen` (one per wandering mob a
   point or two short of full vitality) go to pulse 10. Each of those reschedules itself for
   pulse 20 only to find the mob full. With `generic_char_event`, a walk of all characters
   every 20 pulses, landing on the same pulses, pulses 0, 10 and 20 cost 12 to 17 ms locally
   while the others cost 3 to 4 ms. On staging they pass the 25 ms budget, and the tail, mostly
   the balance events because they are queued last, runs one pulse later. No pulse comes near
   250 ms, so players see nothing.
2. **The boot.** When a boot's zone reset loads the keeper of a fixed shop,
   `live_shopkeeper_for_identity()` walks the whole `character_list`. For every mob that keeps
   no shop, `singleton_shop_id()` then scans all 544 shops. That makes 519 walks,
   13.6 million shop-table scans and 7.4 billion comparisons per boot: 2.4 s of a 4.1 s local
   boot and about 8 s of staging's 12 s. It came in with `4cb743b6a` on 2026-09-22, before
   staging's first boot. Nothing in `a7e43bd0a..ca92ef1c2` changed it. The build of
   `ca92ef1c2` placed the scan's 24-byte loop across a 64-byte cache-line boundary. Staging's
   AMD Zen 3 CPU runs that at 0.74 to 0.85 ns per comparison instead of 0.44 to 0.51, which is
   the 2 to 3 s step; this workstation runs every placement at the same speed. Every staging
   build kept since has had the loop across a boundary. Making the scan cheap recovers about 8 s
   of every staging boot, whatever the alignment.

## Tools and methods that worked

- **A full world without a database:** the run-directory layout of
  `tests/async/run_cast_timing_probe.py` (flat-file, `REDIS=FALSE`) with `CHAOS_MUD=FALSE`,
  which is staging's configuration. It boots in about 4.5 s here, and runs idle for as many
  ticks as wanted. `logs/latency_trace.log` and `DURIS_NEVENT_ANALYTICS=1` work there as on
  staging.
- **Timers in a scratch build:** extract a tree with `git archive <sha> src Makefile` into
  `bin/analysis/`, add `clock_gettime()` sums logged once per tick or per boot step, and build it
  with `make -C <tree>/src BUILD_PROFILE=production OBJDIR=... DMS_BINARY=...
  EXTRA_CFLAGS=-Wno-error`. Never in the worktree.
- **Staging's speed, locally:** the loops that do not depend on the world (`activities`,
  `connections` in the latency trace) take about 1.9 times as long on staging as on this
  workstation. `DURIS_NEVENT_BUDGET_USEC=13000` here therefore stands in for staging's 25 ms
  budget.
- **MariaDB boots:** `tests/async/with_disposable_mariadb.sh` with the commit's own migrations
  (`migrations/bootstrap_multithread_safe.sql`, then `scripts/migration_runner.py adopt
  --kind fresh_bootstrap` and `run`).
- **Profiling on staging:** valgrind cannot load the server (its `.bss` is 1.76 GB, and
  valgrind 3.22 fails to map it; tried here), and `perf` needs root there
  (`perf_event_paranoid` is 4). gdb works with the server as its child (`ptrace_scope` is 1):
  start the server under `gdb -batch`, stop it with `SIGINT` every 0.2 s, and record
  `thread 1` plus `bt` each time.
- **A scratch boot on staging beside the live game:** the live binary, copied to a scratch
  directory, boots on loopback in the production role with `DURIS_PRODUCTION_PORT` set to its
  own port and `REDIS=FALSE`, against a copy of the database made inside staging's own MariaDB
  (`mariadb-dump duris_staging | mariadb <copy>`). Drop the copy, its user and the directory
  afterwards. Since the OS upgrade of 2026-10-09, staging's MariaDB is 11.8.6. Migrations 0031
  and 0032 verify only on MariaDB 10.11 or MySQL 8.0, so a fresh database can no longer be built
  there, though a copy of the live one can; [plan.md](plan.md) item 17 fixes that.
- **`Boot completed in: N milliseconds` is CPU time**, not wall time: `clock()` sums every
  thread's CPU since `run_the_game()` started (`src/net/comm.c` L846-L1010). The boot is single
  threaded, so on staging it tracks the wall-clock boot to within a second.

## 1. A slow pulse every tick on an idle server

### Evidence on staging

The pulse is 250 ms (`OPT_USEC`); the event wheel's budget is 25 ms
(`DURIS_NEVENT_BUDGET_USEC`). At most three players were on in the run of 2026-10-09 03:50 to
09:01. Even so, 198 of its 209 latency windows (read to 08:15) had a pulse over 50 ms, and the
worst pulse was 121 ms. The pattern is the same in every window:

- `affect_update` takes 40 to 115 ms on pulse 299, once per game tick. It is among the ten
  worst samples in 204 of the 207 windows that list them.
- `ne_events` spikes on pulses 0, 10 and 20 of the next tick.
- `event_balance_affects` is the latest callback in 172 of that run's 175 `NEVENT BUDGET WINDOW`
  lines, one pulse late (`max_late_ticks` counts scheduler ticks, which are pulses). The boot's
  first window deferred 71,643 events, with a catch-up debt of 8,976.

Every run with more than two windows shows it, on every build since 2026-10-04:

| Run ended | Windows | Over 50 ms | Worst pulse (us) | Worst `affect_update` (us) |
|---|---|---|---|---|
| 2026-10-05 03:12 | 237 | 228 | 125,847 | 120,410 |
| 2026-10-07 08:17 | 2,497 | 2,489 | 144,832 | 137,315 |
| 2026-10-08 10:01 | 1,232 | 1,226 | 475,386 | 130,946 |
| 2026-10-09 03:50 | 749 | 738 | 144,826 | 137,944 |
| 2026-10-09 09:01 (read to 08:15) | 209 | 198 | 121,020 | 114,971 |
| 2026-10-09 10:44 | 81 | 73 | 114,674 | 108,646 |

The 475 ms pulse on 2026-10-07 13:12:55 UTC was an immortal's `zreset` of Tharnadia
(`COMMAND OP SLOW ... operation=zreset duration_us=469879`), not the tick. In every run of
more than 20 windows, the median of each window's worst `affect_update` is 58 to 71 ms, the
cheapest pulse's event pass 3.0 to 3.6 ms and the average pass 5.3 to 5.6 ms. The run of
2026-10-08 12:11 to 2026-10-09 03:50 deferred 2.58 million callbacks in 15.6 hours, and all its
catch-up debt was repaid. The worst late event falls on pulse 1 or 2 in 738 of its 742
deferring windows.

### What one pass does

Measured locally on 2026-10-09: a production build of `24e7d3fba` with timers inside
`affect_update()` (`src/magic/affects.c` L3821), on a full idle world in staging's
configuration, with no player online:

| Tick after boot | Pass | Regeneration check | Affect countdown and expiry | of which `affect_remove()` | Falling check | Mobs walked | Mob affects | Affects expired |
|---|---|---|---|---|---|---|---|---|
| 1 | 19.7 ms | 9.3 ms | 3.7 ms | 0 | 3.6 ms | 55,031 | 31,912 | 0 |
| 4 | 29.8 ms | 10.2 ms | 13.1 ms | 2.8 ms | 3.7 ms | 55,766 | 84,419 | 882 |
| 8 | 52.9 ms | 12.3 ms | 31.9 ms | 11.1 ms | 5.7 ms | 55,961 | 106,772 | 2,516 |
| 16 | 59.9 ms | 11.7 ms | 40.6 ms | 19.4 ms | 4.5 ms | 56,201 | 122,676 | 5,337 |
| 24 | 49.7 ms | 10.3 ms | 29.9 ms | 11.3 ms | 6.8 ms | 56,504 | 128,784 | 3,507 |

The rest of the pass, the walk itself, disguises and the timers' own cost, is about 3 ms.
Every character walked is a mob. The affects that expire are the mobs' own spells and songs:
shadow shield, soulshield, minor globe, armor, fireshield, coldshield, stone skin, war cry,
infuriate. They are cast again, so the count climbs toward a plateau of about 130,000 after
30 minutes. A Chaos-mode run gives
the same picture (36 to 54 ms after 30 minutes).

The regeneration check finds 11,700 to 12,100 mobs below their maximum vitality every tick,
against 1 to 3 below their maximum hit points and a few hundred below their maximum mana (the
psionicist and mind flayer mobs). Of the vitality ones, 93 to 96% are wanderers (no
`ACT_SENTINEL`), short by 1 or 2 points on average, none with a zero regeneration rate: they
spent the points moving. `StartRegen()` (`src/world/events.c` L256) gives each one an
`event_move_regen` 10 pulses later (`MOB_MOVE_REGEN_DELAY`).

One pass queues 10,900 to 11,800 `event_move_regen` and up to 3,200 `event_balance_affects`
(1,459 and 2,239 at ticks 12 and 24 of the run above). The balance events are queued by
`balance_affects()` (`src/magic/affects.c` L487), with no delay and at most one per mob.

### Where the queued work lands: pulses 0, 10 and 20

Per pulse of the tick, in a local Chaos-mode run with per-pulse logging (which adds about 1 ms
to every pulse), ticks 3 to 8:

| Pulse of the tick | Event pass, mean (max) | Callbacks run | What runs |
|---|---|---|---|
| 0 | 14.5 ms (23.9 ms) | 2,500 | 1,200 to 3,300 `event_balance_affects` (about 3 us each), one `generic_char_event` (4.8 to 5.4 ms), a wave of `event_mob_mundane` |
| 10 | 12.5 ms (20.5 ms) | 12,400 | about 11,000 `event_move_regen` restoring 1 or 2 points |
| 20 | 16.8 ms (21.4 ms) | 12,400 | the same `event_move_regen` again, now finding the mob full and stopping, and `generic_char_event` |
| any other | 3 to 4 ms | about 1,000 | |

- `event_move_regen()` (`src/world/events.c` L178) applies the gain and then always
  reschedules itself (L206). The next run finds the mob at its maximum and returns. Half of the
  24,000 regeneration callbacks of every tick do nothing but find that out.
- `generic_char_event()` (`src/world/handler.c` L298) runs every 20 pulses. It walks all
  56,000 characters even though it does each character's work only once per full period, and
  it took over 5 ms 273 to 306 times in 30 minutes locally. Twenty divides 300, so it runs on
  pulses 0, 20, 40 and so on of every tick, two of them the tick's busy pulses. The per-pulse
  log names it only as an unnamed callback; it is identified by its period and by the
  analytics' per-window totals (15 calls, up to 6.2 ms).

### Why staging defers

The pass checks its budget after each callback and moves the rest of the bucket to the next
pulse (`nevent_defer_suffix()`, `src/world/new_events.c`). Pulses 0, 10 and 20 cost 12 to 17 ms
here, so at staging's speed they reach the 25 ms budget. The balance events are queued by
`affect_update()` after everything else due on pulse 0, so they are the tail of that bucket.
That is why `max_late_name` is almost always `event_balance_affects`, one pulse late, on pulse 1
or 2. With the budget scaled to staging's speed (13 ms), the local world defers 300 to 14,000
callbacks per window, all one pulse late: 23% `event_move_regen`, 20% `event_spellcast`, 18%
`event_mob_mundane`, 17% `event_balance_affects`, 8% `event_mana_regen`, 7% `event_wait`
(Chaos mode, whose mobs cast more). After 12 minutes, even this workstation has a pulse over
50 ms in 6 to 11 of every 14 windows (in the timed build, whose timers add a few ms to the
pass), and its cheapest pulse's event pass has risen from 0.6 to 1.4 ms. The tick grows with the
age of the world.

### The questions, answered

1. **Characters walked and their cost:** 55,000 to 56,500, all mobs on an idle server. The
   split is in the table above: the regeneration check 9 to 12 ms (12,000 events allocated),
   the affect countdown 4 to 40 ms (growing with the mobs' affects), about 3 us per expiring
   affect in `affect_remove()`, and the falling check 3.5 to 7 ms (56,000 `char_falling()`
   calls).
2. **Events queued, and what defers:** about 11,000 to 11,800 `event_move_regen` (pulse 10,
   then again on pulse 20) and up to 3,200 `event_balance_affects` (pulse 0). Those waves are
   what the next pulses defer.
3. **What the cost follows:** the mobs and the affects they carry. With nobody online, the
   pass rose from 20 ms to 45 to 60 ms in 30 minutes as the mobs' affects grew from 32,000 to
   129,000. Staging's at most three players are 0.005% of the characters walked. A run with
   players online was not made; nothing in the cost needs it.
4. **The 29.7 ms `event_mob_mundane` of 2026-10-08 12:07:34:** staging's log names the
   callback, not the mob. Locally, slow `event_mob_mundane` runs are one-offs from different
   mobs: a vault keeper (34570) 7.0 ms, a kobold warrior (1416) 10.9 ms, a dwarven undead
   spirit (30022) 5.9 ms, once each in about 70 minutes of timed idle runs and never repeated. At
   staging's speed those are 11 to 21 ms. It is not a pattern.
5. **Spreading the work without changing what players see:** yes for the event waves; see the
   fix. The pass itself only shrinks if it is sliced.

### Proposed fix

1. In `event_move_regen()`, and in the hit, mana and ward events of the same shape, stop
   rescheduling once the gain has brought the character to its maximum. This removes the
   pulse-20 wave of about 12,000 callbacks. The same points are restored at the same moments.
2. In `StartRegen()`, give an NPC's first event a per-mob offset within
   `MOB_MOVE_REGEN_DELAY` instead of +10 for all. This flattens the pulse-10 wave. The event
   counts elapsed pulses (`regen_elapsed_ticks()`), so the points restored stay the same.
3. Register `generic_char_event` on a pulse the tick does not use, such as 5, so it stops
   stacking on 0 and 20.
4. Sweep the NPCs in `affect_update()` in slices across the tick, as `generic_char_event`
   slices its per-character work, keeping players on the tick boundary. This removes the
   40 to 140 ms pass and spreads the balance events. An NPC's buff then wears off at its
   slice's pulse within the same tick instead of at the boundary.

Items 1 to 3 are small and invisible and remove the event-pass spikes; item 4 removes the
spike of the pass itself.

### Done when

A fix shows as fewer pulses over 50 ms in `logs/latency_trace.log` on an idle full world
(locally, 6 to 11 of 14 windows after 12 minutes today) and as `NEVENT BUDGET WINDOW` lines
becoming rare on staging.

## 2. Boot is 2 s slower since 2026-10-08 10:01

### Evidence on staging

Every boot, from the `status` log of each run. "Boot" is the `Boot completed` figure, which is
CPU time. "Zone resets" runs from `Boot time reset of all zones` to `Done scheduling events`, to
the second. "Loop" is where the build put the scan's loop (see below), where its binary was kept
or rebuilt.

| Run booted | Boot (ms) | Zone resets | Chaos | Loop |
|---|---|---|---|---|
| 2026-10-04 22:11 | 8,855 | 6 s | on | |
| 2026-10-04 22:15 | 9,786 | 6 s | on | |
| 2026-10-05 03:12 | 9,941 | 6 s | on | |
| 2026-10-05 04:03 | 9,502 | 7 s | on | |
| 2026-10-07 08:17 | 10,059 | 7 s | off | `a7e43bd0a`: fits in one line (built here) |
| 2026-10-08 10:01 | 12,316 | 9 s | off | `ca92ef1c2`: crosses (built here) |
| 2026-10-08 11:47 | 12,014 | 9 s | off | |
| 2026-10-08 12:11 | 12,283 | 9 s | off | crosses (staging's build of 12:09) |
| 2026-10-09 03:50 | 11,993 | 9 s | off | the same binary |
| 2026-10-09 09:01 | 11,779 | 9 s | off | crosses (build of 09:00) |
| 2026-10-09 10:44 | 12,365 | 9 s | off | crosses (build of 10:40) |
| 2026-10-09 12:00 | 13,533 | 10 s | off | crosses (build of 11:06) |
| 2026-10-09 13:04 | 12,094 | 9 s | off | the same binary, after the host's reboot and OS upgrade |

The staging checkout was fast-forwarded to `a7e43bd0a` at 2026-10-07 07:49 and to
`ca92ef1c2` at 2026-10-08 09:51, and each boot ran a binary built minutes earlier. Chaos mode
went off at the 2026-10-07 08:17 boot, and the WebSocket listener came on at the 2026-10-08
11:47 boot.

### Where every boot spends its time

Sampled on staging on 2026-10-09: the live binary booted in a scratch directory against a copy
of staging's database, stopped by gdb every 0.2 s through its zone resets. 47 of the 49 samples
were in `reset_zone()`, and 42 of those (89%) in `live_shopkeeper_for_identity()` →
`singleton_shop_id()`. The resets took 9.3 to 9.4 s of wall time, 9.1 to 9.2 s of the game
thread's user CPU, and 0.2 s of system time.

- A zone command `M` for a fixed (not replicated) shop's keeper (`src/world/db.c` L3505) asks
  `live_shopkeeper_for_identity()` (L3244) whether that shop already has a live keeper. It walks
  `character_list` until `singleton_shop_id()` says so. At boot none exists yet, so it walks the
  whole list.
- `singleton_shop_id()` (`src/world/world_singletons.c` L89) answers at once for a bound
  keeper. For every other mob it loops over all 544 `shop_index` entries, comparing each shop's
  keeper with the mob's prototype.
- Counted locally in one boot: 519 calls, 13,774,490 characters visited, 13,639,309 full
  shop-table scans, 7,419,784,096 comparisons. That is 2.40 s of the 2.92 s zone-reset phase
  (82%) and of a 4.1 s boot.
- It came in with `4cb743b6a` ("Prevent duplicate fixed shopkeepers after recovery",
  2026-09-22), before staging's first boot, so every staging boot pays it.

### Why it grew by 2 s on 2026-10-08

**Not the code in the range.** `a7e43bd0a` and `ca92ef1c2`, built here at the production
profile, boot equally fast round after round: flat-file with Chaos (4.3 to 4.8 s, four boots
each), flat-file without Chaos (4.27 to 4.49 s), MariaDB in the local role, and MariaDB in the
production role (`ca92ef1c2` equal or faster in every round). `singleton_shop_id()`,
`live_shopkeeper_for_identity()` and the sizes of `shop_data` (280 bytes) and `char_data`
(1,072 bytes) are the same in both.

**Not staging's data.** On staging, the live binary's resets took 9.32 to 9.43 s against a
copy of the database, and 9.27 to 9.32 s against the same copy with its accumulated state
deleted (accounts, players, items, corpses, shopkeepers, artifacts, ledgers). The resets'
only database work is a transaction per artifact loaded (about 40), which waits rather than
spending CPU.

**Not the host's memory or CPU.** The 13:04 boot, the first after the host's reboot and
upgrade, still took 12,094 ms with 9 s of resets. It had 5.3 GB free and no direct reclaim
(`allocstall` and `pgscan_direct` were 0). There are no cgroup limits, and transparent huge
pages are `madvise`. A CPU-only step after the resets (`World quest catalog ready ...
elapsed_ms`) took 356 to 383 ms in all twelve boots up to 12:00, fast or slow. The game loop's
own costs did not move at the step either: the median worst `affect_update` per window is 58
to 71 ms in every run of more than 20 windows.

**Not world data, Chaos or the WebSocket.** `world.mob`, `world.obj` and `world.wld` are
identical to the local build of the world, and `world.zon` differs by one bulletin board.
Chaos went off one boot before the step, and the WebSocket came on one boot after it.

**The loop's placement.** The slowdown is spread evenly: on the slow boots, every stretch of
the zone list from the 150th zone on takes 1.4 to 1.6 times as long as on the fast boots.
`singleton_shop_id()`'s scan is a 24-byte loop of eight instructions at offset `0xfb` in the
function. Where it falls in a 64-byte cache line depends on where the linker places the
function, which moves whenever code linked before it changes size. A build here reproduces
staging's layout exactly: `78763145a`, the
source of staging's build of 2026-10-09 11:06, puts `reset_zone`, `affect_update` and
`singleton_shop_id` at the same addresses here as in staging's binary. So the two builds made
here stand for staging's builds of those commits:

| Build | `singleton_shop_id` at byte | Loop at byte | Loop |
|---|---|---|---|
| `a7e43bd0a`, built here | 32 | 27 | fits in one line |
| `ca92ef1c2`, built here | 48 | 43 | crosses two lines |
| staging, built 2026-10-08 12:09 | 48 | 43 | crosses two lines |
| staging, built 2026-10-09 09:00 | 0 | 59 | crosses two lines |
| staging, built 2026-10-09 10:40 | 48 | 43 | crosses two lines |
| staging, built 2026-10-09 11:06 (running now) | 48 | 43 | crosses two lines |

The same eight instructions, placed at each position and run over 544 entries of 280 bytes
(ns per comparison):

| Loop at byte | | Staging (AMD Zen 3, 8 vCPUs) | This workstation (Intel) |
|---|---|---|---|
| 3 | fits | 0.441 | 0.207 |
| 11 | fits | 0.472 | 0.198 |
| 19 | fits | 0.512 | 0.204 |
| 27 | fits | 0.476 | 0.201 |
| 35 | fits | 0.477 | 0.197 |
| 43 | crosses | 0.852 | 0.201 |
| 51 | crosses | 0.753 | 0.204 |
| 59 | crosses | 0.742 | 0.205 |

At 7.4 billion comparisons that is about 3.5 s at byte 27 and 6.3 s at byte 43. The difference
of about 2.8 s is the step: resets from 6 or 7 s to 9 or 10 s, and boot CPU from 8.9 to 10.1 s
to 11.8 to 13.5 s. This workstation runs every placement at the same speed, which is why the
step never showed here. The step was chance placement, and any later build can land either way.
The cost underneath it is the scan.

### Other costs in every boot

- `restore_shopkeepers()`: `sql_restore_shopkeeper_catalog()` (`src/sql/sql_player.c` L3062)
  walks the whole `character_list` twice for each restored keeper (L3579 counts the incumbent,
  L3588 extracts it): 544 keepers × 2 × 54,500 characters, 59 million visits. That is 1.87 to
  1.91 s of its 1.99 to 2.01 s locally. The whole step takes 0.76 to 0.86 s on staging. It takes
  0.3 ms when the database has no saved shops, so a local second boot is about 2 s slower than
  the first boot on a new database.
- `remember_boot_shopkeepers()` (`src/world/world_singletons.c` L142) calls
  `singleton_shop_id()` once for every character: about 10 ms locally.
- At runtime, a zone reset whose fixed keeper is missing pays one full scan: about
  56,000 × 544 comparisons, 15 to 26 ms on staging at the two loop speeds. This is consistent
  with the local runtime `event_reset_zone` callbacks of 6 to 15 ms.

### Proposed fix

1. Make `singleton_shop_id()` answer at once for a mob whose prototype keeps no shop: build a
   per-prototype flag, or the list of each prototype's shops, once after the shops are booted,
   and return -1 when it is empty. The 13.6 million full scans become flag reads, and only the
   list walk is left, at about 0.45 s locally at the restore's measured 32 ns per visit.
2. Keep, per shop, the live keepers bound to it (updated where a keeper is bound and where it
   is extracted). `live_shopkeeper_for_identity()` and the restore's incumbent search then look
   it up instead of walking the list.

Item 1 alone takes the 7.4 billion comparisons out of every boot and every runtime reset.
Items 1 and 2 together should cut staging's boot by about 8 s: the scan's sampled share of the
resets plus the restore's 0.8 s. A local boot would drop from 4.1 s to under 2 s.

### Done when

The scan no longer shows in a sampled boot, and staging's `Boot completed` falls by several
seconds and stays there across rebuilds.
