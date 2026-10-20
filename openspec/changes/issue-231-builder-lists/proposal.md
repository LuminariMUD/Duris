# Proposal

## Why

Bare builder lists scan the world, mobile listing instantiates entities, and
object listing is empty. Staff need bounded, read-only inspection with cold names.

## What Changes

- Default all three lists to the standing zone and cap results at 500.
- Preserve explicit VNUM searches and add consistent checked syntax and continuation.
- **BREAKING**: `rlist zone` uses the public zone number shown by `zlist`.
- Populate existing shared short descriptions at boot; list prototypes without I/O.

## Capabilities

### New Capabilities

- `builder-lists`: staff room, mobile, and object inspection with bounded work.

### Modified Capabilities

None. This repository had no OpenSpec capability inventory before this change.

## Impact

`src/world/db.c`, `src/cmd/actinf.c`, focused executable regressions and the
[continuation plan](../../../docs/ongoing-projects/plan-builder-list-commands.md).
No schema, permissions, content, or production operations change.
