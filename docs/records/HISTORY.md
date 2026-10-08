# The history of Duris

Duris: Land of BloodLust is a Forgotten Realms DikuMUD that broke away from Sojourn in late
1995 to become a full-loot, good-against-evil player-killing game. It has been played, wiped,
moved, abandoned, rescued and forked for thirty years. This record puts together what can still
be found about that history: the game's own files, the version-control history in this
repository, archived websites, MUD listings, player reviews, wikis and the official news page.

It is written to be read as a story, but every claim has a source. Where sources disagree, the
disagreement is stated, not settled quietly. [Sources](#sources) lists everything used, and
[Conflicts and open questions](#conflicts-and-open-questions) lists what is still uncertain.

Researched 2026-10-06 and 2026-10-07. Handles (character names) are used for people throughout.
A real name appears only where it is already printed in a public copyright notice or a cited
public source.

## Contents

- [Timeline at a glance](#timeline-at-a-glance)
- [1. Before Duris: DikuMUD and Sojourn (1990-1995)](#1-before-duris-dikumud-and-sojourn-1990-1995)
- [2. The split (late 1995 to March 1996)](#2-the-split-late-1995-to-march-1996)
- [3. Beta and opening (March to September 1996)](#3-beta-and-opening-march-to-september-1996)
- [4. Old Duris on duris.org (1997-2001)](#4-old-duris-on-durisorg-1997-2001)
- [5. The lost years and the second team (2001-2006)](#5-the-lost-years-and-the-second-team-2001-2006)
- [6. Torgal's Duris and the New Age (2006-2010)](#6-torgals-duris-and-the-new-age-2006-2010)
- [7. Wipe 2011, Lohrr, and the end of the public history (2011-2017)](#7-wipe-2011-lohrr-and-the-end-of-the-public-history-2011-2017)
- [8. The official game carries on (2017-2026)](#8-the-official-game-carries-on-2017-2026)
- [9. The code goes public (2025-2026)](#9-the-code-goes-public-2025-2026)
- [The world and its lore](#the-world-and-its-lore)
- [The culture](#the-culture)
- [The codebase as an archaeological site](#the-codebase-as-an-archaeological-site)
- [Staff by era](#staff-by-era)
- [Addresses and machines](#addresses-and-machines)
- [Wipes that can be dated](#wipes-that-can-be-dated)
- [Conflicts and open questions](#conflicts-and-open-questions)
- [Sources](#sources)

## Timeline at a glance

| When | What |
|---|---|
| 1990-1991 | DikuMUD is written at DIKU, the computer science department of the University of Copenhagen. |
| 1993 | Sojourn is founded by Kris Kortright (Miax), Tim Devlin (Cython) and John Bashaw (Gond), set in the Forgotten Realms. |
| Nov-Dec 1994 | Sojourn gets its AD&D-style spell memorization system, coded by Torm (Markus Stenberg). |
| 1 Jan 1995 | Sojourn player wipe; the "Sojourn 1" era begins. |
| Late 1995 | Sojourn splits. Toril continues as the non-player-killing line; Duris becomes the player-killing line. The Mud Connector lists Duris as created in December 1995. |
| Dec 1995 | "The Dream": Sojourn loses its backups and about a month of play, and is restored using code provided by Duris. |
| 17 Mar 1996 | "DURIS IS BORN!" The first Duris news entry, a manifesto signed by "The imps of Duris: Land of BloodLust!" |
| 23 Apr 1996 | Sojourn's old news is wiped. Player killing is in, and Waterdeep has been renamed Verzanan. |
| 10 May 1996 | Tavril releases DE, the Duris zone editor, on `ftp duris.sojourn.com`. |
| ~1 Sep 1996 | Duris opens to the public after its beta ("WHAT OPENING MEANS"). |
| 23 Sep 1996 | Guilds (associations) go in. |
| 14 Mar 1997 | The frag counter is added. |
| 1 Apr 1997 | The game moves from `duris.mi.org` to `duris.org` port 6666. |
| 11 May 1997 | A new website opens at www.duris.org, designed by Paradox. |
| 6 Feb 1998 | A live status page shows 90 players online (69 good, 21 evil); the record for that boot was 111. |
| Apr 2001 | Cython, Tripod and Stravag announce Cypod Interactive and a 3D racewar MMORPG with the working title "Duris3D". The last archived Duris pages at duris.org date from July 2001. |
| 24 Nov 2002 | At durismud.com, Ilienze announces a player wipe and says that "Kvark and I" will add new things. The game is at `durismud.org` port 6666. |
| 2003 | Player reviews remember "200+ heavily addicted players on nightly"; the count now "rarely tops 70". |
| 9 Oct 2005 | The surviving version-control history begins: a CVS import of `lib/` by tharkun. |
| Mar 2006 | Duris runs at `duris.game-host.org`. Torgal removes the undead races (24 Mar). |
| 2006-2007 | The credits read "Duris Currently Run By: Torgal and Kvark". |
| 4 Jan 2008 | The 2008 wipe: new maps, new zones, Winterhaven as the good hometown, and guilds that "can become a kingdom". durismud.com announces "The new age has begun!" |
| 2008-2009 | The game settles at `mud.durismud.com` on ports 7777 and 443. |
| 12 Aug 2009 | The C source enters version control. |
| Jun-Jul 2010 | The project moves from SVN to git. In the July 2010 player wipe, Tharnadia replaces Winterhaven. |
| 23 Oct 2011 | A press release calls Duris "the longest serving PVP Diku Mud on the internet". |
| 14 Apr 2012 | The "wipe 2011" player wipe lands, more than a year in the making. |
| 12 Sep 2014 | A player and equipment wipe; the listing promises "over 150 000 rooms" and "almost 20 years of growth". |
| 17 Feb 2017 | Lohrr's last commit, the last in the public history before 2025. |
| 2018-2026 | The official game continues on private code at durismud.com, with Torgal still involved and regular wipes. |
| 27 Jul 2019 | "We're Back!" The official news honours Lohrr's work as Overlord. |
| 7 Jan 2020 | A wipe "celebrates 25 years of Durismud" and is dedicated to Lohrr's memory. |
| 30 Dec 2021 | A "time capsule" of Duris as it was around 2002 opens on port 2002. |
| 31 Oct-2 Nov 2025 | Xanadin publishes the February 2017 source on GitHub and starts a test MUD. Arih brings up "a new server … the source code supplied by Xanadinn". |
| 6 Nov 2025 | The Community-Duris organisation is created. The revival's website becomes newduris.com. |
| 25 Aug 2026 | Zusuk (moshehbenavraham) begins a large modernisation of the community code. |
| 23 Sep 2026 | This repository's line and Community-Duris diverge (`e1357a30a`); this line was on GitLab from 28 Sep 2026 and has been on GitHub (`LuminariMUD/Duris`) since 8 Oct 2026. |
| 2026 | Three Durises exist: the original game at durismud.com, Community-Duris at newduris.com, and this repository duris.sbs . |

## 1. Before Duris: DikuMUD and Sojourn (1990-1995)

**DikuMUD.** Every Duris login screen still names the five people who wrote DikuMUD in 1990-91
at DIKU in Copenhagen: Sebastian Hammer, Michael Seifert, Hans Henrik Staerfeldt, Tom Madsen and
Katja Nyboe (`lib/information/greeting`, `lib/information/credits`, and the live login banner on
`mud.durismud.com:7777`).

**Copper, Black Knights Realm and Sojourn.** The people who built Sojourn had worked on the
Copper II and Copper III MUDs. A 1995 guidebook, *Playing MUDs on the Internet*, records that
when one MUD "went down in mid-1993, a different Mud spawned from it into what was known to many
as Black Knights Realm … The creators of this world would move on later to form … Sojourn."
Sojourn was founded in 1993 and set in TSR's Forgotten Realms. Wikipedia's TorilMUD article names
its founders as Kris Kortright, Tim Devlin and John Bashaw. On the article's talk page, Eileen
Kortright (who played as Mystra) wrote in 2007: "SojournMUD was created by Miax (Kris Kortright),
Gond (John Bashaw) and Cython (Tim Devlin)."

The Duris source code confirms all three on its own:

- `src/specs/specs.verzanan.c`: "Written by Kristopher Kortright (Miax) … Copyright(c) 1994".
- `src/specs/specs.halfcut.c` (the Jotunheim procs): "Copyright 1997 - Tim Devlin (Cython)", with
  a duris.org address.
- `src/core/structs.h` and `src/core/defines.h`: "John Bashaw, Gond of Duris"; and
  `src/core/files.h`: "Written by: John Bashaw … Copyright 1994".

Waterdeep was the first zone built entirely for Sojourn (Wikipedia). Brad McQuaid, who went on
to create EverQuest, played Sojourn; Wikipedia says that with Kortright's permission he used it
as the model for EverQuest's city of Freeport. In 1995 the guidebook
called Sojourn "now the leader in advanced code and new Zone creation". In 1996 *Yahoo! Wild Web
Rides* remembered it as "a gargantuan MUD … It had over 400 players at peak times, and some of
the most highly modified code in the land."

**The memorization system.** Sojourn added memorized spells in December 1994 (TorilMUD forum
timeline). The comment heading `src/classes/memorize.c` still preserves its author's opinion:
"Spell memorization system code mainly by Markus Stenberg (/ Torm of Duris) 11/94 … This is
really adnd-lookalike memorization/scribing system, which I personally hate, but which other gods
insisted on - shrug." Torm is on the in-game list of pre-split Sojourn coders, alongside Gond,
Nebelun, Brandobarius, Proteus, Mookie, Pizza, Rillifane, Miax, Cython and Requiem
("Copyright 1994, 1995 - Sojourn Systems ltd.").

Sojourn wiped its players on 1 January 1995. According to Toril's own history, that wipe began
the "Sojourn 1" era, whose forgers were Mystra, Lloth and Cython.

## 2. The split (late 1995 to March 1996)

*Yahoo! Wild Web Rides* (1996) tells the split this way: "But gods are vain and so are coders.
Having different opinions on the future direction of Sojourn, they took the code and went their
separate ways. The world was split into two main offshoots: Duris and Toril."

**When.** The best evidence puts the split in late 1995:

- A 2020 timeline on the TorilMUD forums gives "The split: Sojourn1---> Toril1 | Duris - Late
  1995". It also records "The Dream" (around December 1995), when Sojourn lost its backups and a
  month or more of play, and notes that "the restoration from the dream was done using Duris
  provided code". The earliest Usenet reference it found to Duris is dated 20 March 1996.
- The Mud Connector listing says Duris was "Created: December 1995".
- The in-game credits date "Old Duris" as "Copyright 1995, 1996 - Duris Systems Ltd."

Wikipedia and its copies say 1996, citing the 1996 book, but the book gives no year for the
split. Mudstats says Duris was "founded in 1994"; that is probably the Sojourn code's copyright
year, not the split.

**Who went where.** Toril's staff describe Toril 1 (1995-1998) as Sojourn's direct continuation,
with Mystra, Gond and Lloth as its forgers. Cython, a Sojourn 1 forger, went with Duris. The 1998
Duris website lists "DURIS Creators" as Fafhrd, Cython, Tavril, IO, Primus, Timken, Alyx, Krov
and Tasfalen, with "DURIS Server and Machine: Cython" and "DURIS Site provided by: Sojourn Systems
Ltd". Sojourn's infrastructure still hosted early Duris: the first zone editor was released on
`ftp duris.sojourn.com`.

**"DURIS IS BORN!"** The first entry in Duris's news, dated 17 March 1996, is a manifesto
(archived in the 1998 website's news page):

> Rising phoenix-like from the ashes of what was once Sojourn, the all time most popular dikumud
> ever, Duris will head off in the origional direction that Sojourn was _SUPPOSED_ to go in all
> along that being a place were people go FIRST and FORMOST to have _FUN_ … without being hassled
> by gods or bogged down with endless rules …
>
> Duris will be a FAR darker, and FAR more deadly world that Sojourn was. If what you are looking
> for, is a _nice_ _safe_ or _friendly_ mud, where you are protected by artifical code from being
> killed by someone, even another player, then Duris is NOT the mud for you. We do NOT care about
> having 500 players online … Duris will be a race-war pkill mud, with a world many many times
> larger, and code many many times more complex then what Sojourn had.
>
> — The imps of Duris:Land of BloodLust!

Toril went its own way: Toril 1 shut down on 20 September 1998, Sojourn 2 ran from Christmas
1998 to January 2000, Sojourn 3 from May 2001 to 2003, and since 2003 the line has been TorilMUD.

## 3. Beta and opening (March to September 1996)

The 1996 news (archived on the 1998 website) shows Duris turning Sojourn's world into its own:

- **23 April 1996.** "The old NEWS files from SojournMUD have been wiped." So far: "PK was added
  to the mud, the language system re-added, Waterdeep has been renamed Verzanan until a
  replacement can be made, a background story for Duris was added (check login screen) which
  departs from the Forgotten Realms theme". Planned: justice code, new races and classes, a new
  combat system, Drow, Duergar, Orc and Barbarian hometowns, and "a detailed world map with new
  zone placement".
- **10 May 1996.** New zones go in: the Elemental Planes of Water and Earth, Shadamehr Keep,
  Dreggan Woods, Braddistock Mansion, the Arachdrathos Wilderness, the Ethereal Plane, Dragonnia
  (a zone Sojourn had removed in 1995) and an expanded City of Brass. Jail code and "mob narcs"
  arrive. "Tavril has a new zone editor done for DOS/Windows … ftp duris.sojourn.com
  /pub/DE100.ZIP."
- **13 May 1996.** The grey elves get a new home, Sylvandawn ("It looks a lot like Leuthilspar
  though"). The player files are wiped to make room for the new spell system.
- **22 May 1996.** Xyzom opens the drow ghetto for testing while he builds it: "I am striving to
  make the drow race unlike any other race here to play."
- **30 May 1996.** "Replaced all occurances of Waterdeep with Verzanan. Replaced all occurances
  of Trackless Sea with Timeless Sea … This starts the process of renaming and editing Sojourn
  zones". This is why Duris's human capital, Sojourn's first zone, is still called Verzanan.
- **31 May 1996.** The berserker class is removed, and berserkers become psionicists, the new
  class that came with the Illithid race. Zones are moved "to fit a new map and increase zone
  usefulness and geographic realism".
- **June 1996.** Khildarak (the duergar city), the River Styx, the Seacaves, shape-changing, and
  mobs that have real classes.
- **31 August and 1 September 1996.** New character creation, then the opening notice:

  > Opening does NOT mean 'done' … it certainly does NOT mean 'STATIC' … What opening does mean
  > is that you, the player, can be secure in the fact that none of your hard work will be lost.
  > We chose now to open because we have enough good/evil balance to support race wars …

- **23 September 1996.** "Guilds are in!" The guild chat channel, `gcc`, follows on 26
  September.
- **9 November 1996.** A major rework of the evil races. Evil players get one week to switch to
  a good race: "AFTER 11/16/96, NO MORE EVILS WILL BE ALLOWED TO CHANGE TO GOODS!"

## 4. Old Duris on duris.org (1997-2001)

**1997.** Ships were re-added on 28 February ("there is now an actual living person standing
there selling the boat to you"). By 11 March, "Over 200 bad exits have been fixed on the oceans,
so now you ship captians can sail around the world." The frag counter came on 14 March: "Any time
you kill a racewars player, you gain a frag and the dead guy loses a frag." On 1 April: "Duris new
address is duris.org 6666 same ip as before … duris.mi.org 6666 will only work for a little
while longer!" A new website opened at www.duris.org on 11 May. On 13 May, version 2.89b of the
editor, now called dikuEdit, appeared on `ftp://mud.duris.org/pub/` in DOS and Linux builds,
along with the new centaur race.

**The gods, mid-1997.** The wizlist on the 1998 site (last edited June 1997) has two Overlords:
Cython ("the Darklord, God of Evil and the Night") and Fafhrd ("Another one of them damn Imps").
The Implementors were Ilienze ("the World Destroyer"), Tavril ("Lord of Editors"), Tasfalen
("Shadow Lord of Justice") and Paradox ("Mistress of Time"). See [Staff by era](#staff-by-era).

**February 1998.** The website, designed by Paradox, shows the game at its first peak:

- The machine, `mud.duris.org`, had two Pentium II 300 CPUs and 256 MB of RAM, ran Linux 2.0.32,
  and was connected by a T1 line through sierranv.net. It ran the game, the test MUD, the website
  and the mailing list, and was its own DNS server. "Speical thanks to the gods and players have
  helped fund the high cost of running Duris": Cython, Tavril, Osrell, Timken, Tripod, Tasfalen,
  Xyzom, Wug, Ilienze, Xueqin and Zalrix.
- The live status page at 20:39 EST on Friday 6 February 1998 read: "It is 5pm, on the Day of the
  Storm, The 22nd Day of the Month of The Harvest Moon, Year 220 … Good race players 69, Evil race
  players 21 … Total players in game: 90. Record number of active players in game this boot: 111."
- "DURIS 100% PLAYER-RUN ASSOCIATIONS!" listed eleven guilds: Scions of Isis, Circle of Illusion,
  Order of the Fireforge, The Rowan Circle, Clan BloodLust, Exodus of Light, Legends of Old,
  LEGION, Clan Love Tentacle, Dakhira's Madness, and the Cult of Dissolution.

**Spring 1998.** The in-game `oldnews` file in this repository (`lib/information/oldnews`) keeps
the news from 5 March to 29 April 1998. On 5 March the Pine Hollow rings were downgraded: "Thank
LoO for their cheesy abuse of zone resets", LoO being Legends of Old. Player kills under level 20
stopped giving experience and the rest doubled (7 March). "Evils may no longer toggle who"
(11 March). Monks returned (21 March). On 25 March came a joke entry: "A new spell called 'mage
flame' … When cast, it kills everyone. Have fun experimenting." Aerial combat arrived on
17 April. On 27 April: "the mud was down over the weekend due to the power supply dying." On
9 March Celistra was appointed Paradox's assistant on the web, and players were told to use
"duris.org" rather than "www.duris.org".

**The forums, 1999-2001.** From 1999 duris.org ran an Ultimate Bulletin Board with Battle Logs,
Balance, Bug Reports, DE Help, Fake Logs, Gamer Zone, the Flame Board, a Zone Forum and a Player
Council Feedback Forum. The archived thread titles carry the period's mood: "Took me long enough
to frag", "Why evils are F#$%ed." and "Why goodies are F#$%ed." (both in the Player Council
forum, April 2001), "Ogre Slam makes this game no fun at all", and a November 2000 battle log
whose title is a client trigger: "trigger {Tolm is dead! R.I.P.} {g avernus tolm}".

**October 2000.** The staff pages list the Overlords as Cython, Tripod ("God of the Well Hung!"),
Fafhrd and Tavril ("Ruler of the Free World"). The Implementors are Paradox, Orcus, Xueqin,
Ilienze and Zod ("'The Body' Ventura - King of Kingdoms"). Greater Gods: Bellini, Foo ("Bill
Gate's Towelboy") and Clavados (aka "Mr. Sensitive"). Lesser Gods: Zileas and Melkivar. By March
2001 the second rank had been renamed from Implementors to Forgers, the name it still has in the
code.

**Duris3D, April 2001.** The duris.org front page announced:

> Cython, Tripod, and Stravad have formed a new venture called Cypod Interactive. The first
> project by Cypod Interactive will be a MMORPG with the working title: 'Duris3D' … The game will
> be set in the Duris universe, and will be a racewars based game, with full PKilling!

The "People Behind the Mud" page now read "©1994-2001 CyPod Interactive". Nothing more is known
of Duris3D. The last archived Duris pages at duris.org, the forums among them, date from 6 July
2001. By late 2003 the domain shows an unrelated personal website.

**Basternae.** Duris has a sibling as well as a parent. Basternae II (later Basternae: Phoenix
Rising) was another good-against-evil racewar MUD in the same family. Its Magma codebase includes
a `convzone` tool that converts "Duris zones made with older DikuEdit versions", and its credits
have a section "regarding Duris" naming "DikuEdit: Tavril". A comment in `src/core/smoke.c` says
the herb-smoking system was "Originally coded for Basternae II by Sniktiorg Blackhaven" and later
rewritten for Duris "with help from Lohrr" (27 July 2016). Sniktiorg also built Tharnadia, the
human hometown. A 2012 player review recalls starting "duris (and then basternae)". A Usenet
thread titled "Duris/Basternae/Ciannech Rumors" (rec.games.mud.diku) is about copies of Duris and
Basternae code and areas; it could not be read for this record. See
[Conflicts and open questions](#conflicts-and-open-questions).

## 5. The lost years and the second team (2001-2006)

What happened between Cypod's announcement and the mid-2000s is the least documented part of the
story. The in-game credits split it into "OLD DURIS" (Copyright 1995, 1996 - Duris Systems Ltd.)
and "CURRENT DURIS" (Copyright 2000 onward - Duris Mud Project). The fan wiki's credits page says:
"In 2000, after a brief haitus of four years, Duris was resurrected by a new team in an attempt
to keep history alive." The four-year gap does not fit the evidence: the duris.org news, website
and forums show the game running continuously from 1996 to 2001. The "Copyright 2000" date, and
a new team taking over around 2000-2001, do fit.

**2002.** By December 2002 a PHP-Nuke site at durismud.com described itself as "still in heavy
development". It said "telnet to durismud.org port 6666" and ran a poll asking "How did you first
hear about Duris?", one answer being "When Sojourn split into Toril and Duris." Its news shows
the team at work:

- 6 Nov 2002: guard towers removed from the main good-race landmass so that the justice code can
  be redone.
- 11 Nov 2002, posted by Clav: "Duris is in CHAOS mode, so you can get free equipment and levels
  for 1 day while we fix a server time problem". This is the earliest dated Chaos mode found; it
  survives in today's code (`docs/reference/CHAOS_MODE.md`).
- 17 Nov 2002: a poll on fixing the "EQ flood" (equipment inflation), with the options of
  equipment wipes, quality lost on repair, and items "poofing" from enemy corpses.
- 24 Nov 2002, posted by Ilienze: "I have decided to do a pwipe today right now clean slate for
  everyone. Kvark and I will be adding some new things and fixing a few bugs then the mud will go
  back up."

**2003.** Reviews on TopMUDSites show both the loyalty and the strain. Praise: "Duris is the book
to EQ and DAOC's movie" (October 2003), and "Players have lost their minds, educations, jobs,
spouses and credit lines playing this mud" (February 2003). Complaint: "Once upon a time it had
200+ heavily addicted players on nightly. Now the regular number of players in game rarely tops
70." The same review accused the immortal hosting the game of deleting critics' characters. The
claim was never tested; it is recorded here only as evidence of the era's disputes.

**2004.** The phpBB-era durismud.com (April 2004) gave the address as `durismud.org 6666` and the
IP as 82.182.81.121. Kvark had just added "Todays PVP", public logs of player-against-player
fights. Kotil, a quest god, ran world events: rampaging dragons whose scales could be forged into
items, the pirate Redbeard's attempt to escape by sea, an overbreeding plague of Evermeet's
"kooshie" dogs, and stolen city relics. A comment in `src/mob/name_gen.c` reads "Modified by
Kvark (June 2003)".

**2005-2006: moving around.** On 9 October 2005 the version-control history in this repository
begins with tharkun's CVS import of `lib/`: properties, help and information files. The source
code was not added until 2009. Through 2005-2006, balance changes made in game were committed
automatically under the changing god's name, for example "Tharkun: vamping.hellfire from 2.500 to
1.000" and "Clavados: stats.str.Ogre from 160.000 to 165.000". Weebler, one of the help-file
writers the credits name (with Axxa and Illuminati), reworked the help index from late 2005. In March 2006 a reviewer wrote: "I left the game for about two
years when it was moving around alot. Now it has a stable home again." Another gave the address:
`telnet duris.game-host.org 6666 or 4444 or 443`. On 23 March 2006 Torgal "changed references from
durismud.com/org to durismud.net". The next day he removed the undead races, the third side of
the racewar: "looks really unprofessional when you can't choose all the races listed".

## 6. Torgal's Duris and the New Age (2006-2010)

**Torgal and Kvark.** The in-game credits of 2006-2007 read: "Duris Currently Run By: Torgal and
Kvark", with coders Torgal, Kvark, Tharkun, Clavados, Gragt and Lom; the Areas Group of Clavados,
Railand, Beretorn, Fotenak, Phirae, Astansus and Zion; and "Duris Server and Machine: Torgal".
Torgal also appears in the credits among the Old Duris coders and as the Old Duris web-site
maintainer, so he links the two eras. The 2007 wizlist titles him "Torgal the Subversive"; Kvark
is "the God of MetaGrunking". Cython, Fafhrd and Tripod are listed as Honorary Overlords on every
wizlist from then on.

**The 2008 wipe and the New Age.** Torgal branched `wipe-2008` on 13 October 2007, and the branch
became trunk on 7 December 2007. The player wipe took place in early January 2008; one review
calls it "January 4th". The overview in the 2008 news file (`lib/information/news` as of
`0b1903dbc`) lists:

- "Brand new maps. Time to explore!"
- "New main good hometown: Winterhaven. All good races can start there."
- "Two new PC races: Githzerai for goodies, Orog for evils." Harpies were no longer playable.
- "Necromancers can now remort into Lich if they have enough epics."
- "The guild system has been restructured … you build your guild based on guild prestige points.
  Can become a kingdom and war other guilds and much more."
- Zone trophies by experience gained, experience split across the group, and group caps (evil 4,
  good 8).
- "Immortals that are active as players can only have Immortal Rank."

Reviewers saw it as a rebirth. "Duris has been recreated from the ashes once again, with a brand
new face" (April 2008). "You can choose a character, specialize it, then eventually through skill
points (gained by zoning or pkilling) you can gain new skills" (January 2008). By 2009 the
durismud.com front page read "The new age has begun!", with the address
`telnet://mud.durismud.com:7777 or 443`, and four chapters of in-world history told by the
historian Azoormarel (see [The world and its lore](#the-world-and-its-lore)). On 14 February 2008
the game moved to "a new server in the same data center, but with dual processors and a super
fast hard drive". Outposts and buildings were "started by Torgal in 2008 and then continued by
Venthix in 2009" (`src/world/outposts.c`).

**2008-2009 staff and players.** Jexni, a member of staff, answered a critical review in July
2008: "We regularly see 40-50 people logged in at peak times." An anonymous reviewer that summer
listed three problems: the administration, balance, and "the game source has been leaked numerous
times". The 2009 credits read "Run By: Torgal, Lucrot", and later "Torgal, Zion, Lucrot". Lucrot
made 539 commits between October 2008 and May 2010. On 12 August 2009 Torgal moved the source and
areas into the repository ("it should have always been this way"). A new fan forum, durisforum.com,
was announced in July 2009. An October 2009 review gives "an average playerbase of around 50-75
people".

**2010.** This was the busiest year in the history: 1,572 commits, mostly by Venthix, Kitsero,
Odorf, Lucrot and Torgal. In June 2010 the project moved from SVN to git; on 27 July Venthix was
"still learning the finer points of git". Kitsero added the Kuo Toa, Kobold, Planetbound Illithid,
Eladrin and Wood Elf races. The July 2010 player wipe brought "PWIPE CHANGE! Tharnadia replaces
WH" (Keja, 6 July), and the human city returned as the main good hometown. By 2011 the front page
read "The Next Age has begun!" and pointed to Twitter accounts @durismud and @durismudpvp.

## 7. Wipe 2011, Lohrr, and the end of the public history (2011-2017)

**Wipe 2011.** A `wipe2011` branch, worked on from April 2011 by Jexni, Venthix and Seif among
others, reworked magic resistance, healing, melee, skills and the world quest. It shipped as
"tonights pwipe" on 14 April 2012 (Venthix). That wipe added the Jade Empire capital Mitashi,
removed ethermancers, illusionists and Kitsero's new races, and disabled monks and multiclassing.
The fan wiki on Fandom was created on 21 April 2012; its welcome text was written by Maulrok.

**The 2011 press release.** On 23 October 2011 "Duris Mud is the longest serving PVP Diku Mud on
the internet!" announced "on average 100 different players from all over the world in the game
at all times", a ship-combat system with "14 different types of ships", and telnet on port 7777
or 443. It claimed to have been "Free for over 13 years".

**2012: a hard year.** Mud Connector reviews from April to December 2012 describe staff and
player quarrels: a character deleted during a staff-run quest, forum moderation disputes, and
long-time players leaving. Others in the same months defended the staff and the game. The game
went on: hardcore characters (a separate high-risk mode) appear in the code from 2011-2012, and
Kitana (635 commits, October 2012 to March 2014) added the achievement system in April 2013 and a
`wipe2013` branch that November.

**Lohrr.** Lohrr made 2,385 commits between September 2011 and February 2017, more than anyone
else in the history. He added towns with troops (December 2013), siege engines (ballista,
battering ram and catapult, December 2013, persisting through boots from April 2014), and a
`shutdown pwipe` command that wipes the player database and files in one step (August 2014). He
also carried out the 12 September 2014 wipe, the equipment wipes of July 2015 and January 2017,
the object-oriented rewrite of associations (2016), and the herb-smoking system with Sniktiorg
(2016). The credits of this period read "Duris Currently Run By: Torgal, Lohrr", with coders
Torgal, Lohrr, Odorf, Lom, Venthix, Alver and Jexni. The in-game `pleasantry` command, which
makes a punished player blurt out fawning lines, includes "Man, Lohrr really has done a lot of
work on here. We should cut him some slack for all the sleep he's lost."

The Mud Connector listing was last updated on 20 August 2014. It promised "over 150 000 rooms",
"Nearly twenty years of growth", and "Multiple continent world with real-time, in-game ANSI
graphical maps".

**The end of the public history.** On 17 February 2017 Lohrr committed "Added changing racewar
sides of guilds by immortals." It is the last commit before the code resurfaced in 2025, and
6,684 commits lead up to it from the 2005 import.

## 8. The official game carries on (2017-2026)

The public code stops in 2017, but the game did not. The official news page at
durismud.com/news, read on 2026-10-07, runs from September 2018 to July 2026. It shows the
official game continuing on code that kept changing after the February 2017 snapshot:

- **September 2018 to January 2019.** A run of fixes and balance changes. One entry reads: "I owe
  everyone an apology. As of Aug 13, 2014, the wisdom spell damage reduction has been using the
  caster's wisdom instead of the target's."
- **27 July 2019, "We're Back!"** "MOTD has been permanently adjusted reflect Lohrr's
  participation and contributions to Duris during his tenure as Overlord. A tribute mob is
  planned, in his honor, to be added to the world when we wipe."
- **9 December 2019.** "After 7.5 years and a recent server uptime of 605 days, the mud has been
  moved to a new server and is now being hosted inside of a Docker container … since 32bit VMs
  are getting harder to find. R.I.P. bahamut.durismud.com, and welcome ixie.durismud.com!"
- **7 January 2020.** "DURIS HAS WIPED!! This wipe celebrates 25 years of Durismud, and is
  dedicated to the memory of … Lohrr. May he always be remembered!" In the same wipe, "Ceothia has
  had some changes, courtesy of its original designer (thanks Cy!)". Ceothia is credited to Cy.
- **1 January 2021.** "The avatar of Lohrr has replaced the witch doctor."
- **30 December 2021.** "Check out a 'time capsule' of Duris history and experience the mud from
  around the year 2002: telnet mud.durismud.com 2002". It still answered on 2026-10-07.
- **Wipes continued:** 25 February 2022 ("There will be chaos"), 29 October 2022, 21 July 2023,
  4 May 2024 (with Vampire as a new neutral race), 30 December 2024 and 9 January 2026.
- **2026.** On 18 February Torgal signed a news entry: flying transports and ferries "were some of
  my favorite things I (Torgal) ever implemented code-wise". Later that year came a racewar
  balance system that gives the losing side bonuses (23 March) and a "boons" system (April).
  The latest entry read was dated 7 July 2026.

Players kept their own records. The fan wiki was still being edited in 2024, including by Drevarr.
It links a Duris Discord and a Facebook group. Drevarr's DurisParser (2022) charts each wipe
("season") from the public PvP logs, and his "2021 Wipe Charts" compare deaths by wipe from 2014
to 2021.

## 9. The code goes public (2025-2026)

**Private copies.** Several people held copies of the 2017 code. In this repository, commits by
Adam Borowski (kilobyte) carry author dates from 2 February 2021 through 2025. They include UTF-8
conversion of the world files and a `chaos` command "for testmud/chaos". They were merged into
the public line from November 2025.

**Publication.** The GitHub repository xanadinn/DurisMUD was created on 31 October 2025. Its news
file reads: "11/01/2025 Test mud is up … this version of Duris is from Feb 2017 … - Xanadin (old
imm from 2005-07, played as Mabort and Bahb before then)". Mabort is credited with building The
Bronze Citadel and The Plane of Avernus. On 2 November the news file of a second line read: "New
server is up! … the source code supplied by Xanadinn - Arih". Its credits gained a new block,
"Current DURIS … Run By: Arih … Copyright 2000 - 2025", added by resakse along with account-based
logins (eight characters per account) and bcrypt passwords on 7 November. resakse merged
kilobyte's work as pull request #1 the same day.

**Community-Duris.** The Community-Duris organisation was created on 6 November 2025. On
14 November it merged Xanadin's test MUD code ("MergeWithTestMud"). It added Tieflings (Owen,
11 November) and WebSocket and GMCP support (resakse, December 2025). Its wizlist (26 November
2025) names Xanadin, Fotenak, Tyrus and Kitsero as Overlords and Eikel as Forger, with Cython,
Fafhrd and Tripod still Honorary Overlords. On 8 December the message of the day became "New
Duris is up and running … http://www.newduris.com". On 13 December Xanadin was "removing
durismud.com from more places". Liskin joined in late December 2025 and went on to lead the
project. The current Community-Duris/Duris repository was created on 24 August 2026.

**2026.** From 25 August 2026, Zusuk (moshehbenavraham, founder of LuminariMUD) did a large
modernisation of the community code: the source tree reorganised, warnings treated as errors, a
test suite, documentation, and a flat-file backend
(see [CREDITS.md](CREDITS.md)). Community releases that year brought kingdoms built on
guildhalls (a design the 2008 wipe had promised), Chaos events, ships and quest records. The
September 2026 news gave players a "catch-up" covering December 2025 to September 2026. On
23 September 2026 (`e1357a30a`) this repository's line and Community-Duris diverged. This line
lived on GitLab from 28 September 2026 and has been on GitHub at `LuminariMUD/Duris` since
8 October 2026.
[COMMUNITY_DURIS_TRACKING.md](COMMUNITY_DURIS_TRACKING.md) records what each line has done since.

So, thirty years after "DURIS IS BORN!", there are three Durises: the official game at
`mud.durismud.com:7777`, where Torgal is still writing code; the Community-Duris revival at
newduris.com; and this repository `mud.duris.sbs:7777`.

## The world and its lore

**Dakhira, the Black Sun.** The 1997-98 website's lore page, credited to Cython and Zarland, sets
the tone the founders wanted: "From the east, the first glimmers of the Black Sun, Dakhira, cast
their evil light upon the planet. Perpetual twilight hugs the land … Thus comes the time of the
Bloodlust, and as idle thought ravages your mind, you realise… 'Here is where I shall die.'" The
Darklords' hordes ride "the blackest of Durian dragons". The fallen soldier's soul is pulled
"into the heart of the rift in the sky … as Dakhira grows and strengthens". The greeting screen
(`lib/information/greeting`) still signs off: "Welcome to Duris, Land of Bloodlust.. Where death
waits around every corner.. We warned you!" Hidden in its ASCII art are the names Cython, Fafhrd,
Ilienze, Primus, Tripod and Zarland.

**Forgotten Realms roots.** The 23 April 1996 news says the new background story "departs from
the Forgotten Realms theme", but the Realms are everywhere in the world files: Verzanan (once
Waterdeep), Undermountain, the Moonshae Islands, Neverwinter Woods, Myrloch Vale, Evermeet,
Jotunheim and the Underdark (`lib/misc/lookup.zon`). The races are AD&D's: githyanki and
githzerai, illithids (the "squids" of player slang), thri-kreen, duergar and drow.

**Azoormarel's history (2008).** For the New Age wipe, durismud.com published four chapters
narrated by the historian Azoormarel. In the first, the magus Lokpan seizes godhood in his fortress
at Mount Banishment in "Year 516". Torgal, "the unassuming Overlord of the heavens", freezes him
"with a powerful gaze" and hurls him back to earth, where he "crashed into Mount Banishment, and
caused it's ruination". In "The Downfall of the Light", the lands around Tharnadia are overgrown
after Year 528. Bands of orcs, ogres, duergar and goblins close on the city, and on the night of
the Grand Harvest a rumbling begins beneath its noble quarter. That tale leads into the
"Outcasts War". It matches the ruined Tharnadia zones (The Twin Keeps of Devastated Tharnadia,
The Ruins of Tharnadia's Old Quarter) and Winterhaven's turn as the good hometown from 2008
until Tharnadia returned in 2010.

**Scale.** The world grew from Sojourn's zones to "267 unique zones consisting of 162,900 real
rooms" (a listing quoted on mudstats). This repository's zone lookup holds 351 entries
(`lib/misc/lookup.zon`). The 2006-2007 credits list about 230 zones with their builders.
Clavados, Melkivar ("God of endless Zones"), Alachest, Xueqin, Miax, Kolut, Krzzn and Trask are
among the most frequent names.

## The culture

**The racewar.** "Duris consists of a delicately balanced world in which the Good and Evil races
battle one another in the endless pursuit of equipment, frags and more importantly, bragging
rights" (fan wiki). Evil is meant to be harder. The help file (`help racewars`) says evil and undead races are
"blind on the surface world during the day … ANY evil-raced person on the surface will be hunted
down by powerful good-raced PC's and killed on sight." There were once three sides: the code still
defines `RACEWAR_UNDEAD` and `RACEWAR_NEUTRAL` (`src/core/defines.h`). The undead races were
removed in March 2006, and vampires returned as a neutral race on the official game in 2024.

**Full loot and frags.** The FAQ answers "Is player killing, stealing, corpse looting allowed?"
with "Hell yes! Duris is a FULL pkill MUD". The frag, a kill on the other side, has been counted
since March 1997. `help frags` explains that the term was "originally taken from the Vietnam
War". A 2006 review: "you get a rush when your char's eq and life are on the line. Fights range
from 1v1 to 13v13 mega battles." A 2012 review describes the first death almost every new player
has: "A Grey Elf snaps into visibility! A Grey Elf's bash sends you sprawling! … You have died."

**Guilds.** The eleven player-run associations of 1998 are listed in section 4. Clan BloodLust's
own page: "In the dark, twisting passages of the Underdark, Clan BloodLust rules supreme … At first
light, the battle-enraged Clan retreats silently back into the ground from whence it came, bearing
many trophies of its recent slaughter." The Rowan Circle was "founded on the principles of
Friendship, Honor and Trust." Guild rules in the help file limit a player to seceding from three
guilds "EVER".

**Wipes.** Duris resets its players and equipment regularly; the dated ones are listed under
[Wipes that can be dated](#wipes-that-can-be-dated). Each wipe is a season, starting with a level
cap and often a period of "chaos" with free gear. The code has a `shutdown pwipe` command (2014)
and an `EQ_WIPE` switch (2015).

**Gods and in-jokes.** The immortals' humour is part of the archive:

- The wizlists are written in character. The late-1990s list (`lib/information/wizlist.tmp`) is
  in leetspeak: "Cython +h3 D4rkl0rd G0d 0ph 3v1l 4nd +h3 N1gh+", "Paradox B1+ch G0dd3zz, M1s+r3zz
  0f +1m3", "Melkivar G0d 0ph 3ndl3zz Z0n3z", "Zod '+h3 B0dy' V3n+ur4 - K1ng 0ph K1ngd0mz".
- `help kvark` describes Kvark as "a language script created by the MUD with the intention of
  destroying the English language". `help kenon` covers its successor script, and `help tolm` a
  player who "is simply a bot created by the gods of Duris for their amusement". `help coder`
  ends: "The fabled Foo is a mostly unknown to Duris, but oddly his name is scratched to the
  bottom of each boat."
- `help zone god` says the "Melkivar" and "Railand" scripts spend most of their time "correcting
  (herein known as rewriting) user submitted zonefiles."
- The `pleasant` command (`src/magic/magic.c`, `pleasantry()`) makes a punished player blurt out
  lines such as "Torgal rules! I hope I'm just like him when I grow up, minus the fu-man-chu!",
  "I heard Torgal spends money on the Duris link …" and, aimed at the sibling MUD, "Thank god this
  isn't Toril! I'd hate to play a game with no development!"
- The immortal commands `repiss` and `depiss` add a player to, or remove them from, a mob's
  hunting memory.

## The codebase as an archaeological site

The source carries its ancestry:

- **Sojourn underneath.** Header guards are still `_SOJ_STRUCTS_H_`, `_SOJ_CONFIG_H_` and
  `_SOJ_PFILES_H_`. `structs.h` warns that changes must be "documented to ~sojourn/Changed".
  `src/classes/psionics.c` still says "Part of Sojourn … Copyright 1994, 1995 - Sojourn Systems
  Ltd.", and so does `src/magic/affects.c`. Most other headers say "Part of Duris … Copyright 1994
  - 2008 - Duris Systems Ltd.". The 1994 start and the line "John Bashaw, Gond of Duris" (Gond
  stayed with Toril) suggest the headers were edited from Sojourn's, not written fresh. That is an
  inference from the evidence above.
- **1994 initials.** 26 comments are signed "SAM 6-94" or "SAM 7-94" (rerolling, hometowns,
  initial alignments, confirming commands), and more than 160 are signed "JAB", very likely John
  Bashaw, whose name heads several of the same files. They are older than Duris itself.
- **Named authors.** Markus Stenberg (Torm) wrote the memorization system (11/94) and
  `src/guild/guild.c`. Bard songs are "Copyright 1994, 1995, 2003 - Markus Stenberg, Michal
  Rembiszewski". `src/core/files.c` was "Written by: Andrew Choi, Modified by: John Bashaw". The
  text editor is "copyright (c) 1996 by Gary Dezern", who also wrote the storage lockers in 2004.
  The Verzanan procs carry Kortright's 1994 notice that the zone "is NOT freeware or shareware".
- **The zone editor.** `areas/de/` holds durisEdit 2.99c ("the handy-dandy zone creation and
  editing tool"). Its BSD-style license is "Copyright (c) 1995-2007, Michael Glosenger". The game
  credits its creator as Tavril and its later caretakers as Tharkun, Lohrr and Venthix.
- **Version control.** CVS from 9 October 2005, holding `lib/` only (balance changes were
  committed automatically under the god's name). SVN after that; its repository UUID is
  `7a2de714-…` in author addresses up to 11 June 2010. The source and areas were added on
  12 August 2009. Git from June 2010, on hosts named vella (2010), tiamat (2011-2013) and bahamut
  (2013-2017), with dev and macom for development.
- **Commits per year (all branches):** 21 (2005), 118 (2006), 125 (2007), 120 (2008), 690
  (2009), 1,572 (2010), 521 (2011), 543 (2012), 517 (2013), 1,019 (2014), 592 (2015), 709
  (2016), 137 (2017); then 492 (2025) and 3,555 (2026, to early October).

## Staff by era

These rosters are as the sources print them; titles are quoted.

| Source and date | Top tiers |
|---|---|
| Sojourn pre-split coders (in-game credits) | Gond, Nebelun, Brandobarius, Proteus, Torm, Mookie, Pizza, Rillifane, Miax, Cython, Requiem |
| Old Duris coders (in-game credits, 1995-96) | Tavril, Foo, Fafhrd, Io, Stravag, Primus, Cython, Timken, Alyx, Krov, Tasfalen, Ilienze, Torgal |
| Old Duris builders (in-game credits) | Tripod, Orcus, Cython, Ilienze, Clavados, Jera, Melkivar, Paradox, Sniktiorg, Astansus (help files: Osrell, Lowkie) |
| duris.org wizlist, June 1997 | Overlords Cython and Fafhrd; Implementors Ilienze, Tavril, Tasfalen, Paradox; Greater Gods Equinox, Xyzom, Dryzkul, Sehanine, Io, Primus, Timken, Xueqin; Lesser Gods Melkivar, Sniktiorg, Orcus, Ssseri; Immortals Mayla, Sabrae; Avatar Rand al'Thor |
| Leetspeak wizlist, late 1990s (`wizlist.tmp`) | Overlords Cython, Tripod; Implementers Orcus, Stravag, Ilienze, Paradox, Tavril, Melkivar, Zod, Foo; Greater Gods Clavados, Osrell, Mandrake; Honorary Overlord Fafhrd |
| duris.org staff pages, Oct 2000 | Overlords Cython, Tripod, Fafhrd, Tavril; Implementors Paradox, Orcus, Xueqin, Ilienze, Zod; Greater Gods Bellini, Foo, Clavados; Lesser Gods Zileas, Melkivar |
| durismud.com, Nov 2002 | Ilienze and Kvark running the game; Clav posting |
| durismud.com, Apr 2004 | Kvark, Kotil |
| Mid-2000s wizlist (`wizlista`) | Overlords Ilienze, Kvark; Forgers Io, Astansus, Tharkun; Greater Gods Vareena, Melkivar, Clavados, Talsim |
| In-game credits, 2006-07 | Run by Torgal and Kvark |
| Wizlist, July 2007 | Overlords Torgal ("the Subversive"), Kvark; Forgers Zion, Fotenak; Greater Gods Phirae, Axxa, Seif, Clavados |
| In-game credits, 2009 | Run by Torgal and Lucrot, then Torgal, Zion and Lucrot |
| Wizlist, Oct 2010 | Overlords Torgal, Kvark, Zion, Lucrot, Kitsero; Forgers Aliera, Odorf, Venthix |
| In-game credits, 2010 onward | Run by Torgal and Lohrr |
| Official news, 2018-2026 | Mostly unsigned and written as "the Admin team"; Torgal signs an entry in 2026 |
| Community wizlist, Nov 2025 | Overlords Xanadin, Fotenak, Tyrus, Kitsero; Forger Eikel |

Cython, Fafhrd and Tripod have been Honorary Overlords on every wizlist since 2007.

## Addresses and machines

| Address | When | Source |
|---|---|---|
| `duris.sojourn.com` (FTP) | 1996 | 10 May 1996 news |
| `duris.mi.org` port 6666 | 1996 to April 1997 | 1 April 1997 news |
| `duris.org` / `mud.duris.org` port 6666 | April 1997 to 2001 | 1997 news; 1998-2001 website |
| `durismud.org` port 6666 | 2002 to 2004 | durismud.com, Dec 2002 and Apr 2004 |
| `duris.game-host.org` ports 6666, 4444, 443 | about 2006 | Mud Connector reviews, March 2006; archive captures 2006-2008 |
| durismud.net (web references) | 2006 | Torgal's commit of 23 Mar 2006 |
| `mud.durismud.com` ports 7777 and 443 | 2008 to today | durismud.com 2009 onward; live 2026-10-07 |
| `mud.durismud.com` port 2002 | since Dec 2021 | the 2002 "time capsule" |
| Hosts vella, tiamat, bahamut, ixie | 2010, 2011-13, about 2012-2019, 2019 onward | commit author addresses; 9 Dec 2019 news |
| newduris.com | late 2025 onward | the Community-Duris message of the day and wizlist |
| mud.duris.sbs:7777 | 2026 onward | split from newduris 9/23 |

Websites: www.duris.org (1997-2001, by Paradox, with UBB forums); durismud.com (2002 onward; PHP-Nuke,
then phpBB, then the current site with News, PvP logs, maps and donations); the fan wiki on
Fandom (2012 onward); durisforum.com (2009-2010); and the official Twitter accounts (2011).

## Wipes that can be dated

| Date | Notes |
|---|---|
| 1 Jan 1995 | Sojourn wipe; the start of Sojourn 1 |
| 13 May 1996 | Player-file wipe for the new spell system, during the Duris beta |
| 24 Nov 2002 | Ilienze: "clean slate for everyone" |
| ~4 Jan 2008 | The New Age wipe: new maps, Winterhaven |
| Jul 2010 | Tharnadia replaces Winterhaven; new races |
| 14 Apr 2012 | The "wipe 2011" release |
| Aug 2012 | Equipment wipe enabled, then turned off |
| 12 Sep 2014 | Players and equipment |
| Jul 2015 | Equipment wipe |
| Sep 2015 | Multiclassing disabled "for this wipe" |
| 7 Jan 2017 | "EQ Wipe!" |
| 7 Jan 2020 | 25th anniversary, dedicated to Lohrr |
| 1 Jan 2021 | The avatar of Lohrr joins the world |
| 25 Feb 2022, 29 Oct 2022, 21 Jul 2023, 4 May 2024, 30 Dec 2024, 9 Jan 2026 | Official wipes |

Drevarr's charts cover wipes from 2014 to 2021, so there were more wipes in 2015-2019 than are
dated here.

## Conflicts and open questions

- **The split year.** Late 1995 is supported by the in-game copyright lines, the Mud Connector
  ("December 1995"), the TorilMUD timeline and the fan wiki. Wikipedia's 1996 rests on a 1996
  book that gives no year. The first Duris news entry is 17 March 1996, and the public opening
  was about 1 September 1996. Mudstats' "founded in 1994" matches no event and is probably the
  Sojourn copyright year.
- **The "four-year hiatus".** The fan wiki says Duris was "resurrected" in 2000 "after a brief
  haitus of four years". The duris.org news, forums and staff pages show the game running from
  1996 to 2001. Either the hiatus is wrong, or it refers to something else. Possibly the wiki
  counts from the end of "Duris Systems Ltd." (1996) to the start of the "Duris Mud Project"
  (2000).
- **Who ran Duris from 2001 to 2005.** Ilienze and Kvark in late 2002, and Kvark and Kotil in
  2004, are documented. Who owned and hosted the game between Cypod's departure (2001) and Torgal
  (2006), and why the 2003 reviewer distinguished "hosted (not owned)", is not known.
- **Duris3D.** Announced in April 2001 by Cypod Interactive. No later trace has been found.
- **Basternae.** Shared tools (the Magma `convzone` and its "DikuEdit: Tavril" credit) and a
  shared builder (Sniktiorg) are documented. A web-search summary attributed two further claims
  to Xangis, the Basternae author: a 2000-2001 feature "arms race" between Duris and Basternae 2,
  and a legal copy of Duris code and areas given by Cython. Neither could be confirmed at a
  primary source, and neither is used above.
- **Usenet.** Three rec.games.mud.diku threads would settle the 1995-1998 details: the first
  reference to Duris (20 March 1996), "Duris/Basternae/Ciannech Rumors", and "The Return of
  Sojourn" (December 1998). Google Groups refused every request during this research (HTTP 429).
- **Tavril and durisEdit.** The game credits Tavril as the editor's creator; the editor's license
  names Michael Glosenger. They may be the same person, but no source says so.
- **Arih.** The November 2025 credits block naming Arih was committed by resakse, and an
  `src/specs.arih.c` ("professor arih … a chaotic trickster mob loaded only by gods") existed until
  January 2026. Whether Arih is resakse's in-game name is not stated anywhere.
- **The official code after 2017.** The official game's changes from 2018 to 2026 are not in any
  public repository.

## Sources

**This repository** (paths as of October 2026):

- `lib/information/credits`, `credits_2006`, `credits_2008`, `credits_2009`, `credits_2009_1`,
  `credits_2017`: zone builders, the Sojourn, Old Duris and Current Duris rosters, and the
  copyright lines.
- `lib/information/wizlist`, `wizlista`, `wizlist.tmp`, and the wizlist's Git history
  (`7de1eab70`, `a29ba0559`, `a09a7cb3e`, `f4f903133`).
- `lib/information/oldnews` (March-April 1998); `lib/information/news` at `0b1903dbc` (the 2008
  wipe overview) and at `2a79fe583` (2 November 2025); `lib/information/greeting`, `motd`, `faq`;
  `lib/information/help_index` (racewars, frags, guild, kvark, kenon, tolm, coder, zone god,
  immortals, hardcore, kingdom); `lib/misc/lookup.zon`.
- Source headers and comments: `src/core/structs.h`, `src/core/defines.h`, `src/core/files.h`,
  `src/core/files.c`, `src/classes/memorize.c`, `src/classes/bard.c`, `src/classes/psionics.c`,
  `src/magic/affects.c`, `src/guild/guild.c`, `src/specs/specs.verzanan.c`,
  `src/specs/specs.halfcut.c`, `src/net/editor.c`, `src/item/storage_lockers.h`,
  `src/core/smoke.c`, `src/mob/name_gen.c`, `src/world/outposts.c`, `src/magic/magic.c`
  (`pleasantry()`), `areas/de/license.txt`, `areas/de/de.doc`.
- Git history from `4e5f49ef1` (2005-10-09) to the present. Notable commits: `91dae8f5a`
  (durismud.net), the undead-race removal (2006-03-24), `b9b630686` (wipe-2008 branch),
  `be8dd5166` and `642da5400` (source and areas added), `98dac76eb` (Tharnadia replaces WH),
  `49df21a02` (pwipe 2012-04-14), `94ab06371` (shutdown pwipe), `591d6cbb8` (the last 2017
  commit), `2a79fe583` (Arih credits), `e1357a30a` (the 2026 divergence).
- [CREDITS.md](CREDITS.md) and [COMMUNITY_DURIS_TRACKING.md](COMMUNITY_DURIS_TRACKING.md).

**Archived websites** (Internet Archive Wayback Machine):

- duris.org, February 1998: [home](https://web.archive.org/web/19980207003208/http://www.duris.org:80/),
  [wizlist](https://web.archive.org/web/19980207003434/http://www.duris.org:80/text/wizlist_txt.htm),
  [news 1996-1997](https://web.archive.org/web/19980207003413/http://www.duris.org:80/text/news_txt.htm),
  [lore](https://web.archive.org/web/19980207003359/http://www.duris.org:80/text/lore_txt.htm),
  [creators](https://web.archive.org/web/19980207003427/http://www.duris.org:80/text/creators_txt.htm),
  [hardware](https://web.archive.org/web/19980207003657/http://www.duris.org:80/hardware.html),
  [live status](https://web.archive.org/web/19980207003958/http://www.duris.org:80/mud_info.htm),
  [associations](https://web.archive.org/web/19980207003406/http://www.duris.org:80/text/ass_txt.htm),
  [hometowns](https://web.archive.org/web/19980207003440/http://www.duris.org:80/text/homes_txt.htm),
  [Clan BloodLust](https://web.archive.org/web/19980207003932/http://www.duris.org:80/cbl/cblabout.htm).
- duris.org, 1999-2001: [1999 home](https://web.archive.org/web/19991128094557/http://duris.org:80/),
  [overlords, Oct 2000](https://web.archive.org/web/20001009053842/http://www.duris.org:80/overlords.html),
  [implementors, Oct 2000](https://web.archive.org/web/20001009053905/http://www.duris.org:80/implementors.html),
  [Duris3D announcement, Apr 2001](https://web.archive.org/web/20010418152922/http://www.duris.org:80/).
- durismud.com: [Dec 2002](https://web.archive.org/web/20021209082631/http://www.durismud.com:80/),
  [Apr 2004](https://web.archive.org/web/20040407093450/http://www.durismud.com:80/),
  [Jan 2009](https://web.archive.org/web/20090113092831/http://www.durismud.com:80/),
  [Azoormarel speaks, 2008](https://web.archive.org/web/20080207071543/http://www.durismud.com:80/story/1.php),
  [The Downfall of the Light, 2008](https://web.archive.org/web/20080107055015/http://www.durismud.com:80/story/2.php),
  [Feb 2011](https://web.archive.org/web/20110212030237/http://durismud.com/).
- [duris.game-host.org, April 2006](https://web.archive.org/web/20060406185510/http://duris.game-host.org:80/).

**Live sites** (read 2026-10-07):

- [durismud.com/news](https://www.durismud.com/news), the official news from September 2018 to
  July 2026.
- `mud.durismud.com` ports 7777 and 2002: login banners only.
- [Community-Duris/Duris](https://github.com/Community-Duris/Duris),
  [Community-Duris/DurisMUD](https://github.com/Community-Duris/DurisMUD),
  [xanadinn/DurisMUD](https://github.com/xanadinn/DurisMUD).
- [Drevarr/DurisParser](https://github.com/Drevarr/DurisParser) and the
  [2021 wipe charts](https://drevarr.github.io/2021Charts.html).

**Listings, wikis and reviews:**

- [The Mud Connector listing](https://www.mudconnect.com/cgi-bin/search.cgi?mode=mud_listing&mud=Duris%3A+Land+of+BloodLust)
  (created December 1995; last updated 20 August 2014).
- [Mudstats](https://mudstats.com/World/DurisLandofBloodLust), which carries the Mud Connector and
  TopMUDSites reviews from 2003-2013 quoted above.
- The [Duris fan wiki on Fandom](https://duris.fandom.com/wiki/Duris_Wiki), read through its API
  (pages Duris Wiki, Credits, Racewar, Immortals, FAQ, Epic, Hometowns, Unearthed Arcana and zone
  pages).
- [DurisMUD on the MUD wiki](https://muds.fandom.com/wiki/DurisMUD).
- [Press release, 23 October 2011](https://www.newswire.com/news/duris-the-leading-diku-mud-offers-new-features-90110).

**The Sojourn and Toril side:**

- [TorilMUD on Wikipedia](https://en.wikipedia.org/wiki/TorilMUD) and its
  [talk page](https://en.wikipedia.org/wiki/Talk:TorilMUD) (Roan Art / Eileen Kortright, 2007 and
  2011).
- [Sojourn on the MUD wiki](https://muds.fandom.com/wiki/Sojourn), which quotes Shah and Romine,
  *Playing MUDs on the Internet* (Wiley, 1995), pp. 35 and 93, and Towers et al., *Yahoo! Wild
  Web Rides* (IDG Books, 1996), p. 145. The books themselves were not seen.
- ["Sojourn/Toril Pre-Wipe Timeline"](https://www.torilmud.com/phpBB3/viewtopic.php?t=28384),
  TorilMUD forums, 11 August 2020, with quotes from Shevarash.

**Basternae:** [Xangis/magma](https://github.com/Xangis/magma) and the
[ModernMUDConverter README](https://raw.githubusercontent.com/Xangis/ModernMUDConverter/master/README.md).

**Not reached:** the rec.games.mud.diku threads
["Duris/Basternae/Ciannech Rumors"](https://groups.google.com/g/rec.games.mud.diku/c/wGPNWFwRM6g),
[the 1996 split reference](https://groups.google.com/g/rec.games.mud.diku/c/74t9J-S5SiE) and
["The Return of Sojourn"](https://groups.google.com/g/rec.games.mud.diku/c/tYYOWSNDT-w), all
blocked (HTTP 429).
