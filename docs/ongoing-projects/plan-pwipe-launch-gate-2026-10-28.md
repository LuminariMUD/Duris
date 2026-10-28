# October 28 pwipe: account allowlist and launch screen

Status: **planned; not implemented or deployed**. Prepared October 28, 2026.
Public opening: **2026-10-28 at 18:00:00 UTC** (`2026-10-28T18:00:00Z`, Unix
timestamp `1793210400`). Initial approved account: **`mosheh`**.

Source inspected: local checkout `58ed0c42b` on
`branch/local-dev-burnin-fixes`, with `ENVIRONMENT=local`. These findings describe
that checkout, not the current production executable or database.

## Outcome and scope

This is feasible. Finish the existing supervised pwipe early, boot the new season
behind an account allowlist, and let `mosheh` authenticate with the account's
existing password to prepare and inspect the world. Everyone else gets a dedicated
Duris launch screen until 18:00 UTC. From that instant, ordinary authentication,
character creation and game entry resume without another wipe or restart.

- **Outcome:** one consistent gate across Telnet, TLS Telnet, native WebSocket
  login, character creation, reconnect and restored connections; a distinctive
  ANSI/ASCII screen; persistent configuration; exact UTC opening behavior.
- **Non-goals:** changing the wipe/reset policy, changing credentials or character
  privileges, pausing world simulation, a general maintenance framework, a waiting
  room, a scheduler service, or a new database schema. This task produces the plan
  only. Implementation, deployment and the production wipe are separate work.
- **Files:** the account/network entry owners listed below, one small shared gate
  module, one configuration file, one text-art asset, focused tests and the
  operational runbook. No live `.env`, credentials or player/account data edits.
- **Proof:** executable policy tests plus actual socket journeys through each
  supported entry path, a restart, and the existing disposable pwipe journey with
  the gate armed. Existing local qualification is not proof of production readiness.

The proposed defaults below are deliberate implementation choices: automatically
open at the announced time, prevent public registration/character preparation
before then, and disconnect denied sessions after their screen drains. An approved
account still has to pass all normal authentication and admission checks.

## What the current code already provides

1. [account.c](../../src/account/account.c), `finish_account_password`, finishes
   asynchronous password verification before login pages and the account menu.
   It also replaces duplicate sessions. Evaluate the gate after password success
   and before duplicate-session replacement or menu exposure. Match the loaded
   account identity, not the submitted name or a character name.
2. [ws_handlers.c](../../src/net/ws_handlers.c), `ws_finish_login`, has its own
   successful-login path and can reconnect directly to an online/linkdead character.
   `ws_cmd_enter` and `ws_cmd_create_character` are additional entry boundaries.
   A Telnet-only check or a check only in `enter_game` would miss these paths.
3. [account.c](../../src/account/account.c), `account_confirm_char`,
   `account_player_load_complete` and `is_char_in_game`, and
   [nanny.c](../../src/account/nanny.c), `CON_RMOTD`, cover existing-character loads,
   asynchronous continuation, reconnect and the first entry of a new character.
   Some callers set `CON_PLAYING` before calling `enter_game`, which already performs
   world placement and other side effects. Refuse before those transitions.
4. [copyover.c](../../src/persistence/copyover.c), `copyover_recover`, restores
   descriptors directly to `CON_PLAYING`, using the account name returned by the
   authoritative player load. That path also needs the gate before attachment and
   world publication; merely checking a later account prompt is insufficient.
5. [actwiz.c](../../src/cmd/actwiz.c), `do_wizlock`, exposes creation, connection,
   maximum-player and character-level controls. It has no account allowlist or UTC
   opening time. Its runtime flags start at `LOCK_NONE` in nanny.c. The existing
   IP-based multiplay whitelist is also a different policy and should not be reused.
6. `select_terminal` in nanny.c chooses the existing
   [plain greeting](../../lib/information/greeting) or ANSI greeting variants.
   [login_mode_banner.c](../../src/account/login_mode_banner.c) and
   [test_login_mode_banner.py](../../tests/async/test_login_mode_banner.py) show the
   existing color-token/rendering approach. Preserve the normal mode banner.
7. [comm.c](../../src/net/comm.c) loads configuration before accepting players and
   already drains Telnet and WebSocket output before closing `CON_FLUSH` sessions.
   `close_socket` itself discards queued output: use the drain path for the screen.
8. [sql.c](../../src/sql/sql.c), `sql_pwipe`, and
   [cycle_mud.sh](../../scripts/cycle_mud.sh) already distinguish an incomplete reset
   from a completed season awaiting an explicit start. Accounts and credentials
   survive; only eligible exact level-62 Overlords get recreated bodies. The new
   gate must not weaken the durable incomplete-reset fence or alter staff recreation.

The existing [pwipe qualification plan](plan-issue-264.md) records local evidence;
the [runbook](../operations/RUNBOOK.md) owns the supervised operating procedure.
Their recorded qualification language is not fully synchronized. Check the actual
deployment revision and current wipe readiness when carrying out that procedure.

## Admission contract

Before the opening time, with the gate enabled:

- `mosheh`, with the correct existing password, can reach the ordinary account menu,
  select/create a character and enter. Account matching is exact and case-insensitive
  using the server's existing account-name rules. No prefixes, wildcard names,
  character-level exemptions or shared-password bypass.
- Other existing accounts can authenticate, then receive the launch screen and a
  clear reconnect instruction. They cannot reach character selection, reserve a
  character name, roll stats, create a body, reconnect or execute game commands.
- Wrong passwords retain the ordinary authentication failure behavior, including
  for `mosheh`. An allowlisted name never establishes authentication by itself.
- New account registration is deferred until launch on both transports. An absent
  `mosheh` account must not be treated as permission to register that name and enter.
  Existing password recovery may finish normally, but does not grant game admission.
- Staff on unlisted accounts are blocked too. The allowlist does not override bans,
  account deletion fences, blocked characters, racewar rules or other existing locks.
- Repeat the same policy at character-creation and final entry/reconnect boundaries.
  Recheck after asynchronous work and before any resulting persistence/gameplay
  mutation. A menu, pending password/load result or restored descriptor is not an
  exemption. Denied pre-entry state must be released without saving a new character
  or disturbing an already attached session.
- A connection draining a denial accepts no new gameplay/account actions, including
  additional WebSocket commands. Use existing cancellation/cleanup paths so pending
  completions cannot return it to a playable state.

At **`now >= opens_at`**, this gate permits ordinary admission. At
**`now < opens_at`**, the allowlist applies. Evaluate server UTC time at the actual
decision; do not cache "closed" at boot or rely on a delayed timer event. Opening
removes only this restriction, not unrelated locks. Already denied connections
reconnect normally; do not auto-create or auto-enter characters for them.

## Smallest implementation

### 1. Persist and validate one launch configuration

Add `lib/pwipe_launch.cfg`, following the repository's small text-configuration
pattern, with exactly these settings:

```ini
# Shipped default: false. Operator arms the post-wipe boot explicitly.
enabled=false
opens_at_utc=2026-10-28T18:00:00Z
allowed_accounts=mosheh
```

For the preparation boot, set `enabled=true`. Allow a comma-separated list of exact
account names so further approved accounts can be added explicitly. Store no
passwords, hashes, email addresses or tokens here.

Load and validate once before any listener or copyover recovery can admit players,
in normal and minimal boots. Require this shipped file to be present and readable;
reject malformed/duplicate/unknown settings, invalid UTC dates and an empty or
invalid enabled allowlist before opening listeners. Never turn a configuration
error into unrestricted access. A missing art asset, however, must still produce
a plain launch notice and must not disable the gate. SQL-only wipe recovery should
remain independent of this login configuration.

Parse the timestamp strictly as UTC into an integer/time value; do not use local
timezone conversion. Do not store it in `duris.properties`: the existing property
values are floats, unsuitable for exact epoch-second comparisons. The displayed
date and any remaining-time text must come from this same parsed timestamp.

Keep configuration and art outside wiped player stores. Verify both survive the
actual launcher cleanup. At startup log the enabled state, UTC opening time,
current open/closed decision and allowlist count; never log credentials. Changes to
the configured time or approved accounts require a controlled restart. No new
reload command or per-login disk/SQL read is needed; time passing opens the gate
without configuration reload.

### 2. Share the decision across the real entry paths

Add a small `src/account/pwipe_launch.c` / `.h` owner for validated configuration,
the time/account decision and launch-screen rendering. Register it in
[src/Makefile](../../src/Makefile). Keep one policy, reused by the existing owners:

- **account.c:** successful password completion, account registration boundaries,
  account-menu/character-creation admission, existing-character confirmation and
  async completion, and reconnect before replacing the previous descriptor.
- **nanny.c:** the initial greeting and creation/final-entry boundaries, including
  `CON_RMOTD`. Cover normal, generic and Quick terminal choices.
- **ws_handlers.c:** successful password completion before automatic reconnect or
  auth success; registration; entry and chargen mutations; refusal while draining.
  Preserve the existing pending-authentication dispatch guard.
- **copyover.c:** validate the recovered owner's account against the gate before
  publishing the restored player. Release a refused load with the established
  cleanup path. Copyover is never the procedure for starting the wiped season.
- **comm.c:** boot-time loading only, plus output/dispatch integration if the
  existing drain handling needs a narrow adjustment for denied WebSocket sessions.

Use existing authenticated states and authoritative ownership. The presence of
`d->account` alone is not evidence that password verification finished. Reuse the
current racewar/admission ordering and pre-entry cleanup where appropriate, but
keep the launch decision separate from racewar timers and permissions.

### 3. Create the launch screen

Art direction: **"DURIS — THE WORLD REFORGED"**. A large Duris wordmark above a
sealed fortress gate, crossed blades and a skull/hourglass motif. Crimson fire,
gold edges, cold cyan runes and bright white launch information should make this
feel like a new season's title screen. Use original terminal art, not a colored
maintenance error or a copy of an existing greeting.

Add one text asset, `lib/information/pwipe_launch`, using printable ASCII geometry
and the existing Duris color tokens. Render it through the terminal-aware color
path; generic terminals receive the same readable art without escape sequences.
Keep the main composition within 76 visible columns, with CRLF output and a final
color reset. Avoid cursor-position dependencies and continuous animation.

Composition sketch only; implementation must produce and visually review the
finished artwork:

```text
       /\                     .---.                     /\
      /  \___________________/     \___________________/  \
     /    \                   DURIS                   /    \
    /______\          THE WORLD REFORGED             /______\
    |  []  |     .--------------------------------. |  []  |
    |      |     |    /\                  /\      | |      |
    |      |     |   /  \     .----.     /  \     | |      |
    |      |     |   \   \   / o  o \   /   /    | |      |
    |      |     |    \   \  |  /\  |  /   /     | |      |
    |      |     |     \   \  \_==_/  /   /      | |      |
    |      |     |      \   \   ||   /   /       | |      |
    |______|_____|_______\___\__||__/___/________|_|______|

                 THE OLD WORLD HAS FALLEN.
                 A NEW AGE WAITS BEHIND THE GATES.

              GATES OPEN: OCT 28, 2026 - 18:00 UTC
                 Sharpen your blades. Gather your allies.
                    Your next legend begins here.
```

While closed, show the title art at the normal terminal greeting, followed by the
usual account-name/password prompts so approved users can authenticate. After a
denied login show the launch screen with "The new season is being prepared.
Reconnect at 18:00 UTC." The final rendering must use the configured date/time,
not hard-coded text. Quick login may omit the introductory art but must still show
the denial and opening time. Approved users get a short preparation-access notice
before the normal menu. After opening, restore the ordinary greeting/menu flow.

For native WebSocket clients, use the existing authentication-error/text transport
with a readable launch message and UTC date. Verify that the actual client shows
the reason before disconnecting and that ANSI is rendered only by an ANSI-capable
view. If the current browser login UI cannot display the full art, its minimum
contract is a visible launch notice; a custom browser splash is separate UI work.

## Implementation sequence and acceptance

1. **Configuration and policy:** implement the shared owner and boot validation.
   Add `tests/async/test_pwipe_launch_gate.py` with an executable harness. Cover
   disabled mode; exact/case-varied approved accounts; unlisted/missing identities;
   invalid configuration; and the second before, exactly at, and after launch.
   Pass a test time to the policy, following the existing admission-test pattern;
   do not change the host clock or add a production clock override.
2. **Admission paths:** wire the boundaries above. Test correct/wrong passwords,
   an unapproved staff account, deferred registration, creation, existing-character
   entry, Telnet/TLS/WebSocket reconnect, async continuation and copyover. A denial
   must leave no new body, gameplay session, starter items or admission side effects.
   Existing blockers must still win for approved accounts.
3. **Presentation:** add the artwork and test generic/ANSI/Quick output, visible
   width, color reset, date consistency and complete output before disconnect.
   Inspect real terminal transcripts and the browser's denial display. Rendering
   the screen must not require a loaded character.
4. **Real local journey:** add a focused `run_pwipe_launch_gate_journey.py`, reusing
   the disposable fixture/client patterns of
   [run_news_prompt_journey.py](../../tests/async/run_news_prompt_journey.py).
   Use synthetic accounts and short future deadlines in private configuration.
   Prove approved entry and public refusal on real Telnet, TLS and WebSocket
   sockets, restart persistence, and public entry after the deadline without a
   reboot. Exercise MariaDB and flat-file admission; this does not add flat-file
   wipe support. Put generated evidence/artifacts under `bin/`.
5. **Wipe integration:** extend
   [run_pwipe_runtime_journey.py](../../tests/async/run_pwipe_runtime_journey.py)
   with the gate configuration before its first new-season boot. Prove preserved
   account credentials, approved Overlord entry, refusal of an ordinary surviving
   account, preserved config/art, and normal creation/gameplay after opening.
   Reuse established wipe/recovery coverage; no new comprehensive burn-in is needed
   for unchanged reset behavior.
6. **Closeout:** update this plan and the runbook with actual commands, revision,
   results and limitations. Run `./scripts/format.sh --check`, `make -C src`, the
   new focused tests/journeys and applicable existing password, login-banner/news,
   racewar-admission and WebSocket regressions. Validate the maintained flat-file
   build in isolation when qualifying that path. Do not wait for CI as a substitute
   for local proof, and do not claim skipped journeys passed.

## October 28 operating sequence, once implementation is qualified

1. **Prepare before downtime.** Verify the deployed source/binary and current
   supervised-wipe readiness against the existing plan/runbook. Prepare the art and
   disabled config. Verify the production host's UTC clock and the exact 18:00 UTC
   deadline. Verify that `mosheh` is the existing intended account and that its
   intended staff character meets the current recreation rules. The allowlist
   itself neither preserves a body nor grants Overlord permissions.
2. **Perform the separately authorized wipe.** Use the established backup,
   external-writer drain, five-minute confirmed wipe and same-epoch completion
   procedure. Do not modify the reset fence to start early. Keep competing launchers
   stopped through completion. The launcher deliberately leaves the completed
   season awaiting an explicit start.
3. **Arm before the first post-wipe boot.** While the server is stopped, persist
   `enabled=true`, the exact UTC timestamp and `allowed_accounts=mosheh` in the
   actual runtime configuration. Confirm the deadline is still in the future, then
   start the qualified binary with that configuration.
   Validation and the closed gate must be active before public listeners accept a
   player; there must be no unrestricted boot followed by a late lock command.
4. **Verify preparation access.** Log in normally as `mosheh`. From a separate
   unapproved account, verify the screen and refusal over every enabled player
   transport. Confirm that public registration/chargen is unavailable and that a
   restart retains the closed state. Check preparation changes deliberately:
   the world keeps ticking, and staff testing can affect the new season's state.
5. **Be ready before 18:00 UTC.** This is an automatic deadline, not a readiness
   detector. If preparation cannot finish, stop the server before the deadline,
   change the configured time under an owner-approved postponement and restart
   closed; communicate the revised start. Do not disable the gate to troubleshoot.
6. **At 18:00 UTC.** The next normal admission observes the open state. Verify a
   fresh ordinary-account login, new-character creation and game entry, with existing
   permissions/locks still respected. No reset, scheduler callback or restart is
   part of opening. Re-enable external writers/services according to the existing
   wipe runbook; the player gate does not fence those services.
7. **After opening.** Record the actual launch verification. Leave the expired
   configuration harmlessly open, then explicitly disable it in the next controlled
   configuration update so a future wipe cannot mistake this old timestamp for an
   armed gate. Reverting to a binary without the feature before launch would remove
   the restriction; keep the game stopped if such a rollback is required.

## Planning validation

This change contains documentation only. Account/password completion, character
entry, WebSocket reconnect, copyover, output draining, configuration, SQL reset and
launcher owners were inspected directly. The UTC timestamp was independently
converted to `1793210400`. Relative document links, Markdown fence balance,
whitespace and the sketch's ASCII/76-column bounds were checked. Implementation
tests, builds, runtime journeys and the production state have not been validated
for this proposed feature.

Scope review retained only the shared account/time rule, its actual entry paths,
the screen and their proof. Reusing the existing disconnect drain avoids adding
a waiting state or countdown loop; evaluating UTC on admission avoids a scheduler;
using the existing account credentials avoids another authentication mechanism.
