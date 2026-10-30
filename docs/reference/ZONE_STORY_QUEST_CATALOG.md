# Production zone-story quest catalog

The production catalog is generated from the active static quest sources listed
in `areas/AREA`, using the same source boundary as `areas/src/qst/make_qst.c`.
The checked-in snapshot is [ZONE_STORY_QUEST_PRODUCTION_CATALOG.json](ZONE_STORY_QUEST_PRODUCTION_CATALOG.json)
and contains 2,791 eligible repeatable quest definitions, regenerated from the
current area sources on 2026-10-30. It is the offline report's default input;
the runtime builds its catalog from booted quests instead. Keep the snapshot
in step with content edits using the comparison below.

Each legacy `Q` completion block receives a stable definition identity derived
from its giver VNUM and canonical give/receive/disappear contract. Prose changes
therefore do not silently reset a character's distinct completion credit.
A goal, reward, or disappearance change changes the definition identity itself.
Multiple blocks with the same giver and canonical contract are alternative
prose/turn-in routes for one accomplishment and are deduplicated, so reordering
them cannot inflate the denominator. The compiled catalog revision is `1` in
`zone_story_quest_production.h`; content edits do not bump it automatically.
Changing that revision requires a separately designed stored-state migration:
the current SQL and flatfile loaders reject another catalog revision, and this
subsystem does not ship a cross-revision migration/retention tool.

The runtime catalog is built from the quest index immediately after
`boot_the_quests()` and uses the same identity and zone-number rules. A
production definition is active, repeatable, has a stable completion key, and
matches the booted catalog revision. Counting eligibility uses active,
eligible-for-zone-completion, zone, and revision fields; catalog validation
also requires repeatable definitions in this initial scope. The denominator for
a zone is the current eligible catalog, never the number of completion rows.
Catalog membership does not prove that all required/reward objects exist or
that a quest is currently solvable; that requires content/gameplay validation.

Bartender/random world quests are intentionally excluded. They are generated
assigned-run content with different reset and reward semantics; they are not
static zone/story definitions and must not inflate a zone's completion
percentage.

Run the following commands from the repository root. Validate the current area
sources without changing the snapshot:

```text
python3 scripts/zone_story_quest_catalog.py \
  --source-root . \
  --content-revision 1 \
  --check
```

To deliberately regenerate the snapshot after reviewing content/revision changes,
add `--production-output docs/reference/ZONE_STORY_QUEST_PRODUCTION_CATALOG.json`.
That option writes the file even with `--check`; `--check` controls the validation
exit status, not whether output is written. Source validation does not compare
the checked-in snapshot for equality with current content.

Compare the full snapshot to current sources without writing it:

```sh
python3 - <<'PY'
import json
import sys
from pathlib import Path
sys.path.insert(0, "scripts")
from zone_story_quest_catalog import production_catalog
root = Path.cwd()
snapshot = json.loads((root / "docs/reference/ZONE_STORY_QUEST_PRODUCTION_CATALOG.json").read_text())
assert snapshot == production_catalog(root), "quest snapshot differs from current sources"
print("quest snapshot matches current sources")
PY
```

Boot logs report the number of definitions and the revision. A boot with an
empty or invalid catalog fails closed for completion credit and exposes `N/A` in
the personal achievement view; it does not invent a denominator.
