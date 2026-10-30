# Zone-story quest tracking contract

## Scope

The tracker is seasonal and character/PID-based. The current production adapter
covers static `.qst` completion blocks. Bartender quests, epic tasks, XML
instances, and arbitrary native/StudioProc content do not automatically enter
this catalog. See [QUEST_SYSTEMS.md](QUEST_SYSTEMS.md) for the system boundaries.

Ordinary static completion tracking has no assigned-run lifecycle: there is no
acceptance, sharing, expiry, or abandonment record. A successful completion
produces one logical completion transaction. The separate optional
[daily layer](ZONE_STORY_QUEST_DAILY.md) does have an assignment/expiry record.

## Definitions

A quest definition is an eligible, stable piece of zone content. It has a stable definition ID, zone, source, completion identity, and content revision.

A completion transaction is the atomic fact that one definition was completed and a set of characters received credit in the room at that moment.

All current production definitions are repeatable. The first completion of a
definition for a PID in a season contributes to zone percentage; later
completions remain activity history but do not increase the distinct-definition
numerator. Giver VNUM plus canonical give/receive/disappear fields identify a
definition; see [the catalog reference](ZONE_STORY_QUEST_CATALOG.md).

## Credit modes

- `PERSONAL`: direct completer.
- `SOLO`: the transaction had exactly one credited PID.
- `GROUP_PARTICIPANT`: a credited recipient on a multi-recipient transaction.
- `LEADERSHIP`: the direct completer on a multi-recipient transaction.

Modes are overlapping bits: a direct solo completer gets PERSONAL and SOLO;
a direct group completer gets PERSONAL, GROUP_PARTICIPANT, and LEADERSHIP.
LEADERSHIP here does not require being the group's leader pointer. Other
recipients get GROUP_PARTICIPANT. Multiple bits still represent one definition.

Credit is per character PID. Account-wide and lifetime aggregation are future derived views, not initial storage semantics.

## Progress

```text
distinct definitions credited to PID in season
/
eligible definitions in zone and content revision
```

The denominator comes from the catalog, not from completion rows.

## Transaction boundary

The recipient set must be captured at completion time. Later code must not infer recipients by scanning the room again or consulting a changed group leader pointer.

`record_legacy_completion()` captures the direct nonstaff PC plus distinct
nonstaff PC group members in that room. NPCs, staff, and members elsewhere are
excluded. The transaction stores the definition, zone, direct PID, recipient
PIDs, room VNUM, completion timestamp, season, and content revision. Its ID is
idempotent: reusing an ID with different encoded transaction data is a conflict.

The runtime season is the SQL epoch when available, then positive
`ZONE_STORY_SEASON_ID`, then 1. A change to the current revision must not be
treated as an automatic migration of stored state.

## Storage and failure boundary

The runtime serializes completions, credit, names, observations, and daily state
as one service-state document. Flatfile atomically replaces
`<FLATFILE_ROOT>/domains/zone-story-quests.state` with a checked envelope. SQL
uses `zone_story_quest_state` from migration `0026_zone_story_quest_state`; saving
enqueues a whole-state upsert. This enqueue does not acknowledge a database commit.
Immediate save/enqueue rejection restores the previous in-memory state; later
SQL writer failures are logged asynchronously without an in-memory rollback.

The logical transaction groups recipients' tracking credit. It does not make
the legacy offering consumption, item creation, XP, or money reward atomic.
The `.qst` handler logs a tracking failure and still runs its legacy reward path.
The [daily reference](ZONE_STORY_QUEST_DAILY.md) documents saved-state and reward
idempotency limits.
