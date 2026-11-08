# Duris protected door movement bug explained

**Some combat abilities can push people through a door that ordinary movement correctly treats as impassable.** This can matter for access to protected rooms and for getting stuck behind a door.

The problem is confirmed in local executable tests of the ability code. Its frequency on the live game has not been measured.

# What the door rule means

Passdoor is the magical ability to pass through some closed doors. Effects such as ethereal form and shadow projection grant it.

Ordinary walking still refuses a door when all three things are true: the door is **closed**, **locked**, and **pickproof**. Pickproof means a thief cannot pick its lock. The game also uses that combination to stop passdoor movement.

A locked door that can be picked, or a pickproof door that is unlocked, can still allow passdoor movement.

# What goes wrong

Imagine two rooms separated by one of those protected doors. You have passdoor magic active. Trying to walk through the door fails, as intended.

A successful Tempest knockback can nevertheless throw you into the other room. The ability checks the doorway differently and then moves you directly.

The same problem appears in:

- Tempest knockback.
- A nexus guardian energy burst.
- A conjured golem throwing a small opponent.
- The knockback branch used by Judgement.
- The ram outcome of lance charge.

Lance charge has an extra problem: it checks the charger when choosing an exit, then moves both people. In a local test, a charger with passdoor carried a victim without passdoor through the protected door.

# What players could experience

A character could enter a room whose door is meant to prevent that movement. Someone could be thrown away from their group, into danger, or behind a door they cannot walk back through. These are consequences the code permits; they are not claims about recorded player incidents.

Ordinary walking still blocks the protected door. Fleeing, currents, and the inspected NPC walking routes also go through the normal movement checks. For the four single-target knockbacks above, a character without passdoor stayed on the original side of a closed door in the tests.

The bypass also still respects the secret-exit, blocked-wall, castle-wall, and spell-wall checks tested here. It does not open every barrier.

# What should happen next

Treat this as a gameplay correctness bug worth fixing. The trigger needs a particular door state and combat outcome, but the consequences can be disruptive: crossing the wrong door can change a fight or access to a room.

Keep ordinary movement and knockback consistent about protected doors. For lance charge, check the door permission of everyone being moved and decide how the mount should travel.

The game already has a safer movement routine used by other combat abilities. Reuse it where its behavior fits. Changing the shared exit-check shortcut everywhere would also change scanning, listening, and other unrelated behavior.

The builder checker called zcheck describes the ordinary walking rule correctly. The investigation did not find the reported disagreement in its door rule.

# Status and further detail

This is an investigation, with no gameplay fix or deployment. The issue remains open for implementation and testing in a running game.

[GitHub issue 752](https://github.com/LuminariMUD/Duris/issues/752) contains the detailed findings and links to the technical report. The source examined was the November 8 2026 master snapshot `dd31e9f2d`.

