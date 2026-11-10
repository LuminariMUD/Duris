# Issue #707: Bard redesign (base class, Scoundrel, Disharmonist, Minstrel)

Status: implementation and local qualification complete. Five focused PRs are published for review, including the final review repairs. Merge and deployment remain separate work.

- Work item: [Duris #707](https://github.com/LuminariMUD/Duris/issues/707). The scope is "Rani's final proposal — 9 November 2026" at the top of the issue. The earlier proposal below it is history, as the issue says.
- GitHub Development branch: [branch/issue-707-bard-redesign](https://github.com/LuminariMUD/Duris/tree/branch/issue-707-bard-redesign).
- Local worktree: `/home/aiwithapex/projects/duris-issue-707-bard-redesign`.
- Inspected base: `d05167b75a580f850a81805c0d6787bcafc90988`, fetched from `origin/master` on 2026-11-10.
- Method: [ablation](../../.agents/skills/ablation/SKILL.md), applied after reading the song code, skill and spell registrations, casting, spell damage, stealth, pet, charm and achievement paths, and their tests.
- The #612 plan that used to live in this file is now [issue-612-kept-character-resume-plan.md](issue-612-kept-character-resume-plan.md).

## Outcome

Every line of Rani's final proposal is either implemented, or shown by a test to be true on master already, except the one line the owner declined (level 51 charming, see Non-goals). Where the proposal left a range or an alternative, one value is chosen and recorded here. Players can read every new number on the in-game ability pages and in help.

## Non-goals

- Charming level 51 mobs. The owner declined this on 2026-11-10: the highest charmable level stays 50, which is what the code already gives a level 56 Bard.
- Ideas the final proposal dropped: Blink, Blur on Heroism, full caster slots, instruments played from inventory, a universal instrument item, a combat restriction on Drifting, and any "Bard must lead the group" rule.
- Bryken's side suggestions that the final proposal did not adopt: Calming, Peace, Cowardice and Forgetfulness landing more often, a prismatic spray effect on Chaos, and Drifting's success rate.
- Other classes, mob song AI, property/config knobs for the new numbers, database migrations, player news, and production deployment.

## Planning baseline before implementation

The issue was written from a 5 November source read plus player reports. Checked against the base commit, six of its premises had changed or were never true. The following baseline determined the work.

| Proposal line | What the code does now | Effect on the plan |
| --- | --- | --- |
| Make all instruments beltable | Done by #712. Every instrument counts as belt-attachable ([utils.h:587](../../src/core/utils.h#L587)). Of the 209 instrument objects in `areas/obj`, 206 can be held; the other three have no hold flag in their files. | No work. The real gap is the next line. |
| Play from all belt slots and any equipment slot | `has_instrument` already looks at wield through the three belt slots, but returns the first instrument it finds ([bard.c:234](../../src/classes/bard.c#L234)). With a flute held and drums on the belt, `play heroism` is refused ([bard.c:2853](../../src/classes/bard.c#L2853)). Slots below wield are not looked at. | Pick the instrument that fits the song, from every slot. |
| Sing while hidden without breaking Hide | Verses have kept hide since #883 ([bard.c:2580](../../src/classes/bard.c#L2580)). Only the `play`/`wail` command reveals ([interp.c:2281](../../src/cmd/interp.c#L2281)). | Base Bard: no work, the #883 regression is the proof. Scoundrel song switching still needs a change. |
| Heroism: let the combat pulse affect the singer | It does. The singer gets song level / 20 on both pulses, so 2 from song level 40, in any room order since #826 ([bard.c:1651](../../src/classes/bard.c#L1651), tested in [test_song_dispositions_runtime.py](../../tests/async/test_song_dispositions_runtime.py)). Bryken's report is from 5 November, three days before #826. | Only the listeners' value changes, from 1 to 2. |
| Song of Healing should count toward Salvation | It already goes through `heal()` ([bard.c:913](../../src/classes/bard.c#L913)), which credits the achievement for effective healing of other players ([fight.c:798](../../src/combat/fight.c#L798), [achievements.c:490](../../src/world/achievements.c#L490)). Self-healing and healing mobs never count, for any class. One percent of the goal is 10,000 HP, which is slow at song rates. | Add a test that proves the credit. Change code only if that test fails. |
| Humanoid charms are short, others long | There is no humanoid rule. Duration is 1240 / the target's Intelligence, in game hours of 75 seconds ([bard.c:1081](../../src/classes/bard.c#L1081)): Int 100 gives 15 minutes, Int 14 gives 110. | Add the humanoid rule the proposal asks for, as a floor. |

Also settled by reading the code:

- **Rope Trick** hides one target per cast, allows three rope-hidden people in a room, and does not need consent. A target who has not consented gets a resist check and a save ([magic.c:22988](../../src/magic/magic.c#L22988)).
- **Riff** is registered once per spec, not on the base class ([skills.c:3532](../../src/classes/skills.c#L3532)). So `update_skills` wipes it on unspecialise and on every login while unspecialised ([guild.c:116](../../src/guild/guild.c#L116)), and it restarts at 40. Multiclass Bards are never specialised, so a base-class grant would hand Riff to every Rogue/Bard, Cleric/Bard and Conjurer/Bard.
- **Dissonance's** accumulating roll, which the old part of the issue warns about, was fixed by #719. The roll is worked out per target ([bard.c:2272](../../src/classes/bard.c#L2272)).
- **Song of Storms** uses lightning bolt, which Globe stops ([magic.c:1235](../../src/magic/magic.c#L1235)). Squall's per-target hit and hurricane carry no globe flag. Both spells are room-wide, and `bard_storms` already runs once per target ([bard.c:1916](../../src/classes/bard.c#L1916)), so calling the room-wide spell from it would hit every enemy once per enemy.
- **Song IDs.** Poison IDs are numbered from the last song ([spells.h:1111](../../src/magic/spells.h#L1111)), so appending a song renumbers every poison, and a poisoned character carries its poison's ID as an affect type. Two song IDs are defined and unused: `SONG_MINDSHIELD` and `SONG_SNATCHING`.
- **Pets.** A mob singer never fumbles and needs no instrument ([bard.c:345](../../src/classes/bard.c#L345)), and a charmed mob gets its class and spec skills. No mob AI plays Drifting, but an ordered level 46+ Minstrel pet can.
- **Verse timing.** A verse comes every 8.75 seconds, 6.25 hasted. Most spells take 1 to 4 seconds to cast.

Confirmed baselines for the registration changes: Hide 70 (Scoundrel 90), Sneak 70 with no Scoundrel entry, Dual Wield 30/70, Trip 51/90, Disguise 51/55, Meditate 75, Quick Chant 90, Detect Invisibility circle 10, Invisibility not granted, charm reaches 6 levels below the Bard (level 50 at 56), Song of Healing = Cha/8 + song level/4 + song level/14 with 65% for allies.

## Ablation decisions

- **Reuse the two unused song IDs** for the two new songs. Appending would renumber the poison IDs that poisoned characters carry. No migration is needed this way.
- **One pet rule for everything new: the singer must be a player.** A single `player_bard(ch, spec, level)` check gates every new spec bonus. It replaces a group-leader rule, a PvP-only rule and per-pet-type detection, and it is the explicit summoned-pet exclusion the proposal asks for. Both new songs also only affect players.
- **No new spells.** Storms uses squall's existing per-target function and a per-target piece split out of hurricane.
- **No second dispel.** The removal step inside `spell_dispel_magic` becomes a shared helper. The spell uses it for every effect, Chaos for one.
- **Spell Echo reuses two existing points:** the repeat-cast spot Devotion uses after a spell completes ([sparser.c:3414](../../src/net/sparser.c#L3414)) and the spell damage modifier list ([fight.c:4819](../../src/combat/fight.c#L4819)). No new event or queue.
- **Spell dodge sits beside monk Evasion** in `spell_damage` ([fight.c:4501](../../src/combat/fight.c#L4501)). Melee dodge sits beside the existing spec dodge bonus ([fight.c:9423](../../src/combat/fight.c#L9423)).
- **No new tag IDs.** The 10 and 25 second immunities are short markers that use the song's own ID on the victim, the way Riff and fumbles already mark the singer.
- **Riff keeps its registrations.** Retaining the rating needs two small guards and no new saved field.
- **Dropped:** config properties for new numbers (they are named constants, like every other song number), a generic "song proc" layer, new test runners, and any change to existing Minstrel Chaos behaviour.

Nothing else could go: each remaining change maps to one proposal line.

## Current handoff

- Published stack, all open, nondraft and labelled `enhancement`: [#1002](https://github.com/LuminariMUD/Duris/pull/1002) caps/circles/Riff → master; [#1004](https://github.com/LuminariMUD/Duris/pull/1004) instruments/Rope Trick/hidden switching → #1002; [#1005](https://github.com/LuminariMUD/Duris/pull/1005) Scoundrel → #1004; [#1006](https://github.com/LuminariMUD/Duris/pull/1006) Minstrel → #1005; [#1007](https://github.com/LuminariMUD/Duris/pull/1007) Disharmonist → #1006. Review/merge remains; no deployment was requested.
- Canonical plan owner: `/home/aiwithapex/projects/duris-issue-707-bard-redesign`, branch `branch/issue-707-bard-redesign`. Sibling worktrees/branches end in `-bard-utility`, `-bard-scoundrel`, `-bard-minstrel`, `-bard-disharmonist`. Merge parent updates forward, preserving the linear PR bases and avoiding history rewrites.
- Latest master `371b95d97` is integrated through all branches. Its only effective change since the previous integrated base is the racial damroll display label; the final native build and race-command regression passed afterwards.
- PR 5 implementation is `e24a3e591`. Native tests and the complete disposable MariaDB Disharmonist journey passed. Measured Dissonance immediate look 0.5 seconds and immunity 25.27 seconds; Chaos removed exactly one effect and immunity expired after 9.76 seconds (polling precision); Storms hit through active Globe; a completed Echo used exactly one memorized spell.
- Dissonance's real journey exposed a remaining cast wait after `StopCasting`. `interrupt_spellcasting` now cancels only the original cast-owned wait sequence, captured once by scheduling and retained across cast segments. Replacement/unowned combat waits remain. This is process-local event metadata, not saved player state or a schema change. The dedicated sanitizer and live tests passed.
- Final review repairs are complete: `fc6ace887` (#1004) reveals Hide when a failed song switch ends singing; sanitizer state matrix and real `play nonexistent` journey passed. `0b494d80a` (#1005) and `a381a2efc` (#1006) give Shadow Piper and Nimbleness link-controlled lifetimes. The production affect updater runs five ticks in the regression: both songs persist, an ordinary timed control expires, and stop/change/room cleanup still works. Both reported review threads are resolved.
- Final integrated code `f81f5340c` passed native build, formatting/whitespace, song disposition/lifetime and dispatch, actual-object Disharmonist and Minstrel fixtures, Dissonance gates and cast-wait ownership. Earlier gameplay proofs remain valid for unchanged handlers; the failed-switch journey was rerun on its repaired owning branch. After this document is committed, merge it forward through all five branches, push, and verify clean worktrees/remote parity and PR bases; only documentation changes remain in that propagation.
- PR 1 proof: real skills/spell registrations for every Bard spec; Riff 87/100 survives repeated unspecialized logins and all three specs; memorized Detect Invisibility saves/reloads. Implementation/qualification `d896812fc` / `08fdae0b5`.
- PR 2 proof: instrument slot/artifact/darkness/fallback and Rope Trick fifth/sixth/self/group/consent/resist/save fixtures. Extended Minor Creation journey checks all six instruments, held flute plus third-belt drums, hidden wail switch/plain-play reveal, grouped Rope Trick and save/reload. Implementation/parser repair/qualification `cc01fc54a` / `d69b3686c` / `044522680`. Parser arguments include the command word; the hide gate uses `argument + begin + look_at`.
- PR 3 proof: real follower/non-follower, north/south group walks, solo walks, follower/singer transfers, unfollow/group/combat/change/stop cleanup; two -2 Heroism listener effects. Eligibility matrices exclude pet singers/recipients and fighting listeners. Saved poison IDs stay 1536–1542. Implementation/room repair/qualification `88cc4e772` / `712b3badd` / `04343d8bf`.
- New-song room cleanup is required because ordinary LNK_SONG permits one-room grace and transfers bypass normal room-link checks. `check_bard_song_rooms` runs at actual placement and after ordinary followers finish moving, preserving group walks while ending effects on separation. Group/follow/combat boundaries remove the relevant new effects; existing songs keep their behavior.
- PR 4 native proof links actual server objects for healing → heal/vamp → Salvation (only effective other-player healing, no self/NPC/overheal credit), healing/cap/stat matrix, unchanged NPC healing, charm +10 save/40–48-hour floors/preserved longer durations/level-51 refusal, pet Drifting, +5 melee outcomes in 101 and 35 spell avoids in 1000. Gameplay comparison at level 56, rating 100, actual Charisma 150, level-56 lyre measured 36 self / 23 ally before versus 45 self / 33 ally after, with saved Salvation credit and Nimbleness cleanup. Scoundrel segment also passed on that binary. Implementation/qualification `0eb505729` / `09f06e7cd` / `14c52dec4`.
- Fixture detail: Human Adaptive contributes +5 current/max stats, so +45 yields actual Charisma 150 in the support comparison. The journey asserts loaded stats and instrument level; a saved level-achievement marker prevents unrelated rewards. The reported 11 HP is not universal: low-stat native cases produce 11, the controlled high-stat ally baseline produces 23. The 45 healing cap is on the base amount after ally sharing; external healing modifiers continue.
- PR 5 proof: actual-object fixture covers exact probability tickets/save halves, independent one-effect Chaos dispels/markers, suspended and non-dispellable effects, normal full dispel and returned morph body, Storms callback identity/room safety, unchanged Hurricane shared roll, all six Echo spells with profile caps/reflection/non-recursion/dead/departed/replaced targets and exception cleanup. Cast-wait ownership, normal abort/timing/input, song disposition/lifetime, help/facts/framework/chances/coverage, named-set effect ownership/cooldowns and Minstrel native regressions pass.
- Evidence is untracked under each worktree's `bin/qualification/issue707/`: native build and journey logs and JSON reports with binary hashes. Fifth reports are `disharmonist-gameplay.json` and `disharmonist-runtime.log`. Each gameplay command uses `bash tests/async/with_disposable_mariadb.sh`; servers are isolated and no `.env` is borrowed. No artifacts or logs are committed.
- Documentation scope: CLASS-POINTS and power-atlas contain no changed Bard cap/circle numbers, so their unrelated scoring model is preserved. No release tag applies to this review-only work. No production operation, migration, runtime setting, item-stat change or new persistent player field.

## Implementation sequence

Five PRs, in this order, each with its tests and its help and ability-page updates. PR 1 is independent. PRs 3 to 5 use the `player_bard` helper that PR 2 adds.

### PR 1: Caps, circles and Riff

All in [skills.c](../../src/classes/skills.c) unless noted.

- Hide: base Bard 70 → 80. Scoundrel stays 90.
- Scoundrel: Dual Wield 30/70 → 30/80. New Sneak entry 1/85. Trip 51/90 → 51/75. Disguise 51/55 → 51/70.
- Disharmonist: new Quick Chant 1/100 and Meditate 1/100 entries.
- Detect Invisibility: Bard circle 10 → 9. Invisibility: Scoundrel only, circle 10.
- Riff: stays spec-only. `update_skills` leaves an unspecialised Bard's Riff rating alone, and `do_riff` refuses an unspecialised player ([guild.c](../../src/guild/guild.c), [bard.c](../../src/classes/bard.c)). The rating survives unspecialise, relog and respecialise.

Proof: a fixture test for Riff through unspecialise → login update → respecialise; a registration test for the nine numbers across all three specs; on the local server, check `skills` and the spell list for each spec and relog with Detect Invisibility memorised.

### PR 2: Instruments, Rope Trick, hidden song switching

- `has_instrument(ch, song)` looks at every equipment slot and returns the instrument that plays the song (right type, or an artifact). If none fits, it returns the first instrument found, so today's "wrong instrument" messages stay. Its three callers are all in [bard.c](../../src/classes/bard.c). Item stats are untouched: they still come from whatever is equipped.
- Rope Trick ([magic.c](../../src/magic/magic.c)): room limit 3 → 5. A target in the caster's group skips the resist check and the save, as a consenting target does today.
- Scoundrel song switch ([interp.c](../../src/cmd/interp.c)): `play`/`wail` with a song name does not remove hide when a player Scoundrel is already singing. Every other command still reveals.
- Add `player_bard(ch, spec, level)`.

Proof: fixture tests for instrument choice (flute held, drums on belt, plays both; artifact; no match), Rope Trick's fifth and sixth target and a grouped target with no consent, and the hide gate for Scoundrel, non-Scoundrel, not singing, and `play` with no argument. The existing #883 regression proves verses keep hide. Local server run of each.

### PR 3: Scoundrel level 56

- Heroism: listeners get 2 on combat and spell pulse when the singer is a level 56 player Scoundrel. The singer's own value is unchanged.
- Song of the Shadow Piper: takes the unused `SONG_SNATCHING` ID. Flute, level 56, Scoundrel only, allies only. Each player in the group who is in the room and following the singer gets Sneak for as long as the song plays and they share the room, through the same song link Heroism uses. Entering combat still strips Sneak.
- Song table, verse text, ability page, help entry. Retire the "Song of snatching" help note.

Proof: extend [test_song_dispositions_runtime.py](../../tests/async/test_song_dispositions_runtime.py) for both; local server walk with a follower and a non-follower, and a pet singer getting nothing.

### PR 4: Minstrel

- Song of Healing, player Minstrels only: add (level − 31)/5 + (song rating − 50)/10 + (Cha − 100)/10, each at least 0, before the ally share. Each target's base healing is capped at 45 per verse, after the ally share; existing external healing modifiers still apply. A level 56, rating 100, Cha 150 Minstrel goes from 36 to 45 on self and from 23 to 33 on allies.
- Salvation: a test that Song of Healing on another player adds to the achievement counter, not self or mobs.
- Charm, player Minstrels only: targets save at 10 points worse. A humanoid target stays charmed at least 50 to 60 minutes, rolled (40 to 48 game hours). The level limit does not change.
- Drifting: a pet singer's verse does nothing.
- New dodge song (working name **Song of Nimbleness**): takes the unused `SONG_MINDSHIELD` ID. Mandolin, level 56, Minstrel only, allies only, player singer, players only. While it plays, listeners get +5 to melee dodge and a 3.5% chance to avoid each damaging spell.

Proof: fixture tests for the healing numbers and cap, Salvation credit, charm save and duration with level 51 still refused, pet Drifting, and the two dodge hooks; record healing per verse before and after on the local server, which also checks the reported 11 per tick.

### PR 5: Disharmonist

All gated on a player Disharmonist.

- Storms, level 51: after the bolts, a 1 in 5 roll per target per verse casts squall's hit or hurricane's hit on that target at the song level, picked evenly. `cast_hurricane` keeps its behaviour with its per-target body split out ([spells.c](../../src/magic/spells.c)).
- Chaos dispel: on each verse, per target, chance = 5% + 1.5 per 10 song rating above 50 + 1 per 10 Cha above 100 + 0.25 per level the singer is above the target. A target that makes its save halves the chance. Success removes one random dispellable effect and marks the target immune for 10 seconds. The existing Minstrel branch is untouched.
- Dissonance interrupt, level 51: when a verse reaches a target who is casting, chance = 5% + 1.5 per 10 song rating above 50 + 1 per 10 Cha above 100 − Concentration/20 − 1 per 10 of the caster's higher of Int and Wis above 100, kept between 5% and 25%. Success stops the cast with no added lag and marks the target immune for 25 seconds.
- Spell Echo, level 56: after the Disharmonist's damage spell completes (magic missile, burning hands, lightning bolt, fireball, Bigby's clenched fist, shatter), a 50% chance to cast it once more at 30 to 50% damage, rolled. The echo uses no spell slot and cannot echo again.

Proof: extend [test_dissonance_runtime.py](../../tests/async/test_dissonance_runtime.py) for the interrupt, its bounds, immunity and a pet singer; fixture tests for the Chaos chance, save, single removal and immunity, for Storms hitting each target once and passing Globe, and for Echo's roll, scaling and non-recursion; local server fights against a globed caster dummy.

## Files

`src/classes/skills.c`, `src/classes/bard.c`, `src/guild/guild.c`, `src/magic/spells.h`, `src/magic/magic.c`, `src/magic/spells.c`, `src/cmd/interp.c`, `src/net/sparser.c`, `src/combat/fight.c`, `src/abilities/abilities.c`, `src/core/prototypes.h`, `src/core/structs.h`, `src/cmd/actmove.c`, `src/guild/group.c`, `src/world/handler.c`; tests under `tests/async`; `help/duris_help_parsed.hlp` and `lib/information/help_index`; `docs/reference/CLASS-POINTS.md` and `site/power-atlas/data.json` only where they state a changed number.

## Proof

Per PR: `make -C src`, `./scripts/format.sh --check`, the PR's focused tests, the existing Bard tests (`test_song_dispositions_runtime.py`, `test_dissonance_runtime.py`, `test_song_dispatch_lifetime.py`, `test_minor_creation_instrument_journey.py`, `test_class_helpfiles_contract.py`, the ability page tests), and a local server run of the changed abilities. The issue closes when all five PRs are merged and each proposal line has its test or its "already true" proof.

## Gameplay effects to know about

- Trip 90 → 75 trims trained Trip on existing Scoundrels at their next login. Raising the cap later would not give it back.
- Hide 80 also raises Hide for multiclass Bards.
- Squall can throw a flying target out of the room, as the spell does.
- The Dissonance roll only happens when a verse lands mid-cast, so the real interruption rate is below the 5 to 25% figure.
- Spell Echo adds about 20% expected damage to the six listed spells.

## Implemented balance choices

The recorded plan defaults were used throughout. There are no unanswered implementation blockers.

1. Riff stays spec-only and retains acquired ratings through respec/login; it is not a new multiclass/base grant.
2. Scoundrel Trip cap is 75, including the normal next-login trim of higher trained ratings.
3. Rope Trick supports five hidden people in a room, one target per cast. Grouped/self/consenting targets skip resistance and saves.
4. Scoundrels preserve Hide only while already singing and continuing after the switch. Starting, stopping and a failed switch that ends singing reveal Hide.
5. New spec bonuses require a player singer. Shadow Piper and Nimbleness affect players only; pets cannot provide or receive those new song effects.
6. Song of Nimbleness uses mandolin. It adds 5 outcomes in the existing 101-outcome melee dodge roll and 35/1000 avoidance of damaging spells.
7. The healing ceiling is 45 base HP per recipient after the 65% ally share. Normal external modifiers still apply; the controlled level-56 example is 45 self / 33 ally.
8. Minstrel charm saves are 10 points harder, humanoid duration has a rolled 40–48-game-hour floor, and existing longer durations remain. The owner declined level-51 charming.
9. Storms adds one Squall or Hurricane hit on a 1-in-5 check per target per verse, picked evenly.
10. A successful save halves Chaos's chance; Dissonance uses the opposed formula above; Echo covers the six listed targeted damage spells and rolls 30–50% damage once, with no second slot or recursive Echo.
