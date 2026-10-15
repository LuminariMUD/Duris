## Why

Issue #37 requests a usable Underdark connection for the Chasm of the Misty Vale
(zone 150). The owner accepted a two-way passage while retaining the area's
Khomani-Khan surface entrance and existing progression.

## What Changes

- Connect grounded cliff trail 15015 down to existing Underdark tunnel 834025,
  with an up return, describing a long stair passage through the rock.
- Preserve the surface pair, bridge, falling rooms, shafts, and pyramid locks.
- Extend the existing route regression and disposable mortal journey.

## Capabilities

### New Capabilities
- `misty-chasm-underdark-route`: Two-way Underdark access and preserved surface access.

### Modified Capabilities
None.

## Impact

Only `mist_chasm.wld` and `underdark.wld` need content changes. Tests, OpenSpec,
and the continuation plan share the preceding #103/#104 stack. No new rooms,
zone boundaries, resets, procs, migrations, or production operations.
