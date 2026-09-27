# Ship gameplay reference

This is the staff and balance reference for ships as players experience them:
where to buy them, every command, the hull, weapon, equipment and crew
catalogues, the cargo economy, and what everything costs. The engine behind it
(lifecycle, heartbeat, combat maths, persistence, NPC AI) is in
[SHIPS.md](SHIPS.md).

All numbers are copied from `src/ships/ship_variables.c`, `ship_cargo.c`,
`ship_shop.c` and `src/specs/specs.assign.c` at commit `2209da668`. Prices are
shown in platinum. The tables store copper, and 1000 copper is 1 platinum. A
"tick" is one second. The "hours" the shipwright quotes are mud hours of 75
seconds, so 75 ticks make one quoted hour.

Players read the in-game `help ship` topics and `help ships` (see
[SHIPS.md](SHIPS.md#known-issues-and-discrepancies) for where those have drifted
from the code).

## Contents

- [Where ships are sold](#where-ships-are-sold)
- [Commands](#commands)
- [Hulls](#hulls)
- [Weapons](#weapons)
- [Equipment](#equipment)
- [Crews and chiefs](#crews-and-chiefs)
- [Cargo and contraband](#cargo-and-contraband)
- [Costs and timings](#costs-and-timings)
- [Runtime properties](#runtime-properties)

## Where ships are sold

A **shipwright** is a room with `ship_shop_proc`. You can buy a first ship at
any of them. Every other service needs your ship docked in that room. The ten
**ports** are the shipwrights that also trade cargo, and they are the only
places customs inspects a docking ship.

| Room | Location (area file) | Port |
|-----:|----------------------|------|
| 559633 | A Fiord Inlet Harbor (`surface.wld`) | Flann |
| 635260 | Slow, Leisurely River (`newbiemaps.wld`) | Dalvik |
| 88846 | A Small Pier (`menden.wld`) | Menden |
| 82669 | The Myrabolus Ship Yard (`mira.wld`) | Myrabolus |
| 66689 | End of The Docks (`torrhan.wld`) | Torrhan |
| 9967 | The Sarmiz'Duul Ship Yard (`sarmiz.wld`) | Sarmiz'Duul |
| 22441 | The Northern Docks (`stormport.wld`) | Storm Port |
| 49090 | On the Merchant Dock (`desert.wld`) | Venan'Trut |
| 43158 | The Construction Pier, Thur'Gurax Port (`shipy.wld`) | Thur'Gurax |
| 83786 | The Ship Yard of Deramuth Port (`alatorin.wld`) | Deramuth |
| 43118 | The Pier of Hull Construction, Canderthal Harbor (`shipy.wld`) | |
| 43198 | The Hull Construction Pier, Fenaline Shipyard (`shipy.wld`) | |
| 1719 | The Docks of Quietus Quay (`quietus.wld`) | |
| 55410 | The Dockyard On A Large Pier (`wh.wld`, Winterhaven) | |
| 8287 | The Far East Sea Dock (`sylvandawn.wld`) | |
| 76659 | A Pier (`jade.wld`) | |
| 584171 | The Shores of Black Sand (`surface.wld`) | |
| 258421 | The Azure Waters of a Stormy Sea (`surface2011.wld`) | |
| 140854, 133051 | The Ocean (`Duris3.wld`) | |
| 70501 | A Gaping Hole in the Side of a Pirate Ship (`raxquest.wld`) | |

Ships can also dock at any `ROOM_DOCKABLE` room they maneuver into. That gives
no services beyond a safe berth.

## Commands

### At a shipwright

Anyone can `list` and buy a first hull. Everything else acts on your own ship,
which (except for `list`, `summon` and `sell ship`) must be docked in this room
and not undocking. Maintenance blocks `buy hull`, `buy cargo`,
`buy contraband`, `sell` and `summon`. Battle stations block `sell` and
`summon`.

| Command | Effect |
|---------|--------|
| `list [hulls\|weapons\|equipment\|cargo]` | Catalogues. Hull prices are shown as upgrade differences if you own a ship. `list cargo` shows this port's prices and the profit on your hold. |
| `buy hull <n> <name>` | First ship. `<n>` is the list number. The name takes colour codes. |
| `buy hull <n>` | Change hull class. The hold must be empty and the fit-out legal for the new hull. Everyone is put ashore and weapons carry over. |
| `buy weapon <n> <fore\|rear\|port\|starboard>` | Mount a weapon on an arc. |
| `buy equipment <n>` | Fit a ram, levistone or diplomat's flag. |
| `buy cargo <crates>` / `buy contraband <crates>` | Load this port's goods. Contraband needs reputation (see [Contraband](#contraband)). |
| `buy rename <name>` | Rename the ship for 10% of the hull's list price. |
| `buy swap <slot> <slot>` | Swap two slots, mounting position included. |
| `sell cargo` / `sell contraband` / `sell <slot>` | Sell goods, a weapon or a piece of equipment. The diplomat's flag cannot be sold while you carry cargo. |
| `sell ship` | Disabled. |
| `repair all` | Everything at once. |
| `repair sail`, `repair armor <side\|all>`, `repair internal <side\|all>`, `repair weapon <slot>` | Individual repairs. |
| `reload all` / `reload <slot>` | Refill ammunition. |
| `summon ship` / `summon time` | Send for the ship, or ask how long it will take (see [Summoning](#summoning)). |

### At a crew hall

A crew hall is a room with `crew_shop_proc`. You must own a ship.

| Command | Effect |
|---------|--------|
| `list` | Crews and chiefs on offer here, then your current crew sheet. |
| `hire <n>` | Hire the numbered crew or chief. The price is paid in coins. |

### On board

Bridge commands work in the room with the control panel (the bridge). `order`,
`lock` and `fire` need the captain, a group-mate of the online captain, or an
immortal. Any passenger may use `look` and `scan`.

| Command | Effect |
|---------|--------|
| `look ship` / `look status` | Main status display: armour, internals, sail, crew, slots, target, heading and speed. |
| `look crew`, `look cargo`, `look weaponspec` | Crew sheet, manifest and coffers, weapon specifications. |
| `look contacts` / `look c` | Ships within 35 rooms (+0–2 for scout crews). Docked ships beyond 5 rooms are hidden. |
| `look tactical [<x> <y>]` / `look t` | Hex chart centred on the ship, or on a point within contact range. |
| `look sight <slot>` / `look weapon <slot>` | Displayed hit chance for one weapon against the locked target. |
| `look commands` | This list, in game. |
| `look show` | Raw ship dump. |
| `scan [<id>]` | Lookout report on the target or a contact within 20 rooms: armour, weapons, flag. |
| `order heading <0-360\|n\|ne\|e\|se\|s\|sw\|w\|nw\|h>` | Set the course (`h` holds the current heading). |
| `order speed <n\|max\|med\|min>` | Set the speed. Open sea only. |
| `order sail <heading\|n\|e\|s\|w> <0-35>` / `order sail off` | Autopilot to a room up to 35 away. |
| `order maneuver <n\|e\|s\|w>` / `order m` | Move one room in a harbour or zone water, at speed ≤ 20. Docks on entering a dockable room. |
| `order undock` | Leave port (30 ticks) or weigh anchor (13 ticks). |
| `order anchor` | Stop and anchor. The crew repairs faster. |
| `order ram` / `order ram off` | Arm or disarm ramming (needs a target and speed ≥ 20). |
| `order jettison <cargo\|contraband> [n]` / `order j` | Throw goods overboard. About half float as crates. |
| `order salvage [n]` | Hook floating crates aboard. The ship must be stopped. |
| `order fly` / `order land` | Levistone flight. |
| `order signal <id> <message>` | Message a same-race ship within 20 rooms. |
| `order maproom` | Show the room the ship is in. |
| `order <anything else>` | Falls through to the normal `order` command for followers. |
| `lock <id>` / `lock off` | Choose or clear the gunnery target. Docked ships cannot be locked. |
| `fire <slot\|fore\|port\|starboard\|rear>` | Fire one weapon or a whole arc. |
| `get money` / `get coins` | The owner collects salvage and bounty from the coffers. |
| `look out` | View outside the ship, from any interior room. |
| `disembark` | Leave by the entrance or an outer-edge room. Cruisers and Dreadnoughts only through the docking bay. Not while flying. |

From outside, `enter <ship keyword>` boards a ship in the same room. The
keywords are `ship`, the class name and the owner's name. You cannot board a
ship that is flying, a warship that is moving, or any other ship going faster
than 9, unless it is sinking.

### Immortal commands

| Command | Effect |
|---------|--------|
| `world cargo [reload\|reset\|save\|update]` | Show both price grids, re-read the market, flatten it to 1.0, write it, or force a drift tick. |
| `set ship <owner> frags <n>` | Set ship frags. |
| `set ship <owner> guns\|repair\|sail <amount>` | Train a crew skill. These do not queue a save, so the change persists on the next save or at shutdown. |
| `setbit ship <owner> <field> <value>` | Set a raw field: `armor0`–`armor3`, `mxarmor0`–`mxarmor3`, `intern0`–`intern3`, `mxintern0`–`mxintern3`, `sail`, `money`, `frags`, `maxspeed`, `capacity`, `air`, `crew`, `chief` or `clearchiefs`. |
| `rename ship <owner> <new name>` | Rename without charge. |
| `fire pirate\|hunter\|escort [level]` | At any panel, spawn an NPC ship of that type near this ship. |
| `lock ai_off\|ai_pirate\|ai_hunter\|ai_escort\|ai_advanced\|ai_basic` | Attach, retype or remove an NPC brain on the ship at this panel. |
| Hold object 1223, then `look cargo` / `look ships` | Cargo price grid, or every ship with its room and state. |
| Object 1203, `say ship all\|owner <old> <new>\|delete <owner>` | List ships, transfer ownership, or delete a ship. |

Immortals also skip build times, undock in 2 ticks, summon instantly (even at
battle stations), maneuver without cooldown, board moving or flying ships, and
bypass the contraband requirements and the captain check. An
immortal on an NPC ship's bridge counts as its captain, so the AI keeps running
after the captain dies.

## Hulls

`list hulls` numbers hulls from 1 (class index + 1). Merchants carry cargo.
Warships carry none but have more armour and mounts for their weight.

| # | Hull | Kind | Price | Min level | Hull weight | Max load | Cargo | Contraband | People | Max speed | Turn/tick | Accel/tick | Free fit-out weight | Free cargo weight | Max sail | Rooms |
|--:|------|------|------:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Sloop | merchant | 100 | 0 | 10 | 5 | 1 | 0 | 1 | 100 | 50° | 35 | 0 | 0 | 20 | 2 |
| 2 | Yacht | merchant | 300 | 0 | 25 | 12 | 3 | 0 | 2 | 100 | 45° | 28 | 2 | 0 | 40 | 3 |
| 3 | Clipper | merchant | 1,500 | 20 | 110 | 55 | 10 | 1 | 5 | 88 | 30° | 22 | 8 | 6 | 90 | 4 |
| 4 | Ketch | merchant | 2,500 | 25 | 150 | 75 | 20 | 3 | 8 | 78 | 20° | 17 | 10 | 8 | 100 | 4 |
| 5 | Caravel | merchant | 4,000 | 30 | 200 | 100 | 35 | 6 | 10 | 68 | 13° | 13 | 13 | 12 | 110 | 7 |
| 6 | Carrack | merchant | 8,000 | 35 | 260 | 130 | 50 | 9 | 15 | 58 | 8° | 10 | 16 | 24 | 120 | 8 |
| 7 | Galleon | merchant | 12,000 | 40 | 330 | 165 | 70 | 12 | 20 | 50 | 6° | 8 | 19 | 40 | 130 | 10 |
| 8 | Corvette | warship | 9,000 | 31 | 165 | 82 | 0 | 0 | 6 | 74 | 20° | 20 | 13 | 0 | 120 | 5 |
| 9 | Destroyer | warship | 15,000 | 36 | 220 | 110 | 0 | 0 | 8 | 64 | 13° | 14 | 16 | 0 | 130 | 8 |
| 10 | Frigate | warship | 22,000 | 41 | 285 | 142 | 0 | 0 | 10 | 55 | 8° | 10 | 20 | 0 | 140 | 9 |
| 11 | Cruiser | warship | 36,000 | 46 | 400 | 200 | 0 | 0 | 15 | 48 | 5° | 8 | 25 | 0 | 160 | 12 |
| 12 | Dreadnought | warship | not for sale | 51 | 600 | 300 | 0 | 0 | 20 | 40 | 4° | 6 | 32 | 0 | 200 | 15 |
| 13 | Large Ship | NPC only | — | 51 | 600 | 300 | 0 | 0 | 20 | 40 | 4° | 6 | 32 | 0 | 200 | 2 |

- A price of 0 means not for sale to mortals. `buy hull` never accepts the last
  class. The epic-point cost column is 0 for every hull, so no hull purchase
  uses the epic-transaction path today.
- Hull weight sets the repair stock, frags for sinking the ship, crash hits,
  summon price, ram size and levistone weight. Its square root (`√hull`) scales
  stamina costs and the size bonus to be hit.
- Max load is the weight budget for weapons, equipment and cargo (each crate
  weighs 2). Weight above the free allowances slows the ship linearly (see
  [SHIPS.md](SHIPS.md#movement-model)). The `_slots` column in the source is
  unused: every hull has 16 slots.
- The Magical Automatons crew, Mirabolan Merchants (+10% cargo) and the
  speed-bonus crews change these figures. The helm's `SEADOG` innate adds 2 to
  max speed.

### Arcs, mounts and armour

Each arc lists its maximum number of weapon mounts, the maximum weapon weight
on that arc, its armour and its internal structure. Two arcs with armour and
internals both at zero sink the ship. One makes it immobile.

| Hull | Mounts F/P/R/S | Arc weight F/P/R/S | Armour F/P/R/S | Internal F/P/R/S |
|------|----------------|--------------------|----------------|------------------|
| Sloop | 0/0/0/0 | 0/0/0/0 | 2/3/1/3 | 1/1/1/1 |
| Yacht | 1/1/1/1 | 3/5/3/5 | 6/8/4/8 | 3/4/2/4 |
| Clipper | 1/2/1/2 | 10/13/10/13 | 29/36/18/36 | 14/18/9/18 |
| Ketch | 1/2/1/2 | 13/20/13/20 | 40/50/25/50 | 20/25/12/25 |
| Caravel | 1/3/1/3 | 17/26/17/26 | 53/66/33/66 | 26/33/16/33 |
| Carrack | 1/3/1/3 | 21/31/21/31 | 69/86/43/86 | 34/43/21/43 |
| Galleon | 2/3/1/3 | 26/35/26/35 | 88/110/55/110 | 44/55/27/55 |
| Corvette | 1/3/1/3 | 13/32/13/32 | 50/63/37/63 | 22/27/13/27 |
| Destroyer | 2/3/1/3 | 27/38/27/38 | 67/84/50/84 | 29/36/18/36 |
| Frigate | 2/3/2/3 | 31/44/31/44 | 87/109/65/109 | 38/47/23/47 |
| Cruiser | 2/4/2/4 | 35/50/35/50 | 122/153/91/153 | 53/66/33/66 |
| Dreadnought, Large Ship | 3/5/2/5 | 51/75/51/75 | 183/229/138/229 | 79/99/49/99 |

The in-game list shows weapons as F/S/R/P, fore, starboard, rear and port.
Port and starboard are always equal.

## Weapons

`list weapons` numbers weapons from 1. Damage is per fragment. `n×` means n
fragments per shot, each landing separately.

| # | Weapon | Price | Weight | Ammo | Range | Damage | Spread | Sail hit | Hull / sail damage | Armour pierce | Reload | Flight at max range |
|--:|--------|------:|---:|---:|------|------|---:|---:|------|---:|---:|---:|
| 1 | Small Ballista | 50 | 3 | 60 | 0–8 | 2–4 | 10° | 12% | 100% / 50% | 10% | 30 | 7 |
| 2 | Medium Ballista | 100 | 6 | 50 | 0–10 | 4–6 | 10° | 14% | 100% / 50% | 10% | 30 | 8 |
| 3 | Large Ballista | 500 | 10 | 30 | 0–12 | 6–9 | 10° | 16% | 100% / 50% | 10% | 30 | 10 |
| 4 | Small Catapult | 500 | 10 | 30 | 4–15 | 4× 2–3 | 160° | 20% | 100% / 100% | 2% | 30 | 18 |
| 5 | Medium Catapult | 800 | 13 | 20 | 5–20 | 5× 2–4 | 260° | 20% | 100% / 100% | 2% | 30 | 24 |
| 6 | Large Catapult | 1,200 | 17 | 12 | 6–25 | 6× 2–5 | 360° | 20% | 100% / 100% | 2% | 30 | 30 |
| 7 | Heavy Ballista | 1,000 | 15 | 6 | 0–4 | 15–22 | 10° | 0% | 100% / 0% | 15% | 30 | 3 |
| 8 | Light Beamcannon | 4,000 | 7 | 40 | 0–20 | 16→4 by range | 10° | 10% | 100% / 30% | 15% | 45 | 0 |
| 9 | Heavy Beamcannon | 5,000 | 9 | 40 | 0–23 | 22→5 by range | 10° | 10% | 100% / 30% | 15% | 45 | 0 |
| 10 | Mind Blast Cannon | 4,000 | 5 | 50 | 0–20 | crew stun | 360° | — | — | — | 45 | 0 |
| 11 | Fragmentation Cannon | 5,000 | 7 | 20 | 0–16 | 5× 4–6 | 90° | 50% | 50% / 100% | 0% | 45 | 12 |
| 12 | Long Tom Catapult | 5,000 | 9 | 6 | 12–32 | 8× 3–6 | 360° | 20% | 100% / 100% | 3% | 45 | 36 |

- **Spread** scatters where each fragment lands around the firing bearing, so
  360° weapons can hit any arc.
- **Reload** is in ticks, cut by up to about 15% by gunnery skill and lengthened
  by fatigue. **Flight** is in pulses (quarter seconds) and scales with range.
- **Ballistic** weapons (catapults and the Long Tom) care most about closing
  speed. Direct-fire weapons care most about crossing speed (see
  [SHIPS.md](SHIPS.md#hit-chance)).
- A **flying** ship is 4 squares up, and ranges include that: a surface ship
  three squares away is five from it, and a weapon that reaches 4 or less
  cannot hit it from the water. Two flying ships are level with each other.
- A **warship's** sails take 85% of every sail hit
  (`warship.sails.damage.reduction`), before Ship Damage Control.
- The **Mind Blast Cannon** does no damage. A hit stuns the crew for
  `5 + 15 × range factor` ticks (no steering, firing, reloading or repair) and
  knocks everyone aboard down inside mid-range.
- **Capital** weapons (Light and Heavy Beamcannon, Mind Blast, Fragmentation,
  Long Tom) are limited to **one capital item per ship**, and the levistone
  counts too. They also require ship frags **or** gunnery skill of at least
  1600, 1800, 1700, 1900 and 2000 respectively.

Where each weapon can go:

| Weapon | Arcs | Hulls |
|--------|------|-------|
| Small Ballista | all four | Yacht and up |
| Medium Ballista | all four | Clipper and up |
| Large Ballista | all four | Ketch and up |
| Small Catapult | fore, rear | Clipper and up |
| Medium Catapult | fore, rear | Ketch and up |
| Large Catapult | fore, rear | Caravel, Carrack, Galleon, Destroyer and up (not Corvette) |
| Heavy Ballista | port, starboard | Caravel, Carrack, Galleon, Destroyer and up (not Corvette) |
| Light Beamcannon | all four | Ketch and up |
| Heavy Beamcannon | all four | Carrack, Galleon, Destroyer and up |
| Mind Blast Cannon | all four | Clipper and up |
| Fragmentation Cannon | fore, rear | Ketch and up |
| Long Tom Catapult | fore, rear | Carrack, Galleon, Frigate, Cruiser, Dreadnought |

"And up" follows the list order, so "Destroyer and up" means Destroyer,
Frigate, Cruiser and Dreadnought.

## Equipment

One of each item per ship. It occupies a slot but no arc.

| # | Equipment | Price | Weight | Hulls | Effect |
|--:|-----------|------:|--------|-------|--------|
| 1 | Bronze Plated Ram | hull weight (Galleon: 330) | `(hull + 10) / 24` | Clipper and up | Extra fore hit when ramming, halves fore-arc crash damage taken. |
| 2 | Zentharium Levistone | 5,000 (needs 1000 ship frags) | `(hull + 50) / 40`, 0 while flying | Clipper and up | `order fly`: 60 ticks of flight at 4 squares' altitude, 600 ticks to recharge. Capital. |
| 3 | Diplomat's Flag | free | 0 | all | Pirate ambushes become far rarer (1 in 60,001 per tick instead of 1 in 1,001 with the shipped properties). Cruising NPC ships will not choose you as a target, though ambushers spawned for you still attack. Those ambushers lose any mind blast cannon. Cargo sales pay 10% less. |

Equipment installs instantly: its table weight is 0, and install time is
computed from that weight.

## Crews and chiefs

A ship always has one crew. Its three skills (deck, guns, repair) train with use
and never fall below the crew type's base. Hiring a new crew keeps your
training, less 1–5%, floored at the new base. Chiefs speed up training in their
department, add to its modifier, and raise the crew to their minimum skill four
times faster. See [SHIPS.md](SHIPS.md#crew-model) for the formulas.

**Hiring a crew** needs the price in coins and **either** ship frags of at
least the crew's "frags" figure **or** current deck, guns and repair skills all
at or above the new crew's base. **Hiring a chief** needs the price and
**either** the frags **or** your crew's skill in the chief's department at or
above the chief's minimum.

Crew halls on the good side (43220, 43222, 133075, 28197) turn away racewar-evil
characters. Evil-side halls (43221, 9704, 22481, 22648) turn away good
characters. Room 77 lists every crew and chief.

### Crews

| Crew | Level | Base deck/guns/repair | Stamina | Modifiers deck/guns/repair | Price | Frags | Bonus | Hired at |
|------|---:|------|---:|------|---:|---:|------|------|
| Amateur Crew | 1 | 0/0/0 | 500 | 0/0/0 | — | — | | Every new ship starts with it. |
| Sturdy Whalers | 1 | 0/0/0 | 750 | 0/0/0 | 1,000 | 0 | | 43220 Bar of Endless Seas (`shipy`) |
| Strongarms of Ghore | 1 | 0/0/0 | 780 | 0/0/0 | 1,000 | 0 | | 43221 Tavern of Cairme BloodFang (`shipy`) |
| Evermeet Coasters | 1 | 100/120/120 | 625 | 0/1/1 | 2,000 | 90 | | 43222 Martinek's Clam House (`shipy`) |
| Tharnadian Riggers | 1 | 150/80/100 | 600 | 1/0/0 | 1,600 | 80 | | 133075 (Tharnadia) |
| Sarmiz'Duul Scallywags | 1 | 150/100/80 | 600 | 1/0/0 | 1,600 | 80 | | 9704 The Old Scallywag Pub |
| StormPort Bucaneers | 1 | 100/140/100 | 625 | 0/2/0 | 2,000 | 100 | | 22481 Storm Port inn |
| Tekan Madcaps | 2 | 550/450/400 | 700 | 1/1/0 | 5,000 | 350 | | 28197 Verspin, A Private Room |
| Juggernaught Deserters | 2 | 500/500/350 | 725 | 1/1/0 | 5,000 | 360 | | 22648 Stronghold (temporary room) |
| Quietus Powder Monkeys | 2 | 500/800/400 | 750 | 0/2/0 | 6,000 | 500 | Scout +1 | 1734 Quietus, A Dark Tavern |
| Torrhan Black Gang | 2 | 550/450/750 | 750 | 0/0/2 | 6,000 | 450 | Hull repair ×2 | 66735 Tilby's Tavern |
| Winterhaven Seamans | 3 | 1350/1250/1350 | 800 | 1/0/1 | 9,000 | 900 | | 55418 Winterhaven backroom |
| Venan'Trut Royal Shipwrights | 3 | 1250/1300/1750 | 900 | 0/0/4 | 10,000 | 1000 | Speed +1, hull repair ×2 | 49051 Venan'Trut tap room |
| Jade Teikoku Norikumiin | 3 | 1350/1500/1500 | 900 | 1/2/2 | 10,000 | 1000 | Sail repair ×3 | 76859 Jade Shipworks Guild |
| Mirabolan Merchants | 3 | 1550/1300/1250 | 850 | 2/0/0 | 11,000 | 1000 | Cargo +10% | 82641 Myrabolus tavern |
| Boyard Naval Guard | 3 | 1450/1650/1300 | 900 | 1/3/0 | 11,000 | 1100 | Weapon repair ×3 | 38107 Boyard shipping office |
| Corwell Sea Dogs | 3 | 1500/1550/1250 | 800 | 2/2/0 | 12,500 | 1200 | Scout +1 | 54240 tent at the Fiord |
| Ceothian Seafarers | 3 | 1600/1350/1250 | 800 | 3/0/0 | 12,500 | 1200 | Scout +2 | 81021 Ceothia, Golden Cat Inn |
| Magical Automatons | 4 | 3000/3000/2000 | 1500 | 3/3/2 | 40,000 | 3000 | Scout +2, speed +1 | Erzul (automatons quest), or room 77 |

The "level" shown is the table level + 1, and the table level also adds to all
three modifiers. Crews with no price cannot be hired by mortals: the Northshore
Pirates, Twilight Cove Bucaneers, Marauders of the Four Winds, Dark Sun
Syndicate and Scions of the Abyss crew NPC ships. The Automatons come from the
automatons quest: fuse two moonstone fragments with the core from Cyric's
Revenge, then `ask erzul automatons`.

### Chiefs

| Chief | Department | Min skill | Training bonus | Modifier | Price | Frags | Hired at |
|-------|------------|---:|---:|---:|---:|---:|------|
| Deck Cadet | deck | 200 | +10% | +1 | 800 | 120 | 43222, 133075 |
| Rugged Helmsman | deck | 200 | +10% | +1 | 800 | 120 | 9704, 22481 |
| Gunner Cadet | guns | 250 | +10% | +1 | 1,200 | 150 | 43220, 133075 |
| Experienced Canoneer | guns | 250 | +10% | +1 | 1,200 | 150 | 1734 |
| Shipwright Tyro | repair | 220 | +10% | +1 | 1,000 | 130 | 43220 |
| Dock Carpenter | repair | 220 | +10% | +1 | 1,000 | 130 | 9704 |
| Old Quartermaster | deck | 800 | +25% | +2 | 3,000 | 540 | 1734, 82641, 55418 |
| Master Gunner | guns | 1000 | +35% | +2 | 4,000 | 700 | 54240, 22481 |
| Veteran Boatswain | repair | 900 | +30% | +2 | 3,500 | 640 | 43221, 66735, 55418 |
| Chief Mate | deck | 2000 | +50% | +3 | 7,500 | 1350 | 81021, 133075 |
| Elite Gunner | guns | 2500 | +70% | +3 | 9,000 | 1640 | 76859, 38107 |
| Expert Engineer | repair | 2200 | +60% | +3 | 8,000 | 1480 | 49051, 76859 |

All chiefs are also listed in room 77. A new chief replaces the current chief
of the same department.

## Cargo and contraband

### Ports and goods

Each port produces one cargo and one contraband commodity. "Port" and
"commodity" share the same index.

| # | Port | Cargo | Base price | Contraband | Base price | Frags for contraband |
|--:|------|-------|---:|------------|---:|---:|
| 0 | Flann | Cured Meats | 42 | Ancient Books and Scrolls | 192 | 150 |
| 1 | Dalvik | Exotic Foods | 46 | Exotic Herbs | 202 | 150 |
| 2 | Menden | Pine Pitch | 40 | Exotic Oils | 176 | 100 |
| 3 | Myrabolus | Elven Wines | 56 | Elvish Antiquities | 196 | 150 |
| 4 | Torrhan | Bulk Lumber | 36 | Rare Magical Components | 214 | 200 |
| 5 | Sarmiz'Duul | BlackSteel Ingots | 44 | Rare Dyes | 183 | 100 |
| 6 | Storm Port | Bulk Coal | 38 | Rough Diamonds | 220 | 200 |
| 7 | Venan'Trut | Silk Cloth | 52 | Rough Rubies | 204 | 150 |
| 8 | Thur'Gurax | Copper Ingots | 48 | Underdark Mithril | 190 | 150 |
| 9 | Deramuth | Dwarven Mithril | 69 | White Dragon Eggs | 312 | 250 |

### Appetites

`cargo_location_mod[]` is the heart of the trade game. It gives each port's
appetite, as a percentage, for every other port's goods. Rows are the port
buying from you, columns the goods' origin:

| Buyer ↓ / goods → | Fla | Dal | Men | Myr | Tor | Sar | Sto | Ven | Thu | Der |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Flann | — | 254 | 190 | 214 | 225 | 311 | 211 | 249 | 272 | 200 |
| Dalvik | 254 | — | 286 | 178 | 235 | 257 | 275 | 296 | 201 | 208 |
| Menden | 190 | 286 | — | 246 | 271 | 290 | 179 | 185 | 297 | 252 |
| Myrabolus | 214 | 178 | 246 | — | 273 | 287 | 290 | 247 | 239 | 289 |
| Torrhan | 225 | 235 | 271 | 273 | — | 308 | 224 | 254 | 203 | 313 |
| Sarmiz'Duul | 311 | 257 | 290 | 287 | 308 | — | 243 | 276 | 314 | 386 |
| Storm Port | 211 | 275 | 179 | 290 | 224 | 243 | — | 231 | 271 | 184 |
| Venan'Trut | 249 | 296 | 185 | 247 | 254 | 276 | 231 | — | 252 | 297 |
| Thur'Gurax | 272 | 201 | 297 | 239 | 203 | 314 | 271 | 252 | — | 281 |
| Deramuth | 252 | 207 | 283 | 309 | 351 | 325 | 406 | 264 | 317 | — |

The same matrix applies to contraband. It was tuned against sailing distances
(see `calculate_port_distances()`, now dormant), so longer runs generally pay
more.

### Prices

Per crate, where `mod` is the live market modifier for that port and
commodity:

- **Buying** at the producing port: `base × mod[port][port]`.
- **Selling** at another port: `1.5 × base(origin) × appetite / 100 × mod[port][origin]`.
- **Selling back** to the producing port: half its current asking price.

Adjustments on a sale:

| Adjustment | Cargo | Contraband |
|------------|-------|------------|
| Warship hull ("obviously stolen") | −40% | −40% |
| Diplomat's Flag | −10% | none |
| `SEADOG` innate | +10% | none |
| Nexus bonus (`NEXUS_BONUS_CARGO`) | applied to the total | applied to the total |

Cargo purchases also apply the `EPIC_BONUS_CARGO` discount. Players see cargo
prices from a **delayed** copy of the market, refreshed every
`ship.cargo.updateDelayedPrices.secs`, so nobody can trade on a move the moment
it happens. Immortals and contraband use live prices.

### Market movement

- Buying multiplies the port's own modifier by `1 + buyAdjustMod × crates`.
  Selling multiplies the buyer's modifier for that commodity by
  `1 − sellAdjustMod × crates`. Contraband moves several times further per crate.
- Every `ship.cargo.update.secs` each modifier drifts towards its neutral point
  by `(distance + 0.1) × rate`, without overshooting. The neutral point is
  `sellPriceMod` for a port's own goods and `buyPriceMod` for everything else,
  both 0.6 as shipped, so an untouched market settles at 60% of the formula
  prices.
- Every modifier is held inside its band, `minPriceMod`–`maxPriceMod`
  (cargo 0.54–0.69 around its 0.60 neutral point, contraband 0.85–1.3), on
  load, after each trade and after each drift. A heavy trade stops at the edge
  of the band instead of crashing or inflating the price.
- `world cargo reset` puts every modifier to 1.0, which the cargo band then
  holds at 0.69 until drift brings it back to 0.60.

### Capacity, jettison and salvage

- A crate weighs 2. The free space is the lesser of the hull's cargo rating
  (+10% with Mirabolan Merchants) minus the load, and the remaining weight
  budget divided by 2.
- `buy cargo` and `buy contraband` stack onto an existing slot of the same
  goods and record the invoice, so `list cargo` can show profit. Only then do
  they take an empty slot.
- **Jettison** drops crates over water, and each has a 50% chance to float as a
  salvageable crate. Sinking ships jettison their whole hold. NPC ships under
  fire jettison some cargo.
- **Salvage** needs the ship stopped. Warships have no cargo rating, so they
  may hold up to `max load / 5` salvaged crates instead. Salvaged crates carry
  no invoice.
- **Summoning clears all cargo** (see [Summoning](#summoning)).

### Contraband

- **Buying** needs ship frags at least the commodity's requirement, **or** crew
  skills of deck ≥ 4×, guns ≥ 1× and repair ≥ 2× that requirement. Warships
  cannot buy contraband, and neither can a captain at the maximum alignment,
  1000 (`MINCONTRAALIGN`). The allowance is the hull's contraband rating scaled
  down when the ship is weight-limited.
- **Customs** runs when a ship docks at a port by maneuvering. It also runs on
  summon arrival, but a summoned hold is already empty. A port never
  confiscates its own contraband. For each crate of every
  other kind, the confiscation chance is:

  ```text
  c = ship.contraband.baseConfiscationChance (35) + crates_in_slot / 2 - sqrt(ship frags) / 5
  c = c + (100 - c) x (1 - hold load / hold capacity)
  capped at 100; a negative result becomes 5
  ```

  A full hold of ordinary cargo hides contraband best. Every confiscation is
  logged to the status log and `LOG_SHIP`.

## Costs and timings

Build and install time accumulates on the ship's maintenance timer. The ship
cannot sail, and cannot be summoned or sold from, while it runs. The **Trader**
achievement (10,000 crates sold) halves hull, weapon and equipment times.
Immortals skip them.

| Action | Cost | Time |
|--------|------|------|
| First hull | list price (the Sailor's Tattoo takes 100 off, or makes the Frigate free under `CHAOS_STARTER_FRIGATE`) | `75 × class id / 4` ticks (Sloop 18, Galleon 131, Cruiser 206) |
| Hull change | new list price − 90% of the old (a negative result is refunded) | `75 × (new / 2 − old / 3)` ticks up, `75 × (old / 2 − new / 3)` down (0-based class indices, integer division). ×5 during ocean PvP. |
| Weapon | list price | `weight × 75` ticks |
| Equipment | see [Equipment](#equipment) | instant |
| Rename | 10% of hull list price | |
| Swap slots | free | |
| Sail repair | 2 per point | `75 + points` ticks |
| Armour or internal repair | 1 per point | `75 + points` ticks per command |
| Damaged weapon repair | 1 per damage point | 75 ticks |
| Destroyed weapon repair | half list price | 150 ticks |
| Reload | 1 per round | 75 ticks per weapon |
| Sell a weapon | pays 90% of list (10% if damaged) | |
| Sell equipment | pays 90% of list (ram: 90% of hull weight) | |
| Summon | hull weight × 0.05 (the prompt quotes double) | see below |

### Summoning

`summon ship` sends for the ship from anywhere, including Davy Jones' Locker.
The ship must not be sinking or at battle stations, and the caller must be
raidable. The summons clears the hold (except for immortals), puts everyone
ashore and parks the hull in the transit room. On arrival the ship docks at the
calling shipwright, customs runs, and the hold is cleared again, immortals
included. Travel time uses the ship's speed with an empty hold:

| Hull | Travel time |
|------|-------------|
| Sloop, Yacht | `50 / max(speed, 2)` mud hours. ×2 from Davy Jones' Locker, ×2 during ocean PvP. |
| Larger hulls | `70 / max(speed − 20, 2)` mud hours. +15 during ocean PvP. |
| Any | capped at 60 mud hours (75 minutes). Immortal: immediate. |

A sunk ship arrives with no sail. Its speed counts as 2, so fetching a wreck
from the Locker takes about 62 minutes.

A summons still under way at a reboot or copyover is lost. The ship comes back
where it last docked (Davy Jones' Locker for a wreck) and can be summoned
again. The fee is not refunded.

### Timers at sea

| Timer | Ticks |
|-------|-------|
| Undock / weigh anchor | 30 / 13 (immortal 2) |
| Maneuver cooldown | 5 |
| Battle stations after the lock is cleared | 180 |
| Ram cooldown | 50 after a hit, 25 after a miss (−up to 15% for skill) |
| Gun crew recovery after ramming | 25 |
| Mind blast stun | 5–20 |
| Levistone flight / recharge | 60 / 600 |
| Sinking: player / NPC / Cyric's Revenge | 75–150 / 1000–1500 / 7500 |
| NPC despawn after losing its target | 300, extended while players watch |

### Ship Damage Control

The **Ship Damage Control** epic skill protects its owner's ship while the
owner is aboard: every sail and hull hit from another ship is cut by 4% plus a
fifth of the skill (14% at 50, 24% at 100), never below 1 point. Spells and
other damage a character deals to a hull are not reduced. The headless
commodore (mob 2733, in Headless) teaches it from level 56 in 10-point lessons.
The first lesson costs 240 epic points and 16,000 platinum, and the price
rises with the skill. New Chaos characters with starter epic skills enabled
start with it at 100.

### Sinking consequences for the owner

A player ship is never destroyed by sinking. It becomes a **sloop** with every
slot emptied, is docked at Davy Jones' Locker, and keeps its frags and crew. It
has no sail unless an NPC sank a larger hull. The crew loses some training, and
the ship loses its share of the victor's frags (nothing if an NPC made the
kill). Insurance pays a share of the old hull's list price to the owner's bank,
or to an auction-house pickup if they are offline:

| Hull | Insurance |
|------|-----------|
| Sloop | nothing |
| Sunk by an NPC | 90% |
| Merchant | 75% |
| Warship | 50% |

## Runtime properties

Read with `get_property()` from `lib/duris.properties` (section `[ships]`).

| Property | Shipped | Code default | Effect |
|----------|--------:|-------------:|--------|
| `ships.pirate.load.chance` | 1000 | 7200 | Per-tick ambush odds are 1 in (value + 1) for a moving, untargeted ship. |
| `ships.pirate.diplomat.load.chance` | 60000 | 30000 | The same, with a diplomat's flag. |
| `ship.sinking.rewardDivider` | 8 | 7 | Divides salvage and bounty. |
| `ship.cargo.update.secs` | 1800 | 1800 | Market drift interval. |
| `ship.cargo.updateDelayedPrices.secs` | 3600 | 1800 | Delay on the prices players see. |
| `ship.cargo.buyAdjustMod` / `sellAdjustMod` | 0.001 / 0.002 | 0.003 / 0.005 | Market move per cargo crate bought or sold. |
| `ship.contraband.buyAdjustMod` / `sellAdjustMod` | 0.003 / 0.010 | 0.015 / 0.025 | Market move per contraband crate. |
| `ship.cargo.sellPriceMod` / `buyPriceMod` | 0.6 / 0.6 | 1.0 / 1.0 | Neutral points the cargo market drifts to. |
| `ship.contraband.sellPriceMod` / `buyPriceMod` | unset | 1.0 / 1.0 | Neutral points for contraband. |
| `ship.cargo.autoSellAdjustRate` / `autoBuyAdjustRate` | 0.05 / 0.05 | 0.05 / 0.05 | Drift speed for cargo. |
| `ship.contraband.autoSellAdjustRate` / `autoBuyAdjustRate` | 0.05 / 0.05 | 0.05 / 0.05 | Drift speed for contraband. |
| `ship.contraband.baseConfiscationChance` | 35 | 0 | Base customs chance per crate. |
| `ship.cargo.minPriceMod` / `maxPriceMod` | 0.54 / 0.69 | none | The band a cargo modifier is held in, on load, after each trade and after each drift: 0.90–1.15 of the 0.60 neutral point. |
| `ship.contraband.minPriceMod` / `maxPriceMod` | 0.85 / 1.3 | none | The same band for contraband. |
| `warship.sails.damage.reduction` | 0.85 | 1.0 | Multiplies every sail hit a warship takes, before Ship Damage Control. |

Related environment switch: `CHAOS_STARTER_FRIGATE` (see
[CONFIGURATION.md](../operations/CONFIGURATION.md) and
[CHAOS_MODE.md](CHAOS_MODE.md)).
