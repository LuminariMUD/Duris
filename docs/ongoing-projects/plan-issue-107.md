# Issue #107: Choose a stat rolling system before rolling

Status: implementation and local acceptance complete; ready for review, 2026-10-20.
This change includes no OpenSpec workflow files. Worktree: `/home/aiwithapex/projects/duris-issue107-plan`.

Review order: [Telnet #236](https://github.com/LuminariMUD/Duris/pull/236), then
[WebSocket #237](https://github.com/LuminariMUD/Duris/pull/237), then
[creation responses #238](https://github.com/LuminariMUD/Duris/pull/238), then
[first-entry vitals #239](https://github.com/LuminariMUD/Duris/pull/239) on the current
branch `branch/issue-107-first-entry-vitals`.
The required website companion is [DurisWeb #73](https://github.com/LuminariMUD/DurisWeb/pull/73),
worktree `/home/aiwithapex/projects/durisweb-issue107`, branch
`branch/issue-107-stat-choice`. Both browser methods, full-world persistence and
review qualification pass. Merge/release remain owner review steps; no production
operation, merge or release tag was performed. #107 stays open for integration.

Tracking: [Duris #107](https://github.com/LuminariMUD/Duris/issues/107).
Implementation branch: `branch/issue-107-stat-choice`.
Duris source baseline: [master `e19537cced99`](https://github.com/LuminariMUD/Duris/commit/e19537cced993bc8de3de1abd76027e8d40b389a).
DurisWeb source baseline: [master `70288bf4583b`](https://github.com/LuminariMUD/DurisWeb/commit/70288bf4583b94710c981fe35609de0e2b26ad71).

The [October 18 resolution](https://github.com/LuminariMUD/Duris/issues/107#issuecomment-6248090892)
and the owner's confirmation in this planning conversation select **both F and E**.
They supersede the issue body's statement that no system has been selected.
The [earlier E proposal](https://github.com/LuminariMUD/Duris/issues/107#issuecomment-6202646969)
supplies the four +5 bonuses and existing swaps. The owner confirmed the
interpretation of four bonuses across clients and changes for new characters only.
Other historical systems and later objections are context, not extra features.

The previous Cleric plan, including pending production acceptance, is preserved
byte-for-byte in [plan-issue-169.md](plan-issue-169.md).
The [historical investigation](character-stat-rolling-history.md) explains the
older systems; the current source findings below determine implementation scope.

## Outcome

Every new character chooses a method before any starting attributes are rolled,
in both Telnet and the DurisWeb character wizard:

1. **Default / quick start (F):** independently roll each of the ten attributes
   with `1d4 + 86`, range 87-90, mean 88.5 per attribute. This is the preselected
   choice and the Telnet Enter default. Roll once and proceed to bonuses.
2. **Advanced / rerolling (E):** independently roll all ten attributes with
   `3d6 + 77`, range 80-95, mean 87.5 per attribute. Permit unlimited replacement
   rolls before accepting a set. Accepting it advances to bonuses.
3. Both methods grant **four +5 selections**, capped at 100 per attribute,
   followed by optional repeated swaps and normal character confirmation/entry.
   The eight ordinary attributes and luck can receive bonuses and be swapped;
   karma is rolled and displayed but cannot be changed by bonuses or swaps.
4. Keep qualitative stat labels. Preserve racial modifiers, equipment/spell
   effects, the existing entry floor, and all saved characters. Do not gate the
   method on race, class, newbie/veteran selection, or Hardcore.
5. Enforce the same creation order and counts on the server. A browser-only
   hidden button is insufficient. A failed request must leave the accepted
   stats, selected method, and remaining bonuses intact.

Suggested shared explanation:

> Choose your stat rolling system. Default gives consistently strong starting
> stats, a higher average per roll, and a faster start. Advanced gives a wider
> range and lets you reroll for a potentially stronger set, which may take time.
> Both choices receive four +5 bonuses and allow stat swaps.

The higher average describes one unselected roll. It does not compare Default
with an Advanced set selected after many attempts or promise Advanced success.
Full cancellation/restart remains possible, as it is today; this is not a
guarantee against scripts repeatedly starting new characters.

## Non-goals and ablation decisions

- **Keep** the two distributions, pre-roll choice, four-bonus parity, existing
  swap targets, and real journeys through both clients: removing any one leaves
  an explicit requirement incomplete.
- **Simplify** by retaining `roll_basic_attributes()`, `CON_REROLL`, the existing
  Telnet bonus/swap handlers, descriptor-owned WebSocket stats, and the existing
  Vue wizard. Add one explicit Advanced roll type; do not replace the roller.
- **Keep** narrow WebSocket attempt/phase checks and reset handling. Current
  handlers accept out-of-order requests and retain reusable stats; these checks
  are necessary to make the selected method and four-bonus flow authoritative.
- **Simplify** Telnet's three repeated entry blocks into one local prompt
  function used by those three callers. This is an existing duplication with
  real callers, not a general character-creation framework.
- **Drop** A-D, point-buy, fixed-total arrays, new racial balance, exact-number
  displays, extra bonuses, reroll limits, script detection, account quotas,
  persisted method history, migrations, feature flags, new services, and a
  generic workflow/transport framework. None is needed for the selected outcome.
- Keep existing admission, name, class, race, Hardcore, account, and persistence
  policies. Broad creation cleanup and unrelated defects are separate work.
  Production deployment and live player changes are outside this planning task.

## Historical baseline source findings

These are code observations at the baselines above, not runtime test results.
The DurisWeb working checkout was behind master; the five affected implementation
files were compared with fetched `origin/master` and had no differences.

- [actwiz.c](../../src/cmd/actwiz.c), `roll_basic_attributes()` around lines
  5602-5725: `ROLL_NORMAL` actually uses 1d4+86 despite an 80-95 comment.
  The non-mob loop assigns all `MAX_ATTRIBUTES` entries to both base and current
  stats. Race/class do not select a different normal distribution.
  `do_reroll()` also calls this function; [db.c](../../src/world/db.c) uses the
  three separate mob types. Changing `ROLL_NORMAL` globally would affect staff
  rerolls and erase F. Preserve existing type values and callers.
- [nanny.c](../../src/account/nanny.c): `select_class()` at 2878,
  `select_alignment()` at 3019, and `select_hometown()` at 3074 each roll before
  entering `CON_BONUS1`. All three need the choice before that call.
  `select_reroll()` at 2559 still exists but also uses `ROLL_NORMAL`; merely
  routing into it would reroll F rather than restore E.
- The ordinary bonus route is `CON_BONUS1 -> CON_BONUS2 -> CON_BONUS3 ->
  CON_BONUS5`, then swaps. Four awards are real despite five named states.
  `add_stat_bonus()` adds exactly the passed 5, clamps at 100, and updates current
  stats. Telnet currently spends a choice on a stat already at 100; WebSocket
  rejects that request without spending it.
- [structs.h](../../src/core/structs.h) owns numeric connection states,
  `TOTAL_CON`, and descriptor `chargen_*` fields.
  [constant.c](../../src/core/constant.c) indexes `connected_types` by those
  states. [comm.c](../../src/net/comm.c) explicitly classifies creation states
  for ten-minute idle timeouts and zeroes newly allocated descriptors.
  A new prompt state therefore needs dispatcher, display-name, and timeout
  integration; appending a state must not renumber existing values.
- [ws_handlers.c](../../src/net/ws_handlers.c), `ws_cmd_roll_stats()` at 1805:
  any authenticated request with a playable race rolls anew, stores the race,
  and resets bonuses to **five**. `ws_cmd_add_bonus()` checks the count and cap,
  while `ws_cmd_swap_stats()` has no bonus-completion gate.
  `ws_cmd_create_character()` copies descriptor stats without requiring an
  accepted roll, zero remaining bonuses, or a matching rolled race.
  Dispatch has a pending-auth/write guard but no general creation-phase gate.
  These gaps must be handled in the affected creation commands.
- `enter_game()` in nanny.c floors all ten base stats at 80. Both selected
  distributions already meet that floor. Changing it or migrating old
  characters is unnecessary and would widen the behavior change.
- [lib/creation/reroll](../../lib/creation/reroll) is presently a label legend,
  not the actual reroll question. It ends at “Very good:86+” although
  `STAT_INDEX()` distinguishes 86-91 and 92-100.
  [lib/creation/bonus](../../lib/creation/bonus) says four bonuses but calls them
  rolls and describes bonuses as the final step before the existing swaps.
- DurisWeb's
  [MudCharacterCreate.vue](https://github.com/LuminariMUD/DurisWeb/blob/70288bf4583b94710c981fe35609de0e2b26ad71/frontend/src/components/mud/chargen/MudCharacterCreate.vue)
  automatically emits a roll on entering `stats`, always renders Reroll, moves
  to `bonus` without server acceptance, and hardcodes five bonus choices.
  Back navigation can retain stats while changing race. Cancel clears only the
  frontend store. Its global error branch hides the step controls, so a rejected
  capped-stat bonus currently obstructs choosing another stat.
- The browser event passes through
  [MudClientView.vue](https://github.com/LuminariMUD/DurisWeb/blob/70288bf4583b94710c981fe35609de0e2b26ad71/frontend/src/views/MudClientView.vue),
  [useMudConnection.ts](https://github.com/LuminariMUD/DurisWeb/blob/70288bf4583b94710c981fe35609de0e2b26ad71/frontend/src/composables/useMudConnection.ts),
  [mudStore.ts](https://github.com/LuminariMUD/DurisWeb/blob/70288bf4583b94710c981fe35609de0e2b26ad71/frontend/src/stores/mudStore.ts),
  and [mud.ts](https://github.com/LuminariMUD/DurisWeb/blob/70288bf4583b94710c981fe35609de0e2b26ad71/frontend/src/types/mud.ts).
  The request carries only `race`; responses carry labels and `bonusRemaining`.
  No website database or backend route is needed for this socket protocol change.

## Implemented contract and files

The following requirements are implemented in the review stack. They remain the
contract for reviewing or continuing this work.

### 1. Shared roller and Telnet flow

- Add a distinct `ROLL_ADVANCED` value in
  [defines.h](../../src/core/defines.h). Implement 3d6+77 in the existing
  roller without changing `ROLL_NORMAL`, punishment, or mob branches. Correct
  stale descriptions in the touched code.
- Append a `CON_STAT_METHOD` connection state and its indexed name; update
  `TOTAL_CON`, nanny dispatch, and comm's creation timeout bucket.
- Replace the three direct-roll entry blocks with one local
  `prompt_stat_method()` call. Display the shared explanation and choices
  `D) Default` and `A) Advanced`; Enter selects Default. Invalid input/help
  redisplays the prompt without rolling or advancing. Complete race, class,
  alignment, and hometown decisions first.
- On Default selection roll F once, show the result, and enter the first bonus
  prompt. On Advanced selection roll E, show the existing reroll question, and
  enter `CON_REROLL`. That state's rerolls use `ROLL_ADVANCED`; accepting enters
  the same first bonus prompt. Preserve its existing y/Enter reroll and n accept
  interaction. No persistent character method field is needed.
- Keep the four-award state chain and existing swaps. Align Telnet's capped-stat
  handling with WebSocket: selecting a stat already at 100 reports the cap and
  does not consume a choice; a 98-to-100 partial bonus does consume one.
  Preserve karma exclusion and current/base stat synchronization.
- Update the two creation messages for the actual quality ranges, four fixed
  +5 selections, and subsequent swaps. Do not expose individual numeric rolls.

Expected production files: `src/core/defines.h`, `src/core/structs.h`,
`src/core/constant.c`, `src/cmd/actwiz.c`, `src/account/nanny.c`,
`src/net/comm.c`, `lib/creation/reroll`, `lib/creation/bonus`.

### 2. WebSocket contract and attempt lifecycle

Keep this state on the descriptor alongside existing `chargen_stats` and
`chargen_race`. Use one selected-method field and a small phase enum:
unstarted, rolling, bonuses, ready. The bonus counter remains the source for
remaining selections. Do not add a database record, session service, or attempt
history.

- Extend `chargen_options` with the two supported method names and bonus count.
  This also lets the updated website detect a server that lacks the feature.
  Reading options must not silently reset an active attempt.
- Extend `roll_stats` input with `method: "default" | "advanced"`. Missing
  `method` means Default for old clients; reject malformed/unknown values.
  Initial requests store method/race, roll all ten stats, and initialize four
  bonuses. Default immediately enters bonuses; Advanced enters rolling.
- Return method and phase alongside existing labels/count. Subsequent
  `roll_stats` requests are allowed only for Advanced in rolling phase with
  the same race and method. Reject repeated Default rolls, method/race changes,
  and rolls after acceptance without changing stored values.
- Add `accept_stats` for Advanced's transition from rolling to bonuses. A
  duplicate acceptance may acknowledge the current accepted state but must
  never roll again or reset bonus counts. Keep Default's initial response
  compatible with clients that proceed straight to `add_bonus`.
- Permit `add_bonus` only in bonuses with a valid stored roll. Preserve the
  existing no-cost rejection at 100. The fourth successful selection enters
  ready. Permit swaps and `create_character` only in ready, with final race
  matching the rolled race. Validate these conditions before allocating,
  modifying, or persisting a character.
- Guard these mutating commands against unauthenticated or active-character
  sessions, while preserving existing pending-password/write and admission
  checks. A completed attempt must not be reused to create another character
  or alter an existing character.
- Add `reset_chargen` for Cancel or an explicit restart after changing race or
  method. It clears method, phase, stats, race, and bonus count, acknowledges
  completion, and never touches saved characters. Reuse one local reset routine
  where successful creation/entry or account/session replacement invalidates
  the attempt. Descriptor allocation already zeroes state; logout disconnects.
  Recoverable name/admission failures retain the valid attempt for correction.
  Revalidate exact auth/entry callers while implementing cleanup.
- Keep the command/response contracts here updated with final names and payloads.
  Existing clients omitting a method retain Default creation with four bonuses;
  their old reroll action intentionally receives a non-mutating error.
  Their local-only Cancel cannot reset a server attempt: give a clear reconnect
  instruction on a conflicting new roll, and test that reconnect restores a
  clean Default creation. Full in-session restart is supplied by the updated
  website's reset command; do not claim unchanged legacy cancel/reroll behavior.

Expected production files: `src/core/structs.h` and `src/net/ws_handlers.c`;
touch other entry/auth files only where their actual lifecycle calls require
the narrow reset. The new accept/reset operations serve concrete existing
wizard transitions; do not add a generic step API.

### 3. DurisWeb companion implementation

This is required work for issue #107, not an optional follow-up. Keep a focused
companion branch/PR in `LuminariMUD/DurisWeb` referencing the parent issue and this
plan. No separate website issue was found by the planning search; do not invent
a pre-existing work item or close #107 with only the server half complete.

- Add a method selection step immediately before stats using existing wizard
  controls and design tokens. Preselect Default; display the same explanation
  for new and veteran players. Do not send the first roll until the player
  continues from that choice.
- Pass the method through component event, view, composable, and typed command.
  Store the server's method/phase/count and capability metadata. Show Reroll only
  for Advanced while rolling. Advanced's Next action sends `accept_stats` and
  waits for acknowledgement; Default proceeds from its accepted initial roll.
- Replace the hardcoded five-choice wording with four choices / the advertised
  count. Preserve all ten labels and the nine editable targets. Do not infer
  an exact value of 100 from “excellent” or “quite excellent.”
- Treat the server's response as authoritative. Prevent overlapping roll,
  accept, bonus, swap, and reset actions; keep recoverable errors beside usable
  controls so a capped-stat rejection allows another selection.
- Back navigation that changes race or method must explicitly discard the
  unfinished attempt and clear both server and store state before another
  roll. Cancel uses the same acknowledged reset. Revisiting a completed step
  must not silently roll, restore bonuses, or revive stale stats. Disconnect,
  successful creation, and starting another character clear local state.
- When metadata lacks support, do not offer Advanced or pretend it is working.
  Preserve the old server's existing creation experience until the coordinated
  server-first update; do not send unknown accept/reset commands to it.
- Prepare release notes for the eventual website release following its
  repository convention; publication belongs to verified deployment.

Expected files: the five DurisWeb implementation files linked above, focused
Vue/composable/store tests, and the repository's release-note draft location.
Follow DurisWeb `AGENTS.md`, `docs/CONVENTIONS.md`, `docs/development.md`, and
`docs/DESIGN.md`. No frontend redesign or backend/schema changes are planned.

## Proof and acceptance

Use deterministic checks for exact formulas and executable journeys for
reachability. A range check alone cannot distinguish 3d6 from a uniform 80-95
generator, and quality labels cannot prove exact saved numeric values.

1. **Production roller:** add a focused executable test invoking the actual
   `roll_basic_attributes()` with controlled dice outcomes. Prove dice count,
   sides, offset, both extrema, all ten base/current assignments, and unchanged
   normal/staff and mob behavior. Use the existing native-harness pattern;
   do not duplicate the algorithm in Python as its own oracle or add a runtime
   RNG configuration. Proposed driver: `tests/async/test_character_stat_choice.py`.
2. **Real Telnet:** extend
   [test_creation_prompt_journey.py](../../tests/async/test_creation_prompt_journey.py).
   Exercise direct class completion, alignment completion with fixed hometown,
   and hometown selection, each reaching the method prompt before any stat
   result. Cover Enter/explicit Default, Advanced reroll and acceptance, invalid
   choice/help without mutation, prompt framing, four bonuses, concentration/
   partial cap/no-cost full-cap rejection, luck, rejected karma, repeated swaps,
   discard, creation, and save/restart/relogin. Update existing helper steps
   that currently expect “Press return to continue.”
3. **Real WebSocket:** add a focused
   `tests/async/test_character_stat_choice_journey.py`, reusing the isolated
   flat-file server and synthetic account lifecycle in
   [test_account_recovery_journey.py](../../tests/async/test_account_recovery_journey.py).
   Retain/expose its already allocated WebSocket port and use a small socket
   client for the existing protocol, not a second server framework. Exercise
   both methods through actual command dispatch, creation, save, restart,
   and login; inspect the synthetic saved base stats or a fixture staff view
   for exact values. If a minimal world lacks a selected route's data, use
   the existing full-world fixture option rather than weakening the journey.
4. **Server rejection/lifecycle cases:** before-roll bonus/swap/create; invalid
   method; missing method -> Default; repeated Default roll; Advanced reroll
   replacing the full set; accept twice; post-accept reroll; fifth bonus;
   swap/create with bonuses remaining; race mismatch; cap and karma; reset
   during rolling/bonuses/ready; disconnect/relogin; name collision retry;
   successful creation followed by another attempt; and creation commands
   while playing. Assert failure leaves state and saved characters unchanged.
   Include a pre-existing saved-character fixture that bypasses the new prompt
   and retains its stats.
5. **Browser:** add wizard tests in
   `frontend/src/components/mud/chargen/__tests__/MudCharacterCreate.spec.ts`
   and focused composable/store coverage using existing Vitest/socket patterns.
   Prove no pre-choice roll, correct method payload, Default without reroll,
   Advanced acknowledgement before bonuses, four-choice display, cap error
   recovery, blocked overlapping requests, and reset/back/reconnect behavior.
   Exercise old-server metadata absence explicitly.
6. **Cross-client acceptance:** run the actual browser wizard against the changed
   local MUD, complete one character by each method, then reload/login and
   compare saved stats and bonus/swaps with the Telnet journeys. Check keyboard
   navigation and a narrow viewport. Record build SHAs for both repositories.
   Mocked component tests do not establish this acceptance.

Implementation check commands, from the corresponding repository roots:

```bash
# Duris: after C/C++ edits, as required by AGENTS.md
./scripts/format.sh --check
make -C src
python3 tests/async/test_character_stat_choice.py
python3 tests/async/test_creation_prompt_journey.py
python3 tests/async/test_character_stat_choice_journey.py
python3 tests/async/test_character_creation_idle_timeout.py
python3 tests/async/test_creation_availability_contract.py
python3 tests/async/test_creation_all_races_toggle.py
python3 tests/async/test_creation_all_classes_toggle.py
python3 tests/async/test_chaos_hardcore_creation.py
python3 tests/async/test_racewar_admission.py
git diff --check

# DurisWeb: focused tests plus affected-package repository gates
pnpm --dir frontend test:unit --run src/components/mud/chargen/__tests__/MudCharacterCreate.spec.ts
# Also run the specific composable/store tests added or extended by this change.
pnpm --dir frontend format:check
pnpm --dir frontend lint
pnpm --dir frontend type-check
pnpm --dir frontend build
git diff --check
```

Extend the idle-timeout contract for the new state. Update adjacent source
contracts only when their asserted behavior legitimately changes.
Run journeys in isolated local/dev fixtures; compiled artifacts stay under
`bin/` and are not committed. Do not wait for CI to substitute for these local
checks. Report exact commands/results and any missing browser/persistence proof.

## Completed delivery and continuation

- [x] Implement the two distributions and every Telnet entry route.
- [x] Enforce the WebSocket attempt/phase/count/reset contract and legacy Default.
- [x] Implement the required DurisWeb companion and old-server fallback.
- [x] Complete full-world create/save/restart/relogin in both clients and methods.
- [x] Complete desktop/phone browser acceptance and repair reproduced defects.
- [x] Publish all chunks, update #107 and leave a clean review handoff.

Review order, with every PR open and ready for review:
1. [Duris #236](https://github.com/LuminariMUD/Duris/pull/236): shared roller and
   Telnet choice/caps/copy, on `branch/issue-107-stat-choice`.
2. [Duris #237](https://github.com/LuminariMUD/Duris/pull/237): descriptor-owned
   WebSocket method/phase and four-bonus authority, stacked on #236.
3. [Duris #238](https://github.com/LuminariMUD/Duris/pull/238): creation response,
   account projection and full-world qualification repairs, stacked on #237.
4. [Duris #239](https://github.com/LuminariMUD/Duris/pull/239): first-entry vitals
   notification and executable-test build handling, stacked on #238.
5. [DurisWeb #73](https://github.com/LuminariMUD/DurisWeb/pull/73): required website
   companion; integrate/release after the server stack.

Current continuation worktree is `/home/aiwithapex/projects/duris-issue107-plan`,
branch `branch/issue-107-first-entry-vitals`. This branch's plan is authoritative;
an older chunk's progress snapshot does not represent outstanding implementation.
The website worktree is `/home/aiwithapex/projects/durisweb-issue107`, branch
`branch/issue-107-stat-choice`. Its handoff and unpublished local changelog JSON
are `docs/ongoing-projects/issue-107-*`.

Qualified code pins:
- Duris: `7586f75654b06be23da197c3e250f9a7bccdd0d7`; later closeout commits change documentation only.
- DurisWeb: `461ca507ea8e0207b18765214aa74da356a56470`.
- Flat-file artifact: `bin/tests/stat-choice/flatfile-build/server/dms_new`, SHA-256 `e228b01725c07af172cb4f99de4a292fb607f377db44b91649275aa8f675d283`.

Master advanced during the work to `6a323feaab1a` with locker repairs and the new
player MOTD. Each feature branch merged its updated parent, bringing that current
base through the stack without rewriting published history. The combined tree
passed the normal build, verified flat-file build, all five full-world stat-choice
journeys and the named-locker runtime regression. The source tree under `src/`
at this code pin equals the source tree used by that combined qualification.
Earlier browser/formula results remain applicable: the upstream delta affects
locker commands and MOTD text, not the stat or browser protocol paths.

## Final protocol names

- `chargen_options` advertises `statMethods: ["default", "advanced"]` and
  `bonusCount: 4`; it does not reset an attempt.
- `roll_stats` takes `{race, method?}`; omitted method means Default. Its response
  includes ten quality labels, `bonusRemaining`, `method` and `phase`.
- Phases are `rolling`, `bonuses`, `ready`; only same-race/same-method Advanced in
  `rolling` may reroll. Default's first roll is accepted immediately.
- `accept_stats` returns `stats_accepted` with the same fields. Repeated acceptance
  acknowledges current values without restoring awards or changing the roll.
- `add_bonus` returns `bonus_added` with method/phase and existing fields. The
  fourth successful selection reaches ready. `swap_stats` returns `stats_swapped`
  with method/phase; creation requires ready, zero remaining and matching race.
- `reset_chargen` takes no data and returns `{type: "chargen_reset"}` after
  clearing every attempt field. Login/account replacement, accepted saved-character
  entry and successful creation also clear attempts.
- Mutations require completed authentication, no attached character, and either
  actual account-menu state (`CON_ACCT_SELECT_CHAR` or `CON_DISPLAY_ACCT_MENU`).
  Pending password/write guards remain in dispatch.

## Verification evidence

Passed local server checks:
- `make -C src -j8` (normal MariaDB-enabled development build).
- Flat-file build, both through `make -C src PERSISTENCE_BACKEND=flatfile -j8`
  during implementation and the verified fixture builder on the combined tree.
- `python3 tests/async/test_character_stat_choice.py`: production functions under
  ASan/UBSan, exact dice parameters/extrema, all ten base/current assignments,
  unchanged bad/mob rolls and mob floors, partial/full caps, luck/karma, counts,
  exact descriptor preservation, reroll replacement, reset and session gates.
- The 16-scenario creation-prompt suite passed against its built flat-file binary;
  the added live cap/karma/repeated-luck-swap leg passed separately.
- `python3 tests/async/test_character_stat_choice_journey.py --full-world`: all
  five cases pass on the integrated current-master tree: Telnet Default/Advanced,
  WebSocket Default/Advanced/legacy missing-method Default. They cover real
  dispatch, registration, capabilities, reset in each phase, reconnect/account
  replacement, invalid order/method/race, duplicate acceptance, four awards,
  forbidden karma/fifth bonus, repeated swaps, matching-race creation, playing
  guards, name collision/retry, successful-attempt consumption and another new
  character, tutorial room 22800, durable numeric stats, restart and saved entry.
- Post-kit vitals checks pass for all three full-world WebSocket cases and a
  minimal Default case. A saved character bypasses the method prompt and retains
  its stats. The inspector reads the authoritative base-stat domain.
- Creation timeout, availability, all-races, all-classes, Chaos/Hardcore and
  racewar admission contracts pass.
- Account projection contracts and `tests/async/with_disposable_mariadb.sh
  tests/async/run_account_character_projection_mysql.sh` pass using a disposable
  container/schema. This is focused SQL evidence, not a full MariaDB game journey.
- Creation-grant batch/reconciliation contracts, native input queue, ASan/UBSan
  prompt/output runtime and the integrated named-locker runtime pass.
- Changed-file formatting, Python compilation and whitespace checks pass.

The standalone stat-choice journey builds/acquires the existing verified flat-file
artifact when `--binary` is omitted. It does not depend on manually replacing the
normal `bin/server/dms_new`. All generated test builds, including the older prompt
suite's temporary build directory, are below `bin/`. Full-world fixtures copy lib,
use their own authority/journals/ports, and use generated authored world inputs;
`make -j8 world` passed. Generated outputs are not committed.

Passed website checks:
- Eight focused wizard/actual-Pinia/socket tests plus five existing credential
  tests: 13 total. They cover preselection/no premature roll, method payload,
  acknowledgement ordering, caps/error recovery, reset/back/cancel, no overlapping
  mutations, unrelated metadata/error handling, hometown waiting/retry and legacy
  server fallback.
- `pnpm --dir frontend format:check`, `lint`, `type-check` and `build` pass with
  explicit local public endpoints. Build output remains ignored.

## Paired browser acceptance

Regular Playwright drove installed Chrome 155.0.8059.41 because the Browser plugin
is unavailable. URL: `http://127.0.0.1:5179/play`; viewports 1280x900 and 320x568.
The actual Vue wizard/store/composable talked to the changed isolated full-world
MUD with synthetic accounts. Peripheral website HTTP bootstrap/map-data and the
backend-notification socket were fixtures. No MUD creation message was mocked.

Both methods completed four bonuses, swaps, creation, tutorial 22800, durable save,
server restart, account login and saved-character entry without a creation prompt.
Authoritative base stats were identical before/after restart, in Str/Dex/Agi/Con/
Pow/Int/Wis/Cha/Kar/Luk order:
- Default: `[92,94,92,90,88,89,90,90,89,93]`.
- Advanced: `[96,86,91,82,86,88,84,82,85,92]`.

Additional actual-browser proof: no pre-choice roll, Default without Reroll,
Advanced reroll/acceptance, cap-error recovery, repeated luck swaps, acknowledged
Back/Cancel, a fresh default choice after cancellation, keyboard Space/arrow
selection, short-screen vertical scrolling and no horizontal overflow.

The browser exposed and qualified these separate repairs:
- Registration returns the actual account identity; C booleans serialize correctly;
  the account card durably shows level 1 after first entry.
- Race selection waits for hometown metadata, clears stale options, deduplicates
  options requests and retains a failed lookup for retry. Rapid navigation now
  reaches the hometown step before method selection.
- Starter equipment is published after the initial client snapshot. Successful
  blocking-kit completion now sends the existing vitals update. A fresh browser
  character rendered 35/35 after its entry 1/1 snapshot, before reconnect.

Final game-entry/relogin checks have no app console errors or framework overlay.
The existing Vue Router next() deprecation warning remains a baseline warning.
The radio library selects during an asynchronous focus callback; keyboard checks
used physical key-down duration and no custom keyboard workaround. The first map
error was an incorrect peripheral test response, fixed to the actual nodes/edges
API shape; no map product code changed.

Screenshots and redacted evidence are outside both repositories under
`C:/Users/apexw/.codex/visualizations/2026/10/20/01a159e0-f002-79e3-9650-209e90903eb9/`:
`stat-choice-desktop.png`, `stat-choice-default-review.png`,
`stat-choice-mobile.png`, `stat-choice-advanced-review.png`,
`stat-choice-fresh-entry.png`, `stat-choice-browser-evidence.json`.

## Review repairs (2026-10-20)

Both reported findings reproduced and were addressed in review order:
- #236: the recovery contract expected `TOTAL_CON=92` and recovery states at the
  end of the connection-name table. It now checks `CON_STAT_METHOD=93`,
  `TOTAL_CON=93` and the updated ordering, retaining recovery IDs 90–92.
- #237 and #238 had no actionable review findings. The #236 repair was carried
  through each parent branch and into #239 without rewriting published history.
- #239: a second uncached build in the fixed journey build directory failed with
  `flat build did not select __NO_MYSQL__`. Each invocation now owns a temporary
  directory below `bin/tests`, retained until its journeys finish and then cleaned
  up. The existing verified artifact helper, cache and `--binary` path are reused.

The recovery/stat sanitizer harnesses and all 16 Telnet prompt journeys passed on
#236. The three WebSocket lifecycle/persistence journeys passed on #237. All five
full-world Telnet/WebSocket journeys and the disposable MariaDB account projection
harness passed on #238. On #239, consecutive direct invocations with
`DURIS_REGRESSION_BUILD_CACHE` unset passed all five full-world and all five minimal
journeys, including post-kit vitals. The cached runner also passed:
`make test-all -j8 TEST_JOBS=2 TEST_MATCH=character_stat_choice` (normal/production
builds, editor/area tools, world, native signals and two focused Python entries;
not the complete Python suite).

The build-artifact, starter-grant batch/reconciliation/lifecycle/plan/readiness,
transaction/item input-queue and ASan/UBSan prompt/output regressions passed.
Formatting against `origin/master`, Python compilation and whitespace checks
passed. Master remains `6a323feaab1a`; each updated parent is carried into its
child. Keep the review order #236 → #237 → #238 → #239 and squash when integrating
into linear-history master. No release tag, merge or deployment is part of this
review repair. GitHub CI is not a completion gate for this local qualification.

## Next owner action and limits

No implementation or required local acceptance remains. All PRs are left for
review/integration. The issue introduction records the selected rules and review
stack, with the [final evidence comment](https://github.com/LuminariMUD/Duris/issues/107#issuecomment-6295870664).
Keep #107 open until both repositories are integrated. Server protocol lands and
releases before the website. No production operation, migration, merge, release
tag or live changelog publication was performed. The release-note JSON is an
unpublished local draft for the normally authorized deployment/news process.

A full MariaDB game-server/browser journey and full burn-in were outside this
focused qualification. The normal server build plus the isolated account SQL
check are the database-side evidence. No balance certification or live production
acceptance is claimed. The original checkout and unrelated work were preserved.

Final ablation retained the required existing-path changes, narrow lifecycle
state, copy, focused regressions and this handoff. No point-buy, numeric stat
screen, balance change, generic workflow, saved method history, migration or new
service was added. This change adds no OpenSpec workflow files.
