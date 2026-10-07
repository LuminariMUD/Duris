# The "Lost" Sojourn Codebase Was Never Lost -- It Was on Our Hard Drives

*How six AI deep-research tools failed, one former player succeeded, and the code turned out to hold secrets nobody had documented in thirty years.*

## The hunt

I recently went looking for the Sojourn3 codebase -- the production code of Sojourn, the legendary Diku-derivative MUD that shaped EverQuest's design DNA. Before finding it, I asked several major AI "deep research" tools to hunt it down. All of them came back with the same answer: a public release was announced in 2004, but no copy survives anywhere on the indexed internet.

They were right about the internet. They were wrong about the conclusion.

So I did it the old-fashioned way: I asked people I knew from when I actually played. And one of them had a copy.

The code was never lost. It was never leaked. It just lived quietly on the hard drives of former players and builders for twenty-plus years -- the LOCKSS principle ("Lots Of Copies Keep Stuff Safe") achieved entirely by accident, through a community of people who never delete anything.

## Background for the younglings

Sojourn was founded in 1993 by Kris Kortright (Miax) and friends out of the Black Knights Realm / Sequent Diku scene, and at its peak it hosted 400+ simultaneous players -- enormous for a text game. Its influence is hard to overstate: EverQuest's lead designer Brad McQuaid was an avid Sojourn player, and EQ's classes, races, and even the layout of Freeport (a near-copy of Sojourn's Waterdeep) trace straight back to it.

The family tree is famously dramatic:

- **1996** -- Creative differences split Sojourn into **TorilMUD** (non-PK) and **Duris: Land of Bloodlust** (full player-killing).
- **1998 / 2001** -- Sojourn itself continued as Sojourn 2, then Sojourn 3.
- **2003** -- After S3 wound down, its staff founded the modern **TorilMUD**.
- **2004** -- Miax announced he would release the Sojourn3 code and areas into the public domain. The TorilMUD forums erupted, builders opted out of having their zones included, the plan was scaled back... and then silence. No tarball was ever visibly archived anywhere. This is why every research tool concluded the release "probably never happened."

There was also **Homeland** (previously **ExileMUD**) -- a beloved port of the Sojourn lineage onto the CircleMUD codebase -- which was eventually merged into TorilMUD, a move that disappointed a lot of its players, me included. In a 2004 TorilMUD thread, one departing developer called the merger "an excellent idea" and praised Homeland's coder Vhaerun. The staff were optimistic. Those of us who loved Homeland's identity were... less so.

## What I actually found

The copy I recovered is not the trimmed 2004 public-domain release. It's something better and stranger: a **full operational snapshot of Outcast III Beta** -- config.h calls the world "Faerun" -- with 284 zone files, 261 quest files, logs, boards, mail, and even player files. Around 4 million lines of text total; roughly 265,000 lines of actual C code.

Outcast, it turns out, is not a Sojourn clone. The in-game credits lay out the lineage: **Copper -> Black Knights -> "Old Outcast" -> Outcast -> Outcast 2 -> Outcast 3**. That makes Outcast a *sibling* of Sojourn, not a descendant -- both grew out of the same 1993 Copper/Black Knights milieu. The fossils prove it:

- A "bury" command credited to Myrrh, dated **June 30, 1993** (actnoff.c)
- specs.waterdeep.c: "Written by: Miax -- 1993"
- An **Outcast disclaimer dated November 1, 1993** -- the same year Sojourn itself was founded
- Multiple zones carrying 1994 copyrights
- A few zones dated "1988" that are almost certainly typos for 1998 (identical boilerplate in neighboring files is dated 1998)

And the crossover is everywhere once you look. **Shevarash** (later the head of TorilMUD) and **Miax** (owner of Sojourn3) both appear in the Outcast 2 credits. **Cython** -- whose areas Miax explicitly named as safe to include in the 2004 public release -- is credited under "Duris Code" in this tree while also being credited with building the City of Brass, Palace of the Sultan, the Elemental Planes of Air and Fire, and Leuthilspar. The three "rival" games were sharing builders and code the entire time. The feuds were between admins. The people actually making the worlds just kept making them, wherever they happened to be.

## Menzoberranzan: the mystery is solved

For years, "when is Menzo coming?" was the running joke of the entire Sojourn/Toril community. The snapshot answers it, and the answer is brutal in its banality.

Menzoberranzan's zone range (vnums 170-196) is still explicitly reserved. There's a detailed map object of the city. There are tunnel rooms pointing toward it, quests referencing it, mobs from it, credits for it. And there is a comment saying it was **"removed for now to make room for Hyssk."**

Hyssk -- a yuan-ti zone created by Merrshaulk on June 15, 1998 -- took Menzo's hometown slot (slot 3, becoming the yuan-ti start city at room 35100). The most anticipated zone in the game's history was deleted to free up a hometown slot for a snake-people city. "For now" lasted forever. The vnums remain reserved to this day, like a parking space held for someone who died in 1998.

## The Duris blood feud, preserved in comments

The Duris sibling rivalry is documented right in the source:

- **Trip** was ported from Duris with the immortal comment: *"may their crappy code rot in binary hell forever."* They hated Duris. They ported its code anyway.
- **Tracking** was ported from Duris in 1999.
- **NEWJUSTICE** is described in config.h as a "new duris/outcast justice hybrid."
- Most damning of all: **49 zones are shared almost verbatim with Duris** -- same vnums, room prose, exits, and mob placement -- including Underworld, Jotun, Icecrag, Avernus, and Astral Main. That's not "both games are Diku derivatives." That's a common parent world, direct proof that both games inherited the pre-split Sojourn/Toril content base.

Then the two lineages diverged philosophically: Duris kept the simulationist systems (random-load tables, water currents, justice/weather, embedded object scripts), while Outcast went structural (3D room dimensions, seasonal climate matrices, artifacts, boot-time area compilation). Same parents, completely different ideas about what a world should be.

## Settling twenty-year-old player arguments

Having the code means finally answering the things players screamed at each other about for decades:

- **"That proc has NO save!" / "Yes it does!"** -- Both sides were right. Mob procs are wildly inconsistent: some call the normal save routine, some explicitly allow no save, and some apply a +20 modifier that effectively makes the save mathematically hopeless (a forced 1% chance). The arguments were never resolvable from the player side because the answer was different proc by proc.
- **"Rare" items** aren't flagged rare. Rare loading is a zone-reset probability (arg4) plus global object-count limits. Every spawn-camping strategy guide was unknowingly reverse-engineering arg4.
- **XP** runs on four broad curves -- roughly 230M total to level 50 for rogues, up to 316M for mages -- with levels 1-45 deliberately reduced 10% and 46-50 increased 10%. Level 50 becomes prestige progression.
- **Waterdeep's Great Fountain is room 3001** -- the same vnum as the Temple of Midgaard, the stock DikuMUD start room. Even after a decade of total renovation, the fingerprint of the original Diku world is still sitting in the room numbers.

## The lich: the coolest class that maybe never worked

The best design find: **Lich** is not a playable race -- it's an endgame transformation. Reach level 50 as a Necromancer, complete the lich quest, hand a demi-lich the *dagger of oblivion* and a *black-sand hourglass that counted your mortality*, then say "immortality." The engine caps your Charisma at 10, drops you to level 46, wipes your memorized spells, exiles you from several cities -- and, in a beautiful implementation detail, the line that would change your actual race is *commented out*. You stay racially human/drow/yuan-ti; your class change is what makes the engine treat you as undead.

The tragicomic part: the full quest chain is data-complete -- both items are real quest rewards from real NPCs -- but the bundled debug logs record the converter NPC and the dagger as "Bogus" across five older boots. The single coolest transformation in the game may have been silently broken in production for years, and nobody noticed, because almost nobody ever got far enough to try.

Also preserved: **berserkers** and **monks**, disabled in character generation but extensively present, including a one-shot berserker-to-warrior conversion routine noting the class was removed "for reasons of balance."

## The devs, in their own words

The comments are a time capsule of 1990s MUD development. The undisputed champion, from email_reg.c:

> "Omg this is a huge routine. Fuck it, it works, suck me. o_o"

Many immortals are hardcoded directly into personalized procs -- Mystra, Lloth, Cyric, Mask, Shar, Azuth, and others. And the staff guide contains a remarkably candid indictment of the pre-split Outcast gods: cheating, granting favors, feuding, contributing nothing, abusing power. It deliberately names no one. The Outcast 3 credits simply show the same old roster plus new names; the accused were punished by erasure. Somewhere in there is a whole novel's worth of drama, anonymized forever.

(One history passage was even mangled by a blanket find-and-rename into "when Outcast was Outcast... split and became Outcast" -- someone globally replaced the old name with the new one and destroyed the actual history in the process. Archivists, never do this.)

## One important warning

If you have a copy of this tree and you're thinking of publishing it: **scrub it first**. It contains a hardcoded universal master login password, committed player save files (including Miax's) with plaintext password fields, logged failed-password attempts, email addresses, and IP addresses. Preserve the code, but don't publish twenty-year-old credentials.

## Epilogue

Oh -- and I also have the Homeland codebase now, the CircleMUD port. But that's another story.

Thirty years on, the Sojourn family tree -- Copper and Black Knights at the root; Sojourn, Toril, Duris, Outcast, Exile/Homeland as the branches; EverQuest as the kid who went to the big city -- is still mostly undocumented. If you've got an old copy of any of these sitting in a folder somewhere: that's not clutter. That's history. Don't delete it.
