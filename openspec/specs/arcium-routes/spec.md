# arcium-routes Specification

## Purpose
Place Arcium on GC northwest of Evermeet, move Homestead to Turopolis's vacated
site, and move Turopolis to the Eagle Ridge Delta while preserving progression.

## Requirements

### Requirement: Two Good Continent approaches
Arcium SHALL connect through `517246 W <-> 85700 E` and `517645 N <-> 85700 S`,
replacing Homestead at map marker `517245`. Both approaches SHALL be GC in the
Evermeet woodlands. Neither `516444`/`516843` nor the former UC approaches at
`591773`/`592172` SHALL enter Arcium.

#### Scenario: Enter and leave through either approach
- **WHEN** an ordinary player walks each new entrance and its return
- **THEN** the expected rooms are reached without staff movement bypass
- **AND** loaded continent and surface grid coordinates establish the required placement

### Requirement: Relocate Homestead and Turopolis with coherent map travel
Homestead SHALL use marker `548052` and `548452 N <-> 35800 S`, replacing
Turopolis's former surface entrance. Homestead SHALL have no east exit to its
former location. Turopolis SHALL use marker `584445` and
`584845 N <-> 7102 S`. Its Zoo route `7123 W <-> 53000 E` SHALL remain unchanged.
All three markers SHALL have accurate zone labels and no ordinary incoming map
exit. Vacated Arcium footprint `516443` and the previously restored `591772`
SHALL be hills with reciprocal cardinal grid edges.

#### Scenario: Old site and surrounding map
- **WHEN** a player walks the vacated approaches and around the new sites
- **THEN** the intended ordinary routes remain usable
- **AND** the existing mountains retain their ordinary movement barriers
- **AND** Homestead and Turopolis each have their specified entrance and return
- **AND** the Zoo route remains usable

### Requirement: Preserve existing progression
The relocations SHALL preserve room identities, interior exits, flags, resets,
quests, and unrelated secondary connections in all three zones.

#### Scenario: Zone reset and clean restart
- **WHEN** the world resets and restarts
- **THEN** all four surface entrance pairs remain loaded and traversable
- **AND** no new zcheck finding, dangling exit, or one-way trap is introduced
