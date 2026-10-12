# Arena implementation plan

Implement public, ranked, one-on-one Arena battles in Duris. Players may watch from
**level 2** and compete from **level 20**. A match combines a race for temporary
equipment, ordinary Duris combat across connected rooms, overtime, public viewing,
wagers, persistent standings, and champion rewards. Every connected player at level
2 or above can observe either combatant, regardless of racewar side, class, guild,
account age, or location in the world.

Status: planned; implementation has not started. Prepared on 2026-10-12 against
Duris revision `c3f8fffc0`. This deliverable is the implementation plan; it does not
authorize deployment or change the running game.

## Requirements and evidence

The supporting research is preserved beside this plan in `arena-research/`:
the [mechanics report](arena-research/medievia-hero-battles.md),
[timestamped live evidence](arena-research/medievia-hero-battles-live.md), and
[63-record source inventory](arena-research/medievia-hero-battles-sources.tsv).
These retain the historical accounts, source URLs and retrieval hashes, observed
behavior, and unresolved questions. The requirements and proposed decisions below
remain self-contained; none of these documents depends on the old temporary files.
The inventory distinguishes official help, historical testimony, narrative examples,
and direct observations. An empty live spectator list established command access,
not a successfully observed match. No complete arena map, equipment catalogue,
rating formula, or current match transcript was recovered.

The name **Arena**, the two level thresholds, and public observation are user
requirements. Other numbers and unspecified behaviors under “Proposed Duris rules”
are concrete design defaults for review, not claims about Medievia. Do not infer
implementation details from the old Medievia source archive: it lacks Hero Battles.

| Required feature | Evidence and adaptation | Delivery phase |
| --- | --- | --- |
| Registration, withdrawal, personal standing | AUTO_HB and the live registration NPC; replace hero status with level 20 | 1 and 3 |
| Automated pairing and one active match | 90-second window, least recently active applicant, nearest rating, clear requests on start | 3 |
| Two different arenas | Official feature description; build original Duris maps | 2 |
| Equipment collection before combat | Historical preparation phase and exceptional temporary equipment | 2 and 3 |
| Pursuit, retreat, recovery, hazards and equipment changes | Historical accounts; use Duris skills, spells, timing and resources | 2 and 3 |
| Overtime in a smaller arena | Official help; use the historical nine-room layout as the Duris design | 3 |
| Public announcements and competitor discussion | Separate battle announcements and discussion channel | 4 |
| Public observation of either combatant | Mindlink model, level-2 command access; available across Duris from level 2 | 4 |
| Spectator filter and public vital statistics | Gagged perspective by default; separate match status | 4 |
| Wagers and fighter income | Betting before combat; 10 percent of losing stakes to the fighter, 90 percent to winning bettors | 5 |
| Ratings, sortable standings and history | Initial 1,000 rating, rolling 30-day results, inactivity reset | 6 |
| Champion titles, HP and flying mounts | Top twelve; first is Grand Champion; bonuses excluded from Arena combat | 6 |
| No permanent loss from fighting | Historical protection of possessions and progress; explicit restoration design | 2 and 7 |
| Disconnect, idle, abort and restart handling | Linkdead combatants remain vulnerable; idle removal loses; fill recovery gaps explicitly | 3 and 7 |
| Contest integrity and staff controls | No throwing or outside intervention; integrate with Duris conduct and staff permissions | 3, 5 and 7 |
| Accurate in-game instructions | Live help had obsolete directions; verify actual routes and commands | 8 |

All rows are part of the finished feature. Wagers, observation, mounts, and recovery
are not optional follow-ups after a smaller duel-only release. Medievia's general
Hero Points, Master Hero status, Adversary, and four-class hero progression are
separate systems; they are not additional Arena features to transplant. Duris Arena
ratings must also remain separate from epic points, frags, guild scores, and ordinary
PK rankings.

### Design lessons retained from the research

Use these lessons when building the item catalogue, maps, help and playtests. They
describe the intended experience; Medievia's historical numbers are not Duris balance
targets.

| Research finding | Application to Duris |
| --- | --- |
| Players described HP/mana equipment early and offensive or saving-throw equipment later, with collected items denied to the opponent | Test meaningful equipment tradeoffs and changes during a fight; avoid a catalogue with one best loadout for every situation |
| Retreat, protection renewal, recovery and attacking during an opponent's wait state were central tactics | Verify that map routes and native Duris timing permit those choices alongside pursuit and pressure |
| A novice found identifying and selecting unfamiliar gear especially difficult | Give match items clear names and useful identification text; include a first-time competitor in catalogue and preparation playtests |
| Watching is presented as a way to learn; interviews describe recognition of skilled fighters and interest in wagers | Make the public feed understandable enough to learn from, including action outcomes and recovery decisions rather than only damage totals |
| Live help still gave the wrong registration route and an obsolete return shortcut | Walk every published Duris entrance and help sequence on the finished world; command help alone is not navigation proof |

The [2002 preparation account](arena-research/medievia-hero-battles.md#preparation-and-the-equipment-race)
and [historical tactics](arena-research/medievia-hero-battles.md#historical-tactics-and-the-learning-curve)
support the tactical lessons. The [2009 novice account](arena-research/medievia-hero-battles.md#preparation-and-the-equipment-race)
estimated 3–5 minutes of preparation and reported roughly 1,600 HP/800 mana; those
were one player's estimates and achieved values, not verified timers or caps.
The tour's lightsaber, chef's hat and bottled healing item are narrative inspiration,
not recovered item templates. Preserve the distinction between an observed feature,
a historical report, and a proposed Duris rule when tuning or revising this plan.

## Current Duris integration points

Duris already contains arena code, but it does not implement this experience.

| Current source | Observed behavior | Planned use |
| --- | --- | --- |
| [arena.c](../../src/combat/arena.c), [arena.h](../../src/combat/arena.h) | Team arrays, racewar entry, one Opposing Castles map, lives, several game/death modes; disabled by default | Keep legacy behavior separate from the new two-player match state |
| [actnew.c](../../src/cmd/actnew.c), `do_arena` | Ordinary users must already be in `ROOM_ARENA`; staff have on/off/type controls | Route the public Arena subcommands before the legacy location restriction |
| [interp.c](../../src/cmd/interp.c), `CMD_ARENA` | Existing command registration | Reuse the command; enforce level thresholds per subcommand |
| [comm.c](../../src/net/comm.c), `run_activity_phase` | `arena_activity()` invocation is commented out | Schedule the new match pulse explicitly; do not reactivate the old tournament timer |
| [fight.c](../../src/combat/fight.c), `die` and damage paths | Arena exemptions coexist with legacy `ARENA_PLAYER` indexing and normal death side effects | Handle enrolled duelists before normal death, follower dismissal, and legacy team scoring |
| [fraglist.c](../../src/combat/fraglist.c), `fragWorthy` | `ROOM_ARENA` suppresses ordinary frag eligibility | Preserve this protection and check other kill/epic/reward paths |
| [utility.c](../../src/core/utility.c), `broadcast_to_arena` | Sends to configured hometown room ranges; movement calls in handler.c are commented out | Insufficient for global viewing; leave hometown behavior intact |
| [output_channel.h](../../src/net/output_channel.h), [output_style.h](../../src/net/output_style.h), [output_message.h](../../src/player/output_message.h) | Structured output channels, recipient rendering and message provenance | Reuse rendering and combat/room categories for explicitly public match output |
| [currency_transaction.h](../../src/economy/currency_transaction.h) | In-memory balances and ordered saves through one writer | Use existing money conversion and mutation paths for wagers and claims |
| [player_snapshot_capture.c](../../src/player/player_snapshot_capture.c), [player_save_pipeline.c](../../src/player/player_save_pipeline.c) | Captures live items, status, affects, and other character components | Save the permanent character view while temporary battle state is active |
| [mount.c](../../src/classes/mount.c), [new_skills.c](../../src/classes/new_skills.c) | Mount commands and summon-mount behavior already exist | Reuse follower/riding mechanics for champion mounts; do not replace `call`, which calls graves |
| [existing arena zone](../../areas/zon/arena.zon) | Zone 679 is a CTF tournament with old portals | Allocate new room/object/mobile ranges; preserve this zone |

Use a small Arena-specific implementation: `src/combat/arena_duel.c/.h` for match
state, rules and commands; `arena_observer.c/.h` for public feeds; and an Arena
repository with the existing persistence backends. Split further only when a real
responsibility needs it. There is no need for a tournament framework, a second combat
engine, a new worker, dynamic world instancing, or a web application. One match at a
time allows dedicated reusable rooms.

Expose legacy staff functions under `arena legacy ...`; preserve their existing
permission checks and keep them disabled by default. New `arena on/off` control only
the ranked system. Existing hometown duels and unrelated `ROOM_ARENA` behavior must
not enroll players, create ranked results, or enter the new settlement path.

## Proposed Duris rules

### Access and commands

`arena help` and static standings are readable at any level. Live feeds, live vital
statistics, wagering, and public battle announcements require level 2. Competing and
competitor discussion require level 20. Recheck eligibility at pairing, rather than
relying only on the initial command check. A level-19 character must never become a
combatant; a level-1 character must not attach to a live feed.

| Command | Behavior |
| --- | --- |
| `arena` or `arena status` | Current phase, contestants, arena, timers, betting status, and public vitals when eligible |
| `arena join` | Register an eligible character and show the matching deadline |
| `arena withdraw` | Remove an unmatched request |
| `arena queue` | Show applicants and priority; no account or network identifiers |
| `arena rank [name]` | Rating, rank, recent record, last match, champion entitlement |
| `arena list [points\|wins\|losses\|time]` | Sort the rolling standings; default points |
| `arena history [name]` | Recent results with opponent, outcome, timestamp and rating changes |
| `arena watch` | List both available perspectives with phase and filter status |
| `arena watch <fighter>` | Start or switch to that combatant's public perspective |
| `arena watch off` | Stop viewing immediately |
| `arena filter on\|off` | Combatant controls the tactical detail in their perspective; private output is always excluded |
| `arena announcements on\|off` | Persist the player's battle-announcement preference; initially off |
| `arena chat <message>` | Level-20 competitor discussion, using ordinary mute and channel controls |
| `arena wager` | Show the current pools, cutoff, and the caller's stake |
| `arena wager <fighter> <amount> <coin>` | Stake carried coins; explicit copper/silver/gold/platinum denomination |
| `arena claim` | Receive available payouts/refunds; show a clear no-credit or capacity message |
| `arena mount` / `arena mount dismiss` | A qualifying champion calls or dismisses the reward mount |
| `arena on`, `arena off`, `arena abort <reason>` | Staff controls; off stops admissions and aborts an active match with refunds |
| `arena inspect` | Staff-only match, recovery and settlement diagnostics |

Add a registrar NPC and a safe public gallery with discoverable entrances. The NPC
uses the same join/withdraw/rank handlers; help and room text show those exact
commands. Remote `arena join` is also allowed from designated safe town or
registration rooms. This gives all racewar sides access without requiring passage
through an enemy city. Publish the actual entrances and permitted origin rooms when
the world content is built.

A queued character stays in the world and remains vulnerable under normal world
rules. Joining and pairing require an alive, connected, non-fighting character at a
permitted origin, without active hostile effects, pursuit/combat escape restrictions,
an unresolved Arena return, or an incompatible transport state. Apply existing
travel restrictions. Require ordinary pets/followers and mounts to be stabled or
dismissed before admission; do not silently kill or delete them. Cancel a request on
logout, extraction, leaving permitted origins, or becoming ineligible. Arena entry
must not provide an escape from ongoing PK or a free cure.

Keep one request per character and one entrant per account. Pairing across racewar
sides and within a side is allowed; two characters from the same account cannot
fight each other. Staff can inspect and abort, but cannot alter rated pairings, grant
unrecorded advantages, or bet while administering a match.

### Queue and match lifecycle

The first request opens a 90-second matching window. At its deadline, remove invalid
requests and select the applicant whose last completed match was longest ago. A
newcomer has no last-match timestamp and takes priority over previously active
fighters. Break equal priority by queue time, then stable player ID. Choose the
eligible different-account opponent with the closest current rating; break equal
distance by the same priority order. Players cannot select their opponent or map.

With fewer than two eligible applicants, retain the queue and show that another
fighter is needed. A second eligible applicant after the deadline can trigger pairing
on the next pulse. Do not start repeated empty countdowns. Check both selected
players again before transferring either. Clear all requests only when the pair has
successfully entered preparation; tell unselected players to register after the
match. Refuse new registrations during a match, rather than silently losing them.

| State | Work and transition |
| --- | --- |
| Disabled | Status and standings work; no new matches or wagers |
| Waiting | Queue is empty or lacks a pair; first request starts the 90-second deadline |
| Matching | Choose and revalidate two fighters; reserve the map and preserve both permanent character states |
| Preparation | Teleport both together, generate equipment, start feeds and wagering, disable hostile actions and hazards for 180 seconds |
| Combat | Close wagering before accepting the first hostile action; enable ordinary combat and hazards for up to 10 minutes |
| Overtime | Warn at 60 and 10 seconds before transfer; move both into the selected nine-room arena; run for up to 5 minutes |
| Finishing | Resolve one outcome, stop combat/events, freeze wagers, restore both characters, publish the result and credits |
| Resetting | Remove temporary objects, summons, room effects and subscriptions; verify the map is empty and reopen the queue |

The 180-second preparation, 10-minute combat and 5-minute overtime limits are Duris
defaults. The source supports preparation and overtime but not those exact timings
or a final hard timeout. In Duris, overtime expiration is a draw: no rating change
and all wagers refunded. A safety abort is also unrated. Record a draw separately
from an abort so statistics remain meaningful.

Use monotonic deadlines for live timers, and UTC wall-clock times for stored results
and 30-day expiry. Process transitions on the game thread once, in a documented
order: terminal outcomes first, then phase expiry, then new admissions. A lethal
outcome before the deadline wins over a later timeout check; attacks that become
illegal after a transition cannot execute from an old queued event. Preparation
warnings occur at 60, 30, 10 and the final 5 seconds. Publish overtime warnings,
start/end, winner, forfeits, draws, aborts and queue availability.

### Combat and temporary character state

Use actual Duris level, race, class, learned abilities, base attributes, and native
combat rules. Level 20 is an admission threshold, not normalization to level 20 or
maximum level. Display both levels before wagering. Matching uses rating, so large
level differences are possible; include level-20 versus veteran playtests when
tuning equipment. This default avoids inventing an additional progression system.

At entry, preserve a restorable permanent view: original inventory and equipment
with item IDs and containment, resources and conditions, affects and durations,
memorization/spell slots, temporary forms, cooldowns, and return room. Keep original
objects owned by the character in an inaccessible stowed collection. Do not move
them into a public room, repurpose a normal locker, copy persistent item IDs, or
leave their bonuses active. Strip external temporary buffs from the battle view;
disable Arena champion HP and applicable guild/clan HP bonuses there. Do not guess
that every Medievia bonus has a Duris equivalent: enumerate actual bonus sources.

Initialize the battle view with full native resources after removing external gear
and bonuses, a class-usable starter kit, and the character's legally available spell
capacity. Preparation permits equipping, identifying, recovering and self-buffing.
It forbids attacks, hostile spells, theft, traps that harm the opponent, pet attacks,
and environmental damage. A starter kit must supply required spell implements,
appropriate weapons and basic provisions for every playable class; unarmed classes
must remain viable.

During combat, retain normal movement, fleeing, hiding, tracking, casting, wait
states, equipment changes and recovery. Use Duris's tracking cost; the Medievia
sources conflict on its exemption. Do not copy Medievia-specific backstab counts,
spell costs or tick lengths. Arena-created class summons can fight as their owner's
abilities, but are match-bound and cannot bring outside equipment or followers.
The contest still has exactly two player combatants.
Permit attacks between the enrolled opponents through ordinary same-side and
non-PK targeting restrictions only during combat/overtime. Attribute a summoned
creature's actions to its enrolled owner; never extend that exception to outsiders.

Block recall, external teleport/portal/summon, transport, dragging across the boundary,
ordinary quit/camp/rent escape, external healing/attacks, item transfers to outsiders,
mail/shop/auction/locker disposal, and uncontrolled room entry. Validate both origin
and destination at shared movement, targeting and item-transfer boundaries; a
command-name blacklist is insufficient. Permit internal tactical movement and
class effects that do not escape the map or introduce outside resources. Staff
relocation/extraction of a contestant invokes the explicit abort path.

Arena activity must not award ordinary EXP, skill notches, frags, epic points, kill
quest credit, achievements for ordinary world kills, or permanent item progression.
Guard those award paths rather than undoing a whole character save afterward.

Intercept lethal damage and direct death effects for enrolled duelists before normal
death processing. Convert defeat into the match outcome; create no normal player
corpse, death penalty, equipment damage/loss, hardcore death, or legacy team frag.
Environmental defeat and self-inflicted defeat award the other fighter the win.
Resolve genuinely simultaneous lethal outcomes within the same resolution batch as
a draw. Stop pending combat, damage-over-time, spell, pet and room events before
returning either character; stale events must not kill the restored player.

Restore original equipment, possessions, native resources and spell capacity at
their entry values, clamped to valid maxima. Original timed affects and cooldowns
age by elapsed time instead of being refreshed. Arena-only ailments and spent
consumables disappear. Keep legitimate changes outside the battle overlay, including
communication preferences, playtime, Arena results and money credits. Return each
player to their original safe room, or a validated safe hometown fallback if it no
longer exists. Neither victory nor defeat grants a free world heal.

### Maps and equipment

Deliver two original maps in a new dedicated area: one emphasizing interconnected
loops and fire hazards, and one emphasizing vertical routes, alternate approaches
and discoverable hidden exits. Each must offer viable pursuit, retreat and recovery,
two separated starts, and a connected nine-room overtime section. Randomly choose
between validated maps with equal probability; record the map and equipment seed
for the result. No player selection or arbitrary world-room teleport is permitted.

Use ordinary area/object/mobile formats and loading paths. Reserve unused vnums
before authoring; do not overwrite the tournament at 67900. Validate every exit,
spawn, hazard and overtime destination before enabling admissions. Invalid content
keeps Arena closed with a useful staff error, not half an admitted match.

The starting catalogue contains 32 collectible objects per match in addition to the
starter kits, within the historical 20–50 range. Cover HP/mana/movement gear,
hitroll/damroll gear, armor/saves, weapon choices, shields, spell implements, healing
and resource consumables, detection/light, and limited tactical spell items.
Balance quantities and placement for both start locations; use mirrored opportunities
with seeded placement inside equivalent room groups. Taking an item denies it to the
opponent. Nothing respawns during a match, including consumed items.

Write a builder-owned manifest specifying every item template, slot, restrictions,
stats, charges, quantity, placement group and total budget. Avoid permanent quest
items, artifacts and economy rewards. All generated objects, containers, coin-like
objects and summons carry match identity; none can survive cleanup or enter ordinary
player, pet, room, corpse, shop or world-recovery saves.

At overtime, keep equipped/carried match gear and owned summons, cancel effects in
abandoned rooms, and move the fighters to distinct validated positions. Close access
to the larger map and discard its remaining floor loot. Fleeing stays possible inside
the nine-room section. Cleanup traverses nested containers and all match rooms,
including rooms abandoned at overtime.

### Public viewing and communication

Observation is a release requirement. A player at level 2 can watch either fighter
from any normal world location and switch perspectives without traveling to a
gallery, joining the queue, sharing a racewar side, or obtaining staff permission.
Every eligible connected player may subscribe; do not impose a small audience cap.
The fighter's participation makes the public match feed available automatically.
`arena filter` changes tactical detail, never whether the duel can be watched.

Each spectator keeps control of their own body and commands. Watching does not move
them, protect them, transfer control of the combatant, or make them a target in the
arena. Clearly prefix feed lines with Arena and the watched fighter. Local damage
automatically ends viewing with a message; logout, extraction, a level drop below
2, and match completion also detach cleanly. Resolve subscriptions by match ID and
player/runtime identity, never by a dangling descriptor or character pointer.

Deliver both offensive and defensive combat output, spell/skill outcomes, selected
gameplay commands, gear changes and recovery feedback from the chosen perspective.
Publish commands after alias expansion and command resolution from an explicit
allowlist; do not echo arbitrary input, chat arguments, malformed commands or command
history. Render the actual fighter-visible result: observation must not grant extra
hidden-target detection. Allowlisted feedback is captured at gameplay output sites
or through explicit Arena output context, not by scraping the final socket stream.
Publish before any descriptor-only delivery guard so a linkdead fighter still has
a feed. A connection is required for the viewer, not for the watched combatant.

The default filter hides room titles/descriptions/exits, maps, detailed inspections,
personal statistics and prompts in that perspective. Turning it off permits those
Arena tactical details. Private tells, whispers, group/guild/alliance messages,
account/password output, staff output, unrelated room output and administrative
commands remain excluded in both modes. No private conversation is recorded for
later replay. This follows [Duris's privacy decision](../adr/0003-player-privacy-chat-snoop-addresses.md).

`arena status` deliberately exposes both fighters' current/max HP, mana or applicable
class resources, movement, phase and timer to level-2 observers even when a feed is
filtered. Document this separate public surface; filtering is not a promise that
vitals are secret. Do not expose map coordinates, private inventory or world location
through status. Disconnect does not remove a contestant's public status/feed.

Use existing output categories and recipient color preferences. Exclude GMCP and
other protocol packets belonging to the combatant; a viewer's own gauges must still
describe their own character. The complete experience must work in plain telnet;
special client support is not required. Do not reuse immortal snoop, which forwards
private output and has a different authority and audit model.

Allow instantaneous viewing; do not add a delay or replay service. Outside coaching
and collusion are conduct issues. Fighters cannot use the spectator commands during
their own match, and outside commands cannot affect the battle. Announcements are
public, separately opt-in, and independent of the level-20 discussion channel.
Use existing mutes, message limits and privacy rules for discussion, without making
all world chat cross-racewar.

Keep feed work bounded to current subscribers. Generate each perspective's content
once and render per recipient. Reuse output-queue limits; detach a slow subscriber
with an explanation instead of allowing its buffer to grow or delaying combat.
Test fan-out at the server's configured connection limit, including slow readers.

### Wagers and payouts

Wagering uses in-game currency only. Players at level 2 may stake carried money
during preparation, once both fighters and the map are public. Use copper internally
with checked 64-bit arithmetic and the existing denomination conversions. Proposed
limits are a minimum of one gold and a total maximum of 100 platinum per account per
match. Reject zero, negative, malformed, overflowing and unaffordable amounts.

An account chooses one side per match and may add to that side before the cutoff;
it cannot switch sides, cancel a valid stake, or evade the cap through another
character. Neither combatant's account may wager on its match. Show current pools
and the caller's exposure, with projected returns labeled as changeable until betting
closes. No fixed odds are promised. Close betting before the combat state transition
permits an attack; reject late input even if it was queued earlier.

For a decisive result, let `L` be losing stakes, `W` winning stakes, and `b` an
individual winning stake. If both sides have stakes:

```text
fighter award = floor(L / 10)
winning bettors' profit pool = L - fighter award
bettor gross return = b + proportional share of the profit pool
```

Return winning principal explicitly. Split profit by stake, floor each share in
copper, then distribute remaining copper by largest fractional remainder, breaking
ties by stable wager ID. Use overflow-safe multiply/divide. This preserves every
copper and implements the 10/90 split to integer precision. With losing stakes
2,000 gold, winning stakes 4,000 gold, and a winning stake of 1,000 gold, the fighter
receives 200 gold and that bettor receives 1,450 gold including principal.

If either side has no stake, void the pool and return all principal with no fighter
award. Draws, preparation cancellations, staff aborts and server interruptions also
refund principal. A valid combat or overtime forfeit settles as a loss. No currency
is created from an empty pool and no abandoned credit is silently destroyed.

Hold stakes in an Arena-owned pool and create payable credits at settlement.
Automatically offer delivery to online recipients; retain undeliverable or offline
credits for login and `arena claim`. Check balance capacity before consuming a
credit; a full wallet leaves it pending. Claims belong to the wagering character,
with account identity retained for the per-match rules. Use stable match/result and
credit identifiers so repeated completion calls cannot pay twice.

### Ratings and champion rewards

Start at 1,000 points. Keep a rolling 30-day window of completed rated results,
recent wins/losses, kills/defeats, draws, and the last completed-match timestamp in
UTC. Show lifetime totals separately if retained; do not label them as rolling
totals. A forfeit counts as a win/loss but not a combat kill/death. An abort is
neither; a draw is neither a win nor a loss.

The original rating formula is unknown. Use this explicit Duris default to preserve
its documented incentives. `Rw` and `Rl` are winner and loser ratings immediately
before the result:

```text
if Rw > Rl: delta = 0
otherwise: delta = min(Rl, 20 + min(80, floor((Rl - Rw) / 20)))
winner change = +delta
loser change  = -delta
current points = max(0, 1000 + sum(unexpired signed result changes))
```

Equal-rated fighters with at least 20 points transfer 20; an upset gains more, up to
100. Defeating a lower-rated opponent earns no points, and losing to a higher-rated
opponent costs
none. Persist the signed changes at settlement. Expiry removes those changes; it
does not replay old matches against altered opponent ratings. At 30 days a result
leaves the window; a player without a rated result in that window returns to 1,000
and leaves the active champion list. Recompute expiry before pairing or serving
standings. Schedule maintenance for the next result expiration so online champion
entitlements also change at the 30-day boundary without waiting for a command.

Sort by points descending, recent wins descending, recent losses ascending, then
oldest last completed match and stable player ID. The `time` sort uses newest match
first. Champion eligibility requires level 20, at least one rated result inside the
window, no competition suspension, and the highest-ranked eligible character on
that account. Award up to twelve titles; do not fill empty positions with inactive
characters. The first is **Arena Grand Champion**, the rest **Arena Champion**.

| Rank | Bonus HP | Rank | Bonus HP |
| --- | --- | --- | --- |
| 1 | 35 | 7 | 20 |
| 2 | 30 | 8 | 18 |
| 3 | 28 | 9 | 16 |
| 4 | 26 | 10 | 14 |
| 5 | 24 | 11 | 12 |
| 6 | 22 | 12 | 10 |

Use the researched HP table as the initial Duris reward values. Apply the bonus as
a derived entitlement outside matches; never permanently increment base HP. Clamp
current HP when the bonus disappears; gaining a title must not refill missing HP.
Do not overwrite a player's custom title: expose a separate champion badge in
appropriate name/score/standing output. Rank changes, expiry, level changes,
suspension and login recalculate titles, HP and mount eligibility.

Champions can call a free, flying, rideable companion quickly through `arena mount`.
Provide the four thematic types: coatyl for arcane/psionic classes, pegasus for
divine/nature classes, stone falcon for stealth classes, and roc for martial classes.
Create an explicit mapping for every current Duris class and multiclass combination,
using the character's primary class to break mixed-family cases. Names and exact
mount statistics are builder content, while free summoning, flight, riding, and
combat support are required behavior. Use ordinary Duris follower combat to let
them help against dragon-type NPCs where legal; do not import Medievia's separate
dragon travel/combat systems or bypass Duris targeting rules.

Allow one reward mount per owner. Prevent trading, permanent gear storage, loot,
EXP farming, or Arena admission of that mount. Losing entitlement revokes it; if
the owner is riding, dismount through a safe return path rather than leaving them
falling or stuck in invalid terrain. Recheck on each call and login; dismiss on
logout. Persist entitlement through ranking, not duplicate permanent mount grants.

## Persistence and recovery

Follow [ADR 0002](../adr/0002-persistence-reset-memory-is-the-authority.md), the
[player save pipeline](../persistence/PLAYER_SAVE_PIPELINE.md), and
[money handling](../persistence/CRITICAL_COMMAND_PIPELINE.md#money-lives-in-memory).
The game thread owns match state. The existing single writer persists immutable
captures in order; there are no synchronous database queries in the game loop, no
new journal, no second writer, and no database approval required for combat or death.

| State | Ownership and persistence |
| --- | --- |
| Queue, timers, subscriptions | Memory only; reset on reboot/copyover |
| Active combat state and generated gear | Memory only; do not resume an interrupted fight |
| Original possessions and permanent character view | Character-owned stowed objects and entry-state overlay; existing player saves capture this canonical view during a match |
| Match header and result | Stable match ID, participants, phase marker, map/seed, timestamps, reason, pre-result ratings and signed changes |
| Wagers and credits | Match-owned escrow, stake owner/account, side, amount, payable/consumed state; saved through the same writer |
| Competitor metadata | Player-save field for last completed match, retained after old history is pruned so a veteran does not become a first-time entrant |
| Standings and champion privileges | Derive from results; cache in memory; no independent source of truth for the HP bonus |
| Preferences | Ordinary player save components |

Do not suppress whole player saves while fighting. Add a deliberate capture path
that reads original items, affects, resources and return location while retaining
live permanent preferences and wallet changes. Document every overlaid field and
test both manual and automatic saves. An ordinary character load must materialize
the permanent state, never a naked fighter, temporary gear, or a stranded Arena
location. Cleanup and capture must cover morphs, nested containers, pet objects and
world recovery, not just the top-level inventory.

Use additive, guarded migrations under `migrations/` for match, wager and credit
records, and extend the maintained flat-file backend using existing repository
patterns. Load the small active ranking window at boot and refresh it in memory.
Paginate older history through worker reads. Store a match result, its rating changes
and the resulting credits together within the Arena domain's write; guard the final
state so it cannot produce a second outcome. Do not mutate offline wallets with
ad hoc SQL.

Money moves in memory, with the owner it leaves saved first: the player's wallet
before escrow, and a consumed credit before its recipient's wallet. Preserve that
ordering when saves coalesce. Match outcomes must be stable before their dependent
credits can be consumed. Reuse the existing auction/collector claim patterns where
they fit; do not reuse obsolete currency-ledger assumptions. Report an uncertain
commit outcome and reconcile durable state before retrying a payout.

Duris accepts the existing checkpoint loss window on an abrupt crash. This design
must not promise atomic recovery of every last command or exactly-once delivery
across all storage failures. Written escrow is refundable; a crash between an
ordered wallet debit and escrow save may lose that unsaved stake, just as existing
money transfers can. Recovery must never recreate coins from an already consumed
credit or pay a match twice. If eliminating even that bounded loss becomes a
requirement, it needs a separate persistence decision rather than a hidden journal.

| Interruption | Required result |
| --- | --- |
| Disconnect while queued | Remove request; no result or penalty |
| Disconnect during preparation | Cancel the match, restore both, refund all accepted stakes from the live pool; no rating change |
| Disconnect during combat/overtime | Fighter stays vulnerable, timers continue, and reconnect reattaches the same participant |
| Ordinary idle removal during combat/overtime | Resolve a forfeit before normal idle extraction and restore the permanent view |
| Voluntary quit/camp/rent during combat | Explain that leaving is blocked; no escape or implicit draw |
| Staff abort, forced extraction or relocation | Stop battle, restore both, refund stakes, record reason, no rated result |
| Clean shutdown or copyover | Abort before final character capture, queue restorations/refunds, use existing bounded drain; no live match crosses the boundary |
| Abrupt restart | Discard transient combat, load permanent characters, mark unfinished recorded matches aborted and turn their remaining escrow into refund credits |
| Repeated completion or recovery callback | Same result/credit state; no extra ratings, mounts or money |
| Missing map/return content | Close admissions; safely restore to validated hometown fallbacks and report affected match IDs |

Keep settled results for 90 days for recent history and contest review; ratings use
only 30 days. Retain unpaid credits and their settlement evidence until claimed or
handled by the existing account-deletion policy. Add Arena data to the lifecycle,
deletion and export manifests. On a pwipe, reset ranks and privileges with characters;
make wager/credit handling explicit in that lifecycle instead of leaving orphaned
balances. Store operational IDs and outcomes, not private chat, raw commands, or
network addresses.

## Implementation sequence and proof

Each phase has a concrete exit condition. Keep admissions disabled until every phase
passes; internal staging can exercise partial work without calling the full feature
complete. Extend relevant existing tests before creating new harnesses.

### Phase 1 Commands and integration contract

Implement public command parsing, per-command level checks, staff permissions,
legacy routing, and a disabled-by-default match owner. Define membership separately
from the room flag. Reserve world ranges and settle the concrete safe entry/return
rooms. Record the baseline character fields and all affected death, reward,
targeting, movement, item-transfer and extraction paths.

Proof: level 1/2/19/20 boundary checks through the real interpreter; NPC/immortal and
same-account cases; ordinary arena rooms do not create a ranked match; legacy staff
commands retain permissions and no old timer starts accidentally.

### Phase 2 Temporary state and world content

Build both maps, the registrar/gallery, starter kits and equipment manifest. Implement
the character overlay, stowed inventory, temporary object identity, capture rules,
restoration and map validation before enabling combat. Integrate removal of champion
and applicable guild HP bonuses.

Proof: enter and return with nested containers, unusual equipment, affects, memorized
spells and different class resources; save/reload during preparation; no generated
items enter any persistence owner; no original item changes owner. Validate routes,
all item templates, equivalent placement opportunities, every class's usable starter
kit and both nine-room overtime graphs.

### Phase 3 Pairing and full duel lifecycle

Implement the 90-second queue, deterministic ties, automatic map selection,
preparation, combat, overtime, lethal outcome interception, draws, linkdead play and
idle forfeits. Use the scheduled game pulse and existing combat mechanics. Add the
boundary and ordinary reward guards at the shared paths identified in phase 1.

Proof: a real two-character duel from `arena join` through restoration on each map;
same-side and opposing-side pairings, underfilled queue, unselected applicants,
last-moment invalidation, preparation hostility attempts, flee/pursuit/recovery,
overtime, timeout, poison/self/hazard
deaths, direct death effects, class summons and simultaneous defeat. Check that HP,
items, EXP, skills, frags, epic points, hardcore counters and ordinary kill rewards
obey their contracts.

### Phase 4 Public observation and channels

Implement automatic combatant feeds, attach/switch/detach, default filtering, public
vitals, color-safe output, announcements and competitor discussion. Add explicit
public output provenance at every required combat/action/inspection site. Keep
privacy and gameplay authority separate from visual formatting.

Proof: level-2 and level-19 spectators on both racewar sides and in distant rooms can
watch either fighter, switch, and stop; level 1 cannot. Confirm offensive/defensive
combat, cast outcomes, equipment and recovery feedback with filters on/off. Send
private messages, account commands, aliases and unknown commands during the match
and verify exclusion. Test local damage, watched-player disconnect/reconnect,
shapechange, extraction, match end, plain telnet, disabled color and unchanged own
GMCP gauges. Load-test all configured connection slots, including slow readers,
without unbounded memory or delayed combat ticks.

### Phase 5 Wagering and settlement

Implement pool display, denomination parsing, debit/escrow, account limits, cutoff,
10/90 allocation, principal return, refunds and online/offline credits. Wire captures
and delivery ordering to the single writer. Keep disabled/unavailable admission
responses distinct from rejected monetary input.

Proof: verify balances before and after the numerical example, tiny pools and
rounding, one-sided pools, repeated stakes, alternate characters, fighter/staff
exclusion, cutoff race, insufficient funds, integer bounds, full wallets, offline
winners, aborts and duplicate completion. Assert conservation of the entire pool.
Interrupt writes at debit/escrow and credit/wallet boundaries on both persistence
backends; prove source-first loss behavior and absence of duplicate money.

### Phase 6 Rankings and champion benefits

Implement signed rating changes, UTC result history, expiry, sorts, account-qualified
top twelve, persistent last-match metadata, derived HP, visible badges and
class-mapped flying mounts. Wire entitlement updates to results, login, expiry,
level and suspension changes.

Proof: equal/favored/upset outcomes, zero floor, result expiry and exact 30-day
boundary, sort ties, inactivity reset, fewer than twelve entrants, duplicate accounts,
forfeits/draws/aborts, save/restart and deletion. Verify every HP rank, no in-match
bonus, no HP accumulation or healing from recalculation, all class mount mappings,
free calls, flight/combat support, duplicate summons and safe revocation while riding.

### Phase 7 Recovery and operations

Implement staff abort/inspect/on/off and suspend/resume competition through existing
staff discipline mechanisms. Record reasons and outcomes. Finish migration/bootstrap,
flat-file, lifecycle/export/deletion, startup reconciliation and copyover/shutdown
integration. Log unexpected invariant failures with match IDs and provide a clear
operational disable path.

Proof: force disconnect, idle, extraction, abort, copyover, cold restart and storage
failure during every phase; reconnect both contestants and bettors afterward. Verify
permanent inventory and equipment, correct return locations, no match gear/summons,
no stale events or observers, a single result, correct pending credits and a usable
next match. Exercise missing rooms/templates and repeat recovery. Confirm ordinary
death and legacy arenas still work, and the game loop performs no database query.

### Phase 8 Help and release qualification

Write help for Arena, watching/filtering, wagers/claims, ranking/rewards and conduct
in [help_index](../../lib/information/help_index), plus operator recovery instructions.
Cover live access thresholds, queue clearing, both real entrances, timers, public
vitals, privacy boundaries, full payout examples, disconnect consequences and
checkpoint loss behavior. Explain that throwing matches and outside interference
are prohibited under Duris rules; do not import Medievia's entire automation policy.

Run `./scripts/format.sh --check` and `make -C src` after C/C++ changes, focused
behavioral harnesses, and disposable MariaDB/flat-file journeys using
[TESTING.md](../guides/TESTING.md). Register new database tests with the existing
runner and apply migrations twice in the disposable environment. Use local evidence;
do not wait for CI to prove gameplay. This plan-only change needs documentation
checks, not a server build.

Final journey: two eligible ordinary characters join, collect and fight; level-2
spectators from opposing sides and remote rooms watch both perspectives and place
wagers; exercise overtime; one fighter wins; both return with their permanent state;
money, standings and champion entitlements update; log out and back in, then restart
and repeat. Also run a draw and an aborted match. Preserve redacted evidence of
commands, balances, item IDs, rank changes and recovery outcomes.

Release is complete only when every feature row and phase exit condition has
behavioral evidence. Rollback means disabling new matches, aborting/restoring any
active pair, and preserving pending claims and results; do not drop Arena tables or
discard escrow as part of disabling the feature.

## Review points before implementation

The plan supplies defaults so missing Medievia internals do not block a Duris design.
Review the material balance choices together: actual-level matchmaking, the
180/600/300-second phase durations, 32 collectible items, rating delta formula,
one-account champion qualification, wager limits, and the HP/mount reward strength.
Changing those values must not remove level-2 public observation, level-20 entry, or
any required feature from the implementation sequence.

The design uses one active match and existing combat, world loading, output rendering,
currency and persistence paths. Separate viewing and restoration code remain
necessary because staff snoop exposes private data and ordinary saves/death paths
would otherwise persist temporary state or apply world penalties. Additional modes,
brackets, seasons, replay storage, web spectators and generalized services have no
requirement in this scope.
