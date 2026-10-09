# Test quality: seven additions that keep the gate's time

Written 2026-10-09 against `master` at `d6fe4c210`. It proposes seven additions that raise
what the tests prove without making `make test-all` or `make test-db` slower: anything slow
runs outside the gate. The numbers below were counted on that commit. The order and the
decisions are proposed; the owner locks or changes them before the first item starts. This
file is a working note: delete it when the last item lands.

## Where the suite stands

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

## Status

| Item | Subject | Gate time | State |
|---|---|---|---|
| 1 | Prove a regression test fails without its fix | none | Proposed |
| 2 | Make tests break only when behaviour breaks | same or less | Proposed |
| 3 | Fuzz the code that reads outside input | one replay test | Proposed |
| 4 | `clang-tidy` on changed lines | none (commit hook) | Proposed |
| 5 | Keep a history of test runs | none | Proposed |
| 6 | Mutation testing, by hand | none | Proposed |
| 7 | Line coverage, on demand | none (by hand) | Proposed |

Suggested order: 1, 2 and 5 first, because they are cheap and address the breakages already
seen; then 4; then 3 and 6, which look for bugs nobody has reported. Item 7 depends on
nothing and can land at any point.

Proposed decisions:

- Item 1 reports; it does not block a landing.
- Item 4's hook refuses a commit with a new finding on a changed line, as the format hook does.
- Item 3's long runs are by hand; no scheduled workflow.
- Item 7 runs only when a developer asks for it, and its percentage is never a target.

## 1. Prove a regression test fails without its fix

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

It reports and does not block: a test reshaped by a refactor passes on `BASE` and is still
right. The reviewer reads the report; the landing commit message records it.

**Steps.** Write the script. Check it on a fix, such as `932421560` (a board file kept whole
across a failed save), whose `test_boards.py` must fail on the parent, and on a refactor
commit, whose test passes. Add a paragraph to "Before a
merge" in `docs/guides/TESTING.md`.

**Done when** the script exists, it reports both checks correctly, and `TESTING.md` says
when to run it.

## 2. Make tests break only when behaviour breaks

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

## 3. Fuzz the code that reads outside input

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
`LLVMFuzzerTestOneInput` and the shared stubs from item 2. `make fuzz FUZZ_TARGET=<name>
FUZZ_SECONDS=<n>` builds it with `clang -fsanitize=fuzzer,address,undefined` under
`bin/fuzz/` and runs it. Useful inputs and every crash go into
`tests/fuzz/corpus/<target>/` as small committed files. The gate gets one test,
`tests/async/test_fuzz_corpus.py`, which builds each target with `g++`, the sanitizers and a
small `main` that feeds every corpus file once: no fuzzing engine, and seconds of run time
after the compile. Long runs are by hand.

**Done when** the first three targets exist, each has run for an hour, every finding is
fixed in its own commit with its input in the corpus, and the replay test runs in
`make test`.

## 4. `clang-tidy` on changed lines

**Problem.** The warnings are strict and CodeQL runs in CI, but nothing checks for bug
patterns compilers do not warn on: use after `std::move`, `sizeof` of a pointer, a
suspicious string compare, an ignored failure return, a narrowing comparison.

**The change.** A root `.clang-tidy` with `bugprone-*` and a few `cert-*` and
`performance-*` checks. `scripts/tidy.sh` works like `scripts/format.sh`: it checks changed
lines only (through `clang-tidy-diff`), and `--check` only verifies. The `.c` files are
C++20, so the script passes `-x c++ -std=c++20` and the include paths from `src/Makefile`;
no compile database exists, so the script writes one from those flags. The hook in
`scripts/git-hooks/` runs it after the format check.

**Steps.** Run it once over all of `src/` first. Fix each real bug it finds in its own
commit, and turn off each noisy check in `.clang-tidy` with the reason beside it. Then add
it to the hook.

**Done when** `.clang-tidy` and `scripts/tidy.sh` exist, the first full run's real findings
are fixed, and the hook runs it.

## 5. Keep a history of test runs

**Problem.** The runner prints each test's result and time, then forgets them. A journey
that fails now and then is found one red run at a time (the four journey fixes listed
above, all since 2026-10-01), and a test that slowly gets slower is noticed only when the
gate runs late.

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

## 6. Mutation testing, by hand

**Problem.** Nothing measures whether the tests catch bugs. A coverage number (item 7) says
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

## 7. Line coverage, on demand

**Problem.** Nothing shows which code no test reaches. Item 6 scores only the tests that
name a file, and journeys reach most of the server without naming anything, so a function
that no harness and no journey ever runs looks the same as one that both run.

**The change.** `make coverage` runs `scripts/coverage.sh`, and nothing else runs it: it is
never part of `test-all`, `test-db` or the commit hook. One command does the whole run:

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
