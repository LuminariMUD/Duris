# Issue #437: usable bartender quests and recovery

Status: **selection and recovery qualified on both backends; full target gameplay/latency qualification remains**. Updated 2026-10-29.
Issue: [Duris #437](https://github.com/LuminariMUD/Duris/issues/437), including
all three investigation comments. Stack root:
`branch/issue-437-bartender-quest-routes`. Current continuation branch:
`branch/issue-437-quest-recovery`.
Source baseline: `master` / `origin/master` at
`9632f29804687ccf049ddf7a59a5ae16878e0583`.

The planning baseline publishes the plan and links the branch. Implementation
progress and review boundaries are recorded below. The prior #428 plan and
qualification record are preserved byte-for-byte in
[plan-issue-428.md](plan-issue-428.md).

## Outcome

New bartender quests must name suitable, currently usable NPCs in the advertised
zone, with a verified ordinary route from the actual request origin. For accepted
levels **11 through 29**, that route must stay within the origin's resolved local
geography and require no paid transport or special travel equipment. Level **30**
is outside the local-only restriction. Route legality, live availability,
accurate directions and stale-assignment recovery apply at every quest level.

An assignment invalidated by the world must offer a free replacement without an
abandonment charge, lost earned progress, or false completion/history consumption.
If no new target qualifies, refuse a new purchase and return its fee; for an
already paid invalid assignment, retain a durable replacement entitlement.

Keep the boot catalog, level windows, reward filtering/weighting, completion
history, daily allowance, sharing limits and successful completion behavior.
The changes below explicitly replace the defective availability and global
population assumptions, rather than loosening the other rules to manufacture a
target. A positive local grant and completion must pass: refusing every request
does not meet the outcome.

## Non-goals

No general travel planner, combat-safety guarantee, new transport system,
reward rebalance, zone approval list, or world-wide area repair. Preserve the
Divine selector and unrelated quests. Production deployment and reconstruction
of an unidentified player's historical assignment are separate from the local
implementation; retain the latter as an explicit evidence limitation.

## What the source establishes

These findings were checked in the baseline above. The issue comments are useful
leads and previous experiment records, not substitutes for the owning code.
Line numbers below refer to that baseline and may move during implementation.

1. **Global selection is real, and it was specified deliberately.**
   `src/world/world_quest_policy.c:367-383,560-604` filters status, hometowns,
   levels, map presence and rewards, then weights eligible zones globally.
   There is no origin or route check. Before `35b2071a8`, `getQuestZoneList()`
   used local map exits, a below-30 `map_section` comparison and the
   `3000 + level^3` distance threshold. However, the
   [plan committed with that change](https://github.com/LuminariMUD/Duris/blob/35b2071a84fba5d968b07d13fa1f0d2b4a58d267/docs/ongoing-projects/issue-157-dynamic-bar-quests.md#fr-001--global-dynamic-catalog)
   expressly requires a catalog independent of bartender identity, room,
   player zone and continent exits. #437 therefore proposes a policy revision;
   the evidence does not support calling this an accidental omission. Preserve
   the global catalog and narrow its per-request eligible subset.
2. **Geography fields are not travel proofs.**
   `world_quest.c:392-431` returns the first zone-to-map exit without proving
   inbound access. `map.c:1389-1452` assigns continent IDs within map-zone
   connectivity; ordinary interiors can retain zero. `map.h:42-55` defines
   surface continent IDs 1-14; zero is not a valid surface continent.
   `map.c:1466-1617` builds coordinate sections, not mortal routes.
   `calculate_map_distance()` at `map.c:329-355` returns squared coordinate
   distance, or -1 across different map zones. Neither that distance nor
   equal `map_section` proves affordability or legal access.
3. **Zero-population targets are already filtered.**
   `select_cached_mob()` at `world_quest_policy.c:385-446` requires global
   population >=2 for KILL and exactly 1 for ASK. Creation rechecks population
   at `world_quest.c:862-870`. The missing boundary is actual live rooms and
   usable instances, not simply another `mob_index[].number > 0` test.
4. **Prototype ownership can give the wrong destination.**
   `load_mobile_profiles()` at `world_quest_policy.c:249-281` groups targets by
   prototype VNUM interval. Authored resets independently confirm cross-zone
   reuse: `areas/zon/shaughin.zon:185-186` places 6610 in room 6543, and
   `areas/zon/astral_main.zon:13-16` places 19830 in rooms 19701/19704.
   Advertised location and accessible supply must use the selected live zone.
   Do not change reward ownership or average-level arithmetic as a side effect.
5. **Target suitability also needs the live instance.**
   ASK's cached speech/visibility checks and aggression probe in room rnum 1
   do not prove interaction in the target room. KILL does not use the existing
   `combat_eligible` profile. `world_quest.c:911-924` sets its quota from global
   population minus one. Real ASK completion is reached through
   `cmd/actcomm.c::do_ask()`; real KILL progress is credited through
   `combat/fight.c` and `world_quest.c::quest_kill()`.
6. **Movement routines cannot be called as harmless route predicates.**
   `cmd/actmove.c::leave_by_exit()` starts regeneration and checks live blockers;
   entry checks use `ch->in_room`, and some branches alter posture. Commands,
   room hooks and `char_to_room()` can invoke scripts, move or destroy actors.
   Inspect `actmove.c:254-775,780-975,1339-1423`,
   `cmd/interp.c:2814-2830`, and `world/handler.c:1167-1184,1548-1568`.
   `combat/forced_movement.c::map_entry_barrier()` is a reusable side-effect-free
   map barrier check. Flight does not bypass its map mountain/cavern-wall rule.
7. **The Divine fix is a reference, not the bartender solution.**
   Merged #448 changes `economy/divine_boon_selection.c::ordinary_exit()` and
   cached-path validation. Its roots are faction hometowns, and its policy
   assumes some boat/flight travel. Its reset scan also permits probabilities
   >=50. None supplies #437's origin-specific, routine-target contract.
   Generic `world/graph.h` edge macros omit different restrictions and cannot
   be selected by name alone. Do not modify Divine policy for this task.
8. **Stale quests currently remain chargeable obligations.**
   `do_quest()` recreates a prototype for display at `world_quest.c:687-753`;
   it never verifies live availability. `specs/specs.mobile.c:11024-11098`
   charges to abandon; its callback at `10930-10947` records partially
   completed KILL abandonment in history. `quest_kill()` already pays XP per
   credited kill. Recovery must not reset that counter and pay the same progress
   again, or call `sql_world_quest_finished()` for a server-invalid assignment.
9. **Persistence and payment have important current constraints.**
   Active quest state is 14 values in `core/structs.h:1333-1347` and
   `player/player_snapshot.h::quest_values`; capture, load, SQL column arrays
   and the binary snapshot codec all mirror that ordering. There is no saved
   origin room or purchase fee. Despite deferred naming/comments,
   `economy/currency_transaction.c::apply()` currently invokes completion
   synchronously after updating the wallet; player snapshots persist it.
   Do not introduce a second transaction system or assume a durable fee ledger.

The earlier issue experiments and local files under
`bin/tests/issue437-investigation/` contain real level-11/29 client assignments
from Woodseer to Seacaves/Old Graveyard, and the relocated/disappeared 23501
case. I inspected their recorded outputs; I did not rerun those servers for
this planning commit. The policy, creation and movement files checked above
have not changed from the recorded `e08fa3d1b` investigation head; unrelated
trainer edits in `specs.mobile.c` have landed since. Reproduce the relevant
journeys against the implementation build, rather than claiming old binaries
qualify new behavior. Previous sampled path counts are not failure-rate estimates.

The named centaur/Ice Castle report remains qualified. Current authored content
has a 100% reset for centaur 82718 and 100% resets into IceCrag's named rareload
room 97005. The prior full-policy audit excluded that centaur and the three
investigated level-60 IceCrag singletons through non-overlapping level windows.
That does not identify the player's actual target. Record the running revision,
target VNUM/type, accepted level/time and live rooms if the affected record
becomes available; never manufacture those identifiers or assert a zero-load
new assignment from the current count checks. Test synthetic zero-load cases
and the independently proven reused/staging targets regardless.

## Proposed behavior decisions

These are concrete implementation defaults for #437, not claims about current
behavior or authorization to deploy this planning branch.

### Origin, boundary and affordability

- Capture the request room VNUM while validating the real bartender/customer
  interaction, and pass it by value through creation/payment context. Use that
  same room after a payment continuation; do not rediscover any NPC sharing
  the giver VNUM or select relative to a later player position.
- Apply local-only policy to accepted levels 11-29. Preserve the level-11
  admission gate, level-41 mapless gate, and level-50 KILL-only switch.
  Revalidation uses the saved accepted level, so leveling or walking away
  does not silently change an existing contract.
- For a surface-map origin, use its positive continent ID. For an interior,
  find its legally reachable first map boundaries through ordinary directed
  connections; do not traverse an entire continent to decide the origin.
  Require an unambiguous local geography. Resolve Underdark origins as the
  reachable Underdark map component, distinct from surface continents; do not
  equate two continent-zero interiors. A boundary crossing to another surface
  continent or between surface and Underdark is nonlocal for levels 11-29.
  Multiple same-region entrances are valid; conflicting regions or unresolved
  geography produce a clear refusal, never a global fallback.
- Validate the route all the way into the NPC's actual room and a directed
  return route to the origin. A reverse exit need not be the same physical
  entrance if an alternative ordinary return path exists. A one-way trap does
  not qualify. Low-level transit cannot leave and reenter the local region.
- Define affordable here as **no mandatory travel fare, keys, hired travel,
  another player's spell, or equipment/temporary-flight dependency** for
  levels 11-29. Ordinary walking, opening an unlocked door and crawling are
  allowed. Do not restore the squared-distance formula or add an arbitrary
  gameplay radius. This does not promise a shortest journey or combat safety.
  At 30+, allow only travel capabilities the player actually has and the
  validator can prove; unknown scripted/paid transport remains ineligible.

### One conservative route validator

Keep a quest-specific, read-only traversal in `world_quest_policy.c`, reused by
creation and revalidation. It must take explicit source/destination room IDs
and relevant player facts, rather than relocating a real player or invoking
movement/interaction commands. Reuse safe existing predicates where their
contracts fit; extract a small shared predicate only if a real movement rule
otherwise has to be duplicated. Do not refactor the movement subsystem.

Reject secret, blocked, walled, locked/key-dependent exits; castle walls;
map-to-map mountains/cavern walls; closed/private zones; restricted/private,
guild, jail, locker and hazardous rooms; incompatible hostile-town transit;
and current blocking actors, traps or special gates that prevent ordinary
travel. An ordinary mountain room and a legitimate map/zone transition remain
valid. A closed door qualifies only if it can actually be opened without a
key or skill and has no blocking script. Model safe posture changes explicitly.
Water, no-ground, underwater and dangerous plane sectors need explicit policy,
not `can_enter_room()`'s permissive return alone.

Room, mobile and object procedures may intercept travel or ASK. Treat an
unclassified relevant procedure as unproven. Audit procedures encountered in
the representative positive routes and allow only those shown not to gate the
operation, using existing procedure identities. Do not reject every NPC with
`ACT_SPEC` or assume all room scripts are harmless. Do not build a generic
script simulator or a zone approval table.

Use one request-local traversal/live-instance context with explicit shared work
bounds, short-lived room results and no pointers retained across commands.
Keep the existing 32 target-probe and 32 history-check limits. Add a separate
shared room/edge-work limit for origin resolution, outbound and return checks;
calibrate it using the loaded-world journey and existing game-loop latency
trace. Exhaustion is **unproven**, not proof that a quest became impossible:
skip/refuse a new candidate, but never cancel/refund a valid existing quest
because a search budget ran out. Reuse results within the request, avoid one
whole-world traversal per candidate, and do not rebuild the boot catalog.

### Routine sources, live targets and truthful directions

- Add only the necessary routine-source metadata to the boot catalog using
  loaded reset commands. A direct unconditional `M`, positive limit and
  probability 100 are necessary for the conservative routine pool. Account for
  dependency flags, reset mode, random-table/follower/script-only sources and
  placement in holding/distribution rooms. A 100% line alone is insufficient.
  Inspect `db.c::reset_zone()` semantics rather than treating fields as labels.
- Require a proven ordinary placement in the destination zone; a staging-room
  only or rare/conditional source stays out of routine quests, even when it
  happens to have a counted instance. Do not classify by room name text or
  maintain a list of guessed rare VNUMs. A VNUM with a genuine independent
  routine placement can qualify through that placement, not through its rare
  instances. For ambiguous mixed sources, exclude until provenance is proved.
- Keep prototype metadata/level averages and reward pools in their current
  ownership model. Index target placements separately by actual reset room
  zone, reusing the existing profile, so 6610 and 19830 are not falsely
  advertised in their prototype-owning zones. Apply the destination zone's
  existing level/reward eligibility. A mismatch may correctly leave no target;
  do not compensate by changing level windows or borrowing another zone's reward.
- Resolve actual live NPCs once for the bounded request. Require the selected
  target to be alive, in the advertised eligible zone and on a proven route.
  Do not count probes, invalid rooms, pets/charmed summons, inaccessible holding
  rooms or unrelated populations elsewhere. Recheck immediately before
  publishing quest state; live presence and routine provenance are separate gates.
- ASK retains the exactly-one-global-instance rule and existing level/pre-31
  visibility restrictions, and additionally verifies actual visibility,
  speech/interaction and non-aggression in the target environment. Inspect
  predicates for hidden reliance on `ch->in_room` before reusing them.
- KILL requires cached combat eligibility plus live attack legality, including
  safe-room and protected NPC checks. Require at least two usable instances;
  preserve `min(difficulty_scaled_random_7_to_9, usable_count - 1)`.
  Do not promise future replenishment to satisfy the initial quota. After
  partial progress, validate supply against **remaining** kills, not the
  original quota or a fresh minus-one formula.
- Choose the map entrance from the validated route to that actual target zone.
  Store its VNUM in the existing `quest_map_room` independently of whether the
  player has bought the map; `quest_map_bought` still controls disclosure.
  Revalidate before map purchase and display, and keep text/GMCP aligned.
  No map sale for an unavailable/unproven route. A moved target cannot leave
  old zone directions or an unrelated first-marker map on screen.

### Stale assignments and persistence

Use **free replacement**, rather than retrospective cash reimbursement, as the
recovery contract for accepted quests. Exact historical fees are not recorded.
Keep the existing full refund for a new purchase that cannot create a quest.

1. Revalidate from `do_quest()` and bartender request/map/abandon handling,
   before charging or giving stale directions. Run the check once per command
   and reuse its result. A restarted or relogged quest is checked on its first
   use after world loading. Keep presentation serialization free of money/state
   side effects; publish the resulting status through the existing GMCP path.
2. Separate valid, world-unavailable, player-temporarily-blocked and unproven
   results. Despawn, incompatible relocation, insufficient remaining usable
   supply and a newly locked route can establish world unavailability.
   Blindness, temporary incapacity, the player moving elsewhere, or removing
   their own travel equipment must not grant a free reroll. Unproven script
   behavior or a budget limit is not an automatic cancellation either.
3. For a proven invalid, incomplete assignment, mark replacement due and make
   it inactive, retaining accepted level, giver/origin, type, kill progress and
   original quota, map entitlement and remaining share allowance. Explain the
   reason and the free replacement option. Do not write completion history,
   consume daily quota, remove earned XP or pay new rewards. Finished quests
   remain claimable; never cancel one because its last target was killed.
4. `ask <bartender> quest` redeems that one entitlement through the same selector
   without a new fee. Use the current request origin for the replacement and
   persist it after success. Preserve accepted level/type, earned kill count
   and original quota; require enough usable targets for the remaining work.
   Do not replay partial-kill XP, reset share limits or manufacture a completion.
   If no replacement exists, leave no active target and retain the entitlement
   across save/restart. Repeated requests cannot duplicate it. Free cancellation
   can discard it through explicit abandonment without a fee/history penalty.
   Handle recovery before the new-purchase level/quota/fee gates: it continues
   already accepted work, while still requiring loaded completion history and
   rejecting previously completed replacement targets. Never automatically
   abandon or erase progress merely because replacement is temporarily absent.
5. Add two explicit persisted values: accepted origin room VNUM (zero means
   legacy/unknown) and replacement-due flag. Use the existing append-only
   `player_status_field` mechanism with a codec version increment and old-wire
   defaults; leave the 14-value legacy quest payload layout intact. Update
   capture, SQL save/load, materialization and reset/share paths together.
   Add a guarded additive migration for the two SQL columns using the current
   migration runner. No new table, ledger or persistence service.
6. Legacy quests without an origin get target/location validation, but a guessed
   giver location must not be called their accepted origin. At a real bartender,
   validate/rebind a usable quest or offer the same free replacement for an
   invalid/obsolete contract. If the origin cannot be reconstructed on display,
   explain that a bartender check is needed; do not charge, blindly discard it,
   or show unverified directions. Preserve completed legacy quests and progress.
7. Mark quest/recovery mutations dirty with `PLAYER_COMPONENT_STATUS`; prove
   one player snapshot retains both the monetary result and associated quest
   state under the current save model. Handle shared quests explicitly: copy
   origin/accepted policy, revalidate the recipient, never copy a pending
   replacement as an active task, and retain remaining share/progress limits.

## Ablated implementation sequence and files

Current recovery slice: outcome is revalidation and a durable free replacement
for an incomplete world-invalid assignment, retaining accepted type/level, earned
progress, original quota, map entitlement and shares. Non-goals: no fee ledger,
movement simulation, general route engine or new persistence fields. Files:
existing policy, quest/bartender, text/JSON/GMCP consumers and focused fixtures.
Proof: executable revalidation/transition/command cases plus existing snapshot
evidence and disposable save/restart journeys.

Use the same route builder for current travel, maximum permitted player
capabilities, and an optimistic upper bound that includes unknown procedures.
Only the last graph's failure can prove a hard world-route loss; a relevant
unknown gate or exhausted shared work budget cannot cancel work. All passes
share the existing operation bound. Read live target instances once, use
remaining kills for accepted work, and keep the serializer read-only.

Current completion-credit slice: outcome is credit only for the accepted quest
type and advertised actual zone. The death hook calls `quest_kill` for every
matching death; source inspection found it also advancing ASK tasks, including
rewriting their zero kill quota and awarding a KILL completion. Non-goals: no
reward rebalance or death-hook refactor. Files: `world_quest.c` and the existing
production XP/completion fixture. Proof: ASK/KILL wrong-type, wrong-zone, missing
target and invalid-room cases retain exact state/XP/history; legitimate awards
retain existing behavior. Share the identical target-boundary check between the
two real completion callers.

Current presentation slice: outcome is quest status/map rendering without NPC
creation, actor transfers, hooks or lost completed/legacy quest state. Non-goals:
no selection/recovery transition or map entitlement change. Files: existing
`world_quest.c`, `json_utils.c` and their focused executable fixtures. Proof:
production text/JSON rendering with absent prototypes and invalid zones, and
telnet/GMCP map output while actor, quest and room populations remain unchanged.
Reuse boot-cached prototype descriptions and the existing synchronous GMCP map
viewpoint pattern; no new display service or alternate prototype loader.

Current live-selection slice: outcome is a real new assignment from routine
reset provenance, actual NPC locations and usable population, using the accepted
origin's bounded route context and a truthful map entrance. Non-goals: no reward
rebalance, Divine change, area repair or movement/interaction simulation. Files:
the existing world-quest policy/creation/bartender paths, small explicit-room
versions of existing visibility/aggression predicates, and focused fixtures.
Proof: controlled production selection/creation, then positive local command
journeys and relocated/zero/staging/unsafe target refusal with exact refunds.
Keep one profile/catalog and one selector; remove the prototype-only selector
and its unused convenience wrapper rather than leaving a bypass path.

Current route slice: outcome is a bounded, read-only per-request proof from the
accepted origin to actual room IDs and back, including local geography below
30 and a route-derived map entrance. Non-goals for this slice: no catalog/reward
rewrite, movement simulation, global route cache or policy configuration. Files:
`world_quest_policy.c/.h`, its math constants, the existing trap trigger predicate
(shared with actual movement), and one synthetic production-route harness.
Proof: executable room/exit cases plus a loaded-world origin/latency audit before
enabling the new selector. Reuse the existing map barrier, castle wall, dynamic
wall and shop identity predicates; classify audited procedures by identity and
leave other procedures unproven. Outbound and return searches share cached room
checks and one work bound; no whole-world search is repeated for each target.

Implementation order adjustment (2026-10-29): publish the two persisted fields
as a focused prerequisite PR before wiring the policy and recovery consumers.
This leaves each dependency independently buildable and reviewable. Outcome:
retain accepted origin and replacement entitlement through either backend,
defaulting legacy records to unknown origin/no entitlement. Non-goals: no
selector, payment, recovery, or movement behavior changes in this prerequisite.
Files: existing player status capture/codec/repository/materialization paths,
the additive migration, and their existing focused fixtures. Proof: current and
old-wire round trips, capture of wallet plus quest state, flatfile save/load,
isolated SQL migration apply/reapply/save/load, server build and format checks.
The existing status path is sufficient; no new payload, table, ledger or service
is needed. Gameplay work and the full acceptance matrix remain outstanding.

The next reviewable dependency captures the actual request room through the
existing payment context and creation API. Outcome: successful new quests retain
that VNUM even if a continuation observes a later player location; reset clears
it, sharing copies it, and the mutations mark status dirty. Non-goals: no route,
target eligibility, recovery or map policy change in this slice. Files:
`world_quest.c/.h`, `specs.mobile.c`, the existing target-retry fixture and this
handoff. Proof: execute the production continuation/creation/reset functions
with deterministic targets, moved customer, invalid origin and rejected payment;
reuse the persistence proof above and run the focused policy checks/build.
Passing VNUMs directly removes the need for live giver lookups or a second
payment/quest API. Origin validation remains a prerequisite for full route work.

- [ ] **1. Pin baseline and executable failures (1-2 hours).** Extend
  `tests/async/test_world_quest_target_retries.py` for live availability and
  bounded retries; add one focused production-policy route harness if the
  current lightweight fixture cannot represent real room/exit state. Use
  controlled RNG and synthetic graphs, not a copied selector. Reproduce foreign
  selection at 11/29 and unusable 23501 placement through full creation. Record
  the archived policy decision and limits of the named production reports.
- [x] **2. Resolve origin and routes (3-4 hours).** Implement the explicit
  origin/context and conservative traversal in `src/world/world_quest_policy.c`
  and `.h`, with constants in `world_quest_policy_math.h` where appropriate.
  Wire `world_quest.c/.h` and `specs/specs.mobile.c` to pass the request origin.
  Use movement/map sources as contracts; change those production files only
  for a small justified shared read-only predicate.
- [x] **3. Select and describe live routine targets (2-3 hours).** Extend boot
  placement metadata and per-request filtering in the same policy module;
  use actual zone/live supply in `createQuestForGiverVnum()` and validated
  entrances in `quest_buy_map()`. Retain boot level/reward calculations and
  fail-closed history behavior. Update the misleading failure message that
  currently tells low-level players to try colleagues around the world.
- [x] **4. Recover and persist existing work (2-3 hours).** Implement the shared
  validator/replacement transition in `world_quest.c/.h` and bartender handling.
  Touch `src/core/structs.h`, `src/player/player_snapshot.h`,
  `player_snapshot_capture.c`, `player_snapshot_codec.c`,
  `player_snapshot_repository.c`, `player_load_repository.c`, and
  `player_load_materialize.c`, plus the additive migration and its maintained
  schema/runner registration. Update `core/json_utils.c` / `net/gmcp.c` only
  as needed to represent unavailable/replacement status and truthful maps.
  Preserve the legacy importer payload and initialize new fields safely.
- [ ] **5. Prove complete journeys and document (4-6 hours).** Extend
  `tests/async/run_world_quest_dual_backend.py` with request, actual travel,
  ASK/KILL completion, invalidation, free replacement, save and restart.
  Reuse its disposable world/account/database setup and existing client.
  Extend snapshot/codec/load and GMCP tests where the new fields require it.
  Update `docs/reference/CODEBASE.md` and the maintained bartender help source
  after locating its authoring path; do not edit generated help/area output.
  Record exact results here, reread the diff and cut unsupported machinery.

**Ablation decisions:** keep geography, route checks, routine provenance, live
selection and durable recovery because each closes a distinct demonstrated
failure. Simplify around one catalog and one reusable quest validator; reuse
existing payment, player status, migration and journey mechanisms. Choose free
replacement to avoid a new fee ledger and invented legacy refunds. Drop the
old distance formula, prototype-count-only patch, direct reuse of Divine paths,
generic routing service, movement simulation, global route cache/invalidation
framework, new configuration surface, custom test framework and production-wide
content cleanup. Do not add a report, dashboard or separate approval stage.

## Proof and acceptance

The regressions must exercise production decisions and full command routes,
not merely assert that a source string or helper exists.

- **Levels/geography:** 10/11, 29/30, 40/41 and 49/50; local versus foreign
  candidates; interior origin with continent zero; multiple entrances in one
  region; conflicting/unknown origin; Underdark origin and surface transition;
  no local candidate with exact new-purchase refund and no active quest.
- **Routes:** mountains/cavern walls even with flight; ordinary mountain rooms
  and authored map/zone transitions; nearby but separated by a wall;
  one-way entry without a return and an alternate legal return; blocked final
  room; locked/key/secret/blocked/walled edges; openable unlocked doors;
  changed doors, occupied/restricted rooms, hostile transit and an actual
  scripted gate; water/flight capability present versus absent; source-specific
  access rather than reachability from some other faction hometown. Prove the
  traversal leaves characters, events, doors and room populations unchanged.
- **Targets:** zero live instances despite successful prototype loading;
  rare/conditional source and 100% staging-only reset; actual target moved
  outside the advertised zone; reused 6610/19830 and representative 4405
  placement; global count sufficient but usable population insufficient;
  live ASK invisibility/speech/aggression and KILL safe/protected NPC rejection.
  Keep tests for named centaur/IceCrag examples qualified by the full level
  pipeline, and add the exact reported targets if identified.
- **Recovery:** target extracted after acceptance, moved or made inaccessible;
  another player's kills leaving insufficient remaining supply; legitimate
  partial progress; a completed quest whose target is now gone; voluntary
  abandonment retaining its current charges/history; no fee/history penalty
  for server-invalid work; no candidate while replacement is due; repeat
  requests; player movement/temporary incapacity; shared recipients; legacy
  unknown-origin records; save/relogin/restart on both backends. Assert exact
  wallet, progress, XP, quota, history, entitlement and map outcomes.
- **Compatibility/performance:** accepted-level reward floor, withheld rewards,
  weighted sampling among eligible zones, 32-probe/history bounds and history
  read failure remain covered. New traversal bounds are exercised with an
  intentionally oversized graph; exhaustion never invalidates an existing
  task. Record loaded-world command/observer latency and visit counts, avoiding
  unbounded scans and catalog rebuilds. Unknown geography must not empty every
  real hometown's useful low-level pool: qualify positive Good-side and Evil-side
  origins and an Underdark origin, or report the specific unsupported route.
- **Real play:** in disposable flat-file and MariaDB servers, request at
  Woodseer at levels 11 and 29, follow a validated route with ordinary movement,
  interact/kill and complete. Exercise at least one level-30 control, map
  purchase and dynamically invalidated persisted quest. Setup may place the
  synthetic player at the bartender; travel proof may not teleport it to the
  target. Repeated random sampling alone does not prove the policy.

Planned focused commands after implementation (new route/recovery entry points
are added when their fixtures are written):

```sh
python3 tests/async/test_world_quest_dynamic_policy.py
python3 tests/async/test_world_quest_target_retries.py
python3 tests/async/test_world_quest_failure_feedback.py
python3 tests/async/test_world_quest_reward_policy.py
python3 tests/async/test_world_quest_xp_feedback.py
python3 tests/async/test_flatfile_world_quest_history.py
python3 tests/async/test_player_snapshot_capture.py
python3 tests/async/test_player_item_snapshot_codec.py
python3 tests/async/test_flatfile_player_repository.py
python3 tests/async/test_player_load_pipeline.py
python3 tests/async/test_gui_gmcp_contract.py
python3 tests/async/test_persistence_migration_contract.py
python3 tests/async/test_runtime_boot_compatibility.py
python3 scripts/validate_runtime_compatibility.py
python3 tests/async/run_world_quest_dual_backend.py
make -C src
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Extend `player_item_snapshot_codec_harness.cpp`'s current/old-wire fixtures for
the two new fields, and the dual-backend fixture for the migration's isolated
apply/reapply/load checks. Register the new apply/verifier and hashes in
`migrations/migration_manifest.json`; follow the existing immutable migration
contract, without editing sealed historical payloads. Keep all new compiled
output below `bin/`.
The dual-backend journey builds private binaries and uses disposable state and
Docker MariaDB; it does not read `.env`. This checkout reports `ENVIRONMENT=local`.
No production operation, player-data rewrite, wipe or live-world deployment is
part of implementation qualification. Local evidence is the completion gate;
do not wait for hosted CI or claim unrun checks passed.

## Planning validation and handoff

### Implementation checkpoint: persistence prerequisite (2026-10-29)

Review-ready PR: [#451](https://github.com/LuminariMUD/Duris/pull/451),
implementation commit `0cafcc82c`. Its head is `branch/issue-437-bartender-quest-routes`; stack further
implementation on it while the dependency remains open. Do not merge or deploy
the unfinished #437 policy as though this prerequisite completed the issue.

Implemented accepted-origin VNUM and replacement-due status fields in snapshot
schema 13, status capture, SQL save/load and character materialization. The
existing 14-value quest array and its SQL ordering remain intact. All supported
old wire versions (1, 3, 5, 7-12) receive zero defaults on status loads; partial
saves without status receive no invented quest state. Legacy pfile import also
sets both values to zero. Immutable migration `0055_world_quest_recovery`
(manifest sequence 56) adds guarded columns and verifies their definitions.
The baseline/bootstrap and sealed older migrations are unchanged.

Loaded-world follow-up found a missing runtime-contract update: after applying
0055, the compiled boot gate still expected head 0054 and refused the disposable
database with COMPAT-E002. The first focused save/load checks had not booted a
server and did not cover this boundary. The correction in this dependency
updates `migrations/runtime_compatibility_manifest.json` and
`src/core/runtime_compatibility_contract.h` to head 0055, sequence 56, its apply,
verify and complete-history checksums, and measured schema fingerprints from
disposable MySQL 8.0 and MariaDB 10.11. Both engines retain 200 runtime tables.
Runtime compatibility checks are now explicit in the completion commands above.

Correction qualification (all passed):

- `python3 tests/async/test_runtime_boot_compatibility.py`: all 7 passed.
- `python3 scripts/validate_runtime_compatibility.py`: valid synchronized head,
  history and measured fingerprints.
- `RUNTIME_DB_IMAGE=mariadb:10.11 bash tests/async/run_runtime_compatibility_mysql.sh`
  and the same command with `RUNTIME_DB_IMAGE=mysql:8.0`: passed, including
  full-schema checks and intentional schema/history drift rejection.
- `DURIS_WORLD_QUEST_BACKEND=mariadb
  DURIS_WORLD_QUEST_BINARY=/home/aiwithapex/projects/duris/bin/server/dms_new
  python3 tests/async/run_world_quest_dual_backend.py` (environment assignments
  on the same command line): passed. This uses the corrected build and a
  disposable migrated MariaDB server, grants and abandons real bartender tasks,
  saves their status, and exits normally. It proves the runtime boot boundary;
  it does not qualify the unfinished route policy.
- `make -C src -j2` and format/diff checks: passed. Logs under
  `bin/tests/issue437-compat-{mariadb,mysql,journey,build}.log`.

This is the prerequisite portion of step 4, not completion of step 4 or #437.
Selection, origin capture at the bartender, recovery transitions, sharing/reset
integration, route-derived maps, GMCP and real gameplay journeys still need
implementation. Existing policy/target-retry evidence above remains applicable
to the unchanged selector only; it does not qualify the proposed new behavior.

Focused evidence for the prerequisite:

- `python3 tests/async/test_player_snapshot_capture.py`: passed, exercising
  capture/codec of origin, entitlement, partial kill progress and wallet together.
- `python3 tests/async/test_player_item_snapshot_codec.py`: passed with
  ASan/UBSan, current/old-wire defaults and rejection of new field IDs in v12.
- `python3 tests/async/test_flatfile_player_repository.py`: passed, including
  persistence of recovery fields across an unrelated component checkpoint.
- `bash tests/async/run_player_save_claim_mysql.sh`: passed on disposable
  MariaDB 10.11. Apply/reapply retained a synthetic legacy row and its progress;
  real status writer/loader retained quest and wallet state together; an injected
  failure rolled both back and retry succeeded. Includes existing save-claim,
  load-filter and zone-state checks on that same disposable database.
- `python3 tests/async/test_immutable_migration_runner.py`: all 25 passed.
- `python3 tests/async/test_player_load_pipeline.py`: passed.
- `python3 tests/async/test_persistence_migration_contract.py`: passed.
- `python3 tests/async/test_pfile_tool.py`: passed, including `_PFILE_` build.
- `python3 tests/async/test_documentation_contract.py`: all 14 passed.
- `make -C src -j2`, `./scripts/format.sh --check`, `git diff --check`: passed.

Build/SQL logs are local under `bin/tests/issue437-build.log` and
`bin/tests/issue437-sql.log`. No gameplay route/recovery or restart qualification
is claimed yet, and no production operation occurred. Next: stack origin/route
policy and executable synthetic
graph regressions; keep the full outcome and acceptance matrix above.

### Implementation checkpoint: accepted-origin capture (2026-10-29)

Working branch: `branch/issue-437-bartender-route-policy`, based on #451 head
`9a2fd8db0`. Review-ready stacked PR:
[#452](https://github.com/LuminariMUD/Duris/pull/452), implementation commit
`0f71055a3`, targeting #451's branch. The bartender validates co-location and captures its request room
VNUM into the existing payment context. Creation accepts that explicit origin
and stores it only on success; an invalid origin takes the ordinary failure and
refund path. The synchronous giver API checks co-location too. No later player
position or duplicate giver instance is used to infer the accepted origin.
Reset clears origin/entitlement; sharing copies origin; create/reset/share mark
`PLAYER_COMPONENT_STATUS` dirty. The selector remains unchanged in this slice.

Evidence:

- `python3 tests/async/test_world_quest_target_retries.py`: passed. The existing
  fixture now runs the production payment continuation as well as production
  creation/selection: captured room 16633 survives a customer position change;
  invalid origin refunds exactly once with no active quest; payment rejection
  creates no quest; resets clear origin; successful creation marks status dirty.
  The synchronous giver entry point captures the co-located room and rejects a
  remote giver without changing the accepted quest.
  Existing history/probe bounds and failure-state preservation still pass.
- `python3 tests/async/test_world_quest_failure_feedback.py`: passed.
- `python3 tests/async/test_world_quest_dynamic_policy.py`: passed.
- `python3 tests/async/test_world_quest_reward_policy.py`: passed.
- `python3 tests/async/test_world_quest_xp_feedback.py`: passed for MariaDB and
  flatfile fixtures, including existing kill-credit and trainer behavior.
- `./scripts/format.sh --check`, `git diff --check`: passed; documentation
  contract all 14 passed.
- `make -C src -j2`: passed (incremental build, log
  `bin/tests/issue437-origin-build.log`). Persistence evidence from #451 is
  unchanged and is reused; no database suite rerun for this consumer wiring.

Next: build the bounded read-only route context and synthetic room/exit
regressions, then use that same context for live routine-target selection and
revalidation. None of the route, availability or stale-recovery acceptance
claims are satisfied merely by recording the origin. Step 2 remains open until
the traversal and full creation path enforce the contract.

### Route proof prerequisite (2026-10-29)

Working branch: `branch/issue-437-ordinary-routes`, based on #452 head
`5daa9ce34` (including #451's runtime-contract correction). The independently
qualified request-local traversal is implemented in `world_quest_policy.c`.
Review-ready stacked PR: [#458](https://github.com/LuminariMUD/Duris/pull/458),
implementation commit `dab40e144`, targeting #452's branch. The parent runtime
contract correction is commit `3f9a6eb4e` in #451.
The current selector does **not** call it yet. Step 2 stays open until the full
creation path uses it, and step 3 still needs routine/live target selection.
No route-enabled assignment, recovery or real travel outcome is claimed here.

Outward edges and a reverse walk prove directed return reachability, including
alternate return paths. Geography uses potential ordinary connections through
interiors to find unambiguous first map boundaries, separately from actual travel
proof. This prevents an unrelated unknown side-street procedure from erasing a
proved local region. A low-level interior origin must still reach an actual map
boundary through the strict travel graph. Surface continents and directed
Underdark map components are distinct; local restriction ends after accepted
level 29. At 30+, the proof permits present boat, flight and waterbreathing
capabilities. Groundless surface and Underdark sectors require flight; ordinary
low-ceiling passages allow kneeling/crawling without mutating actor posture.

The code reuses `map_entry_barrier`, `check_castle_walls`, `check_wall` and
`singleton_shop_id`; the latter was traced as a read-only lookup, and its
possible unbound-shop scan is charged to the work budget.
`movement_trap_trigger` is extracted from the existing movement trap expression.
Audited travel-safe identities are room `inn`/`ship_shop_proc`, mobile
`world_quest`/`quester`, and object `board`. Shops qualify only when their resolved
secondary procedure is absent or one of those audited mobile procedures.
These are **travel/door** classifications, not permission to assume an NPC's
ASK handler is safe. Other procedures, room affects, occupied single-file
passages, falling/current conditions remain unproven.

Ablation: keep one shared connection rule for geography and actual traversal,
with scripts/actors additionally checked for travel; no movement simulation,
global route cache, configuration, zone approval list or parallel path engine.
Removed unused predecessor storage: the existing reverse edge graph already
supplies the return proof. The result contains room IDs and facts only and must
be rebuilt for the next command.

Evidence:

- `python3 tests/async/test_world_quest_routes.py`: production traversal linked
  with the real map/trap predicates under ASan/UBSan. Covers 10/11, 29/30,
  40/41, 49/50, explicit origin versus another origin's access, interior origin,
  same/foreign/conflicting/unknown geography, distinct Underdark components,
  directed alternate returns, closed/unlocked versus locked/spiked/secret/
  blocked/walled doors, map barriers even with flight, ordinary mountain
  transitions and crawling, restricted rooms/zones, faction transit,
  boat/flight/waterbreathing, known/unknown/secondary procedures, carried/worn
  object handlers, dynamic walls/traps and oversized traversal exhaustion.
  Actor, status, rooms and exits remain byte-for-byte unchanged.
- `python3 tests/async/test_legacy_trap_effects.py`: passed with ASan/UBSan.
- `python3 tests/async/test_world_quest_dynamic_policy.py`: passed.
- `python3 tests/async/test_world_quest_target_retries.py`: passed.
- `make -C src -j2`: passed; `bin/tests/issue437-route-build.log`.
- `python3 tests/async/test_documentation_contract.py`: all 14 passed.
- `./scripts/format.sh --check` and `git diff --check`: passed.
- A disposable MariaDB loaded-world debugger audit ran the production context
  for **38 actual bartender origins / 114 requests**, at levels 11, 29 and 30.
  Final sample: maximum **322,428 work units**, maximum **27,432 microseconds**,
  no exhaustion. Bounds remain 65,536 inspected rooms / 2,000,000 shared work
  units, leaving room for the forthcoming bounded live-instance checks.
  These are helper timings, not command/observer latency or a worst-case
  latency guarantee. The oversized synthetic graph verifies exhaustion returns
  unproven, never cancellation authority.
- Woodseer 16633 proved 18,034 returnable rooms at 11/29; Ixie origin 97653
  proved 12,740; Drow origin 36563 proved 2,523. The audit found respectively
  10/256, 0/85, and 0/0 reachable live instances passing only the existing
  level/zone windows at 11/29. These are **not** fully eligible quest targets:
  routine provenance, interaction/attack legality and history still need their
  planned checks. Do not relax level windows or rewards to fill empty pools.
  Drow and several other origins lack a verified useful low-level pool; further
  qualification must report the precise unsupported origin when it remains.
- Local audit source and exact records are under
  `bin/tests/issue437-routes/loaded_routes.cpp`, `run_loaded.py`, and
  `runtime7/routes.tsv`; the same directory retains earlier failed probes.
  The first loaded audit exposed the fixed boot-contract omission. Later
  audits exposed the overbroad side-street rejection and shop secondary
  `world_quest` delegate; the executable fixture now covers both regressions.

Next: wire this context into one bounded request/live-instance selection path,
index direct unconditional 100% reset placements by their actual zone, and use
actual usable population and route-derived maps in creation. `db.c::reset_zone`
sets `GET_BIRTHPLACE(mob)` to the reset room VNUM for direct `M` loads; pair that
with routine-placement metadata rather than counting unrelated/rare instances.
The local level-11 candidates 16305/16306 independently have direct ordinary
resets in Twisted Wood and staging resets in 16399: keep only usable instances
from proven ordinary sources, not the global count.

Before recovery consumes a failed route result, separate temporary player
capability loss and relevant unknown scripts from proven world unavailability.
The context currently returns unproven for missing routes when any encountered
procedure was unknown; an irrelevant unknown branch must not conceal a
definitively locked target route. All recovery, real ASK/KILL completion,
save/relogin/restart and command/observer latency acceptance remains open.

### Live selection review checkpoint (2026-10-29)

Working branch: `branch/issue-437-live-quest-targets`, based on #458 head
`d91a924bf`. Review-ready PR: [#464](https://github.com/LuminariMUD/Duris/pull/464),
implementation commit `296fcd94c`; base is #458.
`world_quest_policy_select_target` now owns one complete bounded selection path:
boot-cached direct unconditional 100% `M` placements, per-instance birthplace
matching, actual destination zone, a single live-character index, reachable
ordinary source and current room, live ASK/KILL suitability and usable kill
population. Mixed conditional/F/R sources at the same birthplace and random
table rooms stay ineligible. Prototype level averages/reward ownership remain
unchanged. The obsolete prototype-only selector and both convenience wrappers
are removed. History is read before the final live validation; history results
are cached per VNUM while failed attempts are tracked per zone so cross-zone
reuse can retry without duplicate history queries.

Creation publishes the validated target and entrance, sets the initial quota
from usable count minus one, and preserves failure state. Map purchase consumes
the cached entrance and refunds a failed map publication. Below-30 refusal text
no longer advises intercontinental travel. Visibility/aggression now have
explicit-room variants sharing the original implementations; ordinary callers
retain wrappers for their current rooms. Projected visibility accounts for the
observer's own mage flame without relocating it.

Passed: `test_world_quest_target_retries.py` now links the real cached policy,
production visibility/aggression/creation/map/payment bodies and controlled
reset/live fixtures under ASan/UBSan. All **63 scenarios** passed, including
level boundaries, actual-zone reuse, rare/conditional/staging/removed targets,
live interaction/protection changes, lost summon ownership/charm/following,
actual usable quotas, exact fee refunds and map charges, moved-customer origin,
history failure and request-wide 32-probe/history bounds (including last valid
slots and cross-zone retries). Projection room-bounds and planar-affinity tests,
dynamic policy, failure feedback, rewards and difficulty checks passed.

Real loaded-world follow-up identified the starter hide artifact and regeneration
ring as harmless SAY/RUB/periodic handlers that the route proof had conservatively
left unknown. Their owning procedures were audited and those two identities are
now travel-safe, with held/worn regressions that abort if a procedure is invoked.
Unknown held procedures remain unproven. The actual level-56 actor then reached
17,892 rooms using 300,805 work units without exhaustion, but had no eligible
live level/zone targets. The refund is a supported refusal, not a positive grant
or evidence that a new high-level content pool should be invented.

Positive real disposable MariaDB command grants passed at Woodseer for **11 and
29**. Level 11 indexed ordinary 16306 instances while excluding the same VNUM's
staging-born copies. The maintained dual-backend runner now sets its disposable
Chaos actor to 11 with GDB before the first command; no production test command
or content policy was added. Retained Chaos HP/equipment do not qualify combat
difficulty. The MariaDB grant / pipelined paid abandon + next grant / save /
normal shutdown passed (`bin/tests/issue437-live-mariadb-journey.log`,
binary SHA256 `46c07efa21cc0520fad0be5adc150f9debd6de176af5d1b459a48d563338a890`).
The saved row contains target 16306, actual zone 163, origin 16633, quota 1,
verified entrance 568109, map not bought and no replacement due. One catalog
build served both requests. The level-29 grant's private diagnostic record is
`bin/tests/issue437-live-actor-29.log`. These grant checks do not prove travel or
completion. The incremental flatfile build and the same real grant/paid-abandon/save/clean-shutdown journey also passed (`bin/tests/issue437-live-flatfile-journey.log`), binary SHA256 `ac7c22470f2a2e0c8c71316feec57831c11ab6a19f6f06cd722ebe85f4660989`. This grant smoke has no restart/completion claim.

Also passed: `make -C src -j2`; route ASan/UBSan fixture; projection, planar
affinity, dynamic policy, failure feedback, reward, difficulty, help parser and
all 14 documentation contracts; format and diff checks. Updated the codebase
reference and maintained parsed Quest help to describe implemented new selection.

Next focused change: remove existing display-time prototype creation from
`do_quest` / JSON status and room transfer hooks from `show_map_at`. Then implement
accepted-target revalidation, durable free replacement, legacy/share handling
and truthful unavailable maps. Required 11/29 ordinary travel and ASK/KILL
completion, save/relogin/restart on both backends and command/observer latency
journeys remain open. Do not treat this selector PR as completion of #437.

### Read-only presentation checkpoint (2026-10-29)

Review-ready PR: [#465](https://github.com/LuminariMUD/Duris/pull/465),
implementation commit `dbd0bc2c6`, branch `branch/issue-437-quest-presentation`,
based on #464 head `103e289a2`. Text QUEST and JSON status now use `mob_index[].desc2`, whose owning
loader stores the prototype short description. Removed temporary NPC creation/
extraction and the display-time reset of a paid quest when its giver cannot be
loaded. Missing target/zone metadata produces unavailable details while keeping
progress and completed work. Real live eligibility/recovery is the next slice.

`show_map_at` now reuses `gmcp_quest_map`'s synchronous non-moving viewpoint,
restores the room immediately, rejects invalid room IDs, and uses the explicit
`Quest.Map` renderer package. It no longer transfers the actor, invokes arrival/
departure hooks, changes populations, interrupts actions or overwrites `Room.Map`.

Passed: `test_world_quest_remaining_unloaded.py` executes the complete production
QUEST display and JSON serializer under ASan/UBSan for ASK/KILL, unknown history,
missing giver/target/description/zone and completed assignments; NPC loads,
extraction and quest reset abort in the fixture, and status remains byte-identical.
`test_gui_gmcp_contract.py` executes the production text map entry point and normal
GMCP serializers/framing; transfer hooks abort, map and observer-room state remain
unchanged, unpaid/invalid maps emit nothing, and Quest.Map uses its own channel.
`make -C src -j2` and the real MariaDB grant/paid-abandon/save/clean-shutdown smoke passed on binary SHA256 `1c35d86179ba7cf31cd78adf93b2ef4e630dfeedfe5fb93639ec96790b5a9c93` (`bin/tests/issue437-presentation-mariadb-journey.log`). Full stale recovery, legacy policy and the gameplay/
restart journeys above remain open.

### Completion credit checkpoint (2026-10-29)

Review-ready PR: [#466](https://github.com/LuminariMUD/Duris/pull/466),
implementation commit `64fb0b322`, branch `branch/issue-437-quest-credit-boundaries`,
based on #465 head `27c5ff704`. Source tracing found that `fight.c` calls `quest_kill` for every
matching player/group death, while the credit function omitted a quest-type
check. Killing an ASK singleton could therefore rewrite its zero kill quota,
pay XP and manufacture a KILL completion. Both completion functions also
accepted the same VNUM outside the advertised zone, bypassing actual-zone
selection. One private shared predicate now checks alive PC, active assignment,
accepted type, live target identity and target room's zone before either hook.

The existing `test_world_quest_xp_feedback.py` production-body fixture now covers
wrong type, wrong zone, missing/unroomed/out-of-range/wrong-VNUM targets for both
hooks, with unchanged quest/XP/history and positive ASK/KILL controls. Its full
existing award suite passed under ASan/UBSan for MariaDB and flatfile. Also
passed: `make -C src -j2`, policy, 14 documentation, format and diff checks.
No death-hook refactor, reward rebalance or unrelated progression change.
This is a separate focused repair found while tracing #437's recovery path;
accepted-assignment recovery and full gameplay/restart proof remain next.

### Recovery review checkpoint (2026-10-29)

Working branch: `branch/issue-437-quest-recovery`, based on #466 head
`fd1702522`. Review-ready PR: [#467](https://github.com/LuminariMUD/Duris/pull/467),
implementation commit `787f0c6fd`.

The same route builder supplies current/capable/potential proofs within one shared
work bound. Accepted-target validation uses one live scan, saved origin/level,
routine sources, live suitability and remaining kill supply. Hard final/return
locks remain unavailable despite unknown side branches. Relevant unknown
procedures, temporary player restrictions, lost travel capability and exhausted
bounds cannot alone authorize replacement. Zero-origin legacy work gets
target/location checks and needs a real bartender origin before directions.

`world_quest_refresh` marks proven invalid incomplete work inactive/due without
wallet, XP, history or reward changes. `world_quest_replace` uses the same selector
with fixed accepted type and remaining quota. Earned kills, original quota,
accepted level, shares, map entitlement, receiver and original start time survive.
Failed/repeated redemption and completed legacy work are preserved. Recovery and
completed claims precede new-purchase level/allowance gates. Confirmed abandonment
can discard an entitlement for free; normal voluntary abandonment retains its fee
and partial-progress history behavior. Sharing checks the recipient before copying
state and cannot overwrite a replacement entitlement.

Checked text/GMCP overloads reuse one command's verdict; JSON remains read-only.
Quest.Status exposes availability/replacement-due and retains pending progress/map
entitlement. Unverified target/zone directions are withheld and empty Quest.Map
clears stale directions. No extra fields, ledger, global route cache or service.
Final caller tracing removed three unused one-argument map/JSON adapters added
by this slice: every real caller already carries a checked verdict. The normal
one-argument GMCP status gateway remains because login/combat callers use it.
Only the checked map/serializer APIs remain, avoiding another validation path.
Both incremental builds, the 71-scenario native suite and text/JSON/GMCP fixtures
passed after removing these unused adapters; the real journey evidence above is
reused because its production call path is unchanged.

Evidence:

- `test_world_quest_target_retries.py`: **71 production scenarios under
  ASan/UBSan**. Eight accepted ASK/KILL matrices at 11/29/30/41 include real
  refresh/replace transitions and complete bartender/QUEST/sharing commands:
  unknown origin/rebind, actor movement, temporary conditions, hard final/return
  locks versus unknown side branches/gates, lost capabilities, remaining supply,
  accepted-target bounds, exact state retention, free redemption below admission
  and with zero daily allowance, failed/repeated requests, map charges, free
  cancellation, normal paid abandonment and recipient eligibility. Existing 63
  selector/creation/payment regressions remain in that run.
  Log: `bin/tests/issue437-recovery-commands.log`.
- `test_gui_gmcp_contract.py`: real serializers/wire paths cover all unavailable
  states, clearing stale maps with retained entitlement and progress, and prove
  checked rendering performs no second eligibility query.
  `test_world_quest_remaining_unloaded.py`: complete text/JSON rendering under
  ASan/UBSan, missing metadata, finished work and unknown history.
- `test_world_quest_routes.py`; `test_world_quest_xp_feedback.py` (both backends);
  policy, failure feedback, help parser and all 14 documentation contracts passed.
  Format and diff checks passed. Both incremental server builds passed.
- Maintained real journey passed separately on **MariaDB and flatfile**:
  new grant, pipelined paid abandon/new grant, map purchase, disposable world
  invalidation, no-candidate entitlement retention, SQL save (MariaDB), 20
  ordinary town exits to Quivering Leaf Inn, real RENT/relogin, normal server
  shutdown, restart/materialization, and free redemption after content returns.
  Exact accepted fields, wallet and XP are compared across save/relogin/restart
  and redemption. Each process built the catalog once (two boots total).
  These runs used fresh quota-1 KILL assignments; partial 3-of-4 progress is
  proved in the native transition/command fixture, not claimed as real combat.
  The explicit test helper grants 100,000 copper after restart for placement;
  redemption compares the wallet immediately after that setup and charges zero.
- MariaDB log: `bin/tests/issue437-recovery-mariadb-journey.log`, binary SHA256
  `92e7554f770104b3079e0584884165dd235c8866988196f02e034af2d903f875`.
  Original target 16306, replacement 16329, zone 163, origin 16633, quota 1 and
  map entrance 568109; paid map and original start time retained, XP stayed 1.
  Wallet 99,118 survived invalidation/relogin/restart; setup then made it 199,118
  and free redemption left that amount unchanged.
- Flatfile log: `bin/tests/issue437-recovery-flatfile-journey.log`, binary SHA256
  `0f25e09e09e2df797fcb7e6df4e099459233dfb4f76370581b1b503c4d23688a`.
  Same boundaries, replacement 16305. Wallet 99,122 survived until explicit setup
  made it 199,122; redemption left it unchanged. XP stayed 1.
- Fixture repairs: wait for complete async character entry before commands, use
  native inn RENT rather than camping in a city, and pass normal SIGPIPE through
  GDB. The debugger probe uses raw function entry/SysV x86-64 argument registers;
  optimized DWARF initially read the caller's NPC register before the prologue.
  Probe assertions and exact redemption comparisons remain strict. None of these
  repairs changed production logout/signal/quest rules.

Remaining: original baseline/named-target qualification still marked in step 1;
step 5's actual target travel and ASK/KILL completion at 11/29, level-30 control,
real partial progression/history/quota proof, representative Good/Evil/Underdark
qualification (or precise unsupported origin), and command/observer latency.
The final map-request hint was clarified after those real runs to distinguish a
pending entitlement from a failed replacement search. Both builds and the native
71-scenario suite passed again; the quest transition/routing logic is unchanged.
Recovery component qualification does **not** close #437.

Completed on the source baseline:

- Read the full issue and its three comments, traced the current selector,
  creation/payment/display/completion paths, inspected movement/reset/content
  semantics and both player persistence mappings, and inspected the earlier
  selector and its committed policy specification.
- `python3 tests/async/test_world_quest_dynamic_policy.py`: passed.
- `python3 tests/async/test_world_quest_target_retries.py`: passed.
- `python3 tests/async/test_world_quest_failure_feedback.py`: passed.
- `python3 tests/async/test_documentation_contract.py`: all 14 tests passed.
- `git diff --check`: passed.
- Prior #428 plan preservation: SHA-256 of the archived file and the original
  tracked blob both equal
  `db2e06ff1afe39dba4629cc840c579b994e04965df0e31995174625eee95fdbf`.

These are planning/baseline checks, not implementation qualification. No C/C++
file changed, so a server build and the new gameplay journeys are not claimed.

Issue #437 is the implementation work item. No existing matching development
branch or open PR was found. Targeted searches of the connected
`max757/duris` mirror found related display/telemetry records, not a matching
route/availability work item; do not link unrelated work or create a duplicate.
The branch is linked to #437 through GitHub's Development association, verified
with `gh issue develop 437 --repo LuminariMUD/Duris --list`. #448 is an already
landed reference, and #4/#37 are outside this branch's scope.

## Estimate for me to implement

**12-18 hours of my active implementation and local validation time**, broken
down in the five steps above. Most effort is in truthful route/target checks,
legacy recovery semantics and dual-backend gameplay proof, not the below-30
comparison. Allow up to **24 hours** if procedure classification or usable
low-level content needs further investigation, or the disposable persistence
fixtures need repair. This excludes external review, production fact collection
requiring owner access, merge scheduling and deployment. The estimate is for
the complete issue scope, not a same-continent-only patch.


### Room-selector repair found during gameplay qualification (2026-10-29)

Outcome: a generated NPC selector must remain one command argument and resolve
to the same NPC after native ASK parsing. Non-goals: no targeting-policy change.
Files: `world/handler.c` and the existing native room-selector fixture. Proof:
two NPCs named `guard patrol` / `guard captain`, where selecting the captain
must survive production `half_chop` and resolve `2.guard` to the captain.

The previous helper could emit `1.guard captain`. ASK split that into target
`1.guard` and message `captain ...`, addressing the patrol instead. The old
fixture's simplified `isname` stub masked this by matching only single words.
The fixture now links production `isname` and ASK's actual parser. It reproduced
the failure before the fix (`bin/tests/issue437-room-selector-before.log`).
The helper now extracts the first name keyword before calculating the ordinal;
racewar/visibility/height/disguise predicates remain shared and unchanged.
Review-ready PR: [#468](https://github.com/LuminariMUD/Duris/pull/468), commit
`d85f60a57`. The focused ASan/UBSan suite, server build, format/tidy/diff checks
passed. This is a separate focused fix stacked on #467, discovered while preparing real
quest interaction. The gameplay qualification plan is preserved in task-owned
stash `aeb4a5d792af549a10794f035342141cd1333ef0` pending return to
`branch/issue-437-gameplay-qualification`; apply it only after this fix is merged
into that local branch and drop only this verified stash.


### Passive route traces repair (2026-10-29)

Review-ready PR: [#469](https://github.com/LuminariMUD/Duris/pull/469), commit
`494002a8f`, based on #468.

Outcome: ordinary walking/combat traces must not turn a proved route into an
unknown gate. Non-goals: no generic procedure exemption or area allowlist.
Files: `world_quest_policy.c` and the existing route/live-target fixtures. Proof:
route and accepted-target checks with tracks/blood stains, actor/status/rooms
unchanged and procedures never invoked; unknown handlers remain unproven.

The real level-11 ASK trip reached Woodseer streets, then failed at a footprint
left behind (VNUM 1276): ordinary return validation stopped at the new object's
`tracks` procedure. `cmd/track.c` creates it during movement. Its owning handler
in `specs.object.c` handles only decay. Blood stains are likewise created by
normal combat/bleeding (`fight.c` and `handler.c`), and their handler handles only
setup, cosmetic periodic updates and decay. Both identities are now classified
as travel/door/ASK-safe. No procedure runs during validation.

The focused route fixture reproduced the failure before the fix
(`bin/tests/issue437-passive-traces-before.log`). Extended existing accepted
ASK/KILL checks at 11/29/30/41 with the same trace identities. The interrupted
gameplay work is preserved in task-owned stash
`0257c956eb3f6d3e5cc451ba1a06221c1a856ab4`; apply it on the gameplay branch after
fast-forwarding this focused fix, then drop only that verified stash.
Temporary `Q437_DEBUG` owning-source logging was removed completely.

Passed after the passive-trace fix: route ASan/UBSan fixture, all 71 production
selector/recovery/command scenarios, server build, format and diff checks.
