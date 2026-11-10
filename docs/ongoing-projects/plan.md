# Issue #707: Bard redesign (base class, Scoundrel, Disharmonist, Minstrel)

Status: implementation in progress, 2026-11-10. PR 1 (caps, circles and Riff) is qualified and ready for review. PR 2 is in progress on `branch/issue-707-bard-utility`; PRs 3–5 remain unimplemented.

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

## What the code says

The issue was written from a 5 November source read plus player reports. Checked against the base commit, six of its premises have changed or were never true. Each one changes the work.

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

- PR 2 worktree: `/home/aiwithapex/projects/duris-issue-707-bard-utility`, branched from PR 1 implementation `d896812fc`. Merge this PR 1 handoff update into that branch before publishing its PR.
- Started from clean `b0c9e7cae`; merged current master `8a8927eac` before implementation. No existing PR covered this branch.
- PR 1 outcome: registration changes below and retained Riff proficiency with an explicit unspecialized-use refusal. Non-goals: no base Riff grant or spell-slot changes. Files: skills, guild update, Bard Riff facts/command, both help catalogs, focused regression/journey tests. Proof: real registration/update fixtures, disposable MariaDB command/relogin journey, focused Bard checks and native build.
- Ablation: the five slices already map directly to proposal requirements; retain them. Use the existing update/command and journey paths, with no saved field, migration, runtime option, release tag or new test runner.
- PR 1 checks passed: `make -C src -j8`; `./scripts/format.sh --check`; `test_guild_chaos_epic_skills.py`, `test_song_dispositions_runtime.py`, `test_dissonance_runtime.py`, `test_song_dispatch_lifetime.py`, `test_class_helpfiles_contract.py`, `test_ability_skills_3.py`, `test_ability_framework.py`, `test_ability_page_chances.py`, `test_ability_coverage.py`; disposable MariaDB `test_minor_creation_instrument_journey.py --server bin/server/dms_new`. Evidence: `bin/qualification/issue707/{build,instrument-journey,skills-journey}.log` (untracked).
- PR 1 final check passed: `bash tests/async/with_disposable_mariadb.sh python3 tests/async/run_skills_command_journey.py --server bin/server/dms_new`. Added checks cover all Bard/spec grants and memorized Detect Invisibility plus Riff's saved rating through two unspecialized logins and all three specs. The journey passed all new assertions. Earlier attempts caught/fixed a misplaced cap edit and the journey assertions' handling of the spell catalog's `Circle 9` headings and `*` specialization markers. No production operations.
- The missing worktree `.env` is intentional for validation: use disposable MariaDB authority and isolated servers; do not borrow a running server or its database.

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

- Song of Healing, player Minstrels only: add (level − 31)/5 + (song rating − 50)/10 + (Cha − 100)/10, each at least 0, before the ally share. No target receives more than 45 per verse. A level 56, rating 100, Cha 150 Minstrel goes from 36 to 45 on self and from 23 to 33 on allies.
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

`src/classes/skills.c`, `src/classes/bard.c`, `src/guild/guild.c`, `src/magic/spells.h`, `src/magic/magic.c`, `src/magic/spells.c`, `src/cmd/interp.c`, `src/net/sparser.c`, `src/combat/fight.c`, `src/abilities/abilities.c`, `src/core/prototypes.h`; tests under `tests/async`; `help/duris_help_parsed.hlp` and `lib/information/help_index`; `docs/reference/CLASS-POINTS.md` and `site/power-atlas/data.json` only where they state a changed number.

## Proof

Per PR: `make -C src`, `./scripts/format.sh --check`, the PR's focused tests, the existing Bard tests (`test_song_dispositions_runtime.py`, `test_dissonance_runtime.py`, `test_song_dispatch_lifetime.py`, `test_minor_creation_instrument_journey.py`, `test_class_helpfiles_contract.py`, the ability page tests), and a local server run of the changed abilities. The issue closes when all five PRs are merged and each proposal line has its test or its "already true" proof.

## Gameplay effects to know about

- Trip 90 → 75 trims trained Trip on existing Scoundrels at their next login. Raising the cap later would not give it back.
- Hide 80 also raises Hide for multiclass Bards.
- Squall can throw a flying target out of the room, as the spell does.
- The Dissonance roll only happens when a verse lands mid-cast, so the real interruption rate is below the 5 to 25% figure.
- Spell Echo adds about 20% expected damage to the six listed spells.

## Open questions

Each has a default above, so work can start. An answer only changes the named PR.

1. **Riff (PR 1).** Default: stay spec-only and keep the rating through respec. The alternative, a base-class grant, also gives Riff to unspecialised and multiclass Bards, which Bryken argued against.
2. **Trip (PR 1).** The final proposal says 75; Bryken said 90 is fine. Default: 75, with the skill loss noted above.
3. **Rope Trick "five at once" (PR 2).** Default: five hidden at a time, one target per cast, as Bryken described. The alternative is one cast hiding up to five group members.
4. **Scoundrel song switching (PR 2).** Default: only switching while already singing. Should starting a song from hide also stay hidden?
5. **Pets and the new songs (PR 3, PR 4).** Default: players only. Should a Scoundrel's or Minstrel's own charmed pets get Shadow Piper's Sneak or the dodge song?
6. **Dodge song name and instrument (PR 4).** Working choice: Song of Nimbleness on mandolin. Default spell dodge covers damaging spells only.
7. **Healing ceiling (PR 4).** Is "40 to 50 per tick" what the Minstrel receives (default) or what allies receive? If allies, the ally share rises from 65% to 100% for Minstrels.
8. **Charm bonus size (PR 4).** The proposal gives no number. Default: 10 points on the save.
9. **Storms proc rate (PR 5).** The proposal gives no number. Default: 1 in 5 per target per verse, the rate the song's cyclone and call lightning already use.
10. **Chaos, Dissonance and Echo numbers (PR 5).** Defaults: a save halves the Chaos chance; Dissonance uses the formula above; Echo covers damage spells only and rolls 30 to 50%.
