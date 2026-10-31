# Bartender world quests

Bartender quests are generated, paid ASK/KILL assignments handled by the
`world_quest` NPC procedure. This is the standalone reference for their player
commands, selection policy, rewards, recovery, persistence, configuration, and
validation, updated for issue #500 on 2026-10-31. The
configuration values describe this checkout, not a verified production runtime.

Each character has its own assignment and completion history. These are separate
from static `.qst` quests, XML instances, zone-story tracking/dailies, and epic
tasks. The [quest-system overview](QUEST_SYSTEMS.md) explains those boundaries.
A bartender quest may award epic points and thereby trigger ordinary epic task
assignment; it does not add a zone-story catalog completion.

Use [Player flow](#player-flow) for commands, [Rewards](#rewards) for the payout,
[Recovery, maps, and sharing](#recovery-maps-and-sharing) for an existing task,
and [Verification](#verification) for executable checks.

## Source map

- [specs.mobile.c](../../src/specs/specs.mobile.c): `world_quest()` handles NPC
  requests, fees, map purchases, abandonment, legacy claims, and replacement.
- [world_quest.c](../../src/world/world_quest.c): assignment state, completion,
  sharing, rewards, availability refresh, and map/status rendering.
- [specs.assign.c](../../src/specs/specs.assign.c): NPCs assigned the
  `world_quest` procedure. An NPC's name or occupation alone does not make it a
  quest giver.
- [world_quest_policy.c](../../src/world/world_quest_policy.c) and
  [world_quest_policy_math.h](../../src/world/world_quest_policy_math.h): cached
  catalogs, reward pools, target suitability, geographic membership, and selection bounds.
- [actcomm.c](../../src/cmd/actcomm.c) and
  [fight.c](../../src/combat/fight.c): the ASK and killer/group KILL hooks.
- [sql.c](../../src/sql/sql.c) and
  [flatfile_world_quest_history.c](../../src/flatfile/flatfile_world_quest_history.c):
  backend-specific completion history and daily counts behind `sql_world_quest_*`.
- [difficulty.c](../../src/world/difficulty.c) and
  [currency_transaction.c](../../src/economy/currency_transaction.c): difficulty
  scales and the wallet/payment completion boundary.
- [limits.c](../../src/world/limits.c) and
  [item_movement_transaction.c](../../src/item/item_movement_transaction.c):
  final XP credit and queued item-grant delivery.
- [json_utils.c](../../src/core/json_utils.c) and
  [gmcp.c](../../src/net/gmcp.c): `Quest.Status` and `Quest.Map` payloads.
- [player snapshot capture](../../src/player/player_snapshot_capture.c),
  [codec](../../src/player/player_snapshot_codec.c), and
  [load materialization](../../src/player/player_load_materialize.c): saved
  assignment state and compatibility with older snapshots.

## Player flow

At an NPC with the `world_quest` procedure:

```text
ask <bartender> quest
quest
score
ask <bartender> map
quest share <player>
ask <bartender> abandon
ask <bartender> abandon confirm
```

Use the NPC's actual keywords in place of `<bartender>`. All bartender requests
are local ASK interactions. `resign` is also accepted for abandonment, including
`resign confirm`. `quest` shows current work and replays a bought map; `score`
shows the known daily allowance. An enabled zone-story daily may appear
alongside the bartender task; `quest daily` addresses that separate system.

New purchases require level 11, available daily allowance, enough money, and
no active assignment. For each sampled zone, new purchases at levels 11–49
randomize ASK/KILL order and try the other type if necessary; level 50+
purchases select KILL only. There is no player command to request one kind.
A purchase captures the real origin room and bartender VNUM before charging.
Failed selection returns the fee. Purchase and sharing check allowance;
completion consumes it. An unavailable history read is reported separately from
a known exhausted allowance and does not charge for a new task.
There is no elapsed-time quest deadline: the saved start time controls abandonment
cost, not automatic expiry. Level changes do
not reroll the accepted type, target, scope level, or kill quota.

An ASK assignment completes when `do_ask()` reaches the matching NPC in the
advertised zone. Use `ask <target> <message>` with a nonempty message; the
display suggests the current game month, but the world-quest hook does not
validate that phrase. Normal ASK visibility, speech, silence, and underwater
checks still apply, and an intercepting procedure can prevent the hook.
A KILL assignment advances only for the accepted target prototype,
quest type, and actual zone through `quest_kill()`. Its initial quota is a
difficulty-scaled random 7–9, capped at usable target count minus one. XP is
paid per credited kill. The final kill grants the completion reward directly
and clears the assignment. ASK likewise rewards and clears immediately.
Legacy `quest_accomplished` work can still be claimed at the original giver
by asking for `quest`, before the new-purchase level and allowance gates.
The giver is matched by NPC prototype VNUM, not the identity of one live
instance. Current ASK/KILL completions require no return trip to collect payment.

## Rewards

Each character completes and is rewarded independently, including shared work.
Let `C` be that character's current level at the relevant reward call, `L` the
saved accepted quest level, and `N` the original KILL quota.

- **Item:** one uniformly selected prototype from the accepted zone's cached
  reward pool for `L` (falling back to `C` only if the saved level is nonpositive).
  If it cannot be instantiated, `create_random_eq()` uses current level `C`.
  The resulting item has `ITEM_SECRET`, `ITEM_INVISIBLE`, and `ITEM_NODROP`
  removed and `ITEM_NOREPAIR` added. The KILL reward goes to the completing
  character through the player-save transaction, not onto a corpse or on every kill.
- **XP:** `quest_exp_reward()` truncates `EXP_NOTCH(character) * band_multiplier`
  to an integer using current level `C`. A notch is
  `max(new_exp_table[C + 1] / 10, 1)` for mortal levels. ASK requests this full
  amount once. Each credited KILL, including the last, requests integer
  `quest_exp_reward() / N`; the final kill has no additional full XP award.
  If the character levels during a KILL task, later kills recalculate the amount.
  [Settings and history](#settings-and-history) lists the band multipliers.
- **Epics:** both current and accepted levels must exceed 45. The base
  `EPIC_QUEST` amount is a uniform integer from `L - 45` through `L - 43` for
  accepted levels 46–53, 9–10 at 54, 10–11 at 55, and 15 above 55. These are
  inputs to `gain_epic()`, so ordinary epic modifiers, active-task penalties,
  and task assignment still apply; see [Epic tasks](EPIC_TASKS.md).
- **Mercenary money:** a character with `CLASS_MERCENARY` and current level
  above 24 requests `C * 1256 + random(1, 500)` copper at completion.

The XP request passes through `gain_exp(..., EXP_WORLD_QUEST)`. Rested bonuses,
the character's race modifier, the earned-XP difficulty dial, the per-award
one-third-next-level cap, and the global/storage ceiling can change the credit.
Arena, guild, and safe-room checks can suppress XP. With `toggle experience`
enabled, a positive mortal credit prints `Quest EXP:` using the actual credited
amount. Ordinary combat XP is separate from the bartender per-kill award.

Completion captures the scalar reward amounts at the completing interaction.
The detached item, completion history, and a pending-reward marker commit together
through the player-save transaction (MariaDB or the flatfile authority journal).
Only confirmed item publication allows the remaining XP, money, epics, feedback,
and task reset. A rejected capture leaves the task intact; admitted work holds
the task against duplicate turn-ins and retries failed writes/publication.
Failure to create an item also keeps the task and earned kills.

If the process stops after commit but before publication, login restores the
item from the saved inventory. The completed-task marker preserves the captured
remaining scalar rewards for a bartender claim without creating another item
or recording history again. The marker temporarily stores XP, epics and copper
in the completed task's receiver, shares and credited-kill fields; these fields
resume their ordinary meanings when the task is reset.

## Catalog, target, and route policy

[world_quest_policy.c](../../src/world/world_quest_policy.c) builds the global
catalog once at boot through `calc_zone_mob_level()`, after world indexes,
special procedures, and map setup.
Both persistence backends use loaded content; `zones.quest_zone` is not an
approval list. Repeated quest requests reuse cached mobile profiles, reward
pools, and per-level scores rather than scanning all prototypes or querying SQL
for zone eligibility. Temporary probes restore live entity counts.

### Zone and reward eligibility

Policy excludes sentinel/non-normal zones (zone numbers outside `[0, 4000)`),
explicit zones 0/292/536/914, towns and hometowns, and zones without eligible
local rewards. Prototype ownership is resolved from valid room-VNUM intervals.
The mean includes the successfully probed mobile prototypes in that interval,
not their live population or reset frequency. Its truncated value must lie
strictly inside `(L - 7, L + 5)`. A zone whose cached `get_map_room()` result is
absent requires accepted level 41 or higher.

`source_eligible_reward()` admits takeable wands, staves, armor, worn items,
books, quivers, instruments, spellbooks, totems, shields, fireweapons, weapons,
and potions, with these exclusions:

- `ITEM_NORENT`, `ITEM_TRANSIENT`, `STRUNG_KEYS`, `ITEM2_QUESTITEM`, artifacts,
  `IS_NOSHOW`, weight above 99, and the `_noquest_` keyword.
- Granted affects for stone skin, hide, sneak, flight, nofear, air/earth aura,
  inertial barrier, reduce, globe, haste, detect invisible, or detect illusion.
- Every explicit item input or output in the loaded static `quest_index`,
  whether or not a builder set `ITEM2_QUESTITEM`. Type-based static goals do
  not enumerate additional VNUMs for this exclusion.

Each zone then withholds its most valuable `world.quest.reward.top.withheld.percent`
(fallback/configuration 20) percent of source-eligible items, rounded up and
including value ties. If ties would remove the entire pool even though the
rounded requested count is smaller than the pool, withholding is suppressed.
A sole item with positive withholding is still removed; 100% withholding
removes the whole pool. This ceiling is calculated before level filtering.
Remaining rewards must have positive `itemvalue` and pass `2 * itemvalue >= L`
to enter that level's pool. Counts, means, and scores use only this final pool.
The boot log reports `withheld_quest_items` and `withheld_top_value`. The setting
is read when the catalog is built, so a change applies at the next boot.

For eligible zones, the relative selection weight is
`exp(-abs(average_level - L) / 6) * (average_ivalue / L) * eligible_item_count`.
Item count is deliberately linear; zero-reward zones have zero weight. See
[world_quest_policy_math.h](../../src/world/world_quest_policy_math.h) for
boundaries and constants. Weighting uses the untruncated average prototype
level; the eligibility window uses its truncated value. Zones are sampled
without replacement during a request, then suitable prototypes in a zone are
sampled uniformly for validation. The weight describes zone sampling, not a
guaranteed final target distribution after live eligibility/history failures.

### Live targets

KILL targets use the inclusive level band `[L - 4, L + 5]` for both the cached
prototype and live actor. ASK targets instead require both levels below 62,
without a player-relative level band. The zone-average window still applies
to both kinds. A per-request index uses actual destination zones,
not prototype ownership. Each instance must match a direct unconditional 100%
`M` reset in a resetting zone, with a positive maximum, at its saved birthplace.
Birthplace and current room must be in the same actual zone. Mixed
conditional/rare/random-table sources and restricted staging rooms stay
ineligible. Followers, mounts/other mastered mobs, summoned instances, charmed
mobs, and conjured pets are excluded; targets must be alive with positive HP
and at ground height (`z_cord == 0`). Both kinds need player-specific visibility.

KILL targets need at least two usable instances for a new purchase. Their
prototype and live forms must have positive XP and maximum HP above one;
shopkeepers, teachers, guild golems, ignored mobs, prototypes at or above
`MAXLVL` (62), safe rooms, and safe zones are excluded. The initial quota is
capped at usable count minus one.

ASK requires exactly one loaded instance globally (`mob_index.number == 1`),
cached and live levels below `MAXLVL`, speaking ability in both forms,
a live awake target, and a non-silent, non-underwater destination. Below
accepted level 31, invisible/concealed/hidden/ectoplasmic ASK targets remain
excluded even if the
player could see them. The actor must be able to speak; aggression toward that
actor and intercepting mobile/quest procedures reject a new assignment.
A shopkeeper qualifies only when its resolved shop has no delegate procedure or
an audited ambient Bloodstone delegate that ignores ASK. Actual quest interceptors and unaudited ASK handlers remain excluded.
Travel procedures, including Quietus's crew-room LIST/HIRE procedure, are not
quest eligibility checks.

### Geography and request bounds

Assignment and accepted-task validation do not prove an outward or return route.
Doors, locks, keys, secret exits, walls, barriers, traps, scripts, transport,
terrain and flight/boat/waterbreathing requirements do not disqualify an
otherwise eligible target. Players travel using normal game rules. No quest
request executes movement or transport scripts.

Accepted levels 11–29 use the union of the origin's attached surface region
and connected Underdark map component. Quietus (1734) and Bloodstone (74339)
may assign targets in either local region. Level 30 removes this local scope
restriction; it does not remove zone-average, target, reward or mapless rules.

The boot catalog uses surface continent identities and undirected authored
map-to-map adjacency for Underdark components, ignoring travel conditions.
Interior zones attach to the nearest authored zone boundary for each family
separately, allowing nearby connector zones without flooding every connected
interior. Multiple entrances in the same region agree; tied boundaries in
different regions remain unresolved for that family. Surface and Underdark
attachments do not conflict. Interiors cannot merge Underdark components.
Ambiguous geography preserves accepted work as unproven; a known matching
family still permits the task even if the other family is ambiguous.
Geographic membership applies to a target's actual zone, including disconnected
rooms, without requiring a path to either its reset or current room.
Closed/private destination zones and restricted target/reset rooms remain
excluded, independently of transit conditions.

Map hints use geographic entrances and identify a location, not a guaranteed
route. Selection does not spawn a prototype or move the observer.
Target probes and history checks each retain a request-wide limit of 32.
Live-character/visibility/shop-check work retains a two-million-operation bound;
there is no route-search or route-room budget. Previously completed target
VNUMs stay excluded across types, zones and levels using all retained history.
A history-read failure stops assignment. Bounded selection may report no
usable target without trying every candidate in the loaded world.

`createQuest()` distinguishes no eligible zone from no usable target. The
payment continuation captures stable bartender/origin VNUMs rather than a live
NPC pointer; the wallet debit and completion run in memory before the currency
API returns. A failed selection refunds the fee in memory, with wallet changes
persisted by the player's save.

If catalog construction throws, it fails closed and latches the failure for
that process. Requests do not rebuild the catalog or scan prototypes to bypass
it. Content, reset provenance, reward-policy, and map-cache changes require a
new boot catalog; live actor locations and target interactions are rechecked per request.

## Recovery, maps, and sharing

### Availability and free replacement

`world_quest_refresh()` revalidates accepted work for `quest`, bartender
interactions, and no-argument GMCP status sends, including the initial status.
A proven world-invalid incomplete quest becomes inactive with
`quest_replacement_due=1`. Temporary player limitations,
unknown ASK handlers, and exhausted target-check budgets do not alone cancel an assignment.
Completed legacy work remains claimable. Old assignments without an origin need
rebinding at a real bartender to establish their accepted local scope.

The availability results distinguish:

- `valid`: enough suitable targets meet the accepted scope and interaction rules.
- `blocked`: current player/target conditions such as blindness, sleep or silence
  prevent interaction; the accepted task remains.
- `unproven`: an ASK handler, aggression-dependent interaction, unresolved geography,
  or target-check bound prevents a reliable verdict; the task remains.
- `needs_origin`: suitable work exists but the legacy task has no recorded
  origin. Ask a bartender to check it; a valid check binds that room as origin.
- `unavailable`: the world cannot support the remaining work under this
  contract, for example a removed target, inadequate qualifying supply, or a
  geographic mismatch. Refresh grants replacement entitlement. Route changes
  never grant replacement.

Accepted KILL supply is checked against remaining kills; the new-purchase
minus-one rule is not applied again. Scope uses the saved accepted level and
origin even after the character travels or levels. Validation uses one target
check, with no capability-dependent route passes.

Ask any real bartender for `quest` to redeem a replacement without a new fee or
daily penalty, before the new-purchase level and allowance gates. Replacement
still requires an eligible target and loaded target-exclusion history.
It retains accepted type/level, earned kills, original quota, receiver, remaining
shares, purchased-map flag, and original start time. If no
replacement qualifies, the entitlement remains. A successful replacement updates
the target, zone, giver, origin, and geographic map entrance to the new interaction;
the same target may be selected again if it has become usable. Retained kills
do not award XP again. Returning supply does not automatically reactivate a
pending entitlement: ask for `quest` to select the replacement.
`abandon confirm` discards an entitlement and progress without charging money,
recording a target completion, or consuming allowance.

### Voluntary abandonment and maps

Any bartender can abandon ordinary active work. `abandon` immediately charges
and clears ASK work or KILL work with zero credited kills if payment succeeds;
it is not a price-only enquiry. Neither case records completion history.
If a KILL task has progress, `abandon confirm` is required and successful
payment records a completion-history entry with no item, thereby consuming
allowance and excluding that target. Completed legacy work cannot be abandoned.

The money fee is the integer base `world.quest.abandon.mod * C^3`, multiplied
by `clamp(1, 100 * (1 - elapsed_hours / decay_hours), 100) / 100`, then truncated
to an integer copper value. `C` is current level, `elapsed_hours` runs from the
original start time (including offline time), and `decay_hours` defaults to 24.
At or beyond that period the multiplier stays at 1%, not zero. The
`world.quest` difficulty dial does not scale map or abandonment charges.

Buying a map requires a valid assignment and a known geographic entrance; it costs
`10 * current_level` copper and can be done at any bartender. A target can be
valid without a map
entrance, in which case the bartender refuses the map without charging.
A failed post-payment map check refunds the fee. Maps are a paid, repeatable
view of the geographic entrance, not a step-by-step route to the NPC. After buying
one, type `quest` to view it again without another fee. The purchase flag survives
temporary interaction blockage and free replacement; hints are withheld until
a later valid refresh.

### Sharing and kill credit

Use `quest share <player>` with a visible PC in the same room. The recipient
must consent the sharer; group membership is not required. Only the original
receiver can share, subject to remaining shares and the current configured limit.
Sharing has no money fee. The accepted level must be within the configured
high/low bounds of the recipient's current level (inclusive ±6 in this checkout).
There is no separate recipient level-11 check in the sharing branch.

The recipient needs remaining daily allowance, no retained completion for that
target VNUM, and a suitable target checked against the original accepted scope
using the accepted level and remaining KILL count. An active assignment or
replacement entitlement cannot be overwritten. Sharing copies the original
giver, receiver, start time, type, level, target, origin, quota, and already
earned kills. Each recipient then progresses independently; later progress,
replacement, abandonment, or completion does not update the other copies.
The recipient starts with no purchased map and no onward shares; they can buy
their own map. Receiving copied kills awards no retroactive XP.

The death hook calls `quest_kill()` for the killer and other members of the
killer's group in that room; each still needs its own active matching KILL
assignment. They need not have received those assignments through sharing.
A PC-pet kill can reach that group path as well; the pet itself cannot hold a
PC quest. Conjured-pet victims do not invoke this credit path. ASK credits only
the character whose ask reaches the target. These hooks match type, target
VNUM, and actual zone; they do not rerun level, reset-provenance, or
selection-suitability checks at completion time.

## Client status and maps

Quest text and JSON payloads use boot-cached NPC short descriptions without
spawning prototypes. Missing giver/target labels do not reset paid or completed
work. A paid map uses a synchronous viewpoint without room-transfer hooks,
population changes, or action interruption, and emits `Quest.Map` separately
from `Room.Map`.

The serializer in `json_build_quest_status()` supplies:

- `active`, `type` (`ask`, `kill`, or null), `target`, `mapBought`,
  `availability`, and `replacementDue`.
- `remaining` only when the allowance is known; it is omitted while SQL history
  is loading or a history read fails. `score` also omits an unknown count.
- `killCount` and `killRequired` for active or replacement-pending KILL work.
- `zoneNumber` only for a verified, active, incomplete task with known target
  and zone labels. Otherwise `target` is a recovery/completion message or empty.

Availability strings map `valid` to `available`, `blocked` to
`temporarilyBlocked`, `needs_origin` to `needsBartender`, and preserve
`unavailable`/`unproven`. `available` is a validity result, not a promise that
another quest can be bought: idle and completed legacy states also return it.
Use `active`, `replacementDue`, and known `remaining` alongside it.

Pending replacements have `active:false` and retain type, kill progress, and
`mapBought`. `Quest.Map` contains `map` text and `zoneNumber`; its viewpoint
uses a 20-tile radius. An empty map with `zoneNumber:0` clears stale directions
when work becomes unverified, inactive, or complete. `Room.Map` remains the
character's normal map channel. The no-argument status sender can refresh
assignment availability; JSON payload serialization itself does not change
quest state or money.

## Settings and history

### Configuration

Values below are the checked-in [duris.properties](../../lib/duris.properties),
before any runtime configuration or difficulty scaling. Fallbacks in C++ can
differ; in particular `world.quest.share.max` falls back to 0 but this file sets 4.

- Purchase: `world.quest.cost.per.level=20` copper per level, then the world-quest
  difficulty fee scale (C++ fallback also 20). Keep the resulting charge positive:
  the payment callback requires a positive fee, so setting this property to zero
  does not implement free new quests.
- Sharing: `world.quest.share.max=4`, bounded to 0–4; 0 disables sharing.
  `world.quest.level.high.value` and `world.quest.level.low.value` are both 6
  (both C++ fallbacks are also 6). A reduced sharing limit caps an old task's
  remaining shares; increasing it does not refill an existing assignment.
- Daily maxima for level bands ≤30 / ≤40 / ≤50 / ≤55 / other: 8 / 8 / 8 / 5 / 2,
  in `world.quest.max.level.30.andUnder`, `.40.andUnder`, `.50.andUnder`,
  `.55.andUnder`, and `.other`, respectively. All C++ fallbacks are 6, then
  difficulty scaling applies.
- XP notch multipliers for those bands: 0.6 / 0.6 / 0.6 / 0.4 / 0.75,
  in the corresponding `world.quest.exp.level.*` keys. C++ fallbacks are
  1.3 / 1.0 / 0.8 / 0.5 / 1.0.
- Abandonment: `world.quest.abandon.mod=0.25` times current level cubed,
  multiplied by a remaining-time percentage clamped to 1–100.
  Its C++ fallback is 1.0. `world.quest.cost.abandon.time=24` is the decay
  period in hours (also fallback 24).
- `world.quest.reward.top.withheld.percent=20` is read while building the boot
  catalog as an integer clamped to 0–100; 0 disables top-value withholding.
  Changing it requires rebuilding that catalog at boot.

The checked-in `difficulty.dial.world.quest=5` is neutral (multiplier 1).
The [difficulty functions](../../src/world/difficulty.c)
`difficulty_scale_world_quest_fee/allowance/kills()` multiply purchase fees
and initial kills by the effective world-quest multiplier, and divide daily
allowance by it. Non-neutral scaling rounds to the nearest integer, with a
minimum allowance and kill request of one, before the usable-count quota cap.
The multiplier can be changed independently of these base properties.
Fees, allowances, shares, and XP consult their current in-memory settings at
use time; a saved KILL quota is not recalculated. The earned-XP and epic-gain
dials affect their respective reward pipelines separately. Do not infer
effective runtime values from the checked-in properties alone.

### Saved assignment and completion history

Assigned fields live in `pc_only_data` and the player STATUS snapshot: target,
type, level, giver/receiver, start time, kill counts, shares, map, origin, and
replacement entitlement. Stored rooms and zone numbers are VNUMs, not transient
runtime indexes; giver/target are prototype VNUMs and receiver is a player PID.
SQL requires the additive recovery fields from
[0055_world_quest_recovery.sql](../../migrations/immutable/0055_world_quest_recovery.sql);
see [player saves](../persistence/PLAYER_SAVE_PIPELINE.md)
for checkpoint authority.

Snapshot wire version 13 appended origin and replacement fields; earlier wire
versions and legacy pfile imports initialize both to zero. The legacy 14-value
quest payload is unchanged. Reset clears these fields, and sharing copies the
origin. Creation, sharing, map purchase, availability transitions, replacement,
and reset mark STATUS dirty. Partial KILL progress is captured in STATUS too;
the increment relies on the subsequent positive XP credit to mark that component
dirty rather than marking it directly. A zero-credit path does not itself mark
the partial kill dirty; persistence then depends on another STATUS save trigger.

Completion history is separate: SQL uses `world_quest_accomplished` with an
asynchronous login/lazy-read cache; flatfile uses `<FLATFILE_ROOT>/players/<pid>.world-quests`.
SQL history reads return completion timestamps and count them against the UTC day
when the cache is published; a read finishing after midnight cannot consume the
new day's allowance with yesterday's completions. A completion/confirmed
abandonment rolls an existing cache to the current day before adding its count.
Daily counts use UTC days and, below level 50, only completions at the character's
current level; level 50+ uses the whole day's count. Records store current
level when recorded, not accepted quest level. Leveling below 50 can therefore
open allowance in the new level's bucket, but does not clear target exclusions.
Successful completion and a paid abandonment of progressed KILL work create
history; purchasing, sharing, and free replacement do not.

SQL queues the history INSERT and updates its in-memory cache without waiting
for durable database success. Flatfile writes a versioned, SHA-256-checked
history under a per-player lock with atomic replacement, with a 100,000-entry
limit; it stores target, level, and time rather than SQL's giver/reward details.
Neither path makes history and the player's reset/rewards one transaction.
The flatfile wrapper reports write failure through `persistence_alert()`;
the SQL caller ignores the INSERT queue's return value. The task still clears
on a history failure, and a restart can expose missing allowance/exclusion
history. Target exclusions use all retained history.
Unready SQL history and corrupt/unreadable flatfile history block new assignment
and sharing checks. A genuinely absent flatfile history file starts as empty
history. Current assignment snapshots do not reconstruct lost history.

### Staff inspection and troubleshooting

Staff can use `quest stat <player>` to inspect saved assignment fields and
`quest reset <player>` to clear them. Reset is a mutation and discards the
replacement entitlement as well, without a fee or history record; it does not
erase existing completion history. These are trusted-only subcommands using
the local target resolver. `stat` prints the legacy assignment fields; it omits
the newer origin/replacement fields and shows start time only as a yes/no value.
Use the saved STATUS state when those omitted fields matter.

For a refusal or missing reward, distinguish these cases:

- No new task: check level, known remaining allowance, wallet value, catalog
  readiness, local geography, and target/history eligibility. Levels 11–29
  receive the combined "No suitable local task" refusal; higher-level feedback
  distinguishes no eligible zone from no suitable live target. A failed paid
  selection refunds the fee and publishes no new assignment.
- Blocked/unproven/legacy origin: read `quest` and the availability result before
  clearing work. The progress and map purchase are retained. A proved world
  invalidation offers the free replacement path instead of paid abandonment.
- Missing reward item: check the ownership-service rejection/publication logs
  as well as the quest completion history. SQL's recorded reward describes an
  accepted item submission, not confirmation that delivery settled. Resetting
  the assignment neither recreates the item nor reverses a completion record.

## Verification

For documentation changes, run `python3 tests/async/test_documentation_contract.py`.
That checks maintained-document links, anchors, and selected repository
contracts; it does not establish every gameplay statement's accuracy. Review
the owning source paths above as well. Run each focused script below with
`python3 tests/async/<filename>` when its behavior needs qualification:

- [test_world_quest_dynamic_policy.py](../../tests/async/test_world_quest_dynamic_policy.py):
  source contracts for cached catalog/selection, plus executable policy math.
- [test_world_quest_routes.py](../../tests/async/test_world_quest_routes.py):
  production geography on controlled authored graphs, including both regions,
  one-way links, nearest boundaries, disconnected rooms, ambiguity and large worlds.
- [test_world_quest_target_retries.py](../../tests/async/test_world_quest_target_retries.py):
  production creation, live target checks, bartender parsing/payment, sharing,
  legacy claims, and recovery against controlled world/reset fixtures. Its
  300 scenarios also exercise level/zone boundaries, geography, route immunity,
  history/probe caps and refunds, followed by 10 SQL-history scenarios.
- [test_world_quest_reward_policy.py](../../tests/async/test_world_quest_reward_policy.py):
  executable withholding math and source contracts for reward filtering,
  sharing limits, fees, and one-item completion policy.
- [test_world_quest_failure_feedback.py](../../tests/async/test_world_quest_failure_feedback.py):
  source assertions for failed assignment feedback, refunds, and preserved state.
- [test_world_quest_xp_feedback.py](../../tests/async/test_world_quest_xp_feedback.py):
  production reward/XP bodies with controlled dependencies on both backends,
  including credited feedback, modifiers, ceilings, and zero-credit paths.
- [test_world_quest_remaining_unloaded.py](../../tests/async/test_world_quest_remaining_unloaded.py):
  production score/status serialization and quest text with unknown allowance,
  missing labels, completed work, and read-only rendering.
- [test_flatfile_world_quest_history.py](../../tests/async/test_flatfile_world_quest_history.py):
  flatfile completion records, daily counting, corruption, and persistence.

[run_world_quest_dual_backend.py](../../tests/async/run_world_quest_dual_backend.py)
is a separate full-world qualification, not a routine documentation check. It
runs `make world`, builds servers under temporary `bin/tests` roots, and needs
the server build dependencies, GDB, and Docker for MariaDB. It uses disposable
accounts/databases/state roots, never the repository `.env` or long-running
local stack. Its gameplay cases exercise real grants, ordinary outbound/return
travel, ASK/KILL completion, and partial progress across restart. Its recovery
case exercises paid maps, invalidation, relogin/restart, and durable free
replacement. Test-only `DURIS_WORLD_QUEST_BACKEND` selects `mariadb`, `flatfile`,
or `both` (default). `DURIS_WORLD_QUEST_JOURNEY` selects `recovery`, `gameplay`,
`both` (default), or `audit` for the loaded-world audit/observer timing pass.
`reported` checks the Quietus, Bloodstone and Tharnadia purchase/abandon/regrant
reports, consent/sharing/maps with locked exits, restart state for both players,
and Bloodstone ASK/KILL travel, using disposable fixtures. Sharing is enabled
only in that run's private properties copy.
`history` constructs yesterday-only completion history and an aged Tharnadia
task, then checks real abandonment/regrant and restart. Its disposable MariaDB
session clock constructs old-query-day/new-publication-day results and is
restored before the completion marker; flatfile supplies the equivalent
past-day-history control.
Focused gameplay cases can be selected with `DURIS_WORLD_QUEST_GAMEPLAY_CASES=30:1`;
the full matrix is `11:2,11:1,29:1,29:2,30:1` (KILL=1, ASK=2). For example:

```sh
DURIS_WORLD_QUEST_BACKEND=flatfile DURIS_WORLD_QUEST_JOURNEY=gameplay \
  DURIS_WORLD_QUEST_GAMEPLAY_CASES=30:1 \
  python3 tests/async/run_world_quest_dual_backend.py
```

That focused run qualifies one backend/case, not the full default matrix.
The gameplay debugger sets the disposable Chaos actor's requested level and
selects an otherwise eligible zone/prototype with ordinary outward/return paths
for completion testing. Production selection still validates the chosen target.
ASK completion fixtures use NPC levels outside the KILL band. The probe's
navigation helper is independent of eligibility; special-travel assignments
are covered by native policy fixtures. Tagged score requests synchronize
observations with the command response and following prompt.
Explicit `chaos questroom` commands place/fund
the fixture at its bartender; outbound/return travel and target interactions
use normal commands. The recovery probe deliberately closes eligible zones
in memory to force invalidation and a no-candidate wait; a fresh server boot
restores authored world flags while retaining the player's saved entitlement.
The actor's retained Chaos HP/equipment do not qualify combat difficulty.
All sampling/RNG breakpoints are disabled for command/observer timing.
Character creation reuses the maintained combat-journey flow. Focused
`test_world_quest_*` tests cover policy and failure boundaries.

The [issue #437 qualification record](../ongoing-projects/plan-issue-437.md)
retains detailed local journey evidence. Test existence or a source checkout
does not establish the binary, settings, routes, or recovery state of a live
production deployment.
