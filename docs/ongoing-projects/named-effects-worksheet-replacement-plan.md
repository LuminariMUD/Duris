# Named effects: worksheet replacement plan

Status: proposed implementation plan; only Arcorar's identity remains unresolved.
Date: 2026-11-10.
Source reviewed: `9652c5296a254cc807a2d07f7fc0e84b4b94942d`.

## Outcome and scope

Replace the zone-set effect assignments displayed by `namedreport` with the
choices and piece requirements in **random named effects new.xlsx**. Keep
`namedreport` as the command that reports the actual gameplay catalog. For each
accepted worksheet zone, replace its entire old tier list with the two supplied
tiers; do not append them to the old bonuses or leave an old third tier behind.

This document is the plan only. Implementation, gameplay qualification, and
production publication are subsequent work. The worksheet supplies effect choices,
not operational instructions.

Use the existing catalog, origin metadata, affect ownership, and report cache.
Preserve named-drop probabilities, random item modifiers, weapon procs, roaming
spawn selection, the worn-armor driver, weapon contribution, excluded belt slots,
and MariaDB item persistence. Preserve matching-set HP as
`max(0, 5 * (matching_pieces - 2))`, subject to the existing gear HP cap.
No runtime spreadsheet reader, new configuration service, new persistence format,
or general effect framework is needed.

**Confirmed missing-choice policy:** zones omitted from the worksheet or left
without effect choices receive **no named-set spell bonuses**. Preserve the
existing matching-set HP rules. Remove their old spell tiers rather than keeping
them as a fallback. A new zone with blank choices gets no spell-catalog entry.
Rows that supply choices receive an explicit disposition below. Arcorar remains
unmapped; its choice is preserved without assigning it to a guessed zone.

## Decisions supplied for the gaps

The user supplied Tiu's clarification on 2026-11-10: use the same choices for both
Braddistocks, both Underworlds, and every Reliquary; leave missing choices without
effects. Apply each worksheet pair with its original piece thresholds:

| Zones | Final planned choices | Worksheet row |
| --- | --- | --- |
| Braddistock Mansion **#13 and #1350** | **2 pieces: Armor; 4 pieces: Barkskin** | 133 |
| The Underworld **#44 and #300** | **3 pieces: Haste; 5 pieces: Negative Energy Barrier** | 227 |
| Reliquary Nexus **#1301, #1302, #1303, #1304** | **4 pieces: Vampiric Touch; 5 pieces: Stone Skin** | 185 |
| Blank **#112 and #480**, plus the 23 unmatched current zones in the CSV | **No spell bonuses; existing matching-set HP rules remain** | 20, 72, or absent |

This resolves all **33 records** in the
[gap CSV](named-effects-missing-choices.csv): **25 HP-only decisions** and
**8 shared-pair assignments**. Of the 25, **24 currently have spell bonuses to
remove**; Guildhalls #480 already has no spell-catalog entry. The CSV retains
the current effects for comparison and records the final planned disposition.
These decisions are recorded in documentation; gameplay has not been changed.

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

Workbook: `C:\Users\apexw\Downloads\random named effects new.xlsx`.
Worksheet: `Sheet4`, source values in `A1:F288`; row 289 contains no values.
SHA-256: `0fae6fbffb3a4129dd98985485b1311b567cf1e7d3a02d3eef9f0eb210f3e62f`.

- Columns A/B identify the zone. C/D are pieces/effect for tier 1; E/F are
  pieces/effect for tier 2. Piece counts are thresholds, not effect strength.
- There are **287 named rows**, including **285 complete two-tier choices**
  (**570 tier selections**) and two rows with all four choice cells blank.
- **90 rows have a numeric zone ID; 197 do not.** Resolve names against active
  zone headers in [areas/AREA](../../areas/AREA), then use numeric identity.
- There are **28 one-piece tiers**, and supplied thresholds range from 1 to 8.
  Preserve those numbers; raising every one-piece tier to two would change the
  worksheet's choices.
- The workbook uses 52 distinct effect strings. Sixteen spell-name spellings
  need normalization. Awareness, Sneak, and Ultravision require actual support,
  not spelling fixes. After normalization there are 48 existing spell IDs plus
  those three requested effect concepts.
- All choice rows have both complete pairs. There are no formulas or comments
  in the source sheet. The appendix preserves every row and original effect
  spelling so implementation does not depend on an untracked Downloads file.

Current [named_sets.c](../../src/item/named_sets.c) contains **298 sets, 389 tiers,
and 106 distinct effect constants**. Its three-slot structure already accommodates
the worksheet's two-tier rows.

With the resolutions below, the implementation target is **283 zone definitions
and 566 tiers**, excluding the unresolved Arcorar row. This replaces **274**
current definitions, removes spell bonuses from **24** current zones, and adds
**9** loaded zone definitions. The 283 definitions come from **278 worksheet
choice rows**, with five extra definitions from the Braddistock, Underworld, and
Reliquary expansions. Of the other seven populated choice rows, four subarea
choices are superseded by their exact parent-zone rows, two target unloaded
areas, and one is Arcorar. The two blank rows remain HP-only.

## Reconcile zone identities before editing the catalog

Match by numeric ID when ID and name agree. Normalize case, MUD color codes,
punctuation, and obvious title typos for comparison, while retaining the original
worksheet text in the appendix. Never use fuzzy matching as the final identity
rule. The following are concrete exceptions.

| Sheet row(s) | Source issue | Planned resolution or decision |
| --- | --- | --- |
| 6, 223 | Row 6 says ID 23 / The Seacaves. Active #23 is Myconid Mushroom Forest; The Seacaves is #22. Row 223 separately says Myconids. | Source-resolved correction: row 6 → **#22**, row 223 → **#23**. Preserve the original worksheet ID in the appendix. |
| 45, 127 | Row 45 gives stale ID 250 for Plane of Fire, Brass. | Source-resolved correction: row 45 → **#1390** (`brass.zon`). Row 127 is the separate **#254** Plane of Fire. Do not revive #250 or merge the two areas. |
| 92–94 | Ceothia 1/2/3 share the same displayed zone title. | **Chosen interpretation:** **#808 present / #811 past / #814 future**, in authored `areas/AREA` order (`ceothia`, `ceopast`, `ceofutur`). Keep Barkskin at 2 and Stone Skin at 6/5/4 respectively. This is an explicit planning inference, not a worksheet-provided ID. |
| 101, 130, 164, 268 | Darkmore Forest, Jenna's Waystation, and Arlik's Inn are subareas in `minizones.wld`; row 268 separately assigns Mini Zones. | **Resolved by exact-zone precedence:** use row **268** for **#57**: Hawkvision at 1, Elephantstrength at 2. Rows 101/130/164 are superseded alternatives, preserved in the appendix. They cannot have independent grants without changing origin identity. |
| 104, 265 | Shaledrieth appears inside `connectorzones.wld`; row 265 already assigns The Great Realm of Duris. | **Resolved by exact-zone precedence:** use row **265** for **#536**: Levitate at 2, Stone Skin at 8. Row 104 is superseded. Keep one definition for the actual shared origin. |
| 107 | Neverwinter Valley differs from the active title. | Source-resolved correction: **#204 Neverwind Valley**; keep it separate from **#990 Neverwinter Woods** (row 106). |
| 133 | Braddistock Mansion matches both **#13** and **#1350**. | **Resolved:** apply row 133's pair to both independent IDs. Preserve ambiguous legacy items' HP-only identity behavior. |
| 142 | Lair of the Asunwa Jaguar exists as `asunwa.zon`, ID **#353**, but `asunwa` is commented out in `areas/AREA`. | **Resolved as inactive:** omit this definition from the running catalog and preserve its choices for a future area activation. This replacement does not load retired areas. |
| 147 | `jungle.zon` identifies **#670 Jungle of Khazan**; `jungle` is commented out in `areas/AREA`. | **Resolved as inactive #670:** omit the unloaded definition and preserve Armor at 2 / Thornskin at 3 for any future activation. Terrain references elsewhere do not transfer this choice to #240. |
| 153, 157, 179, 212, 221, 223, 226, 282 | Abbreviated, uncertain, reordered, or misspelled names. | Source-resolved mappings: **#708** Enclave of the Opal Phoenix; **#1382** Mitashi; **#437** Lost City of Tikitzopl; **#337** Miaeril Village; **#886** Morg's Place; **#23** Myconid Mushroom Forest; **#458** Orog Encampment; **#882** Temple of Blibdoolpoolp. |
| 185 | “all the Nexuses” is a group choice, not one zone. | **Resolved:** apply row 185's pair to each Reliquary, **#1301–#1304**. **#575** keeps row 266's independent Mountain of Peril Peaks choice despite its `nexus.zon` filename. |
| 227 | The Underworld matches **#44** and **#300**. | **Resolved:** apply row 227's pair to both; do not merge their item origins. |
| 236 | Arcorar - The Great King Forest has no matching zone header or authored zone/room/mobile text, including a search with MUD colors removed. | **Only unresolved identity:** obtain its actual zone ID/current name, or explicitly omit it. Preserve Barkskin at 2 / Endurance at 4; do not choose a different forest by similarity. |
| 288 | Pirate random equipment uses the room of the kill. Ship interiors use the #600 room pool. | **Resolved:** **#600 The Adventurers Shipyards**, Pantherspeed at 3 / Fly at 4. This applies to named gear from the shared ship-zone origin, not exclusively pirate mobs, and is separate from **#431 The Ship Yards** (row 110). |

Straightforward spelling corrections also include Storm Port Stronhold → #226,
Thre Great Shaboath → #328, and Lost Temple of Tikizopl → #441. Corrections here
identify existing zones; they do not request renaming authored areas or old gear.

The two blank rows are **20: #112 Arena of the Elder Brain** and **72: #480
Guildhalls**. Both are explicitly HP-only under the confirmed policy. Remove
#112's current three spell tiers; #480 already has no spell-catalog entry.

Eight worksheet targets are absent from the current catalog and were
excluded in the earlier roster review: **#856** Ancient Bridge (row 83), **#546**
Kvark's Great Connector (114), **#904** Towering Glacier (208), **#1200** Depths of
Duris (213), **#773** Desolate Under Fire (242), **#536** Great Realm (265),
**#384** Valoisian Castle (267), and **#240** Underdark (284).
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
| `SPELL_MINOR_GLOBE_OF_INVULNERABILITY` | `SPELL_MINOR_GLOBE` | 61 |
| `SPELL_GLOBE_OF_INVULNERABILITY` | `SPELL_GLOBE` | 144 |
| `SPELL_TOWER_OF_IRON_WILL` | `SPELL_TOWER_IRON_WILL` | 260 |
| `SPELL_INVISIBLE` | `SPELL_INVISIBILITY` | 189 |
| `SPELL_FIRE_SHIELD` | `SPELL_FIRESHIELD` | 108 |
| `SPELL_LIGHTNING_SHIELD` | `SPELL_LIGHTNINGSHIELD` | 526 |

Three worksheet concepts are not registered callable spells. The following
behavior is now selected using the existing mechanics as the starting point:

- **Awareness:** ten selections, rows 14, 16, 33, 111, 117, 126, 136, 231, 241,
  270. `SKILL_AWARENESS` (#1024) is a skill implemented by `do_awareness` in
  [new_skills.c](../../src/classes/new_skills.c). Grant the **active Awareness
  affect**, using **effective rating `min(56, matching_pieces * 10)`** in the
  native modifier and duration calculations. This follows the existing set
  invocation scale instead of inventing a new progression. Reuse the native
  level/INT/DEX calculation and random roll, applying the resulting
  `SKILL_AWARENESS` affect through set ownership. Extract only the small shared
  application/calculation needed by the manual command and set caller. Do not
  alter learned skill ratings, train the skill, or run the command's messages.
- **Sneak:** three selections, rows 32, 178, 215. `SKILL_SNEAK` (#1000) has no
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
- **Ultravision:** three selections, rows 27, 70, 242. This is an innate/affect
  capability (`INNATE_ULTRAVISION`, `AFF2_ULTRAVISION`), not `SPELL_ULTRAVISION`.
  Register one self-targeted `SPELL_ULTRAVISION` effect with the next available
  spell ID and display name, without adding it to any class's learnable spells.
  Its handler grants only `AFF2_ULTRAVISION`; the set grant is non-saving and
  lasts while supported (`duration = -1` with existing set cleanup). Reuse normal
  affect recomputation so racial and other equipment Ultravision survive removal.

These **16 tier selections** cannot be satisfied by renaming the token. Keep
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
inactive area, or unresolved Arcorar. Flatten the confirmed groups into separate
zone definitions and check the **283-set / 566-tier** resolved target. Include
every current catalog zone absent from the accepted replacement list so none disappears by
accident. Apply the confirmed HP-only policy to those omissions. Revise the counts
only if the remaining Arcorar decision changes the target.

Retain source-row references and the alias map in repository documentation.
This is the reviewed input to the catalog and its tests; no Excel dependency is
needed at game startup or to run the regression suite.

### 2. Make the supplied tiers work through existing gameplay paths

Primary files: [named_sets.c](../../src/item/named_sets.c),
[specs.set.c](../../src/specs/specs.set.c), and, where required,
[named_set_effects.c](../../src/item/named_set_effects.c).

- Replace each accepted catalog entry's old tiers with the two normalized
  choices. Zero the unused third slot. Leave the three-slot structure intact.
- Remove spell-catalog entries for the 24 current sets now designated HP-only.
  Do not encode them as all-zero definitions: `validate_named_sets` rejects
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
- **New native spell coverage:** Ironwood (#237), Inertial Barrier (#180), Tower
  of Iron Will (#260), and Lightning Shield (#526) have native handlers but are
  not in the current catalog. Qualify them and add the existing
  `named_set_ordinary_cast` guard where needed; the inspected handlers currently
  lack that guard. Reuse ownership/suspension machinery, not a second affect system.
- **Ironwood:** row 189 supplies Barkskin at one piece and
  Ironwood at three. Preserve its wood-skin prerequisite and finite absorption.
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
at one/two pieces, native stacking restrictions, and Ironwood's generic skin cooldown.
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
  effect support checks, and report execution. Assert exact two-tier replacements
  and no leftover third tiers. Account explicitly for HP-only and deferred zones
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
- `test_named_set_cooldowns.py` and `test_named_set_report_cache_live.py`:
  preserve Stone Skin timers across re-equip/relog/driver changes, verify
  Ironwood cooldown state through the same transitions, and verify identical
  complete reports with fresh and stale cache states. Keep the no-Redis fallback.
- Existing native wear/report/transfer journeys: exercise representative one-piece,
  two-tier, special-effect, and shared-title sets. Load previously owned items with
  stored origins, confirm the new bonuses without rerolling gear, then remove,
  save, and reload. Cover losing old bonuses as well as gaining new ones. Update
  journey expectations that currently hardcode the previous Tharnadia tiers.
- HP-only transition: use #112 and an omitted current set to prove all former
  spell bonuses disappear while item origins and matching-set HP survive. Test
  a removed catalog entry, not only a changed tier in an entry that remains.

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
migration is expected for this catalog change. Keep ambiguous legacy-title gear
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

## Completion criteria and the remaining question

The implementation is complete when all worksheet rows have an explicit
disposition, every accepted tier is reachable at its exact supplied count, actual
effects and `namedreport` agree, retired tiers disappear, existing item identities
survive reload, and the focused checks above pass. Do not describe a partial
import that skips the three unsupported effect concepts as a full replacement.

**Only row 236 remains unresolved: Arcorar - The Great King Forest.** Its choices
are Barkskin at 2 and Endurance at 4, but the current repository supplies no
matching identity. A search of all authored zone, room, and mobile files, with
MUD colors removed, found neither “Arcorar” nor “Great King Forest”. To close it,
provide the actual numeric zone ID/current zone name, or explicitly omit that row.
Do not substitute an unrelated forest. Keep it outside the 283 resolved
definitions until that decision is recorded.

All other former questions now have a selected implementation rule: authored
Ceothia order, exact-zone precedence for shared subareas, inclusion of the nine
loaded additions, omission of the two unloaded areas, #600 ship origin, the
three active-effect semantics, native armor coexistence, and Ironwood's existing
generic skin cooldown. These choices use the user's delegation to resolve
reasonable defaults; they are distinguished from facts explicitly present in
the worksheet.

Implementation and gameplay proof are still required. In particular, qualify
one-piece activation, the new effect paths, ordinary-effect coexistence, cooldowns,
cache refresh, persistence, and removal of old grants. Those are engineering work,
not unanswered worksheet choices. Do not describe the whole worksheet replacement
as complete while Arcorar has no disposition.

Planning validation performed: read-only extraction of the entire worksheet,
counts and effect-token comparison against current source, active zone-header
reconciliation, and inspection of the relevant runtime/report/test paths.
The 283 resolved definitions were checked for unique loaded zone IDs, exact
piece/effect pairs, nine additions, 24 removals, and the seven excluded source-row
dispositions. The original worksheet values remain intact in the appendix.
No gameplay code, worksheet, database, or production state was changed. Build
and gameplay tests are implementation acceptance work, not results of this plan.

## Appendix: complete worksheet choices

The following is a source snapshot, not an executable import. `Source ID` is
column A exactly as supplied. `Candidate ID` records the selected mapping and
any superseded/inactive disposition. Ceothia order is the selected planning
inference; Arcorar is the sole unresolved identity. A dash means blank or unresolved,
not a decision to retain old effects.
Effect tokens omit only the common `SPELL_` prefix for readability and otherwise
preserve the workbook spelling. Each choice is `pieces: effect`.

| Row | Source ID | Worksheet zone name | Candidate ID | Choice 1 | Choice 2 |
| --- | --- | --- | --- | --- | --- |
| 2 | 14 | Kobold Settlement | 14 | 2: SENSE_LIFE | 3: FARSEE |
| 3 | 18 | The Troll Hills | 18 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD |
| 4 | 20 | Valley of Crushk | 20 | 2: ARMOR | 3: BARKSKIN |
| 5 | 21 | Vargan | 21 | 2: LEVITATE | 3: FARSEE |
| 6 | 23 | The Seacaves | 22 | 2: ARMOR | 3: SOULSHIELD |
| 7 | 26 | The Town of Breale | 26 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_GOOD |
| 8 | 37 | Ako Village | 37 | 2: ARMOR | 3: BARKSKIN |
| 9 | 40 | Caves of Mt. Skelenak | 40 | 2: LEVITATE | 4: FARSEE |
| 10 | 50 | Labyrinth of No Return | 50 | 2: ARMOR | 3: SOULSHIELD |
| 11 | 53 | Fort Marigot | 53 | 3: LEVITATE | 4: PANTHERSPEED |
| 12 | 60 | The Lizardman Swamps of Clavikord | 60 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD |
| 13 | 68 | Dragonnia | 68 | 2: DETECT_INVISIBLE | 3: DETECT_ILLUSION |
| 14 | 73 | The Prisons of Carthapia | 73 | 2: AWARENESS | 4: TOWER_OF_IRON_WILL |
| 15 | 91 | The Mountain of the Banished | 91 | 2: FARSEE | 4: FLY |
| 16 | 93 | Tower of High Sorcery | 93 | 3: AWARENESS | 4: TOWER_OF_IRON_WILL |
| 17 | 94 | Sarmiz'Duul | 94 | 2: FARSEE | 3: SENSE_LIFE |
| 18 | 103 | Village of Split Shield | 103 | 2: ARMOR | 3: THORNSKIN |
| 19 | 106 | Pragtog's Domain | 106 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 20 | 112 | Arena of the Elder Brain | 112 | - | - |
| 21 | 113 | The Outcasts Tower | 113 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_GOOD |
| 22 | 130 | The Citadel | 130 | 2: FARSEE | 4: FLY |
| 23 | 140 | The Faerie Realm | 140 | 2: LEVITATE | 3: SENSE_LIFE |
| 24 | 143 | Nakral''s Crypt | 143 | 2: PROTECTION_FROM_UNDEAD | 3: NEGATIVE_ENERGY_BARRIER |
| 25 | 151 | New Cave City | 151 | 2: PROTECTION_FROM_UNDEAD | 3: NEGATIVE_ENERGY_BARRIER |
| 26 | 152 | Faang | 152 | 2: BLESS | 3: VAPOR_STRIKE |
| 27 | 159 | Pit of Dragons | 159 | 1: INFRAVISION | 3: ULTRAVISION |
| 28 | 160 | Pine Hollow | 160 | 2: BLESS | 3: VAPOR_STRIKE |
| 29 | 162 | The Transparent Tower | 162 | 3: HASTE | 4: FLY |
| 30 | 165 | Woodseer | 165 | 3: LEVITATE | 4: FARSEE |
| 31 | 170 | Khildarak Stronghold | 170 | 2: ARMOR | 4: THORNSKIN |
| 32 | 196 | Tiamat | 196 | 2: HASTE | 3: SNEAK |
| 33 | 197 | The Astral Plane | 197 | 2: AWARENESS | 3: TOWER_OF_IRON_WILL |
| 34 | 200 | Krethik Keep | 200 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 35 | 202 | Shairak and Smokeveil Forest | 202 | 2: LEVITATE | 3: SENSE_LIFE |
| 36 | 213 | Mazzolin | 213 | 2: LEVITATE | 4: PANTHERSPEED |
| 37 | 215 | The Forest City of Aravne | 215 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 38 | 220 | Pits of Cerberus | 220 | 2: FARSEE | 3: SENSE_LIFE |
| 39 | 222 | Desolate | 222 | 2: SENSE_LIFE | 3: FARSEE |
| 40 | 224 | Storm Port | 224 | 2: PROTECTION_FROM_GOOD | 3: PROTECTION_FROM_EVIL |
| 41 | 226 | Storm Port Stronhold | 226 | 2: ARMOR | 4: SOULSHIELD |
| 42 | 232 | Plane of Water | 232 | 2: WATER_BREATHING | 5: STONE_SKIN |
| 43 | 238 | Plane of Earth | 238 | 2: BARKSKIN | 4: STONE_SKIN |
| 44 | 244 | Plane of Air | 244 | 3: HASTE | 5: STONE_SKIN |
| 45 | 250 | Plane of Fire, Brass | 1390 | 2: HASTE | 3: DAZZLE |
| 46 | 257 | Bahamut's Palace | 257 | 1: MINOR_GLOBE_OF_INVULNERABILITY | 3: GLOBE_OF_INVULNERABILITY |
| 47 | 260 | Swamp | 260 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD |
| 48 | 262 | Moonshae Island | 262 | 2: BARKSKIN | 3: FARSEE |
| 49 | 266 | Negative Material Plane | 266 | 2: PROTECTION_FROM_LIVING | 3: VAMPIRIC_TOUCH |
| 50 | 270 | The Halfcut Hills | 270 | 2: PROTECTION_FROM_FIRE | 3: FIRESHIELD |
| 51 | 289 | Kingdom of Torg | 289 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 52 | 294 | Harrow - The Gnome Village | 294 | 2: SENSE_LIFE | 3: FARSEE |
| 53 | 306 | Vast Hidden Grove | 306 | 2: ARMOR | 3: BARKSKIN |
| 54 | 308 | Strathor Valley of the Storm Giants | 308 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 55 | 311 | The Mountain Settlement of the Harpies | 311 | 2: LEVITATE | 3: SENSE_LIFE |
| 56 | 313 | Drifting Realm | 313 | 2: FLY | 4: INVISIBLE |
| 57 | 315 | Sea Kingdom | 315 | 2: COLDSHIELD | 5: STONE_SKIN |
| 58 | 328 | Thre Great Shaboath | 328 | 2: DETECT_INVISIBLE | 3: REGENERATION |
| 59 | 333 | Killing Fields | 333 | 2: PROTECTION_FROM_GOOD | 3: PROTECTION_FROM_EVIL |
| 60 | 335 | The Bloody Plains | 335 | 2: PROTECTION_FROM_GOOD | 3: PROTECTION_FROM_EVIL |
| 61 | 342 | Clan Stoutdorf Settlement | 342 | 4: HASTE | 5: FLY |
| 62 | 360 | Arachdrathos Wilderness | 360 | 2: LEVITATE | 3: FARSEE |
| 63 | 368 | Domain of Lost Souls | 368 | 3: GLOBE_OF_DARKNESS | 7: STONE_SKIN |
| 64 | 371 | Du'Maathe Castle | 371 | 4: HASTE | 5: FLY |
| 65 | 377 | Nax | 377 | 2: BLESS | 3: VAPOR_STRIKE |
| 66 | 391 | Ugta | 391 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 67 | 402 | Pharr Valley | 402 | 2: PROTECTION_FROM_UNDEAD | 4: NEGATIVE_ENERGY_BARRIER |
| 68 | 419 | Forest of Mir | 419 | 2: ARMOR | 3: SOULSHIELD |
| 69 | 441 | Lost Temple of Tikizopl | 441 | 2: PANTHERSPEED | 3: ENDURANCE |
| 70 | 448 | The Keep of Evil | 448 | 2: ULTRAVISION | 4: VAMPIRIC_TOUCH |
| 71 | 450 | Charing | 450 | 3: LEVITATE | 4: PANTHERSPEED |
| 72 | 480 | Guildhalls | 480 | - | - |
| 73 | 510 | Hell, Avernus | 510 | 2: FIRESHIELD | 4: STONE_SKIN |
| 74 | 662 | The Ruins of Tharnadia's Old Quarter | 662 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD |
| 75 | 671 | Father Tel's Holy Cloister | 671 | 2: SENSE_LIFE | 3: SOULSHIELD |
| 76 | 676 | Taliccicopiid | 676 | 2: ARMOR | 3: BARKSKIN |
| 77 | 700 | The Town of Moregeeth | 700 | 3: LEVITATE | 4: PANTHERSPEED |
| 78 | 710 | The Fields Between | 710 | 2: BARKSKIN | 6: STONE_SKIN |
| 79 | 756 | The Obsidian Citadel | 756 | 2: FARSEE | 4: FLY |
| 80 | 758 | Rogue Plains | 758 | 2: FARSEE | 3: FLY |
| 81 | 800 | Rift Valley Jungle | 800 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 82 | 824 | The Temple of the Sun | 824 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD |
| 83 | 856 | An Ancient Bridge | 856 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_UNDEAD |
| 84 | 857 | Arcium, The Plagued Kingdom | 857 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 85 | 936 | Vella's Bordello | 936 | 2: LEVITATE | 3: SENSE_LIFE |
| 86 | 955 | Kimordril | 955 | 2: BLESS | 3: VAPOR_STRIKE |
| 87 | 960 | Jotunheim | 960 | 2: BARKSKIN | 5: STONE_SKIN |
| 88 | 964 | Ixarkon | 964 | 3: LEVITATE | 4: SENSE_LIFE |
| 89 | 975 | Shady Grove | 975 | 3: BLESS | 4: VAPOR_STRIKE |
| 90 | 987 | The Undead Outpost | 987 | 2: FARSEE | 3: SENSE_LIFE |
| 91 | 1325 | Tharnadia - City of Humans | 1325 | 3: ARMOR | 4: BARKSKIN |
| 92 | - | Ceothia 1 | 808 (present; selected) | 2: BARKSKIN | 6: STONE_SKIN |
| 93 | - | Ceothia 2 | 811 (past; selected) | 2: BARKSKIN | 5: STONE_SKIN |
| 94 | - | Ceothia 3 | 814 (future; selected) | 2: BARKSKIN | 4: STONE_SKIN |
| 95 | - | The Stone Tomb of Kelek | 879 | 2: PROTECTION_FROM_UNDEAD | 4: NEGATIVE_ENERGY_BARRIER |
| 96 | - | Myrabolus | 825 | 2: BLESS | 3: VAPOR_STRIKE |
| 97 | - | Forgotten Forest | 827 | 2: LEVITATE | 3: PANTHERSPEED |
| 98 | - | Darkfall Forest | 953 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 99 | - | Haunted Woods | 108 | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_LIVING |
| 100 | - | Centaur Villages | 933 | 2: ARMOR | 3: THORNSKIN |
| 101 | - | Darkmore Forest | 57 (superseded by row 268) | 2: ARMOR | 3: BLESS |
| 102 | - | Quintaragon Castle | 24 | 2: PROTECTION_FROM_FIRE | 4: FIRESHIELD |
| 103 | - | Defense of Longhollow | 344 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD |
| 104 | - | Shaledrieth | 536 (superseded by row 265) | 2: PROTECTION_FROM_EVIL | 3: PROTECTION_FROM_GOOD |
| 105 | - | High Moor Forest | 191 | 1: FARSEE | 3: FLY |
| 106 | - | Neverwinter Woods | 990 | 2: PROTECTION_FROM_COLD | 4: COLDSHIELD |
| 107 | - | Neverwinter Valley | 204 | 2: PROTECTION_FROM_FIRE | 3: FIRE_WARD |
| 108 | - | Elemental Groves | 38 | 1: PROTECTION_FROM_ACID | 2: PROTECTION_FROM_LIGHTNING |
| 109 | - | Southern Coastal Highway | 413 | 2: FARSEE | 3: SENSE_LIFE |
| 110 | - | The Ship Yards | 431 | 2: LEVITATE | 5: FLY |
| 111 | - | Bandit Canyons | 985 | 2: SENSE_LIFE | 4: AWARENESS |
| 112 | - | Lylr-Meop | 822 | 2: ARMOR | 3: BARKSKIN |
| 113 | - | The Motte and Bailey of Duke Delwyn | 828 | 2: LEVITATE | 3: FARSEE |
| 114 | - | Kvark's Great Connector | 546 | 3: SOULSHIELD | 4: HASTE |
| 115 | - | Abandoned Elven Homestead | 358 | 2: FARSEE | 4: HASTE |
| 116 | - | Ashrumite Village | 660 | 3: LEVITATE | 4: SENSE_LIFE |
| 117 | - | Bandit Camp | 148 | 2: SENSE_LIFE | 4: AWARENESS |
| 118 | - | Shadowclave | 939 | 2: ARMOR | 3: BLESS |
| 119 | - | The Mountain Village of Tentro | 690 | 2: ARMOR | 3: BARKSKIN |
| 120 | - | Cloud Giant Kingdom | 995 | 3: HASTE | 4: FLY |
| 121 | - | The City of Newhaven | 352 | 2: PROTECTION_FROM_UNDEAD | 4: PROTECTION_FROM_LIVING |
| 122 | - | Twin Towers Forest | 135 | 2: BLESS | 3: VAPOR_STRIKE |
| 123 | - | Golden Hall of the Crown | 404 | 2: WATER_BREATHING | 4: HASTE |
| 124 | - | Arbre's Forest? | 974 | 2: LEVITATE | 3: SENSE_LIFE |
| 125 | - | Home of the Divine | 407 | 3: FIRESHIELD | 4: SOULSHIELD |
| 126 | - | The Savannah of Broken Trusts | 1385 | 2: BARKSKIN | 4: AWARENESS |
| 127 | - | Plane of Fire | 254 | 2: FIRESHIELD | 5: STONE_SKIN |
| 128 | - | The Twin Keeps of Devastated Tharnadia | 784 | 3: PROTECTION_FROM_LIVING | 4: SOULSHIELD |
| 129 | - | Fisherman's Wharf | 889 | 2: ARMOR | 3: THORNSKIN |
| 130 | - | Jenna's Waystation? | 57 (superseded by row 268) | 2: LEVITATE | 3: PANTHERSPEED |
| 131 | - | A Dark and Twisted Wood | 163 | 2: LEVITATE | 3: FARSEE |
| 132 | - | Lord Krimeneha's Mansion | 164 | 2: ARMOR | 3: BARKSKIN |
| 133 | - | Braddistock Mansion | 13 + 1350 (confirmed) | 2: ARMOR | 4: BARKSKIN |
| 134 | - | The Village of New Hope | 890 | 3: COLDSHIELD | 4: SOULSHIELD |
| 135 | - | Wellvolen | 935 | 2: ELEPHANTSTRENGTH | 3: LIONRAGE |
| 136 | - | Nizari | 400 | 3: AWARENESS | 5: FLY |
| 137 | - | The Cimmerian Nomad Encampment | 62 | 1: PROTECTION_FROM_COLD | 2: COLD_WARD |
| 138 | - | City of Torrhan | 666 | 2: LEVITATE | 4: FLY |
| 139 | - | The Deep Ravine of Passage | 947 | 1: PROTECTION_FROM_FIRE | 3: FIRESHIELD |
| 140 | - | Mistywood | 950 | 2: VAPOR_STRIKE | 4: HAWKVISION |
| 141 | - | The Ruins of Turolopolis | 71 | 1: PROTECTION_FROM_FIRE | 2: FIRE_WARD |
| 142 | - | Lair of the Asunwa Jaguar | 353 (inactive) | 2: SENSE_LIFE | 3: FARSEE |
| 143 | - | Tribal Oasis | 780 | 3: HASTE | 4: FLY |
| 144 | - | Tribal Forest | 422 | 2: FARSEE | 4: FLY |
| 145 | - | Mosswood | 234 | 2: LEVITATE | 4: PANTHERSPEED |
| 146 | - | The Basin Wastes | 340 | 2: SENSE_LIFE | 4: DETECT_INVISIBLE |
| 147 | - | Khazan Jungle | 670 (inactive) | 2: ARMOR | 3: THORNSKIN |
| 148 | - | Jindon the Deathwood Forest | 820 | 2: ARMOR | 3: SOULSHIELD |
| 149 | - | The Battlefield | 664 | 2: FIRESHIELD | 3: SOULSHIELD |
| 150 | - | The Shadow Forest | 63 | 2: LEVITATE | 3: FARSEE |
| 151 | - | Village of Refugees | 986 | 2: LEVITATE | 4: PANTHERSPEED |
| 152 | - | The Trakkia Mountains | 570 | 2: COLDSHIELD | 3: SOULSHIELD |
| 153 | - | Enclave of Opal Phoenix? | 708 | 1: PROTECTION_FROM_COLD | 2: COLD_WARD |
| 154 | - | The Chasm of the Misty Vale | 3000 | 2: ELEPHANTSTRENGTH | 3: LIONRAGE |
| 155 | - | The Rice Fields | 772 | 2: COLDSHIELD | 4: SOULSHIELD |
| 156 | - | The Jade Empire | 766 | 3: HASTE | 4: FLY |
| 157 | - | Mitashi? | 1382 | 2: FARSEE | 3: HASTE |
| 158 | - | Malch'Hor Ganl the Goblin City | 236 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 159 | - | The Docks of Quietus Quay | 17 | 2: FARSEE | 3: SENSE_LIFE |
| 160 | - | Troll Caves | 969 | 1: PROTECTION_FROM_FIRE | 2: FIRE_WARD |
| 161 | - | Goblin Camp | 114 | 2: ARMOR | 3: THORNSKIN |
| 162 | - | The Hall of Knighthood | 709 | 2: HASTE | 4: DAZZLE |
| 163 | - | Orrak | 90 | 2: FIRESHIELD | 4: SOULSHIELD |
| 164 | - | Arlik's Inn? | 57 (superseded by row 268) | 2: BLESS | 3: VAPOR_STRIKE |
| 165 | - | Vargan II | 78 | 1: LEVITATE | 3: PANTHERSPEED |
| 166 | - | The Temple of Lizizania | 92 | 1: PROTECTION_FROM_COLD | 2: COLD_WARD |
| 167 | - | Skulldrach | 127 | 2: ARMOR | 3: SENSE_LIFE |
| 168 | - | Village of the Damned | 806 | 3: HASTE | 4: FLY |
| 169 | - | Drustl's Yerdonia Enslaved | 429 | 1: PROTECTION_FROM_FIRE | 3: FIRESHIELD |
| 170 | - | Mountain Tracts of the Untamed | 209 | 2: SENSE_LIFE | 3: FARSEE |
| 171 | - | The Lost Realms of Shadowfall | 180 | 2: COLD_WARD | 3: FIRE_WARD |
| 172 | - | Barrow of the Quiosho | 206 | 2: FIRE_WARD | 3: COLD_WARD |
| 173 | - | Dark Forest | 750 | 2: HAWKVISION | 3: ELEPHANTSTRENGTH |
| 174 | - | Bugentolen | 958 | 2: LEVITATE | 3: SENSE_LIFE |
| 175 | - | Ogre Raiders | 89 | 2: LEVITATE | 3: FARSEE |
| 176 | - | Treasure Caves | 930 | 2: SENSE_LIFE | 3: FARSEE |
| 177 | - | The Lair of the Swamp Troll King | 261 | 2: FIRE_SHIELD | 3: SOULSHIELD |
| 178 | - | The Scorched Valley | 712 | 2: HASTE | 4: SNEAK |
| 179 | - | Lost City of Tikizopl | 437 | 2: PROTECTION_FROM_UNDEAD | 4: NEGATIVE_ENERGY_BARRIER |
| 180 | - | Lava Springs | 997 | 2: LEVITATE | 3: FIRESHIELD |
| 181 | - | Undead Fog? | 678 | 1: COLD_WARD | 3: COLDSHIELD |
| 182 | - | The Maze of Undead Army | 940 | 2: SOULSHIELD | 3: HASTE |
| 183 | - | Varathorn Keep | 994 | 1: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 184 | - | Ruined Temple of Tezcatlipoca | 989 | 2: PROTECTION_FROM_LIVING | 3: NEGATIVE_ENERGY_BARRIER |
| 185 | - | all the Nexuses, dont know their names | 1301-1304 (confirmed) | 4: VAMPIRIC_TOUCH | 5: STONE_SKIN |
| 186 | - | Tunnels of Payang | 903 | 1: ARMOR | 3: THORNSKIN |
| 187 | - | Ny'Neth | 229 | 2: GLOBE_OF_DARKNESS | 4: VAMPIRIC_TOUCH |
| 188 | - | Ny'Neth's Stronghold | 230 | 2: DETECT_INVISIBLE | 3: REGENERATION |
| 189 | - | Ny'Neth's Stronghold Continued | 387 | 1: BARKSKIN | 3: IRONWOOD |
| 190 | - | Tunnels of Cyric the Destroyer | 545 | 1: ARMOR | 3: THORNSKIN |
| 191 | - | Temple of Flames | 183 | 2: FIRESHIELD | 3: SOULSHIELD |
| 192 | - | The Forgotten Mansion | 35 | 2: COLDSHIELD | 3: SOULSHIELD |
| 193 | - | The Old Graveyard | 84 | 1: PROTECTION_FROM_FIRE | 3: FIRESHIELD |
| 194 | - | The Behemoth Herders | 943 | 3: FIRESHIELD | 5: NEGATIVE_ENERGY_BARRIER |
| 195 | - | Vecna's Tomb | 1300 | 1: REGENERATION | 2: ENDURANCE |
| 196 | - | Zalkapfaan, City of the Headless Horde | 27 | 1: ELEPHANTSTRENGTH | 2: LIONRAGE |
| 197 | - | The Sky City of Ultarium | 760 | 2: FARSEE | 3: FLY |
| 198 | - | Githzerai Stronghold | 444 | 2: HASTE | 3: FLY |
| 199 | - | The Desert City of Venan'Trut | 490 | 2: SENSE_LIFE | 3: FARSEE |
| 200 | - | Fort Boyard | 381 | 3: HASTE | 4: FLY |
| 201 | - | Menden on the Deep? | 888 | 2: ARMOR | 3: BARKSKIN |
| 202 | - | Tundra | 137 | 2: PROTECTION_FROM_COLD | 3: COLD_WARD |
| 203 | - | Northern Lakes and Settlements | 752 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 204 | - | The City of Winterhaven | 550 | 3: HASTE | 5: FLY |
| 205 | - | Verspin | 281 | 2: FARSEE | 3: SENSE_LIFE |
| 206 | - | Village of Werrun | 383 | 2: FIRESHIELD | 5: NEGATIVE_ENERGY_BARRIER |
| 207 | - | The Human Outpost | 821 | 1: ARMOR | 4: SOULSHIELD |
| 208 | - | Towering Glacier of Dayedenvale | 904 | 1: ARMOR | 2: PROTECTION_FROM_COLD |
| 209 | - | Ice Tower | 318 | 2: FARSEE | 3: SENSE_LIFE |
| 210 | - | The Church of the Eternal Dusk | 878 | 3: PROTECTION_FROM_LIVING | 4: SOULSHIELD |
| 211 | - | Ant Forest | 109 | 2: ARMOR | 3: BARKSKIN |
| 212 | - | Village of Miaeril | 337 | 2: LEVITATE | 3: SENSE_LIFE |
| 213 | - | The Depths of Duris | 1200 | 2: PANTHERSPEED | 3: ENDURANCE |
| 214 | - | Alatorin - the Forge City | 831 | 3: HASTE | 5: DETECT_INVISIBLE |
| 215 | - | Sevenoaks | 386 | 2: FLY | 4: SNEAK |
| 216 | - | IceCrag Castle | 970 | 2: FARSEE | 4: HASTE |
| 217 | - | Crystalspyre Mountains | 370 | 2: ARMOR | 3: SOULSHIELD |
| 218 | - | Bloodstone Keep | 740 | 2: SENSE_LIFE | 3: FARSEE |
| 219 | - | The Caverns of the Worms | 69 | 2: LEVITATE | 3: FARSEE |
| 220 | - | The 222nd Layer of the Abyss | 875 | 2: HASTE | 3: BLUR |
| 221 | - | Morg's? | 886 | 1: ARMOR | 2: BLESS |
| 222 | - | Gagga'Jobo Cave System | 190 | 2: BLESS | 3: VAPOR_STRIKE |
| 223 | - | Myconids? | 23 | 2: LEVITATE | 3: SENSE_LIFE |
| 224 | - | Phantasmagoric Caverns | 531 | 2: FARSEE | 3: SENSE_LIFE |
| 225 | - | The Clawed Caverns | 807 | 2: SENSE_LIFE | 3: FARSEE |
| 226 | - | Orog hometown? | 458 | 2: ARMOR | 4: THORNSKIN |
| 227 | - | The Underworld | 44 + 300 (confirmed) | 3: HASTE | 5: NEGATIVE_ENERGY_BARRIER |
| 228 | - | Bogentok | 187 | 2: FARSEE | 4: FLY |
| 229 | - | Lair of the Purple Worm | 425 | 4: HASTE | 5: FLY |
| 230 | - | The Bugger Caves | 64 | 2: ARMOR | 3: THORNSKIN |
| 231 | - | Lair of the Gibberling King | 87 | 3: AWARENESS | 4: SOULSHIELD |
| 232 | - | Arachdrathos Guilds | 367 | 2: LEVITATE | 3: FLY |
| 233 | - | llzazan Ghetto of Arachdrathos | 362 | 2: LEVITATE | 4: THORNSKIN |
| 234 | - | Arachdrathos - Drow City | 364 | 2: LEVITATE | 4: THORNSKIN |
| 235 | - | Valinhaven | 908 | 2: BLESS | 3: VAPOR_STRIKE |
| 236 | - | Arcorar - The Great King Forest | - | 2: BARKSKIN | 4: ENDURANCE |
| 237 | - | Court of the Muse | 67 | 2: BARKSKIN | 3: PANTHERSPEED |
| 238 | - | The Swamp Laboratory of Khul'Lor | 823 | 3: HASTE | 4: FLY |
| 239 | - | Myrloch Vale | 264 | 3: FLY | 4: HASTE |
| 240 | - | The Ruins of Undermountain | 920 | 2: ARMOR | 4: SOULSHIELD |
| 241 | - | The Githyanki Fortress | 1320 | 2: AWARENESS | 3: TOWER_OF_IRON_WILL |
| 242 | - | Desolate Under Fire | 773 | 1: INFRAVISION | 2: ULTRAVISION |
| 243 | - | Prison of Fort Boyard | 430 | 3: FLY | 4: HASTE |
| 244 | - | The Ancient Halls of Ironstar | 1389 | 3: PROTECTION_FROM_LIVING | 4: NEGATIVE_ENERGY_BARRIER |
| 245 | - | The Para-Elemental Plane of Smoke | 1398 | 2: FIRESHIELD | 5: STONE_SKIN |
| 246 | - | Shadamehr Keep | 412 | 2: PROTECTION_FROM_LIVING | 5: STONE_SKIN |
| 247 | - | The Temple to Skrentherlog | 805 | 1: SLOW_POISON | 3: ENDURANCE |
| 248 | - | Dreggan Woods | 410 | 3: NEGATIVE_ENERGY_BARRIER | 4: INVISIBLE |
| 249 | - | Valley of the Snow Ogres | 877 | 3: DAZZLE | 4: GLOBE_OF_INVULNERABILITY |
| 250 | - | The Tempest Court | 1316 | 2: LIGHTNING_SHIELD | 3: DAZZLE |
| 251 | - | The Realm of Barovia | 910 | 3: DETECT_INVISIBLE | 4: NEGATIVE_ENERGY_BARRIER |
| 252 | - | The Royal Mausoleum of Castle IceCrag | 1424 | 2: NEGATIVE_ENERGY_BARRIER | 3: DETECT_INVISIBLE |
| 253 | - | The Ethereal Plane | 124 | 4: DETECT_INVISIBLE | 5: STONE_SKIN |
| 254 | - | The Fortress of Dreams | 326 | 2: FLY | 3: DETECT_ILLUSION |
| 255 | - | The Charcoal Palace | 883 | 2: FIRESHIELD | 3: DAZZLE |
| 256 | - | Apocalypse Castle | 345 | 2: NEGATIVE_ENERGY_BARRIER | 3: VAMPIRIC_TOUCH |
| 257 | - | The Realm of Barovia Continued | 588 | 2: NEGATIVE_ENERGY_BARRIER | 3: GLOBE_OF_INVULNERABILITY |
| 258 | - | The Hall of the Ancients | 777 | 3: FLY | 4: DETECT_INVISIBLE |
| 259 | - | The Bronze Citadel | 324 | 2: PROTECTION_FROM_LIVING | 3: VAMPIRIC_TOUCH |
| 260 | - | Celestial Plane | 455 | 3: BLUR | 4: BIOFEEDBACK |
| 261 | - | Castle Ravenloft | 583 | 3: BIOFEEDBACK | 4: INERTIAL_BARRIER |
| 262 | - | Bastine Castle | 76 | 2: BLESS | 3: FARSEE |
| 263 | - | The Temple of Laduguer | 81 | 2: PROTECTION_FROM_COLD | 3: COLDSHIELD |
| 264 | - | The Halfling Silver Mine | 49 | 2: BLESS | 3: VAPOR_STRIKE |
| 265 | - | The Great Realm of Duris | 536 | 2: LEVITATE | 8: STONE_SKIN |
| 266 | - | The Mountain of Peril Peaks | 575 | 2: HASTE | 3: DETECT_INVISIBLE |
| 267 | - | The Valoisian Castle | 384 | 3: HASTE | 4: FLY |
| 268 | - | Mini Zones | 57 | 1: HAWKVISION | 2: ELEPHANTSTRENGTH |
| 269 | - | Ard'gral, plane of dreams | 304 | 4: DETECT_ILLUSION | 5: STONE_SKIN |
| 270 | - | Astral Plane, Tiamat | 199 | 2: AWARENESS | 3: TOWER_OF_IRON_WILL |
| 271 | - | Black Tunnels | 107 | 1: ARMOR | 3: THORNSKIN |
| 272 | - | The Mountain Valley of Dawndale | 775 | 3: FLY | 4: DETECT_INVISIBLE |
| 273 | - | Dirk'nspire Stronghold | 968 | 2: LEVITATE | 3: FARSEE |
| 274 | - | Githyanki Hometown? | 194 | 2: ARMOR | 4: BARKSKIN |
| 275 | - | Ixxillikor | 42 | 2: FARSEE | 3: SENSE_LIFE |
| 276 | - | Lava Tubes | 120 | 2: LEVITATE | 3: SENSE_LIFE |
| 277 | - | Llyrath Forest | 949 | 2: ARMOR | 3: BARKSKIN |
| 278 | - | The Caverns of Armageddon | 133 | 3: SOULSHIELD | 4: FLY |
| 279 | - | The Minor Plane of Planitude | 34 | 2: LEVITATE | 3: THORNSKIN |
| 280 | - | The Mushroom Forest | 101 | 2: BLESS | 3: VAPOR_STRIKE |
| 281 | - | The Shaughin Settlement | 65 | 2: PANTHERSPEED | 4: FLY |
| 282 | - | The Temple of Blipdoolpoolp | 882 | 2: ARMOR | 4: SOULSHIELD |
| 283 | - | The Underground Lava Caves | 355 | 2: FIRESHIELD | 5: SOULSHIELD |
| 284 | - | The Underdark | 240 | 3: HASTE | 5: NEGATIVE_ENERGY_BARRIER |
| 285 | - | Traoul's Lair | 70 | 2: THORNSKIN | 3: FARSEE |
| 286 | - | Truktakyagyo | 16 | 2: ARMOR | 3: THORNSKIN |
| 287 | - | Turolopolis Zoo | 530 | 1: PROTECTION_FROM_FIRE | 3: FIRE_SHIELD |
| 288 | - | whatever the zone name is for pirate random eq | 600 (ship origin) | 3: PANTHERSPEED | 4: FLY |
