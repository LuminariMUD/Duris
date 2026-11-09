# No-rent flag fixes

Status: planned, not started. No GitHub issue filed yet.
Date: 2026-11-09.
Source inspected: local checkout at `08587b61c`.

## Outcome and scope

A no-rent item should never stay with a character through rent, camp or
link-death. When a character leaves that way, each no-rent item falls to the
floor with a message, or crumbles if it can't be on the floor. Keys follow the
same rule. Lockers stop storing no-rent items, and normal items inside a no-rent
bag are never lost.

Crashes, restarts and copyovers keep today's protection. No migration or
production cleanup is needed.

## What happens today

Tested on a disposable MariaDB server with a full world:

| Scenario | Result |
|---|---|
| No-rent item picked up, then rent | Gone, as intended |
| No-rent key at the inn, even after a trip through a locker | Destroyed, as intended today |
| Flame blade spell, then rent | Gone, as intended |
| No-rent item put in a locker, taken back out, then rent twice | **Kept** |
| No-rent eyeglasses bought from a shop, then rent | **Kept** |
| Previously saved banana put in a no-rent bag, then rent | **Banana lost** with the bag |

The existing `test_norent_key_rent_journey.py` also passed on MariaDB.

Causes:

- A save only drops a no-rent item if it has no ownership record, and it doesn't
  check who the record names
  ([player_snapshot_capture.c:370](../../src/player/player_snapshot_capture.c#L370)).
  That exception is deliberate, so a stray flag can't delete real items.
  [Issue #419](https://github.com/LuminariMUD/Duris/issues/419) reported the same
  problem, and its fix covered keys only.
- Locker saves don't filter the flag
  ([locker_async.c:498](../../src/persistence/locker_async.c#L498)), so storing an
  item gives it an ownership record.
- Shops and other creation grants create the record at delivery
  ([shop.c:345](../../src/economy/shop.c#L345)).
- A skipped no-rent bag takes its whole contents with it
  ([player_snapshot_capture.c:377](../../src/player/player_snapshot_capture.c#L377)).
- Nothing tells the player, and the Locker help says the opposite
  ([duris_help_parsed.hlp:15787](../../help/duris_help_parsed.hlp#L15787)).

Scale in the built world: 1,387 of 19,334 prototypes are no-rent. All 929 keys
become no-rent when created
([objconv.c:226](../../src/item/objconv.c#L226)). 12 no-rent containers can be
picked up.

## Decisions (owner, 2026-11-09)

1. Rent, camp and link-death remove every no-rent item. They fall to the floor
   with a message. This replaces the earlier warn-and-repeat idea.
2. Keys fall too. Destroying keys at the inn goes away.
3. No cleanup of no-rent items players already have.
4. Remove the flag from the three non-key items sold for money (section 5).
   Everything else keeps it, including soulbound gear, summoned books and totems,
   and conjured weapons, which can all be re-summoned or recast.

## Changes

Sections 1 and 2 must ship together. Without section 1, removing the key rule
would let keys with an ownership record survive rent.

### 1. Take no-rent items off before leaving

Add one static helper above `persistence_save_character_terminal`
([actoth.c:2337](../../src/cmd/actoth.c#L2337)) and call it first when the type is
`RENT_INN`, `RENT_CAMPED` or `RENT_LINKDEAD`. Every intentional exit already goes
through that function:

| Exit | Where | Type |
|---|---|---|
| Inn rent | [specs.room.c:368](../../src/specs/specs.room.c#L368), [:447](../../src/specs/specs.room.c#L447) | `RENT_INN` |
| Staff camp shortcut and quit | [actoth.c:305](../../src/cmd/actoth.c#L305), [:1894](../../src/cmd/actoth.c#L1894) | `RENT_INN` |
| Camp finishing | [affects.c:3856](../../src/magic/affects.c#L3856) | `RENT_CAMPED` |
| Idle or link-dead void | [limits.c:2116](../../src/world/limits.c#L2116) | `RENT_LINKDEAD` |
| Staff `extractlink` | [actwiz.c:13269](../../src/cmd/actwiz.c#L13269) | `RENT_LINKDEAD` |

`RENT_CRASH` and `RENT_DEATH` are unchanged. Idle voiding shares the link-death
type, so a connected player who idles out is treated the same way.

Rules, for worn items, carried items and items inside bags, staff included:

- Normal items inside a no-rent bag move to the nearest surviving container, or
  to inventory if there is none. Then the bag comes off.
- The item lands with `obj_to_room`, and logs with `redis_log_floor_drop` as the
  `drop` command does. Tell the character and the room, for example
  "`$p` is no-rent and falls to the floor."
- These crumble with a message instead: `ITEM_NODROP` (39 prototypes) and
  `ITEM2_SOULBIND`, because they can't be dropped, and anything when the character
  is in a locker room or `NOWHERE`.
- Transient items need no special case. `obj_to_room` already dissolves them.

`purge_drop_item` ([actwiz.c:5306](../../src/cmd/actwiz.c#L5306)) is the closest
existing shape, including its warning that `obj_to_room` can free or redirect the
object. Its rules differ, so it can't be reused directly.

### 2. Remove the key special case

Once items are off before the save, this code has nothing to do:

- `rent_keys`, `keys_only` and `rent_key` in
  [player_snapshot_capture.c](../../src/player/player_snapshot_capture.c), and the
  `save_intent == RENT_INN` argument at line 870.
- The `rent_keys` parameter and the `RENT_INN` argument in
  [player_snapshot_repository.c](../../src/player/player_snapshot_repository.c)
  (lines 660, 665, 808).
- `item_claim_is_norent_key` and its comments in
  [item_claim.h](../../src/item/item_claim.h).
- The `rent_keys` parameter and destruction branch in
  [item_claim_repository.c](../../src/item/item_claim_repository.c) and its header.

Keep `item_claim_leaves_out`, so keys already recorded as destroyed stay destroyed.

### 3. Keep bag contents on other saves

Crash saves and checkpoints still skip a no-rent bag with no ownership record, but
its contents must be saved. In `capture_item_tree`, when an item is skipped, walk
its contents with the skipped item's `parent_index` and equipment slot 0. Move the
depth and cycle checks above the skip so a malformed tree still fails.

### 4. Lockers refuse no-rent items

`StorageLocker::LockerToPFile`
([storage_lockers.c:3988](../../src/item/storage_lockers.c#L3988)) runs on every
locker save and on leaving. At its start, when a locker user is present, walk the
room contents, including chests and bags:

- A no-rent item goes back to the user with `obj_to_char` and a notice.
- A no-rent item without `ITEM_TAKE` is discarded. 55 of the 147 no-rent locker
  rows in the local database are blood stains.
- Only touch a private chest the user can open, and record the take with
  `LockerMovementAudit` so the chest log stays accurate.

This also returns items already stored, the next time someone visits, so decision
3 needs no separate code. The existing artifact check isn't enough because it only
sees the top level of the room. Leave
[locker_async.c:498](../../src/persistence/locker_async.c#L498) as it is, so a
no-rent item in a private chest the visitor can't open stays stored.

### 5. Three shop items lose the flag

Change the extra-flags field (7th number), then run `make world`:

| Item | Line | Now | New |
|---|---|---|---|
| Oil lamp (44824) | [evkeep.obj:361](../../areas/obj/evkeep.obj#L361) | 8675344 | 286736 |
| Drider-skin flask (402054) | [library.obj:502](../../areas/obj/library.obj#L502) | 8396800 | 8192 |
| Gnomish eyeglasses (120015) | [surfacekeeps.obj:235](../../areas/obj/surfacekeeps.obj#L235) | 8388608 | 0 |

Their shop prices will roughly double, because `convertObj` halves the computed
cost of no-rent items ([objconv.c:312](../../src/item/objconv.c#L312)). Copies
already bought keep their saved flag and fall at the next rent.

### 6. Help and docs

- In `help/duris_help_parsed.hlp`, correct the Locker sentence and add one sentence
  to Rent and Camp saying no-rent items fall to the floor when you leave.
- Rewrite the key disposal section of
  [DATABASE.md](../reference/DATABASE.md) (lines 363-379), and update the no-rent
  paragraph in [LEGACY_STARTER_KITS.md](../reference/LEGACY_STARTER_KITS.md).

## Tests

Build with `make -C src`, format with `./scripts/format.sh`, and run journeys with:

```bash
tests/async/with_disposable_mariadb.sh python3 tests/async/test_norent_key_rent_journey.py --backend mariadb --server bin/server/dms_new
```

Rework `test_norent_key_rent_journey.py`, keeping the filename because three test
lists name it. Keys now land on the floor instead of being destroyed. Add these
cases:

- Non-key no-rent item falls, with and without an ownership record.
- Shop-bought no-rent item falls.
- Worn item, and item inside a normal bag, fall.
- Saved item inside a no-rent bag survives, and the bag falls.
- No-drop item crumbles.
- Locker hands back a no-rent item, from the floor and from a chest.
- Mortal `camp`, with `camp.timer` lowered in the run root's properties.
- `extractlink <name>` on a link-dead character.
- The existing crash and copyover checks stay as they are.

Also update:

- `test_player_snapshot_capture.py` (lines 303-396): replace key-carry cases with
  bag-contents cases.
- `player_save_claim_mysql_harness.cpp` (lines 971-1060): remove key disposal and
  keep the existing destroyed-item behavior.
- `test_player_save_claim.py` (line 23).

These must still pass: `test_terminal_save_safety.py`,
`test_terminal_extract_item_retention.py`, `test_copyover_custody.py`,
`test_locker_async_pipeline.py`, `test_mysql_locker_grant_journey.py` and
`test_storage_chest_crash_journey.py`.

## Accepted behavior and limits

- Floor items last until someone takes them or the server restarts, so a player
  can relog and pick one up. They can already do this by dropping it by hand.
- Soulbound gear, summoned books and totems, and conjured weapons will now vanish
  at rent. From the code they survive today, though only the shop route was run
  live.
- 139 quest rewards are no-rent and keep the flag: 83 keys, mostly tokens and notes
  otherwise. The 15 that can be worn or wielded are 10 sword fragments, a signet
  ring, two broaches, an onyx orb and a kearonor hide.
- Unchanged: auction, collector, enhancement and quest reward filters, corpses,
  saved rooms, and `convertObj` flagging keys.
- Production data was not checked. The counts above come from the built world
  files and the local database.
