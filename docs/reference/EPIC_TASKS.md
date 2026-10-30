# Epic tasks and errands

Epic tasks are progression obligations in [epic.c](../../src/world/epic.c),
checked on 2026-10-30. They are independent of authored `.qst` quests,
bartender assignments, XML instances, and zone-story achievement credit;
see [QUEST_SYSTEMS.md](QUEST_SYSTEMS.md) for those systems.

## Assignment and saved state

`epic_award_committed()` increments the permanent `TAG_EPICS_GAINED` counter
after a successful non-bottle award. `epic_publish_pvp_award()` does the same
for its PvP publication path. When the counter crosses an `errand_notch`
multiple and the character has no active epic task, it calls
`epic_choose_new_epic_task()`. `epic_initialization()` reads `errand_notch` from
`epic.errandStep`: compiled fallback 200, checked-in configuration 500.
This is cumulative earned epics, not the spendable epic balance; spending
epics does not rewind that counter. One award invokes at most one assignment,
even if it crosses several multiples. An existing active task prevents a new
one rather than creating a queue of future tasks.

The task chooser requires a living PC with no existing `TAG_EPIC_ERRAND`.
Its ordinary roll chooses the zone branch 19 times out of 20 and the alternative
branch once out of 20. A pending zone assignment goes straight back to the zone
branch without rerolling into an easier alternative.

The following affects have duration `-1` and are saved with the player's AFFECTS
component. Task/pending/completed affects use `AFFTYPE_STORE | AFFTYPE_PERM`;
the counter is created by `apply_achievement()` with
`AFFTYPE_NOSHOW | AFFTYPE_PERM | AFFTYPE_NODISPEL`:

- `TAG_EPICS_GAINED`: cumulative counter used for threshold crossings.
- `TAG_EPIC_TASK_PENDING`: an earned zone assignment awaiting catalog/player
  history. This is a pending obligation, not an active task.
- `TAG_EPIC_ERRAND`: the active task. Its modifier encodes the target.
- `TAG_EPIC_COMPLETED`: legacy packed completed-errand data, maintained on
  runestone task completion. Catalog selection uses the separate completed-zone
  read state, not this packed list as its direct input.

Modifier meanings are defined by [epic.h](../../src/world/epic.h):

- A zone number below `SPILL_BLOOD`: find that zone's epic runestone.
- `SPILL_BLOOD` (`10000000`): Spill Blood.
- `SPILL_BLOOD + nexus_id`: convert the specified nexus.
- A negative modifier marks a task received through sharing. Completion checks
  accept the signed or absolute target as appropriate; it cannot be shared onward.

`has_epic_task()` tests only `TAG_EPIC_ERRAND`. A pending affect alone does not
apply the active-task reward penalty. Successful assignment installs an errand,
removes the pending affect, and marks AFFECTS dirty. The character update loop
in [limits.c](../../src/world/limits.c) retries pending assignments automatically;
another stone touch or another epic gain is not required.

## Task-zone catalog and readiness

[epic_task_catalog.c](../../src/world/epic_task_catalog.c) loads a sorted snapshot
from `SELECT number FROM zones WHERE task_zone=1 ORDER BY number`. Full-world
startup calls `epic_task_catalog_refresh()` after zone publication in
[comm.c](../../src/net/comm.c). Paged maintenance uses
`epic_task_catalog_complete()` through the existing scheduler, at a nominal
14,400 event ticks (one hour at four ticks/second). The initial offset and
retries can delay a refresh.

Publication requires 1–1024 strictly increasing positive, loaded zone numbers.
An empty, duplicate, unordered, unloaded, malformed, or oversized candidate is
rejected. A failed refresh retains the last valid snapshot. A valid suffix
cannot replace an invalid preceding page.

`epic_task_catalog_select()` also requires the character's
`gameplay_reads.status == ready`. It uniformly selects among catalog zones
absent from that character's completed-zone read state using reservoir sampling.
Zone epic awards update that state through `gameplay_read_state_add_completed_zone()`;
login hydrates it from retained progression history through
[player_load_repository.c](../../src/player/player_load_repository.c) and
[player_load_materialize.c](../../src/player/player_load_materialize.c).
SQL combines legacy `epic_gain` zone records with ordinary and Divine zone-award
ledger reasons. Thus previously awarded zones are excluded, not merely
previously assigned tasks.

The three selection outcomes have different behavior:

- **selected:** install the chosen zone task.
- **unavailable:** missing/invalid catalog or unready player history; create or
  retain `TAG_EPIC_TASK_PENDING`, keep already-earned epics, and retry later.
- **exhausted:** the catalog and player history are ready, but every catalog zone
  is completed; proceed to the alternative task branch.

An empty catalog is unavailable, not exhausted. The independent initial 5%
alternative roll remains possible even when zone data is unavailable.

Task eligibility is separate from epic payout, stone presence, and the Divine
boon selector. The reviewed roster preserves 107 historical task-zone flags;
do not infer new eligibility from a stone or payout. Use
[EPIC_TASK_ZONES.md](../operations/EPIC_TASK_ZONES.md) for roster provenance,
read-only audit, guarded provisioning, diagnostics, and recovery acceptance.
[EPIC_ZONE_SEED.md](../operations/EPIC_ZONE_SEED.md) describes the separate payout
seed. Production provisioning remains an explicitly authorized operation.

The catalog's boot refresh reports `database_disabled` in a `__NO_MYSQL__`
build, and the maintenance path has no flatfile task-roster implementation.
Flatfile support for epic balances or stone rewards does not imply a working
zone-task catalog. A zone roll can remain pending there; this source does not
provide full epic-task parity between backends.

## Completing each task

### Zone runestone

The player uses `touch <stone>`. `epic_stone()` requires the intended stone,
a charged/unclaimed eligible stone, no fighting in the room, a nonstaff
toucher, and the stone's correct zone. Participants are the toucher and
nonstaff PC group members in the same room, subject to the transaction's
participant limit. Each receives its own captured amount and task comparison.
Ordinary payout calculation and zone/XP participation rules still apply; the
task does not guarantee a fixed number of epics for reaching the room.

A task matches when its modifier or its negation equals the stone's zone.
`prepare_stone_award()` applies `epic.errand.completeBonusMod` and bypasses the
ordinary active-task penalty for that award. On successful publication,
`epic_publish_stone_award()` records the completed errand, removes the matching
task, gives feedback, and publishes epic/level/boon effects. No reward or task
completion is published merely because the touch was submitted.

The zone touch captures all participants, amounts, task modifiers, and stone UID
into one command. Rejection leaves the stone/task unchanged; uncertain outcomes
keep the reservation for coordinator recovery. Claims deduplicate the same
stone UID. New loaded stones have new UIDs. Inspect
[zone_touch_transaction.c](../../src/world/zone_touch_transaction.c),
[zone_touch_command.c](../../src/world/zone_touch_command.c), and
[critical_command_repository.c](../../src/persistence/critical_command_repository.c)
for the command and SQL boundary.

There are two delivery paths in current source:

- Ordinary SQL zone-touch delivery retains committed participant receipts in
  process until an offline character returns, then adds epics in memory and
  applies effects. Unpublished balances and secondary effects held only in this
  pending map are not automatically replayed after a process crash. The durable
  claim/ledger records alone are not a restored player balance.
- Prepared delivery is selected for flatfile or Divine-mode stone awards.
  [divine_boon_delivery.c](../../src/economy/divine_boon_delivery.c) uses a durable
  per-character delivery sequence, ordered receipt application, and a saved
  delivery watermark. STATUS/AFFECTS/SKILLS checkpoints capture the balance and
  task effects together.
  Flatfile's [player-domain repository](../../src/flatfile/flatfile_player_domain_repository.c)
  accepts zone touches with prepared delivery. Legacy unprepared flatfile
  commands are rejected.

The [stone recovery guide](../guides/epic-stone-recovery.md) describes claim and
ordinary SQL receipt behavior. Do not generalize its legacy delivery limits to
prepared receipts, or promise end-to-end task recovery from codec tests alone.

### Spill Blood

When the chooser reaches the alternative branch it normally installs
`SPILL_BLOOD`. Completion is integrated with `submit_pvp_outcome()` and
`combat_outcome_committed()` in [fight.c](../../src/combat/fight.c), rather than
the static/XML quest hooks.

A qualifying PvP award participant with that task receives a 500-epic base
addition before the normal PvP award modifiers, when the epic-award gate in
that path is met. The task-clearing flag travels with the captured combat
outcome. The victim can also satisfy Spill Blood when losing positive frags;
the publication path explicitly acknowledges the victim's own blood. A kill
outside the qualifying PvP/frags path is not sufficient evidence of completion.

The ordinary combat publication removes a still-matching task after committed
outcome delivery. Prepared Divine epic delivery clears it through the durable
delivery path instead. See [combat_outcome_command.c](../../src/combat/combat_outcome_command.c)
and `epic_prepare_pvp_award()` for flags and captured amounts.

### Nexus conversion

Within the alternative branch, a further 10% roll can choose an enemy nexus
when the character is level 51+ and a candidate exists. The task stores
`SPILL_BLOOD + STONE_ID(nexus)`; otherwise it remains Spill Blood. This is
conditional within the alternative branch, not an independent 10% chance on
every assignment.

[nexus_stones.c](../../src/economy/nexus_stones.c), `nexus_stone_epics()`, matches
the converted stone ID for the converter and eligible nonstaff PC group
members in the room. A matching task doubles the random award's **upper bound**,
then removes the affect; it does not simply double every rolled reward.
The lower bound remains `nexusStones.epicsMin`. This older path removes the
task before calling `gain_epic()`, so it does not have the runestone command's
all-or-nothing task/reward boundary.

## Rewards and settings

An unfinished active task scales most ordinary epic sources through
`epic.errand.penaltyMod`, with a minimum of one after that penalty. Exempt types
in `prepare_epic_award()` are RANDOMMOB, STRAHDME, BOTTLE, PVP, SHIP_PVP, and
BOON. A matching runestone completion bypasses the penalty and applies the
completion multiplier. Witch, nexus, epic-bonus, racewar, difficulty, and
applicable Divine modifiers can further affect the actual award.

Relevant checked-in [duris.properties](../../lib/duris.properties) values:

- `epic.errandStep=500` (compiled fallback 200).
- `epic.errand.penaltyMod=0.25` (fallback 0.25).
- `epic.errand.completeBonusMod=2` (fallback 1.5).
- `mobspecs.epicTaskClear.price=2000000` copper (fallback 10000000).
- `nexusStones.epicsMin=15` and `.epicsMax=25` (fallbacks 50 and 70).

These are repository configuration, not verified production settings. The task
multiplier alone does not determine the final stone payout or epic level gain.

## Sharing, viewing, and clearing

`score` displays the active task alongside spendable and cumulative epic totals.
`epic` alone displays the epic-player list; it is not an epic-task journal.
`epic zones` and `epic trophy` are separate zone/progression reports.

`epic share` invokes `do_epic_share()`. The owner must have a positive original
task modifier. It visits consenting PC group members in the same room who
**already have a task**. A recipient's existing Spill Blood or nexus task is
protected. Other existing tasks can be replaced with the negative shared
modifier, preventing onward sharing. There is no bartender share-count setting,
new-quest fee, or daily allowance check in this path. A pending-only character
has no active task to replace and therefore cannot receive one this way.

`clear_epic_task_spec()` in [specs.mobile.c](../../src/specs/specs.mobile.c) is
assigned to mobile VNUM 22428 in [specs.assign.c](../../src/specs/specs.assign.c).
`ask <npc> task` explains the service; `ask <npc> prayer` attempts paid removal.
The NPC must be able to speak, see the character, and find an active task.
It doubles the base price for Spill Blood and increases it by half for a
nexus task whose stone has not reached that side's good/evil alignment threshold.
A missing nexus is rejected for staff attention. Successful clearing removes the task
and deducts money; it is not a task completion or immediate replacement.
Pending-only assignments cannot be cleared through this active-task lookup.

## Diagnostics and persistence limits

`world persistence` exposes `epic_tasks catalog_ready`, active zone count,
`last_refresh`, loaded pending-task count, and `pending_reads_unavailable`.
This distinguishes absent flags from player-read readiness. A failed last
refresh may coexist with a ready retained catalog. The counts describe loaded
characters, not a database-wide audit of every saved task.

First inspect catalog readiness, player history, active/pending affects, and
the normal update-loop retry. Restoring data does not require giving epics
again. Never clear history or re-award a stone to repair an earned pending task.
The provisioning and recovery steps are in
[EPIC_TASK_ZONES.md](../operations/EPIC_TASK_ZONES.md).

Balances and task affects are different persistence concerns. The ordinary
epic transaction changes a balance in memory and queues history; player saves
write balances/affects. The SQL ledger supplies progression reads. Runestone
claims and prepared delivery provide additional command-specific guarantees;
nexus/prayer/sharing paths must not inherit those guarantees by assumption.
See [the critical command pipeline](../persistence/CRITICAL_COMMAND_PIPELINE.md#epic-points-and-frags-live-in-memory)
and [player saves](../persistence/PLAYER_SAVE_PIPELINE.md).

## Verification

- [test_set_based_gameplay_reads.py](../../tests/async/test_set_based_gameplay_reads.py):
  selection/readiness, completed-zone exclusions, saved pending tasks and retry,
  threshold crossings, and zone/alternative roll behavior.
- [test_epic_task_catalog_mysql.py](../../tests/async/test_epic_task_catalog_mysql.py):
  SQL boot, paged refresh/retry, malformed/duplicate rows, and snapshot retention.
  Run under `tests/async/with_disposable_mariadb.sh python3 tests/async/test_epic_task_catalog_mysql.py`;
  the standalone script requires that disposable database environment.
- [test_epic_task_seed.py](../../tests/async/test_epic_task_seed.py): reviewed
  roster and seed CLI contracts. `python3 scripts/epic_task_seed.py check` is a
  local read-only content validation.
- [test_epic_task_recovery_journey.py](../../tests/async/test_epic_task_recovery_journey.py):
  real stone reward, saved pending obligation, scheduled catalog recovery,
  and ready player history in disposable MariaDB. It takes `--server`, default
  `bin/server/dms_new`; it may request a rerun after the legitimate 5%
  alternative roll. It does not establish flatfile catalog support.
- [test_epic_stone_transaction.py](../../tests/async/test_epic_stone_transaction.py)
  and [test_epic_stone_runtime.py](../../tests/async/test_epic_stone_runtime.py):
  command codecs, rollback/replay, admission, publication, and recovery boundaries.

Use isolated test worlds and disposable databases for journeys. Their existence
does not establish current production recovery, live roster configuration, or
that every sharing/nexus/PvP edge has a full gameplay test.
