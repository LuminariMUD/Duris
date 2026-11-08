# Issue 752 movement restriction investigation

**Five active movement routes can cross a closed, locked, pickproof door that ordinary walking refuses.** Four test the displaced character's `AFF2_PASSDOOR`; lance charge tests the charger and can carry a victim without that effect. Native execution of the actual handler bodies reproduced all five routes.

Investigated November 8, 2026 against fetched `origin/master` commit
`dd31e9f2def81483d7200a146d2e8828040f7da9`.
Tracking issue: [752](https://github.com/LuminariMUD/Duris/issues/752).
[Plain English explanation](issue-752-plain-english.md).

The findings below describe the original source snapshot. [PR 850](https://github.com/LuminariMUD/Duris/pull/850) implements the follow-up fix; it has not been deployed. No production operation or player-data access was needed.

The fix routes all five displacements through the existing forced-movement subsystem. Mounted lance ram validates the charger, victim and mount before departure and after leave hooks, preserves the charger's riding link during arrival hooks, and separates the victim from their own riding companion. Walking checks every riding participant before and after all departure hooks, covering lance approach and missed-charge continuation. Recovery preserves scripted redirects and dismounts. The existing removal-generation guard avoids full character-list scans on normal walking. Lance charge revalidates participants and the equipped lance after its approach and arrival hooks, and does not reference a lance scrapped by wear. Source identity checks protect post-movement work, and guardian death bursts retain their dead, still-registered source.

Verification includes 373 ASan/UBSan actual-handler and walking-departure scenarios, 50 walking permission cases, existing combat regressions and a disposable socket-game Squall/walking journey. Restoring each of the three adversarial-review defects independently makes the native regression fail. Normal walking also checks that no identity lookup scans the character list unless a departure hook removed someone. The full safe gate at implementation commit `b64c49a67` passed 1,002 of 1,003 regressions: the unchanged Divine Boon journey timed out during PvP finishing blows, then passed unchanged in isolation against the same verified server binary. Latest integration results are recorded on PR 850.

## Door rules and root cause

[`CAN_GO`](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/core/utils.h#L651-L660) requires an existing exit with a destination, rejects `EX_SECRET` and `EX_BLOCKED`, and checks castle walls. For a closed door it only asks whether the character has `AFF2_PASSDOOR`. It does not inspect `EX_LOCKED` or `EX_PICKPROOF`.

[Ordinary walking](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/cmd/actmove.c#L1389-L1420) permits a mortal through a closed door only with passdoor and `(!locked || !pickproof)`. Thus **closed AND locked AND pickproof** blocks a mortal even with passdoor. A trusted immortal has an explicit exception. Locked alone and pickproof alone do not defeat passdoor. An open door is outside this particular check.

`VIRTUAL_CAN_GO` has no character parameter and rejects closed doors outright. It does not have the passdoor loophole.

The affected handlers choose a direction with `CAN_GO`, often also `check_wall`, then use `char_from_room` and `char_to_room` directly. They skip the walking door gate. [`char_to_room`](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/world/handler.c#L1406-L1528) places a character and runs entry effects; it does not validate the door just crossed. Its `dir = -1` argument is not an authorization check.

Passdoor is an attainable state: [ethereal form](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/classes/ethermancer.c#L1410-L1440) and [shadow projection](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/magic/magic.c#L10399-L10430) explicitly grant it. The audit did not measure how often players combine this state with the affected abilities near protected doors.

## Five reproduced movement routes

- **Squall (Tempest handler)**, `spell_single_tempest`, [ethermancer.c:2441](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/classes/ethermancer.c#L2441-L2466). After nonlethal spell damage, a successful takedown roll chooses a direction. The victim's passdoor allows the protected exit; the handler relocates the victim directly. The public `spell_tempest` dispatches this callback through area damage.
- **Nexus guardian energy burst**, [nexus_stones.c:883](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/economy/nexus_stones.c#L883-L948). An eligible target that fails the agility dodge is thrown in a random direction. The victim's passdoor admits the protected exit. Active callers exist at lines 975 and 1076.
- **Conjured golem throw**, [specs.mobile.c:13297](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/specs/specs.mobile.c#L13297-L13358). While fighting, its periodic combat branch can throw a target of size small or less. The victim's passdoor admits the protected exit. The special is assigned to mobile 1121 in `specs.assign.c:1199`.
- **Judgement**, `spell_oldjudgement`, [magic.c:23442](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/magic/magic.c#L23442-L23498). Its eligible evil target can fail the fear save and be thrown through the protected exit with passdoor. Despite the function's name, it is active: `event_judgement` calls it at line 23588, and `spell_judgement` schedules that event at line 23888. The test isolated the door displacement from subsequent astral banishment.
- **Lance charge ram**, [actoff.c:1160](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/cmd/actoff.c#L1159-L1195) and [case 3](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/cmd/actoff.c#L1330-L1369). Exit selection uses the charger's `CAN_GO` and `can_enter_room`. The ram directly relocates the victim and charger. With passdoor on the charger and none on the victim, both crossed the protected door in the harness. This also carries a victim without passdoor through an ordinary closed door when the charger has passdoor. The initial ranged approach and the missed-charge continuation use `do_simple_move`; those portions retain the walking door gate.

The golem throw and nexus burst can impose this movement on a player; the bug is not limited to the player choosing to use a travel ability. A room-access shortcut, separation from a group, or inability to walk back through the door is a plausible consequence. None is asserted as a recorded production incident.

## Complete caller classification

Comment-stripped source contains **30 `CAN_GO` call sites and 6 `VIRTUAL_CAN_GO` call sites**, excluding the macro definitions. The commented missile-barrage knockback at `magic.c:4605` is not active code. The references below use the pinned source line numbers above.

### Direct movement requiring the door restriction

Seven call sites belong to the five routes described above: Tempest 2446; nexus burst 912; golem throw 13329; Judgement 23447; lance charge 1160, 1169 and 1184. These are the confirmed bypass candidates for implementation.

### Movement that reaches the normal walking gate

Fourteen call sites select candidates before standard movement. Their permissive preliminary check can choose a route that later fails, but does not by itself bypass the door restriction:

- `actmove.c:2101,2361`: Delirium follower command selection and movement direction selection. Commands/`do_simple_move` ultimately revalidate movement.
- `actoff.c:2975`: flee exit selection; successful attempts call `do_simple_move` at 3088. Counting an ultimately blocked exit can still affect escape selection and the calculated flee chance.
- `interp.c:1976` and `handler.c:1774`: water currents call `do_move`.
- `kingdom_guards.c:1288`: patrol calls `do_move`.
- `mobact.c:7974,8184,10499`: assist, wander, and aggression movement call `do_move`.
- `specs.mobile.c:9950,10089,10113,10142`: patrol selection ends in `do_move`.
- `specs.winterhaven.c:1714`: janitor moving toward rubbish calls `do_move`.

These routes were source-traced. They were not individually exercised through live commands during this investigation. Consider stricter candidate selection as a separate follow-up if failed route choices are disruptive; a global `CAN_GO` change would affect more than these routes.

### Inspection and planning rather than relocation

Eight `CAN_GO` sites do not directly transfer a character:

- `actinf.c:10037`: `do_scan`, adjacent visibility.
- `actoth.c:3295`: `do_listen`, also using its separate behind-door listening rule.
- `range.c:1729,1823`: `range_scan` and `range_scan_track`. They temporarily use `ch->in_room` as a search cursor and restore it; they do not unlink/reinsert the actor into rooms.
- `mobact.c:588`: `In_Adjacent_Room`, an adjacency query.
- `mobact.c:8444,8464`: `MobCanGo`, a movement planning predicate for an NPC and its followers.
- `actmove.c:1687`: deceptive flee departure messages, not the direction actually traversed.

Do not automatically give these callers all walking permissions or restrictions. What a character can hear, see, or plan is a separate design question from what can physically move through a doorway.

### Falling and effects using virtual exits

- `falling.c:149` uses `VIRTUAL_CAN_GO` for fall eligibility; line 188 uses `CAN_GO` before scheduling. The actual `falling_step` independently requires an open downward exit at lines 220-228. A closed protected door therefore does not become a traversable fall merely because the initial check sees passdoor. Changes to falling's startup, reprieve, or room-sector repair behavior need separate consideration.
- Five other virtual-exit uses carry effects rather than characters: `fight.c:2315,2355` propagate death sounds; `mobact.c:4909,4927` trace breath effects; `specs.highway.c:551` spreads fire. They reject closed exits and do not have this passdoor mismatch.

This accounts for all 36 active sites: 7 direct movement, 14 normal movement selection, 8 inspection/planning/messages, 2 falling startup checks, and 5 effect-propagation checks.

## zcheck agrees with walking

The [header comment](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/world/zcheck.c#L45-L50) explicitly says passdoor fails when a closed door is locked **and** pickproof. That agrees with walking. Its locked-door audit first skips states below locked at line 783, then sets `pass_ok = !pickproof` at line 796. Within that locked-door model this is also correct.

The reported comment disagreement was not reproduced on this master snapshot. The comment's old line-number references are stale. Its description of an "unwinnable" door should be read as a conclusion about the modeled opening methods, not proof that every special movement handler respects the barrier. Any comment edit should clarify that scope; it should not claim that walking allows passdoor through locked pickproof doors.

## Executable evidence and its limits

A disposable C++ harness used the repository's real headers and unmodified full function bodies extracted with the existing `tests/async/_paths.py` helper. It executed all five handlers above with deterministic combat rolls and a two-room world. It used ASan and UBSan. There were **45 handler scenarios**, nine per handler:

- Closed, locked, pickproof with passdoor: displaced character crossed. For lance charge, passdoor was only on the charger; the victim also crossed.
- The same sealed door without passdoor: no placement.
- Open exit without passdoor: placement.
- Closed locked pickable door with passdoor: placement.
- Closed unlocked pickproof door with passdoor: placement.
- Secret exit, blocked exit, castle wall, or spell wall: no placement in each of those four controls.

Castle/spell wall checks were controlled fixture callbacks. Damage, saves, skill success, messaging, lag, and room placement were also controlled; Judgement's later astral banishment was suppressed to isolate displacement. The golem's unrelated follow-on bearhug was refused. The harness shows the real ability branches reach room placement through the protected exit. It is not a booted-server test of entry/leave procs, mounts, death, or persistence.

A second disposable harness extended `test_water_shoreline_runtime.py`'s production movement dispatcher and core prefix. The retained prefix includes the actual closed-door gate, entry checks, traps, exhaustion and cost calculation; final room placement remains a fixture. Eight door cases produced the ordinary walking results described above. The decisive comparison was:

```text
walking       closed locked pickproof/passdoor  CAN_GO=1 moved=0 room=0
Tempest       closed locked pickproof/passdoor  victim=1 actor=0
Nexus burst   closed locked pickproof/passdoor  victim=1 actor=0
Judgement     closed locked pickproof/passdoor  victim=1 actor=0
Golem throw   closed locked pickproof/passdoor  victim=1 actor=0
Lance ram     closed locked pickproof/passdoor  victim=1 actor=1
```

The original water shoreline runtime regression also passed. Neither investigation harness reported a sanitizer error. Scratch sources, binaries and logs are ignored files under `bin/issue-752/` in the investigation worktree; no generated artifact belongs in the change.

To reproduce in a disposable local game, create two otherwise ordinary dry rooms joined by a visible, unblocked door with `EX_ISDOOR | EX_CLOSED | EX_LOCKED | EX_PICKPROOF`, and no castle/spell wall. Use a mortal with passdoor; verify walking fails, then trigger each displacement until its selected direction points through the door. For lance charge, target someone in the same room, give only the charger passdoor, and trigger the ram outcome. Use suitable alignment/failed saves for Judgement and a small target for the golem. Confirm both the destination room and the ability messages. Repeat after a fix with an ordinary closed pickable door and with each participant lacking passdoor.

No live-server incident frequency, affected zone count, deployed binary revision, or actual player journey was established here.

## Recommended implementation scope

Keep `CAN_GO` and `VIRTUAL_CAN_GO` unchanged for this fix. Enforce physical doorway permissions at the five actual displacement routes, with focused regression coverage for each. Continue to allow passdoor through closed doors that are not simultaneously locked and pickproof.

[`move_forced`](https://github.com/LuminariMUD/Duris/blob/dd31e9f2def81483d7200a146d2e8828040f7da9/src/combat/forced_movement.c#L39-L74) already models the walking passdoor restriction and other physical barriers. Kick, rearkick and tackle already use this movement subsystem. Reuse the existing single-target executor for the four single-target routes where its contract fits, while preserving their damage, failure outcomes and messages.

Lance charge requires an explicit decision for the charger, victim, and mount. At minimum, every person actually moved must meet the closed-door rule. Do not blindly substitute `move_forced_pair`: it contains a tackle-specific ocean prohibition and separates riders from mounts, which may not match mounted charge. Decide those behaviors before adapting it; do not introduce a second generic movement framework.

Use the existing physical-displacement rule as the default. If any ability is intentionally supposed to ignore protected doors, record that as a named ability exception with player-facing documentation and a regression, rather than relying on the permissive macro accidentally.

For implementation acceptance, exercise all five routes plus normal walking, with passdoor on neither/each participant, open and each closed-door combination, secret/blocked exits, castle/spell walls, private-room capacity, and proc-triggered relocation or removal. Pair movement must not leave only one participant relocated after a refusal. Preserve charge's mount handling and the existing ordinary-movement behavior of flee and currents. Confirm at least one full local gameplay journey in addition to native handler tests.

## Validation status

- Source audit and focused investigation: complete for the pinned snapshot.
- Native ability reproduction: 45 scenarios completed under ASan/UBSan.
- Native walking comparison: 8 door scenarios completed under ASan/UBSan.
- Existing `test_water_shoreline_runtime.py`: passed.
- Repository safe gate `make test-all`: passed, including development/production builds, all 1,001 regressions (zero failures/timeouts/signals), and the native signal-handler check. The regression phase took 1,028.89 seconds. Existing combat edge cases, controlled flee, falling, and water shoreline runtime suites passed.
- Runtime fix, deployment, and full ability journeys in a running game: follow-up work.
