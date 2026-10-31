# Quest systems

Duris has several independent systems called quests. This reference describes
the current source as checked on 2026-10-30. It describes repository behavior;
it does not establish which binary or configuration is running in production.
Function names below are the entry points to recheck when changing behavior.

## Choose the right reference

- **Authored NPC and zone quests:** `.qst` files supply dialogue and item/coin
  turn-ins. Start with [Static NPC quests](#static-npc-quests) below and the
  [area-writing manual](../content/area_writing.txt), section VIII.
- **Bartender world quests:** generated, paid ASK/KILL assignments, with their
  own player status and completion history. See
  [Bartender world quests](BARTENDER_QUESTS.md).
- **Zone-story tracking:** a completion ledger and achievement views over the
  static `.qst` catalog. See [Tracking and dailies](#tracking-and-dailies), the
  [tracking contract](ZONE_STORY_QUEST_TRACKING_CONTRACT.md), and the
  [catalog reference](ZONE_STORY_QUEST_CATALOG.md).
- **Zone-story dailies:** an optional daily assignment and renown layer over
  that catalog. It ships disabled; see
  [ZONE_STORY_QUEST_DAILY.md](ZONE_STORY_QUEST_DAILY.md).
- **XML quests:** the separate actor/action/tag engine in `nq.c`. Its parser
  exists, but command registration, saving, and several policies are incomplete.
  See [XML_QUESTS.md](XML_QUESTS.md) before attempting to author content.
- **Epic tasks:** progression obligations assigned while gaining epics: find a
  runestone, Spill Blood, or convert a nexus. See [EPIC_TASKS.md](EPIC_TASKS.md).

These systems do not share an acceptance record, journal, daily allowance, or
completion identity. In particular, bartender completions and epic runestones
do not contribute definitions to the static zone-story percentage. A bartender
quest can award epic points, which can trigger an epic task through the ordinary
epic award path; that does not make it a zone-story completion.

## Source map

- [quest.c](../../src/world/quest.c): static file reader, `quester()`, goal
  consumption, rewards, and staff inspection.
- [make_qst.c](../../areas/src/qst/make_qst.c) and
  [specs.assign.c](../../src/specs/specs.assign.c): area compilation, quest boot,
  tracking bootstrap, and quest-procedure assignment.
- [world_quest.c](../../src/world/world_quest.c) and
  [world_quest_policy.c](../../src/world/world_quest_policy.c): generated task
  state, selection, routes, completion, maps, and sharing.
- [specs.mobile.c](../../src/specs/specs.mobile.c): `world_quest()` handles
  bartender requests, fees, abandonment, and replacement.
- [sql.c](../../src/sql/sql.c) and
  [flatfile_world_quest_history.c](../../src/flatfile/flatfile_world_quest_history.c):
  bartender completion history and daily allowance, through the
  `sql_world_quest_*` interface on both builds.
- [zone_story_quest_runtime.c](../../src/world/zone_story_quest_runtime.c),
  [zone_story_quest_production.c](../../src/world/zone_story_quest_production.c),
  and [zone_story_quest_feature.c](../../src/world/zone_story_quest_feature.c):
  static definition binding, completion credit, achievements, and dailies.
- [nq.c](../../src/cmd/nq.c): XML definitions, actors, actions, tags, and instances.
- [epic.c](../../src/world/epic.c) and
  [epic_task_catalog.c](../../src/world/epic_task_catalog.c): epic task assignment,
  catalog readiness, rewards, and sharing.
- [interp.c](../../src/cmd/interp.c),
  [actcomm.c](../../src/cmd/actcomm.c),
  [actobj.c](../../src/cmd/actobj.c), and
  [fight.c](../../src/combat/fight.c): actual command registration and interaction
  hooks. A function's existence alone does not make a command available.

## Static NPC quests

### Content and loading

Editable content lives in `areas/qst/<area>.qst`, selected by `areas/AREA`.
`make_qst` concatenates the active per-area sources into `tworld.qst`; world
generation produces `areas/world.qst`, which `boot_the_quests()` reads.
`assign_the_questers()` attaches `quester` as each giver prototype's `qst_func`.
Mini mode uses `areas_mini/mini.qst` and skips quests if that file is absent.

Use the maintained [world generation procedure](../guides/BUILDING.md#area-file-generation):
`make build-area-tools`, then `make world`. Combined world files are generated
outputs. Edit the per-area source and check its mobile/object references there.
The runtime file ends with a `$` terminator. Per-area giver blocks end with
`S`; the final `end` source supplies the combined file's terminator.

### File language

A giver starts with `#<mobile-vnum>` and ends with `S`. Its records are:

- `M`, followed by tilde-terminated keyword and response strings: dialogue.
  `MA` sends the response to the room.
- `Q`, followed by a tilde-terminated completion message: starts one turn-in
  rule. `QA` sends completion/disappearance text to the room.
- `G I <object-vnum>`: require and consume one object of this prototype.
- `G T <item-type-number>`: require and consume one object of this type.
- `G C <coin-value>`: require and consume a total value in the server's base
  money units (copper).
- `R I <object-vnum>`, `R C <coin-value>`, `R S <skill-number>`, and
  `R E <xp>`: reward an item, money, a skill/spell, or experience.
- `D`, followed by tilde-terminated text: remove the giver after this rule
  succeeds. The implementation extracts its equipment/inventory and the NPC;
  an old comment suggesting it only moves to the void is stale.

`G`, `R`, and `D` belong to the most recently declared `Q`; they cannot precede
it. The loader prepends messages, completion rules, and goals to linked lists.
Consequently, later dialogue/rules in a file are considered first. Put specific
alternatives after general ones and verify overlaps with a real turn-in.

Illustrative per-area fragment (replace the VNUMs with valid content):

```text
#12300
M
help token~
$n says, 'Bring me the lost token.'~
Q
$n says, 'Thank you for finding it.'~
G I 12301
R E 1000
R I 12302
S
```

Repeated identical item goals request multiple copies. Keep specific-item and
item-type goals disjoint: the precheck examines the same NPC inventory for
both, and consumption is not a rollback-capable transaction. Consolidate coin
requirements into one `G C` value for the same reason.

`qc_action <number>` is a special message keyword used for ambient NPC actions
by `execute_quest_routine()` from `mobact.c`. It rolls on mobile updates; the
number is not an exact repeating timer. It supplies room flavor rather than a
completion rule.

### Interaction and completion

Players use `ask <giver> <keywords>`, `tell <giver> <keywords>`, and
`give <item-or-coins> <giver>`. The `isname()` matcher compares the entire
supplied message with a keyword or contiguous
phrase in the keyword list, case-insensitively; it does not search an arbitrary
sentence for any matching word. XML phrases have different matching rules.
`quester()` requires mutual visibility
for mortals, an awake nonfighting giver, and no conjured-pet involvement.

A give invokes `do_give()` before `quest_completion()` checks the NPC's
inventory and money for all goals, so earlier offerings can contribute.
Successful object and coin transfers reach the NPC in memory before this
check: the currency completion runs before its submit call returns and credits
NPC coins directly. A rejected give does not itself prevent the later goal
check from finding earlier offerings. The engine has no
per-player reservation of items held by the NPC.
The first successful completion rule consumes its requirements, attempts to
record zone-story credit, awards rewards, and optionally removes the giver.
There is no separate accept/abandon/expiry state for a static quest.

Reward details in `give_reward()`:

- An item is submitted through the item-creation grant service. It goes to the
  player only with a free carrying slot and a resulting carried weight strictly
  below the weight limit; equality also sends it to the room. Missing prototypes,
  artifact duplication checks, or grant rejection can prevent an item award.
- Money goes to the direct completer. A skill reward initializes `learned` to
  1 only if the character meets the skill's required level and has not learned it.
- XP goes to the completer and other PC group members in the same room. The
  handler caps the completer's requested XP at one tenth of
  `new_exp_table[level + 1]`. The group
  member branch resets its intermediate value and actually caps at the full
  `new_exp_table[member_level + 1]`; do not assume equal caps.

Turn-in consumption, reward grants, and tracking persistence are separate
operations. Failed tracking is logged and does not stop the legacy reward;
failed item creation does not return consumed offerings. This engine does not
provide an atomic exchange/retry guarantee across all those effects.

### Staff inspection

The following commands are registered at immortal level in `interp.c`:

```text
qview <mobile-vnum>
qref <object-vnum>
qinfo <object-vnum>
qlist
qlist <mobile-vnum>
qlist <from-vnum> <to-vnum>
```

`qview` shows raw dialogue and completion rules. `qref` finds item requirements
and rewards using an object; `qinfo` includes the matching rule details.
`qlist` without arguments uses the current zone's prototype VNUM range;
`hlqlist` is its alias. These inspect indexes without creating NPCs/items.
Trusted `tell <giver> quest` also invokes the older `tell_quest()` display.

## Bartender world quests

The [standalone bartender quest reference](BARTENDER_QUESTS.md) covers player
commands, ASK/KILL completion, selection and travel policy, rewards, fees,
sharing, maps/GMCP, invalid-assignment recovery, persistence, and validation.
Each character owns its assignment and history; these completions do not
contribute definitions to zone-story tracking.

## Tracking and dailies

### Completion identities and credit

At boot, `zone_story_quest_production::bootstrap()` builds definitions from the
booted static quest index and binds each eligible `Q` block to an identity.
Identity uses the giver and canonical goal/reward/disappearance contract;
equivalent alternatives are deduplicated. Prose-only changes do not create a
new accomplishment. The zone is the giver's prototype zone. Revision handling,
eligibility, and snapshot regeneration are specified in
[ZONE_STORY_QUEST_CATALOG.md](ZONE_STORY_QUEST_CATALOG.md).

`record_legacy_completion()` captures the direct completer plus distinct,
nonstaff PC group members in the room before legacy rewards run. It records
the room, time, season, revision, and party context. Staff completers are
ineligible. PERSONAL, SOLO, GROUP_PARTICIPANT, and LEADERSHIP are credit modes,
not four separately completed quests. Distinct definitions per character/PID
per season determine percentages; repeated completions remain history.

The season uses the SQL season epoch when available, then positive
`ZONE_STORY_SEASON_ID`, then 1. This service has its own persisted state,
separate from the player's bartender fields and epic task affects. SQL uses
the `0026_zone_story_quest_state` repository; flatfile uses
`<FLATFILE_ROOT>/domains/zone-story-quests.state`. Flatfile saves replace the
checked state file atomically. SQL saves enqueue a whole-state upsert; a
successful enqueue is not a commit acknowledgment. Immediate serialization,
flatfile-write, or SQL-enqueue rejection restores the prior in-memory tracker
state, and the legacy caller logs the failure but continues rewards. A later
SQL writer failure is logged asynchronously and does not perform that rollback.

Player views are `achievements zones`, `achievements zone <area>`, and
`leaderboard quests [page]`. The leaderboard omits staff and zero-completion
characters and delays public counts up to 12 hours; personal views remain current.
The [tracking contract](ZONE_STORY_QUEST_TRACKING_CONTRACT.md) defines the
numerator, denominator, transaction boundary, and group-credit meaning.

### Optional daily layer

`ZONE_STORY_DAILY_ENABLED` is read at bootstrap and is false when unset.
Enabling dailies does not create a second authored quest language. The service
chooses among suitable definitions in the same static catalog, using recorded
evidence and a deterministic fixed UTC-day assignment per PID/season.

Default suitability needs 20 attempts from 5 distinct PIDs, a success,
accessible current-revision evidence, and known party context; carrying by
someone over 10 levels higher cannot establish suitability. No suitable
candidate produces a persisted no-candidate result, not an invented assignment.
Only the assigned definition/revision completed in its period can award one
renown, once for the durable `season:pid:period` key. Repeat completions still
do not inflate distinct-definition percentages.

`quest daily` and the extra `quest`/`score` text appear only with enabled,
populated daily state. The [daily reference](ZONE_STORY_QUEST_DAILY.md) contains
the full evidence policy, reporting command, storage format, and rollout rules.
Tracking/achievement credit and daily renown are separate outcomes; disabling
dailies does not disable ordinary static completions.

## Native and scripted quest content

Some zone mechanics are implemented in native special procedures rather than
one of these data engines. Examples and focused journeys include the
[Kjelgar crystal quest test](../../tests/async/test_kjelgar_crystal_quest.py)
and [automaton recovery test](../../tests/async/test_automaton_quest_recovery.py).
Their state and rewards must be traced in the owning procedure; this reference
does not imply automatic XML, bartender, or zone-story tracking integration.

[StudioProc](../content/STUDIOPROC.md) is the separate trigger language for
scripted NPC/room behavior. Use its guide for encounters, conditional actions,
and trigger authoring. A script or native procedure called a quest does not
automatically become a stable zone-story catalog definition.

## Verification and maintenance

For documentation changes, run the existing link/anchor and source-contract
suite:

```sh
python3 tests/async/test_documentation_contract.py
```

For behavior/content changes choose the relevant existing check; these commands
are validation entry points, not a claim they were run for every documentation
edit:

- Static staff inspection: `python3 tests/async/test_quest_staff_commands.py`;
  real inspection journey: [run_quest_staff_journey.py](../../tests/async/run_quest_staff_journey.py).
- Bartender policy, rewards, history, and journeys: see the
  [standalone verification guide](BARTENDER_QUESTS.md#verification).
- Tracking/catalog/dailies:
  [test_zone_story_quest_tracking_contract.py](../../tests/async/test_zone_story_quest_tracking_contract.py),
  [test_zone_story_quest_production_catalog.py](../../tests/async/test_zone_story_quest_production_catalog.py),
  [test_zone_story_quest_feature.py](../../tests/async/test_zone_story_quest_feature.py),
  and [test_zone_story_quest_repository.py](../../tests/async/test_zone_story_quest_repository.py).
- XML and epic validation limits and journeys are listed in their dedicated
  [XML](XML_QUESTS.md#verification) and [epic](EPIC_TASKS.md#verification) guides.

When changing a system, recheck both its handler and the registered caller,
backend, configured values, and failure path. A passing parser/helper test does
not establish a working command, durable reward, or production rollout.
