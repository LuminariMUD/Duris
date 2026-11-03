# Issue #611: preserve assigned NPC ship pursuit

Status: implementation and local acceptance complete; preparing the focused review PR. Updated 2026-11-03.

- Work item: [Duris #611](https://github.com/LuminariMUD/Duris/issues/611).
- GitHub-linked development branch: [branch/issue-611-npc-pursuit](https://github.com/LuminariMUD/Duris/tree/branch/issue-611-npc-pursuit).
- Local worktree: `/home/aiwithapex/projects/duris-issue-611`.
- Inspected base: `96ef0ed6b1c1e70edf8aaf560712edc322ce70f6` (`origin/master` when the worktree was created).
- Method: [ablation](../../.agents/skills/ablation/SKILL.md), applied to the current source, existing tests, and every acceptance criterion below.
- Compatibility context: closed [#474](https://github.com/LuminariMUD/Duris/issues/474), fixed by [PR #471](https://github.com/LuminariMUD/Duris/pull/471). Preserve its recovery behavior; neither item needs reopening or a second closure.

The earlier flight-transport plan is preserved verbatim after this plan.

## Outcome

Pirates and hunters spawned to attack different player ships must retain those separate, valid assignments while approaching from approximately 45 map rooms away. Escort retaliation must also keep pursuing a valid attacker beyond player contact range. Player lock range, five-minute inactivity expiry, combat refreshes, and the existing 180-second battle-stations/summon cooldown must continue to work.

This addresses the reproduced pile-on mechanism: the heartbeat currently discards each attacker's intended victim, then ordinary replacement selection can send all attackers after the same ship. A successful fix prevents that forced loss of valid assignments. It does not guarantee a universal limit on attackers per ship: legitimate reacquisition after a victim becomes unavailable still uses existing selection rules.

## Non-goals

No change to spawn positions, spawn odds, merchant encounter flags, frag-based difficulty, diplomats, player contact radius, replacement-target ordering, or encounter caps. No new persistent fields, migration, configuration option, target registry, telemetry system, production operation, or deployment. The reported group-leader/high-ranking-player preference is not an established selection rule. Reconstructing Rani's runs requires incident evidence that this checkout cannot supply.

## What the code and executable checks establish

Line numbers below refer to the inspected base. A comparison with the issue's cited `27f4c71cd` found no differences in the relevant ship sources, map-coordinate function's file, or lifecycle test.

1. **The initial assignment is explicit.** [ship_npc.c](../../src/ships/ship_npc.c):1346 computes a 45-room spawn offset for pirates/hunters; at 1390 it assigns `ship->target` and `NPC_AI_ENGAGING`. Escorts start with a separate `escort` relationship; `NPCShipAI::escort_attacked_by()` at [ship_npc_ai.c](../../src/ships/ship_npc_ai.c):486 assigns their combat target.
2. **The expiry condition has the reported scope error.** [ship_base.c](../../src/ships/ship_base.c):2527 applies `!ship_target_in_contact(ship)` to every ship. Only the `T_TARGET_IDLE == 0` branch excludes NPCs. Timer decrement precedes this block; NPC AI runs later, at 3138.
3. **The contact predicate combines availability and player range.** [ship_utils.c](../../src/ships/ship_utils.c):1133 rejects unloaded, sinking, docked, or non-shared-map targets before checking 3-D range against `35 + scout bonus`. Removing its use for NPCs without preserving those availability checks would drop behavior the acceptance criteria explicitly require.
4. **AI engagement and reacquisition are separate updates.** `NPCShipAI::activity()` at 262 fills contacts with `getcontacts(ship, false)`. An engaging ship whose target is missing changes to CRUISING and breaks; a later cruising update calls `find_new_target()`. `find_current_target()` at 623 checks the current target against enumerated contacts, skipping docked and sinking ships; failure starts maintenance but does not itself null the target pointer.
5. **Replacement selection explains convergence but predates this regression.** `find_new_target()` at 649 takes the first valid non-diplomat contact. [ship_utils.c](../../src/ships/ship_utils.c):1150 enumerates the ship-object hash, subject to `MAXSHIPS`. `getcontacts(..., false)` imposes no distance cutoff; [map.c](../../src/world/map.c):388 requires a shared map zone without a 50-room bound. Neither active selection loop compares frags, group leadership, or existing attackers. `is_valid_target()` at 739 rejects docked/sinking ships but currently has no unloaded check, so preserving rejection of unloaded targets also requires checking reacquisition.
6. **Lifetime cleanup already has an owner.** `dock_ship()` at [ship_base.c](../../src/ships/ship_base.c):3161 calls `clear_references_to_ship(..., false)`. `delete_ship()` calls it with `true` before freeing the ship; deletion also clears AI escort/boarding references. `try_unload_npc_ship()` at [ship_npc.c](../../src/ships/ship_npc.c):1566 uses that deletion path. Preserve these paths and the sinking sweep's intentional early return; do not replace raw-pointer cleanup with contact checks or runtime-pointer guesses.
7. **Player recovery is already exercised, with a specific NPC blind spot.** [test_npc_ship_deletion.py](../../tests/async/test_npc_ship_deletion.py) executes the real heartbeat, lock, fire, volley, ram, summon, docking, and teardown functions. Its NPC AI and contact enumeration are stubs; the escort case is at zero distance. The fixture proves player recovery/lifecycle controls, but cannot prove distant NPC engagement. [ship_shop.c](../../src/ships/ship_shop.c):800 still gates summons on `T_BSTATION`; [ships.h](../../src/ships/ships.h):94 defines `BSTATION` as 180.

Planning verification on this worktree:

- `python3 tests/async/test_npc_ship_deletion.py` passed all cases in MySQL and flat-file builds with ASan/UBSan. This includes idle-lock recovery, combat refresh, actual summon refusal/acceptance at the cooldown boundary, docking, sinking, purge, unload, and reference cleanup.
- After inspecting the supplied investigation fixture and its stubs, reran `python3 bin/tests/pirate_target_investigation.py` from #611 against the current source. Both backend builds reproduced three distinct 45-room assignments being cleared on update 1, all three selecting the same first eligible hash ship on update 2, and retaining that replacement on update 3. Replacing only the heartbeat in the generated harness with its pre-#471 body retained all three original assignments. Both variants ran under ASan/UBSan without findings. Independent selection cases also acquired a first-hash target at 145 rooms.

The investigation script was generated under ignored `bin/` and removed after validation; its reproducible source remains in #611. It seeds spawn-equivalent state, holds ships stationary, and stubs navigation/combat/world/persistence services. It proves the heartbeat/target-selection mechanism; it does not execute random encounter spawning, establish production settings, or reproduce a live sailing trip. No C/C++ source has been changed, so full server builds belong to implementation verification below.

## Ablation decisions

- **Keep the NPC/player distinction at lock expiry.** Both range and inactivity policy are player-lock rules. Exempting only the inactivity timer leaves the reproduced failure intact.
- **Keep NPC target availability separate from player range.** Use existing loaded/docked/sinking flags and `calculate_map_coords()` to reject unavailable NPC targets without imposing a distance limit. Keep this small check local to the heartbeat and reuse its single target-clearing/message path. The existing player contact helper stays unchanged. No new helper API, range option, or persistent state is needed.
- **Keep unloaded-target rejection during replacement selection.** Add the loaded check to the existing AI validity predicate so the same heartbeat cannot clear an unloaded target and immediately reacquire it. Preserve all other eligibility/ordering rules. This is needed for #611's explicit unavailable-target acceptance criterion.
- **Keep one focused real-AI regression alongside the lifecycle fixture.** A dedicated small executable fixture avoids changing every lifecycle test to depend on AI/navigation. Reuse `_paths.extract_function`, headers, sanitizer/compiler conventions, and existing hash/lifetime patterns. Do not build a general harness framework or use runtime string replacement of another test as the maintained solution.
- **Drop encounter rebalance and target-selection redesign.** Randomization, nearest-target preference, per-player caps, spawn-distance changes, and extra tracking state would change unrelated gameplay without fixing the expiry boundary. Whole-map first-match reacquisition remains a separately evaluated concern.
- **Drop a mandatory production investigation or new logging subsystem.** Existing source and deterministic executable evidence are sufficient to implement this fix. Future incident correlation can use the existing spawn log and runtime observations after a normal deployment.

Every retained change addresses a traced failure or an explicit acceptance criterion. The small availability check and unloaded guard prevent the simple NPC exemption from weakening target safety.

## Files

- [src/ships/ship_base.c](../../src/ships/ship_base.c): separate NPC target availability from player range/inactivity expiry; clarify the nearby comment.
- [src/ships/ship_npc_ai.c](../../src/ships/ship_npc_ai.c): reject unloaded replacement candidates in the existing validity check.
- `tests/async/test_npc_ship_targeting.py` (new): deterministic production spawn-assignment/heartbeat/AI/contact regression, compiled for both backends under sanitizers.
- [tests/async/test_npc_ship_deletion.py](../../tests/async/test_npc_ship_deletion.py): retain existing player-recovery and lifecycle controls; extend only where the acceptance matrix below lacks a real-path assertion, such as unavailable-target expiry through the heartbeat.
- This document: record final implementation evidence and any justified scope changes. Preserve the earlier project's plan.

Read-only supporting sources include `ship_utils.c`, `ship_npc.c`, `map.c`, `ship_control.c`, `ship_combat.c`, `ship_shop.c`, and `ships.h`. No changes to those files are presently required.

## Implementation sequence

Execution checkpoint (2026-11-03): verified the worktree is clean at `744f4be77`,
the remote implementation branch matches it, and master still matches the inspected
base. The plan remains minimal: retain the two production changes and focused
executable evidence; no encounter policy, schema, deployment, or release tag is needed.
The source fix and its regression form one reviewable chunk and will be published
together once local verification passes. The maintained fixture compiled on both
backends before the fix: group retention and escort retaliation failed on their
first heartbeat, and the unavailable-target case failed because an unloaded target
was reacquired. These are expected baseline assertion failures, without sanitizer
diagnostics. The two production corrections are now applied; final passing evidence
is recorded in the implementation handoff below.

### 1. Turn the demonstrated failure into maintained executable coverage

Add `test_npc_ship_targeting.py` using the real `ship_activity()`, `NPCShipAI::activity()`, `find_current_target()`, `find_new_target()`, `is_valid_target()`, `update_target()`, and escort retaliation. Execute production hash iteration, contact enumeration, range/bearing calculation, and `calculate_map_coords()`; these are the boundaries the existing fixture stubs away.

Use deterministic map rooms and the real outer `try_load_npc_ship(target, type, level, ch)` overload to exercise the 45-room placement/assignment logic. Stub only its lower-level hull/crew factory and unrelated world services. Hold speed/orders at zero after assignment when checking target stability; assert the produced target, AI mode, and out-of-player-contact distance first. This executes the assignment path without claiming coverage of random encounter odds or full navigation. Use the existing extraction approach; do not copy production target logic into the fixture.

The four-player/three-attacker setup must derive actual hash order rather than rely on allocation addresses. Put an eligible decoy first, with zero frags and `ATTACKBYNPC`, and assign the other three victims to a pirate/hunter mix. Vary the intended victims/frag rankings while keeping a competing eligible first contact. Verify that current code fails the assignment-retention assertions before applying the fix. Record baseline failure as expected evidence, then require the same assertions to pass after implementation.

Test stubs must be explicit: captains/ammunition available; unrelated firing, steering, map rendering, world I/O and persistence controlled. Count the selected maneuver/engagement path so a no-op AI or an early return cannot masquerade as preserved pursuit. Include an escort whose real `escort_attacked_by()` assignment starts beyond player contact range.

### 2. Correct the expiry boundary and retain unavailable-target handling

In the heartbeat's existing target-loss block:

- For players, retain `ship_target_in_contact()` and expiry when `T_TARGET_IDLE` reaches zero, preserving fractional position, altitude and scout bonuses.
- For NPCs, clear the target only when it is unloaded, docked, sinking, or no longer shares a usable map with the attacker. Use existing flags and `calculate_map_coords()`; allow valid same-map pursuit beyond 35–37 rooms and with an expired player inactivity timer.
- Keep one clearing/message path and the subsequent battle-stations refresh. Do not reorder timers, movement, AI updates, or sinking/deletion iteration.

In `NPCShipAI::is_valid_target()`, reject unloaded candidates before the existing current-target/race checks. This must prevent immediate or subsequent reacquisition of an unloaded player hull still present in the hash. Leave diplomat handling, first-match order, current-target preservation, and the AI's ordinary mode transitions intact.

Do not add a maximum NPC pursuit range. Map loss and lifecycle unavailability are distinct from a valid long approach. Retain the existing `MAXSHIPS` contact capacity and AI behavior if its current target is absent from that capped contact list; expanding that policy is outside this fix.

### 3. Prove each acceptance criterion

- **Pirates and hunters:** exercise both types at the actual approximately 45-room spawn separation for scout bonuses 0/1/2. Start `T_TARGET_IDLE` at both zero and one; run repeated heartbeat/AI updates across expiry and for more than 300 ticks with valid stationary targets. Assert the same target, ENGAGING mode, and an executed pursuit/maneuver path. Cover basic and advanced dispatch with controlled maneuver stubs.
- **Group convergence:** three attackers retain three separate victims despite an eligible first-hash decoy, different frag rankings, and `ATTACKBYNPC` on that decoy. Repeat with changed victim assignments so success cannot depend on one favorable hash arrangement. Check several updates, including the first and second updates that formerly lost/replaced the victims.
- **Escort pursuit:** call real retaliation, verify engagement beyond player range through real heartbeat/AI updates, and preserve the separate escort relationship.
- **Unavailable and destroyed targets:** run docked, sinking, unloaded, off-map and different-map-zone cases for NPC and player locks. Assert lock loss and safe mode transition where the attacker is eligible for an AI tick. Keep an unloaded candidate in the hash and ensure cruising cannot select it. Through actual docking, purge/deletion and NPC unload paths, verify target/escort/boarding references clear before free, unrelated references survive, and the next heartbeat has no invalid access. Reuse lifecycle tests for their existing teardown coverage.
- **#474 compatibility:** retain 300-tick idle player-lock expiry with no captain aboard, renewal by outgoing fire/incoming volleys/ram attempts, explicit `lock off`, and out-of-range expiry. Keep summon blocked while battle stations is positive and accepted only after the existing 180-tick stand-down; cover the lock's final idle tick and cooldown boundary. Death recovery is represented by an absent captain in the isolated fixture; do not describe that as a complete character-death journey.
- **Player contact geometry and shared buffers:** keep the existing 35/36/37-room scout boundaries, fractional and altitude cases. Extend the helper's sentinel assertion to the entire shared `contacts[]` buffer so the expiry probe cannot silently corrupt another ship's prepared contacts. Exercise production contact enumeration in the new AI test, without requiring that buffer to remain unchanged across the AI's intentional refresh.
- **Both persistence builds:** compile and execute the new test and existing lifecycle suite with MySQL and `__NO_MYSQL__`, under ASan/UBSan. Every case above must have a passing executable assertion or explicitly named existing control; a contact-helper-only pass is insufficient for assignment retention.

### 4. Build, review, and record evidence

Run the narrow suites during development, then the required local server builds and changed-line checks. From this worktree:

```sh
python3 tests/async/test_npc_ship_targeting.py
python3 tests/async/test_npc_ship_deletion.py
make -C src -j8
make -C src -j8 PERSISTENCE_BACKEND=flatfile DMS_BINARY="$PWD/bin/server/dms_new-flatfile"
./scripts/format.sh --check
./scripts/tidy.sh
git diff --check
```

The existing default build is MariaDB; the flat-file build uses the Makefile's separate backend object directories and a distinct binary, preserving both executables under `bin/`. Neither the tests nor builds require a live database, shared game server, production credentials, or mutations to player data. Fix failures caused by this change; do not widen into a full burn-in or wait for hosted CI.

Review the final diff against this acceptance list and repeat ablation. Commit only necessary source/test/documentation changes, with no generated binaries or investigation scripts. Update this plan with exact passing commands and any unverified gameplay claims. The implementation PR should link #611 as its work item; this planning commit must not close the issue. Keep #474 as a compatibility reference.

## Implementation handoff (2026-11-03)

The heartbeat now distinguishes NPC availability from player lock policy. NPCs keep
loaded, undocked, non-sinking same-map targets without a range or player-idle limit.
Player locks still use the existing contact predicate and 300-tick inactivity timer.
Both branches share the existing target-loss message and battle-stations refresh;
timer, movement, AI and sinking-sweep ordering are unchanged. The existing AI validity
predicate now rejects unloaded replacement candidates before considering the current
target or race. No new public helper, stored state or encounter-selection rule was needed.

The maintained targeting fixture extracts production spawn assignment, heartbeat,
hash traversal, contacts, range/bearing, map coordinates and target AI directly.
The lower-level factory, map rendering, captains/ammo and unrelated world/navigation/
combat services are controlled explicitly. It does not dynamically rewrite the
lifecycle fixture or copy production targeting logic.

Acceptance evidence:

- **Separate assigned pursuit:** four actual hash-ordered player hulls, an eligible
  zero-frag `ATTACKBYNPC` decoy first, and three independently spawned pirate/hunter
  attackers. The real outer factory produces exactly 45-room separation and ENGAGING
  state before stationary updates. All three retain their distinct victims for 305
  heartbeats for each scout bonus 0/1/2, initial idle timer 0/1, basic/advanced AI and
  two victim/frag permutations. Maneuver counters prove dispatch on every update.
- **Escort retaliation:** real escort spawning and `escort_attacked_by()` retain a
  45-room attacker for 305 heartbeat/AI updates while preserving the separate charge.
- **Unavailable targets:** real map/contact/heartbeat/AI paths reject unloaded,
  docked, sinking, off-map and different-map targets for NPC and player ships. Three
  updates confirm safe NPC transition to CRUISING and no unloaded reacquisition even
  with that hull still present in the hash.
- **Lifecycle compatibility:** the existing actual docking, purge, unload, deletion,
  sinking and failed-persistence cases pass. Target/escort/boarding references clear
  as appropriate, unrelated references survive, and additional post-removal heartbeats
  pass under sanitizers. Sinking still intentionally ends its sweep after destruction.
- **Player recovery:** actual lock/fire/volley/ram/summon paths retain 300-tick absent-
  captain recovery, final-idle-tick combat refresh, explicit unlock and out-of-range
  expiry. Summon remains blocked at battle-stations timer 1 and succeeds at 0 after
  the existing 180-tick stand-down. This is not a character-death journey.
- **Geometry/buffer compatibility:** exact 35/36/37-room scout boundaries, fractional
  positions and altitude pass, with a byte-for-byte sentinel over all `contacts[]`
  entries before/after valid and invalid contact probes.

Final local validation (all exit 0):

```sh
python3 tests/async/test_npc_ship_targeting.py
python3 tests/async/test_npc_ship_deletion.py
make -C src -j8
make -C src -j8 PERSISTENCE_BACKEND=flatfile DMS_BINARY=/home/aiwithapex/projects/duris-issue-611/bin/server/dms_new-flatfile
./scripts/format.sh --check
./scripts/tidy.sh
git diff --check
```

Both Python suites compile/run MySQL and flat-file variants under ASan/UBSan, with
no findings. Build logs are ignored local files `bin/issue611-mariadb-build.log` and
`bin/issue611-flatfile-build.log`; both executables are under this worktree's
`bin/server/`. An initial flat-file invocation expanded its output path through the
outer shell into the main checkout's ignored `bin/server/dms_new-flatfile`; it was
not run or installed. The final command above uses an explicit worktree path.

Final ablation retained only the two demonstrated production corrections, one
self-contained boundary regression, narrow lifecycle/geometry assertions and this
handoff. No additional implementation chunk or dependent PR is needed. Review and
merge remain; no release tag, deployment, production mutation, full-world journey
or hosted-CI wait is required for this review-ready scope. The original issue's
historical incident reconstruction and broad reacquisition policy remain outside
the proof. Tracked changes in other worktrees were preserved.

## Live follow-up and limits

No production binary, runtime settings, live hash order, or reporter incident timeline has been inspected here. The source fix and controlled regression can establish assignment retention and prevent the reproduced convergence; they cannot establish which original ships spawned each attacker in either report.

If a pile-on is reported after deployment, capture run time/deployed revision, attacker identity/type, original victim, current victim, target-loss circumstances, participant hulls and diplomats. `try_load_pirate_ship()` already logs original owner and rooms at [ship_npc.c](../../src/ships/ship_npc.c):1315. That log alone does not establish subsequent pursuit. Evaluate any persistent whole-map reacquisition concern as separate gameplay work, using that evidence; do not silently broaden this patch.

## Estimate for my implementation

**Approximately 3–5 hours of active implementation and local verification** from this prepared branch:

- 1–1.5 hours: maintained real-AI fixture, deterministic spawn/group cases, and expected baseline failures.
- 0.5–1 hour: expiry/availability correction, unloaded reacquisition guard, and adversarial lifecycle/player compatibility cases.
- 1.5–2.5 hours: both backend tests/builds, fixes revealed by those checks, formatting/tidy, final ablation review, and implementation handoff.

This is my execution estimate, including regression work; it excludes reviewer turnaround and deployment. The production edit is small, while most of the time is proving the heartbeat/AI boundary and keeping player recovery intact. Unexpected compiler or fixture integration failures would require an updated estimate supported by the specific failure.

---

# Issue #584: flight transport implementation plan

Status: implementation, review follow-up and local acceptance complete. [PR #586](https://github.com/LuminariMUD/Duris/pull/586) and [PR #587](https://github.com/LuminariMUD/Duris/pull/587) were squash-merged in order; [PR #588](https://github.com/LuminariMUD/Duris/pull/588) is rebased directly onto the resulting master and ready to merge. Updated 2026-11-02. No deployment has been performed.

- Work item: [Duris #584](https://github.com/LuminariMUD/Duris/issues/584).
- Linked development branch: [branch/issue-584-flight-transport](https://github.com/LuminariMUD/Duris/tree/branch/issue-584-flight-transport).
- Local worktree: `/home/aiwithapex/projects/duris-issue-584`.
- Inspected base: `5708e269974ab070ea224f720e7e2e787e2d6671` (`origin/master` when created).
- Method: [ablation](../../.agents/skills/ablation/SKILL.md), applied to the code and acceptance criteria below.

## Outcome

An interrupted paid flight must leave its surviving carrier either serving its configured pad or scheduled to return there. Once home, the carrier must be at altitude zero, WAITING, unoccupied, and able to handle `list`, stop discovery, ticket purchase, and another departure. A paid flight carries exactly one eligible player; linked mounts or additional riders cannot bypass ticket/access checks. Paid passengers retain correct altitude and command restrictions, and entering combat without mounted-combat skill must not automatically eject them from the transport.

Preserve ordinary occupied trips, empty returns, ordinary ground mounting/combat, fares, discovery and destination access rules, dedicated extra destinations, and existing copyover/restart compatibility.

## Non-goals

No production intervention, deployment, restart, migrations, player-data changes, refunds, new multi-passenger fare model, global riding/combat redesign, or new scheduler/reconciliation service. No claim that a socket disconnect, NPC horse, or ground melee caused the reported live incident without evidence. #584 remains open until implementation and its acceptance checks are complete. #40 and merged #51 are historical context, not additional work items to close.

## What the current code establishes

The issue cites an older master, `f636c9b19b8f61ec69c810810be8f40fd7dd3726`. Comparison with the inspected base shows no changes to transport, event scheduling, mounting, or mob-combat source. Changes in `fight.c`, `affects.c`, and `handler.c` concern group/GMCP updates and map refreshes; the paths below remain present. Line numbers refer to the inspected base.

1. **Service identity and eligibility are already centralized.** [transport.c](../../src/world/transport.c):82 binds carrier 47020 to pad 582084. `transport_service()` identifies catalog services and excludes mastered mobs. `transport_waiting()` at 429 requires a usable, unoccupied carrier at its configured pad in WAITING state. `flights` intentionally lists learned stops; first discovery occurs through `list`. Neither command needs redesign.
2. **Outbound continuation is coupled to passenger lifetime.** `flying_transport_cmd_give()` at 686, continuation at 884, and recovery at 412 pass the passenger as the event victim. [new_events.c](../../src/world/new_events.c):910 creates an `LNK_EVENT`; `event_broken()` at 2480 cancels an active event when that link disappears. [handler.c](../../src/world/handler.c):3859 calls `clear_all_links()` during extraction. Cancellation is correct scheduler behavior; transport currently loses its only continuation as a consequence.
3. **The movement callback also loses continuation without extraction.** `event_flying_transport_move()` at 777 returns for a missing/different-room victim and never checks that this victim is still its rider. A same-room unlink can therefore be followed by one solo carrier movement and then an unrecovered early return. These are source-verified paths, not a fresh reproduction of the production incident.
4. **Recovery mechanisms already exist.** `transport_land_at_home()` at 214 cancels flight callbacks, unlinks/lands a rider, resets route/step, and restores service. `event_flying_transport_return()` at 889 follows the existing route backwards. Empty returns deliberately use state MOVING; `TRANSPORT_STATE_RETURNING` is defined but unused. `initialize_transport()` resumes validated recovered flights and otherwise lands them; its only production call is post-recovery boot in [comm.c](../../src/net/comm.c):2802. It is not a periodic runtime repair, and calling it again does not by itself repair an ordinary orphan without recovery-pending state.
5. **Boarding checks only the outgoing riding link.** `flying_transport_cmd_give()` at 681 checks `IS_RIDING(ch)` but not `GET_RIDER(ch)`. [affects.c](../../src/magic/affects.c):2809 and 2994 clear outgoing exclusive links only. [handler.c](../../src/world/handler.c):1477 recursively places linked mounts and riders. An incoming rider therefore survives current boarding; only the direct passenger receives altitude 10 and the command lock. NPC redemption is already rejected at transport.c:645, and a player riding a horse is already rejected at 681.
6. **Boarding-time validation alone is incomplete.** [mount.c](../../src/classes/mount.c):117 checks whether the actor is mounted and whether the target already has a rider, but does not reject a target that is itself a paid-flight passenger. Preserve the single-passenger invariant at this later link-creation boundary too, including a same-altitude actor who can otherwise see and mount the passenger. This is a source-backed gap; command reachability still needs an executable test.
7. **Skill-based ejection is separate from attack reachability.** [fight.c](../../src/combat/fight.c):7929 calls `stop_riding()` for any rider without mounted-combat skill. [mount.c](../../src/classes/mount.c):399 only unlinks. However, `MobStartFight()` in [mobact.c](../../src/mob/mobact.c):6792 and `hit()` in fight.c:6819 already reject different altitudes. Exempting a paid passenger from automatic skill-based dismount does not require granting combat immunity or changing all altitude checks.
8. **Real room entry matters.** Flight movement calls `char_to_room()` with a direction. That path recursively moves riders, executes room specials, can extract/relocate characters, normalizes altitude indoors, and dispatches aggression. `VALID_FLYING_EDGE` in [graph.h](../../src/world/graph.h):122 does not filter indoor rooms. These are specific things to inspect in a real flight/attack journey, not proof of the reported ground attack. Surface data confirms room 536087 leads north to 535687, but does not establish a shared incident.
9. **Existing test seams leave an integration gap.** [test_flight_network.py](../../tests/async/test_flight_network.py) compiles production transport code, but [world_singletons_harness.cpp](../../tests/async/world_singletons_harness.cpp) substitutes links, movement, extraction, dismounting, and event scheduling. [test_nevent_cancellation_runtime.py](../../tests/async/test_nevent_cancellation_runtime.py) proves generic cancellation separately. Both are useful controls, but neither alone proves a flight survives production passenger-link teardown or combat.

The issue's live diagnostics and earlier ad hoc harness results are historical reports. This planning pass did not access production or independently rerun those ad hoc reproductions.

## Ablation decisions

- **Keep carrier-owned continuation; simplify away passenger event ownership.** Schedule all outbound events with the carrier as owner and no victim, and resolve the current rider from `LNK_RIDING` in the callback. This removes the demonstrated cancellation dependency without changing generic `event_broken()`, storing a raw passenger pointer, or adding a registry.
- **Keep existing return/reset paths.** A missing passenger transitions to the existing empty return; invalid route/location or scheduling failure uses the existing home landing. A watchdog would add another owner of the same state and is unnecessary for these traced interruptions.
- **Keep one-player boarding.** Reject a passenger with either an outgoing mount or any incoming rider before ticket consumption. Any longer connected riding chain necessarily has an immediate link at this boundary. No recursive fare calculator, manifest, or multi-passenger altitude/command engine is needed.
- **Keep one small paid-passenger predicate if shared by combat and mounting.** Both are concrete consumers of the same service/state/link check. Identify a real catalog service and its attached passenger; do not exempt all NPC mounts, flying creatures, or characters at altitude 10.
- **Keep tests of real links, scheduling, combat, and command dispatch.** Existing stubs cannot prove those requirements. Extend current fixtures/journeys where possible; add at most a focused transport runtime harness if linking those production boundaries cannot fit an existing fixture cleanly.
- **Investigate specific attack/body claims.** Inspect the actual attack path, altitude changes during room entry, and NPC/switched/morphed body guards. Change an attack path only when evidence shows a paid-flight invariant is broken. An unavailable original transcript is not evidence for blanket immunity.
- **Drop schema changes, extra transport states, periodic whole-world scans, generic mount-chain infrastructure, and unrelated cleanup.** None is required by the traced failures or acceptance criteria.

## Implementation sequence

### 1. Lock down the behavioral contract with focused regressions

Extend the flight fixture for missing rider, same-room unlink, separation, incoming rider rejection, and successful service reuse. Reuse its ordinary and extra-destination setup, ticket checks, and route execution. Record expected failures on the unmodified behavior before applying the fix where the fixture can faithfully exercise it.

Add integration coverage using production link/event teardown and combat entry, either within the existing runtime fixture or one small `tests/async/test_flight_transport_runtime.py`. It must execute actual relevant functions, with unrelated world I/O stubbed explicitly. Do not call a fake `extract_char()` or a map-backed fake scheduler and describe that as production extraction coverage. The disposable server journey below provides the full extraction/command path.

### 2. Make transport continuation independent of its passenger

In `src/world/transport.c`:

- Update ticket departure, each outbound rearm, and restored occupied flights to schedule carrier-only events with a null victim. Keep empty returns carrier-only as they already are. Preserve owner-extraction cancellation.
- At callback entry, validate the service/state/route, then resolve the live direct rider. Require the reciprocal riding relationship and room agreement before occupied movement. A missing/unlinked passenger must not cause another occupied step.
- For an unoccupied carrier on its expected route, schedule the existing return from the current step. At step zero it can land at home immediately. For invalid progress, unexpected position, or failed scheduling, use `transport_land_at_home()` rather than leaving MOVING without an event.
- If a remaining riding link points to a separately relocated passenger, detach that link before moving the carrier. Do not drag a relocated player back from another room through the landing helper. Preserve the player's new location and ordinary relocation/falling semantics.
- After `char_to_room()`, verify the carrier survived before dereferencing it or scheduling again, and reacquire the rider rather than retaining a pointer across room-entry callbacks. Reuse the removal-generation/runtime-identity pattern already present in `src/cmd/actmove.c:2268`; do not add another lifetime system. Cover passenger removal during the callback as well as between callbacks.
- Maintain at most one flight continuation and distinguish normal arrival from interruption. Ground and detach the delivered player, then run the empty return; do not allow a terrain-sensitive player `dismount` refusal to turn an intended empty return into an occupied one. Keep the return carrier at flight altitude until home and both delivered player/home carrier at zero.

No flight-specific behavior is added to generic event cancellation. Keep snapshot fields and state values compatible. Existing recovered empty flights and invalid legacy snapshots must still return/land correctly; validate a snapshot of an already stranded carrier through that path.

### 3. Enforce one eligible traveler at every boarding boundary

In ticket redemption, check both `IS_RIDING(ch)` and `GET_RIDER(ch)` before scheduling, consuming the ticket, changing altitude, or linking to the carrier. Preserve the ticket, cash, discovery state, room, and current links on refusal; tell the player to dismount or have their rider dismount first. Existing carrier eligibility already excludes a carrier with a mount or rider.

Use the shared paid-passenger predicate in `do_mount()` to reject attaching an additional rider to an active flight passenger. Also exercise attempts to use ordinary mounting to join an occupied or returning service carrier, so the tested paths cannot substitute an unticketed rider during an interruption. Add only the transport-specific guard demonstrated necessary by these command tests. Preserve all normal centaur/horse ground consent, saddle, skill, and dismount rules.

Apply the same single-passenger validation when recovery reconnects a named rider. If recovery encounters an incompatible pre-existing riding arrangement, resolve it through the existing safe landing/recovery flow before any movement; do not resume a nested flight or ground only the direct rider while moving an additional traveler. Prove each affected live player's link, room, and altitude outcome.

### 4. Resolve combat behavior using the real attack path

Planned policy: a properly attached paid-flight passenger does not need mounted-combat skill to remain aboard. Add the narrow exception in `set_fighting()` for that passenger. Ordinary mounts retain their current skill-based dismount behavior. This exception does not grant immunity, enable blocked passenger commands, or make different-altitude melee legal.

Exercise actual `MobStartFight()`/`hit()` behavior through room entry and scheduled aggression, with an ordinary ground attacker and a correctly elevated passenger, then with a legal same-altitude attack. Check altitude, riding link, combat state, damage/attack rejection as applicable, and continued transport service. Include zero mounted-combat skill and a normal ground-mounted control.

Trace any observed altitude loss before changing targeting: `char_to_room()` indoor handling, room/mobile specials, and the actual route are relevant; the final movement helper alone is not. If a paid route lowers travelers before aggression, repair the smallest demonstrated transport/entry boundary and retest the actual path. Do not add a global altitude condition to `set_fighting()` that would silently alter spells or ranged combat.

For the horse report, test NPC-body redemption rejection, a player already riding an NPC horse, and applicable switched/morphed-body command guards in a disposable environment. Request the original command sequence/body/carrier only if these do not explain the report; mark its cause unconfirmed instead of inventing a new mechanism. The demonstrated nested-player path still receives a complete fix and regression coverage.

### 5. Prove service recovery and document the policy

Extend `tests/async/test_flight_network_journey.py` with disposable players and world state. Use ordinary player commands for discovery, purchase, give, mounting, and allowed/blocked in-flight commands; use staff/test setup only to arrange interruption and attack conditions. Include Torrhan's configured service as a full-world check.

After separation, passenger extraction, and a forced ride unlink, drain the scheduled return and verify exactly one carrier at its configured home, ground altitude, no rider, WAITING, and no stale flight callback. A new/eligible player must discover the stop with `list`, buy a ticket, and successfully depart again. Distinguish socket loss with a still-live passenger from actual extraction.

Retain occupied copyover, empty-return copyover, cold restart, dedicated destinations, and ordinary ground mounting controls. Update `docs/operations/WORLD_SINGLETON_RECOVERY.md` with carrier-owned runtime recovery and single-passenger/combat rules. Include concise refusal messages in the affected commands; update existing flight help only if its current wording promises incompatible behavior.

## Files

Expected implementation files: `src/world/transport.c`, `src/world/transport.h` (shared predicate only), `src/combat/fight.c`, `src/classes/mount.c`; `tests/async/test_flight_network.py`, `tests/async/world_singletons_harness.cpp`, `tests/async/test_world_singletons.py`, `tests/async/test_flight_network_journey.py`; `docs/operations/WORLD_SINGLETON_RECOVERY.md` and this plan's completion evidence.

Conditional: one focused `tests/async/test_flight_transport_runtime.py` if existing fixtures cannot host production link/event/combat integration clearly. `src/world/handler.c`, `src/mob/mobact.c`, and `src/world/graph.h` are investigation targets, not pre-authorized refactoring targets; touch only a demonstrated blocking flight/attack defect. Generic scheduler, link semantics, codecs, database schemas, and area data need no planned changes.

## Proof and acceptance gates

The implementation is complete only when all of these hold:

- Passenger removal/extraction cannot cancel the carrier's only continuation; generic victim-link cancellation and carrier-owner cancellation still behave correctly. No stale passenger access, duplicate continuation, or sanitizer error occurs when teardown happens between or during callbacks.
- Same-room unlink is detected before another occupied step; separation cannot silently abandon a carrier or pull a relocated player back. Missing rider, invalid route/progress, failed scheduling, ordinary arrival, and empty return all end with a usable service or one valid return continuation.
- Incoming rider, outgoing mount, longer connected chain, and later mounting attempts cannot add an unticketed traveler. Refusal leaves tickets/money/access state intact. Solo centaurs remain eligible. Accepted travelers receive altitude 10 and the established mortal command lock, then altitude zero and released links at landing; existing trusted-command behavior is retained.
- Ground attack tests use the real targeting/entry path. Legal combat entry at zero mounted-combat skill retains the paid ride, while ordinary ground riders retain existing behavior. Explicit forced unlink and extraction still exercise recovery independently of the combat exception.
- Every interruption test checks service reuse, not merely that an event was queued. At least one full-world journey validates Torrhan 47020 at pad 582084 and a subsequent purchased trip.
- Occupied/empty recovery and existing ticket/discovery/extra-destination behavior remain compatible on flat-file and MariaDB journeys. A recovered orphan snapshot returns to service; repairing the currently reported production instance remains a separate deployment/operations action.

Run from this worktree after implementation:

```sh
python3 tests/async/test_flight_network.py
python3 tests/async/test_nevent_cancellation_runtime.py
python3 tests/async/test_world_singletons.py
python3 tests/async/test_flight_transport_runtime.py
./scripts/format.sh --check --rev origin/master
make -C src
python3 tests/async/test_flight_network_journey.py
make -C src PERSISTENCE_BACKEND=mariadb
tests/async/with_disposable_mariadb.sh python3 tests/async/test_flight_network_journey.py \
  --backend mariadb --server bin/server/dms_new
git diff --check
```

The default journey builds its flat-file server under `bin/tests`; the MariaDB binary is also under `bin/`. The database wrapper supplies disposable loopback authority and the journey does not use the checkout's `.env` or running game. If a required journey is unavailable, record the specific missing dependency and leave that acceptance claim unverified. Do not wait for CI, stop a shared server, or run a repository-wide burn-in for this task.

## Implementation and verification record

### Implementation handoff: carrier continuation chunk

Implemented carrier-only outbound/recovered events, current-rider checks, empty return on lost riding links, shared route-position validation, remote-passenger detachment, unconditional arrival detachment, and carrier lifetime checks after both occupied and empty room entry. The shared position validator replaces duplicated recovery validation and is used by both runtime callbacks; no scheduler changes, watchdog, new state, or schema were added.

`test_flight_network.py` now covers same-room unlink, unlink plus separation, separation with a remaining ride link, invalid step, unexpected position, and successful purchase/departure after interruptions. Its new carrier-only assertion failed on the unmodified implementation. `test_flight_transport_runtime.py` uses production link creation/removal and event scheduling/cancellation, with isolated allocation and room I/O, to exercise passenger teardown/freeing between and during movement and carrier extraction during outbound/return callbacks. The singleton fixture also tests recovery of an already orphaned flight snapshot.

Checks for this chunk: `make -C src -j8` passed; flight-network, world-singleton and generic event-cancellation sanitizer controls passed during development. Final focused checks are recorded with the review commit. Full-world and dual-backend journeys have not yet been run for the implementation.

PR #586 combined the carrier implementation and review follow-up, then
squash-merged as `4d45fe7f4`. The following checkpoint implements
boarding/combat. No release tag or deployment is appropriate before the stack is
fully merged.

### Implementation handoff: boarding/combat chunk

Implemented incoming-rider ticket refusal, service-carrier/passenger guards in the actual `do_mount()` command, and a narrow `set_fighting()` exception for active paid passengers. Catalog identity, movement state and reciprocal riding links define a paid passenger; altitude alone does not. Two small public predicates serve these concrete command/combat consumers. Ordinary mounting of a service carrier is also refused, preventing a free rider from joining an empty return. Mastered NPCs remain outside the service catalog rules.

Recovery and runtime callbacks detect legacy nested riders and land the chain. Landing first removes every link in the chain, then grounds/places co-located travelers, avoiding recursive movement with inconsistent altitudes. Separately relocated players remain in their new rooms. This is temporary landing state, not a persistent passenger manifest or new fare model.

Focused flight-network, production flight/link/event/combat/mount runtime, and world-singleton sanitizer checks pass. Runtime tests execute the full production `set_fighting()` and `do_mount()` bodies with unrelated services stubbed, including zero-skill paid combat, the ordinary skill-based ground dismount, direct/later mount refusal, and successful ground centaur mounting. The singleton fixture verifies that a named recovered passenger carrying another rider lands both at altitude zero with no residual riding links. The local MariaDB server build passed before the journey runs.

### Acceptance handoff

PR #587 squash-merged the boarding/combat checkpoint as `d04e0d905`. The rebased
acceptance checkpoint is commit `c18fe6d1a` in PR #588. The acceptance
branch adds complete command journeys, focused test modes, and
scheduling-refusal/body/long-chain assertions. Both full-world backends have
passed actual outbound dismount/separation and character extraction at Torrhan,
followed by a newly purchased trip and service reuse, in addition to catalog
discovery, faction/access checks, occupied and empty copyover, logout, dedicated
trips, crash recovery, and normal relog.

Evidence already completed:

- `python3 tests/async/test_flight_network_journey.py` — flat-file full world including both Torrhan interruptions; log `bin/issue584-flatfile-interruptions.log`, exit 0, binary SHA-256 `99a9f7087ccf612fef39c7d9ce6628453800e63b4dc3de698f2d8ed8820b3800`.
- `tests/async/with_disposable_mariadb.sh python3 tests/async/test_flight_network_journey.py --backend mariadb --server bin/server/dms_new` — same complete MariaDB qualification; log `bin/issue584-mariadb-journey.log`, exit 0, binary SHA-256 `e36ea3d5b5d2260915edb62ff9e4eca198bc68a60efd7b02841b8da84e6834ae`.
- `python3 tests/async/test_flight_network_journey.py --interruptions-only` — full-server NPC `kill`/`hit` paths at altitude 0 and 10: different-altitude attack rejected, same-altitude combat entered, riding link retained in both, trip and empty return completed. Both outbound interruption/reuse cases also passed. Log `bin/issue584-focused-flatfile.log`, exit 0. This run preceded the separate socket-reconnect case; its valid evidence is reused.
- Final ablation removed unreachable legacy BFS error/no-path branches after the shared validator already rejects those states. `make -C src -j8`, flight-network, production flight/link/event/combat/mount runtime, and singleton sanitizer tests passed after that deletion. Earlier full-world evidence remains valid for the unchanged reachable branches; no repeat of both complete persistence suites is needed for dead-code removal.
- The flight fixture now explicitly checks a two-edge route: a same-room unlink returns immediately instead of advancing alone. It also proves rejected initial scheduling retains the ticket, rejected continuation lands safely, mortal command restrictions/altitudes, solo centaur travel, longer incoming chains, NPC bodies, and NPC bodies controlled by player descriptors.

- `python3 tests/async/test_flight_network_journey.py --reconnect-only` — passed on the final simplified callbacks, log `bin/issue584-reconnect-qualified.log`, exit 0, binary SHA-256 `ad3a8d53fee751fde3fbfba97aadc89c0b00862ab1553c249577fcb303d75608`. Staff diagnostics confirmed the socket-disconnected character was still live, link-dead, and riding; reconnect restored control, then the trip and empty return completed. The test fixture's initial fare funding and login-banner assumptions were corrected during qualification.

All test sessions are finished; no test process needs to be resumed. Current source and focused tests include the final callback simplification. Both full persistence journeys and the actual NPC attack journey preceded that removal of unreachable branches; their reachable-path evidence is reused, with the build, focused sanitizer regressions and real reconnect journey run afterward. No generic event/link semantics, attack targeting, schema, snapshot format, or area data changed.

Focused modes reuse the same world/authority/command logic. `--interruptions-only` discovers only Torrhan and the nearer Nizari stop; `--reconnect-only` runs only the socket case. They avoid repeating catalog, copyover, and dedicated-trip checks during iteration. All runs use disposable state, random loopback ports, and no checkout `.env` or shared server.

The historical NPC-horse/original attacker sequences remain unconfirmed. Current ordinary-riding and NPC/switched-body guards are covered; no speculative horse or global combat behavior was added. Actual ground and same-altitude NPC attack paths pass, so the implementation adds neither global immunity nor a new targeting rule. The original production cause and production repair/deployment remain outside the evidence and this branch's scope. Keep #584 open until review/merge.

At the planning base, these existing controls passed:

- `python3 tests/async/test_flight_network.py` — catalog, paths, discoveries, fares, commands, tickets, and epic exclusions; ASan/UBSan enabled by the runner.
- `python3 tests/async/test_nevent_cancellation_runtime.py` — cancellation runtime invariants under ASan/UBSan.
- `python3 tests/async/test_world_singletons.py` — singleton/recovery lifecycle, five recovery cycles, riders/travel, and compatibility; ASan/UBSan enabled by the runner.

Those planning-stage passes established the baseline only; implementation evidence is recorded above. No production experiment was performed. The original checkout and other worktrees remain untouched.

## Final completion audit

- Carrier recovery: production transport/link/event sanitizer tests cover real passenger teardown, same-room loss, separation, freeing during movement, owner extraction, generic victim cancellation, and balanced event ownership. The two-edge route assertion forbids the old extra solo outbound step. Invalid position/progress and scheduling refusal restore service. Orphan and occupied snapshots recover without a format change.
- Boarding: production command tests cover incoming/outgoing and longer rider chains, preservation of tickets/cash/discovery on refusal, later mount attempts, NPC and player-controlled NPC guards, solo centaur acceptance, and normal ground mounting. Legacy nested recovery detaches/grounds every linked traveler before movement. Accepted passengers and completed landings have explicit altitude/command-lock assertions.
- Combat: zero-skill paid combat entry and ordinary ground dismount controls execute production `set_fighting()`; real-server NPC `kill`/`hit` tests reject a ground attacker and allow same-altitude combat while retaining the ride. The historical attacker remains unidentified, without being treated as a reproduced universal targeting defect.
- Whole workflow/persistence: both maintained backends complete discovery, fare/access checks, occupied and empty copyover, outbound interruption, actual extraction, Torrhan service reuse, extra destinations, crash recovery and relog. A final real socket reconnect remains distinct from extraction and completes successfully.
- Review delivery: all work is in the three dependent branches/PRs above, with this plan and the existing operations guide updated. The original checkout and unrelated worktrees remain preserved. Required local build, focused regressions, formatting and diff checks pass. No CI wait, release tag, production repair, or deployment is required for the requested review-ready handoff.

There is no remaining implementation/acceptance work for #584 in this plan. Reviewers should process the stack in order and retarget children after their parents merge. The reported production carrier needs the normal owner-approved deployment/recovery workflow separately.

## Original estimate

**5–8 hours of active implementation and verification**, assuming the local compiler, disposable MariaDB/Docker, and existing journey fixtures are available:

- 1–1.5 hours: focused failing cases and production link/event integration.
- 1–1.5 hours: carrier-owned continuation, recovery, and boarding guards.
- 1–2 hours: combat exception and real attack/altitude investigation and tests.
- 2–3 hours: builds, both persistence journeys, fixes from those checks, documentation, and final ablation/diff review.

This estimate excludes waiting for a reporter's exact horse/attack sequence, review, and production deployment. A newly demonstrated special-attack or route-altitude defect could add approximately 1–2 hours; that would be reported with its evidence and a revised estimate, not silently expanded into a combat redesign.

## PR #586 review follow-up (2026-11-02)

Both P2 findings were verified against the production departure and placement
contracts. The refused-departure fixture reproduced WAITING away from home with
no flight event on the original head. The lifetime issue follows directly from
`char_from_room()` permitting removal/replacement before the old caller's snapshot.

The fix shares checked relocation between occupied movement, empty return and
home landing. Recursive riding-companion movement checks both participants at
the same callback boundaries. Refused home placement reuses the existing return
event, and only confirmed home placement publishes WAITING. Startup callers honor
failed landing and avoid accessing removed carriers. The fixtures now model leave
vetoes and duplicate-insertion refusal and exercise the production companion mover.
This keeps the existing state/snapshot format and scheduler; no new recovery service,
configuration, tag, migration or production operation is needed.

Focused proof includes repeated departure/entry refusal followed by recovery and
service reuse; occupied/empty departure redirection, removal and storage replacement;
and passenger/carrier removal during recursive movement and home landing. Validation passed: `make -C src -j8`; `test_flight_network.py`,
`test_flight_transport_runtime.py`, `test_world_singletons.py`,
`test_nevent_cancellation_runtime.py`, `test_mounted_gatekeeper_runtime.py`, and
`test_char_from_room_callbacks.py` (focused native suites use ASan/UBSan);
`./scripts/format.sh`, `./scripts/tidy.sh`, and `git diff --check`.
Full-world final-stack acceptance follows in #588 after carrying this fix through
#587's legacy-chain code.

## PR #587 review carry-forward (2026-11-02)

Rebased the single boarding/combat commit onto the reviewed #586 fix. The runtime
fixture conflict retained both production companion placement and actual mount/combat
bodies. Legacy-chain landing and startup candidate retirement now retain runtime
identities alongside their temporary pointer lists, so an earlier leave callback
cannot make a later queued traveler/carrier a stale access. Removed-count logging
counts actual retirement. A focused legacy-chain case removes the later traveler
from the earlier traveler's departure hook and verifies safe landing and balanced
links/events. Ground centaur mounting, one-player boarding and paid combat semantics
are preserved; no new persistent state or helper layer was needed.

PR #587 carry-forward validation passed: local MariaDB build, flight-network,
production flight/link/event/combat/mount runtime and singleton ASan/UBSan tests,
formatting, tidy and diff checks. The rebased PR remains one logical boarding/combat
commit; #586's review fix is its parent.

## Final review qualification (2026-11-02)

PR #588 was rebased onto merged master `d04e0d905` without changing its two
logical commits: acceptance/simplification at `c18fe6d1a`, then this final
documentation commit.
The documentation conflict retained both the review-follow-up recovery guarantees
and the full-world journey instructions. Master had advanced before merging to
`3b47d69562de60610e5992c759b6c0100ab497d0`; its race-info-only changes did not
overlap this stack. The full stack was rebased before #586, then #587 and #588
were replayed onto each preceding squash merge so their diffs remained narrow.
No release tag is appropriate before merge.

Validation on the final stack passed:

- `make -C src -j8` using the MariaDB backend.
- `test_flight_network.py`, `test_flight_transport_runtime.py`,
  `test_world_singletons.py`, and `test_nevent_cancellation_runtime.py` under
  ASan/UBSan, plus `test_mounted_gatekeeper_runtime.py` and
  `test_char_from_room_callbacks.py`. `test_race_command.py` also passed on the
  rebased head, covering the new master commit.
- `scripts/format.sh`, `scripts/tidy.sh`, and `git diff --check`.
- Complete flat-file full-world journey on the rebased head, binary SHA-256
  `376a6ffac3f5fa6d54ba0fa539d9639ec4b28b1e2304a52a1df882943596c6e7`.
- Complete disposable MariaDB full-world journey on the same flight stack before
  the unrelated race-info-only master rebase, binary SHA-256
  `a247ae9a88efc3c81a54cf36ecf2a14780b3f8614a9c48ae275638d6ed1db612`.

Each complete journey passed 25-stop discovery, fares and access rules, two
copyovers, occupied and empty recovery, logout, ground and same-altitude NPC
attack paths, outbound unlink/separation, actual passenger extraction, Torrhan
service reuse, live socket reconnect, restricted destinations, crash recovery,
and normal relog. The disposable database and all journey processes were removed
by their test harnesses. Hosted CI was not used as a gate.
The MariaDB journey was not repeated after the race-only rebase: ablation keeps
the valid complete-backend evidence and pairs it with the exact-head MariaDB
build, focused flight suites, race suite, and complete flat-file journey.
