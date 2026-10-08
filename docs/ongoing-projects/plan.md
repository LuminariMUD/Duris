# Plan: work items #22, #12, #9, #21, #28, #25 and #8, and the 2026-10-08 log review

Written 2026-10-08 against `master` at `6e1b93cdb`, after the clean-rebuild and fall fixes
landed (!16). One phase per work item. Phases 8 and 9 were added the same day from the log
review that followed the staging restart; they have no work item, and the findings file
that held them was deleted when they were written here. The order and the decisions below
are proposed; the owner locks or changes them before Phase 1 starts. This file is a working
note: delete it when the last phase lands.

## Status

Updated 2026-10-08. A new session starts here, then reads the phase it continues.

| Phase | Item | State |
|---|---|---|
| 1 | #22 | Not started. |
| 2 | #12 | Not started. |
| 3 | #9 | Not started. |
| 4 | #21 | Not started. |
| 5 | #28 | Not started. |
| 6 | #25 | Not started. |
| 7 | #8 | Not started. |
| 8 | log review | Not started. |
| 9 | log review | Not started. |

## Why these seven

Fifteen work items are open. These seven are defects, exposures or wrong pointers, each a
bounded change with a gate and a regression test. Phases 8 and 9 are the three open rows of
the log review after the 2026-10-08 staging restart: a latent defect, a logged warning and a
stale heading. The other eight work items are not in this plan:

| Item | Why not here |
|---|---|
| [#20](https://gitlab.com/max757/duris/-/work_items/20) | A retention and disclosure policy is the owner's decision; no engineering until it is made. |
| [#19](https://gitlab.com/max757/duris/-/work_items/19) | Needs a run-or-retire decision and a representative clone the repository does not have. |
| [#15](https://gitlab.com/max757/duris/-/work_items/15) | Needs four answers from the builder and a re-exported sheet; the builder called it not critical. |
| [#24](https://gitlab.com/max757/duris/-/work_items/24) | Its own fix direction asks for observation data from a test server before any curve is designed. |
| [#16](https://gitlab.com/max757/duris/-/work_items/16) | A usability feature larger than any phase here; it follows Phase 3, which bounds the listing it extends. |
| [#26](https://gitlab.com/max757/duris/-/work_items/26) | A rollup and a report for a subsystem that ships off; #17 landed, so it is ready, but it is feature work. |
| [#23](https://gitlab.com/max757/duris/-/work_items/23), [#27](https://gitlab.com/max757/duris/-/work_items/27) | Coverage work, each several journeys and (#27) a sanitizer build; the material of the plan after this one. |

## Are the items still valid?

All seven are. Every code claim in them was read again at `6e1b93cdb`; the line numbers
below are from that commit. None is closed, duplicated by another item or covered by an open
merge request.

| Phase | Item | Verdict | What the check added or corrected |
|---|---|---|---|
| 1 | [#22](https://gitlab.com/max757/duris/-/work_items/22) Hung test, one-word backup failure | Valid, accurate | `run_test()` (`tests/run_regression_tests.py` L84) has no timeout and `main()` prints failures only after both loops (L187). The backup tool drops stderr at two sites, `run()` (L390) and `streaming_process()` (L364); the second already has a 300 s deadline and a process-group kill, which is the shape the runner needs. `failure()` (L60) drops the message on purpose because the command line names the database user and host. |
| 2 | [#12](https://gitlab.com/max757/duris/-/work_items/12) No per-address limit before login | Valid, accurate | Lines moved: `MAX_CONNECTIONS` (`src/core/config.h` L125), `avail_descs` (`src/net/comm.c` L2424), `bannedsite()` called at L3869, the 3600-pulse idle default at L1846 and a 2400-pulse case for the creation states at L1834. `new_descriptor()` resolves the PROXY header from `DURIS_TRUSTED_PROXY_IP` (L3508, L3764) before the ban check, so a count by resolved address already tells players behind the proxy apart. Since !16 the `Losing descriptor without char` line is in `logs/log/debug` (noted on the item). |
| 3 | [#9](https://gitlab.com/max757/duris/-/work_items/9) Shop listing, dompurify, dead helpers | Valid, accurate | `shopping_list()` (`src/economy/shop.c` L1676) appends `Gbuf4` to the stack buffer `Gbuf1` (L1604) with `strcat()` at L1796, unchecked. dompurify 3.4.15 (`site/package-lock.json` L1380). `got_all_ingredients()` (`src/classes/salchemist.c` L550) and `extract_used_ingredients()` (L666) have no caller outside their file. |
| 4 | [#21](https://gitlab.com/max757/duris/-/work_items/21) Scans stale, SECURITY.md wrong | Valid, accurate | `SECURITY.md` L5 and L10 name `1.81.x`, L17 the GitHub form; `VERSION` is `0.1.63`. `docs/operations/SECURITY_BASELINE.md` L72 records libcurl as added after the scan, and L6 "Local Commands" is the replay recipe. `docs/records/SECURITY-COMPLIANCE.md` L102 and L119 to L122 carry the `PARTIAL` and `STALE` rows. |
| 5 | [#28](https://gitlab.com/max757/duris/-/work_items/28) Studio-proc ids, `world.trg` | Valid, accurate | `SP_TAG_*` 2198 to 2200 at `src/mob/studioproc.h` L154 to L156; `TAG_INFO_COOLDOWN` 2126 (`src/magic/spells.h` L1256) is the last tag; `MAX_AFFECT_TYPES` is `MAX_SKILLS + 200` = 2200 (`src/core/defines.h` L104). No `areas/trg/` and no `areas/world.trg`. `areas/m_slow` is `make_all` then `make_lookup`; `make_all` runs the six tools built from `areas/src/<type>/make_<type>.c`. The engine says its file framing mirrors `world.qst` (`src/mob/studioproc.c` L28), so `make_qst.c` is the model. |
| 6 | [#25](https://gitlab.com/max757/duris/-/work_items/25) Site unpublished, links elsewhere | Valid, accurate | `README.md` L416 links the community site, L439 to L442 build badges from `LuminariMUD/DurisMUD`; `site/build.mjs` L12 and `site/test_site.py` L13 default to `Community-Duris/Duris`. |
| 7 | [#8](https://gitlab.com/max757/duris/-/work_items/8) Quest EXP line, empty zones | Valid, accurate | `display_gain()` prints only for `EXP_KILL` (`src/world/limits.c` L915); `summary_for_at()` (`src/world/zone_story_quest_feature.c` L809) adds every zone and an unnamed one reads "This area" (L385). |

## Decisions (proposed)

Decisions 9 and 10 were locked by the owner on 2026-10-08 as written below; Phases 8 and 9
have nothing left to decide. Decisions 1 to 8 and 11 are still proposed.

| # | Decision | Where |
|---|---|---|
| 1 | A pooled test is ended after 900 s and a journey after 1800 s, by killing its process group; both are constants in the runner. A test ended that way, or by a signal, is a failure with its own label in the summary. A failure's output is printed when it happens, and every 60 s a line names the tests still running. | Phase 1 |
| 2 | A failed backup subprocess is reported with the command's basename, the phase, the exit status and the last 20 lines of its stderr (at most 2 KiB), with the database user, host and password replaced. | Phase 1 |
| 3 | At most 8 connections per address that have not entered an account name; the ninth is told so and closed, with one debug-log line, and nobody is banned. A connection silent at the account name prompt is closed after 120 s. Both are constants in `src/core/config.h`, documented in `CONFIGURATION.md`. The address is the one PROXY resolution yields. | Phase 2 |
| 4 | The listing is sent in pieces when the next line would not fit; dompurify is bumped by `npm audit fix --prefix site`; the two helpers are deleted. | Phase 3 |
| 5 | The SBOM, the source checks and Trivy run locally as the baseline's recipe says. CodeQL runs only if its CLI can be fetched; otherwise the baseline says so. `SECURITY.md` names the `0.1.x` line and a confidential work item on `max757/duris` as the channel. Dependency updates are noticed when the scans are rerun, and the baseline says so in one sentence. | Phase 4 |
| 6 | The three studio-proc ids are defined at the end of the `TAG_` list in `spells.h`, with a `static_assert` beside them and a source contract that no other `TAG_` reaches 2198. `world.trg` is built by `make_trg` from `areas/trg/<area>.trg`, run by `make_all`, and a malformed source fails `make world` with its file and line. | Phase 5 |
| 7 | The site is not published for now, and `docs/guides/GITHUB_PAGES.md` records that. Every README and site link goes to `gitlab.com/max757/duris`; the build badge goes; the commit and issue badges use shields.io's GitLab endpoints. | Phase 6 |
| 8 | The two display fixes are taken from the community tree with the author kept where a commit applies, adapted otherwise, as Phase 5 of the last plan did. | Phase 7 |
| 9 | The vnums `specs.assign.c` names are checked by a source contract against the area files `areas/AREA` lists, not at run time: the 121 assignments to vnums no longer in the world are deleted, and the test fails the gate when a new one appears or an area leaves the list. The `0` lookups keep returning 0 on a miss; about sixty callers outside `specs.assign.c` compare their result against 0. | Phase 8 |
| 10 | The nineteen explicit `board` assignments in `specs.assign.c` go; `initialize_boards()` assigns the special to every table row itself. 55197, the discussion board loaded into Winterhaven's Immortal Control Room, gets a `board_info` row at AVATAR for read, write and remove, file `lib/boards/winterhaven`. 87 and 55026 are loaded by no zone and stay plain objects. Room 1196 keeps the necklace; the zone comment that still calls it a board is corrected. | Phase 9 |
| 11 | The phases are done in the order below. | All |

## Order

By cost of leaving it: the gate every later phase runs (#22), then the one exposure (#12: a
silent client can hold every login slot for 15 minutes), a latent stack overflow and a
known advisory (#9), scans that have not run since 2026-08-27 (#21), an id collision waiting
to happen and triggers in a hand-edited file (#28), links that send readers to other
repositories (#25), then two display gaps (#8). The log-review phases come last: an
assignment to index 0 that no loaded object or mob reaches today, though room 0 does carry
`inn` (Phase 8), then a logged warning and a stale heading (Phase 9).

Things to keep in mind across phases:

- **Phases 8 and 9** both edit `src/specs/specs.assign.c`; Phase 9's nineteen lines are among
  the ones Phase 8's contract reads, so land 8 first.
- **#12** edits `src/net/comm.c`, which `tests/async/test_boot_log_hygiene.py` pins in
  places; read its contracts before moving anything there.
- **#9 and #25** both touch `site/`; run `npm test --prefix site` in both.
- **#21 and #25** both edit README-level documents. `tests/async/test_documentation_contract.py`
  pins README strings and checks every maintained Markdown link; run it bare.
- **#9's** listing bound is what #16 (not in this plan) builds on.

## Every phase

- One branch and one merge request per phase, closing its work item.
- `./scripts/format.sh --check`, `make -C src`, the phase's focused tests, then one run of
  `make test-all` and `make test-db` before it lands.
- A regression test for each behaviour that changes, as the item's done-when asks.
- The head a review reads is tagged `backlog/phase-<n>-review-<round>`, rounds from 0, and
  the tag is pushed with the branch.
- A phase starts from `master`, is reviewed on its merge request, and lands as a `--no-ff`
  merge of the last reviewed head, with the landing recorded in this file's Status table.
- The phase's section is brought up to date in the same branch: what was built, what differs
  from the plan and why, the gate's result, and what is left.

---

## Phase 1: a hung test holds the gate, a failed backup says one word (#22)

**Checked.** `run_test()` runs each test with `subprocess.run()` and no deadline, and holds
its output until it exits. `main()` runs the pool, then the 15 journeys in
`RESOURCE_INTENSIVE_TEST_NAMES` side by side, and prints every failure's output after both.
Nothing says what is still running. In the backup tool, `run()` and `streaming_process()`
send stderr to `/dev/null`; the second kills the process group at 300 s; `require()` raises
`BackupError(code)` and `main()` prints one JSON record, so a failure is the word
`subprocess_failed` and nothing else.

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
2. The backup change, with a case in `tests/async/test_persistence_backup.py` where a subprocess fails with
   stderr naming the user and host, and the record carries the phase, exit status and tail
   without either.
3. `docs/guides/TESTING.md` and `docs/operations/BACKUPS.md` describe the deadline and the
   record. Gate.

## Phase 2: unauthenticated connections per address (#12)

**Checked.** `new_descriptor()` accepts up to `MAX_CONNECTIONS` descriptors in all, resolves
the client address through the PROXY header when the peer is `DURIS_TRUSTED_PROXY_IP`, and
applies only the ban list. The idle switch closes a descriptor at the account name prompt
after 3600 pulses (15 minutes); creation states get 2400.

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

## Phase 3: the shop listing, dompurify, two dead helpers (#9)

**Checked.** As the item says, at the lines in the validity table.

**Fix.** In `shopping_list()`, before each `strcat()`, send `Gbuf1` and start it again when
the next line would not fit; the trailing "Nothing!" path is unchanged. `npm audit fix
--prefix site`, then `npm test --prefix site`. Delete the two helpers; `get_bottle()` and
`get_id_for()` stay, our tree calls them.

**Steps.**

1. The listing bound, with a harness test that lists a keeper carrying 700 items and
   receives every line in order.
2. The lockfile bump; `npm audit --prefix site` reports nothing.
3. The deletion; `make -C src` clean. Gate.

## Phase 4: the security scans and `SECURITY.md` (#21)

**Checked.** As the item says, at the lines in the validity table. The replay recipe is the
"Local Commands" section of `docs/operations/SECURITY_BASELINE.md`.

**Fix.** Run `make security-sbom`, `make security-check` and Trivy `v0.70.0` against
`bin/security/scanner-rootfs/` as `security.yml` does; CodeQL by decision 5. Record the
result and its date in `SECURITY_BASELINE.md`, with libcurl in the inventory. Update the
`PARTIAL` and `STALE` rows of `docs/records/SECURITY-COMPLIANCE.md`. Rewrite `SECURITY.md`:
the `0.1.x` line, a confidential work item on `max757/duris` as the channel, no other
repository named.

**Steps.**

1. The scans, recorded.
2. The three documents; `tests/async/test_documentation_contract.py` and
   `tests/async/test_security_dependency_baseline.py` pass bare. Gate.

## Phase 5: studio-proc tag ids and `world.trg` (#28)

**Checked.** As the item says, at the lines in the validity table. The build cannot see a
colliding `#define`, so the item's "fails the build" is met by a `static_assert` on the
sentinel plus a source contract that fails the gate; that reading is recorded under the
item when the phase lands.

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

## Phase 6: the site and the README's links (#25)

**Checked.** As the item says, at the lines in the validity table.

**Fix.** By decision 7: `site/build.mjs` and `site/test_site.py` take the forge and
repository from one setting defaulting to `gitlab.com/max757/duris`, build GitLab blob and
edit links, and the edit action is renamed. `README.md` links commits and issues on GitLab,
drops the build badge, and corrects the critical-commands row. `docs/guides/GITHUB_PAGES.md`
records that the site is a local build.

**Steps.**

1. The site change; `npm test --prefix site`.
2. The README and the guide; `tests/async/test_documentation_contract.py` bare. Gate.

## Phase 7: the quest EXP line and `achievements zones` (#8)

**Checked.** As the item says, at the lines in the validity table.

**Fix.** By decision 8: the community's `cf575ede6` (one `Quest EXP:` line with the applied
amount when the display is on and XP was credited) and `5516cf284` plus `7b1405cfd` (only
zones with a completed quest, sorted by completed count, name, zone number), fetched by URL
as `docs/records/COMMUNITY_DURIS_TRACKING.md` describes, and adapted where our files differ.

**Steps.**

1. The EXP line, with a harness test for both branches of the done-when.
2. The filter and the sort, with a test that pins them.
3. The ledger rows for the three commits. Gate.

## Phase 8: specials named for vnums that are not in the world land on index 0 (log review)

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

## Phase 9: six `board` specials without a table row, and the audit's heading (log review)

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
