# Gameplay scenarios

Plain-text scripts that drive the real server. Each one runs against a disposable
MariaDB schema, a private copy of the minimal world (`areas_mini/`) and a freshly
booted server. After the scenario, the server must shut down cleanly and its logs
must hold no crash or sanitizer report.

```sh
make -C src                                   # builds bin/server/dms_new
scripts/mudtest smoke                         # the built-in smoke scenario
scripts/mudtest scenario tests/scenarios/x.scn [more.scn...]
```

`scripts/mudtest` needs Docker for the disposable database.

## Soak

```sh
make world                                     # the soak boots the full world
scripts/build-san.sh -j4                       # ASan/UBSan build at bin/server/dms_san
DURIS_SERVER_BINARY=bin/server/dms_san scripts/mudtest soak --minutes 60 --bots 8
```

The soak boots the full world, creates one level-50, high-HP bot per class, and lets them
wander, fight whatever they find, loot, wear gear, rest and reconnect. A staff character runs a
copyover halfway through. The run fails if the server dies, does not shut down cleanly, or its
output holds a sanitizer or crash report. `--keep DIR` saves the server output and logs.

## Writing one

```
# comments start with '#'
staff  Gmname                                   level-62 actor
actor  Name class=MONK spec=WAYOFSNAKE level=40 skill=SKILL_BASH:100
Name> command        send a command and wait until it has finished
Name? text           text has reached Name since Name's last check
Name! text           text has NOT reached Name since Name's last check
restart              save everyone, stop, boot again, log everyone back in
```

- Declare every actor before the first step. Names are one capitalised word of
  3–12 letters. `class`, `spec` and `skill` take the names from `src/core/defines.h`,
  `src/core/structs.h` and `src/magic/spells.h` (without the `CLASS_`/`SPEC_` prefix).
- `?` waits up to 15 seconds. `!` first sends `score` so anything in flight has
  arrived, then checks. Both look only at output since that actor's previous check.
- `!` fails on any earlier mention too, such as a cast message naming the actor. Consume
  expected messages with a `?` first (`Watcher? fades out of existence`), then check.
- To reproduce a bug report, write the steps a player took, then `?`/`!` lines for
  what should and should not appear. A scenario that fails before a fix and passes
  after it is the regression test for that fix.
