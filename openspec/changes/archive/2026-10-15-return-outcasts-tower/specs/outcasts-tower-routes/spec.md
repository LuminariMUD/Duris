## ADDED Requirements

### Requirement: Good Continent surface access
Outcasts Tower SHALL connect through `546861 N -> 11300` and `11300 S -> 546861`
on the Good Continent south of Kimordril. The old EC entrance SHALL be removed.

#### Scenario: Ordinary player enters and returns
- **WHEN** a player walks north from 546861 and south from 11300
- **THEN** the player reaches 11300 and returns to 546861 without staff movement bypass
- **AND** 546861 is on loaded GC at (61,117), south of Kimordril at (61,109)

### Requirement: Coherent map footprints
The new marker at 546461 SHALL have no ordinary incoming map exit. The vacated
615849 footprint SHALL have hill terrain and reciprocal cardinal grid exits.

#### Scenario: Surrounding travel
- **WHEN** a player traverses the old site and walks around the new footprint
- **THEN** all intended map routes remain usable without entering an isolated marker
- **AND** 616249 north reaches 615849 rather than the tower
- **AND** the existing mountain at 615449 still rejects ordinary walking north

### Requirement: Preserve existing progression and secondary access
The relocation SHALL preserve `11348 N -> 30172` and `30172 S -> 11348`, tower
resets and interior exits, and Homestead and Turolopolis/Zoo content.

#### Scenario: Reset and restart
- **WHEN** the development world resets and restarts
- **THEN** both surface and secondary exit pairs remain loaded and traversable
- **AND** no new dangling exits or one-way traps are introduced
