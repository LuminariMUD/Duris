## Context

The owner selected footprint 546461 (61,116), with southern approach 546861
(61,117), seven rows south of Kimordril's approach 543661 (61,109). Coordinates
are zero-based surface grid offsets from 500000, width 400.

## Goals / Non-Goals

Move the tower's surface access to GC and keep its Underworld access. Preserve
all area IDs, resets, and interior progression. Do not relocate Homestead or
Turolopolis, change engine movement, or deploy production.

## Decisions

Use the existing occupied map-cell convention: a named marker at 546461 with no
ordinary incoming map exits. Redirect the southern edge to the actual entrance;
remove inward edges from 546061/546460/546462. Keep surrounding grid routes.

Restore old footprint 615849 to DarkPeak hills matching its east/west neighbors,
restore their missing inward edges, and return 616249 N to the footprint. Its
sector-0 Waters of the Abyss placeholder is not usable terrain to retain.
The existing mountain 615449 to its north remains impassable to an ordinary
walker; retain its authored edge and test the terrain rejection, alongside
successful east/west/south traversal. Do not flatten the peak to satisfy a test.

Reuse existing world generation, parsing, isolated authority, and character
journey helpers. Native assignment of 11300 as a ship room is disabled code.

## Risks / Trade-offs

The retained Underworld route now connects GC to the same Underworld network;
this is an explicit owner decision. Check the loaded continent, all entrance
directions, old-site walking, resets, and zcheck deltas before publication.

## Migration Plan

Regenerate and boot only a disposable development world. Publish authored sources
for review; production rollout remains separate. Reverting the authored diff and
regenerating restores the old placement without changing persisted identities.
