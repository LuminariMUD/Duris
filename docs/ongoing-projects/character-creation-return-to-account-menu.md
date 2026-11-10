# Character creation returns to the account menu

Status: implemented and locally qualified; paired PRs are ready for review.
Date: 2026-11-05.
Implementation base: fetched `origin/master`, `44d3760d2`.
Inspected DurisWeb revision: `dae44ef41c93381a9142ccb72bae73c2462e574d`.

## Implementation and review handoff

- Server: [Duris PR #711](https://github.com/LuminariMUD/Duris/pull/711),
  `branch/creation-account-menu`, worktree
  `/home/aiwithapex/projects/duris-creation-menu`.
- Browser: [DurisWeb PR #155](https://github.com/LuminariMUD/DurisWeb/pull/155),
  `branch/creation-account-menu`, commit `1c2ac3f`, worktree
  `/home/aiwithapex/projects/durisweb-creation-menu`.
- Both PRs target their repository's `master` and are ready for review. They
  require coordinated rollout; neither has been merged or deployed by this task.
  No migration, player-data rewrite, release tag, or live announcement was needed.

The server returns committed ordinary Keep and connected approval to the menu;
pending applications retain the queue. Explicit Play retains the MOTD/entry
route. Rested responses distinguish level 0, and structured WebSocket waiting
status covers resumed applications. A socket regression found initialization
publishing `Char.Vitals` during chargen; that sender now requires `CON_PLAYING`.
The pre-entry cleanup/menu helper also replaces the duplicated failed-Keep
cleanup. Persistence, timers and starter-grant machinery are reused.

The browser closes creation on its saved receipt, refreshes the account menu,
and establishes its playing character/timers only from actual entry. It has a
resumable approval waiting view and first-entry rested explanation. The existing
creation-view flag moved into the MUD store; no separate completion state machine
was needed. Its development guide and unpublished changelog payload are included
in PR #155.

### Review follow-up

Adversarial review of the new flow found session and deletion gaps around
pre-entry bodies. WebSocket `login` and `enter` now require a menu or fresh
socket with no body or load in flight, in-game `logout` is refused, and a
deletion-fenced account gets no WebSocket session. Deletion refuses a PID held
by any descriptor, and a temporary load's cleanup no longer ends that holder's
save session. The Chaos kit and reward intents are decided at first entry, so a
parked character follows the server's mode when played.
`test_websocket_session_guard_journey.py` covers these through real sockets.

Rollout: server-side, a browser tab opened before the paired client deploys
still treats `created` as entry and shows a false in-game state until refreshed.

### Browser proof

Frontend commands passed: focused Vitest runs for
`useMudConnectionChargen.spec.ts` and `RestedBonusPanel.spec.ts` (114 tests),
`format:check`, `lint`, `type-check`, and `build`. Commands use
`pnpm --dir frontend --config.verifyDepsBeforeRun=false ...` because the isolated
worktree reuses installed dependencies. Builds supply explicit loopback public
endpoint settings; no environment file or credential was copied.

Installed Playwright with Chromium exercised the actual `/play` view at
`http://127.0.0.1:5198/play` against the changed isolated MUD, with a temporary
loopback TLS proxy for its WebSocket. Browser plugin was unavailable. Website
read APIs were fixture responses; MUD registration, creation, persistence,
approval and entry used real sockets and production handlers.

Verified: wizard through Keep -> menu/rested display -> explicit Enter;
1440×1000 desktop and 390×844 mobile with no horizontal overflow; pending Keep
-> waiting view -> disconnect -> login/select -> resumed waiting -> approval
-> level-0 menu -> explicit Enter. Page identity, meaningful content, absence
of a Vite overlay, and a normal played-character login were checked. The final
control captured no console warnings/errors or page errors. Screenshots were
visually inspected; key files include `creation-menu-browser-mobile.png`,
`creation-menu-browser-waiting.png` and `creation-menu-browser-approved-menu.png`.
The timer regression proves no creation-time start and one start across repeated
real-entry status updates. Firefox, WebKit and production deployment are outside
this local acceptance.

## Outcome

Let a player finish and save a new character now, then first play it later
without consuming its starting well-rested bonus. After a successful Keep,
an ordinary character returns to the account menu at level 0. Only an explicit
selection to play that character proceeds through first entry and grants its
150-tick well-rested affect and starter kit.

Creation, time at the account menu, disconnects, and server restarts must not
start or consume that bonus. At the current 75-second tick, 150 ticks nominally
represent 3 hours, 7 minutes, 30 seconds. After first entry, the existing
playing/offline countdown and subsequent rested eligibility remain unchanged.

**Approval exception:** when staff approval is required, retain the connected
approval waiting screen after Keep. Once approval is durably saved, return to
the account menu rather than entering the game. This preserves the current
staff queue without introducing an offline application system. A player who
disconnects while waiting can select the saved character later to rejoin that
queue. Approval never starts the bonus; the player selects Play after approval.

The implementation is a small-to-moderate flow change across Duris and its
paired browser client. Persistence and first-entry machinery already exist;
most qualification work is checking their boundaries after the new transition.

## Current behavior and reusable support

- [nanny.c](../../src/account/nanny.c), `keep_new_character()`,
  `save_kept_character()`, and `account_creation_pulse()`: Keep already waits in
  `CON_CREATION_SAVE` for a committed snapshot, publishes the account entry,
  and establishes the initial baseline. It records the approval decision with
  `PLR3_KEPT_CHARACTER` and `PLR3_APPROVAL_PENDING`. A queued request is not a
  successful creation. Failed and uncertain writes have distinct handling.
- `continue_kept_character()` currently sends an approved Telnet character to
  `CON_RMOTD`; Return then calls `enter_game()`. For WebSocket it calls
  `ws_finish_kept_character()`, which currently enters the game immediately
  unless approval is pending.
- [account.c](../../src/account/account.c), `confirm_play_character()`, already
  loads a level-0 character and calls the same continuation. Preserve this
  explicit Play route when changing creation completion; returning every call
  to the menu would make saved characters impossible to start.
- `enter_game()` detects a new character by level 0, supplies the full initial
  rested eligibility, initializes the character, and applies `TAG_WELLRESTED`
  with duration 150 and `AFFTYPE_OFFLINE`. Starter delivery uses the existing
  acknowledged first-entry snapshot and durable grant handling.
  [config.h](../../src/core/config.h) defines `SECS_PER_MUD_HOUR` as 75.
- `release_preentry_character()` already cancels applicable pre-entry work,
  detaches the descriptor, and frees its loaded character. `free_char()` in
  [db.c](../../src/world/db.c) ends the save-pipeline session. Reuse this
  lifecycle after acknowledgment; do not simulate quitting a playing character.
- `check_rested_bonus()` and `ws_cmd_rested_bonus()` currently derive all
  account-menu results from hours since `last_save`. The existing
  [account projection](../../src/account/account.h) includes `level`, so a
  level-0 special case needs no new persistent field or offline player load.
- The inspected DurisWeb client treats every `create_character: created`
  response as entry: it fabricates level 1, sets `in_game`, and starts timers.
  Its creation view closes only when that connection state changes. This is a
  required companion change, not merely a compatibility check.

The existing [durable Keep and resumable first-entry plan](issue-612-kept-character-resume-plan.md) describes
the underlying persistence work. This plan builds on the inspected code and
does not replace that work or rely on historical PR status as deployment proof.

## Scope boundaries

Keep the existing level-0 boundary, approval flags, save acknowledgments,
account ownership checks, admission rules, and starter-grant receipts. No new
database column, migration, timer, persistent "first played" flag, configuration
switch, or general login-state framework is needed. Do not remove
`AFFTYPE_OFFLINE`, change bonus duration/strength, reimburse previously played
characters, or change ordinary level-1+ logins. Staff `newchar` and recovery
commands retain their existing contracts.

The smallest implementation separates completion of creation/approval from an
explicit request to play. Keep the existing persistence implementation and
qualify it through the changed flow rather than adding another save mechanism.

## Implementation steps

### 1. Return committed creation and approval to the menu

Change the completion routing in `nanny.c` and the WebSocket completion code
in [ws_handlers.c](../../src/net/ws_handlers.c).

- Distinguish the existing save kinds at acknowledgment: initial Keep,
  approval, and legacy-policy persistence. Ordinary initial Keep and successful
  approval end at the account menu. Pending initial Keep still enters
  `CON_ACCEPTWAIT`. Explicit Play and its legacy-policy save continue through
  the entry path; they must not loop back to the menu.
- Preserve the current acknowledgment, outstanding-writer, PID, runtime,
  request, account, and name checks. Publish the account projection and initial
  baseline before announcing success or releasing the character. A failed or
  uncertain save must retain its existing error/reconciliation behavior and
  must not emit a successful creation receipt.
- For Telnet, report that the character was saved and can be selected whenever
  the player is ready. Release it with the existing pre-entry cleanup, enter
  the ordinary account-menu state, and render a correctly framed menu prompt.
  The authenticated account remains connected and the new character appears
  exactly once in its list.
- Move the creation-time MOTD presentation to explicit first Play as needed;
  preserve the existing welcome/news gates and Telnet Return acknowledgment.
  No gameplay prompt, world insertion, entry-side admission commit, starter
  delivery, or well-rested affect should occur during creation completion.
- For WebSocket, separate the creation receipt from the actual entry work in
  `ws_finish_kept_character()`. Send `create_character: created` with the
  existing character metadata and `waitingForApproval` while the body still
  exists. For a nonwaiting character, release it and send the existing
  `ws_send_auth_success()` account/list response in a valid menu state. Reset
  chargen state without reading the released body. Do not send full game state
  or set `CON_PLAYING` on this path.
- Preserve waiting connections, staff announcements, durable approval before
  accepted-name publication, and the existing decline/delete acknowledgment.
  Send a structured WebSocket waiting status through the existing system
  message envelope whenever the continuation reaches `CON_ACCEPTWAIT` (for
  example, `data.status: waiting_for_approval`). This must cover selection of
  a previously saved applicant as well as initial Keep: resumed selection
  does not receive a `create_character` receipt.
  Successful connected approval sends the approval notice and account menu,
  without a second creation receipt. Approval committed after disconnect is
  honored when the owner next selects the character.

Keep the distinction local to these transitions. The existing `created` flag
controls creation acknowledgment; do not silently reinterpret every false
value as either Play or approval, since those need different destinations.

### 2. Preserve explicit first entry

Selection through Telnet and WebSocket must continue to load the same saved
PID, stats, ownership, and creation choices. Recheck account blocking, racewar
admission/cooldowns, launch gates, and pending approval at the existing entry
boundaries; saving a character does not grant permission to play it later.

An approved level-0 selection follows the existing `enter_game()` route. Let it
perform initialization, apply the full 150-tick bonus, publish the new account
projection, and complete the acknowledged starter grant exactly once. Retain
command blocking while starter delivery is pending. Do not move those effects
to Keep, approval, account-list rendering, or character loading.

### 3. Show the starting bonus accurately

In `account.c::check_rested_bonus()`, handle `c->level == 0` before calculating
offline thresholds. Suggested text: "Starting well-rested bonus: 150 ticks,
available when you first enter the game." It must not suggest waiting 9 or 20
hours, or imply staff approval has been granted.

In `ws_handlers.c::ws_cmd_rested_bonus()`, add a derived
`availableOnFirstEntry` boolean to the existing per-character response. For
level 0, report the bonus as fully available (`restedPercent: 100`) and do not
invent 20 offline hours. Keep the existing numeric fields compatible and let
the paired UI use the boolean to replace the hours/progress explanation.
For played characters, retain the existing calculation and render behavior.
This is response metadata, not persisted state or a new eligibility rule.

### 4. Update the paired DurisWeb client

Required files in the separate DurisWeb repository:

- `frontend/src/composables/useMudConnection.ts`: a creation receipt clears
  the completed form and reports success; it must not synthesize a level-1
  playing character or start game timers. The subsequent account response
  refreshes the menu. Start timers only through actual game entry. Preserve
  real GMCP entry and reconnect behavior, including first Play of level 0.
- `frontend/src/views/MudClientView.vue`: close creation on successful Keep,
  independently of entering `in_game`. Show a clear waiting view when
  `waitingForApproval` is true or the server's structured waiting status arrives
  after selecting a saved applicant. Do not offer menu actions while the server
  is still in `CON_ACCEPTWAIT`. Explain that disconnecting is safe and selecting
  the character later resumes waiting. Approval returns the view to the menu.
- `frontend/src/types/mud.ts`, and `frontend/src/stores/mudStore.ts` only where
  needed: type the existing `waitingForApproval` and new
  `availableOnFirstEntry` fields and retain just enough transient state for
  that waiting/completion UI. Clear it on approval/menu response or disconnect.
- `frontend/src/components/mud/account/RestedBonusPanel.vue`: display the
  first-entry guarantee for unplayed characters, including that the normal
  offline countdown begins after first entry. Keep played-character displays.
- Extend `frontend/src/composables/__tests__/useMudConnectionChargen.spec.ts`
  and the applicable view/panel tests for these transitions and wording.

Do not reuse `account: return_to_menu` unchanged: its current consumer opens a
post-game confirmation dialog and deliberately keeps the game view visible.
The existing auth/account refresh is the simpler fit for creation completion.
Coordinate server and browser release, and verify with a freshly loaded client;
the inspected old client misinterprets the new completion behavior. No general
protocol-version negotiation is needed for this scoped change.

## Verification and acceptance

Extend existing executable tests and isolated journeys rather than introducing
a new test framework. Use disposable MariaDB fixtures with
synthetic accounts. The implementation progress section records actual results;
the remaining list is the acceptance scope, not a claim that every case passed.

1. **Create and defer:** on both transports with MariaDB, finish Keep and
   observe the menu, one selectable level-0 character, preserved PID and all
   ten base stats, and unchanged race/class/alignment/home/newbie/hardcore
   choices. Confirm no world entry, bonus affect, or delivered starter kit.
   Exercise menu commands and creating/selecting another character to expose
   stale descriptor/chargen state.
2. **Wait, disconnect, and restart:** inspect the committed level-0 snapshot,
   reconnect and cold-restart before Play, and model a long delay with the
   existing synthetic persistence fixtures. First Play must still receive
   all 150 ticks. Inspect the real affect at entry before a scheduled tick,
   or account explicitly for elapsed ticks in a socket-level assertion; an
   approximate UI label alone does not prove duration. Never age live data.
3. **First entry and replay:** Play immediately and after the delayed/restart
   cases; verify level initialization, stats, a full bonus, and one starter kit.
   Save, disconnect, and restart again; kit receipts/items and ordinary/Chaos
   starting rewards must not duplicate. A short logout after entry must reduce
   the existing bonus under its normal offline rule, without a fresh-character
   reset. Keep the normal rested requalification behavior.
4. **Approval:** cover approval off/on, accepted names, pending creation,
   reconnect with approval mode changed, connected approval, approval committed
   after disconnect, and decline. Connected approval ends at the menu; a later
   Play enters. Pending characters cannot enter or receive bonuses. Preserve
   staff queue visibility while connected and pending policy across restart.
5. **Persistence/lifetime boundaries:** retain delayed, rejected, and ambiguous
   Keep/approval cases, duplicate input, and mixed-transport takeover. No success
   precedes a committed save; no callback uses a freed/replaced character;
   committed characters survive loss of the completion response. A denied
   first Play leaves the saved character available without starting its bonus.
6. **Displays and real browser:** both rested displays identify level 0 as
   available on first entry immediately and after restart. In a real browser,
   verify form -> saving -> account menu -> explicit Play, plus approval
   waiting -> account menu -> Play. Confirm no game view, fabricated character,
   automatic `enter`, game timer, or post-game return dialog at creation.
   Preserve a control case for ordinary played-character login/rested display.

Primary existing tests to extend or adapt:

- `tests/async/test_kept_character_lifecycle.py` for completion routing;
  `test_kept_character_journey.py` for saved state, reconnect, restart, and
  transport takeover; `test_kept_character_approval_journey.py` for approval.
- `tests/async/test_kept_character_matrix.py` and
  `test_kept_starter_grant_journey.py` for accepted-name/Chaos combinations
  and durable starter delivery; retain relevant ambiguous-commit/competition
  regressions for the acknowledgment boundary.
- `tests/async/test_creation_prompt_journey.py`,
  `test_character_stat_choice_journey.py`, and shared creation helpers such as
  `test_mariadb_combat_journey.py::create_character()`. Helpers that promise a
  playing character must now explicitly select it after Keep. Keep tests that
  deliberately stop before entry distinct. Audit other `PRESS RETURN` and
  `create_character: created` expectations by purpose; do not globally replace
  them, since account login and explicit Play still use their own prompts.
- `tests/async/run_mysql_rested_checkpoint_journey.py` remains the existing
  post-entry rested persistence control; adapt its creation helper if needed.

Implementation validation commands start with:

```sh
make -C src
python3 tests/async/test_kept_character_lifecycle.py
tests/async/with_disposable_mariadb.sh python3 tests/async/test_kept_character_journey.py --backend mariadb --server bin/server/dms_new
./scripts/format.sh --check
git diff --check
```

Run the affected approval, starter, matrix, and fault journeys on MariaDB
using their existing `--backend`/`--server` options, including the matrix's
`--chaos` leg and the Keep journey's `--override telnet`, `--override websocket`,
`--delay`, and `--reject` cases. Record the precise commands and results with
the implementation; source assertions alone do not satisfy the journey cases.

From the DurisWeb root, run focused frontend unit tests, then
`pnpm --dir frontend format:check`, `pnpm --dir frontend lint`,
`pnpm --dir frontend type-check`, and `pnpm --dir frontend build`, followed by
the real browser journey against the changed local server. Follow that
repository's current instructions when implementing its companion change.

## Delivery

Prepare one focused Duris implementation PR and its paired DurisWeb PR, with
this plan updated to record actual validation and remaining gaps. Include the
player-facing behavior in the relevant release notes during release work.
Build and verify locally; CI is not a completion/merge gate under this
repository's instructions. Deployment and live content changes are separate
from this planning request. No migration or player-data rewrite is required.
