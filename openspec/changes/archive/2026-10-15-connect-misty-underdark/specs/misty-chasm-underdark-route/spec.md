## ADDED Requirements

### Requirement: Ordinary two-way Underdark passage
Misty Chasm SHALL connect `15015 D -> 834025` and `834025 U -> 15015` through
an open stair passage requiring no key, flight, swim, or staff movement bypass.
The existing low-ceiling tunnel's ordinary terrain constraints SHALL remain.

#### Scenario: Surface to tunnel and back
- **WHEN** a human on foot enters from 638825, follows the forest trail to 15015,
  descends to 834025, walks the adjoining UD tunnel network, and returns
- **THEN** each intended room is reached, and the player can return to 638825
- **AND** the route needs no fall, secret door, locked door, or staff-only movement

### Requirement: Preserve existing entrances and progression
The change SHALL retain `638825 W <-> 15000 E`, both existing exits of 15015,
all room identities, bridge and shaft falls, pyramid locks, resets, and quests.

#### Scenario: Existing area remains intact
- **WHEN** the authored and generated world are checked
- **THEN** only the new reciprocal passage and its descriptions differ in the two endpoint records
- **AND** no existing exit is replaced or removed

### Requirement: Durable loaded routes
The new passage SHALL remain loaded and traversable after zone reset and clean
restart, without new zcheck findings or one-way traps.

#### Scenario: Reset and restart
- **WHEN** zones 150 and 7000 reset and the world restarts
- **THEN** ordinary surface-to-UD and return journeys still pass
- **AND** diagnostics differ from baseline only by the intended new entrances
