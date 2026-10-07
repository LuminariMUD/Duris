# Community-Duris tracking

Our line (`gitlab.com/max757/duris`) and
[Community-Duris/Duris](https://github.com/Community-Duris/Duris) on GitHub share one history up
to 2026-09-23 and have been developed separately since. This file records where the split is,
every change they have landed since, sorted into bug fixes and everything else, and what we did
with each one.

**Checked through (2026-10-04):** their `master` at `f45d71acc`, their
`experimental-accounting` at `f7d26eaa7`, their unmerged branches at the heads listed in
[Their unmerged branches](#their-unmerged-branches), our `master` at `0d6a772b9`.
[Updating this file](#updating-this-file) has the commands for the next check.

## The split

| | Commit | When (UTC) |
|---|---|---|
| Last commit on both `master` branches | `e1357a30a`, the merge of their PR #626 (nexus portal targeting), tagged `staging-2026-09-23-1622` | 2026-09-23 16:19 |
| Our first commit after it | `d86a642ad` | 2026-09-24 22:10 |
| Their first `master` commit after it | `7755d95cd`, the merge of their PR #660 | 2026-10-01 03:10 |

Size of each line since the split, as of the check above:

| Line | Commits | Files changed | Lines |
|---|---|---|---|
| Our `master` | 414 (394 without merges) | 945 | +45,897 / -110,258 |
| Their `master` | 99 (56 without merges) | 237 | +15,816 / -1,886 |
| Their `experimental-accounting` | 441 more than their `master` | 1,667 | +431,488 / -88,194 |

Three PR branches are on both sides. Our `master` took them on 2026-09-26 in `2209da668`, the
merge of `consolidate/persistence-prs`, at the heads they had then. They merged the same
branches a week later, two of them with extra commits:

| Their PR | Head in our history | What they added later |
|---|---|---|
| #601 boon completion capacity | `004598b0e` | Nothing |
| #573 atomic crafting | `a1fe27a42` | 3 commits |
| #596 stale coin authority | `c3e9ce470` | 2 commits |

This is why `git merge-base --all` prints four commits for the two `master` branches.
`e1357a30a` is the split; the other three are those branch heads.

### The two lines went opposite ways on persistence

- **Ours** made memory the authority again
  ([ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md)). Migration
  `0034_retire_death_custody_and_accounting` dropped the death custody, restitution and economy
  accounting tables, and the code that waited on them went with it.
- **Theirs** kept that model and extends it. Their `master` adds operator tooling on top of
  custody and restitution, and `experimental-accounting` adds economy accounting.

Three things follow for every row below:

- A fix of theirs to custody, restitution, accounting or the coin-transfer command layer has
  nothing to apply to here. Those rows are `N/A`.
- Migration numbers collide from `0031` on (their `0031_player_item_runtime_state`, our
  `0031_economy_accounting`). Never cherry-pick one of their migrations.
- Shared files have drifted, so a change we take is usually rewritten for our code (`Adapted`)
  rather than cherry-picked (`Adopted`).

## Reading the tables

Each branch has three tables: bug fixes, changes that are not bugs (balance, features, content,
performance), and housekeeping (tests, CI, dependencies, operator tooling). A PR that mixes
classes is split into lettered parts, one per row. PR numbers are theirs:
`https://github.com/Community-Duris/Duris/pull/<number>`. Dates are merge dates in UTC. Their
unmerged branches share one set of the same three tables, with a row keyed by branch.

**Our line** says what our tree has: whether the defect is there, or why the change has nothing
to apply to. Once a row is decided, it names our commit or the reason.

**Status** is one of:

| Status | Meaning |
|---|---|
| `Open` | Not decided or not done yet. Our line names the work item once there is one. |
| `Adopted` | Their commits taken as they are. Our line names the commit. |
| `Adapted` | The same change written for our code. Our line names the commit. |
| `Rejected` | Decided against. Our line gives the reason. |
| `Ours first` | We had already fixed it. Our line names the commit. |
| `Shared` | The same commits are in our history. |
| `N/A` | It changes code our line removed or never had. |

## Their master

### Bug fixes

| PR | Merged | What they fixed | Our line | Status |
|---|---|---|---|---|
| #660 (a) | 10-01 | A raised, player-owned pet could wear a hidden (`!show`) NPC helper weapon it inherited and fire its procs (their issue #590). | `374c8a518` (2026-10-04): a raised corpse's items are on the raised creature again, and `wear()` refuses a hidden item for a player's pet, so `wear`, `wield` and `hold` by keyword skip it as `wear all` did. | `Adapted` |
| #660 (b) | 10-01 | A scheduled backup interrupted after publishing was never completed. Adds automatic `finalize` (off by default) and a retry throttle (their issue #525). | `scripts/persistence_backup.py` was reworked here from 2026-10-01 to 2026-10-03 (11 commits, `2f2c0f405` to `a6741ccf9`). Whether that covers the same interruption is not verified. | `Open` |
| #601 | 10-01 | A boon reward result (2,080 bytes) overflowed the 2,048-byte critical-completion buffer. | `004598b0e` is in our history and the 4,096-byte limit is in our tree. | `Shared` |
| #594 | 10-01 | `achievements zones` listed zones with no completed quests, some as "This area". Now only zones with a completed quest are listed, highest count first. | Not in ours: `summary_for_at` in `src/world/zone_story_quest_feature.c` still lists every zone. Work item [#8](https://gitlab.com/max757/duris/-/work_items/8). | `Open` |
| #573 (a) | 10-01 | Poison mixing, Encrust and Harvester exchanges could consume inputs twice or reroll results across a crash. Made atomic through database craft receipts (their issue #551). | We merged the earlier head, then our persistence reset removed the craft-receipt layer. Their 3 later commits build on it. | `N/A` |
| #573 (b) | 10-01 | Saving a staff account wrote the immortal menu category over the character's own racewar. | `6e4934ab0` (2026-09-29). | `Ours first` |
| #573 (c) | 10-01 | Copyover restored a session's account under the character's name. | `9a4c3bcfd` (2026-09-30). | `Ours first` |
| #573 (d) | 10-01 | Copyover exec kept the old process's Redis world-writer lease, so the new process could not claim it. | `a9e6e391d` (2026-10-04): a copyover releases the lease before its exec and the image it starts claims it at boot; the lease is 60 seconds and the game loop renews it. | `Adapted` |
| #671 | 10-02 | `artifact fixit` freed its display object, then read and freed it again. | `00efb191f` (2026-09-30). | `Ours first` |
| #596 | 10-02 | A coin transfer that committed after a disconnect left stale wallet and bank revisions on the retained character (their issue #505). | We merged the earlier head, then our reset removed the coin-transfer command layer (`src/economy/coin_transfer_command.c`) that their 2 later commits patch. | `N/A` |
| #694 | 10-03 | `chaos platinum` printed success before the wallet credit was confirmed. | Same code in ours (`do_chaos` in `src/combat/chaos.c`). Not verified that a credit can still fail after submission in our currency path. | `Open` |
| #700 (b) | 10-03 | Shop `list` could overflow its output buffer. | Latent in ours: the listing loop in `src/economy/shop.c` appends without a bound into a 65,536-byte buffer, which takes about 700 priced items on one keeper. Work item [#9](https://gitlab.com/max757/duris/-/work_items/9). | `Open` |
| #700 (c) | 10-03 | An unterminated quote overflowed the stack in the new quantity parser. | The parser is new in #700 (a); ours does not have it. | `N/A` |
| #702 | 10-03 | GMCP `Room.Info` updates were dropped when more than 500 rooms changed between flushes, and room indexes were used without a bounds check. | Present: `gmcp_mark_room_dirty` and `gmcp_flush_dirty_rooms` in `src/net/gmcp.c` are unchanged since the split. | `Open` |

### Not bugs

| PR | Merged | Class | What they changed | Our line | Status |
|---|---|---|---|---|---|
| #663 | 10-01 | Balance | NPC alchemists attack with paced class abilities, about a third as often as a sorcerer of the same level, instead of stocking and using real potions. No bottles drop. A fresh zone spawn has a 10% chance to carry one poison-mixing vial (their issue #661). | Not in ours. | `Open` |
| #573 (e) | 10-01 | Balance | Player potion mixing (`mix`) removed as unsupported. Poison mixing stays. | Ours keeps `do_mix`. | `Open` |
| #595 | 10-01 | Content | Cleric pets refuse orders with authored lines for their patron, read from `lib/misc/divine_refusal.json`. Pilot for Garl (vnums 66026, 66031), switched off by default (their issue #278). | Ours has part 1, the refusal decision ([DIVINE_REFUSAL.md](../reference/DIVINE_REFUSAL.md)), not the authored content. | `Open` |
| #522 | 10-01 | Feature | `exp.rested.enabled` (default on) turns the rested XP bonus off for the whole server. Staff spell-ups still grant it. | Not in ours. | `Open` |
| #511 | 10-01 | Performance | Ordinary NPC activity is throttled in regions with no player nearby. Off by default on their `master`, on by default on `experimental-accounting` (their issue #299). | Not in ours. | `Open` |
| #697 | 10-03 | Feature | A separate `Quest EXP` line shows the experience a quest reward actually added (their issue #598). | Not in ours. Work item [#8](https://gitlab.com/max757/duris/-/work_items/8). | `Open` |
| #700 (a) | 10-03 | Feature | `buy <item> quantity <1-50> [into <container>]` for produced stock, with markers in `list` and one summary per batch (their issue #539). | Not in ours. Work item [#16](https://gitlab.com/max757/duris/-/work_items/16). | `Open` |

### Housekeeping

| PR | Merged | Class | What they changed | Our line | Status |
|---|---|---|---|---|---|
| #659 | 10-01 | Dependencies | `codeql-action` 4.38.1 to 4.38.2. | Our line has no hosted pipeline. | `N/A` |
| #662 | 10-01 | Dependencies | `dompurify` 3.4.15 to 3.4.16 in `site/`. | Ours is at 3.4.15. Work item [#9](https://gitlab.com/max757/duris/-/work_items/9). | `Open` |
| #444 | 10-01 | Tests | The auction journey builds its inspector per run instead of in the shared `bin/tests/` path, where parallel runs overwrote it. | `tests/async/test_flatfile_auction_coin_put_journey.py` still uses the shared `bin/tests/coin-death-inspector`. | `Open` |
| #591 | 10-01 | Tests | Telemetry SQL round trips on MySQL 8.4 and MariaDB 11.4 as a required CI job (their issue #564). | Its harness and test changes are `38c59e6fe` (2026-10-07): the `telemetry_repository` leg of `make test-db` on the wrapper's MariaDB, taking `TEST_DB_*`. Their container wrapper, loopback proxy and hosted job are not. | `Adapted` |
| #677 | 10-02 | Operations | Telemetry follow-up acceptance runbook and a read-only preflight script. | Not taken (decision 10 of the plan that landed Phase 5, !15): the writer's own startup check covers what the preflight script checked, and the runbook paragraph on the `telemetry_health` line is ours. | `Open` |
| #671 (b) | 10-02 | Build | Executable bit on their migration `0031` verifier, and link repairs in item-transfer test harnesses. | Their migration and their harness changes. | `N/A` |
| #700 (d) | 10-03 | Build | Initialised variables for GCC 12 `maybe-uninitialized` warnings in four files. | Warnings from their GCC 12 build. Not checked against ours. | `Open` |
| #695 | 10-03 | Operations | Reports and status queries for death-recovery custody (their issue #570). | Built on death custody, which migration `0034` dropped. | `N/A` |
| #704 | 10-03 | Operations | Offline repair for a custody row whose item payload is missing (their issue #526). | Built on the restitution tooling and receipt tables that migration `0034` dropped. | `N/A` |

## Their experimental-accounting branch

Their second line, active since 2026-09-28. It last took their `master` at `4f9f41dd7`; later
`master` PRs arrive as separate "Port ..." PRs (#665, #666, #669, #674, #696, #698, #699, #701,
#705), which are the rows above and are not repeated here. Nothing below is on their `master`
yet. Their player-facing summary of the whole period is `lib/information/news` on this branch.

### Bug fixes

| PR | Merged | What they fixed | Our line | Status |
|---|---|---|---|---|
| #679 | 10-02 | Race, class and specialization help showed stale captured tables instead of live game data. | Not checked. | `Open` |
| #691 | 10-03 | A fragmented Telnet subnegotiation frame reached command processing before its terminator arrived, and a doubled IAC inside a frame ended it early. | Not checked. | `Open` |
| Direct commits | 10-01 | Arithmetic and ordering in enhancement, Craft, Forge and salvage: overflowing or negative enhancement prices, level-gate overflow, payment and material checked before equipment changes, salvage outputs checked before the item is consumed (`2e5852e41`, `2ccef37af`, `49f76401c`, `7360003fa`, `cfb42c8ec`, `a2c560b9d`, `5017a0e9e`, `8f9f624f7`, `c5ea78c95`, `d4af6fac3`). | Not checked. | `Open` |

### Not bugs

| PR | Merged | Class | What they changed | Our line | Status |
|---|---|---|---|---|---|
| #597 | 10-03 | Balance | Minor Globe, Spirit Ward, Greater Spirit Ward and Globe have a finite capacity that wears down with time and absorbed damage. Recasting restores a ward; equipment wards renew on a schedule. `score` shows them (their issue #453). | Not in ours. | `Open` |
| #703 | 10-04 | Balance | A resisted Dispel Magic still shortens each timed spell by 10% of its remaining duration and wears down wards and barriers. Also changes dispel handling of portals. | Not in ours. | `Open` |
| #679 (b) | 10-02 | Feature | `help index [category] [page]` and suggestions for mistyped topics. | Not in ours. | `Open` |
| #692 | 10-03 | Feature | An opt-in supervisor process keeps playing sessions connected across a copyover exec. | Not in ours. | `Open` |
| #684 | 10-03 | Performance | Account lookup at login moved off the game thread. | Not checked. | `Open` |
| #689 | 10-03 | Performance | Sockets are serviced between pulses instead of once per 250 ms pulse. Connection cap of 256. | Not checked. | `Open` |
| #690 | 10-03 | Performance | Character maintenance is scheduled per character on the timer wheel instead of a sweep of every character every 5 seconds. | Not checked. | `Open` |
| #687 | 10-03 | Performance | Live characters are looked up by runtime ID through a hash map instead of a list walk. | Not checked. | `Open` |
| #686 | 10-03 | Hardening | Per-session limits on queued commands (64 KiB, 256 entries) and queued output (1 MiB, 1,024 entries). | Not checked. | `Open` |
| #688 | 10-03 | Engine | Copyover file written with explicit little-endian fields and a CRC instead of native structures. | Not checked. | `Open` |
| #706 | 10-04 | Performance | World activity throttling (#511) turned on by default. | Follows #511. | `Open` |
| #708 | 10-04 | Content | Player news through October 3. | Their news file. | `N/A` |

### Housekeeping

| PR | Merged | Class | What they changed | Our line | Status |
|---|---|---|---|---|---|
| #685 | 10-03 | Operations | An external observer detects and recovers a stalled world loop. | Not checked. | `Open` |
| #680, #681 | 10-02, 10-03 | Tests | Audit of test execution, redundant runs removed. | Their suite. | `N/A` |
| #667, #668, #670, #673, #676, #682, #693 and about 150 direct commits | 09-28 to 10-04 | Accounting | Economy accounting, custody, quarantine recovery and their fixtures. Includes the news item "fixed item turn-ins and NPC item rewards for static quests" (`e92a5424b`), a fix to accounting reward claims. | Our line dropped accounting and custody (migration `0034`). | `N/A` |

## Their unmerged branches

Work that sits on a branch and is on neither their `master` nor `experimental-accounting`. Sizes
are against the branch each one targets. A row moves into the tables above when its branch
merges.

| Branch | Their PR | Targets | Commits | Size | Head checked |
|---|---|---|---|---|---|
| `codex/discovered-zone-dailies` | #678 | `experimental-accounting` | 80 | 304 files, +211,693 / -4,389 | `6c25eeb3b` |
| `codex/telemetry-balance-expansion` | #683 (draft) | `experimental-accounting` | 37 | 199 files, +47,952 / -692 | `c861086df` |
| `codex/accounting-plan5` | None | `experimental-accounting` | 17 | 35 files, +8,544 / -62 | `7a78bb065` |
| `codex/artifact-control` | #508 (draft) | `master` | 2 | 52 files, +7,307 / -58 | `05200680e` |
| `feat/epic-levelling-reform` on Faemill's fork | #658 (draft) | `master` | 7 | 43 files, +1,528 / -121 | `52dc6e4e0` |
| `codex/craft-forge-recovery` | #675 | `experimental-accounting` | 16 | 16 files, +652 / -151 | `696c5eb52` |
| `codex/issue-664-historical-reconciliation` | #707 (draft) | `experimental-accounting` | 1 | 2 files, +160 / -3 | `473b36fad` |

`codex/player-news-2026-10-03` has nothing left; it merged as #708.

Most of the zone-dailies branch is data and documents: 81 story files (64,763 lines), the
generated quest catalog (about 100,000 lines) and 60 per-zone design documents with 60 audits.
Its source change is 3,338 added lines in 31 files. It also carries ten fixes to mob procedures
and room files that have nothing to do with the feature; those are the first four rows below.
The branch was still being pushed to during this check.

### Bug fixes

| Branch | What they fixed | Our line | Status |
|---|---|---|---|
| Zone dailies, `7297b964e` | Sin in the Hall of the Ancients checked Freedom of Movement on the procedure's actor argument, which is null on periodic calls, instead of on its opponent. Its room message printed `&N` instead of the target's name. | Present: `hoa_sin` in `src/specs/specs.hoa.c` is the same code. Their commit applies to our `master` cleanly. | `Open` |
| Zone dailies, `b28262d8c` and `348eccdf3` | The Halfcut Hills crossbow ambusher never fired in play: it attacked during the set-up call and declined the periodic ones. It also kept shooting a target that had died or left, and the struck player never saw the warning line. | Present: `crossbow_ambusher` in `src/specs/specs.halfcut.c` is the same code. The two commits apply cleanly in order. | `Open` |
| Zone dailies, six commits | Fifteen room descriptions named the wrong exit direction: Desolate (2, `b1ff082bc`), Moonhollow in the Rift Valley Jungle (5, `f5d5b2a5c`), Tempest Court (2, `dc586e34c`), Tribal Forest (3, `f8090481d`), Ironstar (2, `b07b560cc`) and Brass (1, `d18758098`). | Present: our six `.wld` files are identical to theirs before the fixes. All six commits apply cleanly. | `Open` |
| Zone dailies, `3f1ecf2be` | Tower of Darkness: two room descriptions named the wrong direction, and four door keyword lists ended in a stray `&n` colour code, which their commit says broke the magic passwords. | Present: our `areas/wld/lortower.wld` is identical to theirs before the fix. The commit applies cleanly. | `Open` |
| Zone dailies, design documents | Found, not fixed: 58 of the 60 per-zone documents under `docs/design/zone-stories/` list pending repairs to quests, rewards and access in the shared world files. | The world files are ours too. One checked: `areas/qst/halfcut.qst` rewards item 25000, which no object file defines. The rest is not checked. | `Open` |
| Telemetry, `e0e837102`, `03da1882d`, `b3fb28b9f` | The telemetry writer started without checking the live schema and its permissions (their issue #561). Queued observations were lost across a restart or copyover with no record of the gap (their issue #566). Sessions were not recovered after a deferred start or a capacity refusal. | Taken as `f7368e60e`, `476376592` and `95cf073c7` (2026-10-07), without their `IMPLEMENTATION_STATUS.md`, `RECOVERED_FOLLOWUPS.md`, `BALANCE_EXPANSION_PLAN.md` and `preflight.py`. On top: the transport carries the repository's refusal cause and a `schema_check` to the operator line (`ce09d17bc`), and `run_telemetry_schema_boot_journey.py` proves the checks and the ledger on a running server. Work item [#17](https://gitlab.com/max757/duris/-/work_items/17). | `Adopted` |
| Craft and Forge recovery, #675 | A Craft or Forge interrupted between the item commit and the player save lost its progression. | Built on the database craft receipts and command coordinator that our persistence reset removed. | `N/A` |
| Accounting plan 5, `c3a948594`, `87424d5a7`, `7a78bb065` | Wrong or missing rows in the accounting audit views. | Our line dropped accounting (migration `0034`). | `N/A` |

### Not bugs

| Branch | Class | What they changed | Our line | Status |
|---|---|---|---|---|
| Zone dailies, #678 | Feature and content | Zone journals and dailies for areas a character has visited: `quest zone <area>`, `quest daily <area>`, `achievements zone <area>`. Visiting an area unlocks its journal and meeting an NPC reveals its requests. The first qualifying daily each day adds 1 renown. 81 authored story files in `areas/story/`, covering all 27 starter and town areas. Switched off unless economy accounting is active. | Ours has the zone-story quests and `quest daily`, not the journals or the story files. Their engine side depends on accounting, which ours dropped; the story files are plain data. | `Open` |
| Epic levelling reform, #658 | Balance | Levels 51 to 56 by experience alone, with a per-level experience table. Epic points are banked only from level 56, paid as experience below it and forfeited when a character drops below it. Epic skills cost 5 times their base instead of 3. Artifact feeding from everything but PvP is cut to about an eighth (zone 0.15 to 0.02) and can lift a timer no higher than 72 hours. New staff command `artifeed`. | Not in ours (`exp.maxExpLevel` is 50). The branch starts at the split commit; a trial merge into our `master` conflicts in 6 files. | `Open` |
| Artifact control, #508 | Feature | One catalog, `lib/artifacts/catalog.json`, sets each artifact's variant and each power's chance, cooldown, wind-up, mana cost and level. Staff change it through `scripts/artifactctl.py` and an admin command. Legacy behaviour stays the default. Needs their migration `0029_artifact_control`. | Not in ours. A trial merge conflicts in 13 files, mostly migration manifests and tests. | `Open` |
| Telemetry, #683 | Operations | Records battle data for balance work: who took part in a shared battle and what each contributed, combat builds, and blindness, stun and status-control spells that landed. Adds 14 migrations. | Not in ours. | `Open` |

### Housekeeping

| Branch | Class | What they changed | Our line | Status |
|---|---|---|---|---|
| Zone dailies, #678 | Tools and tests | Builder guide `docs/guides/ZONE_STORY_BUILDING.md`, zone inventory and coverage scripts, and tests for the ten fixes above. | Follows the journals and the fixes. | `Open` |
| Accounting plan 5 | Accounting | Read-only audit and provenance queries, and checks that refuse a restore with incomplete accounting evidence. | Our line dropped accounting (migration `0034`). | `N/A` |
| Historical reconciliation, #707 | Operations | A report on 25 quarantined-save cases from their staging server. | About their server's data; nothing to apply here. | `N/A` |

## Updating this file

Fetch their branches. This needs no configured remote. A PR from someone's fork, such as #658,
has no branch in their repository and is fetched by its number:

```sh
git fetch --no-tags https://github.com/Community-Duris/Duris \
	'+refs/heads/*:refs/remotes/community/*' \
	'+refs/pull/658/head:refs/remotes/community/pr-658'
```

List what merged since the last check, using the commits from **Checked through**:

```sh
git log --first-parent --reverse --format='%h %cs %s' f45d71acc..community/master
git log --first-parent --reverse --format='%h %cs %s' f7d26eaa7..community/experimental-accounting
```

Look at one merge, and test whether a commit of theirs is already in ours:

```sh
git diff --stat <merge>^1 <merge>
git merge-base --is-ancestor <commit> origin/master && echo shared
```

List their branches with unmerged work, see what one holds, and try one of its commits on our
`master` without changing anything (exit status 0 means it applies cleanly):

```sh
git branch -r --list 'community/*' --no-merged community/experimental-accounting
git log --oneline community/experimental-accounting..community/<branch>
git merge-tree --write-tree --merge-base=<commit>^ origin/master <commit>
```

A PR's description and linked issue come from the public API, and their player news shows what
they told players:

```sh
curl -s https://api.github.com/repos/Community-Duris/Duris/pulls/<number>
git diff f7d26eaa7 community/experimental-accounting -- lib/information/news
```

For each new merge, add a row to the right table: bug fix or not, what it changes, and what our
tree has. For an unmerged branch, update its head and its rows the same way. When a row is
decided, set its status and put our commit or the reason in **Our line**. Then move **Checked
through** to the new commits and refresh the size table:

```sh
git rev-list --count e1357a30a..origin/master
git diff --shortstat e1357a30a origin/master
```
