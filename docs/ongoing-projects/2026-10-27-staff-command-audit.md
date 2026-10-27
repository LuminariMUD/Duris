# Local staff-command audit — 2026-10-27

Status: **local command sweep complete**. Production was not changed. The
substantive behavior of every argument form was not exhaustively qualified.

The checkout was clean on `master` at `b24e874c58924f9cde149371ab2cdd78bb2f66d9`,
matching `origin/master` after fetching. The existing local MariaDB-primary MUD
was running on port 7777, and the configured staff character had level 62.

## Scope and method

The source-registered staff commands were inventoried, including granted
commands omitted from `wizhelp`, and each was sent through the real command
interpreter as the configured staff character. A usage response alone does not
establish that the substantive operation works. Command inputs and responses
were recorded, and fixture-dependent operations were followed up separately.

The current master build ran under AddressSanitizer and UndefinedBehaviorSanitizer
against an isolated local database and copied full-world runtime. The clone's
database user could not read `duris_dev`; external integrations were disabled.
Diagnostics, command transcripts, and memory samples are owner-only outside
Git. ASan stacks identified the crash directly, so GDB was unnecessary.
Copyover was not exercised; it would replace the sanitizer binary.

## Registered command ledger

The names below are the complete source-registered staff command surface for
this revision. Every name has a `dispatched` result in the private command
journal at `bin/tests/staff-command-audit/results.ndjson`. Some first-pass
responses were syntax, permission, or missing-target guards; follow-up
actions are described below and in that journal.

- Level 0 (1): grant

- Level 57 (21): approve, at, decline, echo, finger, goto, gshout, knock, makeguide, map, mreport, newbie, poofin, poofout, ptell, release, silence, snowball, title, users, wizmsg

- Level 58 (24): asclist, cheat, divineboon, eqrate, fly, hlist, hlqlist, lookup, mlist, olist, qinfo, qlist, qref, questwhere, qview, rename, rlist, transfer, where, which, whitelist, wizhelp, zcheck, zlist

- Level 59 (27): account, clone, difficulty, echoa, echoe, echog, echot, echou, echoz, freeze, levels, load, newbsa, newbsu, pleasant, properties, pulse, purge, secret, setattr, sethome, teleport, tranquilize, trapremove, trapset, whois, ztestdesc

- Level 60 (25): advance, allow, ban, cd, demote, extractlink, force, givepet, inroom, instacast, makeexit, offlinemsg, page, punish, reinitphys, reroll, restore, sacrifice, setbit, snoop, storage, string, swim, wizconnect, zreset

- Level 61 (23): affectpurge, deathobj, debug, depiss, ingame, invite, ok, petition_block, proclib, randobj, redis, repiss, resetspec, revoke, shutdow, shutdown, statistic, supervise, switch, terminate, test, uninvite, wizlock

- Level 62 (4): newchar, resetarti, rwc, sql

Separately tested staff-only branches of ordinary commands (41) include
artifacts staff all, artifacts staff player, artifacts staff hunt, artifacts poof help, artifacts swap help, artifacts timer help, artifacts clear help, artifacts files help, artifacts reset help, stat game, stat room, stat zone, stat object, stat mobile, stat skill, stat race, stat pvp, stat damage, boon list, divineclaim list, poll all, poll create, poll close, nexus staff list, nexus reload, nexus reset, mine reset, mine load, mine purge, stat world, stat shop, stat quest, stat trap, divineclaim grant, divineclaim remove, poll create and submit, artifacts timer set, artifacts poof, artifacts swap, artifacts clear, artifacts reset.

## Findings and coverage

The source inventory identifies 125 distinct staff command names: 124 above
mortal level and the grantable level-zero `grant`. **All 125 were dispatched**
through the real interpreter as the configured level-62 staff character on the
observed full-world server. Another **41 of 41** staff-only branches of
otherwise mortal-level commands were exercised, including the poll wizard's
cancel, create, and close paths. Sixty-three additional follow-up command labels
checked paging, outdoor flight, live peer targeting, saving, and the repaired
template path. These are command invocations, not exhaustive coverage of every
argument combination or mutation. A syntax or guard response is identified
as such below.

1. **`ingame` buffer overflow; fixed locally.** The old implementation
   multiplied percent signs for each `%p` inside a fixed stack buffer without
   checking its remaining space. An isolated build of the unchanged handler
   reported an AddressSanitizer stack-buffer-overflow during template
   construction, before any target descriptor was needed. `inroom` had a
   related unbounded input copy and passed raw user percent text through a
   printf-family formatter. Both now use one bounded, literal target-token
   substitution function. A focused ASan/UBSan test passes repeated target
   tokens and preserves unrelated percent text literally. With a separate
   connected player, `ingame` substituted that player's name and `inroom`
   substituted room occupants; both kept unrelated percent text literal.

2. **`hlist` is a reserved no-op, not a runtime failure.** Its current handler
   is empty and the help entry explicitly calls it a placeholder. The command
   was dispatched, and no functional behavior was claimed.

3. **`test oceanpvp` emits a contradictory error.** The old observed server
   returned both `Ocean PvP state: No.` and `Invalid keyword.` for one command.
   The handler was missing a `return` after the valid branch; that return is
   added locally. The rebuilt server returned only `Ocean PvP state: No.`.

4. **Autonomous lich event caused a heap buffer overflow.** After the first
   three staff probes, the isolated server aborted under AddressSanitizer.
   The first relevant frames were `IS_OUTDOORS` → `mana_regen` → `StartRegen` →
   `raise_undead` → `spell_raise_lich`; the read occurred before the allocated
   `world` array. `raise_undead` started mana regeneration before placing the
   new undead in a room, so its room index was `NOWHERE`. The local fix starts
   regeneration after `char_to_room` and makes `IS_OUTDOORS` return false for an
   invalid room index. The focused outdoor-bounds test and existing PSP regen
   test pass under ASan/UBSan. The rebuilt full-world server completed the
   125-command sweep and additional branches without repeating that sanitizer
   error; it remains under observation.

5. **`page` was advertised at a lower level than it allows.** The command
   registry required level 58, but its handler rejects anyone below level 60;
   the help entry also says level 60. The local registry now requires level 60
   so `wizhelp` and the interpreter agree with the actual permission check.
   A disposable level-58 player was denied `page info status`, while the
   level-62 staff character received a ready cache on the rebuilt server.

6. **`artifacts hunt` failed silently when a legacy player directory was
   absent.** `artifacts hunt v` returned no text on the clone, while its status
   log reported that the directory could not be opened and incorrectly named
   the artifact directory. The local fix gives a clear no-saves response for a
   missing initial directory and names the actual player-save path for other
   failures. The rebuilt server returned `No legacy player saves for initial
   'v'.` for that same probe.

7. **Several successful world-control commands gave no direct confirmation.**
   `nexus reload 1`, `nexus reset`, and `mine reset/load/purge map` produced only
   a prompt, while the staff log recorded each operation. The local fix adds
   explicit success, request, and failure responses, without claiming a mine
   load completed when the loader supplies no result. The rebuilt server
   acknowledged all five operations, and the staff log recorded them.

8. **`stat world` reported only `broken, leave me alone.`** The world-wide exit
   implementation is disabled in source. The local fix replaces that message
   with the available `zlist`, `zcheck <zone>`, and `rlist` inspection paths and
   removes the dead commented implementation. This clarifies the limitation;
   it does not restore a world-wide exit report.

9. **Bare `account` had an empty usage string.** The initial command returned
   only a prompt. Source review found `ACCOUNT_SYNTAX` defined as an empty
   string; only `account i <online player>` is implemented, while lookup and
   edit branches report unsupported. The local fix provides useful syntax and
   corrects the help entry. The rebuilt isolated server returned the new
   syntax and showed account information for the staff character. The primary
   local server also served the corrected `help account` after atomic import.

10. **`zlist` undercounted the loaded zones by one.** The full-world boot
    reported 353 zones, but the staff listing's footer said 352. The footer
    printed `top_of_zone_table`, which is the last zero-based index; the local
    fix prints that value plus one. The rebuilt listing returned 353.

11. **`stat quest` rendered goals as control bytes and could index before the
    quest table.** With Gynaeros, the old diagnostic printed a numeric goal
    type as an unprintable character and a null completion message as
    `(null)`. Source review found that `find_quester_id` returns `-1` for an
    ordinary mobile, but this branch indexed `quest_index[qi]` without a
    guard. The local fix routes `stat quest` to the existing guarded `qview`
    renderer. The rebuilt server returned `That mobile has no quests.` for an
    ordinary pygmy and rendered Gynaeros identically to `qview`, without
    control bytes.

The read-only `zcheck 3000` report had **0 high and 46 low findings**: 23 rooms
unreachable by its exit-only graph and 23 non-reciprocal ordinary exits. Its
own scope excludes portal objects and compiled triggers, which are used by
this zone, so these are route-review leads rather than proven inaccessible
rooms. No authored world data was changed on the strength of this report.

The full command transcript, sanitizer output, and memory samples remain in
the private local audit directory. The first observed run aborted at its first
relevant ASan stack. Repaired full-world runs completed the sweep and target
journeys without another ASan/UBSan access error. At clean shutdown, the broad
run retained 27,783,650 bytes in 147,084 allocations; the shorter response
run retained 26,894,231 bytes in 140,890 allocations. The largest allocation
stacks are the full-world mobiles, objects, and strings kept through process
exit. These totals do not prove command-specific leaks or leak freedom. The
observed final process remains running for further local testing.

The primary local service is running the patched `bin/server/dms` on port
7777 (SHA-256 `39a879995471b1a9dee6a104dafd1d85fadac9f34f403006ce7f1b98ed93defc`).
It passed runtime compatibility, entered the game loop once, and completed a
Veridian login, world commands, staff help/command checks, save, and clean
logout. The full-world ASan/UBSan process remains on isolated port 45341 with
memory sampling. The local help import staged 1,416 entries with zero errors.

Focused verification passed: `test_staff_command_template.py`,
`test_outdoors_room_bounds.py`, `test_psp_move_regen.py`,
`test_nexus_stones_empty_table.py`, `test_mining_admin_commands.py`,
`test_artifact_hunt_inspection.py`, `test_quest_staff_commands.py`, and
`test_misty_vale_zone.py`, plus normal and sanitizer builds and the source
format check. The remaining limits are functional depth beyond the recorded
probes, intentional no-op/deprecated commands, compiled zone triggers outside
`zcheck`, and process-exit world retention; none was represented as a green
functional check.
