# Findings: the mob log at boot (staging, 2026-10-07)

Moved here on 2026-10-08 from the clean-rebuild findings. Builders' backlog, not a server
defect. File it as a work item or dismiss it, then delete the file.

`logs/log/mob` gets the same lines at every boot, in the same volume as the run before,
all written by `src/world/db.c`:

| Lines | Message | What it is |
|---|---|---|
| 313 | `M cmd not executed <mob> <max> <room> <chance>` | A zone reset's mobile load whose percentage chance missed this time. The line records a roll, not a fault; whether it should be logged at all is a log-hygiene question. |
| 4 | `F cmd not executed <mob> <max> <room> <chance>` | The same for a follower load. |
| 58 | `FYI - no changes made to MOB: <vnum> has _RIDICULOUS_ damage. <dice> + <bonus> (<min> to <max>) check mob code, stats and racial stats.` | The damage check at load: the mobile's dice exceed the cap for its level, and the server runs it anyway. Builder data. |
| 3 | `Mob '<name>' <vnum> has extreme exp <value>.` | The experience check at load, over ten million: tiamat, aramus dreameater and aan huge dragon. Builder data. |

Suggested action: a builders' pass over the 58 damage lines and the three experience lines;
a decision on whether a missed load chance belongs in the mob log.
