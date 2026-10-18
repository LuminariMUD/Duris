# Issue #57: consistent PSP regeneration and gradual movement decay

Status: RG-01/02/03 implemented, locally qualified and published for review as #201 → #202 → #203.
Prepared 2026-10-18 for [issue #57](https://github.com/LuminariMUD/Duris/issues/57).
Delivery branch: `branch/issue-57-regen-consistency`.
Original base for publication: `43046a57b63f1065aca03ba4a2fc0fb58297f454`.
Review stack rebased onto master `2378b49162ecf04d81366d3863355f93889da27a`.
All five original commits have identical patches after rebasing; the added master
commit changes backup tooling and documentation, not regeneration sources.
Source inspection and executable probes used `2c70abf1728a5930f345ee5f731ccbbb44c238a9`;
the newer base changes auction code and unrelated records, with no differences in
the regeneration sources or previous plan.

**Nexus provisioning / issue #109:** the previous contents of this file are preserved
byte-for-byte in [plan-issue-109.md](plan-issue-109.md), including its outstanding
production acceptance. The existing Nexus diagnostic that points here should be
followed through that link. This plan does not close or supersede that work.

## Outcome, scope and proof

Outcome: one PSP rate calculation supplies event admission, every recovery callback,
and staff display; it honors current eligibility, modifiers and the recovery dial.
Resting/sleeping and incapacitated/dying behavior use status, not posture. Movement
above maximum decays gradually, while positive regeneration still caps correctly.
Preserve elapsed-pulse accounting, fractional credit and event scheduling optimizations.

The owner selected **preserve the current POW+INT base** during planning. The detailed
modifier rules below are now the implemented contract. The historical reproduction
section describes the pre-implementation baseline. Do not restore the quadratic formula.

Non-goals: general movement rebalance, reconstructing historical player complaints,
HP/ward redesign, scheduler rewrites, new properties, services or schema, production
rollout, and changes to live player data. The initial planning commit is `38c0de994`;
implementation continues on the requested delivery branch.

### Active handoff (2026-10-18)

RG-01 replaces the obsolete quadratic PSP policy with the selected POW+INT contract,
uses it in the callback, and adds directional upper/lower PSP bounds. There are no
new scheduler hooks or abstractions. The native regression uses real rate functions,
difficulty, admission, callback and `use_spell()`; its queue and ordinary engine
dependencies are stubbed. It proves the status/posture matrix, modifiers, sunlight,
combat cancellation of fractional credit, full/zero/over-cap bounds, completion
message, casting restart, NPC staggering and one/four-pulse elapsed accounting.

Passed on the RG-01 source changes based on `38c0de994`: `test_psp_move_regen.py`
(ASan/UBSan), `test_difficulty_dials.py`, `test_vampiric_overheal_regen.py`,
`test_tick_work_spread.py`, `test_nevent_catchup_contract.py`,
`test_nevent_regen_death_contract.py`, `test_nevent_scheduler_runtime.py`
(ASan/UBSan), `test_player_event_timing_contract.py`, and `make -C src -j8`.
Build output is ignored at `bin/analysis/issue57-plan/rg01-build.log`.

RG-01 is published as [PR #201](https://github.com/LuminariMUD/Duris/pull/201),
initial head `b1454ab8db2cd986efee99d52737007b667599d0`, with exact remote parity and clean
working tree verified. RG-02 is on `branch/issue-57-movement-decay`, based on that
head. Its only production edit makes the movement upper cap conditional on a positive
increment. The expanded ASan/UBSan test executes `spell_restore_spirit()` twice in
combat to produce 120/100 vitality, then clears combat and executes `do_rest()`:
the first decrement at pulse 61 leaves 119. Damage/saves are stubbed; the producer,
rest, admission, rates and accumulator are real. It also proves progressive decay,
99/100 capping, one/four-pulse equivalence, neutral 80/229/632 movement rates and
NPC/negative dial independence. Both normal and flat-file server builds passed.

RG-02 is published as [PR #202](https://github.com/LuminariMUD/Duris/pull/202),
initial head `0b245add9223f12bd483cd451a15d805a37733a6`, stacked on #201; remote parity
and a clean working tree were verified. RG-03 continues on
`branch/issue-57-regen-lifecycle`. The existing sanitized scheduler runtime test now
also runs the real PSP callback and `StartRegen()` with a controlled rate:
duplicate admission, NPC first/recurring delays, manually delayed queued callbacks,
combat termination, fresh restart payload and full termination pass on the real
queue. The policy harness separately verifies the real rates. No scheduler code changed.

The full-world journey passed against production sources at `0b245add9223f12bd483cd451a15d805a37733a6`.
Flat-file binary SHA-256: `8cb7c7b352bec253a7af313c565c48d14138b3d29e6f7b6376565e1d9228490a`.
It uses disposable local accounts, the complete authored world, ordinary Telnet
commands and existing scheduler traces filtered by the test player's ID. Human base
POW/INT=95 plus the configured +5 racial bonus gives verified current POW/INT=100;
equipment, boons and the well-rested buff are absent. Staff setup gives level 50 and
the required skills. These are controlled fixtures, not balance observations of an
existing player.

- Dials 5/1/10 display 80/160/40 and gain 33/65/17 PSP respectively. Each comparison
  spans 123 traced callbacks; the staff snapshots bracket elapsed time at 120–126
  pulses. Gains agree within the one-point float tolerance plus that sampling window.
- `rest` then `meditate` displays 1,500/tick, fills 10,639/10,639, sends exactly one
  completion message and stops PSP callbacks. At full, staff displays resting
  potential 120. `stand` restores the ordinary 80 rate.
- Actual `will 'adrenaline control'` dispatch spends PSP and restarts one chain for
  both Psionicist and MindFlayer configurations of the isolated character.
- `hit dummy` with recovery pending leaves 1,001 PSP unchanged and display zero,
  with no callbacks during the measured combat interval. `tranquilize`, `wake` and
  `stand` end combat; periodic recovery is observed after 42.014 seconds, by pulses
  903–906. No new restart hook was needed.
- A disposable spell affect set to `MANA_REG=-80` stops recovery. Changing it to
  `+10` and recalculating via the existing staff edit/`balance_affects()` path starts
  90/tick recovery, from 1,006 to 1,009 PSP. The test purges that fixture affect.
- All 569 traced PSP callbacks have unique player/pulse pairs. Native scheduler
  proof additionally verifies owner queues, NPC cadence and one/four-pulse elapsed
  credit within one point.

`.env` was read only for `ENVIRONMENT=local`. The test server stopped and disposable
state/settings were removed. JSON evidence is ignored at
`bin/analysis/issue57-plan/journey.json`; the command below reproduces it. The earlier
PSP implementation and movement cap were also substituted into the native regression
in memory: they fail the rate and first-decrement assertions respectively.

RG-03 is published as [PR #203](https://github.com/LuminariMUD/Duris/pull/203),
initial qualification commit `315dbf7da`, stacked on #202. Review rebasing preserves
the #201 → #202 → #203 order: #201 head `e2930589ce4b2ee48e3f07cb0ffec541b3f9a81d`,
#202 head `604a19314ff76f76b3663545463eb3b5898d4f4e`. Merge in that order and retarget
each remaining child to master after its parent lands; if a parent is squash-merged,
rebase only the child's unique commits onto the new master first. No tags are needed.

Both #203 review findings were reproduced and repaired. The journey CLI creates
missing output parents before saving JSON; `test_psp_regen_journey_output.py` executes
that entry point with a stubbed journey and verifies both new nested directories and
replacement of existing JSON. It failed with `FileNotFoundError` before the fix.
The scheduler harness now schedules at `last_tick + interval` and asserts every queued
callback's elapsed interval: PCs one/four, NPCs first four then five. The old relative
delay fails this assertion at tick zero. Merely replacing three with four also fails:
the heartbeat has already advanced one tick after dispatch, producing five-pulse
recurring gaps. Absolute scheduling preserves four-pulse elapsed credit throughout.

The review rerun passed against production sources at `604a19314ff76f76b3663545463eb3b5898d4f4e`
with the same flat-file binary hash recorded above. The complete CLI created and saved
`bin/analysis/pr203-review/fresh-output/issue57/journey.json` without precreating its
output parents. Dials again gained 33/65/17 PSP over 123 callbacks each, meditation
sent one completion message, both casting restarts passed, combat recovery resumed
after 42.019 seconds, and the zero-to-positive modifier restarted 90/tick recovery.
All 569 traced callbacks had unique pulse identities. The disposable server and state
were removed. Both builds, the focused checks below, all scheduler sanitizer modes,
the output regression, formatting and 14 documentation contracts passed after rebasing.

Full-server execution uses the normal development binary; ASan/UBSan coverage is in
the native policy and scheduler tests. Merge, issue closure and production deployment
remain separate, unperformed actions.

Implementation and proof files:

- `src/world/limits.c`: make `mana_regen()` authoritative, including status and signed rates.
- `src/world/events.c`: consume that rate and correct directional resource bounds.
- One focused `tests/async/test_psp_move_regen.py`, using the existing `_paths.py`
  extraction/native harness conventions and real difficulty module.
- Extend `test_nevent_scheduler_runtime.py` for real-queue PSP lifecycle proof and
  remove the obsolete PSP-bypass fixture comment in `test_tick_work_spread.py`.
- `run_psp_regen_journey.py` drives the isolated full world, reusing existing journey
  helpers. `run_item_pilot_journey.py` adds a two-line opt-in to omit the mini-zone
  boot flag; existing callers retain their original boot command.
- `docs/reference/CODEBASE.md`, `docs/testing/REGRESSIONS.md`, and this plan: document
  the rate contract, deliberate balance effects, executable evidence and remaining gates.
- Existing caller files (`src/classes/memorize.c`, `src/cmd/actnew.c`,
  `src/cmd/actmove.c`, `src/magic/affects.c`, `src/combat/fight.c`) are inspection and
  journey targets. Edit only if a focused test proves a missing necessary restart.
  No speculative restart hooks or modifications to `src/world/new_events.c` are planned.

Proof: real rate functions, callbacks and admission code in a native sanitized harness;
existing focused difficulty, HP and scheduler checks; then a local/dev server journey
through casting, meditation, combat and staff display. Helper-only tests cannot prove
command reachability or the real event queue. No database migration is required.

## Pre-implementation findings (planning baseline)

1. **The PSP split is real and predates recent event optimization.**
   `StartRegen()` calls `mana_regen(ch, false)`; staff `stat` calls it with `true`.
   `event_mana_regen()` instead computes `(POW + INT) / 2.5`, or `/ 0.2` when
   `AFF_MEDITATE` is set. It never evaluates the helper's ongoing combat, sunlight,
   feeblemind, equipment or difficulty rules.
   The actual [2012 change](https://github.com/LuminariMUD/Duris/commit/c8004b74ea84947c878ed5ec58bd6836f1b4d492)
   deliberately replaced the callback's helper call with POW/INT arithmetic but left
   admission unchanged. Treating the old helper as the intended balance would silently
   reverse that change. Preserve the live base and consolidate in the existing helper.

2. **The status switch is invalid, and replacing its selector is insufficient.**
   `GET_POS` masks the two posture bits; `GET_STAT` masks distinct `STAT_*` bits
   (`src/core/utils.h:392-394`, `src/core/defines.h:1140-1154`). The PSP switch tests
   status constants against posture. Even after changing the selector, setting
   `gain = 0` for incapacitation/dying would be followed by meditation and `mana_reg`
   additions, which can restore a gain. Use terminal eligibility gates. The scheduler's
   dead-owner guard in `add_event()` does not reject incapacitated or dying characters:
   `IS_ALIVE` only requires status above `STAT_DEAD`.

3. **Movement's first decrement destroys the surplus.**
   `move_regen()` returns a negative rate above max vitality. `event_move_regen()`
   unconditionally clamps the result to max, including after a negative increment.
   `event_hit_regen()` already demonstrates the necessary positive-increment-only
   upper clamp. `spell_restore_spirit()` and the Reaper energy-drain branch really do
   add vitality without an upper cap and call `StartRegen()`; the resulting state is
   reachable. This inspection is not a live spell/combat reproduction.

4. **Consolidation exposes more PSP boundary behavior that must be covered.**
   The old helper squares `gain`, making a negative intermediate positive. Its
   over-cap path returns negative, while the current callback never consumes that
   rate and also has an unconditional cap. A shared signed rate therefore needs
   directional PSP capping as part of this fix, not a later cleanup.

5. **Restart paths already exist.**
   `use_spell()` subtracts PSP and starts mana regeneration; `do_meditate()` sets the
   flag and starts it; `do_rest()` starts each resource; `affect_total()` retries
   non-full/negative-modified resources for connected players. `affect_update()`
   retries depleted PSP for psionicists/mindflayers each player tick and preserves
   NPC slicing. `stop_fighting()` does not itself start PSP regeneration. Preserve
   the existing periodic recovery path and prove its bounded delay after combat
   rather than inventing a new timer or promising immediate restart.

6. **Reported movement balance is separate.**
   Checked-in recovery dial 5 is neutral; `difficulty_scale_player_regen()` scales
   only positive PC gains, leaving NPC and negative rates alone. #53 is closed.
   #56 transferred its historical movement report through #82 to #106; #106 is now
   closed by owner disposition and does not establish a further balance defect.
   Only #57 is the implementation work item for this branch.

### Fresh reproduction evidence

The complete diagnostic probe attached to #57 was inspected before execution and
run against the current source under UBSan. Its only adjustment was the scratch
output directory, `bin/analysis/issue57-plan/`. It extracts real rate functions,
callbacks and `StartRegen()`, includes the real difficulty module, and stubs ordinary
engine dependencies and the event queue. Its assertions describe existing bugs;
**do not copy them unchanged as desired regression expectations**.

Observed with the issue's level-50 human psionicist, POW=INT=100, generous resource
caps and the checked-in properties:

- PSP helper rates at recovery dials 5/1/10: 24/48/12 per tick; actual gain was
  800 over 3,000 pulses for every dial. Starting before combat still gained 800;
  starting while already fighting scheduled no event and gained zero.
- `mana_reg=+10` changed the helper to 72 but actual ten-tick gain stayed 800.
  `mana_reg=-30` produced helper +32 and the same 800 actual gain; feeblemind
  produced helper 1 with the same 800 actual gain.
- Normal/resting/sleeping/incapacitated/dying statuses all produced helper 24
  and actual gain 80 over 300 pulses. Meditation at skill 75 reported 1,104
  while delivering 999 over 300 pulses (nominal callback rate 1,000).
- At 120/100 vitality, the first decrement was at pulse 61 and changed 120 to
  100; the helper was -5/tick. Positive refill from 99/100 stopped at 100.
- Resting/sitting movement at dials 5/1/10: rates 229/458/115 and measured
  ten-tick gains 2,289/4,579/1,149. One- and four-pulse callback intervals matched.
- Substituting pre-October-10 callbacks and admission with the current rate functions
  gave the same observations. This is a controlled callback comparison, not a replay
  of an old server or proof of the player's historical circumstances.

`PULSES_IN_TICK=300` and `OPT_USEC=250000` mean a nominal 75-second game tick,
not one minute. Float accumulation can leave a one-point discrepancy from rate times
whole ticks; preserve and bound that behavior instead of changing numeric storage.

Also passed during planning: `test_difficulty_dials.py`,
`test_vampiric_overheal_regen.py`, `test_nevent_catchup_contract.py`, and
`test_event_loop_hotspots.py`. These establish existing controls, not a completed fix.
All 14 documentation contracts also passed; the preserved Nexus plan has the same Git
blob hash as the original. No full server build or live gameplay observation was run
for this documentation task.

## Implemented PSP contract

Keep the current `mana_regen(P_char, bool display_only)` interface and express all
rates in resource points per game tick. Use the following order, with explicit
integer truncation at the same base conversion as the callback:

1. Return zero for dead, dying or incapacitated status, active fighting, or the
   existing vulnerable-sun condition (honoring twilight and Globe of Darkness).
   Apply these gates before over-cap handling and bonuses; neither a positive
   modifier nor a stale meditation flag may restore recovery. Apply the same
   eligibility to staff display. Do not broaden sunlight exemptions incidentally.
2. For eligible characters above maximum, retain the helper's gradual PSP decay:
   `min(-1, (max_mana - mana) / 5)`. Do not multiply this negative rate by recovery.
3. Otherwise calculate the existing callback base for PCs and NPCs:
   `int((POW + INT) / 2.5)` normally, `int((POW + INT) / 0.2)` with meditation.
   Preserve that expression's truncation; do not revive the old level/race base or
   add `5 + meditation_skill` on top of the already accelerated meditation base.
   The existing skill prerequisite and advanced-meditation side effects remain.
4. Apply feeblemind's explicit quarter-rate reduction to the nonnegative base,
   then status: sleeping doubles it; resting adds half (integer division).
   Posture alone does not change PSP. Add `points.mana_reg` once as a signed,
   flat points-per-tick adjustment. This makes the formerly bypassed modifiers
   effective without restoring the abandoned quadratic balance curve.
5. Call `difficulty_scale_player_regen()` once on the resulting signed rate.
   Positive player recovery is scaled; zero/negative and NPC rates remain unchanged.
   There is no final square, so stronger negative modifiers cannot turn a drain
   into a gain. A modest negative modifier may still leave positive net recovery.
6. At exactly full PSP, suppress a positive rate for actual scheduling/recovery;
   `display_only=true` reports its potential rate. A true negative net rate may
   drain from full. At zero PSP, stop negative drain and clamp a decrement to zero
   if accumulated credit would cross it. Do not schedule a zero/blocked rate.

For POW=INT=100 and neutral difficulty, this contract yields a normal unmodified
rate of 80; resting 120; sleeping 160; normal meditating 1,000; and resting
meditating 1,500. Normal `mana_reg=+10/-30/-100` gives 90/50/-20; feeblemind alone
20. Dials 1/5/10 give 160/80/40 for the unmodified normal PC and leave an equivalent
NPC at 80. These expectations now pass against the real helper and callback under
ASan/UBSan in `test_psp_move_regen.py`.

Rest/sleep bonuses, feeblemind, signed equipment modifiers, sunlight/combat suppression
and positive difficulty scaling deliberately change affected recovery. Preserving
POW/INT does not mean every previously inconsistent rate remains unchanged. Record
these effects in the implementation PR and codebase documentation.

## Implementation work items

### RG-01 — Unify PSP policy, application and display

- [x] Implement the ordered contract in `mana_regen()`, replacing the obsolete
  base/square and unreachable switch; remove abandoned commented formula code in
  this function only. Update its misleading minute/hour comment.
- [x] Replace the callback's POW/INT expression with `mana_regen(ch, false)`.
  Keep `regen_event_state`, elapsed pulses, fractional remainder, player/NPC delays,
  GMCP updates, psionicist full-reserve message and `stop_meditation()` behavior.
- [x] Apply the max cap only to positive PSP increments; allow gradual over-cap
  negative decay and stop/clamp negative net drain at zero. Base full-resource
  admission on the computed rate rather than the sign of `mana_reg` alone.
- [x] Keep `StartRegen()` deduplication and NPC first-event staggering. Staff
  `stat` should agree automatically through the shared helper, with the documented
  full-resource potential-rate exception; no parallel display calculation.
- [x] Add native regression cases for the real helper, admission and callback:
  dials 1/5/10; varied POW/INT including fractional base truncation; PC/NPC;
  positive/zero/negative modifiers; feeblemind; sunlight/twilight/globe;
  every listed status crossed with posture; incapacitation/dying plus bonuses;
  meditation entry/exit; and reaching full with exactly one completion message.
- [x] Prove idle-to-combat and already-in-combat both gain zero, including an
  already accumulated fractional remainder and a delayed callback. Rechecking the
  current rate must prevent credit while blocked. On restart use a fresh state,
  so blocked elapsed time is not credited later.
- [x] Cover full/over-full/zero PSP, positive capping, signed drain and full ->
  actual `use_spell()` expenditure -> one scheduled recovery event. Preserve
  duplicate-start suppression and normal NPC recurrence/staggered elapsed credit.

### RG-02 — Preserve gradual movement decay

- [x] Cap positive gains and clamp delayed surplus decay when it crosses the maximum
  in `event_move_regen()`, preserving ordinary negative recovery below the maximum.
  Leave `move_regen()` arithmetic, posture properties, difficulty settings,
  CTF conditional bonus, and event cadence unchanged.
- [x] Add a regression that fails on the current first nonzero decrement:
  120/100 must become 119, not 100, with the existing -5/tick initial rate.
  Continue to show progressive decay and normal 99/100 -> 100 positive capping.
- [x] Exercise one-pulse and delayed callbacks using the same real accumulator;
  verify signed movement rates and that the full-resource exit optimization remains.
  Preserve representative neutral standing/resting/sleeping rates 80/229/632 for
  the fed/hydrated ordinary-player fixture without buffs, endurance or epic bonuses.
  Negative/NPC rates must stay independent of the player recovery dial.
- [x] Trace one actual vitality-granting producer through the full-world journey
  or an executable producer fixture, then end combat and start recovery through
  a real command such as rest. A directly seeded 120/100 fixture alone does not
  prove producer reachability or automatic over-cap recovery after combat.

### RG-03 — Integrate and qualify the real lifecycle

- [x] Run the focused sanitized test and the existing controls below. The new test
  must compile actual source functions; do not validate a copied Python formula.
  Reuse existing harness stubs; add no general-purpose regen framework.
- [x] Run formatting checks and the required server build after C/C++ edits.
- [x] In a verified local/dev environment, use an isolated test character to
  compare staff `stat` and accumulated PSP at neutral and changed recovery dials,
  holding stats, effects and elapsed pulses fixed. Include psionicist meditation
  completion and a mindflayer resource-spending/restart control.
- [x] Exercise combat entry while a regen event is pending, no recovery in combat,
  combat exit, and periodic restart within the existing next eligible player
  `affect_update()` tick (nominally up to 75 seconds). Also cover zero-to-positive
  modifier changes and recovery after leaving a suppressing state. If the real
  journey fails to restart, fix that specific existing caller and add a regression.
- [x] Confirm full-resource event termination, no duplicate callback chains, NPC
  cadence, and elapsed-pulse catch-up through the real scheduler. One/four-pulse
  steady-state gains should agree within the measured float remainder tolerance;
  state changes use the rate at callback execution, without adding state history.
- [x] Update CODEBASE, REGRESSIONS and this plan with exact tested revision,
  commands, results and any remaining acceptance gaps. Publish cohesive code/test
  changes for review; retain other repository review requirements. Do not wait for
  hosted CI when the required local proof is available.

Suggested implementation split: RG-01 with its tests, RG-02 with its tests, then
RG-03 evidence and any demonstrated integration repair. These are checklist items
under #57, not separate issues or an obligation to create extra PRs.

## Validation commands and completion

All commands below passed on the final production source tree (builds used `-j8`):

```sh
python3 tests/async/test_psp_move_regen.py
python3 tests/async/test_psp_regen_journey_output.py
python3 tests/async/test_difficulty_dials.py
python3 tests/async/test_vampiric_overheal_regen.py
python3 tests/async/test_nevent_catchup_contract.py
python3 tests/async/test_nevent_regen_death_contract.py
python3 tests/async/test_nevent_scheduler_runtime.py
python3 tests/async/test_player_event_timing_contract.py
python3 tests/async/test_tick_work_spread.py
./scripts/format.sh --check
make -C src
python3 tests/async/test_documentation_contract.py
git diff --check
make -C src -j8 PERSISTENCE_BACKEND=flatfile \
  DMS_BINARY="$PWD/bin/server/dms_issue57_flatfile"
python3 tests/async/run_psp_regen_journey.py \
  --binary bin/server/dms_issue57_flatfile \
  --output bin/analysis/issue57-plan/journey.json
```

Use ASan/UBSan in the native regression, following the existing HP regression.
For source controls, distinguish text assertions from executable scheduler proof.
The local gameplay journey is a separate gate from these commands; document its
fixture, actual entry points, elapsed pulses, resource changes and observations.
Restore test-only runtime settings after the journey. Read only `ENVIRONMENT` first
before choosing a server target, and keep credentials and player records private.

Issue acceptance maps directly to the work above:

- Consistent PSP formula/eligibility/modifiers/dial/display and restart: RG-01 + RG-03.
- Correct status behavior through actual callbacks: RG-01's status/bonus matrix.
- Gradual over-cap movement and ordinary capping: RG-02 + producer journey.
- Preserved elapsed catch-up, neutral movement and optimizations: RG-02 + RG-03.

Do not close #57 on publication of this plan. Completion requires the implementation
and the above local behavior evidence, plus review/merge when separately requested.
Production deployment or production acceptance is separate and needs owner permission.
No migration or full repository burn-in is justified by this change alone.

## Ablation decisions

Keep one existing rate helper and the existing event payload; each supplies an
explicit acceptance requirement. Keep the small PSP boundary/status additions because
making the helper authoritative exposes them. Reuse HP's directional-cap pattern.

Drop the tempting one-line callback substitution: it would replace the deliberately
selected POW/INT balance with the old quadratic formula. Drop a selector-only status
fix: later bonuses could undo it. Drop new tuning knobs, a shared four-resource
framework, new event cancellation machinery, numeric-accumulator rewrites, unrelated
HP/ward cleanup and a rollback of October's optimizations; no requested outcome needs
them. Preserve the previous plan rather than discarding its unrelated acceptance work.

## Publication handoff

Review order is #201 (PSP) → #202 (movement) → #203 (lifecycle qualification).
The active checkout is `branch/issue-57-regen-lifecycle`; its production sources are
identical to #202. All chunks use `Refs #57`, with no closing keyword or release tag.
Refreshed `origin/master` is `2378b4916` (backup scripts/docs/tests only); it changes
none of these production sources. #201 and #202 remain mergeable without rewriting
their reviewed branch histories.
When review is complete, merge/retarget the stack only when requested, preserving the
tested code tree and current branch protections. Keep #53/#56/#106 closed and unchanged.
The planning estimate was 12–20 engineering hours; it is not a measured delivery claim.
