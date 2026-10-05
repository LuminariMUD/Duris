# Experience trophy observation and checkpoint persistence

The first restoration stage tracks accepted PvE experience in memory. It does not
reduce XP, apply familiarity decay, or enable the historical trophy penalties.
Tracking is off by default. The existing `trophy frags` command remains separate.

## Operation

Set `exp.zoneTrophy.observe` to `1` through the normal `properties` command to
collect totals; `0` stops collection without deleting saved history. For example:

```text
properties set exp.zoneTrophy.observe 1
trophy
properties set exp.zoneTrophy.observe 0
```

Use the existing property save workflow if the setting should survive a restart.
The checked-in `lib/duris.properties` sets observation to zero. Only the exact
value `1` enables it.

`trophy` shows the saved/in-memory totals and explicitly states that no XP penalty
applies. Staff can inspect `trophy <character>` or `trophy <character> frags`.
Names come from the loaded world table; removed zones show their number with an
unknown-zone label. These displays perform no zone metadata queries.

## What is counted

- PCs level 25 through the mortal maximum, excluding illithids.
- Positive, accepted damage, melee, tanking, healing, and NPC-kill XP awards.
- Healing identifies PvE using the patient's current opponent. Player opponents
  and player-owned NPC opponents are excluded.
- The final integer award, after the existing modifiers and per-award clamp, only
  inside the branch that actually changes `GET_EXP(ch)`. Awards rejected at the
  character XP cap, zero/negative awards, PvP, quests, world quests, resurrection,
  and death adjustments do not accumulate.
- The recipient's room at credit time determines the zone. Observation includes
  all valid loaded zones on both backends, independently of SQL `zones.trophy_zone`.
  That flag belongs to future enforcement policy; there is no lazy SQL query on
  a cache miss in the XP path.

These are raw XP counters, not normalized familiarity, candidate multipliers, or
immutable analytics events. Existing persisted totals are preserved and may
include historical data. A later enforcement rollout must not assume that these
counters form a clean baseline or silently reinterpret them as normalized units.

One character stores at most 1,024 zone entries. Each total saturates at `INT_MAX`
to preserve the existing SQL and snapshot representation without overflow. New
zones beyond the bound are not recorded; existing entries can still increase.
Allocation failure skips optional observation without interrupting the accepted
XP award. Tracking does not change another zone's total or average group history.

## Persistence and database cost

`record_zone_trophy_award()` mutates only game-thread memory and reports whether
it changed. `gain_exp()` marks `PLAYER_COMPONENT_STATUS` and, if needed,
`PLAYER_COMPONENT_TROPHIES` in the same player revision. It performs no trophy
SQL and creates no per-award save job.

The existing `dirty-player-checkpoint` job runs on a 30-second fixed-delay cycle,
processing eight characters per batch and continuing the remaining batch on
later ticks. Only dirty components are captured. The existing immutable snapshot
pipeline queues them on the one persistence writer.
Other explicit or terminal checkpoints can save earlier; a long cycle or queue
backlog can save later. No second trophy timer or worker is introduced.

SQL login now reads all trophy rows for the player in one query, with the same
bounded load transaction as the other components. The full query budget increases
from 23 to 24. Negative totals, invalid zone identifiers, or too many entries
refuse the load rather than silently truncating saved state. Materialization also
checks the entry bound, including flatfile loads.
The trophy query returns at most 1,025 rows: 1,024 allowed entries plus one to
detect excess history. This bounds MySQL's result buffer before row validation.

The existing SQL snapshot transaction writes XP and replaces that player's trophy
rows together. It performs one trophy `DELETE` and, for a nonempty collection,
one batched `INSERT`, without one `SELECT` per zone. An empty component deletes
old rows. Writing the same save again is harmless; with one writer there is no
revision fence. Flatfile snapshots use
the same trophy component and codec. There is no schema or snapshot-format change.

Character resets and class changes clear the in-memory collection and mark XP/status
and trophies dirty instead of deleting SQL rows behind the checkpoint writer.
Existing character-erasure and fenced season-reset behavior remains responsible
for global lifecycle cleanup.

The old trophy modifier, intermediate XP hooks, legacy per-zone saver/loader, and
database-only decay implementation are removed. The maintenance job ID remains
reserved, disabled in the registry, and completes without SQL even if dispatched.
`exp.zoneTrophy.enabled` and the old threshold/scale/reduction/update properties
cannot reactivate penalties or a competing database writer. Epic trophies are
unaffected.

Changes held only in memory can be lost before a durable checkpoint, and a crash
loses a captured snapshot the writer had not yet applied. Observe actual unacknowledged age through existing save
diagnostics rather than treating the nominal interval as a durability guarantee.

## Verification

```sh
make -C src
python3 tests/async/test_experience_trophy.py
python3 tests/async/test_player_revision_state.py
python3 tests/async/test_player_save_worker.py
python3 tests/async/test_player_save_pipeline.py
python3 tests/async/test_player_load_pipeline.py
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_maintenance_scheduler.py
bash tests/async/run_experience_trophy_mysql.sh
```

The SQL wrapper creates a disposable Docker database, applies the fresh schema
and migrations, and uses synthetic accounts. It never sources the checkout's
`.env`. It exercises checkpoint/reload, a repeated save, rollback
of XP and trophies on an insert failure, empty collection persistence, and the
existing SQL login harness including bounds and malformed trophy rows.

## Not built

Observation is accumulation only. Familiarity decay, a penalty curve and its
enforcement, zone eligibility by `trophy_zone`, and player-facing multiplier feedback
are not built ([#24](https://gitlab.com/max757/duris/-/work_items/24)). Do not restore the SQL decay sweeps.
