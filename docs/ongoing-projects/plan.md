# Plan: seven open fixes and the 2026-10-08 log review

Written 2026-10-08 against `master` at `6e1b93cdb`, after the clean-rebuild and fall fixes
landed (`2ce50bafb`). Rewritten the same day, after the move to GitHub, so that it stands
alone: each phase holds the problem, what was checked, the fix, the steps and when it is
done, and nothing here depends on an outside tracker. Phases 8 and 9 come from the log
review that followed the staging restart; the findings file that held them was deleted when
they were written here. The order and the decisions below are proposed; the owner locks or
changes them before Phase 1 starts. This file is a working note: delete it when the last
phase lands.

Work started on 2026-10-08 under the owner's goal to carry the plan through on its own:
the decisions still proposed were taken as written, and each phase's section says where
the work differs from them. Each phase's branch starts from the previous phase's branch,
and its pull request targets that branch (Phase 1's targets `master`), so a review reads
one phase's diff and the phases land in order; Phase 1's deadlines are then the gate of
every later phase.

## Status

Updated 2026-10-08. A new session starts here, then reads the phase it continues.

| Phase | Subject | State |
|---|---|---|
| 1 | Hung tests and silent backup failures | Built on `fix/4-phase-1-hung-tests`, gate green; open for review as PR #5, tag `backlog/phase-1-review-0` and one test fix after it. |
| 2 | Unauthenticated connections per address | Built on `fix/4-phase-2-connection-limit` (on Phase 1), gate green; open for review as PR #6, tag `backlog/phase-2-review-0`. |
| 3 | Shop listing, dompurify, dead helpers | Built on `fix/4-phase-3-shop-listing` (on Phase 2), gate green; open for review as PR #7, tag `backlog/phase-3-review-0`. |
| 4 | Security record and `SECURITY.md` | Built on `fix/4-phase-4-security-record` (on Phase 3), documents only, their tests green; open for review as PR #8, tag `backlog/phase-4-review-0`. |
| 5 | Studio-proc tag ids and `world.trg` | Built on `fix/4-phase-5-studioproc` (on Phase 4), gate green; open for review as PR #9, tag `backlog/phase-5-review-0`. |
| 6 | Site and README links | Landed 2026-10-08 on `master`, directly at the owner's request. |
| 7 | Quest EXP line and `achievements zones` | Built on `fix/4-phase-7-display-fixes` (on Phase 5), gate green; open for review as PR #10, tag `backlog/phase-7-review-0`. |
| 8 | Specials assigned to missing vnums | Built on `fix/4-phase-8-dead-specials` (on Phase 7), gate green; open for review, tag `backlog/phase-8-review-0`. |
| 9 | `board` specials and the audit heading | Not started. |

## Why these

Phases 1 to 7 are defects, exposures or wrong pointers, each a bounded change with a gate and
a regression test. Phases 8 and 9 are the three open rows of the log review after the
2026-10-08 staging restart: a latent defect, a logged warning and a stale heading. Other open
work is not in this plan:

| Work | Why not here |
|---|---|
| Archive, export and erasure are built but switched off (finding P00-S08 in `docs/records/SECURITY-COMPLIANCE.md`). | A retention and disclosure policy is the owner's decision; no engineering until it is made. |
| The 200-player readiness gate (`scripts/session14_gate.py`) has never been run. | Needs a run-or-retire decision, a manifest revised for the persistence reset, and a representative clone the repository does not have. |
| The flight dragon network (mobs 47015 to 47041): the world files are redesigned, the code is not. | Needs four answers from the builder and a re-exported sheet; the builder called it not critical. |
| Experience trophies: only observation is built, not the familiarity, penalty curve or enforcement. | The curve should come from observation data on a test server, which does not exist yet. |
| Quantity purchases (`buy <item> quantity <n> [into <container>]`, one summary per batch). | A usability feature larger than any phase here; it follows Phase 3, which bounds the listing it extends. |
| Telemetry: nothing rolls up or reports the encounter facts. | Feature work for a subsystem that ships off; the writer side it builds on landed in `338092a78`. |
| Live journeys for the Collector of Antiquities past intake, and full-server sanitizer journeys for four lifetime fixes. | Coverage work, each several journeys and (the second) a sanitizer build; the material of the plan after this one. |

## Decisions (proposed)

Decisions 5, 7, 9 and 10 were locked by the owner on 2026-10-08 as written below; Phases 8
and 9 have nothing left to decide. Decisions 5 and 7 were rewritten the same day for the move
to GitHub. Decisions 1 to 4, 6, 8 and 11 are still proposed.

| # | Decision | Where |
|---|---|---|
| 1 | A pooled test is ended after 900 s and a journey after 1800 s, by killing its process group; both are constants in the runner. A test ended that way, or by a signal, is a failure with its own label in the summary. A failure's output is printed when it happens, and every 60 s a line names the tests still running. | Phase 1 |
| 2 | A failed backup subprocess is reported with the command's basename, the phase, the exit status and the last 20 lines of its stderr (at most 2 KiB), with the database user, host and password replaced. | Phase 1 |
| 3 | At most 8 connections per address that have not entered an account name; the ninth is told so and closed, with one debug-log line, and nobody is banned. A connection silent at the account name prompt is closed after 120 s. Both are constants in `src/core/config.h`, documented in `CONFIGURATION.md`. The address is the one PROXY resolution yields. | Phase 2 |
| 4 | The listing is sent in pieces when the next line would not fit; dompurify is bumped by `npm audit fix --prefix site`; the two helpers are deleted. | Phase 3 |
| 5 | The scan of record is the `security baseline` workflow, which now runs on every push to `master`; Phase 4 records its latest completed run instead of replaying it, and runs only `make security-sbom` locally to see libcurl in the inventory. `SECURITY.md` names the `0.1.x` line and the private vulnerability reporting form of `LuminariMUD/Duris`, which the owner turned on on 2026-10-08. The baseline says in one sentence that Dependabot proposes action-pin and `site/` npm updates weekly. | Phase 4 |
| 6 | The three studio-proc ids are defined at the end of the `TAG_` list in `spells.h`, with a `static_assert` beside them and a source contract that no other `TAG_` reaches 2198. `world.trg` is built by `make_trg` from `areas/trg/<area>.trg`, run by `make_all`, and a malformed source fails `make world` with its file and line. | Phase 5 |
| 7 | The site is published by the existing `Project website` workflow, with the repository's GitHub Pages source set to GitHub Actions, at `https://luminarimud.github.io/Duris/`. The site's repository default is `LuminariMUD/Duris`. The README's documentation link goes to that site; its build and last-commit badges and its commit link go to `LuminariMUD/Duris`; the issues badge and link go, since work is not tracked in issues. | Phase 6 |
| 8 | The two display fixes are taken from the community tree with the author kept where a commit applies, adapted otherwise. | Phase 7 |
| 9 | The vnums `specs.assign.c` names are checked by a source contract against the area files `areas/AREA` lists, not at run time: the 121 assignments to vnums no longer in the world are deleted, and the test fails the gate when a new one appears or an area leaves the list. The `0` lookups keep returning 0 on a miss; about sixty callers outside `specs.assign.c` compare their result against 0. | Phase 8 |
| 10 | The nineteen explicit `board` assignments in `specs.assign.c` go; `initialize_boards()` assigns the special to every table row itself. 55197, the discussion board loaded into Winterhaven's Immortal Control Room, gets a `board_info` row at AVATAR for read, write and remove, file `lib/boards/winterhaven`. 87 and 55026 are loaded by no zone and stay plain objects. Room 1196 keeps the necklace; the zone comment that still calls it a board is corrected. | Phase 9 |
| 11 | The phases are done in the order below. | All |

## Order

By cost of leaving it: the gate every later phase runs (Phase 1), then the one exposure
(Phase 2: a silent client can hold every login slot for 15 minutes), a latent stack overflow
and a known advisory (Phase 3), a security record and policy that are out of date (Phase 4),
an id collision waiting to happen and triggers in a hand-edited file (Phase 5), links that
sent readers to other repositories (Phase 6, landed), then two display gaps (Phase 7). The
log-review phases come last: an assignment to index 0 that no loaded object or mob reaches
today, though room 0 does carry `inn` (Phase 8), then a logged warning and a stale heading
(Phase 9).

Things to keep in mind across phases:

- **Phases 8 and 9** both edit `src/specs/specs.assign.c`; Phase 9's nineteen lines are among
  the ones Phase 8's contract reads, so land 8 first.
- **Phase 2** edits `src/net/comm.c`, which `tests/async/test_boot_log_hygiene.py` pins in
  places; read its contracts before moving anything there.
- **Phase 3** touches `site/`; run `npm test --prefix site`.
- **Phase 4** edits README-level documents. `tests/async/test_documentation_contract.py`
  pins README strings and checks every maintained Markdown link; run it bare.
- **Phase 3's** listing bound is what quantity purchases (not in this plan) build on.

## Every phase

- One branch per phase, from `master`, reviewed on a pull request on `LuminariMUD/Duris`.
- `./scripts/format.sh --check`, `make -C src`, the phase's focused tests, then one run of
  `make test-all` and `make test-db` before it lands.
- A regression test for each behaviour that changes, as the phase's "Done when" asks.
- The head a review reads is tagged `backlog/phase-<n>-review-<round>`, rounds from 0, and
  the tag is pushed with the branch.
- A phase lands as a `--no-ff` merge of the last reviewed head, with the landing recorded in
  this file's Status table.
- The phase's section is brought up to date in the same branch: what was built, what differs
  from the plan and why, the gate's result, and what is left.

---

## Phase 1: a hung test holds the gate, a failed backup says one word

**Built** on `fix/4-phase-1-hung-tests` (from `master` at `690a7575d`), 2026-10-08:

- `89c370bc7`: `tests/run_regression_tests.py` runs each test in its own process group
  with its output in a temporary file (`run_test(path, deadline)`), ends one still running
  at `POOLED_DEADLINE_SECONDS` (900) or `JOURNEY_DEADLINE_SECONDS` (1800) with `SIGKILL` to
  the group, and labels a result `PASS`, `FAIL`, `TIMEOUT` or the signal's name. A failure's
  output is printed when it fails; the end of the run lists failures with their kind; the
  summary reads `N passed, F failed (T timed out, S ended by a signal)`; every
  `PROGRESS_SECONDS` (60) a `still running:` line names the running tests. The cases are in
  `tests/async/test_root_test_harness.py`. `docs/guides/TESTING.md` says so.
- `76fb1bfa8`: `scripts/persistence_backup.py` keeps a failed command's stderr.
  `subprocess_error()` builds the `BackupError` with `command` (basename), `phase` (a
  required keyword of `run()` and `streaming_process()`, one per call site), `exit_status`
  (negative for a signal, null at the deadline) and `stderr` (last 20 lines, at most
  2 KiB), the values of `DB_PASSWD`, `DB_USER` and `DB_HOST` the command was given replaced
  longest first, before the cut; `failure()` merges that detail into the record. The case is
  in `tests/async/test_persistence_backup.py`; `docs/operations/BACKUPS.md` describes the
  record.

**What differs from the plan, and why.**

- The runner's cases went into the existing `test_root_test_harness.py`, which already
  loads the runner, not a new `test_regression_runner.py`; and `main()` is driven by
  patching `ROOT` and `TEST_DIRECTORY`, so `discover_tests()` needed no `directory`
  parameter.
- A test's output goes to a temporary file, not a pipe: reading a pipe after the kill would
  wait for any process that left the group and still held it; the file is read once the
  test's own process has been reaped.
- The values are replaced where the error is built, from the environment the command was
  given, not in `failure()` from the tool's own: the restore's commands run with a clean
  environment and their own database user and password.
- The restore's import (`streaming_process(..., input_pipe=True)`) keeps no stderr:
  MariaDB quotes the rows it rejects, and the plan rules out printing a restored row.
- `run()`'s own deadline (120 s for the restore's service load, 300 s otherwise) is reported
  as `subprocess_timed_out` with its phase and what the command wrote, instead of a bare
  `subprocess.TimeoutExpired`.
- `tests/async/test_persistence_backup_integration.py` (the CI `backup recovery` job, root
  and a disposable MariaDB) passes `phase="test"` to its fixture calls.

**Gate** on `76fb1bfa8`: `./scripts/format.sh --all --check` clean, `make test-all -j16
TEST_JOBS=16` 675 passed, 0 failed (0 timed out, 0 ended by a signal) in 8 min 53 s,
`make test-db` 48 of 48. The new runner case fails on the old runner. The CI `backup
recovery` job was replayed in a privileged `ubuntu:24.04` container: the four
regression files and `test_persistence_backup_integration.py` as root (5 tests, real
MariaDB) passed. Nothing is left.

**After the tag.** Phase 2's gate failed `test_root_test_harness.py` once: its `gone()`
helper read `/proc/<pid>/stat` of a process reaped between the open and the read, which
raises `ProcessLookupError`, not `FileNotFoundError`. One commit after
`backlog/phase-1-review-0` treats both as gone; the pull request's head is the one to
review.

**Problem.** Two failures that are hard to see, first recorded in a pipeline analysis of
2026-09-11. A test that hangs holds `make test` and `make test-all` until someone kills it,
and prints nothing meanwhile; a failed test's output is shown only after every test has
finished. The backup tool, `scripts/persistence_backup.py`, throws away a failed
subprocess's stderr and reports only `subprocess_failed`: when five restore-qualification
tests failed in September, that word was all there was, and the cause (a lock file the
verifier rejected) was found only by reproducing them. The command line can name the
database user and host, so neither it, nor a credential, nor a restored row may be printed.

**Checked** at `6e1b93cdb`. `run_test()` (`tests/run_regression_tests.py` L84) runs each test
with `subprocess.run()` and no deadline, and holds its output until it exits. `main()` runs
the pool, then the 15 journeys in `RESOURCE_INTENSIVE_TEST_NAMES` side by side, and prints
every failure's output after both (L187). Nothing says what is still running. In the backup
tool, `run()` (L390) and `streaming_process()` (L364) send stderr to `/dev/null`; the second
already kills the process group at 300 s, which is the shape the runner needs. `require()`
raises `BackupError(code)` and `main()` prints one JSON record. `failure()` (L60) drops the
message on purpose because the command line names the database user and host.

**Fix.**

- The runner: `run_test(path, deadline)` starts the test with `Popen(start_new_session=True)`
  and `communicate(timeout=deadline)`. On `TimeoutExpired` it kills the group with
  `SIGKILL`, reaps it, keeps what was written, and marks the result `timed_out`. A negative
  return code is reported as the signal. `report()` prints a failed test's output at once;
  the end of the run lists failures by name and kind, and the summary line counts timeouts
  and signals apart. While a pool waits, `as_completed(timeout=60)` prints the names still
  running. Deadlines: 900 s pooled (a pooled test may first build a server artifact, about
  three minutes), 1800 s journeys (the slowest measured 309 s on a loaded host).
- The backup tool: `BackupError` carries the command's basename, the phase (a parameter the
  callers pass), the exit status and a bounded stderr tail; `run()` and
  `streaming_process()` capture stderr; `failure()` renders them with the values of
  `DB_USER`, `DB_HOST` and `DB_PASSWD` replaced before the record is printed.

**Steps.**

1. The runner change, with `tests/async/test_regression_runner.py`: three throwaway scripts
   in a temporary directory (sleep forever; spawn a sleeping child and wait on it; print and
   exit 1) run through `run_test()` with a one-second deadline. The two hangs end as
   `timed_out` within a few seconds and leave no process in their group; the failure's
   output is in its result. The smallest seam for the end-to-end assertion (output before
   the summary) is a `directory` parameter on `discover_tests()`.
2. The backup change, with a case in `tests/async/test_persistence_backup.py` where a
   subprocess fails with stderr naming the user and host, and the record carries the phase,
   exit status and tail without either.
3. `docs/guides/TESTING.md` and `docs/operations/BACKUPS.md` describe the deadline and the
   record. Gate.

**Done when.**

- A test that sleeps forever, and one that spawns a child that does, are each ended at their
  deadline and reported as a timeout, and the rest of the run completes. A test of the
  runner covers both.
- A failing test's output appears before the run ends.
- A deliberately failing backup subprocess is reported with its phase, exit status and a
  bounded, sanitized stderr tail, and a test pins that no credential or host reaches the
  output.

## Phase 2: unauthenticated connections per address

**Built** on `fix/4-phase-2-connection-limit` (stacked on Phase 1), 2026-10-08:

- `7c21ef491` (a defect found on the way, its own commit): every listener is an
  `AF_INET6` socket, so an IPv4 client arrives as `::ffff:a.b.c.d`, and both checks of
  `DURIS_TRUSTED_PROXY_IP` parsed the setting only as IPv6. An IPv4 proxy, such as the
  `127.0.0.1` in `.env.example`, was never trusted: its PROXY and `X-Forwarded-For`
  headers were ignored, every website player had the proxy's address, and a completed
  WebSocket handshake closed every other website login in progress as a stale connection
  from the same address. `proxy_peer_is_trusted()` (`comm.c`) now matches a v4-mapped peer
  against the IPv4 form, and `websocket.c` calls it instead of its own copy.
- `dad3822f6`: `MAX_UNNAMED_CONNECTIONS_PER_ADDRESS` (8) and `UNNAMED_CONNECTION_TIMEOUT`
  (`120 * WAIT_SEC`) beside `MAX_CONNECTIONS` in `src/core/config.h`. `new_descriptor()`
  counts, after the address is known, the open connections from it in `CON_SSLNEGO`,
  `CON_GET_TERM` or `CON_GET_ACCT_NAME` (an authenticated DurisWeb service connection
  excepted) and, at 8, closes the new one before anything is set up: one `LOG_DEBUG` line
  `Refused connection from <address>: 8 open connections have not entered an account
  name.`, and a plain telnet client first reads `Too many connections from your address.`
  A connection from the trusted proxy without a PROXY header has the proxy's address,
  shared by its clients, and is not limited. The idle switch closes a connection silent at
  `CON_GET_ACCT_NAME` after `UNNAMED_CONNECTION_TIMEOUT`.
  `tests/async/test_connection_limit_journey.py` (in the resource-intensive set) drives a
  flat-file server: eight telnet connections from `127.0.0.1` and the ninth refused; eight
  TLS connections still negotiating from `127.0.0.4` and the ninth refused; an account
  created from `127.0.0.2` meanwhile; eight proxied connections for one PROXY-header client
  and the ninth refused while another client's is kept; nine telnet connections from the
  proxy's own address all kept; two website handshakes through the proxy with different
  `X-Forwarded-For` addresses both kept; a connection silent at the prompt closed between
  115 and 135 s. `docs/operations/CONFIGURATION.md` has a "Connections before an account
  name" section, and its `DURIS_TRUSTED_PROXY_IP` row, which had fallen out of its table
  and said telnet honoured `X-Forwarded-For`, is back in the table and correct.

**What differs from the plan, and why.**

- The trusted-proxy fix was not in the plan; without it the requirement that players
  behind the proxy are not counted as one address could not hold, and the journey's proxy
  case failed on it.
- WebSocket connections are counted as well as telnet and TLS ones, but a WebSocket client
  already kept at most one connection that had not logged in (a completed handshake closes
  the address's older ones), so the cap matters for telnet and TLS.
- A TLS connection that never finishes its handshake needed no new timeout: GnuTLS ends it
  after its default 40 s (a silent socket on the old dev server was closed after 39 s).
- The journey is `test_connection_limit_journey.py`, not `run_connection_limit_journey.py`:
  the runner discovers `test_*.py`, and the resource-intensive set is a list of those. The
  proxy case is part of the journey, not a separate harness.
- `docs/operations/RUNBOOK.md` names no login idle timeout and was not changed.
- A website client that sits at the account name prompt is now closed after 120 s, like a
  telnet one (it was 15 minutes); the plan's decision 3 does not tell them apart.

**Gate** on `348ae9fd4` (the same tree as `dad3822f6` before the rebase onto Phase 1's
test fix): `./scripts/format.sh --all --check` clean, `make test-all -j16 TEST_JOBS=16`
675 passed, 1 failed (`test_root_test_harness.py`, the `gone()` race fixed on Phase 1's
branch and then passing 12 runs in a row), `test_connection_limit_journey.py` 127 s,
`make test-db` 48 of 48. The journey's proxy case failed before `7c21ef491`: every
proxied connection was counted under the proxy's address. Nothing is left.

**Problem.** Found on 2026-10-05 in a full read of one server's logs. Over 51 minutes one
address opened 753 plain-telnet connections: a median of 13 a minute, at most 26 a minute,
11 in the busiest second. None got past the account name prompt (`CON_GET_ACCT_NAME`,
state 60), about 21 were open at once, and the client closed each within seconds. The server
was unaffected only because the client hung up: nothing limits how many connections one
address holds before it logs in, the ban list is the only per-host control (and a new server
starts with it empty), and a connection idle at the name prompt is kept for 15 minutes. One
client that opens about 240 connections and stays silent would hold every slot for 15 minutes
at a time and keep players out. A ban entry is a stopgap, not a fix. Whatever is chosen must
leave a server behind a trusted proxy usable, where many players share the proxy's address
(`DURIS_TRUSTED_PROXY_IP` in `docs/operations/CONFIGURATION.md`). Each such connection leaves
one `Losing descriptor without char` line, in `logs/log/debug` since `2ce50bafb`.

**Checked** at `6e1b93cdb`. `MAX_CONNECTIONS` is 256 for all clients together
(`src/core/config.h` L125; `avail_descs` in `src/net/comm.c` L2424). `new_descriptor()`
resolves the client address through the PROXY header when the peer is
`DURIS_TRUSTED_PROXY_IP` (L3508, L3764) and only then applies the ban list (`bannedsite()`,
called at L3869), so a count by resolved address already tells players behind the proxy
apart. The idle switch closes a descriptor at the account name prompt after 3600 pulses
(15 minutes, the default case at L1846); creation states get 2400 (L1834).

**Fix.** After the PROXY resolution, count the open descriptors with the same resolved
address that have not yet entered an account name; at the cap, write "Too many connections
from your address." and close the new one, with a debug-log line. A `CON_GET_ACCT_NAME` case
in the idle switch closes a silent connection at 480 pulses. The two constants sit beside
`MAX_CONNECTIONS` in `config.h` and are described in `docs/operations/CONFIGURATION.md`.

**Steps.**

1. The count and the refusal, the idle case, the constants.
2. A flat-file server journey (`tests/async/run_connection_limit_journey.py`, in the
   resource-intensive set): eight sockets from `127.0.0.1` reach the name prompt, the ninth
   is refused, a login bound to `127.0.0.2` still reaches the prompt and logs in, and a
   socket silent at the prompt is closed after the timeout. A harness case for the proxy:
   two PROXY headers with different client addresses from one peer count separately.
3. `CONFIGURATION.md`, `docs/operations/RUNBOOK.md` if it names the idle timeout. Gate.

**Done when.**

- One address cannot hold more than a set number of connections that have not yet entered an
  account name, and the limit is a documented constant.
- A connection that sends nothing at the account name prompt is closed well before
  15 minutes.
- A test opens connections from one address up to and past the limit and sees the excess
  refused while a login from another address still succeeds.
- Players behind the trusted proxy are not counted as one address.

## Phase 3: the shop listing, dompurify, two dead helpers

**Built** on `fix/4-phase-3-shop-listing` (stacked on Phase 2), 2026-10-08:

- `c4a9eb681`: `shopping_list()` sends `Gbuf1` and starts it again when the next line would
  not fit, before each `strcat()`; the "Nothing!" path is unchanged.
  `tests/async/test_shop_list_extract_contract.py`, the listing's existing test, now also
  compiles the production `shopping_list()` under ASan and UBSan with a keeper carrying
  700 items (about 70 KB) and checks every line arrives once, in order, in pieces under
  64 KB. Without the bound it reports a stack-buffer overflow.
- `3151e2d85`: `npm audit fix --prefix site` moved dompurify to 3.4.16, and an `overrides`
  entry in `site/package.json` pins katex 0.18.2. `npm audit --prefix site` reports no
  vulnerability; `npm test --prefix site` passes (15 tests).
- `2c814182e`: `got_all_ingredients()` and `extract_used_ingredients()` deleted;
  `get_bottle()` and `get_id_for()` keep their callers.
- `b606a9d8b`: the three rows in `docs/records/COMMUNITY_DURIS_TRACKING.md`: #700 (b) and
  #662 `Adapted`, #573 (e) `Rejected` (ours keeps `mix`; the helpers are noted).

**What differs from the plan, and why.**

- `npm audit` also reported katex 0.16.47 (GHSA-238p-pmpm-9mq7, low, fixed in 0.18.2),
  which mermaid pulls in, and a second dompurify advisory (GHSA-6688-9rhm-gjv2, fixed by
  the same 3.4.16). Every mermaid 12 release, 12.1.0 included, asks for katex `^0.16.47`,
  and npm's only automatic fix was a downgrade to mermaid 10.8.0, so the override pins
  katex instead, beside the existing `lodash-es` one. Mermaid's one katex call
  (`renderToString` with `throwOnError`, `displayMode`, `output`) renders under 0.18.2, and
  the site's diagrams use no math. Dependabot's #3 (dompurify) is the same lockfile line
  and becomes redundant when this lands; #1 (mermaid 12.1.0) is unaffected.
- The listing harness extends the listing's existing test instead of adding a file, and
  the bound is written inline at the one call site rather than as the community tree's
  `append_listing` helper.
- `2caf3a289` fixes a race in `tests/async/run_telemetry_schema_boot_journey.py`, found by
  this phase's gate: after its copyover signal the old image can still log a
  `telemetry_health` line (here a stall alert raised by the copyover tick) carrying the old
  producer, which the journey took for the new image's. It now reads from the old image's
  `copyover: executing new binary` line.
- This section's "Problem" called the community tree `LuminariMUD/Duris`; since the move
  to GitHub that is this repository, and theirs is `Community-Duris/Duris`.

**Gate** on `b606a9d8b`: `./scripts/format.sh --all --check` clean, `make test-all -j16
TEST_JOBS=16` 676 passed, 0 failed, `make test-db` 47 of 48 (`telemetry_schema_boot`, the
race above; with `2caf3a289` the leg passed twice in a row on its own). Nothing is left.

**Problem.** Three small things the community tree (`Community-Duris/Duris`, master at
`a1e4a7efd`, split from ours at `e1357a30a` on 2026-09-23) fixed after the split, found on
2026-10-04 by comparing the trees:

1. `shopping_list()` appends one line per item the keeper carries to a stack buffer of
   `MAX_STRING_LENGTH` (65,536 bytes) with `strcat()` and no length check, so a keeper
   carrying roughly 650 listable items overflows it. Latent: nothing caps what a keeper buys
   from players, but no keeper is known to hold that many. Their fix is part of `ef96aa3e3`,
   an `append_listing` helper that sends the buffer and starts again when the next line
   would not fit; the rest of that commit serves their quantity purchase and does not apply.
2. `site/package-lock.json` holds dompurify 3.4.15, pulled in by mermaid. `npm audit --prefix
   site` reports advisory GHSA-p98j-92pf-mc4p (low severity, DOM XSS through an
   `afterSanitize` hook), fixed in 3.4.16. Their fix is `4ffc58db1`, a lockfile bump.
3. `got_all_ingredients()` and `extract_used_ingredients()` have no caller in `src/` or
   `tests/`. Their `97095fd00` deletes them together with `get_bottle()` and `get_id_for()`,
   which our tree still calls.

**Checked** at `6e1b93cdb`. `shopping_list()` (`src/economy/shop.c` L1676) appends `Gbuf4` to
the stack buffer `Gbuf1` (L1604) with `strcat()` at L1796, unchecked. dompurify 3.4.15 is at
`site/package-lock.json` L1380. The helpers are at `src/classes/salchemist.c` L550 and L666.

**Fix.** In `shopping_list()`, before each `strcat()`, send `Gbuf1` and start it again when
the next line would not fit; the trailing "Nothing!" path is unchanged. `npm audit fix
--prefix site`, then `npm test --prefix site`. Delete the two helpers; `get_bottle()` and
`get_id_for()` stay.

**Steps.**

1. The listing bound, with a harness test that lists a keeper carrying 700 items and
   receives every line in order.
2. The lockfile bump; `npm audit --prefix site` reports nothing.
3. The deletion; `make -C src` clean. Gate.

**Done when.**

- A listing longer than the buffer reaches the player whole, and a test pins it.
- `npm audit --prefix site` reports no vulnerability.
- The two helpers are gone and the build is clean.

## Phase 4: the security record and `SECURITY.md`

**Built** on `fix/4-phase-4-security-record` (stacked on Phase 3), 2026-10-08, in
`ddb8abfc0`:

- The scan of record is the `security baseline` run 37808827646 on `master` at
  `690a7575d` (completed 2026-10-08 16:46 UTC): `make security-check` passed; CodeQL 2.27.1
  found 0 results over 58 rules and code scanning listed no open alert; Trivy `v0.70.0`
  scanned all 23 resolved direct packages, `libcurl4-gnutls-dev` 8.5.0 among them (its
  `trivy-results.json` artifact), with no fixed HIGH or CRITICAL finding.
- `docs/operations/SECURITY_BASELINE.md`: the workflow section says it runs on every push
  and pull request to `master` and that local replay is for changes that touch what it
  checks; Dependabot (action pins and `site/` npm, weekly) in one sentence; the failure
  policy says the hosted scan lists nothing unfixed or below HIGH; "Baseline Result
  (2026-10-08)" replaces the August one and the libcurl note, with the settings the owner
  turned on that day.
- `docs/records/SECURITY-COMPLIANCE.md`: the reporting row and the action-pin, source and
  container rows are `PASS`, the scan paragraph says what ran, and the header's date is
  2026-10-08. The direct-dependency row stays `PARTIAL` (transitive packages are not
  inventoried).
- `SECURITY.md`: the `0.1.x` line and the private vulnerability reporting form of
  `LuminariMUD/Duris` (`gh api repos/LuminariMUD/Duris/private-vulnerability-reporting`
  reads `{"enabled":true}`); no other repository is named.
- `tests/async/test_account_recovery_contract.py` C13 pinned the old "libcurl added, no
  scan has covered it yet" bullet; it now pins the scan that covered it.

**What differs from the plan, and why.**

- `make security-sbom` run locally lists `libcurl4-gnutls-dev` as declared but unresolved:
  this workstation has `libcurl4-openssl-dev` 8.5.0 instead. The workflow, which installs
  the build-deps package, resolved it, so the record cites the workflow's inventory.
- The hosted scan reports only fixed HIGH and CRITICAL findings, so the August scan's
  unfixed MEDIUM Git advisory (`CVE-2024-52005`) is kept as the last one seen at that
  depth rather than dropped or claimed fixed.
- No code changed, so the gate was the tests that read documents: the 41 tests that read
  `docs/` or the README, run bare (all pass after C13), and `npm test --prefix site`
  (15 tests). Phase 5's full gate runs on top of this tree.

**Problem.** Until the move to GitHub the dependency and code scans last ran on 2026-08-27,
and `libcurl4-gnutls-dev`, added to the build dependencies on 2026-09-06, was never scanned.
Since 2026-10-08 the `security baseline` workflow (`.github/workflows/security.yml`:
`make security-check`, a CodeQL C/C++ analysis of a warning-as-error build, and Trivy
`v0.70.0` over the direct-package root `make security-sbom` generates in
`bin/security/scanner-rootfs/`) runs on every push to `master`, and Dependabot
(`.github/dependabot.yml`) proposes action-pin and `site/` npm updates weekly. What is left
is the record and the policy:

- `docs/operations/SECURITY_BASELINE.md` still carries the 2026-08-27 result (19 resolved
  direct packages, one unfixed medium Git advisory `CVE-2024-52005`, no fixed HIGH or
  CRITICAL finding) and notes libcurl as unscanned.
- `docs/records/SECURITY-COMPLIANCE.md` still marks the container scan `STALE`, the source
  checks and action pins `PARTIAL` ("nothing proposes updates", "CodeQL last ran
  2026-08-27"), and the reporting process `PARTIAL`, and its scan paragraph says no hosted
  pipeline runs the scans.
- `SECURITY.md` promises fixes "in the current `1.81.x` line" (`VERSION` is `0.1.63` and was
  never `1.x`) and sends reporters to the private reporting form of `LuminariMUD/DurisMUD`,
  which now redirects to the community repository.

On 2026-10-08 the owner turned on, for `LuminariMUD/Duris`, private vulnerability reporting,
Dependabot security updates, and secret scanning with push protection.

**Checked** at `6e1b93cdb`, and on GitHub on 2026-10-08. `SECURITY.md` L5 and L10 name
`1.81.x`, L17 the form. `SECURITY_BASELINE.md` L72 records libcurl as added after the scan;
its "Local Commands" section (L6) is the local recipe. `SECURITY-COMPLIANCE.md` L102 and L119
to L122 carry the `PARTIAL` and `STALE` rows, L110 to L115 the scan paragraph. The
`security baseline` run at `02bdd8008` passed, and code scanning listed no open alert.

**Fix.** By decision 5: take the latest completed `security baseline` run on `master`, its
CodeQL result and its `trivy-results.json` artifact, and run `make security-sbom` locally to
see libcurl among the resolved direct packages (or record why it is not). Record the result
and its date in the baseline's result section, replacing the libcurl note, with one sentence
each on the workflow, on Dependabot, and on the repository settings turned on 2026-10-08.
Update the `PARTIAL` and `STALE` rows and the scan paragraph of `SECURITY-COMPLIANCE.md`.
Rewrite `SECURITY.md`: the `0.1.x` line, the private vulnerability reporting form of
`LuminariMUD/Duris`, no other repository named.

**Steps.**

1. The scan result, read and recorded.
2. The three documents; `tests/async/test_documentation_contract.py` and
   `tests/async/test_security_dependency_baseline.py` pass bare. Gate.

**Done when.**

- `SECURITY_BASELINE.md` records a scan dated after 2026-09-06 that covers libcurl, with its
  findings.
- `SECURITY-COMPLIANCE.md` no longer marks the scans `STALE` or the reporting process
  `PARTIAL`.
- `SECURITY.md` names the current version line and a reporting channel on this repository.
- How dependency updates are noticed is written down in one sentence.

## Phase 5: studio-proc tag ids and `world.trg`

**Built** on `fix/4-phase-5-studioproc` (stacked on Phase 4), 2026-10-08:

- `4827305a2`: `TAG_STUDIOPROC_TRIG` 2198, `_COOLDOWN` 2199 and `_COUNTER` 2200 end the
  `TAG_` list in `spells.h`; `SP_TAG_*` in `studioproc.h` alias them, beside a
  `static_assert(TAG_INFO_COOLDOWN < SP_TAG_TRIG && SP_TAG_COUNTER <= MAX_AFFECT_TYPES)`.
  `tests/async/test_studioproc_tag_ids.py` fails when any other `spells.h` define reaches
  2198 (checked with a stray `TAG_COLLIDES 2199`).
- `f31d8b14f`: `areas/src/trg/make_trg.c` (with its `Makefile`, in `areas/src` `SUBDIRS`)
  reads `trg/<area>.trg` for each area `areas/AREA` lists, checks the framing the engine
  reads (header, `T` ... `~`, `S`, no `#~`), appends it to `tworld.trg` and ends that with
  `#~`; `areas/make_all` runs it and `areas/moveall` makes it `world.trg`. The root
  `Makefile` lists the tool, `world.trg` and `tworld.trg`, and watches `areas/trg/`;
  `scripts/cycle_mud.sh` rebuilds the tools when `make_trg` is missing.
  `areas/trg/.gitkeep` keeps the directory. `tests/async/test_make_trg.py` builds the tool
  and runs a good source, an area without one, and six malformed ones;
  `test_clean_all.py` and `test_flatfile_launcher.py` know the new tool and outputs.
  `docs/content/STUDIOPROC.md`, `howto_trg.txt` and `docs/guides/BUILDING.md` describe the
  generated file. A real `make world` wrote `areas/world.trg` (`#~` only), and with a
  broken `areas/trg/limbo.trg` it failed: `error: trg/limbo.trg:4: a trigger is not ended
  by ~`.
- `b439fa892`: a "Connections before an account name, and the trusted proxy" section in
  `docs/testing/REGRESSIONS.md` for Phase 2's journey, which belonged in Phase 2 but is
  added here so the pushed branches below are not rewritten.

**What differs from the plan, and why.**

- The `static_assert` sits in `studioproc.h` beside the aliases, not in `spells.h`:
  `spells.h` does not see `MAX_AFFECT_TYPES`, and `studioproc.h` now includes `spells.h`.
  The test reads every numeric define in `spells.h`, not only `TAG_` ones: the list also
  holds `AIP_`, `ACH_`, `PR_` and `TYPE_` values in the same index space. As the plan
  read it, the build catches the ids leaving `skills[]` or the list passing them at its
  last entry, and the gate catches any other define taking one of their numbers.
- `make_trg` checks the framing only. A record's content (events, conditions, actions) is
  still checked by the engine at boot, which logs and skips a bad record; the docs say
  which fault fails where.
- With no source the generated file holds `#~` (the world target requires every output to
  be non-empty), so the boot line reads `STUDIOPROC: 0 records, 0 triggers, ...` rather
  than `no areas/world.trg`. No test pinned the old line.
- A failed generation leaves the `tworld.*` files the earlier tools wrote, as any failing
  generator already did; `make clean-all` removes them.

**Gate** on `b439fa892`: `./scripts/format.sh --all --check` clean (1038 files),
`make test-all -j16 TEST_JOBS=16` 678 passed, 0 failed, `make test-db` 48 of 48. This is
also the full gate for Phase 4's documents, which this tree contains. Nothing is left.

**Problem.** Two loose ends the studio-proc engine left on purpose, listed in
`docs/content/STUDIOPROC.md` under "Deliberately not included":

1. `src/mob/studioproc.h` takes `SP_TAG_TRIG` 2198, `SP_TAG_COOLDOWN` 2199 and
   `SP_TAG_COUNTER` 2200 from the unused top of the `skills[]` index space
   (`MAX_AFFECT_TYPES + 1` is 2201). The `TAG_` list in `src/magic/spells.h` knows nothing of
   them. If that list ever grows past 2197, a new tag and a studio-proc tag share a number
   and each silently reads the other's affects.
2. The engine reads `areas/world.trg` at boot, but nothing generates it: `areas/m_slow` and
   the `make_*` tools build `world.wld`, `.mob`, `.obj`, `.zon` and `.qst` from per-area
   sources, and there is no `areas/trg/` and no trigger step. A builder's triggers would live
   in one hand-edited file that `make world` neither produces nor checks. With no file the
   engine logs `STUDIOPROC: no areas/world.trg, proc engine idle.`

**Checked** at `6e1b93cdb`. `SP_TAG_*` are at `src/mob/studioproc.h` L154 to L156;
`TAG_INFO_COOLDOWN` 2126 (`src/magic/spells.h` L1256) is the last tag; `MAX_AFFECT_TYPES` is
`MAX_SKILLS + 200` = 2200 (`src/core/defines.h` L104). There is no `areas/trg/` and no
`areas/world.trg`. `areas/m_slow` is `make_all` then `make_lookup`; `make_all` runs the six
tools built from `areas/src/<type>/make_<type>.c`. The engine says its file framing mirrors
`world.qst` (`src/mob/studioproc.c` L28), so `make_qst.c` is the model. The build cannot see
a colliding `#define`, so "adding a `TAG_` that reaches 2198 fails the build" is met by a
`static_assert` on the sentinel plus a source contract that fails the gate; this section
records that reading when the phase lands.

**Fix.**

1. The three ids move to the end of the `TAG_` list in `spells.h` (`TAG_STUDIOPROC_TRIG`
   2198, `_COOLDOWN` 2199, `_COUNTER` 2200), the `SP_TAG_*` names alias them, and a
   `static_assert` pins them above `TAG_INFO_COOLDOWN` and below `MAX_AFFECT_TYPES + 1`.
   `tests/async/test_studioproc_tag_ids.py` parses every `#define TAG_` in `spells.h` and
   refuses any other value at or above 2198.
2. `areas/src/trg/make_trg.c`, modeled on `make_qst.c`: for each area in `areas/AREA` with
   an `areas/trg/<area>.trg`, check the framing the engine checks (zone, vnum, line) and
   append it to `areas/world.trg`; a malformed source exits nonzero naming the file and
   line, which fails `make world`. `make_all` runs it. `areas/world.trg` joins the generated
   outputs in `.gitignore`. A test runs the tool on a good and a malformed temporary source.
3. `docs/content/STUDIOPROC.md` and `docs/guides/BUILDING.md` describe the generated file.
   The full-world boot test's log line for the engine changes from "no areas/world.trg" to
   the loaded count once a source exists; until a builder adds one, the file is empty and
   the engine stays idle.

**Done when.**

- Adding a `TAG_` that reaches 2198 fails the build or the gate, as read above.
- `make world` writes `areas/world.trg` from tracked per-zone sources, and a malformed
  trigger fails generation with its zone and line.
- `docs/content/STUDIOPROC.md` and `docs/guides/BUILDING.md` describe the generated file.

## Phase 6: the site and the README's links

**Landed** 2026-10-08 on `master`, in the commit after `0cd8a4010`. What was built:

- The owner set the GitHub Pages source to GitHub Actions, and the `Project website` run for
  `0cd8a4010` deployed the site to `https://luminarimud.github.io/Duris/`.
- `README.md`: the documentation link goes to that site; the build badge, last-commit badge
  and commit link read `LuminariMUD/Duris`; the issues badge and link are gone; the
  critical-commands row describes the guide as it is now (the words of its
  `docs/README_docs.md` row).
- `site/build.mjs` and `site/test_site.py` default to `LuminariMUD/Duris`, so a local build
  links to this repository.
- `docs/guides/GITHUB_PAGES.md` says where the site is published and names the new default.

What differs from the plan: the phase went straight to `master` at the owner's request, with
no branch, pull request or review tags. The site catalog's summary of the critical-commands
guide ("transactions, journals, replay, and fences") was stale in the same way as the README
row and was corrected too. The steps below were not run as written; the checks were
`npm test --prefix site` (14 tests), `tests/async/test_documentation_contract.py` bare, and
the 32 tests that read `docs/` or the README, all passing, with no C/C++ change to gate. Nothing is left.
The build badge reports the `compile test` workflow, which was failing on `master` that day.

**Problem.** The website built from `site/` (a project hub from `site/catalog.json`: 30
guides rendered from `docs/`, the diagram gallery and the Power Atlas, described in
`docs/guides/GITHUB_PAGES.md`) is published nowhere, and several links lead to other
repositories:

1. `.github/workflows/pages.yml` ("Project website") runs on pushes to `master`, builds and
   tests the site, then fails at its `Configure Pages` step because GitHub Pages is not
   enabled for `LuminariMUD/Duris`. `README.md` instead invites readers to
   `https://luminarimud.github.io/Duris/`, the community tree's site with their
   documentation, not ours.
2. `site/build.mjs` and `site/test_site.py` take the repository from `GITHUB_REPOSITORY` and
   default to `LuminariMUD/Duris`, so every "View source" and "Edit on GitHub" link in a
   local build opens the community tree. In the workflow the variable is
   `LuminariMUD/Duris`, so a published build would link correctly.
3. `README.md` builds its build, last-commit and issues badges, and its commit and issue
   links, from `LuminariMUD/DurisMUD`, which GitHub now redirects to `LuminariMUD/Duris`.
   Its guide table describes critical commands as "journal, inbox/results, outbox, replay";
   nothing is journaled or replayed since ADR 0002.

**Checked** at `6e1b93cdb`, and on GitHub on 2026-10-08. `README.md` L416 links the
community site, L432 is the critical-commands row, L439 to L442 and L448 to L449 build the
badges and links from `LuminariMUD/DurisMUD`. `site/build.mjs` L12 and `site/test_site.py`
L13 hold the default. The `Project website` run at `7e08eae0b` built 30 guides and 2
diagrams, passed the site tests and failed at `Configure Pages`; the repository has no Pages
site.

**Fix.** By decision 7: once the owner sets the Pages source to GitHub Actions, the next
push to `master` publishes the site at `https://luminarimud.github.io/Duris/`.
`site/build.mjs` and `site/test_site.py` default to `LuminariMUD/Duris`. In `README.md` the
documentation link goes to that site; the build badge reports `build.yml` and the
last-commit badge and commit link read `LuminariMUD/Duris`; the issues badge and link go;
the critical-commands row is corrected. `docs/guides/GITHUB_PAGES.md` says where the site is
published.

**Steps.**

1. The site defaults; `npm test --prefix site`.
2. The README and the guide; `tests/async/test_documentation_contract.py` bare. Gate.
3. Once Pages is on and the phase has landed, open the README's documentation link once and
   see the site.

**Done when.**

- A reader following any link in `README.md` or in a built site page lands on this
  repository or its site, or the link is gone.
- Either the site is published from this repository and `docs/guides/GITHUB_PAGES.md` says
  where, or the decision not to publish is recorded there.
- `npm test --prefix site` passes with the new defaults.

## Phase 7: the quest EXP line and `achievements zones`

**Built** on `fix/4-phase-7-display-fixes` (stacked on Phase 5), 2026-10-08:

- The three community commits, cherry-picked with `-x` and their authors kept, all
  applying cleanly in order: `536ce6dba` (their `cf575ede6`, Liskin: one `Quest EXP:` line
  with the applied amount for `EXP_WORLD_QUEST`, and `tests/async/test_world_quest_xp_feedback.py`),
  `2e1984e9c` (their `5516cf284`, Liskin: `summary_for_at()` keeps only zones with a
  completed quest, sorted by count, name, zone number) and `3682944ca` (their `7b1405cfd`,
  xander-l: the sort's formatting and stronger cases in
  `tests/async/zone_story_quest_feature_harness.cpp`).
- `a69444da3`: their XP harness included `world/rested.h` and stubbed
  `has_active_rested_bonus()`, from their rested-XP feature; ours checks `TAG_WELLRESTED`
  and `TAG_RESTED` with `affected_by_spell()`, so the harness stubs that. Its cases, both
  branches of the first "Done when" item among them, pass on both backends.
- `82fc0184b`: ledger rows #697 and #594 `Adopted`.
- `8498aa0c1`: the `achievements` help entry in `lib/information/help_index` and
  `docs/reference/ZONE_STORY_QUEST_DAILY.md` say which zones the summary lists.

**What differs from the plan.** Only the harness fit above and the help text, which
their commits did not change.

**Gate** on `8498aa0c1`: `./scripts/format.sh --all --check` clean, `make test-all -j16
TEST_JOBS=16` 679 passed, 0 failed, `make test-db` 48 of 48. Nothing is left.

**Problem.** Two display fixes the community tree made after the split, found in the same
comparison as Phase 3. Neither changes a reward or a game mechanic.

1. `display_gain()` prints an `EXP:` line only for `EXP_KILL`. A player with the EXP display
   on sees a number for a kill and nothing for the XP a bartender quest gives. Their
   `cf575ede6` (four lines in `src/world/limits.c` plus a test) prints one `Quest EXP:` line
   when the display is on and XP was credited, and passes the applied amount
   (`after_exp - before_exp`), so the number is what the character gained after modifiers
   and caps. It changes `display_gain()` and its call in `gain_exp()`.
2. `summary_for_at()` adds every zone to the `achievements zones` summary, so the list
   includes zones where the player has completed nothing, and a zone with no name appears as
   "This area". Their `5516cf284` and `7b1405cfd` keep only zones with at least one
   completed quest, sorted by completed count, then name, then zone number.

**Checked** at `6e1b93cdb`. `display_gain()` prints only for `EXP_KILL`
(`src/world/limits.c` L915) and is called from `gain_exp()` at L1577. `summary_for_at()`
(`src/world/zone_story_quest_feature.c` L809) adds every zone, and an unnamed one reads
"This area" (L385).

**Fix.** By decision 8: the three community commits, fetched by URL as
`docs/records/COMMUNITY_DURIS_TRACKING.md` describes, and adapted where our files differ.

**Steps.**

1. The EXP line, with a harness test for both branches of the first "Done when" item.
2. The filter and the sort, with a test that pins them.
3. The ledger rows for the three commits. Gate.

**Done when.**

- With the EXP display on, a world-quest reward prints one `Quest EXP:` line with the applied
  amount, and prints none when nothing was credited. A test covers both.
- `achievements zones` lists only zones with a completed quest, most completed first. A test
  pins the filter and the order.

## Phase 8: specials named for vnums that are not in the world land on index 0

**Built** on `fix/4-phase-8-dead-specials` (stacked on Phase 7), 2026-10-08, in
`44345ebc9`:

- `tests/async/test_spec_assign_vnums.py` reads every live `real_object0(N)`,
  `real_mobile0(N)` and `real_room0(N)` with a numeric `N` in `specs.assign.c` (block and
  line comments blanked, `#if 0` blocks skipped, line numbers kept) and checks it against
  the `#N` lines of `areas/obj|mob|wld/<area>.*` for the areas `areas/AREA` lists. That
  reading gives the same 17,681 mobs, 19,150 objects and 253,261 rooms as the generated
  `world.*` files. Before the deletion it named 142 lines: exactly the 121 of the appendix
  below, and 21 more.
- The 142 lines are deleted, with the two continuation lines of the bridge troll's
  trailing comment and seven section headings left with nothing under them (Sylvandawn
  twice, fooquest, the pirate ship's `mobs` and `general jabbering`, Wilderness Near
  Verzanan, Troll Hills). 1,209 live assignments remain, all naming a vnum the world has.

**What differs from the plan, and why.**

- The 21 more are `mob_index[real_mobile0(N)].func.mob = 0;` lines for spec teachers that
  left the world (1500 to 1520, 200011, 200012, 200321, 210006), which the appendix's
  count left out because they assign no special. They wrote 0 over mob 1's special and
  are as dead as the rest, so they went too, and the contract covers every lookup.
- The special procedures only these lines named (the pirate ship's talkers, the outpost
  captains, `fooquest_*` and others) stay in the source. They were already unreachable
  except through index 0, and deleting them is outside decision 9.

**Gate** on `44345ebc9`: `./scripts/format.sh --all --check` clean, `make test-all -j16
TEST_JOBS=16` 680 passed, 0 failed, `make test-db` 48 of 48. Nothing is left.

**Review round 1** (PR #11, review of `12a728d74`; tag `backlog/phase-8-review-1`),
2026-10-09. Two findings, each fixed in its own commit, and two defects the fixes turned up:

- `b53795c3c`: 60 of the 142 deleted lines named content still in the world under a new
  vnum: its zone moved, and the same prototype sits in an area `areas/AREA` lists, with no
  special. Those lines are re-pointed instead of deleted. Black Pearl (142xxx) from
  `raxquest` and `fooquest`: Long John Silver, his parrot and dragon, ten pirate talkers,
  nine objects, fooquest's sage and illithid, 13 `newbie_quest` NPCs and the dragonslayer.
  Charing (45xxx) from Sylvandawn: Zilota and Nelanna (`world_quest`), nine guild guards,
  three city guards, the trail keeper, the dump and the Royal Stables. The City of Brass
  (139xxx) from `brass-old-2/3`: the iron golem, Latisia, the staff of blue flames and the
  ring of elemental control. And the AoD hall's inn, now 29812 in `cbl_hall`, which holds
  the whole hall at +310. Each pair was checked by diffing the two prototypes in full, and
  the section headings came back under the zones' current names. Four procs named the old
  numbers and move with them: `long_john_silver_shout`'s helpers and wraith,
  `fooquest_mob`'s illithid, `fooquest_boss`'s dragon and `ring_elemental_control`'s own
  object (every rub of the ring bailed). `docs/reference/artifact_source_inventory.json` is
  regenerated with it: the staff and the dragonslayer are artifacts, now with a binding.
  82 lines stay deleted: the 21 spec-teacher zeroes; three Sylvandawn lines whose Charing
  copy was already bound (45049, 45036, 45006); the 26 `outpost_captain` lines; room
  70501, whose copy 142201 is `ZONE_SHIP_ZONE_ENTRANCE`; and 31 whose content is nowhere in
  the listed world. The outpost captains stay deleted although `patrols` reuses map5's
  descriptions: those guards are not sentinel or stay-zone, load in rooms that open onto
  the surface map, and the captains are level 60 now, so the tower garrison proc, which
  hunts every racewar-evil player in its zone, would be new behaviour on them.
- `191a475eb`: `guild_guard` acts only in a room its switch names, and the switch still
  named Sylvandawn's and old Brass's rooms, so the re-pointed guards blocked nobody, nor
  did 45049, bound before this phase. Each Charing or Brass room joins the case of the room
  it replaces, with the same exit and class rule: 45126 (rogues, west), 45039 (warriors,
  south), 45145 (bards, north), 45063 and 45065 (the royal chambers, east), 45072 (the
  treasure, west), 139119 and 139125 (the temple, south). Charing's temple, 45027, opens
  east where Sylvandawn's opened west, so it joins 7588, the east-for-clerics case. The
  contract also checks now that every `guild_guard` mob a zone loads stands in a room the
  switch names; without these cases it names the eight guards.
- `2ae0ffe43` (an older defect that check found): `guild_guard` was bound to mob 16501,
  with a case for room 16501 and insignia 9316, all from a guild that left long ago.
  Woodseer has 165xx now, so the binding sat on its halfling street guard and the case on
  a stairway with no north exit. Both are gone.
- `db0525bc2`: the contract read numeric lookups one line at a time, 1,268 of the 1,293
  live ones, and missed the two clang-format had wrapped and the 18 named constants. It now
  reads the whole live source, resolves a name through the headers' `#define` lines, fails
  on any other name, and checks 1,288; the rest are the loop variables of three loops. A
  wrapped dead lookup, one through a header `#define`, and an undefined name each fail it.

The special procedures of the 82 deleted lines that nothing else names stay in the source,
as before.

**Checked** at `f44291043`. `real_room0()`, `real_mobile0()` and `real_object0()`
(`src/world/db.c` L4607, L4680, L4748) return 0 for a missing vnum; the comment at
L4531-4539 says this was done so `spec_ass.c` never indexes -1. `specs.assign.c` assigns
through them at about 1,500 sites with no check. Against the `world.*` files generated at the
2026-10-08 staging boot, with comments and `#if 0` blocks excluded, 17 object, 86 mobile and
18 room assignments name vnums that do not exist (the appendix below). The last in file order
wins: object 1 ("a silvery pendant in the shape of a skull", `areas/obj/Magetower.obj`) ends
with `staff_of_blue_flames` (L1971), mobile 1 ("mob", a placeholder) with `world_quest`
(L2214) and room 0 "The Void" with `inn` (L2462). Object 1 and mobile 1 are loaded by no zone
command and no `player_items` row holds object 1, so those two are dormant; room 0 is live.
The lookups cannot change: about sixty callers outside `specs.assign.c` compare their result
against 0 (`src/classes/mount.c` L652-657, `src/magic/smagic.c` L3037, and the rest).

**Fix.** By decision 9, no runtime guard. `tests/async/test_spec_assign_vnums.py` reads every
live `real_object0(N)`, `real_mobile0(N)` and `real_room0(N)` with a numeric `N` in
`specs.assign.c` (comments and `#if 0` blocks stripped; the few named constants and the loop
at L317 are outside its reach) and checks each against the `#N` lines of the area files
`areas/AREA` lists, `areas/obj/<area>.obj`, `areas/mob/<area>.mob` and
`areas/wld/<area>.wld`, which is what `make_all` concatenates into the generated files. The
121 dead lines are deleted. The alternative, a specs-local helper that skips and logs a miss,
means rewriting the 1,500 call sites into call form, since the `0` lookups' return cannot
move, and would log every one of these lines at each boot until the same pruning was done;
the contract gets the same protection from the gate alone.

**Steps.**

1. The test. Before any pruning it must name exactly the 121 lines in the appendix; a
   difference means an area the generator reads differently from the list, and the test
   follows the generator.
2. Delete the 121 lines; `make -C src`; the test passes bare. Gate.

**Appendix: the dead assignments** (`src/specs/specs.assign.c` lines at `f44291043`,
format `vnum→special (line)`).

Objects (17), all landing on object 1:
35102→magic_pool (L1287); 35103→magic_pool (L1288); 32507→shard_frozen_styx_water (L1455);
70549→circlet_of_light (L1501); 70554→ljs_sword (L1502); 70556→wuss_sword (L1503);
70558→head_guard_sword (L1504); 70559→priest_rudder (L1505); 70565→alch_bag (L1506);
70568→alch_rod (L1507); 70571→ljs_armor (L1508); 70572→dragon_skull_helm (L1509);
65050→dragonslayer (L1552); 4801→magic_pool (L1827); 4802→magic_pool (L1828);
25080→ring_elemental_control (L1965); 25103→staff_of_blue_flames (L1971).

Mobiles (86), all landing on mobile 1:
8028→cityguard (L374); 8034→cityguard (L375); 8047→cityguard (L376); 1919→bridge_troll (L416);
65012→fooquest_mob (L478); 65013→fooquest_boss (L479); 4070→piercer (L569);
4120→guild_guard (L570); 210004→undeadcont_track (L587); 210005→undeadcont_track (L588);
4812→poison (L622); 4830→wanderer (L623); 150115 to 150140→outpost_captain (L687 to L712,
26 lines); 8003→world_quest (L772); 8309→world_quest (L779); 8004→money_changer (L904);
8019→guild_guard (L905); 8029→guild_guard (L906); 8037→guild_guard (L907);
8039→guild_guard (L908); 8040→guild_guard (L909); 8041→guild_guard (L910);
8042→guild_guard (L911); 8044→janitor (L912); 8050→guild_guard (L913);
8311→guild_guard (L914); 8312→guild_guard (L915); 8313→guild_guard (L916);
14202→bridge_troll (L987); 25000→guild_guard (L1051); 25101→guild_guard (L1054);
25104→guild_guard (L1055); 150100→patrol_leader (L1212); 150101→patrol_leader_road (L1213);
65015, 65016, 65018, 65019, 65022, 65024, 65026, 65028, 65029, 65030, 65032, 65033,
65034→newbie_quest (L1228 to L1240, 13 lines); 70535→long_john_silver_shout (L1514);
70542→undead_parrot (L1515); 70546→undead_dragon_east (L1516);
70552→pirate_cabinboy_talk (L1519); 70554→pirate_female_talk (L1520); 70502, 70503, 70539,
70540, 70541, 70549, 70551, 70561→pirate_talk (L1521 to L1528); 87891→world_quest (L2214).

Rooms (18), all landing on room 0:
29605→inn (L296); 19890→GithyankiCave (L2294); 3398→inn (L2318); 66355→undead_inn (L2337);
43341→patrol_shops (L2340); 140854→ship_shop_proc (L2388); 258421→ship_shop_proc (L2389
and L2392); 70501→ship_shop_proc (L2391); 8010→pet_shops (L2435); 8211→dump (L2436);
8323→pet_shops (L2437); 8003→inn (L2438); 8287→ship_shop_proc (L2439); 29502→inn (L2456);
30511→inn (L2457); 29903→inn (L2459); 30303→inn (L2462).

## Phase 9: six `board` specials without a table row, and the audit's heading

**Checked** at `f44291043`. `board_info[]` (`src/cmd/boards.c` L55-103, `NUM_OF_BOARDS` 44
at L52) is what `find_board()` (L121) searches, so an object carrying the `board` special
without a row makes `look`, `read`, `examine`, `write` or `remove` near it log
`degenerate board!  (what the hell...)` (L199). `specs.assign.c` assigns `board` to nineteen
vnums (L1761-1776, L2102, L2103); six of them, 76, 86, 87, 42, 55026 and 55197, have no row.
`initialize_boards()` (L134) already assigns the special to every row (L162) and a board
whose file does not exist yet loads quietly (`Board_load_board()` L519), so none of the
nineteen lines is needed. Of the six, 42 is now "a dazzling pearl necklace"
(`areas/obj/dalvik.obj` L549) that `areas/zon/heavens.zon` L182 still loads into room 1196
"The Ideas Room" under the comment `* The board of IDEAS`; 55197 "a discussion board"
(`areas/obj/wh.obj` L2590) is loaded by `areas/zon/wh.zon` L559 into room 55612, the Immortal
Control Room of Winterhaven; 76, 86, 87 and 55026 are loaded by no zone command and held by
no character. The staging run before the restart logged the line six times, the last six
seconds after a level-62 login. Separately, `scripts/item_ownership_audit.sh` L65 still
prints `item loss: dropped at load, deleted at next save` over the orphan-payload count,
which the header comment at L10-14 says is not a loss.

**Fix.** By decision 10: delete the nineteen lines; add the 55197 row and raise
`NUM_OF_BOARDS` to 45; correct the zone comment at `heavens.zon` L182; reword the echo to
say what the header says.

**Steps.**

1. The deletion and the row. `tests/async/test_spec_assign_vnums.py` gains a check that
   `specs.assign.c` assigns `board` nowhere, so the table stays the one owner. In a local
   boot a wizard reads and writes the Winterhaven board; `logs/log/board` stays empty.
2. The zone comment and the echo. Gate.
