# Issue #455: separate unread news from combat condition colors

Status: **implementation plan; implementation has not started**. Updated 2026-10-30.
Issue: [Duris #455](https://github.com/LuminariMUD/Duris/issues/455).
Branch: [branch/issue-455-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-455-plan).
Source baseline: origin/master at c9361959ceb6cb2a9004fea2c03748cef909dc3f.
Worktree: /home/aiwithapex/projects/duris-issue-455.

The completed #420 plan and qualification record are preserved byte-for-byte
in [plan-issue-420.md](plan-issue-420.md).

## Outcome

Render the existing prompt-frame color transition before the unread-news
suffix. Combat condition words keep their current severity colors; the space,
`(news)` marker and closing `>` use the resolved prompt-frame foreground. Keep
the exact visible wording, spacing, marker position and terminal framing.
The marker still appears only when the owning character has unread news.

For example, the default raw markup changes from
`EC:&+R pretty hurt (news)&+g> ` to
`EC:&+R pretty hurt&+g (news)> `. A player-selected prompt foreground replaces
the default green through the existing profile resolver.

## Findings checked against the code

Paths and line numbers refer to the baseline above.

1. **The reported ordering defect is current.** In
   [make_prompt](../../src/net/prompt.c), lines 289-295 construct the footer
   with the news suffix first and output_role_markup(...) second. The footer
   is appended at line 415 after combat fields, optional staff visibility and
   AFK status. The issue's final append line and capacity expression are stale:
   the current code uses pPromptCap + footer_size, with footer space reserved
   before appending combat fields. Preserve this protection.

2. **Either condition can be the final colored field.** The tank path at
   lines 324-352 and enemy path at lines 379-404 choose severity foregrounds
   without a trailing reset. They can also append cyan `(warded)`. A tank-only
   prompt can exhibit the problem without an EC field. Visibility can leave
   magenta active; AFK has its own explicit reset. The shared footer is the
   common boundary that needs correction.

3. **The frame color is configurable.** Lines 89-96 resolve the owner's
   OutputChannel::Prompt profile with a Static caller policy. In
   [output_role_markup](../../src/net/output_profiles.c), lines 672-681,
   OutputRole::None with use_base=true selects the profile base foreground or
   falls back to the existing `&+g`. A new hard-coded `&n` or green marker
   would bypass the established frame selection. Reuse the existing call.

4. **Ownership and notification state are separate from this defect.**
   [has_unread_news](../../src/player/news.c), lines 17-23 and 76-80, compares
   published content with the owning PC's acknowledgement through GET_PLYR.
   make_prompt also obtains that owner before reading preferences. No change
   to news acknowledgement, publication or persistence is needed.

5. **Existing executable coverage misses color inheritance.**
   [test_word_output_integration.py](../../tests/async/test_word_output_integration.py)
   extracts the real make_prompt, queue, pager and news-command bodies and
   links the production ANSI/profile/news code. Its
   [news_prompt_checks.inc](../../tests/async/news_prompt_checks.inc) already
   covers unread/read, layouts, ANSI/MSP, smart prompts, auxiliary prompts,
   owner/body switching and long-name footer preservation. It does not assert
   the news marker's foreground after a combat condition.
   [combat_prompt_checks.inc](../../tests/async/combat_prompt_checks.inc)
   demonstrates visible-offset attribute assertions with AnsiString.

6. **Color separation and client parsing are different claims.**
   [process_output](../../src/net/comm.c), lines 4660-4682, converts queued
   markup through AnsiString::term; TERM_GENERIC removes color attributes.
   A corrected transition separates the server's styled runs. It cannot change
   a client's condition regex after that client strips all colors: the visible
   text remains identical. The issue supplies no failing client trigger, and
   this checkout does not establish that client's parsing contract. Do not
   claim universal trigger compatibility from a server color test. If an
   affected client's trigger is supplied during implementation, replay the
   before/after output through that actual trigger and identify any separate
   client fix without changing this server prompt format speculatively.

## Executable planning evidence

The unchanged baseline passes:

    SANITIZE=1 python3 tests/async/test_word_output_integration.py

A temporary probe reused that harness and inserted checks into a temporary
copy of its news fixture; no tracked C/C++ or test file was changed. With real
make_prompt and production AnsiString under ASan/UBSan, it exercised:

- TC only, EC only, and both conditions, at 20/100 health;
- one-line and two-line prompts with resource fields enabled;
- TERM_ANSI and TERM_MSP;
- default green and a custom bright-cyan prompt foreground.

All 24 combinations rendered `(news)` in the condition's bright red instead
of the frame foreground. Representative actual raw output was
`&+g<&+r 20h&n TC:&+R pretty hurt (news)&+g> &n`; the custom-frame case
ended `pretty hurt (news)&+C> &n`. This confirms the defect and the coverage
gap; these are baseline observations, not evidence that a fix has passed.
The probe's world, visibility, logging and transport boundaries are fixtures;
process_output is stubbed. No booted-world, socket/client or production
reproduction is claimed. Temporary probe sources are removed after planning.

## Files and implementation sequence

Expected implementation changes: src/net/prompt.c and
tests/async/news_prompt_checks.inc. Update this plan with final evidence.
No new test runner, production helper, header or configuration is needed.

1. **Extend the existing news fixture first.** Use its real fighting pointers
   and same-room characters to cover TC-only, EC-only and combined conditions.
   Assert that condition words retain their severity attributes, while the
   space before `(news)`, every marker character and `>` match the frame
   foreground. Include default and custom frame colors that differ from the
   tested injury color. The new boundary assertions must fail on the baseline.

2. **Reorder the two existing footer arguments.** Keep the same format string,
   output_role_markup call, news predicate, footer buffer, capacity reservation
   and terminal suffix. Pass frame markup first and the conditional news suffix
   second. This yields frame markup followed by optional ` (news)` and `> `.
   Apply the correction for every ordinary prompt, using the existing common
   footer rather than inserting resets in individual condition branches.

3. **Prove the boundary and retained behavior together.** Extend the same
   fixture with the cases below. Reuse its production AnsiString conversion
   to inspect terminal output as well as raw markup. Follow the actual
   process_output sequence for TERM_GENERIC: clear colors before term().
   Preserve registry/preferences and fixture state between cases so custom
   profiles and unread state cannot leak into existing checks.

4. **Build, review and record results.** Run the commands below, review the
   entire diff, and record exact results and limitations in this plan before
   committing implementation. Artifacts stay under bin/. No CI wait is needed.

## Proof and acceptance

- Use a bright-red injured condition on each of TC and EC and retain its
  exact words and severity attribute. The footer is shared by every severity;
  duplicating the entire unchanged health-threshold ladder is unnecessary.
- Cover TC-only, EC-only and combined fields in the 24-case layout/terminal/
  frame matrix used by the baseline probe. Both marker and closing bracket
  must use the frame foreground. An injury color matching the frame must not
  be the only test, since it could hide the old ordering.
- With PROMPT_WARD, a positive final tank/enemy ward stays cyan and `(news)`
  returns to the frame color. Include the optional trailing visibility and
  AFK fields as focused shared-footer cases.
- Read/acknowledged and empty-publication controls omit `(news)`; they retain
  the old closing-frame markup. Noncombat prompts receive the same marker
  frame color. Assert exactly one marker when unread.
- Compare expected plain text, including spaces, field labels, condition
  wording and one/two-line layout. The ANSI boundary changes; visible text
  does not. Render representative default/custom cases through the production
  terminal converter and verify the marker/frame foreground there too.
  TERM_GENERIC output stays free of color escapes with unchanged text.
- Keep MSP opening/closing tags, its terminal reset, the normal final reset,
  and the reserved footer under long-name truncation. Retain the existing
  smart-prompt, pager/editor/confirmation/menu, no-prompt and switched/morphed
  owner controls in the same executable suite.
- The regression's baseline failure and fixed success must be recorded.
  Passing raw marker-presence tests alone is insufficient. The harness does
  not certify a live client trigger or full game-loop combat timing.

Commands after implementation:

    SANITIZE=1 python3 tests/async/test_word_output_integration.py
    make -C src
    ./scripts/format.sh --check
    python3 tests/async/test_documentation_contract.py
    git diff --check

Use the project's local/development build configuration. This formatting-only
behavior change needs no new database, persistence or restart journey. The
existing full news journey exercises acknowledgement/reload/copyover/restart,
but does not assert this combat color boundary; rerunning both persistence
backends would not replace the targeted regression above.

## Ablation and non-goals

Keep the single shared-footer correction because the 24 executable cases
demonstrate the failure there. Keep the existing profile resolver and footer
reservation because custom colors and bounded terminal framing depend on them.
Extend the existing integration fixture because presence-only checks missed
the defect and it already executes the affected function and ANSI code.

Drop per-condition resets, a news-specific color preference, a new semantic
role, a footer helper, a parser/protocol redesign and a second test framework:
none is necessary to establish the required boundary. Do not refactor health
thresholds, change combat/ward mechanics, add a new visible separator or move
the marker outside the prompt. Smart-prompt design, unrelated prompt cleanup,
news storage, migrations, external-client changes, deployment and full burn-in
are outside this task. No player help change is needed for unchanged wording
and controls. The only extra planning file preserves the previous #420 record.

## Tracking, estimate and planning validation

GitHub #455 is the work item for this branch. An open-PR search found no
existing #455 PR. Create the branch's native link in the issue's Development
section and add the committed plan link to the issue. Keep #455 open: a
planning commit must not use an issue-closing keyword. No additional work item
is justified by the inspected code or the issue's empty comment history.

Estimate: **45-75 minutes of my active implementation time**, including
regression-first coverage, the footer change, sanitizer checks, the required
local build, final review and implementation commit/push. Roughly 20-30 minutes
is regression coverage, 5 minutes is the production edit, and 20-40 minutes is
compilation, validation and handoff. Allow up to 90 minutes if fresh-build or
terminal-fixture setup needs repair. External review, merge/deployment and any
separately demonstrated client parser change are excluded.

Planning qualification completed:

- SANITIZE=1 python3 tests/async/test_word_output_integration.py: passed.
- Temporary 24-case baseline probe under ASan/UBSan: every case confirmed the
  reported inheritance defect; no sanitizer finding. Probe sources removed.
- python3 tests/async/test_documentation_contract.py: all 14 tests passed.
- git diff --check: passed.
- cmp confirmed plan-issue-420.md is byte-identical to the baseline plan;
  SHA-256: 9306f27c4fad0663f588bb44f6b05fc8492d368d9bffb872c5c325570020f8e7.

Only this plan and preservation of the previous plan are committed. No
production implementation or full server build is part of this commit.
