# Named effects: worksheet replacement plan

Status: implemented and locally qualified in this worktree. Arcorar is omitted.
Date: planned 2026-11-10; implementation qualified 2026-11-11.
Source reviewed: `0afba843d9ef5752627435be8ed09b3928ce181b`.

## Outcome and scope

Replace the zone-set effect assignments displayed by `namedreport` with the
choices and piece requirements in **random named effects new (1).xlsx**. Keep
`namedreport` as the command that reports the actual gameplay catalog. For each
accepted worksheet zone, replace its entire old tier list with its one, two, or
three populated worksheet tiers. Clear every unused slot and retain Celestial
Plane's explicitly supplied third tier. Do not append choices to old bonuses.

This document specifies the implementation and its qualification. Production
publication remains a separate owner operation. The worksheet supplies effect
choices, not operational instructions.

Use the existing catalog, origin metadata, affect ownership, and report cache.
Preserve named-drop probabilities, random item modifiers, weapon procs, roaming
spawn selection, the worn-armor driver, weapon contribution, excluded belt slots,
and MariaDB item persistence. Preserve matching-set HP as
`max(0, 5 * (matching_pieces - 2))`, subject to the existing gear HP cap.
No runtime spreadsheet reader, new configuration service, new persistence table,
or general effect framework is needed.

**Confirmed missing-choice policy:** zones omitted from the worksheet or left
without effect choices receive **no named-set spell bonuses**. Preserve the
existing matching-set HP rules. Remove their old spell tiers rather than keeping
them as a fallback. A new zone with blank choices gets no spell-catalog entry.
Rows that supply choices receive an explicit disposition below. Arcorar is explicitly omitted for now; its choice is preserved for reference.

## Decisions supplied for the gaps

The user supplied Tiu's clarification on 2026-11-10: use the same choices for both
Braddistocks, both Underworlds, and every Reliquary; leave missing choices without
effects. The revised workbook now supplies choices for all 23 previously missing
current zones, so their earlier HP-only decisions are superseded. Keep the shared
zone decisions and apply the revised piece thresholds:

| Zones | Final planned choices | Worksheet row |
| --- | --- | --- |
| Braddistock Mansion **#13 and #1350** | **2 pieces: Armor; 4 pieces: Barkskin** | 134 |
| The Underworld **#44 and #300** | **3 pieces: Haste; 5 pieces: Negative Energy Barrier** | 228 |
| Reliquary Nexus **#1301, #1302, #1303, #1304** | **4 pieces: Vampiric Touch; 5 pieces: Stone Skin** | 311–314, one explicit row per zone |
| The 23 formerly missing current zones in the CSV | **Use the newly supplied choices, including one-tier rows** | 68, 204, 290–310 |
| Blank **#112 and #480** | **No spell bonuses; existing matching-set HP rules remain** | 20, 73 |

This resolves all **33 records** in the
[gap CSV](named-effects-missing-choices.csv): **2 HP-only decisions** and
**31 replacement assignments**, including the eight shared-zone assignments.
Only **#112** currently has spell bonuses to remove; Guildhalls #480 already has
no spell-catalog entry. The CSV retains the current effects for comparison,
updates every worksheet row reference, and records the revised disposition.
The implementation follows these decisions; production publication is separate.

Use separate catalog rows for the eight numbered zones. Sharing choices does not
merge their origins or let pieces from different zones count as one set. Existing
items follow the replacement by origin, including losing retired bonuses; the
plan does not grandfather old effect lists. Include that change in the eventual
player-facing release explanation.

The worksheet supersedes the effect and threshold choices in the
[previous assignment plan](named-zone-set-first-pass-assignments.md) for accepted
rows. That document's identity and eligibility findings remain useful evidence;
its old assignments must no longer be the test oracle for replaced rows. The
[previous delivery plan](named-zone-set-implementation-plan.md) documents the
existing system, not the requirements for this replacement.

## Source and baseline

Workbook: `C:\Users\apexw\Downloads\random named effects new (1).xlsx`.
Worksheet: `Sheet4`, source values in `A1:I314`.
SHA-256: `3545e7e46f1e11ecf43dd604bc243e7b4d267707784120121dd047e9fd09a69f`.
This revision supersedes the earlier six-column workbook snapshot. Match revisions
by zone identity/title, not row position: rows were inserted and the generic Nexus
row was replaced by four explicit Reliquary rows.

- Columns A/B identify the zone. C/D, E/F, and G/H are pieces/effect for tiers
  1, 2, and 3. Column I contains explanatory notes. Piece counts are thresholds,
  not effect strength. An empty tier pair is intentionally unused.
- There are **313 named rows**: **305 two-tier rows, five one-tier rows, one
  three-tier row, and two blank rows**, totaling **618 tier selections**.
- **117 rows have a numeric zone ID; 196 do not.** Resolve names against active
  zone headers in [areas/AREA](../../areas/AREA), then use numeric identity.
- There are **26 one-piece tiers**, and supplied thresholds range from 1 to 8.
  Preserve those numbers; raising every one-piece tier to two would change the
  worksheet's choices.
- The workbook uses **75 distinct effect strings**. **22** spell-name spellings
  need normalization. Awareness, Sneak, and Ultravision require actual support,
  not spelling fixes. After normalization there are **71 existing spell IDs** plus
  those three requested effect concepts.
- Every populated tier has both a threshold and an effect; there are no partial
  pairs or formulas. Column I explicitly explains the two blank zones. The
  appendix preserves all rows, tiers, original spellings, and source notes so
  implementation does not depend on an untracked Downloads file.

The pre-replacement [named_sets.c](../../src/item/named_sets.c) baseline contained **298 sets, 389 tiers,
and 106 distinct effect constants**. Its three-slot structure already accommodates
the revised worksheet, including its three-tier row.

With the resolutions below, the implementation target is **306 zone definitions
and 608 tiers**, excluding the explicitly omitted Arcorar row: **300 two-tier sets, five
one-tier sets, and one three-tier set**. This replaces **297** current definitions,
removes spell bonuses from **one** current zone (#112), and adds **9** loaded
zone definitions. The 306 definitions come from **304 worksheet choice rows**,
with two extra definitions from the Braddistock and Underworld expansions.
The four Reliquaries now have explicit source rows and must not be expanded a
second time. Of the other seven populated choice rows, four subarea
choices are superseded by their exact parent-zone rows, two target unloaded
areas, and one is Arcorar. The two blank rows remain HP-only.

The one-tier sets are Ugta **#391** (row 66), Lost Temple of Tikitzopl **#441**
(70), Ghore **#115** (293), Minizones of the Underdark **#885** (303), and
Minizones of the Surface **#979** (307). Celestial Plane **#455**, row **261**,
grants Warring Zeal at **3**, Divine Fury at **5**, and Battletide at **7**.

## Reconcile zone identities before editing the catalog

Match by numeric ID when ID and name agree. Normalize case, MUD color codes,
punctuation, and obvious title typos for comparison, while retaining the original
worksheet text in the appendix. Never use fuzzy matching as the final identity
rule. The following are concrete exceptions.

| Sheet row(s) | Source issue | Planned resolution or decision |
| --- | --- | --- |
| 6, 224 | Row 6 says ID 23 / The Seacaves. Active #23 is Myconid Mushroom Forest; The Seacaves is #22. Row 224 separately says Myconids. | Source-resolved correction: row 6 → **#22**, row 224 → **#23**. Preserve the original worksheet ID in the appendix. |
| 45, 128 | Row 45 gives stale ID 250 for Plane of Fire, Brass. | Source-resolved correction: row 45 → **#1390** (`brass.zon`). Row 128 is the separate **#254** Plane of Fire. Do not revive #250 or merge the two areas. |
| 93–95 | Ceothia 1/2/3 share the same displayed zone title. | **Chosen interpretation:** **#808 present / #811 past / #814 future**, in authored `areas/AREA` order (`ceothia`, `ceopast`, `ceofutur`). Keep Barkskin at 2 and Stone Skin at 6/5/4 respectively. This is an explicit planning inference, not a worksheet-provided ID. |
| 102, 131, 165, 269 | Darkmore Forest, Jenna's Waystation, and Arlik's Inn are subareas in `minizones.wld`; row 269 separately assigns Mini Zones. | **Resolved by exact-zone precedence:** use row **269** for **#57**: Hawkvision at 1, Elephantstrength at 2. Rows 102/131/165 are superseded alternatives, preserved in the appendix. They cannot have independent grants without changing origin identity. |
| 105, 266 | Shaledrieth appears inside `connectorzones.wld`; row 266 already assigns The Great Realm of Duris. | **Resolved by exact-zone precedence:** use row **266** for **#536**: Levitate at 2, Stone Skin at 8. Row 105 is superseded. Keep one definition for the actual shared origin. |
| 108 | Neverwinter Valley differs from the active title. | Source-resolved correction: **#204 Neverwind Valley**; keep it separate from **#990 Neverwinter Woods** (row 107). |
| 134 | Braddistock Mansion matches both **#13** and **#1350**. | **Resolved:** apply row 134's pair to both independent IDs. Preserve ambiguous legacy items' HP-only identity behavior. |
| 143 | Lair of the Asunwa Jaguar exists as `asunwa.zon`, ID **#353**, but `asunwa` is commented out in `areas/AREA`. | **Resolved as inactive:** omit this definition from the running catalog and preserve its choices for a future area activation. This replacement does not load retired areas. |
| 148 | `jungle.zon` identifies **#670 Jungle of Khazan**; `jungle` is commented out in `areas/AREA`. | **Resolved as inactive #670:** omit the unloaded definition and preserve Armor at 2 / Thornskin at 3 for any future activation. Terrain references elsewhere do not transfer this choice to #240. |
| 154, 158, 180, 213, 222, 224, 227, 283 | Abbreviated, uncertain, reordered, or misspelled names. | Source-resolved mappings: **#708** Enclave of the Opal Phoenix; **#1382** Mitashi; **#437** Lost City of Tikitzopl; **#337** Miaeril Village; **#886** Morg's Place; **#23** Myconid Mushroom Forest; **#458** Orog Encampment; **#882** Temple of Blibdoolpoolp. |
| 311–314 | Each Reliquary now has an explicit numeric ID and pair. | **Resolved:** use one source row for each of **#1301–#1304**; do not retain an extra generic Nexus row. **#575** keeps row 267's independent Mountain of Peril Peaks choice despite its `nexus.zon` filename. |
| 228 | The Underworld matches **#44** and **#300**. | **Resolved:** apply row 228's pair to both; do not merge their item origins. |
| 237 | Arcorar - The Great King Forest has no matching zone header or authored zone/room/mobile text, including a search with MUD colors removed. | **Explicitly omitted at the user's request.** Preserve the source choice for reference; do not assign another forest by similarity. |
| 289 | Pirate random equipment uses the room of the kill. Ship interiors use the #600 room pool. | **Resolved:** **#600 The Adventurers Shipyards**, Pantherspeed at 3 / Fly at 4. This applies to named gear from the shared ship-zone origin, not exclusively pirate mobs, and is separate from **#431 The Ship Yards** (row 111). |

Straightforward spelling corrections also include Storm Port Stronhold → #226,
Thre Great Shaboath → #328, and Lost Temple of Tikizopl → #441. Corrections here
identify existing zones; they do not request renaming authored areas or old gear.

The two blank rows are **20: #112 Arena of the Elder Brain** and **73: #480
Guildhalls**. Both are explicitly HP-only under the confirmed policy. Remove
#112's current three spell tiers; #480 already has no spell-catalog entry.
The revised notes call #112 disconnected with no mobs and #480 player-created
guildhalls. Those are the worksheet's reasons for leaving the choices blank,
not new instructions to change area access or population.

Eight worksheet targets are absent from the current catalog and were
excluded in the earlier roster review: **#856** Ancient Bridge (row 84), **#546**
Kvark's Great Connector (115), **#904** Towering Glacier (209), **#1200** Depths of
Duris (214), **#773** Desolate Under Fire (243), **#536** Great Realm (266),
**#384** Valoisian Castle (268), and **#240** Underdark (285).
**Include all eight**, plus the newly resolved ship zone **#600**. They are loaded
zone IDs, and the user's newer worksheet explicitly supplies their choices.
That supersedes the earlier roster's selection policy, including Valoisian's
historical exclusion. A closed or inaccessible area can still have existing gear;
granting that gear a catalog bonus does not reopen the area or create drops.
Leave access flags, resets, routing, and drop probabilities unchanged. Do not claim
these nine additions make nine new areas farmable. Unlike these loaded records,
#353 and #670 cannot pass current catalog validation because their areas are absent.

The source chain for these resolutions is
[areas/AREA](../../areas/AREA), [jungle.zon](../../areas/zon/jungle.zon),
[ship.zon](../../areas/zon/ship.zon),
[ship room allocation](../../src/ships/ship_base.c),
[kill-drop attribution](../../src/item/random_equipment_drop.c), and
[item naming/origin storage](../../src/item/random_equipment.c).
`random_equipment_kill_drop` passes the killer's room to `create_random_eq`, which
stores that room's numeric zone ID. Ship rooms occupy 60000–64999 in #600.
The old crew-equipping call in `ship_npc.c` is commented out; it is not the active
drop path. The same origin logic explains why the Mini Zones and Shaledrieth
subareas cannot receive separate pairs through the current catalog.

## Normalize effect names

Use the existing constants below in the catalog. This is a data translation,
not a request to add duplicate spell definitions to `spells.h`.

| Worksheet string | Existing constant | ID |
| --- | --- | --- |
| `SPELL_PROTECTION_FROM_EVIL` | `SPELL_PROTECT_FROM_EVIL` | 34 |
| `SPELL_PROTECTION_FROM_GOOD` | `SPELL_PROTECT_FROM_GOOD` | 81 |
| `SPELL_PROTECTION_FROM_FIRE` | `SPELL_PROTECT_FROM_FIRE` | 96 |
| `SPELL_PROTECTION_FROM_COLD` | `SPELL_PROTECT_FROM_COLD` | 97 |
| `SPELL_PROTECTION_FROM_LIGHTNING` | `SPELL_PROTECT_FROM_LIGHTNING` | 98 |
| `SPELL_PROTECTION_FROM_ACID` | `SPELL_PROTECT_FROM_ACID` | 105 |
| `SPELL_PROTECTION_FROM_UNDEAD` | `SPELL_PROT_FROM_UNDEAD` | 136 |
| `SPELL_PROTECTION_FROM_LIVING` | `SPELL_PROTECT_FROM_LIVING` | 318 |
| `SPELL_NEGATIVE_ENERGY_BARRIER` | `SPELL_NEG_ENERGY_BARRIER` | 333 |
| `SPELL_WATER_BREATHING` | `SPELL_WATERBREATH` | 85 |
| `SPELL_GLOBE_OF_INVULNERABILITY` | `SPELL_GLOBE` | 144 |
| `SPELL_TOWER_OF_IRON_WILL` | `SPELL_TOWER_IRON_WILL` | 260 |
| `SPELL_INVISIBLE` | `SPELL_INVISIBILITY` | 189 |
| `SPELL_FIRE_SHIELD` | `SPELL_FIRESHIELD` | 108 |
| `SPELL_LIGHTNING_SHIELD` | `SPELL_LIGHTNINGSHIELD` | 526 |
| `SPELL_ACCELERATED_HEALING` | `SPELL_ACCEL_HEALING` | 356 |
| `SPELL_BATTLE_TIDE` | `SPELL_BATTLETIDE` | 395 |
| `SPELL_GIRILALS GRANITE HAMMER` | `SPELL_GIRILALS_GRANITE_HAMMER` | 652 |
| `SPELL_ILIENZES_FLAMING_SWORD` | `SPELL_ILIENZES_FLAME_SWORD` | 390 |
| `SPELL_NEGATIVE_FEEDBACK_BARRIER` | `SPELL_NEG_ARMOR` | 593 |
| `SPELL_lliendils stormshock` | `SPELL_LLIENDILS_STORMSHOCK` | 388 |
| `SPELL_thryms icerazor` | `SPELL_THRYMS_ICERAZOR` | 393 |

Three worksheet concepts are not registered callable spells. The following
behavior is now selected using the existing mechanics as the starting point:

- **Awareness:** nine selections, rows 14, 16, 112, 118, 127, 137, 232, 242,
  271. `SKILL_AWARENESS` (#1024) is a skill implemented by `do_awareness` in
  [new_skills.c](../../src/classes/new_skills.c). Grant the **active Awareness
  affect**, using **effective rating `min(56, matching_pieces * 10)`** in the
  native modifier and duration calculations. This follows the existing set
  invocation scale instead of inventing a new progression. Reuse the native
  level/INT/DEX calculation and random roll, applying the resulting
  `SKILL_AWARENESS` affect through set ownership. Extract only the small shared
  application/calculation needed by the manual command and set caller. Do not
  alter learned skill ratings, train the skill, or run the command's messages.
- **Sneak:** three selections, rows 32, 179, 216. `SKILL_SNEAK` (#1000) has no
  spell callback. Grant a **successful active `SKILL_SNEAK` / `AFF_SNEAK` affect**
  with the native wearer-level duration, without a skill-success roll, lag, or
  training. Ordinary movement keeps it; the existing combat-start path removes
  `SKILL_SNEAK`. Suppress the set grant while fighting or mounted and reapply on
  the next ordinary set pulse once eligible. Add no new cooldown or persistent
  toggle. A manual removal can clear the current affect but cannot permanently
  disable an equipped passive bonus; dropping below the threshold does that.
  Ensure movement's learned-skill check cannot penalize set-granted Sneak for a
  zero trained rating, and set grants cannot notch a learned skill. Preserve
  manual/innate/equipment Sneak sources when the set is removed.
- **Ultravision:** three selections, rows 27, 71, 243. This is an innate/affect
  capability (`INNATE_ULTRAVISION`, `AFF2_ULTRAVISION`), not `SPELL_ULTRAVISION`.
  Register one self-targeted `SPELL_ULTRAVISION` effect with the next available
  spell ID and display name, without adding it to any class's learnable spells.
  Its handler grants only `AFF2_ULTRAVISION`; the set grant is non-saving and
  lasts while supported (`duration = -1` with existing set cleanup). Reuse normal
  affect recomputation so racial and other equipment Ultravision survive removal.

These **15 tier selections** cannot be satisfied by renaming the token. Keep
their intended choices in scope and implement the semantics above;
do not silently substitute True Seeing, Farsee, or another spell. Extend the
existing supported-effect switch and dispatch only for these concrete effects.
Do not invoke a null spell callback or relax support checks for arbitrary skills.
The existing ordinary/set suspension function skips skill IDs other than the
dragon song. Extend that exception specifically for Awareness and Sneak, and
apply the existing ordinary-cast guard to their manual affect paths as needed.
Do not stack a second active modifier when the player already has the same effect.

## Implementation sequence

### 1. Freeze the reconciled assignment manifest

Use the identity decisions above to record final zone ID(s), canonical effect
IDs, both thresholds, and disposition: replace, add, HP-only, superseded subarea,
inactive area, or explicitly omitted Arcorar. Flatten the confirmed groups into separate
zone definitions and check the **306-set / 608-tier** resolved target. Include
every current catalog zone absent from the accepted replacement list so none disappears by
accident. Apply the confirmed HP-only policy to those omissions. Arcorar is outside the accepted scope and does not change those counts.

Retain source-row references and the alias map in repository documentation.
This is the reviewed input to the catalog and its tests; no Excel dependency is
needed at game startup or to run the regression suite.

### 2. Make the supplied tiers work through existing gameplay paths

Primary files: [named_sets.c](../../src/item/named_sets.c),
[specs.set.c](../../src/specs/specs.set.c), and, where required,
[named_set_effects.c](../../src/item/named_set_effects.c).

- Replace each accepted catalog entry's old tiers with all populated normalized
  choices, in worksheet order. A one-tier row has two zero slots, a two-tier row
  has one zero slot, and Celestial Plane uses all three slots. Leave the existing
  three-slot structure intact. Empty pairs do not retain old tiers and are not
  unanswered choices.
- Remove the spell-catalog entry for **#112**, the only current set now HP-only.
  Do not encode it as an all-zero definition: `validate_named_sets` rejects
  entries with no effects. Matching-set HP and stored origins already operate
  independently of the spell catalog. Keep those paths working for unlisted sets.
- **One-piece grants:** `random_set` currently returns at `count < 2`, before
  checking spells or refreshing cleanup. Allow one eligible worn armor piece
  to grant a one-piece tier and keep its cleanup event alive. Reuse the existing
  zero-HP `TAG_SETPROC` bookkeeping if appropriate, and clamp HP at zero below
  two pieces. The cleanup event currently exits when that bookkeeping affect
  is absent, so moving only `check_zone_spells` above the early return is
  insufficient. Verify 0→1→2→1→0, driver swaps, and weapon-only cases.
- **Paired armor effects:** many rows pair Armor with Barkskin or Thornskin.
  The set dispatcher currently blocks all three when `AFF_ARMOR` is present,
  even though the native Barkskin/Thornskin handlers can grant their additional
  skin flags without a second AC modifier. Let those native handlers supply
  the intended compatible portions; preserve the no-double-AC rule and ordinary
  cast ownership. **Use native coexistence, not an automatic stronger-AC upgrade.**
  Evaluate tiers in worksheet order: Armor can supply AC while Barkskin or
  Thornskin supplies its additional native skin flag/benefits. Do not sum two AC
  modifiers or remove an ordinary armor cast to force an upgrade. Verify direct
  high-count equip, stepwise equip, ordinary casts in both orders, and threshold
  loss. Preserve native AC precedence when another armor source is already active.
- **New native spell coverage:** thirteen normalized spells have handlers but
  are absent from the current catalog: Accelerated Healing, Air/Earth/Fire/Water
  Form, Girilal's Granite Hammer, Ilienze's Flaming Sword, Lliendil's Stormshock,
  Inertial Barrier, Ironwood, Lightning Shield, Sanctuary, and Tower of Iron Will.
  Qualify the actual handlers and add `named_set_ordinary_cast` where missing.
  Reuse ownership/suspension machinery, including all nodes of multipart buffs.
- **Elemental forms:** preserve `elemental_form_failure_message` in
  [magic.c](../../src/magic/magic.c). Earth, Fire, and Water Form require the
  matching Conjurer/Magus specialization; Air Form has no matching-specialization
  gate. Keep mutual exclusion with other forms and elemental auras, including
  ordinary casts. Noneligible wearers keep the other tiers and HP, with no
  substitute form or repeated failure messages. Display these restrictions in
  `namedreport` and help. Test stat/max-stat and HP recomputation through Fire
  and Water Form removal, and Fireshield overlap in the Charcoal Palace set.
- **Weapon enhancements:** Ilienze, Thrym, Lliendil, and Girilal in rows
  **45, 57, 251, and 309** create character affects, not new weapon objects.
  Reuse [reavers.c](../../src/classes/reavers.c), the weapon predicates in
  `core/utils.h`, and the existing hit-proc dispatch. Require a suitable wielded
  weapon for the native grant/proc; do not invent a Reaver-class restriction.
  Add missing ordinary-cast guards for Ilienze, Lliendil, and Girilal; Thrym
  already has one. Qualify non-Reaver wearers, both wield slots, weapon swaps,
  native shield synergies, and loss of the named threshold. Failed periodic
  grants must stay silent. Preserve ordinary weapon-spell affects on set removal.
- **Monastery healing pair:** row **290** grants Accelerated Healing at 2 and
  Regeneration at 3. The set dispatcher's broad healing exclusion currently
  prevents both from being granted, but the native spell handlers permit both
  and [limits.c](../../src/world/limits.c) already compares their benefits instead
  of double-counting them. Narrow the set dispatch gate to allow that native
  coexistence while retaining `SKILL_REGENERATE`/Pactum exclusions. Add the missing
  ordinary-cast guard to Accelerated Healing. Test 1/2/3 pieces, both cast orders,
  in/out-of-combat healing, and dropping back below either threshold.
- **Three-tier Celestial Plane:** evaluate Warring Zeal at 3, Divine Fury at 5,
  and Battletide at 7, using their native combination and ordinary-cast rules.
  Keep the invocation-level cap at 56 from six pieces onward. Prove thresholds 2/3,
  4/5, and 6/7 plus removal back through them; no tier may disappear because the
  old draft assumed exactly two choices.
- **Ironwood:** row **188**, Ny'Neth's Stronghold, now supplies Barkskin at one
  piece and Ironwood at three. Preserve its wood-skin prerequisite and finite absorption.
  **Use the existing generic Stone Skin cooldown interval**, defaulting to 60 seconds
  from a successful grant, through `timer.stoneskin.generic` and the existing
  wearer cooldown path. Track Ironwood under its own spell ID, add it to the
  existing named-cooldown list, and do not reset its timer by re-equipping or
  switching drivers. Grant no replacement absorb counters while Ironwood is
  still active. After depletion/expiry, retry only once the interval has elapsed
  and a compatible wood-skin prerequisite is present. Invoke at the normal named
  level `min(56, pieces * 10)`; keep native absorption and damage rules.
  Suppress failed periodic attempts and award no healing XP for an automatic
  set invocation. Preserve ordinary manual Ironwood casting and its normal XP
  behavior. Mark the set cooldown accurately in `namedreport` alongside Stone Skin.
  The separate Stronghold Continued row **189** now grants Lifelust/Battle Ecstasy;
  it must not retain its previous Ironwood tier.
- **Reused special paths:** keep Conjure Elemental's existing wearer cooldown
  (`timer.conjureElement.generic`, default five minutes), level floor/cap, pet limits,
  and native summon lifetime for
  rows **253** and **299**. A summoned pet is not a removable set affect. Preserve
  Negative Feedback Barrier's negative-shield prerequisite and native skin
  exclusions for row **49**, with no newly invented cooldown for that existing
  catalog effect. Qualify the new Sanctuary pairing with Stone Skin (row **302**)
  and the revised Stornog's Spheres tier (row **13**) through their native paths.
- **Other interactions:** retain native shield exclusions, ordinary casts,
  stats/speed caps, shared-effect ownership, and Stone Skin's existing cooldown.
  Most spells use `min(56, pieces * 10)` invocation level; Stone Skin uses
  `min(56, pieces * 5)`, and Endurance has its existing level floor. Test the
  one/two-piece invocation levels 10 and 20; do not raise them to 30 by accident.
- Add only the narrow active-effect support needed for Awareness, Sneak, and
  Ultravision with the semantics selected above. Cover ordinary/manual,
  innate, equipment, and multiple-set coexistence as applicable.

### 3. Publish the same catalog through namedreport and help

[do_namedreport](../../src/world/random.mob.c) already consumes
[generate_named_report](../../src/redis/redis_report_cache.c), which iterates
`named_sets`. Keep that single source of truth and pagination. Update supported
effect names and relevant notes, including one-piece activation, HP remaining zero
at one/two pieces, native stacking and weapon/form restrictions, Conjure Elemental's
five-minute cooldown, and Ironwood's generic skin cooldown. Show the exact one,
two, or three tiers for each zone, including Celestial Plane's seven-piece tier.
Do not add a separate display-only worksheet table to the command.

Check cached, uncached, and Redis-unavailable output. Use the existing cache
invalidation/warming path at release so an old process's report cannot advertise
the previous tiers. Remove obsolete restriction notes when the final catalog
no longer contains the affected choices. Keep the report's explanation that
unlisted sets still follow the matching-set HP rules. Update canonical help in
[lib/information/help_index](../../lib/information/help_index), its normal MariaDB publication,
and [hints](../lib/information/hints.txt) as applicable. Mark the previous
assignment document superseded for these rows without deleting its historical
identity decisions.

### 4. Verify the replacement, including existing equipment

Extend existing tests rather than introducing another harness:

- `test_named_set_catalog.py`: replace the obsolete “old effects never change”
  digest and old assignment-document assertions with the reconciled manifest.
  Keep the independent roaming-spawn digest, loaded-zone/unique-ID checks,
  effect support checks, and report execution. Assert the exact **306 definitions /
  608 tiers** and the **5 one-tier / 300 two-tier / 1 three-tier** distribution.
  Check both cleared unused slots and Celestial Plane's retained third tier.
  Account explicitly for HP-only and deferred zones
  in the loaded-zone coverage check rather than treating every omitted spell row
  as an accidental deletion.
- Identity/disposition checks: exact parent-zone rows win for #57/#536; the three
  Ceothia eras use the selected 808/811/814 mapping; #353/#670 remain absent;
  the nine loaded additions are present, including #600 rather than #431 for
  pirate/ship-origin gear. Keep existing origin metadata and do not alter source
  room attribution or make shared spell choices combine distinct zone counts.
- `test_named_set_membership.py`: prove one-piece activation and cleanup, exact
  boundary counts for every configured threshold, mixed origins, excluded belt
  slots, unchanged HP, and the armor driver requirement.
- `test_named_set_effect_ownership.py` and `test_named_set_effect_levels.py`:
  qualify new handlers, low invocation levels, armor pairs, Ironwood prerequisites
  and depletion, ordinary effects in both orders, innate Ultravision, Sneak break
  behavior, and two sets supporting the same effect. Removing one provider must
  not strip the surviving provider or an ordinary effect.
  Include eligible/ineligible Magus form wearers, conflicting forms/auras,
  multipart form cleanup, weapon enhancement hit procs and weapon prerequisites,
  the Monastery healing pair, and Celestial Plane's three-tier combinations.
- `test_named_set_cooldowns.py` and `test_named_set_report_cache_live.py`:
  preserve Stone Skin timers across re-equip/relog/driver changes, verify
  Ironwood cooldown state through the same transitions, and verify identical
  complete reports with fresh and stale cache states. Keep the no-Redis fallback.
- Existing native wear/report/transfer journeys: exercise representative one-piece,
  one/two/three-tier, special-effect, and shared-title sets. Load previously owned
  items with stored origins, confirm the new bonuses without rerolling gear, then remove,
  save, and reload. Cover losing old bonuses as well as gaining new ones. Update
  journey expectations that currently hardcode the previous Tharnadia tiers.
- HP-only transition: use **#112** to prove all former spell bonuses disappear
  while item origins and matching-set HP survive. Confirm **#480** stays absent.
  Test a removed catalog entry as well as changed tiers, and prove that the 23
  newly supplied current zones receive their choices instead of the old HP-only
  draft disposition.

Run the affected `test_named_set_*.py` scripts directly, including origin tests
when validating unchanged item identity, plus `test_random_equipment_golden.py`
and `test_random_mob_theme_runtime.py` to guard the preserved generation/spawn
behavior. After C/C++ edits run `./scripts/format.sh --check` and `make -C src`.
Use the existing local/disposable MariaDB and native journey setup; record exact
commands and results. A source-only catalog check is not gameplay proof. CI is
not a required wait.

### 5. Cut over and retain a simple rollback

Existing gear follows the replacement by its stored zone origin; effect choices
are not copied into every item's data. No item reroll, item rewrite, or database
migration is required. Pet timer payload v3 appends Ironwood after the three v2
deadlines; v1/v2 reads and unchanged v2 timer positions are preserved. Pets without
Ironwood still use the earlier payload versions. A rollback build must retain
this additive codec even when using the previous catalog. Keep ambiguous legacy-title gear
on the existing HP-only path.

Verify a normal restart and the supported copyover/reload path rebuild transient
bonuses from the new catalog and clear retired grants. If a path retains old
grants, fix or constrain that actual transition before claiming a live cutover.
Keep the previous catalog revision as rollback input. Reverting the code/catalog
and rebuilding transient effects must restore old bonuses without damaging item
origins; invalidate the report cache on rollback too. Reuse the existing rollback
journey where its assumptions fit, updating its old fixed roster expectations.

Production execution remains a separate, explicitly authorized operation under
the repository deployment rules. The implementation handoff should identify the
revision, final assignments/deferred rows, focused proof, help publication, and
cache refresh needed for that release.

## Completion criteria and implementation status

The implementation is complete when all worksheet rows have an explicit
disposition, every accepted tier is reachable at its exact supplied count for
an eligible wearer satisfying native prerequisites, actual
effects and `namedreport` agree, retired tiers disappear, existing item identities
survive reload, and the focused checks above pass. Do not describe a partial
import that skips the three unsupported effect concepts as a full replacement.

**Row 237, Arcorar - The Great King Forest, is omitted for now at the user's
request.** Its source choices remain in the appendix for reference and do not
create a catalog entry. The implementation target is 306 sets and 608 tiers.

All other former questions now have a selected implementation rule: authored
Ceothia order, exact-zone precedence for shared subareas, inclusion of the nine
loaded additions, omission of the two unloaded areas, #600 ship origin, the
three active-effect semantics, native armor coexistence, and Ironwood's existing
generic skin cooldown. The revised weapon, form, healing, summon, and third-tier
rules above preserve native behavior and the updated worksheet's choices.
These choices use the user's delegation to resolve
reasonable defaults; they are distinguished from facts explicitly present in
the worksheet.

Implementation and local gameplay qualification are complete, including one-piece
activation, the new effect paths, ordinary-effect coexistence, cooldowns, cache
refresh, persistence, and removal of old grants. Arcorar has an explicit omitted
disposition and does not block this implementation. Production publication remains
separate; no worksheet decisions remain open for this scope.

Planning validation performed: read-only extraction of the entire worksheet,
counts and effect-token comparison against current source, active zone-header
reconciliation, and inspection of the relevant runtime/report/test paths.
The 306 resolved definitions were checked for unique loaded zone IDs, exact
piece/effect pairs in all three slots, nine additions, one removal, and the seven
excluded source-row dispositions. The 33-row gap CSV was reconciled to the revision:
31 replacement assignments and two explicit blanks. The revised worksheet values,
including its two explanatory notes, remain intact in the appendix.
Implementation result (2026-11-11): the 306 definitions, new active effects,
one-piece ownership/cleanup, native buff coexistence, report/help, and four-timer
player/pet persistence are present. `make -C src -j4` and `make world` passed.
The catalog, membership, ownership, invocation-level, cooldown, live Redis cache,
origin, random-equipment golden, random-mob theme, pet restore, elemental-form,
and Conjurer Fire regressions passed. Formatting passed with
`scripts/format.sh --staged --check` using a temporary index; the Windows mount's
executable mode bits caused a false diff in the unstaged formatter.

The private full-world MariaDB journey passed wear, native effect thresholds,
save/reload, and removal for #1325, one-piece #159, three-tier #455, HP-only #112,
Fire Form #883, and Water Form #1424. Native transfer preserved the nested item
graph and origins across reboot. The report journey verified all 306 rows,
MariaDB help, warm/cold cache equality, replacement of a stale report on reboot,
Redis loss, and paginated no-Redis output. The previous-catalog round trip used
the same four #112 item UIDs: the old three spells returned with the previous
catalog, disappeared with the replacement, and HP, origins, and the item graph
remained intact. That compatibility build uses the previous catalog with the
current persistence/ownership fixes, including the additive pet timer codec.
Evidence is retained in
`/home/aiwithapex/.cache/duris-named-effects-01a1c47f/named-replacement-bnm7v8sv`.
Its `replacement.json` records all nine completed stages and `passed: true`;
`replacement-transcript.txt`, per-case results, and the private SQL snapshot
retain the detailed evidence. The separate native report runtime is
`/home/aiwithapex/.cache/duris-named-effects-01a1c47f/named-report-mariadb-q1db_3hj`.
The tested server SHA-256 is
`83b002a916f447c78bb23072f62fdfc5a3b25e03280922e2b637183120f5ae0f`.
The previous-catalog compatibility binary SHA-256 is
`d67ef04b89bfd77bb89b37ce78197d3b86971a9a93ded0ea4904cb9d49687387`.

Focused regression commands (all passed): run `python3 tests/async/<name>.py`
for `test_named_set_catalog`, `test_named_set_membership`,
`test_named_set_effect_ownership`, `test_named_set_effect_levels`,
`test_named_set_cooldowns`, `test_named_set_report_cache_live`,
`test_named_set_origin`, `test_random_equipment_golden`,
`test_random_mob_theme_runtime`, `test_pet_restore_state`,
`test_elemental_forms_runtime`, `test_conjurer_fire_runtime`, and
`test_healing_spell_precedence_runtime`. The ownership regression also executes
Monastery's two healing tiers in both grant orders, at 1/2/3 pieces and back down,
while retaining the native Pactum/Regenerate exclusions. The healing precedence
regression executes native healing calculations in and out of combat.

To run the native qualification from a Windows-backed checkout, set
`NAMED_SET_ARTIFACT_ROOT` to a private Linux directory, then run
`tests/async/with_disposable_mariadb.sh python3 tests/async/run_named_set_replacement_journey.py <compatible-previous-catalog-server>`.
The successful final invocation used `bin/tests/named-compat/dms_previous_catalog`
and `--resume /home/aiwithapex/.cache/duris-named-effects-01a1c47f/named-replacement-bnm7v8sv`;
the aggregate result is also in `bin/named-replacement-journey-resume8.log`.
The mutable runtime needs Linux file modes and directory fsync. Source and all
compiled artifacts stay in this worktree; tests enforce loopback disposable
schemas. The failed Windows-directory attempt remains under `bin/tests`.
Production deployment has not been performed.
Native qualification used normal restarts and MariaDB reloads. Live copyover or
hotboot was not exercised; use the qualified normal restart for this release.

## Appendix: complete worksheet choices

This is a snapshot of the revised workbook, not an executable import.
Source ID is column A exactly as supplied. Candidate ID records the selected
mapping and superseded/inactive disposition. Ceothia order remains the selected
planning inference; Arcorar is explicitly omitted.
Effect tokens omit only the common SPELL_ prefix for readability and otherwise
preserve the workbook spelling. Each choice is **pieces: effect**. A dash in a
choice column means that tier is unused; only rows 20 and 73 have no choices.
The Notes column preserves source column I verbatim.

| Row | Source ID | Worksheet zone name | Candidate ID | Choice 1 | Choice 2 | Choice 3 | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 14 | Kobold Settlement | 14 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 3 | 18 | The Troll Hills | 18 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD | - | - |
| 4 | 20 | Valley of Crushk | 20 | 2: ARMOR | 3: BARKSKIN | - | - |
| 5 | 21 | Vargan | 21 | 2: LEVITATE | 3: FARSEE | - | - |
| 6 | 23 | The Seacaves | 22 | 2: ARMOR | 3: SOULSHIELD | - | - |
| 7 | 26 | The Town of Breale | 26 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_GOOD | - | - |
| 8 | 37 | Ako Village | 37 | 2: ARMOR | 3: BARKSKIN | - | - |
| 9 | 40 | Caves of Mt. Skelenak | 40 | 2: LEVITATE | 4: FARSEE | - | - |
| 10 | 50 | Labyrinth of No Return | 50 | 2: ARMOR | 3: SOULSHIELD | - | - |
| 11 | 53 | Fort Marigot | 53 | 3: LEVITATE | 4: PANTHERSPEED | - | - |
| 12 | 60 | The Lizardman Swamps of Clavikord | 60 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD | - | - |
| 13 | 68 | Dragonnia | 68 | 3: GLOBE_OF_INVULNERABILITY | 6: STORNOGS_SPHERES | - | - |
| 14 | 73 | The Prisons of Carthapia | 73 | 2: AWARENESS | 4: TOWER_OF_IRON_WILL | - | - |
| 15 | 91 | The Mountain of the Banished | 91 | 2: FARSEE | 4: FLY | - | - |
| 16 | 93 | Tower of High Sorcery | 93 | 3: AWARENESS | 4: TOWER_OF_IRON_WILL | - | - |
| 17 | 94 | Sarmiz'Duul | 94 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 18 | 103 | Village of Split Shield | 103 | 2: ARMOR | 3: THORNSKIN | - | - |
| 19 | 106 | Pragtog's Domain | 106 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 20 | 112 | Arena of the Elder Brain | 112 | - | - | - | not connected, no mobs, blank |
| 21 | 113 | The Outcasts Tower | 113 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_GOOD | - | - |
| 22 | 130 | The Citadel | 130 | 2: FARSEE | 4: FLY | - | - |
| 23 | 140 | The Faerie Realm | 140 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 24 | 143 | Nakral''s Crypt | 143 | 2: PROTECTION_FROM_UNDEAD | 3: NEGATIVE_ENERGY_BARRIER | - | - |
| 25 | 151 | New Cave City | 151 | 2: PROTECTION_FROM_UNDEAD | 3: NEGATIVE_ENERGY_BARRIER | - | - |
| 26 | 152 | Faang | 152 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 27 | 159 | Pit of Dragons | 159 | 1: INFRAVISION | 3: ULTRAVISION | - | - |
| 28 | 160 | Pine Hollow | 160 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 29 | 162 | The Transparent Tower | 162 | 2: FLY | 3: HASTE | - | - |
| 30 | 165 | Woodseer | 165 | 3: LEVITATE | 4: FARSEE | - | - |
| 31 | 170 | Khildarak Stronghold | 170 | 2: ARMOR | 4: THORNSKIN | - | - |
| 32 | 196 | Tiamat | 196 | 2: HASTE | 3: SNEAK | - | - |
| 33 | 197 | The Astral Plane | 197 | 2: TOWER_OF_IRON_WILL | 5: DISPLACEMENT | - | - |
| 34 | 200 | Krethik Keep | 200 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 35 | 202 | Shairak and Smokeveil Forest | 202 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 36 | 213 | Mazzolin | 213 | 2: LEVITATE | 4: PANTHERSPEED | - | - |
| 37 | 215 | The Forest City of Aravne | 215 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 38 | 220 | Pits of Cerberus | 220 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 39 | 222 | Desolate | 222 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 40 | 224 | Storm Port | 224 | 2: PROTECTION_FROM_GOOD | 3: PROTECTION_FROM_EVIL | - | - |
| 41 | 226 | Storm Port Stronhold | 226 | 2: ARMOR | 4: SOULSHIELD | - | - |
| 42 | 232 | Plane of Water | 232 | 2: WATER_BREATHING | 5: STONE_SKIN | - | - |
| 43 | 238 | Plane of Earth | 238 | 2: BARKSKIN | 4: STONE_SKIN | - | - |
| 44 | 244 | Plane of Air | 244 | 3: HASTE | 5: STONE_SKIN | - | - |
| 45 | 250 | Plane of Fire, Brass | 1390 | 2: FIRESHIELD | 3: ILIENZES_FLAMING_SWORD | - | - |
| 46 | 257 | Bahamut's Palace | 257 | 2: FLY | 4: AIR_FORM | - | - |
| 47 | 260 | Swamp | 260 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD | - | - |
| 48 | 262 | Moonshae Island | 262 | 2: BARKSKIN | 3: FARSEE | - | - |
| 49 | 266 | Negative Material Plane | 266 | 2: NEGATIVE_ENERGY_BARRIER | 4: NEGATIVE_FEEDBACK_BARRIER | - | - |
| 50 | 270 | The Halfcut Hills | 270 | 2: PROTECTION_FROM_FIRE | 3: FIRESHIELD | - | - |
| 51 | 289 | Kingdom of Torg | 289 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 52 | 294 | Harrow - The Gnome Village | 294 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 53 | 306 | Vast Hidden Grove | 306 | 2: ARMOR | 3: BARKSKIN | - | - |
| 54 | 308 | Strathor Valley of the Storm Giants | 308 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 55 | 311 | The Mountain Settlement of the Harpies | 311 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 56 | 313 | Drifting Realm | 313 | 2: FLY | 4: INVISIBLE | - | - |
| 57 | 315 | Sea Kingdom | 315 | 2: COLDSHIELD | 3: thryms icerazor | - | - |
| 58 | 328 | Thre Great Shaboath | 328 | 2: COMBAT_MIND | 3: DETECT_INVISIBLE | - | - |
| 59 | 333 | Killing Fields | 333 | 2: PROTECTION_FROM_GOOD | 3: PROTECTION_FROM_EVIL | - | - |
| 60 | 335 | The Bloody Plains | 335 | 2: PROTECTION_FROM_GOOD | 3: PROTECTION_FROM_EVIL | - | - |
| 61 | 342 | Clan Stoutdorf Settlement | 342 | 4: HASTE | 5: FLY | - | - |
| 62 | 360 | Arachdrathos Wilderness | 360 | 2: LEVITATE | 3: FARSEE | - | - |
| 63 | 368 | Domain of Lost Souls | 368 | 3: GLOBE_OF_DARKNESS | 7: STONE_SKIN | - | - |
| 64 | 371 | Du'Maathe Castle | 371 | 4: HASTE | 5: FLY | - | - |
| 65 | 377 | Nax | 377 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 66 | 391 | Ugta | 391 | 4: REGENERATION | - | - | - |
| 67 | 402 | Pharr Valley | 402 | 2: ARMOR | 3: BARKSKIN | - | - |
| 68 | 285 | Pharr Valley Swamp | 285 | 2: PROTECTION_FROM_UNDEAD | 4: SOULSHIELD | - | - |
| 69 | 419 | Forest of Mir | 419 | 2: ARMOR | 3: SOULSHIELD | - | - |
| 70 | 441 | Lost Temple of Tikizopl | 441 | 5: CHAOS_SHIELD | - | - | - |
| 71 | 448 | The Keep of Evil | 448 | 2: ULTRAVISION | 4: INVISIBLE | - | - |
| 72 | 450 | Charing | 450 | 3: LEVITATE | 4: PANTHERSPEED | - | - |
| 73 | 480 | Guildhalls | 480 | - | - | - | player created guildhalls, blank |
| 74 | 510 | Hell, Avernus | 510 | 4: STONE_SKIN | 8: INFERNAL_FURY | - | - |
| 75 | 662 | The Ruins of Tharnadia's Old Quarter | 662 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD | - | - |
| 76 | 671 | Father Tel's Holy Cloister | 671 | 2: SENSE_LIFE | 3: SOULSHIELD | - | - |
| 77 | 676 | Taliccicopiid | 676 | 2: ARMOR | 3: BARKSKIN | - | - |
| 78 | 700 | The Town of Moregeeth | 700 | 3: LEVITATE | 4: PANTHERSPEED | - | - |
| 79 | 710 | The Fields Between | 710 | 2: BARKSKIN | 6: STONE_SKIN | - | - |
| 80 | 756 | The Obsidian Citadel | 756 | 2: FARSEE | 4: FLY | - | - |
| 81 | 758 | Rogue Plains | 758 | 2: FARSEE | 3: FLY | - | - |
| 82 | 800 | Rift Valley Jungle | 800 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 83 | 824 | The Temple of the Sun | 824 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD | - | - |
| 84 | 856 | An Ancient Bridge | 856 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_UNDEAD | - | - |
| 85 | 857 | Arcium, The Plagued Kingdom | 857 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 86 | 936 | Vella's Bordello | 936 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 87 | 955 | Kimordril | 955 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 88 | 960 | Jotunheim | 960 | 2: BARKSKIN | 5: STONE_SKIN | - | - |
| 89 | 964 | Ixarkon | 964 | 3: LEVITATE | 4: SENSE_LIFE | - | - |
| 90 | 975 | Shady Grove | 975 | 3: BLESS | 4: VAPOR_STRIKE | - | - |
| 91 | 987 | The Undead Outpost | 987 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 92 | 1325 | Tharnadia - City of Humans | 1325 | 3: ARMOR | 4: BARKSKIN | - | - |
| 93 | - | Ceothia 1 | 808 (present; selected) | 2: BARKSKIN | 6: STONE_SKIN | - | - |
| 94 | - | Ceothia 2 | 811 (past; selected) | 2: BARKSKIN | 5: STONE_SKIN | - | - |
| 95 | - | Ceothia 3 | 814 (future; selected) | 2: BARKSKIN | 4: STONE_SKIN | - | - |
| 96 | - | The Stone Tomb of Kelek | 879 | 2: PROTECTION_FROM_UNDEAD | 4: NEGATIVE_ENERGY_BARRIER | - | - |
| 97 | - | Myrabolus | 825 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 98 | - | Forgotten Forest | 827 | 2: LEVITATE | 3: PANTHERSPEED | - | - |
| 99 | - | Darkfall Forest | 953 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 100 | - | Haunted Woods | 108 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_LIVING | - | - |
| 101 | - | Centaur Villages | 933 | 2: ARMOR | 3: THORNSKIN | - | - |
| 102 | - | Darkmore Forest | 57 (superseded by row 269) | 2: ARMOR | 3: BLESS | - | - |
| 103 | - | Quintaragon Castle | 24 | 2: PROTECTION_FROM_FIRE | 4: FIRESHIELD | - | - |
| 104 | - | Defense of Longhollow | 344 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD | - | - |
| 105 | - | Shaledrieth | 536 (superseded by row 266) | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_GOOD | - | - |
| 106 | - | High Moor Forest | 191 | 1: FARSEE | 3: FLY | - | - |
| 107 | - | Neverwinter Woods | 990 | 2: PROTECTION_FROM_COLD | 4: COLDSHIELD | - | - |
| 108 | - | Neverwinter Valley | 204 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD | - | - |
| 109 | - | Elemental Groves | 38 | 1: PROTECTION_FROM_ACID | 2: PROTECTION_FROM_LIGHTNING | - | - |
| 110 | - | Southern Coastal Highway | 413 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 111 | - | The Ship Yards | 431 | 2: LEVITATE | 5: FLY | - | - |
| 112 | - | Bandit Canyons | 985 | 2: SENSE_LIFE | 4: AWARENESS | - | - |
| 113 | - | Lylr-Meop | 822 | 2: ARMOR | 3: BARKSKIN | - | - |
| 114 | - | The Motte and Bailey of Duke Delwyn | 828 | 2: LEVITATE | 3: FARSEE | - | - |
| 115 | - | Kvark's Great Connector | 546 | 3: SOULSHIELD | 4: HASTE | - | - |
| 116 | - | Abandoned Elven Homestead | 358 | 2: FARSEE | 4: HASTE | - | - |
| 117 | - | Ashrumite Village | 660 | 3: LEVITATE | 4: SENSE_LIFE | - | - |
| 118 | - | Bandit Camp | 148 | 2: SENSE_LIFE | 4: AWARENESS | - | - |
| 119 | - | Shadowclave | 939 | 2: ARMOR | 3: BLESS | - | - |
| 120 | - | The Mountain Village of Tentro | 690 | 2: ARMOR | 3: BARKSKIN | - | - |
| 121 | - | Cloud Giant Kingdom | 995 | 3: LIFELUST | 4: LIONRAGE | - | - |
| 122 | - | The City of Newhaven | 352 | 2: PROTECTION_FROM_UNDEAD | 4: PROTECTION_FROM_LIVING | - | - |
| 123 | - | Twin Towers Forest | 135 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 124 | - | Golden Hall of the Crown | 404 | 2: WATER_BREATHING | 4: HASTE | - | - |
| 125 | - | Arbre's Forest | 974 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 126 | - | Home of the Divine | 407 | 3: FIRESHIELD | 4: SOULSHIELD | - | - |
| 127 | - | The Savannah of Broken Trusts | 1385 | 2: BARKSKIN | 4: AWARENESS | - | - |
| 128 | - | Plane of Fire | 254 | 2: FIRESHIELD | 5: STONE_SKIN | - | - |
| 129 | - | The Twin Keeps of Devastated Tharnadia | 784 | 3: PROTECTION_FROM_LIVING | 4: SOULSHIELD | - | - |
| 130 | - | Fisherman's Wharf | 889 | 2: ARMOR | 3: THORNSKIN | - | - |
| 131 | - | Jenna's Waystation | 57 (superseded by row 269) | 2: LEVITATE | 3: PANTHERSPEED | - | - |
| 132 | - | A Dark and Twisted Wood | 163 | 2: LEVITATE | 3: FARSEE | - | - |
| 133 | - | Lord Krimeneha's Mansion | 164 | 2: ARMOR | 3: BARKSKIN | - | - |
| 134 | - | Braddistock Mansion | 13 + 1350 (confirmed) | 2: ARMOR | 4: BARKSKIN | - | - |
| 135 | - | The Village of New Hope | 890 | 3: COLDSHIELD | 4: SOULSHIELD | - | - |
| 136 | - | Wellvolen | 935 | 2: ELEPHANTSTRENGTH | 3: LIONRAGE | - | - |
| 137 | - | Nizari | 400 | 3: AWARENESS | 5: FLY | - | - |
| 138 | - | The Cimmerian Nomad Encampment | 62 | 1: PROTECTION_FROM_COLD | 2: COLD_WARD | - | - |
| 139 | - | City of Torrhan | 666 | 2: LEVITATE | 4: FLY | - | - |
| 140 | - | The Deep Ravine of Passage | 947 | 1: PROTECTION_FROM_FIRE | 3: FIRESHIELD | - | - |
| 141 | - | Mistywood | 950 | 2: VAPOR_STRIKE | 4: HAWKVISION | - | - |
| 142 | - | The Ruins of Turolopolis | 71 | 1: PROTECTION_FROM_FIRE | 2: FIRE_WARD | - | - |
| 143 | - | Lair of the Asunwa Jaguar | 353 (inactive) | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 144 | - | Tribal Oasis | 780 | 3: HASTE | 4: FLY | - | - |
| 145 | - | Tribal Forest | 422 | 2: FARSEE | 4: FLY | - | - |
| 146 | - | Mosswood | 234 | 2: LEVITATE | 4: PANTHERSPEED | - | - |
| 147 | - | The Basin Wastes | 340 | 2: SENSE_LIFE | 4: DETECT_INVISIBLE | - | - |
| 148 | - | Khazan Jungle | 670 (inactive) | 2: ARMOR | 3: THORNSKIN | - | - |
| 149 | - | Jindon the Deathwood Forest | 820 | 2: ARMOR | 3: SOULSHIELD | - | - |
| 150 | - | The Battlefield | 664 | 2: FIRESHIELD | 3: SOULSHIELD | - | - |
| 151 | - | The Shadow Forest | 63 | 2: LEVITATE | 3: FARSEE | - | - |
| 152 | - | Village of Refugees | 986 | 2: LEVITATE | 4: PANTHERSPEED | - | - |
| 153 | - | The Trakkia Mountains | 570 | 2: COLDSHIELD | 3: SOULSHIELD | - | - |
| 154 | - | Enclave of Opal Phoenix | 708 | 1: PROTECTION_FROM_COLD | 2: COLD_WARD | - | - |
| 155 | - | The Chasm of the Misty Vale | 3000 | 2: ELEPHANTSTRENGTH | 3: LIONRAGE | - | - |
| 156 | - | The Rice Fields | 772 | 2: COLDSHIELD | 4: SOULSHIELD | - | - |
| 157 | - | The Jade Empire | 766 | 3: HASTE | 4: FLY | - | - |
| 158 | - | Mitashi | 1382 | 2: FARSEE | 3: HASTE | - | - |
| 159 | - | Malch'Hor Ganl the Goblin City | 236 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 160 | - | The Docks of Quietus Quay | 17 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 161 | - | Troll Caves | 969 | 1: PROTECTION_FROM_FIRE | 2: FIRE_WARD | - | - |
| 162 | - | Goblin Camp | 114 | 2: ARMOR | 3: THORNSKIN | - | - |
| 163 | - | The Hall of Knighthood | 709 | 2: HASTE | 4: DAZZLE | - | - |
| 164 | - | Orrak | 90 | 2: FIRESHIELD | 4: SOULSHIELD | - | - |
| 165 | - | Arlik's Inn | 57 (superseded by row 269) | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 166 | - | Vargan II | 78 | 1: LEVITATE | 3: PANTHERSPEED | - | - |
| 167 | - | The Temple of Lizizania | 92 | 1: PROTECTION_FROM_COLD | 2: COLD_WARD | - | - |
| 168 | - | Skulldrach | 127 | 2: ARMOR | 3: SENSE_LIFE | - | - |
| 169 | - | Village of the Damned | 806 | 3: HASTE | 4: FLY | - | - |
| 170 | - | Drustl's Yerdonia Enslaved | 429 | 1: PROTECTION_FROM_FIRE | 3: FIRESHIELD | - | - |
| 171 | - | Mountain Tracts of the Untamed | 209 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 172 | - | The Lost Realms of Shadowfall | 180 | 2: COLD_WARD | 3: FIRE_WARD | - | - |
| 173 | - | Barrow of the Quiosho | 206 | 2: FIRE_WARD | 3: COLD_WARD | - | - |
| 174 | - | Dark Forest | 750 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 175 | - | Bugentolen | 958 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 176 | - | Ogre Raiders | 89 | 2: LEVITATE | 3: FARSEE | - | - |
| 177 | - | Treasure Caves | 930 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 178 | - | The Lair of the Swamp Troll King | 261 | 2: FIRE_SHIELD | 3: SOULSHIELD | - | - |
| 179 | - | The Scorched Valley | 712 | 2: HASTE | 4: SNEAK | - | - |
| 180 | - | Lost City of Tikizopl | 437 | 2: PROTECTION_FROM_UNDEAD | 4: NEGATIVE_ENERGY_BARRIER | - | - |
| 181 | - | Lava Springs | 997 | 2: LEVITATE | 3: FIRESHIELD | - | - |
| 182 | - | Undead Fog | 678 | 1: COLD_WARD | 3: COLDSHIELD | - | - |
| 183 | - | The Maze of Undead Army | 940 | 2: SOULSHIELD | 3: HASTE | - | - |
| 184 | - | Varathorn Keep | 994 | 1: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 185 | - | Ruined Temple of Tezcatlipoca | 989 | 2: PROTECTION_FROM_LIVING | 3: NEGATIVE_ENERGY_BARRIER | - | - |
| 186 | - | Tunnels of Payang | 903 | 1: ARMOR | 3: THORNSKIN | - | - |
| 187 | - | Ny'Neth | 229 | 2: GLOBE_OF_DARKNESS | 4: VAMPIRIC_TOUCH | - | - |
| 188 | - | Ny'Neth's Stronghold | 230 | 1: BARKSKIN | 3: IRONWOOD | - | - |
| 189 | - | Ny'Neth's Stronghold Continued | 387 | 2: LIFELUST | 6: BATTLE_ECSTASY | - | - |
| 190 | - | Tunnels of Cyric the Destroyer | 545 | 1: ARMOR | 3: THORNSKIN | - | - |
| 191 | - | Temple of Flames | 183 | 2: FIRESHIELD | 3: SOULSHIELD | - | - |
| 192 | - | The Forgotten Mansion | 35 | 2: COLDSHIELD | 3: SOULSHIELD | - | - |
| 193 | - | The Old Graveyard | 84 | 1: PROTECTION_FROM_FIRE | 3: FIRESHIELD | - | - |
| 194 | - | The Behemoth Herders | 943 | 3: FIRESHIELD | 5: NEGATIVE_ENERGY_BARRIER | - | - |
| 195 | - | Vecna's Tomb | 1300 | 2: ENDURANCE | 6: PASS_WITHOUT_TRACE | - | - |
| 196 | - | Zalkapfaan, City of the Headless Horde | 27 | 1: ELEPHANTSTRENGTH | 2: LIONRAGE | - | - |
| 197 | - | The Sky City of Ultarium | 760 | 2: FARSEE | 3: FLY | - | - |
| 198 | - | Githzerai Stronghold | 444 | 2: HASTE | 3: FLY | - | - |
| 199 | - | The Desert City of Venan'Trut | 490 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 200 | - | Fort Boyard | 381 | 3: HASTE | 4: FLY | - | - |
| 201 | - | Menden on the Deep | 888 | 2: ARMOR | 3: BARKSKIN | - | - |
| 202 | - | Tundra | 137 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD | - | - |
| 203 | - | Northern Lakes and Settlements | 752 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 204 | 755 | The Dark Stone Tower of the Northern Realms | 755 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 205 | - | The City of Winterhaven | 550 | 3: REGENERATION | 4: COMBAT_MIND | - | - |
| 206 | - | Verspin | 281 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 207 | - | Village of Werrun | 383 | 2: FIRESHIELD | 5: NEGATIVE_ENERGY_BARRIER | - | - |
| 208 | - | The Human Outpost | 821 | 1: ARMOR | 4: SOULSHIELD | - | - |
| 209 | - | Towering Glacier of Dayedenvale | 904 | 1: ARMOR | 2: PROTECTION_FROM_COLD | - | - |
| 210 | - | Ice Tower | 318 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 211 | - | The Church of the Eternal Dusk | 878 | 3: PROTECTION_FROM_LIVING | 4: SOULSHIELD | - | - |
| 212 | - | Ant Forest | 109 | 2: ARMOR | 3: BARKSKIN | - | - |
| 213 | - | Village of Miaeril | 337 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 214 | - | The Depths of Duris | 1200 | 2: PANTHERSPEED | 3: ENDURANCE | - | - |
| 215 | - | Alatorin - the Forge City | 831 | 3: HASTE | 5: DETECT_INVISIBLE | - | - |
| 216 | - | Sevenoaks | 386 | 2: FLY | 4: SNEAK | - | - |
| 217 | - | IceCrag Castle | 970 | 2: FARSEE | 4: HASTE | - | - |
| 218 | - | Crystalspyre Mountains | 370 | 2: ARMOR | 3: SOULSHIELD | - | - |
| 219 | - | Bloodstone Keep | 740 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 220 | - | The Caverns of the Worms | 69 | 2: LEVITATE | 3: FARSEE | - | - |
| 221 | - | The 222nd Layer of the Abyss | 875 | 2: HASTE | 3: BLUR | - | - |
| 222 | - | Morg's | 886 | 1: ARMOR | 2: BLESS | - | - |
| 223 | - | Gagga'Jobo Cave System | 190 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 224 | - | Myconids | 23 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 225 | - | Phantasmagoric Caverns | 531 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 226 | - | The Clawed Caverns | 807 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 227 | - | Orog hometown | 458 | 2: ARMOR | 4: THORNSKIN | - | - |
| 228 | - | The Underworld | 44 + 300 (confirmed) | 3: HASTE | 5: NEGATIVE_ENERGY_BARRIER | - | - |
| 229 | - | Bogentok | 187 | 2: FARSEE | 4: FLY | - | - |
| 230 | - | Lair of the Purple Worm | 425 | 4: HASTE | 5: FLY | - | - |
| 231 | - | The Bugger Caves | 64 | 2: ARMOR | 3: THORNSKIN | - | - |
| 232 | - | Lair of the Gibberling King | 87 | 3: AWARENESS | 4: SOULSHIELD | - | - |
| 233 | - | Arachdrathos Guilds | 367 | 2: LEVITATE | 3: FLY | - | - |
| 234 | - | llzazan Ghetto of Arachdrathos | 362 | 2: LEVITATE | 4: THORNSKIN | - | - |
| 235 | - | Arachdrathos - Drow City | 364 | 2: LEVITATE | 4: THORNSKIN | - | - |
| 236 | - | Valinhaven | 908 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 237 | - | Arcorar - The Great King Forest | omitted by owner | 2: BARKSKIN | 4: ENDURANCE | - | - |
| 238 | - | Court of the Muse | 67 | 2: BARKSKIN | 3: PANTHERSPEED | - | - |
| 239 | - | The Swamp Laboratory of Khul'Lor | 823 | 3: HASTE | 4: FLY | - | - |
| 240 | - | Myrloch Vale | 264 | 3: FLY | 4: HASTE | - | - |
| 241 | - | The Ruins of Undermountain | 920 | 2: ARMOR | 4: SOULSHIELD | - | - |
| 242 | - | The Githyanki Fortress | 1320 | 2: AWARENESS | 3: TOWER_OF_IRON_WILL | - | - |
| 243 | - | Desolate Under Fire | 773 | 1: INFRAVISION | 2: ULTRAVISION | - | - |
| 244 | - | Prison of Fort Boyard | 430 | 3: FLY | 4: HASTE | - | - |
| 245 | - | The Ancient Halls of Ironstar | 1389 | 3: PROTECTION_FROM_LIVING | 4: NEGATIVE_ENERGY_BARRIER | - | - |
| 246 | - | The Para-Elemental Plane of Smoke | 1398 | 2: FIRESHIELD | 5: STONE_SKIN | - | - |
| 247 | - | Shadamehr Keep | 412 | 2: PROTECTION_FROM_LIVING | 5: STONE_SKIN | - | - |
| 248 | - | The Temple to Skrentherlog | 805 | 1: SLOW_POISON | 3: ENDURANCE | - | - |
| 249 | - | Dreggan Woods | 410 | 2: COMBAT_MIND | 5: DISPLACEMENT | - | - |
| 250 | - | Valley of the Snow Ogres | 877 | 3: DAZZLE | 4: GLOBE_OF_INVULNERABILITY | - | - |
| 251 | - | The Tempest Court | 1316 | 2: LIGHTNING_SHIELD | 3: lliendils stormshock | - | - |
| 252 | - | The Realm of Barovia | 910 | 3: DETECT_INVISIBLE | 4: GLOBE_OF_INVULNERABILITY | - | - |
| 253 | - | The Royal Mausoleum of Castle IceCrag | 1424 | 3: CONJURE_ELEMENTAL | 6: WATER_FORM | - | - |
| 254 | - | The Ethereal Plane | 124 | 4: DETECT_INVISIBLE | 5: STONE_SKIN | - | - |
| 255 | - | The Fortress of Dreams | 326 | 2: DETECT_ILLUSION | 3: DETECT_INVISIBLE | - | - |
| 256 | - | The Charcoal Palace | 883 | 2: FIRESHIELD | 4: FIRE_FORM | - | - |
| 257 | - | Apocalypse Castle | 345 | 3: DISPLACEMENT | 5: CHAOS_SHIELD | - | - |
| 258 | - | The Realm of Barovia Continued | 588 | 2: DETECT_INVISIBLE | 3: DETECT_ILLUSION | - | - |
| 259 | - | The Hall of the Ancients | 777 | 3: FLY | 4: DETECT_INVISIBLE | - | - |
| 260 | - | The Bronze Citadel | 324 | 2: PROTECTION_FROM_LIVING | 3: VAMPIRIC_TOUCH | - | - |
| 261 | - | Celestial Plane | 455 | 3: WARRING_ZEAL | 5: DIVINE_FURY | 7: BATTLE_TIDE | - |
| 262 | - | Castle Ravenloft | 583 | 3: BIOFEEDBACK | 4: INERTIAL_BARRIER | - | - |
| 263 | - | Bastine Castle | 76 | 2: BLESS | 3: FARSEE | - | - |
| 264 | - | The Temple of Laduguer | 81 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD | - | - |
| 265 | - | The Halfling Silver Mine | 49 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 266 | - | The Great Realm of Duris | 536 | 2: LEVITATE | 8: STONE_SKIN | - | - |
| 267 | - | The Mountain of Peril Peaks | 575 | 2: HASTE | 3: DETECT_INVISIBLE | - | - |
| 268 | - | The Valoisian Castle | 384 | 3: HASTE | 4: FLY | - | - |
| 269 | - | Mini Zones | 57 | 1: HAWKVISION | 2: ELEPHANTSTRENGTH | - | - |
| 270 | - | Ard'gral, plane of dreams | 304 | 4: DETECT_ILLUSION | 5: STONE_SKIN | - | - |
| 271 | - | Astral Plane, Tiamat | 199 | 2: AWARENESS | 3: TOWER_OF_IRON_WILL | - | - |
| 272 | - | Black Tunnels | 107 | 1: ARMOR | 3: THORNSKIN | - | - |
| 273 | - | The Mountain Valley of Dawndale | 775 | 3: FLY | 4: DETECT_INVISIBLE | - | - |
| 274 | - | Dirk'nspire Stronghold | 968 | 2: LEVITATE | 3: FARSEE | - | - |
| 275 | - | Githyanki Hometown | 194 | 2: ARMOR | 4: BARKSKIN | - | - |
| 276 | - | Ixxillikor | 42 | 2: FARSEE | 3: SENSE_LIFE | - | - |
| 277 | - | Lava Tubes | 120 | 2: LEVITATE | 3: SENSE_LIFE | - | - |
| 278 | - | Llyrath Forest | 949 | 2: ARMOR | 3: BARKSKIN | - | - |
| 279 | - | The Caverns of Armageddon | 133 | 3: REGENERATION | 4: COMBAT_MIND | - | - |
| 280 | - | The Minor Plane of Planitude | 34 | 2: LEVITATE | 3: THORNSKIN | - | - |
| 281 | - | The Mushroom Forest | 101 | 2: BLESS | 3: VAPOR_STRIKE | - | - |
| 282 | - | The Shaughin Settlement | 65 | 2: PANTHERSPEED | 4: FLY | - | - |
| 283 | - | The Temple of Blipdoolpoolp | 882 | 2: ARMOR | 4: SOULSHIELD | - | - |
| 284 | - | The Underground Lava Caves | 355 | 2: FIRESHIELD | 5: SOULSHIELD | - | - |
| 285 | - | The Underdark | 240 | 3: NEGATIVE_ENERGY_BARRIER | 5: HASTE | - | - |
| 286 | - | Traoul's Lair | 70 | 2: THORNSKIN | 3: FARSEE | - | - |
| 287 | - | Truktakyagyo | 16 | 2: ARMOR | 3: THORNSKIN | - | - |
| 288 | - | Turolopolis Zoo | 530 | 1: PROTECTION_FROM_FIRE | 3: FIRE_SHIELD | - | - |
| 289 | - | whatever the zone name is for pirate random eq | 600 (ship origin) | 3: PANTHERSPEED | 4: FLY | - | - |
| 290 | 48 | The Monestary of Tranquility | 48 | 2: ACCELERATED_HEALING | 3: REGENERATION | - | - |
| 291 | 55 | The Tharnadian Ruin | 55 | 3: PROTECTION_FROM_LIVING | 4: SOULSHIELD | - | - |
| 292 | 66 | The Shaughin Hunting Grounds | 66 | 3: LIFELUST | 4: LIONRAGE | - | - |
| 293 | 115 | Ghore | 115 | 4: REGENERATION | - | - | - |
| 294 | 132 | The Twin Towers | 132 | 2: LEVITATE | 4: FARSEE | - | - |
| 295 | 198 | Astral Plane, Side Areas | 198 | 2: TOWER_OF_IRON_WILL | 5: DISPLACEMENT | - | - |
| 296 | 241 | the Mushroom Caverns | 241 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH | - | - |
| 297 | 292 | Ailvio, Duris Newbie Outpost | 292 | 2: ARMOR | 3: BLESS | - | - |
| 298 | 320 | The Plane of Avernus | 320 | 4: STONE_SKIN | 8: INFERNAL_FURY | - | - |
| 299 | 435 | Temple of the Earth | 435 | 4: CONJURE_ELEMENTAL | 7: EARTH_FORM | - | - |
| 300 | 529 | the Lost Temple of the North | 529 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD | - | - |
| 301 | 532 | The Orcish Slave Camp | 532 | 2: ARMOR | 3: BLESS | - | - |
| 302 | 590 | The Ravenloft Catacombs | 590 | 3: STONE_SKIN | 6: SANCTUARY | - | - |
| 303 | 885 | The Minizones of the Underdark | 885 | 6: STONE_SKIN | - | - | - |
| 304 | 900 | The Fog Enshrouded Wood | 900 | 2: SENSE_LIFE | 3: FARSEE | - | - |
| 305 | 914 | Wutvr, Duris Newbie Outpost | 914 | 2: ARMOR | 3: BLESS | - | - |
| 306 | 954 | Troll Slave Compound | 954 | 2: ARMOR | 3: BLESS | - | - |
| 307 | 979 | The Minizones of the Surface | 979 | 6: STONE_SKIN | - | - | - |
| 308 | 1310 | The BrimStone Forge | 1310 | 2: COMBAT_MIND | 4: LIFELUST | - | - |
| 309 | 1312 | Grumbar's Domain | 1312 | 3: GIRILALS GRANITE HAMMER | 4: STONE_SKIN | - | - |
| 310 | 4020 | The Arcaneum of L'srillizzin | 4020 | 3: INTELLECT_FORTRESS | 5: FLY | - | - |
| 311 | 1301 | The Reliquary Nexus of Aggression | 1301 | 4: VAMPIRIC_TOUCH | 5: STONE_SKIN | - | - |
| 312 | 1302 | The Reliquary Nexus of The Dead | 1302 | 4: VAMPIRIC_TOUCH | 5: STONE_SKIN | - | - |
| 313 | 1303 | The Reliquary Nexus of the Corsairs | 1303 | 4: VAMPIRIC_TOUCH | 5: STONE_SKIN | - | - |
| 314 | 1304 | The Reliquary Nexus of the Roper Den | 1304 | 4: VAMPIRIC_TOUCH | 5: STONE_SKIN | - | - |
