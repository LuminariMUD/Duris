## Context

Misty's sole ordinary external pair is `638825 W <-> 15000 E`. Grounded cliff
trail 15015 is reached before the rope bridge through 15001, 15006..15014. It
has no fall chance, door reset, or down exit. Its existing east/south trail exits
continue unchanged. Selecting a trail here avoids the falling bridge and shaft
rooms and does not provide a shortcut into the locked pyramid.

## Goals / Non-Goals

Provide ordinary two-way passage into the actual Underdark and back to the
surface. Preserve all existing progression, identities, exits, and accepted
no-change areas. Do not create native movement logic, connector rooms, doors,
keys, or reset machinery when two authored open exits suffice.

## Decisions

Use `15015 D <-> 834025 U`. The UD endpoint is a low-ceiling tunnel at (25,335)
in the grid based at 700000, width 400. It has no up exit and connects through
833625 and 834026 to the surrounding tunnel network. Source traversal reaches
thousands of non-mountain/non-slime/non-air UD cells and multiple area entrances;
this is an existing network, not an isolated numeric counterpart of the surface.

Describe a long, winding stair cut into the cliff and bedrock. Both exits have
zero door flags and require no key. A human on foot can fit the existing low
ceiling; keep that ordinary terrain constraint. Confirm actual light/vision,
movement, map section, and return behavior in a disposable world before editing.

## Risks / Trade-offs

The additional route intentionally connects Khomani-Khan to the Underdark.
Adding it before the bridge preserves the bridge/fall/pyramid progression.
Compare zones 150 and 7000 against baseline: the expected entrance lists gain
15015 and 834025 respectively, with no new structural findings. Reuse valid
earlier relocation evidence; repeat unchanged routes once and the new path
through reset/restart, rather than retesting unrelated terrain four times.

## Migration Plan

Regenerate and boot only development data, walk surface-to-UD and back, check
the immediate UD network, resets and restart, then publish the final stacked PR.
Reverting the two room edits removes the passage without changing saved identities.
