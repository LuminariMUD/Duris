# Merge Request !1 Adversarial Review

**Merge request:** `max757/duris!1`

**Reviewed head:** `cef782686f2a23e3454c6a731a3fe40683c02914`

**Base:** `96c8ff02ffa5eea75a6fdd4c099d13845f22af21`

**Result:** Three high-severity findings.

## 1. A failed player rename can strand the ship under a nonexistent owner

**Location:** `src/net/modify.c:1678-1682`. The ship has already been committed
under `new_name` before `sql_player_rename()` runs. The same failure pattern is
present in the locker rollback at `src/net/modify.c:1687-1699`.

**Impact:** A database failure during a rename can leave the player under the
old name and the ship under the unused new name. The player then loses access
to the ship. The split is durable when the first ship write committed.

**Repro:** Run the real `rename_character()` and `rename_ship_owner()` with a
fault-injected store where the first ship write succeeds, the player rename
fails, and the compensating ship write also fails. This is the ordinary shape
of a database outage that begins after the first write. The function returns
failure with the player still named `Oldname`, while the live ship and its
durable row remain owned by `Newname`. `get_ship_from_owner("Oldname")` then
returns null.

```text
After failed player rename and failed compensation: player=Oldname db_player=Oldname ship=Newname db_ship=Newname
```

The locker-failure path has the same data-integrity risk if either compensating
write fails. Logging that compensation failed does not restore ownership.

**Fix:** Make the player-row rename and ship-row owner update one database
transaction. Keep the old in-memory ship owner/name snapshot and restore it
locally on rollback, without requiring another database write. Do not report a
failed rename until durable player and ship ownership are still on the same
name. Add fault cases for failure of each statement, `COMMIT`, and rollback or
compensation.

## 2. A lost COMMIT acknowledgement makes a new ship permanently unsaveable

**Location:** `src/sql/sql_player.c:10955-10961`.

**Impact:** A newly inserted ship can become unsaveable until reboot, losing
all later ship changes. The live ship forgets its database ID even though its
row exists, so every retry collides with `UNIQUE(owner_name)`.

**Repro:** MySQL or MariaDB can apply `COMMIT` and lose the response, for
example when the connection drops after the server commits. In that state
`sql_commit()` returns false even though the row exists. Run the real
`sql_save_ship()` against a fault-injected transaction that applies `COMMIT`
but returns failure. The new failure branch resets the live ship to
`db_id == -1`; the next retry takes the insert path and collides with the
existing row.

```text
After COMMIT applied but reply lost: row_exists=1 db_id=-1
Retry success=0 insert_attempts=2
```

The added regression test models only the unambiguous rollback outcome, so it
does not cover this failure.

**Fix:** Treat a failed `COMMIT` as an unknown outcome. Reconcile the row by the
unique owner key before deciding whether the in-memory ID exists, or make the
first-save operation idempotent with an upsert that returns the existing or
inserted ID. Add both fault cases: `COMMIT` rejected and rolled back, and
`COMMIT` applied with its response lost.

## 3. Loading every row can exhaust the ship-room pool and leave crashable ships

**Location:** `src/sql/sql_player.c:11148-11171`. The resulting invalid state is
created through `src/ships/ship_base.c:1623-1632` and dereferenced during
shutdown at `src/ships/ship_base.c:625-636`.

**Impact:** A sufficiently populated `ships` table can cause an out-of-bounds
world access during normal shutdown. It can also permanently consume rooms
claimed by a partially allocated layout during the running process.

**Repro:** The merge request removes the 512-row ceiling, but each loaded ship
consumes 2-15 rooms from the fixed 4,997-room range `60003..64999`. Run the real
`sql_load_all_ships()`, `load_ship()`, `set_ship_physical_layout()`, and
`shutdown_ships()` with persisted frigates, which consume nine rooms each. At
512 rows the harness exits cleanly. At 700 rows the pool is exhausted; 145
ships remain registered with `LOADED` restored from their persisted flags and
at least one `roomnum == -1`. Orderly shutdown then evaluates
`world[real_room(-1)]`, producing an AddressSanitizer heap-buffer-overflow.

```text
rows=512 load_result=1 created=512 loaded_with_invalid_rooms=0
rows=700 load_result=1 created=700 loaded_with_invalid_rooms=145
ERROR: AddressSanitizer: heap-buffer-overflow
READ ... in shutdown_ships() at ship_base.c:627
```

`sql_load_all_ships()` logs `load_ship()` failure and continues without
erasing or deleting the ship. `set_ship_physical_layout()` also leaves any
rooms claimed before exhaustion marked as occupied. The new greater-than-512
behavior therefore creates a deterministic boot/shutdown crash for plausible
hull mixes.

**Fix:** Make physical-layout allocation atomic: reserve all required rooms
before mutating the world, or unwind every claimed room on failure. On any
`load_ship()` failure, remove and destroy the partially loaded ship before
continuing, or fail boot cleanly. Clear transient `LOADED` before attempting
placement rather than trusting the persisted bit. Add a test that exceeds room
capacity and then walks and shuts down the registry under AddressSanitizer;
asserting only that every owner row was visited is insufficient.

## Verification evidence

The merge request's 13 focused ship tests all passed, including its seven new
regressions. The three findings above exercise failure states those tests do
not model.

The fault-injection harnesses compiled the real changed functions with C++20
and AddressSanitizer/UndefinedBehaviorSanitizer. The room-capacity harness was
also run at the old 512-row boundary as a control and completed without an
invalid room or sanitizer error.
