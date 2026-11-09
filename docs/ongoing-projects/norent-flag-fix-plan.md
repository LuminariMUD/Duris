# No-rent flag fixes

Status: built and tested. All four stacked pull requests are open for review.
Date: 2026-11-09.
Source inspected: `master` at `fa173cbad`, then merged up to `ddbcaa90a`.

## Progress

Each row is one pull request, stacked on the one above it. Nothing is left to build:
merge them in order, top row first. Line numbers below are from before this work.

| PR | Sections | Branch | State |
|---|---|---|---|
| [#933](https://github.com/LuminariMUD/Duris/pull/933) | 1, 2, 3 and their tests | `branch/norent-flag-fix` | In review |
| [#937](https://github.com/LuminariMUD/Duris/pull/937) | 4 (lockers) | `branch/norent-flag-fix-lockers` | In review |
| [#939](https://github.com/LuminariMUD/Duris/pull/939) | 5 (seven items, auction refusal) | `branch/norent-flag-fix-items` | In review |
| [#940](https://github.com/LuminariMUD/Duris/pull/940) | 6 (help and docs) | `branch/norent-flag-fix-help` | In review |

Notes from building so far:

- `test_norent_key_rent_journey.py` covers the shop case with the obsidian key
  (5783, sold in room 5848), because the eyeglasses lose the flag in section 5. Its
  camp and `extractlink` cases use a second, mortal character in room 1457.
- No artifact prototype is no-rent, and the coin pile isn't, so section 1 has no
  coin or artifact handling.
- Section 4 tests a public chest made with `eq sort none`. Private chests use the
  existing `locker_container_access_allowed` check, which a leave invalidates first,
  so a private chest is only cleared while the visitor has it open.

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
4. Remove the flag from the three non-key items sold for money, and from Ensis
   Unguis, Lancea Cineralae, Simulacrum Anguis and wind blade, which are meant to
   last (section 5). Everything else keeps it, including soulbound gear and summoned
   books and totems, which can be re-summoned.
5. Flame blade and holy blade stay no-rent, and their help changes to say so
   (section 6). Doom blade is included because holy blade runs the same spell code.

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
- These crumble with a message instead: `ITEM_NODROP` (36 prototypes once section
  5 is done) and `ITEM2_SOULBIND`, because they can't be dropped, and anything when
  the character is in a locker room or `NOWHERE`.
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

### 5. Seven items lose the flag

Change the extra-flags field (7th number) of each prototype below, then run
`make world`.

Three shop items:

| Item | Line | Now | New |
|---|---|---|---|
| Oil lamp (44824) | [evkeep.obj:361](../../areas/obj/evkeep.obj#L361) | 8675344 | 286736 |
| Drider-skin flask (402054) | [library.obj:502](../../areas/obj/library.obj#L502) | 8396800 | 8192 |
| Gnomish eyeglasses (120015) | [surfacekeeps.obj:235](../../areas/obj/surfacekeeps.obj#L235) | 8388608 | 0 |

Their shop prices will roughly double, because `convertObj` halves the computed
cost of no-rent items ([objconv.c:312](../../src/item/objconv.c#L312)). Copies
already bought keep their saved flag and fall at the next rent.

Three conjured weapons, to match the help published in
[#912](https://github.com/LuminariMUD/Duris/pull/912). The flag is in the prototype
and is also added when the spell runs, so both must go:

| Weapon | Prototype line (8470984 becomes 82376) | Code line to delete |
|---|---|---|
| Ensis Unguis (56) | [heavens.obj:821](../../areas/obj/heavens.obj#L821) | [magic.c:29561](../../src/magic/magic.c#L29561) |
| Lancea Cineralae (93) | [heavens.obj:1212](../../areas/obj/heavens.obj#L1212) | [magic.c:29614](../../src/magic/magic.c#L29614) |
| Simulacrum Anguis (171) | [heavens.obj:2096](../../areas/obj/heavens.obj#L2096) | [magic.c:29667](../../src/magic/magic.c#L29667) |

They stay out of auctions, the collector, enhancement and quest rewards, because
they remain no-drop and no-sell and can't be picked up.

Wind blade (98), to match its "Permanent" help. Only the spell sets the flag, so
delete [ethermancer.c:803](../../src/classes/ethermancer.c#L803) and leave the
prototype alone. Unlike the three above it isn't no-drop, so losing the flag would
let it be auctioned. Add `ITEM_TRANSIENT` to the auction refusal
([auction_houses.c:872](../../src/economy/auction_houses.c#L872)). Shops, the
collector, enhancement and quest rewards already refuse transient items, and this
also stops other transient items being listed.

Copies of all four already conjured keep their saved flag, so under decision 3 they
are lost once at the next rent. Any copy conjured after this ships lasts.

### 6. Help and docs

- Locker, Rent and Camp help exists in both `lib/information/help_index` (LOCKER
  STORAGE sentence at line 10264, RENT at 13740, CAMP at 2168) and
  `help/duris_help_parsed.hlp` (Locker sentence at line 15787, Rent, Camp), and both
  are imported. In both files, correct the Locker sentence and add one sentence to
  Rent and Camp saying no-rent items fall to the floor when you leave.
- Say that these three weapons don't outlast the session. They are no-rent and
  transient, so they are gone once you rent, camp or lose your link:

  | Spell | Change | Where |
  |---|---|---|
  | Flame blade | Duration "Forever" becomes "Until you leave the game" | `help_index:6371`, `duris_help_parsed.hlp:10162` |
  | Holy blade | "remains until lost or destroyed" becomes "remains until lost, destroyed or you leave the game" | `help_index:24821` |
  | Doom blade | Duration "Forever" or "Permanent" becomes "Until you leave the game" | `help_index:4657`, `duris_help_parsed.hlp:7483` |
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
- Each of the four conjured weapons in section 5 survives rent.
- The auction house refuses a transient item.
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
`test_locker_async_pipeline.py`, `test_mysql_locker_grant_journey.py`,
`test_storage_chest_crash_journey.py`, `test_issue_550_conjuration_runtime.py` and
`test_wind_blade_creation_runtime.py`.

## Accepted behavior and limits

- Floor items last until someone takes them or the server restarts, so a player
  can relog and pick one up. They can already do this by dropping it by hand.
- Soulbound gear and summoned books and totems will now vanish at rent. From the
  code they survive today, though only the shop route was run live.
- Flame blade, holy blade and doom blade already vanish at rent, by test for flame
  blade and by code for the other two. Only their help changes.
- 139 quest rewards are no-rent and keep the flag: 83 keys, mostly tokens and notes
  otherwise. The 15 that can be worn or wielded are 10 sword fragments, a signet
  ring, two broaches, an onyx orb and a kearonor hide.
- Unchanged: the no-rent checks in auctions, the collector, enhancement and quest
  rewards, plus corpses, saved rooms, and `convertObj` flagging keys.
- Production data was not checked. The counts above come from the built world
  files and the local database.
