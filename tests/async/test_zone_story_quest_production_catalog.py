#!/usr/bin/env python3

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile


ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "zone_story_quest_catalog.py"
spec = importlib.util.spec_from_file_location("zone_story_quest_catalog", SCRIPT)
catalog_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(catalog_module)

catalog = catalog_module.production_catalog(ROOT)
assert catalog["source"]["kind"] == "legacy_static_qst"
assert catalog["source"]["area_list"] == "areas/AREA"
assert catalog["source"]["excludes"] == ["bartender_random_world_quests"]
# Counted from the area files, apart from the catalog's parser: one definition for each
# distinct block, a Q or QA block under a giver keyed by its goal lines and whether it
# disappears (blocks alike are one accomplishment), and every giver has one. A parser that
# skipped blocks would fall short here; new quests count on both sides.
contracts = set()
for path in catalog_module.active_quest_files(ROOT):
    giver, block = None, None
    for line in path.read_text(errors="replace").splitlines() + ["$"]:
        line = line.strip()
        ends = line == "$" or line in {"Q", "QA"} or (
            line.startswith("#") and line[1:].lstrip("-").isdigit())
        if ends and block is not None:
            contracts.add((giver, tuple(sorted(block))))
            block = None
        if line.startswith("#") and line[1:].lstrip("-").isdigit():
            giver = int(line[1:])
        elif line == "$":
            giver = None
        elif line in {"Q", "QA"} and giver is not None:
            block = []
        elif block is not None and (line == "D" or line.split()[:1] in (["G"], ["R"])):
            block.append(" ".join(line.split()))
assert len(catalog["definitions"]) == len(contracts), (len(catalog["definitions"]), len(contracts))
assert {item["giver_vnum"] for item in catalog["definitions"]} == {giver for giver, _ in contracts}
assert all(item["zone_number"] > 0 for item in catalog["definitions"])
assert all(item["source_system"] == "zone_story" for item in catalog["definitions"])
assert all(item["repeatable"] is True for item in catalog["definitions"])
assert len({item["definition_id"] for item in catalog["definitions"]}) == len(catalog["definitions"])
# Givers past their area's first hundred vnums (Winterhaven) or its top room (the Tower of
# Darkness) belong to that area, not to a zone number no area has.
zone_by_giver = {item["giver_vnum"]: item["zone_number"] for item in catalog["definitions"]}
assert zone_by_giver[55100] == 550
assert zone_by_giver[134146] == 1340

with tempfile.TemporaryDirectory(prefix="duris-zone-story-production-catalog-") as temporary:
    output = pathlib.Path(temporary) / "catalog.json"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source-root",
            str(ROOT),
            "--production-output",
            str(output),
            "--check",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["source"]["fingerprint_sha256"] == catalog["source"]["fingerprint_sha256"]
    assert len(written["definitions"]) == len(catalog["definitions"])

print("zone-story production catalog coverage regression passed")
