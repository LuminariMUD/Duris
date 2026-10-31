# Issue #500: bartender eligibility without travel proof

Status: **ASK ready in PR #520; geography/removal in draft PR #522, final journeys running**. Updated 2026-10-31.

- Work item: [Duris #500](https://github.com/LuminariMUD/Duris/issues/500).
- Branch: [branch/issue-500-geography](https://github.com/LuminariMUD/Duris/tree/branch/issue-500-geography), linked in the issue's Development section and stacked on [PR #520](https://github.com/LuminariMUD/Duris/pull/520).
- Current review: [draft PR #522](https://github.com/LuminariMUD/Duris/pull/522).
- Local worktree: `/home/aiwithapex/projects/duris-worktrees/issue-500-eligibility`.
- Audited source/base: `807c6d8dce8be4102d43c91950c80548a58f7f02`, the current head of [PR #513](https://github.com/LuminariMUD/Duris/pull/513), `branch/issues-500-506-bartender-bugfixes`.
- Method: the repository's [ablation skill](../../.agents/skills/ablation/SKILL.md).

PR #513 is open, so this is a dependent branch. Its procedure/allowance fixes are prerequisites, not new changes belonging to this plan. Review the new diff against #513 while it is open; integrate the prerequisite and current master before final implementation qualification without duplicating or discarding its work. Master advanced during planning from `9ad734e9e` to `aa77a2030`; this plan remains pinned to the inspected #513 head. Keep #500 open until implementation and acceptance are complete. #506 remains tracked by #513; this branch introduces no new allowance work.

The previous shared plan is already preserved byte-for-byte in [plan-issue-420.md](plan-issue-420.md); comparison passed before replacement. The separate [#500/#506 qualification record](plan-issues-500-506.md) remains intact. Its former geography decisions and the issue's archived investigation are historical evidence, not the current task list.

## Outcome

Implement all three decisions in the current issue body:

1. New ASK/KILL assignments at every supported quest level, shares, accepted-task validation and replacement selection do not depend on an outward route, a return route, obstacles, travel capabilities, unknown travel scripts, or route-search budgets. Normal movement rules continue to govern travel.
2. At accepted levels 11–29, eligible targets may belong to either the origin's attached surface region or its connected Underdark map component. Quietus room 1734 and Bloodstone room 74339 must support both. Keep unrelated regions excluded. Level 30 removes this local-region restriction while other zone/target rules still apply.
3. ASK admits otherwise suitable targets with authored and live levels below `MAXLVL` (currently 62), without the KILL band. KILL retains inclusive `[L - 4, L + 5]` checks on both levels. Preserve the strict zone-average window and target-interaction checks.

Update the [bartender reference](../reference/BARTENDER_QUESTS.md), including assignment, maps, sharing, recovery and verification wording. A broader pool does not guarantee selection of a particular NPC or an otherwise eligible target at every player level in every zone.

## Non-goals

- No reward, cost, wallet-publication, daily-allowance, completion-history, sharing-limit, quota, XP or random-selection balance changes. Preserve #513's midnight/abandonment repair.
- Keep the existing level-11 minimum, ASK/KILL purchases at 11–49, KILL-only purchases at 50+, and mapless-zone minimum of 41.
- Keep routine-reset/birthplace provenance, actual destination zone, live supply, speech, visibility, aggression, ASK interception, safe-room KILL restrictions, controlled/summoned exclusions and target history. Route-only checks must not become disguised target restrictions.
- Retain genuine non-route replacement causes, earned progress, accepted level/type/quota, receiver, start time, purchased-map entitlement and legacy origin/replacement persistence. Do not resurrect already persisted replacement entitlements: saved state does not identify whether a past route rejection caused them.
- No movement changes, script/transport execution, travel abilities granted to players, schema migration, content balancing, new runtime configuration, general graph service, production operation, deployment or full burn-in.

## Source findings

These findings come from the checked-out source, not from accepting the issue's diagnosis. Line references describe the pinned baseline.

1. **Route gating is active in several paths.** In [world_quest_policy.c](../../src/world/world_quest_policy.c), `quest_target_request` (944–1019) builds routes before indexing candidates. Empty/exhausted routes prevent selection; `common()` requires `reachable()` for reset and live rooms. `world_quest_policy_check_target()` (1161–1278) uses current/capable/potential route passes for accepted work. A missing return can produce `unavailable`, not just temporary refusal.

2. **Geography itself applies travel rules.** `quest_route_builder::region()` (368–435) calls `connection()`, excluding locks, walls, castle/map barriers and terrain. It stores one integer; mixed surface/Underdark boundaries resolve to zero. Underdark membership currently requires a directed return. Merely bypassing the final route verdict leaves hidden route dependencies.

3. **Named origins exist, but unrestricted flooding is unsafe.** [specs.assign.c](../../src/specs/specs.assign.c) binds giver 1709 and Cerrio 74060. [quietus.zon](../../areas/zon/quietus.zon) places 1709 at 1734; [bs.zon](../../areas/zon/bs.zon) places 74060 at 74339. A read-only parser of AREA-listed authored files, using zone top intervals and `ZONE_MAP`, found Quietus boundaries 635755/636555 and 850045. Bloodstone has direct surface boundaries and adjacent interiors including mountaintracks; unrestricted interior traversal expands through 5,165 rooms and many map boundaries. Simply deleting obstacle filters from that flood is not a justified locality rule. The previous loaded-world record identifies local Bloodstone anchors including 602263/598665 and 813720; requalify their membership under the new topology. The authored parser is not a server boot or proof of eligible targets.

4. **Existing map helpers have narrower meanings.** `IS_MAP_ROOM()` in [map.h](../../src/world/map.h) uses `ZONE_MAP`, not just surface/Underdark VNUM ranges. `assign_continents()` in [map.c](../../src/world/map.c) supplies surface identities. `calculate_map_coordinates()` combines interiors/maps and filters reciprocal exits/ocean; `map_section` is not an independent Underdark-component identifier. `get_map_room()` in [world_quest.c](../../src/world/world_quest.c):387 returns the first direct zone map exit. It can provide a cached hint but cannot represent BOTH memberships or resolve every interior origin.

5. **ASK is filtered before quest type selection.** `ordinary_instance()` (991–1005) applies authored and live `[L - 4, L + 5]` checks. Changing only the ASK branch cannot recover those candidates. `world_type_eligible()` separately checks the ASK prototype against `MAXLVL`; an explicit live cutoff is needed when the shared band goes away. `static_zone_eligibility()` (927–942) retains the truncated zone average, reward pool and mapless threshold. [world_quest_policy_math.h](../../src/world/world_quest_policy_math.h) defines the strict `(L - 7, L + 5)` zone window; [config.h](../../src/core/config.h):114 defines `MAXLVL` as 62.

6. **Commands and maps consume the same policy.** `do_quest()` in world_quest.c:654 checks the sharing recipient through the accepted-target API. `world_quest_refresh()` at 795 converts `unavailable` into a saved replacement entitlement. Map hints come from the route context. [specs.mobile.c](../../src/specs/specs.mobile.c):10854 says local tasks require ordinary travel; world_quest.c also has travel-specific status/share wording. Map payment revalidates the target and must retain its non-route protection.

7. **The route counter also bounds non-route work.** `quest_spend_work()` charges live-character scans, visibility/lighting and shop lookup as well as traversal. Remove route budgets/dependencies, but retain clearly named bounded target checks and the existing 32 target-probe/32 history-check limits. Target/history exhaustion retains its conservative meaning and must not become a route verdict.

8. **Existing tests encode the superseded policy.** [world_quest_routes_harness.cpp](../../tests/async/world_quest_routes_harness.cpp) expects obstacles, missing returns and mixed regions to refuse. [world_quest_live_targets_harness.cpp](../../tests/async/world_quest_live_targets_harness.cpp):890–1011 expects locks, lost flight, scripts and oversized graphs to block accepted work; sharing/map-payment cases also depend on routes. [run_world_quest_dual_backend.py](../../tests/async/run_world_quest_dual_backend.py):600–608 expects the named level-29 refusals. [world_quest_journey_probe.cpp](../../tests/async/world_quest_journey_probe.cpp) exposes the route graph for test navigation. Removing only production callers would leave qualification broken or misleading.

## Files and implementation sequence

### 1. Establish geographic membership and failing cases

Use existing harnesses and the disposable loaded-world probe to establish the actual surface identity and independent Underdark component attached to both named givers, including Bloodstone's connector zones. Record positive and negative room/zone fixtures before finalizing the attachment traversal.

The representation must satisfy all of the following:

- Reuse loaded world/zone metadata and existing surface continent identities. Compute Underdark components from authored map-to-map adjacency, independent of locks, terrain, procedures and player facts. Connectivity is geographical, not an outward/return proof; a one-way link cannot alone disqualify a target. Never merge Underdark components through interior zones, surface travel, scripts or transports.
- Represent surface and Underdark membership separately and accept their union. Multiple entrances into one region are one membership. Having one of each is not a conflict.
- Resolve attachments at map boundaries, using local connector relationships justified by the loaded-world audit. Zone membership must cover disconnected reset/live rooms within the same authored zone; neither room needs an ordinary-exit path to the giver. Do not cross a map region to discover additional origin regions or union arbitrary remote interior networks.
- Unknown geography is not permission for remote targets below 30. Genuine geographic uncertainty may remain conservative, but scripts, locks and route budgets must not create it; both named origins must resolve. Raw room flooding and first-exit selection are inadequate. If loaded metadata cannot express a demonstrated local attachment unambiguously, use the smallest explicit quest-local attachment data for that origin rather than a general resolver, broad fallback or new configuration.
- Prefer stable topology/attachment data in the existing boot catalog after map setup. Do not scan the entire world per request or cache player-dependent routes. Keep the implementation in the policy owner. At 30+, bypass local membership only.

Extend the existing route harness into geographic coverage and the live-target harness into assignment/command coverage. Add cases that fail on the baseline for all three decisions, including remote-region negative controls. Reuse filenames and runners unless a rename is actually necessary.

### 2. Replace route proof in the shared policy

Expected production files: [world_quest_policy.c](../../src/world/world_quest_policy.c), [world_quest_policy.h](../../src/world/world_quest_policy.h), [world_quest_policy_math.h](../../src/world/world_quest_policy_math.h).

- Remove `quest_route_builder`, current/capable/potential passes, reverse-return graphs and public route-only APIs after updating all consumers. Remove obsolete movement/trap/barrier includes, stubs and route limits. Do not retain an always-true route wrapper or compatibility switch.
- Separate ordinary-instance checks from type-level rules. Put authored/live KILL bands in the KILL path and authored/live `< MAXLVL` in ASK. Retain remaining interaction checks, including #513's passive Bloodstone ASK handlers.
- Use the same geography for selection, validation, sharing and replacement, preserving accepted level/origin. Keep legacy origin-zero binding and invalid-origin handling; describe origin as scope provenance instead of travel proof.
- Classify accepted targets once for actual supply/interaction. Retain `valid`, `blocked`, `unproven`, `needs_origin` and `unavailable` for their surviving non-route meanings. Preserve blindness, silence, aggression and handler uncertainty.
- Retain closed/private destination zones and restricted final-room exclusions currently supplied by `ordinary_space()` where they protect target eligibility. Move only those restrictions into the target check; do not copy terrain, transit-room restrictions, player capabilities or unknown travel procedures. ASK's underwater/silence checks are interaction constraints and stay; lack of travel gear must not disqualify KILL.
- Supply map hints independently from known geographic entrances for the target's actual zone, consistent with local scope. Reuse cached `get_map_room()` when suitable; select a deterministic attached entrance when needed. Hints identify a place, not a proved route. A genuinely mapless target remains valid under the existing 41+ rule without a purchasable hint.
- Retain bounded target/history work under accurate names, with no graph requirement. Old route size/work limits become irrelevant.

### 3. Integrate commands without changing unrelated state behavior

Expected additional production edits: small wording/comment changes in [world_quest.c](../../src/world/world_quest.c) and [specs.mobile.c](../../src/specs/specs.mobile.c), plus only integration changes demonstrated necessary by the shared policy.

Exercise real `world_quest()` requests, `do_quest()` sharing, `world_quest_refresh()`, map-payment continuations and `world_quest_replace()`. Remove travel-specific refusal wording. Preserve payment ordering, genuine-failure refunds, remaining-kill supply, free replacement, dirty marking and GMCP cache behavior.

A route change after acceptance, during sharing or during map payment must not block/invalidate work, clear its geographic hint, grant replacement, alter progress or cause a route-only refund. Genuine target/supply/location failures must retain their behavior. Keep serialized fields and GMCP status values; no schema or client protocol change is needed.

### 4. Update tests and the reference

Expected test changes:

- [test_world_quest_routes.py](../../tests/async/test_world_quest_routes.py) and its harness: replace route-proof assertions with geography/non-mutation assertions; remove unused movement predicate extraction.
- [test_world_quest_target_retries.py](../../tests/async/test_world_quest_target_retries.py) and the live-target harness: add type-level coverage and new refresh/share/map expectations; retain history/probe/payment controls.
- [world_quest_journey_probe.cpp](../../tests/async/world_quest_journey_probe.cpp) and [run_world_quest_dual_backend.py](../../tests/async/run_world_quest_dual_backend.py): remove qualification dependencies on the deleted route API. Navigation is test tooling for deliberately walkable fixtures, not an eligibility oracle. Select controlled targets for real ASK/KILL completion. Test special-travel assignments/status separately without requiring the runner to walk them. Preserve recovery/history coverage.
- Update [test_world_quest_dynamic_policy.py](../../tests/async/test_world_quest_dynamic_policy.py) only for changed contracts and any concrete references found by a repository-wide symbol search. Change registration only if an entry point changes.

Update BARTENDER_QUESTS.md's source map, live targets, geographic policy, bounds, recovery, map/share wording and verification examples. Explain both local regions, level 30, independent ASK cutoff, preserved zone window and normal movement. Remove claims about route proof, gear-based eligibility and local mixed-region refusal. Record final evidence/limitations in this plan.

## Proof and acceptance

1. **No travel gating:** otherwise eligible ASK/KILL at 11, 29, 30 and a high supported level accept locked/secret/blocked/walled exits, missing returns, no ordinary path, unknown transit scripts, transport-only access, traps/barriers and flight/boat/waterbreathing requirements. Check both reset and live rooms. Keep ASK destination speech restrictions as negative controls. For high-level ASK use accepted/shared-target validation; retain KILL-only new purchases at 50+. A graph larger than the old route bounds cannot refuse an eligible target.
2. **Both local regions:** for each named origin and levels 11/29, cover ASK/KILL in attached surface and Underdark regions. Use controlled eligible zone averages/rewards to isolate geography; report actual loaded-world grants separately. Reject another surface continent/disconnected Underdark component. Interior bridges must not merge components. Cover multiple/mixed entrances, disconnected rooms within a zone, one-way topology and player travel after acceptance. At 30, remote geography alone cannot refuse.
3. **ASK and KILL levels:** vary authored/live values independently below `L - 4`, above `L + 5`, at 61, 62 and above. Keep zone means eligible so they do not obscure the type test. ASK accepts out-of-band levels below 62 and refuses either level at 62; KILL retains exact endpoints and adjacent rejections. Preserve strict zone-average boundaries `L - 7`/`L + 5` and positive cases just inside. Keep interaction, provenance and history negative controls.
4. **Refresh/sharing/maps:** run real refresh, sharing with fixture sharing enabled, map purchase and replacement selection after each route-change class. Verify accepted fields, partial progress, wallet/history, shares, replacement flag, paid-map entitlement and Quest.Status/Quest.Map. Missing targets, inadequate supply and true interaction failures remain meaningful controls. Saved level 29 stays local after the player reaches 30. Preserve legacy origin binding and previously persisted replacement entitlements.
5. **Commands/persistence:** update named-giver `reported` cases and deterministic surface/Underdark/broad-ASK fixtures. Run disposable flatfile and MariaDB journeys, refresh/share/map state across relog/restart and real ASK/KILL completion on walkable fixtures. Inspect saved and live state; restart must not reintroduce route blocking or lose progress. Keep genuine no-candidate/replacement and history-rollover controls. Random sampling of one region cannot establish both-region coverage.
6. **Read-only checks and bounded work:** policy must not move actors, execute scripts, consume keys/traps, change equipment/affects, probe prototypes during requests or mutate assignment state before publication. Retain non-mutation assertions and target/history bounds. Confirm obsolete route symbols have no remaining consumer or substitute route requirement.

Planned commands after implementation, from the worktree:

```sh
python3 tests/async/test_world_quest_routes.py
python3 tests/async/test_world_quest_target_retries.py
python3 tests/async/test_world_quest_dynamic_policy.py
python3 tests/async/test_world_quest_reward_policy.py
python3 tests/async/test_world_quest_failure_feedback.py
python3 tests/async/test_world_quest_remaining_unloaded.py
make -C src
DURIS_WORLD_QUEST_BACKEND=both DURIS_WORLD_QUEST_JOURNEY=reported python3 tests/async/run_world_quest_dual_backend.py
DURIS_WORLD_QUEST_BACKEND=both DURIS_WORLD_QUEST_JOURNEY=both python3 tests/async/run_world_quest_dual_backend.py
./scripts/format.sh --check
python3 tests/async/test_documentation_contract.py
git diff --check
```

Integrate new deterministic cases into these existing selections. Use fresh binaries from existing runner helpers. Confirm local/dev environment before gameplay tests; use disposable accounts/databases/state roots and artifacts under `bin/`. The target suite includes SQL-history cases; run the separate history journey only if a change disturbs that integration. Do not wait for hosted CI. Record failed/skipped checks distinctly; helper tests do not replace command/persistence proof.

## Ablation decisions

- **Keep:** one eligibility owner, geographic data needed by low-level selection/validation, independent ASK/KILL rules, target-interaction classification, map hints and focused command/persistence proof. Each serves a requirement or traced consumer.
- **Simplify:** three capability-dependent route passes become geography plus one target check. Reuse the boot catalog, surface identities, current status/persistence machinery and harnesses.
- **Drop:** movement-procedure allowlist expansion, permissive route fallbacks, ferry/teleport discovery, general graph infrastructure, configurable legacy/new modes, reward/history changes and unrelated cleanup.
- **Investigate first:** the exact Bloodstone attachment boundary without obstacle filters. The authored audit shows why unrestricted traversal is not a safe substitution. Completion requires positive/negative loaded-world membership evidence, not an assumed region or an unresolved product decision.

## Planning evidence and implementation estimate

Completed at the pinned baseline, before source edits:

- `python3 tests/async/test_world_quest_dynamic_policy.py`: passed.
- `python3 tests/async/test_world_quest_target_retries.py`: all 72 live-target/creation/payment scenarios and 10 SQL-history scenarios passed under the existing ASan/UBSan harness. These establish old behavior/compatibility, not the requested new rules.
- `cmp docs/ongoing-projects/plan.md docs/ongoing-projects/plan-issue-420.md`: matched before replacement.
- Source/caller/test review and read-only authored geography audits described above. No new server build, booted-world reproduction, production observation or implementation acceptance is claimed.

Planning validation: `python3 tests/async/test_documentation_contract.py` passed all 14 tests; `git diff --check` passed. The diff changes only this plan, and `gh issue develop 500 --list` confirms its Development branch link. Commit/push and verify matching local/remote heads, then publish the committed plan link without closing #500.

Estimate for **me to implement and locally qualify: 4–6 hours of active work**:

- 45–75 minutes: loaded geography confirmation and failing fixtures.
- 75–105 minutes: policy removal, level split, map/command integration and focused regressions.
- 60–90 minutes: journey/probe changes and disposable backend runs.
- 30–60 minutes: reference updates, builds, final review and commits.

Allow up to **8 hours** if Bloodstone's attachment data or navigation-fixture separation needs additional work. This includes implementation and local validation, not just editing the selector. It excludes prerequisite merge/review waiting, deployment and production qualification.

## Implementation evidence: ASK target levels

The first chunk moves the authored/live level band from the shared ordinary-instance
filter into KILL eligibility. ASK now checks both levels against `MAXLVL`, leaving
zone eligibility and interaction checks in place. The reference describes this
implemented rule; its route/geography sections await the next chunk.

The extended native fixture first failed against the old source for a level-11
ASK with authored target level 6 and live level 11. After the production change,
all **184** live-target/creation/payment scenarios passed under ASan/UBSan,
including 112 new authored/live level cases at accepted levels 11/29/30/49.
Both the selector and accepted-target API are exercised with forced quest type;
the destination zone average remains fixed while each target level varies.
All 10 SQL-history cases also passed.

Additional checks passed: `make -C src -j8`, dynamic policy contracts, XP feedback
(MariaDB and flatfile), reward policy, 14 documentation checks, formatting and
`git diff --check`. These results qualify the level chunk only; route removal,
dual-region geography and the planned command/persistence journeys remain open.
Current master `aa77a2030` was merged for build/compatibility qualification.

## Implementation evidence: route removal and both regions (in progress)

The second chunk replaces the route builder and all three capability passes
with boot-time geography and one accepted-target interaction/supply check.
The production route API and route limits are removed. Target-check bounds,
actual restricted destination/reset rooms, provenance and ASK interaction rules
remain. Maps use geographic zone entrances; travel changes no longer clear
them or invalidate a task. Refusal messages now describe target/scope state.

The attachment decision is now concrete: gather authored map boundaries and
interior-zone adjacency, then resolve the nearest boundary **separately for
surface and Underdark**. The map-only Underdark graph uses undirected
connectivity, ignoring movement flags; interior connectors cannot merge map
components. Ties between different identities remain unresolved for that family.
This avoids flooding all 5,165 connected Bloodstone interior rooms and requires
no special-case origin table, new configuration or travel simulation.

The disposable **flatfile loaded-world audit passed**. Both 1734 and 74339
resolve to surface region 2 and Underdark component 239868 in that boot's rnums.
Both Good and Evil observers received eligible tasks at 11/29/30 from both
origins. Component rnums are process-local evidence, not persisted identifiers.
The geometry harness passes mixed/nearest boundaries, incoming/one-way edges,
disconnected rooms, unrelated surface/Underdark rejection, ambiguity, unchanged
world memory and a graph larger than the old route limit.

The expanded native suite passed **284** scenarios and 10 SQL-history cases,
including the final terrain-fixture addition. It covers named-origin synthetic
ASK/KILL geography at 11/29/30/56, broad ASK and KILL levels at 11/29/30/49/56,
strict zone-average endpoints, refresh/sharing/map-payment route immunity and
genuine target invalidation. The old distribution-room fixture is now explicitly
private: its rejection proves location policy rather than a missing path.
The journey probe now has its own ordinary-exit navigation helper; assignment
is independent of whether that test helper can walk the target.

`make -C src -j8`, dynamic/reward/failure/remaining contracts, geography,
formatting, whitespace and 14 documentation checks passed. The first `reported`
and `both` journey runs failed in their ordinary-exit navigator after accepting
valid broader-pool targets: one walked into a map barrier, and one could not
reach remaining targets after restart. This did not justify restoring route
eligibility. The test navigator now uses the actual read-only map-barrier
predicate, and gameplay sampling explicitly chooses otherwise eligible fixtures
with ordinary outward/return paths for their routine instances and birthplaces.
Debugger hooks select that zone/prototype; production validation, publication,
payments, movement, ASK/KILL, reward and persistence still execute normally.
Special-travel acceptance is independently covered by native fixtures.

The reported suite also enables sharing only in its disposable properties copy,
then exercises actual CONSENT, QUEST SHARE and paid MAP with the giver's exits
locked. It saves/restarts both source and recipient and compares copied work,
paid map, purse, allowance and remaining shares. Fresh `reported` and `both`
runs on both backends are underway; completion still requires their results.

The next journey attempts exposed two further fixture defects: snapshots could
observe a partially processed movement batch, and the newly created sharing
recipient had not equipped its visibility gear. Navigation now synchronizes
every movement/preparation command through its prompt, and score observations
use tagged requests plus their response/prompt. The recipient uses normal
`wear all` before consenting. The ASK completion sampler now specifically
selects an eligible target outside the KILL band and records its live level;
a focused 11/29 ASK journey on both backends supplements the full matrix.
These are test changes, not production travel restrictions. All current journey
results remain pending; draft #522 must not be marked ready before they pass.

Further qualification isolated stale queued score observations: snapshots now
carry a unique request identifier, and the reader accepts only its own response.
The broad ASK run completed its level-11 case. Its first level-29 fixture used
a safe room, where existing reward rules legitimately suppress XP; completion
fixtures now avoid safe/arena/guild locations when proving positive XP. No
reward rule changed. Fresh full, reported and focused ASK runs are in progress;
the required final result is still both backends passing every planned journey.
Baseline, native and failed-journey logs are retained locally under
`bin/qualification/issue500/` and are not tracked.

The walker now observes each authored destination before submitting the next
movement command, with a bounded wait and an exact room assertion. A prompt or
batch-end score alone did not establish that every requested step had finished.
The runner also freezes its probe source at startup so editing the checkout
cannot mix probe signatures between its MariaDB and flatfile passes. A prior
intermediate run's flatfile debugger stopped on that signature mismatch; this
was not a server crash. Final `both` and `reported` runs use the corrected
step synchronization. No production change was needed for these harness fixes.

Exact step observation then identified the remaining concrete navigation error:
the simplified walker admitted ocean sectors (for example 556132 -> 555732),
which ordinary movement rejects. The walker now conservatively excludes ocean
and hazardous planar terrain, as appropriate for its completion fixtures only.
Production eligibility remains independent of these travel checks. Superseded
reported runs were interrupted with normal cleanup; the corrected full/reported
pair is the remaining completion gate.

Ablation after that diagnosis removes the temporary per-step polling: the
failure was an inadmissible ocean edge in test navigation, not evidence for a
new movement-publication protocol. The final walker retains ordered batches,
unique score request IDs, response/prompt synchronization and an exact end-room
assertion (or a checked combat interruption). The stricter reported run already
in flight may finish with per-step assertions; the final full run qualifies the
batched reader on both backends. No eligibility or acceptance requirement is
weakened by removing the diagnostic polling.

The full matrix next reached a genuine scripted movement gate on its chosen
level-29 ASK fixture. Its navigator now rejects opaque room/mobile/object
movement handlers and room affects when selecting ordinary completion fixtures,
reusing the production Bloodstone passive-handler predicate through the existing
debugger mechanism rather than copying that allowlist. This test-only screening
does not restore travel gating to production. The new full run is in progress.

**Reported-giver qualification passed on both backends.** For each backend the
result includes all 10 Good/Evil named-giver grant cases, six saved/restarted
abandon/regrant sequences, actual consent/share/map with locked giver exits and
both players' retained state after restart, progressed-abandon history, legacy
origin binding, durable free replacement, and Bloodstone level-30 ASK/KILL
completion and ordinary return travel. The recipient restores an active level-29
task from origin 1734, paid map, original receiver and no onward shares.
Evidence: `bin/qualification/issue500/reported-passed.json` (ignored).
The reported run used stricter per-step movement observation; the final full
matrix still must qualify the simplified batched walker and 11/29 cases.
