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
- Occupied/empty recovery and existing ticket/discovery/extra-destination behavior remain compatible on MariaDB journeys. A recovered orphan snapshot returns to service; repairing the currently reported production instance remains a separate deployment/operations action.

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
scheduling-refusal/body/long-chain assertions. The MariaDB full-world journeys have
passed actual outbound dismount/separation and character extraction at Torrhan,
followed by a newly purchased trip and service reuse, in addition to catalog
discovery, faction/access checks, occupied and empty copyover, logout, dedicated
trips, crash recovery, and normal relog.

Evidence already completed:

- `tests/async/with_disposable_mariadb.sh python3 tests/async/test_flight_network_journey.py --backend mariadb --server bin/server/dms_new` — same complete MariaDB qualification; log `bin/issue584-mariadb-journey.log`, exit 0, binary SHA-256 `e36ea3d5b5d2260915edb62ff9e4eca198bc68a60efd7b02841b8da84e6834ae`.

- Final ablation removed unreachable legacy BFS error/no-path branches after the shared validator already rejects those states. `make -C src -j8`, flight-network, production flight/link/event/combat/mount runtime, and singleton sanitizer tests passed after that deletion. Earlier full-world evidence remains valid for the unchanged reachable branches; no repeat of the complete MariaDB persistence suite is needed for dead-code removal.
- The flight fixture now explicitly checks a two-edge route: a same-room unlink returns immediately instead of advancing alone. It also proves rejected initial scheduling retains the ticket, rejected continuation lands safely, mortal command restrictions/altitudes, solo centaur travel, longer incoming chains, NPC bodies, and NPC bodies controlled by player descriptors.

- `python3 tests/async/test_flight_network_journey.py --reconnect-only` — passed on the final simplified callbacks, log `bin/issue584-reconnect-qualified.log`, exit 0, binary SHA-256 `ad3a8d53fee751fde3fbfba97aadc89c0b00862ab1553c249577fcb303d75608`. Staff diagnostics confirmed the socket-disconnected character was still live, link-dead, and riding; reconnect restored control, then the trip and empty return completed. The test fixture's initial fare funding and login-banner assumptions were corrected during qualification.

All test sessions are finished; no test process needs to be resumed. Current source and focused tests include the final callback simplification. The MariaDB persistence journeys and the actual NPC attack journey preceded that removal of unreachable branches; their reachable-path evidence is reused, with the build, focused sanitizer regressions and real reconnect journey run afterward. No generic event/link semantics, attack targeting, schema, snapshot format, or area data changed.

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
- Whole workflow/persistence: MariaDB journeys complete discovery, fare/access checks, occupied and empty copyover, outbound interruption, actual extraction, Torrhan service reuse, extra destinations, crash recovery and relog. A final real socket reconnect remains distinct from extraction and completes successfully.
- Review delivery: all work is in the three dependent branches/PRs above, with this plan and the existing operations guide updated. The original checkout and unrelated worktrees remain preserved. Required local build, focused regressions, formatting and diff checks pass. No CI wait, release tag, production repair, or deployment is required for the requested review-ready handoff.

There is no remaining implementation/acceptance work for #584 in this plan. Reviewers should process the stack in order and retarget children after their parents merge. The reported production carrier needs the normal owner-approved deployment/recovery workflow separately.

## Original estimate

**5–8 hours of active implementation and verification**, assuming the local compiler, disposable MariaDB/Docker, and existing journey fixtures are available:

- 1–1.5 hours: focused failing cases and production link/event integration.
- 1–1.5 hours: carrier-owned continuation, recovery, and boarding guards.
- 1–2 hours: combat exception and real attack/altitude investigation and tests.
- 2–3 hours: builds, the MariaDB persistence journey, fixes from those checks, documentation, and final ablation/diff review.

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

- Complete disposable MariaDB full-world journey on the same flight stack before
  the unrelated race-info-only master rebase, binary SHA-256
  `a247ae9a88efc3c81a54cf36ecf2a14780b3f8614a9c48ae275638d6ed1db612`.
