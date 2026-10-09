# Plan: the 2026-10-09 log review's fixes, seven test-quality additions and MariaDB 11.8

Written 2026-10-09 against `master` at `24e7d3fba`. It holds the open work of two working
notes it replaces: the 2026-10-09 log review (Part 1, items 1 to 9) and the test-quality
proposals (Part 2, items 10 to 16). Both notes were deleted when their work was written here;
their last versions are at `24e7d3fba`, where
`docs/ongoing-projects/log-review-2026-10-09.md` also records what the review read and what
it found expected or benign. Part 3 (item 17) was added the same day: the staging host's
upgrade to MariaDB 11.8, found during the tick and boot investigation, stops a new database
from being built. Each item holds the problem, the evidence, the change and when it is done. The order and the decisions are proposed; the owner locks or changes them before
the first item starts. This file is a working note: delete it when the last item lands.

Kept apart, in their own working notes:

- [tick-and-boot-performance.md](tick-and-boot-performance.md): the review's two
  performance findings, the slow tick and the slower boot, each an investigation.
- [staging-host-follow-ups.md](staging-host-follow-ups.md): the host owner's work left
  from the review and the host's 26.04 upgrade (SSH, a GitHub token, backups).

[ADR 0003](../adr/0003-player-privacy-chat-snoop-addresses.md) is the decision record for
items 3, 8 and 9.

## Status

Part 1, the log review's fixes:

| # | Item | Severity | State |
|---|---|---|---|
| 1 | `server_reboots` records one of ten restarts: a service stop kills the launcher before it writes | Low | Open |
| 2 | Plain HTTP requests to `ws.duris.sbs` reach the MUD's WebSocket port and get a tunnel error | Low | Open |
| 3 | `lib/etc/hosts` keeps every client's address and reverse-DNS name, and nothing prunes it | Low | Open (part of ADR 0003) |
| 4 | Nine shops ask for a buy rate the loader clamps at every boot | Low | Open, data |
| 5 | `logs/boot.log` is stale since 2026-10-04 and nothing writes it | Low | Open |
| 6 | `cmd.debug` never records a one-letter command, and records stale text for an empty line | Low | Open |
| 7 | Wizard broadcasts go into `status` raw, a lost peer's host is a color code, and zone-command lines print internal indices | Low | Open |
| 8 | `snoop` never tells its target, and nothing ages out players' addresses | Low | Decided (ADR 0003); code pending |
| 9 | Any immortal can read a player's last 200 private messages with `recall` | Medium | Decided: disable; code pending |

Part 2, test quality:

| # | Item | Gate time | State |
|---|---|---|---|
| 10 | Prove a regression test fails without its fix | none | Proposed |
| 11 | Make tests break only when behaviour breaks | same or less | Proposed |
| 12 | Fuzz the code that reads outside input | one replay test | Proposed |
| 13 | `clang-tidy` on changed lines | none (commit hook) | Proposed |
| 14 | Keep a history of test runs | none | Proposed |
| 15 | Mutation testing, by hand | none | Proposed |
| 16 | Line coverage, on demand | none (by hand) | Proposed |

Part 3, database engine support:

| # | Item | Severity | State |
|---|---|---|---|
| 17 | A new database cannot be built on MariaDB 11.8: migrations 0031 and 0032 know only MariaDB 10.11 and MySQL 8.0 | Medium | Open |

## Order (proposed)

The two parts touch different files and can go side by side.

- **Part 1:** 9 first, the one Medium item, decided and small; then 8 with 3, the rest of
  ADR 0003's code; then 6, which loses the moves before a crash; then 1, 2, 7, 4 and 5.
- **Part 2:** 10, 11 and 14 first, because they are cheap and address the breakages already
  seen; then 13; then 12 and 15, which look for bugs nobody has reported. 16 depends on
  nothing and can land at any point. 12 uses 11's shared stubs, so 11 comes first.
- **Part 3:** 17 touches only the migration runner, the manifest, two new verifier files and
  a test leg, so it can go beside either part. It has to land before a database is next built
  on staging, and before production moves to Ubuntu 26.04.

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

### 4. Nine shops ask for a buy rate the loader clamps

**Problem.** At every boot the shop loader caps a buy rate above 0.8 and logs `Shop #N: Old
buy/sell` (`src/economy/shop.c` L2383-2424) for shops 31310, 47061, 47070, 47097, 47116, 59081
and 59097 (1.0 to 0.8), and 89091 and 89118 (0.9 to 0.8). The 09:01 boot logs the same nine.

**The change.** Set those rates to 0.8 in the shop files under `areas/shp/`, so that the boot
log carries nothing.

**Done when** a boot logs no `Old buy/sell` line.

### 5. `logs/boot.log` is stale

**Problem.** `logs/boot.log` is dated 2026-10-04 22:05. Nothing in `scripts/` or `src/` writes
it, and the boot's stderr goes to the journal. It shows 15 `Recalculating zone numbers`
warnings ("Heaven has invalid number: 1 (should be 0)" and others). Neither the 03:50 boot
nor the 09:01 boot prints them, so the file misleads anyone who reads it.

**The change.** Delete it (decision 2), or have the launcher write the boot's stderr there.

**Done when** no `logs/boot.log` older than the last boot is left on the host.

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
