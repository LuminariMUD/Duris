# Legacy weapon and gear proc cleanup

Research date: 2026-11-07. Source baseline: `39d5d2413aef73ffc77155e0afecd4623b5130f5`, plus the current working tree. Status: researched proposal; no production code has been changed for this work.

## Objective and scope

Make existing weapon and gear procs easier to read, find, and safely change through small extractions, reuse of existing helpers, and clearer ownership of related code. Preserve current gameplay. `item_actions`, its adapters, rollout settings, timing, and mana system are outside this project.

Apply the repository's [ablation skill](../../.agents/skills/ablation/SKILL.md): a helper needs concrete duplicate callers or a demonstrated responsibility boundary. Start local. Give each helper one job. Keep each item's chance, messages, spell arguments, and return behavior apparent at its call site. A move should leave one implementation and the same callable symbols.

The first implementation should touch only `specs.object.c`, `specs.underworld.c`, and focused tests. It needs two small local helpers: one for a matching family of melee eligibility checks and one for the duplicated deflection-target scan. Kvasir's repeated messages and existing ownership macros can be cleaned up in the same files. Further opportunities below are alternatives for subsequent small changes, not a requirement to build every proposed component.

## Findings that govern the work

- There is real repetition in ordinary procs, but their guards are not universally interchangeable. Some test the target before RNG; others roll first. Some accept `CMD_MELEE_HIT` exactly; others use `cmd / 1000`.
- The legacy callback's final `char *` parameter carries different payloads. Knowing the event is a prerequisite to interpreting it. Moving parsing or casts into a shared entry point can change what commands a proc consumes.
- Return values are gameplay behavior. A defensive proc returning true can prevent the original attack; an offensive proc's return is not necessarily used by its caller.
- `CheckMultiProcTiming()` currently returns true immediately. Its unreachable code would check and set `TAG_STOP_PROC`, but that does **not** happen in the inspected implementation. Its name and callers give a misleading impression of active throttling.
- Callback identities are used outside combat, including world-quest eligibility checks. Keep the named callback wrappers when extracting common internals.
- Current `config.h` defines `THARKUN_ARTIS`. Several apparent duplicates are alternative preprocessor branches. The working tree already has unrelated changes, including `config.h` and `Makefile`; preserve those and verify the selected configuration when implementing.

## How to trace an item today

Start with its vnum, find its effective callback assignment, and then inspect the event that reaches it. A callback definition alone does not establish how the item behaves.

| Entry | Owning code | Payload and consequence |
| --- | --- | --- |
| Ordinary weapon hit | [`hit` / `weapon_proc`](../../src/combat/fight.c#L8705) | Packed `value[5..7]` spells or a callback with `CMD_MELEE_HIT` and the victim pointer. These routes are selected, not blindly run together. |
| Backstab | [`single_stab`](../../src/cmd/actoff.c#L7786) | Direct callback with `CMD_MELEE_HIT`; does not run the generic packed-spell route. |
| Incoming melee | [`pv_common`](../../src/combat/fight.c#L11450) | Equipped callbacks receive `CMD_GOTHIT` and `proc_data *`; here only `data.victim` is populated. A true result stops this attack path. |
| Incoming spell | [`spell_damage`](../../src/combat/fight.c#L4574) | `CMD_GOTNUKED` with damage, type, flags, messages, and attacker in `proc_data`. A true result handles/intercepts the incoming damage. |
| Player command | [`special`](../../src/cmd/interp.c#L2829) | Text argument. Room, equipment, inventory, nearby mobiles/quests, and room objects have an ordered dispatch. A true result consumes the command. |
| Object initialization/tick | [`instantiate_object_template_impl`](../../src/world/db.c#L3236), [`event_object_proc`](../../src/world/db.c#L2831) | `CMD_SET_PERIODIC` decides whether to schedule; ticks use `CMD_PERIODIC`, a null character, and null argument. The callback normally finds its wearer from the object. |
| Set effects | [`set_proc`](../../src/specs/specs.object.c#L13637) | Set membership/counting, per-item suppression flags, selected timer source, and set-specific callbacks. |
| Data-driven wrappers | [`studioproc_obj`](../../src/mob/studioproc.c#L1670), [`proclib_obj_cmd_bridge`](../../src/mob/studioproclib.c#L331) | Saved incumbent callback runs first; true prevents the later layer. Proc-library periodic work has its own scheduling path. |

The defensive slot order is explicit in [`proccing_slots`](../../src/combat/fight.c#L353). An earlier weapon interception can prevent a later ioun interception. That array is also used by `destroystuff`; a proc cleanup must not silently change equipment-damage traversal.

Assignments mostly live in [`assign_objects`](../../src/specs/specs.assign.c#L1219), but `assign_rooms` also assigns objects, and other subsystems install callbacks dynamically. Boot calls object and room assignment before [`studioproc_boot`](../../src/world/db.c#L647). Preserve installation order as well as the final function name.

For artifacts, reuse [`artifact_source_inventory.py`](../../scripts/artifact_source_inventory.py). It preprocesses the assignment source and resolves chained literal assignments in execution order. Its current check passes: 171 tracked artifact templates, 80 literal bindings, 69 distinct callbacks. These counts cover its **artifact source corpus**, not all gear or live availability. It does not replace inspection of dynamic assignments, packed spells, or ordinary non-artifact items.

Useful traces verified in `specs.assign.c`:

| Vnum | Callback | First useful inspection |
| --- | --- | --- |
| 67262 / 67237 / 67242 | `mace_of_sea` / `serpent_blade` / `lich_spine` | Matching melee guards, then different effects. |
| 36884 | `kvasir_dagger` | One trigger roll, one four-way effect selection, repeated messages. |
| 26665 / 922 | `elvenkind_cloak` / `deflect_ioun` | Same legacy room-target selection; retain the ioun's existing routing boundary. |
| 92020, 82500, 83605 / 18000 | `generic_parry_proc` / `generic_riposte_proc` | Existing shared callbacks already demonstrate ordinary reuse. |
| 38763 / 76032 | `ring_of_regeneration` / `proc_whirlwinds` | Command activation and periodic readiness in one callback. |
| 41915 | `lightning_sword` | An always-true `CheckMultiProcTiming` term currently prevents its effect path. |

## First pass: small extractions with real callers

### 1. Share identical melee eligibility checks

**Evidence:** [`mace_of_sea`](../../src/specs/specs.object.c#L4352), `serpent_blade` at 4380, `lich_spine` at 4485, and `neg_orb` at 4517 repeat the event/living-wielder/worn-by/living-victim checks before their chance rolls. Kvasir's checks have the same relevant ordering and eligibility.

**Change:** add one file-local function, tentatively `melee_proc_target(P_obj, P_char, int, char *)`, which checks that exact contract and returns the victim or null. Reuse `OBJ_WORN_BY` and `legacy_proc_arg<P_char>`. Leave RNG and effects in each callback. Start with the four simple functions above; include Kvasir after its message cleanup is separately understood.

The resulting shape should remain readable:

```cpp
P_char victim = melee_proc_target(obj, ch, cmd, arg);
if (!victim || number(0, 29))
    return FALSE;

// The item's existing messages and direct effect calls remain here.
```

**Boundary:** do not add same-room, visibility, hostility, player-only, primary-slot, or immobility requirements. Those are not part of this shared family. Do not substitute the current fighting opponent for the supplied victim. Do not adopt `cmd / 1000` callers or chance-before-target callers by adding options to the helper.

**Proof:** execute the real callbacks for unrelated text commands, periodic initialization, dead/null participants, carried gear, wrong wearer, failed roll, and successful roll. Record RNG bounds/draw count, messages, spell arguments, and return value. Existing world-quest tests cover unrelated `CMD_ASK` behavior for several of these handlers, but do not prove their successful combat effects.

### 2. Share the legacy spell-deflection target scan

**Evidence:** [`elvenkind_cloak`](../../src/specs/specs.underworld.c#L2888) and [`deflect_ioun`](../../src/specs/specs.underworld.c#L2955) contain the same count/select/traverse logic. The item-specific text surrounds the same damage redirection.

**Change:** extract only that scan into a static `legacy_deflection_target(P_char wearer)` in the same file. Keep the existing 1-in-4 selection, preliminary guards, messages, damage call, and true/false return at each caller. The ioun's existing alternative route stays where it is.

**Boundary:** preserve room-list order and the number and bounds of random draws. The current count includes non-trusted characters, while the second walk excludes the wearer. This has a corner case when the wearer is trusted; a cleanup must not silently replace it with a uniformly sampled filtered vector. The ioun also has a `!ch->in_room` guard that the cloak lacks. Do not merge their eligibility policies accidentally.

**Proof:** compare target identity and draws for zero/one/many candidates, trusted bystanders, trusted wearer, wearer at different list positions, and every selectable index. Then execute both callbacks and compare damage/type/flags/messages and interception return. The existing native-artifact harness exercises the ioun entry point, but a new cloak-versus-ioun legacy parity fixture is still needed for this extraction.

### 3. Collapse Kvasir's repeated presentation

**Evidence:** [`kvasir_dagger`](../../src/specs/specs.object.c#L4428) has four branches: two identical ice-message blocks and two identical fire-message blocks, each containing three `act` calls.

**Change:** store the existing four-way choice, select the ice or fire text, emit the three messages once, then retain a switch for the four direct spell calls. This is a local restructuring; it does not require a generic effect table or message service.

**Boundary:** retain one trigger roll followed by one effect-choice roll, the audience order `TO_NOTVICT`, `TO_CHAR`, `TO_VICT`, and the existing visibility flag. The first spell uses `SPELL_TYPE_SPELL`; other branches pass zero. Keep those call types and the source-object argument exactly.

**Proof:** force all four choices and compare exact message text, flags, audience order, spell, level, call type, target, and source. Include the failed trigger and unrelated-command paths. A test merely checking that four spell names remain in the file is insufficient.

### 4. Reuse existing ownership expressions while touching callers

**Evidence:** [`OBJ_WORN_BY`](../../src/core/utils.h#L1074) already implements the repeated `OBJ_WORN(obj) && obj->loc.wearing == ch`. `neg_orb`, `madman_mangler`, `ljs_sword`, `wuss_sword`, and `head_guard_sword` contain expanded forms.

**Change:** use the existing macro for identical checks in functions already being edited. Keep slot restrictions expressed with existing `OBJ_WORN_POS` where that is the actual rule.

**Boundary:** being worn by a character and being in that character's primary weapon slot are different requirements. Do not replace one with the other. `GET_OBJ_PROC` is also available, but it handles negative `R_num` and panics on null; mass substitution for raw indexing is not automatically behavior-preserving.

**Proof:** the same callback fixture used for opportunity 1 covers custody and owner cases. No independent framework or broad repository sweep is needed for a Boolean-expression replacement.

## Subsequent opportunities, in order of usefulness

### 5. Make the disabled multiproc limiter honest

**Evidence:** [`CheckMultiProcTiming`](../../src/cmd/actoff.c#L13949) returns true before checking or setting `TAG_STOP_PROC`. Its callers span several spec files. [`doombringer`](../../src/specs/specs.underworld.c#L1027) contains `CheckMultiProcTiming(ch) || !number(0, 2)`, so the second roll is currently never evaluated. [`lightning_sword`](../../src/specs/specs.undermountain.c#L409) contains the function positively in a rejection condition, so it currently returns false before its 1-in-33 roll and effects.

**Smallest first change:** remove the unreachable body and state clearly that the function is a retained, disabled legacy gate. That immediately removes misleading code without touching every caller.

**Optional later change:** remove the no-op calls by simplifying their actual Boolean expressions. Preserve short-circuit evaluation: the Doombringer fallback roll disappears, not becomes unconditional. Preserve the currently disabled lightning-sword behavior until a separate gameplay fix is approved. Do not turn its dead effect path on as an incidental cleanup.

**Proof:** enumerate all real call sites with comments and inactive preprocessor branches distinguished; compare draw sequences and reachable effects before and after. A shared “proc chance” wrapper would hide this problem rather than solve it.

### 6. Give set-proc execution one existing home

**Evidence:** [`specs.set.c`](../../src/specs/specs.set.c) contains `master_set`, while the related `master_set_adapter`, cleanup payload/event, group grant helper, `apply_zone_spell`, `check_zone_spells`, `random_set`, set table, and `set_proc` are a contiguous block in [`specs.object.c`](../../src/specs/specs.object.c#L13260). Catalog, origin, and effect ownership already have dedicated `src/item/named_set*` files.

**Change:** move the contiguous execution block into the existing `specs.set.c`. Keep callback symbols and assignments stable. Localize helpers after checking actual external references. Retain the existing catalog/origin/effect modules as their owners; avoid inventing a new set manager or splitting the block into several files.

**Boundary:** relocation only in the first change. `master_set` has its own numeric slot order and membership list. The generic set table has a different list, including 82559, and different counting/suppression behavior. `master_set_adapter` ignores the passed count. Do not consolidate these lists by assuming they are equivalent. Named-set cleanup, linked grants, timer-source selection, duplicate handling, and belt exclusions are gameplay rules.

**Proof:** run the named-set membership, effect-level, cooldown, and effect-ownership checks; update tests that extract source by filename to follow the real moved definitions. Execute an applicable existing wear/removal journey when integrating. Preserve function-pointer identities used in event matching and quest policy. The existing 161-line destination has a misleading Zalrix file banner and many unrelated declarations; prune only declarations proved unused by the combined file.

### 7. Separate packed-spell decoding and application within `weapon_proc`

**Evidence:** [`weapon_proc`](../../src/combat/fight.c#L8759) repeats the same offensive-victim/beneficial-self spell invocation in its random-one and all-spells branches. It also decodes three decimal-packed spell IDs inline.

**Change:** first extract only the duplicated application block into a static function beside `weapon_proc`, taking the spell, level, wielder, original victim, and source. Keep selection, RNG, messages, room checks, loop order, and route selection in `weapon_proc`. A decoding helper is justified only if its named result makes the three-slot format clearer; it has one legacy consumer and is optional.

**Boundary:** preserve the current nonzero count and slot indexes. Sparse slots are not compacted; the all-spells path runs in descending index order. Preserve `value[5] > 999999999` as the one-of selector and `value[7]` as the denominator. Do not add packed procs to backstab. Do not share code with or alter `weapon_actions.c` in this project. Bounds validation or sparse-slot repairs would be separate behavior changes.

**Proof:** `packed_parity()` in the existing weapon-action test compares enabled/disabled execution for ordered mixed bundles and sparse bundles. Its pure-beneficial case takes the instant fallback. Its one-of selection, self-buff suppression, and effect-transition cases primarily exercise enabled routing, so extend those cases to run with the new system off before relying on them for this extraction. Verify room departure between effects and exact one-of draws. The test file's name does not mean the new system must be enabled to use its legacy coverage.

**Location:** after the function is simpler, a dedicated `src/item/weapon_procs.c` is a possible home for generic weapon execution and a coherent group of simple offensive callbacks. Create it only with an actual move that reduces tracing across responsibilities. Do not create empty files for defensive, command, periodic, and artifact families in advance.

### 8. Organize mixed callbacks by the event they actually handle

**Evidence:** [`ring_of_regeneration`](../../src/specs/specs.object.c#L11201) combines initialization, slot checks, command parsing, charge consumption, healing, and periodic recharge. [`proc_whirlwinds`](../../src/specs/specs.object.c#L11247) has a similar shape, but different slots, flag, targeting, and refusal return values.

**Change:** keep a short visible event dispatch in each callback; put command-only parsing inside its command branch and periodic readiness in its periodic branch. Extract a file-local subfunction only when one branch remains substantial after this restructuring. A common device state machine is unnecessary.

**Boundary:** the ring currently calls `one_argument` before testing `CMD_RUB`. Combat events carry a binary payload; [`one_argument`](../../src/cmd/interp.c#L2698) calls `strlen` for non-null arguments. Guarding parsing by event is a concrete safety investigation, not merely a cosmetic move. A null periodic argument is already handled by the parser. The bracer clears `ITEM_HUM` on an invalid slot before its event checks; moving that mutation can change behavior. Its uncharged command returns true, whereas the ring's uncharged rub returns false.

**Proof:** first reproduce the non-text payload case with the real parser and an equipped ring. Keep any demonstrated fix distinct from a pure refactor. Exercise initialization, periodic null actor, unrelated commands, target matching, wrong slot, uncharged activation, successful activation, and exact recharge boundaries. Preserve whether timer/flag writes happen before or after the effect.

## Opportunities deliberately deferred after ablation

These are tempting extractions whose cost or semantic differences currently outweigh the benefit of adding a shared API.

- **Universal message helper:** the inspected three-`act` groups differ in visibility flags, audience order, terse flags, or extra messages. Kvasir's local simplification is worthwhile. The identical riposte message trio in `madman_mangler` and `generic_riposte_proc` could later become one narrowly named local helper; it must leave hit loops outside. A configurable message dispatcher would obscure simple calls.
- **Universal cooldown helper:** the code mixes last-use timestamps, expiry timestamps, strict `<`, inclusive `<=`, property-derived intervals, and RNG added to cooldown checks. Some callbacks spend the cooldown before invoking an effect and others afterward. Keep one-line arithmetic explicit; use named constants for confusing slots locally before considering shared mechanics.
- **Universal drain/heal helper:** active Bloodfeast uses negative spell damage with `RAWDAM_NOKILL`, then healing; Avernus heals first and uses different damage flags and caps. Encrusted bloodstone has undead/resistance checks and melee damage. Reusing `vamp`, `spell_damage`, and `melee_damage` preserves meaningful distinctions.
- **Generic multi-hit/multi-spell executor:** `madman_mangler` checks `char_in_list` between hits; `lightning_armor` checks `IS_ALIVE` between spells; Doombringer uses damage return codes. Movement, extraction, and retargeting semantics require individual proof. This is not a quick loop-deduplication task.
- **Temporary-save RAII wrapper:** `lich_spine` and `nightbringer` assign the save to 20, while other procs add 5 or 15. The restore happens after arbitrary spell code. A destructor holding the same raw character pointer is not a lifetime fix. First reproduce the actual lifetime requirement; preserve absolute versus additive changes and nested-call behavior. This remains a targeted safety task, not an initial helper.
- **Global affect factory:** existing `set_short_affected_by`, `affect_to_char`, `affect_to_char_with_messages`, and linked-affect helpers already exist. Duration units, source ownership, stacking, wear-off messages, and persistence differ. Use the matching existing API; do not flatten these policies into an option list.
- **Common forced-disarm helper:** [`forced_weapon_drop`](../../src/item/forced_weapon_drop.c) already handles floor transfer and persistence for its callers. `disarm_pick_gloves` transfers the weapon to the victim's inventory and applies a disarm affect. That is different behavior; do not switch it to a floor-drop helper based on the word “disarm.”
- **Proc registry/event bus/base class:** assignment tables and wrappers already exist. Preserve stable callback identities and improve local bodies first. Replacing the ABI across combat, commands, periodic work, Studio, and proclibs would be a separate architectural project.
- **Generic eligibility policy:** applying `CanDoFightMove`, primary-wield restrictions, or a living-wearer check to every callback would change some items. The first melee helper has a deliberately narrow set of matching callers.
- **Blanket removal of old branches or dormant functions:** `THARKUN_ARTIS` alternatives, commented blocks, `item_procs`, and disconnected `random_eq_proc` require separate reachability/configuration evidence. `item_procs` has no direct call found in the inspected C sources; that is not a complete proof of removability. Do not attach `random_eq_proc` to an object as cleanup.

## Tracing improvements without a new subsystem

Keep a short event/payload note beside the existing callback typedef and pseudo-command constants when those declarations are next touched. Specifically document that `CMD_GOTHIT` currently provides only the attacker field and that `TRUE` means different things to different dispatchers. This is a documentation improvement, not a reason to initialize or reinterpret other fields without examining consumers.

Use stable symbol names in move descriptions and keep existing wrappers. [`world_quest_policy.c`](../../src/world/world_quest_policy.c#L908) explicitly recognizes `mace_of_sea`, `serpent_blade`, `lich_spine`, and numerous other function pointers as ASK-safe. Replacing all these pointers with one generic callback would change quest classification even if combat output looked identical.

Keep source-to-callback tracing in ordinary files and the existing inventory tool. The tool already handles preprocessor selection and chained literal assignments. A broader non-artifact inventory can be added to that tool only if it serves a concrete conversion batch; a second manually maintained registry would drift.

When moving implementations, inspect source-extraction tests as callers too. `_paths.py` finds relocated **filenames**; it does not discover a function that moved from `specs.object.c` into `specs.set.c`. Update the extractor target and retain the actual executable assertions. Do not weaken tests into text-presence checks to accommodate the move.

## Proposed delivery sequence and acceptance

1. **First patch:** opportunities 1–4, limited to the two existing spec files. Two local helpers, Kvasir message restructuring, ownership-expression reuse. Add or extend one focused runtime fixture for the changed callbacks. Stop here and assess whether reading the result is actually easier.
2. **Second patch, if useful:** clarify the disabled multiproc function. Caller elimination is a separate follow-up because of short-circuit and disabled-effect cases.
3. **Third patch, independent:** relocate set execution into `specs.set.c`, with no counting or effect-policy changes.
4. **Later, individually justified:** simplify packed-spell application, then consider its dedicated file; investigate mixed command/periodic handlers. Each is independently reviewable and does not depend on creating a broad proc framework.

For every implementation patch:

- Capture the original callback's RNG draws, messages, native effect calls, return value, and state changes under deterministic inputs; compare the refactored callback against those observations. Draw bounds and conditional draw count matter, not just the final damage number.
- Exercise the actual event path relevant to the change. Direct callbacks alone do not prove dispatcher ordering, first-interceptor wins, backstab routing, or wrapper behavior.
- Include actor/target death, movement, source removal, or extraction when the touched effect can cause them. Treat a reproduced existing defect separately from behavior-preserving factoring.
- Run the smallest applicable existing regressions, `./scripts/format.sh --check`, and `make -C src` after C/C++ changes. Use the repository's gameplay/persistence journey requirements when touching those boundaries. CI is not a completion dependency.
- Re-read the diff and delete optional layers. A helper should replace a repeated block, not move the same branching into a harder-to-find function with many flags.

Suggested test reuse, with limits:

| Changed boundary | Existing evidence to reuse | What it does not establish alone |
| --- | --- | --- |
| Melee guards and stable callback identity | `test_world_quest_target_retries.py` and `world_quest_live_targets_harness.cpp` | Successful proc chance, message, spell, and damage parity. |
| Packed weapons | `test_weapon_actions_runtime.py`, ordered/sparse legacy comparisons and beneficial fallback; `run_weapon_actions_journey.py` where applicable | Full legacy one-of and effect-transition parity, every custom native proc, or defensive slot ordering. |
| Cloak/ioun legacy deflection | Relevant entry-point cases in `test_native_artifact_runtime.py` | Exhaustive legacy cloak/ioun target selection and trusted-wearer behavior. |
| Set module move | `test_named_set_membership.py`, `test_named_set_effect_levels.py`, `test_named_set_cooldowns.py`, `test_named_set_effect_ownership.py` | Full loaded-game wear/transfer/persistence behavior; use the applicable existing named-set journey too. |
| Proclib wrapper preservation | `test_proclib_bridge_contract.py` | It is a source contract, not complete runtime proof of arbitrary incumbent effects. |
| Periodic event owner lifetime | `test_nevent_periodic_rearm_runtime.py` | Every callback's internal pointer use or command parsing. |
| Affect/immunity callers | `test_freedom_of_movement_procs.py` | All proc effects; it targets reviewed binding/immunity paths. |

## Research verification and open boundaries

Executed during this research:

- `python3 scripts/artifact_source_inventory.py --check` — passed; the tracked artifact inventory matches the inspected sources/configuration.
- `python3 tests/async/test_proclib_bridge_contract.py` — passed; existing displaced-callback ordering contract remains intact.
- `python3 tests/async/test_named_set_membership.py` — passed; real worn-set counting, HP thresholds, legacy separation, and independent cleanup execute successfully in its fixture.

Earlier in this same review, `test_item_actions_runtime.py` and `test_weapon_actions_runtime.py` passed with ASan/UBSan. Only the latter's legacy fixtures are relevant reuse for this plan; those runs do not prove proposed refactors or every proc.

No new helper, module move, balance change, server build, deployment, or production inspection was performed for this document. Production obtainability and live configuration are not inferred from source assignment. Potential defects noted above need a targeted reproducer before a fix is claimed. The deliverable is the researched cleanup plan; implementation remains pending.
