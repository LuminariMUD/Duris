# Monk glove melee proc plan

Status: framework implemented and validated; content pilot remains (2026-11-08). The research worktree was clean at
`4fddd48b4`; implementation stays on `branch/monk-glove-proc-research` for the
framework PR, followed by a dependent content-pilot PR. The baseline research is
separated in [PR #804](https://github.com/LuminariMUD/Duris/pull/804), stacked on
[PR #797](https://github.com/LuminariMUD/Duris/pull/797). Neither PR authorizes a
production deployment. No existing release tag will be moved; this feature does
not need a release tag before review.

## Current execution / handoff

- **Outcome:** explicitly opted-in primary gloves proc on player monks' resolved
  barehand attacks, including ripostes and the separate PvP pressure strike.
  Inspection, runtime/editor valuation, delayed actions and persistence must agree.
- **Non-goals:** weight/damage formula changes, new proc or scheduler systems,
  global cooldowns, specialization multipliers and production operations.
- **Files:** the framework file list below, existing focused runtime fixtures,
  monk/builder help; authored object records only in the dependent pilot.
- **Proof:** sanitizer-backed executable combat/dispatcher/runtime tests, focused
  lifecycle regressions, both builds and formatting, persistence on both backends,
  and an isolated gameplay journey. Record actual results here before each PR.
- **Ablation:** retain the existing dispatcher, packed encoding, continuation and
  item-action adapter. Use the adapter's captured source slot to distinguish
  pending glove actions even after their flag is cleared. No new runtime category
  or configuration namespace is needed. The plan already excludes speculative
  machinery; no requirement is dropped.
- Prerequisite [PR #797](https://github.com/LuminariMUD/Duris/pull/797),
  `branch/fix-editor-valuation-build`, fixes two pre-existing staff-editor build
  blockers (missing C++20 and the removed `AFF2_MINOR_INVIS` symbol). The required
  touched-file format check also necessitated formatting that legacy editor file;
  the framework PR is based on #804 so its review excludes both the mechanical diff
  and the 105-entry research catalog.
- Implemented: bit-20 opt-in and correct flag names; shared glove predicate;
  pre-damage capture and terminal dispatch in `hit()` / `monk_superhit()`;
  malformed packed-glove rejection; delayed source-slot/class/flag validation;
  runtime/editor packed valuation; shared weapon/glove inspection; monk help.
- Found and fixed an immediate packed-bundle lifetime gap: check the existing
  continuation between effects so participant/source extraction or relocation
  stops the bundle. Existing weapon behavior and spell selection remain covered.
- Passed: MariaDB and flatfile server builds (`make -C src -j4`, then
  `make -C src PERSISTENCE_BACKEND=flatfile -j4`); normal editor build; sanitizer
  weapon-action and sword-action suites; `test_monk_glove_tools.py`;
  `test_sql_item_instance_fields.py`; attack-continuation and item-proc-guard suites.
  Staff debug editor build passed in #797's worktree. Compiled outputs are under
  `bin/`; no production environment or running local stack was touched.
- Also passed: `test_combat_start_lifetime.py`, `test_riposte_lifetime.py`,
  `test_world_recovery_pipeline.py`, and `test_world_recovery_codec.py` (including
  packed values and all three upper extra2 bits). `./scripts/format.sh --check`
  and normal + debug editor builds pass with the final framework sources.
- Real-game proof passed on **both** backend builds:
  `python3 tests/async/run_monk_glove_journey.py --flatfile bin/tests/monk-flatfile-server --mariadb bin/tests/monk-sql-server`.
  The disposable fixture creates an ordinary level-one monk, loads and equips a
  deterministic test glove, observes actual punches and player proc messages,
  removes/re-equips it, saves and restarts, then verifies staff inspection,
  actual weapon hits and non-monk exclusions. Fixture staff use `hit`, because
  `kill` at OVERLORD is the intentional instant-slay command. Only fixture state
  is promoted; no real account or DB is used. Both disposable DB and game roots
  are removed by the journey.
- The sanitizer runtime additionally checks every specialization and secondary
  monk admission through real `monk_superhit()`, one native dispatch per strike,
  fatal base-hit suppression, removal/extraction/relocation cancellation, invalid
  packed data, delayed class/flag/slot cancellation, busy suppression and retaining
  an already-started action when a separate weapon is later equipped.
- Remaining project work: the dependent authored-content pilot, its before/after
  runtime values, progression/spec/PvE/PvP samples and player identify check.
  Choose and record the owned-copy policy before any production activation.
  No production glove is enabled by the framework.

Researched 2026-11-08 against `b9bcce5e1c0081d373382c0e9cd3f18d48832b84`.
Companion inventory: [105 monk glove candidates, ascending ivalue](monk-proc.md).

## Recommendation

**Let explicitly marked gloves supply the proc for a monk's barehand strike, using the existing `weapon_proc()` dispatcher.** Keep the attack itself barehanded. Add one item flag and a small admission/dispatch path; reuse the existing spell encoding, native callbacks, messages, and optional item-action runtime.

The recommended initial rules are player monks, every monk specialization, primary gloves only, and one proc opportunity per qualifying strike. Include ordinary punches, successful barehand counterattacks, and the separate PvP pressure-point strike. Individual glove effects and their chances remain content decisions.

This gives builders a familiar way to add a spell proc to another glove without editing a vnum list in combat code. A genuinely custom effect can use the existing native callback mechanism.

## What the code already provides

- [`hit()`](../../src/combat/fight.c#L7873) distinguishes barehand attacks with `weapon == nullptr`. Its [final proc block](../../src/combat/fight.c#L8706) currently requires a weapon. Passing gloves as the attack's weapon would be wrong: that would interfere with attack type, damage dice, skills, poison, and other weapon-specific logic.
- [`weapon_proc()`](../../src/combat/fight.c#L8729) already accepts an object without requiring `ITEM_WEAPON`. It chooses either packed spells or the object's assigned callback with `CMD_MELEE_HIT` and the actual victim pointer. Those are alternative routes, not two procs to run together.
- [`melee_proc_target()`](../../src/specs/specs.object.c#L101) already accepts an object worn by the attacker. A glove callback can use it without changing the event or payload format.
- [`GET_CLASS(ch, CLASS_MONK)`](../../src/core/utility.c#L5060) includes the primary and secondary class. Dragon, Snake, and Chi are [specializations of `CLASS_MONK`](../../src/core/structs.h#L2410), so the dispatcher needs no specialization switch.
- [`monk_superhit()`](../../src/combat/fight.c#L11334) bypasses `hit()`. The [attack scheduler](../../src/combat/fight.c#L10441) substitutes this pressure-point strike for two normal attack opportunities against players. Hooking only `hit()` would omit it.
- [`MonkRiposte()`](../../src/combat/fight.c#L9680) already calls `hit(..., nullptr)`. It will inherit the normal hook. Snake's [`monk_critic()`](../../src/combat/fight.c#L6999) is part of a strike's resolution and must not receive a second proc dispatch.
- The 314 hand-slot records from the inventory were rechecked against the current source: all are unchanged, and all have zero `value[5..7]`. This is evidence that packed glove spells would be new content, not evidence that every native glove callback should suddenly receive melee-hit events.

## Gameplay contract

The framework implements these rules. Content activation and balance remain in the pilot.

1. **Who:** `IS_PC(ch) && GET_CLASS(ch, CLASS_MONK)`. This includes unspecialized monks, Dragon, Snake, Chi, and characters with monk as a secondary class. NPCs and pets do not gain offensive glove procs in this player-balance change. Existing glove periodic and defensive behavior retains its own rules.
2. **Which attack:** the actual strike is barehanded. An actual weapon hit uses its weapon proc only. Do not add another strength, weight, martial-arts rating, or free-hands requirement: the existing equipment and attack rules already apply those consequences. A held item or shield can reduce attack opportunities without creating a separate glove eligibility rule.
3. **Which gloves:** only the pair equipped in `WEAR_HANDS`, explicitly opted in as described below. No inventory scan, other armor slots, or fallback to `WEAR_HANDS_2`. Four-handed races get one source and one opportunity, not two. A glove such as 83505 can still participate when worn in the primary glove slot.
4. **When:** once when a qualifying strike reaches its post-damage proc point and both participants remain valid in the original room and height. Misses, attacks stopped before that point, lethal base hits, and interrupted/relocated attacks do not proc. Match existing weapon-proc contact semantics; do not add a new requirement that final HP loss be positive. Armor, shields, and immunity can reduce a resolved hit's damage.
5. **Pressure-point strike:** one opportunity after `monk_superhit()` resolves and both participants survive. Its cost of two normal attacks does not grant two rolls. Preserve the function's existing return/hit-count behavior when damage ends the fight.
6. **Other attacks:** barehand ripostes and legitimate additional `hit()` attacks get their own opportunity. Do not hook `melee_damage()` globally: kicks, spell damage, retaliation damage, and Snake's extra pressure-point damage would otherwise become additional proc sources. The existing vampiric-touch early return in `hit()` also remains an early return; it does not reach this proc point.
7. **Specializations:** identical admission and chance rules. Any later spec-specific effect belongs in that effect's implementation and balance review, not in the common dispatch path.

## One explicit item opt-in

Add `ITEM2_MONK_PROC` to `extra2_flags`. At this baseline, `BIT_20` is the next unused defined bit in that flag family; verify it again before implementation. Keep existing numeric flag assignments stable.

A valid proc glove is an `ITEM_ARMOR` or `ITEM_WORN` object with `ITEM_WEAR_HANDS` and `ITEM2_MONK_PROC`. Put that small object predicate beside the existing helpers in [`objmisc.h`](../../src/item/objmisc.h). It has actual consumers in combat, valuation, inspection, and delayed-action validation.

The flag is needed because “has a native callback” does not mean “intended to proc on monk punches.” Existing gloves may have periodic, defensive, command, or set callbacks. Making every glove receive a new event can revive dormant behavior. The flag makes each addition deliberate, including on shared-class equipment such as 5817.

Register its name in [`extra2_bits`](../../src/core/common.c#L497). **That array is positional and currently stops at bit 17 even though `defines.h` defines bits 18 (`ACCOUNT_BOUND`) and 19 (`ENHANCED`).** Add the correctly positioned entries for those existing bits before the bit-20 entry; appending `MONK_PROC` directly would name the wrong bit. The [area editor shares `common.c`](../../areas/de/src/Makefile#L41), so do not create another flag table.

Use the current object format and stored flag word. No new object type, schema column, event ID, class skill, character timer, or central glove-vnum registry is needed. `ITEM2_MAGIC` remains a separate decision: opting into a proc must not silently change barehand weapon-immunity handling.

### Ordinary spell effects

Use the existing packed weapon fields on an opted-in glove:

- `value[5]`: up to three spell IDs, packed in three-digit groups. The low group is the first slot. The existing high-digit mode selects one spell instead of the whole bundle.
- `value[6]`: spell level, with the same fixed-level semantics as weapons.
- `value[7]`: denominator of the existing one-in-N proc roll.
- `_char_msg`, `_victim_msg`, `_room_msg`: existing optional extra-description messages.

For a first glove, prefer one ordinary, single-target damage spell and its existing messages. A denominator of 30 means one chance in 30 **qualifying strikes**, not one chance in 30 combat rounds; that is an encoding example, not a proposed balance value.

Keep new bundles contiguous, with real supported spell IDs, a valid positive spell level, and a positive denominator. The legacy dispatcher has a deliberately preserved sparse-slot counting quirk and reverse cast order; do not repair that behavior as part of this feature. Before dispatch, reject malformed new glove configurations such as negative packed values or a populated packed spell with a nonpositive level/denominator; do not let invalid packed content accidentally select the native fallback. Add focused validation for the opted-in content rather than a new general item-definition system.

### Custom native effects

Bind a named callback in [`specs.assign.c`](../../src/specs/specs.assign.c), as for existing weapons. Keep `value[5] == 0` so the existing dispatcher chooses that callback. The callback uses `melee_proc_target()`, owns its chance and effects, and can continue handling its existing periodic/defensive events separately.

Do not combine a populated packed proc with a native melee effect and expect both to run. Do not copy a weapon callback onto gloves without checking its wield-slot assumptions, weapon-value interpretation, messages, lifetime handling, and other events. Give new callbacks the appropriate [`get_ival_from_proc()`](../../src/economy/tradeskill.c#L2844) contribution.

Initial effects should not call `hit()`, `pv_common()`, or otherwise manufacture further melee attacks. This keeps proc chains out of the initial balance work. That is a content constraint, not a claim that the existing engine prevents every possible recursive effect. A future extra-attack proc needs its own bounded chaining design and proof; it does not justify a new global recursion framework now.

## Combat integration

Keep the implementation local to `fight.c`, using the existing [`attack_continuation`](../../src/combat/attack_continuation.h) contract. Although its field is named `weapon`, the implementation can [capture and validate an object in any equipment slot](../../src/combat/attack_continuation.c#L57).

Use a small capture/dispatch pair with two real callers:

1. Before damage resolution, capture an eligible player's primary glove and the actual target using `begin_attack_continuation(ch, victim, gloves, WEAR_HANDS)`. If the attack or item does not qualify, keep an empty context. Capture after any target redirection, so a grapple misfire procs against the character actually struck.
2. At the proc point, call `check_attack_continuation()`. Recheck the class/item opt-in on the returned live objects, then call `weapon_proc(gloves, actor, target)` once. This prevents a glove removed, replaced, extracted, or swapped during damage from supplying the proc for that earlier strike.
3. In `hit()`, use the new path only for `weapon == nullptr`, at the existing final weapon-proc stage. Leave the actual weapon branch and its pet exception intact. Do not assign the gloves to the `weapon` variable.
4. In `monk_superhit()`, capture before `melee_damage()`, examine its damage result, and dispatch only when it reports `DAM_NONEDEAD` and the continuation remains valid. Then return using the current hit-count contract.

The new dispatch is terminal at those call sites: do not dereference the participants or gloves after an effect that can kill, extract, or move them. Keep callback return values separate from hit success; the existing `weapon_proc()` boolean is not a safe “victim survived” signal. Native callbacks and multi-effect execution must also stop before using invalidated state internally. Reuse the existing continuation/lifecycle machinery for any demonstrated gap reached by the selected effects.

Do not put the dispatch in `calculate_attacks()` or the outer combat loop. Those know attack opportunities, not whether a particular blow reached the proc point, and they would miss counterattacks that enter `hit()` separately.

## Reuse the existing item-action route

Packed spells already pass through [`selected_packed_weapon_action()`](../../src/item/weapon_actions.c#L314). The checked-in properties have `itemActions.enabled=0` and `itemActions.weapons.enabled=0`, so the default route is immediate legacy execution. Runtime settings may differ.

Keep that routing intact. When existing weapon item actions are enabled, a qualifying offensive packed glove proc should use the same windup, mana settings, one-pending-action-per-item rule, cancellation, and original-target behavior. The [runtime tracks an equipped source's actual slot](../../src/item/item_actions.c#L522), so it already supports gloves. No `monkActions` subsystem or separate configuration namespace is needed.

Extend the packed adapter's validation narrowly for non-weapon glove sources: the actor must still be a player monk, the source must still be opted in, and it must still occupy `WEAR_HANDS`. Class changes, flag removal, and switching to the second glove slot must cancel pending glove actions. Apply that validation based on the glove source category, not only on the flag still being set, or clearing the flag could bypass the check. Preserve ordinary weapon validation.

Qualification as a barehand strike is decided when the action starts. A scheduled effect need not invent a later “current attack” to validate; equipping a weapon afterward prevents future glove opportunities on weapon hits, while the already-started action follows its source/class cancellation rules. A suppressed or busy scheduled action must not fall back to an instant cast. Purely beneficial packed bundles retain the existing immediate behavior.

## Value, inspection, and saved items

These are part of a usable feature, not a reason to introduce another framework.

- **Runtime ivalue:** [`itemvalue()`](../../src/economy/tradeskill.c#L2038) currently credits packed spells only on items with `ITEM_WIELD`. Extend that eligibility to valid opted-in gloves, using the same formula and ensuring the denominator is positive. Keep the gloves' armor valuation. Do not award a flat bonus merely for having the flag, and do not turn the object into a weapon to get a value.
- **Editor ivalue:** the area editor has its own [equivalent calculation](../../areas/de/src/obj/object.cpp#L1081). Make the same narrow eligibility change there; avoid a separate valuation-refactoring project.
- **Staff inspection:** [`stat`'s proc explanation](../../src/cmd/actwiz.c#L2032) currently lives under `ITEM_WEAPON`. Show the opted-in glove's spell level/chance or native callback and its monk/primary-slot scope as well. Keep the armor stats. The generic [`setbit` fields](../../src/cmd/actset.c#L917) already expose `extra2` and `val5..val7`.
- **Player inspection:** add a clear “activates on a monk's barehand strikes when worn on the primary hands” description. Preserve existing information access: [`identify`](../../src/magic/magic.c#L14475) reveals packed spell names to level-56+ conjurers; do not silently expose weapon proc details to everyone while adding glove support. Factor only the small shared display code actually needed by both item types.
- **Encrusting:** `do_encrust` clones armor and worn items into vnum 1251, keeps `extra2_flags`, and overwrites `value[5..7]` with the jewel's spell at 1/30. Left alone, it would replace an opted-in glove's authored proc with a crafter-chosen one, and the copy would fall outside any update of the selected vnums. Refuse to encrust opted-in gloves.
- **Persistence:** the fields already exist, but template changes are not guaranteed to reach owned copies. [SQL restoration](../../src/sql/sql_player.c#L1055) restores the instance's extra2 flags; [world recovery](../../src/world/world_recovery_pipeline.c#L1493) restores saved values and flags. Prove fresh loading and save/reload on both supported backends. Before enabling production content, explicitly choose and document whether existing copies are updated. If retroactive coverage is intended, prepare a targeted, rerunnable content update for the selected vnums that preserves UIDs, ownership, enhancements, and unrelated flags/values. Do not add a per-hit template overlay or assume reboot alone refreshes old copies.

## Small implementation sequence

### 1. Framework and fixture proof

Implement the opt-in, the two attack hooks, delayed validation, valuation, and inspection. Use a test-only glove with a deterministic effect to prove both packed and native routing. Enable no production glove as a side effect of introducing the flag.

Expected files:

- `src/core/defines.h`, `src/core/common.c`, `src/item/objmisc.h`: flag and shared object eligibility.
- `src/combat/fight.c`: capture/dispatch helpers and the two call sites.
- `src/item/weapon_actions.c`: glove-specific validation within the existing packed adapter.
- `src/economy/tradeskill.c`, `areas/de/src/obj/object.cpp`: packed-glove valuation.
- `src/cmd/actwiz.c`, `src/magic/magic.c`: inspection.
- Focused tests and the relevant monk/builder help explaining the final behavior.

### 2. Small content pilot

Select a few gloves from [the inventory](monk-proc.md), keeping their current stats visible beside the proposed effect and recalculated ivalue. Useful review anchors are 500110 (explicit monk identity), 44424 (punching identity), 76052 (narrow melee class list), and 5817 (Chaos monk main gloves). These are not a claim that their acquisition order matches their ivalue.

Use simple effects first. Add the flag and packed fields to the selected authored `areas/obj/*.obj` records; native callback files and bindings are needed only for a selected effect that actually requires custom code. Preserve current native-proc/artifact benchmarks such as 1210 until separately evaluated. Keep the 5813-to-5817 weight increase and non-MAGIC candidates visible during balance review.

Measure actual qualifying strikes and proc activations at low, middle, and late levels; compare Dragon, Snake, and Chi, plus PvE and PvP. High attack rates, haste, combat speed, and ripostes all increase opportunities. For an immediate proc with chance `1/N`, the expected activations from `H` eligible strikes are `H/N`; expected extra damage per eligible strike is approximately the proc's mean effective damage divided by `N`. Scheduled actions, resisted spells, and control effects require direct measurement. Tune each glove's chance/effect rather than adding a global cooldown, proc-per-minute system, or spec multiplier in advance.

## Proof required before shipping implementation

Extend the existing [weapon-action runtime tests](../../tests/async/test_weapon_actions_runtime.py) for shared dispatcher behavior. Add focused executable coverage of the actual new combat hooks; helper-only assertions do not prove that a barehand strike reaches them.

- Plain monk, all three specs, and secondary-class monk can proc; non-monks, NPCs, pets, unmarked gloves, inventory gloves, other slots, and second-pair-only gloves cannot.
- An actual weapon hit never also procs gloves. Ordinary punches and barehand ripostes dispatch once. A pressure-point superhit dispatches once despite consuming two attack opportunities. Snake's extra pressure damage does not double-dispatch. Misses, intercepted attacks, fatal base hits, and the vampiric-touch early return do not dispatch.
- Both glove slots filled still produce one source. Removing, replacing, or extracting the selected gloves during the strike cancels their opportunity. A target redirected before the hit receives the proc; a later opponent change does not retarget it.
- Packed chance boundaries, fixed level, offensive/self targets, bundle selection/order, and native fallback work through the existing dispatcher. Malformed new glove data fails closed. Existing weapon parity tests continue to pass.
- Lethal procs, reflected effects, movement, height changes, actor/target extraction, and glove extraction are exercised under ASan/UBSan. Preserve [continuation](../../tests/async/test_attack_continuation.py), [combat lifetime](../../tests/async/test_combat_start_lifetime.py), and [native event guard](../../tests/async/test_item_proc_guards.py) coverage where touched.
- With item actions enabled, gloves schedule from `WEAR_HANDS`, cancellation occurs on source/class/flag changes, and busy/suppressed starts do not instant-cast. With them disabled, immediate behavior works. Test both paths even if production currently uses only one.
- Ivalue increases for the actual packed effect, does not increase for an empty marker, and agrees with the editor for the fixtures. Flag round-trips preserve bits 18 and 19. New and persisted item instances retain the intended configuration on both backends.
- A local gameplay journey proves an equipped monk's real attacks can trigger the proc, and unequipping the gloves stops it. Repeat with a non-monk and an actual weapon. Verify player messages and staff inspection alongside the journey.

Run `./scripts/format.sh --check`, the focused tests, and `make -C src` after C/C++ implementation; build the touched area editor with `make -C areas/de/src`. Build and test outputs stay under `bin/`. The baseline research needed no build; implementation results are recorded above.

## Scope kept small

The outcome is weapon-style effects on explicitly selected monk gloves throughout progression. The existing dispatcher is the framework. The new pieces supply admission, the missing barehand call sites, and the existing tools' awareness of those effects.

There is no new proc language, registry, item type, event bus, spell executor, timer service, or specialization hierarchy. Existing weight and barehand damage formulas are outside this change. Production effect choices, values, and treatment of already-owned copies must be recorded in the content pilot; they cannot be inferred from the candidate catalog alone.

Plan verification: read the owning combat, class, item-action, valuation, editor, inspection, and persistence code; rechecked all 314 catalogued glove records against current source. That was the research baseline; current implementation and proof are recorded in the execution / handoff section above.
