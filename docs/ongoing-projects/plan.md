# Issue #368 — restore authored legacy object traps

Status: implementation in progress, 2026-10-25. Editor chunk published in
[PR #375](https://github.com/LuminariMUD/Duris/pull/375). Saved-copy compatibility is
implemented and locally qualified on its dependent branch; runtime effects, authored
content changes and loaded gameplay qualification remain pending.
Issue: [#368](https://github.com/LuminariMUD/Duris/issues/368).
Target branch: `branch/issue-368-legacy-traps`.
Code inspected: [`e1efb9bc0779e8b6615353c5672e29f21c6bb7a8`](https://github.com/LuminariMUD/Duris/commit/e1efb9bc0779e8b6615353c5672e29f21c6bb7a8).
The implementation starts from that revision plus plan commit `9b1f97509`.
Subsequent movement of master is not evidence of implementation or qualification.

The [selected design](https://github.com/LuminariMUD/Duris/issues/368#issuecomment-6398324337)
records the owner's delegated behavior choices; the
[earlier investigation](https://github.com/LuminariMUD/Duris/issues/368#issuecomment-6397485715)
records historical evidence and its limits. Treat the selected values as requirements,
but use the owning source and actual journeys to establish how they must be implemented.
The previous contents of this pathname are preserved byte-for-byte in
[plan-issue-264.md](plan-issue-264.md).

## Outcome, boundaries, files and proof

- **Outcome:** resolve every one of the 61 active authored definitions: 55 generic
  traps with defined effects, six retired T records with their retained behavior;
  implement the seven local creature profiles, 17 T-field repairs and four container
  flag repairs. Fresh instances and recognized saved copies must behave consistently
  without restoring spent charges. Invalid configurations remain visible and inert.
- **Non-goals:** no general trap framework, configurable target schema, new NPC
  prototypes, global direction/data migration, changes to the existing 0–8 effect
  balance, database schema migration, production operation, deployment or full burn-in.
  This branch begins with a documentation-only commit; implementation follows in focused PRs.
- **Files:** the owners in the evidence/phase sections below, the 31 authored object
  inputs represented by the manifest (only files whose content changes need editing),
  focused existing tests plus the explicitly proposed tests, and builder/regression
  documentation. Preserve unrelated changes and the existing special procedures.
- **Proof:** independent authored/generated/loaded inventories, real effect and command
  execution, sanitizer lifecycle tests, round trips through actual restoration owners,
  MariaDB and flat-file gameplay/restart journeys, and a qualified full generated-world
  boot. A silent warning log, helper-only test or CI status is insufficient.

## What the current code actually establishes

| Finding | Owning source and consequence |
| --- | --- |
| The inventory is still 61, with type counts 9:13, 10:2, 11:6, 12:9, 13:2, 14:6, 15:13, 16:10. | Independently reparsed the files named by [areas/AREA](../../areas/AREA); all old tuples match the issue. Use [make_obj.c](../../areas/src/obj/make_obj.c)'s active-input selection, not a glob over alternate object files. |
| Runtime and load diagnostics independently hard-code 0–8. | [trap.c](../../src/combat/trap.c), `trap_damage_supported`; [db.c](../../src/world/db.c), object T parser. Updating the switch alone leaves false boot diagnostics; widening the parser alone hides inert traps. |
| Staff tools also stop at slash. | `do_trapstat` and `do_trapset` in trap.c require matching names, validation, flags and help. |
| “get/put” is not currently a complete call path. | `checkgetput` is called by two pickup paths in [actobj.c](../../src/cmd/actobj.c). `put()` has an `if (o_obj) /* Trap check */` comment but no trap call. The selected OBJECT behavior needs an actual put hook for restored types, with single/bulk caller safety. Do not claim the existing test proves putting is covered. |
| OPEN runs after opening; movement checks run before movement costs/publication. | [actmove.c](../../src/cmd/actmove.c), `do_open` and `do_simple_move`. Preserve that ordering. A glyph cannot simply return false after arbitrary spell side effects. |
| Pointer presence is not proof of a live actor. | `IS_ALIVE` dereferences the pointer. Reuse `find_character_by_runtime_id`, `find_live_object(expected, uid)`, and the identity/room checks exemplified by `get_can_continue`. Snapshot identities, not saved linked-list next pointers, across effects. |
| Allocating an NPC has side effects before room placement. | `read_mobile` registers the character, increments the prototype count, schedules events and calls [convertMob](../../src/mob/mobconv.c). `char_to_room` can refuse placement or extract an NPC on an invalid destination. Allocate/rollback a batch deliberately; raw .mob HP/damage are not final runtime stats. |
| Spell reuse has important semantics. | [magic.c](../../src/magic/magic.c): low-level self-dispel returns early, high-level self-dispel bypasses saves; harm carries a nonlethal flag; minor paralysis uses its level argument for duration. [affects.c](../../src/magic/affects.c): Stun owns its racial/elite checks and two-stage fear save. Use an independent caster, not the victim. |
| Prototype repair is insufficient for restored copies. | Stored fields overwrite prototypes in [player_load_items.c](../../src/player/player_load_items.c), [sql_player.c](../../src/sql/sql_player.c), both binary restore paths in [files.c](../../src/core/files.c), [world_recovery_pipeline.c](../../src/world/world_recovery_pipeline.c), and [account_reward_snapshot.c](../../src/account/account_reward_snapshot.c). Normalize after the final stored-field application, before use/publication. |
| The legacy binary writer notices only charge differences. | files.c selects `O_U_TRAP` by comparing `trap_charge` alone, although its payload stores all four fields. Compare all four so a custom mask/type/level is not lost on a later save with unchanged charges. The existing wire format already accommodates this. |
| Container state is also restored. | Player/world snapshots overwrite `value[]`. “Start closed” describes fresh prototypes, not permission to reclose an already-open saved container. See the restore rules below. |
| Existing tests are useful but narrower than acceptance. | `test_unsupported_trap_damage.py` executes extracted dispatch/check functions with spell stubs. `test_get_trap_lifecycle.py` executes pickup finalizers with synthetic trap effects. They do not prove native spell defenses, put hooks, NPC conversion, full-world loading or the new saved-copy repair. |

The editor's south/west/east bit assignments differ from the runtime. Keep the runtime's
N=8, E=16, S=32, W=64, U=128, D=256 convention. Correct the listed content and the editor's
labels/constants consistently; do not rewrite unrelated area files.

## Behavior to implement

Effective level for restored types is 25 for zero, otherwise the positive value capped at
100; reject negative levels without consuming charges. Legacy 0–8 encoded damage dice
remain unchanged. Use the existing vnum-14 temporary trap-caster pattern, with effective
caster level and ordinary converted prototype attributes, never player equipment or class
bonuses. Its registration, events, retaliation, extraction and cleanup require real tests;
its nominal HP is not a safety guarantee.

| Type | Contract |
| --- | --- |
| 9 | Existing character-targeted dispel: ordinary removable-affect iteration, saves, resistance and non-dispellable protections. |
| 10 | A local hostile rift creates the specified NPC. No portal, player relocation or global character selection. It remembers the triggering character; normal later NPC updates decide aggression, rather than starting combat synchronously in the gate handler. |
| 11 | Create the specified local NPC batch and start its normal attack on the triggering character. |
| 12 | Existing wither at effective level, including saves, construct/undead behavior, stat effects and existing-affect exclusions. |
| 13 | Existing harm: pre-mitigation 100 on a successful save, otherwise 200, with its nonlethal flag and no player Zealot bonus. |
| 14 | Existing poison with positive level, including its normal random poison family, resistance, save, immunity and durations. |
| 15 | Minor paralysis. Caster stays level L; pass duration-level `clamp(floor(L/5),4,16)` to the existing spell, yielding 3–12 seconds. Keep resistance, paralysis immunity, Freedom of Movement, save modifier 0 and break on external damage. Do not apply/extend it when either minor or major paralysis already exists. |
| 16 | Ordinary magic resistance, then `Stun(..., true)` with full duration `clamp(floor(L/20),1,4) * WAIT_SEC`. Keep native immunities, existing-stun rejection, fear saves and half-duration outcome. |

Mortal PCs and PC pets are eligible; exclude staff, ordinary NPCs and the temporary caster.
A ROOM spell snapshots eligible character identities in the source room and revalidates
each before applying it. A valid spell activation spends one positive charge total even
on a save, immunity or existing effect. Invalid configuration/caster creation failure does
not spend a charge. Zero is always disarmed; -1 is unlimited. For restored types, MULTI
means unlimited only while charge is nonzero; do not revive a disarmed MULTI trap.

### Creature profiles

Lookup by the explicit **(object vnum, type)** pair. Unlisted combinations are invalid,
diagnosed and charge-preserving; there is no guessed fallback or reuse of object value
slots as a target schema.

| Object | Type | NPC | Batch | Initial charges | Room cap for NPC vnum |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 41361 | 10 | 200 | 1 | 1 | 1 |
| 42290 | 10 | 200 | 1 | 1 | 1 |
| 32820 | 11 | 32861 | 3 | 1 | 6 |
| 32870 | 11 | 32861 | 3 | 1 | 6 |
| 32835 | 11 | 32861 | 1 | 1 | 6 |
| 32846 | 11 | 32871 | 1 | 1 | 1 |
| 41927 | 11 | 200 | 1 | 2 | 1 |

Use ordinary converted mob instances and ordinary rewards/lifecycle, without trap-level
rescaling, additional equipment resets, timers or a reward subsystem. Room caps include
all living instances of the NPC vnum. ROOM does not multiply the batch by population.
Preflight capacity for the entire batch, allocate before exposing the encounter, and clean
up a failed batch with no charge consumption. Commit the charge once the complete batch
has been placed; subsequent ordinary combat/death does not refund it. Revalidate identities
after callback-capable operations. No new placements for 32835/32846.

### Retirements and retained procedures

Remove only generic T data for 32831, 55022, 57567, 77721, 131215 and 131226.

- 32831 retains `pesky_imp_chest`: three imps once per chest instance, tracked by
  `value[3]`. 32833 retains that procedure **and** its distinct one-charge poison trap.
- 77721 retains `trap_tower1_para`, its upward trigger, existing exemptions and
  1-in-3 chance of five combat pulses of wait. Do not retune it to the generic stun cap.
- 55022 remains the decorative non-takeable display case.
- 57567 retains its quest-switch and ghost-librarian reset behavior; no new portable
  100-charge movement ward.
- 131215/131226 retain weapon spell data, messages, affects and mob equipment resets.

The special assignments are in [specs.assign.c](../../src/specs/specs.assign.c);
implementations are in [specs.shabo.c](../../src/specs/specs.shabo.c) and
[specs.hoa.c](../../src/specs/specs.hoa.c). Retiring T does not retire these procedures.

## Implementation sequence and proof gates

Unchecked boxes below remain future work. Keep each step reviewable; no placeholder test
should stand in for its stated behavior.

### Current handoff — 2026-10-25

Worktree: `/home/aiwithapex/projects/duris-issue368`; current branch
`branch/issue-368-trap-compatibility`, based on editor commit `0f83475c2` / PR #375
(`branch/issue-368-legacy-traps`). The primary checkout is unrelated and untouched.
Current `origin/master` remains the inspected `e1efb9bc0` base.

First chunk aligns editor EAST/SOUTH/WEST constants and flag-list indexes with runtime
N/E/S/W/U/D bits 8/16/32/64/128/256, and corrects the same labels in the builder guide.
Executing the actual `getObjTrapFlagsStrn` exposed an out-of-bounds read in its OPEN
separator handling (`strlen(strn - 1)`); the same chunk fixes that expression.
`test_legacy_trap_editor.py` executes all 4096 flag combinations under ASan/UBSan,
including exact east/west/open display checks, and checks the editor flag-list order.
The required formatting check exposed pre-existing whole-file formatting drift in
the three touched editor files. They are mechanically formatted to satisfy that gate;
behavior changes remain the three direction constants, flag-list order and OPEN index.

Ablation: keep the existing constants, flag list and formatter; change their owning
definitions rather than adding a translation layer or migrating unrelated authored data.
No runtime effect is enabled and none of the 61 authored trap records has changed yet.

Validation: `python3 tests/async/test_legacy_trap_editor.py` passed; `make -C src -j8`
passed (log: ignored `bin/issue368-evidence/build-mariadb.log`). Remaining proof belongs
to its affected implementation slice. Formatting and `git diff --check` pass.
Saved-copy chunk: `combat/trap_legacy.c/.h` owns the single 23-row compatibility policy
used after stored fields by the six restoration owners. The explicit vnum argument keeps
the policy independent of the global prototype registry; each owner supplies its validated
snapshot or loaded-object vnum. It preserves partial/spent/custom traps and special-proc
`value[3]`, limits only the five selected unlimited encounters, and adds CLOSEABLE without
CLOSED only to matching bones/urn copies. World normalization runs after its final values[]
overwrite. Binary unique-field detection **and stock grouping** now compare all four trap
fields; inspecting the writer exposed the second potential state-loss path.

`legacy_trap_manifest.py` freezes all 61 original/final tuples independently of runtime
policy. `test_legacy_trap_restore.py` exercises both real binary readers, the real writer,
SQL extra-row loading and actual reward JSON capture/application under ASan/UBSan for
all 61 profiles, charges -2/-1/0/1/2/100, individual custom mask/type/level edits, and
two load/save cycles. Container open/closed flags also round-trip through these owners.
Player graph hydration and framed world recovery have executable representative repairs,
including disarmed and retired state, final values[] ordering and preserved proc markers.
The existing world harness needed current boot-boundary includes/stubs to compile; that
fixture repair changes no server behavior.

Additional validation passed: `make -C src -j8`, `make -C src -j8 pfile`, flat-file
server build with `PERSISTENCE_BACKEND=flatfile BIN_ROOT=$PWD/bin/issue368-flatfile`,
`test_player_load_items.py`, `test_world_recovery_pipeline.py`,
`test_locker_container_weight_lifecycle.py`, `test_legacy_object_identity.py`,
`test_item_extra_descr_codec.py`, `test_player_item_snapshot_codec.py`, and
`test_spellbook_persistence_contract.py`. Build logs remain under
`bin/issue368-evidence/`. These native/synthetic boundary tests do not replace the
pending loaded gameplay/restart acceptance on both backends.

Ablation: the one small normalizer is required by six real owners; existing wire formats,
codecs and loaders are retained. No data rewrite, schema change, new restoration service,
or prototype-wide overwrite was added. Next: independent authored/generated content
checks and shared runtime/load validation, then real effect execution and command hooks.

### Runtime/content work in progress — 2026-10-25

Compatibility is published in [PR #377](https://github.com/LuminariMUD/Duris/pull/377),
head `26174bb1f`, stacked on #375. Current worktree branch is
`branch/issue-368-trap-effects`, now based on focused fixture dependency
[PR #383](https://github.com/LuminariMUD/Duris/pull/383), commit `8ed816523`, above #377.
The runtime/content/command checkpoint is being published while the remaining loaded
qualification is completed; it is not yet runtime acceptance.

Implemented so far: shared definition validation, fixed seven-profile lookup, native
spell dispatch, finite/MULTI charge boundaries, whole-batch allocation/placement rollback,
identity snapshots and caster cleanup; atomic trapset edits and trapstat names/flags;
17 authored tuple repairs, six retirements and four fresh container flags; item-on-put
hooks after permission/capacity checks; identity-safe bulk puts and safe slip/equipment
callers; and GLYPH continuation through the existing movement preflight before each next
matching trap. The per-attempt identity list prevents unlimited glyphs from firing twice;
ordinary 0-8 triggers keep their stopping behavior. Sneak learning is not repeated during
the new preflight loop.

Two traced lifecycle boundaries needed narrow support. `CHAR_RFLAG_TRAP_CASTER` is an
existing runtime-flag slot; raw damage forces nonlethal/no-XP flags on the temporary
caster so nominal prototype HP is not its safety mechanism. Gate memory has one runtime
identity in `npc_only_data` because ordinary PID memory cannot represent a triggering
pet; the normal memory update uses that identity with its existing safety/aggression
checks, rather than starting combat synchronously or adding a scheduler.

Passed: `test_legacy_trap_effects.py` executes the actual dispatcher, five native spells,
Stun and the ordinary memory update with controlled RNG/saves; durations, defenses,
duplicate controls, ROOM filtering, all seven profiles, capacity and batch failures,
PC/pet deferred gate aggression, and actor/caster/object extraction pass ASan/UBSan.
`test_put_trap_lifecycle.py` executes real single/bulk placement boundaries with denied
permissions, rejection and extraction of participants/siblings, including persistence
of earlier successful items. Existing unsupported/0-8, pickup lifecycle and empty-command
checks pass. `make world` and independent authored/generated inventory checks pass for
all 61 resolutions and four container flags. Current server builds have passed after
the integration edits; final builds are still required after the latest source changes.

Next required work: native movement/builder/special-procedure coverage, both-backend
loaded gameplay/save/restart journeys, exact loaded prototype/boot-log evidence,
retaliation/no-reward verification through the actual damage path, relevant regressions,
final formatting/build/diff review, and publication of this focused dependent PR.
Do not mark #368 resolved or the runtime slice review-ready from the native fixtures alone.

Native movement/builder and retained special-procedure checks now pass in the effects
fixture: unlimited glyph visitation, later blocking trap, control interruption, atomic
invalid builder edits, three imps exactly once per chest marker, and the unchanged five
combat-pulse tower wait with its staff exemption. Both loaded backends also verified all
61 exact fresh trap states through `stat trap` after full generated-world startup.
The first loaded fixture used the nonexistent `trapstat` alias, then a keyword collision
with the builder's starter book; numeric-vnum stringing fixed those fixture errors.
Room activity can emit unsolicited prompts, so the journey now uses an inventory response
as a read-only command barrier. Full scenario/save/restart completion remains pending.

The legacy flat-file lethal corpse journey now passes death, bystander damage, server
survival, reconnect, custody and spent-state restart. Its stale automatic-boon reply was
repaired independently in #383 (five expectations across four existing journeys); the
server behavior was already correct. No full regression cycle was required for that
literal fixture correction. Reuse this successful corpse evidence unless affected
production paths change.

### 1. Content contract and shared validation

- [ ] Add one focused content regression with an independent golden old/final manifest
  matching the appendix. Parse only AREA-selected inputs. Check the seven profiles,
  all 17 changes, six removals and four container flag edits; reject duplicate/missing
  vnums and remaining unsupported configurations.
- [ ] Define supported types/profiles once for runtime and db.c load diagnostics.
  Keep effect/profile validation separate from charge eligibility: a spent valid trap
  is not an invalid definition. Keep implementation-local helpers in trap.c; add only
  the small shared header/API required by the concrete loader/restoration consumers.
- [ ] Extend trapstat/trapset with names 9–16, profile restrictions, meaningful GLYPH/
  MULTI reporting and negative-level validation. Invalid builder edits must not leave
  a half-modified trap.
- [ ] Align editor direction definitions and flag-list ordering in
  `areas/de/src/obj/traps.h` and `areas/de/src/flagdef.cpp`; check formatting through
  `obj/objtypes.cpp`. Update `docs/content/area_writing.txt` and relevant command help.
  Keep existing runtime constants and unrelated data intact.

**Exit:** content contract fails on the present 61 definitions for the expected reasons;
validation rejects real invalid types/profiles while recognizing every planned final row.

### 2. Effect execution and bounded creature creation

- [ ] Add types 9–16 in trap.c using the contracts above. Keep 0–8 behavior and charge
  rules on their existing path.
- [ ] Snapshot trap fields and victim identities before effects. Reuse
  `find_character_by_runtime_id` and `find_live_object` rather than inventing another
  entity registry. Never test IS_ALIVE through an already-freed pointer.
- [ ] Implement temporary-caster cleanup and the explicit charge commit points.
  Verify ordinary spell and helper behavior with production functions, not only counters.
- [ ] Implement the seven profiles in a small fixed table/switch, including whole-batch
  capacity, placement failure rollback, cap counting and distinct gate/summon aggression.

**Exit:** native focused tests execute all eight effects, duration boundaries, defenses,
duplicate-effect rejection, ROOM filtering, missing profile/caster, cap/full-batch failure,
retaliation and target/actor/caster extraction. Sanitizers find no lifetime error; no caster,
event, combat link, corpse or reward leaks from temporary casting.

### 3. Real command integration and content edits

- [ ] Repair the 17 T tuples and remove the six specified records; preserve all other
  object/proc fields. Set container flags `value[1]`: 67803 1→5, 142233 17→21,
  142251 0→5, 142438 0→5. Add no lock or key requirement.
- [ ] Implement GLYPH continuation for restored types. After effects, revalidate actor,
  source room, object identity and current movement eligibility/exit. Continue safely
  to later matching traps, once per object; do not hide a subsequent blocking trap.
  Preserve non-glyph stop-the-attempt behavior and legacy 0–8 semantics.
- [ ] Preserve pickup rejection and OPEN-after-opening ordering. Wire OBJECT on the
  **item being put** for restored types 9–16: after ordinary permission/capacity checks
  but before acknowledgement, detachment, transfer or publication. An invalid put must
  not spend charges. Do not introduce destination-container hazards by inference.
- [ ] Adapt single/bulk put and any shared transfer callers reached by the hook so a
  trap rejection or invalidated actor/item/container stops safely. Reuse the pickup
  identity pattern; do not retain `next_content` across effects. Preserve ordinary
  legacy 0–8 put behavior and unrelated coin transfer behavior.
- [ ] Verify explicit directions (including the east-only royal equipment room,
  west-only shrine and downward Barovia glyph), all-direction rows, special-procedure
  overlap, disarming, and the four first-open container states.

**Exit:** actual movement/get/put/open command paths show the chosen outcomes, one charge
per activation and no delivery/publication after rejection. Existing bulk pickup and
special procedures keep their prior guarantees.

### 4. Saved-copy compatibility and round trips

- [x] Add one narrow, idempotent normalization function for the appendix's changed/
  retired profiles. Match vnum plus the **old mask/type/level**, not vnum alone.
  Preserve custom combinations, unrelated vnums and zero/disarmed state.
- [x] Preserve remaining positive charges, capped only where the new initial budget
  is smaller. Convert -1→1 only for 32820, 32870, 32835, 32846 and 41361.
  Clear generic trap fields on matching retired records. Normalize the two authored
  levels without ever converting negative level into an unsavable spell.
- [x] Call normalization after stored fields are complete in each actual owner:
  `materialize_item_graph/apply_extra_descriptions` (player_load_items.c);
  legacy SQL extra-description loading (sql_player.c); `restoreObjects` and
  `read_one_object` (files.c); world recovery materialization
  (world_recovery_pipeline.c); and `account_reward_snapshot_apply`.
  Respect existing snapshot verification and ownership/publication order.
- [x] Update the legacy files.c `O_U_TRAP` difference predicate to include all four
  fields; keep its existing encoding and other formats unchanged.
  Review repair: counted stock records now normalize every expanded copy immediately
  before placement. The native writer/reader regression expands two copies of every
  golden profile with five charge states; later copies cannot retain an old unlimited
  budget or a retired trap. Individual and counted ASan/UBSan round trips pass.
- [x] Preserve saved open/closed state. The four CLOSED changes initialize **fresh**
  objects only. For recognized legacy 142251/142438 with the original non-closeable
  container flags, add CLOSEABLE while leaving them open; other saved flag combinations
  remain as stored. Do not reclose opened loot or reset a special procedure's value[3].
- [x] Prove each restore owner actually invokes normalization after its final overwrite;
  a passing normalization helper alone is insufficient. Round-trip fresh, partial,
  exhausted, disarmed MULTI, old unlimited→finite, retired and custom states. Repeat the
  load/save cycle to prove idempotence and no rearming.

**Exit:** both persistence authorities and each reachable legacy/recovery/reward materializer
preserve the selected behavior and actual remaining budget. No broad data rewrite or schema
change is necessary. Normal save/restart guarantees are not represented as a new
crash-atomic spawn transaction.

### 5. Focused tests, generated world and gameplay qualification

Prefer extending existing tests before adding infrastructure:

- `test_unsupported_trap_damage.py`: retain invalid/0–8 coverage; add new effect/profile/
  level/charge cases. Its current effect stubs alone cannot verify native spell behavior.
- `test_get_trap_lifecycle.py` and `test_bulk_get_publication.py`: lifetime/rejection
  regression; extend the executable coverage to the new put/movement boundaries.
- `test_player_load_items.py`, `test_item_extra_descr_codec.py`,
  `test_player_item_snapshot_codec.py`, `test_world_recovery_pipeline.py` and relevant
  reward/binary restoration harnesses: prove real restore boundaries and round trips.
  Source-contract tests can supplement, not replace, executable evidence.
- Proposed new `test_legacy_trap_content.py`: independent authored/generated manifest,
  four containers and active-input selection. Proposed focused native
  `test_legacy_trap_effects.py`: real effect/helper and lifecycle behavior with controlled
  save/RNG inputs. Add a small restoration harness only where existing owners lack one.
- Proposed `test_legacy_trap_journey.py [SERVER BACKEND]`: reuse the disposable runtime,
  account/TCP and fixture machinery in `test_corpse_trap_restart_journey.py` and
  `test_flatfile_combat_journey.py`. Exercise actual generated prototypes, every effect
  and spawn profile, changed trigger classes, get/put/open, save/reconnect, spent
  floor/corpse state and restart on both backends. Keep the existing lethal corpse-trap
  journey as a legacy regression.
- Register only the relevant new checks in `tests/run_regression_tests.py` /
  `tests/run_db_tests.sh` where needed; document commands/evidence in
  `docs/testing/REGRESSIONS.md`.

Implementation commands (new test filenames above are proposed, not present yet):

```sh
./scripts/format.sh --check --rev origin/master
make -C src -j8
make -C src -j8 PERSISTENCE_BACKEND=flatfile BIN_ROOT="$PWD/bin/issue368-flatfile"
make world
python3 tests/async/test_unsupported_trap_damage.py
python3 tests/async/test_get_trap_lifecycle.py
python3 tests/async/test_bulk_get_publication.py
python3 tests/async/test_legacy_trap_content.py
python3 tests/async/test_legacy_trap_effects.py
python3 tests/async/test_player_load_items.py
python3 tests/async/test_item_extra_descr_codec.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_world_recovery_pipeline.py
python3 tests/async/test_corpse_trap_restart_journey.py "$PWD/bin/issue368-flatfile/server/dms_new" flatfile
tests/async/with_disposable_mariadb.sh python3 tests/async/test_corpse_trap_restart_journey.py "$PWD/bin/server/dms_new" mariadb
python3 tests/async/test_legacy_trap_journey.py "$PWD/bin/issue368-flatfile/server/dms_new" flatfile
tests/async/with_disposable_mariadb.sh python3 tests/async/test_legacy_trap_journey.py "$PWD/bin/server/dms_new" mariadb
```

Use isolated local environments and the disposable SQL wrapper; it does not source the
checkout's .env. Keep generated worlds, binaries and evidence under the repository's
ignored output locations. Do not commit area aggregates or runtime data.

- [ ] Regenerate with the existing root `make world` target (`areas/m_slow` and the
  area tools), then independently verify all 61 generated prototypes against the
  appendix and four container flags. Source parsing alone is not this proof.
- [ ] Boot the full generated world in an isolated local runtime, with normal floor/
  corpse restoration enabled rather than debugger `-z` shortcuts. Inspect loaded
  prototypes and complete startup logs from that exact binary/world generation.
- [ ] Assert the 61 old unsupported-definition warnings are absent **and** valid
  effects execute; inject an unrelated invalid configuration to prove warnings and
  charge preservation still work. Check parser duplicates by vnum, not warning count.
- [ ] Save evidence with source SHA, binary/world hashes, backend, commands, outcomes
  and complete boot log paths. Qualify restored-world state before claiming clean boot.

### 6. Final ablation and closeout

- [ ] Reread the actual diff: every source/data/helper change must serve a listed
  outcome; preserve spell balance outside the selected trap callers and existing
  special procedures. Keep the single compatibility normalizer because multiple real
  loaders require it; do not duplicate its policy.
- [ ] Keep the existing serializers, world generator, mob templates, identity lookups
  and test runtime. Drop speculative configuration, a generic effect plugin system,
  entity registries, replacement persistence formats and new scheduler/reward layers.
- [ ] Confirm each manifest row, profile, timing, save/defense, charge rule, continuation
  rule, restoration owner and acceptance condition has direct evidence.
- [ ] Record remaining implementation/qualification failures honestly; fix them before
  calling #368 resolved. Follow normal review requirements, without waiting for CI as a
  substitute for local evidence. Publishing/merging a future PR and production release
  are separate actions from this plan-only publication.

## Planning evidence and estimate

Planning checks completed on the pinned base:

- AREA-selected inventory: all 61 old tuples independently matched; 17 changed targets,
  six removals, 38 retained tuples and seven explicit spawn profiles accounted for.
- `python3 tests/async/test_unsupported_trap_damage.py` — passed.
- `python3 tests/async/test_get_trap_lifecycle.py` — passed.
- These establish the existing baseline only. No proposed new effect, generated-world
  change, saved-copy repair, full build or gameplay qualification has been performed.

Estimated implementation and qualification effort for one engineer: **32–48 hours,
approximately 4–6 focused working days**.

| Work | Hours |
| --- | ---: |
| Contract tests, validation and builder/documentation alignment | 3–5 |
| Real spell execution, caster lifecycle and fixed spawn profiles | 8–12 |
| Command continuation/put integration and authored content edits | 5–8 |
| Six restoration owners, legacy writer and persistence tests | 6–9 |
| Both-backend gameplay/restart and full-world qualification | 6–8 |
| Final review, findings and evidence closeout | 4–6 |

The main uncertainty is callback/lifetime behavior and the separate restoration paths,
not editing the object files. The estimate includes a repair/review allowance but excludes
external review latency and production scheduling. It is an effort estimate, not a
promise that the unimplemented behavior has already been validated.

## Complete old-to-final manifest

Fields are effect mask, type, charges, level. Old fields below were read from the pinned
checkout, not assumed from the issue. Remove T means retire generic trap state only.
For rows retaining a T record, the effect contracts above supply the new runtime behavior.

| Vnum | Active input | Observed old T | Required final T |
| ---: | --- | --- | --- |
| 1458 | [areas/obj/kobold.obj](../../areas/obj/kobold.obj) | `6 16 1 100` | `6 16 1 100` |
| 3835 | [areas/obj/element.obj](../../areas/obj/element.obj) | `2 16 1 50` | `2 16 1 50` |
| 6003 | [areas/obj/lizard.obj](../../areas/obj/lizard.obj) | `2 12 1 23` | `2 12 1 23` |
| 6707 | [areas/obj/court.obj](../../areas/obj/court.obj) | `2 12 1 21` | `2 12 1 21` |
| 6714 | [areas/obj/court.obj](../../areas/obj/court.obj) | `2 9 1 16` | `2 9 1 16` |
| 6715 | [areas/obj/court.obj](../../areas/obj/court.obj) | `2 12 1 16` | `2 12 1 16` |
| 6716 | [areas/obj/court.obj](../../areas/obj/court.obj) | `2 9 1 16` | `2 9 1 16` |
| 6721 | [areas/obj/court.obj](../../areas/obj/court.obj) | `2 12 1 31` | `2 12 1 31` |
| 6740 | [areas/obj/court.obj](../../areas/obj/court.obj) | `2 16 1 16` | `2 16 1 16` |
| 22209 | [areas/obj/desolate.obj](../../areas/obj/desolate.obj) | `512 14 6 10` | `512 14 6 10` |
| 32015 | [areas/obj/avernus.obj](../../areas/obj/avernus.obj) | `2 14 1 56` | `2 14 1 56` |
| 32820 | [areas/obj/shabo.obj](../../areas/obj/shabo.obj) | `1536 11 -1 50` | `512 11 1 50` |
| 32831 | [areas/obj/shabo.obj](../../areas/obj/shabo.obj) | `516 11 3 50` | Remove T |
| 32833 | [areas/obj/shabo.obj](../../areas/obj/shabo.obj) | `516 14 1 50` | `516 14 1 50` |
| 32835 | [areas/obj/shabo.obj](../../areas/obj/shabo.obj) | `32 11 -1 56` | `65 11 1 56` |
| 32846 | [areas/obj/shabo.obj](../../areas/obj/shabo.obj) | `5 11 -1 56` | `509 11 1 56` |
| 32870 | [areas/obj/shabo.obj](../../areas/obj/shabo.obj) | `1536 11 -1 50` | `512 11 1 50` |
| 35506 | [areas/obj/lavcav.obj](../../areas/obj/lavcav.obj) | `2 15 2 100` | `2 15 2 100` |
| 41353 | [areas/obj/highway.obj](../../areas/obj/highway.obj) | `516 9 1 50` | `516 9 1 50` |
| 41361 | [areas/obj/highway.obj](../../areas/obj/highway.obj) | `3140 10 -1 100` | `2069 10 1 100` |
| 41926 | [areas/obj/mir.obj](../../areas/obj/mir.obj) | `2304 9 2 100` | `2305 9 2 100` |
| 41927 | [areas/obj/mir.obj](../../areas/obj/mir.obj) | `6 11 2 100` | `6 11 2 100` |
| 41928 | [areas/obj/mir.obj](../../areas/obj/mir.obj) | `6 15 1 100` | `6 15 1 100` |
| 42175 | [areas/obj/mir.obj](../../areas/obj/mir.obj) | `6 12 1 50` | `6 12 1 50` |
| 42212 | [areas/obj/tribal.obj](../../areas/obj/tribal.obj) | `2 9 1 50` | `2 9 1 50` |
| 42290 | [areas/obj/tribal.obj](../../areas/obj/tribal.obj) | `2 10 1 50` | `2 10 1 50` |
| 43503 | [areas/obj/earth.obj](../../areas/obj/earth.obj) | `256 16 -1 50` | `257 16 -1 50` |
| 43506 | [areas/obj/earth.obj](../../areas/obj/earth.obj) | `64 12 -1 50` | `17 12 -1 50` |
| 43511 | [areas/obj/earth.obj](../../areas/obj/earth.obj) | `5 15 -1 75` | `509 15 -1 75` |
| 44160 | [areas/obj/tikitt.obj](../../areas/obj/tikitt.obj) | `64 13 1 90` | `17 13 1 90` |
| 44465 | [areas/obj/githzer.obj](../../areas/obj/githzer.obj) | `1057 16 -1 80` | `1089 16 -1 80` |
| 44532 | [areas/obj/githzer.obj](../../areas/obj/githzer.obj) | `6 16 1 60` | `6 16 1 60` |
| 44557 | [areas/obj/githzer.obj](../../areas/obj/githzer.obj) | `6 9 1 50` | `6 9 1 50` |
| 55022 | [areas/obj/wh.obj](../../areas/obj/wh.obj) | `2 13 -1 50` | Remove T |
| 57567 | [areas/obj/nexus.obj](../../areas/obj/nexus.obj) | `1 15 100 100` | Remove T |
| 58404 | [areas/obj/ravenloft.obj](../../areas/obj/ravenloft.obj) | `509 12 2 0` | `509 12 2 25` |
| 58406 | [areas/obj/ravenloft.obj](../../areas/obj/ravenloft.obj) | `389 14 3 61` | `389 14 3 61` |
| 59045 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `512 15 1 60` | `512 15 1 60` |
| 59047 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `6 15 1 200` | `6 15 1 100` |
| 59124 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `2 15 1 60` | `2 15 1 60` |
| 59203 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `2317 9 4 100` | `2317 9 4 100` |
| 59231 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `6 9 1 60` | `6 9 1 60` |
| 59239 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `260 16 1 100` | `261 16 1 100` |
| 59258 | [areas/obj/ravenloft2.obj](../../areas/obj/ravenloft2.obj) | `8 15 3 60` | `9 15 3 60` |
| 66212 | [areas/obj/cityruin.obj](../../areas/obj/cityruin.obj) | `516 15 1 20` | `516 15 1 20` |
| 67803 | [areas/obj/shortb.obj](../../areas/obj/shortb.obj) | `516 14 1 60` | `516 14 1 60` |
| 77721 | [areas/obj/hall.obj](../../areas/obj/hall.obj) | `2180 16 10000 60` | Remove T |
| 82024 | [areas/obj/jin.obj](../../areas/obj/jin.obj) | `516 15 -1 35` | `516 15 -1 35` |
| 82215 | [areas/obj/lylr.obj](../../areas/obj/lylr.obj) | `512 15 3 50` | `512 15 3 50` |
| 83254 | [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj) | `512 15 1 100` | `512 15 1 100` |
| 83368 | [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj) | `13 9 1 100` | `13 9 1 100` |
| 83527 | [areas/obj/alatorin.obj](../../areas/obj/alatorin.obj) | `509 14 5 100` | `509 14 5 100` |
| 91025 | [areas/obj/barovia.obj](../../areas/obj/barovia.obj) | `2308 9 5 60` | `2309 9 5 60` |
| 98701 | [areas/obj/unoutpst.obj](../../areas/obj/unoutpst.obj) | `6 12 1 60` | `6 12 1 60` |
| 130002 | [areas/obj/vecna.obj](../../areas/obj/vecna.obj) | `9 9 -1 60` | `2057 9 -1 60` |
| 131215 | [areas/obj/earthp.obj](../../areas/obj/earthp.obj) | `509 16 1 99` | Remove T |
| 131226 | [areas/obj/earthp.obj](../../areas/obj/earthp.obj) | `509 16 1 99` | Remove T |
| 135129 | [areas/obj/firesworn_altar.obj](../../areas/obj/firesworn_altar.obj) | `2 15 1 51` | `2 15 1 51` |
| 142233 | [areas/obj/blackpearl.obj](../../areas/obj/blackpearl.obj) | `512 9 1 15` | `512 9 1 15` |
| 142251 | [areas/obj/blackpearl.obj](../../areas/obj/blackpearl.obj) | `1536 12 -1 60` | `1536 12 -1 60` |
| 142438 | [areas/obj/Voluntown.obj](../../areas/obj/Voluntown.obj) | `512 9 1 60` | `512 9 1 60` |
