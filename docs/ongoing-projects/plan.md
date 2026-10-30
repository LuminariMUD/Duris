# Issue #453: attach Minor Creation instruments to a belt

Status: **planned; implementation has not started**. Updated 2026-10-30.
Issue: [Duris #453](https://github.com/LuminariMUD/Duris/issues/453).
Branch: [branch/issue-453](https://github.com/LuminariMUD/Duris/tree/branch/issue-453).
Source baseline: origin/master at `c9361959ceb6cb2a9004fea2c03748cef909dc3f`.
Worktree: `/home/aiwithapex/projects/duris-issue-453`.

The previous shared plan and completed qualification record for #420 are
preserved byte-for-byte in [plan-issue-420.md](plan-issue-420.md).
This request authorizes planning, commit/push, and issue/branch linking.
Implementation is the next task.

## Outcome and explicit rule

Make Minor Creation's six wooden instruments attachable through
`wear <instrument> attach`: lyre 1241, horn 1242, drum 1243, mandolin 1244,
harp 1245, and flute 1246. Apply the same prototype capability in the full
world and the tracked mini world, including ordinary loads of those VNUMs.

Belt attachment remains an authored item capability: these six prototypes
will explicitly carry `ITEM_ATTACH_BELT`. Instrument type, low weight,
wooden material, or creation by this spell alone will not automatically
grant it to other items. Existing character/item eligibility, a worn waist
item, and an available attachment slot still govern success.

## Findings checked against the codebase

1. **The spell resolves precisely these six prototypes.**
   `minor_create_name_list[]` in `src/core/constant.c:501-507` maps all six
   names to the reported VNUMs. `cast_minor_creation()` in
   `src/magic/spells.c:251-290` uses `read_object(vnum, VIRTUAL)` and adds
   `ITEM_NOSELL`; it does not set wear capabilities. The current
   `read_object()` in `src/world/db.c:3297-3304` parses and instantiates the
   object template. Instantiation copies `prototype.wear_flags` at line 3142.

2. **The defect is present in both maintained datasets.**
   `areas/obj/heavens.obj:9713-9784` and
   `areas_mini/mini.obj:8453-8524` define 1241-1246 as type 32
   (`ITEM_INSTRUMENT`) with wear flags 16385 (`ITEM_TAKE | ITEM_HOLD`).
   The lyre weighs zero; the other five weigh one.
   `ITEM_ATTACH_BELT` is `BIT_24` (8388608) in `src/core/defines.h:185`.
   Adding that bit yields 8404993. Preserve each record's other fields:
   the full and mini records have existing differences in flags, restrictions,
   and description capitalization.

3. **The named loader and its description in the issue are stale/imprecise.**
   The relevant current function is `parse_object_template()`, starting at
   `src/world/db.c:2859`. Its existing attachment defaults at lines 3024-3034
   cover named drink containers, named containers with capacity below 25,
   and all quivers. They are not a general small-object or weight rule.
   Instruments receive no inferred attachment flag.

4. **World content does not establish a universal small-instrument policy.**
   A read-only scan of `areas/obj/*.obj` found 43 instrument records with the
   attachment bit; 39 have exactly 8404993 and four have additional wear bits.
   Examples include 402080/402081 in `library.obj`, 66613 in `torrhan.obj`,
   89159 in `newhope.obj`, and 138539 in `savannah.obj`.
   Numerous other zero/one-weight instruments lack the bit. The scan includes
   files with duplicate/inactive records and is evidence about source records,
   not a booted world's unique active prototype count. The issue's comparisons
   support the requested six-item correction, not a global type/weight default.

5. **The player route includes pickup and existing equipment restrictions.**
   `spell_minor_creation()` in `src/magic/magic.c:5977-5984` adds
   `ITEM2_STOREITEM` and puts the object in the room. The player must
   `get <instrument>` before wearing it.
   `do_wear()` in `src/cmd/actobj.c:6956-6998` resolves the inventory item
   and maps `attach` to wear case 21. `wear()` checks carried ownership,
   binding, condition and `can_char_use_item()` before its switch.
   Case 21 at lines 6743-6793 checks the attachment bit, a waist item, and
   three existing attachment slots before equipping. It contains no instrument
   exception. Adding the bit also makes these items eligible for the existing
   automatic wear selection; keep that behavior consistent with other
   belt-capable items.

6. **The authoring files are editable sources.**
   `docs/guides/BUILDING.md:179-205` distinguishes per-area sources from
   generated `areas/world.*`. Edit `heavens.obj` and the tracked mini fixture;
   regenerate the combined full world for validation without committing it.
   No SQL schema or prototype database migration is indicated by this path.

## Planning evidence and limits

- `python3 tests/async/test_newbie_object_template.py` passed at the baseline,
  compiling and executing the current parser/cache/instantiator under ASan/UBSan.
  Its existing belt assertion covers a synthetic bag, not these instruments.
- A temporary native probe reused that test's production-function extraction
  and fixture prelude, fed all six actual records from each dataset through the
  production parser, and passed under ASan/UBSan. All twelve parsed instruments
  retained only `ITEM_TAKE | ITEM_HOLD` and lacked `ITEM_ATTACH_BELT`.
  The temporary probe and binaries were removed automatically.
- The existing `test_wear_all_regression.py` native portion extracts hand
  cases 12-14, not belt case 21. It cannot certify belt attachment.
- No server boot, successful casting/attachment, persisted-item upgrade, or
  production reproduction is claimed at this planning stage.

## Non-goals

- No global `ITEM_INSTRUMENT` rule, weight threshold, spell-specific runtime
  flag override, new helper, configuration option, or replacement equipment path.
- No changes to other instrument prototypes, class/race restrictions, musical
  effects, hold/play requirements, Minor Creation eligibility/economics, item
  flags other than these six prototypes' attachment bit, or belt capacity.
- No retroactive rewrite of already saved/live item instances, persistence
  migration, production operation, deployment, or full burn-in.
  Fresh loads from refreshed world data are the acceptance boundary; existing
  instances need not acquire the new capability automatically.
- No unrelated help, telemetry, documentation-link cleanup, or issue closure.
  This document records the explicit rule; runtime help does not currently
  promise a conflicting rule.

## Files and ablated implementation sequence

Expected behavior edits: `areas/obj/heavens.obj` and `areas_mini/mini.obj`.
Expected proof edits: `tests/async/test_newbie_object_template.py`,
new `tests/async/test_minor_creation_instrument_journey.py`, and its
resource-intensive registration in `tests/run_regression_tests.py`.
Update this plan with completion evidence.

1. **Add the loader regression before editing the content.**
   Extend the existing object-template executable with a separate data-driven
   phase reading the real six VNUM records from each source dataset. Reuse its
   parser, instantiator and cleanup; keep synthetic caching/artifact cases
   intact. Assert instrument identity, TAKE/HOLD/ATTACH capabilities in both the
   parsed template and materialized object, and preservation of weight and
   instrument values. The attachment assertion must fail on the current data
   for each dataset. Include an unchanged, unflagged instrument control such
   as `newhope.obj` VNUM 89177 to prove the loader still does not infer a
   global instrument policy. Do not add a second parser/harness framework or
   a test that merely searches for decimal flag text.

2. **Correct exactly twelve wear-flag fields.**
   Change 16385 to 8404993 for VNUMs 1241-1246 in both datasets. Leave all
   other columns and text byte-for-byte unchanged. The normal parser, spell,
   and equipment command then carry the capability through existing code.
   Regenerate the combined full-world objects and verify all six generated
   records retain the added bit; generated output stays ignored.

3. **Prove the actual player workflow in disposable state.**
   Reuse `test_flatfile_combat_journey.py` for its isolated server build,
   world, ports and socket client, following
   `test_shambler_reflection_journey.py` for prepared mortal spell fixtures
   and command-response synchronization. Use a mortal Bard with valid
   fourth-circle Minor Creation access, sufficient mana/preparation and
   normal item eligibility; `src/classes/skills.c:1463-1470` registers that
   access. Staff may prepare private test state, but the mortal must perform
   the real cast, pickup and wear commands.

   For all six names, execute `cast 'minor creation' <name>`, observe room
   creation, `get <name>`, then `wear <name> attach` with a valid waist item.
   Observe the correct VNUM/identity and attachment slot in real equipment
   state, plus departure from carried inventory. Remove between cases.
   Across the same journey, fill all three slots and prove a fourth item is
   rejected without losing it, and remove the waist item before a fresh
   attempt to prove the existing belt-required refusal. Also retain a normal
   hold/remove check and an unflagged-instrument refusal control.
   Check the spell's existing NOSELL/STOREITEM flags through inspection.
   Require the command's own receipt and following prompt; a stray prompt
   or absence of failure text is insufficient.

4. **Finish proportional qualification and review.**
   Register the new journey with the existing resource-intensive tests so
   discovery schedules it appropriately. Run the commands below, reread the
   complete diff, verify only the twelve intended data fields changed, and
   record exact commands/results and remaining limits here.

Ablation keeps authored capabilities in two existing datasets, extends an
existing loader test, and adds one focused command journey using existing
helpers. Omitting either dataset leaves a supported world broken; omitting the
loader assertions leaves source/parse propagation unguarded; omitting the
journey leaves casting and real attachment unproven. A broad loader default
would change unrelated instruments, a spell override would duplicate prototype
policy, and a new equipment helper would duplicate working command behavior.
Those alternatives and persistence/operational work are dropped.

## Proof and acceptance

Planned implementation commands:

```sh
python3 tests/async/test_newbie_object_template.py
make world
python3 tests/async/test_minor_creation_instrument_journey.py
python3 tests/async/test_documentation_contract.py
git diff --check
```

The journey must build a fresh flat-file server with the existing build helper
by default; any explicitly supplied binary must be freshly built from this
checkout. Keep compiled artifacts under `bin/` and runtime accounts/world
state in a disposable fixture. Do not use live player state or production
configuration. Production C/C++ edits are not planned; if they become necessary,
run the repository-required `make -C src` and changed-line formatting checks.

Completion requires all six Minor Creation names to reach the correct attached
object, both source datasets and generated full-world records to contain the
capability, unchanged hold behavior, the existing no-belt/full-belt refusals,
an unrelated unflagged instrument remaining ineligible, and preserved other
prototype fields and spell-added flags. Report native loader proof and actual
socket gameplay proof separately. No database/restart suite or hosted-CI wait
is needed for this prototype capability correction.

## Tracking and implementation estimate

#453 is the work item for this branch. The issue had no comments when reviewed.
Targeted searches found no open PR mentioning 453 and no other open issue
matching `instrument`; no additional work item is inferred from those results.
Link this branch directly in #453's Development section and add the committed
plan link to the issue. Use `Refs #453` for the planning commit, keeping the
issue open until implementation and proof are complete.

Estimate: **1.5-2.5 hours of my active implementation time** after this plan.
Allow about 20-35 minutes for regression/data changes, 45-75 minutes for the
prepared-caster journey and controls, and 25-40 minutes for world generation,
fresh server build, focused checks and final review. Allow up to 3 hours if
spell preparation or isolated-world setup needs more work. This includes local
implementation, validation and reviewable commits; external review, merge
waiting and production deployment are excluded.

## Planning completion checks

This commit contains this plan and preservation of the previous #420 record.

- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `git diff --check`: passed.
- The archived #420 record equals the baseline shared plan byte-for-byte;
  SHA-256: `9306f27c4fad0663f588bb44f6b05fc8492d368d9bffb872c5c325570020f8e7`.
- Baseline native loader qualification and the twelve-record parser probe
  passed as described above; this is not implementation acceptance.
- Publication and the direct issue/branch association are verified after the
  planning commit and reported in the issue handoff.

The game behavior remains at the baseline until the implementation steps
above are carried out.
