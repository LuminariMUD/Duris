# Issue #478: keep character-selection level aligned after death

Status: **implementation plan; implementation and gameplay reproduction pending**.
Updated 2026-10-30.
Issue: [Duris #478](https://github.com/LuminariMUD/Duris/issues/478).
Branch: [branch/issue-478-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-478-plan).
Source baseline: origin/master at c9361959ceb6cb2a9004fea2c03748cef909dc3f.
Worktree: /home/aiwithapex/projects/duris-issue-478.

The completed Shambler plan previously at this path is preserved byte-for-byte
in [plan-issue-420.md](plan-issue-420.md). This change delivers planning only.
The existing checkout and its unrelated edits remain untouched.

## Outcome

After an ordinary, non-arena death, the account's character list must show the
character's current authoritative level. At the default cutoff, a level-16 Monk
must retain level and XP, and these observations must agree:

- the character's level and XP immediately before and after death processing;
- the character-selection row on the existing account connection;
- the character list after disconnecting and authenticating again;
- the persisted player status after the terminal snapshot commits;
- the character loaded by selecting that row, including after a server restart.

Verify the shared server projection through both telnet text and WebSocket
character-list JSON. Keep configured death-XP rules, respawn behavior, queued
input disposal, account ownership/admission, and asynchronous saves intact.
A menu projection must never become the source used to overwrite player level.

## Source findings and remaining uncertainty

All source locations below refer to the baseline above. The report's production
symptom is unverified; source inspection identifies a plausible stale-cache path,
not a completed production reproduction.

1. **Both menu protocols consume cached account state.**
   [account.c](../../src/account/account.c), display_character_list()
   (around lines 1630-1778), formats acct_chars.level.
   [ws_handlers.c](../../src/net/ws_handlers.c), ws_build_character_list()
   (around lines 2702-2735), emits that same field as JSON level.
   A second display-only calculation would duplicate the problem.

2. **A new account read and an existing session have different sources.**
   [sql_player.c](../../src/sql/sql_player.c), sql_load_account()
   (around lines 1508-1562), selects pd.level by joining account_characters
   to player_data; account_from_rows() materializes it into acct_chars.
   account_characters does not supply the level in that query.
   Its projection repair handles ownership/mapping, not a separate stored level.
   On flat-file, [flatfile_account_adapter.c](../../src/flatfile/flatfile_account_adapter.c)
   serializes membership level into identity records and loads it back.
   Therefore a MariaDB reconnect may repair an in-memory mismatch, whereas a
   flat-file reconnect can retain a stale durable membership level.

3. **The existing helper already supplies the needed publication behavior.**
   sync_account_character_projection() in account.c:2550-2577 copies current
   player level, PID, race/classes, specialization, playtime and room into its
   account entry, with optional write_account(). write_account():3186-3217
   persists through the selected backend and copies the account into its other
   connected sessions. MariaDB account saves write account/mapping metadata,
   not player_data.level. This helper already runs after normal character entry;
   the WebSocket creation path also publishes after entry raises level 0 to 1.
   Reuse it while the character still has its descriptor/account.

4. **The normal death path bypasses the older projection-update location.**
   [fight.c](../../src/combat/fight.c):2890-2928 calls
   persistence_save_character_terminal(ch, RENT_DEATH), then extracts through
   extract_char_after_terminal_save().
   [actoth.c](../../src/cmd/actoth.c):2133-2155 queues the snapshot directly
   through player_save_pipeline_request(); it does not call writeCharacter()
   or the projection helper.
   [handler.c](../../src/world/handler.c):4018-4068 clears queued input, sends
   the account menu/return signal, detaches the descriptor and frees the player,
   without updating its account-character level.
   [files.c](../../src/core/files.c):1347-1455 still has a flat-file projection
   refresh in writeCharacter(), but this is not the terminal helper's path.
   The ordinary queued writeCharacter() path also returns before that block.
   Changing only that legacy block would miss the reported workflow.

5. **Player status has an independent persistence/load path.**
   [player_snapshot_capture.c](../../src/player/player_snapshot_capture.c):140
   captures GET_LEVEL(ch), alongside experience.
   [player_snapshot_repository.c](../../src/player/player_snapshot_repository.c)
   maps the status level to player_data.level; the
   [load repository](../../src/player/player_load_repository.c) reads it and
   [materializer](../../src/player/player_load_materialize.c):233-235 assigns
   player.level from the loaded status. load_char_into_game() uses this pipeline,
   rather than acct_chars.level, to create the playable character.
   Thus saved/loaded level 16 with menu level 1 is consistent with a stale cache.
   A session entering at 1, advancing to 16, and dying before another entry
   refresh is a concrete candidate to reproduce.

6. **The XP protection and input fix are present independently.**
   [limits.c](../../src/world/limits.c):623-627 reads
   exp.goodieDeathExpLossLevelThreshold with default 30; gain_exp() protects
   EXP_DEATH below it. fight.c:2564-2589 guards both ordinary XP loss and the
   Lich's forced-delevel branch with that cutoff.
   The changes described by merged [PR #314](https://github.com/LuminariMUD/Duris/pull/314)
   and [PR #412](https://github.com/LuminariMUD/Duris/pull/412) are therefore
   relevant controls, not assumptions that resolve #478.
   Retain the input flush and existing death-HP snapshot/respawn ordering.

**Investigate before editing:** reproduce the 1-to-16 same-session sequence and
record whether existing-session, immediate-reconnect and post-commit-reconnect
results differ. Also start from an already saved level-16 login as a control.
Do not assert that every level-16 death shows 1. If the candidate does not
reproduce, trace the observed account refresh/write ordering before selecting a
fix. In particular, distinguish queue acceptance from committed player status.

## Non-goals

- No change to XP balance, the configurable cutoff, Monk abilities, race rules,
  character creation levels, or which deaths return to the account menu.
- No new schema/migration, duplicate SQL level column, account cache service,
  background refresh job, general event framework, or persistence redesign.
- No per-render database query, forced logout/relogin, frontend workaround,
  synchronous database wait in the death handler, or revival of old retry logic.
- No raw production character/account investigation, destructive production
  reproduction, deployment, broad burn-in, or waiting for hosted CI.
- No implementation of #213's broader onboarding work or reopening #314/#412.

## Files and implementation sequence

Expected production edit: **src/cmd/actoth.c**, at the shared terminal-save
boundary. Reuse **src/account/account.c** unchanged unless reproduction exposes
a concrete limitation in the helper. An edit to fight.c, handler.c, a display
renderer, or the SQL/load repositories needs evidence that the shared boundary
cannot satisfy an acceptance item.

Expected proof edit: add one focused two-backend journey,
**tests/async/run_death_level_projection_journey.py**. The existing death-input
runner is flat-file-only and does not inspect level or restart behavior; reuse
its combat/client setup and keep it as an unchanged input-compatibility check.
Reuse the existing journey clients, disposable database setup, server/world
fixtures and player inspector rather than adding another test framework.
Use one focused native regression for the terminal helper only if the runtime
journey cannot exercise its failure branches deterministically.
Register new tests in the existing runners where applicable.
Documentation edits are this plan and the preserved #420 record.

1. **Establish a failing, observable regression.**
   Use disposable accounts and a non-hardcore Monk under the shipped cutoff.
   Enter at level 1, raise it to 16 through existing staff/gameplay facilities
   without relogging, and verify the live level/XP. Avoid direct database
   mutation of a live character. Trigger a real non-arena death.
   Request the character list on the same connection before selecting again,
   capture the displayed numeric level, then compare saved player status,
   loaded level/XP and a newly authenticated account list.
   Retain a baseline failure transcript/assertion against the unmodified code.
   Reuse run_issue213_onboarding_journey.py for its two-backend environment,
   staff setup, state inspection and graceful-restart patterns; do not run or
   copy its entire unrelated onboarding campaign.

2. **Publish through the existing terminal-save path.**
   Proposed minimal change: after the terminal snapshot is accepted/coalesced,
   call sync_account_character_projection(ch, room, TRUE) while descriptor
   ownership is still intact. Reuse the calculated save-room vnum, current
   post-death level and existing account fanout/persistence. This also keeps
   quit/rent callers of the shared boundary consistent without separate patches.
   Account writes do not write MariaDB player status; flat-file needs the
   durable membership update for reconnect. Preserve the existing return and
   extraction contract: a terminal save queues and the caller leaves.
   Treat projection write failure with the existing bounded persistence-alert
   pattern; do not claim a successful player commit from the helper's result.
   On queue/capture failure, preserve existing diagnostics and departure
   semantics; do not persist a projection as evidence that player status saved.
   Recheck this placement against the reproduction before committing it.

3. **Prove both session and persistence behavior.**
   Execute the acceptance cases below with fresh MariaDB and flat-file binaries.
   Use bounded saved-revision/state polling when comparing durable status,
   rather than sleeping and assuming a queue has committed. Separately exercise
   immediate reconnect/reselection so waiting in the test cannot conceal a
   real ordering defect. If it exposes an additional blocker, repair the
   smallest existing ordering boundary and update this plan before expanding.
   Observe the real WebSocket return-to-menu/character-list messages with the
   existing protocol client; a helper-only test does not prove that payload.
   Preserve unrelated account entries and account admission/membership fields.

4. **Finish and record evidence.**
   Reread the diff with the ablation checks below. Run applicable formatting,
   focused regressions, both builds and documentation checks. Record exact
   commands, binary/source identities, baseline failure and fixed results here.
   Keep generated transcripts, server state and binaries under ignored bin/.
   Commit only the necessary source, regression and documentation changes.

## Proof and acceptance

- **Reported case:** a same-session level-1-to-16 Monk dies below cutoff; the
  same-connection telnet list and WebSocket list report 16, the reloaded
  character is 16, and committed player status contains 16 with unchanged XP.
- **Persistence:** fresh authentication immediately after death and after the
  save commits agrees with that result; graceful server restart and fresh
  authentication preserve it. Check player_data.level/exp on MariaDB and
  player snapshot plus membership level on flat-file.
- **Control:** a character who entered already at level 16 remains correctly
  displayed after death. Include a pre-existing stale flat-file membership
  repaired by normal authoritative character entry, then death/reconnect.
- **Actual delevel:** at/above the configured cutoff, choose XP that causes a
  real loss of level and assert the new current level in the list, snapshot and
  reloaded character. Do not substitute highest_level or hard-code 16/30.
  Reuse existing XP cutoff tests for default/configured protection and Lich rules.
- **Shared caller:** one quit/rent control after an in-session level change
  exercises the same terminal boundary without adding a second refresh path.
- **Integrity:** no other character's level/identity/membership changes; the
  existing account fanout remains valid, with no use of acct_chars pointers
  invalidated by account copies. A disconnected descriptor is never retained
  by an asynchronous callback.
- **Failure and compatibility:** rejected snapshot submission and account-write
  failure keep current alerts/departure behavior and do not assert durability;
  no new blocking wait or retry machinery. Death text, fresh menu input,
  queued-input disposal, respawn HP and configured XP behavior still pass.

Planned commands (implement the new journey's arguments as shown):

    make -C src
    make -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY=../bin/server/dms_issue478_flatfile
    python3 tests/async/run_death_level_projection_journey.py --backend mariadb --binary bin/server/dms_new --output bin/qualification/issue478/mariadb
    python3 tests/async/run_death_level_projection_journey.py --backend flatfile --binary bin/server/dms_issue478_flatfile --output bin/qualification/issue478/flatfile
    python3 tests/async/test_death_respawn_state.py
    python3 tests/async/test_death_transition_contract.py
    python3 tests/async/test_player_account_identity_save.py
    python3 tests/async/test_flatfile_account_membership.py
    python3 tests/async/test_world_quest_xp_feedback.py
    python3 tests/async/test_lich_death_experience.py
    python3 tests/async/test_terminal_save_safety.py
    ./scripts/format.sh --check
    python3 tests/async/test_documentation_contract.py
    git diff --check

Each journey invocation must exercise both protocol observations.
Use tests/async/disposable_schema.sh / with_disposable_mariadb.sh for MariaDB,
and a private temporary flat-file root. Read local environment classification
without printing secrets; do not point tests at the checkout's production DB.
Run run_death_input_journey.py with the fresh flat-file --binary and an ignored
--output directory to preserve input-compatibility coverage. Do not require the
unrelated full-world corpse/loot journey unless that behavior is touched.

## Ablation decisions

**Keep:** one publication at the shared terminal boundary, the existing helper
and backend writers, same-session plus reconnect/restart proof, both renderers,
and a real delevel control. Omitting any leaves a stated outcome or an actual
consumer unverified.

**Simplify:** one focused journey reusing existing disposable setup. Retain
existing cutoff/respawn/input tests instead of duplicating their matrices.
Use existing alerts and account fanout; no new flags, callbacks or services.

**Drop:** patching each death/quit caller, changing XP to match a stale menu,
querying player_data every time a list renders, fixing the frontend separately,
schema backfills and a full qualification campaign. None is needed by the traced
cache-publication gap. A per-death wait would change the current save contract.

**Investigate:** the immediate-reconnect ordering and flat-file durable identity
publication must be demonstrated, not inferred from a green helper test.
Revisit only the affected step if that evidence changes the proposed boundary.

## Tracking, estimate and planning evidence

#478 is the implementation work item for this branch. The open-PR and linked-
branch checks found no existing work for it. Link branch/issue-478-plan in #478's
Development section and post the committed plan link. #314 and #412 are merged
reference PRs, not additional open work items. Planning commits must reference
#478 without an issue-closing keyword; leave the issue open.

Estimate: **3-5 hours of my active implementation time** including the failing
reproduction, shared-boundary repair, two-backend/protocol persistence journeys,
required builds, focused regressions and final reviewable commits. Roughly
45-75 minutes is reproduction, 30-45 minutes is fix/failure-path coverage,
90-150 minutes is journeys/builds, and 15-30 minutes is documentation/review.
Allow up to 6 hours if immediate-reconnect ordering exposes another necessary
persistence repair. This excludes external review, merge waiting, deployment
and production/full-world qualification.

Planning baseline checks completed successfully:

- python3 tests/async/test_death_respawn_state.py
- python3 tests/async/test_death_transition_contract.py
- python3 tests/async/test_player_account_identity_save.py
- python3 tests/async/test_flatfile_account_membership.py (native membership test)

These checks establish existing controls; none reproduces #478. At the planning
stage there is no C/C++ change, full build, booted-game reproduction, database
mutation or production operation. All 14 documentation contracts and
git diff --check passed. The archived prior plan was compared byte-for-byte
with HEAD:docs/ongoing-projects/plan.md and is identical. Implementation
acceptance remains pending.
