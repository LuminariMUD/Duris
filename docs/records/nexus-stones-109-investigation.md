# Nexus stone data investigation and recovery options

## Implementation handoff — 2026-10-18

The historical investigation below is retained as dated evidence. Its open design
questions are superseded by [issue #109](https://github.com/LuminariMUD/Duris/issues/109)
and the [implementation plan](../ongoing-projects/plan.md). The current branch implements safe no-stat
sage handling, neutral guardian cleanup and observable loading failures. Migration
`0046_nexus_phase1` provides the insert-only seed. Migration and runtime compatibility
qualification passed on MySQL 8.0, MariaDB 10.11 and MariaDB 11.8, including conflict
refusal, partial/played-state replay, verifier drift and lock lifetime. Both server
backends and native Nexus sanitizer tests pass. Full-world gameplay and production
acceptance are still pending; exact commands/results are maintained in the plan.

Selected configuration:

- Marduk: ID 1, room 130199, epic bonus type 1.
- Enlil: ID 3, stored room 130399, cargo bonus type 3. Keep the existing override
  to Cyric's Revenge interior slot 7. Its active VNUM is dynamic; a missing ship is
  a load failure, with no static-room fallback.
- New rows: neutral alignment, NULL touch timestamp, `stat_affect=0` and
  `affect_amount=0`. Preserve existing 11% rates, 12-day expiry and capture rewards.
  Antu/Ningishzida and additional stat benefits remain excluded.

The seed checks both target rows before either insert, rejects incompatible
configuration or reserved names on other IDs, and preserves legitimate existing
alignment/timestamps and unrelated rows. Existing matching rows are unchanged on
reapply. The immutable verifier proves static configuration and valid alignment;
it deliberately does not require neutral state after play or delete unrelated rows.
The ordinary migration runner now holds its advisory lock throughout apply,
verification and history publication, and detects session loss.

Before rollout, identify the actual process/binary and database, inspect effective
properties, back up the target, and retain these read-only results:

```sql
SELECT DATABASE();
SHOW CREATE TABLE nexus_stones;
SELECT id,name,room_vnum,align,stat_affect,affect_amount,bonus,last_touched_at
FROM nexus_stones ORDER BY id;
```

Use the existing immutable runner and runtime verifier on an isolated clone first.
The new runtime head and compiled header must match the applied ledger. The supported
bootstrap is InnoDB; historical MyISAM data does not justify assuming transactional
rollback. Unexpected live rows require reconciliation, not a destructive reset.

After explicit production approval, use the runner's confirmed target and validated
backup flow during its required quiescent maintenance window. Prepare/build before
that window. Verify the seed and contract, then perform a controlled restart; staff
`nexus reset`/`nexus reload` cannot discover newly inserted SQL rows. Require exactly
IDs 1/3 for this rollout, successful load logs for Marduk at 130199 and Enlil at the
resolved ship VNUM, and actual stone/guardian placement. Complete the plan's
non-staff capture, faction rewards, cooldown, expiration and saved-state restart
checks before closing the issue.

For rollback, save current Nexus state and the exact IDs inserted by the rollout
before stopping writers for a targeted data restore. Preserve unrelated/pre-existing
state and restart to clear the cache. Once migration success is recorded, do not
delete ledger history or assume the old binary can boot against the new head.
Prefer a compatible forward correction. A binary/database downgrade requires a
separately reviewed matching backup restore and accounting for intervening writes.

## Historical investigation — 2026-10-16

Investigated 2026-10-16 against commit
`1dad54760c7f27a24881fd4a41fa59b600937875`.
Related issue: [#109 — Nexus stones missing from game](https://github.com/LuminariMUD/Duris/issues/109).

**The database configured by this checkout contains zero Nexus stone records.**
The server needs those records to create the stones. Current provisioning creates
the table without populating it, and neither the historical repository backup nor
the production backup supplied for this investigation contains the missing rows.
The immediate symptom is therefore explained by missing catalogue data. The
original catalogue, and when or why it became empty, remain unknown.

The practical recovery path is to reconstruct a reviewed catalogue from surviving
code and world evidence, explicitly choosing the values that cannot be recovered.
That would establish a new supported configuration; it would not prove an exact
restoration of the historical game.

## Database evidence

The checkout's `.env` identifies its environment as `production`. A connection
using that configuration executed the following inside a read-only transaction:

```sql
START TRANSACTION READ ONLY;
SELECT COUNT(*) AS stone_count FROM nexus_stones;
SELECT id, name, room_vnum, align, stat_affect, affect_amount, bonus
FROM nexus_stones
ORDER BY id;
COMMIT;
```

The count was **0**, and the row query returned no records. Connection credentials
and database host details are intentionally omitted from this report.

This confirms the state of the configured database, rather than inferring it from
the staff command. The running server's process environment and deployed binary
were not independently matched to this checkout during the quick check. The
reported live symptom is consistent with the queried database.

## Why the stones do not appear

- Normal non-mini startup calls `init_nexus_stones()` in
  [comm.c](../../src/net/comm.c), around line 984.
- The MySQL branch of `load_nexus_stones()` in
  [nexus_stones.c](../../src/economy/nexus_stones.c), around line 217, reads the
  catalogue once at boot. It loads each stone and stores the record in
  `nexus_rows`. An empty result is explicitly accepted as a valid world state.
- `load_nexus_stone()`, around line 1301, creates object VNUM **394**, names it
  from the record, places it in the resolved room, and loads the appropriate
  guardian. The object and guardian templates already exist in
  [heavens.obj](../../areas/obj/heavens.obj) and
  [heavens.mob](../../areas/mob/heavens.mob).
- The staff listing prints `(no stones in database)` when the in-memory vector
  is empty. That message alone could also follow a query or first-row load
  failure; the read-only SQL check supplies the separate evidence of an empty
  persisted catalogue here.
- The MySQL loader stops at the first invalid or unloadable row. Valid catalogue
  contents and successful world placement both need verification after repair.
- The zone resets examined in #109 do not supply the missing catalogue. Spawning
  the base object through a zone reset would not recreate the database records
  used by the Nexus mechanics.

The existing staff reset and reload operations act on configured stones. In the
MySQL branch, `reset_nexus_stones()` respawns from `nexus_rows`; it does **not**
query newly inserted rows. A database repair therefore needs a controlled restart
or a separately implemented and tested catalogue refresh. A restart is the
simpler existing path.

## Repository and history search

The first pass searched the current migrations, scripts, documentation, and Nexus
implementation. The expanded pass searched tracked files, historical paths,
locally available Git refs, historical SQL files, and the historical SQL archive.
The local repository is not shallow. No remote-only or unreachable history was
searched.

| Source | Finding |
| --- | --- |
| [bootstrap_legacy_baseline.sql](../../migrations/bootstrap_legacy_baseline.sql), around line 537 | Creates `nexus_stones`; no seed rows. |
| [bootstrap_multithread_safe.sql](../../migrations/bootstrap_multithread_safe.sql), around line 773 | Contains the schema; no Nexus catalogue seed found. |
| [run_migration.sh](../../migrations/run_migration.sh), around line 2576 | Creates the table if absent. Later timestamp conversion does not populate it. Rerunning these migrations will not restore the stones. |
| Historical versions of `src/duris.sql` | Nexus references found were table definitions, not populated records. |
| History search for Nexus `INSERT`, `REPLACE`, and `COPY` statements in SQL, code, scripts, and text | No matching catalogue population statements found. |
| Historical `archives/sql.tar.gz` | Its `duris_dev_backup.sql` contains an empty Nexus data section: `DISABLE KEYS` is immediately followed by `ENABLE KEYS`, with no inserts. |
| [flatfile_nexus_repository_harness.cpp](../../tests/async/flatfile_nexus_repository_harness.cpp) | Contains synthetic fixtures, including Marduk in room 1001 and Enlil in room 3003. These are test inputs, not authoritative world placements. |

The historical archive's Git blob is
`3fb6a4c3f35d202b2b5740f2109255dd2f7e732b`. Its SQL member is 48,345,270 bytes;
the empty Nexus data section is around lines 907–932. The archive was moved into
`archives/` in commit `7ab89cac9` and removed in `3cb3646e0` on 2026-08-27.

These checks found no recoverable canonical catalogue. They do not establish
that no copy ever existed outside the available repository history.

## Supplied production backup

The user supplied [this Google Drive archive](https://drive.google.com/file/d/1O_8OWi2ySTo7WMseJxEjQLP4ZiDfoYng/view).
It was downloaded to the git-ignored project path
`tmp/DurisMUD-production-database-2026-07-12.tar.xz`.

| Property | Observed value |
| --- | --- |
| Archive size | 15,014,224 bytes |
| SHA-256 | `e3bfb5de3348f04893fc0916e9da6b7095ff0b7d184f34903815d1c9f649b9a7` |
| Integrity | `xz --test` passed |
| SQL member | `prod.sql`, 345,366,975 bytes |
| Filename date | 2026-07-12 |
| SQL dump footer | `Dump completed on 2026-06-23 23:24:20` |
| Nexus data statements | Zero exact `INSERT INTO nexus_stones` or `REPLACE INTO nexus_stones` statements |

The filename date is not the dump's recorded completion date. The SQL footer's
timezone and the reason for the different archive name were not established.
The earlier conversational description of a July 12 backup referred to its
filename; the dump itself records June 23.

The Nexus schema begins at `prod.sql:3242`. Its data section at lines 3256–3262
contains only:

```sql
-- Dumping data for table `nexus_stones`
LOCK TABLES `nexus_stones` WRITE;
/*!40000 ALTER TABLE `nexus_stones` DISABLE KEYS */;
/*!40000 ALTER TABLE `nexus_stones` ENABLE KEYS */;
UNLOCK TABLES;
```

There are no records between those statements. This backup cannot restore stone
identities, locations, bonuses, stat fields, or past alignment/touch state.

To inspect only the relevant section again, without importing the backup:

```bash
tar -xOf tmp/DurisMUD-production-database-2026-07-12.tar.xz prod.sql \
  | sed -n '3236,3262p'
```

## Surviving configuration evidence

[nexus_stones.h](../../src/economy/nexus_stones.h), lines 38–42, preserves four
named IDs:

| ID | Name |
| --- | --- |
| 1 | Marduk |
| 2 | Antu |
| 3 | Enlil |
| 4 | Ningishzida |

[credits](../../lib/information/credits), lines 158–161, also names all four
Reliquary Nexuses. `MAX_NEXUS_STONES` is 9, but that capacity is not evidence that
nine actual records existed.

There is some evidence for bonus assignments: the Nexus bonus table comments
associate Marduk with epics, and the cargo reward message names Enlil. Other
comments use the older name Enki for experience. These fragments are not a
complete, consistent seed definition.

Current [duris.properties](../../lib/duris.properties), lines 2353–2356, contains
bonus rates of 0.110 for epics, 0.150 for experience, 0.110 for cargo, and 0.110
for prestige. These establish configured rates, not which missing row should
select each bonus. Bonus types also include none and random drops in the header.

The following candidate chambers exist in the individual world files. Their
existence and descriptions do not establish a name-to-room mapping:

| Room VNUM | Chamber | Source |
| --- | --- | --- |
| 130199 | The Nexus, in the Reliquary Nexus of Aggression | [nexus_ic.wld](../../areas/wld/nexus_ic.wld), line 2760 |
| 130284 | The Reliquary Nexus of The Dead | [nexus_uc.wld](../../areas/wld/nexus_uc.wld), line 1491 |
| 130399 | The Nexus, in the Corsairs area | [nexus_island.wld](../../areas/wld/nexus_island.wld), line 2405 |
| 130423 | The Nexus of the Roper Den | [nexus_roper.wld](../../areas/wld/nexus_roper.wld), line 404 |

**Enlil has an existing placement override.**
[ship_npc.h](../../src/ships/ship_npc.h), line 77, identifies Enlil as the stone
for Cyric's Revenge. `nexus_to_cyrics_revenge` defaults to true in
[ship_npc.c](../../src/ships/ship_npc.c), line 1913. The stone loader replaces
that record's room with the ship's room slot 7; if the ship is absent, loading
that stone fails. See also [the ship reference](../reference/SHIPS.md#cyrics-revenge-and-the-zone-ship).
Assigning every named stone to a static Nexus chamber would overlook this
existing behavior. Ship availability and initialization order need checking
before a reconstructed catalogue is enabled.

The `stat_affect` field also needs a deliberate valid value. The sage ask/train
paths use it in `char_stat()` and `apply_names[]`; the schema default `-1` is
not sufficient evidence of a valid gameplay configuration. No original
`stat_affect` or `affect_amount` assignments were recovered.

## Recovery options

| Option | What it achieves | Main limitation |
| --- | --- | --- |
| Reconstruct a complete reviewed catalogue | Restores the feature using known IDs, surviving mechanics, and explicitly chosen missing values. This is the recommended path if no further historical source is available. | Room mappings, stat settings, and unsupported bonus assignments become design decisions, not recovered history. |
| Build and verify a small initial catalogue | Establishes working spawn, guardian, touch, reward, and persistence behavior before enabling the remaining stones. | Leaves part of the feature unavailable; the initial records still need reviewed values. |
| Leave Nexus gameplay unavailable deliberately | Avoids choosing replacement gameplay data now. | The issue remains unresolved. Player guidance and any objectives requiring unavailable stones would need review. |
| Seek another historical source if one becomes available | A former maintainer's export, another server's catalogue, or records of actual placements could improve fidelity. | No such source is currently available, and it need not block a reconstruction. |

An indirect search of retained gameplay logs or other backup tables might recover
individual names or placements. That work has not been completed, and such
fragments would still require validation before being treated as a full catalogue.

For reconstruction, prefer the following bounded sequence:

1. Produce a proposed table containing each ID, name, room or ship placement,
   bonus type, stat field, and stat amount. Mark each value as code-supported or
   newly chosen. Do not imply that the four candidate rooms prove four mappings.
2. Choose a fresh starting state, such as neutral alignment and no previous touch
   timestamp. This would be a new initialization policy, not recovered player
   state.
3. Add a versioned seed that can be rerun without overwriting legitimate existing
   records or player-influenced state. Preserve existing bonus rates unless a
   separate balance change is intended.
4. Verify in an isolated local/staging database and full-world server: catalogue
   loading, the Cyric's Revenge dependency, guardian placement, touching/turning,
   rewards, sage stat use, persistence, and cold restart. Confirm that repeated
   provisioning does not duplicate records or reset state.
5. Add an actionable empty-catalogue diagnostic, distinguishing absent data from
   SQL and world-placement failures. Account for intentional empty test worlds;
   an existing regression explicitly expects empty data to be accepted.
6. Present the concrete seed and validation results for production approval,
   then apply the approved change with a backup and controlled restart.

The investigation and documentation requests do not authorize a production seed,
migration, or restart. No proposed catalogue has been selected or implemented.

## Validation and current status

Completed: source and history inspection, the configured database's read-only
count and row query, archive integrity checking, and inspection of both available
backup Nexus sections. Source inspection also established candidate rooms, named
IDs, bonus-rate configuration, and Enlil's ship dependency.

No production database records, server settings, or gameplay code were changed.
The downloaded archive remains in `tmp/`; it was not imported. No server was
restarted and no build or gameplay regression was run for this investigation.
The work remains at diagnosis and recovery planning.
