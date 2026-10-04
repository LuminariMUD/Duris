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
