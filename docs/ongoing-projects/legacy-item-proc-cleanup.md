# Legacy weapon and gear proc cleanup

Research date: 2026-11-07. Source baseline: `896ff7b28`. Status: every delivery step is implemented as a stacked PR awaiting review and merge; see the progress log below.

## Progress log

Keep this table current; a new session should be able to resume from it alone. PRs are stacked: each branch is based on the one above it, so merge them in order.

| Step | Branch | PR | State |
| --- | --- | --- | --- |
| Plan | `docs/legacy-item-proc-cleanup-plan` | #773 | Ready for review |
| 1. Dead code | `proc-cleanup/dead-code` | #774 | Ready for review |
| 2. `CheckMultiProcTiming` removal and `lightning_sword` activation | `proc-cleanup/multiproc-timing` | #775 | Ready for review |
| 3a. Pilot: event guards (`melee_proc_target`, `defense_proc_data`) in `specs.object.c` and `specs.underworld.c` | `proc-cleanup/pilot-helpers` | #776 | Ready for review |
| 3b. Pilot: `act_trio` in the same two files | `proc-cleanup/pilot-act-trio` | #779 | Ready for review |
| 3c. Pilot: `periodic_stoneskin` and the cloak/ioun deflection merge | `proc-cleanup/pilot-stoneskin-deflect` | #780 | Ready for review |
| 3d. Owner review of the converted pilot files | — | — | Requested on #776/#779/#780; the sweep proceeds as stacked PRs, so review can happen alongside |
| 4a. Sweep A: `specs.winterhaven.c`, `specs.vecna.c`, `specs.zion.c` | `proc-cleanup/sweep-a` (on #777) | #783 | Ready for review |
| 4b/4c. Sweep B: `specs.undermountain.c`, `specs.jot.c`, the eleven small files, and the leftover `OBJ_WORN_BY` spellings | `proc-cleanup/sweep-b` (on #783) | #784 | Ready for review |

With 4b merged, every item-proc spec file is on the shared helpers. The plan's delivery sequence is then complete; what remains is review and merging.
| 5. Payload parsing defects | `proc-cleanup/payload-parsing` (on 3a) | #777 | Ready for review |
| 6a. Set execution moved to `specs.set.c` | `proc-cleanup/set-move` (on 3c) | #781 | Ready for review |
| 6b. `weapon_proc` packed spells | `proc-cleanup/weapon-proc` (on the plan PR) | #778 | Ready for review |
| Tracing note: event payloads beside the pseudo-command constants | `proc-cleanup/event-notes` (on the plan PR) | #782 | Ready for review |

Merge order: #773 → #774 → #775 → #776 → #779 → #780 → #781 → #777 → #783 → #784; #778 and #782 after #773. Retarget each PR's base to `master` as the one below it merges.

Decisions made while working:

- **`random_eq_proc` stays.** It is unbound, but its comment says it is kept until it is attached on purpose, and its removal would reach `selected_random_weapon_action()` and the `itemActions.randomWeapons` settings, which this project leaves alone. `test_weapon_actions_runtime.py` calls it directly.
- **`floating_pool` and `skill_beacon` had definitions** (the research listed them as prototype-only). Neither is assigned anywhere, so their definitions were deleted as unbound callbacks.
- **`lightning_sword` activation** is its own commit. When the bolt kills a no-corpse victim, the proc falls through to a `TO_CHAR` `act` that is passed the dead victim, but the message has no victim token and `TO_CHAR` never dereferences it, so it stays as is. Its player news belongs to the next `news-update` run after merge.
- **Pilot split.** The pilot ships as stacked PRs, one helper family each (3a–3c), so each can be reviewed alone. The sweep (step 4) waits for the owner's review of the pilot files.
- **Event guards (3a).** 76 callbacks use the helpers: 54 in `specs.object.c` and 22 in `specs.underworld.c`. Left on their old guards on purpose: `artifact_biofeedback` (periodic and melee share one victimless body), `good_evil_sword` (the actor is `obj->loc.wearing` and the melee path reads no victim), `vapor` (its `CMD_GOTHIT` branch also acts when the item is only carried), `vareena_statue` (`cmd / 1000` there filters room objects, not melee), and `elvenkind_cloak`/`deflect_ioun` (merged in 3c). `doombringer` now targets the hit's victim instead of `GET_OPPONENT`; they differ only after a grapple misfire, where the proc now strikes the character actually hit. `circlet_of_light` and other non-weapon gear that "handle" melee hits never receive them: only `weapon_proc` and backstab send `CMD_MELEE_HIT`, always to the wielded weapon. `circlet_of_light`'s branch (whose roll reads as 14 in 15) is therefore dead either way.
- **`act_trio` (3b)** merged 107 consecutive `TO_CHAR`/`TO_VICT`/`TO_NOTVICT` trios with the same hide flag, actor, object, and victim. They were found by a statement-level script (`act(` statements on their own lines, adjacent, six arguments, no `ACT_*` flags), so trios with flags, a null victim, or something between the calls stay as plain `act`. When all three texts are identical, the literal is hoisted to a named local (`kvasir_dagger`, `bloodfeast`, `sunblade`, `mankiller`). When two of them match (22 cases), the literal is simply passed twice, as before. Tests that compile a converted callback must also extract `void act_trio(` from `comm.c`.
- **`periodic_stoneskin` (3c)** takes the wearer as a parameter (`bool periodic_stoneskin(P_obj obj, P_char ch, int level, int interval)`), because each item finds its wearer differently. It has seven callers, not nine: the `bloodfeast` block and the second shadow-globe block were in the deleted `THARKUN_ARTIS` halves. `dragonlord_plate` stays explicit, because it tests `affected_by_spell(SPELL_STONE_SKIN)` rather than `has_skin_spell`, which is a different rule.
- **Deflection (3c)** is the static `deflect_spell()` in `specs.underworld.c`. Both callbacks now use `defense_proc_data`; the ioun keeps its native route first.
- **Payload defects (5).** `proc_whirlwinds` was not a defect: `cmd == CMD_TAP &&` short-circuits before it parses. `rapier_penetration` has the same `ParseTarget` shape, but nothing binds it (its assignment is commented out), so it belongs to the winterhaven sweep, most likely as a deletion. `test_item_proc_payloads.py` fails with an ASan heap-buffer-overflow before the fix.
- **`weapon_proc` (6b)** keeps the legacy sparse-slot count quirk and the reverse cast order, both pinned by `packed_parity()`. Making sparse slots "work" would turn on spells that never fired.
- **Set move (6a).** The moved helpers stay non-static: five test harnesses extract and stub `random_set`, `apply_zone_spell`, and `check_zone_spells` by their current signatures. `test_world_quest_target_retries.py` used to compile `specs.set.c` whole for `master_set`; it now extracts `master_set` and its tables, like the rest of the set code. The named-set wear journey needs the prepared `bin/tests/named-set-roster-world` runtime, which does not exist on this machine. The move was proved with the full build, the four `test_named_set_*` tests, and `test_flatfile_full_world_boot.py`.
- **Stale journeys.** `toggle boon` now replies "Divine Boons apply automatically…", so `run_weapon_actions_journey.py`, `run_device_actions_journey.py`, and `run_falling_skills_journey.py` timed out at setup. #778 fixes the expected line. Until it merges, apply that one-line change locally before running those journeys on another branch.
- **Pilot real-server results.** On a flatfile build of 3a + 3b, `mace_of_sea` fired 7 times in 229 weapon hits, and the Avernus journey (`--family avernus --case off-hold`) passed.
- **Stack shape.** #777 was rebased onto #781 so that the winterhaven sweep stacks on it and the chain stays linear.
- **Sweep A (4a).** 21 procs moved to the guards, and 52 `act` trios became `act_trio`. `rapier_penetration` was deleted (unbound; its prototype lived in `specs.winterhaven.h`). Left on their old guards: `vecna_krindor_main`'s `CMD_GOTHIT` branch and `krindor_illusionist` (their actor is the owner from `loc.carrying`/`loc.wearing`, and they run when the item is only carried). `CMD_SAY`/`CMD_PRAY` `ParseTarget` calls are text and stay. `vecna_dispel` and `vecna_boneaxe` used to target `GET_OPPONENT` without checking it, and now need the hit's living victim. `test_item_proc_payloads.py` extracts `act_trio` now that `deathseeker_mace` uses it.
- **Dead periodic procs revived (4a review).** Periodic events pass `ch == NULL`, so a liveness test ahead of a `CMD_PERIODIC` branch kills it. `gauntlets_legend` (3-minute stoneskin, now only without a skin, and a 1-in-10 combat proc), `buckler_saints` (3-minute heal), `deathseeker_mace` and `illithid_axe` (50% per tick cure critic or invigorate; the axe also returned FALSE on `CMD_SET_PERIODIC`), `demon_slayer` (75 HP drain on undead wearers, now floored at 1 HP because nothing calls `die()` there), and `vecna_stonemist` (room mist stripping stoneskin) now use the wearer, or no actor, on periodic ticks. This is a gameplay change made as a bug fix; it is its own commit and belongs in player news. Grep other spec files for the same shape during their sweeps.
- **Other 4a review fixes.** `deathseeker_mace` and `illithid_axe` parse only say commands (they ran `half_chop` over binary payloads). `volo_longsword`, `bel_sword` and koztk's say-procs return when `ParseTarget` yields no target (an opponent on another z level stops the fight and returns NULL). `vecna_deathaltar` fires only on touch and checks `IS_NPC`. Three message typos were fixed. `zion_shield_absorb_proc` still tests the wearer's blindness before blinding the attacker; that may be the intended rule, so it was left.
- **Sweep B (4b/4c).** 31 procs moved to the guards, and 16 `act` trios became `act_trio`. Four unbound callbacks were deleted with their commented assignments, prototypes, and dead `tradeskill.c` identity checks: `betrayal`, `monitor_trident`, `frost_elb_dagger`, and `gesen` (whose guard `cmd == CMD_MELEE_HIT ||` was inverted). The commented-out `dagger_of_wind` copy in `specs.lohrr.c` went too. `iron_flindbar` had no event test and reinterpreted the `CMD_GOTHIT` `proc_data` its wielded weapon receives as a character, which is the #777 defect class; it now acts only on melee hits. `elfdawn_sword` stays as it is (its melee test only chooses the return value). Text-command `act` calls that passed the payload as an unused victim now pass 0. `specs.eth2.c` and `specs.lohrr.c` include `world/specs.prototypes.h`. In 4c, three `!OBJ_WORN(obj) || obj->loc.wearing != ch` spellings in `specs.object.c` became `!OBJ_WORN_BY(obj, ch)`. The remaining `loc.wearing` comparisons sit beside `OBJ_WORN_POS` (a different rule) or are diagnostics.
- **4b review fixes.** The sweep itself was gameplay-identical; a full read of the touched files found pre-existing bugs, all fixed on the same branch in separate commits. Memory safety: `special()` now reads `next_content` before running an object proc, because `huntsman_ward`, `generic_drow_eq` and `obj_imprison` extract their own object (regression in `test_weapon_actions_runtime.py`); `event_mob_proc` stops if the proc extracted the mob; procs that used a victim after `raw_damage`/`melee_damage`/`damage`/`die` killed it (`illesarus`, `hellfire_axe`, `berserker_toss`, `wall_generic`, `sword_whirlwinds`, `orcus_wand`, `varon`) now stop; `good_evil_defenseProc` read past `manaCosts`; `eth2_tree_obj` leaked its tree; `lightning_sword` no longer adds a critical hit after a corpseless kill. Logic slips: a cast-precedence error on `staff_of_blue_flames` lag, an always-false `== !STAT_NORMAL` in the shabo procs, swapped `damage()` arguments in `stat_pool_common`, `good_evil_sword`'s once-per-boot static, `out_of_god_bp`'s vnum/index mix-up, `dragonslayer`'s level cap unequipping, `holy_weapon`'s integer percentage, `living_necroplasm`'s missing `else`, `vigor_mask`'s unreachable remove branch, `treasure_chest` firing on any `open`, the flesh golem's room vnum, target and spawn vnum, and several wrong message audiences. Revived (gameplay change, its own commit): `tripboots`, `blindbadge`, `fumblegaunts`, `dragon_skull_helm`, `alch_bag` (refills only when empty) and the `berserker_toss` mob proc. Message typos were fixed in bound procs only; unbound procs such as `cell_drunk` were left.
- **Named-set journeys** need `bin/tests/named-set-roster-world`, which the main checkout no longer has. To prepare it:
  1. Create `state/` (mode 0700) with an empty `state/domains/` (also 0700), and run `bin/tests/coin-death-inspector <abs state> seed-combat`.
  2. Symlink `areas`, `areas_mini`, and `docs` from the repo, copy `lib/`, and generate `duris.crt`/`duris.key` with `openssl req -x509` (key mode 0600).
  3. Create `logs/log` and `journals/{players,critical}` (0700), and copy the flatfile build to `bin/tests/named-set-flatfile-server`.
  4. Boot it once and create the journey character with `journey.create_character(client, expected_room=None)`, then `save`. The journey fixture reads player 1 before it boots, and it needs an absolute state path.
  
  On that runtime, `run_named_set_wear_journey.py 1325` passes on the stack tip (#784): 5-piece thresholds, save/reboot, and removal.
- **Lightning sword rate check.** Nine 15-minute fights pool to 57 bolts in 1,576 weapon hits (3.6%) against 47.8 expected at 1 in 33, about 1.3 standard deviations; without the first, clustered run (15/165) it is 2.98%. Every bolt immediately follows a counted hit, so there are no uncounted opportunities and no double dispatch. `number(0, 32)` from `random.c` returns 0 at 0.03032 over 10 million draws.
- **Pilot 3c real-server checks.**
  - **Stoneskin:** a staff character in the full-world runtime (above) wore the misty gloves (26666, taken from Vecna with `force vecna give misty <name>`), and stone skin appeared within one periodic tick. World artifacts can't be duplicated with `load obj`, because artifact identity refuses a second copy.
  - **Deflection:** checked with a non-artifact fixture copy of vnum 26665 in the weapon journey's mini world. The sentinel's packed wand-blade casts magic missile at the cloaked player, and 13 of 36 spells were deflected, to both mortal bystanders. A fresh character must `drop all` before `get`, because its starter kit exceeds its carrying limit.
- **Owner review gate (3d).** The goal said not to wait, so the sweep went ahead as stacked, unmerged PRs. The owner's review of the pilot happens on #776/#779/#780, and anything it changes can be applied to the sweep PRs before they merge.
- **#778 journeys.** After the boon-reply fix, `run_weapon_actions_journey.py`, `run_device_actions_journey.py`, and `run_falling_skills_journey.py` all pass.
- **Tests that compile converted callbacks** must extract the helpers too: `test_world_quest_target_retries.py`, `test_word_output_integration.py`, `test_weapon_actions_runtime.py` (`melee_proc_target`), and `test_freedom_of_movement_procs.py` (`defense_proc_data`; its fixture now wears the armor). `test_item_proc_guards.py` covers the helper contracts plus `mace_of_sea` and `generic_parry_proc`.
- **Real-server checks** use a flatfile build (`make -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY=$PWD/bin/server/dms_flatfile`) and the fixture from `run_weapon_actions_journey.py`: rename the Avernus fixture vnum to the item under test (the sentinel wields it against the player) and count the victim message over a long fight. The script used is not committed; it is a few lines around `configure()` and `MudClient`.
- **Commented-out code** was removed from the item-proc spec files (`specs.object.c`, `specs.underworld.c`, `specs.winterhaven.c`, `specs.undermountain.c`, `specs.zion.c`, `specs.ioun.c`, `specs.vecna.c`): block comments of four or more lines holding three or more statements, plus the three commented `CheckMultiProcTiming` terms. Mob, room, and assignment files were left for their own sweeps. A comment-stripped preprocessor diff of each file showed that only the intended dead blocks changed.

## Objective and bar

Make weapon and gear procs easier to read, find, and change. Remove dead code, give repeated checks one shared spelling, and replace copy-pasted blocks with a few small helpers.

**The bar is the same gameplay, not identical internals.** Take the simpler or more consistent version whenever players cannot tell the difference. These differences are acceptable without asking:

- the order or number of random draws, when every chance stays the same;
- the order in which different audiences receive their messages;
- strict-versus-inclusive cooldown boundaries (one second);
- unreachable or staff-only corner cases;
- checks the dispatcher already guarantees, such as custody of the weapon that just hit;
- arguments the callee ignores.

These are gameplay changes and need the owner's approval: a different chance, damage, level, or effect; which slot can proc (wield slot versus any worn slot, offhand weapons); turning a dead proc on or deleting a live one; different text players see.

`item_actions`, its adapters, rollout settings, timing, and mana system are outside this project. Apply the [ablation skill](../../.agents/skills/ablation/SKILL.md): every helper needs real callers and one job, and each item's chance, messages, and effects stay visible at its call site.

## Findings that govern the work

- **The `char *` argument's payload depends on the event.** A melee hit carries a `P_char`, `CMD_GOTHIT`/`CMD_GOTNUKED` carry `proc_data *`, periodic events carry null, and only player commands carry text. Parsing a non-text payload as text is a defect (see opportunity 7).
- **`cmd / 1000` is just a melee-hit test.** Player commands stop at 877 (`MAX_CMD`), `CMD_MELEE_HIT` (1000) is the only dispatched value of 1000 or more, and every negative pseudo-command (down to −300) truncates to zero. So `dam = cmd / 1000; if (!dam …)` means `cmd != CMD_MELEE_HIT`.
- **Return values are gameplay.** A defensive proc returning true stops the incoming attack or spell. A command proc returning true consumes the command.
- **`CheckMultiProcTiming()` always returns true.** Its throttling body is unreachable.
- **Callback identity matters outside combat.** [`world_quest_policy.c`](../../src/world/world_quest_policy.c#L908) classifies callbacks by function pointer, and `tradeskill.c` compares one too. Keep the named callbacks; share their internals, not their identity.
- **`THARKUN_ARTIS` is always defined** ([`config.h`](../../src/core/config.h#L32)). Its four `#else` halves are dead.

## How to trace an item today

Start with its vnum, find its effective callback assignment, and then inspect the event that reaches it.

| Entry | Owning code | Payload and consequence |
| --- | --- | --- |
| Ordinary weapon hit | [`hit` / `weapon_proc`](../../src/combat/fight.c#L8705) | Packed `value[5..7]` spells or a callback with `CMD_MELEE_HIT` and the victim pointer. These routes are selected, not run together. |
| Backstab | [`single_stab`](../../src/cmd/actoff.c#L7786) | Direct callback with `CMD_MELEE_HIT`; no packed-spell route. |
| Incoming melee | [`pv_common`](../../src/combat/fight.c#L11450) | Equipped callbacks receive `CMD_GOTHIT` and `proc_data *` with only `data.victim` set. True stops the attack. |
| Incoming spell | [`spell_damage`](../../src/combat/fight.c#L4574) | `CMD_GOTNUKED` with damage, type, flags, messages, and attacker in `proc_data`. True intercepts the damage. |
| Player command | [`special`](../../src/cmd/interp.c#L2829) | Text. Room, equipment, inventory, nearby mobiles, and room objects are dispatched in order. True consumes the command. |
| Object initialization/tick | [`instantiate_object_template_impl`](../../src/world/db.c#L3236), [`event_object_proc`](../../src/world/db.c#L2831) | `CMD_SET_PERIODIC` decides whether to schedule; ticks use `CMD_PERIODIC` with null actor and argument. |
| Set effects | [`set_proc`](../../src/specs/specs.object.c#L13637) | Set membership, suppression flags, timer source, set callbacks. |
| Data-driven wrappers | [`studioproc_obj`](../../src/mob/studioproc.c#L1670), [`proclib_obj_cmd_bridge`](../../src/mob/studioproclib.c#L331) | The saved incumbent callback runs first; true prevents the later layer. |

The defensive slot order is explicit in [`proccing_slots`](../../src/combat/fight.c#L353); an earlier interception prevents a later one. `destroystuff` uses the same array.

Assignments mostly live in [`assign_objects`](../../src/specs/specs.assign.c#L1219); `assign_rooms` and other subsystems also install callbacks, and boot runs both before [`studioproc_boot`](../../src/world/db.c#L647). For artifacts, [`artifact_source_inventory.py`](../../scripts/artifact_source_inventory.py) resolves chained literal assignments in execution order (171 tracked templates, 80 bindings, 69 callbacks); it does not cover dynamic assignments, packed spells, or non-artifact gear.

## Opportunities

### 1. Delete dead code first

Nothing here can reach a player, and removing it first shrinks every later sweep.

- **`THARKUN_ARTIS` alternates, about 445 lines:** the `#else` halves holding the old `bloodfeast` and `trans_tower_shadow_globe` (`specs.object.c`) and `mace`, `unholy_avenger_bloodlust`, `flamberge`, and `holy_mace` (`specs.underworld.c`). Remove those halves, the `#ifdef` lines, and the `config.h` define; no other code uses it. `artifact_source_inventory.py` mentions it in a comment and in its `configuration` label, so update both and the tracked inventory if `--check` compares that label.
- **`#if 0` blocks:** 17 in `src/specs/`, plus commented-out code such as the `holy_weapon` rewrite in `specs.object.c` and commented `CheckMultiProcTiming` terms.
- **Callbacks that are never bound:** `blackness_sword` (`specs.highway.c`), `creeping_doom`, `cursed_mirror`, `mist_claymore`, `zarbon_shaper` (`specs.object.c`), `secret_door` (`specs.verzanan.c`), and `random_eq_proc` (`item/random_equipment.c`). Nothing assigns them and nothing looks callbacks up by name at runtime.
- **`orb_of_destruction`:** `assign_objects` binds vnum 26662 to it and two lines later rebinds 26662 to `neg_orb`. Delete the shadowed assignment, the callback, and its identity comparisons in `world_quest_policy.c` and `tradeskill.c`, which can never match.
- **Stale prototypes with no definition (15):** `chess_board`, `floating_pool`, `io_proc_item`, `lathander`, `lloth_avatar`, `loviatar`, `period_book`, `skill_beacon`, `soul_render`, `soulrender`, `staff_of_oghma`, `torms_chessboard`, `valkyrie`, `vaprak_claw`, `wall_generic1` in `specs.prototypes.h`.
- **[`item_procs`](../../src/specs/specs.assign.c#L2574):** no callers, and a comment in `kingdom_harvest.c` already documents that it would read freed memory. Delete it with its prototype and update that comment.

**Proof:** build, the source-extracting tests, and `artifact_source_inventory.py --check`, since the inventory preprocesses `THARKUN_ARTIS`.

### 2. One melee-hit target helper for every spec file

**Evidence:** about 100 procs in 16 spec files handle melee hits (`specs.object.c` 47, `specs.underworld.c` 19, `specs.winterhaven.c` 9, `specs.undermountain.c` 7, `specs.jot.c` 5, and 11 more). They spell one check a dozen ways: `cmd == CMD_MELEE_HIT` or `cmd / 1000`; the victim from the payload, from `GET_OPPONENT`, or from `ParseTarget`; with or without a living-wielder test; with `OBJ_WORN_BY` or its expansion. About half already check exactly the contract below.

**Change:** one shared function, declared in `specs.prototypes.h` and defined in `specs.object.c`, where most callers are:

```cpp
// The victim of a melee hit by obj's living wearer, or NULL when the event,
// wearer, custody, or victim does not qualify.
P_char melee_proc_target(P_obj obj, P_char ch, int cmd, char *arg)
{
	if (cmd != CMD_MELEE_HIT || !IS_ALIVE(ch) || !OBJ_WORN_BY(obj, ch))
	{
		return NULL;
	}
	P_char victim = legacy_proc_arg<P_char>(arg);
	return IS_ALIVE(victim) ? victim : NULL;
}
```

Each melee branch then reads:

```cpp
P_char victim = melee_proc_target(obj, ch, cmd, arg);
if (!victim || number(0, 29))
    return FALSE;
```

Normalizations to take while converting:

- `cmd / 1000` and the `dam` local it fills go away. `bel_sword` reuses `dam` for real damage, so it gets its own local.
- A missing living-wielder or custody test is gained. Only the weapon that just hit receives the event, so this is invisible.
- A victim taken from `GET_OPPONENT(ch)` or `ParseTarget` becomes the hit's payload. This ends the text parsing of a pointer (opportunity 7). The two differ only when a grapple misfire in `hit()` redirects an already-fighting attacker's swing onto the grappler without changing `GET_OPPONENT`. The proc then strikes the character the weapon actually hit, which is the consistent rule for a rare corner case.
- A victim that was only null-checked also gets the liveness test. A dead character is not being hit.
- A roll made before the target test moves after it.
- `if (cmd == CMD_SET_PERIODIC) return FALSE;` preambles go, because the helper already refuses that event. Procs that return true there to schedule a periodic effect keep it.

Real rules stay at the call site after the helper call: wield-slot-only procs (`OBJ_WORN_POS(obj, WIELD)`), `CanDoFightMove`, class and race gates, elite or undead exclusions. Multi-event procs convert only their melee branch.

When a proc gets a helper call, it no longer needs the expanded ownership tests. Once every file is converted, sweep what remains in `src/specs/` to `OBJ_WORN_BY`: there are 24 expanded or redundant spellings in `specs.object.c` and `specs.underworld.c` today. Do not replace `OBJ_WORN_POS` with it; being in the wield slot is a different rule.

**Companion for defensive events:** 33 procs in six spec files handle `CMD_GOTHIT` or `CMD_GOTNUKED` (`specs.object.c` 11, `specs.underworld.c` 7, `specs.winterhaven.c` 5, `specs.zion.c` 4, `specs.vecna.c` 3, `specs.barovia.c` 1). Almost all of them read `proc_data`, and about a dozen already check that the wearer is alive and wearing the item. A sibling `struct proc_data *defense_proc_data(P_obj obj, P_char ch, int cmd, int event, char *arg)` returns the payload when `cmd == event`, the wearer is alive and wearing the item, and the payload is non-null. Custody is again guaranteed by the dispatcher, which walks the defender's equipment. Callers keep their own attacker, damage-type, and chance tests, and their return values, which decide whether the attack is stopped. Add it in the pilot alongside `melee_proc_target`.

`test_world_quest_target_retries.py` compiles `mace_of_sea`, `serpent_blade`, `lich_spine`, `sword_whirlwinds`, `kvasir_dagger`, and `hammer_titans` from source text; add the helper to its extraction list. Grep `tests/` for each converted callback name and do the same wherever it is extracted.

### 3. One three-audience message helper

**Evidence:** the code repeats `act(to_char, …, TO_CHAR); act(to_vict, …, TO_VICT); act(to_room, …, TO_NOTVICT);` with identical visibility flag, actor, object, and victim **604 times** across `src/`, more than 200 of them in `src/specs/` (`specs.object.c` 82, `specs.winterhaven.c` 45, `specs.underworld.c` 39). Another 66 places in `src/specs/` send the same text to two or three audiences. [`act`](../../src/net/comm.c#L5702) has no combined form.

**Change:** add one function beside `act` in `comm.c`/`comm.h`, tentatively:

```cpp
void act_trio(const char *to_char, const char *to_vict, const char *to_room,
	      int hide_invisible, P_char ch, P_obj obj, P_char vict);
```

It sends `TO_CHAR`, `TO_VICT`, then `TO_NOTVICT`. Callers that send the same text twice pass the same string, through a local when the literal is long. Trios using `ACT_TERSE`, `ACT_SILENCEABLE`, or mismatched arguments stay as plain `act` calls. This project converts the item-proc spec files; `actoff.c`, `fight.c`, `magic.c` and other subsystems can adopt it later in their own sweeps.

`kvasir_dagger` shows the payoff. Its four branches hold two identical ice blocks and two identical fire blocks of three `act` calls each. It becomes one message choice, one `act_trio(msg, msg, msg, …)`, and a four-case switch for the spells. The riposte trio shared by `madman_mangler` and `generic_riposte_proc` converts the same way.

### 4. Delete `CheckMultiProcTiming`

[`CheckMultiProcTiming`](../../src/cmd/actoff.c#L13949) returns true before its body. It appears 32 times in seven spec files; 26 calls are compiled.

| Form | Callers | Removal |
| --- | --- | --- |
| An `&&` conjunct | 23: `specs.winterhaven.c` 8, `specs.underworld.c` 6, `specs.object.c` 4, `specs.zion.c` 3, `specs.eth2.c` 1, `specs.hoa.c` 1 | Delete the conjunct |
| `if (CheckMultiProcTiming(ch)) { … }` | `torment` | Unwrap the block |
| `(CheckMultiProcTiming(ch) \|\| !number(0, 2))` | [`doombringer`](../../src/specs/specs.underworld.c#L1027) | Delete the whole parenthetical; the 1-in-3 roll was never drawn |
| `… \|\| CheckMultiProcTiming(ch) \|\| number(0, 32)` in a rejection test | [`lightning_sword`](../../src/specs/specs.undermountain.c#L409) | Delete the term; this turns the proc on (owner-approved, below) |

Delete the function and its prototype. The six uncompiled occurrences go with opportunity 1. `TAG_STOP_PROC` stays registered in `skills.c`; it costs one line, and removing a registered tag is a separate question.

**`lightning_sword` (owner-approved gameplay change, 2026-11-07):** the always-true term makes it reject every hit, so its 1-in-33 effect has never run while the gate has been disabled. Dropping the term turns the proc on, which is almost certainly the original intent. Make this its own commit, mention it in the PR description and in player news, and in the local gameplay check confirm that it fires at roughly 1 in 33 hits.

### 5. Merge the cloak and ioun deflection bodies

**Evidence:** [`elvenkind_cloak`](../../src/specs/specs.underworld.c#L2888) and [`deflect_ioun`](../../src/specs/specs.underworld.c#L2955) contain the same count/select/redirect code, differing only in message text and the ioun's native route. These are the only copies in `src/`.

**Change:** one static function in `specs.underworld.c` that takes the object, wearer, `proc_data`, and the three message strings. It picks a random non-trusted character in the room other than the wearer, sends the messages, redirects the damage with `SPLDAM_NODEFLECT`, and returns whether it deflected. Each callback keeps its 1-in-4 trigger and data checks. The ioun keeps its native route in front.

This selection is uniform over the eligible bystanders. For a mortal wearer it is the same draw as today. It removes the staff-wearer quirk where the last bystander could never be chosen, and the ioun's extra `!ch->in_room` test, which only differs in room index 0. Both changes are invisible to players.

`test_native_artifact_runtime.py` compiles `deflect_ioun` from source text; add the new function to its extraction list.

### 6. One periodic self-stoneskin helper

**Evidence:** at least nine worn-item blocks repeat the same thing: find the wearer, skip if it already has a skin spell, check a `timer[0]` interval, cast `spell_stone_skin` on the wearer, and stamp the timer. These are `illesarus` (`specs.hoa.c`), `artifact_stone`, `transp_tow_misty_gloves`, `bloodfeast`, `dragonlord_plate_oldold`, `good_evil_stoneOrSoulshield`, `sunblade`, and two blocks in `trans_tower_shadow_globe` (`specs.object.c`). They differ only in level and interval, plus a call type that `spell_stone_skin` ignores (`[[maybe_unused]] int type`).

**Change:** `bool periodic_stoneskin(P_obj obj, int level, int interval)`, which returns whether it cast. Each item keeps its own level and interval, including its property lookup. `apply_zone_spell` and `barb` have different structures; leave them.

### 7. Fix text parsing of binary payloads

This is a defect class, not a refactor, so it ships as its own change.

- Six `specs.winterhaven.c` procs (`volo_longsword`, `deathseeker_mace`, `illithid_axe`, `demon_slayer`, `rapier_penetration`, `gladius_backstabber`) call [`ParseTarget`](../../src/cmd/actoff.c#L654) on melee hits. It runs `one_argument` over the victim struct's bytes as if they were a name, and a taunted wielder can see "You try to switch opponents but can't!" from a proc check. Opportunity 2 fixes the melee branches. Check whether their other events reach `ParseTarget` too.
- [`ring_of_regeneration`](../../src/specs/specs.object.c#L11201) calls `one_argument` before testing `CMD_RUB`, so combat payloads reach [`one_argument`](../../src/cmd/interp.c#L2698)'s `strlen`. [`proc_whirlwinds`](../../src/specs/specs.object.c#L11247) has the same shape. Parse only inside the command branch.

**Proof:** run each callback with a melee-hit and a `CMD_GOTHIT` payload under ASan, before and after the fix.

### 8. Move set execution into `specs.set.c`

**Evidence:** [`specs.set.c`](../../src/specs/specs.set.c) holds `master_set`, while `master_set_adapter`, the cleanup payload and event, the group grant helper, `apply_zone_spell`, `check_zone_spells`, `random_set`, the set table, and `set_proc` are one contiguous block in [`specs.object.c`](../../src/specs/specs.object.c#L13260).

**Change:** move the block, keeping callback symbols and assignments. Make helpers static where nothing outside uses them. Fix the misleading Zalrix banner and drop declarations the combined file does not use. Do the pure move in one commit and any cleanup in the next, so review stays easy. The `master_set` and generic set lists, counting, suppression, and cooldown sources are gameplay rules; do not merge them as part of the move.

**Proof:** `test_named_set_membership.py`, `test_named_set_effect_levels.py`, `test_named_set_cooldowns.py`, `test_named_set_effect_ownership.py`, with their extraction targets updated to the new file, plus an existing named-set wear/removal journey. `_paths.py` resolves filenames, not functions, so moved definitions need their extractors updated.

### 9. Simplify packed-spell application in `weapon_proc`

**Evidence:** [`weapon_proc`](../../src/combat/fight.c#L8759) repeats the same offensive-victim/beneficial-self invocation in its random-one and all-spells branches, and decodes three decimal-packed spell IDs inline.

**Change:** decode the three slots once and apply through one static function beside `weapon_proc`. Slot order and sparse-slot handling may change as long as the same spells apply. Keep the data format: `value[5] > 999999999` selects one-of, and `value[7]` is the denominator, because area files encode it. Do not add packed procs to backstab or touch `weapon_actions.c`.

**Proof:** `packed_parity()` in `test_weapon_actions_runtime.py` with the new system off, plus a local fight with a packed-spell weapon.

## Deliberately not doing

- **Cooldown helper:** 99 of the 138 timer checks in `src/specs/` are already the one-line `obj->timer[N] + seconds <= curr_time`. A helper saves nothing.
- **Drain/heal helper:** Bloodfeast, Avernus, and encrusted bloodstone use different formulas, flags, and caps, and players see those numbers. Keep `vamp`, `spell_damage`, and `melee_damage` calls explicit.
- **Generic multi-hit or multi-spell executor:** death, movement, and extraction between hits differ by proc and can crash. Handle them per proc.
- **Temporary saving-throw helper:** about 15 procs set or adjust `SAVING_SPELL` around a spell and restore it afterward. The values are balance numbers, and restoring after a spell that extracts the victim may write to a freed character. Reproduce that first. A helper that restores only when the victim is still valid could then serve every caller as a safety fix.
- **Affect factory, forced-disarm sharing, proc registry or event bus:** existing APIs already cover these, they encode different rules, or they would replace the callback ABI across combat, commands, periodic work, Studio, and proclibs.

## Proof for every patch

Same gameplay is the bar, so no golden traces. Each patch needs:

- `make -C src` and `./scripts/format.sh --check`.
- Every test that extracts a touched function from source text, with its extraction list updated. Grep `tests/` for each touched name.
- One small runtime test for the shared helpers (`melee_proc_target`, `defense_proc_data`, `act_trio`, the deflection selector, `periodic_stoneskin`), following `test_freedom_of_movement_procs.py`. It should cover the helper contracts plus one real converted callback each, showing the wiring.
- A local gameplay check with the `.env` test account: wield or wear a converted item, fight, and confirm procs fire with correct messages. Restarting the local server is free.
- `python3 scripts/artifact_source_inventory.py --check` when assignments or `THARKUN_ARTIS` change.

| Changed boundary | Existing evidence to reuse |
| --- | --- |
| Melee callbacks and callback identity | `test_world_quest_target_retries.py`, `world_quest_live_targets_harness.cpp` |
| Packed weapons | `test_weapon_actions_runtime.py`, `run_weapon_actions_journey.py` |
| Cloak/ioun | `test_native_artifact_runtime.py` |
| Set module move | the four `test_named_set_*.py` tests and a named-set journey |
| Proclib wrapper | `test_proclib_bridge_contract.py` |
| Periodic owner lifetime | `test_nevent_periodic_rearm_runtime.py` |
| Affect/immunity callers | `test_freedom_of_movement_procs.py` |

## Delivery sequence

1. **Dead code** (opportunity 1). No gameplay surface.
2. **`CheckMultiProcTiming` removal** (opportunity 4), with `lightning_sword`'s activation as a separate commit.
3. **Pilot:** add the helpers from opportunities 2 (both), 3, 5, and 6, with their runtime test, and convert `specs.object.c` and `specs.underworld.c` completely. Stop and confirm with the owner that the converted files read better before sweeping further.
4. **Sweep** the remaining spec files linearly, a file or a few small files per PR, applying the same rewrites, then the leftover `OBJ_WORN_BY` spellings.
5. **Payload parsing fixes** (opportunity 7), as a defect PR.
6. **Set move** (opportunity 8) and **`weapon_proc`** (opportunity 9), independently.

Branch from `master` in a separate worktree; the main checkout carries unrelated uncommitted changes, including `config.h` and `Makefile`.

## Tracing improvements without a new subsystem

- Add a short event/payload note beside the callback typedef and pseudo-command constants. It should say what the `char *` carries for each event and what `TRUE` means to each dispatcher. Note that `CMD_GOTHIT` currently populates only the attacker field.
- Keep named callbacks; quest policy and tradeskill classify by identity.
- Keep source-to-callback tracing in `specs.assign.c` and the inventory tool rather than a second hand-maintained registry.

## Research record

Read-only, at `896ff7b28`:

- `python3 scripts/artifact_source_inventory.py --check`, `test_proclib_bridge_contract.py`, and `test_named_set_membership.py` passed during the first research pass.
- The counts above come from scans of `src/` that skip `#if 0`, the dead `THARKUN_ARTIS` halves, and comments. The melee-proc and `act`-trio counts come from pattern scans and are approximate; the conversion will find the exact set. Dead-callback status was checked by searching all of `src/` for each name. There is no `dlsym` lookup; `-rdynamic` exists for `signals.c` crash backtraces.
- Production obtainability and live configuration are not inferred from source assignment.
