# Issue #115: artifact activation message repair

Tracking: https://github.com/LuminariMUD/Duris/issues/115
Status: implemented, locally verified, and published for review (2026-10-16).
PR: https://github.com/LuminariMUD/Duris/pull/116 (open, not a draft).
Implementation commit: `0fa0c3de94e9bce28e494b2033b4a5e2e921a56e`.
Branch: `branch/issue-115-activation-messages`, based on `origin/master` at
`b149b3ada6e8c9c1e041ad864772195173fef7c6`.
Worktree: `/home/aiwithapex/projects/duris-issue115`.

## Scope and ablation

Outcome: all eight Totem of Mastery opening whispers and the matching Circlet of
Light `mystra` whisper supply their existing object to `act()` so `$q` renders
the colored item name. Preserve wording, recipients, equipment gates, spell
choices, levels, targets, and solo/group behavior.

Non-goals: historical log rewriting, website masking, gameplay changes,
production rollout, migrations, or release tags. The primary checkout and
unrelated open PRs remain separate. This is one focused PR; no dependency stack
is necessary.

Files: `src/specs/specs.object.c`, the existing output integration regression
and its artifact cases, and this continuation document.

Proof: extend `test_word_output_integration.py` to execute both real procedures
through real `act()` and `send_to_char()`/queues; check actor and observer item
names, color preservation, public-log text, and spell arguments in solo/group
cases. Include the already-correct `lion` and `beblessed` branches as controls.
Run it before the fix to reproduce the defect, then after the fix, the existing
combat-outcome snapshot regression, changed-line formatting, and `make -C src`.

Ablation: reuse the existing formatter/queue harness instead of writing a
second formatter or new test framework. Repair the nine call arguments only;
no production helper, configuration, or fallback is needed.

## Continuation and acceptance

- Source inspection confirms the issue's nine missing object arguments on the
  current base. `$q` reads the fourth argument; the adjacent room/effect calls
  already provide it. Totem VNUM 1230 is assigned to `totem_of_mastery`.
- The original checkout reports `ENVIRONMENT=local`. This isolated worktree
  requires no credentials or running server for its focused executable checks.
- The public PvP HTTP API is not implemented in this repository (`site/` is the
  documentation site). A fresh production battle/API check needs the repaired
  server deployed first. Leave that checkbox pending for authorized rollout;
  do not claim an old recorded battle proves the repair, and do not rewrite it.
- The only production changes are the nine `0` -> `obj` fourth arguments.
  `spirit`, `hawk`, `panther`, `sense`, `raven`, `ward`, `elephant`, and `mystra`
  are repaired for the Totem, and `mystra` for the Circlet. All other arguments,
  message strings, and procedure behavior are unchanged.
- The regression first failed on the unchanged production source at the check
  that the actor's output contains no `(NULL)`. With the repair, 94 cases pass:
  nine Totem words x five accepted slots x solo/group, plus both Circlet words x
  solo/group. Unsupported-slot rejection also passes. The test executes the real
  procedures, formatter, sender and queues; spell calls are recorded instead of
  executed. The existing test log sink now writes into fixture `PlayerLog`
  instances; their public text equals each recipient's queued text byte for byte,
  including colors. No full-server gameplay or database/API capture is claimed.

## Verification completed, 2026-10-16

Run these from the worktree root:

```sh
python3 tests/async/test_word_output_integration.py
SANITIZE=1 python3 tests/async/test_word_output_integration.py
python3 tests/async/test_combat_outcome_transactional_cutover.py
./scripts/format.sh --check
clang-format --dry-run --Werror tests/async/artifact_activation_checks.inc
git diff --check
make -C src -j8
```

All passed. The output integration suite includes its existing chat, world,
combat/prompt, privacy, pager and queue checks alongside the new 94 activation
cases. AddressSanitizer/UndefinedBehaviorSanitizer reported no findings. The
combat-outcome suite passed all five tests, including public snapshot ownership
and serialized log preservation. The default MariaDB development build compiled
471 translation units and linked `bin/server/dms_new`; its retained local log is
`bin/analysis/issue115/build.log`. Generated build/test files remain under `bin/`.

Final ablation retained one existing harness with a case include, one source
repair, and this handoff. No formatter, website, database, or gameplay change was
needed. No additional defect was established during focused verification.

## Review and rollout handoff

The implementation is committed and pushed in PR #116 against `master`. The
pre-commit formatting and changed-line clang-tidy checks passed. No dependent
PR or release tag is needed. Next: review the PR; keep the issue open for the
remaining fresh public combat log and HTTP API comparison after an authorized
deployment. Source and executable verification are complete.

For that later acceptance, use disposable test characters, with an observer,
activate the Totem words and Circlet `mystra` in their supported slots, and capture
a new battle. Confirm both points of view contain the colored item names and no
activation `(NULL)`, then compare their stored public logs with the event API
response. `mystra` retains its self-targeted lightning effect. Existing event 3
remains historical evidence and is not expected to change. No merge, deployment,
production data change, historical rewrite, or release tag is part of this PR.
