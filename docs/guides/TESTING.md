# Testing

The project uses focused regression tests in `tests/async/`, plus
schema/migration checks at `tests/` root. The root `Makefile` provides a single
gate while retaining fast commands for focused work.

## Layout

```
tests/
├── async/                       # focused regression + source-contract tests
│   ├── test_*.py                # plain python3 regressions; no framework
│   ├── run_*.sh                 # special-purpose and legacy thin wrappers
│   └── run_*_mysql.sh           # MySQL-backed schema-contract tests (need a live DB)
├── run_regression_tests.py      # discovery, bounded parallelism, failure summary
├── compare_bootstrap_mud_schema.sh   # diff live schema vs bootstrap baseline
├── test_migration_replay_safety.sh   # migration re-run safety
└── test_run_migration_persistence_schema.sh
```

## Test styles

**Source-contract tests** — read the C sources as text and assert structural
invariants (a guard exists, a call site was not reintroduced, an ordering
holds). Example (`tests/async/test_sql_pool_shutdown.py`): slices out
`sql_pool_acquire`/`sql_pool_shutdown` from `src/sql/sql_pool.c` and asserts the
closing-pool checks are present. These need no database and no build.

**Behavioral tests** — boot or exercise server logic where feasible; most
regression coverage for past crashes is contract-style because full boots are
expensive.

**Schema tests** - verify migrations/persistence contracts against disposable
MySQL or MariaDB instances (development databases only).

## Running

```bash
# Complete gate: builds all maintained binaries and tools,
# generates world data, then runs Python and native regression tests.
make test-all

# Regression tests without rebuilding the server or area editor:
make test

# Limit concurrency, filter by filename, or inspect discovery:
make test TEST_JOBS=1
make test-python TEST_MATCH=wear
make test-list

# Single test (preferred while iterating):
python3 tests/async/test_wear_all_regression.py
# or via its wrapper:
tests/async/run_sql_pool_shutdown.sh

# Isolated Docker database legs and MariaDB journeys (Docker is an optional prerequisite):
make test-db

# Full historical legacy upgrade, replay, bootstrap equivalence, and compatibility:
tests/async/run_legacy_migration_mysql.sh

# Runtime schema compatibility on both supported variants:
tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh
```

`TEST_JOBS=0` is the default and selects up to eight workers based on available
CPUs. Test output is buffered per process so parallel failures remain readable.
The runner executes every discovered `test_*.py` in a separate process and
returns nonzero if any test fails. The journeys that boot a real server, and the
large sanitizer harness, start together once the parallel phase is done. They
wait on game time, not on the CPU, and they share one server build.

`make test-all` deliberately excludes Docker and externally provisioned
database checks. `make test-db` builds the server and generates the world first, then
runs the isolated database legs and the MariaDB journeys listed in
`tests/run_db_tests.sh`, 12 at a time (`TEST_DB_JOBS=N` changes that). Every test creates and destroys its own MySQL or MariaDB
container, prints `PASS` or `FAIL` with its seconds, and writes its log under
`bin/tests/db/`. A new leg or journey is one more line in that list;
`tests/async/with_disposable_mariadb.sh CMD...` gives a journey its own MariaDB.
The three scripts at the root of `tests/` require explicitly named disposable
or read-only databases and are manual migration-verification tools. Never point
them at production.

The MariaDB playtime journey runs in `make test-db`. To run it alone after a
MariaDB server build, use `tests/async/with_disposable_mariadb.sh python3
tests/async/test_mysql_playtime_journey.py --server bin/server/dms_new`. The
journey creates and removes its own schema and
invokes `test_playtime_mysql_repository.py` with that schema's environment. Both
scripts are excluded from argument-free discovery; the database-independent
playtime capture, checkpoint, legacy SQL, and flat-file tests remain in `make test-all`.

The game loop budget journey (`test_mysql_game_loop_budget_journey.py`, in
`make test-db`) boots the full world on MariaDB, has scripted players camp and rent
while the first hourly event runs, and fails if a pulse runs past its 250 ms. It
prints what the loop measured (tick, event and command times, deferred events, the
costliest callbacks), so it is also the load to measure a build with:
`tests/async/with_disposable_mariadb.sh python3
tests/async/test_mysql_game_loop_budget_journey.py --server <dms_new> --players 30
--hours 2`.

The world capture journey (`test_mysql_world_capture_journey.py`, in `make test-db`)
boots the full world on MariaDB and Redis with world recovery on and 8,000 more objects
on the ground, and has scripted players play while the first capture runs. It fails if
the generation is not above the old 64 MiB ceiling, if its capture takes a third of its
300 s, or if a pulse runs past its 250 ms; it then kills the server, and fails unless the
next boot restores the generation. It prints the generation's size, the capture's time
and what the restore brought back; `--players N` scales the load. Its first boot is on
an empty database, so it is also the boot test for SQL queued before the writer starts:
it fails unless every artifact the boot created has its `artifacts` and
`artifact_domain_state` rows, each outpost's stored hit points are set and the frag list
cache is filled. Both boots must cache the six artifact lists (the restored one reads
them after the restore), and neither may log a `sql job` line (`not queued`, or
`failed at boot`).
`run_world_recovery_journey.py`, also in `make test-db`, covers the switch on the mini
world: off, the alert of an outage, the writer coming back, a crash's restore and the
defaults. `run_world_restart_journey.py <server> <scenario>` covers what a restart leaves,
one scenario a run and each its own line in `make test-db`: `crash` (the lease is renewed,
the boot after a crash consumes the generation it restored and publishes its own, and a
second crash restores that one), `copyover` (the new image holds the lease at once),
`restart` (a clean stop takes a last capture and the boot restores it), `taken` (an object
a character took and saved after the capture is not restored to the floor, and one it
saved and dropped before the capture is; the boot reaps the dropped object's ownership
record with the dissolved starter kit's, so the login after it counts no
`missing_payload_rows` and the saves wrote no `unowned_object` line, both without
`DURIS_PERSISTENCE_TRACE`), `handover` (a character takes the banana after the capture
and is checkpointed, gives it to a second one, who saves, drops it and saves, and the
server crashes before the giver's next checkpoint: the boot keeps the record, which is
what makes the giver's older copy load as stale, so the floor copy comes back and only
one character holds the banana), `midcapture` (an object that leaves a floor
container while a capture runs, and whose drop is journaled, is restored once) and
`slowread` (a boot whose reads of Redis miss their deadline asks again and restores).

MySQL fixtures that reuse a table within a statement must account for MySQL's
`Can't reopen table` restriction on connection-local temporary tables; MariaDB
may accept the same fixture. Use isolated ordinary tables with explicit cleanup
when needed to execute the actual production query shape. Do not weaken queries
or narrow the backend matrix merely to make a temporary-table fixture pass.

### Shared journey server artifacts

The Python runner defaults `DURIS_REGRESSION_BUILD_CACHE` to
`bin/regression-artifacts`. Account recovery, flat-file boot preflight, Chaos
kit, combat and full-world boot acquire one compatible flat-file server from
`tests/async/server_build_artifacts.py`. Each journey retains its own temporary
authority, journals, logs, listeners and process cleanup. Executables are shared
read-only; runtime state is never stored in the artifact directory. The
item-prompt ASan/UBSan harness remains a separate build with its existing flags
and the server build's 600-second ceiling. That one server build uses every
core, and the journeys start together when it is done.

The artifact key covers all files under `src/` (including untracked files),
test headers, the helper contract, the flat-file backend, and the inherited build
environment, including profile, feature flags and Make overrides. It also hashes
the effective compiler, Make, assembler, linker, compiler internals, installed
headers and libraries. Standard GNU compiler search directories and explicit
`CPATH`, `CPLUS_INCLUDE_PATH`, `C_INCLUDE_PATH` and `LIBRARY_PATH` directories,
plus explicit include/library paths in Make's effective flags, are fingerprinted
by content. Keep external build inputs in these declared paths;
use `DURIS_REGRESSION_BUILD_CACHE=off` for toolchains with hidden inputs or
wrappers that do not support GNU compiler discovery. Runtime-only full-world
diagnostics and shell working-directory variables do not invalidate a build.

On every acquisition, the helper verifies executable and build-log SHA-256
hashes and rechecks the client-free compilation assertions. Missing or malformed
metadata, altered binaries/logs and changed inputs trigger a fresh build. Inputs
are checked again after compilation; a build spanning an input change is rejected.
A per-key lock prevents duplicate concurrent builds, and atomic manifests publish
only successful artifacts. Replacement builds use new directories so an existing
process keeps its executable. Old generations remain until the cache is removed
when no journeys are using it; `make clean-all` also removes `bin/`.

Direct test invocations build privately unless the cache variable is set. To
measure the complete Python gate on the same host and worker count:

```bash
DURIS_REGRESSION_BUILD_CACHE=off python3 tests/run_regression_tests.py --jobs 4
DURIS_REGRESSION_BUILD_CACHE="$PWD/bin/benchmark-fresh" python3 tests/run_regression_tests.py --jobs 4
DURIS_REGRESSION_BUILD_CACHE="$PWD/bin/benchmark-fresh" python3 tests/run_regression_tests.py --jobs 4
```

Choose an unused directory for the clean-cache run. Per-journey output reports
server build time, artifact validation time, and remaining journey/fixture time.
The last category includes inspector compilation and process startup; it is not
solely gameplay time. Cache keys hash environment values without storing their
plaintext in manifests. Never check cache artifacts into Git.

Measured once on 2026-09-10 (four-CPU Ubuntu 24.04 container, four workers, GCC
13.3.0): the Python gate took 1,315 s with five server builds, 911 s with an empty
artifact cache (one build, 30.7% faster) and 781 s with a retained cache (no build,
40.6% faster). These are single-run, host-specific numbers, not an SLA.

## Before a merge

Run the gate, one command after the other, on a quiet machine. The performance
gate (`test_telemetry_capacity_272.py`) and the latency journeys are
CPU-sensitive, and a busy machine fails their time budgets.

```bash
./scripts/format.sh --all --check
make test-all -j16 TEST_JOBS=16
make test-db
```

`make test-all` takes about 10 minutes and `make test-db` about 3½ (16 cores,
2026-09-29). Run these only when the change touches what they check:

| Check | When |
| --- | --- |
| The backup-recovery container job (root-only `test_persistence_backup_integration.py`) | backup, restore, `scripts/backup_*`, or the flat-file launcher |
| CodeQL and Trivy (`security.yml`) | dependencies, `packaging/`, `Dockerfile`, network or authentication code, and before a production deploy |
| `npm ci --prefix site && npm test --prefix site` | `docs/` or `site/` |

Do not replay the `flatfile-build`, `quality` or `build.yml` workflow jobs step
by step. Their tests are the ones `make test-all` just ran on the same host.

## Full-world save diagnostics

`test_flatfile_full_world_boot.py` supports opt-in synthetic failure/recovery
experiments without using the configured database:

| Variable | Effect |
| --- | --- |
| `DURIS_FULL_WORLD_ARTIFACT_DIR` | Retain failed synthetic authority, journals, transcripts, and server diagnostics in a private untracked directory; TLS keys are excluded and the fixture password is redacted. |
| `DURIS_FULL_WORLD_REPEATS` | Run 1-100 fresh fixture journeys with one build. |
| `DURIS_FULL_WORLD_BINARY_CACHE` | Legacy opt-in cache prefix below `bin/`; verified generations now live in `<prefix>.artifacts/`. Existing legacy binary/JSON pairs are not reused. `DURIS_REGRESSION_BUILD_CACHE` takes precedence when set. |
| `DURIS_FULL_WORLD_DELAY_CAMP=1` | Hold the synthetic player lock through camp timeout; verify retention, automatic retry, and a later fresh-intent camp. |
| `DURIS_FULL_WORLD_CRASH_PHASE` | `before_ack` or `after_ack` replaces the first clean shutdown with an intentional crash around the save durability boundary. |

Normal runs keep their original deadlines and successful-fixture cleanup.
Classify failures by boot, manual save, camp, recovery, or shutdown; distinguish
an observation timeout from a rejected save. Retain the revision/worker timeline
before diagnosing storage or scheduler latency. A passing rerun cannot establish
the cause of a historical failure whose timeline was discarded.

The separate combat journey reconnects after creation to hydrate account-bank
revision and disables optional boons. It proves that stated fixture scope;
it does not prove first-session currency or boon-enabled death/reward behavior.

## Validation matrix

No single command proves release readiness. Use the narrowest applicable row while
iterating, then run every row required by the session or release gate.

| Evidence boundary | Command | What it proves | What it does not prove |
|---|---|---|---|
| Documentation | `python3 tests/async/test_documentation_contract.py` | Maintained links, paths, commands, configuration names, safety language, and diagram contracts | Runtime or database behavior |
| Focused source/runtime | `python3 tests/async/test_<feature>.py` | One named invariant or compiled harness | Unrelated domains or integrated load |
| Server build | `make -C src` | C++20 server compiles under the warning profile | Schema compatibility or runtime readiness |
| Repository gate | `make test-all` | Maintained builds, generated world inputs, all discovered Python tests, and native signal tests | Docker database suites, representative data, or a 200-player hold |
| Disposable database | `make test-db` | Listed schema contracts, legacy-to-current convergence, and the MariaDB journeys on a real server, each on its own Docker container | Configured database state |
| Dual-engine boot contract | `tests/async/run_runtime_compatibility_mysql.sh` and `RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh` | Fresh bootstrap, immutable head, drift rejection, and boot compatibility on MySQL 8 and MariaDB 10.11 | A configured or production upgrade |
| Lifecycle/privacy | commands below | Pending-policy fail-closed behavior, synthetic archive/export/erasure contracts, and disposable schemas | Controller approval, legal compliance, or enabled canonical mutation |
| Capacity/fault precursors | commands below | Bounded 25/50/100/200 logical-client codecs and named crash/fault invariants | Representative eight-profile 30-minute 200-player readiness |
| 200-player gate | [`PHASE03_READINESS.md`](../gates/PHASE03_READINESS.md) | Only the complete qualified workload, fault, reconciliation, privacy, migration, and restore evidence can support readiness | Nothing until every criterion is executed and recorded |

### Load, recovery, and fault contracts

These focused tests use source inspection, compiled local harnesses, or synthetic
state. They do not connect to the configured database:

```bash
python3 tests/async/test_player_load_pipeline.py
python3 tests/async/test_player_load_items.py
python3 tests/async/test_player_load_pets.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_critical_command_coordinator.py
python3 tests/async/test_critical_transaction_contract.py
python3 tests/async/test_world_recovery_pipeline.py
python3 tests/async/test_maintenance_scheduler.py
python3 tests/async/test_worker_fault_injection.py
python3 tests/async/test_phase01_recovery_gate.py
python3 tests/async/test_phase02_capacity_and_crash_gate.py
```

The Phase 01 and Phase 02 gates include 25/50/100/200 logical-client waves and bounded
codec/crash coverage. They are precursor evidence only. They do not perform the eight
representative workload profiles, 30-minute 200-player holds, production-clone query
measurements, or complete fault/reconciliation matrix the 200-player gate requires.

### Account recovery contracts

Password reset by email is covered by an executed core harness (injected mail sender and
clock, no network), a wire-level SMTP harness against a fake relay on `127.0.0.1`, a
source-contract pin set, and a telnet journey that boots the client-free server with a
fake relay. None of them needs a real relay or a database; the compiled harnesses need
`g++` plus the libcurl and OpenSSL development headers from the dependency metapackage:

```bash
python3 tests/async/test_account_recovery.py
python3 tests/async/test_account_recovery_smtp_live.py
python3 tests/async/test_account_recovery_contract.py
python3 tests/async/test_account_recovery_journey.py
```

The harnesses never print a reset code or an address; a captured code reaches the driver
only through a temporary file. TLS/STARTTLS and SMTP AUTH are not exercised (the fake relay
is plaintext on loopback, which the configuration rules permit), so the first production
send is the first evidence for a real relay.

### Lifecycle and privacy contracts

Run the source/synthetic controls first:

```bash
python3 scripts/validate_data_lifecycle.py --json
python3 tests/async/test_data_lifecycle_manifest.py
python3 tests/async/test_season_reset_manifest.py
python3 tests/async/test_lifecycle_archive_execution.py
python3 tests/async/test_personal_data_export.py
python3 tests/async/test_account_erasure.py
python3 tests/async/test_immutable_migration_runner.py
python3 tests/async/test_runtime_boot_compatibility.py
```

Then run schema behavior only through the self-contained disposable wrappers:

```bash
tests/async/run_lifecycle_archive_schema_mysql.sh
tests/async/run_personal_data_export_schema_mysql.sh
tests/async/run_account_erasure_schema_mysql.sh
tests/async/run_legacy_migration_mysql.sh
tests/async/run_immutable_migration_ledger_mysql.sh
tests/async/run_runtime_compatibility_mysql.sh
RUNTIME_DB_IMAGE=mariadb:10.11 tests/async/run_runtime_compatibility_mysql.sh
```

Each wrapper must create and destroy its own isolated container. Never replace its
target with `.env` values or use a configured, shared, restored, or production
database. The checked-in lifecycle policy keeps canonical archive, export, and erasure
mutation disabled; passing tests prove the guard and synthetic contract, not policy
approval.

## 200-player readiness

Neither `make test-all`, `make test-db`, the Phase 01/02 logical-client gates, nor a
successful server boot is 200-player readiness evidence. Only the complete gate in
[`PHASE03_READINESS.md`](../gates/PHASE03_READINESS.md) is: eight profiles at
25/50/100/200 clients with 30-minute 200-client holds, the fault matrix, reconciliation
after every run, and privacy/restore validation on isolated representative data. That
document holds the procedure and the gate's current state. `UNQUALIFIED` is a safe
refusal, not a failed workload, and `QUALIFIED` is not readiness evidence either.

## Conventions for new tests

- One concern per file; name it after the feature/regression
  (`test_<feature>.py`). The root runner discovers it automatically. Add a
  `run_<feature>.sh` wrapper only when the test needs special environment setup
  or is useful as a standalone workflow.
- Keep them fast and deterministic; prefer source contracts over full boots
  when the invariant is structural.
- When you change behavior, add or update the focused regression test next to
  it — this is a stated repo convention (see `AGENTS.md`).
- Schema-related changes should extend or add a `_schema_mysql` variant so the
  contract is checked against a real database on a clone.

## What exists today (samples)

| Area | Tests |
|------|-------|
| Persistence | `run_persistence_contract_mysql.sh`, dirty-flush retry, SQL pool shutdown, `test_player_corpse_persistence_contract.py`, `run_corpse_persistence_schema_mysql.sh` |
| Crash regressions | wear-all, relic pickup, stuck command gate |
| Saves | copyover save guards, ship save guards/dedup, epic save guards |
| Phase 01 recovery gate | `test_phase01_recovery_gate.py` drives 25/50/100/200 logical-client waves with ambiguous-commit retries and enforces fork/ownership/route contracts |
| Critical commands | `test_critical_command_coordinator.py` exercises identity, codec, multi-key ordering, duplicate attachment, exact completion, retries, fences, bounds, and lifecycle |
| Critical transactions | `test_critical_transaction_contract.py` plus guarded `run_critical_command_schema_mysql.sh` cover schema, duplicate/mismatch, atomic rollback, concurrent locking, ambiguity lookup, outbox retry/dedupe/dead-letter/restart, and reconciliation |
| Help files | class/race helpfile completeness contracts |
| Event loop | hotspot budget regression |
| Build contract | `test_compiler_warning_profile.py`, `test_message_buffer_bounds.py` |
| Untrusted input | `test_unicode_runtime.py`, `test_ansi_runtime.py`, `test_json_utils_runtime.py`, `test_ttype_runtime.py` |

The four untrusted-input suites are behavioral rather than contract-style: they
exercise the live decoders that handle network and player-visible text — UTF-8
widths and malformed/overlong/surrogate encodings, ANSI colour parsing and
gradients, JSON and GMCP escaping, and RFC 1091 terminal-type negotiation
including MTTS capability parsing. That is the shape to copy when the code under
test is a parser: every case is a real call, and every defect found while
writing them (unbounded continuation runs, invalid UTF-8 re-encoded as `U+FFFD`
and accepted as a map glyph, `MTTS 4JUNK` silently enabling capabilities,
gradient application dereferencing `end()` on an empty string) stayed as a
regression.

`test_compiler_warning_profile.py` is what keeps the `-Werror` guarantee in
[BUILDING.md](BUILDING.md#warning-profile) real: it fails if any of the six
formerly-excepted categories is suppressed again, by flag, by a reintroduced
exception variable, or by pragma.
