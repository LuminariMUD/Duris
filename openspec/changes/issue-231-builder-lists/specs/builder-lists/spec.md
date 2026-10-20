# Builder lists

## Purpose

Let staff inspect rooms and prototypes with predictable work and output, without
creating entities or reading persistence while listing.

## ADDED Requirements

### Requirement: Checked scope selection
The commands SHALL default to the standing zone, accept exact VNUMs and inclusive
normalized ranges across zones, and accept `zone <public-number>` optionally
intersected with an exact VNUM or range. They MUST reject malformed, signed,
overflowing, missing, unknown-zone, or extra arguments before listing.

#### Scenario: Public identity and location
- **WHEN** a bare command is issued in a valid room
- **THEN** it lists that room's zone using public zone identity
- **AND** an invalid location fails without a world fallback
- **AND** explicit VNUM searches work without a current room

#### Scenario: Explicit syntax
- **WHEN** any command receives an exact VNUM, reversed range, or zone intersection
- **THEN** it lists only that inclusive scope and reports the scope
- **AND** invalid syntax produces useful command-specific usage

### Requirement: Prototype ownership
Mobile and object zone membership SHALL use numeric partitions from zero through
the first zone top, then above the previous top through the current top. It MUST
include unloaded prototypes regardless of reset references or instance location.

#### Scenario: Cross-zone resets and wide zones
- **WHEN** a prototype is reset by another zone or a zone spans several hundreds
- **THEN** listing follows numeric ownership and explains it in usage

### Requirement: Bounded work and truthful continuation
Each command SHALL render at most 500 entries and probe at most one additional
match. Traversal MUST use existing sorted indices and zone bounds, without a
whole-world scan or total count. Output MUST report the shown count and empty
results, and truncation MUST provide a valid remaining range preserving scope.

#### Scenario: Limit boundaries
- **WHEN** a scope has 0, 1, 199, 499, 500, or more than 500 matches
- **THEN** the count is exact for rendered entries and truncation appears only above 500
- **AND** continuation includes the first unrendered VNUM and original upper bound

### Requirement: Read-only cold names
Mobile and object lists SHALL show existing shared short descriptions, current
population, and reset limit even before instantiation. Listing MUST NOT create or
extract entities, perform file/database I/O, or invoke events or special procedures.

#### Scenario: Boot and ordinary loading
- **WHEN** normal or mini indices load sentinel or EOF-terminated files
- **THEN** real records have shared names before commands run, empty names are safe,
  ordinary loads reuse names and original positions, and cleanup is safe

### Requirement: Safe output and access
The commands SHALL keep IMMORTAL registration, reject NPC handlers, require paging
for results, and allow help without paging. Rows MUST have bounded ANSI-aware
single-line names; rooms MUST show public zone, VNUM, name and safe sector text.

#### Scenario: Output edge cases
- **WHEN** names are empty, long, colorized, or multiline, or a sector is invalid
- **THEN** rows stay bounded and readable with a clear empty/unknown placeholder
- **AND** 500 rows and footer fit the existing pager

#### Scenario: Access
- **WHEN** a mortal attempts a list, or staff request help with paging off
- **THEN** the mortal cannot invoke the handler and staff can read usage
