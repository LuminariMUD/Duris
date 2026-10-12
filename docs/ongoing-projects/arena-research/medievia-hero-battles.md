# Medievia Hero Battles mechanics and player experience

Research date: 12 October 2026.

Hero Battles are Medievia's public, ranked, one-on-one competition for heroes. Their distinctive combination is arena equipment, pursuit through connected rooms, resource management, public viewing through a combatant's perspective, and a betting pool that pays the victorious fighter as well as successful spectators. The official feature description presents unusually powerful equipment and two arenas with different tactics. [Hero Battles feature](https://www.medievia.com/f/hbattles.html)

The experience can be reconstructed substantially from the published help, historical player guides, interviews, and a live level-1/level-2 access check on 12 October 2026. **A complete contemporary specification cannot be recovered from these sources:** exact arena maps, the item catalogue, several timers, rating arithmetic, and exceptional settlement behavior remain unresolved. Live testing confirmed entry restrictions and exposed obsolete navigation instructions in the help. No actual match was observed: the server reported no battle and no available Mindlink feeds at the checks recorded below.

The scope is Hero Battles. Adversary, ordinary arena PK quests, CPK Duel, and Hero Hunt are separate systems. The public Medievia IV source archive does not supply the missing Hero Battle implementation.

## Live access check on 12 October 2026

Arvenyl was created as a level-1 cleric and then advanced to level 2. A valid email was submitted, but no verification code was entered; the game nevertheless admitted the character and allowed the checks below. Level 2 persisted through logout and a fresh login; the character was then logged out cleanly. Live quit help warns that level-1 characters do not save. Login details and the email address are excluded from these research artifacts.

| Test | Direct result |
| --- | --- |
| Level 1: `LINK`, `MINDLINK` | Both reported as unknown commands. |
| Level 1: `HEROBATTLE`, `HEROSTATUS` | Recognized; reported no battle in progress. |
| Level 1: `HEROLIST P` | Recognized; displayed the ranked competitors. |
| Level 2: `LINK` | Entered MedLink successfully. |
| Level 2: `MINDLINK` | Recognized; listed no available feeds. |
| Old registration route | East then north reached the Mudslinger Rumor Mill, with no sign; `CHALLENGE` failed there. |
| Actual registration route | **South, south, down** from Welcome to MedLink reached **The Hero's Challenge**. |
| `CHALLENGE` at the actual room | Pili rejected participation because the character was not a hero. |
| `ASK`, then `WITHDRAW` there | No hero ranking; no challenge had been registered. |
| `LINK R` inside MedLink | Refused the old shortcut and required ordinary movement. |

These checks establish that this fresh level-1 character could neither reach MedLink normally nor invoke Mindlink. Level 2 unlocked both commands, but did **not** unlock competition. Spectator command access was confirmed; an actual viewing session remains untested because no feed was available. The [live evidence ledger](medievia-hero-battles-live.md) records timestamps and distinguishes observations from help statements.

## Evidence and historical timeline

Different eras must remain distinguishable:

| Evidence | Date or era | What it establishes |
| --- | --- | --- |
| [Official game history](https://www.medievia.com/start.html) | Medievia IV opened 1 February 1996 | Hero Battles and Mindlink were additions in **4.1**, after the initial 4.0 release. The page does not give a separate 4.1 launch date. |
| [Torx interview](https://www.medievia.com/ms/inttorx.html) | Published 30 October 2000; interview 23 October | An established competitive scene: admired champions, spectators wagering, and competition for places in the battle queue. Torx reported over 70 battles in one month. |
| [Allyrellia interview](https://www.medievia.com/ms/intally.html) | Published 18 February 2001; interview 5 February | A participant valued the competition because personal equipment wealth mattered less than speed, skill, and luck. This is player testimony, not proof of identical starting statistics. |
| [Izz's guide](https://www.medievia.com/ms/herob.html) | 28 December 2002 | Detailed account of the staff-run period, preparation, movement, and equipment tactics. |
| [Fayla interview](https://www.medievia.com/ms/intfayla.html) | 17 August 2004 | The developer describes automated Hero Battles as recently completed; the interviewer had already tried them. Automation was available by this date, not necessarily first released on it. |
| [Zamerati interview](https://www.medievia.com/ms/lorintzamerati.html) | 3 May 2009 | A novice's firsthand description of preparation and overtime, with approximate figures and a tracking claim that conflicts with the older guide. |
| Published help pages | Retrieved in October 2026; revision dates unspecified | Rules reference; several core pages were also checked in-game. Navigation can be obsolete even in the live help. |
| [Live access checks](medievia-hero-battles-live.md) | 12 October 2026 | Level threshold, relocated registration, hero-only participation, command output, and battle/feed availability. |

The apparent conflict between old advice to wait for a god to organize a match and today's documented automated registration is therefore understandable. An old feature page's reference to a choice of arenas also does not override the automated system's explicit restriction on player selection.

## Eligibility and arriving at the arena

The hero progression is four completed classes and total level 124. Hero status is a privilege that can be lost through misconduct; the help does not establish whether level alone passes every battle-entry check. The four classes are warrior, thief, mage, and cleric. [HERO](https://www.medievia.com/help/HERO.html), [Becoming a Hero](https://www.medievia.com/hero.html)

`LINK` enters MedLink, the game's social area, starting at level 2 in the live test. Normal entry from NPK or CPK is documented as restricted, with exceptions for one's own gohome or current clan hall. The help still describes `LINK R` as a return shortcut, but the running game explicitly refused that shortcut in the new MedLink. [MEDLINK](https://www.medievia.com/help/MEDLINK.html), [live navigation checks](medievia-hero-battles-live.md#medlink-navigation)

The **live-verified route**, starting outside MedLink, is:

```text
link
south
south
down
look
challenge
```

Wait for the initial LINK transit to finish before moving. The intermediate rooms are **The Descent to Adversary** and **Above the Hero Arena**. The destination is **The Hero's Challenge**, whose banner lists `CHALLENGE`, `WITHDRAW`, and `ASK`. `LOOK SIGN` found no sign there. Its distinguished imp is **Pili, the steward of HeroBattles**. His level-2 challenge rejection was explicit: “You are not a hero and therefore cannot participate in HeroBattles.” [Live registration checks](medievia-hero-battles-live.md#registration-and-eligibility)

Both web and live `HELP AUTO_HB` still give the obsolete east/north route and sign instruction. That help documents requests/withdrawals on HB, no player choice of opponent or arena, and one battle at a time. Those match-management rules were read live, not exercised with qualified heroes. [AUTO_HB](https://www.medievia.com/help/AUTO_HB.html)

### Matchmaking

After the first request, a **90-second window** precedes pairing. Among applicants, the system selects the hero whose last battle was longest ago, then that hero's nearest neighbor in rating. Existing requests are cleared when the battle starts; those wanting the next match must register again after it ends. Whisking inside the arena causes an automatic loss; disconnection leaves the fighter attackable. Intentionally losing is forbidden. [AUTO_HB](https://www.medievia.com/help/AUTO_HB.html)

Unspecified cases include equal-distance rating ties, never-before-seen fighters, insufficient applicants at the deadline, leaving the registration room, and requests made while a battle is already running. Queue priority is not documented as first-come-first-served.

## Preparation and the equipment race

**Historical mechanics, reported by Izz in 2002:** an initial phase disables attacks while contestants gather roughly 20–50 items. His advice is to collect aggressively, identify unfamiliar finds, memorize routes, and review personal logs. Equipment can be denied to an opponent by taking it first. He recommends HP/mana gear early, then changing toward hitroll, damroll, and saving-spell equipment later. Fire rooms make some flee routes dangerous. He says arena tracking carries no movement lag. Sanctuary, quickness, armor, and alignment protection need renewal. The guide describes no permanent loss of equipment, gold, or levels from participating. That protection does not imply that a spectator's losing wager is refunded. [The Basics of Herobattling](https://www.medievia.com/ms/herob.html)

**A later firsthand account:** Zamerati estimated **3–5 minutes** for collection, reported approximately **1,600 HP and 800 mana**, and found identifying and choosing equipment the hardest part. These are one novice's estimate and achieved statistics, not verified timers, targets, or caps. His opponent deliberately allowed extra learning time. He described overtime closing off rooms and limiting movement to a **3×3, nine-room area**, where fleeing remained possible. [Zamerati interview](https://www.medievia.com/ms/lorintzamerati.html)

The evidence supports arena-specific equipment acquisition. It does **not** establish exactly how normal inventory is stored, whether every entrant receives starter items, whether both players have access to identical drops, whether placements are random, or how an interrupted match restores possessions. “Equal opportunity” should not be silently converted into normalized attributes or identical loadouts.

### Surviving examples of arena equipment

The official tour depicts a lightsaber, white chef's hat, stompers, silver trinket, and a bottled burp used for healing. It also depicts a secret floor panel, vertical movement, and a sequence of harm spells, image removal, backstabs, fireshield retaliation, healing, fleeing, and a fatal attack while recovering. The protagonist returns to the ordinary world and resolves to learn by watching other battles. These are illustrative narrative details; the tour is **not an item database or a captured match log**. No exact item statistics follow from it. [Hero Battle tour](https://www.medievia.com/t/herobattle.html)

## Combat and movement

The published sources do not describe a separate turn-selection interface. Fighters use ordinary MUD commands under combat wait states, while movement and recovery create opportunities between exchanges. The general skill descriptions below explain those interactions; unlisted arena-specific overrides remain possible.

### Backstab and retaliation

`BACKSTAB`, abbreviated `BS`, initiates combat and requires a main-hand weapon flagged as a backstabber. A current thief with warrior progression can attempt up to three stabs; characters that previously completed thief can attempt up to two. Success, damage band, and multiplier involve separate rolls. Sneaking affects detection; hitroll influences additional attempts and damage rolls; target AC affects damage-band selection up to the documented −100 limit. The attacker waits **three combat rounds** after either success or failure. This creates a recovery interval for the defender. [BACKSTAB](https://www.medievia.com/help/BACKSTAB.html)

`BASH` stuns the victim for one round and imposes a two-round wait on the user, whether it hits or misses. It needs a wielded weapon; current warriors have better success. These timings are ordinary skill rules, not separately measured Hero Battle timings. [BASH](https://www.medievia.com/help/BASH.html)

### Fleeing and knowing the map

`FLEE` selects a random escape direction and may fail; fewer exits increase that risk. Rage can block fleeing, and its melee attacks defeat automatic wimpy fleeing. Thus a retreat is not the same as choosing an exit directly. [FLEE](https://www.medievia.com/help/FLEE.html)

Ordinary `TRACK <name>` supplies location information as the player moves; `TRACK OFF` stops it. General help says tracking slows characters who are not current thieves. [TRACK](https://www.medievia.com/help/TRACK.html)

**Tracking conflict:** the 2002 guide claims an arena exemption, whereas Zamerati avoided tracking in overtime because he believed it slowed movement. The later speaker was a novice, so his statement cannot prove a code change. The interaction among current class, arena phase, and tracking needs direct verification; neither blanket “always free” nor “always slows you” is established for the current server.

### Protection and resource management

| Mechanic | Published general behavior | Relevance to a duel |
| --- | --- | --- |
| [Sanctuary](https://www.medievia.com/help/SPELL_SANCTUARY.html) | Halves physical and magical damage, with the stated dragon-breath exception; costs 75 mana and lasts 2–6 ticks according to level. | A lapse sharply increases exposure to burst damage. |
| [Phantasmal image](https://www.medievia.com/help/SPELL_PHANTASMALIMAGE.html) | Current mage 27+ or cleric 28+; costs 75 mana, lasts 12 ticks. Images absorb hits and disappear on damage; mages can produce more. A bash hitting an image destroys it without knocking down the caster. | Some attacks consume defenses instead of injuring or disabling the player. |
| [Manashield](https://www.medievia.com/help/SPELL_MANASHIELD.html) | Current mage 19+; 7 mana, three ticks. Redirects damage into mana at 1–2 times HP damage and ends when mana reaches one-third of maximum; malediction neutralizes it. | Survival can consume the same resource needed for offense and recovery. |
| [Quickness](https://www.medievia.com/help/SPELL_QUICKNESS.html) | Improves travel without exhausting breath; costs 50 mana, duration level/2 + 5. | Helps movement endurance. This source does not establish extra melee attacks. |
| [Meditate](https://www.medievia.com/help/MEDITATE.html) | Warrior/thief recovery of HP and vitality consumes movement; requires resting alone. | Breaking contact may enable recovery, if the opponent cannot immediately find you. |
| [Ticks](https://www.medievia.com/help/TICK.html) | Spell duration and regeneration use ticks; posture affects recovery. The help does not give a fixed real-time duration. | “Three ticks” must not be translated into a guessed number of seconds. |
| [Shield room](https://www.medievia.com/help/SPELL_SHIELDROOM.html) | Described as excluding mobs, with exceptions for powerful ones. | It is not documented as a barrier against a pursuing player. |

Class history matters alongside current class: multiclassing retains earlier skills and attributes but resets HP, mana, and movement for the new class. That general progression rule does not specify arena normalization. [MULTICLASS](https://www.medievia.com/help/MULTICLASS.html)

### Historical tactics and the learning curve

Rika's July 2000 PK guide describes using an opponent's wait state to flee, heal, orient, and return; replacing HP gear with offensive gear after taking damage; and disrupting predictable backstab cycles with images, early engagement, blindness, or debuffs. It emphasizes knowing the terrain and using spell-bearing items to preserve mana or recover without leaving combat. These are historical tactical observations, not guaranteed present-day formulas or an optimal build. [Advanced Player Killing](https://www.medievia.com/ms/advpk.html)

The player experience therefore has several simultaneous demands: interpreting fast text, knowing where the next movement will lead, recognizing items immediately, noticing expiring protections, and deciding whether the next available action should heal, chase, disable, or attack. This is a synthesis of the preceding mechanics, not evidence of an undocumented combat subsystem.

## Overtime and ending a match

The core help says a battle ends when a hero dies or a god aborts it. Contestants cannot leave the battle zone. If a match runs too long, overtime moves combat into a smaller arena. Its trigger time, warning interval, selection of destination rooms, and preservation of floor objects are not specified. [HEROBATTLE](https://www.medievia.com/help/HEROBATTLE.html)

The 2009 account's closing rooms and nine-room destination add useful historical detail, but do not establish that every arena or current overtime instance uses that geometry. No published evidence found here proves a hard overall timeout, forced draw, damage escalation, or sudden-death debuff.

“Whisking” means an idle character being moved to the Void; it is distinct from losing a network connection. The general idle help gives no exact inactivity timer. [IDLE](https://www.medievia.com/help/IDLE.html)

Post-match locations, full healing, spell restoration, equipment cleanup, restart recovery, and automatic cancellation refunds require stronger evidence than the narrative tour's return to the ordinary world.

## Announcements and spectator experience

There are two related communication surfaces:

- `HB` is the hero discussion/arrangement channel. Its help says staff must enable it, that typing it alone reports availability and listening gods, and that gagged heroes cannot speak there. This may preserve staff-run-era behavior; automation's reliance on HB does not prove the manual channel gate disappeared. [HB](https://www.medievia.com/help/HB.html)
- The `HEROBATTLE` setting in `SETCOMM` controls the yellow public battle announcements. `HEROBATTLE` itself displays ongoing battle statistics. Warnings precede combat. [HEROBATTLE](https://www.medievia.com/help/HEROBATTLE.html)

`HEROSTATUS <your name>` reports one's own rating/rank. During a match, any player can use bare `HEROSTATUS` for both fighters' vital statistics. This is a distinct documented information surface from the spectator feed. [HEROSTATUS](https://www.medievia.com/help/HEROSTATUS.html)

On the fresh character, **Hero Battle Announcements were off** in `SETCOMM`. `SETCOMM 7` enabled them and the follow-up listing confirmed the change. Bare `HB` at level 1 unexpectedly performed a humble-bow social, so it is not a reliable low-level availability probe. The live help restricts the HB discussion channel to heroes. [Live command checks](medievia-hero-battles-live.md#spectator-commands-and-announcements)

### Mindlink

| Command | Effect |
| --- | --- |
| `MINDLINK` | Lists available sources, activity descriptions, and color status. |
| `MINDLINK <name>` | Watches an available player's perspective. |
| `MINDLINK DONE` | Ends viewing. |
| `MINDLINK GAG` | Source player toggles the feed's information filter. |

The feed can include commands, combat, tells, and typing mistakes. **Hero Battles start with the gag enabled:** it hides statistics, room names, the status prompt, and exits. A fighter may disable it. Other kinds of Mindlink need not have that default. Color settings can also affect rendering: a viewer without color enabled may see escape sequences from a colored source. [MINDLINK](https://www.medievia.com/help/MINDLINK.html)

The filter makes watching different from controlling a transparent tactical map. However, it does not establish complete location secrecy: other text may reveal clues, and the relationship between gagged output and `HEROSTATUS` is not fully documented. Spectator delay, feed switching during combat, and controls against outside coaching remain unverified.

The live level-1 rejection and level-2 success qualify the help's broad statement that any player may watch: this character needed level 2 simply to invoke `MINDLINK`. With no active feed, successful connection to a fighter could not be tested. [Live level comparison](medievia-hero-battles-live.md#level-1-and-level-2)

For modern client context, MedUI supplies a separate communications window, map window, vital gauges, and buff display. Its README does not promise special handling of a Mindlinked fighter's output. A spectator should not assume those gauges track the watched hero correctly. [MedUI README](https://github.com/jmckisson/MedUI/blob/master/README.md)

## Wagering and fighter income

`HEROWAGER <heroname> <amount>` selects a winner and an in-game gold stake. Betting closes **before combat begins**, despite the help's opening shorthand about a battle “starting.” The pool uses proportional payouts, not a fixed bookmaker price. Of the losing side's stakes, **10% goes to the victorious fighter** and **90% goes to bettors on that fighter**, proportional to their stakes. [HEROWAGER](https://www.medievia.com/help/HEROWAGER.html)

Let `L` be losing stakes, `W` winning stakes, and `b` one successful bettor's stake:

```text
fighter award = 0.10 × L
bettor share  = 0.90 × L × b / W
```

For `L=2,000`, `W=4,000`, and `b=1,000`, the fighter receives 200 and that bettor's share is 450. The help's worked example distributes the losing pool and loses a few coins to rounding. It does not explicitly specify the winning stake's return accounting. A gross return of 1,450 in this example assumes the 1,000 stake is returned; verify that separately. [HEROWAGER](https://www.medievia.com/help/HEROWAGER.html)

Unknown settlement cases include a zero-sided pool, minimum/maximum stakes, repeated bets, side changes, wagering by contestants, bank versus carried gold, death/disconnection of a bettor, and abort/reboot refunds. None should be filled in from the old source archive's casino code.

## Rankings and persistence

`HEROLIST <sortby>` supports `P`oints, `W`ins, `L`osses, and `T`ime. Fighters begin with a **1,000** rating. Battles older than **30 days** leave the ranking equation; someone inactive for more than 30 days has points reset. This is a rolling calculation, not a simultaneous season reset. The help does not explicitly give the inactive reset value or the precise recalculation method. [HEROLIST](https://www.medievia.com/help/HEROLIST.html)

| Outcome | Published rating effect |
| --- | --- |
| Beat a lower-ranked opponent | No points gained. |
| Lose to a higher-ranked opponent | No points lost. |
| Beat a higher-ranked or equal-point opponent | Points and rank can improve. |
| Lose to a lower-ranked or equal-point opponent | The exact penalty is not supplied. |

The exact delta function, ties, limits, rounding, replay order after an old result expires, and treatment of aborts/forfeits are unpublished here. **Calling this Elo would be an unsupported claim.** The rules identify directional incentives without identifying the algorithm. [HEROLIST](https://www.medievia.com/help/HEROLIST.html)

The core battle help lists saved points, kills, deaths, wins, losses, and time. It does not define whether every displayed statistic shares the ranking's 30-day window, or exactly what “time” measures. [HEROBATTLE](https://www.medievia.com/help/HEROBATTLE.html)

The actual `HEROLIST P` and `HEROLIST T` displays contained two entries during this session:

| Hero | Points | Wins | Losses | Displayed Time |
| --- | --- | --- | --- | --- |
| Destin | 1400 | 5 | 0 | Tue Sep 22 03:49:27 2026 |
| Nasha | 1400 | 5 | 0 | Tue Sep 22 03:37:50 2026 |

`Time` is therefore displayed as a calendar timestamp, not a duration. Its timezone and precise event meaning were not established. The header explains kills/deaths, but the visible columns were HeroName, Points, W, L, and Time. These two records do not establish the rating formula or a constant points-per-win value. [Live standings](medievia-hero-battles-live.md#standings)

## Champion rewards and similarly named points

The top 12 are Champion Heroes; first place is Grand Champion. The published HP bonuses are:

| Rank | Bonus HP | Rank | Bonus HP |
| --- | --- | --- | --- |
| 1 | 35 | 7 | 20 |
| 2 | 30 | 8 | 18 |
| 3 | 28 | 9 | 16 |
| 4 | 26 | 10 | 14 |
| 5 | 24 | 11 | 12 |
| 6 | 22 | 12 | 10 |

Champion and clan HP bonuses do **not** apply inside a Hero Battle. Champions also receive a visible title and a special flying mount. [HEROBATTLE](https://www.medievia.com/help/HEROBATTLE.html)

| Current class | Published champion mount |
| --- | --- |
| Mage | Coatyl |
| Cleric | Pegasus; mount help also describes a gray winged horse |
| Thief | Stone falcon |
| Warrior | Roc |

These mounts respond to `CALL`, arrive quickly without a fee, and can fight evil dragons for their owner. Qualification is tied to the top twelve on `HEROLIST P`. Exact mount statistics and the timing of revocation after losing rank are not specified. [Becoming a Hero](https://www.medievia.com/hero.html), [HEROMOUNT](https://www.medievia.com/help/HEROMOUNT.html)

**Hero Battle rating is not the same as general HEROPOINTS.** The latter reward broader heroic activity and can include participation in battles; Master Hero is a separate status based on those activity points among online players. Some HEROPOINTS prose describes proposed future requirements rather than implemented rules, so it does not establish a present compulsory monthly quota or a fixed per-battle activity-point reward. [HEROPOINTS](https://www.medievia.com/help/HEROPOINTS.html), [MASTER HERO](https://www.medievia.com/help/MASTER-HERO.html)

## Conduct and player controls

The current rule pages prohibit combat triggers/automation and broader unattended or complex automation. Historical advice about aliases and macros must be read within those rules, not as permission for automated tactical decision-making. The same rules explicitly allow the built-in Hero Wager system while prohibiting player-organized gambling and bets on ordinary duels. [RULE6](https://www.medievia.com/help/RULE6.html), [TRIGGER](https://www.medievia.com/help/TRIGGER.html)

Rule 7z prohibits intentionally throwing game-sponsored contests, including Hero Battles. Rule 7f prohibits deliberate disconnection for an unfair advantage. A loss of connection therefore neither pauses combat nor establishes a legitimate escape route. [RULE7](https://www.medievia.com/help/RULE7.html)

General conduct rules still apply; the automated battle help does not establish a ban on the `BASH` skill.

## What the full experience adds up to

There are three overlapping experiences:

1. **The fighter** learns a specialized environment and equipment pool, then makes repeated decisions about pressure, escape, recovery, and expenditure. Permanent character progress unlocks participation, while temporary arena resources and practiced execution shape the match.
2. **The spectator** follows a recognizable player, watches command-level decisions through filtered output, and learns enough to try competing. A wager makes that observation personally consequential.
3. **The regular competitor** gains a public reputation and durable recognition, but must keep participating to retain ranking-based privileges.

This is an interpretation of the documented mechanics and historical accounts. The interviews supply a social dimension that command help misses: Torx admired another competitor's speed and won wagers on him; Allyrellia found an accessible source of competitive excitement and respect. The event was both a contest and a public demonstration of skill.

## Why the public source archive cannot complete the specification

The inspected [DikuMUDOmnibus archive](https://github.com/DikuMUDOmnibus/Medievia) is at commit `d128b51236e249a730d60da5d4eb2359dc873acb`. Its ordinary arena has [dueling/PK quest help](https://github.com/DikuMUDOmnibus/Medievia/blob/d128b51236e249a730d60da5d4eb2359dc873acb/lib/help_key.txt#L840-L873) and [a PK-counter exemption](https://github.com/DikuMUDOmnibus/Medievia/blob/d128b51236e249a730d60da5d4eb2359dc873acb/src/fight.c#L1493-L1496). It does not have Hero Battle commands in its [command table](https://github.com/DikuMUDOmnibus/Medievia/blob/d128b51236e249a730d60da5d4eb2359dc873acb/src/interp.c#L72), nor matching implementation symbols in the searched source.

The 4.1 introduction in the official history is consistent with this archive preceding the feature, but the archive's label alone does not establish a precise release build. Its [original README](https://github.com/DikuMUDOmnibus/Medievia/blob/d128b51236e249a730d60da5d4eb2359dc873acb/MEDIEVIA.README#L1-L5) describes an unauthorized acquisition; public availability does not establish an official source release.

In particular, `lib/wld/The_Arena` must not be presented as a recovered Hero Battle map, and old combat formulas must not be presented as the contemporary Hero Battle server's formulas.

## Unresolved details and evidence needed

These gaps materially prevent an exact reproduction. They are not proposed mechanics.

| Area | Unresolved questions | Evidence that would settle them |
| --- | --- | --- |
| Entry | Hero status is required; level-2 rejection confirmed. Reclass eligibility, exact flags, resource/status restrictions, and minimum applicants remain unknown | Entry responses from additional character states and qualified heroes |
| Pairing | Tie-breaking, newcomers, disconnects while queued, unavailable selected player | Queue records with requests, ratings, and last-battle timestamps |
| Preparation | Precise duration, countdown messages, first legal attack, whether betting shares the timer | Timestamped complete match log |
| Inventory | Storage/restoration, starting kit, consumable limits, item ownership and cleanup | Before/inside/after inventories and item identifies |
| Equipment | Full names, slots, attributes, effects, quantities, placements, randomness, respawn | Item catalogue and repeated opening-phase observations |
| Arenas | Names, complete room graphs, secret exits, hazards, spawn locations, selection distribution | Maps recorded from multiple matches, room/exits output |
| Combat exceptions | Tracking by class/phase, spell restrictions, timing changes, normalization | Controlled in-arena comparisons against ordinary combat |
| Overtime | Trigger timer, warning, teleport versus incremental closure, map variants, item carryover | Full transition log with positions and inventories |
| Death and return | XP/gold/gear effects, return location, resource and affect restoration | Pre/post character state, separately distinguishing wagers |
| Rating | Delta formula, draw/abort/forfeit handling, ties, expiry/recalculation, history retention | Matched before/after standings and dated results |
| Wagers | Principal, rounding, caps, empty pools, repeat bets, balance source, refunds | Balance changes and settlement messages across cases |
| Viewing | Commands unlocked at level 2 in this test. Actual feed connection, gag leaks, statistics visibility, latency, swapping feeds, and coaching restrictions remain untested | Both player views plus spectator logs from the same battle |
| Rewards | Minimum participation, fewer than 12 contestants, ties, revoke timing, activity-point amount | Rank transitions, HP checks, mount calls, point accounting |
| Recovery | Reboot/crash/administrative abort during each phase | Maintainer documentation or controlled nonproduction tests |

The in-game `CHANGES` and numbered `ANNOUNCEMENT` commands are additional sources for revisions not reproduced by their web help pages. Live `HELP ANNOUNCEMENTINDEX` documents topic searches but requires level 6; `ANNINDEX HEROBATTLE` was unavailable to the level-2 character. That history search was therefore not completed. [CHANGES](https://www.medievia.com/help/CHANGES.html), [ANNOUNCEMENT](https://www.medievia.com/help/ANNOUNCEMENT.html), [live help checks](medievia-hero-battles-live.md#live-help)

## Research coverage

The work covered the official command/help index and relevant linked rules; the official feature, history, hero overview, and tour; all seven linked newspaper archive indexes spanning 1999–2010; and a targeted scan of 93 additional historical articles selected for hero, class, combat, tips, and interview relevance. The 2002 guide and 2009 interview were read in full. The strongest historical additions were the 2004 automation interview and the competing tracking accounts.

Searches also sought arena maps, equipment lists, logs, rating arithmetic, and refund behavior. A public MedUI map file had no Hero Battle/arena name hits in a string scan; that narrow check is not a complete semantic examination of the binary map. The Winterdale fan site could not be inspected successfully. No usable complete arena map, item list, production source, or complete real-match transcript was recovered.

The subsequent live session checked the core Hero Battle help, compared command access at levels 1 and 2, found the relocated registration NPC, tested his eligibility check, and checked for matches and spectator feeds. It confirmed some published rules while demonstrating that live help can retain obsolete directions. It did not reach the combat arena or observe a match.

The companion [source inventory](medievia-hero-battles-sources.tsv) records the principal sources and their evidence classes; the [live evidence ledger](medievia-hero-battles-live.md) records the direct checks. The remaining uncertainty is explicit so this research can inform later design without turning gaps into invented Medievia behavior.
