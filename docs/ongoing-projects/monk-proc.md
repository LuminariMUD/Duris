# Monk glove proc candidates

Status: preserved research baseline for monk balance, updated 2026-11-08.
The [implementation plan and pilot](monk-glove-proc-plan.md) record current work;
the catalog and ordering below retain the original pre-pilot values.

Valuation baseline: `77dcd194274eb7fe3737530a308395ee6f804a70`. The original catalog sweep used `5958a80f7`; all 105 listed object records were unchanged at that research checkpoint. The
subsequent pilot changes only 21575, 500110, 76052 and 5817; its current effects
and recalculated values are recorded in the plan.

## Scope and ordering

This document preserves every entry from the previous monk-glove candidate list: **105 distinct vnums**, comprising **16 focus candidates**, **72 broader stat/weight alternatives**, **6 existing-proc/artifact benchmarks**, and **11 conditional or low-priority reserves**. The initial sweep inspected 19,334 AREA-selected object prototypes and all 314 hand-slot prototypes; 265 passed the single-class monk class-mask check. A class-mask pass is not proof of race eligibility, acquisition, or an ideal monk item.

The catalog and detailed entries are in **ascending native ivalue**, with **ascending vnum** as the tie-breaker. This is an equipment-value ordering, not an asserted minimum player level or a strict upgrade path. All entries carry the hand wear flag; gloves do not occupy the weapon/held-item slots just because they are worn on hands.

## How ivalue was calculated

- Executed the current C++ [itemvalue()](../../src/economy/tradeskill.c#L1793) and [get_ival_from_proc()](../../src/economy/tradeskill.c#L2844) in an isolated, temporary native harness, using each unchanged template's values, modifiers, permanent affects, wear flags and effective native proc assignment.
- Used the loader's armor-to-worn normalization when an armor template has zero base armor. No item was instantiated in the game, persisted, enhanced, or modified.
- Native callback symbols were used only as distinct identities for the real proc-value comparisons; gameplay callback bodies were not executed. The packed-weapon-spell and racial-stat-replacement branches were asserted absent for these 105 templates. Unexpected use of those branches or corruption diagnostics aborts the harness.
- The harness ran with undefined-behavior and float-cast-overflow sanitizers. Values are the integer results returned by the runtime function, including its multipliers and truncation.
- Ivalue is class-agnostic: it does not price the monk-specific cost of item weight, class/race usefulness, acquisition difficulty, or whether a proc explicitly excludes monks. It also does not use the item's monetary cost as its ivalue. The smooth-dragon-scale gloves illustrate this: their fumblegaunts proc adds a valuation credit even though it skips monks.
- These are native prototype values, not measurements of a live production item with saved enhancements, studio/proclib overrides, or other runtime mutations.

## Monk rules that affect the selection

- **Individual equip limit:** a player monk normally cannot wear a glove heavier than `floor(current STR / 10)`; the divisor comes from `monk.weight.str.modifier.denominator=10`. The back-slot exception does not exempt gloves. [Wear check](../../src/cmd/actobj.c#L6025).
- **Armor class:** let `W` be full equipped weight, `L` level and `M` martial-arts rating. Monk AC bonus is `clamp(-400, -4*L - M + 3*max(0, W - floor((60-L)/6)), 50)`. Lower AC is better. [MonkAcBonus](../../src/classes/new_skills.c#L514).
- **Bare-hand damage:** full equipped weight above `floor(L*STR/100)` reduces rolled monk damage, with a result floor of 1. Damroll is applied later. [MonkDamage](../../src/classes/new_skills.c#L656).
- **Base attacks:** use `E = sum(trunc(item_weight / 2))`, rounding each equipped item individually. One attack is lost for each full 10 pounds above `floor(STR/2)`, retaining at least one base attack. Zero- and one-pound gloves contribute zero to this tally; one-pound gloves still add full weight to AC/damage. Negative glove weights reduce both relevant budgets. Loose inventory is excluded. [calculate_attacks](../../src/combat/fight.c#L10403).
- **Hands free:** weapons, shields, held items and worn lights interfere with normal monk attack handling. A normal glove slot is separate. [MonkNumberOfAttacks](../../src/classes/new_skills.c#L707).
- **Magic gloves:** below level 51, unarmed hits need MAGIC gloves to bypass innate weapon immunity. Several strong candidates, including sunstone knuckles, fists of steel and mithril-bladed gloves, lack MAGIC in the template. [Immunity check](../../src/combat/fight.c#L8645).
- **Normal starter kit:** the monk class kit gives 1147–1151, with no gloves; the racial/basic kit scan likewise found no hand item. [Kit plan](../../src/account/newbie_kit_plan.c#L299).
- **Chaos kit:** standard and enhanceable monk main-hands are both 5817; the Illusionist profiles also use 5817. The optional second glove slot uses 83505 where anatomy permits it. [Standard monk](../../src/account/chaos_eq_data.h#L138), [Enhanceable monk](../../src/account/chaos_eq_data.h#L393), [Optional slots](../../src/account/chaos_eq_data.h#L588).
- **Proc dispatch:** an ordinary unarmed hit does not automatically call a glove's packed weapon-spell or native melee-hit proc. The weapon_proc call in the hit path requires an actual weapon. Periodic and defensive glove procs are existing alternatives; an offensive glove-on-hit design needs an intentional dispatch route. [Weapon proc call](../../src/combat/fight.c#L8714).

## Balance findings to retain

- **5813 → 5817 adds 14 pounds:** ghostly gloves weigh −10; the blood-crystal result weighs +4. The recipe costs the ghostly gloves, five huge blood crystals [500025], and 400 platinum. The extra full worn weight can outweigh the gain of +4 damroll. [Recipe](../../areas/qst/minizones.qst#L169).
- **500110 is explicitly monk-themed but weak:** identify reveals “gloves of the monk,” yet the item gives only +1 damroll and AR 4 at one pound and drops from Mu, an NPC at level 60. Its ivalue is 10.
- **76052 has the narrowest non-artifact class fit:** only Monk, Berserker and Dreadlord are allowed. It has ivalue 91 and is not MAGIC in the prototype.
- **1210 is the only exact Monk-only hand-item class allow-mask in the sweep:** it is an existing artifact/proc benchmark, not a missing-proc starter. Its ivalue is 1519, including a raw native proc credit of 205 before multipliers.
- **139152 is blocked for ordinary wearers:** ITEM_ALLOWED_RACES is set with a zero race mask. The monk class mask permits it, but that empty race allow-list prevents normal monk use. The Illithid/Mindflayer universal usability exception is separate. [Usability owner](../../src/world/handler.c#L5137).
- **83468 is transient:** the attractive −10 weight must be considered alongside ITEM_TRANSIENT, rather than treating it as unconditional permanent progression gear.
- **Shared gear needs deliberate scope:** nearly every entry allows other classes. A proc intended to balance monks should enforce that intended class scope rather than silently buff every wearer.
- **First design pass:** 500110, 21575, 74278, 44424, 22422, 76052, 70937, 5817 and 83505. Use 1210 and the other existing-proc entries as benchmarks. This is a starting priority, not approval of a proc effect or budget.

## Column definitions

- **AR** is stored armor `value[0]`, not a final character AC result; material, condition, armor rules and monk encumbrance still matter. A separate signed AC modifier is shown as AC.
- **HITROLL / DAMROLL** are accuracy/damage bonuses; HP is hit points; MV is movement. `_MAX` changes a stat ceiling. Negative saves improve saving throws. Negative COMBAT_PULSE is a combat-speed modifier.
- **Weight** is stored full item weight in pounds. Negative values are actual template values. The default per-item STR gate is zero for nonpositive weight, otherwise ten times the listed weight.
- Stored wear flags below are the authored masks; the loader also adds HOLD for TAKE items (and TAKE for HOLD items). Wearing a glove normally still uses a glove slot.
- **Magic** means the prototype's ITEM2_MAGIC flag, not a claim based on the name, a glow flag or magical-looking descriptions.
- **NPC L** describes the source NPC, not a player equip requirement or a solo recommendation. Shop stock is separate from defeating the keeper.
- **Raw proc credit** is the get_ival_from_proc contribution added before the ivalue multipliers; it is not a flat final-ivalue increment.
- **No source found** means no direct AREA-selected reset, shop stock or quest reward was located. Scripts, special grants or other acquisition routes may still exist; source presence does not itself prove current accessibility.

## All entries, ascending ivalue

| Ivalue | Vnum | Name, including identified alias | Weight (lb) | Stats and permanent affects | Review role |
| ---: | ---: | --- | ---: | --- | --- |
| 1 | [17040](#vnum-17040) | a pair of blue fungus gloves | 0 | armor 1 | Defense/entry |
| 1 | [28950](#vnum-28950) | Kulnon's brass knuckles | 5 | armor 1 | Conditional |
| 1 | [95523](#vnum-95523) | some combat knuckles | 4 | armor 2; +2 DAMROLL; -7 DEX | Conditional |
| 1 | [300017](#vnum-300017) | a pair of bone-razored talons | 1 | armor 0 | Conditional |
| 3 | [16625](#vnum-16625) | some ugly leather gloves | 0 | armor 0; -2 AC | Defense/entry |
| 6 | [55264](#vnum-55264) | a pair of gloves with razor-sharp talons | 1 | armor 0; +1 HITROLL; +1 DAMROLL | Light offense |
| 6 | [94371](#vnum-94371) | some rusty iron shackles | 0 | armor 7; -10 MV; +2 DAMROLL | Light offense |
| 7 | [3428](#vnum-3428) | a pair of lead-filled gloves | 5 | armor 6; +2 DAMROLL; -4 DEX | Conditional |
| 7 | [96432](#vnum-96432) | a pair of tough leather gloves | 0 | armor 0; -5 AC | Defense/entry |
| 9 | [89062](#vnum-89062) | a pair of red cotton gloves | 0 | armor 1; +4 HP | Defense/entry |
| 10 | [66417](#vnum-66417) | some abominable cloth | 5 | armor 0; DETECT_MAGIC | Conditional |
| 10 | [89057](#vnum-89057) | a pair of black cotton gloves | 0 | armor 1; +4 DEX | Defense/entry |
| 10 | [89067](#vnum-89067) | a pair of green cotton gloves | 0 | armor 1; +4 AGI | Defense/entry |
| 10 | [89072](#vnum-89072) | a pair of blue cotton gloves | 0 | armor 1; +4 CON | Defense/entry |
| 10 | [500110](#vnum-500110) | a pair of simple leather gloves → a pair of gloves of the monk | 1 | armor 4; +1 DAMROLL | Focus: identity/punching |
| 13 | [16598](#vnum-16598) | some thin leather gloves | 0 | armor 0; +4 DEX; -3 AC | Defense/entry |
| 13 | [17085](#vnum-17085) | a pair of spiked adamantite gauntlets | 8 | armor 6; +1 DAMROLL | Conditional |
| 13 | [21575](#vnum-21575) | a pair of iron knuckles | 1 | armor 6; +1 DAMROLL | Focus: identity/punching |
| 15 | [90718](#vnum-90718) | some gloves sewn with human bones | 4 | armor 5; +2 DAMROLL | Conditional |
| 15 | [97033](#vnum-97033) | a pair of blue and white gauntlets | 3 | armor 7; +1 HITROLL | Conditional |
| 16 | [16653](#vnum-16653) | some sheer silk gloves | 0 | armor 0; -5 AC; +4 AGI | Defense/entry |
| 17 | [2682](#vnum-2682) | a pair of iron gloves | 0 | armor 8; +1 HITROLL | Defense/entry |
| 17 | [88205](#vnum-88205) | a pair of shark-skin gloves | 0 | armor 8; +1 DAMROLL | Light offense |
| 18 | [93608](#vnum-93608) | a pair of studded black leather gloves | 0 | armor 5; +1 DAMROLL; +1 HITROLL | Light offense |
| 20 | [4014](#vnum-4014) | a pair of warrior's gloves | 1 | armor 4; +2 HITROLL; +1 DAMROLL | Focus: class allow-list |
| 22 | [15257](#vnum-15257) | a pair of smooth batskin gloves | 1 | armor 5; +2 HITROLL; +1 DAMROLL | Light offense |
| 22 | [18723](#vnum-18723) | a pair of shiny black gloves | 1 | armor 5; +1 HITROLL; +2 DAMROLL | Light offense |
| 25 | [10102](#vnum-10102) | a pair of smooth batskin gloves | 1 | armor 6; +2 HITROLL; +1 DAMROLL | Light offense |
| 25 | [99416](#vnum-99416) | a pair of spiked leather gloves | 0 | armor 6; +1 HITROLL; +2 DAMROLL | Light offense |
| 26 | [55401](#vnum-55401) | a pair of fingerless leather gloves | 0 | armor 0; +5 DEX; +2 HITROLL | Defense/entry |
| 27 | [22422](#vnum-22422) | the gloves of tearing | 0 | armor 5; +2 HITROLL; +4 DEX | Focus: identity/punching |
| 29 | [15005](#vnum-15005) | a pair of bone razored talons | 1 | armor 8; +2 DAMROLL; +1 HITROLL | Light offense |
| 30 | [74278](#vnum-74278) | some chain linked fighting mitts | 1 | armor 4; +1 DAMROLL; +5 STR | Focus: identity/punching |
| 34 | [8109](#vnum-8109) | an ashen volcanic-forged articulated finger gauntlets | 0 | armor 10; +2 HITROLL; +1 DAMROLL | Light offense |
| 37 | [16626](#vnum-16626) | some halfling-sized gauntlets | 1 | armor 8; +5 STR; +1 HITROLL | Focus: class allow-list |
| 37 | [82512](#vnum-82512) | the claws of the ruiner | 1 | armor 9; +2 HITROLL; +2 DAMROLL | Light offense |
| 43 | [22258](#vnum-22258) | some spiked steel-mesh gloves | 0 | armor 9; +2 DAMROLL; +5 AGI | Light offense |
| 43 | [77359](#vnum-77359) | some spiked steel-mesh gloves | 0 | armor 9; +2 DAMROLL; +5 AGI | Light offense |
| 47 | [7641](#vnum-7641) | the gloves of the Knights of the Rose | 1 | armor 5; +3 DAMROLL | Light offense |
| 54 | [44424](#vnum-44424) | some spiked knuckles → the spiked knuckles of punching | 0 | armor 6; +10 HP; +2 DAMROLL | Focus: identity/punching |
| 54 | [83468](#vnum-83468) | some tricksters gloves | -10 | armor 5; +3 DEX_MAX; -3 SAVING_SPELL | Defense/entry |
| 54 | [97913](#vnum-97913) | some fur-cuffed cured leather gloves | 0 | armor 8; +17 MV; +6 AGI | Defense/entry |
| 57 | [40402](#vnum-40402) | a pair of whitened steel gauntlets | 0 | armor 10; +2 HITROLL; +6 DEX | Light offense |
| 58 | [30844](#vnum-30844) | a pair of heavy spiked combat gloves | 0 | armor 5; +3 DAMROLL; +4 STR | Light offense |
| 60 | [28597](#vnum-28597) | a set of neberihide gloves | 1 | armor -8; +3 DEX; +3 DAMROLL | Light offense |
| 64 | [5813](#vnum-5813) | a pair of ghostly gloves | -10 | armor 8; +14 HP; +4 POW | Defense/entry |
| 65 | [44414](#vnum-44414) | a pair of adamantite-plated gloves | 0 | armor 13; +3 DAMROLL; -1 SAVING_SPELL | Light offense |
| 66 | [31823](#vnum-31823) | a pair of hydra's claws | 1 | armor 8; +2 HITROLL; +2 DAMROLL; PROT_FIRE | Light offense |
| 67 | [96062](#vnum-96062) | the claws of the destroyer | 2 | armor 5; +3 DAMROLL; +5 DEX | Heavier/sustain |
| 69 | [18002](#vnum-18002) | the claws of Vermithrax | 3 | armor 8; +3 DAMROLL; +1 HITROLL | Heavier/sustain |
| 71 | [5054](#vnum-5054) | some diamondine gauntlets | 2 | armor 12; +3 DAMROLL; -2 SAVING_PARA | Heavier/sustain |
| 71 | [6617](#vnum-6617) | some fingerless hunting gloves | 1 | armor 5; +15 HP; +5 CON | Defense/entry |
| 71 | [49158](#vnum-49158) | a pair of gnomish mesh gloves | 2 | armor 12; +5 DEX; +7 STR | Heavier/sustain |
| 71 | [96078](#vnum-96078) | the talons of the raven | 1 | armor 5; +15 HP; +5 STR | Defense/entry |
| 71 | [142295](#vnum-142295) | a pair of swashbucklers gauntlets | 0 | armor 0; +3 DAMROLL; +3 STR_MAX | Light offense |
| 75 | [8410](#vnum-8410) | the claws of a werewolf | 1 | armor 8; +3 HITROLL; -3 SAVING_BREATH | Light offense |
| 75 | [16245](#vnum-16245) | obsidian gauntlets | 1 | armor 8; +3 DAMROLL; -3 SAVING_PARA | Focus: class allow-list |
| 75 | [42270](#vnum-42270) | a set of sharp blue claws | 1 | armor 4; +8 AGI; +2 HITROLL | Light offense |
| 75 | [42912](#vnum-42912) | some spiked raxian pit gauntlets | 0 | armor 8; -3 SAVING_PARA; +3 DAMROLL | Light offense |
| 81 | [99537](#vnum-99537) | a fine pair of gloves studded with amethysts | 0 | armor 8; +16 HP; -3 SAVING_FEAR | Defense/entry |
| 82 | [38121](#vnum-38121) | some dragonscale gloves | 2 | armor 12; +5 CON; +15 HP | Heavier/sustain |
| 84 | [83557](#vnum-83557) | some fingerless orog-hide gloves | 2 | armor 5; +17 HP; +2 DAMROLL | Heavier/sustain |
| 89 | [66438](#vnum-66438) | some white fur skin gloves | 5 | armor 8; +3 DAMROLL; +3 DEX_MAX | Conditional |
| 91 | [30006](#vnum-30006) | a pair of gloves studded with durithalite | 0 | armor 9; +3 HITROLL; +10 HP | Light offense |
| 91 | [67259](#vnum-67259) | some fingerless gloves of su-monster skin | 0 | armor 0; +25 HP; -2 SAVING_PARA | Benchmark |
| 91 | [76052](#vnum-76052) | a pair of sunstone knuckles | 0 | armor 8; +3 DEX_MAX; +3 HITROLL | Focus: identity/punching |
| 93 | [42168](#vnum-42168) | a wet pair of black gloves | 1 | armor 3; +20 HP; +2 HITROLL | Light offense |
| 100 | [83505](#vnum-83505) | some black leather gloves with mithril blades | 0 | armor 5; +4 DEX_MAX; +3 DAMROLL | Focus: identity/punching |
| 106 | [1452](#vnum-1452) | a glowing, clawed talon of a tako demon | 3 | armor 5; +3 HITROLL; +3 DAMROLL | Heavier/sustain |
| 107 | [75827](#vnum-75827) | some spiked gauntlets of the Sixth Legion | 0 | armor 8; +4 HITROLL; +2 DAMROLL | Light offense |
| 111 | [70937](#vnum-70937) | some fists of steel → the claws of the Soulrender | 1 | armor 7; +3 HITROLL; +3 DAMROLL | Focus: identity/punching |
| 118 | [97057](#vnum-97057) | the skinned hands of a troll | 1 | armor 9; +15 HP_REGEN; +2 DAMROLL | Light offense |
| 119 | [78482](#vnum-78482) | a pair of mailed dragoon gloves | 2 | armor 8; +4 DAMROLL; +3 DEX_MAX | Heavier/sustain |
| 123 | [70943](#vnum-70943) | the gauntlets of pounding → titanium gauntlets, made for pounding | 2 | armor 12; +3 HITROLL; +3 DAMROLL | Focus: class allow-list |
| 127 | [36](#vnum-36) | gloves of smooth dragon scale | 1 | armor 10; +3 HITROLL; -5 SAVING_BREATH | Conditional |
| 127 | [83588](#vnum-83588) | a pair of black leather gloves glowing with faerie fire | 0 | armor 10; +5 AGI_MAX; -5 SAVING_SPELL | Defense/entry |
| 139 | [34565](#vnum-34565) | a pair of darkmail gauntlets | 1 | armor 14; +5 STR_MAX; +3 DAMROLL | Light offense |
| 144 | [77534](#vnum-77534) | some thick cargo gloves | 0 | armor 20; +3 HITROLL; +3 DAMROLL | Light offense |
| 145 | [23055](#vnum-23055) | the gauntlets of immortality | 1 | armor 0; +4 DAMROLL; +20 HP | Light offense |
| 150 | [138931](#vnum-138931) | a pair of skeletal gauntlets | 1 | armor 10; +3 DAMROLL; +3 HITROLL; HAWKVISION | Light offense |
| 151 | [132006](#vnum-132006) | a pair of silverish githyanki gauntlets | 0 | armor 10; +4 HITROLL; +3 DAMROLL | Light offense |
| 159 | [88919](#vnum-88919) | some snake-rattle gloves | 1 | armor 15; +15 HP; +10 MV; AWARE | Defense/entry |
| 159 | [135423](#vnum-135423) | some mauve-skinned fingerless gloves of an illithidlich | 1 | armor 20; +5 CON_MAX; +5 POW_MAX | Defense/entry |
| 166 | [55404](#vnum-55404) | a pair of fingerless silk gloves | 0 | armor 0; +20 HP; +5 AGI_MAX; PROTECT_EVIL | Defense/entry |
| 166 | [55405](#vnum-55405) | a pair of fingerless silk gloves | 0 | armor 0; +20 HP; +5 DEX_MAX; PROTECT_EVIL | Defense/entry |
| 174 | [77529](#vnum-77529) | some webspinner claws | 0 | armor 12; +4 HITROLL; -3 SAVING_PARA; SLOW_POISON; PROT_ACID | Light offense |
| 175 | [139038](#vnum-139038) | gloves of sapphire-encrusted brass | 0 | armor 9; +4 DAMROLL; +10 HP; SENSE_LIFE | Light offense |
| 179 | [32623](#vnum-32623) | some gloves of rage | 0 | armor 10; +4 HITROLL; HASTE | Focus: class allow-list |
| 187 | [28960](#vnum-28960) | the gauntlets of the war giant Torg | 2 | armor 12; +2 HITROLL; +2 DAMROLL; DETECT_INVISIBLE | Focus: class allow-list |
| 191 | [120037](#vnum-120037) | some spectral gauntlets of the battleragers | 0 | armor 4; +3 STR_MAX; +3 DAMROLL; HASTE | Focus: class allow-list |
| 194 | [139152](#vnum-139152) | some gauntlets of cooled magma | 3 | armor 12; +9 STR; +4 DAMROLL; PROT_FIRE | Conditional |
| 204 | [98945](#vnum-98945) | some spiked zanthium gloves | 0 | armor 12; +4 HITROLL; +3 DAMROLL; PROT_LIGHTNING | Light offense |
| 212 | [5523](#vnum-5523) | magical gloves of slayer's accuracy | 0 | armor 10; +10 DEX; +4 HITROLL; HAWKVISION | Light offense |
| 216 | [5817](#vnum-5817) | some razor-knuckled blood crystal gloves | 4 | armor 20; +15 HP; +4 DAMROLL; PROTECT_EVIL; DETECT_EVIL | Focus: identity/punching |
| 237 | [44451](#vnum-44451) | the gloves of shadows | 0 | armor 15; +5 HITROLL; +40 MV | Light offense |
| 244 | [23806](#vnum-23806) | a pair of gauntlets formed of dust | 0 | armor 10; +6 STR_MAX; +3 DAMROLL | Benchmark |
| 265 | [96074](#vnum-96074) | the holy gauntlets of the planetar | 1 | armor 15; +5 HITROLL; -4 SAVING_SPELL; AWARE | Defense/entry |
| 325 | [131636](#vnum-131636) | the legendary silverish gauntlets of Gith's Blessing | 0 | armor 15; +4 HITROLL; +4 DAMROLL; SPIRIT_WARD, TOWER_IRON_WILL | Defense/entry |
| 326 | [23808](#vnum-23808) | a pair of stone gauntlets | 0 | armor 10; +6 STR; STONE_SKIN; PROT_ACID | Benchmark |
| 360 | [83628](#vnum-83628) | the claws of the Legendary Tarrasque | 4 | armor 30; +4 HITROLL; +4 DAMROLL; HASTE | Heavier/sustain |
| 389 | [88320](#vnum-88320) | a pair of vampiric dragonscale gauntlets | 4 | armor 6; +15 HP_REGEN; +3 DEX_MAX; PROT_FIRE; PROT_COLD, PROT_LIGHTNING, PROT_GAS, PROT_ACID, VAMPIRIC_TOUCH; SPIRIT_WARD | Heavier/sustain |
| 484 | [131649](#vnum-131649) | Tempest, the swirling gauntlets of storms | 0 | armor 25; -4 SAVING_SPELL; +5 CON_MAX; DETECT_INVISIBLE, HASTE, FLY; PROT_COLD, PROT_LIGHTNING | Defense/entry |
| 563 | [77734](#vnum-77734) | the sacred stone claws of Aan | 5 | armor 6; -50 AC; +50 HP; STONE_SKIN | Benchmark |
| 615 | [55280](#vnum-55280) | the gauntlets of a Living Legend | 4 | armor 0; +30 HP; -30 AC; HASTE, SNEAK | Benchmark |
| 1519 | [1210](#vnum-1210) | tendrils of shadowy mist | -10 | armor 15; -1 COMBAT_PULSE; +5 DAMROLL; HASTE; GLOBE, VAMPIRIC_TOUCH | Benchmark |

## Detailed entries, in the same ivalue order

<a id="vnum-17040"></a>

### 17040 — a pair of blue fungus gloves — ivalue 1

- **Review role:** Defense/entry.
- **Fit / caution:** Zero-weight shop filler with no bonuses; entry option only.
- **Stats:** armor 1.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 40 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of blue fungus gloves”; keywords `glove gloves blue`.
- **Prototype source:** [areas/obj/khildarak.obj](../../areas/obj/khildarak.obj#L522).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: a clansdwarf [17062], NPC L35; [shop stock](../../areas/shp/khildarak.shp#L245).
- **Acquisition:** Drop/carried equipment: a clansdwarf [17062], NPC L35; [reset](../../areas/zon/khildarak.zon#L2405).
- **Authored description (glove gloves blue):** These gloves offer only basic protection. They are woven from a deep blue fungus fiber.

<a id="vnum-28950"></a>

### 28950 — Kulnon's brass knuckles — ivalue 1

- **Review role:** Conditional.
- **Fit / caution:** Brass-knuckle theme, but 5 pounds and no stat modifiers. QUESTITEM; holder is Kulnon L60. Low priority without broader rebalance.
- **Stats:** armor 1.
- **Weight:** 5 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 50.
- **Template:** ARMOR; material BRASS; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_GLOW. **Extra2 flags:** ITEM2_QUESTITEM.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “Kulnon's brass knuckles”; keywords `kulnon brass knuckles`.
- **Prototype source:** [areas/obj/torg.obj](../../areas/obj/torg.obj#L779).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Kulnon, the legend [28955], NPC L60; [reset](../../areas/zon/torg.zon#L711).
- **Authored description (kulnon brass knuckles):** The are worn upon the hands of Kulnon the legendary warrior.

<a id="vnum-95523"></a>

### 95523 — some combat knuckles — ivalue 1

- **Review role:** Conditional.
- **Fit / caution:** Knuckle theme and explicit melee allow-list, but 4 pounds and -7 DEX. Shop stock; do not treat as ideal without its drawbacks.
- **Stats:** armor 2; +2 DAMROLL; -7 DEX.
- **Weight:** 4 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 40.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 2,500 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some combat knuckles”; keywords `combat knuckles`.
- **Prototype source:** [areas/obj/kimordril.obj](../../areas/obj/kimordril.obj#L239).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: Gildak [95542], NPC L30; [shop stock](../../areas/shp/kimordril.shp#L311).
- **Acquisition:** Drop/carried equipment: Gildak [95542], NPC L30; [reset](../../areas/zon/kimordril.zon#L397).
- **Authored description (combat knuckles):** These combat knuckles are not unlike a pair of brass knuckles. They fit around the hands easily, and have heavy spikes which could inflict damage if used properly.

<a id="vnum-300017"></a>

### 300017 — a pair of bone-razored talons — ivalue 1

- **Review role:** Conditional.
- **Fit / caution:** Knuckle/razor description, but no modifiers and no MAGIC. Distinct vnum from 15005.
- **Stats:** armor 0.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** OTHER (12); material BONE; craftsmanship ABOVE (9); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_SECRET. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of bone-razored talons”; keywords `bone talons bone-razored`.
- **Prototype source:** [areas/obj/thechasmofthemistyvale.obj](../../areas/obj/thechasmofthemistyvale.obj#L268).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: A small mud dweller [300014], NPC L33; [reset](../../areas/zon/thechasmofthemistyvale.zon#L171).
- **Authored description (talons bone bone-razored):** Cut off a mud dweller from the swamps of the misty chasm, these claws have been roughly cured and made into functional handwear. The bones that once took residence inside the hands have been worked sharp and lashed to the flesh so as to form razors that extend down from the wrists to just beyond the first set of knuckles.

<a id="vnum-16625"></a>

### 16625 — some ugly leather gloves — ivalue 3

- **Review role:** Defense/entry.
- **Fit / caution:** Zero-weight shop AC filler; entry option only.
- **Stats:** armor 0; -2 AC.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 100 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some ugly leather gloves”; keywords `gloves glove`.
- **Prototype source:** [areas/obj/woodseer.obj](../../areas/obj/woodseer.obj#L2053).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: Leelon the armorer [16546], NPC L45; [shop stock](../../areas/shp/woodseer.shp#L461).
- **Acquisition:** Drop/carried equipment: Leelon the armorer [16546], NPC L45; [reset](../../areas/zon/woodseer.zon#L607).
- **Authored description (gloves glove):** It is clear that whoever made these gloves was either not at their best or simply not skilled enough to bother. The stitching between the fingers is poorly done, making the gloves so worthless that it would almost be better to wear nothing at all.

<a id="vnum-55264"></a>

### 55264 — a pair of gloves with razor-sharp talons — ivalue 6

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 0; +1 HITROLL; +1 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** WORN (loaded from zero-armor ARMOR); material BONE; craftsmanship EXCELLENT (11); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of gloves with razor-sharp talons”; keywords `talons gloves razor sharp`.
- **Prototype source:** [areas/obj/wh.obj](../../areas/obj/wh.obj#L3274).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Grendilyn [55133], NPC L46; [reward and recipe](../../areas/qst/wh.qst#L2436).
- **Acquisition:** Quest inputs: the talons of a vulture [55227]; 2,000 quest currency units.
- **Acquisition:** Quest rewards: a pair of gloves with razor-sharp talons [55264].

<a id="vnum-94371"></a>

### 94371 — some rusty iron shackles — ivalue 6

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 7; -10 MV; +2 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_SECRET. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_LEGS, ITEM_WEAR_FEET, ITEM_WEAR_HANDS, ITEM_WEAR_ARMS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some rusty iron shackles”; keywords `rusty iron shackles`.
- **Prototype source:** [areas/obj/herders.obj](../../areas/obj/herders.obj#L1128).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Container reset: target [94370]; [reset](../../areas/zon/herders.zon#L571).
- **Authored description (rusty iron shackles):** These shackles are very old and extremely rusty. Corrosion over time has caused the shackles to warp causing very dangerous barbs to pertrude all over them like little rusty spikes.

<a id="vnum-3428"></a>

### 3428 — a pair of lead-filled gloves — ivalue 7

- **Review role:** Conditional.
- **Fit / caution:** Description explicitly has lead sewn into knuckles; 5 pounds and -4 DEX. Thematic reserve, poor monk weight trade.
- **Stats:** armor 6; +2 DAMROLL; -4 DEX.
- **Weight:** 5 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 50.
- **Template:** ARMOR; material LEATHER; craftsmanship S_BELOW (6); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; Deny classes: PSIONICIST, SORCERER, NECROMANCER, CONJURER, ROGUE, ASSASSIN, BARD, THIEF, MINDFLAYER, ILLUSIONIST, BLIGHTER, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of lead-filled gloves”; keywords `gloves pair leather lead filled`.
- **Prototype source:** [areas/obj/flind.obj](../../areas/obj/flind.obj#L406).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a flind trainer [3412], NPC L27; [reset](../../areas/zon/flind.zon#L175).
- **Authored description (gloves pair leather lead filled):** These leather gloves have pockets of lead sewn into the knuckle area to aid in striking. Each glove is very heavy and well worn.

<a id="vnum-96432"></a>

### 96432 — a pair of tough leather gloves — ivalue 7

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 0; -5 AC.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 300 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of tough leather gloves”; keywords `tough leather gloves`.
- **Prototype source:** [areas/obj/ixarkon.obj](../../areas/obj/ixarkon.obj#L496).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a duergar gardener [96447], NPC L15; [reset](../../areas/zon/ixarkon.zon#L283).
- **Authored description (tough leather gloves):** A pair of tough leather gloves, used by workers in the gardens.

<a id="vnum-89062"></a>

### 89062 — a pair of red cotton gloves — ivalue 9

- **Review role:** Defense/entry.
- **Fit / caution:** New Hope shop entry; zero weight and HP. Generic early option, no explicit monk identity.
- **Stats:** armor 1; +4 HP.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 200 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of red cotton gloves”; keywords `gloves cotton red`.
- **Prototype source:** [areas/obj/newhope.obj](../../areas/obj/newhope.obj#L1066).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: a tempermental drow [89098], NPC L46; [shop stock](../../areas/shp/newhope.shp#L136).
- **Acquisition:** Drop/carried equipment: a tempermental drow [89098], NPC L46; [reset](../../areas/zon/newhope.zon#L1311).
- **Authored description (gloves cotton red):** This pair of gloves is made from woven cotton that has been dyed a dark red color. They allow flexibility while granting a small protection from blows to the hand, as well as keeping the fingers warm during cold weather. A thin pad of leather is attached to the palm to aid in gripping things - like the handle of a weapon.

<a id="vnum-66417"></a>

### 66417 — some abominable cloth — ivalue 10

- **Review role:** Conditional.
- **Fit / caution:** Broad melee allow-list includes Monk but 5 pounds and no stat modifiers; detect magic alone does not establish monk ideal.
- **Stats:** armor 0; DETECT_MAGIC.
- **Weight:** 5 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 50.
- **Template:** type 8; material ELECTRUM; craftsmanship AVERAGE (7); condition 100; monetary cost 202 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, MONK, ROGUE, ASSASSIN, MERCENARY, THIEF, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES, ITEM_SECRET, ITEM_NOIDENTIFY. **Extra2 flags:** ITEM2_MAGIC, ITEM2_QUESTITEM.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some abominable cloth”; keywords `abominable cloth`.
- **Prototype source:** [areas/obj/battlefi.obj](../../areas/obj/battlefi.obj#L254).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Room reset: target [66524]; [reset](../../areas/zon/battlefi.zon#L186).
- **Authored description (shimmering gloves):** These gloves shimmer inbetween the state of visibility and transparency. With an odd color resembling that of silver, these things seem to adjust themselves to whomever wear's them. What they are made of is difficult to tell, maybe they're of a substance from the spiritual world.

<a id="vnum-89057"></a>

### 89057 — a pair of black cotton gloves — ivalue 10

- **Review role:** Defense/entry.
- **Fit / caution:** New Hope shop entry; zero weight and DEX. Generic early option, no explicit monk identity.
- **Stats:** armor 1; +4 DEX.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 200 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of black cotton gloves”; keywords `gloves black cotton`.
- **Prototype source:** [areas/obj/newhope.obj](../../areas/obj/newhope.obj#L980).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: a tempermental drow [89098], NPC L46; [shop stock](../../areas/shp/newhope.shp#L136).
- **Acquisition:** Drop/carried equipment: a tempermental drow [89098], NPC L46; [reset](../../areas/zon/newhope.zon#L1306).
- **Authored description (gloves black cotton):** This pair of finely made gloves has been created from black cotton. They are very flexible, not getting in the way of any movement, yet providing the hands with a small bit of protection as well as keeping them warm. It is an intense black color, seeming to absorb all of the light around it.

<a id="vnum-89067"></a>

### 89067 — a pair of green cotton gloves — ivalue 10

- **Review role:** Defense/entry.
- **Fit / caution:** New Hope shop entry; zero weight and AGI. Generic early option, no explicit monk identity.
- **Stats:** armor 1; +4 AGI.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 200 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of green cotton gloves”; keywords `gloves cotton green`.
- **Prototype source:** [areas/obj/newhope.obj](../../areas/obj/newhope.obj#L1155).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: a tempermental drow [89098], NPC L46; [shop stock](../../areas/shp/newhope.shp#L136).
- **Acquisition:** Drop/carried equipment: a tempermental drow [89098], NPC L46; [reset](../../areas/zon/newhope.zon#L1316).
- **Authored description (gloves cotton green):** This pair of gloves has been made from a sturdy cotton material as has been dyed a dark green with bright green stripes. The gloves do not hinder movement and keep fingers warm while protecting them a slight bit from blows so that it is possible to do complex tasks even in the coldest of weather.

<a id="vnum-89072"></a>

### 89072 — a pair of blue cotton gloves — ivalue 10

- **Review role:** Defense/entry.
- **Fit / caution:** New Hope shop entry; zero weight and CON. Generic early option, no explicit monk identity.
- **Stats:** armor 1; +4 CON.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 200 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of blue cotton gloves”; keywords `gloves cotton blue`.
- **Prototype source:** [areas/obj/newhope.obj](../../areas/obj/newhope.obj#L1241).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: a tempermental drow [89098], NPC L46; [shop stock](../../areas/shp/newhope.shp#L136).
- **Acquisition:** Drop/carried equipment: a tempermental drow [89098], NPC L46; [reset](../../areas/zon/newhope.zon#L1321).
- **Authored description (gloves cotton blue):** This pair of gloves is made from sturdy cotton that was dyed a dark blue color. Random strands of cotton in the gloves remained a light blue during the dying process, giving the gloves a speckled look. They are very light, allowing the fingers to do complex jobs, without leaving them open to being hurt. They also keep the hands warm during cold weather.

<a id="vnum-500110"></a>

### 500110 — a pair of gloves of the monk — ivalue 10

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Identifies as gloves of the monk. MAGIC. Weak stats despite Mu being level 60; good thematic target, not an early drop.
- **Stats:** armor 4; +1 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 2,319 (not ivalue).
- **Magic / usability:** MAGIC yes; Deny classes: PSIONICIST, SORCERER, NECROMANCER, CONJURER, ROGUE, ASSASSIN, BARD, THIEF, MINDFLAYER, ILLUSIONIST, BLIGHTER, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of simple leather gloves”; identifies as “a pair of gloves of the monk”; keywords `gloves leather simple _id_`.
- **Prototype source:** [areas/obj/surface.obj](../../areas/obj/surface.obj#L953).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Mu [500212], NPC L60; [reset](../../areas/zon/surface.zon#L570).
- **Authored description (gloves leather simple):** Made of leather, these gloves are so simple, it's scary.

<a id="vnum-16598"></a>

### 16598 — some thin leather gloves — ivalue 13

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 0; +4 DEX; -3 AC.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 200 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some thin leather gloves”; keywords `gloves leather`.
- **Prototype source:** [areas/obj/woodseer.obj](../../areas/obj/woodseer.obj#L1608).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the halfling warrior [16661], NPC L10; [reset](../../areas/zon/woodseer.zon#L378).
- **Authored description (gloves leather):** Thin soft leather has been carefully stitched togther to give extra protection to the hands without making it difficult to manipulate things.

<a id="vnum-17085"></a>

### 17085 — a pair of spiked adamantite gauntlets — ivalue 13

- **Review role:** Conditional.
- **Fit / caution:** Description has knuckle spikes, but 8 pounds for only +1 damage; poor monk trade and STR &gt;=80 equip gate by default.
- **Stats:** armor 6; +1 DAMROLL.
- **Weight:** 8 lb; half-weight attack contribution 4; default per-item equip gate STR ≥ 80.
- **Template:** ARMOR; material ADAMANTIUM; craftsmanship AVERAGE (7); condition 100; monetary cost 35,000 (not ivalue).
- **Magic / usability:** MAGIC no; Deny classes: PSIONICIST, SORCERER, NECROMANCER, CONJURER, MINDFLAYER, ILLUSIONIST, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of spiked adamantite gauntlets”; keywords `gauntlets spiked`.
- **Prototype source:** [areas/obj/khildarak.obj](../../areas/obj/khildarak.obj#L1099).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: a clansdwarf [17081], NPC L35; [shop stock](../../areas/shp/khildarak.shp#L359).
- **Acquisition:** Drop/carried equipment: a clansdwarf [17081], NPC L35; [reset](../../areas/zon/khildarak.zon#L2487).
- **Authored description (guantlets spiked):** These guantlets are finely crafted from polished steel. The joints are all very flexible making them very effective and comfortable. Long steel spikes protrude from the knuckle area making them a deadly weapon as well as good protection.

<a id="vnum-21575"></a>

### 21575 — a pair of iron knuckles — ivalue 13

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Iron knuckles: direct unarmed theme; light low-end offense. Bounty hunter L28.
- **Stats:** armor 6; +1 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of iron knuckles”; keywords `battered bloody iron knuckles`.
- **Prototype source:** [areas/obj/clfhaven.obj](../../areas/obj/clfhaven.obj#L866).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a bounty hunter [21608], NPC L28; [reset](../../areas/zon/clfhaven.zon#L803).

<a id="vnum-90718"></a>

### 90718 — some gloves sewn with human bones — ivalue 15

- **Review role:** Conditional.
- **Fit / caution:** Description puts sharp ridges along knuckles; 4 pounds for +2 damage is a mediocre monk trade.
- **Stats:** armor 5; +2 DAMROLL.
- **Weight:** 4 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 40.
- **Template:** ARMOR; material BONE; craftsmanship AVERAGE (7); condition 100; monetary cost 1,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_SECRET, ITEM_FLOAT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some gloves sewn with human bones”; keywords `gloves bone human sewn`.
- **Prototype source:** [areas/obj/river_styx.obj](../../areas/obj/river_styx.obj#L282).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a black abishai devil [90711], NPC L36; [reset](../../areas/zon/river_styx.zon#L71).
- **Authored description (gloves bone human sewn):** Fashioned from a common-looking leather, these gloves are remarkable in that pieces of human bone have been attached to the top of material, making the handwear look like a pair of skeletal hands. A faint black glow emminates from the bones, showing that magic is certainly at work here. As you look more closely at the bones, you can see sharp ridgids along the knuckles and the bones seem to slowly..move.

<a id="vnum-97033"></a>

### 97033 — a pair of blue and white gauntlets — ivalue 15

- **Review role:** Conditional.
- **Fit / caution:** Broad melee allow-list includes Monk, but only +1 hit at 3 pounds; weaker than lighter choices.
- **Stats:** armor 7; +1 HITROLL.
- **Weight:** 3 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 30.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 750 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of blue and white gauntlets”; keywords `gauntlets blue white`.
- **Prototype source:** [areas/obj/icecrag.obj](../../areas/obj/icecrag.obj#L463).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a sergeant [97020], NPC L41; [reset](../../areas/zon/icecrag.zon#L658).
- **Acquisition:** Drop/carried equipment: a lieutenant [97043], NPC L41; [reset](../../areas/zon/icecrag.zon#L676).
- **Acquisition:** Drop/carried equipment: a lieutenant [97044], NPC L41; [reset](../../areas/zon/icecrag.zon#L680).
- **Acquisition:** Drop/carried equipment: a lieutenant [97045], NPC L41; [reset](../../areas/zon/icecrag.zon#L692).
- **Acquisition:** Drop/carried equipment: a lieutenant [97046], NPC L41; [reset](../../areas/zon/icecrag.zon#L700).
- **Acquisition:** Drop/carried equipment: a member of the Upper Echelon [97037], NPC L41; [reset](../../areas/zon/icecrag.zon#L749).
- **Acquisition:** Drop/carried equipment: a member of the Court Patrol [97004], NPC L35; [reset](../../areas/zon/icecrag.zon#L760).
- **Acquisition:** Drop/carried equipment: a vault sentinel [97009], NPC L59; [reset](../../areas/zon/icecrag.zon#L819).
- **Acquisition:** Drop/carried equipment: a lieutenant [97047], NPC L41; [reset](../../areas/zon/icecrag.zon#L983).
- **Acquisition:** Drop/carried equipment: a lieutenant [97048], NPC L41; [reset](../../areas/zon/icecrag.zon#L988).
- **Acquisition:** Drop/carried equipment: a lieutenant [97049], NPC L41; [reset](../../areas/zon/icecrag.zon#L1006).
- **Acquisition:** Drop/carried equipment: a lieutenant [97050], NPC L41; [reset](../../areas/zon/icecrag.zon#L1011).
- **Acquisition:** Drop/carried equipment: the Commander [97021], NPC L55; [reset](../../areas/zon/icecrag.zon#L1057).
- **Authored description (gauntlets):** The gauntlets are standard issue to the castles guards. They are made from weapon grade steel and provide good coverage of the hand. Even though the colors are just painted on, there is no evidence of wear and tear yet.

<a id="vnum-16653"></a>

### 16653 — some sheer silk gloves — ivalue 16

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 0; -5 AC; +4 AGI.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN; material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 1,500 (not ivalue).
- **Magic / usability:** MAGIC no; Deny classes: PSIONICIST, SORCERER, NECROMANCER, CONJURER, MINDFLAYER, ILLUSIONIST, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** ITEM_FLOAT, ITEM_NOIDENTIFY. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some sheer silk gloves”; keywords `gloves silk`.
- **Prototype source:** [areas/obj/woodseer.obj](../../areas/obj/woodseer.obj#L2466).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: the handsome shopkeeper [16691], NPC L45; [shop stock](../../areas/shp/woodseer.shp#L764).
- **Acquisition:** Drop/carried equipment: the handsome shopkeeper [16691], NPC L45; [reset](../../areas/zon/woodseer.zon#L656).
- **Authored description (gloves silk):** These sheer silk gloves do little to protect against the elements, but they breathe well and don't restrict movement at all.

<a id="vnum-2682"></a>

### 2682 — a pair of iron gloves — ivalue 17

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +1 HITROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of iron gloves”; keywords `gloves iron`.
- **Prototype source:** [areas/obj/breale.obj](../../areas/obj/breale.obj#L717).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Esmerelda [2600], NPC L56; [reward and recipe](../../areas/qst/breale.qst#L24).
- **Acquisition:** Quest inputs: a fennel root [2674].
- **Acquisition:** Quest rewards: a pair of iron gloves [2682].

<a id="vnum-88205"></a>

### 88205 — a pair of shark-skin gloves — ivalue 17

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +1 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of shark-skin gloves”; keywords `gloves shark`.
- **Prototype source:** [areas/obj/kuotoa.obj](../../areas/obj/kuotoa.obj#L51).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a kuo-toa guard [88201], NPC L41; [reset](../../areas/zon/kuotoa.zon#L151).

<a id="vnum-93608"></a>

### 93608 — a pair of studded black leather gloves — ivalue 18

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +1 DAMROLL; +1 HITROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of studded black leather gloves”; keywords `gloves black leather`.
- **Prototype source:** [areas/obj/bordello.obj](../../areas/obj/bordello.obj#L75).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Padh, the big black bouncer [93605], NPC L35; [reset](../../areas/zon/bordello.zon#L32).

<a id="vnum-4014"></a>

### 4014 — a pair of warrior's gloves — ivalue 20

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Melee class allow-list explicitly includes Monk; 1-pound offense.
- **Stats:** armor 4; +2 HITROLL; +1 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 150 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of warrior's gloves”; keywords `gloves warriors warrior's pair`.
- **Prototype source:** [areas/obj/caves_skelenak.obj](../../areas/obj/caves_skelenak.obj#L186).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Goortok [4027], NPC L46; [reset](../../areas/zon/caves_skelenak.zon#L168).
- **Authored description (gloves warriors warrior's pair):** These are a very nice pair of gloves. They fit your hands perfectly.

<a id="vnum-15257"></a>

### 15257 — a pair of smooth batskin gloves — ivalue 22

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +2 HITROLL; +1 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material HIDE; craftsmanship AVERAGE (7); condition 100; monetary cost 5,000 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT, ITEM_NOSUMMON. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of smooth batskin gloves”; keywords `batskin gloves glove smooth`.
- **Prototype source:** [areas/obj/faang.obj](../../areas/obj/faang.obj#L530).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a fierce ogre warrior [15211], NPC L35; [reset](../../areas/zon/faang.zon#L426).

<a id="vnum-18723"></a>

### 18723 — a pair of shiny black gloves — ivalue 22

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +1 HITROLL; +2 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 22,585 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_GLOW, ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of shiny black gloves”; keywords `gloves`.
- **Prototype source:** [areas/obj/bogentok.obj](../../areas/obj/bogentok.obj#L227).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a troll sergeant [18735], NPC L55; [reset](../../areas/zon/bogentok.zon#L490).

<a id="vnum-10102"></a>

### 10102 — a pair of smooth batskin gloves — ivalue 25

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 6; +2 HITROLL; +1 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material HIDE; craftsmanship AVERAGE (7); condition 100; monetary cost 1,258 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_NOSUMMON. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of smooth batskin gloves”; keywords `gloves batskin bat skin smooth`.
- **Prototype source:** [areas/obj/mush1.obj](../../areas/obj/mush1.obj#L28).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a troll-ogre mutant [10101], NPC L35; [reset](../../areas/zon/mush1.zon#L44).

<a id="vnum-99416"></a>

### 99416 — a pair of spiked leather gloves — ivalue 25

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 6; +1 HITROLL; +2 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship SKILLED (12); condition 100; monetary cost 900 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of spiked leather gloves”; keywords `gloves`.
- **Prototype source:** [areas/obj/kastle.obj](../../areas/obj/kastle.obj#L238).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: Yngve Aarseth [42963], NPC L24; [shop stock](../../areas/shp/raxthan.shp#L1).
- **Acquisition:** Drop/carried equipment: Yngve Aarseth [42963], NPC L24; [reset](../../areas/zon/raxthan.zon#L103).
- **Acquisition:** Drop/carried equipment: Sir Vraklask [99433], NPC L38; [reset](../../areas/zon/kastle.zon#L421).
- **Authored description (gloves):** These gloves are made from a very fine grade of leather. Crimson stains can be seen upon the surface of the pointed spikes.

<a id="vnum-55401"></a>

### 55401 — a pair of fingerless leather gloves — ivalue 26

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 0; +5 DEX; +2 HITROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN (loaded from zero-armor ARMOR); material CLOTH; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_QUESTITEM.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of fingerless leather gloves”; keywords `fingerless leather gloves`.
- **Prototype source:** [areas/obj/wh.obj](../../areas/obj/wh.obj#L4772).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: Monfit [55119], NPC L46; [shop stock](../../areas/shp/wh.shp#L335).
- **Acquisition:** Drop/carried equipment: Monfit [55119], NPC L46; [reset](../../areas/zon/wh.zon#L849).

<a id="vnum-22422"></a>

### 22422 — the gloves of tearing — ivalue 27

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Description explicitly places razor-sharp steel over the knuckles; zero weight.
- **Stats:** armor 5; +2 HITROLL; +4 DEX.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship AVERAGE (7); condition 100; monetary cost 2,999 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gloves of tearing”; keywords `gloves tearing`.
- **Prototype source:** [areas/obj/stormport.obj](../../areas/obj/stormport.obj#L313).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Torn [22440], NPC L51; [reset](../../areas/zon/stormport.zon#L388).
- **Authored description (gloves tearing):** This pair of gloves have been crafted from heavy leather. Fastened to the knuckles are a semi-circle of razor sharp steel, which looks extremely painful if they were to contact flesh.

<a id="vnum-15005"></a>

### 15005 — a pair of bone razored talons — ivalue 29

- **Review role:** Light offense.
- **Fit / caution:** Melee allow-list includes Monk; no direct reset/shop/quest reward located. Distinct vnum from 300017.
- **Stats:** armor 8; +2 DAMROLL; +1 HITROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material BONE; craftsmanship ABOVE (9); condition 100; monetary cost 5,000 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: WARRIOR, ANTIPALADIN, MONK, ROGUE, ASSASSIN, MERCENARY, BARD, THIEF, ALCHEMIST, BERSERKER, BLIGHTER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES, ITEM_SECRET, ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of bone razored talons”; keywords `bone razored talons`.
- **Prototype source:** [areas/obj/mist_chasm.obj](../../areas/obj/mist_chasm.obj#L79).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** No direct AREA-selected reset, shop stock, or quest reward located; prototype presence alone does not establish ordinary availability.
- **Authored description (bone razored claws):** These claws have been chopped off of a mud dweller, the bone razors that protrude from the gloves are actually the remnants of the hands' former infra- structure.

<a id="vnum-74278"></a>

### 74278 — some chain linked fighting mitts — ivalue 30

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Fighting-mitt theme plus STR; shop stock, so keeper level 59 does not imply a level-59 equipment requirement.
- **Stats:** armor 4; +1 DAMROLL; +5 STR.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 5,432 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some chain linked fighting mitts”; keywords `mits chain linked fighting`.
- **Prototype source:** [areas/obj/bs.obj](../../areas/obj/bs.obj#L3316).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: the shop's keeper [74236], NPC L59; [shop stock](../../areas/shp/bs.shp#L1350).
- **Acquisition:** Drop/carried equipment: the shop's keeper [74236], NPC L59; [reset](../../areas/zon/bs.zon#L1958).

<a id="vnum-8109"></a>

### 8109 — an ashen volcanic-forged articulated finger gauntlets — ivalue 34

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 10; +2 HITROLL; +1 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material MITHRIL; craftsmanship ONE_KIND (15); condition 100; monetary cost 10,000 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_NOSELL, ITEM_FLOAT. **Extra2 flags:** ITEM2_SLAY_GOOD.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “an ashen volcanic-forged articulated finger gauntlets”; keywords `ashen volcanic-forged finger gauntlets`.
- **Prototype source:** [areas/obj/temple_laduguer.obj](../../areas/obj/temple_laduguer.obj#L141).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: an elite Duergar Dwarf guard [8108], NPC L46; [reset](../../areas/zon/temple_laduguer.zon#L405).
- **Authored description (gauntlets):** These gauntlets have been forged in the volcanic blacksmith forges of the Temple.

<a id="vnum-16626"></a>

### 16626 — some halfling-sized gauntlets — ivalue 37

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Melee class allow-list includes Monk; +STR and hitroll. No halfling race restriction in prototype despite name.
- **Stats:** armor 8; +5 STR; +1 HITROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 50,000 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES, ITEM_NOIDENTIFY. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some halfling-sized gauntlets”; keywords `gauntlets`.
- **Prototype source:** [areas/obj/woodseer.obj](../../areas/obj/woodseer.obj#L2070).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: Leelon the armorer [16546], NPC L45; [shop stock](../../areas/shp/woodseer.shp#L461).
- **Acquisition:** Drop/carried equipment: Leelon the armorer [16546], NPC L45; [reset](../../areas/zon/woodseer.zon#L608).
- **Authored description (gauntlets):** These gauntlets are made of a fine chain mesh that has been lined on the inside with soft linen, and lined on the outside with sharp polished spikes. This pair of gauntlets is clearly of the finest quality and workmanship, and must be worth a great deal of money.

<a id="vnum-82512"></a>

### 82512 — the claws of the ruiner — ivalue 37

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 9; +2 HITROLL; +2 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material BONE; craftsmanship AVERAGE (7); condition 100; monetary cost 100 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the claws of the ruiner”; keywords `claws ruiner`.
- **Prototype source:** [areas/obj/mira.obj](../../areas/obj/mira.obj#L175).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the ruiner [82513], NPC L50; [reset](../../areas/zon/mira.zon#L253).
- **Authored description (claws ruiner):** Upon examination of these claws you ask yourself. 'How did they get so big? How did they get so strong?'

<a id="vnum-22258"></a>

### 22258 — some spiked steel-mesh gloves — ivalue 43

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 9; +2 DAMROLL; +5 AGI.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 14,009 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spiked steel-mesh gloves”; keywords `steel mesh gloves`.
- **Prototype source:** [areas/obj/desolate.obj](../../areas/obj/desolate.obj#L903).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a vengeful outcast [22296], NPC L51; [reset](../../areas/zon/desolate.zon#L517).
- **Authored description (steel mesh gloves):** These loose fitting gloves are pulled comfortably over ones hands and offer some nice protection due to the high quality of steel in which they were crafted with.

<a id="vnum-77359"></a>

### 77359 — some spiked steel-mesh gloves — ivalue 43

- **Review role:** Light offense.
- **Fit / caution:** Distinct vnum from 22258 with same offensive stats; no normal reset/shop/quest reward located.
- **Stats:** armor 9; +2 DAMROLL; +5 AGI.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 14,009 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spiked steel-mesh gloves”; keywords `steel mesh gloves`.
- **Prototype source:** [areas/obj/desolateinv.obj](../../areas/obj/desolateinv.obj#L873).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** No direct AREA-selected reset, shop stock, or quest reward located; prototype presence alone does not establish ordinary availability.
- **Authored description (steel mesh gloves):** These loose fitting gloves are pulled comfortably over ones hands and offer some nice protection due to the high quality of steel in which they were crafted with.

<a id="vnum-7641"></a>

### 7641 — the gloves of the Knights of the Rose — ivalue 47

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +3 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 3,000 (not ivalue).
- **Magic / usability:** MAGIC no; Deny classes: PSIONICIST, SORCERER, CONJURER, MINDFLAYER, ILLUSIONIST, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gloves of the Knights of the Rose”; keywords `gloves knight knights rose`.
- **Prototype source:** [areas/obj/bastine.obj](../../areas/obj/bastine.obj#L596).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Sir Lyonel [7609], NPC L38; [reset](../../areas/zon/bastine.zon#L175).
- **Authored description (gloves glove knights knight rose):** On the gloves is imprinted the design of a rose within a shield.

<a id="vnum-44424"></a>

### 44424 — the spiked knuckles of punching — ivalue 54

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Identifies as spiked knuckles of punching; zero weight + HP + damroll. MAGIC.
- **Stats:** armor 6; +10 HP; +2 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spiked knuckles”; identifies as “the spiked knuckles of punching”; keywords `spiked knuckles _id_`.
- **Prototype source:** [areas/obj/githzer.obj](../../areas/obj/githzer.obj#L460).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Zangzk, the githzerai captain [44422], NPC L53; [reset](../../areas/zon/githzer.zon#L608).
- **Authored description (spiked knuckles):** These knuckles have several small straps banded together which can be fastened around the palm of the hand, fitting the knuckles very tightly and securely. Three large razor blades jut out of each hand, each between the middle knuckles. Covering the top of the hand is a black leather half-glove, similar to the type archers wear, also covered with tiny, adamantite spikes.

<a id="vnum-83468"></a>

### 83468 — some tricksters gloves — ivalue 54

- **Review role:** Defense/entry.
- **Fit / caution:** Negative weight is particularly attractive for monk AC/damage budgets, but ITEM_TRANSIENT is set (drop-sensitive).
- **Stats:** armor 5; +3 DEX_MAX; -3 SAVING_SPELL.
- **Weight:** -10 lb; half-weight attack contribution -5; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship MASTER (14); condition 100; monetary cost 33,442 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOSLEEP. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some tricksters gloves”; keywords `tricksters gloves`.
- **Prototype source:** [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj#L5999).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Sambisam the gnome trickster [83418], NPC L56; [reset](../../areas/zon/alatorin.zon#L2589).
- **Authored description (tricksters gloves):** These small silken gloves have a strange magical feel, contouring to their wearers hands and seeming to be repulsive to magic.

<a id="vnum-97913"></a>

### 97913 — some fur-cuffed cured leather gloves — ivalue 54

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +17 MV; +6 AGI.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship S_BELOW (6); condition 100; monetary cost 9,438 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some fur-cuffed cured leather gloves”; keywords `fur-cuffed cured leather gloves`.
- **Prototype source:** [areas/obj/surfacemini.obj](../../areas/obj/surfacemini.obj#L137).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a mountain farseer [97916], NPC L41; [reset](../../areas/zon/surfacemini.zon#L145).
- **Authored description (fur-cuffed cured leather boots):** This fine piece of cured leather clothing has white fur stitched along top, providing comfort and warmth.

<a id="vnum-40402"></a>

### 40402 — a pair of whitened steel gauntlets — ivalue 57

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 10; +2 HITROLL; +6 DEX.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material STEEL; craftsmanship S_ABOVE (8); condition 100; monetary cost 5,555 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of whitened steel gauntlets”; keywords `gauntlets steel whitened`.
- **Prototype source:** [areas/obj/gold_hal.obj](../../areas/obj/gold_hal.obj#L29).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the master knight teacher [40404], NPC L44; [reset](../../areas/zon/gold_hal.zon#L673).
- **Authored description (gauntlets steel whitened):** These gauntlets are made of polished steel, and have small gold hinges about them for them to move during combat. The top of the gauntlets around the knuckle area seems about four inches thick, while the palm side is made of only cured leather, to ensure maximum maneuvurability for the hands, and allows much better grip. These gauntlets were made from pure steel melted with a strange white substance to make the hard metal seem bright. Very finely made, and very beautiful these gauntlets are indeed lustrous and costly.

<a id="vnum-30844"></a>

### 30844 — a pair of heavy spiked combat gloves — ivalue 58

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +3 DAMROLL; +4 STR.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CLOTH; craftsmanship BELOW (5); condition 100; monetary cost 10,000 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of heavy spiked combat gloves”; keywords `heavy spiked combat gloves`.
- **Prototype source:** [areas/obj/stormht.obj](../../areas/obj/stormht.obj#L674).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: an elite captain [30835], NPC L40; [reset](../../areas/zon/stormht.zon#L251).

<a id="vnum-28597"></a>

### 28597 — a set of neberihide gloves — ivalue 60

- **Review role:** Light offense.
- **Fit / caution:** Stored base armor is -8 (unusual); report raw value, not a computed AC claim.
- **Stats:** armor -8; +3 DEX; +3 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship EXCELLENT (11); condition 100; monetary cost 800 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_GLOW, ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a set of neberihide gloves”; keywords `gloves neberi neberihide`.
- **Prototype source:** [areas/obj/pods.obj](../../areas/obj/pods.obj#L1526).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a wild male elfling [28602], NPC L55; [reset](../../areas/zon/pods.zon#L545).
- **Authored description (gloves neberi neberihide):** The thick hide of the neberi has been wrought into a pair of gloves by an expert leatherworker. The striations of color have been used to great effect, creating what seems to be restless bands of color that move across the back of the wearer's hands ceaselessly.

<a id="vnum-5813"></a>

### 5813 — a pair of ghostly gloves — ivalue 64

- **Review role:** Defense/entry.
- **Fit / caution:** Negative weight helps full worn-weight budgets; MAGIC. Shop and ghost-quartermaster L51 drop; ingredient for 5817.
- **Stats:** armor 8; +14 HP; +4 POW.
- **Weight:** -10 lb; half-weight attack contribution -5; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material NONSUBSTANTIAL; craftsmanship AVERAGE (7); condition 100; monetary cost 46,989 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOREPAIR. **Extra2 flags:** ITEM2_MAGIC, ITEM2_QUESTITEM.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of ghostly gloves”; keywords `pair ghostly gloves`.
- **Prototype source:** [areas/obj/minizones.obj](../../areas/obj/minizones.obj#L1514).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: the ghost of the quartermaster [5812], NPC L51; [shop stock](../../areas/shp/minizones.shp#L164).
- **Acquisition:** Drop/carried equipment: the ghost of the quartermaster [5812], NPC L51; [reset](../../areas/zon/minizones.zon#L793).
- **Authored description (pair ghostly gloves):** These gloves shimmer with a ghostly omnipresence.

<a id="vnum-44414"></a>

### 44414 — a pair of adamantite-plated gloves — ivalue 65

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 13; +3 DAMROLL; -1 SAVING_SPELL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; Deny classes: PSIONICIST, SORCERER, NECROMANCER, CONJURER, ROGUE, ASSASSIN, THIEF, MINDFLAYER, ILLUSIONIST, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** ITEM_GLOW. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of adamantite-plated gloves”; keywords `gloves plated adamantite`.
- **Prototype source:** [areas/obj/githzer.obj](../../areas/obj/githzer.obj#L255).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a githzerai tactical sergeant [44415], NPC L43; [reset](../../areas/zon/githzer.zon#L580).
- **Authored description (gloves plated adamantite):** These black-leather gloves are plated with large, spiked pieces of dark adamantite.

<a id="vnum-31823"></a>

### 31823 — a pair of hydra's claws — ivalue 66

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +2 HITROLL; +2 DAMROLL; PROT_FIRE.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material FLESH; craftsmanship W_ABOVE (10); condition 100; monetary cost 785 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of hydra's claws”; keywords `claws hydra`.
- **Prototype source:** [areas/obj/icetower.obj](../../areas/obj/icetower.obj#L387).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a cave hydra [31808], NPC L49; [reset](../../areas/zon/icetower.zon#L224).
- **Authored description (claws hydra):** A vile pair of hydra's claws have been hollowed out to fit as a pair of gloves with very sharp nails.

<a id="vnum-96062"></a>

### 96062 — the claws of the destroyer — ivalue 67

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +3 DAMROLL; +5 DEX.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material BONE; craftsmanship AVERAGE (7); condition 100; monetary cost 40,000 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the claws of the destroyer”; keywords `claws destroyer`.
- **Prototype source:** [areas/obj/jotun.obj](../../areas/obj/jotun.obj#L1018).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Grishnar [96071], NPC L58; [reward and recipe](../../areas/qst/jotun.qst#L290).
- **Acquisition:** Quest inputs: the sacred totem of the snow trolls [96061].
- **Acquisition:** Quest rewards: the claws of the destroyer [96062]; 100,000 experience.
- **Acquisition:** Quest: Rashnik [96072], NPC L58; [reward and recipe](../../areas/qst/jotun.qst#L325).
- **Acquisition:** Quest inputs: the feathered standard of the ice trolls [96060].
- **Acquisition:** Quest rewards: the claws of the destroyer [96062]; 100,000 experience.
- **Authored description (claws destroyer):** This wicked clawed glove is passed among the troll shamans of Jotunheim as an emblem of Vaprak's pleasure. Only a great service to one of the shamans could cause him to depart with his gloves.

<a id="vnum-18002"></a>

### 18002 — the claws of Vermithrax — ivalue 69

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +3 DAMROLL; +1 HITROLL.
- **Weight:** 3 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 30.
- **Template:** ARMOR; material BONE; craftsmanship AVERAGE (7); condition 100; monetary cost 9,483 (not ivalue).
- **Magic / usability:** MAGIC no; Deny classes: PSIONICIST, CLERIC, DRUID, SHAMAN, SORCERER, NECROMANCER, CONJURER, WARLOCK, MINDFLAYER, ILLUSIONIST, ETHERMANCER, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the claws of Vermithrax”; keywords `claws dragon vermithrax`.
- **Prototype source:** [areas/obj/wolfen.obj](../../areas/obj/wolfen.obj#L39).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Vermithrax, the celestial dragon [18000], NPC L59; [reset](../../areas/zon/wolfen.zon#L165).
- **Authored description (claws dragon vermithrax):** These claws have been treated and converted into a pair of battle gloves. The dragon's skin had been tanned, and its scales sewn to the flesh which inturn had the claw bones attached for added protection.

<a id="vnum-5054"></a>

### 5054 — some diamondine gauntlets — ivalue 71

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 12; +3 DAMROLL; -2 SAVING_PARA.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material DIAMOND; craftsmanship ONE_KIND (15); condition 100; monetary cost 78,181 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_SECRET, ITEM_FLOAT, ITEM_NORESET, ITEM_NOSUMMON, ITEM_NOSLEEP, ITEM_NOCHARM. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some diamondine gauntlets”; keywords `gauntlets diamondine`.
- **Prototype source:** [areas/obj/labyrinth.obj](../../areas/obj/labyrinth.obj#L821).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a massive diamondine golem [5020], NPC L57; [reset](../../areas/zon/labyrinth.zon#L332).
- **Authored description (gauntlets diamondine):** These gauntlets have been crafted from a very good grade of diamondine. Not a flaw is evident upon the hard slick surface of them.

<a id="vnum-6617"></a>

### 6617 — some fingerless hunting gloves — ivalue 71

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +15 HP; +5 CON.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship EXCELLENT (11); condition 100; monetary cost 13,000 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some fingerless hunting gloves”; keywords `fingerless hunting gloves`.
- **Prototype source:** [areas/obj/shaughin2.obj](../../areas/obj/shaughin2.obj#L141).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a shaughin elite hunter [6607], NPC L54; [reset](../../areas/zon/shaughin2.zon#L107).

<a id="vnum-49158"></a>

### 49158 — a pair of gnomish mesh gloves — ivalue 71

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 12; +5 DEX; +7 STR.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 12,928 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of gnomish mesh gloves”; keywords `gnomish mesh gloves`.
- **Prototype source:** [areas/obj/desert.obj](../../areas/obj/desert.obj#L2342).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Shop: Burnn [49203], NPC L55; [shop stock](../../areas/shp/desert.shp#L235).
- **Acquisition:** Drop/carried equipment: Burnn [49203], NPC L55; [reset](../../areas/zon/desert.zon#L1595).
- **Authored description (gnomish mesh gloves):** These gloves were designed by the gnomes. They seem to fit snugly around the hands.

<a id="vnum-96078"></a>

### 96078 — the talons of the raven — ivalue 71

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +15 HP; +5 STR.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material BONE; craftsmanship AVERAGE (7); condition 100; monetary cost 5,440 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the talons of the raven”; keywords `talons raven`.
- **Prototype source:** [areas/obj/jotun.obj](../../areas/obj/jotun.obj#L1281).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Mimir [96013], NPC L59; [reward and recipe](../../areas/qst/jotun.qst#L36).
- **Acquisition:** Quest inputs: an intricate golden amulet [96008].
- **Acquisition:** Quest rewards: the talons of the raven [96078]; 80,000 experience.
- **Acquisition:** Drop/carried equipment: Jabulanth [32829], NPC L58; [reset](../../areas/zon/shabo.zon#L372).
- **Authored description (talons raven):** These gloves have been skillfully crafted from the finest leather, and died a deep black. Images of ravens scrawl across the black surface of the glove; the ravens are of a black so deep that they seem to suck all light into their surface. The gloves seem to mold themselves to fit the shape of their wearer.

<a id="vnum-142295"></a>

### 142295 — a pair of swashbucklers gauntlets — ivalue 71

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 0; +3 DAMROLL; +3 STR_MAX.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_FLOAT, ITEM_LIT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of swashbucklers gauntlets”; keywords `gauntlets`.
- **Prototype source:** [areas/obj/blackpearl.obj](../../areas/obj/blackpearl.obj#L994).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a thin weary slave [142250], NPC L56; [reset](../../areas/zon/blackpearl.zon#L597).

<a id="vnum-8410"></a>

### 8410 — the claws of a werewolf — ivalue 75

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +3 HITROLL; -3 SAVING_BREATH.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material HIDE; craftsmanship W_ABOVE (10); condition 100; monetary cost 13,628 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NODROP, ITEM_SECRET, ITEM_NOIDENTIFY. **Extra2 flags:** ITEM2_BLESS, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the claws of a werewolf”; keywords `claws werewolf`.
- **Prototype source:** [areas/obj/grave.obj](../../areas/obj/grave.obj#L152).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a werewolf [8405], NPC L35; [reset](../../areas/zon/grave.zon#L204).
- **Authored description (claws werewolf):** These claws have been severed from a lycanthrope and seem to be wearable as a set of gloves.

<a id="vnum-16245"></a>

### 16245 — obsidian gauntlets — ivalue 75

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Melee class allow-list includes Monk; 1 pound, +3 damroll.
- **Stats:** armor 8; +3 DAMROLL; -3 SAVING_PARA.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material OBSIDIAN; craftsmanship V_SKILLED (13); condition 100; monetary cost 10,000 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “obsidian gauntlets”; keywords `gauntlets obsidian`.
- **Prototype source:** [areas/obj/trnsptow.obj](../../areas/obj/trnsptow.obj#L732).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a lost adventurer [16230], NPC L60; [reset](../../areas/zon/trnsptow.zon#L215).
- **Authored description (gauntlets):** Made of dark obsidian, the insides of these gauntlets have been worn smooth to protect the wearer. The outer edges have been left rough and sharp, pliable only due to the magic they have been imbued with. Any magic powerful enough to make stone this pliable and strong is a magic to be respected.

<a id="vnum-42270"></a>

### 42270 — a set of sharp blue claws — ivalue 75

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 4; +8 AGI; +2 HITROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material BONE; craftsmanship AVERAGE (7); condition 100; monetary cost 2,100 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_INVISIBLE, ITEM_FLOAT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a set of sharp blue claws”; keywords `claws blue set`.
- **Prototype source:** [areas/obj/tribal.obj](../../areas/obj/tribal.obj#L1097).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Room reset: target [42302]; [reset](../../areas/zon/tribal.zon#L191).
- **Authored description (claws blue set):** A set of razor sharp blue claws attached to pieces of blue leather, this thing could be probably worn on hand for improved combat performance as well as

<a id="vnum-42912"></a>

### 42912 — some spiked raxian pit gauntlets — ivalue 75

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; -3 SAVING_PARA; +3 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material SILVER; craftsmanship EXCELLENT (11); condition 100; monetary cost 9,000 (not ivalue).
- **Magic / usability:** MAGIC yes; Deny classes: PSIONICIST, CLERIC, DRUID, SHAMAN, SORCERER, NECROMANCER, CONJURER, WARLOCK, MINDFLAYER, ILLUSIONIST, ETHERMANCER, THEURGIST, SUMMONER; Deny races: THRIKREEN, CENTAUR.
- **Extra flags:** ITEM_FLOAT, ITEM_NOSLEEP, ITEM_NOCHARM. **Extra2 flags:** ITEM2_SILVER, ITEM2_BLESS, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spiked raxian pit gauntlets”; keywords `spiked raxian gauntlets pit`.
- **Prototype source:** [areas/obj/raxthan.obj](../../areas/obj/raxthan.obj#L240).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a raxian pit fighter [42918], NPC L36; [reset](../../areas/zon/raxthan.zon#L63).
- **Authored description (spiked raxian gauntlets pit):** These gauntlets seem to be made from a strange silverish substance. Perhaps even silver itself, they are covered in spikes. You notice they are very thick and at the same time very flexiable.

<a id="vnum-99537"></a>

### 99537 — a fine pair of gloves studded with amethysts — ivalue 81

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +16 HP; -3 SAVING_FEAR.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material RUBY; craftsmanship ONE_KIND (15); condition 100; monetary cost 109,285 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a fine pair of gloves studded with amethysts”; keywords `gloves amethysts`.
- **Prototype source:** [areas/obj/cldgt.obj](../../areas/obj/cldgt.obj#L456).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Stronmar, the cloud giant king [99552], NPC L58; [reset](../../areas/zon/cldgt.zon#L572).

<a id="vnum-38121"></a>

### 38121 — some dragonscale gloves — ivalue 82

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 12; +5 CON; +15 HP.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material DRAGONSCALE; craftsmanship SKILLED (12); condition 100; monetary cost 1,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** ITEM2_BLESS, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some dragonscale gloves”; keywords `dragonscale gloves`.
- **Prototype source:** [areas/obj/fortb.obj](../../areas/obj/fortb.obj#L223).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Ciuto [38114], NPC L60; [reset](../../areas/zon/fortb.zon#L187).

<a id="vnum-83557"></a>

### 83557 — some fingerless orog-hide gloves — ivalue 84

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +17 HP; +2 DAMROLL.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material HIDE; craftsmanship AVERAGE (7); condition 100; monetary cost 153 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some fingerless orog-hide gloves”; keywords `fingerless orog hide orog-hide gloves`.
- **Prototype source:** [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj#L7712).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Metlan the smuggler leader [83381], NPC L53; [reset](../../areas/zon/alatorin.zon#L3633).
- **Authored description (fingerless orog hide orog-hide gloves):** These thick gloves have been stitched together with the skinned hide of an orog. They lack any fingers, however, allowing for greater gripping mobility by their wearer.

<a id="vnum-66438"></a>

### 66438 — some white fur skin gloves — ivalue 89

- **Review role:** Conditional.
- **Fit / caution:** Broad melee allow-list includes Monk, +3 dam/max DEX, but 5-pound cost; low priority against lighter options.
- **Stats:** armor 8; +3 DAMROLL; +3 DEX_MAX.
- **Weight:** 5 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 50.
- **Template:** ARMOR; material FLESH; craftsmanship AVERAGE (7); condition 100; monetary cost 1,234 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some white fur skin gloves”; keywords `white fur gloves skin`.
- **Prototype source:** [areas/obj/battlefi.obj](../../areas/obj/battlefi.obj#L633).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: an angry gorilla [66429], NPC L55; [reset](../../areas/zon/battlefi.zon#L356).
- **Authored description (white fur gloves skin):** These gloves come from the fur of a white ape. These apes are urban legends come to life. Many unsuspecting travellers have been caught unaware by these beasts, and ripped apart.

<a id="vnum-30006"></a>

### 30006 — a pair of gloves studded with durithalite — ivalue 91

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 9; +3 HITROLL; +10 HP.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship V_SKILLED (13); condition 100; monetary cost 23,850 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of gloves studded with durithalite”; keywords `gloves durithalite`.
- **Prototype source:** [areas/obj/underworld3.obj](../../areas/obj/underworld3.obj#L96).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Llaranc, the great drow fisherman [30025], NPC L55; [reset](../../areas/zon/underworld3.zon#L174).
- **Authored description (gloves durithalite):** These fine black-leather gloves have been studded with finely cut pieces of durithalite.

<a id="vnum-67259"></a>

### 67259 — some fingerless gloves of su-monster skin — ivalue 91

- **Review role:** Benchmark.
- **Fit / caution:** ARTIFACT stat benchmark, no assigned native proc found.
- **Stats:** armor 0; +25 HP; -2 SAVING_PARA.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN (loaded from zero-armor ARMOR); material FLESH; craftsmanship ONE_KIND (15); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOSELL, ITEM_FLOAT, ITEM_NOLOCATE, ITEM_ARTIFACT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some fingerless gloves of su-monster skin”; keywords `gloves unique fingerless su monster su-monster skin`.
- **Prototype source:** [areas/obj/unique.obj](../../areas/obj/unique.obj#L940).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the su-elder [95301], NPC L36; [reset](../../areas/zon/darkfall.zon#L35).

<a id="vnum-76052"></a>

### 76052 — a pair of sunstone knuckles — ivalue 91

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Narrow allow-list: Monk, Berserker, Dreadlord ONLY. Zero weight. NOT MAGIC in prototype.
- **Stats:** armor 8; +3 DEX_MAX; +3 HITROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material STONE; craftsmanship SKILLED (12); condition 100; monetary cost 8,821 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: MONK, BERSERKER, DREADLORD.
- **Extra flags:** ITEM_GLOW, ITEM_ALLOWED_CLASSES. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of sunstone knuckles”; keywords `sunstone knuckles`.
- **Prototype source:** [areas/obj/cosmic.obj](../../areas/obj/cosmic.obj#L689).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Omoona [76052], NPC L60; [reset](../../areas/zon/cosmic.zon#L497).

<a id="vnum-42168"></a>

### 42168 — a wet pair of black gloves — ivalue 93

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 3; +20 HP; +2 HITROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material WAX; craftsmanship SKILLED (12); condition 100; monetary cost 72,020 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NODROP, ITEM_SECRET, ITEM_FLOAT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a wet pair of black gloves”; keywords `gloves black wet evil`.
- **Prototype source:** [areas/obj/mir.obj](../../areas/obj/mir.obj#L532).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Container reset: target [42174]; [reset](../../areas/zon/mir.zon#L54).
- **Authored description (gloves wet black evil):** This bizzare pair of black gloves is made from an unknown silk-like material. It is wet in touch, and fits well to every hand, shrinking itself a little when being put on. It vaguely pulsates with its own rhythm.

<a id="vnum-83505"></a>

### 83505 — some black leather gloves with mithril blades — ivalue 100

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Description explicitly puts mithril razor blades over knuckles; zero weight, max DEX and damroll. Also optional second-hand-slot Chaos gear.
- **Stats:** armor 5; +4 DEX_MAX; +3 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material LEATHER; craftsmanship W_ABOVE (10); condition 100; monetary cost 11,221 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some black leather gloves with mithril blades”; keywords `black leather gloves mithril blades`.
- **Prototype source:** [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj#L6656).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Gimabon the tracker [83436], NPC L59; [reward and recipe](../../areas/qst/alatorin.qst#L7053).
- **Acquisition:** Quest inputs: the bloody head of Gr'Tak the Raider [500004]; the bloody head of Krekish ViceFang [500006].
- **Acquisition:** Quest rewards: some black leather gloves with mithril blades [83505]; a commendation token of stealth [83463]; 60,000 experience.
- **Authored description (black leather gloves mithril blades):** These black leather gloves fit snugly around ones hands. Small razor blades made of thin slivers of mithril protrude from the knuckles of these gloves.

<a id="vnum-1452"></a>

### 1452 — a glowing, clawed talon of a tako demon — ivalue 106

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 5; +3 HITROLL; +3 DAMROLL.
- **Weight:** 3 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 30.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 10,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NODROP, ITEM_SECRET, ITEM_NOSUMMON, ITEM_LIT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a glowing, clawed talon of a tako demon”; keywords `clawed talon demon tako`.
- **Prototype source:** [areas/obj/kobold.obj](../../areas/obj/kobold.obj#L805).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a summoned tako demon [1436], NPC L59; [reset](../../areas/zon/kobold.zon#L282).
- **Authored description (clawed talon demon tako):** The talon is a glovelike sheath which can either be worn or held with the razor sharp claw of the tako demon sticking out of it. The object glows with an errie, evil light... possed of a dangerous magic.

<a id="vnum-75827"></a>

### 75827 — some spiked gauntlets of the Sixth Legion — ivalue 107

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +4 HITROLL; +2 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 15,091 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_NODROP. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spiked gauntlets of the Sixth Legion”; keywords `spiked gauntlets sixth legion`.
- **Prototype source:** [areas/obj/roguerai.obj](../../areas/obj/roguerai.obj#L337).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Mabus [75834], NPC L56; [reset](../../areas/zon/roguerai.zon#L238).

<a id="vnum-70937"></a>

### 70937 — the claws of the Soulrender — ivalue 111

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Identifies as claws of the Soulrender; fists of steel before identify. Allow-list includes Monk and rogues; NOT MAGIC.
- **Stats:** armor 7; +3 HITROLL; +3 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 2,000 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: MONK, ROGUE, ASSASSIN, MERCENARY, BARD, THIEF, BLIGHTER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some fists of steel”; identifies as “the claws of the Soulrender”; keywords `fists steel claws souldrender _id_`.
- **Prototype source:** [areas/obj/knight.obj](../../areas/obj/knight.obj#L395).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Volknur [70914], NPC L60; [reset](../../areas/zon/knight.zon#L275).

<a id="vnum-97057"></a>

### 97057 — the skinned hands of a troll — ivalue 118

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 9; +15 HP_REGEN; +2 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material HIDE; craftsmanship AVERAGE (7); condition 100; monetary cost 8,000 (not ivalue).
- **Magic / usability:** MAGIC no; Deny classes: CLERIC, DRUID, SHAMAN, WARLOCK, MINDFLAYER, ETHERMANCER, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the skinned hands of a troll”; keywords `skinned hands troll`.
- **Prototype source:** [areas/obj/icecrag.obj](../../areas/obj/icecrag.obj#L830).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Cision [97026], NPC L60; [reset](../../areas/zon/icecrag.zon#L1015).
- **Authored description (troll hands skinned):** A horrid sight indeed. Troll hands alone are enough to send chills down ones spine, but disembodied and skinned is outrageous. They are rather thick, almost one quarter of an inch in some places. The green skin is covered in old blisters and sores, and shockingly, they still fester. The skin is plyable and slightly warm. Almost as if the tissue were still alive.

<a id="vnum-78482"></a>

### 78482 — a pair of mailed dragoon gloves — ivalue 119

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 8; +4 DAMROLL; +3 DEX_MAX.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material MITHRIL; craftsmanship MASTER (14); condition 100; monetary cost 33,453 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of mailed dragoon gloves”; keywords `pair mailed dragoon gloves`.
- **Prototype source:** [areas/obj/caertannad.obj](../../areas/obj/caertannad.obj#L1220).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Mithranil the Dragoon [78493], NPC L51; [reward and recipe](../../areas/qst/caertannad.qst#L779).
- **Acquisition:** Quest inputs: Blackbeard's chest [78481].
- **Acquisition:** Quest rewards: a pair of mailed dragoon gloves [78482].
- **Authored description (pair mailed dragoon gloves):** These dragons bear markings of dwarven design.

<a id="vnum-70943"></a>

### 70943 — titanium gauntlets, made for pounding — ivalue 123

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Identifies as titanium gauntlets, made for pounding; melee allow-list includes Monk.
- **Stats:** armor 12; +3 HITROLL; +3 DAMROLL.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 3,000 (not ivalue).
- **Magic / usability:** MAGIC no; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_GLOW, ITEM_ALLOWED_CLASSES. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gauntlets of pounding”; identifies as “titanium gauntlets, made for pounding”; keywords `gauntlets pounding _id_`.
- **Prototype source:** [areas/obj/knight.obj](../../areas/obj/knight.obj#L479).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Bearax, Lord of Warriors [70924], NPC L51; [reset](../../areas/zon/knight.zon#L322).

<a id="vnum-36"></a>

### 36 — gloves of smooth dragon scale — ivalue 127

- **Review role:** Conditional.
- **Fit / caution:** Native fumblegaunts exists but explicitly returns without effect for CLASS_MONK. No normal source found. Do not count its proc as a monk benefit.
- **Stats:** armor 10; +3 HITROLL; -5 SAVING_BREATH.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material DRAGONSCALE; craftsmanship EXCELLENT (11); condition 100; monetary cost 3,456 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “gloves of smooth dragon scale”; keywords `dragon gloves scale`.
- **Prototype source:** [areas/obj/heavens.obj](../../areas/obj/heavens.obj#L401).
- **Existing proc:** `fumblegaunts`; [binding](../../src/specs/specs.assign.c#L1337), [callback](../../src/specs/specs.object.c#L8244). Raw native proc credit **5**, before itemvalue multipliers.
- **Proc behavior:** Assigned native proc explicitly returns for CLASS_MONK. Its generic ivalue credit is still counted, but its combat proc is not a monk benefit.
- **Acquisition:** No direct AREA-selected reset, shop stock, or quest reward located; prototype presence alone does not establish ordinary availability.
- **Authored description (dragon gloves scale):** These gloves were carefully created from scales of a dragon, probably an infant dragon. The scales are smooth, allowing the wielder great agility when holding something, if they can keep their hands on it...

<a id="vnum-83588"></a>

### 83588 — a pair of black leather gloves glowing with faerie fire — ivalue 127

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 10; +5 AGI_MAX; -5 SAVING_SPELL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material CURED_LEATHER; craftsmanship W_ABOVE (10); condition 100; monetary cost 25,443 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_GLOW. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of black leather gloves glowing with faerie fire”; keywords `black leather gloves glowing faerie fire`.
- **Prototype source:** [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj#L8426).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Basillion the drow worm hunter [83488], NPC L60; [reset](../../areas/zon/alatorin.zon#L4418).
- **Authored description (black leather gloves glowing faerie fire):** This fine pair of black leather gloves fits tightly around ones hands, with buckled-straps wrapping around wrists for optimal stability. A deep, mystical enchantment on these gloves has caused them to burn with faerie fire.

<a id="vnum-34565"></a>

### 34565 — a pair of darkmail gauntlets — ivalue 139

- **Review role:** Light offense.
- **Fit / caution:** Strong 1-pound melee/max-STR combination; no normal reset/shop/quest reward located.
- **Stats:** armor 14; +5 STR_MAX; +3 DAMROLL.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material STONE; craftsmanship MASTER (14); condition 100; monetary cost 15,650 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of darkmail gauntlets”; keywords `gauntlets darkmail rock`.
- **Prototype source:** [areas/obj/4horse.obj](../../areas/obj/4horse.obj#L1046).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Room reset: target [34804]; [reset](../../areas/zon/4horse.zon#L228).
- **Authored description (gauntlets darkmail rock):** Darkmail is a strange material that is believed to be alien in nature. The rock used in the creation of these gauntlets could be from a meteorite that struck the planet aeons ago. The gauntlets are strong, yet pliable and they are very magical in nature.

<a id="vnum-77534"></a>

### 77534 — some thick cargo gloves — ivalue 144

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 20; +3 HITROLL; +3 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material HIDE; craftsmanship AVERAGE (7); condition 100; monetary cost 7,899 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_GLOW. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some thick cargo gloves”; keywords `thick heavy cargo gloves`.
- **Prototype source:** [areas/obj/airshipgrave.obj](../../areas/obj/airshipgrave.obj#L493).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the undead cargo handler [77522], NPC L54; [reset](../../areas/zon/airshipgrave.zon#L219).
- **Authored description (thick heavy cargo gloves):** It would certainly take good craftsmanship and very strong leather to construct a pair of gloves that are not only are fit for the head cargo handler on one of the busiest transport ships ever but also manage to last for hundreds of years buried beneath the mountain while even the former user has long since decayed.

<a id="vnum-23055"></a>

### 23055 — the gauntlets of immortality — ivalue 145

- **Review role:** Light offense.
- **Fit / caution:** Strong zero-weight-budget melee stats at 1 pound; no normal reset/shop/quest reward located.
- **Stats:** armor 0; +4 DAMROLL; +20 HP.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** WORN; material SILICON; craftsmanship ONE_KIND (15); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_GLOW, ITEM_HUM. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gauntlets of immortality”; keywords `gauntlets immortality`.
- **Prototype source:** [areas/obj/nyneth2.obj](../../areas/obj/nyneth2.obj#L523).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Room reset: target [23098]; [reset](../../areas/zon/nyneth2.zon#L135).

<a id="vnum-138931"></a>

### 138931 — a pair of skeletal gauntlets — ivalue 150

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 10; +3 DAMROLL; +3 HITROLL; HAWKVISION.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material BONE; craftsmanship W_ABOVE (10); condition 100; monetary cost 78,021 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_NOREPAIR, ITEM_NODROP. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of skeletal gauntlets”; keywords `bone skeletal gauntlets`.
- **Prototype source:** [areas/obj/lornecro.obj](../../areas/obj/lornecro.obj#L520).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Faethor [138919], NPC L51; [reset](../../areas/zon/lornecro.zon#L302).
- **Authored description (bone skeletal gauntlets):** These gauntlets have been made of a skeleton's hand that has been magicaly sewn together with a black fabric that gives the glove a dire and sinister appearance.

<a id="vnum-132006"></a>

### 132006 — a pair of silverish githyanki gauntlets — ivalue 151

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 10; +4 HITROLL; +3 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material SILVER; craftsmanship EXCELLENT (11); condition 100; monetary cost 782 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** ITEM2_SILVER, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of silverish githyanki gauntlets”; keywords `silverish githyanki gauntlets`.
- **Prototype source:** [areas/obj/githyanki_fortress.obj](../../areas/obj/githyanki_fortress.obj#L65).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Di'zanr'reak the githyanki chief knight [132002], NPC L58; [reset](../../areas/zon/githyanki_fortress.zon#L153).

<a id="vnum-88919"></a>

### 88919 — some snake-rattle gloves — ivalue 159

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 15; +15 HP; +10 MV; AWARE.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material REPTILESCALE; craftsmanship W_ABOVE (10); condition 100; monetary cost 18,385 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some snake-rattle gloves”; keywords `gloves rattle snake`.
- **Prototype source:** [areas/obj/fishermans_wharf.obj](../../areas/obj/fishermans_wharf.obj#L286).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Razhl, the three-headed hydra serpent [88900], NPC L51; [reset](../../areas/zon/fishermans_wharf.zon#L137).
- **Authored description (gloves rattle snake):** The skin from these gloves came from a powerful serpent.

<a id="vnum-135423"></a>

### 135423 — some mauve-skinned fingerless gloves of an illithidlich — ivalue 159

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 20; +5 CON_MAX; +5 POW_MAX.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material FLESH; craftsmanship S_ABOVE (8); condition 100; monetary cost 4,600,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some mauve-skinned fingerless gloves of an illithidlich”; keywords `gloves`.
- **Prototype source:** [areas/obj/eternal.obj](../../areas/obj/eternal.obj#L380).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Oothoous, the Alhoon [135415], NPC L56; [reset](../../areas/zon/eternal.zon#L357).
- **Authored description (gloves):** These gloves are made from the mauve skin of an mindflayer who has been skinned alive. These gloves represent a prize among illithid outcasts whom have taken up sorcerery instead of psionics.

<a id="vnum-55404"></a>

### 55404 — a pair of fingerless silk gloves — ivalue 166

- **Review role:** Defense/entry.
- **Fit / caution:** Cyan silk upgrade via Seyb: 55401 + 55402 + 50 platinum. +max AGI; separate vnum from green and wisdom variants.
- **Stats:** armor 0; +20 HP; +5 AGI_MAX; PROTECT_EVIL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN (loaded from zero-armor ARMOR); material PAPER; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of fingerless silk gloves”; keywords `pair fingerless silk gloves`.
- **Prototype source:** [areas/obj/wh.obj](../../areas/obj/wh.obj#L4800).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Seyb [55121], NPC L46; [reward and recipe](../../areas/qst/wh.qst#L1981).
- **Acquisition:** Quest inputs: 50,000 quest currency units; a pair of fingerless leather gloves [55401]; a thread of really pretty silk [55402].
- **Acquisition:** Quest rewards: a pair of fingerless silk gloves [55404].

<a id="vnum-55405"></a>

### 55405 — a pair of fingerless silk gloves — ivalue 166

- **Review role:** Defense/entry.
- **Fit / caution:** Green silk upgrade via Seyb: 55401 + 55403 + 50 platinum. +max DEX; separate vnum from cyan and wisdom variants.
- **Stats:** armor 0; +20 HP; +5 DEX_MAX; PROTECT_EVIL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** WORN (loaded from zero-armor ARMOR); material PAPER; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of fingerless silk gloves”; keywords `pair fingerless silk gloves`.
- **Prototype source:** [areas/obj/wh.obj](../../areas/obj/wh.obj#L4812).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Seyb [55121], NPC L46; [reward and recipe](../../areas/qst/wh.qst#L1987).
- **Acquisition:** Quest inputs: 50,000 quest currency units; a pair of fingerless leather gloves [55401]; a thread of really pretty silk [55403].
- **Acquisition:** Quest rewards: a pair of fingerless silk gloves [55405].

<a id="vnum-77529"></a>

### 77529 — some webspinner claws — ivalue 174

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 12; +4 HITROLL; -3 SAVING_PARA; SLOW_POISON; PROT_ACID.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material NONSUBSTANTIAL; craftsmanship W_ABOVE (10); condition 100; monetary cost 22,220 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some webspinner claws”; keywords `webspinner spinning spinner claws`.
- **Prototype source:** [areas/obj/airshipgrave.obj](../../areas/obj/airshipgrave.obj#L413).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the collector [77549], NPC L56; [reset](../../areas/zon/airshipgrave.zon#L306).
- **Authored description (webspinner spinning spinner claws):** These appear to be the claws of some massive arachnid. Venom drips from tiny holes at the tip of each claw, and by the wrist their is a gro- tesque gaping hole that seems to be layered in thick webbing.

<a id="vnum-139038"></a>

### 139038 — gloves of sapphire-encrusted brass — ivalue 175

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 9; +4 DAMROLL; +10 HP; SENSE_LIFE.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material BRASS; craftsmanship MASTER (14); condition 100; monetary cost 100,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOLOCATE. **Extra2 flags:** ITEM2_BLESS, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “gloves of sapphire-encrusted brass”; keywords `gloves brass sapphire`.
- **Prototype source:** [areas/obj/brass.obj](../../areas/obj/brass.obj#L504).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the efreeti padashaw Ornon Kasoon [139000], NPC L60; [reset](../../areas/zon/brass.zon#L1024).
- **Authored description (gloves brass sapphire):** These spectacular gloves sparkle with brilliance from within.

<a id="vnum-32623"></a>

### 32623 — some gloves of rage — ivalue 179

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Melee class allow-list includes Monk; zero weight and permanent haste.
- **Stats:** armor 10; +4 HITROLL; HASTE.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 5,731 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, PALADIN, ANTIPALADIN, MONK, ROGUE, MERCENARY, BARD, BERSERKER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some gloves of rage”; keywords `gloves rage`.
- **Prototype source:** [areas/obj/eth2.obj](../../areas/obj/eth2.obj#L291).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Room reset: target [32707]; [reset](../../areas/zon/eth2.zon#L137).

<a id="vnum-28960"></a>

### 28960 — the gauntlets of the war giant Torg — ivalue 187

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Melee class allow-list includes Monk; 2 pounds and balanced hit/dam.
- **Stats:** armor 12; +2 HITROLL; +2 DAMROLL; DETECT_INVISIBLE.
- **Weight:** 2 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 20.
- **Template:** ARMOR; material OBSIDIAN; craftsmanship ONE_KIND (15); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, MONK, MERCENARY, ALCHEMIST, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES, ITEM_NOSLEEP, ITEM_NOCHARM, ITEM_HUM. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gauntlets of the war giant Torg”; keywords `war gauntlets torg`.
- **Prototype source:** [areas/obj/torg.obj](../../areas/obj/torg.obj#L916).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Torg [28963], NPC L60; [reset](../../areas/zon/torg.zon#L773).
- **Authored description (war gauntlets torg):** These gauntlets bear the power of the war giant Torg. His power imbued here makes them literally tingle to the touch.

<a id="vnum-120037"></a>

### 120037 — some spectral gauntlets of the battleragers — ivalue 191

- **Review role:** Focus: class allow-list.
- **Fit / caution:** Melee class allow-list includes Monk; zero weight, max STR, damage, haste.
- **Stats:** armor 4; +3 STR_MAX; +3 DAMROLL; HASTE.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material NONSUBSTANTIAL; craftsmanship ONE_KIND (15); condition 100; monetary cost 6,555 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, MONK, MERCENARY, BARD, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES, ITEM_HUM. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spectral gauntlets of the battleragers”; keywords `spectral gauntlets battleragers _noquest_`.
- **Prototype source:** [areas/obj/surfacekeeps.obj](../../areas/obj/surfacekeeps.obj#L588).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: the spirit of Brigy Stonehammer [120056], NPC L60; [reset](../../areas/zon/surfacekeeps.zon#L285).
- **Authored description (spectral gauntlets battleragers):** These strange magical gauntlets exist. ..and then suddenly they do not.

<a id="vnum-139152"></a>

### 139152 — some gauntlets of cooled magma — ivalue 194

- **Review role:** Conditional.
- **Fit / caution:** BLOCKED BY RACE MASK: ITEM_ALLOWED_RACES is set, but allowed-races mask is zero. Ordinary player monks cannot equip this despite class permission. Requires content correction before considering a monk proc; Illithid/Mindflayer bypass is a separate exception.
- **Stats:** armor 12; +9 STR; +4 DAMROLL; PROT_FIRE.
- **Weight:** 3 lb; half-weight attack contribution 1; default per-item equip gate STR ≥ 30.
- **Template:** ARMOR; material GRANITE; craftsmanship V_SKILLED (13); condition 100; monetary cost 657,000 (not ivalue).
- **Magic / usability:** MAGIC yes; Deny classes: WARRIOR, RANGER, PALADIN, ANTIPALADIN, ROGUE, MERCENARY, BERSERKER, DREADLORD, AVENGER; Allow races: NONE (blocks ordinary wearers).
- **Extra flags:** ITEM_GLOW, ITEM_ALLOWED_RACES. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some gauntlets of cooled magma”; keywords `gauntlets magma`.
- **Prototype source:** [areas/obj/brass.obj](../../areas/obj/brass.obj#L2370).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: an efreeti armorer [139121], NPC L55; [reset](../../areas/zon/brass.zon#L525).

<a id="vnum-98945"></a>

### 98945 — some spiked zanthium gloves — ivalue 204

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 12; +4 HITROLL; +3 DAMROLL; PROT_LIGHTNING.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material DRAGONSCALE; craftsmanship ONE_KIND (15); condition 100; monetary cost 55,000 (not ivalue).
- **Magic / usability:** MAGIC yes; Deny classes: PSIONICIST, CLERIC, DRUID, SHAMAN, SORCERER, NECROMANCER, CONJURER, WARLOCK, MINDFLAYER, ILLUSIONIST, ETHERMANCER, THEURGIST, SUMMONER, DRAGOON.
- **Extra flags:** ITEM_FLOAT. **Extra2 flags:** ITEM2_BLESS, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS, ITEM_HOLD. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some spiked zanthium gloves”; keywords `spiked zanthium gloves`.
- **Prototype source:** [areas/obj/tezcat.obj](../../areas/obj/tezcat.obj#L803).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: Bard Faust, The Lord of Darkness [98959], NPC L60; [reset](../../areas/zon/tezcat.zon#L235).
- **Authored description (gloves spiked zanthium):** This gloves seems to be made out of a strong reddish metal. It's very thick yet surpisingly it is also rather flexible. You have never seen or touched anything quite like it before.

<a id="vnum-5523"></a>

### 5523 — magical gloves of slayer's accuracy — ivalue 212

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 10; +10 DEX; +4 HITROLL; HAWKVISION.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material LEATHER; craftsmanship EXCELLENT (11); condition 100; monetary cost 29,292 (not ivalue).
- **Magic / usability:** MAGIC yes; Deny classes: PSIONICIST, CLERIC, DRUID, SHAMAN, SORCERER, NECROMANCER, CONJURER, WARLOCK, ALCHEMIST, ILLUSIONIST, ETHERMANCER, THEURGIST.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “magical gloves of slayer's accuracy”; keywords `gloves slayers accuracy _noquest_`.
- **Prototype source:** [areas/obj/tharnadian_ruin.obj](../../areas/obj/tharnadian_ruin.obj#L333).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a drow master assassin [5523], NPC L51; [reset](../../areas/zon/tharnadian_ruin.zon#L289).
- **Authored description (gloves slayers accuracy):** These leather gloves are of master artisan quality, but there is far more to them than fine stiching. A tremendous power has been enchanted upon these gloves. The wearer is granted incredible powers of dexterity and accuracy. Yes, a slayer's dream come true.

<a id="vnum-5817"></a>

### 5817 — some razor-knuckled blood crystal gloves — ivalue 216

- **Review role:** Focus: identity/punching.
- **Fit / caution:** Both standard and enhanceable Chaos monk kits; also Illusionist kits. Thrulmar reward: 5813 + 5 x 500025 + 400 platinum. MAGIC. Replaces -10 weight gloves with +4.
- **Stats:** armor 20; +15 HP; +4 DAMROLL; PROTECT_EVIL; DETECT_EVIL.
- **Weight:** 4 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 40.
- **Template:** ARMOR; material GEM; craftsmanship MASTER (14); condition 100; monetary cost 289,434 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** none. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “some razor-knuckled blood crystal gloves”; keywords `razor knuckled blood crystal gloves`.
- **Prototype source:** [areas/obj/minizones.obj](../../areas/obj/minizones.obj#L1571).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Thrulmar the undead minotaur [5813], NPC L56; [reward and recipe](../../areas/qst/minizones.qst#L169).
- **Acquisition:** Quest inputs: a pair of ghostly gloves [5813]; 5 × a huge blood crystal [500025]; 400,000 quest currency units.
- **Acquisition:** Quest rewards: some razor-knuckled blood crystal gloves [5817].

<a id="vnum-44451"></a>

### 44451 — the gloves of shadows — ivalue 237

- **Review role:** Light offense.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 15; +5 HITROLL; +40 MV.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_HUM. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gloves of shadows”; keywords `gloves shadows`.
- **Prototype source:** [areas/obj/githzer.obj](../../areas/obj/githzer.obj#L942).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: a shadow mephit [44440], NPC L47; [reset](../../areas/zon/githzer.zon#L678).
- **Authored description (gloves shadows):** These gloves totally conceal the hands and forearms of the wearer as they enshroud the wearer with total shadow.

<a id="vnum-23806"></a>

### 23806 — a pair of gauntlets formed of dust — ivalue 244

- **Review role:** Benchmark.
- **Fit / caution:** Native earthquake_gauntlet: worn main-hand-slot periodic combat earthquake, 1/10 check, spell level 50. Already procs.
- **Stats:** armor 10; +6 STR_MAX; +3 DAMROLL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material IRON; craftsmanship AVERAGE (7); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** none. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of gauntlets formed of dust”; keywords `dusty gauntlets dust`.
- **Prototype source:** [areas/obj/plane_earth_one.obj](../../areas/obj/plane_earth_one.obj#L72).
- **Existing proc:** `earthquake_gauntlet`; [binding](../../src/specs/specs.assign.c#L1155), [callback](../../src/specs/specs.object.c#L7647). Raw native proc credit **65**, before itemvalue multipliers.
- **Proc behavior:** Periodic combat proc while worn in WEAR_HANDS: 1-in-10 check casts level-50 earthquake. It specifically checks the main glove slot.
- **Acquisition:** Drop/carried equipment: Ogremoch Prince of the Elemental Plane of Earth [23806], NPC L61; [reset](../../areas/zon/plane_earth_one.zon#L61).

<a id="vnum-96074"></a>

### 96074 — the holy gauntlets of the planetar — ivalue 265

- **Review role:** Defense/entry.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 15; +5 HITROLL; -4 SAVING_SPELL; AWARE.
- **Weight:** 1 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 10.
- **Template:** ARMOR; material STEEL; craftsmanship AVERAGE (7); condition 100; monetary cost 23,049 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOSUMMON, ITEM_LIT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the holy gauntlets of the planetar”; keywords `holy gauntlets planetar`.
- **Prototype source:** [areas/obj/jotun.obj](../../areas/obj/jotun.obj#L1213).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: the planetar Quelranor [96077], NPC L59; [reward and recipe](../../areas/qst/jotun.qst#L430).
- **Acquisition:** Quest inputs: a jagged lightning sword [96038].
- **Acquisition:** Quest rewards: the holy gauntlets of the planetar [96074]; 175,000 experience.
- **Authored description (holy gauntlets planetar):** These slightly green metallic gauntlets seem to sparkle with a divine presence. A faint nimbus of light surrounds the gauntlets, attesting to their sacred nature.

<a id="vnum-131636"></a>

### 131636 — the legendary silverish gauntlets of Gith's Blessing — ivalue 325

- **Review role:** Defense/entry.
- **Fit / caution:** ITEM_ALLOWED_RACES restricts this to Githyanki and Githzerai. Quest reward; strong zero-weight melee option where race allowed.
- **Stats:** armor 15; +4 HITROLL; +4 DAMROLL; SPIRIT_WARD, TOWER_IRON_WILL.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material SILVER; craftsmanship ONE_KIND (15); condition 100; monetary cost 456,544 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes; Allow races: GITHYANKI, GITHZERAI.
- **Extra flags:** ITEM_NOREPAIR, ITEM_ALLOWED_RACES, ITEM_NOLOCATE, ITEM_NOSUMMON. **Extra2 flags:** ITEM2_SILVER, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the legendary silverish gauntlets of Gith's Blessing”; keywords `legendary silverish gith's blessingsilvery gauntlets`.
- **Prototype source:** [areas/obj/airp.obj](../../areas/obj/airp.obj#L410).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: Darthikya, the Githyanki Hunter [131621], NPC L45; [reward and recipe](../../areas/qst/airp.qst#L167).
- **Acquisition:** Quest inputs: the heart of ixteal [131615].
- **Acquisition:** Quest rewards: the legendary silverish gauntlets of Gith's Blessing [131636].

<a id="vnum-23808"></a>

### 23808 — a pair of stone gauntlets — ivalue 326

- **Review role:** Benchmark.
- **Fit / caution:** Native artifact_stone already assigned. Zero weight +6 STR, stone skin and acid protection.
- **Stats:** armor 10; +6 STR; STONE_SKIN; PROT_ACID.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material DIAMOND; craftsmanship MASTER (14); condition 100; monetary cost 90,000 (not ivalue).
- **Magic / usability:** MAGIC no; All classes.
- **Extra flags:** ITEM_GLOW, ITEM_NOIDENTIFY. **Extra2 flags:** none.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of stone gauntlets”; keywords `stone gauntlets _noquest_`.
- **Prototype source:** [areas/obj/plane_earth_one.obj](../../areas/obj/plane_earth_one.obj#L96).
- **Existing proc:** `artifact_stone`; [binding](../../src/specs/specs.assign.c#L1152), [callback](../../src/specs/specs.object.c#L456). Raw native proc credit **125**, before itemvalue multipliers.
- **Proc behavior:** Worn periodic proc uses periodic_stoneskin at spell level 30 and timer.stoneskin.generic (checked-in value 60 seconds); helper and wearer/state checks still apply.
- **Acquisition:** Drop/carried equipment: Entemoch Prince of the Elemental Plane of Earth [23808], NPC L61; [reset](../../areas/zon/plane_earth_one.zon#L79).
- **Authored description (stone gauntlets):** Thse stone gauntlets give off an aura of great power.

<a id="vnum-83628"></a>

### 83628 — the claws of the Legendary Tarrasque — ivalue 360

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 30; +4 HITROLL; +4 DAMROLL; HASTE.
- **Weight:** 4 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 40.
- **Template:** ARMOR; material DRAGONSCALE; craftsmanship MASTER (14); condition 100; monetary cost 111,400 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_SECRET, ITEM_FLOAT, ITEM_NOSLEEP. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_FEET, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the claws of the Legendary Tarrasque”; keywords `claws legendary tarrasque _noquest_`.
- **Prototype source:** [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj#L9223).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Drop/carried equipment: The Legendary Tarrasque [7365], NPC L60; [reset](../../areas/zon/alatorin.zon#L4488).
- **Authored description (claws legendary tarrasque):** These claws are massive, curved scythes of ivory-white bone. Incredibly sharp, they feel thick enough to shear through solid granite. They vibrate with a low, predatory hum, rattling with a primordial magic that allows them to bypass even the most potent physical and arcane defenses.

<a id="vnum-88320"></a>

### 88320 — a pair of vampiric dragonscale gauntlets — ivalue 389

- **Review role:** Heavier/sustain.
- **Fit / caution:** Shared gear selected for low weight and useful physical or defensive stats; this is a stats-based alternative, not explicit monk-only equipment.
- **Stats:** armor 6; +15 HP_REGEN; +3 DEX_MAX; PROT_FIRE; PROT_COLD, PROT_LIGHTNING, PROT_GAS, PROT_ACID, VAMPIRIC_TOUCH; SPIRIT_WARD.
- **Weight:** 4 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 40.
- **Template:** ARMOR; material DRAGONSCALE; craftsmanship ONE_KIND (15); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: WARRIOR, RANGER, PSIONICIST, PALADIN, ANTIPALADIN, CLERIC, MONK, DRUID, SHAMAN, ROGUE, ASSASSIN, MERCENARY, THIEF, BERSERKER, REAVER, DREADLORD, AVENGER.
- **Extra flags:** ITEM_ALLOWED_CLASSES. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “a pair of vampiric dragonscale gauntlets”; keywords `gauntlets hellfire vampiric _noquest_`.
- **Prototype source:** [areas/obj/firep.obj](../../areas/obj/firep.obj#L233).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** Quest: the man-god, Hephaestus [88318], NPC L62; [reward and recipe](../../areas/qst/firep.qst#L50).
- **Acquisition:** Quest inputs: a magnificent pile of black and red dragonscales [88322]; a pair of battered and worn gauntlets [88323].
- **Acquisition:** Quest rewards: a pair of vampiric dragonscale gauntlets [88320]; the broken rays of morning Sunrise [55270].

<a id="vnum-131649"></a>

### 131649 — Tempest, the swirling gauntlets of storms — ivalue 484

- **Review role:** Defense/entry.
- **Fit / caution:** Excellent zero-weight defensive stats; no normal reset/shop/quest reward located. Chaos Theurgist kit contains it; availability needs follow-up.
- **Stats:** armor 25; -4 SAVING_SPELL; +5 CON_MAX; DETECT_INVISIBLE, HASTE, FLY; PROT_COLD, PROT_LIGHTNING.
- **Weight:** 0 lb; half-weight attack contribution 0; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material NONSUBSTANTIAL; craftsmanship ONE_KIND (15); condition 100; monetary cost 250,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOREPAIR. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “Tempest, the swirling gauntlets of storms”; keywords `gauntlets tempest storms`.
- **Prototype source:** [areas/obj/airp.obj](../../areas/obj/airp.obj#L584).
- **Existing proc:** no native assignment or embedded _proclib_ description found; raw native proc credit 0. Permanent affects above are static benefits, not a missing proc.
- **Acquisition:** No direct AREA-selected reset, shop stock, or quest reward located; prototype presence alone does not establish ordinary availability.

<a id="vnum-77734"></a>

### 77734 — the sacred stone claws of Aan — ivalue 563

- **Review role:** Benchmark.
- **Fit / caution:** Native artifact_stone already assigned. Strong existing defensive stats/proc; 5 pounds.
- **Stats:** armor 6; -50 AC; +50 HP; STONE_SKIN.
- **Weight:** 5 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 50.
- **Template:** ARMOR; material STONE; craftsmanship AVERAGE (7); condition 100; monetary cost 20,000 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_NOIDENTIFY. **Extra2 flags:** ITEM2_BLESS, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the sacred stone claws of Aan”; keywords `aan sacred stone claws`.
- **Prototype source:** [areas/obj/hall.obj](../../areas/obj/hall.obj#L585).
- **Existing proc:** `artifact_stone`; [binding](../../src/specs/specs.assign.c#L1447), [callback](../../src/specs/specs.object.c#L456). Raw native proc credit **125**, before itemvalue multipliers.
- **Proc behavior:** Worn periodic proc uses periodic_stoneskin at spell level 30 and timer.stoneskin.generic (checked-in value 60 seconds); helper and wearer/state checks still apply.
- **Acquisition:** Drop/carried equipment: Aan, the dragonlord of the Sacred Hells [77734], NPC L62; [reset](../../areas/zon/hall.zon#L461).
- **Authored description (claws giant sacred):** Made of rugged stone, these claws are a reproduction of the legendary claws of the god Aan. It is rumored that they could shred mountains and tear pieces away from the sun. Carved from rough stone, they look quite fierce indeed. The way they are made, the wearer's hands slip into the center of the dragon shaped wrists, and the stone shaped clams protrude from the wristbrace and come about the hands- quite impressively crafted.

<a id="vnum-55280"></a>

### 55280 — the gauntlets of a Living Legend — ivalue 615

- **Review role:** Benchmark.
- **Fit / caution:** Native gauntlets_legend already assigned: combat periodic heal/damage effects; activation branches also exist. Quest reward.
- **Stats:** armor 0; +30 HP; -30 AC; HASTE, SNEAK.
- **Weight:** 4 lb; half-weight attack contribution 2; default per-item equip gate STR ≥ 40.
- **Template:** WORN (loaded from zero-armor ARMOR); material MITHRIL; craftsmanship ONE_KIND (15); condition 100; monetary cost 0 (not ivalue).
- **Magic / usability:** MAGIC yes; All classes.
- **Extra flags:** ITEM_GLOW, ITEM_NOSELL, ITEM_NOREPAIR, ITEM_FLOAT. **Extra2 flags:** ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “the gauntlets of a Living Legend”; keywords `gauntlets living legend _noquest_`.
- **Prototype source:** [areas/obj/wh.obj](../../areas/obj/wh.obj#L3503).
- **Existing proc:** `gauntlets_legend`; [binding](../../src/specs/specs.assign.c#L1838), [callback](../../src/specs/specs.winterhaven.c#L2558). Raw native proc credit **235**, before itemvalue multipliers.
- **Proc behavior:** Worn combat periodic check has a 1-in-10 effect: heals the wearer for 1/8 max HP when below 1/4, or 1/12 when below 1/2; can remove 1/25 or 1/15 of the opponent's max HP within its coded health bands. Also supplies level-60 stone skin on a 180-second timer while hurt and without a skin, outside no-magic rooms; out-of-combat clap hands invokes level-50 nonexistence on a 600-second timer.
- **Acquisition:** Quest: Sootfoot [55103], NPC L46; [reward and recipe](../../areas/qst/wh.qst#L1119).
- **Acquisition:** Quest inputs: a pair of magical bronze gauntlets [55162]; the gnomish orb of binding [55209]; a strange glowing flint of armor [55284]; the story of a Living Legend [55279].
- **Acquisition:** Quest rewards: the gauntlets of a Living Legend [55280].
- **Acquisition:** Quest: Navift [74254], NPC L55; [reward and recipe](../../areas/qst/bs.qst#L919).
- **Acquisition:** Quest inputs: a pair of magical bronze gauntlets [55162]; the gnomish orb of binding [55209]; a strange glowing flint of armor [55284]; the story of a Living Legend [55279].
- **Acquisition:** Quest rewards: the gauntlets of a Living Legend [55280].

<a id="vnum-1210"></a>

### 1210 — tendrils of shadowy mist — ivalue 1519

- **Review role:** Benchmark.
- **Fit / caution:** Only hand-slot prototype with exact Monk-only class allow-mask. ARTIFACT; -10 weight, +5 damage, -1 combat pulse. Native tendrils defensive proc already assigned; rare secondary burst does stone skin, 2-round stun and 10d45 damage. Benchmark, not missing-proc starter.
- **Stats:** armor 15; -1 COMBAT_PULSE; +5 DAMROLL; HASTE; GLOBE, VAMPIRIC_TOUCH.
- **Weight:** -10 lb; half-weight attack contribution -5; default per-item equip gate STR ≥ 0.
- **Template:** ARMOR; material NONSUBSTANTIAL; craftsmanship ONE_KIND (15); condition 100; monetary cost 500,000 (not ivalue).
- **Magic / usability:** MAGIC yes; Allow classes: MONK.
- **Extra flags:** ITEM_GLOW, ITEM_NOSELL, ITEM_ALLOWED_CLASSES, ITEM_FLOAT, ITEM_ARTIFACT. **Extra2 flags:** ITEM2_SILVER, ITEM2_MAGIC.
- **Stored wear flags:** ITEM_TAKE, ITEM_WEAR_HANDS. All entries admit the hand category; actual anatomy and normal wear checks still apply.
- **Names:** template “tendrils of shadowy mist”; keywords `tendrils shadowy mist`.
- **Prototype source:** [areas/obj/heavens.obj](../../areas/obj/heavens.obj#L9369).
- **Existing proc:** `tendrils`; [binding](../../src/specs/specs.assign.c#L1140), [callback](../../src/specs/specs.underworld.c#L3926). Raw native proc credit **205**, before itemvalue multipliers.
- **Proc behavior:** Incoming-melee defensive callback. An outer 1-in-8 check emits the sidestep/elbow message; a nested 1-in-8 check casts level-60 stone skin on the wearer, stuns the attacker for two violence pulses and deals 10d45 damage. The nested burst is 1 in 64 eligible callbacks. The standalone elbow damage is commented out, and the callback returns false rather than cancelling the incoming hit.
- **Acquisition:** Room reset: target [6801]; [reset](../../areas/zon/dragonnia.zon#L94).
- **Authored description (tendrils shadowy mist):** Wisps of streaming darkness swirl and interwine with the light, creating the impression that these gloves, if they can truly be called that, are phantasms out of your worst nightmares come true.

## Verification and limits

- The original 314 hand-slot source records matched the assembled areas/world.obj byte-for-byte at the initial sweep. The 105 entries in this document were separately revalidated unchanged at the valuation baseline above.
- Native valuation ran successfully for all 105 unique vnums with undefined-behavior and float-cast-overflow sanitizers. Native proc credits were included for every assigned benchmark and the conditional fumblegaunts item.
- Checked that the catalog and detail sections each contain exactly the same 105 unique vnums and are sorted by (ivalue, vnum). All linked local source files exist.
- No game code, item definitions, procs, accounts, characters, database records or running server state were changed. No production gameplay or acquisition journey was run.
- This inventory records candidates and known drawbacks. It does not establish that every broader alternative needs a proc, that all sources are obtainable by every monk race/side, or that ivalue alone measures monk combat strength.
