# Issue #812: owner-based random treasure for pet kills

Status: planned; no gameplay changes implemented.
Date: 2026-11-08.
Issue: [#812 — Pet finishing blows ignore the owner's luck and Hardcore random-drop bonus](https://github.com/LuminariMUD/Duris/issues/812).
Source inspected: local `master` at `628dfce559c81c484d88dcf139e93c7a2569fe7d`.

## Outcome and scope

A qualifying pet finishing blow should receive the same random equipment and
material reward calculation as its owning player killing that NPC at the pet's
location. Use the owner's current luck, Hardcore status, neutral-side status,
and level. Keep the existing two independent rolls and put their results on the
dying NPC so normal corpse handling delivers the loot.

This plan also explicitly makes generated-item scaling and finder-dependent
generation use the owner. The pet's level must neither bypass an owner's
level-gap restriction nor reduce the owner's eligible rewards. The combat
location remains the actual killer's location, including when the owner is
elsewhere.

The work covers `random_equipment_kill_drop()` and its roll/generation paths.
It does not change XP or kill attribution elsewhere, group rewards, recipes,
dragon scales, soul shards, drop rates/configuration values, pet ownership
rules, or corpse/loot access. No migration or production operation is needed.

## Verified current behavior

- [`die()`](../../src/combat/fight.c) calls
  `random_equipment_kill_drop(killer, ch)` before corpse handling. Other special
  drops have separate paths and are outside this change.
- [`random_equipment_drop.c`](../../src/item/random_equipment_drop.c) admits a
  living player or `IS_PC_PET` killer against an NPC victim. It already resolves
  `credited_killer` for salvage messages, but passes the actual killer to both
  `check_random_drop()` calls and to equipment/material generation.
- `check_random_drop()` uses that actor's room for guild/town restrictions and
  that actor's level, current luck, neutral-side status, and Hardcore flag for
  reward calculations. `IS_HARDCORE` requires a PC, so a pet cannot receive its
  owner's multiplier. The shipped multiplier is 1.50.
- [`IS_PC_PET`](../../src/core/utils.h) means an NPC with an `LNK_PET` link to a
  PC; `GET_MASTER` reads that link. There is no same-room or same-group
  requirement in this random-drop path. Do not import the separate PvP rules.
- [`create_random_eq()`](../../src/item/random_equipment.c) uses the finder for
  luck-dependent naming, owner keywords, messages, and the zone obtained from
  `finder->in_room`. Its explicit finder level affects material quality and
  named-item chance. `create_material()` uses finder level for quality and can
  apply an Alchemist resource benefit/message to a PC finder.
- [`test_random_drop_owner_message.py`](../../tests/async/test_random_drop_owner_message.py)
  explicitly requires pet-based generation. The executable
  [`test_random_equipment_golden.py`](../../tests/async/test_random_equipment_golden.py)
  also freezes four pet-kill cases with deliberately different owner stats and
  an owner standing in a guild room. Those expectations need a deliberate,
  narrowly reviewed behavior update.

The issue's reported low-drop hunting session does not establish its cause:
pet finishing blows and whether materials were counted were not confirmed.
The implementation should be proven with controlled cases, not that sample.

## Behavior decisions

1. **Owner selection:** use the existing direct PC master of `IS_PC_PET`.
   Ordinary player kills use the player. Unowned NPCs and NPC-owned followers
   remain rejected by the kill-drop handler. Do not infer ownership from
   grouping, names, class, or summon flags, or traverse an ownership chain.
2. **Chance and eligibility:** use the owner's current `GET_C_LUK`, Hardcore
   flag, neutral race-war side, and level for both rolls. Owner level governs
   the maximum level gap, low-level formula, and low-level bonus. With the
   default gap of 10, a level-32 owner remains eligible against level 22 and is
   rejected against level 21 regardless of the pet's level.
3. **Neutral behavior:** retain the existing early unscaled neutral win, after
   eligibility checks, using the owner's side. Do not multiply that early win
   by Hardcore, roll percentages, or the loot difficulty dial. If it fails,
   the ordinary owner-based calculation follows in the existing RNG order.
4. **Location and victim:** keep guild/town checks tied to the actual killer's
   room and keep the existing victim EXP, shopkeeper, level, and elite checks.
   Named equipment's zone, zone origin, and zone-dependent affects also come
   from the actual killer's room. An owner elsewhere must not change these.
5. **Generation:** pass the owner and owner level to equipment/material
   generation; keep victim level as the source level. Owner luck determines
   named-item chance, owner identity supplies owner keywords, and existing
   finder messages go to the owner. An eligible Alchemist owner receives the
   existing material-generation benefit exactly as on a direct kill, with its
   existing roll and amount. Preserve the level-zero equipment-to-material
   fallback, but evaluate its level against the owner.
6. **Admission and delivery:** preserve the existing actual-killer-alive rule;
   add no owner-alive, owner-present, or grouping requirement. Keep one attempt
   per existing equipment/material branch, the one-in-26 stone substitution,
   victim inventory placement, and existing salvage wording/message cadence.
   Do not add a second reward pass for the owner.

## Implementation

### 1. Separate reward attributes from the combat location

In `src/item/random_equipment_drop.c`:

- Keep `check_random_drop()` receiving the actual killer. After its existing
  null guard, select a local reward actor with the existing `IS_PC_PET` /
  `GET_MASTER` logic. Keep room checks on the original actor; read level,
  current luck, neutral-side status, and Hardcore status from the reward actor.
  Preserve formula arithmetic, rounding, configuration reads, and RNG order.
- Reuse the handler's existing `credited_killer` for generation, its finder
  level, and messages. Keep the two calls to `check_random_drop(killer, ...)`,
  so each retains the original combat location. Leave victim placement and
  admission checks intact.

In `src/item/random_equipment.c` and `src/item/random_equipment.h`, give
`create_random_eq()` a trailing optional source-room argument, defaulting to
`NOWHERE` to mean the existing finder-room behavior. The kill-drop handler
passes `killer->in_room` explicitly while passing the owner as finder. Use the
effective source room only to obtain the generation zone; finder-dependent
attributes/messages still use the finder. Existing staff, quest, and generated
NPC callers retain their current behavior without call-site changes.

This small argument is needed because the owner and kill location can differ.
Do not temporarily move/copy a character to substitute stats or rooms. No
general reward context, ownership service, new config switch, or alternate
drop formula is needed. `create_material()` needs only corrected arguments.

### 2. Prove the change in the existing executable harness

Extend `test_random_equipment_golden.py`, which already compiles the production
modules with real RNG/configuration and ASan/UBSan. Reuse its character, room,
pet-link, message, and object fixtures. Add behavioral assertions outside the
frozen-output cases, recording enough object state to compare material tier,
equipment values/affects, names, zone origin, and recipient. Do not replace
production chance calculations with a test copy of the formula.

For each comparison, reset equivalent victim/state fixtures and the RNG seed.
Compare a direct owner kill at the pet's location with a linked-pet kill:

- Deliberately different owner/pet luck, including owner luck 160 versus pet
  luck 60, then reverse them. Changing only pet luck/level must not change the
  owner's reward outcome or subsequent RNG sentinel. Select deterministic
  seeds that demonstrate owner luck changes outcomes for each drop branch.
- Owner Hardcore on/off, with seeds that expose the bonus in equipment and
  material rolls. Direct and pet kills must agree under each setting; a flag
  placed on the NPC must not grant a player bonus.
- Owner/victim gaps of 10 and 11, with pet levels on the opposite side of the
  boundary. Cover owner levels 14/15 and 25/26 to exercise both low-level
  transitions and include the reported level-32 owner versus level-34–41 mobs.
- Neutral and non-neutral owners with deliberately different pet sides.
  Exercise both the neutral early win and its failure/fallthrough; verify the
  early win's unchanged scaling and RNG behavior.
- Equipment only, material only, both, neither, and stone substitutions using
  deterministic cases. Confirm correct owner-derived quality/naming and
  Alchemist effects. Count at most two inserted objects and no duplicate
  salvage messages; distinguish existing
  named-item guidance and Alchemist messages from salvage feedback.
- Owner in another room/zone, including a guild or town, while the pet fights
  in an eligible room. Compare against the owner fighting at that room. Also
  test a pet fighting in a guild or town while the owner stands elsewhere;
  cover town victim levels 25/26. Keep named-zone text, origin, and effects tied
  to the pet's location, never the remote owner.
- Existing rejection cases: unowned NPC, NPC-owned follower, PC victim, dead
  actual killer, no-EXP victim, and shopkeeper. Rejected cases create no items,
  messages, or RNG draws. Preserve eligibility of a linked pet with a remote
  owner without adding a grouping restriction, and preserve the existing
  absence of an owner-alive requirement.

First demonstrate failure of the new ownership assertions on the original
code. Update only the four intentionally changed pet-kill rows and their RNG
sentinels in `tests/fixtures/random_equipment_golden.txt` and
`tests/fixtures/random_equipment_rng_golden.txt`. Review each changed row
against the owner-based contract; do not regenerate unrelated golden cases.
Update the harness's frozen-fixture documentation to record this intentional
behavior exception. All direct-player, standalone generation, material, and
stone golden cases must remain unchanged.

Update `test_random_drop_owner_message.py` to remove its requirement for
pet-based generation and retain its death-path wiring/message checks. The
executable assertions above are the proof of reward behavior.

### 3. Document and verify the complete path

Update `docs/reference/RANDOM_EQUIPMENT.md` and the pet-drop section of
`docs/testing/REGRESSIONS.md` with owner stats, owner level/neutral semantics,
kill-location behavior, generation effects, and actual test evidence. Clarify
the relevant comments in `lib/random_equipment.cfg` and `lib/hardcore.cfg`
without changing values.

Run the focused checks and required build during implementation:

```sh
python3 tests/async/test_random_drop_owner_message.py
python3 tests/async/test_random_equipment_golden.py
python3 tests/async/test_random_equipment_config_contract.py
python3 tests/async/test_random_equipment_config_runtime.py
python3 tests/async/test_hardcore_config_runtime.py
python3 tests/async/test_difficulty_dials.py
make -C src
./scripts/format.sh --check
git diff --check
```

Keep new compiled/runtime artifacts under `bin/`. Perform a focused local/dev
gameplay check with a real linked pet landing the finishing blow: verify the
owner receives the existing salvage message and generated loot reaches the
victim's corpse once. Use disposable fixtures and controlled local drop
settings where needed; do not modify production or committed rate values.
Keep deterministic probability proof in the harness rather than relying on a
small live kill sample. Record the exact checks performed and any unavailable
gameplay verification; CI completion is not a prerequisite.

## Completion criteria

The fix is complete when direct and pet kills agree for the same owner,
victim, combat location, configuration, and RNG state; pet stats cannot change
the reward; owner Hardcore/luck/level/neutral behavior is demonstrated for
both rolls; generated loot uses the owner while retaining the kill zone; and
admission, messages, corpse delivery, and unaffected golden cases remain
correct. Deliver the implementation, focused tests, and documentation as one
coherent change. Deployment is separate.

Planning validation: issue and owning source/test paths were inspected;
document links and whitespace were checked. No build, executable regression,
gameplay test, or deployment was performed as part of writing this plan.
