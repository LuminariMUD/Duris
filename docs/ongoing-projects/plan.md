# Issue #456: announce scavenger floor pickups before equipment use

Status: **planned; implementation has not started**. Updated 2026-10-30.
Issue: [Duris #456](https://github.com/LuminariMUD/Duris/issues/456).
Branch: [branch/issue-456-plan](https://github.com/LuminariMUD/Duris/tree/branch/issue-456-plan).
Baseline: `origin/master` at `c9361959ceb6cb2a9004fea2c03748cef909dc3f`.
Worktree: `/home/aiwithapex/projects/duris-issue-456`.
The branch is linked to #456 through GitHub's Development relationship.

The previous #420 plan and qualification record are preserved byte-for-byte in
[plan-issue-420.md](plan-issue-420.md). This document applies the repository's
[ablation skill](../../.agents/skills/ablation/SKILL.md). This delivery authorizes
planning, commit/push and issue linkage; the implementation below is future work.

## Outcome

A visible `ACT_SCAVENGER` NPC picking an ordinary object up from the floor emits
one normal room pickup message before any resulting wear or wield message.
Successful pickups that leave the object in inventory also emit that pickup
message. Use the existing `get()` visibility and successful Slip rules. Failed
pickups must not announce success or reach equipment evaluation. Preserve item
selection, transfer checks, object identity checks and equipment decisions.

## Findings checked against the codebase

1. **The reported call is still silent.** In `src/mob/mobact.c:8050-8156`,
   `event_mob_mundane()` selects the best eligible object. Its floor arm at
   lines 8144-8153 saves the pointer and UID, calls
   `get(ch, best_obj, NULL, FALSE)`, re-resolves the object, then calls
   `CheckEqWorthUsing()` only when that same live object is carried by the NPC.
   This confirms the defect independently of the issue's historical line numbers.

2. **The normal pickup function already provides the required publication.**
   `src/cmd/actobj.c:462-820` rejects invalid/bound items, scraps, prohibited NPC
   pickups, triggered traps and hitched items before reaching the floor transfer.
   Lines 807-812 remove the object from the room, emit the actor message, emit
   the room message when `showit && !slip`, and attach it to the actor.
   `act(..., 1, ..., TO_ROOM)` retains normal invisible-actor filtering.
   Enabling `showit` therefore reuses existing checks and message formatting.
   It does not mean every observer sees every pickup: successful Slip and normal
   visibility rules remain authoritative. NPC skill lookup exists in
   `src/core/utility.c:5169`, so do not assume Slip is exclusively a player rule.

3. **Equipment publication follows pickup on the current synchronous path.**
   `CheckEqWorthUsing()` and `IsBetterObject()` in
   `src/mob/mobact.c:7051-7160` eventually call `wear(..., 1)` for usable gear.
   `get()` and `obj_to_char()` (`src/world/handler.c:1891-2005`) perform this
   floor transfer immediately. The comment at `mobact.c:8149-8150` referring to
   an `item_get_completion` callback is obsolete; searching current `src/` finds
   that name only in the comment. Do not build a deferred-publication fix from
   that comment or from the older collector implementation. Retain pointer/UID
   re-resolution because `get()` can consume/extract objects, including coins.

4. **Container scavenging already has a separate announcement.** The sibling
   arm calls `get(..., best_obj, FALSE)` and emits its existing "gets some stuff"
   room text. Its policy is separate from this floor defect. Enabling all
   scavenger `get()` calls would change that behavior and can duplicate messages.
   The humanoid coin-rescan loop immediately above scavenging is also separate.

5. **The historical change is real; the example location is not a fixture.**
   `git show 4764ebf2e -- src/mob/mobact.c` confirms that the old direct floor
   transfer and explicit room `act()` were replaced by the silent `get()` call.
   Mobile 16042 exists in `areas/mob/pineholl.mob:695` and its act flags contain
   `ACT_SCAVENGER` (`src/core/defines.h:1162`). Its checked-in reset is room
   16109 (`areas/zon/pineholl.zon:300`), whereas the issue reports room 16128.
   Wandering or live state may explain that observation; neither a live location
   nor a booted-world reproduction was verified during planning. Use an isolated
   synthetic scavenger for repeatable proof; no area edit is indicated.

6. **Existing tests can supply the proof, with one necessary fixture repair.**
   `tests/async/test_get_trap_lifecycle.py` compiles real production pickup and
   trap functions under ASan/UBSan, including an NPC success case, but does not
   drive the scavenger call site or distinguish room-message ordering.
   Its current `credit_coins(P_char, int64_t)` stub fails to compile against the
   denomination-array signature now used by `actobj.c:328-329`.
   `tests/async/run_npc_container_claim_journey.py` already boots a disposable
   flat-file world, seeds a staff observer, loads a real scavenger and inspects
   its inventory/equipment. It provides a suitable existing socket journey to
   extend with floor cases. Its historical "claim" name is not evidence that
   current floor pickups use deferred claims.

## Non-goals

No shared `get()` behavior change, manual success `act()`, new message helper,
configuration, queue, callback, migration or ownership protocol. No change to
Slip, visibility, NPC intelligence/timing, selection priority, equipment ratings,
container-loot messages, coin rescanning, world content or player help. No
production operation, deployment, full burn-in or hosted-CI dependency.

## Files and implementation sequence

Expected changes: `src/mob/mobact.c`,
`tests/async/test_get_trap_lifecycle.py`,
`tests/async/run_npc_container_claim_journey.py`, and this plan's completion
record. No new production file or general test framework is needed.

1. **Repair and extend the existing native regression first.** Update only the
   outdated coin-credit fixture signature to accept the production denomination
   array, preserving its existing success/refusal controls. Run the unchanged
   scenarios to establish a usable baseline. Then extract the actual production
   scavenger floor arm and `find_scavenged_object()` into this existing fixture;
   invoke it with real `get()` and controlled room/object services. A direct
   fixture call to `get(..., TRUE)` alone would miss the defective caller.
   Record `act()` audience and order, and use a controlled equipment-evaluation
   boundary to check that the same carried object is evaluated after pickup.
   The visible NPC success assertion must fail on the unmodified floor caller.

2. **Enable the existing floor message at its caller.** Change only the floor
   call to `get(ch, best_obj, NULL, TRUE)`. Remove the adjacent obsolete
   deferred-completion comment; retain saved pointer/UID, re-resolution and the
   carried-by guard. Leave the container calls and shared pickup implementation
   unchanged. Re-run the native regression and require the following cases:
   - Visible eligible NPC: exactly one room pickup before equipment evaluation.
   - Eligible object kept in inventory: exactly one pickup, without a wear event.
   - Refused/trap-rejected pickup: no success message or equipment evaluation.
   - Consumed/extracted object: no stale-pointer dereference or equip attempt.
   - Successful Slip: existing room-message suppression remains intact.
   Retain existing player, container, coin, trap and refusal coverage. A fixture
   equipment boundary proves call ordering, not the real equipment algorithm.

3. **Prove the observed behavior on a disposable server.** Extend the existing
   NPC container journey with two uniquely named floor objects: a takeable
   wearable for an eligible humanoid NPC with an empty matching slot, and a
   takeable non-wearable item that stays in inventory. Ensure the NPC has no
   Slip and the observer can see it. Preserve the existing container scenario.
   Capture the observer transcript continuously across drop and scavenger tick;
   do not clear asynchronous pickup messages while polling. Bound the wait and
   synchronize staff commands on their own replies and following prompts.
   Assert exactly one rendered floor pickup, its position before the real
   wear/wield message for the same object, and final NPC custody via staff
   inspection. For the second object require pickup without equipment text.
   Reuse the current fixture, ports, inspector, socket client and cleanup. Keep
   this existing manual journey directly runnable; no new runner layer is needed.

4. **Complete focused qualification and update this record.** Run the commands
   below, record exact results and fixture limitations, reread the final diff,
   and keep only changes required by #456. Do not claim a native stub proves
   observer output or that a flat-file journey qualifies MariaDB persistence.

## Proof and completion commands

Run from the worktree root after implementation:

```sh
python3 tests/async/test_get_trap_lifecycle.py
python3 tests/async/test_mobact_coin_pickup_rescan.py
./scripts/format.sh --check
make -C src -j6
python3 tests/async/test_flatfile_player_repository.py \
  --build-inspector "$PWD/bin/tests/coin-death-inspector"
make -C src PERSISTENCE_BACKEND=flatfile \
  BIN_ROOT="$PWD/bin/qualification/issue456" \
  OBJDIR="$PWD/bin/qualification/issue456/objects/server" \
  SERVER_BIN_DIR="$PWD/bin/qualification/issue456/server" \
  DMS_BINARY="$PWD/bin/qualification/issue456/server/dms_new" -j6
python3 tests/async/run_npc_container_claim_journey.py \
  "$PWD/bin/qualification/issue456/server/dms_new"
python3 tests/async/test_documentation_contract.py
git diff --check
```

The installed pre-commit hook also formats and runs clang-tidy on staged C/C++
lines. All compiled artifacts and temporary qualification evidence stay under
ignored `bin/`; disposable gameplay state is private and removed by the journey.

Completion requires the failing-before/passing-after caller regression, real
observer pickup-before-equipment output, inventory-only pickup, preserved
container behavior, passing focused checks and builds, and an updated handoff
with any remaining limitations. Implementation is not complete merely because
`FALSE` has changed to `TRUE`.

## Ablation decisions

**Keep** the caller flag change: without it ordinary floor pickup stays silent.
**Keep** object identity/custody guards: `get()` may remove the selected object.
**Simplify** publication to the existing `get()` message; a second `act()` risks
false or duplicate success and bypasses its Slip/visibility policy. **Drop**
deferred-completion work: the traced floor path is synchronous. **Keep** the
small native-fixture repair and caller coverage because the existing check does
not compile and does not exercise this caller. **Reuse** the existing socket
journey because the requirement concerns actual observer text and equipment
order. **Drop** a new harness, automatic-runner wrapper, area changes, broad
ownership cleanup and unrelated test-suite repair: none is needed for this fix.

## Planning validation and estimate

During planning, on the unchanged production baseline:

- `python3 tests/async/test_mobact_coin_pickup_rescan.py`: passed.
- `python3 tests/async/test_get_trap_lifecycle.py`: failed to compile because its
  scalar coin-credit stub cannot accept the current denomination array. No
  runtime assertions ran; this is an inherited fixture failure, not evidence
  that #456 is fixed or reproduced in a running server.
- `gh issue develop 456 --list -R LuminariMUD/Duris`: confirms this linked branch.

- `python3 tests/async/test_documentation_contract.py`: all 14 checks passed.
- `git diff --check`: passed after normalizing the final newline.
- Archived #420 plan: compared byte-for-byte against the baseline Git blob.

No game-server build or gameplay journey is claimed for this plan-only change.

**My implementation estimate: 75-120 minutes of active work**, including the
fixture repair, failing-before/passing-after regression, tiny production edit,
real-server floor scenarios, builds, focused qualification and handoff. Roughly
20-35 minutes cover native proof and the edit, 25-40 cover the journey, and
30-45 cover builds, verification and review. Unexpected fixture/build defects
may extend that range; review waiting, merge and deployment are excluded.
