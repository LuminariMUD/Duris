# Plan: seven open fixes and the 2026-10-08 log review

Written 2026-10-08 against `master` at `6e1b93cdb`, after the clean-rebuild and fall fixes
landed (`2ce50bafb`). Rewritten the same day, after the move to GitHub, so that it stands
alone: each phase holds the problem, what was checked, the fix, the steps and when it is
done, and nothing here depends on an outside tracker. Phases 8 and 9 come from the log
review that followed the staging restart; the findings file that held them was deleted when
they were written here. The order and the decisions below are proposed; the owner locks or
changes them before Phase 1 starts. This file is a working note: delete it when the last
phase lands.

## Status

Updated 2026-10-08. A new session starts here, then reads the phase it continues.

| Phase | Subject | State |
|---|---|---|
| 1 | Hung tests and silent backup failures | Not started. |
| 2 | Unauthenticated connections per address | Not started. |
| 3 | Shop listing, dompurify, dead helpers | Not started. |
| 4 | Security record and `SECURITY.md` | Not started. |
| 5 | Studio-proc tag ids and `world.trg` | Not started. |
| 6 | Site and README links | Not started. |
| 7 | Quest EXP line and `achievements zones` | Not started. |
| 8 | Specials assigned to missing vnums | Not started. |
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

Decisions 9 and 10 were locked by the owner on 2026-10-08 as written below; Phases 8 and 9
have nothing left to decide. Decisions 5 and 7 were rewritten on 2026-10-08 for the move to
GitHub. Decisions 1 to 8 and 11 are still proposed.

| # | Decision | Where |
|---|---|---|
| 1 | A pooled test is ended after 900 s and a journey after 1800 s, by killing its process group; both are constants in the runner. A test ended that way, or by a signal, is a failure with its own label in the summary. A failure's output is printed when it happens, and every 60 s a line names the tests still running. | Phase 1 |
| 2 | A failed backup subprocess is reported with the command's basename, the phase, the exit status and the last 20 lines of its stderr (at most 2 KiB), with the database user, host and password replaced. | Phase 1 |
| 3 | At most 8 connections per address that have not entered an account name; the ninth is told so and closed, with one debug-log line, and nobody is banned. A connection silent at the account name prompt is closed after 120 s. Both are constants in `src/core/config.h`, documented in `CONFIGURATION.md`. The address is the one PROXY resolution yields. | Phase 2 |
| 4 | The listing is sent in pieces when the next line would not fit; dompurify is bumped by `npm audit fix --prefix site`; the two helpers are deleted. | Phase 3 |
| 5 | The scan of record is the `security baseline` workflow, which now runs on every push to `master`; Phase 4 records its latest completed run instead of replaying it, and runs only `make security-sbom` locally to see libcurl in the inventory. `SECURITY.md` names the `0.1.x` line and the private vulnerability reporting form of `LuminariMUD/Duris`, which the owner turns on in the repository settings (it is off). The baseline says in one sentence that Dependabot proposes action-pin and `site/` npm updates weekly. | Phase 4 |
| 6 | The three studio-proc ids are defined at the end of the `TAG_` list in `spells.h`, with a `static_assert` beside them and a source contract that no other `TAG_` reaches 2198. `world.trg` is built by `make_trg` from `areas/trg/<area>.trg`, run by `make_all`, and a malformed source fails `make world` with its file and line. | Phase 5 |
| 7 | The site is published by the existing `Project website` workflow once the owner sets the repository's GitHub Pages source to GitHub Actions; it then lives at `https://luminarimud.github.io/Duris/`. The site's repository default becomes `LuminariMUD/Duris`. The README's documentation link goes to that site; its build and last-commit badges and its commit link go to `LuminariMUD/Duris`; the issues badge and link go, since work is not tracked in issues. If the owner decides not to publish, the deploy job leaves `pages.yml`, the README link goes, and `docs/guides/GITHUB_PAGES.md` records that the site is a local build. | Phase 6 |
| 8 | The two display fixes are taken from the community tree with the author kept where a commit applies, adapted otherwise. | Phase 7 |
| 9 | The vnums `specs.assign.c` names are checked by a source contract against the area files `areas/AREA` lists, not at run time: the 121 assignments to vnums no longer in the world are deleted, and the test fails the gate when a new one appears or an area leaves the list. The `0` lookups keep returning 0 on a miss; about sixty callers outside `specs.assign.c` compare their result against 0. | Phase 8 |
| 10 | The nineteen explicit `board` assignments in `specs.assign.c` go; `initialize_boards()` assigns the special to every table row itself. 55197, the discussion board loaded into Winterhaven's Immortal Control Room, gets a `board_info` row at AVATAR for read, write and remove, file `lib/boards/winterhaven`. 87 and 55026 are loaded by no zone and stay plain objects. Room 1196 keeps the necklace; the zone comment that still calls it a board is corrected. | Phase 9 |
| 11 | The phases are done in the order below. | All |

## Order

By cost of leaving it: the gate every later phase runs (Phase 1), then the one exposure
(Phase 2: a silent client can hold every login slot for 15 minutes), a latent stack overflow
and a known advisory (Phase 3), a security record and policy that are out of date (Phase 4),
an id collision waiting to happen and triggers in a hand-edited file (Phase 5), links that
send readers to other repositories (Phase 6), then two display gaps (Phase 7). The
log-review phases come last: an assignment to index 0 that no loaded object or mob reaches
today, though room 0 does carry `inn` (Phase 8), then a logged warning and a stale heading
(Phase 9).

Things to keep in mind across phases:

- **Phases 8 and 9** both edit `src/specs/specs.assign.c`; Phase 9's nineteen lines are among
  the ones Phase 8's contract reads, so land 8 first.
- **Phase 2** edits `src/net/comm.c`, which `tests/async/test_boot_log_hygiene.py` pins in
  places; read its contracts before moving anything there.
- **Phases 3 and 6** both touch `site/`; run `npm test --prefix site` in both.
- **Phases 4 and 6** both edit README-level documents.
  `tests/async/test_documentation_contract.py` pins README strings and checks every
  maintained Markdown link; run it bare.
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
- A document the phase edits loses any link it still has to an outside tracker for the same
  work; this file is the record.
- The phase's section is brought up to date in the same branch: what was built, what differs
  from the plan and why, the gate's result, and what is left.

---

## Phase 1: a hung test holds the gate, a failed backup says one word

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
  2026-08-27"), and the reporting process `PARTIAL`.
- `SECURITY.md` promises fixes "in the current `1.81.x` line" (`VERSION` is `0.1.63` and was
  never `1.x`) and sends reporters to the private reporting form of `LuminariMUD/DurisMUD`,
  which now redirects to the community repository. Private vulnerability reporting is off on
  `LuminariMUD/Duris`.

**Checked** at `6e1b93cdb`, and on GitHub on 2026-10-08. `SECURITY.md` L5 and L10 name
`1.81.x`, L17 the form. `SECURITY_BASELINE.md` L72 records libcurl as added after the scan;
its "Local Commands" section (L6) is the local recipe. `SECURITY-COMPLIANCE.md` L102 and L119
to L122 carry the `PARTIAL` and `STALE` rows. The `security baseline` run at `02bdd8008`
passed, and code scanning listed no open alert.

**Fix.** By decision 5: take the latest completed `security baseline` run on `master`, its
CodeQL result and its `trivy-results.json` artifact, and run `make security-sbom` locally to
see libcurl among the resolved direct packages (or record why it is not). Record the result
and its date in the baseline's result section, replacing the libcurl note, with one sentence
each on the workflow and on Dependabot. Update the `PARTIAL` and `STALE` rows of
`SECURITY-COMPLIANCE.md`. Rewrite `SECURITY.md`: the `0.1.x` line, the private vulnerability
reporting form of `LuminariMUD/Duris`, no other repository named.

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

**Problem.** The website built from `site/` (a project hub from `site/catalog.json`: 30
guides rendered from `docs/`, the diagram gallery and the Power Atlas, described in
`docs/guides/GITHUB_PAGES.md`) is published nowhere, and several links lead to other
repositories:

1. `.github/workflows/pages.yml` ("Project website") runs on pushes to `master`, builds and
   tests the site, then fails at its `Configure Pages` step because GitHub Pages is not
   enabled for `LuminariMUD/Duris`. `README.md` instead invites readers to
   `https://community-duris.github.io/Duris/`, the community tree's site with their
   documentation, not ours.
2. `site/build.mjs` and `site/test_site.py` take the repository from `GITHUB_REPOSITORY` and
   default to `Community-Duris/Duris`, so every "View source" and "Edit on GitHub" link in a
   local build opens the community tree. In the workflow the variable is
   `LuminariMUD/Duris`, so a published build would link correctly.
3. `README.md` builds its build, last-commit and issues badges, and its commit and issue
   links, from `LuminariMUD/DurisMUD`, which GitHub now redirects to `Community-Duris/Duris`.
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
