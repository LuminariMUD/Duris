# Investigations: the slow tick and the slower boot

Two performance findings of the 2026-10-09 log review, moved here on 2026-10-09 so that each
gets a proper investigation. The review's other open findings are in [plan.md](plan.md); its
own file was deleted then, and its last version is at `24e7d3fba`. Each section holds the evidence so far, what the code does,
the questions to answer, a method and when it is done. This file is a working note: delete
an investigation when it is concluded and its fix has landed or been declined, and the file
when none is left.

| # | Investigation | Severity | State |
|---|---|---|---|
| 1 | A 40 to 140 ms pulse every 75 s from `affect_update` on an idle server, and the event wheel defers work in most windows | Low | Open |
| 2 | Boot takes about 12 s, up from about 10 s, since the build booted 2026-10-08 10:01 | Info | Open; commit range known |

## Tools on this host

- **`logs/latency_trace.log`**, always on: one summary per 300-pulse window (one game tick,
  75 s), with the minimum, maximum and average of each section (`total_tick`, `ne_events`,
  `affect_and_points`, `affect_update`, `point_update`, `activities`, `connections`,
  `commands`, `gmcp_flush`, `prompts`, `combat`) and the ten worst samples with their tick.
  Each restart archives it with the run's logs in `logs/old-logs/<date>/`.
- **`NEVENT BUDGET WINDOW`** lines in `logs/log/status`, one per window that deferred work or
  ran it late. `DURIS_NEVENT_ANALYTICS=1` adds per-pulse `NEVENT BUDGET` and `NEVENT CATCHUP`
  lines and per-callback timing (`NEVENT ANALYTICS WINDOW` and `CALLBACK`);
  `DURIS_NEVENT_BUDGET_USEC` sets the per-pulse budget (25,000 by default). Both are in
  [EVENTS.md](../reference/EVENTS.md) and `docs/operations/CONFIGURATION.md`.
- **`COMMAND OP SLOW`** and **`MUD TICK TOOK TOO LONG`** in `status` name a slow command.
- **Boot timing:** `Boot completed in: N milliseconds` in `status`. The boot's reset of
  every zone is the run of `reset_zone: ... force_item_repop: 2` lines (351 zones).
- **Profilers:** `valgrind` (callgrind) and `gprof` work for the `staging` user. `perf` is
  installed but `kernel.perf_event_paranoid` is 4, so it needs root to lower that first.
- **A world to measure on without touching staging:** the tests' isolated flat-file server
  (`IsolatedServer` in `tests/async/test_account_recovery_journey.py`) boots a disposable
  copy, though in `--minimal` mode; a full-world local server needs `make world` and its
  own ports.

## 1. A slow pulse every tick on an idle server

### Evidence

The pulse is 250 ms (`OPT_USEC`); the event wheel's budget is 25 ms
(`DURIS_NEVENT_BUDGET_USEC`). At most three players were on in the run of 2026-10-09 03:50 to
09:01. Even so, 198 of its 209 latency windows (read to 08:15) had a pulse over 50 ms, and the
worst pulse was 121 ms. The pattern is the same in every window:

- `affect_update` takes 40 to 115 ms on pulse 299, once per game tick. It is among the ten
  worst samples in 204 of the 207 windows that list them.
- `ne_events` spikes on pulses 0, 10 and 20 of the next tick.
- `event_balance_affects` runs one tick late in 172 of that run's 175 `NEVENT BUDGET WINDOW`
  lines. The boot's first window deferred 71,643 events, with a catch-up debt of 8,976.

Every run with more than two windows shows it, on every build since 2026-10-04:

| Run ended | Windows | Over 50 ms | Worst pulse (us) | Worst `affect_update` (us) |
|---|---|---|---|---|
| 2026-10-05 03:12 | 237 | 228 | 125,847 | 120,410 |
| 2026-10-07 08:17 | 2,497 | 2,489 | 144,832 | 137,315 |
| 2026-10-08 10:01 | 1,232 | 1,226 | 475,386 | 130,946 |
| 2026-10-09 03:50 | 749 | 738 | 144,826 | 137,944 |
| 2026-10-09 09:01 (read to 08:15) | 209 | 198 | 121,020 | 114,971 |
| 2026-10-09 10:44 | 81 | 73 | 114,674 | 108,646 |
| current, booted 10:44 (read to 11:19) | 27 | 19 | 89,956 | 81,231 |

The last two runs are the build of `master` at `d6fe4c210` and the one after the chat-log
change, so the cost is still there today.

The 475 ms pulse on 2026-10-07 13:12:55 UTC was an immortal's `zreset` of Tharnadia
(`COMMAND OP SLOW ... operation=zreset duration_us=469879`), not the tick. No pulse went past
250 ms otherwise, so players see no lag. But this is the tick's cost with nobody on: it scales
with the world, not the player count. The 200-player gate (`scripts/session14_gate.py`) has
never measured it under load.

The deferrals follow from the tick. Each character whose affects change gets an
`event_balance_affects` queued with no delay (`balance_affects()`, `src/magic/affects.c`
L488-493). Thousands land at once after the tick's `affect_update()` and overrun the 25 ms
budget on the next pulses: the worst late event falls on pulse 1 or 2 of the window in 738 of
the 742 deferring windows of the run of 2026-10-08 12:11 to 2026-10-09 03:50. That run
deferred 2.58 million callbacks in 15.6 hours, about 3,400 per window after boot, and about
75% more per window than the run of 10-07 to 10-08. The level was flat within the run. All the
catch-up debt was repaid. There was one `NEVENT SLOW`, on 2026-10-08 12:07:34: a single
`event_mob_mundane` callback took 29.7 ms in a 54 ms pass. The logs do not say which mob.

### What the code does

The game loop calls `affect_update()` once per tick (`src/net/comm.c` L2338, under
`if (!pulse)`), with `point_update()` after it, and times both into `affect_and_points`.
`affect_update()` (`src/magic/affects.c` L3821) walks every character in `character_list`:
every mob in the world, not only players. For each one below its maximum hit points,
vitality, mana (psionicists and mind flayers only) or ward it calls `StartRegen()`. For each
affect it counts the duration down, and an affect that runs out gets its wear-off message and
removal, which reaches `balance_affects()`.

### Questions

1. How many characters does one pass walk, and what does each cost? Split the pass into the
   walk, `StartRegen()`, and the affect countdown and removal.
2. How many events does one pass queue, by callback (regeneration, `event_balance_affects`,
   others), and which of them make up the work deferred on the next pulses?
3. Does the cost follow the number of mobs, the number of affects, or the players? An idle
   world shows it, so the base is the world.
4. Which mob was the 29.7 ms `event_mob_mundane`, and is it a pattern?
5. Would spreading the work over the tick remove the spike without changing what players see:
   a slice of `character_list` per pulse, or a spread of the balance and regeneration events?

### Method

1. On a local server with the full world (not staging), set `DURIS_NEVENT_ANALYTICS=1` and
   let it run idle for 20 ticks; keep `latency_trace.log` and the analytics windows.
2. Count the characters a pass walks and the events it queues, with a temporary counter in a
   local build.
3. Profile the pass with callgrind, collecting only inside it
   (`--toggle-collect=affect_update`), to split the cost by function.
4. Repeat with players on, from a scripted client, to see what they add.
5. If a fix spreads the work, compare the latency windows before and after on the same world.

### Done when

The pass's cost is attributed by function with numbers, the events it queues are counted by
callback, and a fix is chosen or the cost is accepted with its reason. A fix shows as fewer
pulses over 50 ms in `latency_trace.log` on an idle server.

## 2. Boot is 2 s slower since 2026-10-08 10:01

### Evidence

Every boot since the first staging boot, by the run's archive (named for its end), from the
`status` log of each run:

| Run booted | Boot (ms) | Boot zone resets (351 zones) |
|---|---|---|
| 2026-10-04 22:11 | 8,855 | 6 s |
| 2026-10-04 22:15 | 9,786 | 6 s |
| 2026-10-05 03:12 | 9,941 | 6 s |
| 2026-10-05 04:03 | 9,502 | 7 s |
| 2026-10-07 08:17 | 10,059 | 7 s |
| 2026-10-08 10:01 | 12,316 | 9 s |
| 2026-10-08 11:47 | 12,014 | 9 s |
| 2026-10-08 12:11 | 12,283 | 9 s |
| 2026-10-09 03:50 | 11,993 | 9 s |
| 2026-10-09 09:01 | 11,779 | 9 s |
| 2026-10-09 10:44 | 12,365 | 9 s |

The step is between the boots of 2026-10-07 08:17 and 2026-10-08 10:01, and it is in the
zone resets: they grew from 6 or 7 s to 9 s on the same 351 zones, about the whole 2 s. The
second resolution of the `reset_zone` lines cannot say which zones grew.

### The builds

The reflog of the staging checkout pins both builds. It was fast-forwarded to `a7e43bd0a` at
2026-10-07 07:49, and the binary booted at 08:17 was built at 08:16. It was fast-forwarded to
`ca92ef1c2` at 2026-10-08 09:51, and the binary booted at 10:01 was built at 10:00. So the
slower reset came in `a7e43bd0a..ca92ef1c2`: 70 commits, 66 of them not merges. Both binaries
are gone (the clean rebuild of 2026-10-09 removed `bin/server/history/`). The commits that
touch `src/`, `areas/` or `lib/`:

- falling: `ad4858fb7` (hold a falling character until the fall lands), `3a137f55c`,
  `baad34d91`, `80f8cd7d9`;
- wandering: `7e4030a65` (keep wandering mobs off Faang's canyon wall);
- item ownership: `61fa52894` (reap stale ownership records at boot), `0ca22fdcc`,
  `9f157be7a`;
- the rest, unlikely to touch a zone reset: telemetry (`f7368e60e`, `ce09d17bc`,
  `476376592`, `95cf073c7`, `2f101c275`, `56f2305b7`, `ffc349606`, `489c17d07`), logging and
  start-up (`5e9b90b22`, `345812f19`, `cad2fc5ec`, `21f26b3b1`, `d84d7f083`), casting
  (`f461a9b91`) and documentation (`5a535d819`).

The world data changed little in the range: six files under `areas/` and `lib/`, 14 lines
added and 19 removed.

### Questions

1. Which commit in the range adds the 2 s, and which zones grew?
2. Is the extra time per object or mob loaded (an ownership record, a fall check), or a fixed
   cost of some zones?
3. Is it needed at boot, or can the boot skip it, as it skips other per-load work?

### Method

1. Build `a7e43bd0a` and `ca92ef1c2` locally with the same world and time the boot's zone
   resets on each, to confirm the step outside staging.
2. Time each zone's reset: a temporary microsecond timer around `reset_zone()` in a local
   build, or callgrind on the boot with `--toggle-collect=reset_zone`.
3. Bisect the candidates above, falling and ownership first, by the reset time.

### Done when

The commit that added the time and the work it does per reset are named, and the time is
recovered or accepted with its reason.
