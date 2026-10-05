# Compatibility playtime

## Contract

Compatibility playtime measures the time a player character remains resident in
the game. It is **not** active-input time, anti-idle time, or the telemetry session
measure ([SESSION_STATE.md](SESSION_STATE.md)).

- The live `player.time.played` value remains the loaded or administrator-set
  baseline. `player.time.logon` remains the existing wall-clock session anchor.
- A save captures baseline plus nonnegative elapsed seconds since that anchor.
  It does not advance either live field. Repeated captures and retries therefore
  cannot compound the same session interval.
- An uninitialized/nonpositive anchor, failed clock, or clock before the anchor
  contributes no elapsed seconds. Values saturate at signed `INT_MAX`, matching
  the SQL column. The live baseline is unsigned; corrupt out-of-range values are
  capped, not reinterpreted as recoverable historical playtime.
- A normal load establishes the captured total as the next baseline and resets
  `logon` to the load time. Time while the character is unloaded is excluded.
- A linkdead character still resident in the world continues accumulating time.
  Reattaching its descriptor does not start a new accounting interval. This
  preserves the existing score/logon convention rather than introducing a new
  activity policy in a compatibility fix.
- Staff-set baselines and the existing `EQ_WIPE` offset remain in the stored
  baseline. Display code continues subtracting the offset where it already did.
  This work does not move the equipment-wipe/login workflow or infer missing
  historical offsets.

`player/player_playtime.h` owns the shared calculation, and the immutable capture
calls it. A later write must not replace an elapsed total with the old live
baseline.
The retired regular-player flat-file fallback is not revived or redesigned.

## Checkpoint ownership and bounded loss

The existing `persistence_checkpoint.c` owner marks **status only** before a
periodic checkpoint, including otherwise quiet characters. It retains the
existing eight-player continuation batches, runtime-ID re-resolution, and wipe
suppression of new dirty marks. No unrelated gameplay mutation is needed to
persist elapsed time; no new timer or telemetry writer is introduced.

The scheduler starts this job after five seconds and repeats it after thirty
seconds, plus continuation/scheduler delay. Under healthy operation a crash can
lose the still-uncaptured tail since the last checkpoint. This is not a hard
thirty-second durability guarantee: capture refusal, writer backlog, or an
unhealthy scheduler can enlarge the exposure. Existing queue/health diagnostics
remain authoritative. Capture adds no main-loop I/O and no durability fence.

A save writes the captured total, so writing the same save again cannot compound
it. A crash loses the totals the writer had not yet written.

## Focused verification


```sh
python3 tests/async/test_player_playtime_capture.py
python3 tests/async/test_playtime_checkpoint.py
python3 tests/async/test_playtime_flatfile.py
```

- Controlled-clock capture: 3,600 + 600 = 4,200; repeat saves; terminal/death
  intent; resident linkdead time; reload/offline exclusion; clock/range guards;
  staff baseline and wipe-offset arithmetic; unchanged live time fields.
- Quiet checkpoint: no unrelated dirty components, repeated cycles, eight-player
  continuation boundary preserved.
- Real flat-file repository: full baseline, status-only elapsed update, duplicate
  and stale revisions, reload with a fresh session anchor.

With a disposable loopback MariaDB (the journey also runs in `make test-db`):

```sh
TEST_DB_HOST=127.0.0.1 TEST_DB_USER=<fixture-user> TEST_DB_PASSWORD=<fixture-password> \
  python3 tests/async/test_mysql_playtime_journey.py --server bin/server/dms_new
```

The journey creates its own uniquely named schema, applies the tracked schema and
migrations only there, and removes that schema afterward. It never reads `.env`.
Its SQL repository subtest uses connection-private temporary tables. The gameplay
journey checks explicit/repeated/quiet saves, resident link loss and reconnect,
terminal quit, restart, death/reload, acknowledged-save crash recovery, and
playtime across a real live copyover. A synthetic offline fixture character is
promoted only to invoke the copyover command; the runtime executable is copied
inside the disposable fixture directory.

After the copyover the test checks the preserved connection's save and then closes
the fixture connection; it does not test the account menu.

Build the changed C++ code with `make -C src`. Both MariaDB and flat-file backend
builds must pass; use a separate `DMS_BINARY` for the latter to avoid replacing the
binary used by the SQL journey.

## Historical data

No migration or historical repair is performed. Old stored totals may omit prior
sessions or reflect legacy/wipe/admin conventions. Do not treat them as verified
active time or backfill guessed seconds; the calculation affects future captures
only. Telemetry sessions must not reuse the field as their accumulator.
