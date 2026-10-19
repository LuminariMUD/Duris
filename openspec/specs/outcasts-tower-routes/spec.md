# outcasts-tower-routes Specification

## Purpose
Place Outcasts Tower on GC south of Kimordril and Temple of Lizizania on EC south
of Torg while preserving the tower's Underworld route and coherent map travel.

## Requirements

### Requirement: Good Continent surface access
Outcasts Tower SHALL connect through `551667 N -> 11300` and `11300 S -> 551667`
at marker `551267` on the Good Continent south of Kimordril, replacing Lizizania's
surface entrance. The superseded entrance from `546861` SHALL be removed.

#### Scenario: Ordinary player enters and returns
- **WHEN** a player walks north from 551667 and south from 11300
- **THEN** the player reaches 11300 and returns to 551667 without staff movement bypass
- **AND** 551667 is on loaded GC at (67,129), south of Kimordril at (61,109)

### Requirement: Coherent map footprints and Lizizania access
The vacated footprint `546461` SHALL have hill terrain and reciprocal cardinal
grid exits. Lizizania SHALL use marker `615849` and
`616249 N <-> 9288 S` on EC south of Torg. Both active markers SHALL have accurate
zone labels and no ordinary incoming map exit. Lizizania SHALL no longer return
to `551667`.

#### Scenario: Surrounding travel
- **WHEN** a player traverses the old site and walks around the new footprints
- **THEN** all intended map routes remain usable without entering an isolated marker
- **AND** 546861 north reaches the restored hills at 546461
- **AND** 616249 north reaches Lizizania at 9288 and south returns to 616249

### Requirement: Preserve existing progression and secondary access
The relocation SHALL preserve `11348 N -> 30172` and `30172 S -> 11348`, tower
resets and interior exits, and Lizizania's internal routes, resets, and quests.

#### Scenario: Reset and restart
- **WHEN** the development world resets and restarts
- **THEN** both zones' surface pairs and the tower's secondary pair remain loaded and traversable
- **AND** no new dangling exits or one-way traps are introduced
