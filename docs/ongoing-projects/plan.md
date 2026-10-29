# Issue #437: usable bartender quests and recovery

Status: **implementation in progress; persistence prerequisite first**. Updated 2026-10-29.
Issue: [Duris #437](https://github.com/LuminariMUD/Duris/issues/437), including
all three investigation comments. Implementation branch:
`branch/issue-437-bartender-quest-routes`.
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

- [ ] **1. Pin baseline and executable failures (1-2 hours).** Extend
  `tests/async/test_world_quest_target_retries.py` for live availability and
  bounded retries; add one focused production-policy route harness if the
  current lightweight fixture cannot represent real room/exit state. Use
  controlled RNG and synthetic graphs, not a copied selector. Reproduce foreign
  selection at 11/29 and unusable 23501 placement through full creation. Record
  the archived policy decision and limits of the named production reports.
- [ ] **2. Resolve origin and routes (3-4 hours).** Implement the explicit
  origin/context and conservative traversal in `src/world/world_quest_policy.c`
  and `.h`, with constants in `world_quest_policy_math.h` where appropriate.
  Wire `world_quest.c/.h` and `specs/specs.mobile.c` to pass the request origin.
  Use movement/map sources as contracts; change those production files only
  for a small justified shared read-only predicate.
- [ ] **3. Select and describe live routine targets (2-3 hours).** Extend boot
  placement metadata and per-request filtering in the same policy module;
  use actual zone/live supply in `createQuestForGiverVnum()` and validated
  entrances in `quest_buy_map()`. Retain boot level/reward calculations and
  fail-closed history behavior. Update the misleading failure message that
  currently tells low-level players to try colleagues around the world.
- [ ] **4. Recover and persist existing work (2-3 hours).** Implement the shared
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
implementation commit `0cafcc82c`. This branch is its head; stack further
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
