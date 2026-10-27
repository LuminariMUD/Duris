# Watchable racewar group battle runner — lean first version

Status: implementation in progress; tracked in [GitHub issue #405](https://github.com/LuminariMUD/Duris/issues/405).
Updated: 2026-10-27. Full-party provisioning and gear/spell preparation are in
review. Native targeting, input receipts and targeted stop are the next chunk;
the operator CLI, combat loop and full-battle acceptance remain outstanding.
Dedicated branch: [branch/issue-405-racewar-battle-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-405-racewar-battle-plan).
The issue and implementation PRs link here; partial PRs must not automatically close #405.
Source baseline: [master at f0264a484](https://github.com/LuminariMUD/Duris/commit/f0264a48452dbf3dc76079e59eaf85b99ecdeff9).

## Outcome and scope

Prepare two full, geared groups of **real mortal player characters**, place them
in a chosen room, and drive a watchable fight through their normal game
connections. The purpose is to put strain on the real game and expose bugs,
including interactions between player combat, groups, equipment, spells, output,
death, and persistence.

The user explicitly retained real characters when offered NPC teams. Keep the
normal player input queue, lag, casting, resource use, and death paths. No NPC
stand-ins, training dummies, staff-forced combat loop, or direct calls to damage
functions. Implementation was authorized after the plan was published.

The three non-negotiable deliverables are:

- Two full geared parties on opposing good/evil racewar sides. Read the running
  server's independent caps; the checked-in properties currently specify
  **20 versus 20**. Do not substitute a small demonstration fight.
- Actual combat that someone can watch by logging in with a normal client.
- A configurable battlefield VNUM, defaulting to the controlling staff
  character's current room when preparation begins.

Also retain the agreed absence of environment restrictions: no test-server,
localhost, hostname, `ENVIRONMENT`, `TEST_MUD`, or Chaos-mode gate. Use existing
staff authority and ordinary room rules; the operator chooses the setup.

## What makes this version smaller

Keep the diverse fixed roster below and its existing Chaos gear. Use a simple
level-56 baseline, maximum eligible ordinary skills, the existing compatible
unspecialized epic grant, full caster books, and a small ready spell loadout.
There is no specialization-selection engine or perfect endgame-build optimizer.

Use **two or three useful active choices per character**, chosen from a few
shared role routines. Ordinary melee, passive skills, racial traits, and equipment
procs continue naturally. Prepare only the spells those choices need. The
characters can possess a broader toolkit without automating every part of it.

Defer automatic rematches/reset, corpse recovery and re-gearing, pet control,
specialization coverage, active racial-ability coverage, bench/ability rotation,
cross-room pursuit, crash-resume machinery, a general action DSL, dashboards,
and detailed damage/healing attribution. Keep a reliable stop and basic evidence.

This removes automation work, not players from the fight. It tests fewer active
ability combinations than the original plan, and does not claim exhaustive
skill/spell/pet coverage. Pets and more actions can be added after a useful
full-group baseline exists.

## Source anchors

- [Group admission](../../src/guild/group.c) enforces consent, sides, leadership,
  and caps. [GMCP](../../src/net/gmcp.c), `gmcp_send_group_status()`, exposes
  `maxSize`, member HP, rank, and room presence. The checked-in
  [properties](../../lib/duris.properties) set both caps to 20; 13 is the fallback.
- [Chaos kit preparation](../../src/account/nanny.c) already handles class/race
  equipment, unavailable body slots, unarmed classes, and item ownership grants.
  Existing `chaos kit <character>` requires an empty online mortal; existing
  `chaos kitbag <class> <race>` supplies the same kit to staff.
  [High-level staff access](../../src/combat/chaos.c) does not require enabling
  Chaos globally. Wait for grant completion before issuing wear commands.
- [Memorization](../../src/classes/memorize.c) supplies the master-book contents,
  class/circle eligibility, and finite preparation limits. Master spellbook VNUM
  7 is defined in [defines.h](../../src/core/defines.h). A full book is not an
  unlimited supply of prepared casts.
- [Epic skills](../../src/classes/epic_skills.c) already provide
  `grant_epic_skills_without_specialization()`, including prerequisites and
  exclusions. Reuse it on the unspecialized baseline.
- [Accounts](../../src/account/account.c) disconnect duplicate logins to the
  same account. Each simultaneously connected combatant therefore needs its own
  account. [newchar](../../src/account/wiz_newchar.c) attaches a character to the
  invoking account and is not a solution for 40 simultaneous clients.
- [The combat journey](../../tests/async/test_flatfile_combat_journey.py) already
  automates account/character creation and normal combat/death connections.
  [The Paladin journey](../../tests/async/run_paladin_balance_journey.py) already
  drives multiple clients and groups. Reuse those patterns without their fixed
  passwords, localhost-only connection assumptions, or fixture-state edits.
- [Visible target lookup](../../src/world/handler.c), `get_char_room_vis()`,
  uses race keywords/ordinals for most opposing PCs. Their real names appearing
  in GMCP does not make those names legal mortal command targets.
- [Staff commands](../../src/cmd/actwiz.c) provide advancement, restoration,
  transfer, and targeted tranquilize. Restoring skills only restores taught
  values; tranquilize alone does not prove that a pending spell has stopped.

These are inspected source facts. The proposed runner still needs runtime proof.

## Implementation: one script and a small preparation helper

### 1. Connect and create the full parties

Use one Python process with concurrent normal player connections and a staff
control connection. Read the host/port and staff login from explicit configuration;
keep secrets outside source, command-line arguments, and gameplay transcripts.
The human observer uses a separate account to avoid displacing the controller.

Automate creation of the missing dedicated accounts and characters through the
existing registration flow. A supplied set of existing dedicated accounts can be
reused. Do not turn account provisioning into 40 manual chores or modify ordinary
account admission rules. Handle the selected setup's normal confirmation prompts;
report any unresolved admission step instead of calling a partial group ready.

Log in the two leaders first and obtain the actual caps. Preserve the captured
default room before moving staff. Fill each side independently from the fixed
roster; for a smaller cap, retain frontline, healing, and damage roles. For a
larger cap, repeat legal baseline builds. Validate server creation availability
and report any necessary substitutions instead of enabling races/classes globally.

Use fresh character identities for a fresh match. This avoids an automatic
restore/recovery subsystem. Reuse accounts where practical, respecting their
existing character capacity. Keep a simple untracked run record of the exact
accounts/characters created and their results. Earlier characters and corpses
retain ordinary game persistence; there is no automatic wipe, account deletion,
or claim that the match rolls back the world. A full account is an explicit
provisioning condition, not a reason to overwrite an earlier character.

### 2. Prepare a consistent geared baseline

A small staff helper should do only the missing per-character setup:

- Advance through the existing progression path to the mortal cap, currently 56.
  Use a documented base-stat profile of 100 before normal racial/equipment
  calculations and recalculate normal resources. Do not inflate HP to prolong fights.
- Keep characters unspecialized; maximize eligible ordinary skills/spells to their
  actual ceilings, then use the existing compatible unspecialized epic grant.
- Reconcile only the newly created character's starting items, grant the existing
  Chaos kit, and verify usable equipment is worn, including weapons and unusual
  racial slots. Use the server's selected kit profile without changing its mode.
- Supply the master book to book casters and finish only valid queued
  memorize/pray preparation for the short action list, within circle capacity.
  Restore the appropriate mana/slot resources for other caster models.

Use existing commands for gear grants, transfers, consent, grouping, and ranks.
Use ordinary commands for a small selection of pre-fight buffs. Restore the
agreed starting resources once before combat. No refills during the fight.

The helper may also expose the narrow stop operation described below. It is not
a second combat engine or a new control service, and needs no schema migration.

### 3. Place, inspect, and start

Resolve the requested room VNUM, or the captured staff room. Transfer named
participants there, obtain consent, form the two groups, and set legal ranks.
Read back the location, counts, and readiness. Fail preparation clearly if a
required item, character, or group slot is missing.

Wait for an explicit `start` in the runner's terminal. The observer can enter the
room using existing staff movement/visibility controls. Normal room output makes
the battle watchable; no custom spectator UI is required.

The room retains its ordinary flags and movement rules. Explain a missing room
or blocked combat rather than silently changing the world. Unrelated inhabitants
continue normal behavior.

### 4. Run simple combat through real player input

Start ordinary attacks on legal opposing targets. Use a few shared routines:

- Physical characters: maintain melee and try one suitable signature action.
- Healers: heal an injured group member; otherwise use their selected attack.
- Casters: alternate two prepared combat spells; fall back to an ordinary legal
  action when resources run out.
- Support characters: use one selected support ability and an attack.

Each class gets a short explicit command selection, not a bespoke AI. Summoning
classes use an eligible direct combat action in this version; do not quietly
claim pet coverage. If a proposed command is unavailable to the unspecialized
build, choose another eligible action and record that selection.

Read the minimal existing GMCP state needed for health, group presence, and the
current opponent; use command response text for the selected actions. Handle
Telnet/GMCP framing correctly and drain all sockets continuously. Keep at most
one pending action per character so casting/lag cannot build a runaway queue.

Resolve enemy race keywords/ordinals again after deaths or movement. Prefer the
current opponent where possible. Allies use their ordinary visible names.
Continue to obey native targeting, wait, casting, posture, and resource gates;
do not drive combat with staff `force` or direct effect calls.

Begin with ordinary damage, healing, and a small set of control/support actions.
Leave complex summon chains, item activations with separate windups, and lasting
room hazards outside this first script. Normal equipment procs still apply and
must be observed in the full match.

### 5. Finish, stop, and preserve useful bug evidence

A run ends on elimination, withdrawal, a visible time limit, or operator `stop`.
There is no automated tournament or reset. Dead characters stay out of that
match; no automatic relogging as reinforcements or teleporting withdrawn players
back into combat.

Keep only `start`, `status`, and `stop` as operator controls. Stop first ends new
commands, then uses the targeted helper/existing cancellation paths to stop the
selected participants' attacks and pending selected actions. Verify they settle;
merely closing their sockets leaves automatic combat running. Handle the actual
kit procs encountered, and report unresolved effects instead of claiming a clean
stop. Never use room-wide purge, global restore, or `transfer all`.

For bug finding, retain:

- Timestamped per-character gameplay transcripts and commands, after login.
- A short run summary: roster, classes/races, room, actual caps, preparation
  failures, duration, outcome, deaths, disconnects, and obvious rejected actions.
- Server log/crash evidence pointers when accessible. A disconnect is a symptom,
  not proof of a server crash; report what was actually observed.

Use an untracked `bin/racewar-battles/<run-id>/` directory. Distinguish attempts
from confirmed executions in the few action checks; do not build a universal
coverage/attribution system. Note any survivor/PC whose script never produced a
confirmed useful action. If a participant disconnects unexpectedly or output
stalls, stop/report an interrupted run rather than silently claiming victory.

If the controller or server becomes unreachable, preserve the run record and
say in-game stop is unconfirmed. A fresh run is deliberate; no automatic resume.
The existing server's logs and diagnostics support investigation without adding
a new telemetry subsystem.

## Fixed starting roster

Keep the previously checked 20-slot candidate roster: **12 races and 18 distinct
classes per side**. All 40 base race/class pairs were checked against the current
table; live availability and chosen actions still need verification. These are
unspecialized baseline builds, so duplicate healers need no spec-selection work.
Neutral races must explicitly join the intended racewar side.

Good side:

1. Mountain dwarf warrior — frontline leader.
2. Barbarian berserker — physical damage.
3. Human paladin — protection/support.
4. Centaur ranger — weapon and ranged coverage.
5. Thri-kreen warrior — racial combat variation.
6. Human monk — unarmed combat.
7. Halfling rogue — opening/positional actions.
8. Minotaur mercenary — physical damage.
9. Grey elf bard — group support.
10. Githzerai psionicist — mental abilities.
11. Mountain dwarf cleric — primary healing.
12. Human cleric — additional healing.
13. Firbolg shaman — healing and debuffs.
14. Grey elf druid — nature magic.
15. Gnome sorcerer — spell damage.
16. Human conjurer — spell damage.
17. Halfling illusionist — illusion/control abilities.
18. Githzerai ethermancer — class-specific magic.
19. Grey elf summoner — available direct combat spells.
20. Tiefling dragoon — class-specific weapon actions.

Evil side:

1. Thri-kreen warrior — frontline leader.
2. Duergar berserker — physical damage.
3. Troll mercenary — racial combat variation.
4. Orc anti-paladin — offensive support.
5. Githyanki monk — unarmed/racial combat.
6. Drow rogue — opening/positional actions.
7. Goblin reaver — class-specific combat.
8. Kobold bard — group support.
9. Drow cleric — primary healing.
10. Duergar cleric — additional healing.
11. Ogre shaman — healing and debuffs.
12. Githyanki psionicist — mental abilities.
13. Drider blighter — racial anatomy and class magic.
14. Kobold sorcerer — spell damage.
15. Drow necromancer — necromancy.
16. Githyanki conjurer — spell damage.
17. Goblin illusionist — illusion/control abilities.
18. Tiefling ethermancer — class-specific magic.
19. Drow summoner — available direct combat spells.
20. Minotaur mercenary — another physical/racial variation.

## Files and work sequence

Expected implementation footprint:

- `scripts/run_racewar_battle.py`: concurrent clients, a small fixed roster/action
  dictionary, preparation, simple combat loop, and transcripts. Start with one
  script rather than a separate configuration language and framework.
- `src/cmd/battleprep.c` and its header, with normal command/Makefile wiring:
  only the missing preparation and targeted stop behavior.
- Owning skill/kit/memorization functions only if a required existing function
  needs exposing; do not copy their policy into a new subsystem.
- A focused helper regression and a real-client full-group journey, extending
  existing checks where practical. Keep usage instructions with this plan until
  the runnable tool is delivered.

Revised estimate: **10-16 hours of active engineering with Codex doing the work**,
including implementation and focused full-group verification:

1. Reuse the client/creation flow and connect the full roster: **2-3 hours**.
2. Add the small baseline/kit/spell preparation helper: **2-4 hours**.
3. Implement placement, short action lists, start/stop, and transcripts: **3-4 hours**.
4. Build, watch full matches, reproduce/fix scoped findings, and document use:
   **3-5 hours**.

This replaces the earlier 24-36-hour estimate because automatic recovery,
specialization/pet coverage, rotation, and extensive reporting are removed.
The earlier plan had accumulated too much automation for the requested first
version. These numbers are estimates, not a measured Codex throughput guarantee.
Reassess after the first end-to-end setup if an existing account, item, or combat
defect blocks the chosen flow. Unrelated game repairs are not secretly included.

## Proof and finish line

- [x] Both sides contain real mortal PCs at the actual full group caps, with
  verified equipped Chaos kits and ready selected spells/resources.
- [ ] Explicit room selection and the default staff-room behavior work, with no
  environment gate or global room/account/rules changes.
- [ ] A normal client observes a full-size battle with melee, spell damage, and
  healing/support through actual player commands. Confirm useful execution from
  every selected role; a sent command alone is not proof.
- [ ] Normal player timing, resource depletion, racewar targeting, group behavior,
  equipment procs, deaths, and relevant saves are exercised. Record any category
  not reached instead of claiming it passed.
- [ ] The script drains all participants' output, cannot accumulate an unbounded
  input queue, distinguishes rejection/disconnection from success, and retains
  enough timestamped evidence to investigate a failure.
- [ ] Operator stop handles the selected participants and pending actions without
  disturbing uninvolved characters. Verify the stopped state, including observed
  kit effects; report interruption honestly when confirmation is impossible.
- [ ] Run a second fresh full-group match using the same account pool and another
  room to prove the tool is usable again without implementing automatic reset.

Use focused helper tests for the actual eligibility/spell/stop changes, then
`./scripts/format.sh --check` and `make -C src` after C/C++ changes. Exercise the
full real-client journey on the chosen setup. If an owning persistence path is
changed, run its applicable backend tests; no unrelated broad test matrix or
full burn-in is required. Do not wait for CI to finish the local work.

During the full run, observe server responsiveness as well as combat correctness,
using existing diagnostics when available. State the party sizes, duration, and
observed failures. One successful fight does not establish long-term stability,
maximum capacity, or exhaustive combat coverage.

## Implementation handoff

### Chunk 1: native preparation ([PR #406](https://github.com/LuminariMUD/Duris/pull/406), ready for review)

Implementation commit: `ffd1463fd` on `branch/issue-405-racewar-battle-plan`.
The PR targets `master`; dependent work should branch from its head and target
this branch until #406 merges. The PR remains open; no merge or deployment has
been performed.
GitHub converted the original issue-linked branch into a closing PR link at PR
creation. That link was removed; ordinary issue/PR/plan references remain. Check
`closingIssuesReferences` before publishing other partial chunks so #405 stays
open until all acceptance criteria pass.

`battleprep <exact-player-name> baseline|spells` is registered as an Overlord
command, without environment or Chaos gates. `baseline` uses native advancement,
sets base stats to 100, applies actual unspecialized skill/spell/song ceilings and
the existing epic grant, and restores derived resources. It refuses non-mortals,
disconnected/dead targets, specialization/multiclass, combat (including incoming
attacks), casts, item windups, and active memorization.

`spells` completes the player's existing memorize/pray queue after checking every
entry against current eligibility, book availability and per-circle capacity.
Validation is atomic: a bad entry leaves the whole queue unchanged. It does not
create spells or replenish mana/slots. Changes use existing dirty-component
tracking; the runner must issue ordinary `save` after final preparation.

Ablation: retain existing `chaos kit`, staff load/give of master book VNUM 7,
transfer, group, rank and restore commands. No new kit catalog, item deletion,
book-grant service, or persistence path is needed. Starting inventory can be
removed/dropped using ordinary character commands before the empty-inventory
Chaos grant; confirm the selected setup's result in the full journey.

Files: `src/cmd/battleprep.{c,h}`, normal command/Makefile/attribute wiring,
`tests/async/test_battleprep_runtime.py`, `tests/async/run_battleprep_journey.py`,
and this plan. Verified on 2026-10-27:

- `python3 tests/async/test_battleprep_runtime.py`: ASan/UBSan command checks passed
  for authority/exact target/busy guards, skill and song ceilings, native resource
  models, and atomic eligibility/book/circle validation.
- `python3 tests/async/test_epic_skill_grant.py`: existing eligibility harness passed.
- `python3 tests/async/test_command_attributes_coverage.py` and
  `python3 tests/async/test_spell_abort_command.py`: registration contracts passed.
- `python3 tests/async/test_documentation_contract.py`: all 14 checks passed.
- `./scripts/format.sh --check`, `git diff --check`, and `make -C src -j4`: passed.
- Flat-file build passed with `make -C src PERSISTENCE_BACKEND=flatfile
  DMS_BINARY=/home/aiwithapex/projects/duris/bin/server/dms_battleprep_flatfile -j4`.
- `python3 tests/async/run_battleprep_journey.py --binary
  bin/server/dms_battleprep_flatfile`: passed real login/command dispatch, mortal
  denial, native advancement, master-book load/give, cleric/sorcerer queued
  preparation, acknowledged saves, server restart and reloaded prepared spells.
  Executable SHA-256: `723ccd6862895aa8dd91446cc74bed8df90974151977692e2e9b71591632690c`.

Local build/journey logs: `bin/racewar-battles/implementation/` (untracked).
The journey uses disposable flat-file authority. No persistence implementation
changed; MariaDB runtime behavior and full-party combat remain unverified.

Next: stack the concurrent client/provisioning runner and targeted stop/combat
chunks on #406.
The seven finish-line requirements above remain unchecked until runtime evidence
proves them. No release tag or deployment is needed for review-only chunks.

Integration findings for the runner: use `rest` (sitting alone does not enter the
resting state), and unquoted names for `pray full heal` / `memorize <spell>`;
casting has its own syntax. Await `Save complete for <name>.`, since a normal
prompt can follow `Save queued` before persistence finishes. For targeted stop,
reuse `StopCasting()` (which also aborts item actions), `stop_singing()`,
`stop_memorizing()` and targeted `tranquilize()`, with explicit participant input
queue draining and observed settling. Their presence alone is not stop proof;
the next chunk must exercise queued actions and actual kit effects.

### Chunk 2: real connections and full-roster provisioning ([PR #407](https://github.com/LuminariMUD/Duris/pull/407), ready for review)

Working branch: `branch/issue-405-racewar-runner`, based on #406 at `ba32e7831`.
PR #407 targets `branch/issue-405-racewar-battle-plan` while #406 is open.
Implementation commit: `e9173a282`. Next dependent work should branch from #407's
head and target `branch/issue-405-racewar-runner`; neither PR closes #405.
Active worktree: `/home/aiwithapex/projects/duris-racewar-runner` (Windows:
`\\wsl.localhost\Ubuntu\home\aiwithapex\projects\duris-racewar-runner`).
The primary `/home/aiwithapex/projects/duris` was released clean for the separately
authorized local master rebuild; do not run this task's builds or journeys there.
The app worktree tool hit a Windows Git ownership check, so this is a native WSL
Git worktree. Required ignored binaries, world files and evidence were copied
before releasing primary; no credentials or player data from the local MUD were copied.

`scripts/run_racewar_battle.py` now contains an asyncio client with incremental
Telnet/GMCP framing, continuous socket draining, bounded retained text and
timestamped gameplay logs that start after login. Preparation commands serialize
per connection. A prompt is explicitly **not** proof of a combat action; the
future combat loop still needs action-specific completion/rejection checks.

Provisioning uses the normal registration and creation flow, four simultaneous
admissions below the native eight-login limit, live race/class menus, separate
accounts, and fresh characters. Credentials are kept in a reusable private
account-pool file; run rosters contain only identities and preparation state.
The two leaders supply independent `Group.Status.maxSize` values. Existing staff
`stat room`, `goto` and named `transfer` commands support default/explicit location,
including wilderness VNUMs hidden by `Room.Info`. Group formation uses ordinary
consent and group commands, with actual PC membership and room presence checked.

Source finding: both self and leader `group back/front` branches deliberately
return without changing ranks. Preserve native default ranks; do not enable that
disabled mechanic just for the runner. Native character creation sets neutral
races' initial side through its alignment path; placement verifies actual racewar
side from staff `stat char` instead of assuming alignment alone proves it.

PR #407 review follow-up (2026-10-27): the delayed-entry-prompt finding was valid.
The local socket regression reproduced an incomplete `Paging` result and early
paging commands during normal staff entry, reconnect, connection override and
new-character entry. Telnet decoding now preserves text/GMCP/prompt order;
command completion requires a prompt at or after its matched response, and both
entry paths wait for a prompt after `Char.Status` before starting gameplay logs
and paging setup. This reuses the existing parser and command lock without a new
transport, retry, delay or command-queue layer.

Review validation: `python3 tests/async/test_racewar_runner.py` passes all 13
tests, including the two new socket regressions; `python3
tests/async/test_documentation_contract.py` passes all 14 checks, and
`git diff --check` passes. A disposable two-client native smoke check reused
`configure()`/`Server` from the existing journey and the binary hash recorded
below. Staff login, fresh character creation, paging OFF, room lookup and both
asynchronous save acknowledgements passed. Its receipt and gameplay transcripts
are under `/home/aiwithapex/projects/duris-pr407-review/bin/pr407-review/entry-smoke-02/`.
An initial smoke assertion assumed a single space in the toggle table; correcting
that assertion to accept the native column spacing required no application change.
The earlier 80-character provisioning evidence remains applicable; no C/C++ or
provisioning policy changed, so no rebuild or full-roster rerun was needed.

Git review: the stack remains #406 -> #407 -> #409 -> #410. The prospective merge
of #407 into `master` at `224f1824d` was conflict-free. Keep the dependency bases
and carry this correction forward with merges; no rebase, squash, or release tag
is needed. The active combat worktree has separate uncommitted work and must be
preserved; once that work is committed, merge the updated
`branch/issue-405-battle-preparation` into its combat branch.

`python3 tests/async/test_racewar_runner.py`: eleven focused tests passed, including
failure cancellation that closes every partial-roster connection and preserves
credential-free roster evidence, unequal independent group caps, and native paging
setup. `python3 tests/async/test_documentation_contract.py`: 14 checks passed.

`python3 tests/async/run_racewar_provision_journey.py --binary
bin/server/dms_battleprep_flatfile --output bin/racewar-battles/provision-03`
passed on 2026-10-27 using the existing tested native binary, SHA-256
`723ccd6862895aa8dd91446cc74bed8df90974151977692e2e9b71591632690c`:

- First run: full good/evil 20/20 groups in captured staff room 22800.
- Second run after normal server shutdown/restart: full 20/20 groups in explicit
  room 1200, using the same 40 accounts and 40 different character identities.
- Native GMCP membership has zero NPCs, exact expected names, actual size/cap 20,
  and every member present in the selected room on both runs. All 80 characters
  reached acknowledged ordinary saves.
- Both sides retained 12 races. Good had 17 distinct classes, evil 18. The server's
  checked-in `lib/creation_availability.cfg` disables Dragoon, so the requested
  Tiefling Dragoon became a Tiefling Warrior; the run records that substitution.

Receipts are `bin/racewar-battles/provision-03/result.json` and each match's
`summary.json`, `roster.json`, and per-character JSONL transcripts. The private
`accounts.json` is not a shareable receipt. There were no C/C++ changes in this
chunk, so the valid native build evidence was reused. The operator CLI, gear/spell
preparation, combat actions, stop and final acceptance journey remain outstanding.
These provisioning-only runs do not satisfy either full-combat acceptance run.

Runtime progress: `provision-01` created all 40 real characters but failed placement
because the inherited `toggle page off` spelling was invalid; paged `stat` output
consumed the next transfer. The runner now reads the actual toggle state and uses
`toggle paging` only when needed, checking the native confirmation.
`provision-02` was deliberately interrupted for the worktree move, with its server
stopped. `provision-03` then passed from the new worktree, including grouping and
account reuse. Do not repeat it merely for documentation or PR-link edits.

### Chunk 3: gear and selected spell preparation ([PR #410](https://github.com/LuminariMUD/Duris/pull/410), ready for review)

Working branch: `branch/issue-405-battle-preparation`, based on the small Centaur
compatibility fix in [PR #409](https://github.com/LuminariMUD/Duris/pull/409) at
`5b6318283`. #409 targets #407; this preparation PR targets
`branch/issue-405-centaur-kit`. Continue exclusively in
`/home/aiwithapex/projects/duris-racewar-runner`.
Implementation commit: `5e0e359aa`. Stack the combat chunk on
`branch/issue-405-battle-preparation` while #410 is open.

`prepare_fighters()` clears only fresh starter inventories through normal
remove/drop commands, observes empty inventory, and awaits the existing Chaos
kit grant. It then advances the character, outfits the catalog, supplies a full
master book when missing, queues two copies of each selected memorize/pray spell,
restores resources and saves. The grant precedes advancement because asynchronous
achievement rewards can otherwise race its empty-inventory admission check.

`battleprep <name> equip` uses existing `wear()` with the catalog's intended
categories. Generic `wear all` can strand kit armor when multi-slot items occupy
its intended slots. Binding, anatomy and hand limits remain native. Read-only
`equipment` verifies actual armor counts, a worn kit weapon, retained hand-item
alternatives and occupied usable hand capacity. Books stay carried; monks keep
hands/shields free for normal unarmed mechanics. No second catalog or direct
`equip_char()` bypass was added.

Mana and slot casters retain native resource models. The runner verifies current
score/level/resources, and native commune/tupor/deforest slot listings. A final
`group` query refreshes membership and levels: cached `Group.Status` alone can
retain pre-advancement levels. Exact full membership, levels and room presence
must match the prepared roster before it is reported ready.

The full setup exposed a Centaur kit defect: boots 83486 are unusable on hoofed
feet, while horseshoes are valid. PR #409 supplies portable golden horseshoes
99061 through normal grant validation; the full run below verifies them worn.

Verification on 2026-10-27:

- `python3 tests/async/test_chaos_equipment_ready.py`: ASan/UBSan checks passed for
  native catalog-directed placement, duplicate counts, anatomy, unarmed monks,
  retained alternatives, hand capacity and current profile selection.
- `python3 tests/async/test_battleprep_runtime.py` and
  `python3 tests/async/test_chaos_kit_runtime.py`: focused native checks passed.
- `python3 tests/async/test_racewar_runner.py`: 14 focused checks, including fresh
  readiness snapshots and incomplete-gear rejection.
- Both MariaDB and flat-file builds passed; formatting/diff checks passed.
- `python3 tests/async/run_racewar_provision_journey.py --binary
  bin/server/dms_battle_ready_flatfile --output bin/racewar-battles/preparation-full-08
  --prepare`: passed with 40 fully prepared PCs and 40 acknowledged saves. Both
  live groups contain 20/20 PCs, every member is level 56 and present in room 22800.
  Native spell preparation covered 18 PCs; five slot casters had full native slots;
  12 book-class PCs had full master books. Full resources are recorded per PC.
- Binary SHA-256: `e57074e91bd75a539cf7a9b7fa8923b5d2caa0a46690d7863ff99e9c45da17f9`.
  Receipts: `bin/racewar-battles/preparation-full-08/result.json`,
  `match-1/summary.json`, `match-1/preparation.json`, and gameplay/native logs.
  The fixture uses real item prototypes with disposable flat-file authority.

Earlier probes remain local diagnostic evidence. `preparation-full-07` also
completed setup, but its cached group snapshots were superseded by the explicit
live refresh in `preparation-full-08`. Do not repeat either run for documentation
or PR-link changes. No live MUD operation or deployment was performed.

Next: operator CLI, pre-fight buffs, normal-command combat, targeted stop, and two
full battle journeys. The native input receipt extension is being developed in
separate unstaged networking/descriptor files; it is not part of this preparation
chunk. It acknowledges actual dequeue only, never successful combat execution.

### Chunk 4: native battle controls ([PR #411](https://github.com/LuminariMUD/Duris/pull/411), ready for review)

Branch: `branch/issue-405-battle-controls`, originally stacked on #410 at `ee90a711c`.
Implementation commit: `ce7bf946a`. #406/#407/#409/#410 are now merged, and #411
targets `master` after ordinary synchronization merge `0f808b50b`. Its native
source tree exactly matches the combat checkout's integrated source tree
`34c260e7765d97783f54df7d4285e4254b1b67e1`; the already-passed MariaDB/flat-file
builds and focused native checks are reused. No history was rewritten.
Worktree: `/home/aiwithapex/projects/duris-racewar-runner`. The reviewed #407
prompt-ordering fix is included through #410's existing merge, without rewriting
history. Operator work is on `branch/issue-405-racewar-combat`, which already
contains this integrated source and retains its separate runner changes.

Outcome: observe actual player input dequeue, obtain legal mortal room selectors,
and stop only the selected participants and actions involving them. Non-goals:
no combat dispatch, damage, lag, room-rule or resource shortcut; no new service,
recovery subsystem or general action configuration. This is the minimum native
support the one-script runner needs for bounded queues and reliable stop evidence.

- `Core.Hello {"commandReceipts":true}` opts this connection into `Char.Input`.
  The initial message has the current `sequence`; each playing-command dequeue
  increments it and reports the canonical `command` verb. Arguments, credentials,
  login, paging and editor input are not echoed. A receipt proves dequeue only,
  not admission, completed casting or a successful effect. Renegotiation never
  acknowledges queued input. Legacy clients do not opt in and receive no receipts.
- `Room.Info.players[].target` is a normal keyword/ordinal selector, or null when
  none is available. It shares the exact existing `get_char_room_vis()` matching
  predicate, including racewar names, introduction, NPC collisions, visibility,
  disguise and height. The normal command still resolves it at execution time;
  it is not a stable identity and must be refreshed after movement/death.
- `battleprep stop <exact-player-names>` drains selected descriptor queues and
  partial input, aborts casting/memorizing/singing and pending item actions
  involving those characters, then uses native targeted tranquilize. Linkdead
  mortals can still be stopped. NPCs, staff and missing targets are reported.
  `battleprep status <exact-player-names>` is read-only and reports quiet/pending,
  including incoming melee. Quiet is a snapshot, so the runner must observe a
  settling interval and must not claim success after a lost control connection.
  Ongoing unrelated fights/actions remain untouched; incoming attacks involving
  a selected participant necessarily stop with that participant.

Files: `src/cmd/battleprep.c`, native descriptor/GMCP/room serializers and target
lookup, `src/item/item_actions.{c,h}`, their focused tests, the existing provisioning
journey's `--controls` diagnostic and this plan. Shared predicates avoid a second
targeting or item-cancellation policy. No persistence path changed.

Focused ASan/UBSan checks for input receipts, target selectors, battleprep and item
actions pass, as do all 16 integrated runner tests and the GUI GMCP contract.
Both backend builds pass. The four-PC native control journey passed with
`--controls`; it is not a full-party battle acceptance run. Remaining work:
operator CLI, pre-fight buffs, combat decisions and result classification,
settled targeted stop, observer output, and two fresh 20/20 matches using the
same accounts and different rooms. Do not mark #405 complete from control proof.

Completed native proof on 2026-10-27:

- `python3 tests/async/test_gmcp_input_receipts.py`,
  `python3 tests/async/test_room_target_selectors.py`,
  `python3 tests/async/test_battleprep_runtime.py` and
  `python3 tests/async/test_item_actions_runtime.py`: sanitizer checks passed.
- `python3 tests/async/test_gui_gmcp_contract.py`: serializer/wire checks passed.
  All 16 existing runner checks and all 14 documentation checks passed.
- `make -C src -j4` and the corresponding `PERSISTENCE_BACKEND=flatfile` build
  passed. Formatting and diff whitespace checks passed.
- `python3 tests/async/run_racewar_provision_journey.py --binary
  bin/server/dms_battle_combat_flatfile --output bin/racewar-battles/controls-03
  --controls`: four real geared PCs; opt-in look dequeue receipts, legal mortal
  attack/spell selectors, native melee, active-cast abort, queued-attack stop,
  quiet status after six seconds, an unaffected standing bystander and acknowledged
  saves all passed. `controls-01`/`02` exposed test assumptions (case-normalized
  status names and score not refreshing GMCP vitals); those assertions were fixed
  to check native status and observed score/prompt output instead of cached data.
- Binary SHA-256:
  `890d4f9d7acd6949038fa8b7a4f6d9a9ee472d92a55d91a7d8fd5f3dd450910c`.
  Evidence: `bin/racewar-battles/controls-03/result.json`,
  `match-1/controls.json`, per-character transcripts and native server logs.

The user reiterated that discovering game defects and observing load/performance
are primary purposes. The full-battle chunk must retain failure evidence and
sample controller responsiveness during combat; investigate reproducible findings
and ship focused repairs. Queue/cast elapsed time includes native gameplay lag and
must not be represented as server processing latency. A successful fight alone
does not prove capacity or long-term stability. The user is merging ready PRs
individually; check live dependency state before publishing/retargeting each chunk.

### Native finding: queued input crosses death into the account menu ([PR #412](https://github.com/LuminariMUD/Duris/pull/412), ready for review)

The full 20/20 `battle-03` run in the combat worktree produced 13 deaths. Queued
gameplay input was then consumed by the account menu (`Invalid Selection` after
the death/menu output). This is a game-session transition defect independent of
the runner's conservative handling of absent dead PCs.

Fix branch: `branch/issue-405-death-input`, based on #411. The ordinary extraction
transition and direct hardcore-death transition now discard queued and partial
input while preserving output. `flush_input_queue()` also replaces the same
drain loop in targeted battle stop and is reused when closing a descriptor.
There is no new state machine, gameplay rule or persistence mutation.

Files: `src/net/comm.{c,h}`, `src/world/handler.c`, `src/combat/fight.c`,
`src/cmd/battleprep.c`, focused native input-reset/battleprep tests, and
`tests/async/run_death_input_journey.py`. The native sanitizer test proves complete
and partial input clearing, intact death/menu output, unrelated session isolation,
idempotence and fresh menu input. A real-client regression sends benign type-ahead
behind an ordinary attack on the existing disposable executioner fixture, then
checks native death, the account menu and a fresh character-list selection.
Verified on 2026-10-27: both backend builds, the input-reset and battleprep
ASan/UBSan tests, terminal saved-item extraction contracts, formatting and
changed-line clang-tidy pass. The real-client journey fails on the prior binary
with `queued gameplay reached the account menu` and passes on the fixed binary,
including death/menu output and a fresh menu selection. No persistence
implementation changed, so an unrelated database matrix was not run.

Evidence in the combat worktree: `bin/racewar-battles/death-input-before/` and
`bin/racewar-battles/death-input-after/`. Fixed binary SHA-256:
`3606bc3b6d7fb39d68c3925a0d9b5df5644e1de6fa9880d49731a9fb97785ab3`.
The tested complete `src` tree is `7b265f78e455a56f8afc34b91c9df829f89e3698`,
identical on this focused branch and the integrated combat checkout. Full battle
acceptance and the separately discovered 15-participant PvP outcome limit remain
in progress; this chunk does not close #405.

### Native finding: full-group PvP outcomes exceed the capture limit ([PR #414](https://github.com/LuminariMUD/Duris/pull/414), ready for review)

Branch: `branch/issue-405-full-group-outcomes`, based on #412. Edit/qualification
worktree: `/home/aiwithapex/projects/duris-battle-fixes`; the operator remains in
`/home/aiwithapex/projects/duris-racewar-runner` on `branch/issue-405-racewar-combat`.
The full fight's reward failure was traced to the 15-participant outcome bound:
the native producer captures both groups, so 20/20 cannot reach the writer.

Outcome: capture, persist and replay all 40 participants atomically, retaining
the existing public snapshot limits and old records. Non-goals: no dropped
participants, snapshot truncation, split kill transactions, general batching
framework, group-rule changes or increase to the coordinator's total admission
memory budget. The retained changes are the existing bounded codec/storage
limits and the one required SQL widening.

Implementation currently raises capture to 40, command payload capacity to 8 MiB,
maximum combat/completion/SQL result buffers to 8,192 bytes and flat-file authority
operations to 82. Small outcomes keep their old result sizes. Decoders accept old
1,536/2,048-byte results with the original participant bound and validate row
lengths before reading; native domain format 4 admits larger receipts while
formats 1–3 retain their old bounds. Migration 0054 (sequence 55) widens only the
known 4,096-byte SQL inbox to 8,192 with online DDL requirements. The baseline
and sealed migrations stay unchanged.

Proof so far: expanded native capture/codec tests, full-group flat-file prepared
award/replay tests, and the disposable SQL outcome suite pass. SQL proof includes
all 40 maximum-sized public snapshots, a failure at the last participant that
rolls back the entire outcome, retry, exact replay, preserved prior result bytes,
idempotent widening and refusal to narrow an unexpected column. New runtime
metadata fingerprints were measured and cleanly verified on isolated MariaDB
10.11 and MySQL 8.0; `scripts/validate_runtime_compatibility.py` passes.

Local evidence in this fix worktree: `bin/combat-capacity-codec.log`,
`bin/combat-capacity-flatfile.log`, `bin/combat-capacity-mysql.log`,
`bin/full-group-schema.log` and `bin/full-group-schema-result.json`. The one-off
metadata driver is ignored at `bin/measure_full_group_schema.py` and creates only
network-isolated task containers, which it removes afterward. No production or
primary local database was accessed. Both server builds now pass. The tested native
source tree is `f157a00977744d653e7d380cde1a13d773d51227`, identical on this branch
and the integrated combat checkout. The flat-file binary SHA-256 is
`be370f514e32f26c273f23928a77ef2646459afe474060b252c1a3fc56427b48`.
The final two full battles are running as `bin/racewar-battles/battle-04` in the
combat worktree; this PR's persistence proof does not claim their completion.

Commands/results for this chunk:

- `python3 tests/async/test_combat_outcome_transactional_cutover.py`: five tests pass,
  including 40-PC native capture, full snapshot encode/decode and old receipt reads.
- `python3 tests/async/test_flatfile_player_domain_repository.py`: full-group
  prepared award storage/replay and old/new native format bounds pass.
- `bash tests/async/run_combat_outcome_schema_mysql.sh`: disposable SQL suite passes,
  including full-group late rollback/retry, replay, long snapshots and migration guards.
- `python3 tests/async/test_critical_command_codec.py` and
  `python3 tests/async/test_critical_completion_capacity.py`: bounded command codecs
  and complete 8,192-byte fresh/replayed completion delivery pass.
- `python3 tests/async/test_divine_boon_delivery.py` and
  `python3 tests/async/test_reward_producer_replay.py`: prepared award recovery and
  duplicate-delivery behavior pass.
- `python3 tests/async/test_migration_runner_cli_safety.py`,
  `python3 scripts/validate_runtime_compatibility.py` and all 14 documentation
  checks pass. Formatting, whitespace and normal commit hooks pass.
- `make -C src -j4` and `make -C src PERSISTENCE_BACKEND=flatfile
  DMS_BINARY=/home/aiwithapex/projects/duris-racewar-runner/bin/server/dms_battle_full_group_flatfile
  -j4` pass in the integrated combat checkout. Logs are under
  `bin/racewar-battles/implementation/full-group-build-*.log` there.

### Early-stop finding: legacy acid pulses re-engage stopped participants

`battle-04` passed the repaired first 20/20 match (120.02 seconds, 14 deaths,
26 survivor save acknowledgements, 204 completed spells, no capture failures,
37 PCs receiving frag-award messages). The second fresh match correctly reused
the 40 accounts in room 1200, but its 30-second operator stop exposed a remaining
control gap: legacy `event_acidimmolate` kit pulses continued outside
`item_actions` and restarted melee. Standing sleepers also suffered native
collapse/stun damage. The runner reported the unconfirmed stop honestly.

Fix branch: `branch/issue-405-stop-effects`, based on #414. `battleprep stop`
cancels only acid events whose actor or target is a selected PC, using native
event handles; status includes those incoming/outgoing events. Effects between
other characters remain untouched. Successfully tranquilized standing sleepers
settle into a sitting sleep posture, avoiding later collapse damage. The native
command test covers both directions, unrelated events and the resulting posture.

The operator chunk separately batches by the actual 1,023-byte input limit, so
all 40 names are stopped in one native command; the earlier arbitrary batches of
eight allowed spells to finish between batches. A focused client test verifies
the full roster is sent atomically. No blanket event cancellation, room flags,
general effect framework or normal-combat change is introduced.

The existing four-PC `--controls` journey now seeds the actual legacy acid spell
through the native staff command and proves incoming-pulse cancellation and
stable health after stop. The old binary fails the stable-health check; the fixed
binary passes it in `bin/racewar-battles/acid-stop-after-02` in the combat worktree.
Both backend builds, native ASan/UBSan battleprep checks, formatting and commit
hooks pass. The test now establishes melee before starting the abortable cast,
so the cast cannot complete while the test is still waiting for melee to begin.
Fixed binary SHA-256: `702d63df0285c3d0ef6c4828750450685afac036e907cf730596a98a34672f33`.
Tested source tree: `8ddac7afe1fbf34ae680aa6f585e8fa206c20f00`, identical on the
focused fix branch and combat checkout. The full pair is running as `battle-05`.
Completed first-match combat,
reward, persistence and performance evidence remains valid; no unrelated tests
need repeating.
