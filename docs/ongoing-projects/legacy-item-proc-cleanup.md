# Legacy weapon and gear proc cleanup

Research date: 2026-11-07. Source baseline: `896ff7b28`. Status: plan; no production code has been changed for this work.

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
