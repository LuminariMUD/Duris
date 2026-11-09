# Flat-file backend removal: fast approach

Status: first pass implemented in a PR stack; test conversion deferred. See "Implementation log" at the end.
Date: 2026-11-09.
Source baseline: `06743dec0`. A recount at `4c2708c96` found no change to
persistence paths or to the counts below.

## Outcome

Make MariaDB the only supported server persistence backend and delete most of
the optional flat-file implementation quickly. Preserve current MariaDB
gameplay, persistence, startup, and recovery behavior. Leave shared code under
its existing names and paths where moving it would add work without helping
remove the backend.

The owner confirms that only database persistence has been used and no
flat-file state needs preserving. No data conversion, database migration,
player wipe, or support for restoring old flat-file authority backups is
required. This plan authorizes no production operation or deletion of runtime
data. The immediate task is documenting the approach; implementation is separate.

Budget: roughly **2–4 active agent hours for the first pass**, including a fresh
build and focused MariaDB verification. This is an estimate with limited
confidence, not a deadline or a promise of complete test-suite conversion.
Reassess if a concrete shared dependency or regression requires more work.
Background wall-clock for the database suite and regression runner is extra and
has not been measured.

## Baseline and boundaries

The source scan found 87 C/C++ source/header files and about 31,800 lines under
`src/flatfile`, plus 119 other source/header files mentioning flat-file code or
backend switches. There are 289 `__NO_MYSQL__` mentions across 72 source files.
These are overlapping discovery counts, not a deletion quota or a list of files
that all need editing.

Tests are the main deferred cost, and they reach well beyond the 55 test/helper
files that directly request a flat-file server build; the trial results below
give the measured reach. A filename containing `flatfile` does not establish
that the file is disposable. For example, MariaDB bank/restart and deletion
journeys import helpers from `test_flatfile_combat_journey.py`.

Keep these existing shared pieces as needed:

- [`flatfile_store.c/.h`](../../src/flatfile/flatfile_store.h): atomic file I/O
  and locking used by MariaDB-mode locker receipts, combat intents, starter-kit
  intents, locker shutdown recovery, and
  [`shopkeeper_boot.c`](../../src/economy/shopkeeper_boot.c). Preserve the
  `shopkeeper-boot/state` marker: it distinguishes clean stops from crashes and
  recovery so a restart does not incorrectly replenish shop stock.
- `flatfile_information_read()` in
  [`flatfile_help_catalog.c`](../../src/flatfile/flatfile_help_catalog.h): the
  MariaDB server reads news and information pages through it in
  [`news.c`](../../src/player/news.c), `get_mud_info()` in
  [`sql.c`](../../src/sql/sql.c), and
  [`information_cache.c`](../../src/cmd/information_cache.c).
- Shopkeeper snapshot types and capture code: MariaDB
  [`sql_save_shopkeeper()`](../../src/sql/sql_player.c) captures a
  `flatfile_shopkeeper_record`, which the SQL snapshot repository writes.
  Retain the necessary declarations and their dependency closure; trim
  backend-only dependencies when that makes deletion possible. In particular,
  trim `flatfile_shopkeeper_repository.h` to its record types so it no longer
  pulls in `flatfile_authority_transaction.h`.
- Shared snapshot/command codecs, existing recovery files, and their tests.
  Filesystem-based world content, configuration, logs, and copyover state also
  remain outside backend removal.
- Small test-only MySQL shims may remain temporarily if existing unit tests
  need them. Remove them from server build inputs; deleting a few hundred lines
  of test compatibility is not worth converting the entire suite in this pass.
  They do not by themselves keep those tests passing; see the trial results.

Do not add a new persistence interface, compatibility backend, replacement
repository layer, or stub that pretends a save succeeded. Preserve the existing
memory-authoritative game behavior and ordered background MariaDB writer.

## Trial results

A trial on scratch copies of `06743dec0` measured these facts without changing
the repository. It stripped `__NO_MYSQL__` and analyzed the resulting build but
deleted no backend code, so the test failures below are a lower bound.

- **The strip is mechanically safe.** `unifdef` removed 7,036 lines from 71
  files. All 521 `.c`/`.cpp` files under `src` preprocess identically before and
  after, ignoring `__LINE__` values.
- **Runtime dispatch is the main manual edit.** The strip leaves 107 lines in 33
  files outside `src/flatfile` that select a backend at runtime.
- **Almost none of `src/flatfile` is needed.** With the mode queries made
  constant and built at `-O2`, only 9 of 46 flat-file objects still have a
  consumer; the other 37 (about 23,450 lines) are unreferenced. Six of the 9 are
  reached only through mode-gated file paths in `divine_trade_runtime.c`,
  `frag_cap_repository.c`, and `divine_boon_repository.c`. Modeling those paths
  as removed leaves `flatfile_store`, `flatfile_shopkeeper_capture`, and
  `flatfile_help_catalog`.
- **The restore qualifier needs nine sources**, with no shim or `__NO_MYSQL__`:
  `flatfile_store`, `locker_receipt`, `combat_outcome_intent`,
  `starter_kit_intent`, `critical_command`, `item_transfer_command`,
  `currency_command`, `combat_outcome_command`, and `artifact_guild_command`. A
  receipts-only qualifier linked from them under `-Wall -Wextra -Wpedantic
  -Werror`.
- **Test reach is much wider than 55 files.** Of the 1,006 tests the regression
  runner discovers, up to 235 reach a flat-file server, a `src/flatfile` source,
  or the `-D__NO_MYSQL__`/shim compile path. That is a static upper bound
  through imports. The runner also discovers 66 `test_flatfile_*` files.
- **The strip alone breaks ordinary unit tests.** Of 154 shim-built and
  source-contract tests run after the strip, 57 failed that pass on a pristine
  copy. Of those, 40 failed at compile, link, or run time because their harnesses
  were written for the `__NO_MYSQL__` shape of the code, and 17 assert source
  text that no longer exists. Exposing the shim to every compile and adding the
  missing `mysql_query` stub fixed only 11 of 42 retried, so these are
  per-harness repairs.

## Implementation sequence

### 1. Establish the MariaDB baseline and retained dependencies

- Check worktree changes and preserve unrelated work. Use a task branch or
  isolated worktree when implementation starts; prefer an isolated worktree so
  the standard `bin/server/dms_new` used by restore can be rebuilt safely.
- Start from the retained set in the trial results. Compiler and linker errors
  catch anything that has changed since, so no separate reference trace is
  needed.
- Run the proof section's regressions and the regression runner once on the
  starting commit, and record pre-existing failures separately. Use disposable
  databases and synthetic player state throughout.
- Check the actual prerequisites before deletion. The SQL journeys need Docker.
  `unifdef` must be installed; it is not on the WSL dev machine, but `apt-get
  download unifdef` and `dpkg -x` into a temporary directory work without root.
  The restore
  integration needs real root, not just a namespace: `unshare -Urm` fails its
  ownership checks, which is why CI runs it under `sudo`. The proof section
  gives a container command that works without `sudo`.

### 2. Select the existing MariaDB implementation mechanically

- In [`src/Makefile`](../../src/Makefile), always use the MariaDB client headers
  and library. Remove the server's `__NO_MYSQL__` definition and shim include
  path. Keep accepting `PERSISTENCE_BACKEND=mariadb` if existing callers pass
  it; explicitly reject `flatfile` and unknown values rather than silently
  building a different backend than requested.
- Strip the disabled branches with `unifdef -U__NO_MYSQL__ -t -m` on each file
  under `src` that has a `__NO_MYSQL__` directive, excluding `src/no_mysql`. The
  `-t` flag is required: without it `unifdef` stops at digit separators such as
  `250'000U` in `copyover.c`. Treat exit status 2 as failure. Text mode is safe
  here because every directive is a plain `#ifdef` or `#ifndef` and none sits
  inside a comment. Fix the five leftover comment mentions by hand
  (`ship_cargo.c`, `ship_base.c`, `kingdom_internal.h`, `kingdom_db.c`, and
  `epic.c`). Do not run a broad regex deletion across C/C++ conditionals or test
  fixtures.
- Commit the strip and Makefile change on their own, once the preprocessor
  comparison in the proof section shows no difference. That keeps the largest
  diff provably behavior-neutral and easy to revert.
- Simplify runtime backend dispatch to the MariaDB path. In
  [`persistence_mode.c/.h`](../../src/persistence/persistence_mode.h), accept
  unset/empty `PERSISTENCE_MODE` and `mariadb-primary`; reject obsolete flat-file
  values with a clear diagnostic. The mixed fallback mode already fails today.
- Inspect ordinary runtime branches as well as preprocessor branches. For
  example, `artifact_mana_store.c` and `divine_boon_repository.c` compile file
  implementations even in a MariaDB build, and `locker_recovery.c` dispatches
  using `persistence_mode_flatfile_root()`. The strip leaves 107 such lines in
  33 files; at each one, keep the MariaDB branch.
- Remove `persistence_mode_get()`, `persistence_mode_requires_mysql()`, and
  `persistence_mode_flatfile_root()` from the header so the compiler lists every
  remaining site and no selectable flat-file path can survive. Most of their
  callers guard calls being deleted anyway, so keeping them saves little.
  `persistence_mode_name()` can stay for its one boot log line.

### 3. Delete backend-only code and build entries

- Remove flat-file repositories, authority transactions, adapters, and
  restoration code once their MariaDB/shared consumers have been resolved.
- Remove their object entries and obsolete includes. Cover flat-file-only
  implementations outside `src/flatfile`, including economy, guild, kingdom,
  ship, and player code, and the file paths in `frag_cap_repository.c` and
  `divine_boon_repository.c`. `economy/divine_trade_flatfile.c` and
  `guild/artifact_population_flatfile.c` are the two flat-file-named objects
  outside that directory.
- Keep the shared file primitives, `flatfile_help_catalog`, and shopkeeper
  snapshot/capture code in place. Rename or move nothing merely to eliminate the
  word `flatfile`.
- Use compiler/linker failures to catch missed dependencies, then trace each
  consumer. Retain shared behavior or remove a proven backend-only caller;
  do not retain a whole repository cluster for one shared declaration.

### 4. Keep MariaDB startup and recovery tools working

- Update [`scripts/cycle_mud.sh`](../../scripts/cycle_mud.sh) to require the
  existing MariaDB configuration and follow its current migration, schema,
  backup, and shutdown paths. Reject a non-MariaDB `PERSISTENCE_MODE` before
  boot, but ignore leftover `FLATFILE_STATE_DIR` and `FLATFILE_BACKUP_DIR`: the
  local `.env` sets both and must not be edited, so rejecting them would stop
  the server from starting.
  Preserve environment/target/TLS guards and the `mariadb/production` build
  stamp contract; removing backend selection must not break production-profile
  admission.
- Make the small corresponding changes in
  [`persistence_backup.py`](../../scripts/persistence_backup.py) and
  [`persistence_restore.py`](../../scripts/persistence_restore.py): retain
  database dumps, receipt/journal capture, isolated database checks, and service
  restore. Remove flat-file authority capture/restore branches that depend on
  deleted code. Preserve existing MariaDB backup format compatibility.
- MariaDB restore currently runs
  [`qualify_flatfile_restore`](../../scripts/qualify_flatfile_restore.cpp)
  with `--receipts`. Trim that tool and
  [`build_restore_qualifier.py`](../../scripts/build_restore_qualifier.py) to
  retain the locker/combat/starter-kit receipt checks without linking the
  deleted authority repositories. Keeping the existing executable name and
  `--receipts` invocation is acceptable for this pass. Build it from the nine
  sources in the trial results, and drop `-D__NO_MYSQL__` and `-Isrc/no_mysql`
  from its compile line.
- Remove the extra flat-file server build from `build-restore-tools` in the
  root Makefile, and update `test-backup-recovery` in the same change: it also
  invokes flat-file tests and the two-backend integration setup. Keep its
  MariaDB backup/restore and shared launcher/receipt checks usable. Do not leave
  an operational build target referencing deleted sources. Update current
  build/configuration instructions and `.env.example` where they would otherwise
  advertise removed server support; never edit the local `.env`. The current
  instructions are `docs/guides/BUILDING.md`, `docs/operations/CONFIGURATION.md`,
  `docs/operations/BACKUPS.md`, `docs/operations/RUNBOOK.md`, and the backend
  branch in `.agents/skills/local-deploy/SKILL.md`.
- Update `.github/workflows` in the same change. Delete the `flatfile-build` job
  from `quality.yml`, which would otherwise fail on every PR; its other tests
  still run through `make test-all`. Mirror the `test-backup-recovery` changes in
  `backup-recovery.yml`.

### 5. Verify the first pass and record the remainder

- Adapt only the selected regression harnesses and shared helpers needed to
  prove the retained MariaDB behavior. Reuse their existing test doubles and
  disposable database setup. Six database-suite entries name flat-file sources
  that are going away, so they are in scope: `run_address_retention_journey.py`,
  `run_item_transfer_schema_mysql.sh`, `run_level_cap_mysql.py`,
  `test_divine_boon_zone_journey.py`, `test_frag_cap_journey.py`, and
  `test_legacy_trap_journey.py`.
- Adapt `test_persistence_mode.py`, `test_supported_server_build_contract.py`,
  and `test_flatfile_launcher.py` in this pass. The last contains shared
  shutdown/signal, target, port, and secret guards despite its name. Replace
  flat-file success cases with rejection cases while retaining the shared
  assertions; use `run_launcher_stop_journey.py` for the MariaDB stop-record path.
- Delete tests whose sole purpose is the removed backend when they have no
  shared consumers. Defer broad gameplay-fixture conversion and test renaming.
- Keep `make test-all` usable. `build.yml` runs it and the runner discovers
  every `test_*.py`, so tests that cannot work yet would fail on every PR and
  hide new regressions. After deletion, run `python3
  tests/run_regression_tests.py` once and list the tests failing because of this
  removal, by exact name, in a new frozenset beside `MANUAL_ONLY_TEST_NAMES`.
  Have the runner print how many it excluded. That list is the deferred
  inventory: each conversion removes an entry, and the project is not finished
  until it is empty.
- Record any other known runner failures in this document. Apart from that named
  list, do not report full-suite coverage from focused checks, add blanket
  skips, suppress failures, or replace persistence tests with unconditional
  success.
- Review the diff and remaining references. Classify retained source as shared
  functionality, retained tests as reusable helpers or deferred conversion,
  and documentation as current instructions or historical evidence. A zero
  result from searching for `flatfile` is not an acceptance requirement.

## Proof

Run from the repository root on Linux/WSL. Implementation must record the exact
commands, results, and unrun checks here. Except where the trial results say
otherwise, these commands have not been run for this documentation task.

Prove the strip before making any other change. Run this once before it and once
after it, writing to different files, then `diff` the two. Replacing digits
hides `__LINE__` shifts, so an empty diff means only disabled code went away.

```bash
cd src
out=../bin/preprocess-before.txt  # use preprocess-after.txt on the second run
find . -type f \( -name '*.c' -o -name '*.cpp' \) -not -path './no_mysql/*' | sort |
  xargs -P "$(nproc)" -I{} sh -c 'printf "%s  %s\n" "$(g++ -std=c++20 -E -P -DTEST_MUD \
    -I. -I/usr/include/libxml2 -I/usr/include/mysql "{}" | sed -E "s/[0-9]+/N/g" |
    sha256sum | cut -d" " -f1)" "{}"' | sort -k2 > "$out"
```

Build fresh objects in a dedicated tree under `bin/`, with the executable at
the standard path in the implementation worktree. Both
`persistence_restore.service_load()` and the integration setup hardcode
`bin/server/dms_new`; a binary only under `bin/flatfile-removal-fast/server/`
would not test the new build during restore. Use the same standard binary for
all journeys. The initial directory check deliberately refuses to reuse an old
object tree; choose another fresh name if it already exists.

```bash
set -euo pipefail
./scripts/format.sh --check
test ! -e bin/flatfile-removal-fast || exit 1
make -C src BIN_ROOT=../bin/flatfile-removal-fast \
  DMS_BINARY="$PWD/bin/server/dms_new" -j4 all pfile telemetry-state
make build-restore-tools

python3 tests/async/test_persistence_mode.py
python3 tests/async/test_supported_server_build_contract.py
python3 tests/async/test_flatfile_launcher.py
python3 tests/async/test_shopkeeper_save_runtime.py
python3 tests/async/test_shopkeeper_boot.py
python3 tests/async/test_locker_receipt_recovery.py
python3 tests/async/test_locker_shutdown_recovery.py
python3 tests/async/test_persistence_backup.py

make world
bash tests/run_db_tests.sh
```

Run the database suite script directly: `make test-db` first runs `build-server`,
which would replace the fresh binary with one from the default object tree. The
script has more than 100 entries, including the bank/restart, deletion,
starter-kit, save-claim, and launcher-stop journeys. It exercises real
boot/login, saves, restart/load, and the economy, guild, and world paths the
dispatch edit touches, which a few hand-picked journeys would not. Compare its
failures against the starting commit.

Some listed harnesses currently use the shims or flat-file-named helpers; adjust
those selected harnesses as needed instead of deleting their coverage. Shopkeeper
and locker checks cover the shared code deliberately retained.

In the selected configuration tests, check default/explicit MariaDB builds,
unset/empty/`mariadb-primary` runtime modes, and rejected flat-file/mixed/unknown
settings with a clear diagnostic and nonzero exit. Exercise Makefile rejection
with a dry run and launcher rejection with its isolated `--check-config`
fixture, before migrations, backup, or boot can run. Preserve ordinary database
connection failure behavior; an unavailable database must never select a file
backend.

After narrowing `test_persistence_backup_integration.py`, run its existing
MariaDB restore and receipt rejection cases explicitly. They need real root, so
without `sudo` use a throwaway container. The server built on the host runs
inside it, so the image must match the host (Ubuntu 24.04 here). On the starting
code, both cases passed this way in about three minutes, plus package
installation:

```bash
docker run --rm --cap-add SYS_ADMIN --security-opt seccomp=unconfined \
  --security-opt apparmor=unconfined -v "$PWD:/src:ro" ubuntu:24.04 bash -euc '
  export DEBIAN_FRONTEND=noninteractive
  cp -a /src /work && cd /work && chown -R root:root .
  apt-get update -qq
  apt-get install -y -qq equivs mariadb-server mariadb-client iproute2 python3 make
  make build-deps-package
  apt-get install -y -qq ./bin/packages/duris-build-deps_1.0_all.deb
  DURIS_RUN_BACKUP_INTEGRATION=1 python3 -u \
    tests/async/test_persistence_backup_integration.py \
    PersistenceRecoveryIntegration.test_mariadb_full_dump_schema_history_values_and_isolated_service_boot \
    PersistenceRecoveryIntegration.test_locker_receipt_qualification_rejects_corruption_and_unexpected_entries \
    PersistenceRecoveryIntegration.test_qualifier_checks_nonempty_combat_and_starter_records -v'
```

Run the database suite from a short checkout path. Journeys put a Redis unix socket
under `bin/tests/<temporary>/`, and a path over 107 characters makes Redis exit at
startup; the long `flatfile-backend-removal-plan` worktree path is enough to cause it.

Narrow both `build_native_fixture()` and `setUpClass()`: currently even these
cases require flat-file repository sources and `dms_restore_flatfile`. Keep
the real isolated database import, schema/value checks, service boot, source
immutability checks, and invalid-receipt rejection. Extend the receipt cases
with valid and corrupt **nonempty** combat-intent and starter-kit records using
their existing codecs; the current MariaDB restore case creates only an empty
combat directory and no starter-kit records. This proves the trimmed qualifier
still validates all three retained formats. Do not disable receipt validation
or count the opt-in suite's default skip as a pass.

Run applicable additional focused checks only when a touched path, failure, or
unresolved dependency justifies them. No repository-wide burn-in or wait for CI
is part of this first pass.

## Completion and deferred work

The first pass is complete when MariaDB is the sole selectable server backend,
the fresh server and required restore tool build, the selected executable checks
pass, the regression runner passes with only the named deferred tests excluded,
removed repositories have no live consumers, and remaining limitations are
recorded. A failed, skipped, or unavailable required check (including isolated
backup/restore) leaves the first pass incomplete; record that specific behavior
as unverified and continue independent work.

The change alters no schema or data, so `git revert` and a rebuild undo it.

Deferred work is the tests on the named list (flat-file gameplay journeys and the
shim-built unit and source-contract tests from the trial), shared helper/type
renaming or relocation, removing now-unused test shims, historical documentation
cleanup, the `file:flatfile-*` rows in `migrations/data_lifecycle_manifest.json`
and the validator entries that require them, peripheral tooling cleanup
(coverage, fuzz, and `scripts/validate_colorization_journey.py`), and full-suite
qualification, and removing the submitter-less `shop_trade_*` path and its
no-op hooks. Repair a peripheral tool now if a required first-pass command
actually depends on it. Do not weaken MariaDB persistence or recovery to make the
initial deletion faster.

Start the journey conversion at its shared points. `test_flatfile_combat_journey.py`
is imported by 142 test modules; its `build_flatfile_server()`, `run_journey()`,
and `make_fixture()` helpers, and `make_overlord()` (used by 63 files), hold most
of the flat-file-specific setup.

## Implementation log

Worktree: `duris-worktrees/flatfile-backend-removal-plan`. The work ships as
stacked PRs, each branch built on the previous one; the deferred inventory lives
in the runner's named list. To continue, check out the top branch of the stack
and pick up at the first step not marked done.

| Step | Branch | State |
| --- | --- | --- |
| 2a. Strip `__NO_MYSQL__`, Makefile | `branch/flatfile-backend-removal-plan` | done (#859) |
| 2b + 3. Runtime dispatch, delete backend | `branch/flatfile-removal-runtime` | done (#860) |
| 4. Launcher, backup, restore, CI, docs | `branch/flatfile-removal-tools` | done |
| 5. Tests and deferred list | `branch/flatfile-removal-tests` | done |

### Deferred test conversion (branch `branch/flatfile-removal-test-conversion`, #864)

Each batch removes names from `FLATFILE_REMOVAL_DEFERRED_TEST_NAMES`; `make test-all`
must stay green after each one.

| Batch | Deferred left | Notes |
|---|---|---|
| Remove deleted sources, includes, and stubs from harnesses | 165 | Mechanical |
| Repair harness compile and link failures | 128 | Harnesses compile real client headers; some now use SQL or queue fakes |
| Repoint source-text contracts | 64 | No MariaDB behavior change found; `test_ship_salvage.py` now checks what a stubbed `sql_save_ship` receives, not a read-back |
| Journeys already in `make test-db` become manual-only | 51 | 13 tests; they run on MariaDB with `--server` |

| Shared journey harness on MariaDB; 22 journeys move to `make test-db` | 29 | `mariadb_authority()` builds a disposable migrated schema; converted journeys are manual-only and listed in `tests/run_db_tests.sh` |

| Compile-level leftovers and most remaining journeys | 6 | 16 tests move to `make test-db`; 7 are deleted or return to `make test-all` |

The six still deferred, with what each needs:

- `flatfile_auction_coin_put_journey`: a full-world boot, because
  `init_auction_houses()` does not run under `--minimal`.
- `flatfile_locker_journey`: converted but blocked by suspected finding 1 below.
- `flatfile_newbie_regrant_journey`: converted but blocked by suspected finding 2 below.
- `pet_restart_journey`: SQL seeding across `player_items` and `player_pet_items`.
- `flatfile_full_world_boot`: depends on flat directories and a saved `RENT_CAMPED`,
  which MariaDB does not store.
- `flatfile_player_repository`: about 41 files still reference its inspector.

Suspected gameplay findings, not caused by this work and not changed in `src/`:

1. Entering a locker by your own character name is refused in the converted journey.
   `locker_enter_character` builds the locker name from `account_characters.racewar`,
   which is 0 there while the locker is `account.journeyacct.1.locker`. Check whether
   real data has the same mismatch, or only this journey's seed.
2. The Chaos Sorcerer spellbook assertion requires `value3` to equal the spell count;
   observed `pages=1668 spells=226`. `FillMasterSpellBook` stores the sum of spell
   circles, so the old assertion may never have held for that book.

Login assertions after death, and two `You break camp...` logins, now expect the
normal `Welcome to Duris` text, because `rtype` is always 0 on MariaDB.

`make test-all` has no database, so a converted journey belongs in
`tests/run_db_tests.sh`. Remaining conversions use `mariadb_authority()` in
`test_flatfile_combat_journey.py` and replace file seeding with SQL.

Finding from the journey conversion: MariaDB has no saved `save_intent`, so
`d->rtype` in `account.c` is always 0. Logging in after a death prints the normal
login text rather than "You rejoin the land of the living...", and by reading
`nanny.c` the death-return birthplace routing and hunger reset are skipped too. This
is how production already behaves; removing the flat-file backend did not change it.
Converted journeys assert the MariaDB behavior, and the owner can decide whether to
restore the old return handling.

Still deferred from the compile batch: `divine_boon_repository` and
`frag_cap_repository` (their default mode is flat-file only), `flatfile_help_catalog`
(needs a fake `help_cache` for about 150 assertions), `epic_gain_runtime`, and
`new_player_bank_hydration` (fixtures rebuilt on the deleted boon and player-domain APIs).

Possible existing server issues found while converting, not caused by this work and
not changed: `save_account_character_departure` returns before stamping
`acct_good`/`acct_evil` when `sql_queue` refuses, skipping the side-switch cooldown;
`PurgeCorpseFile` has no `skip_corpse_save` guard and passes `action_description` to
`snprintf` without a null check.

### Step 5 evidence

`tests/run_regression_tests.py` now holds `FLATFILE_REMOVAL_DEFERRED_TEST_NAMES`,
174 exact names, and prints how many it excluded. 49 backend-only `test_flatfile_*`
tests with no other reference, and 37 orphaned harnesses, are deleted. The
selected harnesses are adapted: persistence mode, build contract, launcher, backup
unit tests, restore integration (narrowed, with new nonempty combat and starter-kit
qualifier cases), combat-intent backup, locker shutdown recovery, and the six
database-suite scripts. `persistence_restore_fixture.cpp` is now receipts-only.

When the list stood at 177, its causes were: 37 build a flat-file server, 86 include
or compile deleted code, and 54 fail an assertion. A sample of 25 of those 54 showed
source-text or stubbed-harness breakage, not a MariaDB behavior change. The other 29
were not read individually, so a behavior change hiding among them is not ruled out.

### Final proof (first pass)

Commands are the ones in the Proof section; results at the commit recorded in the PR.

| Check | Result |
| --- | --- |
| Starting commit, `make test-all` | 1011 of 1011 passed in 18 minutes |
| Starting commit, `tests/run_db_tests.sh` | 107 of 112 passed |
| Strip comparison | 520 of 521 identical; the other differs by one reflowed line |
| Fresh build under `bin/flatfile-removal-fast`, plus `-O2` production profile | clean under `-Werror` |
| `python3 tests/run_regression_tests.py` | passes with 174 named exclusions |
| `tests/run_db_tests.sh` on the fresh server | 102 of 112 passed; 5 more pass individually after the harness repairs below; the last 5 also fail on the starting commit |
| Restore integration in a root container | all 3 cases passed, including new nonempty combat and starter-kit records |

The fresh-server database run first failed `artifact_guild`, `statistics`,
`telemetry_repository`, `artifact_mana`, and `last_command`, all on harness compile
or link errors. Each was repaired and passes when run on its own; the whole suite
was not repeated afterward, because only test files changed.

Known failures that are not from this work: `world_restart_clean`, `_copyover`,
`_crash`, `_handover`, and `_taken` fail identically on the untouched starting
commit, timing out waiting for the `Save` prompt.

First pass is done. Remaining work is the deferred list under "Completion and
deferred work": each conversion removes a name from
`FLATFILE_REMOVAL_DEFERRED_TEST_NAMES`, starting at `test_flatfile_combat_journey.py`.

### Step 4 evidence

`cycle_mud.sh` rejects any `PERSISTENCE_MODE` except `mariadb-primary` and ignores
leftover `FLATFILE_*` settings. `persistence_backup.py` and `persistence_restore.py`
capture and restore MariaDB only; a flat-file generation in a backup root is now
rejected as `invalid_generation_manifest`, which the owner's "no flat-file state"
statement makes acceptable. `qualify_flatfile_restore` is receipts-only and links
the nine sources from the trial. `build-restore-tools` no longer builds a second
server, the `flatfile-build` CI job is gone, and the current docs and
`.env.example` no longer advertise the backend. `check_flatfile_account_locker_conversion.sh`
and `scripts/restore_flatfile_backup.sh` keep their names; the first is a read-only
historical check and the second is the generic restore wrapper.

### Steps 2b and 3 evidence

Every dispatch site now keeps its MariaDB branch and `persistence_mode_get()`,
`persistence_mode_requires_mysql()`, and `persistence_mode_flatfile_root()` are
gone. `persistence_mode_configure()` rejects any value except unset, empty, or
`mariadb-primary`. These two steps ship together because deleting the mode
queries is what makes the deleted repositories uncompilable.

`src/flatfile` keeps `flatfile_store`, `flatfile_help_catalog`,
`flatfile_shopkeeper_capture`, and two headers trimmed to record types:
`flatfile_shopkeeper_repository.h` and `flatfile_ship_repository.h`. The ship
header is a new finding: the divine trade command codec is shared with the SQL
path and carries `flatfile_ship_crew_record`/`flatfile_ship_slot_record`.

Also removed because only the deleted paths used them: `divine_trade_flatfile`,
`artifact_population_flatfile`, `boon_shop_transaction`, `boon_shop_command`,
`kingdom_restore.h`, the flat boon helpers in `boon.c`, and `item_claim_log_item`.

Left in place on purpose: `shop_trade_transaction`, `shop_trade_runtime`, and
`shop_trade_command` have no submitter after this change, but seven files call
their no-op busy/ready/capture hooks and `shop.c` shares the payload type.
Removing them is ordinary dead-code cleanup, recorded under deferred work.

Proof so far: the server, `pfile`, and `telemetry-state` build at `-Og` under
`-Werror`, and `run_mysql_bank_restart_journey.py` passes on the new binary.
Baseline on the starting commit: `make test-all` 1011 of 1011 passed in 18
minutes.

### Step 2a evidence

`unifdef -U__NO_MYSQL__ -t -m` over the 71 files, then `./scripts/format.sh` for
the blank lines it left. The 5 leftover macro comments, and comments that
described the two-backend split in the same files, are rewritten. The
preprocessor comparison shows 520 of 521 files identical; the exception,
`net/comm.c`, differs only because clang-format joined one `if` condition onto a
single line, which is the same tokens. `make -C src` builds, and
`make -C src -n PERSISTENCE_BACKEND=flatfile all` stops with the new diagnostic.

**The strip alone breaks tests that build the flat-file server or use the
`__NO_MYSQL__` shape of the code.** `make test-all` is not expected to pass until
the top of the stack adds the named deferred list, so merge the stack together.
