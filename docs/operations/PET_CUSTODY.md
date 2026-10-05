# Durable custody for raised followers

Migration `0028_pet_custody` adds a nullable, unique `player_pets.pet_uid` and
allows owner type 11 in the three item authority tables. Existing pet rows keep
`NULL` and their existing player owned equipment route. The migration and its
verification script are additive and rerunnable on MariaDB 10.11 and MySQL 8.

A raise happens in memory: the raised creature takes what the corpse held, and
the corpse leaves the world. A follower is saved with its master, whose save
records the pet and its items (`player_pets`, `player_pet_items`) and claims
those items. A player's pet equips no hidden (`!show`) item, which an NPC's
corpse can hold: `wear()` refuses it for every command.

A player save verifies every UID, root, parent, and vnum against pet custody
before replacing the pet item projection. A save that omits a pet with a
committed owner revision places its row on `custody_pending` hold instead of
deleting its equipment. A fresh authoritative login is needed before normal
saving resumes after a committed raise whose live publication failed. Repeated
loads and saves must retain one pet record and one copy of each UID.

When a stable raised pet is dismissed or dies, its durably pet-owned live
equipment and inventory are removed before corpse or floor publication. A
return that has already committed player custody is also withheld if its live
callback has not published it yet. The committed pet row and its remaining
pet-owned item graph stay in custody; the next save marks the row
`custody_pending`. These held items do not appear in the room or on a newly
loaded follower. Staff must reconcile the held graph through an explicit
custody transfer before releasing it.

## How long a raised follower lives

A limited lifetime is intended, and has been since 2009. It comes from the corpse
(`raise_undead()` and the other raises in `src/classes/necromancy.c`):

- A corpse gets a decay timer at death: 120 real minutes for a player's corpse and 20 for
  an NPC's (`timer.decay.corpse.pc` and `.npc`).
- A raise reads the minutes the corpse had left and uses them as the charm's duration,
  with a floor of 4. A dracolich, golem, titan or avatar gets half of that plus
  `6000 / INT`.
- The raise also schedules the creature's death shortly after that number of minutes: one
  minute after for the two dracoliches, and 2 to 11 minutes after for the others.
- Preserve (`max(10, level / 2)` game hours) and embalm (`max(50, level * 2)`) lengthen
  the corpse's timer, so they lengthen the follower's life only when cast before the
  raise. Nothing extends it afterwards.
- A caster with the Unholy Alliance innate, or holding or wielding a necromancer globe,
  gets a permanent follower: no expiry and no scheduled death (`setup_pet()`).
- A necromancer's follower whose charm link breaks for any reason dies a minute later
  (`charm_broken()`).

The two timers use different clocks. The charm affect counts game ticks of 75 seconds,
and the death is scheduled in real minutes, so with a long timer the follower dies while
still charmed (a 120-minute corpse gives a charm of 150 real minutes and a death at 122
to 131). The charm only runs out first when the corpse had little time left: under 8 to
44 minutes, depending on the roll.
This is long-standing behaviour, not a regression; making the death wait for the charm
would lengthen every follower's life by about a quarter, which is a balance change.

## Saved state and holds

A summoned follower is saved as the creature that was generated, not as its area
prototype. Each necromancer and theurgist creation path records an explicit kind
(`summoned_pet_kind` in `src/player/pet_restore_state.h`), and `player_pets.restore_state`
(migration `0013_pet_restore_state`) holds a bounded, versioned payload: the generated
name and descriptions, rolled base stats and points, damage dice, classes, race, level,
alignment, size, intrinsic affects, aggression, act flags and undead spell slots.
Equipment is restored through the ordinary item loader, and derived bonuses are
recomputed from the base values, so equipment does not compound across restarts.

The charm and the death are saved as absolute Unix deadlines, so time offline counts, and
zero means permanent. A restore never makes a finite follower permanent because its owner
has since gained a globe or the innate. The kind's cost is the same on a restore as in
`count_undead`, so a restore creates no follower beyond the owner's budget.

When a follower cannot be restored safely, the loader keeps its whole record and item tree
without creating a mobile or live copies of the items. The owner gets a notice, and
`logs/log/file` gets `pet recovery held pid=<pid> pets=<n>`. A held record is written
again by every later pet save, including quit and death, and is never released
automatically, even if the owner's capacity grows.

| `hold_reason` | Meaning |
| --- | --- |
| 1 | A summon prototype saved before generated state existed |
| 2 | Generated state that is malformed, of an unknown version, or does not match the prototype |
| 3 | The saved charm or death deadline has passed |
| 4 | The owner's capacity would be exceeded |
| 5 | The mobile prototype is not available |
| 6 | Custody pending (above) |

Staff review provenance and every equipment UID before deciding what happens to a held
record; there is no command that deletes, hands out or releases one.
[pet-recovery-review.sql](pet-recovery-review.sql) is a read-only report of held rows and
of old summon rows without generated state.

## Rollback and recovery

Do not restore the old owner type checks or drop `pet_uid` while type 11 rows
exist. An older server cannot interpret those owners. First stop writers and
take a verified database backup. Reconcile each pet's UID graph to an explicit
destination under item authority, checking its physical rows and player
snapshot, then confirm no type 11 owners, pet receipts, or pending holds need
replay. Only then can a separately reviewed down migration remove the new
schema. Retaining the additive schema while rolling back application code is
safe only when there are no pet custody records. Never delete a held pet row or
its items merely to clear a load or save error.
