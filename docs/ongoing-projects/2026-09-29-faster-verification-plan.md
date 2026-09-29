# Faster verification: the same tests, without the waiting

**Date:** 2026-09-29

**Status:** Landed on master on 2026-09-29, as far as master allows. The plan below was measured
on a branch that is not merged yet; [Landed on master](#landed-on-master) says what differs, what
was measured on master, and what waits for that branch. The "before" times come from the saved logs
of real runs. The "after" times were measured on the same machine (16 cores, 47 GB) in a throwaway worktree
of `fix/7-persistence-phase-1` at `488f226fc` (699 tests, 24 `test-db` legs), with the changes of
this plan applied only there. Another project's CI job loaded the machine during some of them; those
runs say so.

## What is slow

| What | Today | What it runs |
|---|---|---|
| `make test-all -j16 TEST_JOBS=16` | 35–37 min (2,124 s, 2,157 s and 2,239 s on 2026-09-29) | every discovered `tests/async/test_*.py` (699) |
| `make test-db` | about 8 min | 24 legs, each with its own MySQL or MariaDB container |
| The 13 MariaDB journeys | about 20 min (1,186 s) | a hand-written script, one journey after another |
| Replaying the `.github/workflows` jobs | about 10 min of tests for `flatfile-build` alone | mostly tests `make test-all` already ran |

One verification round (build, `make test-all`, `make test-db`, the journeys) takes over an hour.
Almost none of that hour is the CPU working.

## Where the time goes

### `make test-all`: 30 of its 35 minutes are one queue

The runner (`tests/run_regression_tests.py`) runs 685 tests on the worker pool, then the 14 tests in
`RESOURCE_INTENSIVE_TEST_NAMES` **one at a time**. The saved runs:

| Run | Workers | Total | Pool (685 tests) | The 14, one at a time |
|---|---|---|---|---|
| 2026-09-28 02:49 | 16 | 2,143 s | 247 s | 1,896 s (88%) |
| 2026-09-28 18:13 | 8 | 2,168 s | 454 s | 1,714 s (79%) |
| 2026-09-29 04:22 | 8 | 2,238 s | 318 s | 1,920 s (86%) |
| 2026-09-29 09:48 | 16 | 2,157 s | 325 s | 1,832 s (85%) |
| 2026-09-29 11:12 | 16 | 2,124 s | 304 s | 1,820 s (86%) |

- **The machine is idle during that queue.** 30 `vmstat` samples over five minutes of it averaged
  94% idle. A running combat journey used 3% of one core and its server 2%. The journeys wait on
  game time: combat rounds, restarts, and real camp timers (the game-loop session journey quits
  twice and waits out both camps).
- **The reason for the queue is gone.** `docs/guides/TESTING.md` says these tests run serially "so
  their inner compiler workers cannot starve one another and exhaust per-build timeouts": each
  journey used to build its own server. Since `1b18086dc` (2026-09-10) they share one verified build
  in `bin/regression-artifacts` under a lock, so a run builds the server once. The queue stayed.
- **That one build uses `-j2`** (`tests/async/server_build_artifacts.py`), a leftover from when it ran
  inside the pool: 131–185 s in every saved run, and every journey waits for it. A full MariaDB
  server build at `-j16` took 65 s here.
- **The pool is already as fast as it gets.** 8 or 16 workers give the same 4–8 minutes because the
  pool is bounded by its longest tests (ASan/UBSan harness builds of up to 240 s), not by workers.
- Several of the 14 are several journeys in a row: combat 3 variants (373 s), newbie regrant 4
  (261 s), Chaos kit 5 classes (195 s), account recovery 2 (177 s).

### `make test-db`: 24 containers, one after another

Each leg starts its own container, waits for it to accept connections, applies migrations, builds a
harness and runs it. The legs don't depend on each other: container names are unique (`$$`,
`$RANDOM`, a uuid), and host ports are either unpublished (`docker exec`) or random
(`-p 127.0.0.1::3306`). One file is shared: three legs (`run_currency_transaction_schema_mysql.sh`,
`run_experience_trophy_mysql.sh`, `run_player_load_repository_mysql.sh`) build and run the same
`bin/tests/player_load_repository_mysql_harness`.

### The MariaDB journeys: in no gate at all

No make target runs them. Each review writes its own runner. On 2026-09-29 that was
`run_journeys.sh` and `rerun_journeys.sh` in the session scratchpad, following the recipe in the agent
memory: one MariaDB on a fixed port 3407, then the journeys one after another. Combat took 201 s
(410 s on the rerun), saved-item allocator 126 s, saved-item recovery 123 s, corpse haul 114 s,
playtime 109 s, stalled writer 106 s, deletion 101 s, chaos raise 87 s, information cache 76 s,
corpse-haul count cap 54 s, world writer retry 46 s, locker receipt 40 s, generated NPC 3 s (failed;
it needs a flat-file server). Without `TEST_DB_HOST`, `make test-all` runs
`test_mysql_combat_journey.py` in 0.03 s: it skips.

Nothing forces that queue either. Every journey creates and drops its own uuid-named schema and picks
its own free ports. The only one tied to a fixed port is `test_locker_receipt_recovery.py`: its
harness passes port 3306 to `mysql_real_connect()`, so it has to reach the container on the Docker
bridge IP.

### CI replays repeat `make test-all`

There is no hosted pipeline (no `.gitlab-ci.yml`), so "CI" means replaying `.github/workflows` on
this host. There:

- `quality.yml` `flatfile-build` runs 60 test scripts, **all of them already in `make test-all`**
  (607 s when run one by one). On a hosted runner it proved the tests pass without the MySQL client
  libraries. Here the libraries are installed, so it proves nothing new. The client-free build and
  boot are covered by `test_flatfile_boot_preflight.py`, which is in `make test-all`.
- `quality.yml` `quality`: 6 test scripts, all in `make test-all`. Unique: `./scripts/format.sh --all
  --check`, and the `py_compile` and `bash -n` checks.
- `build.yml` is `make test-all`.
- `backup-recovery.yml`: 4 of its 5 scripts are in `make test-all`. Unique: the root-only
  `test_persistence_backup_integration.py`.
- `security.yml` (CodeQL, Trivy) and `pages.yml` (`npm test` for `site/`) are unique.

## The rules

1. **Keep every test.** Nothing is deleted, shortened or loosened. Every check a gate runs today
   still runs in a gate, and `make test-db` gains the MariaDB journeys. (One leg leaves
   `make test-db` because it was never isolated. Its checks run in two other legs; see change 2.)
2. **Run side by side what only waits.** Journeys wait on game time and legs wait on containers, so
   running them together costs little CPU.
3. **Leave CPU-bound work as it is, on a quiet machine.** The 685-test pool still runs first and
   alone, so the CPU-sensitive performance gate (`test_telemetry_capacity_272.py`) sees the same
   load as today. Both gates run with nothing else loading the machine. In the loaded runs below,
   the only failures were time budgets and latency checks.
4. **Nothing new to install.** The runner, `make`, `bash`, `xargs` and Docker are enough.
5. **Measured.** Each change shows its time from a real run, and it is done only after three clean
   runs in a row.

## The changes

### 1. `make test-all`: the 14 journeys run side by side

- `tests/run_regression_tests.py`: after the pool, run the 14 in a pool of their own, one worker
  each, instead of the `for path in resource_intensive_tests` loop:

  ```python
  with ThreadPoolExecutor(max_workers=max(1, len(resource_intensive_tests))) as executor:
      for future in as_completed([executor.submit(run_test, path)
                                  for path in resource_intensive_tests]):
          report(future.result())
  ```

  `partition_tests()` and the list stay the same, so `test_root_test_harness.py` still holds.
- `tests/async/server_build_artifacts.py`: build with `-j{os.cpu_count()}` instead of `-j2`. The
  build runs while the machine is otherwise idle, and every journey waits for it.
- `tests/async/test_flatfile_player_repository.py --build-inspector`: copy the binary to a temporary
  name beside `bin/tests/coin-death-inspector`, then `os.replace()` it. Six of the 14 (and eight
  `run_*_journey.py` scripts) rebuild the inspector and copy it over that one path. Side by side, a
  plain copy onto a binary another journey is running fails with "Text file busy", or is read
  half-written.
- `available_ports()`: the shared one in `test_flatfile_combat_journey.py` and its copies in
  `test_account_recovery_journey.py` and `run_world_quest_dual_backend.py` (31 other files call one
  of the three). Draw the plain port at random from 20000–32000 instead of `bind(0)`, and keep the
  probe and the 200 retries. `bind(0)` takes a port from the kernel's ephemeral range, which here (WSL2) is only
  44620–48715. The probe then releases it, and the server binds it only after its world has loaded
  (about 7 s). Everything else running side by side draws from the same 4,096 ports: outgoing
  connections, other probes, and Docker's random host ports. In experiment 5 (change 2), one
  server lost that race (`bind error 1`, then `terminate called`). Below the ephemeral range, only
  another test's own probe can take the port first.
- `tests/async/test_item_movement_prompt_runtime.py`: raise its ASan/UBSan harness build timeout from
  120 s to 600 s, the ceiling the shared server build already has. The build is one single-threaded
  `g++` that takes 48–62 s alone. It took 101 s, 108 s (experiment 1) and 121 s (the loaded run
  below, which failed on it) whenever it shared the CPU. It shares the CPU with the server build at
  the start of the side-by-side run. The timeout exists to catch a hung compiler, and 600 s still
  does. This is the one number the plan changes in a test, and it is a time budget, not a check.
- `tests/async/test_player_load_pets.py` (found while measuring): it runs all of
  `test_player_load_items.py` again as a child with a 30 s timeout, although the runner already runs
  that test on its own (8–20 s; 31 s under load). Drop the nested run. It repeats work and adds a
  timeout that fails only under load.
- `docs/guides/TESTING.md`: replace "Resource-intensive tests still run serially, with two jobs per
  server build" and the paragraph that gives the old reason.

**Measured**, experiment 1: the 14 started together (`xargs -P14`) from a cold artifact cache, with
nothing else running. All 14 passed in **471 s**, against 1,714–1,920 s one at a time. The shared
build took 68.9 s at `-j16` (131–185 s at `-j2`), while the other 13 waited on its lock. After that,
each journey ran 5–7% slower than alone (combat 392 s after the wait, against 373 s), and the machine
was 80–87% idle. The slowest were combat (471 s), newbie regrant (359 s), the game-loop session
(331 s) and the Chaos kit (289 s).

A full `make test-all` with this change (runner, `-j16`, atomic inspector) ran from a cold cache
while another project's CI job loaded the machine to a load average of 26–29 on 16 cores. It took
**1,055 s**, against 2,124–2,239 s on a quiet machine before. The pool alone took 565 s instead of about
300 s. 697 of 699 passed. The two failures were both time budgets starved by that load: the ASan
build above (121 s against its 120 s), and the nested run in `test_player_load_pets.py` (31 s
against its 30 s). Both are fixed above.

The clean run: a full `make test-all` from a cold cache on a quiet machine, with changes 1 and 3.
The port fix was not in it yet, because experiment 5 found that race later. **699 passed, 0 failed, in 606 s (10.1 min)**,
against 2,124–2,239 s. The pool took 277 s, as before. The journeys took 329 s side by side, now led
by newbie regrant (329 s), the game-loop session (304 s) and the Chaos kit (264 s). Flat-file combat
took 207 s, and the cold server build 61.6 s. Once the builds were done, the machine was 90–98% idle.
The generated-NPC journey (60 s in experiment 2) will not lengthen that.

### 2. `make test-db`: the legs and the MariaDB journeys, side by side

- New `tests/async/with_disposable_mariadb.sh CMD...`: start `mariadb:10.11` on a random loopback
  port, wait until it answers, export `TEST_DB_HOST`, `TEST_DB_PORT`, `TEST_DB_USER`,
  `TEST_DB_PASSWORD` and `TEST_DB_CONTAINER`, run `CMD`, and remove the container on exit. These are
  the first 20 lines of `run_mysql_stalled_writer_journey.sh`, made generic. Every MariaDB journey
  gets its own server, so nothing is shared and the fixed port 3407 goes away.
- New `tests/run_db_tests.sh`: the test list, one line per test (a name and a command, as the recipe
  lists them today), run with `xargs -P "${TEST_DB_JOBS:-12}"`. Each test writes its own log under
  `bin/tests/db/`, prints `PASS` or `FAIL` with its seconds, and the script ends with the tails of the
  failed logs and exits nonzero if any failed. The list is the 23 isolated legs (one leaves; see
  below) and the 12 MariaDB journeys, longest first.
- `Makefile`: `test-db: build-server` (the journeys run `bin/server/dms_new`). It keeps the Docker
  checks, then runs `tests/run_db_tests.sh`.
- `run_player_load_repository_mysql.sh` leaves the list. It is not isolated: it sources the
  checkout's `.env` and runs against the configured development database (it only refuses
  production-like names). That breaks the rule that `make test-db` uses its own containers and never
  the configured game database (`burnin` skill), and in a checkout without `.env` it fails at once (it
  did in experiment 2). Its fixture matrix already runs twice in disposable containers, in the
  currency and trophy legs (`PLAYER_LOAD_DISPOSABLE_SCHEMA=1`). What it adds on its own is loading
  the `.env` character from `duris_dev`, so it stays as a manual development-database check.
- The currency and trophy legs both build and run `bin/tests/player_load_repository_mysql_harness`.
  Each builds its own file, named after the leg.
- `locker_receipt_harness.cpp` and `test_locker_receipt_recovery.py` honour `TEST_DB_PORT` (as
  `850d21253` did for four journeys), so the locker receipt leg runs through the wrapper like the
  rest.
- `run_generated_npc_journey.py` needs no database, only a flat-file server, so it moves to
  `make test-all` instead: with no argument it takes the shared artifact from
  `server_build_artifacts.build_flatfile_server()` like the other flat-file journeys, it is renamed
  `test_generated_npc_journey.py` so the runner finds it, and it joins the side-by-side list (and
  the copy of that list in `test_root_test_harness.py`). The MariaDB list is then 12 journeys.
- `test_player_save_claim.py` checks that its four loader legs are listed in the `Makefile`; it
  reads `tests/run_db_tests.sh` instead, without the player-load leg. The currency and trophy legs
  still build the loader harness, which is what that check protects.
- `docs/guides/TESTING.md`: `make test-db` now includes the MariaDB journeys, and the manual
  playtime-journey paragraph points to it.

**Measured**, experiment 2: the 36 (24 legs and 12 MariaDB journeys, each journey with its own
MariaDB) plus the generated-NPC journey, through a list-and-`xargs` runner, 12 at a time. 36 of 37
passed in **478 s**, against about 8 + 20 minutes one after another. The legs took 12–73 s (the legacy
migration leg 120 s), and the journeys 54–144 s, except MariaDB combat. At 478 s it set the wall
time on its own. The one failure was `run_player_load_repository_mysql.sh`, above.

Experiment 4: the final list, in the order the plan gives it. That is the 23 isolated legs and the
11 other MariaDB journeys, with combat as three variants (change 3), longest first, 12 at a time, while
another project's CI job still loaded the machine (load average 15–19). It took **250 s**; 36 of 37
passed. The failure was `test_information_cache_journey.py`: a page command missed its own 5-second
response limit. That journey checks latency. It passed on the quiet machine in experiment 2 (90 s),
and its flat-file run passed in both `make test-all` runs, so it is rule 3's case: run the gate on a
quiet machine.
The runs that set the wall time were saved-item recovery and allocator (192–195 s) and the combat
variants (189–191 s).

Experiment 5: the same list again, on a quiet machine. It took **193 s**, and the information cache
journey passed (98 s). 36 of 37 passed again: this time the chaos-raise journey's server lost its
listening port (`bind error 1`), the race that the `available_ports()` bullet under change 1 fixes.
Experiment 6, with that fix, on a quiet machine: **37 of 37 passed in 198 s**, and no server
reported a bind error.

### 3. The two combat journeys run their three variants at once

`test_flatfile_combat_journey.py` and `test_mysql_combat_journey.py` each run three independent
variants one after another: default coins, reset coins, and boons enabled. Each variant has its own
fixture, ports and (on MariaDB) schema. They are the slowest test in each gate. In `__main__`, start
the three as child processes of the same script (`--variant NAME`), wait for all three, and fail if
any failed. The parent builds the inspector and gets the server once, then passes the binary to
the children. They are processes, not threads, so no module state is shared. `--one` keeps working.

**Measured**, experiment 3: the six variants (three per journey), each as its own process and all at
once, with another project's CI job still loading the machine (load average 16–19). All six passed.
The three MariaDB variants took 192–196 s together, against 410–478 s one after another. The three
flat-file variants took 209–226 s, against 373–392 s. In `make test-all` this moves the tail's
critical path from combat (471 s) to newbie regrant (359 s). In `make test-db` it removes the one
test that set the wall time; see the measurement under change 2.

### 4. One routine, no replays

Before a merge, run the gate, one command after the other, on a quiet machine. The performance gate
and the latency journeys are CPU-sensitive:

```bash
./scripts/format.sh --all --check
make test-all -j16 TEST_JOBS=16
make test-db
```

Run these only when the change touches what they check:

| Check | When |
|---|---|
| The backup-recovery container job (root-only `test_persistence_backup_integration.py`) | backup, restore, `scripts/backup_*`, or the flat-file launcher |
| CodeQL and Trivy (`security.yml`) | dependencies, `packaging/`, `Dockerfile`, network or authentication code, and before a production deploy |
| `npm ci --prefix site && npm test --prefix site` | `docs/` or `site/` |

Never replay `flatfile-build`, `quality` or `build.yml` step by step. Their tests are the ones
`make test-all` just ran on the same host. Update the agent memory recipes (local CI replay,
disposable MariaDB legs) to point here and to `make test-db`.

## Before and after

All "after" times were measured on this machine, quiet, with the plan's changes in a throwaway
worktree.

| | Before | After |
|---|---|---|
| `make test-all` (699 tests) | 2,124–2,239 s (35–37 min) | **606 s (10.1 min)**, 699 of 699 passed |
| `make test-db` (24 legs) | about 8 min | **193–198 s (3.3 min)** for the legs and the MariaDB journeys together; 37 of 37 passed with the port fix |
| The 13 MariaDB journeys | about 20 min, run by hand | included in `make test-db` above (the generated-NPC journey moves to `make test-all`) |
| Replaying workflow jobs whose tests `make test-all` runs | about 10 min of tests for `flatfile-build` alone | none |
| **One full round**: `make test-all`, `make test-db`, the MariaDB journeys | **63–65 min** | **about 13½ min** |

The saving comes from three places:
- **Running side by side what only waits.** The 14 journeys (1,820 s → 329 s) and the `test-db` work
  (about 1,660 s → 198 s).
- **Not waiting on one slow build.** The shared server build went from `-j2` (131–185 s) to `-j16`
  (62–69 s).
- **Not repeating work.** Combat's three variants run at once, the nested items test and the
  `flatfile-build` replay are gone.

Every test still runs, and `make test-db` now also runs the 12 MariaDB journeys that no gate ran.

## What was cut, and why

The plan was put through [plan ablation](../../.agents/skills/plan-ablation/SKILL.md): each part was
removed in turn, and it stayed only if a requirement or a concrete risk failed without it. These were
cut:

- **Deleting, merging or shortening tests.** Rule 1. They are also not where the time goes: 402 of
  the 685 pool tests take under a second each, 92 s of CPU in all.
- **Shorter in-game timers in the journeys** (the game-loop session's two real camps). That would change
  what the journey checks, and side by side it no longer adds to the total.
- **Splitting the other multi-variant journeys** (newbie regrant ×4, Chaos kit ×5, account
  recovery ×2). Once combat runs its variants at once, the tail is bound by newbie regrant (359 s)
  and the game-loop session (331 s), which is one session and cannot be split. Splitting more would
  save under 30 s.
- **Running the 14 journeys during the pool instead of after it.** It would save about five
  minutes. But both failures in the loaded run were time budgets starved of CPU, and overlapping
  would put the journeys' builds and servers on the CPU-bound pool, next to the performance gate, on
  every run.
- **ccache or a shared object library for the harnesses.** Most harnesses are one multi-source `g++`
  command, which ccache does not cache. A shared library would mean reworking about 150 harness
  builds to save part of a five-minute phase.
- **A higher default worker count or longest-first ordering in the pool.** 8 and 16 workers give the
  same pool time, and ordering would save at most about 20 s.
- **Running `make test-db` during `make test-all`.** Its harness builds and container starts would
  land on the CPU-bound pool and the performance gate. One after the other is still about 13½ minutes.
- **Choosing tests by changed files.** It needs a map from sources to tests that nobody maintains,
  and it can miss an effect. With the gate this short, run all of it.
- **A hosted pipeline, or an umbrella `make verify` target.** Verification is local by design
  (`AGENTS.md`), and three commands are no burden. A new target would make nothing faster.
- **One shared MariaDB for all the journeys**, as the hand-written runner had. Each journey already
  uses its own schema, but on one server they would share its load and its locks (the stalled-writer
  journey locks tables and stops its server). The runner would also have to own a container's
  lifecycle. With one server per journey, every line of the list stands alone.
- **Changing `run_mysql_stalled_writer_journey.sh` to use the new wrapper.** It works, and it is
  already in the list as it is.

## Done when

- On a quiet machine, `make test-all` passes three times in a row in about 10 minutes, and
  `make test-db` (legs and MariaDB journeys) passes three times in a row in about 3½ minutes, with no
  new flaky test. Each change lands in its own commit with its own check. The `.env` leg and the
  nested items test, found while measuring, get their own commits too.
- `docs/guides/TESTING.md`, the `burnin` skill (unchanged commands, new times) and the agent memory
  describe the gate above, and no review runs the MariaDB journeys by hand again.

## Landed on master

Master is not the branch the plan measured. `fix/7-persistence-phase-1` is 37 commits ahead of it.
Master had 17 `make test-db` legs, not 24, and no gate ever ran its MariaDB journeys, so several of
them had stopped passing. The plan went through plan ablation again, against master.

### What landed

| Change | Commit |
|---|---|
| 1. The journeys run side by side, on one server build at `-j$(nproc)` | `7fed66bd9` |
| 1. The inspector is replaced whole | `4cf276b20` |
| 1. `available_ports()` draws from 20000–32000 | `e18cc8b68` |
| 1. The sanitizer build gets 600 s | `3827bfb39` |
| 1. The nested items test is gone | `0bccac115` |
| 2. `tests/run_db_tests.sh`, `with_disposable_mariadb.sh`, `test-db: build-server` | `2de992efb` |
| 2. The locker receipt leg and the corpse haul journey take `TEST_DB_PORT` | `867dc83ad` |
| 2. The currency and trophy legs build their own loader harness file | `e46204708` |
| 2. The generated-NPC journey runs in `make test-all` | `f7b301cdc` |
| 3. The combat variants run at once | `c17808e57` |
| 4. The routine is in `docs/guides/TESTING.md` ("Before a merge") | with this document |

The list in `tests/run_db_tests.sh` is 32 tests: master's 17 legs, the output preferences,
currency, experience trophy and item transfer legs, and eleven MariaDB journeys (combat, corpse
haul and its count cap, saved-item recovery and allocator, world writer retry, deletion, chaos
raise, playtime, information cache, locker receipt). `make test-all` runs 15 journeys side by side.

### Fixed on the way

Each was needed for a test in the list to pass on master, and each has its own commit.

- `57fb6860a`: the deletion, playtime, information cache and generated-NPC journeys take
  `TEST_DB_PORT`. It is the branch's `850d21253`.
- `70de26222`: the collector catalog leg's fingerprint. It is the branch's `a970f6bec`. Master's
  `make test-db` stopped at this leg, so the eight legs after it had not run.
- `9bc21a8fc`, `5831878a4` and `e46204708`: the locker receipt, output preferences and trophy
  legs stopped at the linker.
- `57bfc15a3`: the currency leg's coin matrix built a duplicate row. It is the branch's
  `916f99520`.
- `9b52ca019`: the loader fixture matrix, which the currency and trophy legs run, still expected a
  refused load where #531 made master degrade it.
- `2a2ea84b7`: the item transfer leg sourced `.env` and ran against the configured development
  database. It has its own container now. Its craft case built the payload from before #573.
- `0e82c5690`: a flat-file character promoted to immortal was refused at its next login or
  copyover, so the generated-NPC journey failed. It is the branch's `6e4934ab0`, resolved against
  master's degraded item load.
- `f59877ec2`: raising a corpse that holds a coin pile from before item custody committed, then
  went through live recovery and paused the caster's saves. The chaos raise journey failed on it.
  Its default mode also expected the corpse's items with the caster; a follower holds them.
- `ca5b00dd3`: a character could not be deleted in a world without zone-story content, so the
  deletion journey failed. It is the branch's `a810bed5a`.

Three of these change `src/`: `ca5b00dd3`, `0e82c5690` and `f59877ec2`.
- `d56aad34f`: `apply_persistence_contract.sh` and `verify_persistence_contract.sh` probed for
  `--ssl-mode` with `grep -q` under `pipefail`. When `mysql --help` died of SIGPIPE, they chose
  `--skip-ssl`, which MySQL 8's client refuses. The persistence contract leg lost that race in the
  first side-by-side run.
- Five contract tests looked for their leg in the `Makefile`. They read `tests/run_db_tests.sh` now.

### Cut or left for the branch

- **`TEST_DB_CONTAINER` and an image override in the wrapper.** Nothing on master reads them. The
  stalled-writer journey, which needs the container name, keeps its own wrapper.
- **`run_player_load_repository_mysql.sh` leaving the list.** It was never in master's list. It
  stays a manual check against the development database.
- **Four files that only the branch has:** `run_player_save_claim_mysql.sh`,
  `run_sql_pool_interrupt_mysql.sh`, `test_player_save_claim.py` and
  `run_mysql_stalled_writer_journey.sh`. They test the save claim, the query cut-off and the one
  writer, which master does not have.

### Measured on master

Another project's local CI ran on this machine through most of the afternoon, with up to eight
containers of two CPUs each. Only the first `make test-db` run had a quiet machine.

| Run | Machine | Result | Time |
|---|---|---|---|
| `make test-db`, before the port and probe fixes | 12 tests of its own at once | 20 of 31 | 535 s |
| `make test-db` | quiet | **28 of 28** | **187 s** |
| `make test-db` | saturated, 8% idle on average | 25 of 28 | 452 s |
| `make test-db` | saturated, 24% idle | 27 of 28 | 228 s |
| `make test-db`, all 32 tests | loaded, 39% idle | **32 of 32** | **200 s** |
| `make test-all -j16 TEST_JOBS=16`, cold server build | loaded | **696 of 696** | **886 s** (pool 522 s, journeys 364 s) |
| `make test-all -j16 TEST_JOBS=16` | saturated, 17% idle | 694 of 696 | 690 s (pool 407 s, journeys 283 s) |
| `make test-all -j16 TEST_JOBS=16`, 15 journeys | loaded, 26% idle | 696 of 697 | 818 s (pool 440 s, journeys 379 s) |
| `make test-all -j16 TEST_JOBS=16`, 15 journeys | quiet from the journeys on | **697 of 697** | **622 s** |

Before, `make test-all` took 2,124–2,239 s, and `make test-db` stopped at its ninth leg.

Every failure in the saturated runs was a time budget, and every one of those tests passed in a
run with more CPU. That is rule 3: run the gate on a quiet machine.

- The two saved-item journeys: the server did not exit within its 20 seconds.
- The corpse haul journey: it read the ownership table before the write landed.
- The playtime journey: 8 played seconds against 5 measured ones, with a tolerance of 2.
- `test_flatfile_ip_activity.py`, `test_redis_donation_worker_live.py` and
  `test_telemetry_runtime_integration.py`, in the pool: a 2-second window, a worker's counters and
  a flush capped at 250 ms. Each passed three times in a row alone, right after its run.

No server reported a bind error in any run after the port fix.

The pool took 407–522 s, not the 277 s of the plan, because it shared the CPU. It is CPU-bound, and
its longest tests are the economy accounting harness builds (up to 458 s).

Three clean runs in a row, which "Done when" asks for, were dropped at the owner's request: one
clean run of each gate is the evidence.

### When the persistence branch merges

1. `Makefile` will conflict in `test-db`. Keep master's recipe, and add the branch's three tests to
   `tests/run_db_tests.sh`:

   ```
   stalled_writer tests/async/run_mysql_stalled_writer_journey.sh
   player_save_claim tests/async/run_player_save_claim_mysql.sh
   sql_pool_interrupt tests/async/run_sql_pool_interrupt_mysql.sh
   ```

   Leave `run_player_load_repository_mysql.sh` out, as change 2 says.
2. Point `test_player_save_claim.py` at `tests/run_db_tests.sh`.
3. Where a test file conflicts, take the branch's side: it describes the branch's server. That is
   the loader harness, the chaos raise journey, the item transfer leg, and the link lists of the
   locker receipt, output preferences, trophy and currency legs. Keep from master the
   `TEST_DB_PORT` lines, the combat variants, and the currency and trophy legs' own harness file.
4. `handler.c` will conflict where master counts a corpse's coin piles. The branch raises in
   memory and drops that code.
