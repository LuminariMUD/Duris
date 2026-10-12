# Medievia Hero Battles live evidence

Date: 12 October 2026. Endpoint: `medievia.com:4000`. Character: **Arvenyl**, a newly created cleric. Level 1 was tested first; level 2 was then reached before continuing. Times below are UTC timestamps recorded when commands were sent, not the server's unspecified leaderboard timezone.

This ledger paraphrases command results and excludes credentials, the registration email, and unrelated game output. Reading a helpfile confirms what the running game documents; it does not demonstrate that every documented mechanic executes as described.

## Level 1 and level 2

| UTC | State or command | Result |
| --- | --- | --- |
| 06:03:37 | `SCORE` | Confirmed level-1 cleric, 55 maximum HP and 113 maximum mana. |
| 06:04:07 | `LINK` | Unrecognized at level 1. |
| 06:04:07 | `MINDLINK` | Unrecognized at level 1. |
| 06:04:07 | `HEROBATTLE`, `HEROSTATUS` | Both recognized; no active battle. |
| 06:05:58 | `HEROLIST P` | Standings readable at level 1. |
| 06:08:40 | `SCORE` after leveling | Confirmed level-2 cleric, 69 maximum HP and 126 maximum mana. |
| 06:08:41 | `MINDLINK` | Recognized and displayed an empty list of available sources. |
| 06:08:42 | `LINK` | Entered transit, then arrived in MedLink. |

The character gained level 2 through ordinary city combat after the user authorized leveling. No subsequent level was pursued. Email registration was completed before these checks, but no email verification code was entered. The level comparison therefore did not coincide with a verification-code change.

At 06:17:47, Arvenyl quit successfully from the City of Medievia. A fresh connection authenticated the saved character; `SCORE` at 06:18:34 again confirmed level 2. A final `QUIT` at 06:18:48 ended the connection. Live `HELP QUIT` says level-1 characters do not save, whereas levels 2–11 can quit from the city. Level-2 persistence was tested directly; level-1 persistence was not.

These observations support a level threshold for this character. They do not test every account state, reclassed character, special privilege, or alternate path into the area.

## Medlink navigation

At 06:09:02 the character moved east from **Welcome to MedLink!** into **The MedLink Real Estate Exchange**. North at 06:09:12 led to **The Mudslinger Rumor Mill**. There was no sign, and `CHALLENGE` did not operate as registration there. This directly contradicts the location given by live `HELP AUTO_HB`.

At 06:10:03, `LINK R` did not move the character. The game described the recall shortcut as a feature of old MedLink and required running through the new area instead. Live `HELP MEDLINK` still advertises that shortcut.

The successful route was:

```text
Welcome to MedLink!
  south → The Descent to Adversary              06:10:39
  south → Above the Hero Arena                 06:10:45
  down  → The Hero's Challenge                 06:10:48
```

Do not descend at the first southern room: that exit leads into Adversary's **The Decision Point**, a separate system. The Hero Battle branch is one room farther south.

The initial `LINK` transition included an animated journey before arrival. One movement at the starting room was interrupted by the lottery machine; subsequent movement worked without purchasing anything. Movement should be checked against the resulting room rather than assumed successful from the command alone.

## Registration and eligibility

**The Hero's Challenge** contained a distinguished imp named **Pili, the steward of HeroBattles**. Its room banner advertised `CHALLENGE`, `WITHDRAW`, and `ASK`; the only listed exit was up. `LOOK SIGN` at 06:10:54 found no sign.

| UTC | Command at registration | Result |
| --- | --- | --- |
| 06:10:55 | `ASK` | Pili explained that Arvenyl was not a hero and had no HEROLIST entry. |
| 06:10:56 | `CHALLENGE` | Pili explicitly denied participation because Arvenyl was not a hero. |
| 06:12:29 | `WITHDRAW` | Pili reported that no challenge had been issued. |

This verifies the nonhero exclusion at the actual registration NPC. It does not establish whether every total-level-124 character qualifies regardless of flags, recent reclass, equipment, or other state. No battle was created, and no queue entry remained from this test.

## Spectator commands and announcements

At level 1, bare `HB` invoked a humble-bow social rather than giving Hero Battle channel status. The command therefore should not be used as a low-level readiness check. Live `HELP HB` restricts that discussion channel to heroes.

`SETCOMM` showed **Hero Battle Announcements off** on this fresh character. At 06:12:27, `SETCOMM 7` enabled the channel; another listing verified it was on. No battle announcement was received during the subsequent checks.

At 06:11:25, bare `HEROWAGER` recognized the command but reported no battle. No amount or contestant was supplied and no wager was placed. At 06:11:26, `HEROSTATUS Arvenyl` denied personal statistics to a nonhero outside a battle.

`MINDLINK` was checked repeatedly after level 2. It was available as a command but had no sources to watch. This proves command access, not successful attachment to a fighting hero or the behavior of the spectator gag during combat.

## Standings

Both `HEROLIST P` at 06:05:58 and `HEROLIST T` at 06:12:17 displayed:

| Hero | Points | W | L | Time as shown by the game |
| --- | --- | --- | --- | --- |
| Destin | 1400 | 5 | 0 | Tue Sep 22 03:49:27 2026 |
| Nasha | 1400 | 5 | 0 | Tue Sep 22 03:37:50 2026 |

There were no other displayed entries in these results. The output proves that the Time column is a calendar timestamp; it does not identify the timezone or prove which precise event that timestamp represents. Equal ratings and equal records do not reveal the points formula or tie-breaking policy.

## Live help

The following core topics were read completely in-game. The substantive text was consistent with the corresponding web help already cited in the report. In particular, the obsolete navigation instructions were still present in the live help; merely checking the in-game text would not have exposed their mismatch with the world.

| Command | Started at UTC | Subjects checked |
| --- | --- | --- |
| `HELP HEROBATTLE` | 06:03:42 | Public viewing/wagers, saved statistics, champion HP table, ending/overtime |
| `HELP AUTO_HB` | 06:04:17 | Entry directions, queue commands, 90-second matching, restrictions, disconnection/idle |
| `HELP MINDLINK` | 06:04:50 | Source listing, attachment, stopping, default gag, filtered fields |
| `HELP MEDLINK` | 06:05:29 | LINK, old recall shortcut, level-2 minimum |
| `HELP HEROLIST` | 06:05:50 | Sorts, 1000 starting points, 30-day window, rating direction |
| `HELP HEROWAGER` | 06:05:56 | Cutoff, 10/90 split, proportional calculation, example rounding |
| `HELP HEROSTATUS` | 06:05:57 | Personal ranking versus current-fight statistics |
| `HELP HEROMOUNT` | 06:07:44 | Top-twelve qualification, mount types, calling |
| `HELP HB` | 06:08:13 | Hero-only discussion channel and staff enabling |
| `HELP HERO` | 06:11:50 | Hero progression/status and participation |
| `HELP HEROPOINTS` | 06:11:51 | Separate activity points; historical future-plan prose remains present |

Additional relevant checks:

- `HELP ANNOUNCEMENTINDEX` at 06:08:30 documents topic filtering and a minimum level of 6. At 06:11:52, `ANNINDEX HEROBATTLE` was unavailable at level 2, so it did not retrieve historical announcements.
- `HELP MEDLINK_GUIDE` at 06:09:36 contained only an under-construction notice.
- `GUIDE HEROBATTLE` could not navigate MedLink: the guide listed its supported towns and rejected this location.
- `HELP PAGE` documented `PAGE #0`; setting it removed paging and allowed later helpfiles to be read without truncated pages.
- `HELP QUIT` at 06:17:08 documented the level-1 saving restriction and low-level city logout described above.

## Availability and limits

At 06:04, the battle-status commands reported no match. Later checks at 06:11, 06:14, 06:17, and 06:18 again found no match, with repeated empty Mindlink lists at 06:08, 06:11, 06:13, 06:14, 06:17, and 06:18. The last two queries were `MINDLINK` at 06:18:46 and `HEROBATTLE` at 06:18:47, after reconnecting. These are sampled observations over approximately 15 minutes in the playable world, not proof of uninterrupted inactivity between commands or of general system availability.

No match was watched, no hero participated on the test character, and no combat-arena map or equipment list was recovered. The material additions are the demonstrated command-level threshold, the relocated registration route, direct nonhero rejection, announcement default, standings format, and the two concrete help/world contradictions.
