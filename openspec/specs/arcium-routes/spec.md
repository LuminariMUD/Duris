# arcium-routes Specification

## Purpose
Keep both Arcium approaches on GC northwest of Evermeet while preserving
Homestead, existing progression, and travel at the vacated site.

## Requirements

### Requirement: Two Good Continent approaches
Arcium SHALL connect through `516444 W <-> 85700 E` and `516843 N <-> 85700 S`.
Both approaches SHALL be GC and northwest of active Evermeet woodland at 517246.
The former UC entrances at 591773 and 592172 SHALL no longer enter Arcium.

#### Scenario: Enter and leave through either approach
- **WHEN** an ordinary player walks each new entrance and its return
- **THEN** the expected rooms are reached without staff movement bypass
- **AND** loaded continent and surface grid coordinates establish the required placement

### Requirement: Preserve map travel and Homestead
The new marker 516443 SHALL have no ordinary incoming map exit. The old footprint
591772 SHALL be hills with reciprocal cardinal grid edges. Homestead's footprint
517245 and approaches 517246/517645 SHALL remain unchanged.

#### Scenario: Old site and surrounding map
- **WHEN** a player walks the vacated east/south approaches and around the new site
- **THEN** the intended ordinary routes remain usable
- **AND** the existing north/west mountains retain their ordinary movement barriers
- **AND** both Homestead entrance pairs remain usable

### Requirement: Preserve Arcium progression
The relocation SHALL preserve all Arcium room identities, interior exits, flags,
resets, quests, and all accepted no-change areas.

#### Scenario: Zone reset and clean restart
- **WHEN** the world resets and restarts
- **THEN** both new entrance pairs remain loaded and traversable
- **AND** no new zcheck finding, dangling exit, or one-way trap is introduced
