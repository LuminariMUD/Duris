# Findings: a fall that landed three rooms away (Faang, 2026-10-07)

Written 2026-10-07 against `master` at `a7e43bd0a`, from a play-test report by the owner.
Working note: file the defect as a work item and delete this file. The resolution of each
finding is at the end, under [Resolution](#resolution-2026-10-08).

## What happened

Bogum (level 6, 159 hp) fast-walked the route from the shaman caves to the Faang inn with a
Mudlet alias, one command per line. The transcript, read against the code, is:

| Step | Room | What the player saw | What the server did |
|---|---|---|---|
| `d` | 15345 → 15266 A Steep Canyon Wall | Room, "A huge black widow spider rushes towards you" | Ordinary move. 15266 has `F 5` in `areas/world.wld`: a 5% fall chance. |
| `d` | 15266 | "You rediscover the law of gravity... ...the hard way!" | `command_interpreter()` rolled the room's fall chance before running the command (`src/cmd/interp.c:1886`), won the 5%, called `falling_start()` and **discarded the `d`**. `falling_start()` scheduled `event_falling_char` with delay 0 and speed 1 (`src/world/falling.c`). |
| event | 15266 → 15265 | "A Steep Canyon Wall" (room text only) | `falling_step()`: route `downward` through the open down exit, speed 1 → 31. At speed < 45 the faller gets no message of their own, only `do_look()`; the room sees "$n drops from sight" / "$n falls in from above". Next step scheduled in `falling_event_delay(31)` = 4 ticks (one second). |
| `d` | 15265 → 15263 The East Bank | Room | The 10% roll in 15265 (`F 10`) missed, so the queued `d` ran as a normal move. Nothing checks for a pending fall. |
| `s` | 15263 → 15264 A Large Sleeping Cave | Room, guards, receptionist | Normal move into the inn. |
| event | 15264 | "You land with stunning force!", "The world starts spinning, and your ears are ringing!" | The second `falling_step()` fired with `ch->in_room` = the inn. The inn has no down exit, so `falling_choose_route()` returned `stay` and `falling_should_land()` returned true: impact damage at speed 31, position dropped, `Stun()`, possibly `KnockOut()`, all in the inn. The inn saw "$n falls in from above, landing in a crumpled heap!". |

Live checks afterwards: `stat room 15266` shows `Chance of falling: 5%`, `stat room 15265`
shows `10%`, `where bogum` shows room 15264. The command loop in `src/net/comm.c` dispatches
one queued command per descriptor per pulse, so the three moves took three ticks, inside the
four-tick gap between fall steps.

## Is a fall there intended?

Yes. The two canyon-wall rooms on the only path to the inn carry builder-set fall chances
(`F 5` on 15266, `F 10` on 15265; loaded at `src/world/db.c:1313`). The roll happens on every
command typed while standing in such a room, not on entering it, and succeeds unless the
character is trusted, flying or levitating, or has an active climb affect that catches them
with `climb skill / 2` percent (`falling_climb_catches`). A character who types one command in
each room has a 14.5% chance of at least one fall per traversal. A fast-walk changes nothing
except that the swallowed command is a movement, which is why one `d` in the alias produced no
"you cannot go that way".

## Findings

| # | Severity | Finding | Evidence | Suggested action |
|---|---|---|---|---|
| 1 | Medium, gameplay bug | A falling character can keep acting and walking, and the fall then resolves wherever they are. Nothing gates commands or movement on a pending `event_falling_char`: `do_move` in `src/cmd/actmove.c` never looks at it, `char_falling()` (`src/core/utility.c:5633`) only tests the room sector and `z_cord`, and neither `char_from_room()` nor any move path cancels the event. `falling_step()` reads `ch->in_room` when it fires. With one second between the first and second step (speed 31) a player can move up to four rooms; a move into any room with an open down exit would even pull them down through it. | The transcript above; `stat room` and `where` after the fact. The 2026-09-14 hardening (`8cbd8ea2c`) covers relocation *during* a step (damage or stun moving the character) but not between steps. | Gate it: in `command_interpreter()` refuse movement and most commands while `event_falling_char` is scheduled ("You are falling!"), the way `PLR2_WAIT` and casting are gated a few lines above the fall roll. Belt and braces: carry the expected room in the event payload next to `speed`, and have `falling_step()` abort (or cancel on `char_from_room()`) when the character is no longer there. |
| 2 | Low, UX | The faller gets no message when a step moves them down at speed below 45: only the new room's `do_look()`. A fall step is indistinguishable from a walk, which is what made the transcript confusing. | `falling_step()` after the move: `act("$n falls in from above.", … TO_ROOM)` then `checked_look()`, nothing to `ch`. | Send the faller a line such as "You tumble down!" on every step, in every speed band. |
| 3 | Info, design | The fall roll is per command, not per room entry, and a successful roll discards the command (`src/cmd/interp.c:1886-1894`). Typing `look` or `say` on the wall can drop you. This is legacy behaviour, unchanged since before the sources moved on 2026-08-31. | Code reading. | Owner's call. If kept, say so in the builder docs next to the `F` record. |
| 4 | Info, balance | Impact damage for a one-room fall is `max_hit × speed/250 + rand(80,120) − agility`, minimum 2, halved by safe fall (`falling_impact_damage`). At speed 31 that is 12% of max hp plus roughly 80 to 120 minus agility, most of a level-6 character's bar, plus stun and a knockout check. | `src/world/falling_policy.c`. | Worth a look alongside 1: the flat 80–120 term dominates short falls. |
| 5 | Info, content | Faang's only route from the newbie caves to its inn runs down this fall-chance wall, with an aggressive black widow spider in 15266. | Route computed from `areas/world.wld`; transcript. | Builders' call. |
| 6 | Info, testing | `tests/async/run_falling_skills_journey.py` already boots a minimal world, walks a character off a ledge and lands it, with `falling_journey_fixture.cpp` controlling skills and hp. | File headers. | The regression for finding 1 fits there: give the ledge room a fall chance, spam `look` until the fall starts, send a move inside the four-tick gap, and assert the move is refused (or that the landing happens in the fall's own room). |

## Reproduction without a client

Any mortal in 15265 typing `look` repeatedly falls within a few dozen commands (10% each).
Send `d` immediately after "You rediscover the law of gravity" and `s` after the next room
text: the landing messages arrive in A Large Sleeping Cave.

## Resolution (2026-10-08)

On the branch `fix/build-findings-and-falling`, with the build findings of
[build-findings.md](build-findings.md).

| # | Status | Change |
|---|---|---|
| 1 | Fixed | `command_interpreter()` refuses every command but the casting escape hatches (petition, return) while an `event_falling_char` is pending: "You are falling!" (`src/cmd/interp.c`, right after the casting gate). The event payload carries the room the step was scheduled in, and a step whose faller is elsewhere, summoned or teleported between two steps, does nothing (`src/world/falling.c`). Regressions: the shelf phase of `tests/async/run_falling_skills_journey.py` (a room with `F 100`, a move typed behind the command that starts the fall), and the payload case in `tests/async/test_falling_skills.py`. |
| 2 | Fixed | "You tumble downward!" to the faller on every step below speed 90; the faster band already had its line. |
| 3 | Documented | `docs/content/area_writing.txt`, under the `F` record: a successful roll swallows the command, and the character can do nothing but petition until the fall lands. The roll stays per command. |
| 4 | Kept | The impact arithmetic is the legacy rule, faithfully reproduced (`falling_policy.c` keeps it so it can be checked without a world), and it is not a defect: a one-room fall is meant to hurt. Softening the flat term is a balance change, and that is the owner's to make, not a fix. |
| 5 | Builders | World content, not server behaviour: the route and the spider are zone data under `areas/`. No change. |
| 6 | Done | See 1. |
